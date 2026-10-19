"""系统商城、穿搭、送礼与物品使用。"""
import random

from . import storage
from .engine import (_add_realm_progress, _apply_items, _breakthrough, _remove_items,
                     add_power_progress, awaken_power, npc_remember, sync_achievements)
from .models import (
    CURRENCY, EQUIPMENT_BONUS, EQUIP_SLOTS, GIFT_CATEGORIES, LOTTERY_TICKET, REALMS,
    affinity_stage, clamp, find_npc, game_today, now_iso,
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
    {"name": "错题精析手册", "desc": "把踩过的坑变成台阶（学业线）：等级进度 +8", "price": 60, "type": "consumable", "cat": "修炼", "use": {"progress": 8}},
    {"name": "考研真题精讲", "desc": "真题刷三遍，考场如回家（学业线）：等级进度 +15", "price": 120, "type": "consumable", "cat": "修炼", "use": {"progress": 15}},
    {"name": "运动蛋白粉", "desc": "练后半小时的黄金补给（运动线）：等级进度 +6", "price": 40, "type": "consumable", "cat": "修炼", "use": {"progress": 6}},
    {"name": "体测冲刺训练营", "desc": "两周集训，成绩单焕然一新（运动线）：等级进度 +12", "price": 95, "type": "consumable", "cat": "修炼", "use": {"progress": 12}},
    {"name": "吉他进阶单曲课", "desc": "一首拿得出手的完整曲目（音乐线）：等级进度 +10", "price": 80, "type": "consumable", "cat": "修炼", "use": {"progress": 10}},
    {"name": "深夜食堂食谱", "desc": "一个人也要好好吃饭（厨艺线）：等级进度 +5", "price": 30, "type": "consumable", "cat": "修炼", "use": {"progress": 5}},
    {"name": "街头摄影实战课", "desc": "扫街构图与光影的临门一脚（摄影线）：等级进度 +8", "price": 60, "type": "consumable", "cat": "修炼", "use": {"progress": 8}},
    {"name": "引气散", "desc": "修行入门丹散，吐纳之间灵气入体：修为 +10（需已觉醒）", "price": 30, "type": "consumable", "cat": "修炼", "use": {"power": 10}},
    {"name": "聚灵阵盘", "desc": "一方小阵，打坐事半功倍：修为 +25（需已觉醒）", "price": 90, "type": "consumable", "cat": "修炼", "use": {"power": 25}},
    {"name": "洗髓丹", "desc": "洗筋伐髓的珍品丹药：修为 +15 且体魄永久 +1（需已觉醒）", "price": 220, "type": "consumable", "cat": "修炼", "use": {"power": 15, "stat": {"体魄": 1}}},
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
    {"name": "系统抽奖券", "desc": "多一次转动命运转盘的机会（抽奖页使用）", "price": 60, "type": "tool", "cat": "特殊"},
    # ---- 特殊商品（系统特供，剧情中使用） ----
    {"name": "心动雷达", "desc": "系统出品的缘分探测器：剧情中使用，会提示附近与你有缘的人", "price": 120, "type": "tool", "cat": "特殊"},
    {"name": "好运徽章", "desc": "系统认证的幸运符，据说能让今天的小概率好事发生", "price": 80, "type": "tool", "cat": "特殊"},
    {"name": "时光胶卷", "desc": "把与某人共度的一段时光封存成胶卷，随时重温", "price": 150, "type": "tool", "cat": "特殊"},
    {"name": "神秘钥匙", "desc": "来历不明的钥匙，系统标注：等一个注定的人来用（伏笔收藏品）", "price": 300, "type": "tool", "cat": "特殊"},
    {"name": "觉醒·灵种", "desc": "系统深处的封存之物——一粒微光流转的种子，服下即点亮灵根，踏入修行之门（一次性）", "price": 500, "type": "consumable", "cat": "特殊", "use": {"awaken": 1}},
    # ---- 情趣（成年人的浪漫与私密：前半氛围仪式感，后半直白成人向） ----
    {"name": "心形暖手宝", "desc": "冬天递过去的温度，比说什么都管用", "price": 35, "type": "tool", "cat": "情趣"},
    {"name": "香薰蜡烛", "desc": "灯光调暗一档，气氛就近一步——约会收尾的仪式感", "price": 45, "type": "tool", "cat": "情趣"},
    {"name": "玫瑰花瓣浴盐", "desc": "一整晚放松氛围的仪式感担当", "price": 60, "type": "tool", "cat": "情趣"},
    {"name": "按摩精油", "desc": "从肩颈放松开始的温柔借口", "price": 88, "type": "tool", "cat": "情趣"},
    {"name": "真丝眼罩", "desc": "「猜猜我是谁」——惊喜与好梦两相宜", "price": 120, "type": "tool", "cat": "情趣"},
    {"name": "情侣对香", "desc": "一人一瓶的木质调，靠近时才闻得出是同一支", "price": 150, "type": "tool", "cat": "情趣"},
    {"name": "情趣骰子", "desc": "掷出什么就做什么——把今晚的主动权交给运气", "price": 90, "type": "tool", "cat": "情趣"},
    {"name": "冰火润滑剂", "desc": "一热一凉的两支装，剩下的交给想象力和默契", "price": 150, "type": "tool", "cat": "情趣"},
    {"name": "情侣手铐", "desc": "毛绒外皮，锁得住手腕锁不住心跳；安全钥匙各执一把", "price": 180, "type": "tool", "cat": "情趣"},
    {"name": "遥控跳蛋", "desc": "遥控器在谁手里，今晚的心跳频率就归谁管——出门前那顿晚餐会很难熬", "price": 260, "type": "tool", "cat": "情趣"},
    {"name": "情趣内衣", "desc": "盒上系着卡片：「只给最信任的人看的那一面」", "price": 300, "type": "tool", "cat": "情趣"},
    {"name": "深层按摩棒", "desc": "说明书写着「深层放松，建议两人使用」——读的人都会心一笑", "price": 380, "type": "tool", "cat": "情趣"},
]

