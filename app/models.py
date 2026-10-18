"""游戏状态模型：以 dict 为核心，提供默认值与操作工具。"""
from datetime import datetime, timezone, timedelta
from copy import deepcopy

from . import memory

REALMS = ["凡人", "炼气", "筑基", "金丹", "元婴", "化神", "炼虚", "合体", "大乘", "渡劫", "飞升"]

# 主线（设定集定案"大主线＝渡劫飞升"）：目标文本按境界主干派生，索引与 REALMS 一一对应。
# 只能靠真实突破推进——模型的 quest_progress 碰不到 title/stage/desc，只能记进展说明。
QUEST_TITLE = "渡劫飞升"
QUEST_MILESTONES = [
    "尚未踏入修行：表达修炼意向、领取初始功法，才算上了这条路。",
    "炼气：打熬根基——在一界立足、明自己要走的路，修为水到渠成方可言筑基。",
    "筑基：筑就道基——灵压脱凡，宗门与坊市才会正眼看你；需灵材与引路之人。",
    "金丹：凝练金丹——丹药灵材之外，你得有自己的一条道；机缘与代价同行。",
    "元婴：元婴出窍——神魂离体，跨州远行初具自保之力；此境之后敌手渐真。",
    "化神：神识化形——外放察异动，禁地边缘不再是死地；一州之事你已能插手。",
    "炼虚：窥见空间之理——远行不再依赖他人传送，阵法禁制也拦不住你。",
    "合体：法体合一——可与一方巨擘并列行事，宗门之事会主动找上门。",
    "大乘：道行臻至极限——一州一地已困不住你，此界的因果该由你定。",
    "渡劫：天劫临身——成则飞升，败则道消；这一步不靠刷数值，靠积累与选择。",
    "飞升：此界之事已有结论——离开玄灵界，路上的承诺与仇怨该有个交代。",
]
MAIN_QUEST_NOTES = 3  # 任务面板"近况"保留的条数
START_REALM = 1       # 开局系统觉醒即已引气入体（炼气）；主线起始档位与它同源，不会写歪

WORLD_URBAN = "urban"
WORLD_XIANXIA = "xianxia"
WORLD_NAMES = {WORLD_URBAN: "都市", WORLD_XIANXIA: "修仙界"}

EQUIP_SLOTS = ["武器", "防具", "法宝", "足履"]

CURRENCY = "下品灵石"  # 修仙界硬通货，也是商城的计价单位
LOTTERY_TICKET = "系统抽奖券"

# 系统专属物品：只能经系统通道（开局发放、抽奖扣除）增减。
# 剧情契约不得发放或扣除它们——否则模型一次申报就能凭空造出上千次抽奖，
# 再借奖池里的在售物品半价卖出，把经济系统整条洗空。
SYSTEM_ITEMS = frozenset({LOTTERY_TICKET})

# 初始功法（设定集 V1.2 §4.1）：六条路线，品质固定为初始范围内最高的上品
TECHNIQUE_ROUTES = ["剑修", "体修", "法修", "魔修", "丹修", "阵符修"]
INITIAL_TECHNIQUE_GRADE = "上品"

