# -*- coding: utf-8 -*-
"""配置加载：.env + YAML"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def load_env():
    """加载 .env 到环境变量"""
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")


def load_yaml(name: str) -> dict:
    """加载 config/{name}.yml"""
    import yaml
    path = ROOT / "config" / f"{name}.yml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_chroma_config() -> dict:
    """Chroma 与文档处理配置"""
    return load_yaml("chroma")


def get_database_config() -> dict:
    """数据库配置"""
    data = load_yaml("database")
    return data.get("database", {})


def get_prompts_config() -> dict:
    """提示词配置"""
    return load_yaml("prompts")


def validate_startup_config() -> None:
    """启动配置校验：.env 与 database.yml 必填项"""
    load_env()

    required_env = ["OPENAI_API_KEY", "OPENAI_BASE_URL", "JWT_SECRET_KEY"]
    missing_env = [k for k in required_env if not os.getenv(k)]

    db = get_database_config()
    required_db = ["host", "port", "database", "user", "password"]
    missing_db = [k for k in required_db if db.get(k) in (None, "")]

    errors = []
    if missing_env:
        errors.append(f".env 缺少配置: {', '.join(missing_env)}")
    if missing_db:
        errors.append(f"config/database.yml 缺少配置: {', '.join(missing_db)}")

    if errors:
        raise RuntimeError("；".join(errors))
