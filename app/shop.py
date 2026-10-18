"""系统商城、装备、炼丹与物品使用。"""
import random

from . import storage
from .engine import _add_realm_progress, _apply_items, _breakthrough, _remove_items
from .models import (
    CURRENCY, EQUIPMENT_BONUS, EQUIP_SLOTS, LOTTERY_TICKET, REALMS, clamp, now_iso,
)

SELL_RATIO = 0.5  # 卖出回收比例

# use 效果：{"progress": N} 加修为；{"stat": {"体魄": 1}} 永久加属性
SHOP_CATALOG = [
    # ---- 丹药（修为） ----
    {"name": "聚气丹", "desc": "服用后修为 +5", "price": 20, "type": "consumable", "use": {"progress": 5}},
    {"name": "引气符", "desc": "激发后灵气灌体，修为 +6", "price": 30, "type": "consumable", "use": {"progress": 6}},
    {"name": "凝元丹", "desc": "凝聚元力，修为 +10", "price": 50, "type": "consumable", "use": {"progress": 10}},
    {"name": "洗髓丹", "desc": "洗涤经脉，修为 +12", "price": 80, "type": "consumable", "use": {"progress": 12}},
    {"name": "筑基液", "desc": "冲击瓶颈的珍品，修为 +20", "price": 150, "type": "consumable", "use": {"progress": 20}},
    {"name": "疗伤丹", "desc": "疗伤续命，关键时刻的保命之物", "price": 15, "type": "consumable"},
    {"name": "解毒丹", "desc": "化解常见丹毒瘴毒", "price": 12, "type": "consumable"},
    # ---- 属性丹（永久） ----
    {"name": "力士散", "desc": "药力入骨，体魄 +1", "price": 60, "type": "consumable", "use": {"stat": {"体魄": 1}}},
    {"name": "凝神香", "desc": "静心凝神，神识 +1", "price": 60, "type": "consumable", "use": {"stat": {"神识": 1}}},
    {"name": "悟道茶", "desc": "一盏入喉，悟性 +1", "price": 90, "type": "consumable", "use": {"stat": {"悟性": 1}}},
    {"name": "风华露", "desc": "气韵天成，魅力 +1", "price": 60, "type": "consumable", "use": {"stat": {"魅力": 1}}},
    # ---- 符箓与杂项 ----
    {"name": "遮息符", "desc": "收敛气息，让修行者难以看穿你的底细", "price": 40, "type": "tool"},
    {"name": "护身符", "desc": "贴身佩戴，据说能抵挡一次致命打击", "price": 80, "type": "tool"},
    {"name": "传讯玉简", "desc": "可向熟人传讯的玉简，千里一线", "price": 25, "type": "tool"},
    {"name": "储物袋", "desc": "内藏一方小空间的锦袋，出门必备", "price": 100, "type": "tool"},
    # ---- 法器（可装备，加属性） ----
    {"name": "玄铁短剑", "desc": "凡铁百炼而成，锋利可靠（武器·体魄+2）", "price": 120, "type": "equipment",
     "equip": EQUIPMENT_BONUS["玄铁短剑"]},
    {"name": "青霜剑", "desc": "寒气逼人的下品法剑，剑修之选（武器·体魄+4）", "price": 400, "type": "equipment",
     "equip": EQUIPMENT_BONUS["青霜剑"]},
    {"name": "护心镜", "desc": "护住心脉的青铜古镜（防具·体魄+3）", "price": 180, "type": "equipment",
     "equip": EQUIPMENT_BONUS["护心镜"]},
    {"name": "避水珠", "desc": "蕴含水行灵韵的珠子，凝神静气（法宝·神识+3）", "price": 200, "type": "equipment",
     "equip": EQUIPMENT_BONUS["避水珠"]},
    {"name": "踏云靴", "desc": "步履生风，身法更胜一筹（足履·体魄+1 魅力+1）", "price": 160, "type": "equipment",
     "equip": EQUIPMENT_BONUS["踏云靴"]},
    # ---- 材料（可卖出换灵石） ----
    {"name": "千年灵芝", "desc": "药香扑鼻的灵芝，药铺与丹师都收", "price": 30, "type": "material"},
    {"name": "玄铁矿石", "desc": "沉甸甸的矿石，锻造师的最爱", "price": 25, "type": "material"},
    {"name": "一阶妖丹", "desc": "妖兽内丹，蕴含驳杂灵力", "price": 35, "type": "material"},
]

