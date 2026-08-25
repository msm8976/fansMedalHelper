"""
业务服务层模块
"""
import asyncio
import random
from abc import ABC, abstractmethod
from typing import Any

from .api import BiliApi
from .constants import BiliConstants
from .exceptions import BiliException, LoginError
from .logger_manager import LogManager
from .models import UserInfo
from .utils import safe_get


class BaseService(ABC):
    """基础服务抽象类"""

    def __init__(self, api: BiliApi, logger=None):
        self.api = api
        self.log = logger or LogManager.get_system_logger()

    @abstractmethod
    async def execute(self, *args, **kwargs):
        """执行服务方法"""
        pass


class AuthService(BaseService):
    """用户认证服务"""

    async def login_verify(self) -> UserInfo:
        """登录验证"""
        try:
            login_info = await self.api.loginVerift()
            mid = login_info.get('mid', 0)
            name = login_info.get('uname', '')

            if mid == 0:
                raise LoginError("登录失败，可能是 access_key 过期")

            # 获取用户详细信息
            user_info = await self.api.getUserInfo()
            return UserInfo(
                mid=mid,
                name=name,
                medal=user_info.get('medal'),
                raw_data=login_info
            )
        except Exception as e:
            raise LoginError(f"登录验证失败: {e}")

    async def execute(self, *args, **kwargs) -> UserInfo:
        """执行登录验证"""
        return await self.login_verify()


