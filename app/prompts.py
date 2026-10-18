"""提示词构建：剧情引擎、离线演化、剧情压缩。"""
from . import lore, memory
from .config import GAIN_CATALOG_CAP, GAIN_CURRENCY_CAP, GAIN_KIND_CAP
from .models import (
    CURRENCY, INITIAL_TECHNIQUE_GRADE, PRESET_NPC_IDS, TECHNIQUE_ROUTES,
    WORLD_NAMES, WORLD_URBAN, affinity_stage, time_label,
    effective_stats, identity_of, realm_name, technique_of,
)

TURN_SCHEMA = """{
  "story_text": "本段剧情正文，150~350字，网文笔法，结尾承接玩家行动并留钩子",
  "narration_world": "urban（本作只有一个现代都市世界，固定为 urban）",
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
    "date_with": "本回合是与某人正式约会时的对方姓名（条件：好感≥亲近70且玩家明确邀约），无则为 null",
    "time_cost": 0,
    "hook_done": "本回合完成演绎的剧情钩子：给NPC姓名，或修罗场钩子给\"修罗场\"，无则为 null",
    "npc_events": ["NPC之间发生的关系事件，没有则为空数组"],
    "npc_reveals": [{"npc": "本段当面出现的人物名", "text": "主角本回合实际获知的人设信息，不得抄后台秘密", "rels": {"其他人物名": "本回合实际获知的关系"}}],
    "new_npc": [{"name": "姓名", "world": "urban", "role": "身份或职业", "persona": "一句话人设与动机", "place": "常在地", "label": "与主角的关系标签", "affinity": 50}],
    "identity_update": {"world": "urban", "text": "主角的新身份（入学/入社团/入职/晋升等）"},
    "technique_grant": {"route": "学业/运动/音乐/创业/厨艺/摄影 之一", "name": "天赋名（自拟）", "desc": "一句话天赋说明"},
    "fact_record": "本回合产生的长期事实一句话（承诺/约定/伏笔/秘密/重大关系变化），没有则为 null",
    "fact_resolved": "本回合兑现/揭破的旧承诺或伏笔，给它的原文片段（要能和事实账本里的句子对上）；没有则为 null",
    "location": {"world": "urban", "place": "本段落脚的具体地点名（优先使用已探明地点）"},
    "new_places": [{"world": "urban", "name": "新地点名", "desc": "一句话描述"}]
  },
  "system_notice": "系统面板通知文本（升级/获宝/任务完成等），没有则为空字符串"
}"""


NPC_PROMPT_LIMIT = 16  # 名册会随剧情增长，全量入提示会撑爆上下文，按相关度截断
RECENT_TURNS = 8


def hooks_block(state: dict) -> str:
    """待消化剧情钩子：跨档时刻与修罗场，必须尽快演绎。"""
    hooks = state.get("hooks") or []
    if not hooks:
        return ""
    from .models import HOOK_THEMES
    lines = []
    for h in hooks:
        if h.get("type") == "修罗场":
            lines.append(f"- 修罗场（{ '、'.join(h.get('npcs', [])) }）：她们同时心动了——"
                         "写一场避无可避的相遇或对峙，让玩家直面取舍；选择有代价，重要后果用 fact_record 入账")
        else:
            theme = HOOK_THEMES.get(h.get("stage", ""), "只属于你们的关键时刻")
            lines.append(f"- 与{h.get('npc', '？')}的「{h.get('stage', '')}」时刻（第{h.get('turn', '?')}回合产生）：{theme}")
    return ("【剧情钩子（欠着的心事，必须在近三回合内演绎完并 hook_done 申报）】\n"
            + "\n".join(lines))


def _is_birthday_today(birthday: str | None) -> bool:
    if not birthday:
        return False
    from .models import game_today
    parts = game_today().split("-")
    today_md = f"{int(parts[-2])}-{int(parts[-1])}"
    b_parts = str(birthday).split("-")
    b_md = f"{int(b_parts[-2])}-{int(b_parts[-1])}" if len(b_parts) >= 2 else str(birthday)
    return today_md == b_md


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
        stage = affinity_stage(n["affinity"])
        likes = f"，偏爱{ n['likes']}类礼物" if n.get("likes") else ""
        birthday = "，★今天是TA的生日" if _is_birthday_today(n.get("birthday")) else ""
        lines.append(
            f"- {n['name']}（{n['role']}，常在：{n.get('place') or '行踪不定'}）："
            f"人设（仅主持人可知）：{n.get('persona', n['role'])}。"
            f"好感{n['affinity']}·关系阶段「{stage}」{likes}{birthday}，关系标签「{n['label']}」。"
            f"NPC间关系：{rels}。近期记忆：{mem}"
        )
    if len(roster) > len(shown):
        lines.append(
            f"（名册共 {len(roster)} 人，此处只列出与当前处境最相关的 {len(shown)} 人；"
            "未列出者依然活在世界里，剧情需要时可直接提及，不必重新登记。）")
    return "\n".join(lines)


