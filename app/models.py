"""游戏状态模型：以 dict 为核心，提供默认值与操作工具。"""
from datetime import date, datetime, timezone, timedelta
from copy import deepcopy

from . import memory

# 系统等级（题材：都市恋爱）。索引与主线阶段一一对应，只能靠真实提升推进。
REALMS = ["无名路人", "初露锋芒", "校园新星", "崭露头角", "风云人物", "校园传奇",
          "城市新锐", "万众瞩目", "众星捧月", "城市传奇", "人生赢家"]

# 主线（"大主线＝人生赢家"）：目标文本按等级主干派生，索引与 REALMS 一一对应。
# 只能靠真实提升推进——模型的 quest_progress 碰不到 title/stage/desc，只能记进展说明。
QUEST_TITLE = "人生赢家"
QUEST_MILESTONES = [
    "系统尚未觉醒：大一新生拖着行李箱的寻常日常——直到报到日的夜晚，一切开始改变。",
    "初露锋芒：大一入学，大学生活从零开局。把成绩、身体与自信先立起来，让改变被看见。",
    "校园新星：社团、竞赛或一场惊艳全场的亮相——让人记住你的名字。",
    "崭露头角：校园之外初试身手，兼职、创业或一次漂亮的出手，攒下第一份家底。",
    "风云人物：感情线与事业线交织成网，麻烦与青睐一起找上门——学会应付人心。",
    "校园传奇：毕业前的传奇一笔——把校园里最重要的人和事都握在手里，不留遗憾。",
    "城市新锐：走出校园在城市站稳脚跟——身份、收入与影响力都要立得住。",
    "万众瞩目：聚光灯照过来的时代，一举一动都有回响；护住不想失去的东西。",
    "众星捧月：身边群星环绕，真心与假意交错——分清谁是路灯，谁是月亮。",
    "城市传奇：从京都到魔都，处处留下你的传说；系统交付最后的机会与代价。",
    "人生赢家：事业、真心与自由都不再是选择题——大结局，由你亲手写下。",
]
MAIN_QUEST_NOTES = 3  # 任务面板"近况"保留的条数
START_REALM = 1       # 开局系统觉醒即"初露锋芒"；主线起始档位与它同源，不会写歪

WORLD_URBAN = "urban"
WORLD_NAMES = {WORLD_URBAN: "都市"}

EQUIP_SLOTS = ["上装", "鞋履", "配饰", "座驾"]

CURRENCY = "系统金币"  # 系统商城的计价单位
LOTTERY_TICKET = "系统抽奖券"

# 系统专属物品：只能经系统通道（开局发放、抽奖扣除）增减。
# 剧情契约不得发放或扣除它们——否则模型一次申报就能凭空造出上千次抽奖，
# 再借奖池里的在售物品半价卖出，把经济系统整条洗空。
SYSTEM_ITEMS = frozenset({LOTTERY_TICKET})

# 初始天赋（六条路线，品质固定为初始范围内最高的 S 级）
TECHNIQUE_ROUTES = ["学业", "运动", "音乐", "创业", "厨艺", "摄影"]
INITIAL_TECHNIQUE_GRADE = "S级"

# 穿搭加成表（商城在售服饰共用的单一数据源）
EQUIPMENT_BONUS = {
    "运动夹克": {"slot": "上装", "stats": {"体魄": 2}},
    "修身西装": {"slot": "上装", "stats": {"魅力": 4}},
    "轻便跑鞋": {"slot": "鞋履", "stats": {"体魄": 3}},
    "智能腕表": {"slot": "配饰", "stats": {"头脑": 3}},
    "城市单车": {"slot": "座驾", "stats": {"体魄": 1, "魅力": 1}},
}

# 好感阶段（恋爱线主干）：阈值与标签一一对应，跨档时系统公告
AFFINITY_STAGES = [(0, "初识"), (25, "熟识"), (50, "朋友"), (70, "亲近"), (85, "心动"), (100, "羁绊")]
GIFT_CATEGORIES = ("约会", "情趣", "特殊")  # 可赠送物品的分类

# 地点类型白名单（new_places.type 只接受这些枚举，防注入也统一前端图例）
PLACE_TYPES_KNOWN = ("campus", "city", "leisure", "nature", "culture", "transport", "secret")


def is_romanceable(npc: dict) -> bool:
    """是否可进入恋爱线（约会/恋爱成就）。角色边界的单一事实源——
    成就、约会判定都必须走这里，别在多处各写一遍条件。"""
    return npc.get("role") != "母亲"
