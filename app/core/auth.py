# -*- coding: utf-8 -*-
"""认证：JWT、密码哈希"""
import os
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or "evergrow-dev-secret-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天


class TokenDecodeError(Exception):
    """JWT 解码错误"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def hash_password(password: str) -> str:
    """密码哈希"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: int, username: str) -> str:
    """创建 JWT"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并验证 JWT，失败抛出 TokenDecodeError"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise TokenDecodeError("expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenDecodeError("invalid") from e