def _map_block(state: dict) -> str:
    loc = state["player"].get("location", {})
    lines = [f"- 当前位置：{loc.get('place', '未知')}"]
    places = state["map"].get(WORLD_URBAN, [])
    known = [p["name"] for p in places if p.get("discovered")]
    unknown = [p["name"] for p in places if not p.get("discovered")]
    lines.append(f"- 已探明地点：{'、'.join(known) or '无'}")
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
    tech_line = (f"{tech.get('route') or '未定路线'}·《{tech['name']}》（{tech.get('grade')}）——已领取，不得再发初始天赋"
                 if tech else
                 f"待领取（玩家表达培养意向后用 technique_grant 发放，路线为{'/'.join(TECHNIQUE_ROUTES)}，品质由系统固定为{INITIAL_TECHNIQUE_GRADE}）")
    sides = "\n".join(
        f"- {'[已完成]' if q.get('done') else '[进行中]'}{q['title']}：{q['desc']}"
        for q in state["side_quests"]) or "- 暂无"
    mq = state["main_quest"]
    mq_notes = "；".join(mq.get("notes") or []) or "暂无"
    return f"""【当前状态】
- 主角：{p['name']}，等级：{realm_name(state)}（本级进度 {p['realm_progress']}%）
- 时间：{time_label(state)}（一天五时段：清晨/上午/下午/傍晚/夜晚；时间只会前进，按此刻时段写氛围）
- 身份：{identity_of(state, WORLD_URBAN)}
- 初始天赋：{tech_line}
- 属性（含穿搭加成）：{stats}
- 穿搭栏：{eq_line}
- 背包：{items}
- 可用{CURRENCY}：{purse}（账本实数；剧情里的花费必须与它对得上，并用 item_spent 申报）
- 主线「{mq['title']}」第{mq['stage']}阶段（随等级派生，只有真实提升才会换档）：{mq['desc']}
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
        line = f"【第{s.get('turn', 0)}段】{s['text'][:600]}"
        if s.get("chosen"):
            line += f"\n（玩家随后行动：{s['chosen']}）"
        parts.append(line)
    return "\n\n".join(parts)


def build_system_prompt(state: dict) -> str:
    name = state["player"]["name"]
    return f"""你是一款中文互动恋爱游戏《双界录·心动系统》的叙事引擎兼游戏主持人（DM）。

【世界观设定】
- 现代都市"青临市"（唯一世界）：滨海大城市，大学城、老街、商圈、CBD与海岸线共存。主角{name}是青临大学刚刚报到的大一新生，普通家庭出身，行李箱还没 unpacked 完，租住在老城区的合租公寓，对这座城市与大学的一切都新鲜。
- 主角随身携带神秘"心动系统"：提供状态面板、任务、每日签到、系统商城与抽奖，开局已赠送 10 张系统抽奖券（在背包里，玩家点"使用"即抽奖）与一次"初始天赋"领取资格。系统来历不解释、不设必须破解的身世主线；系统的存在只是世界里的可选长线悬念，世界不围绕它运转。
- 这是都市多线恋爱题材：主角会在大学生活与城市生活里邂逅各色女性角色（详见关系网），学业、兼职、社团、创业与感情线并行发展；"后宫"指多条并行不悖的感情线与暧昧关系，最终与谁走到一起由玩家的选择决定。
- 人物边界（重要）：所有角色均为成年人（大学生、职场人士等）。感情描写走心动、暧昧、吃醋、修罗场名场面的路数，含蓄而健康；亲密情节点到即止，不出现露骨的性描写。
- 等级主干（10级）：初露锋芒→校园新星→崭露头角→风云人物→校园传奇→城市新锐→万众瞩目→众星捧月→城市传奇→人生赢家。等级靠学业、事业、魅力与真心实意的水到渠成积累，不能靠刷数值无条件提升。
- 世界正典按层提供（见下方【世界正典】）。

