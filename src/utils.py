"""
工具函数模块
"""
import hashlib
import json
import random
import time
from typing import Any
from urllib.parse import urlencode

from .constants import BiliConstants


class Crypto:
    """加密工具类"""

    @staticmethod
    def md5(data: str | bytes) -> str:
        """生成MD5哈希"""
        if isinstance(data, str):
            return hashlib.md5(data.encode()).hexdigest()
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def sign(data: str | dict) -> str:
        """生成签名"""
        if isinstance(data, dict):
            _str = urlencode(data)
        elif isinstance(data, str):
            _str = data
        else:
            raise TypeError("数据类型错误")
        return Crypto.md5(_str + BiliConstants.APPSECRET)


class SignableDict(dict):
    """可签名的字典类"""

    @property
    def sorted(self):
        """返回按字母排序的字典"""
        return dict(sorted(self.items()))

    @property
    def signed(self):
        """返回带签名的排序字典"""
        _sorted = self.sorted
        return {**_sorted, "sign": Crypto.sign(_sorted)}


def client_sign(data: dict[str, Any]) -> str:
    """客户端签名"""
    _str = json.dumps(data, separators=(",", ":"))
    for algorithm in ["sha512", "sha3_512", "sha384", "sha3_384", "blake2b"]:
        _str = hashlib.new(algorithm, _str.encode("utf-8")).hexdigest()
    return _str


def random_string(length: int = 16) -> str:
    """生成随机字符串"""
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.sample(chars, length))


def get_timestamp() -> int:
    """获取当前时间戳"""
    return int(time.time())


def safe_get(data: dict[str, Any], *keys, default=None):
    """安全获取嵌套字典值"""
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return default
    return data
