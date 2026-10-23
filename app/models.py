"""游戏状态模型：以 dict 为核心，提供默认值与操作工具。"""
from datetime import date, datetime, timezone, timedelta
from copy import deepcopy

from . import memory

# 系统等级（题材：都市恋爱）。这是成长目标；剧情章节由 campaign 单独记录。
REALMS = ["无名路人", "初露锋芒", "校园新星", "崭露头角", "风云人物", "校园传奇",
          "城市新锐", "万众瞩目", "众星捧月", "城市传奇", "人生赢家"]

# 保留 main_quest 字段兼容已有存档，含义为等级成长目标，不再承担剧情章节。
QUEST_TITLE = "成长目标 · 人生赢家"
QUEST_MILESTONES = [
    "系统尚未觉醒：大一新生拖着行李箱的寻常日常——直到报到日的夜晚，一切开始改变。",
    "初露锋芒：大一入学，大学生活从零开局。把成绩、身体与自信先立起来，让改变被看见。",
    "校园新星：社团、竞赛或一场惊艳全场的亮相——让人记住你的名字。",
    "崭露头角：校园之外初试身手，兼职、创业或一次漂亮的出手，攒下第一份家底。",
    "风云人物：感情线与事业线交织成网，麻烦与青睐一起找上门——学会应付人心。",
    "校园传奇：让一件重要的校园作品真正完成，把成长落在共同经历上。",
    "城市新锐：在城市里尝试新的机会——身份、收入与影响力都靠具体经历积累。",
    "万众瞩目：聚光灯照过来的时代，一举一动都有回响；护住不想失去的东西。",
    "众星捧月：身边群星环绕，真心与假意交错——分清谁是路灯，谁是月亮。",
    "城市传奇：从京都到魔都，处处留下你的传说；系统交付最后的机会与代价。",
    "人生赢家：成长等级已经登顶。校园篇章仍可选择参与，事业、关系与人生目标由你继续定义。",
]
MAIN_QUEST_NOTES = 3  # 任务面板"近况"保留的条数
START_REALM = 1       # 开局系统觉醒即"初露锋芒"；主线起始档位与它同源，不会写歪

WORLD_URBAN = "urban"
WORLD_NAMES = {WORLD_URBAN: "都市"}

EQUIP_SLOTS = ["上装", "鞋履", "配饰", "座驾"]

CURRENCY = "系统积分"  # 系统商城、签到与成长奖励
CASH = "华夏币"        # 现实生活、旅行、事业与投资，不能与系统积分混用
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

NPC_SEED_AFFINITY = {
    "郭瑞莹": 60,
    "梁雅婷": 70,
    "小朱": 50,
    "雅倩": 25,
    "王德芙": 20,
    "花碎花": 20,
    "邓碧瑶": 55,
    "炭炭": 15,
    "走路摇": 30,
    "张琦": 30,
    "绿小林子": 25,
    "韩冰": 25,
    "小杨": 25,
    "车车": 15,
    "灵儿": 15,
    "傲寒": 20,
    "杨幂": 10,
    "刘亦菲": 10,
    "宋轶": 10,
    "杨超越": 10,
    "章若楠": 10,
    "赵丽颖": 10,
    "赵今麦": 10,
    "迪丽热巴": 10,
    "张靓颖": 10,
    "邓紫棋": 10,
    "单依纯": 10,
    "鞠婧祎": 10,
    "乌苏苏": 25,
    "乐乐": 25,
    "吃不饱": 25,
    "吐泡泡": 25,
    "歪歪": 25,
    "小新": 25,
    "慕慕": 25,
}

# 好感阶段（关系深度主干）：阈值与标签一一对应，跨档时系统公告
AFFINITY_STAGES = [(0, "初识"), (25, "熟识"), (50, "朋友"), (70, "亲近"), (85, "心动"), (100, "羁绊")]


def affinity_stage(affinity: int) -> str:
    """好感数值对应的阶段标签。"""
    stage = AFFINITY_STAGES[0][1]
    for threshold, label in AFFINITY_STAGES:
        if affinity >= threshold:
            stage = label
    return stage
GIFT_CATEGORIES = ("约会", "情趣", "特殊")  # 可赠送物品的分类

# 地点类型白名单（new_places.type 只接受这些枚举，防注入也统一前端图例）
PLACE_TYPES_KNOWN = ("campus", "city", "leisure", "nature", "culture", "transport", "secret")


def is_romanceable(npc: dict) -> bool:
    """是否可进入恋爱线（约会/恋爱成就）。角色边界的单一事实源——
    成就、约会判定都必须走这里，别在多处各写一遍条件。"""
    return npc.get("role") != "母亲"

# ---------- 好感护栏与人物生活状态 ----------
AFFINITY_TURN_CAP = 10     # 普通回合：单 NPC 累计变化上限
AFFINITY_DATE_CAP = 15     # 约会回合：约会对象的上限
# 新登记人物的初始好感上限：防止模型用一句“旧识”直接造出亲近/羁绊；
# 旧识重逢走归档恢复，不受此限。
NEW_NPC_AFFINITY_CAP = 50

