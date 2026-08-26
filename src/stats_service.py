"""
统计和报告服务模块
"""
from dataclasses import dataclass, field
from typing import Any

from .services import BaseService
from .utils import safe_get


@dataclass(frozen=True)
class ReportContext:
    """任务报告上下文"""

    initial_medal: dict[str, Any] | None = None
    before_medals: list[dict[str, Any]] = field(default_factory=list)
    task_actions: dict[int, set[str]] = field(default_factory=dict)


class StatsService(BaseService):
    """统计服务"""

    def __init__(self, api, user_name: str, logger=None):
        super().__init__(api, logger)
        self.user_name = user_name

    def calculate_unlit_medals(self, medals: list[dict[str, Any]]) -> list[str]:
        """计算未点亮勋章"""
        unlit_medals = []

        for medal in medals:
            nick_name = safe_get(medal, 'anchor_info',
                                 'nick_name', default='未知用户')
            is_lighted = safe_get(medal, 'medal', 'is_lighted', default=1)

            if not is_lighted:
                unlit_medals.append(nick_name)

        return unlit_medals

    def generate_report_messages(
        self,
        unlit_medals: list[str],
        action_messages: list[str],
    ) -> list[str]:
        """生成统计报告消息"""
        messages = [f"【{self.user_name}】 今日任务情况如下："]
        messages.extend(action_messages)

        if unlit_medals:
            display_names = ' '.join(unlit_medals[:5])
            if len(unlit_medals) > 5:
                display_names += '等'
            messages.append(f"【未点亮】{display_names} {len(unlit_medals)}个")

        return messages

    def generate_action_messages(
        self,
        before_medals: list[dict[str, Any]],
        after_medals: list[dict[str, Any]],
        task_actions: dict[int, set[str]],
    ) -> list[str]:
        """生成本轮任务操作报告"""
        if not task_actions:
            return ["【本轮操作】无"]

        before_index = self._index_medals(before_medals)
        seen_target_ids = set()
        entries = []

        for medal in after_medals:
            target_id = safe_get(medal, 'medal', 'target_id')
            if not target_id:
                continue

            target_id = int(target_id)
            if (
                target_id not in task_actions
                or target_id not in before_index
                or target_id in seen_target_ids
            ):
                continue
            seen_target_ids.add(target_id)

            name = safe_get(medal, 'anchor_info', 'nick_name', default='未知用户')
            medal_name = safe_get(medal, 'medal', 'medal_name', default='未知粉丝牌')
            delta = self._today_feed_delta(before_index.get(target_id), medal)
            entries.append(
                (delta, f"【{medal_name}】{name} 今日亲密度 +{delta}")
            )

        entries.sort(key=lambda entry: -entry[0])
        messages = [message for _, message in entries]

        return messages or ["【本轮操作】无"]

    def _index_medals(self, medals: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        indexed = {}

        for medal in medals:
            target_id = safe_get(medal, 'medal', 'target_id')
            if target_id:
                indexed[int(target_id)] = medal

        return indexed

    def _today_feed_delta(
        self,
        before_medal: dict[str, Any] | None,
        after_medal: dict[str, Any],
    ) -> int:
        before_feed = safe_get(before_medal or {}, 'medal', 'today_feed', default=0)
        after_feed = safe_get(after_medal, 'medal', 'today_feed', default=0)
        return max(0, after_feed - before_feed)

    async def get_current_medal_info(self, initial_medal: dict[str, Any]) -> list[str]:
        """获取当前佩戴勋章信息"""
        messages = []

        try:
            initial_medal_info = await self.api.getMedalsInfoByUid(initial_medal['target_id'])

            if initial_medal_info.get('has_fans_medal'):
                medal = initial_medal_info['my_fans_medal']
                messages.append(
                    f"【当前佩戴】「{medal['medal_name']}」({medal['target_name']}) "
                    f"{medal['level']} 级 "
                )
        except Exception as e:
            self.log.error(f"获取当前勋章信息失败: {e}")

        return messages

    async def execute(
        self,
        medals: list[dict[str, Any]],
        context: ReportContext | None = None,
    ) -> list[str]:
        """生成完整的统计报告"""
        report_context = context or ReportContext()
        unlit_medals = self.calculate_unlit_medals(medals)
        action_messages = self.generate_action_messages(
            report_context.before_medals,
            medals,
            report_context.task_actions,
        )
        messages = self.generate_report_messages(unlit_medals, action_messages)

        if report_context.initial_medal:
            medal_info = await self.get_current_medal_info(report_context.initial_medal)
            messages.extend(medal_info)

        return messages