CATALOG_BY_NAME = {g["name"]: g for g in SHOP_CATALOG}

# ---- 系统抽奖（设定集 V1.2 · 五）：四档品质 + 新手奖池 ----
LOTTERY_QUALITIES = [("普通", 70), ("稀有", 24), ("史诗", 5), ("传说", 1)]

# 新手奖池：开局赠送的抽奖次数专用。count 缺省为 1。
NEWBIE_POOL = {
    "普通": [
        {"name": "下品灵石", "desc": "修仙界通用货币", "count": 8},
        {"name": "聚气丹", "desc": "服下后修为+5"},
        {"name": "疗伤丹", "desc": "药性温和的疗伤圣药"},
        {"name": "千年灵芝", "desc": "药香扑鼻的灵芝，丹道基础材料"},
        {"name": "玄铁矿石", "desc": "沉甸甸的矿石，锻造师的最爱"},
        {"name": "一阶妖丹", "desc": "妖兽内丹，蕴含驳杂灵力"},
        {"name": "干粮行囊", "desc": "系统出品的压缩口粮，荒野求生的底气", "count": 3},
    ],
    "稀有": [
        {"name": "凝元丹", "desc": "服下后修为+10"},
        {"name": "洗髓丹", "desc": "服下后修为+12"},
        {"name": "悟道茶", "desc": "饮后悟性永久+1"},
        {"name": "护身符", "desc": "危急时刻或能挡下一次致命伤"},
        {"name": "玄铁短剑", "desc": "锻造精良的短剑，体魄+2（可装备）"},
        {"name": "引灵诀（残）", "desc": "残缺的引灵法门，打坐时可多引一缕灵气"},
    ],
    "史诗": [
        {"name": "青霜剑", "desc": "寒气逼人的法器长剑，体魄+4（可装备）"},
        {"name": "避水珠", "desc": "温润水珠，神识+3（可装备）"},
        {"name": "筑基液", "desc": "大耗材料的进阶丹液", "count": 2},
        {"name": "玄元剑诀（中品）", "desc": "中品剑修功法，剑出如风，杀伐凌厉"},
        {"name": "百草丹方（上品）", "desc": "上品丹修传承，识药、配伍、控火之道尽在其中"},
    ],
    "传说": [
        {"name": "青元剑典（传承）", "desc": "传说中的剑修传承典籍，从炼气到金丹的完整剑道"},
        {"name": "小乾坤袋", "desc": "内藏一方丈空间的宝袋，可容纳十倍行囊"},
        {"name": "系统积分×50", "desc": "系统特殊奖励，用途待系统升级后揭晓（收藏品）"},
    ],
}

# ---- 炼丹配方：need 为 {材料: 数量} ----
RECIPES = [
    {"name": "疗伤丹", "need": {"千年灵芝": 1}, "desc": "入门丹方，药性温和"},
    {"name": "聚气丹", "need": {"千年灵芝": 1, "下品灵石": 5}, "desc": "以灵石为引，聚灵成丹"},
    {"name": "凝元丹", "need": {"千年灵芝": 2, "一阶妖丹": 1}, "desc": "丹毒与药力相搏，成丹凝而不散"},
    {"name": "洗髓丹", "need": {"一阶妖丹": 2, "玄铁矿石": 1}, "desc": "矿石镇毒，妖丹为炉"},
    {"name": "筑基液", "need": {"千年灵芝": 3, "一阶妖丹": 3}, "desc": "大耗材料的进阶丹液"},
]
RECIPES_BY_NAME = {r["name"]: r for r in RECIPES}