# 好感单回合护栏（规则侧钳制，与提示词软约束双轨）
AFFINITY_TURN_CAP = 10     # 普通回合：单 NPC 累计变化上限
AFFINITY_DATE_CAP = 15     # 约会回合：约会对象的上限
AFFINITY_OFFLINE_CAP = 15  # 离线结算：单 NPC 上限（离线跨多天，放宽一档）

DATE_AFFINITY_REQUIREMENT = 70  # 正式约会需达到「亲近」
MAX_DATES_KEPT = 30             # 约会回忆保留条数
CHAT_HISTORY_KEPT = 40          # 每个会话保留的消息条数（滚动窗口）

# ---------- 超凡觉醒（心动系统的隐藏功能：只有主角在偷偷修仙） ----------
POWER_STAGES = ["凡人", "灵觉初醒", "淬体", "他心通", "灵犀", "御气"]
POWER_PROGRESS_PER_STAGE = 100   # 每境修为满 100 突破
POWER_STAGE_EFFECTS = {          # 突破时的一次性/持续效果（引擎侧接线）
    1: "灵觉初醒：可感知灵气，修炼类道具开始积累修为",
    2: "淬体：气血重铸，体魄永久 +2",
    3: "他心通：人物详情可听见 TA 对你的真实心声",
    4: "灵犀：每日与同一人的第一条短信令好感 +1",
    5: "御气：身轻如燕，跨地点赶路不再多耗时段",
}

# 跨档剧情钩子的主题提示（按新阶段给 AI 的演绎方向）
HOOK_THEMES = {
    "熟识": "一场只属于你们俩的默契时刻（小秘密、共同的玩笑）",
    "朋友": "一次互相帮衬的麻烦或约定（守信、并肩）",
    "亲近": "一次交心的深夜对话，或触到 TA 家庭线的一角",
    "心动": "告白前夜级别的关键事件（试探、险些说破、心跳加速的瞬间）",
    "羁绊": "定情与承诺（说出口的话、不许再收回）",
}
MAX_HOOKS = 5  # 待消化剧情钩子上限

# 成就：谓词式定义，引擎在关键结算点统一检查
ACHIEVEMENTS = [
    {"id": "first_gift", "title": "初次心意", "desc": "送出第一份礼物",
     "check": lambda st: any(cnt for per_npc in ((st.get("gift_log") or {}).get("daily") or {}).values()
                             for cnt in per_npc.values())},
    {"id": "first_date", "title": "初次约会", "desc": "与心动的人完成第一次正式约会",
     "check": lambda st: bool(st.get("dates"))},
    {"id": "first_heart", "title": "怦然心动", "desc": "有人对你达到「心动」（好感85+）",
     "check": lambda st: any(n["affinity"] >= 85 and is_romanceable(n) for n in st["npcs"]
                             if n.get("known_to_player", n.get("last_seen_turn", -1) >= 0))},
    {"id": "first_bond", "title": "定下羁绊", "desc": "与心动的人定下「羁绊」（好感100）",
     "check": lambda st: any(n["affinity"] >= 100 and is_romanceable(n) for n in st["npcs"]
                             if n.get("known_to_player", n.get("last_seen_turn", -1) >= 0))},
    {"id": "explorer", "title": "城市探索者", "desc": "探明 10 处地点",
     "check": lambda st: sum(1 for pl in st.get("map", {}).get("urban", []) if pl.get("discovered")) >= 10},
    {"id": "social", "title": "相识满座", "desc": "认识 8 位角色",
     "check": lambda st: sum(1 for n in st["npcs"]
                             if n.get("known_to_player", n.get("last_seen_turn", -1) >= 0)) >= 8},
    {"id": "lucky_hand", "title": "手气不错", "desc": "累计抽奖 10 次",
     "check": lambda st: int((st["player"].get("lottery") or {}).get("total_drawn", 0)) >= 10},
    {"id": "top_level", "title": "人生赢家", "desc": "等级抵达满级",
     "check": lambda st: st["player"].get("realm", 0) >= len(REALMS) - 1},
]

# 时间与日程：一天五时段，回合按时段推进
TIME_SLOTS = ["清晨", "上午", "下午", "傍晚", "夜晚"]


def advance_time(state: dict, slots: int) -> None:
    """时间只前进：跨过夜晚自动进入第二天清晨。"""
    if slots <= 0:
        return
    t = state.setdefault("time", {"day": 1, "slot": 0})
    total = int(t.get("slot", 0)) + slots
    t["day"] = int(t.get("day", 1)) + total // len(TIME_SLOTS)
    t["slot"] = total % len(TIME_SLOTS)


def time_label(state: dict) -> str:
    t = state.get("time") or {"day": 1, "slot": 0}
    return f"第{int(t.get('day', 1))}天·{TIME_SLOTS[int(t.get('slot', 0)) % len(TIME_SLOTS)]}"


