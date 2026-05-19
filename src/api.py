import asyncio
import hashlib
import json
import random
import string
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from aiohttp import ClientSession

from .constants import BiliConstants
from .exceptions import BiliApiError
from .logger_manager import LogManager
from .utils import SignableDict, client_sign, get_timestamp, random_string

if TYPE_CHECKING:
    from .user import BiliUser


def retry(tries: int = 3, interval: int = 1):
    """重试装饰器"""
    def decorate(func):
        async def wrapper(*args, **kwargs):
            count = 0
            func.isRetryable = False
            log = LogManager.get_logger(f"{args[0].u.name}")

            while True:
                try:
                    result = await func(*args, **kwargs)
                except Exception as e:
                    count += 1

                    if isinstance(e, BiliApiError):
                        if e.code == BiliConstants.ErrorCodes.TOKEN_ERROR:
                            raise e
                        elif e.code == BiliConstants.ErrorCodes.RATE_LIMIT:
                            await asyncio.sleep(10)
                        elif e.code == BiliConstants.ErrorCodes.SERVER_ERROR:
                            pass
                        else:
                            raise e

                    if count > tries:
                        log.error(
                            f"API {urlparse(args[1]).path} 调用出现异常: {str(e)}")
                        raise e
                    else:
                        await asyncio.sleep(interval)

                    func.isRetryable = True
                else:
                    return result

        return wrapper
    return decorate