# ---------- NPC 生活状态 ----------
# 新人物还没有共同经历；目标从三位主线搭档的公开心愿起步，其余留待剧情揭示。
NPC_GOALS = {
    "梁雅婷": "在作品上写下自己的名字",
    "郭瑞莹": "试一次不靠完美演奏也能表达自己的合作",
    "邓碧瑶": "从语音里的队友走到现实里的伙伴",
}
DEFAULT_BOUNDARIES = {
    "principles": "不接受被欺骗；重要的事要当面说清",
    "boundary": "关系推进需要真实相处与明确同意",
    "romance_style": "慢热",
}
NPC_BOUNDARIES = {
    "梁雅婷": {
        "principles": "把话说开，不接受被当成备选",
        "boundary": "不喜欢被瞒着做决定",
        "romance_style": "专一",
    },
    "郭瑞莹": {
        "principles": "重要的事要坦白，讨厌被替她做决定",
        "boundary": "不接受长期隐瞒与敷衍",
        "romance_style": "慢热但认真",
    },
    "邓碧瑶": {
        "principles": "线上线下的承诺一样算数",
        "boundary": "不接受只把她当树洞",
        "romance_style": "需要确定感",
    },
}


def default_life(npc: dict, day: int = 1) -> dict:
    return {
        "goal": NPC_GOALS.get(npc.get("name", ""), ""),
        "status": "如常生活",
        "mood": "平静",
        "next": None,
        "updated_day": max(1, int(day or 1)),
    }


def ensure_life(npc: dict, day: int = 1) -> dict:
    """补齐 NPC 的结构化生活状态；next 只在有具体安排时存在。"""
    life = npc.get("life")
    if not isinstance(life, dict):
        life = {}
    base = default_life(npc, day)
    for key in ("goal", "status", "mood"):
        value = life.get(key)
        life[key] = (value[:80] if isinstance(value, str) and value.strip() else base[key])
    next_event = life.get("next")
    if isinstance(next_event, dict):
        try:
            next_day = int(next_event.get("day", 0))
            next_slot = int(next_event.get("slot", 0))
        except (TypeError, ValueError):
            next_event = None
        else:
            text = str(next_event.get("text", "")).strip()[:60]
            next_event = ({
                "day": max(1, next_day),
                "slot": clamp(next_slot, 0, 4),
                "place": str(next_event.get("place", ""))[:20],
                "text": text,
            } if text and next_day >= 1 else None)
    else:
        next_event = None
    life["next"] = next_event
    try:
        life["updated_day"] = max(1, int(life.get("updated_day", day)))
    except (TypeError, ValueError):
        life["updated_day"] = max(1, int(day or 1))
    npc["life"] = life
    return life


def default_boundaries(npc: dict) -> dict:
    return dict(NPC_BOUNDARIES.get(npc.get("name", ""), DEFAULT_BOUNDARIES))


def ensure_boundaries(npc: dict) -> dict:
    """补齐角色的原则、边界与恋爱观；旧档只用默认值，不凭空编造秘密。"""
    data = npc.get("boundaries")
    if not isinstance(data, dict):
        data = {}
    base = default_boundaries(npc)
    for key in ("principles", "boundary", "romance_style"):
        value = data.get(key)
        data[key] = (value[:80] if isinstance(value, str) and value.strip() else base[key])
    npc["boundaries"] = data
    return data


PROGRESS_TURN_CAP = 10     # 单回合等级进度上限（仅模型申报路；签到/支线/GM 内部通道不受限）

MAX_DATES_KEPT = 30             # 约会回忆保留条数
CHAT_HISTORY_KEPT = 40          # 每个会话保留的消息条数（滚动窗口）

# ---------- 超凡觉醒（心动系统的隐藏功能：只有主角在偷偷修仙） ----------
POWER_STAGES = ["凡人", "灵觉初醒", "淬体", "他心通", "灵犀", "御气"]
POWER_PROGRESS_PER_STAGE = 100   # 每境修为满 100 突破
POWER_STAGE_EFFECTS = {          # 突破时的一次性/持续效果（引擎侧接线）
    1: "灵觉初醒：可感知灵气，修炼类道具开始积累修为",
    2: "淬体：气血重铸，体魄永久 +2",
    3: "他心通：人物详情可感知 TA 最近共同经历的回声",
    4: "灵犀：每日与同一人的第一条短信，TA 会记得你的主动",
    5: "御气：身轻如燕，跨地点赶路不再多耗时段",
}