def currency_count(state: dict) -> int:
    for it in state["player"]["items"]:
        if it["name"] == CURRENCY:
            return it.get("count", 0)
    return 0


def _take_currency(state: dict, n: int) -> bool:
    for it in state["player"]["items"]:
        if it["name"] == CURRENCY:
            if it.get("count", 0) < n:
                return False
            it["count"] -= n
            if it["count"] <= 0:
                state["player"]["items"].remove(it)
            return True
    return n <= 0


def buy(state: dict, name: str) -> dict:
    goods = CATALOG_BY_NAME.get(name)
    if goods is None:
        return {"ok": False, "msg": "商城里没有这件商品。"}
    if not _take_currency(state, goods["price"]):
        return {"ok": False, "msg": f"灵石不足（需要 {goods['price']}，持有 {currency_count(state)}）。"}
    _apply_items(state, [{"name": goods["name"], "desc": goods["desc"]}])
    storage.save(state)
    return {"ok": True, "msg": f"购得『{goods['name']}』（花费 {goods['price']} 灵石）。"}


def sell(state: dict, name: str) -> dict:
    item = next((i for i in state["player"]["items"] if i["name"] == name), None)
    if item is None:
        return {"ok": False, "msg": "背包里没有这件物品。"}
    goods = CATALOG_BY_NAME.get(name)
    if goods is None:
        return {"ok": False, "msg": "这件物品没有行情，无法卖出。"}
    refund = max(1, int(goods["price"] * SELL_RATIO))
    item["count"] -= 1
    if item["count"] <= 0:
        state["player"]["items"].remove(item)
    for it in state["player"]["items"]:
        if it["name"] == CURRENCY:
            it["count"] += refund
            break
    else:
        state["player"]["items"].append({"name": CURRENCY, "desc": "修仙界通用货币", "count": refund})
    storage.save(state)
    return {"ok": True, "msg": f"卖出『{name}』，回收 {refund} 灵石。"}


def draw_lottery(state: dict) -> dict:
    """消耗一张抽奖券，按品质权重从新手奖池抽取并入账（设定集 V1.2 · 五）。"""
    item = next((i for i in state["player"]["items"] if i["name"] == LOTTERY_TICKET), None)
    if item is None or item.get("count", 0) < 1:
        return {"ok": False, "msg": "没有可用的抽奖券。"}
    item["count"] -= 1
    if item["count"] <= 0:
        state["player"]["items"].remove(item)

    names = [q for q, _ in LOTTERY_QUALITIES]
    weights = [w for _, w in LOTTERY_QUALITIES]
    quality = random.choices(names, weights=weights, k=1)[0]
    prize = dict(random.choice(NEWBIE_POOL[quality]))
    prize["count"] = max(1, int(prize.get("count", 1)))
    _apply_items(state, [prize])

    lot = state["player"].setdefault("lottery", {"total_drawn": 0, "history": []})
    lot["total_drawn"] = int(lot.get("total_drawn", 0)) + 1
    lot["history"] = (lot.get("history") or [])[-59:] + [{
        "no": lot["total_drawn"], "quality": quality,
        "name": prize["name"], "count": prize["count"], "ts": now_iso(),
    }]
    state["inbox"] = (state.get("inbox") or [])[-49:] + [{
        "ts": now_iso(), "type": "event", "world": state["player"]["world"],
        "title": f"抽奖 · 第{lot['total_drawn']}次",
        "text": f"【{quality}】{prize['name']}×{prize['count']} 已入账（新手奖池）。",
    }]
    storage.save(state)
    return {"ok": True, "quality": quality, "prize": prize,
            "msg": f"抽奖结果：【{quality}】{prize['name']}×{prize['count']} 已入账（新手奖池）。"}


