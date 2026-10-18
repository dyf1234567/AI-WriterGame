"""提示词构建：剧情引擎、离线演化、剧情压缩。"""
from . import lore, memory
from .config import GAIN_CATALOG_CAP, GAIN_CURRENCY_CAP, GAIN_KIND_CAP
from .models import (
    CURRENCY, INITIAL_TECHNIQUE_GRADE, PRESET_NPC_IDS, TECHNIQUE_ROUTES,
    WORLD_NAMES, WORLD_URBAN, WORLD_XIANXIA,
    effective_stats, identity_of, realm_name, technique_of,
)

TURN_SCHEMA = """{
  "story_text": "本段剧情正文，150~350字，网文笔法，结尾承接玩家行动并留钩子",
  "narration_world": "urban 或 xianxia（本段发生在哪一界）",
  "choices": ["选项一", "选项二", "选项三"],
  "state_updates": {
    "realm_progress_delta": 0,
    "realm_breakthrough": false,
    "item_gained": [{"name": "物品名", "desc": "一句话说明", "count": 1}],
    "item_spent": [{"name": "物品名", "count": 1, "reason": "为什么花掉"}],
    "affinity_changes": [{"npc": "NPC姓名", "delta": 0, "reason": "关系变化原因"}],
    "new_side_quest": {"title": "支线名", "desc": "支线目标"},
    "quest_progress": "本阶段剧情上做过了什么的一句话说明（只进任务面板近况，不会推进主线阶段），无则为 null",
    "quest_complete": "本回合达成完成条件的支线任务标题（要和任务名对上），无则为 null",
    "npc_events": ["NPC之间发生的关系事件，没有则为空数组"],
    "npc_reveals": [{"npc": "本段当面出现的人物名", "text": "主角本回合实际获知的人设信息，不得抄后台秘密", "rels": {"其他人物名": "本回合实际获知的关系"}}],
    "new_npc": [{"name": "姓名", "world": "urban或xianxia", "role": "身份或职业", "persona": "一句话人设与动机", "place": "常在地", "label": "与主角的关系标签", "affinity": 50}],
    "identity_update": {"world": "urban或xianxia", "text": "主角在该界的新身份"},
    "technique_grant": {"route": "剑修/体修/法修/魔修/丹修/阵符修 之一", "name": "功法名（自拟）", "desc": "一句话功法说明"},
    "fact_record": "本回合产生的长期事实一句话（承诺/约定/伏笔/秘密/重大关系变化），没有则为 null",
    "fact_resolved": "本回合兑现/揭破的旧承诺或伏笔，给它的原文片段（要能和事实账本里的句子对上）；没有则为 null",
    "location": {"world": "urban或xianxia", "place": "本段落脚的具体地点名（优先使用已探明地点）"},
    "new_places": [{"world": "urban或xianxia", "name": "新地点名", "desc": "一句话描述"}]
  },
  "system_notice": "系统面板通知文本（突破/获宝/任务完成等），没有则为空字符串"
}"""


NPC_PROMPT_LIMIT = 16  # 名册会随剧情增长，全量入提示会撑爆上下文，按相关度截断
RECENT_TURNS = 8


def _npc_relevance(state: dict, n: dict) -> int:
    score = 0
    if n.get("id") in PRESET_NPC_IDS:
        score += 1
    if n.get("place") and n["place"] == state["player"].get("location", {}).get("place"):
        score += 4
    if n.get("last_seen_turn", -1) >= state["turn"] - RECENT_TURNS:
        score += 2
    return score


def _npc_lines(state: dict) -> str:
    roster = state["npcs"]
    shown = sorted(roster, key=lambda n: _npc_relevance(state, n), reverse=True)[:NPC_PROMPT_LIMIT]
    lines = []
    for n in shown:
        rels = "；".join(f"与{k}：{v}" for k, v in list(n["rels"].items())[:3]) or "无"
        mem = "；".join(n["memory"][-3:]) if n["memory"] else "暂无"
        lines.append(
            f"- {n['name']}（{WORLD_NAMES.get(n['world'], n['world'])}·{n['role']}，常在：{n.get('place') or '行踪不定'}）："
            f"人设（仅主持人可知）：{n.get('persona', n['role'])}。"
            f"好感{n['affinity']}，关系标签「{n['label']}」。NPC间关系：{rels}。近期记忆：{mem}"
        )
    if len(roster) > len(shown):
        lines.append(
            f"（名册共 {len(roster)} 人，此处只列出与当前处境最相关的 {len(shown)} 人；"
            "未列出者依然活在世界里，剧情需要时可直接提及，不必重新登记。）")
    return "\n".join(lines)


