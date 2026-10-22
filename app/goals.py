"""玩家自定义人生目标：系统只记录、提示与反馈，不替玩家决定人生。"""
import re

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
    for goal in goals:
        if not isinstance(goal, dict):
            continue
        if "mode" not in goal:
            criteria = infer_criteria(goal.get("title", ""), goal.get("desc", ""))
            goal["criteria"] = criteria
            goal["mode"] = "objective" if criteria else "subjective"
            if goal.get("status") == "completed":
                goal["legacy_completion"] = True  # 保留旧档完成记录，不伪造已核验事实。
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
    positions = career.get("positions") or {}
    if isinstance(positions, dict) and positions:
        from .career import STAGES
        lines = []
        for name, position in positions.items():
            if name in STAGES:
                stage_name = STAGES[name][clamp(int(position.get("stage", 0)), 0, len(STAGES[name]) - 1)]
                lines.append(f"{name}·{stage_name}")
        return f"{stats or '属性未知'}；{'、'.join(lines) or '暂无事业'}"
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
        "mode": goal.get("mode", "subjective"),
        "criteria": [dict(item) for item in goal.get("criteria") or []],
        "actual": [_criterion_actual(state, item) for item in goal.get("criteria") or []],
        "legacy_completion": bool(goal.get("legacy_completion")),
    }
    if goal.get("completed_day"):
        view["completed_day"] = int(goal["completed_day"])
    return view


def goals_view(state: dict) -> list[dict]:
    return [goal_view(state, goal) for goal in ensure_goals(state)]


def active_goals(state: dict) -> list[dict]:
    return [goal for goal in goals_view(state) if goal.get("status") == "active"]


def create_goal(state: dict, title: str, desc: str = "", target_days: int = 30,
                criteria=None) -> dict:
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
    if criteria is not None:
        try:
            criteria = normalize_criteria(criteria)
        except ValueError as exc:
            return {"ok": False, "msg": str(exc)}
    else:
        criteria = infer_criteria(title, desc)
    if criteria:
        milestones = [criterion_label(item) for item in criteria]
        plan += " 完成条件以存档中的真实成果核验；记录感想不会直接增加完成度。"
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
        "mode": "objective" if criteria else "subjective",
        "criteria": criteria,
        "plan": plan,
        "milestones": [{"text": item, "done": False} for item in milestones],
        "notes": [],
        "model_turn": -1,
        "model_delta": 0,
    }
    goals.append(goal)
    sync_objectives(state)
    return {"ok": True, "msg": f"目标已写入系统：{title}（{days} 天）。",
            "goal": goal_view(state, goal)}


def _mark_milestones(goal: dict, note: str = "") -> None:
    # 主观目标由玩家明确记下完成了哪一步，不再用33/67/100百分比冒充事实。
    for index, milestone in enumerate(goal.get("milestones") or []):
        if note and (milestone.get("text", "") in note
                     or f"完成里程碑{index + 1}" in note
                     or f"完成第{index + 1}步" in note):
            milestone["done"] = True
            milestone["evidence"] = note[:80]


def advance_goal(state: dict, goal_id: str, delta: int = MANUAL_PROGRESS,
                 note: str = "", manual: bool = False) -> dict:
    goal = next((item for item in ensure_goals(state)
                 if item.get("id") == str(goal_id)), None)
    if goal is None:
        return {"ok": False, "msg": "找不到这个目标。"}
    if goal.get("status") != "active":
        return {"ok": False, "msg": "这个目标已经结束。"}
    if goal.get("mode") == "objective":
        sync_objectives(state)
        text = str(note or "").strip()[:80]
        if text:
            day = int((state.get("time") or {}).get("day", 1))
            goal["notes"] = (list(goal.get("notes") or []) + [f"第{day}天：{text}"])[-NOTES_KEPT:]
        return {"ok": False, "msg": "这个目标按真实成果核验，不能用记录次数或模型申报增加进度。", "goal": goal_view(state, goal)}
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
    _mark_milestones(goal, text)
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
    return ("【人生目标（玩家自己定的，不强制；客观目标由引擎核验，主观目标有实际进展才可用 goal_progress）】\n"
            + "\n".join(lines))


# 可核验的目标只读取引擎保存的实体、技能和结算记录；不会把一段叙述当成资产。
METRICS = {"asset_value", "gold", "company_count", "company_valuation", "equity",
           "skill_level", "released_works", "championships", "graduated", "achievement", "cash", "completed_works"}
METRIC_NAMES = {"asset_value": "持有资产价值", "gold": "可用华夏币", "cash": "可用华夏币", "company_count": "持有公司数量",
                "company_valuation": "所持公司最高估值", "equity": "持有股权比例",
                "skill_level": "技能等级", "released_works": "已发行作品数量", "completed_works": "已完成作品数量",
                "championships": "正式冠军次数", "graduated": "完成毕业",
                "achievement": "取得成就"}


