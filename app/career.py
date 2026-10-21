"""事业引擎：娱乐/电竞/商业三领域并行（成长爽文型）。

入门靠机遇标记（世界事件产出）或硬门槛直接申请；周结算发周薪
（内部通道）＋资产收益；【事业】前缀行动处理晋升与特训。
名望是跨系统货币——事件门槛、NPC 反应、晋升要求都看它。
"""
from . import skills as sk
from .models import CURRENCY, clamp

PREFIX = "【事业】"

DOMAINS = ("娱乐", "电竞", "商业")

# 阶段名（stage 0=未入行 … 5=顶级）
STAGES = {
    "娱乐": ("未入行", "练习生", "新人", "二三线", "一线", "顶流"),
    "电竞": ("未入行", "青训队员", "替补选手", "主力选手", "明星选手", "传奇"),
    "商业": ("未入行", "练摊小贩", "小店老板", "公司创始人", "集团董事长", "商业帝国掌舵人"),
}

# 周薪（成长爽文型：入门≈兼职量级 → 顶级破千）
WEEKLY_INCOME = {
    "娱乐": (0, 40, 120, 300, 700, 1500),
    "电竞": (0, 35, 100, 260, 600, 1300),
    "商业": (0, 30, 90, 250, 600, 1400),
}

# 直接申请入门的硬门槛：(技能id, 等级) + 属性(名, 值) 或 金币
ENTRY_REQUIREMENTS = {
    "娱乐": {"skill": ("vocal", 3), "stat": ("魅力", 10)},
    "电竞": {"skill": ("mech", 3), "stat": ("头脑", 10)},
    "商业": {"skill": ("manage", 2), "gold": 200},
}
ENTRY_OPPORTUNITIES = {"娱乐": "经纪公司试镜邀请", "电竞": "青训营测试资格",
                        "商业": "天使投资人名片"}

# 晋升要求：stage→(核心技能等级, 名望, 金币投入)；特定阶段发资产
PROMOTION = {
    "娱乐": {1: ("vocal", 3, 10, 0), 2: ("vocal", 4, 25, 50), 3: ("stage", 5, 40, 200),
             4: ("stage", 7, 60, 800)},
    "电竞": {1: ("mech", 3, 10, 0), 2: ("mech", 4, 25, 50), 3: ("mech", 6, 40, 200),
             4: ("mech", 8, 60, 500)},
    "商业": {1: ("manage", 2, 10, 0), 2: ("manage", 4, 25, 100), 3: ("manage", 5, 40, 500),
             4: ("manage", 7, 60, 2000)},
}
STAGE_ASSETS = {  # 晋到该阶段时发放
    ("电竞", 4): {"type": "战队股份", "name": "城市战队 10% 股份", "value": 800, "weekly": 40},
    ("商业", 3): {"type": "公司股权", "name": "初创公司 60% 股权", "value": 600, "weekly": 30},
    ("商业", 4): {"type": "公司股权", "name": "集团控股股权", "value": 3000, "weekly": 150},
}


def ensure_career(state: dict) -> dict:
    p = state.setdefault("player", {})
    c = p.setdefault("career", {}) if isinstance(p.get("career"), dict) else {}
    p["career"] = c
    c.setdefault("domain", None)
    c.setdefault("stage", 0)
    c.setdefault("fame", {d: 0 for d in DOMAINS})
    c.setdefault("opportunities", [])
    c.setdefault("week_key", "")
    c.setdefault("train_week", "")
    c.setdefault("train_count", 0)
    if not isinstance(p.get("assets"), list):
        p["assets"] = []
    return c


def give_opportunity(state: dict, name: str) -> bool:
    """机遇标记入档（幂等）；返回是否首次获得。"""
    c = ensure_career(state)
    if name in c["opportunities"]:
        return False
    c["opportunities"].append(name)
    return True


def add_fame(state: dict, domain: str, amount: int) -> None:
    c = ensure_career(state)
    if domain in c["fame"]:
        c["fame"][domain] = clamp(c["fame"][domain] + amount, 0, 100)


def fame_total(state: dict) -> int:
    c = ensure_career(state)
    return max(c["fame"].values()) if c["fame"] else 0


def _gold_count(state: dict) -> int:
    from .shop import currency_count
    return currency_count(state)


def _take_gold(state: dict, n: int) -> bool:
    from .engine import _apply_items
    from .shop import currency_count
    if currency_count(state) < n:
        return False
    # 借用 remove 通道：金币按负数入账走 _remove_items
    from .engine import _remove_items
    return _remove_items(state, CURRENCY, n) >= n