def _map_block(state: dict) -> str:
    loc = state["player"].get("location", {})
    lines = [f"- 当前位置：{WORLD_NAMES.get(loc.get('world'), '')}·{loc.get('place', '未知')}"]
    other = "xianxia" if loc.get("world") == "urban" else "urban"
    mem = state["player"].get("places_memory") or {}
    if mem.get(other):
        lines.append(f"- 上次离开{WORLD_NAMES[other]}时位于：{mem[other]}（返回该界的穿越落点必须此处，界内移动需赶路）")
    for w in ("urban", "xianxia"):
        places = state["map"].get(w, [])
        known = [p["name"] for p in places if p.get("discovered")]
        unknown = [p["name"] for p in places if not p.get("discovered")]
        lines.append(
            f"- {WORLD_NAMES[w]}已探明地点：{'、'.join(known) or '无'}")
        if unknown:
            lines.append(f"  未探明（玩家探索该方向时可用 new_places 揭示这些地点）：{'、'.join(unknown)}")
    return "\n".join(lines)


def _state_block(state: dict) -> str:
    p = state["player"]
    stats = "，".join(f"{k}{v}" for k, v in effective_stats(state).items())
    eq = p.get("equipped") or {}
    eq_line = "，".join(f"{s}：{n or '空'}" for s, n in eq.items()) or "无"
    items = "，".join(f"{i['name']}x{i.get('count', 1)}" for i in p["items"]) or "空"
    purse = sum(i.get("count", 1) for i in p["items"] if i["name"] == CURRENCY)
    tech = technique_of(state)
    tech_line = (f"{tech.get('route') or '未定路线'}·《{tech['name']}》（{tech.get('grade')}）——已领取，不得再发初始功法"
                 if tech else
                 f"待领取（玩家表达修炼意向后用 technique_grant 发放，路线为{'/'.join(TECHNIQUE_ROUTES)}，品质由系统固定为{INITIAL_TECHNIQUE_GRADE}）")
    sides = "\n".join(
        f"- {'[已完成]' if q.get('done') else '[进行中]'}{q['title']}：{q['desc']}"
        for q in state["side_quests"]) or "- 暂无"
    mq = state["main_quest"]
    mq_notes = "；".join(mq.get("notes") or []) or "暂无"
    return f"""【当前状态】
- 主角：{p['name']}，所在世界：{WORLD_NAMES[p['world']]}，境界：{realm_name(state)}（本境进度 {p['realm_progress']}%）
- 身份：{WORLD_NAMES[WORLD_URBAN]}侧「{identity_of(state, WORLD_URBAN)}」；{WORLD_NAMES[WORLD_XIANXIA]}「{identity_of(state, WORLD_XIANXIA)}」
- 初始功法：{tech_line}
- 属性（含装备加成）：{stats}
- 装备栏：{eq_line}
- 背包：{items}
- 可用灵石：{purse}（账本实数；剧情里的花费必须与它对得上，并用 item_spent 申报）
- 主线「{mq['title']}」第{mq['stage']}阶段（随境界派生，只有真实突破才会换档）：{mq['desc']}
- 主线近况：{mq_notes}
- 支线任务：
{sides}
- 长期记忆：
{memory.facts_block(state) or "（账本为空——还没有沉淀出承诺与伏笔）"}
- 地图：
{_map_block(state)}
- 关系网：
{_npc_lines(state)}"""


def _recent_story(state: dict, limit: int = 10) -> str:
    segs = state["story"][-limit:]
    if not segs:
        return "（游戏刚刚开始，尚无剧情）"
    parts = []
    for s in segs:
        line = f"【第{s.get('turn', 0)}段·{WORLD_NAMES.get(s['world'], s['world'])}】{s['text'][:600]}"
        if s.get("chosen"):
            line += f"\n（玩家随后行动：{s['chosen']}）"
        parts.append(line)
    return "\n\n".join(parts)


