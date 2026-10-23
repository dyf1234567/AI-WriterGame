"""系统商城、穿搭、送礼与物品使用。"""
import random

from . import storage
from .engine import (_add_realm_progress, _apply_items, _remove_items,
                     add_power_progress, awaken_power,
                     npc_remember, settle_growth, sync_achievements)
from .config import DATA_DIR
from .models import (
    CASH, CURRENCY, EQUIPMENT_BONUS, EQUIP_SLOTS, GIFT_CATEGORIES, LOTTERY_TICKET,
    SYSTEM_ITEMS, clamp, find_npc, game_today, now_iso,
)

SHOP_CATALOG = [
    # ---- 系统特供（系统商城的本行：数据化道具，效果由引擎直接结算） ----
    {"name": "经验卡（小）", "desc": "系统特供的成长值注入卡，使用即结算：等级进度 +6", "price": 25,
     "type": "consumable", "cat": "系统", "use": {"progress": 6}},
    {"name": "经验卡（中）", "desc": "系统特供的成长值注入卡，使用即结算：等级进度 +15", "price": 60,
     "type": "consumable", "cat": "系统", "use": {"progress": 15}},
    {"name": "经验卡（大）", "desc": "系统特供的成长值注入卡，使用即结算：等级进度 +40", "price": 150,
     "type": "consumable", "cat": "系统", "use": {"progress": 40}},
    {"name": "双倍经验时段卡", "desc": "激活后进入双倍经验时段：接下来 3 次等级进度收益 ×2", "price": 120,
     "type": "consumable", "cat": "系统", "use": {"buff": {"exp_boost": 3}}},
    {"name": "强化胶囊·体魄", "desc": "系统出品的定向强化剂，服用即结算：体魄永久 +1", "price": 100,
     "type": "consumable", "cat": "系统", "use": {"stat": {"体魄": 1}}},
    {"name": "强化胶囊·头脑", "desc": "系统出品的定向强化剂，服用即结算：头脑永久 +1", "price": 100,
     "type": "consumable", "cat": "系统", "use": {"stat": {"头脑": 1}}},
    {"name": "强化胶囊·情商", "desc": "系统出品的定向强化剂，服用即结算：情商永久 +1", "price": 130,
     "type": "consumable", "cat": "系统", "use": {"stat": {"情商": 1}}},
    {"name": "强化胶囊·魅力", "desc": "系统出品的定向强化剂，服用即结算：魅力永久 +1", "price": 100,
     "type": "consumable", "cat": "系统", "use": {"stat": {"魅力": 1}}},
    {"name": "技能灌顶卡", "desc": "向主修技能（等级最高者）注入经验：+30 经验（背包内使用）", "price": 150,
     "type": "consumable", "cat": "系统", "use": {"skill_xp": 30}},
    {"name": "幸运药剂（小）", "desc": "下一次抽奖的品质保底提升至【稀有】，抽后失效", "price": 80,
     "type": "consumable", "cat": "系统", "use": {"luck": "稀有"}},
    {"name": "SSR保底券", "desc": "下一次抽奖的品质保底提升至【史诗】，抽后失效", "price": 240,
     "type": "consumable", "cat": "系统", "use": {"luck": "史诗"}},
    # ---- 修炼成长（等级进度） ----
    {"name": "专注咖啡", "desc": "自习神器，喝完专注拉满：等级进度 +5", "price": 20, "type": "consumable", "cat": "修炼", "use": {"progress": 5}},
    {"name": "提神能量饮", "desc": "熬夜救星，精神为之一振：等级进度 +8", "price": 30, "type": "consumable", "cat": "修炼", "use": {"progress": 8}},
    {"name": "一对一辅导课时", "desc": "学长学姐手把手带飞：等级进度 +14", "price": 50, "type": "consumable", "cat": "修炼", "use": {"progress": 14}},
    {"name": "名师精品网课", "desc": "名师亲授，融会贯通：等级进度 +24", "price": 80, "type": "consumable", "cat": "修炼", "use": {"progress": 24}},
    {"name": "冲刺计划表", "desc": "考前/赛前的冲刺方案：等级进度 +45", "price": 150, "type": "consumable", "cat": "修炼", "use": {"progress": 45}},
    {"name": "便携医药包", "desc": "创可贴纱布一应俱全，磕磕碰碰的底气", "price": 15, "type": "consumable", "cat": "修炼"},
    {"name": "感冒冲剂", "desc": "淋雨夜跑之后的及时雨", "price": 12, "type": "consumable", "cat": "修炼"},
    {"name": "错题精析手册", "desc": "把踩过的坑变成台阶（学业线）：等级进度 +18，同路线额外 +20%", "price": 60, "type": "consumable", "cat": "修炼", "route": "学业", "use": {"progress": 18}},
    {"name": "考研真题精讲", "desc": "真题刷三遍（学业线）：等级进度 +36，同路线额外 +20%", "price": 120, "type": "consumable", "cat": "修炼", "route": "学业", "use": {"progress": 36}},
    {"name": "运动蛋白粉", "desc": "练后半小时的黄金补给（运动线）：等级进度 +12，同路线额外 +20%", "price": 40, "type": "consumable", "cat": "修炼", "route": "运动", "use": {"progress": 12}},
    {"name": "体测冲刺训练营", "desc": "系统集训（运动线）：等级进度 +30，同路线额外 +20%", "price": 95, "type": "consumable", "cat": "修炼", "route": "运动", "use": {"progress": 30}},
    {"name": "吉他进阶单曲课", "desc": "一首拿得出手的完整曲目（音乐线）：等级进度 +25，同路线额外 +20%", "price": 80, "type": "consumable", "cat": "修炼", "route": "音乐", "use": {"progress": 25}},
    {"name": "商业策划实战课", "desc": "练习预算与项目计划（创业线）：等级进度 +24，同路线额外 +20%", "price": 80, "type": "consumable", "cat": "修炼", "route": "创业", "use": {"progress": 24}},
    {"name": "深夜食堂食谱", "desc": "一个人也要好好吃饭（厨艺线）：等级进度 +9，同路线额外 +20%", "price": 30, "type": "consumable", "cat": "修炼", "route": "厨艺", "use": {"progress": 9}},
    {"name": "街头摄影实战课", "desc": "扫街构图与光影（摄影线）：等级进度 +18，同路线额外 +20%", "price": 60, "type": "consumable", "cat": "修炼", "route": "摄影", "use": {"progress": 18}},
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
    {"name": "觉醒·灵种", "desc": "系统深处的封存之物——一粒微光流转的种子，服下即点亮灵根，踏入修行之门（一次性）", "price": 150, "type": "consumable", "cat": "特殊", "use": {"awaken": 1}},
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


POOL_SELL_PRICE = {
    "便利店饭团": 8, "自习室月卡": 25, "大师吉他课（进阶）": 60,
    "精品摄影套装（高阶）": 70, "传奇钢琴大师课（传承）": 120, "限量款行李箱": 90,
}

# 抽奖专属奖励同样有真实使用效果；旧存档中的同名物品也能直接使用。
PRIZE_CATALOG = [
    {"name": "便利店饭团", "desc": "补充体力：等级进度 +2", "price": 8, "type": "consumable", "cat": "修炼", "reward_only": True, "use": {"progress": 2}},
    {"name": "自习室月卡", "desc": "安静的固定座位：等级进度 +12", "price": 25, "type": "consumable", "cat": "修炼", "route": "学业", "reward_only": True, "use": {"progress": 12}},
    {"name": "大师吉他课（进阶）", "desc": "掌握一首舞台曲目：等级进度 +25、魅力 +1", "price": 60, "type": "consumable", "cat": "修炼", "route": "音乐", "reward_only": True, "use": {"progress": 25, "stat": {"魅力": 1}}},
    {"name": "精品摄影套装（高阶）", "desc": "构图与后期实战：等级进度 +28、头脑 +1", "price": 70, "type": "consumable", "cat": "修炼", "route": "摄影", "reward_only": True, "use": {"progress": 28, "stat": {"头脑": 1}}},
    {"name": "传奇钢琴大师课（传承）", "desc": "完整舞台训练：等级进度 +45、魅力 +2", "price": 120, "type": "consumable", "cat": "修炼", "route": "音乐", "reward_only": True, "use": {"progress": 45, "stat": {"魅力": 2}}},
    {"name": "限量款行李箱", "desc": "整理远行装备：体魄 +1、魅力 +1", "price": 90, "type": "consumable", "cat": "属性", "reward_only": True, "use": {"stat": {"体魄": 1, "魅力": 1}}},
    {"name": "系统积分×50", "desc": "兑换系统积分 ×50", "price": 50, "type": "consumable", "cat": "特殊", "reward_only": True, "use": {"currency": 50}},
]

SELL_RATIO = 0.5  # 卖出回收比例

# ---------- 商城配置：GM 可写的动态货架与抽奖（data/shop_config.json） ----------
SHOP_CONFIG_FILE = DATA_DIR / "shop_config.json"
SHOP_CONFIG_DEFAULT: dict = {
    "rotation": {"enabled": True, "slots": 8, "period": "day"},    # 货架轮换：每日随机8件
    "pinned": ["系统抽奖券", "觉醒·灵种"],                            # 常驻货架
    "custom_items": [],                                             # GM 上架的自定义商品
    "lottery": None,          # None=默认（四档权重＋总池每日轮换子集）
}
_shop_config_cache: dict = {"mtime": None, "data": None}


def _sanitize_shop_cfg(raw: dict) -> dict:
    """配置唯一清洗口：GM 端点保存与文件读取都走这里——
    价格/属性/件数/白名单的钳制只在一处定义，手改文件注入越界值同样被拦。"""
    from . import engine as _eng
    cfg = _default_cfg()
    rot = raw.get("rotation") or {}
    if isinstance(rot, dict):
        r = dict(cfg["rotation"])
        r["enabled"] = bool(rot.get("enabled", True))
        r["slots"] = max(4, min(int(rot.get("slots", 8)) or 8, 48))
        r["period"] = "slot" if rot.get("period") == "slot" else "day"
        cfg["rotation"] = r
    pinned_in = raw.get("pinned")
    if isinstance(pinned_in, list):
        cfg["pinned"] = [str(n) for n in pinned_in
                         if str(n) in {g["name"] for g in SHOP_CATALOG}][:20]
    items_in = raw.get("custom_items")
    if isinstance(items_in, list):
        items = []
        for it in items_in[:60]:
            if not isinstance(it, dict):
                continue
            name = _eng._clean_text(it.get("name"), 20)
            if not name:
                continue
            try:
                price = max(1, min(int(it.get("price", 10)), 9999))
            except (TypeError, ValueError):
                price = 10
            goods = {"name": name, "desc": _eng._clean_text(it.get("desc"), 40),
                     "price": price, "type": "consumable" if it.get("use") else "tool",
                     "cat": str(it.get("cat", "特殊"))[:4] or "特殊"}
            if isinstance(it.get("use"), dict):
                use = {}
                if "progress" in it["use"]:
                    try:
                        use["progress"] = max(1, min(int(it["use"]["progress"]), 30))
                    except (TypeError, ValueError):
                        pass
                if isinstance(it["use"].get("stat"), dict):
                    for k, v in it["use"]["stat"].items():
                        if str(k) in ("体魄", "头脑", "情商", "魅力"):
                            try:
                                use.setdefault("stat", {})[str(k)] = max(1, min(int(v), 5))
                            except (TypeError, ValueError):
                                pass
                if use:
                    goods["use"] = use
            items.append(goods)
        cfg["custom_items"] = items
    lot_in = raw.get("lottery")
    if isinstance(lot_in, dict):
        lot = {}
        w = lot_in.get("weights")
        if isinstance(w, dict) and w:
            lot["weights"] = {q: max(0, min(int(w.get(q, 0)) or 0, 1000))
                              for q in ("普通", "稀有", "史诗", "传说")}
        if "per_day" in lot_in:
            lot["per_day"] = bool(lot_in["per_day"])
        pool_in = lot_in.get("pool")
        if isinstance(pool_in, dict) and pool_in:
            legal = {g["name"] for g in SHOP_CATALOG + PRIZE_CATALOG}
            pool = {}
            for q, names in pool_in.items():
                if str(q) in ("普通", "稀有", "史诗", "传说"):
                    pool[str(q)] = [str(n) for n in (names or []) if str(n) in legal][:12]
            lot["pool"] = pool or None
        cfg["lottery"] = lot or None
    return cfg


def load_shop_config() -> dict:
    """读 data/shop_config.json（mtime 缓存；坏文件/越界值经统一清洗回安全配置）。"""
    import json as _json
    global _shop_config_cache
    try:
        mtime = SHOP_CONFIG_FILE.stat().st_mtime
    except OSError:
        return _default_cfg()
    if _shop_config_cache["mtime"] == mtime and _shop_config_cache["data"]:
        return _shop_config_cache["data"]
    cfg = _default_cfg()
    try:
        raw = _json.loads(SHOP_CONFIG_FILE.read_text(encoding="utf-8"))
        cfg = _sanitize_shop_cfg(raw if isinstance(raw, dict) else {})
    except (OSError, ValueError, TypeError):
        pass  # 坏文件回默认
    _shop_config_cache = {"mtime": mtime, "data": cfg}
    return cfg


def _default_cfg() -> dict:
    import copy as _copy
    return _copy.deepcopy(SHOP_CONFIG_DEFAULT)


def save_shop_config(cfg: dict) -> None:
    import json as _json
    global _shop_config_cache
    SHOP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    SHOP_CONFIG_FILE.write_text(_json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    _shop_config_cache = {"mtime": None, "data": None}


def custom_catalog() -> list[dict]:
    """GM 自定义商品 → 商品字典（use 效果原样透传，写入时已校验）。"""
    out = []
    for it in load_shop_config().get("custom_items") or []:
        if isinstance(it, dict) and it.get("name") and it.get("price"):
            goods = {"name": str(it["name"]), "desc": str(it.get("desc", "")),
                     "price": int(it["price"]), "type": str(it.get("type", "tool")),
                     "cat": str(it.get("cat", "特殊"))}
            if isinstance(it.get("use"), dict):
                goods["use"] = it["use"]
            out.append(goods)
    return out


def full_catalog() -> list[dict]:
    """全局目录 = 基础在售 + GM 自定义（买入/卖出/送礼/剧情白名单统一口径）。"""
    return SHOP_CATALOG + PRIZE_CATALOG + custom_catalog()


def catalog_by_name() -> dict[str, dict]:
    return {g["name"]: g for g in full_catalog()}


def _seed_str(state: dict | None) -> str:
    """货架/奖池种子：period=day 按游戏日、slot 按时段——同档期人人一致，跨期轮换。"""
    from .models import game_today
    if not state:
        return "seed"
    if (load_shop_config().get("rotation") or {}).get("period") == "slot":
        t = state.get("time") or {}
        return f"{game_today(state)}-s{int(t.get('slot', 0))}"
    return game_today(state)


def shelf_catalog(state: dict | None = None) -> list[dict]:
    """当期货架：常驻 + 按种子确定性抽 N 件 + 自定义（展示层；购买不限货架）。"""
    cfg = load_shop_config()
    rot = cfg.get("rotation") or {}
    everything = [g for g in full_catalog() if not g.get("reward_only")]
    if not rot.get("enabled"):
        return everything
    pinned = set(cfg.get("pinned") or [])
    tops = [g for g in everything if g["name"] in pinned]
    pool = [g for g in everything if g["name"] not in pinned]
    slots = max(1, min(int(rot.get("slots", 14)), len(pool)))
    import zlib
    s = zlib.crc32(_seed_str(state).encode("utf-8"))
    picked = []
    while len(picked) < slots and pool:
        s = (s * 1103515245 + 12345) & 0x7fffffff
        picked.append(pool.pop(s % len(pool)))
    return tops + picked + custom_catalog()




def currency_count(state: dict, currency: str = CURRENCY) -> int:
    return sum(max(0, int(it.get("count", 0))) for it in state["player"]["items"]
               if it.get("name") == currency)


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
    goods = catalog_by_name().get(name)
    if goods is None:
        return {"ok": False, "msg": "商城里没有这件商品。"}
    # 限时货架：只有当天在架的商品能买（常驻+轮换+自定义）；全目录仅供卖出/送礼
    if name not in {g["name"] for g in shelf_catalog(state)}:
        return {"ok": False,
                "msg": f"『{name}』今日不在货架上——限时货架每天随机上架 8 件，明天再来看看。"}
    if not _take_currency(state, goods["price"]):
        return {"ok": False, "msg": f"系统积分不足（需要 {goods['price']}，持有 {currency_count(state)}）。"}
    _apply_items(state, [{"name": goods["name"], "desc": goods["desc"]}])
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
    return {"ok": True, "msg": f"购得『{goods['name']}』（花费 {goods['price']} 系统积分）。"}


def sell(state: dict, name: str) -> dict:
    item = next((i for i in state["player"]["items"] if i["name"] == name), None)
    if item is None:
        return {"ok": False, "msg": "背包里没有这件物品。"}
    if name in SYSTEM_ITEMS or name in (CASH, CURRENCY):
        return {"ok": False, "msg": "系统专属物品不可交易——抽奖券只能用来抽奖。"}
    goods = catalog_by_name().get(name)
    # 目录外（模型自创）物品给 1 金保底回收：不能变现就只是背包垃圾
    base_price = goods["price"] if goods else POOL_SELL_PRICE.get(name, 1)
    refund = max(1, int(base_price * SELL_RATIO))
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
    return {"ok": True, "msg": f"卖出『{name}』，回收 {refund} 系统积分。"}


LOTTERY_QUALITIES = [("普通", 70), ("稀有", 24), ("史诗", 5), ("传说", 1)]

# 新手奖池：开局赠送的抽奖次数专用。count 缺省为 1。
NEWBIE_POOL = {
    "普通": [
        {"name": "系统积分", "desc": "系统商城通用货币", "count": 8},
        {"name": "专注咖啡", "desc": "自习神器：等级进度+5"},
        {"name": "感冒冲剂", "desc": "淋雨夜跑之后的及时雨"},
        {"name": "心形暖手宝", "desc": "冬天递过去的温度，比说什么都管用"},
        {"name": "运动蛋白粉", "desc": "练后半小时的黄金补给：等级进度+6"},
        {"name": "便利店饭团", "desc": "系统出品的加餐口粮，深夜自习的底气", "count": 3},
        {"name": "经验卡（小）", "desc": "系统特供的成长值注入：等级进度+6"},
    ],
    "稀有": [
        {"name": "一对一辅导课时", "desc": "等级进度+10"},
        {"name": "名师精品网课", "desc": "等级进度+12"},
        {"name": "精读书单", "desc": "啃完这份书单，头脑永久+1"},
        {"name": "电影票", "desc": "两张连座——第二张，要送给谁？"},
        {"name": "香薰蜡烛", "desc": "灯光调暗一档，气氛就近一步"},
        {"name": "运动夹克", "desc": "清爽利落的运动系穿搭，体魄+2（可装备）"},
        {"name": "自习室月卡", "desc": "靠窗的固定座位一个月，安静与咖啡香兼得"},
        {"name": "幸运药剂（小）", "desc": "下一次抽奖保底【稀有】品质"},
        {"name": "强化胶囊·魅力", "desc": "系统出品的定向强化剂：魅力永久+1"},
    ],
    "史诗": [
        {"name": "修身西装", "desc": "重要场合的一击必杀，魅力+4（可装备）"},
        {"name": "智能腕表", "desc": "低调有质感，头脑+3（可装备）"},
        {"name": "冲刺计划表", "desc": "考前/赛前的珍品冲刺方案", "count": 2},
        {"name": "大师吉他课（进阶）", "desc": "进阶音乐课程，指弹与编曲的门槛一次跨过"},
        {"name": "精品摄影套装（高阶）", "desc": "高阶摄影套装，机身镜头与后期课打包带走"},
        {"name": "双倍经验时段卡", "desc": "接下来 3 次等级进度收益 ×2"},
        {"name": "技能灌顶卡", "desc": "主修技能 +30 经验"},
    ],
    "传说": [
        {"name": "传奇钢琴大师课（传承）", "desc": "传说级的大师亲授名额，从基本功到舞台表现完整传承"},
        {"name": "限量款行李箱", "desc": "说走就走的底气，装得下说走就走的全部行装"},
        {"name": "系统积分×50", "desc": "系统特殊奖励，用途待系统升级后揭晓（收藏品）"},
        {"name": "SSR保底券", "desc": "下一次抽奖保底【史诗】品质"},
    ],
}




def lottery_weights() -> list[tuple[str, int]]:
    """品质权重：GM 配置优先，否则默认四档。"""
    lot = load_shop_config().get("lottery") or {}
    w = lot.get("weights") or {}
    if w and all(q in w and int(w[q]) >= 0 for q, _ in LOTTERY_QUALITIES):
        return [(q, int(w[q])) for q, _ in LOTTERY_QUALITIES]
    return LOTTERY_QUALITIES


def lottery_pool(state: dict | None = None) -> dict[str, list[dict]]:
    """实际奖池：GM 整池覆盖优先；否则总池每日轮换（每品质抽子集，同日人人一致）。"""
    lot = load_shop_config().get("lottery") or {}
    override = lot.get("pool")
    if isinstance(override, dict) and override:
        by_name = catalog_by_name()
        out = {}
        for q, items in override.items():
            pool = []
            for nm in items or []:
                g = by_name.get(str(nm))
                if g:
                    pool.append({"name": g["name"], "desc": g["desc"], "count": g.get("use", {}).get("progress") and 1 or 1})
            out[str(q)] = pool or [dict(i) for i in NEWBIE_POOL.get(q, [])[:1]]
        # 池内条目补 count 默认
        for q in NEWBIE_POOL:
            out.setdefault(q, [dict(i) for i in NEWBIE_POOL[q][:1]])
        return out
    if lot.get("per_day") is False:
        return NEWBIE_POOL
    # 每日轮换：每品质按种子的确定性抽样
    import zlib
    seed = zlib.crc32(_seed_str(state).encode("utf-8"))
    take = {"普通": 4, "稀有": 3, "史诗": 2, "传说": 2}
    out = {}
    for q, items in NEWBIE_POOL.items():
        k = min(take.get(q, 3), len(items))
        picked, s, pool = [], seed + sum(ord(c) for c in q), list(items)
        while len(picked) < k and pool:
            s = (s * 1103515245 + 12345) & 0x7fffffff
            picked.append(pool.pop(s % len(pool)))
        out[q] = picked
    return out


def draw_lottery(state: dict) -> dict:
    """消耗一张抽奖券，按品质权重从当期奖池抽取并入账。"""
    item = next((i for i in state["player"]["items"] if i["name"] == LOTTERY_TICKET), None)
    if item is None or item.get("count", 0) < 1:
        return {"ok": False, "msg": "没有可用的抽奖券。"}
    item["count"] -= 1
    if item["count"] <= 0:
        state["player"]["items"].remove(item)

    quals = lottery_weights()
    names = [q for q, _ in quals]
    weights = [w for _, w in quals]
    lucky = state["player"].pop("lucky_draw", "")
    if lucky in names:
        floor = names.index(lucky)
        weights = [w if i >= floor else 0 for i, w in enumerate(weights)]
        if sum(weights) <= 0:
            weights = [1 if i == floor else 0 for i in range(len(names))]
    quality = random.choices(names, weights=weights, k=1)[0]
    prize = dict(random.choice(lottery_pool(state)[quality] or NEWBIE_POOL[quality]))
    prize["count"] = max(1, int(prize.get("count", 1)))
    if prize["name"] in catalog_by_name():
        prize["desc"] = catalog_by_name()[prize["name"]]["desc"]
    _apply_items(state, [prize])

    lot = state["player"].setdefault("lottery", {"total_drawn": 0, "history": []})
    lot["total_drawn"] = int(lot.get("total_drawn", 0)) + 1
    lot["history"] = (lot.get("history") or [])[-59:] + [{
        "no": lot["total_drawn"], "quality": quality,
        "name": prize["name"], "count": prize["count"], "ts": now_iso(),
    }]
    sync_achievements(state)
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
    luck_note = f"（幸运加持生效：保底【{lucky}】）" if lucky in names else ""
    return {"ok": True, "quality": quality, "prize": prize,
            "msg": f"抽奖结果：【{quality}】{prize['name']}×{prize['count']} 已入账（新手奖池）{luck_note}。"}


def lottery_view(state: dict) -> dict:
    """抽奖面板数据：余券、品质档、奖池概览与最近抽取记录。"""
    tickets = sum(i.get("count", 0) for i in state["player"]["items"] if i["name"] == LOTTERY_TICKET)
    lot = state["player"].get("lottery") or {}
    pools = {q: [{"name": p["name"], "count": p.get("count", 1)} for p in items]
             for q, items in lottery_pool(state).items()}
    return {"tickets": tickets, "qualities": [q for q, _ in LOTTERY_QUALITIES],
            "pool": pools, "history": list((lot.get("history") or [])[-12:])[::-1],
            "total_drawn": int(lot.get("total_drawn", 0))}


# ---------- 送礼（恋爱核心循环·阶段A） ----------

GIFT_DAILY_CAP = 1   # 同一人每天最多 1 份（星露谷规则）
GIFT_WEEKLY_CAP = 2  # 同一人每周最多 2 份


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


def _week_key(state: dict | None = None) -> str:
    """周限额键：跟随游戏内日历（与 game_today 同源），日键与周键一起翻篇。"""
    from datetime import date
    iso = date.fromisoformat(game_today(state)).isocalendar()
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
    goods = catalog_by_name().get(item_name)
    if goods is None or goods.get("cat") not in GIFT_CATEGORIES:
        return {"ok": False, "msg": "这件物品不适合作为礼物赠送。"}
    if (goods.get("cat") == "情趣" and goods["price"] >= 250
            and (npc.get("relationship") or {}).get("status") not in ("flirt", "partner", "distance")):
        return {"ok": False, "msg": f"和{npc['name']}还没到那一步——这样的礼物火候不到只会吓退彼此（需已是彼此承认的暧昧或恋人）。"}
    if not any(i["name"] == item_name for i in state["player"]["items"]):
        return {"ok": False, "msg": "背包里没有这件物品。"}

    log = state.setdefault("gift_log", {"daily": {}, "weekly": {}})
    today, week = game_today(state), _week_key(state)
    daily = log.setdefault("daily", {}).setdefault(today, {})
    weekly = log.setdefault("weekly", {}).setdefault(week, {})
    # 生日有额外心意，每日限一份，并豁免普通每周两份上限。
    def _md(date_str: str) -> str:
        parts = date_str.split("-")
        try:
            return f"{int(parts[-2])}-{int(parts[-1])}" if len(parts) >= 2 else ""
        except (TypeError, ValueError):
            return ""
    birthday_today = bool(npc.get("birthday")) and _md(npc["birthday"]) == _md(today)
    # 生日规则：当日仍限一份（防刷），但不占每周限额（星露谷精神）；
    # 台账永远照写——豁免的是限额，不是记录，否则成就判定会被跳过。
    bd_week = log.setdefault("bd_week", {}).setdefault(week, {})
    weekly_eff = weekly.get(npc["name"], 0) - bd_week.get(npc["name"], 0)
    if daily.get(npc["name"], 0) >= GIFT_DAILY_CAP:
        return {"ok": False, "msg": f"今天已经给{npc['name']}送过礼物了，心意太频会变负担——明天再说。"}
    if not birthday_today and weekly_eff >= GIFT_WEEKLY_CAP:
        return {"ok": False, "msg": f"这周给{npc['name']}的礼物已经够多了（每周限 {GIFT_WEEKLY_CAP} 份）。"}

    base = _gift_base_value(goods)
    liked = bool(npc.get("likes")) and npc["likes"] == goods["cat"]
    # 偏好首揭制：第一次命中偏好才明示品类，此后只给模糊反馈——摸索的乐趣留给玩家
    first_reveal = liked and not npc.get("likes_known")
    if liked:
        npc["likes_known"] = True
    note = f"收到礼物『{item_name}』"
    if liked:
        note += "（投其所好：正中偏好）" if first_reveal else "（这份礼物很合她心意）"
    npc_remember(npc, state["turn"], note, prefix="送礼：")

    _remove_items(state, item_name, 1)
    daily[npc["name"]] = daily.get(npc["name"], 0) + 1
    weekly[npc["name"]] = weekly.get(npc["name"], 0) + 1
    if birthday_today:
        bd_week[npc["name"]] = bd_week.get(npc["name"], 0) + 1
    ach = settle_growth(state)
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照

    msg = f"把『{item_name}』送给了{npc['name']}。"
    if birthday_today:
        msg = f"今天是{npc['name']}的生日！{msg}（生日心意，不占每周限额）"
    elif liked:
        msg += (f"（投其所好：TA偏爱{goods['cat']}类礼物）" if first_reveal
                else "（她似乎很喜欢这个）")
    for a in ach:
        msg += " " + a
    return {"ok": True, "msg": msg, "liked": liked}


def use_item(state: dict, name: str) -> dict:
    item = next((i for i in state["player"]["items"] if i["name"] == name), None)
    if item is None:
        return {"ok": False, "msg": "背包里没有这件物品。"}
    if name == LOTTERY_TICKET:
        return draw_lottery(state)
    goods = catalog_by_name().get(name)
    if goods is None or goods.get("type") != "consumable" or not goods.get("use"):
        return {"ok": False, "msg": "这件物品暂时无法直接使用。"}
    use = goods["use"]
    if "luck" in use:
        ranks = [quality for quality, _ in LOTTERY_QUALITIES]
        current = state["player"].get("lucky_draw", "")
        incoming = str(use["luck"])
        if current in ranks and incoming in ranks and ranks.index(current) >= ranks.index(incoming):
            return {"ok": False, "msg": f"已有【{current}】保底，无需使用『{name}』，物品已保留。"}
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
        progress = use["progress"]
        route = (state["player"].get("technique") or {}).get("route")
        matched = bool(goods.get("route") and goods["route"] == route)
        if matched:
            progress += max(1, (progress + 4) // 5)
        _add_realm_progress(state, progress)
        msgs.append(f"等级进度 +{progress}" + ("（同路线天赋加成 +20%）" if matched else ""))
        # 已觉醒者：世俗修炼同样滋养灵根，修为同额入账
        if (state.get("power") or {}).get("awakened") and "power" not in use:
            msgs.extend(add_power_progress(state, progress))
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
    if "currency" in use:
        _apply_items(state, [{"name": CURRENCY, "desc": "系统商城通用货币", "count": use["currency"]}])
        msgs.append(f"系统积分 +{use['currency']}")
    if "buff" in use:
        buffs = state["player"].setdefault("buffs", {})
        charges = min(9, int(buffs.get("exp_boost") or 0) + int(use["buff"].get("exp_boost") or 0))
        buffs["exp_boost"] = charges
        msgs.append(f"双倍经验时段已开启：接下来 {charges} 次等级进度收益 ×2")
    if "skill_xp" in use:
        from .skills import SKILLS, add_xp, ensure_skills
        book = ensure_skills(state)
        top = max(SKILLS, key=lambda sid: (int((book.get(sid) or {}).get("lv", 0)),
                                           int((book.get(sid) or {}).get("xp", 0)),
                                           -list(SKILLS).index(sid)))
        gained = add_xp(state, top, int(use["skill_xp"]))
        skill_name = SKILLS[top][0]
        msgs.append(f"{skill_name} +{use['skill_xp']} 经验" + (f"（{'，'.join(gained)}）" if gained else ""))
    if "luck" in use:
        state["player"]["lucky_draw"] = str(use["luck"])
        msgs.append(f"幸运加持已生效：下一次抽奖保底【{use['luck']}】品质")
    msgs.extend(settle_growth(state))
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
        _apply_items(state, [{"name": old, "desc": catalog_by_name().get(old, {}).get("desc", "")}])
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
    _apply_items(state, [{"name": name, "desc": catalog_by_name().get(name, {}).get("desc", "")}])
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
    return {"ok": True, "msg": f"换下『{name}』，已放回背包。"}
