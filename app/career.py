"""事业引擎：娱乐/电竞/商业三领域并行（成长爽文型）。

入门靠机遇标记（世界事件产出）或硬门槛直接申请；周结算发周薪
（内部通道）＋资产收益；【事业】前缀行动处理晋升与特训；
【经营】前缀处理团队、宣传与项目，项目按游戏日到期自动结算。
名望是跨系统货币——事件门槛、NPC 反应、晋升要求都看它。
"""
import random

from . import skills as sk
from .models import CURRENCY, clamp, now_iso

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

# 经营项目：接单后按游戏日推进，到期自动结算；不是点一下等周薪。
PROJECTS = {
    "娱乐": {
        "single": {"name": "单曲制作", "days": 14, "cost": 150, "skill": ("vocal", 3),
                   "min_stage": 1, "difficulty": 8, "base": 140, "fame": 6, "xp": 30},
        "variety": {"name": "综艺通告", "days": 7, "cost": 60, "skill": ("acting", 2),
                    "min_stage": 1, "difficulty": 6, "base": 90, "fame": 4, "xp": 20},
        "tour": {"name": "小型巡演", "days": 30, "cost": 400, "skill": ("stage", 4),
                 "min_stage": 2, "difficulty": 13, "base": 380, "fame": 12, "xp": 50,
                 "asset": {"type": "演出合约", "name": "巡演合约", "value": 1200, "weekly": 25}},
    },
    "电竞": {
        "city_cup": {"name": "城市赛", "days": 7, "cost": 80, "skill": ("mech", 3),
                     "min_stage": 1, "difficulty": 7, "base": 110, "fame": 5, "xp": 25},
        "bootcamp": {"name": "青训营", "days": 14, "cost": 150, "skill": ("sense", 3),
                     "min_stage": 1, "difficulty": 8, "base": 160, "fame": 7, "xp": 30},
        "league": {"name": "联赛赛季", "days": 30, "cost": 500, "skill": ("mech", 5),
                   "min_stage": 2, "difficulty": 13, "base": 420, "fame": 14, "xp": 60,
                   "asset": {"type": "战队股份", "name": "联赛战队 5% 股份", "value": 1500, "weekly": 35}},
    },
    "商业": {
        "popup": {"name": "校园快闪店", "days": 7, "cost": 100, "skill": ("manage", 2),
                  "min_stage": 1, "difficulty": 6, "base": 130, "fame": 4, "xp": 20},
        "group_buy": {"name": "社区团购", "days": 14, "cost": 200, "skill": ("manage", 3),
                      "min_stage": 1, "difficulty": 9, "base": 220, "fame": 6, "xp": 30},
        "brand": {"name": "品牌联名", "days": 30, "cost": 500, "skill": ("manage", 4),
                  "min_stage": 2, "difficulty": 13, "base": 450, "fame": 12, "xp": 45,
                  "asset": {"type": "联名合约", "name": "品牌联名合约", "value": 1400, "weekly": 30}},
    },
}
OPS_COSTS = {"staff": 50, "quality": 20, "marketing": 30}
OPS_CAPS = {"staff": 5, "quality": 5, "marketing": 5}
OPS_LABELS = {"staff": "招聘", "quality": "培训", "marketing": "宣传"}
STAFF_WEEKLY_COST = 15


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
    ops = c.get("ops") if isinstance(c.get("ops"), dict) else {}
    for key, cap in OPS_CAPS.items():
        try:
            ops[key] = clamp(int(ops.get(key, 0)), 0, cap)
        except (TypeError, ValueError):
            ops[key] = 0
    c["ops"] = ops
    if not isinstance(c.get("projects"), list):
        c["projects"] = []
    try:
        c["project_seq"] = max(0, int(c.get("project_seq", 0)))
    except (TypeError, ValueError):
        c["project_seq"] = 0
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


def _active_project(c: dict) -> dict | None:
    return next((p for p in c.get("projects", []) if p.get("status") == "active"), None)


def _project_view(state: dict, project: dict) -> dict:
    day = int((state.get("time") or {}).get("day", 1))
    return {
        "id": project.get("id", ""),
        "name": project.get("name", ""),
        "domain": project.get("domain", ""),
        "start_day": int(project.get("start_day", day)),
        "end_day": int(project.get("end_day", day)),
        "days_left": max(0, int(project.get("end_day", day)) - day),
        "cost": int(project.get("cost", 0)),
        "plan": project.get("plan", "steady"),
        "status": project.get("status", "active"),
        "outcome": project.get("outcome", ""),
        "result": project.get("result", ""),
        "score": project.get("score"),
    }