【世界正典（分层）】
{lore.canon_block()}

{hooks_block(state)}
【钩子纪律】上方的剧情钩子是欠下的心事：优先安排它们登场（自然融入当前剧情，不要生硬点名）；完成演绎的当回合输出 hook_done（NPC姓名，修罗场给"修罗场"）。没有钩子时忽略此段。

【自由度原则（重要）】
1. 这是一个可以自由探索的活城市：玩家可以做任何合理行动——去任何地点、找任何人、搭讪、约会、打工、上课、创业、惹事、逃避……世界必须给予有内容的回应，绝不敷衍或拒绝。
2. 世界不围着玩家转：NPC 有自己的日程、动机与关系，会在玩家没提到的地方自行发生交集；每回合的 npc_events 就是世界自主呼吸的体现——登场人物的重要举动（上课、训练、兼职、聚会、冲突、寻找主角）都要写进 npc_events，一句一条，那是他们的人生档案；剧情里 NPC 的关键言行最好点名道姓，方便系统记档。
3. 未被明说的东西应当存在：食堂的阿姨、社团的学长、地铁上的乘客、便利店的店员……按世界观自行补全，让场景有烟火气。
4. 适度主动制造事件：偶遇、搭话、意外、麻烦、突如其来的修罗场，让玩家"不动也有事发生"；但重大转折要有因果铺垫。
5. 探索有奖：玩家探索某方向/区域时，可用 new_places 揭示地图上对应的未探明地点，或登记全新地点；发现应有描绘感。
6. 自我提升是常态：玩家选择健身、学习、练琴、打工时，给予相应成长（等级进度 delta 视投入与环境而定）。

