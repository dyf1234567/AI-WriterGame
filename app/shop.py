"""系统商城、穿搭、手作工坊与物品使用。"""
import random

from . import storage
from .engine import _add_realm_progress, _apply_items, _breakthrough, _remove_items
from .models import (
    CURRENCY, EQUIPMENT_BONUS, EQUIP_SLOTS, LOTTERY_TICKET, REALMS, clamp, now_iso,
)

SELL_RATIO = 0.5  # 卖出回收比例

# use 效果：{"progress": N} 加等级进度；{"stat": {"体魄": 1}} 永久加属性
# cat 为前端分类筛选标签
SHOP_CATALOG = [
    # ---- 修炼成长（等级进度） ----
    {"name": "专注咖啡", "desc": "自习神器，喝完专注拉满：等级进度 +5", "price": 20, "type": "consumable", "cat": "修炼", "use": {"progress": 5}},
    {"name": "提神能量饮", "desc": "熬夜救星，精神为之一振：等级进度 +6", "price": 30, "type": "consumable", "cat": "修炼", "use": {"progress": 6}},
    {"name": "一对一辅导课时", "desc": "学长学姐手把手带飞：等级进度 +10", "price": 50, "type": "consumable", "cat": "修炼", "use": {"progress": 10}},
    {"name": "名师精品网课", "desc": "名师亲授，融会贯通：等级进度 +12", "price": 80, "type": "consumable", "cat": "修炼", "use": {"progress": 12}},
    {"name": "冲刺计划表", "desc": "考前/赛前的珍品冲刺方案：等级进度 +20", "price": 150, "type": "consumable", "cat": "修炼", "use": {"progress": 20}},
    {"name": "便携医药包", "desc": "创可贴纱布一应俱全，磕磕碰碰的底气", "price": 15, "type": "consumable", "cat": "修炼"},
    {"name": "感冒冲剂", "desc": "淋雨夜跑之后的及时雨", "price": 12, "type": "consumable", "cat": "修炼"},
    # ---- 属性课程（永久属性） ----
    {"name": "健身月卡", "desc": "一个月的系统训练，体魄 +1", "price": 60, "type": "consumable", "cat": "属性", "use": {"stat": {"体魄": 1}}},
    {"name": "精读书单", "desc": "啃完这份书单，头脑 +1", "price": 60, "type": "consumable", "cat": "属性", "use": {"stat": {"头脑": 1}}},
    {"name": "沟通表达课", "desc": "会说话是门手艺，情商 +1", "price": 90, "type": "consumable", "cat": "属性", "use": {"stat": {"情商": 1}}},
    {"name": "形象改造套餐", "desc": "发型穿搭一步到位，魅力 +1", "price": 60, "type": "consumable", "cat": "属性", "use": {"stat": {"魅力": 1}}},
    # ---- 约会与心意 ----
    {"name": "手写贺卡", "desc": "一笔一划写下的话，比千言万语都重", "price": 25, "type": "tool", "cat": "约会"},
    {"name": "电影票", "desc": "两张连座——第二张，要送给谁？", "price": 40, "type": "tool", "cat": "约会"},
    {"name": "游乐园双日票", "desc": "摩天轮的夜景与全城告白率最高的地方", "price": 80, "type": "tool", "cat": "约会"},
    {"name": "惊喜盲盒", "desc": "系统出品的未知惊喜，拆开才知道", "price": 100, "type": "tool", "cat": "约会"},
    # ---- 穿搭（可装备，加属性） ----
    {"name": "运动夹克", "desc": "清爽利落的运动系穿搭（上装·体魄+2）", "price": 120, "type": "equipment", "cat": "穿搭",
     "equip": EQUIPMENT_BONUS["运动夹克"]},
    {"name": "修身西装", "desc": "重要场合的一击必杀（上装·魅力+4）", "price": 400, "type": "equipment", "cat": "穿搭",
     "equip": EQUIPMENT_BONUS["修身西装"]},
    {"name": "轻便跑鞋", "desc": "脚踏实地，步履生风（鞋履·体魄+3）", "price": 180, "type": "equipment", "cat": "穿搭",
     "equip": EQUIPMENT_BONUS["轻便跑鞋"]},
    {"name": "智能腕表", "desc": "低调有质感，日程尽在掌握（配饰·头脑+3）", "price": 200, "type": "equipment", "cat": "穿搭",
     "equip": EQUIPMENT_BONUS["智能腕表"]},
    {"name": "城市单车", "desc": "穿行老街与海风的第一台座驾（座驾·体魄+1 魅力+1）", "price": 160, "type": "equipment", "cat": "穿搭",
     "equip": EQUIPMENT_BONUS["城市单车"]},
    # ---- 特殊商品（系统特供，剧情中使用） ----
    {"name": "心动雷达", "desc": "系统出品的缘分探测器：剧情中使用，会提示附近与你有缘的人", "price": 120, "type": "tool", "cat": "特殊"},
    {"name": "好运徽章", "desc": "系统认证的幸运符，据说能让今天的小概率好事发生", "price": 80, "type": "tool", "cat": "特殊"},
    {"name": "时光胶卷", "desc": "把与某人共度的一段时光封存成胶卷，随时重温", "price": 150, "type": "tool", "cat": "特殊"},
    {"name": "神秘钥匙", "desc": "来历不明的钥匙，系统标注：等一个注定的人来用（伏笔收藏品）", "price": 300, "type": "tool", "cat": "特殊"},
    # ---- 手作材料（可卖出换金币） ----
    {"name": "手冲咖啡豆", "desc": "香气饱满的咖啡豆，咖啡爱好者的心头好", "price": 30, "type": "material", "cat": "材料"},
    {"name": "烘焙材料包", "desc": "面粉黄油模具一应俱全的烘焙套装", "price": 25, "type": "material", "cat": "材料"},
    {"name": "永生花材", "desc": "不会凋谢的花材，手作礼物的灵魂", "price": 35, "type": "material", "cat": "材料"},
    # ---- 手作礼物（工坊成品，可送出/可卖出） ----
    {"name": "永生花束", "desc": "亲手扎的永生花束，不会凋谢的心意", "price": 40, "type": "tool", "cat": "手作"},
    {"name": "手冲咖啡礼盒", "desc": "自己烘的自己冲，装进亲手画的包装", "price": 45, "type": "tool", "cat": "手作"},
    {"name": "烘焙曲奇礼盒", "desc": "烤得恰到好处的曲奇，甜而不腻", "price": 60, "type": "tool", "cat": "手作"},
    {"name": "定制手绳", "desc": "一针一线编的手绳，独一无二的贴身之物", "price": 70, "type": "tool", "cat": "手作"},
    {"name": "星空投影灯", "desc": "把整片星空搬进房间的大制作", "price": 150, "type": "tool", "cat": "手作"},
]

