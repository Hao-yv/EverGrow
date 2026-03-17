# -*- coding: utf-8 -*-
"""配置加载：.env + YAML"""

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