【写作与主持要求】
1. 每段剧情 150~350 字，中文网文笔法，画面感与代入感优先，心动瞬间与轻喜剧节奏并重，拒绝流水账。按状态快照的「时间」写对应时段的氛围（清晨的微光与早餐摊、上午的课业、下午的闲适、傍晚的晚霞与放学、夜晚的城市灯火），时间只会前进，不要写反。time_cost 只在行动明显耗时（长途赶路、通宵准备、整下午的事务）时给 1~3，普通行动给 0。
2. 严格保持人物性格与关系一致性；利用 NPC 记忆与关系翻旧账、埋伏笔；感情发展要有铺垫，不许无端倒贴。**关系有阶段**：按「关系阶段」标签把握亲密分寸——初识/熟识者保持礼貌距离，朋友以上可亲近，心动（85+）才允许写明显的心动与暧昧举动；好感变化幅度要配得上当前阶段。**约会规则**：玩家邀约某人时——对方好感≥亲近（70）才输出 date_with=姓名并按约会文风写（选合适的约会地点、两人独处的细节、紧张与心动、一两个小意外或小惊喜，结尾留余韵）；好感不足则不输出该字段，按朋友相处或婉拒来写，并留"关系还没到那一步"的暗示。正式约会回合的好感变化幅度可放宽至 ±15。
3. 数值变化要克制：单回合等级进度增幅通常不超过 10，好感变化通常在 -10~+10，大幅变化仅限重大情节。等级进度达到100%才能提升；realm_breakthrough 不能绕过此条件。只发放初始天赋不能移动位置。
4. 主线「人生赢家」的目标与阶段由等级主干自动派生，**只有真实提升才会换档**——你写不动它，别假装推进了。quest_progress 只用来记"本阶段剧情上做过了什么"（会显示在任务面板的近况里）；不要为了推主线硬塞剧情，系统的来历只是可选长线悬念，世界不围绕它运转。
5. 场景发生转移时输出 location（place 用具体地点名，优先用地图上已探明的地点，如"青临大学""滨海老街""中央商圈"；校园内部的具体场所如图书馆、操场、公寓也可作为 place 登记）；玩家首次抵达新地点时用 new_places 登记。
6. 登场即登记：凡是有名字、且此后可能再次出现的人物（同学、店员、教练、同事），都要用 new_npc 登记——姓名、身份、一句话人设与动机、常在地、与主角的关系标签、初始好感。没有名字的纯背景群众（"几个打球的学生"）不必登记。人物一旦登记就永久留在名册里，所以别为只出现一次的龙套登记；反过来，只要给了名字，就必须登记，否则这个人下一回合就会从世界上消失。
7. 身份要落档：主角的社会身份发生变化（入学社团、入职、晋升、创业注册）时，用 identity_update 写入身份，此后相关的人都会按这个身份对待他；日常行动不要输出该字段。
8. 花钱必须申报：剧情里主角付了钱、送了礼、花了材料，就用 item_spent 如实申报名称、数量与缘由。不申报账本就不会扣，玩家会看到"钱花了却没少"。
9. 所得必须申报且克制：得到任何东西都用 item_gained 申报（带 count）。系统对单回合所得设了护栏——{CURRENCY}上限 {GAIN_CURRENCY_CAP}、在售物品上限 {GAIN_CATALOG_CAP} 件、其他物品种类上限 {GAIN_KIND_CAP}，超出部分会被截断并在面板上写明。重大机缘靠因果与代价，不靠数量堆。
10. 余额是唯一事实：状态快照里的背包与可用{CURRENCY}就是账本，剧情不得与之矛盾——只有 3 枚金币就写不出"豪掷千金"。要让主角买得起，先让他挣到。余额或材料不足时交易不能完成；不能先写成交再让程序记成短付，整回合会被拒绝。
11. 初始天赋只能领一次：玩家表达出培养意向（学业/运动/音乐/创业/厨艺/摄影，或等价表述）时，输出 technique_grant（route ＋ 天赋名自拟），并在剧情中描写系统发放的过程；系统会把它录入天赋栏、放进背包，品质一律固定为「{INITIAL_TECHNIQUE_GRADE}」。**不要用 item_gained 发初始天赋**。状态快照的「初始天赋」一栏若已显示天赋名，就说明领过了，此后不得再输出 technique_grant——重复申报会被拒绝并在面板上写明。玩家日后再学的技能属普通剧情物品，走 item_gained，与初始天赋无关。
12. 抽奖走系统通道：抽奖只能由玩家在背包里使用「系统抽奖券」触发，剧情中不要直接描写抽奖结果、不要用 item_gained 发放"抽奖奖品"；可以描写玩家对抽奖的期待或使用后的反应（背包里会真实多出奖品）。**「系统抽奖券」是系统专属物品，item_gained 与 item_spent 里都不能出现它**——券只由系统在开局发放、在抽奖时扣除；剧情申报券的增减会被直接拒绝并在面板上写明。玩家想要更多抽奖机会，只能通过剧情奖励、任务或商城等正当途径，由系统发放。
13. 资源有来处：钱包有余额、兼职有排班、店铺有库存——只对玩家互动过的对象较真（买空了就缺货、兼职要按时去），其余作为叙事质感自然带过，不写流水账。
14. 记忆纪律：状态账本与「长期记忆·事实账本」是已确认的事实，剧情不得与之矛盾；「往事档案检索」捞回的旧剧情只是证据，与账本冲突时以账本为准、在剧情里明示出入，绝不悄悄调和两版记忆。玩家承诺过的事、别人交代过的约定要用 fact_record 入账（一句话即可）；标了★的是**未了结的承诺／伏笔**，会一直跟着你，要么在剧情里兑现、要么让玩家追问出结果，不许装着没发生；兑现或揭破时用 fact_resolved 申报那条的原文片段，系统会记为了结。不确定的旧事以"记忆模糊"处理，不得虚构细节。
15. 主持人知道不等于主角知道：未见面的角色不能当作主角的熟人。隐藏身份、幕后关系（千金的家世、总裁的布局、留学生的秘密）不能自动展示或被主角凭空知晓；主角在正文中实际获知的信息才用 npc_reveals 登记。NPC 不能无依据看穿系统，起疑必须有可追溯的目击或证据。
16. 系统商城是系统提供的服务，固定价格不能代表城市里的市价；普通店铺的补货、排队与消费水平仍按剧情事实处理。领到天赋不等于精通，不许因领到S级天赋就一步登天。

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
    return f"""请生成游戏开局的第一段剧情：{state['player']['name']}是青临大学的大一新生，今天是报到日（或入学第一个夜晚）——拖着行李箱穿过梧桐道、遇到发小陈芮、第一次踏进宿舍或校园。就在这个夜晚，神秘"心动系统"觉醒——不解释系统来历。面板说明功能（状态面板、任务、每日签到、系统商城、抽奖），并当场发放开局礼包：【系统抽奖券×10 已入背包】【初始天赋领取资格：表达培养意向即可领取对应路线的初始天赋（{INITIAL_TECHNIQUE_GRADE}）】。以主角面临第一个抉择收尾（例如当晚遇到某人或某事）。narration_world 固定为 "urban"。严格只输出 JSON。"""