CATALOG_BY_NAME = {g["name"]: g for g in SHOP_CATALOG}
SHOP_CATEGORIES = ["全部", "修炼", "属性", "约会", "穿搭", "特殊", "材料", "手作"]

# ---- 系统抽奖：四档品质 + 新手奖池 ----
LOTTERY_QUALITIES = [("普通", 70), ("稀有", 24), ("史诗", 5), ("传说", 1)]

# 新手奖池：开局赠送的抽奖次数专用。count 缺省为 1。
NEWBIE_POOL = {
    "普通": [
        {"name": "系统金币", "desc": "系统商城通用货币", "count": 8},
        {"name": "专注咖啡", "desc": "自习神器：等级进度+5"},
        {"name": "感冒冲剂", "desc": "淋雨夜跑之后的及时雨"},
        {"name": "手冲咖啡豆", "desc": "香气饱满的咖啡豆，手作礼物的原料"},
        {"name": "烘焙材料包", "desc": "面粉黄油模具一应俱全的烘焙套装"},
        {"name": "永生花材", "desc": "不会凋谢的花材，手作礼物的灵魂"},
        {"name": "便利店饭团", "desc": "系统出品的加餐口粮，深夜自习的底气", "count": 3},
    ],
    "稀有": [
        {"name": "一对一辅导课时", "desc": "等级进度+10"},
        {"name": "名师精品网课", "desc": "等级进度+12"},
        {"name": "精读书单", "desc": "啃完这份书单，头脑永久+1"},
        {"name": "电影票", "desc": "两张连座——第二张，要送给谁？"},
        {"name": "运动夹克", "desc": "清爽利落的运动系穿搭，体魄+2（可装备）"},
        {"name": "自习室月卡", "desc": "靠窗的固定座位一个月，安静与咖啡香兼得"},
    ],
    "史诗": [
        {"name": "修身西装", "desc": "重要场合的一击必杀，魅力+4（可装备）"},
        {"name": "智能腕表", "desc": "低调有质感，头脑+3（可装备）"},
        {"name": "冲刺计划表", "desc": "考前/赛前的珍品冲刺方案", "count": 2},
        {"name": "大师吉他课（进阶）", "desc": "进阶音乐课程，指弹与编曲的门槛一次跨过"},
        {"name": "精品摄影套装（高阶）", "desc": "高阶摄影套装，机身镜头与后期课打包带走"},
    ],
    "传说": [
        {"name": "传奇钢琴大师课（传承）", "desc": "传说级的大师亲授名额，从基本功到舞台表现完整传承"},
        {"name": "限量款行李箱", "desc": "说走就走的底气，装得下说走就走的全部行装"},
        {"name": "系统积分×50", "desc": "系统特殊奖励，用途待系统升级后揭晓（收藏品）"},
    ],
}

