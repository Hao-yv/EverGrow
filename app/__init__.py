# EverGrow
# -*- coding: utf-8 -*-
"""EverGrow FastAPI 应用入口"""
import logging
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.routes import router
from app.core.config import ROOT as APP_ROOT
from app.core.config import get_chroma_config, validate_startup_config
from app.core.db import get_db

app = FastAPI(title="EverGrow", description="亲子矛盾 RAG 智能问答平台")
logger = logging.getLogger(__name__)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(conversations_router)


def _error_payload(code: str, message: str, detail):
    return {"code": code, "message": message, "detail": detail}


def _check_config() -> dict:
    required_env = ["OPENAI_API_KEY", "OPENAI_BASE_URL", "JWT_SECRET_KEY"]
    missing = [k for k in required_env if not os.getenv(k)]
    if missing:
        return {"ok": False, "message": f"缺少环境变量: {', '.join(missing)}"}
    return {"ok": True, "message": "配置正常"}


def _check_database() -> dict:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                _ = cur.fetchone()
        return {"ok": True, "message": "数据库连通"}
    except Exception as e:
        return {"ok": False, "message": f"数据库不可用: {e}"}


def _check_chroma() -> dict:
    try:
        import chromadb
        from chromadb.config import Settings

        cfg = get_chroma_config()
        path = str(APP_ROOT / cfg.get("persist_directory", "data/chroma_db"))
        collection_name = cfg.get("collection_name", "agent")
        # 仅做可用性检查，不进行耗时检索
        client = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
        _ = client.get_or_create_collection(name=collection_name)
        return {"ok": True, "message": "Chroma 可用"}
    except Exception as e:
        return {"ok": False, "message": f"Chroma 不可用: {e}"}


@app.on_event("startup")
def on_startup():
    """启动时做关键配置校验，避免运行中才报错"""
    validate_startup_config()


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", f"HTTP_{exc.status_code}"))
        message = str(detail.get("message", "请求失败"))
        payload_detail = detail.get("detail")
    else:
        code = f"HTTP_{exc.status_code}"
        message = str(detail) if isinstance(detail, str) else "请求失败"
        payload_detail = None if isinstance(detail, str) else detail
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(code=code, message=message, detail=payload_detail),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            detail=exc.errors(),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            code="INTERNAL_ERROR",
            message="服务器内部错误",
            detail=str(exc),
        ),
    )


@app.get("/")
def root():
    return {"status": "ok", "message": "EverGrow 亲子矛盾 RAG 智能问答"}


@app.get("/health")
def health():
    checks = {
        "config": _check_config(),
        "database": _check_database(),
        "chroma": _check_chroma(),
    }
    is_healthy = all(v.get("ok") for v in checks.values())
    return {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks,
    }


