"""
TV扫码登录。
"""
import asyncio

import aiohttp

from .constants import BiliConstants
from .utils import SignableDict, get_timestamp

QR_CODE_URL = "http://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code"
POLL_URL = "http://passport.bilibili.com/x/passport-tv-login/qrcode/poll"
DEFAULT_POLL_SECONDS = 180
POLL_INTERVAL_SECONDS = 3


class TvLogin:
    """使用 TV 扫码登录获取 access_key。"""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def get_qr_code(self) -> tuple[str, str]:
        data = {
            "local_id": "0",
            "ts": str(get_timestamp()),
            "appkey": BiliConstants.APPKEY,
        }
        async with self.session.post(
            QR_CODE_URL,
            data=SignableDict(data).signed,
            headers=self._headers(),
        ) as response:
            payload = await response.json()

        if payload.get("code") != 0:
            raise RuntimeError(f"获取二维码失败: {payload}")

        login_data = payload.get("data") or {}
        return login_data["url"], login_data["auth_code"]

    async def poll_access_key(self, auth_code: str, timeout_seconds: int) -> str:
        deadline = get_timestamp() + timeout_seconds
        while get_timestamp() < deadline:
            data = {
                "auth_code": auth_code,
                "local_id": "0",
                "ts": str(get_timestamp()),
                "appkey": BiliConstants.APPKEY,
            }
            async with self.session.post(
                POLL_URL,
                data=SignableDict(data).signed,
                headers=self._headers(),
            ) as response:
                payload = await response.json()

            if payload.get("code") == 0:
                return payload["data"]["access_token"]

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        raise TimeoutError("扫码登录超时")

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": BiliConstants.HEADERS["User-Agent"],
        }
