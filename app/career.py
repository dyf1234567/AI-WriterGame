"""事业引擎：娱乐/电竞/商业三领域并行（成长爽文型）。

入门靠机遇标记（世界事件产出）或硬门槛直接申请；周结算发周薪
（内部通道）＋资产收益；【事业】前缀行动处理晋升与特训；
【经营】前缀处理团队、宣传与项目，项目按游戏日到期自动结算。
名望是跨系统货币——事件门槛、NPC 反应、晋升要求都看它。
"""
import random

from . import skills as sk
from .models import CASH, clamp, now_iso
from . import enterprises

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

# 直接申请入门的硬门槛：(技能id, 等级) + 属性(名, 值) 或 华夏币
ENTRY_REQUIREMENTS = {
    "娱乐": {"skill": ("vocal", 3), "stat": ("魅力", 10)},
    "电竞": {"skill": ("mech", 3), "stat": ("头脑", 10)},
    "商业": {"skill": ("manage", 2), "gold": 200},
}
ENTRY_OPPORTUNITIES = {"娱乐": "经纪公司试镜邀请", "电竞": "青训营测试资格",
                        "商业": "天使投资人名片"}

# 晋升要求：stage→(核心技能等级, 名望, 华夏币投入)；特定阶段发资产
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

ROLES = {"娱乐": ("歌手", "演员", "导演", "编剧", "主播", "制作人", "传媒公司老板"),
         "电竞": ("职业选手", "战队老板", "教练", "主播"),
         "商业": ("店主", "创始人", "投资人", "职业经理人")}
OWNER_ROLES = ("战队老板", "传媒公司老板", "创始人", "投资人")
ROLE_SKILLS = {"演员": "acting", "导演": "acting", "编剧": "speech", "主播": "speech",
               "制作人": "stage", "传媒公司老板": "manage", "战队老板": "manage",
               "教练": "sense", "投资人": "invest", "职业经理人": "manage"}


def _day(state: dict) -> int:
    return max(1, int(state.get("time", {}).get("day", 1)))


def _sync(c: dict) -> None:
    """domain/stage/ops兼容旧存档和界面；positions才是多领域持有权。"""
    domain = c.get("active_domain")
    pos = c.get("positions", {}).get(domain, {})
    c["domain"] = domain if pos else None
    c["stage"] = int(pos.get("stage", 0))
    c["ops"] = pos.get("ops", {k: 0 for k in OPS_CAPS})
    c["_mirror_domain"], c["_mirror_stage"] = c["domain"], c["stage"]


def _position(state: dict, c: dict, domain: str, stage: int = 1, role: str = "") -> dict:
    if domain not in c["positions"]:
        c["positions"][domain] = {"stage": clamp(stage, 1, 5),
            "roles": [role or ROLES[domain][0]], "active_role": role or ROLES[domain][0],
            "ops": {k: 0 for k in OPS_CAPS}, "employees": [], "delegated": False,
            "employment_contract": not role or role not in OWNER_ROLES,
            "entered_day": _day(state), "last_salary_day": _day(state), "train_week": "", "train_count": 0}
    return c["positions"][domain]


