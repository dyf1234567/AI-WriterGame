"""互动都市连载的场景契约与本地文风检查；不调用模型、不改世界事实。"""
from copy import deepcopy
import hashlib
import re

from . import character_cards


class NarrativeFormatError(ValueError):
    """模型把内部写作过程混进了读者正文。"""


WRITING_CRAFT = """【都市连载写法（只落实到正文，不展示本节或写作过程）】
贴着主角“你”的此刻见闻写，保留玩家决定；不切进别人的内心，不写“你不知道的是”。从正在办的事、未接完的话或眼前结果接笔，环境只写影响这场事的一两处，不轮流用阳光、晚霞、霓虹开场。
网文的劲在欲望、交锋与兑现：这回合办成或碰到什么，必须让人看见台阶；已有能力用在具体难题上，得到有根据的反馈，别靠路人齐声震惊、反派无故挑衅和空降奖励制造爽点。休息闲聊可以安静，不硬塞危机。
人物先对事说话，各有目的和顾虑；允许答非所问、打岔、嘴硬、拒绝和留半句，别让所有人都温柔开导、替剧情作总结。情绪优先落在选择、台词、正在处理的物件和后果；不机械追加眼底一丝、嘴角一抹、指尖一颤、呼吸一滞，也不换同义词继续演。
对话换人就换段，叙述按镜头与信息转折分段；长短句交替，关键处写足，过场带过，不一句一行排电报，不堆比喻。好感、任务、技能、系统通知留给面板，正文演相处与办事，不念数值结算单。
回合末落在一个具体的答复、行动、结果或确实待选的问题上；兑现眼前的小回报，再把决定交回玩家。不要“命运的齿轮”“故事才刚刚开始”“这一刻你终于明白”的旁白升华，也不是每回合都留神秘短信。
输出前在内部复核：接住上句了吗，人物知道这件事吗，有无替玩家答应、重演初遇、复制上回合起手和结尾？发现问题就改本次草稿，检查过程不要输出。"""


def _clean(value, limit=240):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def voice_hint(npc: dict) -> str:
    """从当前人设推导声口；GM改人设后随之改变，不固定口头禅。"""
    card_voice = character_cards.voice_hint(npc)
    if card_voice:
        return card_voice
    persona = str(npc.get("persona") or npc.get("role") or "")
    if re.search(r"寡言|惜字|沉默|内向", persona):
        return "话少，先答眼前要紧的事；没说出的由实际选择承接，不故作神秘。"
    if re.search(r"嘴碎|话多|话痨|消息灵通", persona):
        return "接话快，会追问、插话和打趣，热心也有分寸；不一口气交代整段设定。"
    if re.search(r"雷厉风行|经理|经纪|创业|商人|工作室", persona):
        return "先说条件、安排和代价，态度藏在是否让步里；不满口商业术语。"
    if re.search(r"克制|高冷|一板一眼|沉稳", persona):
        return "表达简洁、有判断，关系变化落在称呼和实际让步；不固定写冷笑或反问。"
    if re.search(r"网友|连麦|游戏|说话直接", persona):
        return "口语直接，可用双方已经理解的游戏简称；不滥用网络梗，不编线下共同经历。"
    if re.search(r"直率|莽撞|体育|田径", persona):
        return "直说想法，碰到不懂的会追问；避免每句都豪爽表态。"
    if re.search(r"温柔|耐心|外冷内柔", persona):
        return "关心落在具体问题和做法上，可以有自己的不耐烦；不用客服式安慰包办答案。"
    return "按此人当下目的、身份与关系说人话；不用统一的温柔语气或固定口头禅。"


