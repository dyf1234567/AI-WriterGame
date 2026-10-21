"""玩家自定义人生目标：系统只记录、提示与反馈，不替玩家决定人生。"""
from .models import clamp, game_today

MAX_ACTIVE_GOALS = 5
MIN_TARGET_DAYS = 7
MAX_TARGET_DAYS = 1095
MODEL_PROGRESS_TURN_CAP = 25
MANUAL_PROGRESS = 5
NOTES_KEPT = 6

# 系统只给起点，不替玩家写完整人生。玩家的实际路线由自由行动决定。
GOAL_PLANS = {
    "商业": ("先算清启动资金与第一笔成本，做一次真实的小规模试卖",
             "把一个小项目跑通，并留下完整账本",
             "复盘现金流与竞争，决定扩张还是收手"),
    "娱乐": ("打磨一项能拿出手的作品（声乐/乐器/演技/台风）",
             "完成一次公开演出或发布",
             "根据反馈决定下一步：签约、独立还是换赛道"),
    "电竞": ("把操作与意识练到稳定水平",
             "参加一次正式比赛，并回看录像",
             "复盘战绩，决定职业、主播还是战队经营"),
    "学业": ("补齐核心课程或技能，拿出一次可展示的成果",
             "完成一次有反馈的阶段成果",
             "复盘成绩与方向，决定深造还是就业"),
    "关系": ("创造一次真正的共同经历",
             "把重要的话说清楚，确认彼此的边界",
             "根据对方的选择决定继续、放缓或告别"),
    "生活": ("先完成一件今天就能做的小事",
             "坚持一个周期，并记录变化",
             "复盘并调整方向"),
    "其他": ("把目标拆成第一件具体行动",
             "完成一次阶段成果",
             "复盘并决定下一步"),
}
_DOMAIN_WORDS = (
    ("商业", ("公司", "创业", "生意", "店", "投资", "钱", "商业", "企业", "股权")),
    ("娱乐", ("歌", "音乐", "演员", "明星", "直播", "娱乐", "舞台", "综艺", "电影")),
    ("电竞", ("电竞", "比赛", "战队", "游戏", "冠军", "排位", "主播")),
    ("学业", ("考试", "学业", "保研", "留学", "论文", "毕业", "课程", "成绩")),
    ("关系", ("恋爱", "约会", "结婚", "关系", "喜欢", "告白", "伴侣")),
    ("生活", ("健身", "旅行", "摄影", "厨艺", "生活", "健康", "阅读")),
)


def ensure_goals(state: dict) -> list[dict]:
    goals = state.get("goals")
    if not isinstance(goals, list):
        goals = []
        state["goals"] = goals
    return goals


def _domain_of(title: str, desc: str) -> str:
    text = f"{title} {desc}"
    for domain, words in _DOMAIN_WORDS:
        if any(word in text for word in words):
            return domain
    return "其他"


def _current_line(state: dict) -> str:
    player = state.get("player") or {}
    stats = "、".join(f"{name}{value}" for name, value in list((player.get("stats") or {}).items())[:4])
    career = player.get("career") or {}
    domain = career.get("domain")
    stage = int(career.get("stage", 0) or 0)
    if domain:
        try:
            from .career import STAGES
            stage_name = STAGES[domain][min(stage, len(STAGES[domain]) - 1)]
            career_line = f"{domain}·{stage_name}"
        except (KeyError, IndexError, TypeError):
            career_line = str(domain)
    else:
        career_line = "暂无事业"
    return f"{stats or '属性未知'}；{career_line}"


def _plan_for(state: dict, title: str, desc: str) -> tuple[str, list[str], str]:
    domain = _domain_of(title, desc)
    milestones = list(GOAL_PLANS[domain])
    plan = (f"当前条件：{_current_line(state)}。系统建议先把「{milestones[0]}」做出来——"
            "路线由你决定，系统不替你选择。")
    return domain, milestones, plan


def goal_view(state: dict, goal: dict) -> dict:
    day = int((state.get("time") or {}).get("day", 1))
    target = int(goal.get("target_day", day))
    view = {
        "id": goal.get("id", ""),
        "title": goal.get("title", ""),
        "desc": goal.get("desc", ""),
        "domain": goal.get("domain", "其他"),
        "created_day": int(goal.get("created_day", day)),
        "target_day": target,
        "target_days": int(goal.get("target_days", max(0, target - day))),
        "days_left": target - day,
        "overdue": goal.get("status") == "active" and day > target,
        "status": goal.get("status", "active"),
        "progress": clamp(int(goal.get("progress", 0)), 0, 100),
        "plan": goal.get("plan", ""),
        "milestones": [dict(item) for item in (goal.get("milestones") or [])],
        "notes": list(goal.get("notes") or [])[-NOTES_KEPT:],
    }
    if goal.get("completed_day"):
        view["completed_day"] = int(goal["completed_day"])
    return view


def goals_view(state: dict) -> list[dict]:
    return [goal_view(state, goal) for goal in ensure_goals(state)]


def active_goals(state: dict) -> list[dict]:
    return [goal for goal in goals_view(state) if goal.get("status") == "active"]