class BiliApi:
    """B站API接口类"""

    def __init__(self, user: 'BiliUser', session: ClientSession):
        self.u = user
        self.session = session
        self.headers = BiliConstants.HEADERS.copy()

    def _check_response(self, resp: dict) -> dict:
        """检查API响应"""
        if resp["code"] != 0 or ("mode_info" in resp["data"] and resp["message"] != ""):
            raise BiliApiError(resp["code"], resp["message"])
        return resp["data"]

    @retry()
    async def _get(self, *args, **kwargs):
        """GET请求"""
        async with self.session.get(*args, **kwargs) as resp:
            return self._check_response(await resp.json())

    @retry()
    async def _post(self, *args, **kwargs):
        """POST请求"""
        async with self.session.post(*args, **kwargs) as resp:
            return self._check_response(await resp.json())

    async def getFansMedalandRoomID(self) -> AsyncGenerator[dict]:
        """获取用户粉丝勋章和直播间ID"""
        url = BiliConstants.URLs.FANS_MEDAL_PANEL
        params = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
            "page": 1,
            "page_size": BiliConstants.Tasks.DEFAULT_PAGE_SIZE,
        }
        first_flag = True

        while True:
            data = await self._get(url, params=SignableDict(params).signed, headers=self.headers)

            if first_flag and data.get("special_list"):
                for item in data["special_list"]:
                    yield item
                self.u.wearedMedal = data["special_list"][0]
                first_flag = False

            for item in data.get("list", []):
                yield item

            if not data.get("list"):
                break

            params["page"] += 1

    async def likeInteract(self, room_id: int):
        """点赞直播间"""
        url = BiliConstants.URLs.LIKE_INTERACT
        data = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "click_time": 1,
            "roomid": room_id,
        }
        self.headers.update(
            {"Content-Type": "application/x-www-form-urlencoded"})
        await self._post(url, data=SignableDict(data).signed, headers=self.headers)

    def _sign_like_payload(self, data: dict) -> dict:
        """点赞接口按外部实现使用未 urlencode 的参数串签名。"""
        sorted_data = dict(sorted(data.items()))
        query = "&".join(f"{key}={value}" for key, value in sorted_data.items())
        sign = hashlib.md5(f"{query}{BiliConstants.APPSECRET}".encode()).hexdigest()
        return {**sorted_data, "sign": sign}

    def _like_headers(self) -> dict:
        buvid = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=37)
        )
        return {
            **self.headers,
            "Content-Type": "application/x-www-form-urlencoded",
            "Buvid": buvid,
            "env": "prod",
        }

    async def likeInteractV3(
        self,
        room_id: int,
        up_id: int,
        self_uid: int,
        *,
        click_time: int = 1,
    ):
        """点赞直播间V3"""
        url = BiliConstants.URLs.LIKE_INTERACT_V3
        data = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "click_time": click_time,
            "room_id": room_id,
            "anchor_id": up_id,
            "uid": self_uid,
        }
        await self._post(
            url,
            data=self._sign_like_payload(data),
            headers=self._like_headers(),
        )

    async def shareRoom(self, room_id: int):
        """分享直播间"""
        url = BiliConstants.URLs.SHARE_ROOM
        data = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
            "interact_type": 3,
            "roomid": room_id,
        }
        self.headers.update(
            {"Content-Type": "application/x-www-form-urlencoded"})
        await self._post(url, data=SignableDict(data).signed, headers=self.headers)

    async def sendDanmaku(self, room_id: int) -> str:
        """发送弹幕"""
        url = BiliConstants.URLs.SEND_DANMAKU
        params = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
        }
        data = {
            "cid": room_id,
            "msg": random.choice(BiliConstants.DANMAKU_LIST),
            "rnd": get_timestamp(),
            "color": "16777215",
            "fontsize": "25",
        }
        self.headers.update(
            {"Content-Type": "application/x-www-form-urlencoded"})

        try:
            resp = await self.session.post(
                url, params=SignableDict(
                    params).signed, data=data, headers=self.headers
            )
            resp = await resp.json()

            # 检查响应格式
            if resp.get("code") != 0:
                # 尝试处理错误响应
                if resp.get("mode_info") and resp["mode_info"].get("extra"):
                    return json.loads(resp["mode_info"]["extra"])["content"]
                else:
                    raise BiliApiError(resp.get("code", -1),
                                       resp.get("message", "未知错误"))

            # 成功响应处理
            if resp.get("mode_info") and resp["mode_info"].get("extra"):
                return json.loads(resp["mode_info"]["extra"])["content"]
            else:
                return "弹幕发送成功"

        except BiliApiError as e:
            if "已经发送过" in str(e):
                return "重复弹幕"
            elif e.code == 0:  # 特殊情况，code为0但有错误信息时重试
                # 重试发送简单弹幕
                try:
                    await asyncio.sleep(self.u.config.get("DANMAKU_CD", 3))
                    params.update({"ts": get_timestamp()})
                    data.update({"msg": "111"})

                    resp = await self.session.post(
                        url, params=SignableDict(
                            params).signed, data=data, headers=self.headers
                    )
                    resp = await resp.json()

                    if resp.get("mode_info") and resp["mode_info"].get("extra"):
                        return json.loads(resp["mode_info"]["extra"])["content"]
                    else:
                        return "弹幕发送成功"
                except Exception as retry_error:
                    raise e from retry_error
            else:
                raise e
        except Exception as e:
            raise BiliApiError(-1, f"弹幕发送异常: {str(e)}")

    async def loginVerift(self):
        """登录验证"""
        url = BiliConstants.URLs.LOGIN_INFO
        params = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
        }
        return await self._get(url, params=SignableDict(params).signed, headers=self.headers)

    async def getUserInfo(self):
        """获取用户信息"""
        url = BiliConstants.URLs.USER_INFO
        params = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
        }
        return await self._get(url, params=SignableDict(params).signed, headers=self.headers)

    async def getMedalsInfoByUid(self, uid: int):
        """根据UID获取勋章信息"""
        async for medal in self.getMyMedals():
            if int(medal.get("target_id", 0)) == int(uid):
                return {
                    "has_fans_medal": True,
                    "my_fans_medal": medal,
                }

        return {
            "has_fans_medal": False,
            "my_fans_medal": None,
        }

    async def getMyMedals(self) -> AsyncGenerator[dict]:
        """获取自己持有的粉丝勋章"""
        page = 1
        total_page = 1

        while page <= total_page:
            data = await self._get_my_medals_page(page)
            for medal in data.get("items", []):
                yield medal

            page_info = data.get("page_info", {})
            total_page = max(1, int(page_info.get("total_page", page)))
            page += 1

    async def _get_my_medals_page(self, page: int) -> dict:
        url = BiliConstants.URLs.MY_MEDALS
        params = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "page": page,
            "page_size": BiliConstants.Tasks.MY_MEDALS_PAGE_SIZE,
            "ts": get_timestamp(),
        }
        return await self._get(url, params=SignableDict(params).signed, headers=self.headers)

    async def heartbeat(self, room_id: int, up_id: int):
        """发送心跳包"""
        data = {
            "platform": "android",
            "uuid": self.u.uuids[0],
            "buvid": random_string(37).upper(),
            "seq_id": "1",
            "room_id": f"{room_id}",
            "parent_id": "6",
            "area_id": "283",
            "timestamp": f"{get_timestamp() - 60}",
            "secret_key": "axoaadsffcazxksectbbb",
            "watch_time": "60",
            "up_id": f"{up_id}",
            "up_level": "40",
            "jump_from": "30000",
            "gu_id": random_string(43).lower(),
            "play_type": "0",
            "play_url": "",
            "s_time": "0",
            "data_behavior_id": "",
            "data_source_id": "",
            "up_session": f"l:one:live:record:{room_id}:{get_timestamp()-88888}",
            "visit_id": random_string(32).lower(),
            "watch_status": "%7B%22pk_id%22%3A0%2C%22screen_status%22%3A1%7D",
            "click_id": self.u.uuids[1],
            "session_id": "",
            "player_type": "0",
            "client_ts": f"{get_timestamp()}",
        }

        # 添加client_sign
        data.update({
            "client_sign": client_sign(data),
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
        })

        url = BiliConstants.URLs.HEARTBEAT
        self.headers.update(
            {"Content-Type": "application/x-www-form-urlencoded"})
        return await self._post(url, data=SignableDict(data).signed, headers=self.headers)

    async def wearMedal(self, medal_id: int):
        """佩戴勋章"""
        url = BiliConstants.URLs.WEAR_MEDAL
        data = {
            "medal_id": medal_id,
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
        }
        return await self._post(url, data=SignableDict(data).signed, headers=self.headers)

    async def getGroups(self):
        """获取应援团列表"""
        url = BiliConstants.URLs.GROUPS
        params = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
        }
        res = await self._get(url, params=SignableDict(params).signed, headers=self.headers)
        for group in res["list"]:
            yield group

    async def signInGroups(self, group_id: int, owner_id: int):
        """应援团签到"""
        url = BiliConstants.URLs.SIGN_IN_GROUPS
        params = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
        }
        return await self._get(url, params=SignableDict(params).signed, headers=self.headers)

    async def getOneBattery(self):
        """获取电池"""
        url = "https://api.live.bilibili.com/xlive/revenue/v1/wallet/getInfo"
        params = {
            "access_key": self.u.access_key,
            "actionKey": "appkey",
            "appkey": BiliConstants.APPKEY,
            "ts": get_timestamp(),
        }
        return await self._post(url, data=SignableDict(params).signed, headers=self.headers)
