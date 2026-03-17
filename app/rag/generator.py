# -*- coding: utf-8 -*-
"""
EverGrow RAG 生成模块
基于检索到的文档，调用 LLM 生成回答
"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent.parent

load_dotenv(ROOT / ".env")

with open(ROOT / "config" / "prompts.yml", encoding="utf-8") as f:
    PROMPTS = yaml.safe_load(f)

SYSTEM_PROMPT = PROMPTS["system_prompt"]
QA_TEMPLATE = PROMPTS["qa_template"]
QA_TEMPLATE_WITH_HISTORY = PROMPTS.get("qa_template_with_history", QA_TEMPLATE)
NO_RESULT_PROMPT = PROMPTS["no_result_prompt"]

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ["OPENAI_BASE_URL"],
        )
    return _client


def _format_history(messages: list[dict]) -> str:
    """将对话历史格式化为 LLM 可读文本"""
    lines = []
    for m in messages:
        role = "用户" if m.get("role") == "user" else "助理"
        lines.append(f"{role}：{m.get('content', '').strip()}")
    return "\n".join(lines) if lines else "（无）"


def _build_context(docs: list[dict]) -> str:
    """将检索到的文档拼接成 context 文本"""
    parts = []
    for i, doc in enumerate(docs, 1):
        title = doc.get("title", "未知")
        content = doc.get("content", "")
        parts.append(f"【{i}】《{title}》\n{content}")
    return "\n\n".join(parts)


def generate(question: str, docs: list[dict]) -> dict:
    """
    基于检索到的文档生成回答。

    Args:
        question: 用户问题
        docs: 检索到的文档列表，每项含 content, title, source_file, chroma_doc_id

    Returns:
        {"answer": str, "sources": [{"title": str, "source_file": str}, ...]}
    """
    if not docs:
        return {"answer": NO_RESULT_PROMPT, "sources": []}

    context = _build_context(docs)
    user_message = QA_TEMPLATE.format(context=context, question=question)

    client = _get_client()
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-5.2-chat"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    answer = resp.choices[0].message.content

    sources = [
        {
            "title": doc.get("title", "未知"),
            "source_file": doc.get("source_file", "")
        }
        for doc in docs
    ]

    return {"answer": answer, "sources": sources}


def generate_stream(question: str, docs: list[dict], history: list[dict] | None = None):
    """
    流式生成回答，逐个 yield 文本片段。
    docs 为空时 yield no_result_prompt（此时应由调用方先尝试 web 检索，通常不会走到这里）。
    history: 历史对话 [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}, ...]，用于多轮上下文。
    """
    if not docs:
        yield NO_RESULT_PROMPT
        return

    context = _build_context(docs)
    history_clean = [m for m in (history or []) if m.get("content")] if history else []
    if history_clean:
        history_str = _format_history(history_clean)
        user_message = QA_TEMPLATE_WITH_HISTORY.format(
            context=context, question=question, history=history_str
        )
    else:
        user_message = QA_TEMPLATE.format(context=context, question=question)
    client = _get_client()

    stream = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-5.2-chat"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        stream=True,
    )

    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and getattr(delta, "content", None):
            yield delta.content
