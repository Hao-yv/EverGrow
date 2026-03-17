#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EverGrow 数据库初始化脚本
- 创建表：knowledge_articles, users, conversations, conversation_messages
- 创建初始管理员：username=admin, password=admin

依赖：pymysql, pyyaml, bcrypt
运行：python scripts/init_db.py
"""

from pathlib import Path
import sys

# 项目根目录
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    import pymysql
    import yaml
    import bcrypt
except ImportError as e:
    print("请先安装依赖: pip install pymysql pyyaml bcrypt")
    raise SystemExit(1) from e


def load_db_config():
    config_path = ROOT / "config" / "database.yml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["database"]


def get_connection(config):
    return pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        charset="utf8mb4",
    )


def create_tables(conn):
    sql = """
    SET NAMES utf8mb4;
    SET FOREIGN_KEY_CHECKS = 0;

    CREATE TABLE IF NOT EXISTS `knowledge_articles` (
      `id` BIGINT NOT NULL AUTO_INCREMENT,
      `chroma_doc_id` VARCHAR(64) NOT NULL COMMENT 'Chroma 文档 ID',
      `title` VARCHAR(200) NOT NULL COMMENT '问题/标题',
      `stage` VARCHAR(30) NULL COMMENT '年龄段',
      `category` VARCHAR(30) NULL COMMENT '矛盾类型',
      `source_file` VARCHAR(255) NULL COMMENT '原始文件名',
      `source_author` VARCHAR(100) NULL COMMENT '作者/机构',
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_chroma_doc_id` (`chroma_doc_id`),
      KEY `idx_stage_category` (`stage`, `category`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识条目元数据';

    CREATE TABLE IF NOT EXISTS `users` (
      `id` BIGINT NOT NULL AUTO_INCREMENT,
      `username` VARCHAR(50) NOT NULL COMMENT '用户名',
      `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
      `nickname` VARCHAR(50) NULL COMMENT '昵称',
      `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_username` (`username`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户';

    CREATE TABLE IF NOT EXISTS `conversations` (
      `id` BIGINT NOT NULL AUTO_INCREMENT,
      `user_id` BIGINT NULL COMMENT '用户，匿名为空',
      `session_id` VARCHAR(64) NULL COMMENT '匿名会话标识',
      `title` VARCHAR(100) NULL COMMENT '会话摘要',
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      KEY `idx_user_id` (`user_id`),
      KEY `idx_session_id` (`session_id`),
      CONSTRAINT `fk_conv_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='问答会话';

    CREATE TABLE IF NOT EXISTS `conversation_messages` (
      `id` BIGINT NOT NULL AUTO_INCREMENT,
      `conversation_id` BIGINT NOT NULL COMMENT '所属会话',
      `role` ENUM('user','assistant') NOT NULL COMMENT '角色',
      `content` TEXT NOT NULL COMMENT '消息内容',
      `retrieved_doc_ids` JSON NULL COMMENT '引用的 chroma_doc_id 列表',
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      KEY `idx_conversation_id` (`conversation_id`),
      CONSTRAINT `fk_cm_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话消息';

    SET FOREIGN_KEY_CHECKS = 1;
    """
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            with conn.cursor() as cur:
                cur.execute(stmt)
    conn.commit()


def create_admin_user(conn):
    password_hash = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE username = %s", ("admin",))
        if cur.fetchone():
            print("admin 用户已存在，跳过创建")
            return
        cur.execute(
            "INSERT INTO users (username, password_hash, nickname) VALUES (%s, %s, %s)",
            ("admin", password_hash, "管理员"),
        )
    conn.commit()
    print("已创建初始管理员: username=admin, password=admin")


def main():
    print("正在加载配置...")
    config = load_db_config()

    print("正在连接数据库...")
    conn = get_connection(config)

    try:
        print("正在创建表...")
        create_tables(conn)
        print("表创建完成")

        print("正在创建初始管理员...")
        create_admin_user(conn)

        print("数据库初始化完成")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
