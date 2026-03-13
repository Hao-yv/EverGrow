"""
@Time    : 2026/3/13
@Author  : Zhang Hao yv
@File    : database.py
@Desc    : 基于 PyMySQL 的数据访问层。会话、消息 CRUD，支持游客（user_id=None）。
"""
import json
from typing import Optional

import pymysql

from utils.config_loader import load_db_config


def _get_connection_params() -> dict:
    """从 config/database.yml 获取连接参数"""
    conf = load_db_config().get("database", {})
    return {
        "host": conf.get("host", "localhost"),
        "port": int(conf.get("port", 3306)),
        "user": conf.get("user", "root"),
        "password": str(conf.get("password", "")),
        "database": conf.get("database", "evergrow_db"),
        "charset": "utf8mb4",
    }


def _get_connection():
    """创建并返回 PyMySQL 连接"""
    return pymysql.connect(**_get_connection_params())


def ensure_session_exists(
    session_id: str,
    user_id: Optional[int],
    title: str = "",
) -> None:
    """
    确保会话存在，不存在则插入。
    支持游客：user_id 可为 None。
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (id, user_id, title)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = COALESCE(NULLIF(%s, ''), title),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (session_id, user_id, title[:100], title[:100]),
            )
        conn.commit()
    finally:
        conn.close()


def save_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
) -> None:
    """
    保存一条消息。
    metadata 中的 type 会映射到 message_type 列（如 refined_gold_advice）。
    """
    msg_type = "normal"
    meta = metadata or {}
    if "type" in meta:
        msg_type = str(meta.pop("type", "normal"))

    meta_json = json.dumps(meta, ensure_ascii=False) if meta else None

    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (session_id, role, content, message_type, metadata)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_id, role, content, msg_type, meta_json),
            )
        conn.commit()
    finally:
        conn.close()


def get_user_sessions(user_id: Optional[int], limit: int = 50) -> list[dict]:
    """
    获取用户的会话列表，按 updated_at 倒序。
    游客（user_id=None）返回空列表。
    """
    if user_id is None:
        return []

    conn = _get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, updated_at
                FROM sessions
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return cur.fetchall()
    finally:
        conn.close()


def get_chat_history(session_id: str, limit: int = 20) -> list[dict]:
    """
    获取指定会话的消息历史，按 created_at 正序。
    返回字段：role, content, message_type, created_at
    """
    conn = _get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                """
                SELECT role, content, message_type, created_at
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (session_id, limit),
            )
            return cur.fetchall()
    finally:
        conn.close()


def delete_session(session_id: str, user_id: Optional[int]) -> bool:
    """
    删除会话（仅当 user_id 匹配或会话属于游客时）。
    返回 True 表示已删除，False 表示不存在或无权限。
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            # 校验：会话须存在且 user_id 匹配（游客 user_id=None 对应 sessions.user_id IS NULL）
            cur.execute(
                "SELECT id FROM sessions WHERE id = %s AND ((%s IS NULL AND user_id IS NULL) OR user_id = %s)",
                (session_id, user_id, user_id),
            )
            if not cur.fetchone():
                return False

            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
            affected = cur.rowcount
        conn.commit()
        return affected > 0
    finally:
        conn.close()

def get_user_by_username(username: str) -> dict | None:
    conn = _get_connection()

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            sql = "SELECT id, username, password_hash FROM users WHERE username = %s"
            cur.execute(sql, (username,))
            return cur.fetchone()
    finally:
        conn.close()

def create_user(username: str, password_hash: str) -> int:
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            sql =  "INSERT INTO users (username, password_hash) VALUES (%s, %s)"
            cur.cursor(
                sql,
               (username, password_hash)
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()