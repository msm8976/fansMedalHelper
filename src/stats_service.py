"""
统计和报告服务模块
"""
from typing import Any

from .services import BaseService
from .utils import safe_get


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

    def generate_report_messages(self, unlit_medals: list[str]) -> list[str]:
        """生成统计报告消息"""
        messages = [f"【{self.user_name}】 今日任务情况如下："]

        if unlit_medals:
            display_names = ' '.join(unlit_medals[:5])
            if len(unlit_medals) > 5:
                display_names += '等'
            messages.append(f"【未点亮】{display_names} {len(unlit_medals)}个")

        return messages

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

    async def execute(self, medals: list[dict[str, Any]], initial_medal: dict[str, Any] | None = None) -> list[str]:
        """生成完整的统计报告"""
        unlit_medals = self.calculate_unlit_medals(medals)
        messages = self.generate_report_messages(unlit_medals)

        if initial_medal:
            medal_info = await self.get_current_medal_info(initial_medal)
            messages.extend(medal_info)

        return messages