# 成就：谓词式定义，引擎在关键结算点统一检查
ACHIEVEMENTS = [
    {"id": "first_gift", "title": "初次心意", "desc": "送出第一份礼物",
     "check": lambda st: any(cnt for per_npc in ((st.get("gift_log") or {}).get("daily") or {}).values()
                             for cnt in per_npc.values())},
    {"id": "first_date", "title": "初次约会", "desc": "与心动的人完成第一次正式约会",
     "check": lambda st: bool(st.get("dates"))},
    {"id": "first_heart", "title": "怦然心动", "desc": "有人对你达到「心动」（好感85+）",
     "check": lambda st: any(n.get("affinity", 0) >= 85 and is_romanceable(n) for n in st["npcs"]
                             if n.get("known_to_player", n.get("last_seen_turn", -1) >= 0))},
    {"id": "first_bond", "title": "定下羁绊", "desc": "与心动的人定下「羁绊」（好感100）",
     "check": lambda st: any(n.get("affinity", 0) >= 100 and is_romanceable(n) for n in st["npcs"]
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
    t["minute"] = [360, 540, 840, 1080, 1260][t["slot"]]
    t["clock_day"], t["clock_slot"] = t["day"], t["slot"]


def time_label(state: dict) -> str:
    t = state.get("time") or {"day": 1, "slot": 0}
    minute = int(t.get('minute', [360, 540, 840, 1080, 1260][int(t.get('slot', 0)) % 5]))
    return f"第{int(t.get('day', 1))}天·{TIME_SLOTS[int(t.get('slot', 0)) % len(TIME_SLOTS)]} {minute // 60:02d}:{minute % 60:02d}"


# 人生阶段：由游戏内日期自然推进，不按剧情章节强切。
START_AGE = 18
LIFE_STAGES = [
    (18, "大学阶段", "发现可能"),
    (22, "社会起点", "建立事业"),
    (28, "社会影响力", "塑造格局"),
    (35, "无限人生", "自由定义"),
]


def life_stage_view(state: dict) -> dict:
    day = max(1, int((state.get("time") or {}).get("day", 1)))
    age = START_AGE + (day - 1) // 365
    education = state.get("player", {}).get("education", {})
    career = state.get("player", {}).get("career") or {}
    positions = career.get("positions") or {}
    fame = max((career.get("fame") or {}).values() or [0])
    stage = max([int(p.get("stage", 0)) for p in positions.values() if isinstance(p, dict)] or [int(career.get("stage", 0))])
    if fame >= 60 or stage >= 4:
        current = (age, "社会影响力", "让你的作品、事业与选择产生更远的回响")
    elif education.get("status", "enrolled") == "enrolled":
        current = (age, "大学阶段", "校园是起点，事业与关系可以同时发展")
    elif stage or education.get("status") in ("graduated", "withdrawn", "leave"):
        current = (age, "自主生活", "建立自己的生活、事业与长期关系")
    else:
        current = (age, "探索阶段", "由你决定下一种生活")
    next_stage = None
    return {
        "age": age,
        "stage": current[1],
        "theme": current[2],
        "day": day,
        "next_age": next_stage[0] if next_stage else None,
        "next_stage": next_stage[1] if next_stage else "",
        "days_to_next": (max(0, (next_stage[0] - age) * 365 - ((day - 1) % 365))
                         if next_stage else 0),
    }


THEME_ID = "urban-romance-v1"
LEGACY_THEME_IDS = {None, ""}  # 无标识的一律视为旧题材存档

# 旧题材物品改名（财富随存档迁移）
LEGACY_ITEM_RENAMES = {"下品灵石": CURRENCY, "系统金币": CURRENCY}
# 已下线人物：旧题材专属人物＋周母（2026-10-19 用户定案移除，亲情线不再出场）
LEGACY_NPC_IDS = {"npc_xuanyangzi", "npc_luoqingyi", "npc_zhaoqing", "npc_molao", "npc_xueluo", "npc_zhoumu",
                   # 2026-10-20 大换血前的旧九人：随旧档退场
                   "npc_suwanqing", "npc_chenrui", "npc_linhui", "npc_guqingyan", "npc_yeling",
                   "npc_songyutang", "npc_xuqin", "npc_shenman", "npc_baijing"}


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
    from .campaign import campaign_view, ending_options
    result["campaign"] = campaign_view(result)
    result["ending_options"] = ending_options(result)
    result["npc_total"] = len(state.get("npcs", []))
    result["server_date"] = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    result["game_date"] = game_today(state)  # 游戏世界日期（签到/限额/生日的结算钟）
    result["life_stage"] = life_stage_view(state)
    from .economy import wallets_view
    from .geography import atlas_view
    result["wallets"] = wallets_view(state)
    result["atlas"] = atlas_view(state)
    result["cash_name"] = CASH
    from .life_clock import clock_view
    from .world_sim import world_view
    result["clock_view"] = clock_view(result)
    result["world_view"] = world_view(result)
    from . import goals as _goals
    result["goals"] = _goals.goals_view(state)
    # 只读便捷字段：金币以背包物品形式存储，外部工具不该被迫按名字翻包
    result["currency"] = sum(i.get("count", 1) for i in state["player"].get("items", [])
                             if isinstance(i, dict) and i.get("name") == CURRENCY)
    result["currency_name"] = CURRENCY
    from . import career as _career, skills as _skills, world_events as _we
    result["skills_view"] = _skills.skills_view(state)
    result["career_view"] = _career.career_view(state)
    result["event_today"] = _we.event_today(state)
    result["events_view"] = _we.events_view(result)
    result["dates"] = list(state.get("dates", []))[-20:]
    # 主持人后台不进浏览器：事实账本、剧情钩子与导演状态是给模型的
    result.pop("facts", None)
    result.pop("facts_history", None)
    result.pop("chat_history", None)
    result.pop("summary_source", None)
    for segment in result.get("story", []):
        if isinstance(segment, dict):
            segment.pop("narrative_quality", None)
    result.pop("hooks", None)
    result.pop("director", None)
    result.pop("world_sim", None)
    result.pop("character_arcs", None)
    result["chats"] = {k: {"msgs": list(v.get("msgs", []))[-CHAT_HISTORY_KEPT:]}
                       for k, v in (state.get("chats") or {}).items()}
    result["achievement_defs"] = [{"id": a["id"], "title": a["title"], "desc": a["desc"]}
                                  for a in ACHIEVEMENTS]
    visible = []
    for npc in result["npcs"]:
        known = npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0)
        if not known:
            continue
        shown = {
            k: npc.get(k) for k in ("id", "name", "world", "role", "place", "affinity", "label")
        }
        # 偏好品类首揭制：没送中过偏好（likes_known）就不下发 likes，F12 也翻不到
        shown["likes"] = npc.get("likes") if npc.get("likes_known") else ""
        shown["project_arc_complete"] = bool(npc.get("project_arc_complete"))
        shown["relationship_status"] = npc.get("relationship_status", "")
        from .relationships import relationship_view
        shown["relationship"] = relationship_view(npc)
        life = ensure_life(npc, int((state.get("time") or {}).get("day", 1)))
        shown["life"] = {k: life.get(k) for k in ("goal", "status", "mood", "next")}
        shown["boundaries"] = dict(ensure_boundaries(npc))
        public_memos = [str(m) for m in (npc.get("memory") or [])
                        if str(m).startswith(("送礼：", "短信：", "第"))]
        if (state.get("power") or {}).get("stage", 0) >= 3:
            recent = public_memos[-1] if public_memos else "你们还没有留下可以共同回望的经历。"
            shown["heart_voice"] = f"{npc['name']}的记忆回声：{recent}"
        visible.append(shown | {"persona": npc.get("public_persona") or f"已知身份：{npc['role']}。更多经历有待了解。",
             "rels": npc.get("known_rels", {}), "memory": npc.get("known_memory", []),
             # 白名单只放行玩家亲历记忆（送礼：/短信：/第N回合：），其余后台写入一律不下发
             "memo": [m for m in (npc.get("memory") or [])[-12:]
                      if str(m).startswith(("送礼：", "短信：", "第"))][-6:]})
    result["npcs"] = visible
    return result


def default_npcs() -> list[dict]:
    """预设名册 35 人（2026-10-20 用户定案大换血）。

    前 9 位对位继承旧阵容的数值口径（好感/偏好/生日/常在地），保证测试与
    平衡不变；其余 26 位为新面孔。无定位的七位网友名按主播/网络身份推荐。
    """
    return [
        {
            "id": "npc_guoruiying", "name": "郭瑞莹", "world": WORLD_URBAN, "affinity": 60,
            "role": "青梅竹马·魔都音乐学院学姐", "place": "外滩滨江",
            "likes": "情趣",
            "birthday": "3-21",
            "persona": "在魔都音乐学院读钢琴系的青梅竹马，聪明敏锐，外冷内柔，"
                       "嘴上嫌弃却记得主角所有的习惯，对其近来的变化隐隐起疑又不敢深问", "label": "青梅竹马", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_liangyating", "name": "梁雅婷", "world": WORLD_URBAN, "affinity": 70,
            "role": "同班同学·热心肠", "place": "京华大学",
            "likes": "约会",
            "birthday": "8-8",
            "persona": "主角的同班同学，班里的“消息灵通人士”，话多义气、嘴碎但可靠，"
                       "最早察觉主角的变化，好奇心重", "label": "同班好友", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_xiaozhu", "name": "小朱", "world": WORLD_URBAN, "affinity": 50,
            "role": "辅导员", "place": "京华大学",
            "likes": "特殊",
            "birthday": "9-10",
            "persona": "比学生大不了几岁的年轻辅导员，管得严但护学生；行事沉稳得不像普通教职工"
                       "（伏笔：家里似乎有不得了的人脉）", "label": "辅导员", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"走路摇": "社团事务旧识，彼此心照不宣地装作不熟"},
        },
        {
            "id": "npc_yaqian", "name": "雅倩", "world": WORLD_URBAN, "affinity": 25,
            "role": "校花", "place": "京华大学",
            "likes": "情趣",
            "birthday": "5-5",
            "persona": "全校公认的门面担当，高冷克制的学霸；滴水不漏的外表下"
                       "藏着好胜心与极少示人的柔软", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"花碎花": "闺蜜，表面形影不离实则暗暗较劲"},
        },
        {
            "id": "npc_wangdefu", "name": "王德芙", "world": WORLD_URBAN, "affinity": 20,
            "role": "学妹·田径队", "place": "京华大学",
            "likes": "约会",
            "birthday": "11-3",
            "persona": "体育特长保送的大一学妹，直率莽撞、认死理，摔倒了也笑着爬起来；"
                       "一旦认定一个人就勇往直前", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"梁雅婷": "选课系统里认识的饭搭子"},
        },
        {
            "id": "npc_huasuihua", "name": "花碎花", "world": WORLD_URBAN, "affinity": 20,
            "role": "校花闺蜜", "place": "银杏商街",
            "likes": "情趣",
            "birthday": "7-18",
            "persona": "雅倩形影不离的闺蜜，笑起来眼睛弯弯；隐瞒着家里盘下半条银杏商街的事实，"
                       "在奶茶店打工只为“体验生活”", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"雅倩": "闺蜜，表面形影不离实则暗暗较劲", "炭炭": "追星追成朋友的退役idol"},
        },
        {
            "id": "npc_dengbiyao", "name": "邓碧瑶", "world": WORLD_URBAN, "affinity": 55,
            "role": "网友", "place": "魔都南站",
            "likes": "特殊",
            "birthday": "10-24",
            "persona": "游戏里认识两年的网友，深夜连麦的固定队友；声音慵懒、说话直接，"
                       "偶尔深夜的语音里藏着心事，从没见过面", "label": "网友", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_tantan", "name": "炭炭", "world": WORLD_URBAN, "affinity": 15,
            "role": "退役女团成员", "place": "龙脊CBD",
            "likes": "特殊",
            "birthday": "1-9",
            "persona": "二十三岁退团的前女团主舞，雷厉风行、慧眼识人，正在魔都转型做工作室；"
                       "对“不追星只当朋友”的年轻人格外有耐心", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"花碎花": "追星追成朋友的退役idol"},
        },
        {
            "id": "npc_zouluyao", "name": "走路摇", "world": WORLD_URBAN, "affinity": 30,
            "role": "cos社社长·网红", "place": "京华大学",
            "likes": "特殊",
            "birthday": "12-1",
            "persona": "学期中途转学来的cos社社长，百万粉的出圈网红，清冷疏离、来历成谜；"
                       "观察力惊人，似乎对“系统的异常”有自己的判断，只观察、先不动声色", "label": "神秘社长", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"小朱": "社团事务旧识，彼此心照不宣地装作不熟"},
        },
        {
            "id": "npc_zhangqi", "name": "张琦", "world": WORLD_URBAN, "affinity": 30,
            "role": "学姐·保研学霸", "place": "京华大学",
            "likes": "约会",
            "birthday": "4-12",
            "persona": "大四保研的学姐，图书馆闭馆前的最后一盏灯常为她亮着；温柔耐心，"
                       "讲题时会不自觉放软声音，被学弟学妹私下叫“琦姐”", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"雅倩": "保研辅导认识，互相欣赏"},
        },
        {
            "id": "npc_lvxiaolinzi", "name": "绿小林子", "world": WORLD_URBAN, "affinity": 25,
            "role": "双胞胎姐姐·漫研社", "place": "京华大学",
            "likes": "约会",
            "birthday": "6-15",
            "persona": "双胞胎中的姐姐，绿头发是漫研社的“社色”；主导泼辣，妹妹被欺负第一个冲上去，"
                       "其实自己才是更爱哭的那个", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"韩冰": "双胞胎妹妹，吵架三分钟和好"},
        },
        {
            "id": "npc_hanbing", "name": "韩冰", "world": WORLD_URBAN, "affinity": 25,
            "role": "双胞胎妹妹·电竞部经理", "place": "京华大学",
            "likes": "特殊",
            "birthday": "6-15",
            "persona": "双胞胎中的妹妹，人如其名外冷内热；电竞部金牌经理，排兵布阵一板一眼，"
                       "只有对着姐姐才会露出软乎乎的一面", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"绿小林子": "双胞胎姐姐，吵架三分钟和好", "小杨": "电竞部的黄金搭档"},
        },
        {
            "id": "npc_xiaoyang", "name": "小杨", "world": WORLD_URBAN, "affinity": 25,
            "role": "电竞社社长", "place": "京华大学",
            "likes": "约会",
            "birthday": "5-20",
            "persona": "电竞社社长兼主力选手，操作犀利、性格自来熟，输了比赛会蹲在椅子上生闷气；"
                       "拉赞助的本事比打比赛还强", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"韩冰": "电竞部的黄金搭档", "车车": "解说圈认识的师兄"},
        },
        {
            "id": "npc_cheche", "name": "车车", "world": WORLD_URBAN, "affinity": 15,
            "role": "电竞解说", "place": "龙脊CBD",
            "likes": "特殊",
            "birthday": "2-14",
            "persona": "LPL新生代解说，语速快到需要导播提醒；台上激昂台下安静，"
                       "解说席的灯光之外是个爱吃甜食的普通人", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"灵儿": "解说搭档，台上互补台下互怼", "小杨": "解说圈认识的师妹"},
        },
        {
            "id": "npc_linger", "name": "灵儿", "world": WORLD_URBAN, "affinity": 15,
            "role": "电竞解说·退役选手", "place": "龙脊CBD",
            "likes": "约会",
            "birthday": "2-14",
            "persona": "前职业选手转解说的“技术流”，分析到位话不多，金句都留给关键团；"
                       "退役那天哭得比夺冠还凶", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"车车": "解说搭档，台上互补台下互怼"},
        },
        {
            "id": "npc_aohan", "name": "傲寒", "world": WORLD_URBAN, "affinity": 20,
            "role": "唱歌主播", "place": "回声Livehouse",
            "likes": "情趣",
            "birthday": "10-1",
            "persona": "直播间走出的唱歌主播，一副烟嗓唱尽人间清醒；驻唱的Livehouse永远爆满，"
                       "下播后喜欢坐在吧台角落安静听别人的歌", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"乐乐": "直播平台的师姐妹"},
        },
        {
            "id": "npc_yangmi", "name": "杨幂", "world": WORLD_URBAN, "affinity": 10,
            "role": "明星·演员", "place": "龙脊CBD",
            "likes": "特殊",
            "birthday": "9-12",
            "persona": "一线女演员，智商情商双高的“拼命三娘”；戏里千面，戏外是圈里出了名的义气，"
                       "嘴上不饶人心里护短", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"迪丽热巴": "同公司的好友，互称损友"},
        },
        {
            "id": "npc_liuyifei", "name": "刘亦菲", "world": WORLD_URBAN, "affinity": 10,
            "role": "明星·演员", "place": "外滩滨江",
            "likes": "特殊",
            "birthday": "8-25",
            "persona": "被叫了二十年“神仙姐姐”的女演员，本人比角色松弛得多；爱猫爱书爱发呆，"
                       "在外滩散步被认出来会认真道谢", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_songyi", "name": "宋轶", "world": WORLD_URBAN, "affinity": 10,
            "role": "明星·演员", "place": "紫宸美术馆",
            "likes": "约会",
            "birthday": "11-17",
            "persona": "低调的实力派演员，旗袍扮相出圈；不拍戏的日子泡在美术馆里，"
                       "看展时会摘掉所有饰品像普通观众", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_yangchaoyue", "name": "杨超越", "world": WORLD_URBAN, "affinity": 10,
            "role": "明星·歌手", "place": "星愿游乐园",
            "likes": "情趣",
            "birthday": "7-31",
            "persona": "从选秀锦鲤走到今天的女艺人，真实得不像明星；综艺感拉满，"
                       "私下爱去游乐园排队买冰淇淋", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"鞠婧祎": "后台认识的朋友"},
        },
        {
            "id": "npc_zhangruonan", "name": "章若楠", "world": WORLD_URBAN, "affinity": 10,
            "role": "明星·演员", "place": "银杏商街",
            "likes": "约会",
            "birthday": "11-9",
            "persona": "笑起来有月牙眼的青年演员，邻家感拉满；不拍戏时会戴着帽子和口罩"
                       "逛商业街，被认出来就大方合影", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_zhaoliying", "name": "赵丽颖", "world": WORLD_URBAN, "affinity": 10,
            "role": "明星·演员", "place": "龙脊CBD",
            "likes": "特殊",
            "birthday": "10-16",
            "persona": "从农村姑娘走到收视女王的女演员，圈内公认的“戏疯子”；"
                       "对演技较真到帧，对生活简单到一碗面", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"杨幂": "多年老友，互相抢过角色也互相撑过场"},
        },
        {
            "id": "npc_zhaojinmai", "name": "赵今麦", "world": WORLD_URBAN, "affinity": 10,
            "role": "明星·青年演员", "place": "魔都大学",
            "likes": "约会",
            "birthday": "9-23",
            "persona": "童星出身的青年演员，现实中真在魔都大学读书；片场校园两头跑，"
                       "赶论文的样子和普通大学生一模一样", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_dilireba", "name": "迪丽热巴", "world": WORLD_URBAN, "affinity": 10,
            "role": "明星·演员", "place": "云顶天文台",
            "likes": "特殊",
            "birthday": "6-3",
            "persona": "新疆走出的顶流女演员，异域美貌下是出了名的敬业；夜戏收工后"
                       "爱去天文台看星星，说是“离家乡最近的方式”", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"杨幂": "同公司的好友，互称损友"},
        },
        {
            "id": "npc_zhangliangying", "name": "张靓颖", "world": WORLD_URBAN, "affinity": 10,
            "role": "歌手", "place": "回声Livehouse",
            "likes": "特殊",
            "birthday": "10-11",
            "persona": "海豚音歌后，华语乐坛的实力担当；录音棚外的她爱去小livehouse"
                       "听新人唱歌，坐在最后一排不打扰任何人", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_dengziqi", "name": "邓紫棋", "world": WORLD_URBAN, "affinity": 10,
            "role": "歌手", "place": "星愿游乐园",
            "likes": "特殊",
            "birthday": "8-16",
            "persona": "铁肺歌姬，创作型的舞台发电机；私底下是个游戏迷，"
                       "据说打手游比开演唱会还认真", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_danyichun", "name": "单依纯", "world": WORLD_URBAN, "affinity": 10,
            "role": "歌手", "place": "外滩滨江",
            "likes": "约会",
            "birthday": "12-23",
            "persona": "00后唱将，一副干净到发亮的好嗓子；私下慢半拍的迷糊性格，"
                       "逛音乐节会被人流冲散，站在原地唱歌等工作人员来找", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {},
        },
        {
            "id": "npc_jujingyi", "name": "鞠婧祎", "world": WORLD_URBAN, "affinity": 10,
            "role": "女团出身·歌手", "place": "外滩滨江",
            "likes": "情趣",
            "birthday": "6-18",
            "persona": "女团出道转型歌手的“四千年”，舞台上的精致到发丝；"
                       "私下爱在傍晚的外滩散步，戴渔夫帽压低帽檐", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"杨超越": "后台认识的朋友"},
        },
        {
            "id": "npc_wususu", "name": "乌苏苏", "world": WORLD_URBAN, "affinity": 25,
            "role": "网友·游戏主播", "place": "魔都南站",
            "likes": "约会",
            "birthday": "3-8",
            "persona": "深夜档游戏主播，声音好听技术更凶；直播间梗图满天飞，"
                       "下播后是个连外卖都点不明白的生活废人", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"歪歪": "固定双排队友"},
        },
        {
            "id": "npc_lele", "name": "乐乐", "world": WORLD_URBAN, "affinity": 25,
            "role": "网友·唱见主播", "place": "回声Livehouse",
            "likes": "约会",
            "birthday": "5-6",
            "persona": "午后档唱见，翻唱墙头无数；笑声比歌声先出圈，"
                       "点歌台永远排着唱不完的队", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"傲寒": "直播平台的师姐妹", "慕慕": "舞见搭档"},
        },
        {
            "id": "npc_chibubao", "name": "吃不饱", "world": WORLD_URBAN, "affinity": 25,
            "role": "网友·吃播博主", "place": "渔人码头",
            "likes": "情趣",
            "birthday": "1-24",
            "persona": "怎么吃都吃不饱的吃播博主，渔人码头的活地图；镜头前是干饭狂魔，"
                       "镜头后认真记录每家小店的故事", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"吐泡泡": "探店搭子"},
        },
        {
            "id": "npc_tupaopao", "name": "吐泡泡", "world": WORLD_URBAN, "affinity": 25,
            "role": "网友·治愈系主播", "place": "渔人码头",
            "likes": "特殊",
            "birthday": "7-7",
            "persona": "直播养鱼和水母的治愈系主播，说话慢吞吞爱吐泡泡音；"
                       "直播间背景永远是蓝色的，像一小片安静的海", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"吃不饱": "探店搭子"},
        },
        {
            "id": "npc_waiwai", "name": "歪歪", "world": WORLD_URBAN, "affinity": 25,
            "role": "网友·电竞陪玩", "place": "龙脊CBD",
            "likes": "约会",
            "birthday": "9-15",
            "persona": "排行榜常客的电竞陪玩，嘴上“歪理”一套一套；下单的客户一半为了上分，"
                       "一半为了听她损人", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"乌苏苏": "固定双排队友"},
        },
        {
            "id": "npc_xiaoxin", "name": "小新", "world": WORLD_URBAN, "affinity": 25,
            "role": "网友·兼职主播", "place": "银杏商街",
            "likes": "情趣",
            "birthday": "4-1",
            "persona": "隔壁学校的大学生兼职主播，白天上课晚上开播；攒生活费的样子笨拙又认真，"
                       "粉丝量不大但个个是真朋友", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"邓碧瑶": "互关很久的网友"},
        },
        {
            "id": "npc_mumu", "name": "慕慕", "world": WORLD_URBAN, "affinity": 25,
            "role": "网友·舞见主播", "place": "星愿游乐园",
            "likes": "约会",
            "birthday": "8-20",
            "persona": "翻跳区舞见，一支宅舞出圈；现实中温柔到说话都带气音，"
                       "只有在游乐园里会玩得像个小孩", "label": "尚未结识", "memory": [], "deeds": [],
            "known_to_player": False,
            "rels": {"乐乐": "舞见搭档"},
        },
    ]