# 装备加成表（商城法器共用的单一数据源）
EQUIPMENT_BONUS = {
    "玄铁短剑": {"slot": "武器", "stats": {"体魄": 2}},
    "青霜剑": {"slot": "武器", "stats": {"体魄": 4}},
    "护心镜": {"slot": "防具", "stats": {"体魄": 3}},
    "避水珠": {"slot": "法宝", "stats": {"神识": 3}},
    "踏云靴": {"slot": "足履", "stats": {"体魄": 1, "魅力": 1}},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def game_today() -> str:
    """签到统一按中国时区结算，不依赖浏览器或宿主时区。"""
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def public_state(state: dict) -> dict:
    """玩家已知档案与主持人后台档案隔离，秘密不传给浏览器。"""
    result = deepcopy(state)
    result["server_date"] = game_today()
    visible = []
    for npc in result["npcs"]:
        known = npc.get("known_to_player", npc.get("world") == WORLD_URBAN
                        or npc.get("last_seen_turn", -1) >= 0)
        if not known:
            continue
        visible.append({
            k: npc.get(k) for k in ("id", "name", "world", "role", "place", "affinity", "label")
        } | {"persona": npc.get("public_persona") or f"已知身份：{npc['role']}。更多经历有待了解。",
             "rels": npc.get("known_rels", {}), "memory": npc.get("known_memory", [])})
    result["npcs"] = visible
    return result


def default_npcs() -> list[dict]:
    return [
        {
            "id": "npc_chenrui", "name": "陈锐", "world": WORLD_URBAN,
            "role": "死党同桌", "persona": "话多义气，嘴碎但可靠，最早察觉主角的变化，好奇心重",
            "place": "青临市",
            "affinity": 70, "label": "死党", "memory": [], "deeds": [],
            "rels": {"苏晚晴": "老同学，互相熟但爱斗嘴"},
        },
        {
            "id": "npc_suwanqing", "name": "苏晚晴", "world": WORLD_URBAN,
            "role": "青梅竹马", "persona": "聪明敏锐，外冷内柔，观察力强，对主角的异常隐隐起疑又不敢深问",
            "place": "青临市",
            "affinity": 60, "label": "青梅竹马", "memory": [], "deeds": [], "rels": {"陈锐": "老同学，互相熟但爱斗嘴"},
        },
        {
            "id": "npc_linhui", "name": "林慧", "world": WORLD_URBAN,
            "role": "班主任", "persona": "严肃周到，管得严但护学生；言行间偶尔流露出不属于普通人的沉稳（伏笔：隐藏修行者）",
            "place": "青临市",
            "affinity": 50, "label": "班主任", "memory": [], "deeds": [], "rels": {},
        },
        {
            "id": "npc_xuanyangzi", "name": "玄阳子", "world": WORLD_XIANXIA,
            "role": "青玄宗执剑长老", "persona": "青禾州地方宗门的执剑长老，话少而重，偶尔下山云游，研究古阵与地方史；并不天然知道主角能跨界",
            "place": "青玄宗·山门",
            "affinity": 55, "label": "闻名未谋面", "memory": [], "deeds": [], "rels": {"洛清衣": "师徒，器重其剑道天赋"},
        },
        {
            "id": "npc_luoqingyi", "name": "洛清衣", "world": WORLD_XIANXIA,
            "role": "青玄宗内门弟子", "persona": "青玄宗内门弟子，剑道天才，外冷内热，口是心非，常在关键处出手护短",
            "place": "演武场",
            "affinity": 45, "label": "尚未结识", "memory": [], "deeds": [], "rels": {"赵擎": "同门竞争，嫌其张扬", "玄阳子": "师徒，敬重"},
        },
        {
            "id": "npc_zhaoqing", "name": "赵擎", "world": WORLD_XIANXIA,
            "role": "青玄宗外门弟子", "persona": "世家出身的天才弟子，天资亦佳，处处争先，待人倨傲，视散修如草芥",
            "place": "青玄宗·外门居",
            "affinity": 30, "label": "尚未结识", "memory": [], "deeds": [], "rels": {"洛清衣": "同门竞争，屡屡被压一头而心生不忿"},
        },
        {
            "id": "npc_baijing", "name": "白靖", "world": WORLD_URBAN,
            "role": "神秘转学生", "persona": "隐修世家出身的少年，转学而来，气质清冷疏离；只有观察到具体异常后才会起疑，不会凭空看穿系统",
            "place": "青临市",
            "affinity": 35, "label": "神秘同窗", "memory": [], "deeds": [], "rels": {"林慧": "旧识，彼此心照不宣地装作不认识"},
        },
        {
            "id": "npc_zhoumu", "name": "周母", "world": WORLD_URBAN,
            "role": "母亲", "persona": "温柔操心的普通母亲，烧得一手好菜，最近总觉得儿子\"长个了、饭量见长\"，隐隐担心又不愿多问",
            "place": "青临市",
            "affinity": 85, "label": "母亲", "memory": [], "deeds": [], "rels": {},
        },
        {
            "id": "npc_molao", "name": "莫老", "world": WORLD_XIANXIA,
            "role": "丹房管事", "persona": "青玄宗丹房的市侩老匠，认灵石不认人，但对手艺有底线；指点炼丹时意外地耐心",
            "place": "青玄宗·丹房",
            "affinity": 40, "label": "丹房管事", "memory": [], "deeds": [], "rels": {"玄阳子": "老相识，互相给面子"},
        },
        {
            "id": "npc_xueluo", "name": "血萝", "world": WORLD_XIANXIA,
            "role": "魔道修士", "persona": "出没幽冥古道（通往幽墟州方向）的魔道女子，笑里藏刀、亦敌亦友，关注来历不明的外乡修士，但不能无依据识别跨界者",
            "place": "幽冥古道",
            "affinity": 25, "label": "危险的注视", "memory": [], "deeds": [], "rels": {},
        },
    ]


PRESET_NPC_IDS = {n["id"] for n in default_npcs()}  # 主角团不参与名册淘汰
MAX_NPCS = 30          # 名册上限；超出时按"最久未登场"淘汰剧情生成的人物
DEFAULT_URBAN_IDENTITY = "临江三中·高三学生"

# 世界正典改名表：旧存档里的历史地名迁移到现行正典（青玄宗版）
LEGACY_PLACE_RENAMES = {
    "青荒野岭": "落星荒野",
    "太虚宗·山门": "青玄宗·山门",
    "外门弟子居": "青玄宗·外门居",
    "太虚宗·丹房": "青玄宗·丹房",
    "太虚坊市": "青禾坊市",
    "黑石城": "白溪镇",
    "落霞镇": "白溪镇",
    "剑冢": "古剑冢",
}


def default_map() -> dict:
    """两界地图：坐标为 0-100 百分比（绘制到 400x260 视窗）。"""
    return {
        "urban": [
            {"name": "青临市", "type": "city", "desc": "主角家乡所在的滨海城市，临江三中、老街与江畔都藏在它的烟火气里。", "discovered": True, "x": 28, "y": 62},
            {"name": "东澜自由港", "type": "city", "desc": "东海岸最繁华的自由贸易港，三教九流汇聚，传闻也有修行者的暗线。", "discovered": True, "x": 72, "y": 55},
            {"name": "云京古都", "type": "city", "desc": "内陆千年古都，皇城遗迹与现代都市交错，地下埋着说不清的东西。", "discovered": True, "x": 44, "y": 44},
            {"name": "北漠雪原", "type": "wild", "desc": "极北苦寒之地，常年风雪，传闻冻土下埋着上古遗骸。", "discovered": False, "x": 18, "y": 22},
            {"name": "西岭古国", "type": "secret", "desc": "西部群山深处与世隔绝的古国，据说仍供奉着\"旧神\"。", "discovered": False, "x": 10, "y": 34},
            {"name": "沧溟群岛", "type": "sea", "desc": "外海深处的岛链，海图上标记寥寥，归途者十不存一。", "discovered": False, "x": 86, "y": 13},
            {"name": "极渊海峡", "type": "sea", "desc": "两洋交汇的深渊海峡，暗流汹涌，寻常船只绕行之地。", "discovered": False, "x": 58, "y": 20},
            {"name": "无风带", "type": "sea", "desc": "东南海域的死寂之海，罗盘失灵、连风都会消失的地方。", "discovered": False, "x": 90, "y": 80},
            {"name": "雾隐山庄", "type": "secret", "desc": "都市背后的隐世修行者山庄，寻常人根本找不到入口。", "discovered": False, "x": 42, "y": 72},
            {"name": "星穹天文台", "type": "city", "desc": "建在山顶的天文台，近年频繁记录到\"不该存在的星象\"。", "discovered": False, "x": 66, "y": 26},
        ],
        "xianxia": [
            {"name": "落星荒野", "type": "wild", "desc": "系统首次穿越的落点：青禾州古荒野岭，灵气出人意料地充盈，远处偶有兽吼。", "discovered": True, "x": 76, "y": 72},
            {"name": "灵草溪谷", "type": "wild", "desc": "荒野西侧灵溪山的山腰溪谷，生着成片低阶灵草，采药人偶尔出没。", "discovered": False, "x": 66, "y": 78},
            {"name": "青石村", "type": "town", "desc": "溪畔的凡人小村，青瓦土墙，民风淳朴，偶有修士途经讨水。", "discovered": False, "x": 82, "y": 82},
            {"name": "白溪镇", "type": "town", "desc": "荒野以东最近的凡人聚居地，边陲小镇，鱼龙混杂、消息灵通。", "discovered": False, "x": 88, "y": 62},
            {"name": "青禾坊市", "type": "town", "desc": "青禾州最大的修仙者集市，丹药法器灵石应有尽有。", "discovered": False, "x": 62, "y": 58},
            {"name": "灵溪山", "type": "wild", "desc": "州内灵脉之一，山间灵雾缭绕，山腰即灵草溪谷。", "discovered": False, "x": 58, "y": 76},
            {"name": "黑风岭", "type": "wild", "desc": "青禾州著名的凶地，妖兽盘踞，传闻岭中有前人洞府。", "discovered": False, "x": 74, "y": 50},
            {"name": "青玄宗·山门", "type": "sect", "desc": "青禾州地方宗门青玄宗的入口，云阶千级，剑气隐隐。", "discovered": False, "x": 50, "y": 80},
            {"name": "青玄宗·外门居", "type": "sect", "desc": "青玄宗外门弟子聚居的屋舍群，人声与剑鸣不绝。", "discovered": False, "x": 38, "y": 58},
            {"name": "演武场", "type": "sect", "desc": "青玄宗外门弟子日日切磋之地，剑气纵横。", "discovered": False, "x": 46, "y": 64},
            {"name": "藏经阁", "type": "secret", "desc": "青玄宗典籍所在，外门弟子未经允许不得踏入三层以上。", "discovered": False, "x": 56, "y": 26},
            {"name": "后山禁地", "type": "secret", "desc": "青玄宗后山，常年雾锁，弟子禁足，据说镇压着宗门最深的秘密。", "discovered": False, "x": 18, "y": 20},
            {"name": "青玄宗·丹房", "type": "sect", "desc": "青玄宗丹房，炉火终年不熄，丹香飘出十里。", "discovered": False, "x": 48, "y": 47},
            {"name": "黑水泽", "type": "wild", "desc": "州界边缘瘴气弥漫的大泽，妖兽横行，也是亡命之徒的藏身处。", "discovered": False, "x": 12, "y": 50},
            {"name": "幽冥古道", "type": "secret", "desc": "通往幽墟州方向的古道，正道修士的禁忌之路。", "discovered": False, "x": 86, "y": 34},
            {"name": "古剑冢", "type": "wild", "desc": "云岚州方向的埋剑荒谷，剑鸣不绝，剑修心中的圣地与坟墓。", "discovered": False, "x": 60, "y": 12},
        ],
    }


def default_state(player_name: str, show_affinity: bool = True) -> dict:
    return {
        "version": 1,
        "revision": 0,
        "player": {
            "name": player_name or "林川",
            "world": WORLD_URBAN,
            "location": {"world": WORLD_URBAN, "place": "青临市"},
            "identity": {WORLD_URBAN: DEFAULT_URBAN_IDENTITY, WORLD_XIANXIA: ""},
            "places_memory": {WORLD_URBAN: "青临市", WORLD_XIANXIA: ""},
            "technique": None,  # 初始功法，领取后为 {"route","name","grade","turn"}
            "equipped": {slot: None for slot in EQUIP_SLOTS},
            "realm": START_REALM,  # 开局觉醒即踏入炼气
            "realm_progress": 5,
            "stats": {"体魄": 5, "神识": 6, "悟性": 8, "魅力": 6},
            "items": [
                {"name": "下品灵石", "desc": "修仙界通用货币", "count": 3},
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
        "facts": [],  # 长期事实账本（记忆工程）：承诺/伏笔/秘密
        "last_sign_in": None,
        "npcs": default_npcs(),
        "story": [],
        "summary": "",
        "settings": {"show_affinity": show_affinity},
        "inbox": [],
        "turn": 0,
        "created_at": now_iso(),
        "last_active": now_iso(),
    }


def normalize_state(state: dict) -> dict:
    """旧存档迁移：地名改名去重、补齐地图、位置、NPC（含新增）、装备栏字段。"""
    if not isinstance(state.get("map"), dict):
        state["map"] = default_map()

    # 历史地名迁移到现行正典（如 青荒野岭→落星荒野），改名后按名去重（已探明优先保留）
    for w in (WORLD_URBAN, WORLD_XIANXIA):
        places = state["map"].get(w)
        if not isinstance(places, list):
            continue
        for p in places:
            if p.get("name") in LEGACY_PLACE_RENAMES:
                p["name"] = LEGACY_PLACE_RENAMES[p["name"]]
        merged: list[dict] = []
        for p in places:
            dup = next((m for m in merged if m["name"] == p["name"]), None)
            if dup is None:
                merged.append(p)
            else:
                dup["discovered"] = dup.get("discovered") or p.get("discovered")
        state["map"][w] = merged

    for w in (WORLD_URBAN, WORLD_XIANXIA):
        if not isinstance(state["map"].get(w), list):
            state["map"][w] = []
        known = {p["name"] for p in state["map"][w]}
        for p in default_map()[w]:
            if p["name"] not in known:
                state["map"][w].append(dict(p))
    defaults_by_name = {n["name"]: n for n in default_npcs()}
    existing_names = {n.get("name") for n in state.get("npcs", [])}
    for name, npc in defaults_by_name.items():
        if name not in existing_names:
            state.setdefault("npcs", []).append(dict(npc))
    for npc in state.get("npcs", []):
        if not npc.get("place"):
            npc["place"] = defaults_by_name.get(npc.get("name", ""), {}).get("place", "")
        elif npc["place"] in LEGACY_PLACE_RENAMES:
            npc["place"] = LEGACY_PLACE_RENAMES[npc["place"]]
        npc.setdefault("last_seen_turn", -1)
        npc.setdefault("deeds", [])
        npc.setdefault("known_to_player", npc.get("world") == WORLD_URBAN
                       or npc.get("last_seen_turn", -1) >= 0)
        npc.setdefault("known_rels", {k: v for k, v in npc.get("rels", {}).items()
                                     if npc.get("name") in ("陈锐", "苏晚晴")})
        npc.setdefault("known_memory", [])
    p = state.setdefault("player", {})
    eq = p.setdefault("equipped", {})
    for slot in EQUIP_SLOTS:
        eq.setdefault(slot, None)
    ident = p.setdefault("identity", {})
    for w in (WORLD_URBAN, WORLD_XIANXIA):
        ident.setdefault(w, "")
    if not ident[WORLD_URBAN]:
        ident[WORLD_URBAN] = DEFAULT_URBAN_IDENTITY
    # 身份文案里的旧宗门名一并迁移
    for w in (WORLD_URBAN, WORLD_XIANXIA):
        for old, new in (("太虚宗", "青玄宗"),):
            if old in (ident.get(w) or ""):
                ident[w] = ident[w].replace(old, new)
    p.setdefault("lottery", {"total_drawn": 0, "history": []})
    p.setdefault("technique", None)
    p.setdefault("places_memory", {})
    loc = p.get("location")
    if isinstance(loc, dict) and loc.get("place") in LEGACY_PLACE_RENAMES:
        loc["place"] = LEGACY_PLACE_RENAMES[loc["place"]]
    mem = p.get("places_memory") or {}
    for w in (WORLD_URBAN, WORLD_XIANXIA):
        if mem.get(w) in LEGACY_PLACE_RENAMES:
            mem[w] = LEGACY_PLACE_RENAMES[mem[w]]
    if not isinstance(loc, dict) or not loc.get("place"):
        world = p.get("world") if p.get("world") in (WORLD_URBAN, WORLD_XIANXIA) else WORLD_URBAN
        place = next((pl["name"] for pl in state["map"][world] if pl.get("discovered")), "青临市")
        p["location"] = {"world": world, "place": place}
    state.setdefault("facts", [])
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
    """基础属性 + 装备加成。"""
    stats = dict(state["player"].get("stats", {}))
    for slot, name in (state["player"].get("equipped") or {}).items():
        bonus = EQUIPMENT_BONUS.get(name or "")
        if not bonus:
            continue
        for k, v in bonus["stats"].items():
            stats[k] = stats.get(k, 0) + v
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
    """主线目标由境界主干派生：stage/title/desc 只跟随真实境界，模型改不动。

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
    """主角在某一界的社会身份；未落档时返回占位串。"""
    return (state["player"].get("identity") or {}).get(world) or "尚无正式身份"


def technique_of(state: dict) -> dict | None:
    """已录入的初始功法；未领取时返回 None。"""
    tech = state["player"].get("technique")
    return tech if isinstance(tech, dict) and tech.get("name") else None
