"""技能体系：多技能成长＋确定性检定。

技能是事业领域与世界事件的敲门砖——声乐练上去才能在校园晚会
压住场，操作练上去才能过青训营测试。成长三渠道：
①契约 skill_progress（模型申报，引擎钳制）②世界事件奖励 ③事业特训。
"""
from .models import effective_stats, clamp

# 技能目录：id → (名称, 关联属性, 领域)
SKILLS = {
    "vocal":    ("声乐", "魅力", "娱乐"),
    "instrument": ("乐器", "魅力", "娱乐"),
    "acting":   ("演技", "情商", "娱乐"),
    "stage":    ("台风", "魅力", "娱乐"),
    "mech":     ("操作", "头脑", "电竞"),
    "sense":    ("意识", "头脑", "电竞"),
    "manage":   ("经营", "头脑", "商业"),
    "invest":   ("投资", "头脑", "商业"),
    "coding":   ("编程", "头脑", "学术"),
    "cooking":  ("厨艺", "情商", "生活"),
    "photo":    ("摄影", "审美", "生活"),
    "speech":   ("演讲", "情商", "生活"),
}
SKILL_MAX_LV = 10
XP_PER_LV = 100          # 每级所需经验
MODEL_XP_TURN_CAP = 25   # 模型申报：每技能每回合经验上限
MODEL_SKILLS_TURN_CAP = 2  # 模型申报：每回合最多技能数
TRAIN_XP = 20            # 事业特训单次经验
TRAIN_COST = 15          # 特训金币消耗
TRAIN_WEEK_CAP = 3       # 特训每周限次

VALID_IDS = set(SKILLS)


def ensure_skills(state: dict) -> dict:
    p = state.setdefault("player", {})
    if not isinstance(p.get("skills"), dict):
        p["skills"] = {}
    return p["skills"]


def level(state: dict, skill_id: str) -> int:
    entry = ensure_skills(state).get(skill_id)
    return int(entry["lv"]) if entry else 0


def add_xp(state: dict, skill_id: str, xp: int) -> list[str]:
    """入账经验（调用方自行钳制来源）；升级返回通知。"""
    if skill_id not in VALID_IDS or xp <= 0:
        return []
    skills = ensure_skills(state)
    entry = skills.setdefault(skill_id, {"lv": 1, "xp": 0})
    notices = []
    entry["xp"] += xp
    while entry["xp"] >= XP_PER_LV and entry["lv"] < SKILL_MAX_LV:
        entry["xp"] -= XP_PER_LV
        entry["lv"] += 1
        notices.append(f"【系统】技能提升：{SKILLS[skill_id][0]} L{entry['lv']}！")
    if entry["lv"] >= SKILL_MAX_LV:
        entry["xp"] = min(entry["xp"], XP_PER_LV)  # 满级封顶
    return notices


def apply_model_progress(state: dict, entries) -> list[str]:
    """结算模型申报的 skill_progress：≤2 项、每项 ≤25xp、只认白名单技能。"""
    notices: list[str] = []
    if not isinstance(entries, list):
        return notices
    picked = 0
    for it in entries:
        if not isinstance(it, dict) or picked >= MODEL_SKILLS_TURN_CAP:
            continue
        sid = str(it.get("skill", "")).strip()
        if sid not in VALID_IDS:
            continue
        try:
            xp = max(0, min(int(it.get("xp", 0)), MODEL_XP_TURN_CAP))
        except (TypeError, ValueError):
            continue
        if xp <= 0:
            continue
        picked += 1
        before = level(state, sid)
        notices.extend(add_xp(state, sid, xp))
        if level(state, sid) == before:
            notices.append(f"【系统】{SKILLS[sid][0]}练习 +{xp} 经验。")
    return notices


def skill_check(state: dict, skill_id: str, difficulty: int) -> str:
    """确定性检定：lv≥diff 过 / 差 1 级半过 / 更低不过。
    返回 'pass' | 'half' | 'fail'——半过给打折结果而非全无。"""
    lv = level(state, skill_id)
    if lv >= difficulty:
        return "pass"
    if lv == difficulty - 1:
        return "half"
    return "fail"


def attr_bonus(state: dict, skill_id: str) -> int:
    """关联属性加成：属性每满 10 点检定难度 -1（等效 +1 级）。"""
    name, attr, _ = SKILLS[skill_id]
    return effective_stats(state).get(attr, 0) // 10


def skills_view(state: dict) -> list[dict]:
    out = []
    for sid, (name, attr, domain) in SKILLS.items():
        entry = ensure_skills(state).get(sid)
        out.append({"id": sid, "name": name, "attr": attr, "domain": domain,
                    "lv": int(entry["lv"]) if entry else 0,
                    "xp": int(entry["xp"]) if entry else 0,
                    "learned": bool(entry)})
    return out


def skills_line(state: dict) -> str:
    """提示词行：只列已学技能，未学只给领域提示。"""
    learned = []
    for sid, (name, _, _) in SKILLS.items():
        entry = ensure_skills(state).get(sid)
        if entry:
            learned.append(f"{name}L{entry['lv']}")
    if not learned:
        return "尚未掌握任何技能——练习（唱/琴/排位/编程/烹饪…）或参加活动可习得"
    return "、".join(learned)