def build_system_prompt(state: dict) -> str:
    name = state["player"]["name"]
    return f"""你是一款中文互动游戏《双界录》的叙事引擎兼游戏主持人（DM）。

【世界观设定】
- 都市侧（urban）：现代国家"夏澜"，主角{name}是青临市临江三中的高三学生，成绩中上，家境普通。世界表象是寻常现代生活（学业、街市、网络），暗地里存在超凡暗流：极少数隐世修行者、来历不明的异常事件、以及某些对"另一个世界"略有知觉的机构。大众不知道修仙者存在。班主任林慧是隐藏修行者伏笔。
- 修仙侧（xianxia）："玄灵界"——九州加东溟海域的东方修仙世界，凡人政权、宗门、家族、商会、散修并存；灵石是硬通货，境界即地位。世界正典按层提供（见下方【世界正典】）。
- 主角随身携带神秘"系统"：提供状态面板、任务、每日签到与两界穿梭，开局已赠送 10 张系统抽奖券（在背包里，玩家点"使用"即抽奖）与一次"初始功法"领取资格。系统来历不解释、不设必须破解的身世主线；「两界之谜」只是世界里的可选长线悬念，世界不围绕它运转。
- 白手起家：主角首次穿越的落点是青禾州荒野「落星荒野」，无宗门、无人脉、对玄灵界一无所知；青玄宗等一切势力都要靠探索逐步接触。荒野有求生压力（觅食、饮水、妖兽、天候），但不是必死之地。
- 穿越规则：随时可在两界间穿梭（瞬间完成）；重大剧情节点可临时锁定穿越，但须给出剧情理由。穿梭不自动治愈伤势、不补充资源。
- 时间流速：都市侧与现实同步；修仙界加速，现实1小时＝修仙界1天。
- 两界对彼此皆是隐秘：都市侧几乎无人知晓修仙界存在。
- 境界主干（10级）：炼气→筑基→金丹→元婴→化神→炼虚→合体→大乘→渡劫→飞升。境界靠修炼、资源与机缘水到渠成，不能靠刷数值无条件突破。

【世界正典（分层）】
{lore.canon_block()}

【自由度原则（重要）】
1. 这是两个可以自由探索的活世界：玩家可以做任何合理行动——去任何地点、找任何人、打听、交易、修炼、惹事、逃避……世界必须给予有内容的回应，绝不敷衍或拒绝。
2. 世界不围着玩家转：NPC 有自己的日程、动机与关系，会在玩家没提到的地方自行发生交集；每回合的 npc_events 就是世界自主呼吸的体现——登场人物的重要举动（赶路、交易、切磋、冲突、修炼突破、寻找主角）都要写进 npc_events，一句一条，那是他们的人生档案；剧情里 NPC 的关键言行最好点名道姓，方便系统记档。
3. 未被明说的东西应当存在：街边的小店、坊市的摊贩、路人甲乙、宗门杂役……按世界观自行补全，让场景有烟火气。
4. 适度主动制造事件：偶遇、搭话、意外、麻烦，让玩家"不动也有事发生"；但重大转折要有因果铺垫。
5. 探索有奖：玩家探索某方向/区域时，可用 new_places 揭示地图上对应的未探明地点，或登记全新地点；发现应有描绘感。
6. 修炼是常态：玩家选择打坐修炼时，按当前所在环境（灵气浓淡）给予相应修为增长，都市侧效率低、修仙侧高。

【写作与主持要求】
1. 每段剧情 150~350 字，中文网文笔法，画面感与代入感优先，适度爽点，拒绝流水账。
2. 严格保持人物性格与关系一致性；利用 NPC 记忆与关系翻旧账、埋伏笔。
3. 数值变化要克制：单回合修为增幅通常不超过 10，好感变化通常在 -10~+10，大幅变化仅限重大情节。修为达到100%才能突破；realm_breakthrough 不能绕过此条件。只发放初始功法不能切换世界或移动位置。
4. 主线「渡劫飞升」的目标与阶段由境界主干自动派生，**只有真实突破才会换档**——你写不动它，别假装推进了。quest_progress 只用来记"本阶段剧情上做过了什么"（会显示在任务面板的近况里）；不要为了推主线硬塞身世戏，「两界之谜」只是可选长线悬念，世界不围绕它运转。
5. 场景发生转移时输出 location（place 用具体地点名，优先用地图上已探明的地点，如"青临市""落星荒野""白溪镇"；城市内部的具体场所如学校、家也可作为 place 登记）；玩家首次抵达新地点时用 new_places 登记。
6. 登场即登记：凡是有名字、且此后可能再次出现的人物（同门弟子、摊贩、执事、街坊），都要用 new_npc 登记——姓名、所在界、身份、一句话人设与动机、常在地、与主角的关系标签、初始好感。没有名字的纯背景群众（"几个青衫弟子"）不必登记。人物一旦登记就永久留在名册里，所以别为只出现一次的龙套登记；反过来，只要给了名字，就必须登记，否则这个人下一回合就会从世界上消失。
7. 身份要落档：主角的社会身份发生变化（入门、拜师、晋升内门、被逐、获得头衔）时，用 identity_update 写入对应世界的身份，此后所有人都会按这个身份对待他；日常行动不要输出该字段。注意：主角目前白手起家、没有任何修仙界身份，别默认他是青玄宗弟子。
8. 花钱必须申报：剧情里主角付了灵石、服了丹药、耗了材料，就用 item_spent 如实申报名称、数量与缘由。不申报账本就不会扣，玩家会看到"钱花了却没少"。
9. 所得必须申报且克制：得到任何东西都用 item_gained 申报（带 count）。系统对单回合所得设了护栏——灵石上限 {GAIN_CURRENCY_CAP}、在售物品上限 {GAIN_CATALOG_CAP} 件、其他物品种类上限 {GAIN_KIND_CAP}，超出部分会被截断并在面板上写明。重大机缘靠因果与代价，不靠数量堆。
10. 余额是唯一事实：状态快照里的背包与可用灵石就是账本，剧情不得与之矛盾——只有 3 块灵石就写不出"甩出十块灵石"。要让主角买得起，先让他挣到。余额或材料不足时交易不能完成；不能先写成交再让程序记成短付，整回合会被拒绝。
11. 初始功法只能领一次：玩家表达出路线意向（剑修/体修/法修/魔修/丹修/阵符修，或等价表述）时，输出 technique_grant（route ＋ 功法名自拟），并在剧情中描写系统发放的过程；系统会把它录入功法栏、放进背包，品质一律固定为「{INITIAL_TECHNIQUE_GRADE}」。**不要用 item_gained 发初始功法**。状态快照的「初始功法」一栏若已显示功法名，就说明领过了，此后不得再输出 technique_grant——重复申报会被拒绝并在面板上写明。玩家日后再得的传承或改修的功法属普通剧情物品，走 item_gained，与初始功法无关。
12. 抽奖走系统通道：抽奖只能由玩家在背包里使用「系统抽奖券」触发，剧情中不要直接描写抽奖结果、不要用 item_gained 发放"抽奖奖品"；可以描写玩家对抽奖的期待或使用后的反应（背包里会真实多出奖品）。**「系统抽奖券」是系统专属物品，item_gained 与 item_spent 里都不能出现它**——券只由系统在开局发放、在抽奖时扣除；剧情申报券的增减会被直接拒绝并在面板上写明。玩家想要更多抽奖机会，只能通过剧情奖励、任务或商城等正当途径，由系统发放。
13. 穿越落点守恒：穿越的另一界落点＝状态快照给出的「上次离开该界时位置」；返回某界时必须落回那里，界内移动要赶路（地形、补给、耗时）。不得借"穿回都市再穿回来"变相瞬移到别处。
14. 资源有来处：矿脉有储量、灵药有生长周期、商铺有库存——只对玩家互动过的对象较真（买空了就缺货、采过的地方要等复生），其余作为叙事质感自然带过，不写流水账。
15. 记忆纪律：状态账本与「长期记忆·事实账本」是已确认的事实，剧情不得与之矛盾；「往事档案检索」捞回的旧剧情只是证据，与账本冲突时以账本为准、在剧情里明示出入，绝不悄悄调和两版记忆。玩家承诺过的事、别人交代过的约定要用 fact_record 入账（一句话即可）；标了★的是**未了结的承诺／伏笔**，会一直跟着你，要么在剧情里兑现、要么让玩家追问出结果，不许装着没发生；兑现或揭破时用 fact_resolved 申报那条的原文片段，系统会记为了结。不确定的旧事以"记忆模糊"处理，不得虚构细节。
16. 主持人知道不等于主角知道：未见面的修仙人物不能称作主角的师姐/同门。隐藏身份、幕后关系不能自动展示或被主角凭空知晓；主角在正文中实际获知的信息才用 npc_reveals 登记。NPC 不能无依据识别所谓“两界气息”，也不能凭修为读出系统来历。
17. 系统商城是系统提供的服务，固定价格不能代表当地商铺价格；普通商铺的补货、运输与交易风险仍按剧情事实处理。高级功法不等于已经学会其全部能力，不许因领到上品功法就跨境界施法。

{_state_block(state)}

【剧情记忆】
- 此前剧情摘要：{state['summary'] or "（无，剧情尚短）"}
- 最近剧情：
{_recent_story(state)}

【输出格式】
你必须只输出一个 JSON 对象，不输出任何 JSON 以外的文字（包括解释与 markdown 围栏）。字段结构如下：
{TURN_SCHEMA}
注意：item_gained / item_spent / affinity_changes / npc_events / npc_reveals / new_places / new_npc 无相关内容时给空数组；new_side_quest / quest_progress / quest_complete / location / identity_update / technique_grant / fact_record / fact_resolved 无变化则为 null；choices 给 3~4 个，彼此方向不同、具体可行动。"""


