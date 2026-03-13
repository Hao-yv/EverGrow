"""
@Time    : 2026/3/13
@Author  : Zhang Hao yv
@File    : init_db.py
@Desc    : 基于 PyMySQL 的数据库初始化脚本。创建表结构并插入默认 admin 账户。
@Run     : 在项目根目录执行 python scripts/init_db.py
"""
import os
import sys
import yaml
import pymysql

# 项目根目录加入 path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 密码哈希：优先 bcrypt，否则 passlib
try:
    import bcrypt
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
except ImportError:
    try:
        from passlib.hash import bcrypt as passlib_bcrypt
        def _hash_password(password: str) -> str:
            return passlib_bcrypt.hash(password)
    except ImportError:
        raise ImportError(
            "请安装 bcrypt 或 passlib: pip install bcrypt 或 pip install 'passlib[bcrypt]'"
        )


def _load_db_config() -> dict:
    """从 config/database.yml 加载数据库配置"""
    config_path = os.path.join(_PROJECT_ROOT, "config", "database.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        conf = yaml.safe_load(f)
    return conf.get("database", {})


def _get_connection_params() -> tuple:
    """获取连接参数：(host, port, user, password, database)"""
    conf = _load_db_config()
    return (
        conf.get("host", "localhost"),
        int(conf.get("port", 3306)),
        conf.get("user", "root"),
        str(conf.get("password", "")),
        conf.get("database", "evergrow_db"),
    )


def _create_database(cursor, db_name: str) -> None:
    """创建数据库（如不存在）"""
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute(f"USE `{db_name}`")


def _create_tables(cursor) -> None:
    """创建表结构：users, sessions, messages"""
    # 按依赖顺序删除（messages -> sessions -> users）
    cursor.execute("DROP TABLE IF EXISTS messages")
    cursor.execute("DROP TABLE IF EXISTS sessions")
    cursor.execute("DROP TABLE IF EXISTS users")

    cursor.execute("""
        CREATE TABLE users (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    cursor.execute("""
        CREATE TABLE sessions (
            id VARCHAR(64) PRIMARY KEY,
            user_id BIGINT UNSIGNED NULL,
            title VARCHAR(100) NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
            INDEX idx_sessions_user_updated (user_id, updated_at DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    cursor.execute("""
        CREATE TABLE messages (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL,
            role ENUM('user','assistant') NOT NULL,
            content TEXT NOT NULL,
            message_type VARCHAR(32) NOT NULL DEFAULT 'normal',
            metadata JSON NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_message_session FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            INDEX idx_messages_session_created (session_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)


def _insert_admin_user(cursor, username: str = "admin", password: str = "admin") -> None:
    """插入默认 admin 账户，若已存在则更新密码"""
    password_hash = _hash_password(password)
    cursor.execute(
        """
        INSERT INTO users (username, password_hash)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), updated_at = CURRENT_TIMESTAMP
        """,
        (username, password_hash),
    )


def main() -> None:
    host, port, user, password, db_name = _get_connection_params()

    print(f"[init_db] 连接数据库 {host}:{port} / {db_name} ...")
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        charset="utf8mb4",
        autocommit=False,
    )

    try:
        with conn.cursor() as cursor:
            _create_database(cursor, db_name)
            print("[init_db] 创建表结构...")
            _create_tables(cursor)
            print("[init_db] 插入 admin 账户 (admin/admin)...")
            _insert_admin_user(cursor, "admin", "admin")
        conn.commit()
        print("[init_db] 初始化完成。")
    except Exception as e:
        conn.rollback()
        print(f"[init_db] 错误: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