def create_goal(state: dict, title: str, desc: str = "", target_days: int = 30) -> dict:
    title = str(title or "").strip()[:30]
    desc = str(desc or "").strip()[:200]
    if len(title) < 2:
        return {"ok": False, "msg": "目标至少写两个字。"}
    goals = ensure_goals(state)
    active = [goal for goal in goals if goal.get("status") == "active"]
    if len(active) >= MAX_ACTIVE_GOALS:
        return {"ok": False, "msg": f"同时进行的人生目标最多 {MAX_ACTIVE_GOALS} 个，先完成或放弃一个。"}
    if any(goal.get("title") == title for goal in active):
        return {"ok": False, "msg": "这个目标已经在进行中。"}
    try:
        days = int(target_days)
    except (TypeError, ValueError):
        days = 30
    days = clamp(days, MIN_TARGET_DAYS, MAX_TARGET_DAYS)
    day = int((state.get("time") or {}).get("day", 1))
    domain, milestones, plan = _plan_for(state, title, desc)
    goal_id = f"goal_{day}_{len(goals) + 1}"
    while any(goal.get("id") == goal_id for goal in goals):
        goal_id += "x"
    goal = {
        "id": goal_id,
        "title": title,
        "desc": desc,
        "domain": domain,
        "created_day": day,
        "target_day": day + days,
        "target_days": days,
        "status": "active",
        "progress": 0,
        "plan": plan,
        "milestones": [{"text": item, "done": False} for item in milestones],
        "notes": [],
        "model_turn": -1,
        "model_delta": 0,
    }
    goals.append(goal)
    return {"ok": True, "msg": f"目标已写入系统：{title}（{days} 天）。",
            "goal": goal_view(state, goal)}


def _mark_milestones(goal: dict) -> None:
    milestones = goal.get("milestones") or []
    total = len(milestones)
    if not total:
        return
    progress = int(goal.get("progress", 0))
    for index, milestone in enumerate(milestones):
        threshold = round((index + 1) * 100 / total)
        if progress >= threshold:
            milestone["done"] = True


def advance_goal(state: dict, goal_id: str, delta: int = MANUAL_PROGRESS,
                 note: str = "", manual: bool = False) -> dict:
    goal = next((item for item in ensure_goals(state)
                 if item.get("id") == str(goal_id)), None)
    if goal is None:
        return {"ok": False, "msg": "找不到这个目标。"}
    if goal.get("status") != "active":
        return {"ok": False, "msg": "这个目标已经结束。"}
    today = game_today(state)
    if manual and goal.get("manual_day") == today:
        return {"ok": False, "msg": "今天已经记过一次进展，明天再来。"}
    try:
        delta = int(delta)
    except (TypeError, ValueError):
        delta = MANUAL_PROGRESS
    if delta <= 0:
        return {"ok": False, "msg": "进展必须大于 0。"}
    if manual:
        delta = min(delta, MANUAL_PROGRESS)
    else:
        turn = int(state.get("turn", 0))
        if goal.get("model_turn") != turn:
            goal["model_turn"] = turn
            goal["model_delta"] = 0
        remaining = MODEL_PROGRESS_TURN_CAP - int(goal.get("model_delta", 0))
        if remaining <= 0:
            return {"ok": False, "msg": "本回合这个目标已经推进到上限。"}
        delta = min(delta, remaining)
        goal["model_delta"] = int(goal.get("model_delta", 0)) + delta
    before = int(goal.get("progress", 0))
    goal["progress"] = clamp(before + delta, 0, 100)
    if manual:
        goal["manual_day"] = today
    text = str(note or "").strip()[:80]
    if text:
        day = int((state.get("time") or {}).get("day", 1))
        goal["notes"] = (list(goal.get("notes") or []) + [f"第{day}天：{text}"])[-NOTES_KEPT:]
    _mark_milestones(goal)
    if goal["progress"] >= 100:
        goal["status"] = "completed"
        goal["completed_day"] = int((state.get("time") or {}).get("day", 1))
        msg = f"目标「{goal.get('title', '')}」完成。"
    else:
        msg = (f"目标「{goal.get('title', '')}」进展 +{goal['progress'] - before}"
               f"（当前 {goal['progress']}%）。")
    return {"ok": True, "msg": msg, "goal": goal_view(state, goal)}


def manual_progress(state: dict, goal_id: str, note: str = "") -> dict:
    return advance_goal(state, goal_id, MANUAL_PROGRESS, note, manual=True)


def abandon_goal(state: dict, goal_id: str) -> dict:
    goal = next((item for item in ensure_goals(state)
                 if item.get("id") == str(goal_id)), None)
    if goal is None or goal.get("status") != "active":
        return {"ok": False, "msg": "找不到可放弃的进行中目标。"}
    goal["status"] = "abandoned"
    return {"ok": True, "msg": f"已放下目标「{goal.get('title', '')}」。",
            "goal": goal_view(state, goal)}


def apply_model_progress(state: dict, entries) -> list[str]:
    notices = []
    for entry in entries or []:
        if not isinstance(entry, dict) or not str(entry.get("id", "")).strip():
            continue
        result = advance_goal(state, str(entry["id"]).strip(),
                              entry.get("delta", 5), entry.get("note", ""), manual=False)
        if result.get("ok"):
            notices.append(f"【目标】{result['msg']}")
    return notices


def goal_prompt_block(state: dict) -> str:
    active = active_goals(state)
    if not active:
        return ""
    lines = []
    for goal in active[:MAX_ACTIVE_GOALS]:
        overdue = "·已超期" if goal.get("overdue") else ""
        lines.append(f"- [{goal['id']}] {goal['title']}（进度{goal['progress']}%，"
                     f"目标第{goal['target_day']}天{overdue}）")
    return ("【人生目标（玩家自己定的，不强制；只有玩家做出实际进展时才用 goal_progress 推进）】\n"
            + "\n".join(lines))