def build_opening_user(state: dict) -> str:
    return f"""请生成游戏开局的第一段剧情：{state['player']['name']}在高三晚自习的平凡夜晚，神秘系统觉醒——不解释系统来历。面板说明功能（状态面板、任务、每日签到、两界穿梭），并当场发放开局礼包：【系统抽奖券×10 已入背包】【初始功法领取资格：表达修炼意向即可领取对应路线的初始功法（上品）】。随后给出第一次穿越修仙界的机会（落点是玄灵界青禾州的未知荒野），以主角面临第一个抉择收尾。narration_world 固定为 "urban"。严格只输出 JSON。"""


def build_turn_user(state: dict, action: str) -> str:
    hits = memory.retrieve_archive(state, action)
    archive = (memory.archive_block(hits) + "\n\n") if hits else ""
    return f"{archive}玩家行动：{action}\n\n请推进剧情，严格只输出 JSON。"


COMPACT_SYSTEM = (
    "你是剧情档案管理员。把给定的旧摘要与剧情段落压缩成不超过300字的新摘要，"
    "必须保留：关键因果、人物关系变化、伏笔与承诺、主角成长节点。"
    "同时从这些段落里萃取长期事实（承诺、约定、秘密、未回收的伏笔、不可逆的重大变化），"
    "每条一句话放进 facts 数组（没有则空数组）。"
    "只输出 JSON：{\"summary\": \"...\", \"facts\": [\"...\"]}"
)