def affinity_stage(affinity: int) -> str:
    """好感数值对应的阶段标签。"""
    stage = AFFINITY_STAGES[0][1]
    for threshold, label in AFFINITY_STAGES:
        if affinity >= threshold:
            stage = label
    return stage


def stage_index(affinity: int) -> int:
    """好感数值对应的阶段序号（0~5），用于跨档判定。"""
    idx = 0
    for i, (threshold, _) in enumerate(AFFINITY_STAGES):
        if affinity >= threshold:
            idx = i
    return idx
THEME_ID = "urban-romance-v1"
LEGACY_THEME_IDS = {None, ""}  # 无标识的一律视为旧题材存档

# 旧题材物品改名（财富随存档迁移）
LEGACY_ITEM_RENAMES = {"下品灵石": CURRENCY}
# 已下线人物：旧题材专属人物＋周母（2026-10-19 用户定案移除，亲情线不再出场）
LEGACY_NPC_IDS = {"npc_xuanyangzi", "npc_luoqingyi", "npc_zhaoqing", "npc_molao", "npc_xueluo", "npc_zhoumu"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# 游戏内日历：开局＝2026-09-01（京华大学报到日）。签到、送礼日/周限额、
# 生日判定全部按游戏日期结算——剧情一天五时段，几天就能走到角色的生日，
# 不再出现"生日永远撞不上现实日期"的双时钟问题。
GAME_EPOCH = date(2026, 9, 1)


def game_today(state: dict | None = None) -> str:
    """游戏世界的今天（ISO 日期）。state 缺失/无时间时按第 1 天。"""
    day = 1
    if isinstance(state, dict):
        try:
            day = max(1, int((state.get("time") or {}).get("day", 1)))
        except (TypeError, ValueError):
            day = 1
    return (GAME_EPOCH + timedelta(days=day - 1)).isoformat()


def public_state(state: dict) -> dict:
    """玩家已知档案与主持人后台档案隔离，秘密不传给浏览器。"""
    result = deepcopy(state)
    result["server_date"] = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    result["game_date"] = game_today(state)  # 游戏世界日期（签到/限额/生日的结算钟）
    result["dates"] = list(state.get("dates", []))[-20:]
    # 主持人后台不进浏览器：事实账本与剧情钩子是给模型的，F12 不该能翻到
    result.pop("facts", None)
    result.pop("hooks", None)
    result["chats"] = {k: {"msgs": list(v.get("msgs", []))[-CHAT_HISTORY_KEPT:]}
                       for k, v in (state.get("chats") or {}).items()}
    result["achievement_defs"] = [{"id": a["id"], "title": a["title"], "desc": a["desc"]}
                                  for a in ACHIEVEMENTS]
    visible = []
    for npc in result["npcs"]:
        known = npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0)
        if not known:
            continue
        visible.append({
            k: npc.get(k) for k in ("id", "name", "world", "role", "place", "affinity", "label", "likes")
        } | {"persona": npc.get("public_persona") or f"已知身份：{npc['role']}。更多经历有待了解。",
             "rels": npc.get("known_rels", {}), "memory": npc.get("known_memory", []),
             # 玩家亲历的共同记忆（近6条）：幕后事件与离线内部记录不下发浏览器
             "memo": [m for m in (npc.get("memory") or [])
                      if not str(m).startswith(("幕后：", "离线期间："))][-6:]})
    result["npcs"] = visible
    return result


