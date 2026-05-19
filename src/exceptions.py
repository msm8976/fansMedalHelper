"""
异常处理模块
"""


class BiliException(Exception):
    """B站API异常基类"""

    def __init__(self, message: str, code: int | None = None):
        self.message = message
        self.code = code
        super().__init__(self.message)

    def __str__(self):
        return self.message


class BiliApiError(BiliException):
    """B站API错误"""

    def __init__(self, code: int, message: str):
        super().__init__(message, code)


class LoginError(BiliException):
    """登录错误"""
    pass


class ConfigError(BiliException):
    """配置错误"""
    pass


class NetworkError(BiliException):
    """网络错误"""
    pass


class RateLimitError(BiliException):
    """频率限制错误"""
    pass
