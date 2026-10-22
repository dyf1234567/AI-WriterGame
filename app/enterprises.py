"""有身份、账本和所有权的经营实体；所有结算均使用游戏日。"""
from .models import CASH, clamp

COMPANY_COST = 200
TEAM_COST = 800


def ensure(state: dict) -> list[dict]:
    player = state.setdefault("player", {})
    if not isinstance(player.get("enterprises"), list):
        player["enterprises"] = []
    existing_ids = [int(str(e.get("id", "")).split("_")[-1]) for e in player["enterprises"]
                    if str(e.get("id", "")).startswith("ent_") and str(e.get("id", "")).split("_")[-1].isdigit()]
    player["enterprise_seq"] = max(int(player.get("enterprise_seq", 0) or 0), max(existing_ids, default=0))
    return player["enterprises"]


def migrate_legacy_assets(state: dict) -> None:
    """旧股份升级为有身份的实体；保存原资产引用，且不把同一所有权计算两次。"""
    import re
    assets = state["player"].setdefault("assets", [])
    for index, asset in enumerate(list(assets)):
        if asset.get("entity_id") or asset.get("type") not in ("公司股权", "战队股份"):
            continue
        domain = "电竞" if asset["type"] == "战队股份" else "商业"
        entity, _ = award_asset(state, asset, f"legacy:{index}:{asset.get('name', '')}", domain)
        match = re.search(r"(\d+)\s*%", asset.get("name", ""))
        if match:
            pct = clamp(int(match.group(1)), 1, 100)
            entity["equity"] = {"player": pct, "external": 100-pct}
            entity["valuation"] = round(int(asset.get("value", 0))*100/pct)
        mirrored = next(a for a in assets if a.get("entity_id") == entity["id"])
        asset.update(mirrored)
        if mirrored is not asset:
            assets.remove(mirrored)
        sync_asset(state, entity)


def find(state: dict, identity: str = "", kind: str = "") -> dict | None:
    entities = ensure(state)
    if identity:
        return next((e for e in entities if identity in (e.get("id"), e.get("name"))
                     and (not kind or e.get("kind") == kind)), None)
    return next((e for e in reversed(entities) if not kind or e.get("kind") == kind), None)


def _new(state: dict, kind: str, name: str, domain: str, **fields) -> dict:
    entities = ensure(state)
    player = state["player"]
    player["enterprise_seq"] += 1
    day = int(state.get("time", {}).get("day", 1))
    entity = {"id": f"ent_{player['enterprise_seq']}", "kind": kind,
              "name": str(name).replace("<", "").replace(">", "")[:40],
              "domain": domain, "created_day": day, "last_cashflow_day": day,
              "valuation": 0, "equity": {"player": 100, "external": 0},
              "cash": 0, "employees": [], "ledger": [], "status": "operating"}
    entity.update(fields)
    entities.append(entity)
    return entity


def _pay(state: dict, amount: int) -> bool:
    from .engine import _remove_items
    from .shop import currency_count
    if amount < 0 or currency_count(state, currency=CASH) < amount:
        return False
    return _remove_items(state, CASH, amount) >= amount


def _receive(state: dict, amount: int) -> None:
    from .engine import _apply_items
    if amount > 0:
        _apply_items(state, [{"name": CASH, "desc": "现实生活与事业资金", "count": amount}])


def _record(entity: dict, day: int, label: str, amount: int) -> None:
    entity["ledger"] = entity.get("ledger", [])[-51:] + [
        {"day": day, "label": label, "amount": int(amount), "cash": entity.get("cash", 0)}]


def sync_asset(state: dict, entity: dict) -> None:
    """资产只是实体所有权的显示镜像，不另行产生一份分红。"""
    if entity["kind"] not in ("company", "team", "contract"):
        return
    assets = state["player"].setdefault("assets", [])
    asset = next((a for a in assets if a.get("entity_id") == entity["id"]), None)
    if asset is None:
        asset = {"id": f"asset_{entity['id']}", "entity_id": entity["id"]}
        assets.append(asset)
    pct = int(entity.get("equity", {}).get("player", 0))
    asset.update({"name": f"{entity['name']} {pct}%股权" if entity["kind"] != "contract" else entity["name"],
                  "type": {"company": "公司股权", "team": "战队股份", "contract": "演出合约"}[entity["kind"]],
                  "equity_pct": pct, "value": round(entity.get("valuation", 0) * pct / 100),
                  "weekly": 0})