def default_npcs() -> list[dict]:
    return [
        {
            "id": "npc_suwanqing", "name": "苏晚晴", "world": WORLD_URBAN,
            "role": "青梅竹马·音乐学院学姐", "place": "外滩滨江",
            "likes": "情趣",
            "birthday": "3-21",
            "persona": "隔壁魔都音乐学院的钢琴学姐，与主角青梅竹马一起长大；聪明敏锐，外冷内柔，"
                       "嘴上嫌弃却记得主角所有的习惯，对其近来的变化隐隐起疑又不敢深问",
            "affinity": 60, "label": "青梅竹马", "memory": [], "deeds": [],
            "known_to_player": False,  # 新档全员未结识：剧情登场才点亮关系网,
            "rels": {"陈芮": "老同学，互相熟但爱斗嘴"},
        },
        {
            "id": "npc_chenrui", "name": "陈芮", "world": WORLD_URBAN,
            "role": "发小·同校死党", "place": "京华大学",
            "likes": "约会",
            "birthday": "8-8",
            "persona": "从穿开裆裤一起长大到考进同一所大学的女汉子，话多义气、嘴碎但可靠，"
                       "最早察觉主角的变化，好奇心重",
            "affinity": 70, "label": "死党", "memory": [], "deeds": [],
            "known_to_player": False,  # 新档全员未结识：剧情登场才点亮关系网,
            "rels": {"苏晚晴": "老同学，互相熟但爱斗嘴"},
        },
        {
            "id": "npc_linhui", "name": "林慧", "world": WORLD_URBAN,
            "role": "辅导员", "place": "京华大学",
            "likes": "特殊",
            "birthday": "9-10",
            "persona": "年轻却手腕老到的辅导员，管得严但护学生；行事沉稳得不像普通教职工"
                       "（伏笔：家里似乎有不得了的人脉）",
            "affinity": 50, "label": "辅导员", "memory": [], "deeds": [],
            "known_to_player": False,  # 新档全员未结识：剧情登场才点亮关系网,
            "rels": {"白靖": "旧识，彼此心照不宣地装作不认识"},
        },
        {
            "id": "npc_guqingyan", "name": "顾清言", "world": WORLD_URBAN,
            "role": "学生会长·校花", "place": "京华大学",
            "likes": "情趣",
            "birthday": "5-5",
            "persona": "全校公认的门面担当，高冷克制的学霸会长；滴水不漏的外表下"
                       "藏着好胜心与极少示人的柔软",
            "affinity": 25, "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"宋语棠": "世家旧识，表面客气实则互相较劲"},
        },
        {
            "id": "npc_yeling", "name": "叶泠", "world": WORLD_URBAN,
            "role": "大一学妹·田径队", "place": "京华大学",
            "likes": "约会",
            "birthday": "11-3",
            "persona": "体育特长保送的元气学妹，直率莽撞、认死理，摔倒了也笑着爬起来；"
                       "一旦认定一个人就勇往直前",
            "affinity": 20, "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"陈芮": "选课系统里认识的饭搭子"},
        },
        {
            "id": "npc_songyutang", "name": "宋语棠", "world": WORLD_URBAN,
            "role": "千金大小姐", "place": "银杏商街",
            "likes": "情趣",
            "birthday": "7-18",
            "persona": "宋氏集团独女，隐瞒身份在京华大学\"体验普通人生\"；骄矜之下藏真诚，"
                       "对\"不图她什么\"的人毫无防备",
            "affinity": 20, "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"顾清言": "世家旧识，表面客气实则互相较劲", "沈曼": "自家集团的传奇总裁，又敬又怕"},
        },
        {
            "id": "npc_xuqin", "name": "许沁", "world": WORLD_URBAN,
            "role": "邻家姐姐·插画师", "place": "合租公寓",
            "likes": "特殊",
            "birthday": "10-24",
            "persona": "合租公寓隔壁的自由插画师，温柔慵懒，总\"不小心\"多做一人份宵夜；"
                       "深夜的阳台上好像藏着心事",
            "affinity": 55, "label": "邻居姐姐", "memory": [], "deeds": [],
            "known_to_player": False,  # 新档全员未结识：剧情登场才点亮关系网,
            "rels": {},
        },
        {
            "id": "npc_shenman", "name": "沈曼", "world": WORLD_URBAN,
            "role": "江湾集团总裁", "place": "龙脊CBD",
            "likes": "特殊",
            "birthday": "1-9",
            "persona": "二十九岁执掌江湾集团的传奇女总裁，雷厉风行、慧眼识人；"
                       "对\"有趣\"的年轻人格外有耐心",
            "affinity": 15, "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"宋语棠": "宋家那个嘴硬心软的小侄女"},
        },
        {
            "id": "npc_baijing", "name": "白靖", "world": WORLD_URBAN,
            "role": "神秘留学生", "place": "京华大学",
            "likes": "特殊",
            "birthday": "12-1",
            "persona": "学期中途插班的交换生，清冷疏离、来历成谜；观察力惊人，"
                       "似乎对\"系统的异常\"有自己的判断，只观察、先不动声色",
            "affinity": 30, "label": "神秘同窗", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"林慧": "旧识，彼此心照不宣地装作不认识"},
        },
    ]


PRESET_NPC_IDS = {n["id"] for n in default_npcs()}  # 主要角色不参与名册淘汰
MAX_NPCS = 30          # 名册上限；超出时按"最久未登场"淘汰剧情生成的人物
DEFAULT_URBAN_IDENTITY = "京华大学·大一新生"


