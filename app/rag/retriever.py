"""
EverGrow RAG 检索模块
从 Chroma 向量库检索与问题相关的文档
"""
import os
import re
from pathlib import Path

import chromadb
import yaml
from chromadb.config import Settings
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent.parent
STAGE_ADJACENT = {
    "幼儿期": ["学龄前"],
    "学龄前": ["幼儿期", "小学"],
    "小学": ["学龄前", "初中"],
    "初中": ["小学", "高中"],
    "高中": ["初中"],
    "通用": [],
}


def _get_embedding(text: str, api_key: str, base_url: str, model: str) -> list[float]:
    """调用 OpenAI 兼容接口获取文本的 embedding"""
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding


def _similarity_from_distance(distance: float | None) -> float:
    """将 distance 映射为 [0,1] 相似度（越大越相关）"""
    if distance is None:
        return 0.0
    return 1.0 / (1.0 + float(distance))


def _extract_keywords(question: str, max_keywords: int = 8) -> list[str]:
    """轻量关键词提取：中文片段 + 英文数字词"""
    text = question.strip()
    if not text:
        return []

    tokens: list[str] = []
    for zh in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.append(zh)
        if len(zh) >= 4:
            # 补充 2-gram，增强中文关键词召回
            for i in range(len(zh) - 1):
                tokens.append(zh[i : i + 2])
    tokens.extend(re.findall(r"[A-Za-z0-9_]{2,}", text.lower()))

    seen = set()
    uniq = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
        if len(uniq) >= max_keywords:
            break
    return uniq


def _vector_search(collection, query_embedding: list[float], stage: str | None, n_results: int) -> dict:
    query_kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if stage:
        query_kwargs["where"] = {"stage": stage}
    return collection.query(**query_kwargs)


def _keyword_search(collection, question: str, stage: str | None, limit: int) -> list[dict]:
    """关键词召回：where_document contains，作为向量召回补充"""
    keywords = _extract_keywords(question)
    if not keywords:
        return []

    score_map: dict[str, dict] = {}
    for kw in keywords:
        get_kwargs: dict = {
            "where_document": {"$contains": kw},
            "include": ["documents", "metadatas"],
            "limit": limit,
        }
        if stage:
            get_kwargs["where"] = {"stage": stage}
        try:
            res = collection.get(**get_kwargs)
        except TypeError:
            # 兼容部分 Chroma 版本不支持 get(limit=...)
            get_kwargs.pop("limit", None)
            res = collection.get(**get_kwargs)
        except Exception:
            continue

        ids = res.get("ids", []) or []
        docs = res.get("documents", []) or []
        metas = res.get("metadatas", []) or []
        for doc_id, doc, meta in zip(ids, docs, metas):
            d = score_map.setdefault(
                doc_id,
                {
                    "doc_id": doc_id,
                    "content": doc,
                    "meta": meta or {},
                    "keyword_hits": 0,
                },
            )
            d["keyword_hits"] += 1

    denom = max(1, len(keywords))
    out = []
    for row in score_map.values():
        row["keyword_score"] = min(1.0, row["keyword_hits"] / denom)
        out.append(row)
    out.sort(key=lambda x: x["keyword_score"], reverse=True)
    return out[:limit]


