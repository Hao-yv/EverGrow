# EverGrow
# -*- coding: utf-8 -*-
"""EverGrow FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.routes import router

app = FastAPI(title="EverGrow", description="亲子矛盾 RAG 智能问答平台")


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


@app.get("/")
def root():
    return {"status": "ok", "message": "EverGrow 亲子矛盾 RAG 智能问答"}


@app.get("/health")
def health():
    return {"status": "healthy"}


