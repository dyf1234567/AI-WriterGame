"""The game clock is the only clock that advances the world."""
from copy import deepcopy
from datetime import date

SLOT_STARTS = (360, 540, 840, 1080, 1260)
MAX_SKIP_DAYS = 1095


def ensure_clock(state: dict) -> dict:
    t = state.setdefault("time", {"day": 1, "slot": 0})
    day = max(1, int(t.get("day", 1)))
    slot = max(0, min(4, int(t.get("slot", 0))))
    if ("minute" not in t or t.get("clock_day", day) != day
            or t.get("clock_slot", slot) != slot):
        t["minute"] = SLOT_STARTS[slot]
    t.update(day=day, slot=slot, minute=max(0, min(1439, int(t.get("minute", SLOT_STARTS[slot])))),
             clock_day=day, clock_slot=slot)
    state.setdefault("clock", {}).setdefault("settled_day", day)
    return t


def advance_minutes(state: dict, minutes: int) -> None:
    t = ensure_clock(state)
    minutes = max(0, int(minutes))
    absolute = (t["day"] - 1) * 1440 + t["minute"] + minutes
    day, minute = absolute // 1440 + 1, absolute % 1440
    slot = sum(minute >= boundary for boundary in SLOT_STARTS[1:])
    t.update(day=day, minute=minute, slot=slot, clock_day=day, clock_slot=slot)


def absolute_minute(state: dict) -> int:
    t = ensure_clock(state)
    return (t["day"] - 1) * 1440 + t["minute"]


def settle_world(state: dict) -> list[str]:
    """Replay each crossed day once, so large skips preserve causal event order."""
    from . import career, goals, world_events, world_sim
    from .models import GAME_EPOCH, game_today
    target = deepcopy(ensure_clock(state))
    clock = state.setdefault("clock", {})
    start = min(target["day"], max(1, int(clock.get("settled_day", target["day"]))))
    # Legacy callers may only have the old ISO calendar cursor.
    old_day = (state.get("calendar") or {}).get("day")
    if old_day:
        try:
            start = min(start, max(1, (date.fromisoformat(old_day) - GAME_EPOCH).days + 1))
        except (TypeError, ValueError):
            pass
    notices = []
    world_sim.ensure_world(state)
    for day in range(start + 1, target["day"] + 1):
        state["time"] = deepcopy(target) if day == target["day"] else {"day": day, "slot": 4, "minute": 1439, "clock_day": day, "clock_slot": 4}
        notices.extend(_settle_activity_day(state, day))
        notices.extend(career.settle_until(state, day - 1, day))
        notices.extend(world_events.settle_elapsed(state, day - 1, day))
        notices.extend(world_sim.advance_world(state, day - 1, day))
        _education_day(state, day)
        clock["settled_day"] = day
    state["time"] = target
    notices.extend(world_sim.advance_world(state, target["day"], target["day"]))
    # Also settle projects completed within this game day; career owns its own paid cursor.
    notices.extend(career.settle_until(state, target["day"], target["day"]))
    notices.extend(goals.sync_objectives(state))
    calendar = state.setdefault("calendar", {})
    if calendar.get("day") != game_today(state):
        calendar["day"] = game_today(state)
        note = world_events.on_new_day(state)
        if note:
            notices.append(note)
    clock["settled_day"] = target["day"]
    clock["last_summary"] = notices[-12:]
    if len(notices) > 12:
        notices = [f"【行程】经过 {target['day'] - start} 天，世界有 {len(notices)} 项变化，完整结果保存在资产、人物与事件记录中。"] + notices[-12:]
    return notices


def _settle_activity_day(state: dict, day: int) -> list[str]:
    """Only a completed day can fund that day's projects or improve their skills."""
    clock = state.setdefault('clock', {})
    plan = clock.get('activity')
    if not isinstance(plan, dict):
        return []
    days = max(0, int(plan.get('days', 0)))
    completed = max(0, int(plan.get('completed_days', 0)))
    due = min(days, max(0, day - int(plan.get('start_day', day))))
    if due <= completed:
        return []
    from . import skills
    from .economy import credit
    notices = []
    for _ in range(completed, due):
        if plan.get('kind') == 'work':
            credit(state, 35)
        elif plan.get('kind') == 'train':
            notices.extend(skills.add_xp(state, plan['skill'], 12))
        elif plan.get('kind') == 'study':
            education = state['player']['education']
            if education.get('status') == 'enrolled':
                education['credits'] = min(160, int(education.get('credits', 0)) + 1)
                notices.extend(skills.add_xp(state, 'coding', 8))
        plan['completed_days'] = int(plan.get('completed_days', 0)) + 1
    if plan['completed_days'] >= days:
        clock['last_activity'] = {**plan, 'completed_day': day}
        clock.pop('activity', None)
    return notices


def _education_day(state: dict, day: int) -> None:
    education = state["player"].setdefault("education", {
        "school": "京华大学", "status": "enrolled", "credits": 0, "progress": 0})
    if education.get("status") == "enrolled":
        import re
        year = min(4, 1 + (day - 1) // 365)
        education["year"] = year
        identities = state["player"].setdefault("identity", {})
        current = identities.get("urban", "")
        identities["urban"] = re.sub(r"大[一二三四](?:新生|学生|在读生)", f"大{'一二三四'[year-1]}学生", current)
    if education.get("status") == "enrolled" and day >= 1096 and int(education.get("credits", 0)) >= 120:
        education.update(status="graduated", graduated_day=day)
        state["player"].setdefault("identity", {})["urban"] = "京华大学毕业生"
        state.setdefault("inbox", []).append({"type": "event", "world": "urban", "title": "毕业手续办妥",
                                             "text": "你完成了学业要求，校园经历成为人生的一部分。接下来的生活由你安排。"})


def clock_view(state: dict) -> dict:
    t = ensure_clock(state)
    return {"day": t["day"], "hour": t["minute"] // 60, "minute": t["minute"] % 60,
            "label": f"{t['minute'] // 60:02d}:{t['minute'] % 60:02d}",
            "max_skip_days": MAX_SKIP_DAYS, "mode": "game_time", "recent": (state.get("clock") or {}).get("last_summary", [])}