# ---- 手作工坊配方：need 为 {材料: 数量} ----
RECIPES = [
    {"name": "永生花束", "need": {"永生花材": 1}, "desc": "入门手作，一束不凋谢的心意"},
    {"name": "手冲咖啡礼盒", "need": {"手冲咖啡豆": 1, "系统金币": 5}, "desc": "以金币购齐包装，亲手烘亲自冲"},
    {"name": "烘焙曲奇礼盒", "need": {"手冲咖啡豆": 2, "永生花材": 1}, "desc": "咖啡香与花香同盒，甜而不腻"},
    {"name": "定制手绳", "need": {"永生花材": 2, "烘焙材料包": 1}, "desc": "材料包里的彩线正好编绳，独一无二"},
    {"name": "星空投影灯", "need": {"手冲咖啡豆": 3, "永生花材": 3}, "desc": "大耗材料的大制作，把星空搬进房间"},
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
        return {"ok": False, "msg": f"金币不足（需要 {goods['price']}，持有 {currency_count(state)}）。"}
    _apply_items(state, [{"name": goods["name"], "desc": goods["desc"]}])
    storage.save(state)
    return {"ok": True, "msg": f"购得『{goods['name']}』（花费 {goods['price']} 金币）。"}


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
        state["player"]["items"].append({"name": CURRENCY, "desc": "系统商城通用货币", "count": refund})
    storage.save(state)
    return {"ok": True, "msg": f"卖出『{name}』，回收 {refund} 金币。"}


def draw_lottery(state: dict) -> dict:
    """消耗一张抽奖券，按品质权重从新手奖池抽取并入账。"""
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


def lottery_view(state: dict) -> dict:
    """抽奖面板数据：余券、品质档、奖池概览与最近抽取记录。"""
    tickets = sum(i.get("count", 0) for i in state["player"]["items"] if i["name"] == LOTTERY_TICKET)
    lot = state["player"].get("lottery") or {}
    pools = {q: [{"name": p["name"], "count": p.get("count", 1)} for p in items]
             for q, items in NEWBIE_POOL.items()}
    return {"tickets": tickets, "qualities": [q for q, _ in LOTTERY_QUALITIES],
            "pool": pools, "history": list((lot.get("history") or [])[-12:])[::-1],
            "total_drawn": int(lot.get("total_drawn", 0))}


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
        msgs.append(f"等级进度 +{use['progress']}")
        if state["player"]["realm_progress"] >= 100:
            if _breakthrough(state):
                msgs.append(f"触发提升——当前等级：{REALMS[state['player']['realm']]}！")
    if "stat" in use:
        for key, delta in use["stat"].items():
            stats = state["player"]["stats"]
            stats[key] = clamp(stats.get(key, 0) + delta, 0, 99)
            msgs.append(f"{key} +{delta}")
    storage.save(state)
    return {"ok": True, "msg": f"使用『{name}』：{'，'.join(msgs)}。"}


# ---------- 穿搭装备 ----------

def _remove_one(state: dict, name: str) -> bool:
    return _remove_items(state, name, 1) > 0


def equip(state: dict, name: str) -> dict:
    bonus = EQUIPMENT_BONUS.get(name)
    if bonus is None:
        return {"ok": False, "msg": "这件物品无法装备。"}
    if not any(i["name"] == name for i in state["player"]["items"]):
        return {"ok": False, "msg": "背包里没有这件穿搭。"}
    slot = bonus["slot"]
    equipped = state["player"].setdefault("equipped", {s: None for s in EQUIP_SLOTS})
    old = equipped.get(slot)
    if old:
        _apply_items(state, [{"name": old, "desc": CATALOG_BY_NAME.get(old, {}).get("desc", "")}])
    _remove_one(state, name)
    equipped[slot] = name
    stats = "、".join(f"{k}+{v}" for k, v in bonus["stats"].items())
    storage.save(state)
    msg = f"换上『{name}』至【{slot}】：{stats}。"
    if old:
        msg = f"换下『{old}』退回背包。" + msg
    return {"ok": True, "msg": msg}


def unequip(state: dict, slot: str) -> dict:
    equipped = state["player"].get("equipped") or {}
    name = equipped.get(slot)
    if not name:
        return {"ok": False, "msg": f"【{slot}】槽位没有穿搭。"}
    equipped[slot] = None
    _apply_items(state, [{"name": name, "desc": CATALOG_BY_NAME.get(name, {}).get("desc", "")}])
    storage.save(state)
    return {"ok": True, "msg": f"换下『{name}』，已放回背包。"}


# ---------- 手作工坊 ----------

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
        return {"ok": False, "msg": "没有这份手作配方。"}
    for mat, cnt in recipe["need"].items():
        if _bag_count(state, mat) < cnt:
            return {"ok": False, "msg": f"材料不足：{mat} 需要 {cnt}，持有 {_bag_count(state, mat)}。"}
    for mat, cnt in recipe["need"].items():
        for _ in range(cnt):
            _remove_one(state, mat)
    goods = CATALOG_BY_NAME[name]
    _apply_items(state, [{"name": name, "desc": goods["desc"]}])
    storage.save(state)
    return {"ok": True, "msg": f"大功告成！做成『{name}』x1（心意满满）。"}
