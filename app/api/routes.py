# -*- coding: utf-8 -*-
"""EverGrow API 路由"""
import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.api.auth import get_current_user_id
from app.api.conversations import save_message
from app.core.db import get_db
from app.rag.generator import generate_stream
from app.rag.retriever import search
from app.rag.web_search import search_web

router = APIRouter(prefix="/api", tags=["routes"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("history.content 不能为空")
        if len(text) > 4000:
            raise ValueError("history.content 不能超过 4000 字")
        return text


class RoutesRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    stage: Literal["幼儿期", "学龄前", "小学", "初中", "高中", "通用"] | None = None
    history: list[ChatMessage] | None = None  # 历史对话，用于多轮上下文
    conversation_id: int | None = Field(None, ge=1)

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("question 不能为空")
        return text

    @field_validator("history")
    @classmethod
    def validate_history(cls, v: list[ChatMessage] | None) -> list[ChatMessage] | None:
        if v and len(v) > 20:
            raise ValueError("history 最多 20 条")
        return v


def _infer_stage_from_question(question: str) -> Literal["幼儿期", "学龄前", "小学", "初中", "高中", "通用"]:
    """根据问题文本自动识别年龄段（当用户未显式选择 stage 时使用）"""
    text = question or ""
    if re.search(r"高[一二三123]|高中|青春期", text):
        return "高中"
    if re.search(r"初[一二三123]|初中", text):
        return "初中"
    if re.search(r"[一二三四五六123456]年级|小学", text):
        return "小学"
    if re.search(r"幼儿园|学前", text):
        return "学龄前"
    if re.search(r"婴儿|0[-–]3|零到三|宝宝|幼儿", text):
        return "幼儿期"
    return "通用"


def _verify_conversation_owner(conversation_id: int, user_id: int) -> bool:
    """验证用户是否拥有该会话"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM conversations WHERE id = %s",
                (conversation_id,),
            )
            row = cur.fetchone()
    return row is not None and row[0] == user_id


def _load_history_from_db(conversation_id: int) -> list[dict]:
    """从数据库加载会话历史"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM conversation_messages WHERE conversation_id = %s ORDER BY id ASC",
                (conversation_id,),
            )
            rows = cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in rows]


def _stream_ndjson(
    question: str,
    stage: Literal["幼儿期", "学龄前", "小学", "初中", "高中", "通用"] | None = None,
    history: list[dict] | None = None,
    conversation_id: int | None = None,
    user_id: int | None = None,
):
    """流式生成 NDJSON：首行 sources，后续行 chunk。本地资料不足时自动上网检索"""
    full_answer = []
    try:
        resolved_stage = stage or _infer_stage_from_question(question)
        docs = search(question, stage=resolved_stage)
        if not docs:
            docs = search_web(question, max_results=5)

        sources = [{"title": d.get("title", "未知"), "source_file": d.get("source_file", "")} for d in docs]
        doc_ids = [d.get("chroma_doc_id") for d in docs if d.get("chroma_doc_id")]
        yield json.dumps({"sources": sources, "stage": resolved_stage}, ensure_ascii=False) + "\n"

        # 优先从会话加载历史，否则用传入的 history
        if conversation_id and user_id and _verify_conversation_owner(conversation_id, user_id):
            hist = _load_history_from_db(conversation_id)
        else:
            hist = history

        for chunk in generate_stream(question=question, docs=docs, history=hist):
            full_answer.append(chunk)
            yield json.dumps({"chunk": chunk}, ensure_ascii=False) + "\n"

        if conversation_id and user_id and full_answer:
            if _verify_conversation_owner(conversation_id, user_id):
                save_message(conversation_id, "user", question)
                save_message(conversation_id, "assistant", "".join(full_answer), doc_ids)
    except Exception as e:
        yield json.dumps(
            {
                "code": "STREAM_ERROR",
                "message": "流式生成失败",
                "detail": str(e),
            },
            ensure_ascii=False,
        ) + "\n"


@router.post("/routes")
def api_routes_stream(
    req: RoutesRequest,
    user_id: int | None = Depends(get_current_user_id),
):
    """RAG 问答接口（流式输出），支持 stage、多轮、会话保存"""
    if req.conversation_id and not user_id:
        raise HTTPException(status_code=401, detail="保存到会话需先登录")
    if req.conversation_id and user_id and not _verify_conversation_owner(req.conversation_id, user_id):
        raise HTTPException(status_code=403, detail="无权限操作该会话")

    hist = [{"role": m.role, "content": m.content} for m in (req.history or [])] if req.history else None
    return StreamingResponse(
        _stream_ndjson(
            req.question,
            stage=req.stage or None,
            history=hist,
            conversation_id=req.conversation_id,
            user_id=user_id,
        ),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache"},
    )