def ensure_career(state: dict) -> dict:
    p = state.setdefault("player", {})
    c = p.setdefault("career", {}) if isinstance(p.get("career"), dict) else {}
    p["career"] = c
    migrating = not isinstance(c.get("positions"), dict)
    if migrating:
        c["positions"] = {}
    legacy_domain, legacy_stage = c.get("domain"), int(c.get("stage", 0) or 0)
    if (legacy_domain in DOMAINS and legacy_stage > 0 and
            (migrating or legacy_domain != c.get("_mirror_domain") or legacy_stage != c.get("_mirror_stage"))):
        pos = _position(state, c, legacy_domain, legacy_stage)
        pos["stage"] = clamp(legacy_stage, 1, 5)
        if migrating and isinstance(c.get("ops"), dict):
            pos["ops"] = c["ops"]
        c["active_domain"] = legacy_domain
    c.setdefault("active_domain", next(iter(c["positions"]), None))
    if c["active_domain"] not in c["positions"]:
        c["active_domain"] = next(iter(c["positions"]), None)
    fame = c.get("fame") if isinstance(c.get("fame"), dict) else {}
    c["fame"] = {d: clamp(int(fame.get(d, 0) or 0), 0, 100) for d in DOMAINS}
    c.setdefault("opportunities", [])
    c.setdefault("week_key", "")
    c.setdefault("train_week", "")
    c.setdefault("train_count", 0)
    c.setdefault("settled_through", _day(state))
    c.setdefault("legacy_asset_settled_day", _day(state))
    for domain, pos in list(c["positions"].items()):
        if domain not in DOMAINS or not isinstance(pos, dict):
            c["positions"].pop(domain)
            continue
        pos["stage"] = clamp(int(pos.get("stage", 1) or 1), 1, 5)
        pos.setdefault("roles", [ROLES[domain][0]])
        pos.setdefault("active_role", pos["roles"][0] if pos["roles"] else ROLES[domain][0])
        pos.setdefault("employment_contract", pos["active_role"] not in OWNER_ROLES)
        for key, default in (("entered_day", _day(state)), ("last_salary_day", _day(state)),
                             ("employees", []), ("delegated", False), ("train_week", ""), ("train_count", 0)):
            pos.setdefault(key, default)
        ops = pos.get("ops") if isinstance(pos.get("ops"), dict) else {}
        pos["ops"] = {k: clamp(int(ops.get(k, 0) or 0), 0, cap) for k, cap in OPS_CAPS.items()}
    if not isinstance(c.get("projects"), list):
        c["projects"] = []
    try:
        c["project_seq"] = max(0, int(c.get("project_seq", 0)))
    except (TypeError, ValueError):
        c["project_seq"] = 0
    if not isinstance(p.get("assets"), list):
        p["assets"] = []
    enterprises.ensure(state)
    enterprises.migrate_legacy_assets(state)
    _sync(c)
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
    return currency_count(state, currency=CASH)


cash_count = _gold_count


def _take_gold(state: dict, n: int) -> bool:
    if n < 0 or _gold_count(state) < n:
        return False
    # 借用 remove 通道：华夏币按负数入账走 _remove_items
    from .engine import _remove_items
    return _remove_items(state, CASH, n) >= n


def _give_cash(state: dict, amount: int) -> None:
    from .engine import _apply_items
    if amount > 0:
        _apply_items(state, [{"name": CASH, "desc": "现实生活与事业资金", "count": amount}])


def entry_check(state: dict, domain: str) -> tuple[bool, str]:
    """入门资格：机遇标记直通，或硬门槛（技能+属性/华夏币）。"""
    if domain not in DOMAINS:
        return False, "没有这个领域（可选：娱乐/电竞/商业）。"
    c = ensure_career(state)
    if domain in c["positions"]:
        return False, f"已经持有{domain}职业，可切换焦点或选择其他职业角色。"
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
        return False, f"直接申请需要启动资金 {req['gold']} 华夏币（当前 {_gold_count(state)}）。"
    return True, "硬门槛达标，直接申请成功！"


def _active_project(c: dict, domain: str | None = None) -> dict | None:
    domain = domain or c.get("active_domain")
    return next((p for p in c.get("projects", []) if p.get("status") == "active"
                 and p.get("domain") == domain), None)


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


def project_options(state: dict, domain: str | None = None) -> list[dict]:
    c = ensure_career(state)
    domain = domain or c.get("active_domain")
    if domain not in PROJECTS:
        return []
    pos = c["positions"].get(domain, {})
    active = _active_project(c, domain)
    gold = _gold_count(state)
    out = []
    for project_id, template in PROJECTS[domain].items():
        skill_id, need = template["skill"]
        level = sk.level(state, skill_id)
        stage_ok = int(pos.get("stage", 0)) >= int(template["min_stage"])
        affordable = gold >= int(template["cost"])
        reasons = []
        if not stage_ok:
            reasons.append(f"需{STAGES[domain][template['min_stage']]}阶段")
        if active:
            reasons.append("已有进行中的项目")
        if not affordable:
            reasons.append(f"需{template['cost']}华夏币")
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


