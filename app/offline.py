"""恢复游戏不推进现实离线时间；只补结已经到期的游戏内事实。"""
from . import engine, storage
from .models import now_iso


class OfflineError(RuntimeError):
    pass


def _elapsed(state: dict):
    """保留旧调用兼容；现实时间不再是世界模拟输入。"""
    return None


def check_offline(state: dict) -> list[dict]:
    notes = engine._tick_calendar(state)
    if not notes:
        return []
    items = [{"ts": now_iso(), "type": "event", "world": "urban", "title": "当前游戏日结算", "text": note} for note in notes]
    state["inbox"] = (state.get("inbox", []) + items)[-50:]
    storage.save(state, backup=False)
    return items