def default_map() -> dict:
    """三级地图：世界 → 国家 → 城市/地点。
    countries: 世界层（国家节点）；cities: 国家→城市节点；urban: 城市内地点（含 city 字段）。
    坐标均为 0-100 百分比（绘制到 400x260 视窗）。
    """
    return {
        "countries": [
            {"name": "华夏", "x": 66, "y": 36, "discovered": True,
             "desc": "东方文明古国，高楼与古巷、繁华与烟火并存"},
        ],
        "cities": {
            "华夏": [
                {"name": "京都", "x": 48, "y": 24, "discovered": True,
                 "desc": "华夏首都，政治文化中心；古都风韵与现代气息在这里交融"},
                {"name": "魔都", "x": 74, "y": 58, "discovered": True,
                 "desc": "东方明珠，经济金融中心；不夜的繁华与外滩的浪漫"},
            ],
        },
        "urban": [
            # ---- 京都（北·首都） ----
            {"name": "京华大学", "city": "京都", "type": "campus", "discovered": True, "x": 30, "y": 32,
             "desc": "主角就读的百年学府：银杏大道、图书馆钟楼与湖畔长椅"},
            {"name": "合租公寓", "city": "京都", "type": "city", "discovered": True, "x": 18, "y": 62,
             "desc": "老城区的合租公寓，隔壁住着总“不小心”多做一人份宵夜的插画师"},
            {"name": "银杏商街", "city": "京都", "type": "city", "discovered": True, "x": 52, "y": 52,
             "desc": "京都最繁华的商业街：购物中心、电影院与不打烊的霓虹"},
            {"name": "紫宸美术馆", "city": "京都", "type": "culture", "discovered": False, "x": 38, "y": 14,
             "desc": "古都的美术馆，常年有免费展，安静得能听见笔触"},
            {"name": "燕山枫林", "city": "京都", "type": "nature", "discovered": False, "x": 14, "y": 20,
             "desc": "城郊的郊野公园：登山步道、枫叶溪谷与一夜星空"},
            {"name": "京都站", "city": "京都", "type": "transport", "discovered": False, "x": 68, "y": 76,
             "desc": "高铁枢纽：通往任何远方，也迎来每一个归来的人"},
            {"name": "回声Livehouse", "city": "京都", "type": "leisure", "discovered": False, "x": 60, "y": 84,
             "desc": "藏在胡同深处的地下音乐现场，独立乐队的声浪一夜不断"},
            # ---- 魔都（南·金融） ----
            {"name": "魔都大学", "city": "魔都", "type": "campus", "discovered": False, "x": 34, "y": 28,
             "desc": "魔都顶尖学府，与京华大学并称双子星；沈曼的母校"},
            {"name": "外滩滨江", "city": "魔都", "type": "leisure", "discovered": False, "x": 52, "y": 62,
             "desc": "海风咸咸的滨江步道：咖啡馆、旧书店、琴行与江畔灯火"},
            {"name": "龙脊CBD", "city": "魔都", "type": "city", "discovered": False, "x": 66, "y": 36,
             "desc": "摩天楼森林：实习、面试与深夜亮着的格子间"},
            {"name": "星愿游乐园", "city": "魔都", "type": "leisure", "discovered": False, "x": 78, "y": 50,
             "desc": "滨江的游乐园，摩天轮据说是全城告白成功率最高的地方"},
            {"name": "魔都南站", "city": "魔都", "type": "transport", "discovered": False, "x": 24, "y": 76,
             "desc": "南方铁路枢纽，连接魔都与京都的高铁始发站"},
            {"name": "渔人码头", "city": "魔都", "type": "nature", "discovered": False, "x": 84, "y": 78,
             "desc": "清晨的渔市与傍晚的灯塔，海钓者的秘密基地"},
            {"name": "云顶天文台", "city": "魔都", "type": "secret", "discovered": False, "x": 70, "y": 12,
             "desc": "废弃传闻不断的山顶天文台，近来却常在深夜亮起微光——系统异常信号的源头之一？"},
        ],
    }