def use_item(state: dict, name: str) -> dict:
    item = next((i for i in state["player"]["items"] if i["name"] == name), None)
    if item is None:
        return {"ok": False, "msg": "背包里没有这件物品。"}
    if name == LOTTERY_TICKET:
        return draw_lottery(state)
    goods = CATALOG_BY_NAME.get(name)
    if goods is None or goods.get("type") != "consumable" or not goods.get("use"):
        return {"ok": False, "msg": "这件物品暂时无法直接使用。"}
    item["count"] -= 1
    if item["count"] <= 0:
        state["player"]["items"].remove(item)

    use = goods["use"]
    msgs = []
    if "progress" in use:
        _add_realm_progress(state, use["progress"])
        msgs.append(f"修为 +{use['progress']}")
        if state["player"]["realm_progress"] >= 100:
            if _breakthrough(state):
                msgs.append(f"触发突破——当前境界：{REALMS[state['player']['realm']]}！")
    if "stat" in use:
        for key, delta in use["stat"].items():
            stats = state["player"]["stats"]
            stats[key] = clamp(stats.get(key, 0) + delta, 0, 99)
            msgs.append(f"{key} +{delta}")
    storage.save(state)
    return {"ok": True, "msg": f"使用『{name}』：{'，'.join(msgs)}。"}


# ---------- 装备 ----------

def _remove_one(state: dict, name: str) -> bool:
    return _remove_items(state, name, 1) > 0


def equip(state: dict, name: str) -> dict:
    bonus = EQUIPMENT_BONUS.get(name)
    if bonus is None:
        return {"ok": False, "msg": "这件物品无法装备。"}
    if not any(i["name"] == name for i in state["player"]["items"]):
        return {"ok": False, "msg": "背包里没有这件装备。"}
    slot = bonus["slot"]
    equipped = state["player"].setdefault("equipped", {s: None for s in EQUIP_SLOTS})
    old = equipped.get(slot)
    if old:
        _apply_items(state, [{"name": old, "desc": CATALOG_BY_NAME.get(old, {}).get("desc", "")}])
    _remove_one(state, name)
    equipped[slot] = name
    stats = "、".join(f"{k}+{v}" for k, v in bonus["stats"].items())
    storage.save(state)
    msg = f"装备『{name}』至【{slot}】：{stats}。"
    if old:
        msg = f"卸下『{old}』退回背包。" + msg
    return {"ok": True, "msg": msg}


def unequip(state: dict, slot: str) -> dict:
    equipped = state["player"].get("equipped") or {}
    name = equipped.get(slot)
    if not name:
        return {"ok": False, "msg": f"【{slot}】槽位没有装备。"}
    equipped[slot] = None
    _apply_items(state, [{"name": name, "desc": CATALOG_BY_NAME.get(name, {}).get("desc", "")}])
    storage.save(state)
    return {"ok": True, "msg": f"卸下『{name}』，已放回背包。"}


# ---------- 炼丹 ----------

def _bag_count(state: dict, name: str) -> int:
    return sum(it.get("count", 0) for it in state["player"]["items"] if it["name"] == name)


def alchemy_view(state: dict) -> dict:
    owned: dict = {}
    for it in state["player"]["items"]:
        owned[it["name"]] = owned.get(it["name"], 0) + it.get("count", 0)
    recipes = []
    for r in RECIPES:
        need = [{"name": k, "count": v, "have": owned.get(k, 0)} for k, v in r["need"].items()]
        ok = all(n["have"] >= n["count"] for n in need)
        recipes.append({"name": r["name"], "desc": r["desc"], "need": need, "ok": ok})
    return {"recipes": recipes}


def craft(state: dict, name: str) -> dict:
    recipe = RECIPES_BY_NAME.get(name)
    if recipe is None:
        return {"ok": False, "msg": "没有这份丹方。"}
    for mat, cnt in recipe["need"].items():
        if _bag_count(state, mat) < cnt:
            return {"ok": False, "msg": f"材料不足：{mat} 需要 {cnt}，持有 {_bag_count(state, mat)}。"}
    for mat, cnt in recipe["need"].items():
        for _ in range(cnt):
            _remove_one(state, mat)
    goods = CATALOG_BY_NAME[name]
    _apply_items(state, [{"name": name, "desc": goods["desc"]}])
    storage.save(state)
    return {"ok": True, "msg": f"丹成！炼得『{name}』x1（炉火纯青）。"}