def found_company(state: dict, name: str = "我的工作室", domain: str = "商业") -> tuple[bool, str]:
    if not _pay(state, COMPANY_COST):
        return False, f"创办公司需要 {COMPANY_COST} 华夏币启动资金。"
    entity = _new(state, "company", name or "我的工作室", domain,
                  cash=150, valuation=COMPANY_COST, price=20, demand=60,
                  competition=30, quality=1, marketing=0, weekly_revenue=0,
                  profit=0, customers=0, delegated=False)
    _record(entity, entity["created_day"], "注册与启动资金（注册50，账上150）", COMPANY_COST)
    sync_asset(state, entity)
    return True, f"公司「{entity['name']}」已成立，持股100%，账上150华夏币。可招聘、定价、宣传和融资。"


def acquire_team(state: dict, name: str = "城市新星战队") -> tuple[bool, str]:
    if not _pay(state, TEAM_COST):
        return False, f"收购战队需要 {TEAM_COST} 华夏币。"
    roster = [{"id": f"member_{i}", "name": n, "position": role, "ability": ability}
              for i, (n, role, ability) in enumerate([
                  ("周策", "上路", 48), ("陈野", "打野", 50), ("许星", "中路", 52),
                  ("林川", "射手", 49), ("孟舟", "辅助", 51), ("韩雨", "替补", 47)], 1)]
    entity = _new(state, "team", name or "城市新星战队", "电竞", valuation=TEAM_COST,
                  cash=200, roster=roster, lineup=[r["id"] for r in roster[:5]],
                  matches=0, wins=0, trophies=0, fans=20, sponsorship=0,
                  weekly_revenue=0, profit=0, delegated=False)
    _record(entity, entity["created_day"], "收购（含200华夏币运营现金）", TEAM_COST)
    sync_asset(state, entity)
    return True, f"已收购「{entity['name']}」100%股权，六人名册与200华夏币运营现金已交接。可调整五人阵容、训练和参赛。"


def award_asset(state: dict, specification: dict, source: str, domain: str, day: int | None = None) -> tuple[dict, bool]:
    """固定来源只能取得一份股份；续签合约延长有效期，不复制永久收益。"""
    entities = ensure(state)
    old = next((e for e in entities if e.get("award_source") == source), None)
    day = int(day if day is not None else state.get("time", {}).get("day", 1))
    if old:
        if old["kind"] == "contract":
            old["end_day"] = max(day, old.get("end_day", day)) + 84
            old["status"] = "operating"
        sync_asset(state, old)
        return old, False
    kind = "team" if specification.get("type") == "战队股份" else (
        "company" if specification.get("type") == "公司股权" else "contract")
    name = specification.get("name", "经营资产")
    # 所有奖励股份由同一实体增持，重复项目不会生成另一份同名股份。
    pct = 10 if "10%" in name else 5 if "5%" in name else 60 if "60%" in name else 75
    if kind == "contract":
        pct = 100
    value = max(1, int(specification.get("value", 1)))
    entity = _new(state, kind, name, domain, award_source=source,
                  created_day=day, last_cashflow_day=day,
                  valuation=round(value * 100 / pct), equity={"player": pct, "external": 100-pct},
                  weekly_payout=max(0, int(specification.get("weekly", 0))),
                  end_day=day + 84 if kind == "contract" else 0)
    if kind == "company":
        entity.update({"cash": 200, "price": 20, "demand": 70, "competition": 30,
                       "quality": 2, "marketing": 0, "weekly_revenue": 0, "profit": 0, "customers": 0})
    elif kind == "team":
        entity.update({"cash": 200, "roster": [], "lineup": [], "fans": 30,
                       "sponsorship": 0, "matches": 0, "wins": 0, "trophies": 0,
                       "weekly_revenue": 0, "profit": 0})
    sync_asset(state, entity)
    return entity, True


def create_work(state: dict, project: dict) -> dict:
    entities = ensure(state)
    existing = next((e for e in entities if e.get("project_id") == project["id"] and e["kind"] == "work"), None)
    if existing:
        return existing
    day = int(project.get("completed_day", state.get("time", {}).get("day", 1)))
    edition = 1 + sum(e.get("kind") == "work" for e in entities)
    return _new(state, "work", f"{project['name']}·第{edition}部", "娱乐", created_day=day, last_cashflow_day=day,
                project_id=project["id"], status="ready", quality=clamp(int(project.get("score", 0))*6, 5, 100),
                audience=0, sales=0, released_day=None, valuation=int(project.get("cost", 0)))