def default_state(player_name: str, show_affinity: bool = True) -> dict:
    return {
        "version": 1,
        "revision": 0,
        "theme": THEME_ID,
        "player": {
            "name": player_name or "林川",
            "world": WORLD_URBAN,
            "location": {"world": WORLD_URBAN, "country": "华夏", "city": "京都", "place": "京华大学"},
            "identity": {WORLD_URBAN: DEFAULT_URBAN_IDENTITY},
            "places_memory": {WORLD_URBAN: "京华大学"},
            "technique": None,  # 初始天赋，领取后为 {"route","name","grade","turn"}
            "equipped": {slot: None for slot in EQUIP_SLOTS},
            "realm": START_REALM,  # 开局觉醒即"初露锋芒"
            "realm_progress": 5,
            "stats": {"体魄": 5, "头脑": 8, "情商": 6, "魅力": 6},
            "items": [
                {"name": CURRENCY, "desc": "系统商城通用货币", "count": 3},
                {"name": "系统抽奖券", "desc": "系统开局赠送的抽奖机会，在背包中使用即可抽取（新手奖池）。", "count": 10},
            ],
            "lottery": {"total_drawn": 0, "history": []},
        },
        "map": default_map(),
        "main_quest": {
            "title": QUEST_TITLE,
            "desc": QUEST_MILESTONES[START_REALM],
            "stage": START_REALM,
            "notes": [],
        },
        "side_quests": [],
        "time": {"day": 1, "slot": 0},  # 第1天·清晨
        "power": {"awakened": False, "stage": 0, "progress": 0,
                  "chat_bonus": {}},  # 超凡觉醒：境界/修为/灵犀日结账
        "hooks": [],   # 待消化剧情钩子：{"npc","stage","turn"}
        "achievements": [],  # 已解锁成就 id
        "dates": [],  # 约会回忆：{"npc","turn","ts","place","text"}
        "chats": {},  # 手机会话：{npc名: {"msgs": [{"ts","from","text"}]}}
        "facts": [],  # 长期事实账本（记忆工程）：承诺/伏笔/秘密
        "last_sign_in": None,
        "npcs": default_npcs(),
        "story": [],
        "summary": "",
        "gift_log": {"daily": {}, "weekly": {}},
        "settings": {"show_affinity": show_affinity},
        "inbox": [],
        "turn": 0,
        "created_at": now_iso(),
        "last_active": now_iso(),
    }


def _clear_run_records(state: dict) -> None:
    """题材切换时清空上一轮的可见记录：剧情、收件箱、任务、事实账本与人物记忆。

    保留：货币（已换算）与抽奖券、好感数值、名册本身。
    旧题材专属物品（已不在新商城行情、卖不掉也用不了的）一并清出背包，免得背包里堆旧世界的遗物。
    """
    state["story"] = []
    state["summary"] = ""
    state["inbox"] = []
    state["facts"] = []
    state["side_quests"] = []
    state.setdefault("main_quest", {})["notes"] = []
    for npc in state.get("npcs", []):
        npc["memory"] = []
        npc["deeds"] = []
        npc["known_memory"] = []
    from .shop import CATALOG_BY_NAME  # 函数级导入：shop 依赖本模块，顶层会循环
    keep = {CURRENCY, LOTTERY_TICKET} | set(CATALOG_BY_NAME)
    p = state.setdefault("player", {})
    p["items"] = [dict(i) for i in p.get("items", []) if i.get("name") in keep]


def _migrate_legacy_theme(state: dict) -> None:
    """旧修仙题材存档迁移到都市题材：换地图、清修仙身份、人物与物品按改名表走。

    旧剧情正文与归档在开局新游戏时统一清理（storage.replace_game）；
    本函数至少保证迁移后面板上不再残留上一轮的记录。
    """
    state["theme"] = THEME_ID
    state["map"] = default_map()
    p = state.setdefault("player", {})
    p["world"] = WORLD_URBAN
    p["location"] = {"world": WORLD_URBAN, "place": "京华大学"}
    p["places_memory"] = {WORLD_URBAN: "京华大学"}
    ident = p.setdefault("identity", {})
    ident.pop("xianxia", None)
    ident[WORLD_URBAN] = DEFAULT_URBAN_IDENTITY
    tech = p.get("technique")
    if isinstance(tech, dict) and tech.get("route") not in TECHNIQUE_ROUTES:
        p["technique"] = None  # 旧题材功法路线作废，重新领取新路线天赋
    # 旧题材人物退场；陈锐（男）→陈芮（女）按同 id 覆盖
    state["npcs"] = [n for n in state.get("npcs", []) if n.get("id") not in LEGACY_NPC_IDS]
    # 货币改名，财富随档迁移；其余旧题材物品保留为纪念品（不在新商城行情内）
    for it in p.get("items", []):
        if it.get("name") in LEGACY_ITEM_RENAMES:
            it["name"] = LEGACY_ITEM_RENAMES[it["name"]]
            it["desc"] = "系统商城通用货币"
    _clear_run_records(state)


# 旧版「青临市」单城地图的专属地点：三级地图（华夏·京都/魔都）重构后退役，
# normalize 时清出，防止以"已探明"身份混进新城市层；模型自创地点不受影响。
_RETIRED_PLACES = {
    "青临大学", "中央商圈", "滨海老街", "大学城体育馆", "海滨浴场",
    "星海游乐园", "云栖山公园", "江湾CBD", "青临夜市", "市立美术馆", "青临南站",
}


