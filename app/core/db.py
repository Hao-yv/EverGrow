# -*- coding: utf-8 -*-
"""数据库连接"""
from contextlib import contextmanager

import pymysql

from app.core.config import get_database_config


@contextmanager
def get_db():
    """获取数据库连接（上下文管理器）"""
    cfg = get_database_config()
    conn = pymysql.connect(
        host=cfg.get("host", "localhost"),
        port=cfg.get("port", 3306),
        user=cfg.get("user"),
        password=cfg.get("password"),
        database=cfg.get("database"),
        charset="utf8mb4",
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