def _number(text: str, default: float = 1) -> float:
    text = str(text).replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(亿|千万|百万|万|千|百)?", text)
    if match:
        return float(match.group(1)) * {"亿": 1e8, "千万": 1e7, "百万": 1e6, "万": 1e4,
                                       "千": 1e3, "百": 100}.get(match.group(2), 1)
    nums = {"零": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9}
    match = re.search(r"([零一两二三四五六七八九十百千万亿]+)", text)
    if not match:
        return default
    total = section = digit = 0
    for char in match.group(1):
        if char in nums:
            digit = nums[char]
        elif char in "十百千":
            section += (digit or 1) * {"十": 10, "百": 100, "千": 1000}[char]
            digit = 0
        else:
            section += digit
            total = (total + section) * {"万": 1e4, "亿": 1e8}[char]
            section = digit = 0
    return total + section + digit or default


def _count_target(text: str) -> float:
    match = re.search(r"([\d一两二三四五六七八九十百]+)\s*(?:部|首|个|次|项|座|家|款)", text)
    return _number(match.group(1)) if match else 1


def normalize_criteria(criteria) -> list[dict]:
    if isinstance(criteria, dict):
        criteria = [criteria]
    if not isinstance(criteria, list) or not criteria or len(criteria) > 8:
        raise ValueError("目标判据需要1至8条可核验条件。")
    out = []
    for criterion in criteria:
        if not isinstance(criterion, dict) or criterion.get("metric") not in METRICS:
            raise ValueError("目标包含不支持的客观条件。")
        item = {"metric": criterion["metric"]}
        try:
            target = float(criterion.get("target", 1))
        except (ValueError, TypeError):
            raise ValueError("目标条件的数量必须是正数。") from None
        if not 0 < target <= 1e15:
            raise ValueError("目标条件的数量超出范围。")
        item["target"] = target
        for key in ("name", "skill", "enterprise_id"):
            if criterion.get(key):
                item[key] = str(criterion[key])[:80]
        from .skills import SKILLS
        if item["metric"] == "skill_level" and item.get("skill") not in SKILLS:
            raise ValueError("目标技能不存在。")
        if item["metric"] == "achievement" and not item.get("name"):
            raise ValueError("成就目标需要指定已有成就名称或ID。")
        limits = {"skill_level": 10, "equity": 100, "graduated": 1}
        if item["metric"] in limits and target > limits[item["metric"]]:
            raise ValueError("目标条件超过当前规则允许的上限。")
        out.append(item)
    return out


def infer_criteria(title: str, desc: str = "") -> list[dict]:
    text = f"{title} {desc}"
    out = []
    if any(word in text for word in ("创办", "成立", "开办", "拥有", "持有", "注册", "创始人", "开一家", "开个")) and any(word in text for word in ("公司", "企业")):
        out.append({"metric": "company_count", "target": _count_target(text)})
    if "估值" in text:
        amount = re.split("估值", text, maxsplit=1)[1]
        out.append({"metric": "company_valuation", "target": _number(amount)})
    if any(word in text for word in ("资产", "身家")) and re.search(r"[\d一两二三四五六七八九十百千万亿]", text):
        amount = re.split("资产|身家", text, maxsplit=1)[1]
        out.append({"metric": "asset_value", "target": _number(amount)})
    if any(word in text for word in ("华夏币", "存款", "现金", "赚到", "攒够")):
        match = re.search(r"(?:华夏币|存款|现金|赚到|攒够)\s*(?:达到|超过|累计)?\s*([\d一两二三四五六七八九十百千万亿.]+)", text)
        if not match:
            match = re.search(r"([\d一两二三四五六七八九十百千万亿.]+)\s*(?:华夏币|元|块)", text)
        if match:
            out.append({"metric": "cash", "target": _number(match.group(1))})
    if "股权" in text or "股份" in text:
        match = re.search(r"(\d+(?:\.\d+)?)\s*[%％]", text)
        out.append({"metric": "equity", "target": float(match.group(1)) if match else 1})
    from .skills import SKILLS
    for sid, detail in SKILLS.items():
        if detail[0] in text:
            tail = text.split(detail[0], 1)[1]
            match = re.search(r"(?:L|等级|达到|到)?\s*([\d一两二三四五六七八九十]+)\s*(?:级)?", tail, re.I)
            if match:
                out.append({"metric": "skill_level", "skill": sid, "target": _number(match.group(1))})
    if any(word in text for word in ("发行", "发布", "上映")) and any(word in text for word in ("作品", "单曲", "专辑", "电影", "游戏")):
        out.append({"metric": "released_works", "target": _count_target(text)})
    elif any(word in text for word in ("做出", "完成", "创作", "制作")) and any(word in text for word in ("作品", "单曲", "专辑", "电影", "游戏")):
        out.append({"metric": "completed_works", "target": _count_target(text)})
    if "冠军" in text:
        out.append({"metric": "championships", "target": _count_target(text)})
    if "毕业" in text and not any(word in text for word in ("毕业旅行", "毕业照", "毕业前", "毕业后")):
        out.append({"metric": "graduated", "target": 1})
    if not out and any(word in text for word in ("世界首富", "世界第一", "诺贝尔", "影帝", "影后", "金曲奖")):
        out.append({"metric": "achievement", "name": str(title), "target": 1})
    return out