def start_project(state: dict, project_id: str, plan: str = "steady", domain: str | None = None) -> tuple[bool, str, list[str]]:
    c = ensure_career(state)
    domain = domain or c.get("active_domain")
    if domain not in PROJECTS:
        return False, "还没有入行，先通过【事业】入门一个领域。", []
    template = PROJECTS[domain].get(str(project_id))
    if template is None:
        return False, "没有这个项目。", []
    pos = c["positions"].get(domain, {})
    if int(pos.get("stage", 0)) < int(template["min_stage"]):
        return False, f"这个项目需要{STAGES[domain][template['min_stage']]}阶段。", []
    if _active_project(c, domain) is not None:
        return False, "本领域已有进行中的项目，其他领域仍可同时开展。", []
    if _gold_count(state) < int(template["cost"]):
        return False, f"启动资金不足：需要 {template['cost']} 华夏币。", []
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
    c["projects"] = ([p for p in c["projects"] if p.get("status") != "active"][-24:]
                     + [p for p in c["projects"] if p.get("status") == "active"])
    plan_label = "进取" if plan == "bold" else "稳妥"
    story = (f"你把{template['name']}的项目书签了字，投入 {template['cost']} 华夏币。"
             f"这一轮走{plan_label}路线，预计 {template['days']} 天后结算。"
             "接下来要做的是把人和钱用在正确的地方，而不是每天盯着账面。")
    return True, story, [f"【系统】已启动经营项目「{template['name']}」（{plan_label}），"
                        f"{template['days']} 天后结算。"]


