#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EverGrow 数据导入脚本
- 解析 data/raw 下的 docx、doc、txt
- 向量化后存入 Chroma
- 元数据写入 knowledge_articles

运行：python scripts/ingest.py

依赖：pymysql pyyaml python-dotenv python-docx chromadb openai cryptography

.doc 解析（任选其一）：
- Windows: 安装 Microsoft Word + pip install pywin32
- 通用: 安装 LibreOffice，脚本会自动调用 soffice --headless
- Linux: apt install catdoc 或 antiword
"""

import hashlib
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config():
    """加载配置"""
    import yaml
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    with open(ROOT / "config" / "chroma.yml", encoding="utf-8") as f:
        chroma_cfg = yaml.safe_load(f)

    with open(ROOT / "config" / "database.yml", encoding="utf-8") as f:
        db_cfg = yaml.safe_load(f)["database"]

    return {
        "chroma": chroma_cfg,
        "database": db_cfg,
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_base_url": os.getenv("OPENAI_BASE_URL"),
        "embedding_model": os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-ada-002"),
    }


def extract_metadata_from_filename(filename: str) -> tuple[str, str | None]:
    """从文件名解析标题和作者
    例：1.如何激发孩子的学习热情？.docx -> (如何激发孩子的学习热情？, None)
        100《孩子上幼儿园，不受小朋友欢迎怎么办》+韩晓芝.docx -> (孩子上幼儿园...' 韩晓芝)
    """
    stem = Path(filename).stem
    author = None

    # 提取作者：+作者 或 （作者）
    if "+" in stem:
        parts = stem.rsplit("+", 1)
        stem, author = parts[0].strip(), parts[1].strip() if len(parts) > 1 else None
    match = re.search(r"[（(]([^）)]+)[）)]\s*$", stem)
    if match:
        author = match.group(1).strip()
        stem = stem[: match.start()].strip()

    # 去掉开头的编号：1. 或 100
    stem = re.sub(r"^\d+[\.\s]*", "", stem)
    # 去掉书名号
    stem = re.sub(r"^[《【\[]([^》】\]]+)[》】\]]", r"\1", stem)

    title = stem.strip() or filename
    return title, author


def parse_docx(filepath: Path) -> str:
    """解析 docx 文件内容"""
    from docx import Document

    doc = Document(str(filepath))
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paras)


def _parse_doc_win32(filepath: Path) -> str | None:
    """解析 .doc（Windows + Word + pywin32）"""
    try:
        import win32com.client

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(filepath.resolve()))
            text = doc.Content.Text
            doc.Close(False)
            return text.strip() if text else None
        finally:
            word.Quit()
    except Exception:
        return None


def _parse_doc_catdoc(filepath: Path) -> str | None:
    """解析 .doc（catdoc 或 antiword 命令行）"""
    import shutil
    import subprocess

    for cmd in ["catdoc", "antiword"]:
        exe = shutil.which(cmd)
        if exe:
            try:
                r = subprocess.run([exe, str(filepath)], capture_output=True, text=True, timeout=30)
                if r.returncode == 0 and r.stdout:
                    return r.stdout.strip()
            except Exception:
                pass
    return None


def _parse_doc_libreoffice(filepath: Path) -> str | None:
    """解析 .doc（LibreOffice 无界面转换）"""
    import shutil
    import subprocess
    import tempfile

    soffice = None
    for path in [
        "soffice",
        "libreoffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]:
        if shutil.which(path) or (isinstance(path, str) and Path(path).exists()):
            soffice = path
            break
    if not soffice:
        return None

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "txt", "--outdir", str(out_dir), str(filepath.resolve())],
                capture_output=True,
                timeout=30,
            )
            txt_path = out_dir / (filepath.stem + ".txt")
            if txt_path.exists():
                return txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        except (subprocess.TimeoutExpired, Exception):
            pass
    return None


def parse_doc(filepath: Path) -> str | None:
    """解析 .doc 文件。依次尝试：Word(pywin32) → LibreOffice → catdoc/antiword"""
    for fn in [_parse_doc_win32, _parse_doc_libreoffice, _parse_doc_catdoc]:
        try:
            text = fn(filepath)
            if text and len(text.strip()) > 10:
                return text
        except Exception:
            continue
    return None


def parse_file(filepath: Path, allowed_types: list[str]) -> str | None:
    """解析文档，返回纯文本"""
    suffix = filepath.suffix.lower()
    if suffix not in [f".{t}" for t in allowed_types]:
        return None

    if suffix == ".docx":
        return parse_docx(filepath)
    if suffix == ".doc":
        return parse_doc(filepath)
    if suffix == ".txt":
        return filepath.read_text(encoding="utf-8", errors="ignore")

    return None


def get_embedding(text: str, api_key: str, base_url: str, model: str) -> list[float]:
    """调用 OpenAI 兼容接口获取 embedding"""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.embeddings.create(model=model, input=text)
    return resp.data[0].embedding


# 年龄段：用于 ingest 推断和 retriever 过滤
STAGES = ["幼儿期", "学龄前", "小学", "初中", "高中", "通用"]


def infer_stage(filename: str, title: str, content: str) -> str:
    """从文件名、标题和内容推断年龄段。
    匹配顺序：高中 > 初中 > 小学 > 学龄前 > 幼儿期，默认 通用。
    """
    text = f"{filename} {title} {content[:2000]}"
    # 高中：高一、高二、高三、高中、青春期
    if re.search(r"高[一二三123]|高中|青春期", text):
        return "高中"
    # 初中
    if re.search(r"初[一二三123]|初中", text):
        return "初中"
    # 小学：一到六年级
    if re.search(r"[一二三四五六123456]年级|小学", text):
        return "小学"
    # 学龄前：幼儿园、学前
    if re.search(r"幼儿园|学前", text):
        return "学龄前"
    # 幼儿期：婴儿、0-3
    if re.search(r"婴儿|0[-–]3|零到三", text):
        return "幼儿期"
    return "通用"


def collect_files(data_path: str | Path, allowed_types: list[str]) -> list[Path]:
    """收集待处理文件。优先 data/raw，若不存在或为空则回退 data/"""
    path = ROOT / data_path if isinstance(data_path, str) else data_path
    alt = ROOT / "data"

    # 优先从 data/raw 收集
    if path.exists():
        files = []
        for ext in allowed_types:
            files.extend(path.glob(f"*.{ext}"))
        if files:
            return sorted(set(files))
    # data/raw 不存在或为空时，尝试 data/
    if alt.exists():
        files = []
        for ext in allowed_types:
            files.extend(alt.glob(f"*.{ext}"))
        return sorted(set(files))
    return []


def _split_long_text(text: str, size: int) -> list[str]:
    """超长文本兜底切分（按句号再按字符）"""
    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])", text) if s.strip()]
    units = sentences or [text]
    chunks: list[str] = []
    current = ""
    for u in units:
        candidate = f"{current}{u}" if current else u
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = u
        while len(current) > size:
            chunks.append(current[:size])
            current = current[size:]
    if current:
        chunks.append(current)
    return chunks


def chunk_text(content: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """按段落切块并添加 overlap，默认适合中文问答语料"""
    text = re.sub(r"\r\n?", "\n", content).strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    base_limit = max(100, chunk_size - max(0, chunk_overlap))
    base_chunks: list[str] = []
    current = ""
    for para in paragraphs:
        units = [para] if len(para) <= base_limit else _split_long_text(para, base_limit)
        for u in units:
            candidate = f"{current}\n\n{u}" if current else u
            if len(candidate) <= base_limit:
                current = candidate
            else:
                if current:
                    base_chunks.append(current.strip())
                current = u.strip()
    if current:
        base_chunks.append(current.strip())

    if not base_chunks:
        return []
    if chunk_overlap <= 0:
        return base_chunks

    final_chunks = [base_chunks[0]]
    for i in range(1, len(base_chunks)):
        prev_tail = final_chunks[-1][-chunk_overlap:]
        merged = f"{prev_tail}\n{base_chunks[i]}".strip() if prev_tail else base_chunks[i]
        if len(merged) > chunk_size:
            merged = merged[-chunk_size:]
        final_chunks.append(merged)
    return final_chunks


def run_ingest():
    cfg = load_config()
    if not cfg.get("openai_api_key") or not cfg.get("openai_base_url"):
        raise SystemExit("请在 .env 中配置 OPENAI_API_KEY 和 OPENAI_BASE_URL")
    chroma_cfg = cfg["chroma"]
    db_cfg = cfg["database"]

    data_path = ROOT / chroma_cfg.get("data_path", "data/raw")
    allowed = chroma_cfg.get("allow_knowledge_file_type", ["txt", "pdf", "docx"])
    persist_dir = ROOT / chroma_cfg.get("persist_directory", "data/chroma_db")
    collection_name = chroma_cfg.get("collection_name", "agent")
    chunk_size = int(chroma_cfg.get("chunk_size", 700))
    chunk_overlap = int(chroma_cfg.get("chunk_overlap", 100))

    persist_dir.mkdir(parents=True, exist_ok=True)

    files = collect_files(data_path, allowed)
    raw_path = ROOT / "data" / "raw"
    data_dir = ROOT / "data"
    if files:
        print(f"找到 {len(files)} 个文件，数据路径: {files[0].parent}")
    else:
        raw_path.mkdir(parents=True, exist_ok=True)
        print(f"找到 0 个文件。请将 docx/doc 放入 {raw_path} 或 {data_dir} 后重试")

    if not files:
        print("无文件可处理，退出")
        return

    # 初始化 Chroma
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name=collection_name, metadata={"description": "EverGrow knowledge"})

    # 初始化 MySQL
    import pymysql

    conn = pymysql.connect(
        host=db_cfg["host"],
        port=db_cfg["port"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
        charset="utf8mb4",
    )

    success = 0
    for fp in files:
        try:
            content = parse_file(fp, allowed)
            if not content or len(content.strip()) < 10:
                reason = "解析失败" if fp.suffix.lower() == ".doc" else "内容过短"
                if fp.suffix.lower() == ".doc" and not content:
                    reason += "（.doc 需安装 Word+pywin32 或 LibreOffice 或 catdoc/antiword）"
                print(f"  跳过（{reason}）: {fp.name}")
                continue

            title, author = extract_metadata_from_filename(fp.name)
            stage = infer_stage(fp.name, title, content)
            chunks = chunk_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            if not chunks:
                print(f"  跳过（切块后为空）: {fp.name}")
                continue

            # 清理同名文件旧分块，避免策略升级后出现重复与脏数据
            try:
                collection.delete(where={"source_file": fp.name})
            except Exception:
                pass

            for idx, chunk in enumerate(chunks):
                doc_id = hashlib.md5(f"{fp.name}:{idx}:{chunk[:500]}".encode()).hexdigest()[:32]
                text_for_embed = chunk[:8000] if len(chunk) > 8000 else chunk
                embedding = get_embedding(
                    text_for_embed,
                    cfg["openai_api_key"],
                    cfg["openai_base_url"],
                    cfg["embedding_model"],
                )

                # 写入 Chroma（chunk metadata 用于检索与重排）
                collection.upsert(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[
                        {
                            "source_file": fp.name,
                            "title": title,
                            "stage": stage,
                            "chunk_index": idx,
                            "chunk_total": len(chunks),
                        }
                    ],
                )

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO knowledge_articles (chroma_doc_id, title, stage, category, source_file, source_author)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE title=VALUES(title), stage=VALUES(stage), source_author=VALUES(source_author)
                        """,
                        (doc_id, title, stage, None, fp.name, author),
                    )
                conn.commit()

            success += 1
            print(f"  ✓ {fp.name} -> {title[:40]}... [{stage}] chunks={len(chunks)}")
        except Exception as e:
            print(f"  ✗ {fp.name}: {e}")

    conn.close()
    print(f"\n完成：成功导入 {success}/{len(files)} 篇")


if __name__ == "__main__":
    run_ingest()
