"""
用户管理模块 - 重构版
"""
import asyncio
import uuid
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .api import BiliApi
from .constants import BiliConstants
from .exceptions import LoginError
from .logger_manager import LogManager
from .services import AuthService, DanmakuService, HeartbeatService, LikeService, MedalService
from .stats_service import ReportContext, StatsService


class BiliUser:
    """B站用户类"""

    def __init__(self, access_token: str, white_uids: str = '', banned_uids: str = '', watch_uids: str = '-1', config: dict[str, Any] = None):
        # 基本信息
        self.mid: int = 0
        self.name: str = ""
        self.access_key: str = access_token
        self.config: dict[str, Any] = config or {}
        self.is_login: bool = False

        # 解析任务名单
        self._parse_uid_lists(white_uids, banned_uids, watch_uids)

        # 勋章列表
        self.medals: list[dict[str, Any]] = []
        self.medalsNeedWatch: list[dict[str, Any]] = []
        self.medalsLiving: list[dict[str, Any]] = []
        self.medalsNoLiving: list[dict[str, Any]] = []
        self.medalsBeforeTasks: list[dict[str, Any]] = []
        self.taskActions: dict[int, set[str]] = {}
        self.like_attempted: set[int] = set()
        self.danmaku_attempted: set[int] = set()

        # 会话和API
        self.session = ClientSession(
            timeout=ClientTimeout(total=3), trust_env=True)
        self.api = BiliApi(self, self.session)

        # 业务服务层
        self.auth_service = AuthService(self.api)
        self.medal_service = MedalService(
            self.api, self.whiteList, self.bannedList, self.watchList)
        self.like_service = LikeService(self.api)
        self.danmaku_service = DanmakuService(self.api)
        self.heartbeat_service = HeartbeatService(self.api)
        self.stats_service = None  # 将在登录验证后初始化

        # 任务状态
        self.retry_times: int = 0
        self.max_retry_times: int = BiliConstants.Tasks.MAX_RETRY_TIMES
        self.message: list[str] = []
        self.errmsg: list[str] = []
        self.uuids: list[str] = [str(uuid.uuid4()) for _ in range(2)]

        # 日志
        self.log = LogManager.get_system_logger()  # 初始化系统日志，登录成功后会更新为用户专用日志

    def _parse_uid_lists(self, white_uids: str, banned_uids: str, watch_uids: str):
        """解析点赞/弹幕名单和观看名单。"""
        try:
            self.whiteList = [
                int(x) if x else 0 for x in str(white_uids).split(',')]
            self.bannedList = [
                int(x) if x else 0 for x in str(banned_uids).split(',')]
            self.watchList = [
                int(x) if x else 0 for x in str(watch_uids).split(',')]
        except ValueError:
            raise ValueError("任务 UID 名单格式错误")

    async def login_verify(self) -> bool:
        """登录验证"""
        try:
            user_info = await self.auth_service.execute()
            self.mid = user_info.mid
            self.name = user_info.name

            # 初始化日志和统计服务
            self.log = LogManager.get_logger(self.name)
            self.stats_service = StatsService(self.api, self.name, self.log)

            # 重新初始化服务，使用用户专有的日志记录器
            self.medal_service = MedalService(
                self.api, self.whiteList, self.bannedList, self.watchList, self.log)
            self.like_service = LikeService(self.api, self.log)
            self.danmaku_service = DanmakuService(self.api, self.log)
            self.heartbeat_service = HeartbeatService(self.api, self.log)
            # 获取初始佩戴勋章信息
            if user_info.medal:
                medal_info = await self.api.getMedalsInfoByUid(user_info.medal['target_id'])
                if medal_info.get('has_fans_medal'):
                    self.initialMedal = medal_info['my_fans_medal']

            self.log.success(f"{self.mid} 登录成功")
            self.is_login = True
            return True

        except LoginError as e:
            self.log.error(f"登录失败: {e}")
            self.errmsg.append(f"登录失败: {e}")
            self.is_login = False
            return False
        except Exception as e:
            self.log.error(f"登录异常: {e}")
            self.errmsg.append(f"登录异常: {e}")
            self.is_login = False
            return False

    async def get_medals(self):
        """获取用户勋章"""
        classified_medals = await self.medal_service.execute(self.config)

        # 清空原有勋章列表
        self._clear_medal_lists()

        # 设置分类后的勋章
        self.medals = classified_medals['all']
        self.medalsNeedWatch = classified_medals['need_watch']
        self.medalsLiving = classified_medals['living']
        self.medalsNoLiving = classified_medals['no_living']

    def _clear_medal_lists(self):
        """清空勋章列表"""
        for attr in ['medals', 'medalsNeedWatch', 'medalsLiving', 'medalsNoLiving']:
            getattr(self, attr).clear()

    async def init(self):
        """初始化用户"""
        if not await self.login_verify():
            self.log.error("登录失败 可能是 access_key 过期 , 请重新获取")
            self.errmsg.append("登录失败 可能是 access_key 过期 , 请重新获取")
            await self.session.close()

    async def start(self):
        """开始执行任务"""
        if not self.is_login:
            return

        # 获取勋章信息
        await self.get_medals()
        self.medalsBeforeTasks = list(self.medals)
        self.taskActions = {}
        self.like_attempted.clear()
        self.danmaku_attempted.clear()

        watch_medals = list(self.medalsNeedWatch) if self.config.get('WATCHINGLIVE') else []
        interaction_task = asyncio.create_task(self._run_new_interactions())

        for index, medal in enumerate(watch_medals, 1):
            self._add_task_actions(self.taskActions, [medal], "观看")
            await self.heartbeat_service.execute_one(
                medal,
                self.config,
                index,
                len(watch_medals),
            )

            if interaction_task.done():
                await interaction_task
                await self.get_medals()
                interaction_task = asyncio.create_task(self._run_new_interactions())

        await interaction_task
        await self.get_medals()
        await self._run_new_interactions()

    async def _run_new_interactions(self) -> None:
        tasks = []

        if self.config.get('LIKE_CD'):
            medals = self._not_attempted(self.medalsLiving, self.like_attempted)
            if medals:
                self.like_attempted.update(
                    medal['medal']['target_id'] for medal in medals)
                self._add_task_actions(self.taskActions, medals, "点赞")
                tasks.append(self.like_service.execute(medals, self.config))

        if self.config.get('DANMAKU_CD') and self.config.get('DANMAKU_NUM'):
            medals = self._not_attempted(
                self.medalsNoLiving, self.danmaku_attempted)
            if medals:
                self.danmaku_attempted.update(
                    medal['medal']['target_id'] for medal in medals)
                self._add_task_actions(self.taskActions, medals, "弹幕")
                tasks.append(self.danmaku_service.execute(medals, self.config))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _not_attempted(
        self,
        medals: list[dict[str, Any]],
        attempted: set[int],
    ) -> list[dict[str, Any]]:
        return [
            medal for medal in medals
            if medal['medal']['target_id'] not in attempted
        ]

    def _add_task_actions(
        self,
        actions: dict[int, set[str]],
        medals: list[dict[str, Any]],
        action: str,
    ) -> None:
        for medal in medals:
            target_id = medal['medal']['target_id']
            actions.setdefault(target_id, set()).add(action)

    async def send_msg(self):
        """发送消息统计"""
        if not self.is_login:
            await self.session.close()
            return self.message + self._error_messages()

        # 重新获取勋章数据以确保统计的准确性（按照原始项目逻辑，不显示日志）
        await self.get_medals()

        # 使用统计服务生成报告
        report_context = ReportContext(
            initial_medal=getattr(self, 'initialMedal', None),
            before_medals=self.medalsBeforeTasks,
            task_actions=self.taskActions,
        )
        report_messages = await self.stats_service.execute(
            self.medals,
            report_context,
        )
        self.message.extend(report_messages)

        await self.session.close()
        return self.message + self._error_messages() + ['---']

    def _error_messages(self) -> list[str]:
        if not self.errmsg:
            return []

        return ["错误日志：", *self.errmsg]

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.session.close()