PRESET_NPC_IDS = {n["id"] for n in default_npcs()}  # 主要角色不参与名册淘汰
MAX_NPCS = 44          # 名册上限；超出时按"最久未登场"淘汰剧情生成的人物（预设34人受保护）
DEFAULT_URBAN_IDENTITY = "京华大学·大一新生"


def default_map() -> dict:
    """三级地图：世界 → 国家 → 城市/地点。
    countries: 世界层（国家节点）；cities: 国家→城市节点；urban: 城市内地点（含 city 字段）。
    坐标均为 0-100 百分比（绘制到 400x260 视窗）。
    """
    base = {
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
             "desc": "魔都顶尖学府，与京华大学并称双子星；炭炭的母校"},
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
    from .geography import expand_map
    return expand_map(base)


def default_state(player_name: str) -> dict:
    from .campaign import default_campaign
    state = {
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
            "wallets_version": 1,
            "education": {"school": "京华大学", "major": "通识培养", "status": "enrolled", "credits": 0, "progress": 0},
        },
        "map": default_map(),
        "main_quest": {
            "title": QUEST_TITLE,
            "desc": QUEST_MILESTONES[START_REALM],
            "stage": START_REALM,
            "notes": [],
        },
        "side_quests": [],
        "goals": [],  # 玩家自定义人生目标（goals.ensure_goals 兜底）
        "campaign": default_campaign(),
        "time": {"day": 1, "slot": 0},  # 第1天·清晨
        "skills": {},       # 技能：{"vocal": {"lv": 1, "xp": 0}}（skills.ensure_skills 兜底）
        "career": None,     # 事业（career.ensure_career 惰性补齐，避免顶层 import 环）
        "assets": [],       # 资产：股份/股权等（周收益）
        "power": {"awakened": False, "stage": 0, "progress": 0,
                  "chat_bonus": {}},  # 超凡觉醒：境界/修为/灵犀日结账
        "director": {"active": None, "history": [], "last_event_turn": -999,
                     "last_npc": "", "last_place_count": 0},
        "hooks": [],   # 待消化剧情钩子：{"npc","stage","turn"}
        "achievements": [],  # 已解锁成就 id
        "dates": [],  # 约会回忆：{"npc","turn","ts","place","text"}
        "chats": {},  # 手机会话：{npc名: {"msgs": [{"ts","from","text"}]}}
        "chat_bond": {},  # 每日短信关系微涨：{游戏日期: [npc名]}
        "facts": [],  # 长期事实账本（记忆工程）：承诺/伏笔/秘密
        "facts_history": [],  # 完整历史账本；热窗移出的记录仍可查询、兑现和更新知情
        "chat_history": {},   # 已移出手机热窗的真实对话；只供相关记忆检索
        "last_sign_in": None,
        "npcs": default_npcs(),
        "story": [],
        "summary": "",
        "gift_log": {"daily": {}, "weekly": {}},
        "inbox": [],
        "turn": 0,
        "created_at": now_iso(),
        "last_active": now_iso(),
    }
    for npc in state["npcs"]:
        ensure_life(npc, 1)
        ensure_boundaries(npc)
    state["player"]["items"].append({"name": CASH, "count": 200, "desc": "现实生活与事业启动资金"})
    from .life_clock import ensure_clock
    from .world_sim import ensure_world
    ensure_clock(state)
    ensure_world(state)
    return state