def criterion_label(criterion: dict) -> str:
    metric = criterion.get("metric", "")
    prefix = METRIC_NAMES.get(metric, metric)
    if metric == "skill_level":
        from .skills import SKILLS
        prefix = SKILLS.get(criterion.get("skill"), ("技能",))[0] + "等级"
    return f"{criterion.get('name') or prefix} ≥ {float(criterion.get('target', 1)):g}"


def _criterion_actual(state: dict, criterion: dict) -> dict:
    player = state.get("player") or {}
    metric = criterion.get("metric")
    enterprises = [e for e in player.get("enterprises", []) if isinstance(e, dict)
                   and e.get("status") not in ("closed", "sold")]
    def equity(entity):
        value = entity.get("equity", entity.get("equity_pct", 100))
        return max(0, float(value.get("player", 0) if isinstance(value, dict) else value or 0))
    enterprises = [e for e in enterprises if equity(e) > 0
                   and (not criterion.get("enterprise_id") or e.get("id") == criterion["enterprise_id"])
                   and (not criterion.get("name") or criterion["name"] in str(e.get("name", "")))]
    companies = [e for e in enterprises if e.get("kind", e.get("type")) == "company"]
    actual = 0
    evidence = []
    if metric in ("gold", "cash"):
        from .shop import currency_count
        from .models import CASH
        actual = currency_count(state, currency=CASH)
    elif metric == "asset_value":
        actual = sum(float(e.get("valuation", 0)) * equity(e) / 100 for e in enterprises)
        actual += sum(float(a.get("value", 0)) for a in player.get("assets", [])
                      if isinstance(a, dict) and not a.get("entity_id"))
    elif metric == "company_count":
        actual = len(companies)
        evidence = [e.get("id", e.get("name")) for e in companies]
    elif metric == "company_valuation":
        actual = max((float(e.get("valuation", 0)) for e in companies), default=0)
        evidence = [e.get("id", e.get("name")) for e in companies]
    elif metric == "equity":
        actual = max((equity(e) for e in enterprises if e.get("kind") in ("company", "team")), default=0)
    elif metric == "skill_level":
        from .skills import level
        actual = level(state, criterion.get("skill", ""))
    elif metric in ("released_works", "completed_works"):
        allowed_statuses = ("released",) if metric == "released_works" else ("ready", "released")
        works = [e for e in enterprises if e.get("kind") == "work" and e.get("status") in allowed_statuses]
        actual = len(works)
        evidence = [e.get("id", e.get("name")) for e in works]
    elif metric == "championships":
        actual = sum(int(e.get("trophies", 0)) for e in enterprises if e.get("kind") == "team")
        solo = [h for h in (state.get("events") or {}).get("experience", [])
                if h.get("template") == "arena" and h.get("role") == "solo" and h.get("outcome") == "win"]
        actual += len(solo)
        evidence = [h.get("id") for h in solo]
    elif metric == "graduated":
        actual = int((player.get("education") or {}).get("status") == "graduated")
    elif metric == "achievement":
        achievements = state.get("achievements") or player.get("achievements") or []
        if isinstance(achievements, dict):
            achievements = [dict(value, id=key) if isinstance(value, dict) else {"name": key, "unlocked": value}
                            for key, value in achievements.items()]
        from .models import ACHIEVEMENTS
        known = {a["id"]: a for a in ACHIEVEMENTS}
        achievements = [dict(known.get(a, {"id": a}), unlocked=True) if isinstance(a, str) else a for a in achievements]
        evidence = [a.get("id", a.get("name")) for a in achievements if isinstance(a, dict)
                    and a.get("unlocked", a.get("completed", False))
                    and criterion.get("name") in (a.get("name"), a.get("title"), a.get("id"))]
        actual = len(evidence)
    target = float(criterion.get("target", 1))
    return {"metric": metric, "label": criterion_label(criterion), "actual": actual,
            "target": target, "met": actual >= target, "evidence": evidence}


def sync_objectives(state: dict) -> list[str]:
    notices = []
    for goal in ensure_goals(state):
        if goal.get("mode") != "objective" or goal.get("status") != "active":
            continue
        actual = [_criterion_actual(state, item) for item in goal.get("criteria") or []]
        if not actual:
            continue
        before = int(goal.get("progress", 0))
        goal["progress"] = min(100, int(sum(min(1, item["actual"] / item["target"]) for item in actual) * 100 / len(actual)))
        goal["milestones"] = [{"text": item["label"], "done": item["met"],
                               "actual": item["actual"], "target": item["target"],
                               "evidence": item["evidence"]} for item in actual]
        if all(item["met"] for item in actual):
            goal.update(status="completed", completed_day=int((state.get("time") or {}).get("day", 1)))
            notices.append(f"【目标】目标「{goal.get('title', '')}」已按真实成果核验完成。")
        elif goal["progress"] != before:
            notices.append(f"【目标】「{goal.get('title', '')}」实际进度 {goal['progress']}%。")
    return notices