def release_work(state: dict, identity: str = "", channel: str = "流媒体") -> tuple[bool, str]:
    from . import career
    work = find(state, identity, "work")
    if not work:
        return False, "还没有待发行作品。先完成单曲、综艺或巡演项目。"
    if work["status"] == "released":
        return False, "这部作品已经发行，不能重复发行领奖。"
    cost = {"流媒体": 40, "院线": 100, "网络": 20}.get(channel)
    if cost is None:
        return False, "发行渠道可选：流媒体 / 网络 / 院线。"
    if not _pay(state, cost):
        return False, f"发行需要 {cost} 华夏币。"
    position = career.ensure_career(state)["positions"].get("娱乐", {})
    marketing = int(position.get("ops", {}).get("marketing", 0))
    fame = career.ensure_career(state)["fame"].get("娱乐", 0)
    audience = max(10, int(work["quality"] * (2 + marketing) + fame * 8))
    sales = round(audience * (0.30 if channel == "院线" else 0.16 if channel == "流媒体" else 0.08))
    work.update({"status": "released", "channel": channel, "audience": audience, "sales": sales,
                 "released_day": int(state.get("time", {}).get("day", 1)), "valuation": sales})
    _receive(state, sales)
    career.add_fame(state, "娱乐", min(10, max(1, audience // 100)))
    _record(work, work["released_day"], f"{channel}发行收入", sales)
    return True, f"「{work['name']}」通过{channel}发行，触达{audience}位观众，销售收入{sales}华夏币。作品与受众记录已保留。"


def finance(state: dict, identity: str, percent: int) -> tuple[bool, str]:
    entity = find(state, identity)
    if not entity or entity["kind"] not in ("company", "team"):
        return False, "请选择公司或战队的名称/id。"
    if not isinstance(percent, int) or percent <= 0 or percent > 49:
        return False, "每次融资让出1—49个百分点股权。"
    equity = entity["equity"]
    if percent >= equity.get("player", 0):
        return False, "融资后至少保留1%股权，不能重复出售已经售出的股份。"
    amount = round(max(1, entity.get("valuation", 1)) * percent / 100)
    if amount <= 0:
        return False, "这笔股权价值过低，暂时没有投资方愿意认购。"
    equity["player"] -= percent
    equity["external"] = 100 - equity["player"]
    entity["cash"] += amount  # 增资用于企业经营，不能凭融资给个人凭空发钱。
    _record(entity, int(state.get("time", {}).get("day", 1)), f"融资让出{percent}%股权", amount)
    sync_asset(state, entity)
    return True, f"「{entity['name']}」融资{amount}华夏币进入企业账户，个人持股降至{equity['player']}%，外部持股{equity['external']}%。"


def buy_equity(state: dict, identity: str, percent: int) -> tuple[bool, str]:
    entity = find(state, identity)
    if not entity or entity["kind"] not in ("company", "team"):
        return False, "请选择公司或战队。"
    external = int(entity["equity"].get("external", 0))
    if percent <= 0 or percent > external:
        return False, f"可收购外部股权只有{external}%。"
    price = max(1, round(entity.get("valuation", 0) * percent / 100))
    if not _pay(state, price):
        return False, f"收购{percent}%股权需要{price}华夏币。"
    entity["equity"]["player"] += percent
    entity["equity"]["external"] -= percent
    sync_asset(state, entity)
    return True, f"收购完成，支付{price}华夏币，现持有「{entity['name']}」{entity['equity']['player']}%股权。"


def set_price(state: dict, identity: str, price: int) -> tuple[bool, str]:
    entity = find(state, identity, "company")
    if not entity:
        return False, "还没有公司。可先创办公司。"
    if entity.get("equity", {}).get("player", 0) <= 50:
        return False, "持股未超过50%，不能单方面调整公司定价。"
    if price < 5 or price > 100:
        return False, "商品定价应在5—100华夏币之间。"
    entity["price"] = price
    return True, f"「{entity['name']}」定价调整为{price}华夏币。高价提高单笔毛利，也会减少需求；周结算会给出客流与竞争结果。"


def set_lineup(state: dict, identity: str, members: list[str]) -> tuple[bool, str]:
    entity = find(state, identity, "team")
    if not entity:
        return False, "还没有战队。"
    if entity.get("equity", {}).get("player", 0) <= 50:
        return False, "持股未超过50%，不能单方面调整战队阵容。"
    roster = entity.get("roster", [])
    selected = []
    for member in members:
        item = next((r for r in roster if member in (r["id"], r["name"])), None)
        if item is None:
            return False, f"队员「{member}」不在名册中。"
        selected.append(item)
    if len(selected) != 5 or len({m["id"] for m in selected}) != 5:
        return False, "首发阵容需要五位不同队员。"
    entity["lineup"] = [m["id"] for m in selected]
    return True, "首发阵容已确认：" + "、".join(m["name"] for m in selected) + "。"


def team_match(state: dict, identity: str = "") -> tuple[bool, str]:
    from . import career, skills
    entity = find(state, identity, "team")
    if not entity or len(entity.get("lineup", [])) != 5:
        return False, "需要一支有五人首发阵容的战队。"
    if entity.get("equity", {}).get("player", 0) <= 50:
        return False, "持股未超过50%，不能单方面安排战队参赛。"
    day = int(state.get("time", {}).get("day", 1))
    if entity.get("last_match_day") == day:
        return False, "战队今天已经完成比赛，下一场至少间隔一个游戏日。"
    if not _pay(state, 40):
        return False, "报名与出行需要40华夏币。"
    lineup = [r for r in entity["roster"] if r["id"] in entity["lineup"]]
    strength = sum(r["ability"] for r in lineup) / 5 + skills.level(state, "sense") * 2
    rival = 48 + (entity["matches"] % 4) * 4
    won = strength >= rival
    entity["last_match_day"] = day
    entity["matches"] += 1
    entity["wins"] += int(won)
    prize = 100 if won else 20
    entity["cash"] += prize
    entity["fans"] += 30 if won else 5
    if won and entity["wins"] % 3 == 0:
        entity["trophies"] += 1
    career.add_fame(state, "电竞", 5 if won else 1)
    _record(entity, day, "赛事奖金" if won else "参赛补助", prize)
    return True, (f"「{entity['name']}」{'取胜' if won else '落败'}：阵容强度{strength:.0f}，对手{rival}；"
                  f"{prize}华夏币进入战队账户，粉丝{entity['fans']}，冠军{entity['trophies']}次。")


def hire(state: dict, domain: str, name: str = "", role: str = "成员") -> dict | None:
    entity = next((e for e in reversed(ensure(state)) if e.get("domain") == domain
                   and e["kind"] in ("company", "team") and e.get("equity", {}).get("player", 0) > 50), None)
    if entity is None:
        return None
    index = len(entity.get("employees", [])) + 1
    employee = {"id": f"{entity['id']}_staff_{index}", "name": name or f"{domain}团队成员{index}",
                "role": role, "ability": 40, "weekly_salary": 15, "status": "employed"}
    entity.setdefault("employees", []).append(employee)
    return employee


def settle_day(state: dict, day: int) -> list[str]:
    """逐实体补足整周现金流；已结算节点不会再次支付。"""
    notices = []
    from . import career
    c = career.ensure_career(state)
    for entity in ensure(state):
        if entity["kind"] == "work":
            continue
        cursor = int(entity.get("last_cashflow_day", entity.get("created_day", day)))
        while cursor + 7 <= day:
            cursor += 7
            entity["last_cashflow_day"] = cursor
            if entity.get("status") != "operating":
                continue
            if entity["kind"] == "contract":
                if cursor > entity.get("end_day", cursor):
                    entity["status"] = "expired"
                    continue
                payout = max(0, int(entity.get("weekly_payout", 0)))
                _receive(state, payout)
                _record(entity, cursor, "合约履约收入", payout)
                notices.append(f"【系统】{entity['name']}第{cursor}日履约收入 +{payout}华夏币。")
                continue
            pos = c["positions"].get(entity.get("domain"), {})
            ops = pos.get("ops", {})
            if entity["kind"] == "company":
                price = int(entity.get("price", 20))
                demand = int(entity.get("demand", 60))
                quality = int(ops.get("quality", entity.get("quality", 1)))
                marketing = int(ops.get("marketing", entity.get("marketing", 0)))
                competition = int(entity.get("competition", 30))
                customers = max(0, round((demand + marketing*10 + quality*6 - competition)
                                        * (20/max(5, price))**1.4))
                revenue = customers * price // 5
                cost = customers * 2 + 10 + int(entity.get("manager_salary", 0))
                entity["customers"] = customers
                entity["competition"] = clamp(competition + (2 if customers > 35 else -1), 10, 80)
                entity["demand"] = clamp(demand + (quality - 2) - max(0, price-40)//20, 10, 120)
            else:
                revenue = int(entity.get("fans", 0)) // 3 + int(entity.get("sponsorship", 0))
                cost = 20 + int(entity.get("manager_salary", 0))
            # 员工薪酬从事业周结算统一扣付；此处只计算实体运营成本。
            profit = revenue - cost
            entity["cash"] += profit
            entity["weekly_revenue"], entity["profit"] = revenue, profit
            if entity["cash"] < 0:
                entity["cash"] = 0
                entity["status"] = "suspended"
                notices.append(f"【系统】{entity['name']}现金耗尽，已暂停经营；可注资恢复。")
            else:
                # 利润的一半留作运营储备，另一半按持股分红，不能超过企业现金。
                dividend = min(entity["cash"], max(0, profit//2) * entity["equity"]["player"] // 100)
                entity["cash"] -= dividend
                _receive(state, dividend)
                notices.append(f"【系统】{entity['name']}第{cursor}日：营收{revenue}、成本{cost}、利润{profit}，个人分红{dividend}华夏币。")
                entity["valuation"] = max(20, entity["valuation"] + profit*2)
            _record(entity, cursor, "一周经营利润", profit)
            sync_asset(state, entity)
    return notices


def view(state: dict) -> list[dict]:
    from copy import deepcopy
    return deepcopy(ensure(state))