class MedalService(BaseService):
    """勋章管理服务"""

    def __init__(self, api: BiliApi, white_list: list[int], banned_list: list[int], watch_list: list[int], logger=None):
        super().__init__(api, logger)
        self.white_list = white_list
        self.banned_list = banned_list
        self.watch_list = watch_list

    async def get_all_medals(self) -> list[dict[str, Any]]:
        """获取所有勋章"""
        medals = []

        async for medal in self.api.getFansMedalandRoomID():
            room_id = safe_get(medal, 'room_info', 'room_id')

            # 必须有直播间
            if room_id == 0:
                continue

            medals.append(medal)

        return medals

    def _watch_allowed(self, target_id: int) -> bool:
        """watch_uid 控制观看任务；-1 关闭，0 不限制。"""
        if self.watch_list == [-1]:
            return False
        return self.watch_list == [0] or target_id in self.watch_list

    def interaction_allowed(self, target_id: int) -> bool:
        """使用原始黑白名单逻辑控制点赞和弹幕。"""
        if self.white_list == [0]:
            return target_id not in self.banned_list
        return target_id in self.white_list

    def classify_medals(
        self,
        medals: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """分类勋章"""
        classified = {
            'all': [],
            'need_watch': [],   # 需要观看心跳的勋章
            'living': [],       # 开播中的勋章
            'no_living': []     # 未开播的勋章
        }
        danmaku_all_offline = bool((config or {}).get('DANMAKU_ALL_OFFLINE'))

        for medal in medals:
            medal_data = safe_get(medal, 'medal', default={})
            room_status = safe_get(
                medal, 'room_info', 'living_status', default=0)
            medal_lighted = medal_data.get("is_lighted", 0)
            today_feed = medal_data.get('today_feed', 0)
            target_id = medal_data.get('target_id', 0)
            interaction_allowed = self.interaction_allowed(target_id)

            classified['all'].append(medal)

            if interaction_allowed and room_status == 1:
                classified['living'].append(medal)

            if interaction_allowed and room_status != 1 and (danmaku_all_offline or medal_lighted == 0):
                classified['no_living'].append(medal)

            day_limit = medal_data.get('day_limit', 0)
            if self._watch_allowed(target_id) and (day_limit == 0 or today_feed < day_limit):
                classified['need_watch'].append(medal)

        return classified

    async def execute(
        self,
        config: dict[str, Any] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """执行勋章获取和分类"""
        medals = await self.get_all_medals()
        return self.classify_medals(medals, config)


class LikeService(BaseService):
    """点赞服务"""

    async def like_medals(self, medals: list[dict[str, Any]], config: dict[str, Any]) -> bool:
        """点赞勋章"""
        if config.get('LIKE_CD', 0) == 0:
            self.log.info("点赞任务已关闭")
            return True

        if not medals:
            self.log.info("没有开播直播间，点赞任务无需执行")
            return True

        try:
            if not config.get('ASYNC', 0):
                await self._sync_like(medals, config)
            else:
                await self._async_like(medals, config)

            return True
        except Exception as e:
            self.log.exception("点赞任务异常")
            raise BiliException(f"点赞任务异常: {e}")

    async def _sync_like(self, medals: list[dict[str, Any]], config: dict[str, Any]):
        """同步点赞"""
        self.log.info("同步点赞任务开始....")

        for index, medal in enumerate(medals):
            click_time = random.randint(
                BiliConstants.Tasks.LIKE_CLICK_MIN,
                BiliConstants.Tasks.LIKE_CLICK_MAX,
            )
            await self.api.likeInteractV3(
                medal['room_info']['room_id'],
                medal['medal']['target_id'],
                self.api.u.mid,
                click_time=click_time,
            )

            self.log.success(
                f"{medal['anchor_info']['nick_name']} 点赞{click_time}次成功 "
                f"{index+1}/{len(medals)}"
            )
            if index + 1 < len(medals):
                await asyncio.sleep(config.get('LIKE_CD', 1))

    async def _async_like(self, medals: list[dict[str, Any]], config: dict[str, Any]):
        """异步点赞"""
        self.log.info("异步点赞任务开始....")

        tasks = [
            self.api.likeInteractV3(
                medal['room_info']['room_id'],
                medal['medal']['target_id'],
                self.api.u.mid,
                click_time=random.randint(
                    BiliConstants.Tasks.LIKE_CLICK_MIN,
                    BiliConstants.Tasks.LIKE_CLICK_MAX,
                ),
            )
            for medal in medals
        ]
        await asyncio.gather(*tasks)
        self.log.success(f"异步点赞{len(medals)}个牌子成功")

    async def execute(self, medals: list[dict[str, Any]], config: dict[str, Any]) -> bool:
        """执行点赞任务"""
        return await self.like_medals(medals, config)


class DanmakuService(BaseService):
    """弹幕服务"""

    async def send_danmaku_to_medals(self, medals: list[dict[str, Any]], config: dict[str, Any]) -> int:
        """向勋章发送弹幕"""
        if not config.get('DANMAKU_CD'):
            self.log.info("弹幕任务关闭")
            return 0

        if not medals:
            self.log.info("没有未开播且未点亮的粉丝牌，弹幕任务无需执行")
            return 0

        estimated_time = (
            len(medals) *
            config.get('DANMAKU_CD', 3) *
            config.get('DANMAKU_NUM', 10)
        )
        self.log.info(f"弹幕打卡任务开始....(预计 {estimated_time} 秒完成)")

        success_count = 0
        sent_any = False
        danmaku_num = config.get('DANMAKU_NUM', 10)

        for n, medal in enumerate(medals, 1):
            if config.get('WEARMEDAL'):
                await self.api.wearMedal(medal['medal']['medal_id'])
                await asyncio.sleep(0.5)

            anchor_name = medal['anchor_info']['nick_name']
            room_id = medal['room_info']['room_id']
            success_messages = []
            for i in range(danmaku_num):
                if sent_any:
                    await asyncio.sleep(config.get('DANMAKU_CD', 3))

                try:
                    sent_any = True
                    ret_msg = await self.api.sendDanmaku(room_id)
                except Exception as e:
                    self.log.error(f"{anchor_name} 弹幕发送失败: {e}")
                    break

                if "今日已发送过弹幕" in ret_msg:
                    self.log.warning(f"{anchor_name}: 今日已发送过弹幕，跳过后续弹幕")
                    break

                if self._is_send_success(ret_msg):
                    success_messages.append(ret_msg)
                    self.log.success(
                        f"{anchor_name}: {ret_msg} {i + 1}/{danmaku_num} "
                        f"({n}/{len(medals)})"
                    )
                    continue

                self.log.debug(f"{anchor_name}: {ret_msg}")

            if len(success_messages) == danmaku_num:
                success_count += 1

        return success_count

    def _is_send_success(self, ret_msg: str) -> bool:
        return ret_msg.startswith("弹幕发送成功:")

    async def execute(self, medals: list[dict[str, Any]], config: dict[str, Any]) -> int:
        """执行弹幕任务"""
        return await self.send_danmaku_to_medals(medals, config)


class HeartbeatService(BaseService):
    """心跳观看服务"""

    async def watch_medals(self, medals: list[dict[str, Any]], config: dict[str, Any]) -> bool:
        """观看直播间发送心跳"""
        watch_time = config.get('WATCHINGLIVE', 0)
        if not watch_time:
            self.log.info("每日观看直播任务关闭")
            return True

        if not medals:
            self.log.info("没有需要观看心跳的粉丝牌，每日观看直播任务无需执行")
            return True

        self.log.info(f"每日{watch_time}分钟任务开始")
        self.log.info(f"预计共需运行{watch_time * len(medals)}分钟（{len(medals)}个勋章）")

        # 顺序执行所有勋章的心跳任务
        for index, medal in enumerate(medals, 1):
            await self._watch_single_medal(medal, watch_time, index, len(medals))

        self.log.success(f"每日{watch_time}分钟任务完成")
        return True

    async def _watch_single_medal(self, medal: dict[str, Any], watch_time: int, index: int, total: int):
        """观看单个勋章的直播间"""
        anchor_name = medal['anchor_info']['nick_name']
        room_id = medal['room_info']['room_id']
        target_id = medal['medal']['target_id']

        self.log.info(
            f"开始观看 {anchor_name} 的直播间（{watch_time}分钟）- {index}/{total}")

        for minute in range(1, watch_time + 1):
            try:
                await self.api.heartbeat(room_id, target_id)

                if minute % 5 == 0:
                    self.log.success(
                        f"{anchor_name} 观看了 {minute} 分钟 ({index}/{total})")

                await asyncio.sleep(60)  # 每分钟发送一次

            except Exception as e:
                self.log.error(f"{anchor_name} 心跳发送失败: {e}")
                break

        self.log.success(f"{anchor_name} 观看任务完成 ({index}/{total})")

    async def execute(self, medals: list[dict[str, Any]], config: dict[str, Any]) -> bool:
        """执行观看任务"""
        return await self.watch_medals(medals, config)

    async def execute_one(
        self,
        medal: dict[str, Any],
        config: dict[str, Any],
        index: int,
        total: int,
    ) -> None:
        """执行单个直播间的观看任务。"""
        await self._watch_single_medal(
            medal,
            config.get('WATCHINGLIVE', 0),
            index,
            total,
        )