def _resolve_project(state: dict, c: dict, project: dict, day: int) -> list[str]:
    if project.get("status") != "active":
        return []
    skill_id, _need = project.get("skill", ["vocal", 1])
    position = c["positions"].get(project.get("domain"), {})
    ops = position.get("ops") or {}
    plan = project.get("plan", "steady")
    score = (sk.level(state, skill_id) + sk.attr_bonus(state, skill_id)
             + int(position.get("stage", 0)) + int(ops.get("quality", 0))
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
    # 先标记结算，后续奖励函数可能触发嵌套ensure，不会重复发放。
    project.update({"status": "completed", "outcome": outcome,
                    "completed_day": day, "score": total, "roll": roll})
    if gold:
        _give_cash(state, gold)
        notices.append(f"【系统】经营收入：华夏币 +{gold}。")
    if fame:
        add_fame(state, project.get("domain", ""), fame)
        notices.append(f"【系统】{project.get('domain', '')}名望 +{fame}。")
    if xp:
        notices.extend(sk.add_xp(state, skill_id, xp))
        notices.append(f"【系统】{sk.SKILLS[skill_id][0]}经验 +{xp}。")
    if project.get("domain") == "娱乐" and outcome != "fail":
        work = enterprises.create_work(state, project)
        project["work_id"] = work["id"]
        notices.append(f"【系统】作品「{work['name']}」已交付，可选择渠道发行。")
    if project.get("domain") == "电竞" and outcome == "success":
        team = enterprises.find(state, "", "team")
        if team:
            team["matches"] = team.get("matches", 0) + 1
            team["wins"] = team.get("wins", 0) + 1
            team["fans"] = team.get("fans", 0) + fame * 5
            if project.get("template") == "league":
                team["trophies"] = team.get("trophies", 0) + 1
    if outcome == "success" and project.get("asset"):
        entity, first = enterprises.award_asset(state, project["asset"],
            f"project:{project['domain']}:{project['template']}", project["domain"], day=day)
        project["asset_id"] = entity["id"]
        notices.append(f"【系统】{'获得资产' if first else '维护/续签已有资产'}：{entity['name']}；所有权总量保持100%。")
    result = (f"{label}（评分 {total}/{difficulty}，骰子 {roll:+d}）："
              f"华夏币 +{gold}、名望 +{fame}、经验 +{xp}")
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
            notices.extend(_resolve_project(state, c, project, int(project.get("end_day", day))))
    return notices


def _ops_action(state: dict, body: str) -> tuple[bool, str, list[str]]:
    c = ensure_career(state)
    if not c.get("domain"):
        return False, "还没有入行，先通过【事业】入门一个领域。", []
    parts = body.split()
    position = c["positions"][c["active_domain"]]
    action = parts[0] if parts else ""
    if action in ("招聘", "培训", "宣传"):
        key = {"招聘": "staff", "培训": "quality", "宣传": "marketing"}[action]
        cap = OPS_CAPS[key]
        if int(c["ops"].get(key, 0)) >= cap:
            return False, f"{OPS_LABELS[key]}已经到上限（{cap}）。", []
        cost = OPS_COSTS[key]
        if not _take_gold(state, cost):
            return False, f"需要 {cost} 华夏币。", []
        c["ops"][key] = int(c["ops"].get(key, 0)) + 1
        if key == "staff":
            employee = enterprises.hire(state, c["domain"], parts[1] if len(parts) > 1 else "")
            if employee is None:
                num = len(position["employees"]) + 1
                employee = {"id": f"{c['domain']}_staff_{num}",
                    "name": parts[1] if len(parts) > 1 else f"{c['domain']}成员{num}",
                    "role": "团队成员", "ability": 40, "weekly_salary": STAFF_WEEKLY_COST, "status": "employed"}
            position["employees"].append(employee)
        elif key == "quality":
            for employee in position["employees"]:
                if employee.get("status") == "employed":
                    employee["ability"] = min(100, employee.get("ability", 40) + 5)
            for entity in enterprises.ensure(state):
                if entity.get("domain") == c["domain"] and entity["kind"] == "team":
                    for member in entity.get("roster", []):
                        member["ability"] = min(100, member["ability"] + 3)
        label = {"staff": "团队人数", "quality": "作品品质", "marketing": "宣传力度"}[key]
        story = (f"你把{action}这件事办妥了：{label}提升到 {c['ops'][key]}/{cap}。"
                 "团队会记住这种投入，下一次项目结算时它会有用。")
        return True, story, [f"【系统】{action}完成：{label} +1（{c['ops'][key]}/{cap}），"
                            f"华夏币 -{cost}。"]
    if action == "项目":
        project_id = parts[1] if len(parts) > 1 else ""
        plan = parts[2] if len(parts) > 2 else "steady"
        return start_project(state, project_id, plan)
    return False, "【经营】可选：招聘 / 培训 / 宣传 / 项目 <id> <steady|bold>。", []


def _salary(state: dict, c: dict, domain: str, pos: dict, day: int) -> list[str]:
    income = WEEKLY_INCOME[domain][pos["stage"]] if pos.get("employment_contract") else 0
    _give_cash(state, income)
    notices = ([f"【系统】周结算：{domain}·{STAGES[domain][pos['stage']]}第{day}日工资 华夏币 +{income}。"]
               if income else [])
    staff_cost = int(pos.get("ops", {}).get("staff", 0)) * STAFF_WEEKLY_COST
    if staff_cost:
        if _take_gold(state, staff_cost):
            notices.append(f"【系统】团队周薪：华夏币 -{staff_cost}（{domain}）。")
        else:
            pos["ops"]["staff"] = 0
            pos["delegated"] = False
            for employee in pos.get("employees", []):
                employee["status"] = "left"
            for entity in enterprises.ensure(state):
                if entity.get("domain") == domain:
                    for employee in entity.get("employees", []):
                        employee["status"] = "left"
            notices.append(f"【系统】{domain}团队周薪不足，成员离职。")
    if pos["stage"] >= 2:
        add_fame(state, domain, 1)
    return notices


def settle_until(state: dict, from_day: int, to_day: int) -> list[str]:
    """补齐每个游戏日的工资、项目与企业节点；相同区间重复调用幂等。"""
    c = ensure_career(state)
    start = max(1, int(from_day), int(c.get("settled_through", from_day)))
    finish = max(start, int(to_day))
    notices = []
    for day in range(start + 1, finish + 1):
        for project in list(c["projects"]):
            if project.get("status") == "active" and int(project.get("end_day", day)) <= day:
                notices.extend(_resolve_project(state, c, project, day))
        for domain, pos in list(c["positions"].items()):
            while int(pos["last_salary_day"]) + 7 <= day:
                pos["last_salary_day"] += 7
                notices.extend(_salary(state, c, domain, pos, pos["last_salary_day"]))
        while int(c["legacy_asset_settled_day"]) + 7 <= day:
            c["legacy_asset_settled_day"] += 7
            income = sum(max(0, int(a.get("weekly", 0))) for a in state["player"]["assets"]
                         if not a.get("entity_id"))
            _give_cash(state, income)
            if income:
                notices.append(f"【系统】旧有资产第{day}日收入 华夏币 +{income}。")
        notices.extend(enterprises.settle_day(state, day))
        for domain, pos in list(c["positions"].items()):
            if not pos.get("delegated") or _active_project(c, domain):
                continue
            if (day - int(pos["entered_day"])) % 7:
                continue
            template_id = next(iter(PROJECTS[domain]))
            reserve = pos["ops"].get("staff", 0) * STAFF_WEEKLY_COST + 50
            if _gold_count(state) >= PROJECTS[domain][template_id]["cost"] + reserve:
                ok, _story, ns = start_project(state, template_id, "steady", domain)
                if ok:
                    project = _active_project(c, domain)
                    project["start_day"], project["end_day"] = day, day + PROJECTS[domain][template_id]["days"]
                    notices.append(f"【系统】{domain}委托经理在第{day}日续接基础项目。")
                    notices.extend(ns)
        c["settled_through"] = day
    # 旧存档可能已经位于到期当天，统一时钟也会用(day, day)刷新；空区间仍补账。
    due_day = max(1, int(to_day))
    for project in list(c["projects"]):
        if project.get("status") == "active" and int(project.get("end_day", due_day)) <= due_day:
            notices.extend(_resolve_project(state, c, project, int(project.get("end_day", due_day))))
    for domain, pos in list(c["positions"].items()):
        while int(pos["last_salary_day"]) + 7 <= due_day:
            pos["last_salary_day"] += 7
            notices.extend(_salary(state, c, domain, pos, pos["last_salary_day"]))
    while int(c["legacy_asset_settled_day"]) + 7 <= due_day:
        c["legacy_asset_settled_day"] += 7
        income = sum(max(0, int(a.get("weekly", 0))) for a in state["player"]["assets"] if not a.get("entity_id"))
        _give_cash(state, income)
        if income:
            notices.append(f"【系统】旧有资产第{c['legacy_asset_settled_day']}日收入 华夏币 +{income}。")
    notices.extend(enterprises.settle_day(state, due_day))
    _sync(c)
    return notices


def settle_week(state: dict, week_key: str) -> list[str]:
    """兼容旧周键API并补结漏周；新统一时间推进只调用settle_until。"""
    from datetime import date
    c = ensure_career(state)
    if c["week_key"] == week_key:
        return []
    periods = 1
    def monday(key):
        year, week = key.split("-W")
        return date.fromisocalendar(int(year), int(week), 1)
    if c["week_key"]:
        try:
            periods = (monday(week_key) - monday(c["week_key"])).days // 7
        except (ValueError, TypeError):
            periods = 1
        if periods <= 0:
            return []
    c["week_key"] = week_key
    notices = []
    for _ in range(periods):
        for domain, pos in c["positions"].items():
            notices.extend(_salary(state, c, domain, pos, _day(state)))
        legacy = sum(max(0, int(a.get("weekly", 0))) for a in state["player"]["assets"] if not a.get("entity_id"))
        _give_cash(state, legacy)
        if legacy:
            notices.append(f"【系统】资产周收入 华夏币 +{legacy}。")
    _sync(c)
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
        return False, f"晋升需要投入 {gold_need} 华夏币（当前 {_gold_count(state)}）。"
    c["stage"] = nxt
    c["positions"][c["active_domain"]]["stage"] = nxt
    _sync(c)
    add_fame(state, c["domain"], 10)
    asset = STAGE_ASSETS.get((c["domain"], nxt))
    if asset:
        enterprises.award_asset(state, asset, f"promotion:{c['domain']}:{nxt}", c["domain"])
    from .models import refresh_main_quest
    refresh_main_quest(state)
    employed = c["positions"][c["active_domain"]].get("employment_contract")
    msg = f"【系统】事业晋升：{c['domain']}·{STAGES[c['domain']][nxt]}，名望 +10。"
    if employed:
        msg += f"职业周薪涨至{WEEKLY_INCOME[c['domain']][nxt]}华夏币/周。"
    if asset:
        msg += f" 获得资产：{asset['name']}，按实际经营结果与股权分红。"
    return True, msg


def _train_check(state: dict) -> tuple[bool, str, list[str]]:
    """特训：15华夏币和120游戏分钟换20经验，每领域每周限3次。"""
    from .shop import _week_key
    c = ensure_career(state)
    if not c["domain"]:
        return False, "先入门一个领域才能特训（未入行时请用自由练习行动）。", []
    wk = _week_key(state)
    pos = c["positions"][c["active_domain"]]
    if pos["train_week"] != wk:
        pos["train_week"], pos["train_count"] = wk, 0
    if pos["train_count"] >= sk.TRAIN_WEEK_CAP:
        return False, f"本周特训已满 {sk.TRAIN_WEEK_CAP} 次，下周再来。", []
    if not _take_gold(state, sk.TRAIN_COST):
        return False, f"特训需要 {sk.TRAIN_COST} 华夏币（当前 {_gold_count(state)}）。", []
    pos["train_count"] += 1
    c["train_week"], c["train_count"] = wk, pos["train_count"]
    core = ROLE_SKILLS.get(pos.get("active_role")) or PROMOTION[c["domain"]].get(max(c["stage"], 1), ("vocal",))[0]
    notices = sk.add_xp(state, core, sk.TRAIN_XP)
    sname = sk.SKILLS[core][0]
    notices.insert(0, f"【系统】特训完成：{sname} +{sk.TRAIN_XP} 经验（本周第 {c['train_count']}/{sk.TRAIN_WEEK_CAP} 次）。")
    # 时间由统一引擎按duration_minutes推进，避免直接改时段造成双重计时。
    return True, "", notices


def _switch(state: dict, domain: str) -> tuple[bool, str]:
    c = ensure_career(state)
    if domain not in c["positions"]:
        return False, "尚未进入这个领域，请先入门、创办公司或收购战队。"
    c["active_domain"] = domain
    _sync(c)
    return True, f"当前关注切换为{domain}，其他事业、项目、资产与团队继续保留。"


def _delegate(state: dict, enabled: bool) -> tuple[bool, str]:
    c = ensure_career(state)
    pos = c["positions"].get(c["active_domain"])
    if not pos:
        return False, "还没有可以委托的事业。"
    if enabled and not any(e.get("status") == "employed" for e in pos["employees"]):
        return False, "至少招聘一名在职团队成员后才能委托经营。"
    pos["delegated"] = enabled
    for entity in enterprises.ensure(state):
        if entity.get("domain") == c["active_domain"]:
            entity["delegated"] = enabled
    return True, ("已委托团队按周审查预算并续接基础项目，保留50华夏币生活储备。"
                  if enabled else "已收回经营决策权，现有项目继续执行。")


def _owned_command(state: dict, body: str) -> tuple[bool, str]:
    parts = body.split()
    action, args = parts[0], parts[1:]
    if action == "发行":
        identity = args[0] if args and args[0] not in ("流媒体", "网络", "院线") else ""
        channel = args[-1] if args and args[-1] in ("流媒体", "网络", "院线") else "流媒体"
        return enterprises.release_work(state, identity, channel)
    if action in ("融资", "增持"):
        if not args:
            return False, f"用法：{action} <公司/战队id> <股权百分比>。"
        try:
            percent = int(args[-1].rstrip("%"))
        except ValueError:
            return False, "股权比例必须是整数。"
        return (enterprises.finance if action == "融资" else enterprises.buy_equity)(
            state, args[0] if len(args)>1 else "", percent)
    if action == "定价":
        try:
            price = int(args[-1])
        except (ValueError, IndexError):
            return False, "用法：定价 [公司id] <5—100>。"
        return enterprises.set_price(state, args[0] if len(args)>1 else "", price)
    if action == "阵容":
        team = enterprises.find(state, args[0], "team") if args else None
        return enterprises.set_lineup(state, team["id"] if team else "", args[1:] if team else args)
    if action == "参赛":
        return enterprises.team_match(state, args[0] if args else "")
    if action == "注资":
        if len(args)<2:
            return False, "用法：注资 <公司/战队id> <金额>。"
        entity = enterprises.find(state, args[0])
        try:
            amount = int(args[1])
        except ValueError:
            return False, "金额应为正整数。"
        if not entity or entity["kind"] not in ("company", "team") or amount <= 0:
            return False, "请选择公司或战队，并提供正金额。"
        if not _take_gold(state, amount):
            return False, f"现实资金不足，需要{amount}华夏币。"
        entity["cash"] += amount
        entity["status"] = "operating"
        return True, f"向「{entity['name']}」注资{amount}华夏币，企业账上{entity['cash']}。"
    return False, "没有这个经营操作。"


def action_label(state: dict, action: str) -> str | None:
    for prefix in (PREFIX, "【经营】"):
        if action.startswith(prefix):
            return action[len(prefix):].strip()
    return None


def before_turn(state: dict, action: str) -> dict | None:
    """确定性事业操作；技能与已有身份不限制跨界持有或首日创业。"""
    if action.startswith("【经营】"):
        action = PREFIX + "经营 " + action[len("【经营】"):]
    if not action.startswith(PREFIX):
        return None
    body = action[len(PREFIX):].strip()
    notices: list[str] = []
    c = ensure_career(state)
    duration = 60

    if body.startswith("入门"):
        domain = next((d for d in DOMAINS if d in body), "")
        ok, msg = entry_check(state, domain) if domain else (False, "请指明领域：入门 娱乐/电竞/商业")
        if ok:
            req = ENTRY_REQUIREMENTS[domain]
            if "gold" in req and ENTRY_OPPORTUNITIES[domain] not in c["opportunities"]:
                if not _take_gold(state, req["gold"]):
                    raise ValueError("启动资金不足。")
            _position(state, c, domain)
            c["active_domain"] = domain
            _sync(c)
            add_fame(state, domain, 5)
            notices.append(f"【系统】事业入门：{domain}·{STAGES[domain][1]}！周薪 {WEEKLY_INCOME[domain][1]} 华夏币/周起步。{msg}")
            story = (f"你正式踏入了{domain}这条路。{msg}\n从今天起，{STAGES[domain][1]}就是你的新身份——"
                     f"系统面板刷新，周薪 {WEEKLY_INCOME[domain][1]} 华夏币/周已激活。已有事业和身份继续保留。")
        else:
            raise ValueError(msg)
    elif body.startswith("切换"):
        ok, story = _switch(state, next((d for d in DOMAINS if d in body), ""))
        if not ok:
            raise ValueError(story)
        duration = 0
    elif body.startswith("职业"):
        domain = next((d for d in DOMAINS if d in body), c["active_domain"])
        position = c["positions"].get(domain)
        role = next((r for r in sorted(ROLES.get(domain, ()), key=len, reverse=True) if r in body), "")
        if not position or not role:
            raise ValueError("先入门领域，再选择职业：" + "；".join(f"{d}：{'/'.join(rs)}" for d,rs in ROLES.items()))
        if role not in position["roles"]:
            position["roles"].append(role)
        position["active_role"] = role
        c["active_domain"] = domain
        _sync(c)
        story = f"开始以{role}的身份发展。已有职业和资产保留，职业名称本身不增加收入、能力或成果。"
    elif body.startswith(("创办", "创业")):
        parts = body.split(maxsplit=1)
        name = parts[1] if len(parts)>1 else "我的工作室"
        domain = "娱乐" if any(w in name for w in ("传媒", "影视", "音乐", "唱片")) else "商业"
        ok, story = enterprises.found_company(state, name, domain)
        if not ok:
            raise ValueError(story)
        role = "传媒公司老板" if domain == "娱乐" else "创始人"
        position = _position(state, c, domain, 1, role)
        if role not in position["roles"]:
            position["roles"].append(role)
        position["active_role"] = role
        c["active_domain"] = domain
        _sync(c)
    elif body.startswith("收购战队") or body.startswith("收购 战队"):
        name = body.replace("收购战队", "", 1).replace("收购 战队", "", 1).strip() or "城市新星战队"
        ok, story = enterprises.acquire_team(state, name)
        if not ok:
            raise ValueError(story)
        position = _position(state, c, "电竞", 1, "战队老板")
        if "战队老板" not in position["roles"]:
            position["roles"].append("战队老板")
        position["active_role"] = "战队老板"
        c["active_domain"] = "电竞"
        _sync(c)
    elif body.startswith("晋升"):
        ok, msg = _promo_check(state)
        if not ok:
            raise ValueError(msg)
        notices.append(msg)
        d, s = c["domain"], c["stage"]
        story = f"你的答辩、战绩与经营结果获得认可，事业阶段变为{STAGES[d][s]}。{msg}"
    elif body.startswith("特训"):
        ok, msg, ns = _train_check(state)
        if not ok:
            raise ValueError(msg)
        notices.extend(ns)
        story = f"你把自己摁在训练场整整一个时段——汗水没有白流。{ns[0].split('：', 1)[1]}"
        duration = 120
    elif body.startswith(("委托", "收回委托")):
        ok, story = _delegate(state, not body.startswith("收回"))
        if not ok:
            raise ValueError(story)
    elif body.startswith("经营"):
        sub = body[len("经营"):].strip()
        if sub.split() and sub.split()[0] in ("发行", "融资", "增持", "定价", "阵容", "参赛", "注资"):
            ok, story = _owned_command(state, sub)
            ns = []
        else:
            ok, story, ns = _ops_action(state, sub)
        if not ok:
            raise ValueError(story)
        notices.extend(ns)
    elif body.split() and body.split()[0] in ("发行", "融资", "增持", "定价", "阵容", "参赛", "注资"):
        ok, story = _owned_command(state, body)
        if not ok:
            raise ValueError(story)
    else:
        raise ValueError("可用行动：入门/切换 <领域>、职业 <角色>、创办 <公司名>、收购战队 [名字]、晋升、特训、经营 招聘|培训|宣传|项目、委托、定价、发行、阵容、参赛、融资、增持、注资。")

    choices = ["继续今天的行程", "看看系统面板", "联系领域里认识的人"]
    return {"story_text": story, "narration_world": "urban", "choices": choices,
            "state_updates": {"duration_minutes": duration}, "system_notice": "", "_notices": notices}


def career_view(state: dict) -> dict:
    from .shop import _week_key
    c = ensure_career(state)
    d = c["domain"]
    active = _active_project(c)
    completed = [_project_view(state, project) for project in (c.get("projects") or [])
                 if project.get("status") != "active"][-3:]
    positions = []
    for domain, position in c["positions"].items():
        positions.append({"domain": domain, "stage": position["stage"],
            "stage_name": STAGES[domain][position["stage"]], "roles": list(position["roles"]),
            "active_role": position["active_role"], "delegated": position["delegated"],
            "ops": dict(position["ops"]), "employees": [dict(e) for e in position["employees"]],
            "project_options": project_options(state, domain),
            "weekly_income": WEEKLY_INCOME[domain][position["stage"]] if position.get("employment_contract") else 0})
    pos = c["positions"].get(d, {})
    return {
        "domain": d, "active_domain": d, "stage": c["stage"], "currency": CASH,
        "stage_name": STAGES[d][c["stage"]] if d else "未入行",
        "fame": dict(c["fame"]),
        "weekly_income": sum(p["weekly_income"] for p in positions),
        "opportunities": list(c["opportunities"]),
        "ops": dict(c.get("ops") or {}),
        "active_project": _project_view(state, active) if active else None,
        "active_projects": [_project_view(state, p) for p in c["projects"] if p.get("status") == "active"],
        "all_positions": positions, "positions": {p["domain"]: p for p in positions},
        "role_options": ROLES, "enterprises": enterprises.view(state),
        "project_options": project_options(state),
        "completed_projects": completed,
        "assets": [dict(a) for a in state["player"].get("assets", [])],
        "train_left": max(0, sk.TRAIN_WEEK_CAP - pos.get("train_count", 0)) if pos.get("train_week") == _week_key(state) else sk.TRAIN_WEEK_CAP,
    }


def career_line(state: dict) -> str:
    """提示词行。"""
    c = ensure_career(state)
    if not c["positions"]:
        opp = "、".join(c["opportunities"]) or "暂无"
        return (f"无固定事业（可通过活动机遇或技能门槛入门 娱乐/电竞/商业，也可持有200华夏币即创办公司、800华夏币收购战队；"
                f"持有机遇：{opp}）")
    descriptions = []
    for domain, pos in c["positions"].items():
        project = _active_project(c, domain)
        descriptions.append(f"{domain}·{STAGES[domain][pos['stage']]}（职业{'/'.join(pos['roles'])}，"
            f"{'委托经营' if pos['delegated'] else '亲自经营'}，名望{c['fame'][domain]}，"
            f"团队{pos['ops']['staff']}/品质{pos['ops']['quality']}/宣传{pos['ops']['marketing']}"
            + (f"，项目{project['name']}剩{max(0, project['end_day']-_day(state))}天" if project else "") + "）")
    owned = "；".join(f"{e['id']}:{e['name']}[{e['kind']}]持股{e['equity']['player']}%/估值{e['valuation']}/账上{e['cash']}华夏币"
                     + (f"/状态{e['status']}/受众{e.get('audience', 0)}" if e['kind'] == 'work' else "")
                     for e in enterprises.ensure(state)[-8:])
    return f"当前关注{c['active_domain']}；" + "；".join(descriptions) + ("；经营实体：" + owned if owned else "")