CATALOG_BY_NAME = {g["name"]: g for g in SHOP_CATALOG}
SHOP_CATEGORIES = ["全部", "修炼", "属性", "约会", "情趣", "穿搭", "特殊"]

# ---- 系统抽奖：四档品质 + 新手奖池 ----
LOTTERY_QUALITIES = [("普通", 70), ("稀有", 24), ("史诗", 5), ("传说", 1)]

# 新手奖池：开局赠送的抽奖次数专用。count 缺省为 1。
NEWBIE_POOL = {
    "普通": [
        {"name": "系统金币", "desc": "系统商城通用货币", "count": 8},
        {"name": "专注咖啡", "desc": "自习神器：等级进度+5"},
        {"name": "感冒冲剂", "desc": "淋雨夜跑之后的及时雨"},
        {"name": "心形暖手宝", "desc": "冬天递过去的温度，比说什么都管用"},
        {"name": "运动蛋白粉", "desc": "练后半小时的黄金补给：等级进度+6"},
        {"name": "便利店饭团", "desc": "系统出品的加餐口粮，深夜自习的底气", "count": 3},
    ],
    "稀有": [
        {"name": "一对一辅导课时", "desc": "等级进度+10"},
        {"name": "名师精品网课", "desc": "等级进度+12"},
        {"name": "精读书单", "desc": "啃完这份书单，头脑永久+1"},
        {"name": "电影票", "desc": "两张连座——第二张，要送给谁？"},
        {"name": "香薰蜡烛", "desc": "灯光调暗一档，气氛就近一步"},
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
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
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
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
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
    sync_achievements(state)
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
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


# ---------- 送礼（恋爱核心循环·阶段A） ----------

GIFT_DAILY_CAP = 1   # 同一人每天最多 1 份（星露谷规则）
GIFT_WEEKLY_CAP = 2  # 同一人每周最多 2 份
EXPLICIT_GIFT_MIN_AFFINITY = 70  # 直白成人向礼物（情趣·≥250金币）需「亲近」起步


def _gift_base_value(goods: dict) -> int:
    """按价格档给基础好感：便宜在心意，昂贵在分量。"""
    price = goods["price"]
    if price < 30:
        return 2
    if price < 80:
        return 4
    if price < 200:
        return 6
    return 8


def _week_key() -> str:
    """周限额键：与 game_today 同用固定 UTC+8，避免日键与周键两个时区各自翻篇。"""
    from datetime import datetime, timezone, timedelta
    iso = datetime.now(timezone(timedelta(hours=8))).date().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def give_gift(state: dict, npc_name: str, item_name: str) -> dict:
    """赠送礼物：扣物品、按价值与偏好结算好感、跨阶段公告、缘由入 NPC 记忆。

    限额与星露谷物语一致：同一人每天 1 份、每周 2 份——送礼是心意，不是流水线。
    """
    npc = find_npc(state, npc_name)
    if npc is None:
        return {"ok": False, "msg": "名册上没有这个人。"}
    if not npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0):
        return {"ok": False, "msg": "你还不认识这个人，先在剧情里结识吧。"}
    goods = CATALOG_BY_NAME.get(item_name)
    if goods is None or goods.get("cat") not in GIFT_CATEGORIES:
        return {"ok": False, "msg": "这件物品不适合作为礼物赠送。"}
    if (goods.get("cat") == "情趣" and goods["price"] >= 250
            and npc["affinity"] < EXPLICIT_GIFT_MIN_AFFINITY):
        return {"ok": False, "msg": f"和{npc['name']}还没到那一步——这样的礼物火候不到只会吓退彼此（需「亲近」以上）。"}
    if not any(i["name"] == item_name for i in state["player"]["items"]):
        return {"ok": False, "msg": "背包里没有这件物品。"}

    log = state.setdefault("gift_log", {"daily": {}, "weekly": {}})
    today, week = game_today(), _week_key()
    daily = log.setdefault("daily", {}).setdefault(today, {})
    weekly = log.setdefault("weekly", {}).setdefault(week, {})
    # 生日：好感×8 且不占每日/每周限额（星露谷规则）
    def _md(date_str: str) -> str:
        parts = date_str.split("-")
        return f"{int(parts[-2])}-{int(parts[-1])}" if len(parts) >= 3 else date_str
    birthday_today = bool(npc.get("birthday")) and _md(npc["birthday"]) == _md(today)
    # 生日规则：当日仍限一份（防刷），但不占每周限额（星露谷精神）；
    # 台账永远照写——豁免的是限额，不是记录，否则成就判定会被跳过。
    bd_week = log.setdefault("bd_week", {}).setdefault(week, {})
    weekly_eff = weekly.get(npc["name"], 0) - bd_week.get(npc["name"], 0)
    if daily.get(npc["name"], 0) >= GIFT_DAILY_CAP:
        return {"ok": False, "msg": f"今天已经给{npc['name']}送过礼物了，心意太频会变负担——明天再说。"}
    if weekly_eff >= GIFT_WEEKLY_CAP:
        return {"ok": False, "msg": f"这周给{npc['name']}的礼物已经够多了（每周限 {GIFT_WEEKLY_CAP} 份）。"}

    base = _gift_base_value(goods)
    liked = bool(npc.get("likes")) and npc["likes"] == goods["cat"]
    delta = round(base * 1.5) if liked else base
    if birthday_today:
        delta *= 8
    before_stage = affinity_stage(npc["affinity"])
    npc["affinity"] = clamp(npc["affinity"] + delta, 0, 100)
    after_stage = affinity_stage(npc["affinity"])
    npc["last_seen_turn"] = state["turn"]

    note = f"收到礼物『{item_name}』，好感+{delta}"
    if liked:
        note += f"（投其所好：偏爱{npc['likes']}类礼物）"
    npc_remember(npc, state["turn"], note, prefix="送礼：")

    _remove_items(state, item_name, 1)
    daily[npc["name"]] = daily.get(npc["name"], 0) + 1
    weekly[npc["name"]] = weekly.get(npc["name"], 0) + 1
    if birthday_today:
        bd_week[npc["name"]] = bd_week.get(npc["name"], 0) + 1
    ach = sync_achievements(state)
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照

    msg = f"把『{item_name}』送给了{npc['name']}：好感 +{delta}。"
    if birthday_today:
        msg = f"今天是{npc['name']}的生日！{msg}（生日心意 ×8，不占每周限额）"
    elif liked:
        msg += f"（TA偏爱{goods['cat']}类礼物，加成生效）"
    stage_up = after_stage != before_stage
    if stage_up:
        msg += f" 关系升温：{before_stage} → {after_stage}！"
    for a in ach:
        msg += " " + a
    return {"ok": True, "msg": msg, "delta": delta, "liked": liked,
            "stage_before": before_stage, "stage_after": after_stage}


def use_item(state: dict, name: str) -> dict:
    item = next((i for i in state["player"]["items"] if i["name"] == name), None)
    if item is None:
        return {"ok": False, "msg": "背包里没有这件物品。"}
    if name == LOTTERY_TICKET:
        return draw_lottery(state)
    goods = CATALOG_BY_NAME.get(name)
    if goods is None or goods.get("type") != "consumable" or not goods.get("use"):
        return {"ok": False, "msg": "这件物品暂时无法直接使用。"}
    use = goods["use"]
    # 修行丹药前置校验：未觉醒时灵气无从炼化，不消耗物品
    if "power" in use and not (state.get("power") or {}).get("awakened"):
        return {"ok": False, "msg": "尚未觉醒，灵气无从炼化——先在商城·特殊购入『觉醒·灵种』。"}
    item["count"] -= 1
    if item["count"] <= 0:
        state["player"]["items"].remove(item)

    msgs = []
    if "awaken" in use:
        msgs.append(awaken_power(state))
    if "progress" in use:
        _add_realm_progress(state, use["progress"])
        msgs.append(f"等级进度 +{use['progress']}")
        if state["player"]["realm_progress"] >= 100:
            if _breakthrough(state):
                msgs.append(f"触发提升——当前等级：{REALMS[state['player']['realm']]}！")
        # 已觉醒者：世俗修炼同样滋养灵根，修为同额入账
        if (state.get("power") or {}).get("awakened") and "power" not in use:
            msgs.extend(add_power_progress(state, use["progress"]))
    if "power" in use:
        power = state["power"]
        from .models import POWER_STAGES
        msgs.append(f"修为 +{use['power']}（{POWER_STAGES[power['stage']]} {power['progress']}/{100}）")
        msgs.extend(add_power_progress(state, use["power"]))
    if "stat" in use:
        for key, delta in use["stat"].items():
            stats = state["player"]["stats"]
            stats[key] = clamp(stats.get(key, 0) + delta, 0, 99)
            msgs.append(f"{key} +{delta}")
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
    return {"ok": True, "msg": f"使用『{name}』：{'，'.join(m for m in msgs if m)}。"}


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
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
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
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
    return {"ok": True, "msg": f"换下『{name}』，已放回背包。"}
