"""
@Time    : 2026/3/8 21:20
@Author  : Zhang Hao yv
@File    : config_loader.py
"""
import os
import yaml
from dotenv import load_dotenv
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


def load_rag_config(env_path: str = None) -> dict:
    """
    1. 加载 .env 敏感信息
    2. 加载 config/agent.yml 业务配置
    3. 合并返回
    """
    if env_path is None:
        env_path = get_abs_path(".env")

    # A. 加载 .env
    load_dotenv(env_path, override=False)

    config_dict = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "OPENAI_BASE_URL": os.getenv("OPENAI_BASE_URL", ""),
        "OPENAI_MODEL_NAME": os.getenv("OPENAI_MODEL_NAME", "gpt-5.2-chat"),
        "EMBEDDING_MODEL_NAME": os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-ada-002"),
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
    }


    logger.info("成功完成 RAG 综合配置加载")
    return config_dict


def load_db_config(config_path: str = None, encoding: str = "utf-8") -> dict:
    if config_path is None:
        config_path = get_abs_path("config/database.yml")
    try:
        with open(config_path, "r", encoding=encoding) as f:
            conf = yaml.safe_load(f) # 建议使用 safe_load 更安全
            logger.info(f"数据库配置加载成功: {config_path}")
            return conf
    except Exception as e:
        logger.error(f"数据库配置读取失败: {str(e)}")
        return {}


def load_prompts_config(config_path: str = None, encoding: str = "utf-8") -> dict:
    if config_path is None:
        config_path = get_abs_path("config/prompts.yml")
    try:
        with open(config_path, "r", encoding=encoding) as f:
            conf = yaml.safe_load(f)
            logger.info(f"提示词配置加载成功: {config_path}")
            return conf
    except Exception as e:
        logger.warning(f"提示词配置加载异常，将使用默认模版: {str(e)}")
        return {}


# --- 统一导出配置实例 ---
rag_config = load_rag_config()
db_config = load_db_config()
prompts_config = load_prompts_config()


def get_mysql_url() -> str:
    """
    利用加载的配置动态生成 PyMysql 连接串
    """
    conf = db_config.get('database', {})
    user = conf.get('user', 'root')
    password = conf.get('password', '')
    host = conf.get('host', 'localhost')
    port = conf.get('port', 3306)
    db_name = conf.get('database', 'evergrow_db')
    # 修正 password 为字符串，防止 yml 误读为数字导致拼接失败
    return f"mysql+pymysql://{user}:{str(password)}@{host}:{port}/{db_name}?charset=utf8mb4"


mysql_url = get_mysql_url()

if __name__ == "__main__":
    print(f"API Key: {rag_config.get('OPENAI_API_KEY')[:10]}******")
    print(f"外部数据路径: {rag_config.get('external_data_path')}")