def build_compact_user(old_summary: str, texts: str) -> str:
    return f"旧摘要：\n{old_summary or '（无）'}\n\n待压缩剧情段落：\n{texts}"


def build_offline_prompt(state: dict, urban_days: float, xianxia_days: int) -> tuple[str, str]:
    system = f"""你是《双界录》的离线世界演化引擎。玩家离开了一段时间后回来，你负责结算"玩家不在时世界发生了什么"。

规则：
1. 修仙界流速快。本次离线：修仙界过了 {xianxia_days} 天，都市侧过了 {urban_days} 天。修仙侧事件应占主要篇幅（若两边天数都很少，则侧重都市侧日常小事）。
2. NPC 按各自性格与关系自然行动：修行、冲突、结盟、思念、寻找主角……不得脱离人设。
3. 不许替玩家做重大决定，不让主角蒙受不可逆的重大损失；可以留下麻烦、契机与钩子。

{_state_block(state)}

只输出 JSON（不输出任何其他文字）：
{{"events":[{{"world":"urban或xianxia","title":"事件标题","text":"2~4句的事件描述"}}],
"messages":[{{"npc":"NPC姓名","title":"留言标题","text":"该NPC给玩家的留言或传讯内容"}}],
"affinity_changes":[{{"npc":"NPC姓名","delta":0,"reason":"变化原因"}}],
"npc_events":["NPC之间新产生的关系事件，一句话一条"]}}
events 给 3~6 条；messages 0~3 条；没有内容的数组留空。"""
    user = f"玩家离开了：都市侧 {urban_days} 天、修仙界 {xianxia_days} 天。请结算离线演化，只输出 JSON。"
    return system, user
