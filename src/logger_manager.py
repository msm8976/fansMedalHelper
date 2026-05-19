"""
日志管理模块
"""
import sys

from loguru import logger


class LogManager:
    """日志管理器"""

    _initialized = False

    @classmethod
    def setup_logger(cls, user: str | None = None):
        """设置日志"""
        if not cls._initialized:
            logger.remove()
            logger.add(
                sys.stdout,
                colorize=True,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
                    "<blue> {extra[user]} </blue> <level>{message}</level>"
                ),
                backtrace=True,
                diagnose=True,
            )
            cls._initialized = True

    @staticmethod
    def get_logger(user: str):
        """获取用户专用logger"""
        return logger.bind(user=user)

    @staticmethod
    def get_system_logger():
        """获取系统logger"""
        return logger.bind(user="B站粉丝牌助手")