def project_options(state: dict) -> list[dict]:
    c = ensure_career(state)
    domain = c.get("domain")
    if domain not in PROJECTS:
        return []
    active = _active_project(c)
    gold = _gold_count(state)
    out = []
    for project_id, template in PROJECTS[domain].items():
        skill_id, need = template["skill"]
        level = sk.level(state, skill_id)
        stage_ok = int(c.get("stage", 0)) >= int(template["min_stage"])
        affordable = gold >= int(template["cost"])
        reasons = []
        if not stage_ok:
            reasons.append(f"需{STAGES[domain][template['min_stage']]}阶段")
        if active:
            reasons.append("已有进行中的项目")
        if not affordable:
            reasons.append(f"需{template['cost']}金币")
        item = dict(template)
        item.update({
            "id": project_id,
            "skill_name": sk.SKILLS[skill_id][0],
            "skill_need": need,
            "skill_level": level,
            "skill_ok": level >= need,
            "available": stage_ok and affordable and active is None,
            "reason": "；".join(reasons),
        })
        out.append(item)
    return out


def start_project(state: dict, project_id: str, plan: str = "steady") -> tuple[bool, str, list[str]]:
    c = ensure_career(state)
    domain = c.get("domain")
    if domain not in PROJECTS:
        return False, "还没有入行，先通过【事业】入门一个领域。", []
    template = PROJECTS[domain].get(str(project_id))
    if template is None:
        return False, "没有这个项目。", []
    if int(c.get("stage", 0)) < int(template["min_stage"]):
        return False, f"这个项目需要{STAGES[domain][template['min_stage']]}阶段。", []
    if _active_project(c) is not None:
        return False, "已经有一个进行中的项目，先等它结算。", []
    if _gold_count(state) < int(template["cost"]):
        return False, f"启动资金不足：需要 {template['cost']} 金币。", []
    if not _take_gold(state, int(template["cost"])):
        return False, "启动资金扣除失败。", []
    plan = "bold" if str(plan).lower() in ("bold", "进取", "突破") else "steady"
    day = int((state.get("time") or {}).get("day", 1))
    c["project_seq"] = int(c.get("project_seq", 0)) + 1
    project = {
        "id": f"proj_{c['project_seq']}",
        "template": project_id,
        "name": template["name"],
        "domain": domain,
        "start_day": day,
        "end_day": day + int(template["days"]),
        "cost": int(template["cost"]),
        "plan": plan,
        "base": int(template["base"]),
        "fame": int(template["fame"]),
        "xp": int(template["xp"]),
        "skill": list(template["skill"]),
        "difficulty": int(template["difficulty"]),
        "status": "active",
        "outcome": "",
        "result": "",
    }
    if template.get("asset"):
        project["asset"] = dict(template["asset"])
    c["projects"].append(project)
    c["projects"] = c["projects"][-12:]
    plan_label = "进取" if plan == "bold" else "稳妥"
    story = (f"你把{template['name']}的项目书签了字，投入 {template['cost']} 金币。"
             f"这一轮走{plan_label}路线，预计 {template['days']} 天后结算。"
             "接下来要做的是把人和钱用在正确的地方，而不是每天盯着账面。")
    return True, story, [f"【系统】已启动经营项目「{template['name']}」（{plan_label}），"
                        f"{template['days']} 天后结算。"]


def _resolve_project(state: dict, c: dict, project: dict, day: int) -> list[str]:
    skill_id, _need = project.get("skill", ["vocal", 1])
    ops = c.get("ops") or {}
    plan = project.get("plan", "steady")
    score = (sk.level(state, skill_id) + sk.attr_bonus(state, skill_id)
             + int(c.get("stage", 0)) + int(ops.get("quality", 0))
             + int(ops.get("marketing", 0)) + int(ops.get("staff", 0))
             + (3 if plan == "steady" else -2))
    roll = random.Random(f"{project.get('id')}:{project.get('start_day')}").randint(-2, 2)
    total = score + roll
    difficulty = int(project.get("difficulty", 8))
    if total >= difficulty:
        outcome, factor, label = "success", (1.5 if plan == "bold" else 1.0), "成功"
    elif total >= difficulty - 2:
        outcome, factor, label = "partial", 0.7, "勉强完成"
    else:
        outcome, factor, label = "fail", 0.0, "失败"
    gold = round(int(project.get("base", 0)) * factor
                 + (int(ops.get("marketing", 0)) * 8 if factor else 0))
    fame = round(int(project.get("fame", 0)) * factor)
    xp = round(int(project.get("xp", 0)) * (1.0 if outcome == "success" else 0.6 if outcome == "partial" else 0.3))
    notices = []
    if gold:
        from .engine import _apply_items
        _apply_items(state, [{"name": CURRENCY, "desc": "系统商城通用货币", "count": gold}])
        notices.append(f"【系统】经营收入：系统金币 +{gold}。")
    if fame:
        add_fame(state, project.get("domain", ""), fame)
        notices.append(f"【系统】{project.get('domain', '')}名望 +{fame}。")
    if xp:
        notices.extend(sk.add_xp(state, skill_id, xp))
        notices.append(f"【系统】{sk.SKILLS[skill_id][0]}经验 +{xp}。")
    if outcome == "success" and project.get("asset"):
        state["player"].setdefault("assets", []).append(dict(project["asset"]))
        notices.append(f"【系统】获得资产：{project['asset']['name']}（周收益 +{project['asset']['weekly']}）。")
    result = (f"{label}（评分 {total}/{difficulty}，骰子 {roll:+d}）："
              f"金币 +{gold}、名望 +{fame}、经验 +{xp}")
    project.update({"status": "completed", "outcome": outcome, "result": result,
                    "completed_day": day, "score": total, "roll": roll})
    state["inbox"] = (state.get("inbox") or [])[-49:] + [{
        "ts": now_iso(), "type": "event", "world": "urban",
        "title": f"经营结算 · {project.get('name', '')}", "text": result}]
    notices.append(f"【系统】经营项目「{project.get('name', '')}」{result}")
    return notices


