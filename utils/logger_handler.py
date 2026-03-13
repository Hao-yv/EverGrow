"""
@Time    : 2026/3/8 18:02
@Author  : Zhang Hao yv
@File    : logger_handler.py
@IDE     : PyCharm
"""

import logging
import os
from utils.path_tool import get_abs_path
from datetime import datetime

# 日志保存根目录
LOG_PATH = get_abs_path("logs")

# 确保日志存在
os.makedirs(LOG_PATH, exist_ok=True)

# 配置日志格式 error info debug
DEFAULT_LOG_FORMAT = logging.Formatter(
    '%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s'
)

def get_logger(
        name: str = 'agent',
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        log_file = None
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

#     避免重复添加handler
    if logger.handlers:
        return logger
    # 控制台Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(console_handler)

    # 文件Handler
    if not log_file:
        log_file = os.path.join(LOG_PATH, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(file_handler)
    return logger

# 快捷日志获取器
logger = get_logger()


def log_exception(
    msg: str,
    exc: BaseException | None = None,
    level: int = logging.ERROR,
    log: logging.Logger | None = None,
) -> None:
    """
    记录异常及堆栈，默认使用内置 logger。
    用法: log_exception("登录失败", e) 或 log_exception("Token 解析失败", e, level=logging.WARNING)
    """
    _log = log if log is not None else logger
    if exc is not None:
        _log.log(level, f"{msg}: {type(exc).__name__}: {exc}", exc_info=True)
    else:
        _log.log(level, msg, exc_info=True)


if __name__ == "__main__":
    logger.info("日志信息")
    logger.error("错误日志")
    logger.warning("警告日志")
    logger.debug("调试日志")



