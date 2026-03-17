# -*- coding: utf-8 -*-
"""用户注册、登录"""
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, field_validator

from app.core.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str | None = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 50:
            raise ValueError("用户名 2-50 字符")
        if not re.match(r"^[\w\u4e00-\u9fa5]+$", v):
            raise ValueError("用户名仅支持字母、数字、中文、下划线")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v

    @field_validator("nickname")
    @classmethod
    def nickname_valid(cls, v: str | None) -> str | None:
        if v is None:
            return None
        nickname = v.strip()
        if not nickname:
            return None
        if len(nickname) > 50:
            raise ValueError("昵称不能超过 50 字")
        return nickname


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def login_username_valid(cls, v: str) -> str:
        username = v.strip()
        if not username:
            raise ValueError("用户名不能为空")
        return username

    @field_validator("password")
    @classmethod
    def login_password_valid(cls, v: str) -> str:
        if not v:
            raise ValueError("密码不能为空")
        return v


def get_current_user_id(
    cred: HTTPAuthorizationCredentials | None = Depends(security),
) -> int | None:
    """从 Bearer token 解析用户 ID，未登录返回 None"""
    if not cred or not cred.credentials:
        return None
    payload = decode_token(cred.credentials)
    if not payload or "sub" not in payload:
        return None
    try:
        return int(payload["sub"])
    except (ValueError, TypeError):
        return None


def require_user(user_id: int | None = Depends(get_current_user_id)) -> int:
    """要求已登录，否则 401"""
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user_id


@router.post("/register")
def register(req: RegisterRequest):
    """用户注册"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (req.username,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="用户名已存在")
            pw_hash = hash_password(req.password)
            cur.execute(
                "INSERT INTO users (username, password_hash, nickname) VALUES (%s, %s, %s)",
                (req.username, pw_hash, req.nickname or req.username),
            )
            user_id = cur.lastrowid
    token = create_access_token(user_id, req.username)
    return {
        "access_token": token,
        "user": {"id": user_id, "username": req.username, "nickname": req.nickname or req.username},
    }


@router.post("/login")
def login(req: LoginRequest):
    """用户登录"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, nickname FROM users WHERE username = %s AND is_active = 1",
                (req.username,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user_id, username, pw_hash, nickname = row
    if not verify_password(req.password, pw_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user_id, username)
    return {
        "access_token": token,
        "user": {"id": user_id, "username": username, "nickname": nickname or username},
    }


@router.get("/me")
def get_me(user_id: int = Depends(require_user)):
    """获取当前用户信息"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, nickname FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"id": row[0], "username": row[1], "nickname": row[2] or row[1]}