def normalize_state(state: dict) -> dict:
    """存档迁移：题材切换、补齐地图、位置、NPC（含新增）、装备栏字段。"""
    if state.get("theme") in LEGACY_THEME_IDS:
        _migrate_legacy_theme(state)

    if not isinstance(state.get("map"), dict):
        state["map"] = default_map()
    state["map"].pop("xianxia", None)  # 单世界正典：旧档的修仙界地图退役

    # 三级结构补齐
    dm = default_map()
    if not isinstance(state["map"].get("countries"), list):
        state["map"]["countries"] = dm["countries"]
    if not isinstance(state["map"].get("cities"), dict):
        state["map"]["cities"] = dm["cities"]
    if not isinstance(state["map"].get(WORLD_URBAN), list):
        state["map"][WORLD_URBAN] = []
    known = {p["name"] for p in state["map"][WORLD_URBAN]}
    for p in dm[WORLD_URBAN]:
        if p["name"] not in known:
            state["map"][WORLD_URBAN].append(dict(p))
    state["map"][WORLD_URBAN] = [p for p in state["map"][WORLD_URBAN]
                                 if p["name"] not in _RETIRED_PLACES]
    # 旧档地点缺 city 字段时按新正典回填；模型自创地点按命名前缀推断
    city_of = {p["name"]: p.get("city", "京都") for p in dm[WORLD_URBAN]}
    for p in state["map"][WORLD_URBAN]:
        if not p.get("city"):
            p["city"] = city_of.get(p["name"]) or (
                "魔都" if p["name"].startswith("魔都") else "京都")

    defaults_by_name = {n["name"]: n for n in default_npcs()}
    defaults_by_id = {n["id"]: n for n in default_npcs()}
    state["npcs"] = [n for n in state.get("npcs", []) if n.get("id") not in LEGACY_NPC_IDS]
    existing_ids = {n.get("id") for n in state["npcs"]}
    existing_names = {n.get("name") for n in state["npcs"]}
    for npc in state.get("npcs", []):
        # 同 id 的预设人物以预设档案为底（改名/改世界覆盖旧档），保留记忆与好感
        preset = defaults_by_id.get(npc.get("id"))
        if preset is not None:
            for key in ("name", "world", "role", "persona", "place"):
                npc[key] = preset[key]
    for pid, npc in defaults_by_id.items():
        if pid not in existing_ids and npc["name"] not in existing_names:
            state["npcs"].append(dict(npc))
    for npc in state.get("npcs", []):
        npc["world"] = WORLD_URBAN  # 单世界正典：旧档修仙界人物一并迁回都市
        npc.setdefault("likes", defaults_by_name.get(npc.get("name", ""), {}).get("likes", ""))
        if npc.get("likes") == "手作":  # 手作分类已下线，偏好随新目录迁到情趣
            npc["likes"] = "情趣"
        if not npc.get("place"):
            npc["place"] = defaults_by_name.get(npc.get("name", ""), {}).get("place", "")
        npc.setdefault("last_seen_turn", -1)
        npc.setdefault("deeds", [])
        npc.setdefault("known_to_player", npc.get("last_seen_turn", -1) >= 0)
        npc.setdefault("known_rels", {k: v for k, v in npc.get("rels", {}).items()
                                     if npc.get("name") in ("陈芮", "苏晚晴")})
        npc.setdefault("known_memory", [])
    p = state.setdefault("player", {})
    eq = p.setdefault("equipped", {})
    for slot in EQUIP_SLOTS:
        eq.setdefault(slot, None)
    # 旧装备槽名与不在新加成表内的装备退役退包
    for slot in list(eq.keys()):
        if slot not in EQUIP_SLOTS:
            retired = eq.pop(slot)
            if retired:
                p.setdefault("items", []).append({"name": retired, "desc": "旧装备，已无加成", "count": 1})
    for slot, name in eq.items():
        if name and name not in EQUIPMENT_BONUS:
            eq[slot] = None
            p.setdefault("items", []).append({"name": name, "desc": "旧装备，已无加成", "count": 1})
    ident = p.setdefault("identity", {})
    ident.pop("xianxia", None)
    # 旧档身份里已不存在的校名随地图重构一并更名（保留其余叙述部分）
    if isinstance(ident.get(WORLD_URBAN), str) and "青临大学" in ident[WORLD_URBAN]:
        ident[WORLD_URBAN] = ident[WORLD_URBAN].replace("青临大学", "京华大学")
    if not ident.get(WORLD_URBAN):
        ident[WORLD_URBAN] = DEFAULT_URBAN_IDENTITY
    p.setdefault("lottery", {"total_drawn": 0, "history": []})
    p.setdefault("technique", None)
    mem = p.get("places_memory") or {}
    mem.pop("xianxia", None)
    p["places_memory"] = mem
    loc = p.get("location")
    names = {pl["name"] for pl in state["map"][WORLD_URBAN]}
    place = loc.get("place") if isinstance(loc, dict) else None
    if not isinstance(loc, dict) or loc.get("world") != WORLD_URBAN or place not in names:
        place = place if place in names else "京华大学"
        city = next((pl.get("city", "京都") for pl in state["map"][WORLD_URBAN]
                     if pl["name"] == place), "京都")
        p["location"] = {"world": WORLD_URBAN, "country": "华夏", "city": city, "place": place}
        # 人已在此地，它必然已探明
        for pl in state["map"][WORLD_URBAN]:
            if pl["name"] == place:
                pl["discovered"] = True
    else:
        loc.setdefault("country", "华夏")
        loc.setdefault("city", next(
            (pl.get("city", "京都") for pl in state["map"][WORLD_URBAN]
             if pl["name"] == loc.get("place")), "京都"))
    if p["places_memory"].get(WORLD_URBAN) not in names:
        p["places_memory"][WORLD_URBAN] = p["location"]["place"]
    state.setdefault("facts", [])
    state.setdefault("dates", [])
    state.setdefault("chats", {})
    state.setdefault("time", {"day": 1, "slot": 0})
    state.setdefault("power", {"awakened": False, "stage": 0, "progress": 0, "chat_bonus": {}})
    state.setdefault("hooks", [])
    # 修罗场机制已下线：清掉旧档的残留字段与钩子
    state.pop("drama_day", None)
    state.pop("drama_survived", None)
    state["hooks"] = [h for h in state["hooks"] if h.get("type") != "修罗场"]
    state.setdefault("achievements", [])
    state.setdefault("gift_log", {"daily": {}, "weekly": {}})
    for npc in state.get("npcs", []):
        npc.setdefault("birthday", defaults_by_name.get(npc.get("name", ""), {}).get("birthday", ""))
    # 旧档事实补出类型与了结标记：承诺/伏笔要常驻提示词，不能按入账先后被挤掉
    for fact in state["facts"]:
        if isinstance(fact, dict):
            fact.setdefault("kind", memory.classify_fact(fact.get("text", "")))
            fact.setdefault("closed", None)
    refresh_main_quest(state)
    state.setdefault("settings", {}).setdefault("show_affinity", True)
    state.setdefault("revision", 0)
    return state


