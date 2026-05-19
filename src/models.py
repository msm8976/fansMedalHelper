"""
数据模型模块
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class Medal:
    """勋章数据模型"""
    medal_id: int
    target_id: int
    target_name: str
    medal_name: str
    level: int
    today_feed: int
    intimacy: int
    next_intimacy: int
    is_lighted: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Medal':
        """从字典创建勋章对象"""
        medal_data = data.get('medal', {})
        return cls(
            medal_id=medal_data.get('medal_id', 0),
            target_id=medal_data.get('target_id', 0),
            target_name=medal_data.get('target_name', ''),
            medal_name=medal_data.get('medal_name', ''),
            level=medal_data.get('level', 0),
            today_feed=medal_data.get('today_feed', 0),
            intimacy=medal_data.get('intimacy', 0),
            next_intimacy=medal_data.get('next_intimacy', 0),
            is_lighted=medal_data.get('is_lighted', 0) == 1,
        )


@dataclass
class RoomInfo:
    """直播间信息数据模型"""
    room_id: int
    living_status: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'RoomInfo':
        """从字典创建直播间信息对象"""
        room_data = data.get('room_info', {})
        return cls(
            room_id=room_data.get('room_id', 0),
            living_status=room_data.get('living_status', 0)
        )


@dataclass
class AnchorInfo:
    """主播信息数据模型"""
    uid: int
    nick_name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AnchorInfo':
        """从字典创建主播信息对象"""
        anchor_data = data.get('anchor_info', {})
        return cls(
            uid=anchor_data.get('uid', 0),
            nick_name=anchor_data.get('nick_name', '')
        )


@dataclass
class MedalWithRoom:
    """带直播间信息的勋章数据模型"""
    medal: Medal
    room_info: RoomInfo
    anchor_info: AnchorInfo

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'MedalWithRoom':
        """从字典创建勋章和直播间对象"""
        return cls(
            medal=Medal.from_dict(data),
            room_info=RoomInfo.from_dict(data),
            anchor_info=AnchorInfo.from_dict(data)
        )


@dataclass
class UserInfo:
    """用户信息数据模型"""
    mid: int
    name: str
    medal: dict[str, Any] | None = None
    raw_data: dict[str, Any] | None = None


@dataclass
class Group:
    """应援团数据模型"""
    group_id: int
    group_name: str
    owner_uid: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Group':
        """从字典创建应援团对象"""
        return cls(
            group_id=data.get('group_id', 0),
            group_name=data.get('group_name', ''),
            owner_uid=data.get('owner_uid', 0)
        )