def _clear_run_records(state: dict) -> None:
    """题材切换时清空上一轮的可见记录：剧情、收件箱、任务、事实账本与人物记忆。

    保留：货币（已换算）与抽奖券、好感数值、名册本身。
    旧题材专属物品（已不在新商城行情、卖不掉也用不了的）一并清出背包，免得背包里堆旧世界的遗物。
    """
    state["story"] = []
    state["summary"] = ""
    state["inbox"] = []
    state["facts"] = []
    state["facts_history"] = []
    state["chat_history"] = {}
    state.pop("summary_source", None)
    state["side_quests"] = []
    state.setdefault("main_quest", {})["notes"] = []
    for npc in state.get("npcs", []):
        npc["memory"] = []
        npc["deeds"] = []
        npc["known_memory"] = []
    from .shop import full_catalog  # 函数级导入：shop 依赖本模块，顶层会循环
    keep = {CURRENCY, LOTTERY_TICKET} | {g["name"] for g in full_catalog()}
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
    # 旧题材人物退场；陈锐（男）→梁雅婷（女）按同 id 覆盖
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
    country_names = {c.get("name") for c in state["map"]["countries"]}
    state["map"]["countries"].extend(deepcopy(c) for c in dm["countries"] if c["name"] not in country_names)
    if not isinstance(state["map"].get("cities"), dict):
        state["map"]["cities"] = dm["cities"]
    for country, cities in dm["cities"].items():
        city_nodes = state["map"]["cities"].setdefault(country, [])
        city_names = {c.get("name") for c in city_nodes}
        city_nodes.extend(deepcopy(c) for c in cities if c["name"] not in city_names)
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
        canonical = next((item for item in dm[WORLD_URBAN] if item["name"] == p["name"]), {})
        p.setdefault("country", canonical.get("country", "华夏"))
        p.setdefault("activities", deepcopy(canonical.get("activities", [])))

    defaults_by_name = {n["name"]: n for n in default_npcs()}
    defaults_by_id = {n["id"]: n for n in default_npcs()}
    state["npcs"] = [n for n in state.get("npcs", []) if n.get("id") not in LEGACY_NPC_IDS]
    existing_ids = {n.get("id") for n in state["npcs"]}
    existing_names = {n.get("name") for n in state["npcs"]}
    for npc in state.get("npcs", []):
        # 同 id 的预设人物以预设档案为底（改名/改世界覆盖旧档），保留记忆与好感
        preset = defaults_by_id.get(npc.get("id"))
        if preset is not None:
            renamed = npc.get("name") != preset["name"]
            for key in ("name", "world"):
                npc[key] = preset[key]
            for key in ("role", "persona", "place"):
                if renamed or not npc.get(key) or (key == "place" and npc.get(key) in _RETIRED_PLACES):
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
                                     if npc.get("name") in ("梁雅婷", "郭瑞莹")})
        npc.setdefault("known_memory", [])
        ensure_life(npc, int((state.get("time") or {}).get("day", 1)))
        ensure_boundaries(npc)
        if not isinstance(npc.get("relationship"), dict) and (npc.get("relationship_status") == "恋人" or state.get("partner") == npc.get("name")):
            npc["relationship"] = {"status": "partner", "mode": "exclusive", "since_day": int(state.get("time", {}).get("day", 1)), "history": [], "proposal": None}
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
    if not isinstance(state.get("facts_history"), list):
        state["facts_history"] = []
    state.setdefault("dates", [])
    state.setdefault("chats", {})
    if not isinstance(state.get("chat_history"), dict):
        state["chat_history"] = {}
    state.setdefault("chat_bond", {})
    state.setdefault("goals", [])
    state.setdefault("time", {"day": 1, "slot": 0})
    from .economy import ensure_wallets
    ensure_wallets(state)
    state["player"].setdefault("education", {"school": "京华大学", "major": "通识培养", "status": "enrolled", "credits": 0, "progress": 0})
    from .life_clock import ensure_clock
    ensure_clock(state)
    from .world_sim import ensure_world
    ensure_world(state)
    state.setdefault("power", {"awakened": False, "stage": 0, "progress": 0, "chat_bonus": {}})
    # 技能/事业/资产：旧档惰性补齐（函数级导入防环）
    from . import skills as _skills, career as _career
    _skills.ensure_skills(state)
    _career.ensure_career(state)
    state["player"].setdefault("assets", [])
    state.setdefault("calendar", {})
    director = state.setdefault("director", {})
    if not isinstance(director, dict):
        director = {}
        state["director"] = director
    director.setdefault("active", None)
    director.setdefault("history", [])
    director.setdefault("last_event_turn", -999)
    director.setdefault("last_npc", "")
    director.setdefault("last_place_count", 0)
    state.setdefault("hooks", [])
    state["hooks"] = [h for h in state["hooks"] if h.get("type") != "修罗场"]
    # 修罗场机制已下线：清掉旧档的残留字段与钩子
    state.pop("drama_day", None)
    state.pop("drama_survived", None)
    state.setdefault("achievements", [])
    state.setdefault("gift_log", {"daily": {}, "weekly": {}})
    from .campaign import ensure_campaign
    ensure_campaign(state)
    for npc in state.get("npcs", []):
        npc.setdefault("birthday", defaults_by_name.get(npc.get("name", ""), {}).get("birthday", ""))
        # 六维已下线；好感保留并按名册种子回填（数值条短暂下线期间的档不丢进度上限）
        npc.pop("bond", None)
        seed_aff = NPC_SEED_AFFINITY.get(npc.get("name", ""))
        if int(npc.get("affinity", -1) or -1) < 0 and seed_aff is not None:
            npc["affinity"] = int(seed_aff)
        rel = npc.get("relationship")
        if isinstance(rel, dict) and rel.get("status") == "flirt":
            rel["status"] = "friend"
    # 旧档事实补出类型与了结标记：承诺/伏笔要常驻提示词，不能按入账先后被挤掉
    for fact in state["facts"] + state["facts_history"]:
        if isinstance(fact, dict):
            fact.setdefault("kind", memory.classify_fact(fact.get("text", "")))
            fact.setdefault("closed", None)
            # 旧档没有知情范围：沿用原来的全局可见口径，不做静默收紧
            fact.setdefault("scope", "public")
            if not isinstance(fact.get("known_by"), list):
                fact["known_by"] = []
    refresh_main_quest(state)
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
    """兼容旧字段的成长目标由等级派生；真正剧情章节由 campaign 显式推进。

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