def settle_projects(state: dict) -> list[str]:
    """把到期项目按游戏日结算；重复调用只结算 active 项目。"""
    c = ensure_career(state)
    day = int((state.get("time") or {}).get("day", 1))
    notices = []
    for project in list(c.get("projects", [])):
        if project.get("status") != "active":
            continue
        if day >= int(project.get("end_day", day)):
            notices.extend(_resolve_project(state, c, project, day))
    return notices


def _ops_action(state: dict, body: str) -> tuple[bool, str, list[str]]:
    c = ensure_career(state)
    if not c.get("domain"):
        return False, "还没有入行，先通过【事业】入门一个领域。", []
    parts = body.split()
    action = parts[0] if parts else ""
    if action in ("招聘", "培训", "宣传"):
        key = {"招聘": "staff", "培训": "quality", "宣传": "marketing"}[action]
        cap = OPS_CAPS[key]
        if int(c["ops"].get(key, 0)) >= cap:
            return False, f"{OPS_LABELS[key]}已经到上限（{cap}）。", []
        cost = OPS_COSTS[key]
        if not _take_gold(state, cost):
            return False, f"需要 {cost} 金币。", []
        c["ops"][key] = int(c["ops"].get(key, 0)) + 1
        label = {"staff": "团队人数", "quality": "作品品质", "marketing": "宣传力度"}[key]
        story = (f"你把{action}这件事办妥了：{label}提升到 {c['ops'][key]}/{cap}。"
                 "团队会记住这种投入，下一次项目结算时它会有用。")
        return True, story, [f"【系统】{action}完成：{label} +1（{c['ops'][key]}/{cap}），"
                            f"系统金币 -{cost}。"]
    if action == "项目":
        project_id = parts[1] if len(parts) > 1 else ""
        plan = parts[2] if len(parts) > 2 else "steady"
        return start_project(state, project_id, plan)
    return False, "【经营】可选：招聘 / 培训 / 宣传 / 项目 <id> <steady|bold>。", []


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
        notices.append(f"【系统】周结算：{label}本周收入 系统金币 +{income}（工资与资产收益）。")
    ops = c.get("ops") or {}
    staff = int(ops.get("staff", 0) or 0)
    staff_cost = staff * STAFF_WEEKLY_COST
    if staff_cost:
        if _take_gold(state, staff_cost):
            notices.append(f"【系统】团队周薪：系统金币 -{staff_cost}（{staff}人）。")
        else:
            ops["staff"] = 0
            notices.append("【系统】账面不足以支付团队周薪，团队暂时解散。")
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
    elif body.startswith("经营"):
        ok, story, ns = _ops_action(state, body[len("经营"):].strip())
        if not ok:
            raise ValueError(story)
        notices.extend(ns)
    else:
        raise ValueError("【事业】可选行动：入门 <领域> / 晋升 / 特训 / 经营 <招聘|培训|宣传|项目>。")

    from .engine import _drop_oldest
    choices = ["继续今天的行程", "看看系统面板", "联系领域里认识的人"]
    return {"story_text": story, "narration_world": "urban", "choices": choices,
            "state_updates": {}, "system_notice": "", "_notices": notices}


def career_view(state: dict) -> dict:
    c = ensure_career(state)
    d = c["domain"]
    active = _active_project(c)
    completed = [_project_view(state, project) for project in (c.get("projects") or [])
                 if project.get("status") != "active"][-3:]
    return {
        "domain": d, "stage": c["stage"],
        "stage_name": STAGES[d][c["stage"]] if d else "未入行",
        "fame": dict(c["fame"]),
        "weekly_income": WEEKLY_INCOME[d][c["stage"]] if d else 0,
        "opportunities": list(c["opportunities"]),
        "ops": dict(c.get("ops") or {}),
        "active_project": _project_view(state, active) if active else None,
        "project_options": project_options(state),
        "completed_projects": completed,
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
    ops = c.get("ops") or {}
    active = _active_project(c)
    project = (f"；项目「{active['name']}」剩{max(0, int(active['end_day']) - int(state.get('time', {}).get('day', 1)))}天"
               if active else "；当前无经营项目")
    return (f"{c['domain']}·{STAGES[c['domain']][c['stage']]}，"
            f"周薪{WEEKLY_INCOME[c['domain']][c['stage']]}金/周，名望（{fame}）；"
            f"团队{ops.get('staff',0)}/品质{ops.get('quality',0)}/宣传{ops.get('marketing',0)}"
            f"{project}；晋升用【事业】晋升、训练用【事业】特训、经营用【事业】经营")
