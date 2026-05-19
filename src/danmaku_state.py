"""
弹幕发送状态管理。
"""
import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


class DanmakuStateStore:
    """记录同一账号同一直播间每日弹幕发送状态。"""

    _lock = Lock()

    def __init__(self, state_file: Path | str = ".state/danmaku.json"):
        self.state_file = Path(state_file)

    def has_sent_today(self, mid: int, room_id: int) -> bool:
        today = self._today()
        with self._lock:
            state = self._load_state()
            return self._key(mid, room_id, today) in state["records"]

    def record_sent(self, mid: int, room_id: int, message: str) -> None:
        today = self._today()
        with self._lock:
            state = self._load_state()
            state["records"][self._key(mid, room_id, today)] = {
                "mid": mid,
                "room_id": room_id,
                "date": today,
                "message": message,
                "sent_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._save_state(state)

    def _load_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {"records": {}}

        with self.state_file.open(encoding="utf-8") as file:
            state = json.load(file)

        if not isinstance(state, dict) or not isinstance(state.get("records"), dict):
            raise ValueError(f"弹幕状态文件格式错误: {self.state_file}")

        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.state_file.open("w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def _today(self) -> str:
        return datetime.now().date().isoformat()

    def _key(self, mid: int, room_id: int, date: str) -> str:
        return f"{mid}:{room_id}:{date}"
