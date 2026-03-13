"""
@Time    : 2026/3/13 19:48
@Author  : Zhang Hao yv
@File    : auther.py
@IDE     : PyCharm
"""

import bcrypt
import jwt
import logging
import os
from datetime import datetime, timedelta

from core.manager.database import get_user_by_username, create_user
from utils.logger_handler import logger, log_exception

JWT_SECRET = os.getenv("JWT_SECRET", "evergrow-secret-change-in-production")
JWT_EXPIRE_HOURS = 24 * 7


def register(username: str, password: str) -> dict | None:
    # 校验参数
    if not username or not password:
        logger.debug("注册失败: 参数为空")
        return None
    username = username.strip()
    if len(username) < 1 or len(password) < 1:
        logger.debug("注册失败: 用户名或密码长度无效")
        return None

    if get_user_by_username(username):
        logger.warning("注册失败: 用户名已存在 [%s]", username)
        return None

    try:
        # 哈希密码
        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        # 插入新用户
        user_id = create_user(username, hashed_password)

        # 生成 JWT
        payload = {
            "user_id": user_id,
            "username": username,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode('utf-8')

        logger.info("注册成功: user_id=%s, username=%s", user_id, username)
        return {
            "user": {"id": user_id, "username": username},
            "token": token
        }
    except Exception as e:
        log_exception("注册失败", e)
        return None


def login(username: str, password: str) -> dict | None:
    if not username or not password:
        logger.debug("登录失败: 参数为空")
        return None

    try:
        user = get_user_by_username(username)
        if user is None:
            logger.debug("登录失败: 用户不存在 [%s]", username)
            return None

        stored_hash = user["password_hash"]
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode("utf-8")
        if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            logger.warning("登录失败: 密码错误 [%s]", username)
            return None

        payload = {
            "user_id": user['id'],
            "username": user["username"],
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode('utf-8')

        logger.info("登录成功: user_id=%s, username=%s", user["id"], user["username"])
        return {
            "user": {"id": user["id"], "username": user["username"]},
            "token": token
        }
    except Exception as e:
        log_exception("登录失败", e)
        return None


def resolve_user_from_header(authorization: str | None) -> tuple[int | None, dict | None]:
    if not authorization:
        logger.debug("Token 解析: 缺少 Authorization 头（游客）")
        return (None, None)

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.debug("Token 解析: Bearer 格式无效")
        return (None, None)

    token = parts[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
        log_exception("Token 解析失败", e, level=logging.WARNING)
        return (None, None)

    user_id = payload.get("user_id")
    username = payload.get("username")
    if not user_id or not username:
        logger.warning("Token 解析: payload 缺少 user_id 或 username")
        return (None, None)

    logger.debug("Token 解析成功: user_id=%s, username=%s", user_id, username)
    return (
        user_id,
        {"id": user_id, "username": username}
    )
    
    