def entry_check(state: dict, domain: str) -> tuple[bool, str]:
    """入门资格：机遇标记直通，或硬门槛（技能+属性/金币）。"""
    if domain not in DOMAINS:
        return False, "没有这个领域（可选：娱乐/电竞/商业）。"
    c = ensure_career(state)
    if c["domain"] is not None:
        return False, f"你已在{c['domain']}行业发展（{STAGES[c['domain']][c['stage']]}）。"
    if ENTRY_OPPORTUNITIES[domain] in c["opportunities"]:
        return True, f"凭机遇「{ENTRY_OPPORTUNITIES[domain]}」直接获得入门资格！"
    req = ENTRY_REQUIREMENTS[domain]
    sname, sneed = sk.SKILLS[req["skill"][0]][0], req["skill"][1]
    if sk.level(state, req["skill"][0]) < sneed:
        return False, f"直接申请需要{sname}≥L{sneed}（当前 L{sk.level(state, req['skill'][0])}），或拿到「{ENTRY_OPPORTUNITIES[domain]}」机遇。"
    if "stat" in req:
        from .models import effective_stats
        aname, aneed = req["stat"]
        if effective_stats(state).get(aname, 0) < aneed:
            return False, f"直接申请还需要{aname}≥{aneed}。"
    if "gold" in req and _gold_count(state) < req["gold"]:
        return False, f"直接申请需要启动资金 {req['gold']} 金币（当前 {_gold_count(state)}）。"
    if "gold" in req and not _take_gold(state, req["gold"]):
        return False, "启动资金扣除失败。"
    return True, "硬门槛达标，直接申请成功！"


def settle_week(state: dict, week_key: str) -> list[str]:
    """周结算：周薪＋资产收益（内部通道）；返回通知。"""
    c = ensure_career(state)
    if c["week_key"] == week_key:
        return []
    c["week_key"] = week_key
    notices = []
    p = state["player"]
    income = 0
    if c["domain"]:
        income += WEEKLY_INCOME[c["domain"]][c["stage"]]
    for a in p.get("assets", []):
        income += int(a.get("weekly", 0))
    if income > 0:
        from .engine import _apply_items
        _apply_items(state, [{"name": CURRENCY, "desc": "系统商城通用货币", "count": income}])
        label = f"{c['domain']}·{STAGES[c['domain']][c['stage']]}" if c["domain"] else "资产"
        notices.append(f"【系统】周结算：{label}本周收入 系统金币 +{income}（工资与资产收益，内部通道）。")
    # 名望里程碑：高阶段每周小幅自然增长（在业内持续曝光）
    if c["domain"] and c["stage"] >= 2:
        add_fame(state, c["domain"], 1)
    return notices


def _promo_check(state: dict) -> tuple[bool, str]:
    c = ensure_career(state)
    if not c["domain"] or c["stage"] >= 5:
        return False, "没有可晋升的阶段。"
    nxt = c["stage"] + 1
    skill_id, lv_need, fame_need, gold_need = PROMOTION[c["domain"]][c["stage"]]
    sname = sk.SKILLS[skill_id][0]
    if sk.level(state, skill_id) < lv_need:
        return False, f"晋升{STAGES[c['domain']][nxt]}需要{sname}≥L{lv_need}（当前 L{sk.level(state, skill_id)}）。"
    if c["fame"][c["domain"]] < fame_need:
        return False, f"晋升需要{c['domain']}名望≥{fame_need}（当前 {c['fame'][c['domain']]}）——多参加活动。"
    if gold_need and not _take_gold(state, gold_need):
        return False, f"晋升需要投入 {gold_need} 金币（当前 {_gold_count(state)}）。"
    c["stage"] = nxt
    add_fame(state, c["domain"], 10)
    asset = STAGE_ASSETS.get((c["domain"], nxt))
    if asset:
        state["player"].setdefault("assets", []).append(dict(asset))
    from .models import refresh_main_quest
    refresh_main_quest(state)
    msg = f"【系统】事业晋升：{c['domain']}·{STAGES[c['domain']][nxt]}！周薪涨至 {WEEKLY_INCOME[c['domain']][nxt]} 金/周，名望 +10。"
    if asset:
        msg += f" 获得资产：{asset['name']}（周收益 +{asset['weekly']}）。"
    return True, msg