def effective_stats(state: dict) -> dict[str, int]:
    """基础属性 + 穿搭加成。"""
    stats = dict(state["player"].get("stats", {}))
    for slot, name in (state["player"].get("equipped") or {}).items():
        bonus = EQUIPMENT_BONUS.get(name or "")
        if not bonus:
            continue
        for k, v in bonus["stats"].items():
            stats[k] = clamp(stats.get(k, 0) + v, 0, 99)  # 与属性课程同一上限口径
    return stats


def find_npc(state: dict, name: str) -> dict | None:
    name = (name or "").strip()
    if not name:
        return None
    for npc in state["npcs"]:
        if npc["name"] == name:
            return npc
    for npc in state["npcs"]:
        if name in npc["name"] or npc["name"] in name:
            return npc
    return None


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def realm_name(state: dict) -> str:
    return REALMS[state["player"]["realm"]]


def refresh_main_quest(state: dict) -> None:
    """主线目标由等级主干派生：stage/title/desc 只跟随真实等级，模型改不动。

    旧档里被 quest_progress 覆盖过的 desc 不丢弃，转存进「近况」留痕。
    """
    mq = state.setdefault("main_quest", {})
    try:
        idx = int(state["player"].get("realm", 0))
    except (TypeError, ValueError):
        idx = 0
    idx = clamp(idx, 0, len(QUEST_MILESTONES) - 1)
    goal = QUEST_MILESTONES[idx]
    old = str(mq.get("desc") or "")
    mq["title"] = QUEST_TITLE
    mq["stage"] = idx
    if old and old != goal:
        notes = mq.setdefault("notes", [])
        note = _clean_legacy_desc(old)
        if note not in notes:
            mq["notes"] = (notes + [note])[-MAIN_QUEST_NOTES:]
    mq["desc"] = goal


def _clean_legacy_desc(text: str) -> str:
    return str(text or "").replace("<", "").replace(">", "").strip()[:120]


def identity_of(state: dict, world: str) -> str:
    """主角的社会身份；未落档时返回占位串。"""
    return (state["player"].get("identity") or {}).get(world) or "尚无正式身份"


def technique_of(state: dict) -> dict | None:
    """已录入的初始天赋；未领取时返回 None。"""
    tech = state["player"].get("technique")
    return tech if isinstance(tech, dict) and tech.get("name") else None