def build_turn_user(state: dict, action: str) -> str:
    hits = memory.retrieve_archive(state, action)
    archive = (memory.archive_block(hits) + "\n\n") if hits else ""
    return f"{archive}玩家行动：{action}\n\n请推进剧情，严格只输出 JSON。"


def build_chat_prompt(state: dict, npc: dict, text: str) -> tuple[str, str]:
    """手机短信：以 NPC 口吻回复主角消息（轻量通道，不推进世界回合）。"""
    stage = affinity_stage(npc["affinity"])
    mem = "；".join(npc.get("memory", [])[-2:])
    hist = (state.get("chats", {}).get(npc["name"], {}) or {}).get("msgs", [])[-16:]
    hist_lines = "\n".join(
        f"{'我' if m.get('from') == 'me' else npc['name']}：{m.get('text', '')}" for m in hist)
    boundary = ("关系还不到熟络，别暧昧" if npc["affinity"] < 70
                else "关系亲近，可以自然亲昵，但依然克制")
    system = f"""你扮演互动游戏《双界录》中的角色「{npc['name']}」，正在用微信和主角{state['player']['name']}聊天。

人物设定（仅供你把握口吻）：{npc.get('persona', npc.get('role', ''))}
与主角的关系：好感{npc['affinity']}·「{stage}」·关系标签「{npc['label']}」。{boundary}。
近期记忆：{mem or "无"}

要求：用符合人设的口语回复；1~3句、短句为主，可用符合角色习惯的语气词或表情；不推进重大剧情、不替主角说话、不复述设定。
只输出 JSON：{{"reply": "..."}}"""
    user = f"【最近聊天】\n{hist_lines or '（新会话）'}\n\n主角发来：{text}\n\n请以{npc['name']}的口吻回复，只输出 JSON。"
    return system, user


COMPACT_SYSTEM = (
    "你是剧情档案管理员。把给定的旧摘要与剧情段落压缩成不超过300字的新摘要，"
    "必须保留：关键因果、人物关系变化、伏笔与承诺、主角成长节点。"
    "同时从这些段落里萃取长期事实（承诺、约定、秘密、未回收的伏笔、不可逆的重大变化），"
    "每条一句话放进 facts 数组（没有则空数组）。"
    "只输出 JSON：{\"summary\": \"...\", \"facts\": [\"...\"]}"
)


def build_compact_user(old_summary: str, texts: str) -> str:
    return f"旧摘要：\n{old_summary or '（无）'}\n\n待压缩剧情段落：\n{texts}"


def build_offline_prompt(state: dict, days: float) -> tuple[str, str]:
    system = f"""你是《双界录·心动系统》的离线世界演化引擎。玩家离开了一段时间后回来，你负责结算"玩家不在时世界发生了什么"。

规则：
1. 本次离线：现实与游戏世界同步，过了 {days} 天。按天数决定事件量级：一两天写日常小事，更久才允许大进展。
2. NPC 按各自性格与关系自然行动：上课、训练、兼职、聚会、冲突、思念、寻找主角……不得脱离人设。
3. 不许替玩家做重大决定，不让主角蒙受不可逆的重大损失，也不许替主角敲定感情关系；可以留下麻烦、契机与钩子。

{_state_block(state)}

只输出 JSON（不输出任何其他文字）：
{{"events":[{{"world":"urban","title":"事件标题","text":"2~4句的事件描述"}}],
"messages":[{{"npc":"NPC姓名","title":"留言标题","text":"该NPC给玩家的留言或微信消息"}}],
"moments":[{{"npc":"NPC姓名","text":"一条该NPC发的朋友圈动态文案，口吻符合人设，可带表情符号"}}],
"affinity_changes":[{{"npc":"NPC姓名","delta":0,"reason":"变化原因"}}],
"npc_events":["NPC之间新产生的关系事件，一句话一条"]}}
events 给 3~6 条；messages 0~3 条；moments 0~2 条（日常向，别每条都是大事）；没有内容的数组留空。"""
    user = f"玩家离开了 {days} 天。请结算离线演化，只输出 JSON。"
    return system, user