def scene_card(state: dict, action: str = "", opening: bool = False) -> dict:
    """把卷纲方法缩成一场互动戏的九项约束；它是写前材料，不是未来事实。"""
    player = state.get("player") or {}
    loc = player.get("location") or {}
    story = state.get("story") or []
    current_action = _clean(action, 400)
    if opening:
        mode, change = "开局", "报到时一个具体的小问题让梁雅婷与主角开始说话，系统短暂介入；其他旧识只经手机联系。"
    elif re.search(r"休息|发呆|散步|随便聊|没什么|歇一会", action):
        mode, change = "日常", "接住当前生活与话题，允许安静和无成果；不强造意外、告白或陌生人的任务。"
    elif re.search(r"练习|训练|学习|上课|练琴|声乐|读书", action):
        mode, change = "练习", "演出一次具体尝试、卡住的地方和当场调整；进步以已结算技能为准，别一练即成名。"
    elif re.search(r"公司|作品|工作室|报价|谈判|融资|发行|战队|生意|兼职", action):
        mode, change = "办事", "让需求、条件与反馈具体可见；账本尚未核验的交易只能谈，不能在正文里先签约、到账或夺冠。"
    elif re.search(r"约会|表白|关系|分手|喜欢|找.{0,12}聊|安慰", action):
        mode, change = "相处", "演一轮有来有回的交流，对方有自己的回应；靠真实共同经历推进，不替任何一方接受关系。"
    elif re.search(r"探索|看看|观察|去|前往|寻找|调查", action):
        mode, change = "走访", "只推进这次行动可到达、可看到的一段；给具体发现或反馈，不将传闻直接写成真相。"
    else:
        mode, change = "接戏", "回应玩家眼前真正要做或问的事，让局面产生一处可感知的变化；无需同时推进所有支线。"
    tail = _clean(story[-1].get("text", "")[-220:], 220) if story else "尚无前文，从眼前事件开始。"
    named = [n for n in state.get("npcs", []) if n.get("name") and n["name"] in action]
    nearby = [n for n in state.get("npcs", []) if n.get("known_to_player") and n.get("place") == loc.get("place")]
    people = named or nearby[:2]
    voices = "；".join(f"{_clean(n.get('name'),20)}：{voice_hint(n)}" for n in people[:3]) or "本场无必须登场的人；不为热闹拉来远处角色。"
    when = state.get("time") or {}
    time_place = f"第{when.get('day', 1)}天；{loc.get('country', '华夏')}/{loc.get('city', '京都')}/{loc.get('place', '当前地点')}，实际钟点见当前状态"
    return {
        "intent": current_action or "新生报到，在眼前场景作出第一个选择。",
        "viewpoint": "主角有限视角；玩家尚未决定的台词、感情与重大行动留白。",
        "time_place": time_place,
        "carry": tail,
        "change": f"{mode}：{change}",
        "voices": voices,
        "evidence": "当前规则状态/已确认事实优先；摘要是派生线索，旧文须看来源回合；提议、计划、回忆不等于已发生。",
        "limits": "不越过授权，不擅自跳天或转场；不复述面板，不泄露秘密；不制造既定结果来追求爽感。",
        "stop": ("350~550字左右，3~7个自然段，场内有第一处具体选择。" if opening else
                 "80~180字即可，留生活余味，别硬塞悬念。" if mode == "日常" else
                 "220~450字左右，3~7个自然段，收在眼前答复/结果/待选处；不为凑数注水。"),
    }


def scene_block(state: dict, action: str = "", opening: bool = False) -> str:
    card = scene_card(state, action, opening)
    labels = {"intent": "眼前诉求", "viewpoint": "视角", "time_place": "位置与时序", "carry": "接笔处",
              "change": "本场要演", "voices": "声口", "evidence": "证据", "limits": "边界", "stop": "停笔与篇幅"}
    return "【本回合场景卡（写前约束，不是既成事实；不要逐项照抄）】\n" + "\n".join(f"{labels[k]}：{v}" for k, v in card.items())


_META = re.compile(r"<\s*/?\s*(?:think|analysis|reasoning)\b|(?:^|\n)\s*(?:#{1,4}\s*)?(?:【(?:写作计划|场景卡|文风自检|去AI味自检|思维链)】|(?:写作计划|内部分析|思维链|自检结果)[:：])", re.I)
_PATTERNS = {
    "fate_closing": r"命运的齿轮|故事才刚刚开始|新的篇章[，。！]?\s*(?:就此|由此)?(?:展开|开启)",
    "explained_emotion": r"这一刻[，,]?你(?:终于|忽然|突然)(?:明白|意识到)|你不知道的是",
    "generic_reaction": r"(?:嘴角|唇角)(?:微微)?勾起一抹|眼底闪过一丝|指尖(?:微微)?一颤|呼吸(?:微微)?一滞",
    "summary_tone": r"这不仅(?:仅)?是.{0,30}更是|空气中弥漫着.{0,12}(?:气息|氛围)",
}


def prepare_result(data: dict, state: dict, action: str = "", channel: str = "turn") -> dict:
    """只整理换行并报告信号，绝不以关键词删改剧情、改奖励或另发润色请求。"""
    result = deepcopy(data)
    key = "reply" if channel == "chat" else "story_text"
    text = result.get(key)
    if not isinstance(text, str):
        return result  # 结构类型错误交给原有契约处理。
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if _META.search(text):
        raise NarrativeFormatError("正文混入了内部写作过程，请只返回场景正文与既定JSON字段。")
    if sum(label in text for label in ("起因：", "发展：", "高潮：", "结尾：")) >= 3:
        raise NarrativeFormatError("正文仍是写作提纲，请把本场言行写成正文。")
    result[key] = text
    signals = [name for name, pattern in _PATTERNS.items() if re.search(pattern, text)]
    normalized = re.sub(r"\s+", "", text)
    if channel != "chat" and len(normalized) >= 24:
        for previous in (state.get("story") or [])[-3:]:
            old = re.sub(r"\s+", "", str(previous.get("text") or ""))
            if len(old) >= 24 and normalized[:24] == old[:24]:
                signals.append("repeated_opening")
            if len(old) >= 24 and normalized[-24:] == old[-24:]:
                signals.append("repeated_closing")
    result["_narrative_quality"] = {"version": 1, "characters": len(text), "fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest(), "signals": list(dict.fromkeys(signals))[:8]}
    return result
