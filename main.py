"""
@Time    : 2026/3/13
@Author  : Zhang Hao yv
@File    : main.py
@Desc    : FastAPI 服务入口，测试鉴权接口（register / login / profile）
"""

from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.auth.auther import register, login, resolve_user_from_header

app = FastAPI(title="EverGrow 鉴权测试", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/register")
async def register_endpoint(req: RegisterRequest):
    """注册新用户"""
    result = register(req.username, req.password)
    if result is None:
        raise HTTPException(status_code=400, detail="用户名已存在或参数无效")
    return result


@app.post("/api/auth/login")
async def login_endpoint(req: LoginRequest):
    """登录"""
    result = login(req.username, req.password)
    if result is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return result


@app.get("/api/auth/profile")
async def profile_endpoint(authorization: Optional[str] = Header(None)):
    """获取当前用户信息，需携带 Bearer token"""
    user_id, user_info = resolve_user_from_header(authorization)
    if user_info is None:
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    return user_info


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
