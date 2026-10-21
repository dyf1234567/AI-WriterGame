"""离线演化：回到游戏时按离开的真实时长结算世界变化。"""
from datetime import datetime, timezone

from . import demo, llm, storage
from .config import DEMO_MODE, OFFLINE_MAX_HOURS, OFFLINE_THRESHOLD_MINUTES
from . import engine
from .contracts import OfflineResult
from .engine import _apply_npc_events, _clean_text, npc_remember
from .models import AFFINITY_OFFLINE_CAP, clamp, find_npc, now_iso
from .prompts import build_offline_prompt


class OfflineError(RuntimeError):
    pass


def _elapsed(state: dict) -> float | None:
    """返回离线小时数；未达阈值返回 None。"""
    try:
        last = datetime.fromisoformat(state["last_active"])
    except (ValueError, KeyError):
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    minutes = (now - last).total_seconds() / 60
    if minutes < OFFLINE_THRESHOLD_MINUTES:
        return None
    return min((now - last).total_seconds() / 3600, OFFLINE_MAX_HOURS)


def check_offline(state: dict) -> list[dict]:
    """结算离线演化，返回新增的收件箱条目；无变化返回空列表。"""
    hours = _elapsed(state)
    if hours is None:
        # 不重置离线锚点；频繁打开页面不能吞掉累计的未结算时间。
        return []

    days = round(hours / 24, 3)

    if DEMO_MODE:
        data = demo.offline_result(state, days)
    else:
        system, user = build_offline_prompt(state, days)
        try:
            data = OfflineResult.model_validate(llm.chat_json(system, user, temperature=0.9)).model_dump()
        except Exception as e:
            # 离线结算失败不阻塞玩家继续游戏
            raise OfflineError(f"离线演化生成失败：{e}")

    ts = now_iso()
    new_items: list[dict] = []
    for ev in data.get("events") or []:
        if not isinstance(ev, dict) or not ev.get("title"):
            continue
        new_items.append({
            "ts": ts, "type": "event", "world": "urban",
            "title": _clean_text(ev["title"], 40),
            "text": _clean_text(ev.get("text"), 400),
        })
    for msg in data.get("messages") or []:
        if not isinstance(msg, dict) or not msg.get("npc"):
            continue
        npc = find_npc(state, str(msg.get("npc", "")))
        # 未结识的人不留言——不然玩家点「回复」必被"先去认识"挡下
        if npc is None or not npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0):
            continue
        npc["last_seen_turn"] = state["turn"]
        npc_remember(npc, state["turn"],
                     f"给主角留言：「{_clean_text(msg.get('title', '留言'), 20)}」",
                     prefix="离线期间：")
        new_items.append({
            "ts": ts, "type": "message",
            "from": npc["name"],
            "title": _clean_text(msg.get("title", "留言"), 40),
            "text": _clean_text(msg.get("text"), 400),
        })

    # 朋友圈动态：日常向的"世界呼吸"，收进收件箱
    for mo in data.get("moments") or []:
        if not isinstance(mo, dict) or not mo.get("npc"):
            continue
        npc = find_npc(state, str(mo.get("npc", "")))
        if npc is None or not npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0):
            continue  # 未结识者的动态不出现——朋友圈只属于认识的人
        img = _clean_text(mo.get("image"), 40) or "新发的动态配图"
        new_items.append({
            "ts": ts, "type": "moment", "from": npc["name"],
            "title": f"{npc['name']}的朋友圈",
            "text": _clean_text(mo.get("text"), 200),
            "image": img,
        })

    # 离线好感同样有护栏：跨多天结算放宽一档，但单 NPC 不得被一次灌满
    offline_applied: dict[str, int] = {}
    affinity_notices: list[str] = []
    for ch in data.get("affinity_changes") or []:
        if not isinstance(ch, dict):
            continue
        npc = find_npc(state, str(ch.get("npc", "")))
        delta = ch.get("delta", 0)
        if npc is None or not isinstance(delta, (int, float)):
            continue
        done = offline_applied.get(npc["name"], 0)
        eff = clamp(done + int(delta), -AFFINITY_OFFLINE_CAP, AFFINITY_OFFLINE_CAP) - done
        offline_applied[npc["name"]] = done + eff
        _, notices = engine.change_affinity(state, npc, eff)
        affinity_notices.extend(notices)
        reason = _clean_text(ch.get("reason"), 60)
        if reason:
            npc_remember(npc, state["turn"], reason, prefix="离线期间：")

    # NPC 间关系事件直接落进双方关系与记忆
    _apply_npc_events(state, data.get("npc_events"))

    affinity_notices.extend(engine.settle_growth(state))
    for notice in affinity_notices:
        new_items.append({"ts": ts, "type": "event", "world": "urban",
                          "title": "关系与成长", "text": notice})

    state["inbox"].extend(new_items)
    state["inbox"] = state["inbox"][-50:]
    # 游戏时间同步流逝：你离开的每一天，世界也走过一天（上限仍 7 天）
    t = state.setdefault("time", {"day": 1, "slot": 0})
    elapsed_game_days = min(int(days), 7)
    if elapsed_game_days > 0:
        t["day"] = int(t.get("day", 1)) + elapsed_game_days
        t["slot"] = 0  # 回来时是新的一天的清晨
    state["last_active"] = now_iso()
    storage.save(state)
    return new_items