def _build_stage_filters(stage: str | None) -> list[str | None]:
    """stage 回退顺序：指定阶段 -> 通用 -> 相邻阶段；无 stage 时不过滤"""
    if not stage:
        return [None]
    if stage == "通用":
        return ["通用"]

    ordered = [stage, "通用", *STAGE_ADJACENT.get(stage, [])]
    seen = set()
    result: list[str | None] = []
    for s in ordered:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def search(
    question: str,
    k: int | None = None,
    stage: str | None = None,
    persist_dir: str | Path | None = None,
    collection_name: str | None = None,
) -> list[dict]:
    """
    检索与问题相关的文档。

    Args:
        question: 用户问题
        k: 返回文档数量，默认从 chroma.yml 读取
        stage: 年龄段过滤（幼儿期/学龄前/小学/初中/高中/通用），None 表示不过滤
        persist_dir: Chroma 持久化目录
        collection_name: 集合名称

    Returns:
        [{"content": str, "title": str, "source_file": str, "chroma_doc_id": str}, ...]
    """
    load_dotenv(ROOT / ".env")
    with open(ROOT / "config" / "chroma.yml", encoding="utf-8") as f:
        chroma_cfg = yaml.safe_load(f)

    persist_dir = persist_dir or ROOT / chroma_cfg.get("persist_directory", "data/chroma_db")
    collection_name = collection_name or chroma_cfg.get("collection_name", "agent")
    k = k or int(chroma_cfg.get("k", 3))
    recall_k = int(chroma_cfg.get("recall_k", max(k, 10)))
    keyword_k = int(chroma_cfg.get("keyword_k", recall_k))
    rerank_k = int(chroma_cfg.get("rerank_k", k))
    similarity_threshold = float(chroma_cfg.get("similarity_threshold", 0.22))
    keyword_threshold = float(chroma_cfg.get("keyword_threshold", 0.20))
    vector_weight = float(chroma_cfg.get("hybrid_vector_weight", 0.7))
    keyword_weight = float(chroma_cfg.get("hybrid_keyword_weight", 0.3))

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-ada-002")

    if not api_key or not base_url:
        raise ValueError("请配置 OPENAI_API_KEY 和 OPENAI_BASE_URL")

    query_embedding = _get_embedding(question, api_key, base_url, embedding_model)

    chroma_client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = chroma_client.get_collection(name=collection_name)

    stage_filters = _build_stage_filters(stage)
    keywords = _extract_keywords(question)
    merged: dict[str, dict] = {}

    # 分阶段召回并合并，主阶段优先（fallback_level 越小优先级越高）
    for level, stage_filter in enumerate(stage_filters):
        vector_res = _vector_search(collection, query_embedding, stage=stage_filter, n_results=recall_k)
        keyword_res = _keyword_search(collection, question, stage=stage_filter, limit=keyword_k)

        v_docs = vector_res["documents"][0] if vector_res.get("documents") else []
        v_metas = vector_res["metadatas"][0] if vector_res.get("metadatas") else []
        v_ids = vector_res.get("ids", [[]])[0] if vector_res.get("ids") else [""] * len(v_docs)
        v_dist = vector_res.get("distances", [[]])[0] if vector_res.get("distances") else [None] * len(v_docs)

        for doc, meta, doc_id, dist in zip(v_docs, v_metas, v_ids, v_dist):
            sim = _similarity_from_distance(dist)
            if doc_id in merged:
                merged[doc_id]["vector_similarity"] = max(merged[doc_id]["vector_similarity"], sim)
                if merged[doc_id]["distance"] is None or (dist is not None and dist < merged[doc_id]["distance"]):
                    merged[doc_id]["distance"] = dist
                merged[doc_id]["fallback_level"] = min(merged[doc_id]["fallback_level"], level)
                continue
            merged[doc_id] = {
                "content": doc,
                "meta": meta or {},
                "doc_id": doc_id,
                "distance": dist,
                "vector_similarity": sim,
                "keyword_score": 0.0,
                "fallback_level": level,
                "fallback_stage": stage_filter or "全部",
            }

        for row in keyword_res:
            doc_id = row["doc_id"]
            if doc_id in merged:
                merged[doc_id]["keyword_score"] = max(merged[doc_id]["keyword_score"], row["keyword_score"])
                merged[doc_id]["fallback_level"] = min(merged[doc_id]["fallback_level"], level)
                continue
            merged[doc_id] = {
                "content": row["content"],
                "meta": row["meta"],
                "doc_id": doc_id,
                "distance": None,
                "vector_similarity": 0.0,
                "keyword_score": row["keyword_score"],
                "fallback_level": level,
                "fallback_stage": stage_filter or "全部",
            }

    # 阈值过滤 + 重排
    rerank_rows = []
    for row in merged.values():
        title = str((row["meta"] or {}).get("title", ""))
        content = str(row.get("content") or "")
        title_hit = 1.0 if any(kw in title for kw in keywords) else 0.0
        content_hit = 0.0
        if keywords:
            hit_cnt = sum(1 for kw in keywords if kw in content[:1000])
            content_hit = min(1.0, hit_cnt / max(1, len(keywords)))

        score = (
            vector_weight * row["vector_similarity"]
            + keyword_weight * row["keyword_score"]
            + 0.1 * title_hit
            + 0.1 * content_hit
        )
        # 主阶段优先：level 越小加分越高（0.08, 0.05, 0.02...）
        score += max(0.0, 0.08 - 0.03 * row.get("fallback_level", 0))
        row["hybrid_score"] = score

        passes_threshold = (
            row["vector_similarity"] >= similarity_threshold or
            row["keyword_score"] >= keyword_threshold
        )
        if passes_threshold:
            rerank_rows.append(row)

    rerank_rows.sort(key=lambda x: x["hybrid_score"], reverse=True)
    final_rows = rerank_rows[: max(1, min(rerank_k, k))]

    return [
        {
            "content": r["content"],
            "title": (r["meta"] or {}).get("title", "未知"),
            "source_file": (r["meta"] or {}).get("source_file", ""),
            "chroma_doc_id": r["doc_id"] or (r["meta"] or {}).get("source_file", ""),
            "stage": (r["meta"] or {}).get("stage"),
            "distance": r.get("distance"),
            "vector_similarity": round(float(r.get("vector_similarity", 0.0)), 4),
            "keyword_score": round(float(r.get("keyword_score", 0.0)), 4),
            "hybrid_score": round(float(r.get("hybrid_score", 0.0)), 4),
            "fallback_stage": r.get("fallback_stage"),
        }
        for r in final_rows
    ]