def _train_check(state: dict) -> tuple[bool, str, list[str]]:
    """特训：15 金＋1 时段换 20 经验（按当前领域核心技能），每周限 3 次。"""
    from .shop import _week_key
    c = ensure_career(state)
    if not c["domain"]:
        return False, "先入门一个领域才能特训（未入行时请用自由练习行动）。", []
    wk = _week_key(state)
    if c["train_week"] != wk:
        c["train_week"], c["train_count"] = wk, 0
    if c["train_count"] >= sk.TRAIN_WEEK_CAP:
        return False, f"本周特训已满 {sk.TRAIN_WEEK_CAP} 次，下周再来。", []
    if not _take_gold(state, sk.TRAIN_COST):
        return False, f"特训需要 {sk.TRAIN_COST} 金币（当前 {_gold_count(state)}）。", []
    c["train_count"] += 1
    core = PROMOTION[c["domain"]].get(max(c["stage"], 1), ("vocal",))[0]
    notices = sk.add_xp(state, core, sk.TRAIN_XP)
    sname = sk.SKILLS[core][0]
    notices.insert(0, f"【系统】特训完成：{sname} +{sk.TRAIN_XP} 经验（本周第 {c['train_count']}/{sk.TRAIN_WEEK_CAP} 次）。")
    # 特训也推进时段
    from .models import advance_time
    advance_time(state, 1)
    return True, "", notices


def before_turn(state: dict, action: str) -> dict | None:
    """【事业】拦截：入门/晋升/特训。返回 TurnResult 或 None（非本前缀）。"""
    if not action.startswith(PREFIX):
        return None
    body = action[len(PREFIX):].strip()
    notices: list[str] = []
    c = ensure_career(state)

    if body.startswith("入门"):
        domain = next((d for d in DOMAINS if d in body), "")
        ok, msg = entry_check(state, domain) if domain else (False, "请指明领域：入门 娱乐/电竞/商业")
        if ok:
            c["domain"], c["stage"] = domain, 1
            add_fame(state, domain, 5)
            notices.append(f"【系统】事业入门：{domain}·{STAGES[domain][1]}！周薪 {WEEKLY_INCOME[domain][1]} 金/周起步。{msg}")
            story = (f"你正式踏入了{domain}这条路。{msg}\n从今天起，{STAGES[domain][1]}就是你的新身份——"
                     f"系统面板刷新，周薪 {WEEKLY_INCOME[domain][1]} 金/周已激活。这一行的水很深，但你打算趟出个名堂。")
        else:
            raise ValueError(msg)
    elif body.startswith("晋升"):
        ok, msg = _promo_check(state)
        if not ok:
            raise ValueError(msg)
        notices.append(msg)
        d, s = c["domain"], c["stage"]
        story = (f"晋升答辩/战绩/流水，你拿出了全部筹码——系统面板弹出确认：{STAGES[d][s]}。\n"
                 f"周薪涨至 {WEEKLY_INCOME[d][s]} 金/周，{d}名望突破新高。圈内开始有人打听你的名字。")
    elif body.startswith("特训"):
        ok, msg, ns = _train_check(state)
        if not ok:
            raise ValueError(msg)
        notices.extend(ns)
        story = f"你把自己摁在训练场整整一个时段——汗水没有白流。{ns[0].split('：', 1)[1]}"
    else:
        raise ValueError("【事业】可选行动：入门 <领域> / 晋升 / 特训。")

    from .engine import _drop_oldest
    choices = ["继续今天的行程", "看看系统面板", "联系领域里认识的人"]
    return {"story_text": story, "narration_world": "urban", "choices": choices,
            "state_updates": {}, "system_notice": "", "_notices": notices}


def career_view(state: dict) -> dict:
    c = ensure_career(state)
    d = c["domain"]
    return {
        "domain": d, "stage": c["stage"],
        "stage_name": STAGES[d][c["stage"]] if d else "未入行",
        "fame": dict(c["fame"]),
        "weekly_income": WEEKLY_INCOME[d][c["stage"]] if d else 0,
        "opportunities": list(c["opportunities"]),
        "assets": [dict(a) for a in state["player"].get("assets", [])],
        "train_left": max(0, sk.TRAIN_WEEK_CAP - c["train_count"]) if c["train_week"] == c.get("train_week") else sk.TRAIN_WEEK_CAP,
    }


def career_line(state: dict) -> str:
    """提示词行。"""
    c = ensure_career(state)
    if not c["domain"]:
        opp = "、".join(c["opportunities"]) or "暂无"
        return (f"无固定事业（可通过活动机遇或技能门槛入门 娱乐/电竞/商业；"
                f"持有机遇：{opp}）")
    fame = "、".join(f"{k}{v}" for k, v in c["fame"].items() if v) or "均为0"
    return (f"{c['domain']}·{STAGES[c['domain']][c['stage']]}，"
            f"周薪{WEEKLY_INCOME[c['domain']][c['stage']]}金/周，名望（{fame}）；"
            f"晋升用【事业】晋升、训练用【事业】特训")
