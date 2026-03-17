# -*- coding: utf-8 -*-
"""会话与历史消息 API"""
import json

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, field_validator

from app.api.auth import require_user
from app.core.db import get_db

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None:
            return v
        title = v.strip()
        if not title:
            return None
        if len(title) > 100:
            raise ValueError("会话标题不能超过 100 字")
        return title


class RenameConversationRequest(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        title = v.strip()
        if not title:
            raise ValueError("会话标题不能为空")
        if len(title) > 100:
            raise ValueError("会话标题不能超过 100 字")
        return title


def _get_conversation(conversation_id: int) -> tuple | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, user_id, created_at, updated_at FROM conversations WHERE id = %s",
                (conversation_id,),
            )
            return cur.fetchone()


def _ensure_owner(conversation_id: int, user_id: int) -> tuple:
    row = _get_conversation(conversation_id)
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    if row[2] != user_id:
        raise HTTPException(status_code=403, detail="无权限操作该会话")
    return row


@router.get("")
def list_conversations(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量，1-50"),
    keyword: str | None = Query(None, description="按会话标题关键词搜索"),
    user_id: int = Depends(require_user),
):
    """分页获取当前用户会话列表"""
    offset = (page - 1) * page_size
    kw = (keyword or "").strip()
    has_kw = bool(kw)
    kw_like = f"%{kw}%"
    with get_db() as conn:
        with conn.cursor() as cur:
            if has_kw:
                cur.execute(
                    "SELECT COUNT(*) FROM conversations WHERE user_id = %s AND title LIKE %s",
                    (user_id, kw_like),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM conversations WHERE user_id = %s", (user_id,))
            total = cur.fetchone()[0]
            if has_kw:
                cur.execute(
                    """
                    SELECT id, title, created_at, updated_at
                    FROM conversations
                    WHERE user_id = %s AND title LIKE %s
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, kw_like, page_size, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, title, created_at, updated_at
                    FROM conversations
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, page_size, offset),
                )
            rows = cur.fetchall()
    return {
        "items": [
            {
                "id": r[0],
                "title": r[1] or "新对话",
                "created_at": r[2].isoformat() if r[2] else None,
                "updated_at": r[3].isoformat() if r[3] else None,
            }
            for r in rows
        ],
        "page": page,
        "page_size": page_size,
        "keyword": kw,
        "total": int(total),
        "has_more": offset + len(rows) < total,
    }


@router.post("")
def create_conversation(
    req: CreateConversationRequest | None = None,
    user_id: int = Depends(require_user),
):
    """创建新会话"""
    title = ((req.title if req else None) or "新对话").strip()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (user_id, title) VALUES (%s, %s)",
                (user_id, title[:100]),
            )
            conv_id = cur.lastrowid
    return {"id": conv_id, "title": title[:100]}


@router.patch("/{conversation_id}")
def rename_conversation(
    req: RenameConversationRequest,
    conversation_id: int = Path(..., ge=1),
    user_id: int = Depends(require_user),
):
    """重命名会话"""
    _ensure_owner(conversation_id, user_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET title = %s WHERE id = %s",
                (req.title, conversation_id),
            )
    return {"id": conversation_id, "title": req.title}


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: int = Path(..., ge=1),
    user_id: int = Depends(require_user),
):
    """获取会话详情及消息列表"""
    row = _ensure_owner(conversation_id, user_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, role, content, created_at
                FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY id ASC
                """,
                (conversation_id,),
            )
            msgs = cur.fetchall()
    return {
        "id": row[0],
        "title": row[1] or "新对话",
        "created_at": row[3].isoformat() if row[3] else None,
        "updated_at": row[4].isoformat() if row[4] else None,
        "messages": [
            {"id": m[0], "role": m[1], "content": m[2], "created_at": m[3].isoformat() if m[3] else None}
            for m in msgs
        ],
    }


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int = Path(..., ge=1),
    user_id: int = Depends(require_user),
):
    """删除会话"""
    _ensure_owner(conversation_id, user_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
    return {"ok": True}


def save_message(conversation_id: int, role: str, content: str, doc_ids: list | None = None):
    """内部：保存消息到会话（无鉴权，由调用方保证）"""
    text = (content or "").strip()
    if not text:
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content, retrieved_doc_ids)
                VALUES (%s, %s, %s, %s)
                """,
                (conversation_id, role, text, json.dumps(doc_ids) if doc_ids else None),
            )

    # 会话标题默认跟随首条用户问题
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM conversations WHERE id = %s", (conversation_id,))
            row = cur.fetchone()
            if row and (not row[0] or row[0] == "新对话") and role == "user":
                title = (text[:50] + "…") if len(text) > 50 else text
                cur.execute(
                    "UPDATE conversations SET title = %s WHERE id = %s",
                    (title, conversation_id),
                )
