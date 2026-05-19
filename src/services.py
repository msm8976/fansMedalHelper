"""
业务服务层模块
"""
import asyncio
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

    def __init__(self, api: BiliApi, white_list: list[int], banned_list: list[int], logger=None):
        super().__init__(api, logger)
        self.white_list = white_list
        self.banned_list = banned_list

    async def get_all_medals(self, show_logs: bool = True) -> list[dict[str, Any]]:
        """获取所有勋章"""
        medals = []
        filtered_count = 0
        whitelist_count = 0

        async for medal in self.api.getFansMedalandRoomID():
            target_id = safe_get(medal, 'medal', 'target_id')
            room_id = safe_get(medal, 'room_info', 'room_id')
            anchor_name = safe_get(medal, 'anchor_info',
                                   'nick_name', default='未知用户')

            # 必须有直播间
            if room_id == 0:
                continue

            # 黑名单模式
            if self.white_list == [0]:
                if target_id in self.banned_list:
                    if show_logs:
                        self.log.warning(f"{anchor_name} 在黑名单中，已过滤")
                    filtered_count += 1
                    continue
                medals.append(medal)
            else:
                # 白名单模式
                if target_id in self.white_list:
                    if show_logs:
                        self.log.success(f"{anchor_name} 在白名单中，加入任务")
                    medals.append(medal)
                    whitelist_count += 1

        return medals

    def _should_include_medal(self, medal: dict[str, Any]) -> bool:
        """判断是否应该包含该勋章"""
        target_id = safe_get(medal, 'medal', 'target_id')
        room_id = safe_get(medal, 'room_info', 'room_id')

        # 必须有直播间
        if room_id == 0:
            return False

        # 黑名单模式
        if self.white_list == [0]:
            if target_id in self.banned_list:
                return False
            return True

        # 白名单模式
        if target_id in self.white_list:
            return True

        return False

    def classify_medals(self, medals: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """分类勋章"""
        classified = {
            'need_do': [],      # 需要做任务的勋章
            'others': [],       # 其他勋章
            'living': [],       # 开播中的勋章
            'no_living': []     # 未开播的勋章
        }

        for medal in medals:
            medal_data = safe_get(medal, 'medal', default={})
            room_status = safe_get(
                medal, 'room_info', 'living_status', default=0)
            medal_lighted = medal_data.get("is_lighted", 0)
            today_feed = medal_data.get('today_feed', 0)

            # 勋章点亮分类
            if medal_lighted == 0:
                if room_status == 1:
                    classified['living'].append(medal)
                else:
                    classified['no_living'].append(medal)

            # 任务分类
            if today_feed < 30:
                classified['need_do'].append(medal)
            else:
                classified['others'].append(medal)

        return classified

    async def execute(self, show_logs: bool = True, *args, **kwargs) -> dict[str, list[dict[str, Any]]]:
        """执行勋章获取和分类"""
        medals = await self.get_all_medals(show_logs)
        return self.classify_medals(medals)


class LikeService(BaseService):
    """点赞服务"""

    async def like_medals(self, medals: list[dict[str, Any]], config: dict[str, Any]) -> bool:
        """点赞勋章"""
        if config.get('LIKE_CD', 0) == 0:
            self.log.info("点赞任务已关闭")
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
            for i in range(BiliConstants.Tasks.LIKE_COUNT_SYNC):
                if config.get('LIKE_CD'):
                    await self.api.likeInteractV3(
                        medal['room_info']['room_id'],
                        medal['medal']['target_id'],
                        self.api.u.mid
                    )
                await asyncio.sleep(config.get('LIKE_CD', 1))

            self.log.success(
                f"{medal['anchor_info']['nick_name']} 点赞{i+1}次成功 "
                f"{index+1}/{len(medals)}"
            )

    async def _async_like(self, medals: list[dict[str, Any]], config: dict[str, Any]):
        """异步点赞"""
        self.log.info("异步点赞任务开始....")

        for i in range(BiliConstants.Tasks.LIKE_COUNT_ASYNC):
            if config.get('LIKE_CD'):
                tasks = [
                    self.api.likeInteractV3(
                        medal['room_info']['room_id'],
                        medal['medal']['target_id'],
                        self.api.u.mid
                    )
                    for medal in medals
                ]
                await asyncio.gather(*tasks)

            self.log.success(f"异步点赞第{i+1}次成功")
            await asyncio.sleep(config.get('LIKE_CD', 1))

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

        estimated_time = (
            len(medals) *
            config.get('DANMAKU_CD', 3) *
            config.get('DANMAKU_NUM', 10)
        )
        self.log.info(f"弹幕打卡任务开始....(预计 {estimated_time} 秒完成)")

        success_count = 0

        for n, medal in enumerate(medals, 1):
            if config.get('WEARMEDAL'):
                await self.api.wearMedal(medal['medal']['medal_id'])
                await asyncio.sleep(0.5)

            anchor_name = medal['anchor_info']['nick_name']
            room_id = medal['room_info']['room_id']

            for i in range(config.get('DANMAKU_NUM', 10)):
                try:
                    ret_msg = await self.api.sendDanmaku(room_id)
                    self.log.debug(f"{anchor_name}: {ret_msg}")

                    if "重复弹幕" in ret_msg:
                        self.log.warning(f"{anchor_name}: 重复弹幕, 跳过后续弹幕")
                        break

                    await asyncio.sleep(config.get('DANMAKU_CD', 3))

                except Exception as e:
                    self.log.error(f"{anchor_name} 弹幕发送失败: {e}")
                    break
            else:
                success_count += 1
                self.log.success(f"{anchor_name} 弹幕打卡成功 {n}/{len(medals)}")

        return success_count

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


class GroupService(BaseService):
    """应援团服务"""

    async def sign_in_groups(self, config: dict[str, Any]) -> int:
        """应援团签到"""
        if not config.get('SIGNINGROUP'):
            self.log.info("应援团签到任务关闭")
            return 0

        self.log.info("应援团签到任务开始")
        success_count = 0

        try:
            async for group in self.api.getGroups():
                if group['owner_uid'] == self.api.u.mid:
                    continue

                try:
                    await self.api.signInGroups(group['group_id'], group['owner_uid'])
                    self.log.success(f"{group['group_name']} 签到成功")
                    success_count += 1
                    await asyncio.sleep(config.get('SIGNINGROUP', 2))

                except Exception as e:
                    self.log.error(f"{group['group_name']} 签到失败: {e}")
                    continue

        except KeyError as e:
            # 没有应援团时静默处理
            if str(e) != "'list'":
                self.log.error(f"获取应援团列表失败: {e}")
        except Exception as e:
            self.log.error(f"获取应援团列表失败: {e}")

        if success_count:
            self.log.success(f"应援团签到任务完成 {success_count}个")

        return success_count

    async def execute(self, config: dict[str, Any]) -> int:
        """执行应援团签到"""
        return await self.sign_in_groups(config)
