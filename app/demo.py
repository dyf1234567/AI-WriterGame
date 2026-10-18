"""演示模式内置剧情：未配置模型 API 时使用，保证全流程可跑通。"""
from .models import WORLD_URBAN, WORLD_XIANXIA

_EMPTY_UPDATES = {
    "realm_progress_delta": 0,
    "realm_breakthrough": False,
    "item_gained": [],
    "item_spent": [],
    "affinity_changes": [],
    "new_side_quest": None,
    "quest_progress": None,
    "npc_events": [],
    "new_npc": [],
    "identity_update": None,
    "technique_grant": None,
    "fact_record": None,
}


def opening_segment(name: str) -> dict:
    return {
        "story_text": (
            f"晚自习的白炽灯下，你——{name}，正对着一道解析几何发呆。忽然，视野里浮起一行"
            "只有你能看见的淡金色小字：【双界系统·绑定成功】【基础引气完成·炼气初境】【功能解锁：状态面板 / 任务 / "
            "每日签到 / 两界穿梭】。紧接着，桌面上的笔袋无端一沉——【开局礼包已发放："
            "系统抽奖券×10，已入背包，随时可使用】【初始功法领取资格已激活：表达你的修炼意向"
            "（剑修/体修/法修/魔修/丹修/阵符修），即可领取对应路线的初始功法（上品）】。"
            "前排的陈锐回头冲你挤眉弄眼：\"睡着了吧你，口水都下来了。\"你还没来得及回答，"
            "系统的提示音再次响起：【检测到宿主灵根·可穿越至玄灵界·落点：青禾州未知荒野·是否立即前往？】"
            "桌面上，你的笔轻轻颤了一下。"
        ),
        "narration_world": WORLD_URBAN,
        "choices": [
            "立即穿越，去那个未知荒野看看",
            "先打开背包，试试系统抽奖",
            "默念：我想走剑修路线，领取初始功法",
            "先稳住，装作无事发生，等晚自习结束",
        ],
        "state_updates": {
            **_EMPTY_UPDATES,
            "location": {"world": WORLD_URBAN, "place": "青临市"},
        },
        "system_notice": "【系统】绑定完成。开局礼包已发放：系统抽奖券×10（背包内使用）；初始功法待表达修炼意向后领取。每日签到已开启。",
    }


_XIANYXIA_SEG = {
    "story_text": (
        "白光散去，脚下不再是教室的水磨石地面，而是齐腰深的荒草。你站在一片望不到边的古荒野岭上，"
        "风里裹着陌生而清冽的灵气，远处传来一声低沉的兽吼，惊起一片飞鸟。系统面板安静地亮着："
        "【当前位置：玄灵界·青禾州·落星荒野】【提示：荒野有求生压力，但并非绝地；宿主无宗门、无人脉，"
        "一切从零开始】。你摸了摸口袋——抽奖券还在，那部待领取的初始功法，似乎正等着你的一个念头。"
    ),
    "narration_world": WORLD_XIANXIA,
    "choices": [
        "默念：我想走剑修路线，领取初始功法",
        "先在荒野里探索一圈，辨认方向与水源",
        "打开背包，先抽一发奖碰碰运气",
        "暂且返回都市，做些准备再来",
    ],
    "state_updates": {
        **_EMPTY_UPDATES,
        "realm_progress_delta": 2,
        "location": {"world": WORLD_XIANXIA, "place": "落星荒野"},
    },
    "system_notice": "【系统】抵达玄灵界·落星荒野：灵气浓度高（修炼效率提升），注意求生。",
}

# 修炼路线 -> 初始功法（设定集 V1.2 · 4.1：按意向发放对应路线初始最高品质功法）
# 触发词必须是明确的路线表述，避免"运转功法"之类的泛用词误判
_GONGFA_ROUTES = [
    (["剑修", "剑道", "剑法", "练剑"], "剑修", "青霜剑诀（上品）", "剑修入门功法，剑出如霜，杀伐凌厉，讲究一往无前"),
    (["体修", "炼体", "锻体"], "体修", "磐岩锻体诀（上品）", "体修入门功法，以气血淬炼肉身，皮糙骨坚，近战无惧"),
    (["法修", "法道"], "法修", "玄元素法诀（上品）", "法修入门功法，灵力化元素，火冰雷风随指而动"),
    (["魔修", "魔道"], "魔修", "噬灵魔典（上品）", "魔修入门功法，爆发惊人，附有反噬风险，非常规成长之路"),
    (["丹修", "丹道", "炼丹"], "丹修", "百草丹经（上品）", "丹修入门功法，识药、配伍、控火之道，炼丹效率大增"),
    (["阵符", "阵修", "阵法", "画符"], "阵符修", "八门符阵图（上品）", "阵符修入门功法，布阵画符、设禁破禁，掌控区域"),
]


def _gongfa_segment(state: dict, action: str) -> dict | None:
    """玩家表达了明确的修炼意向时发放初始功法；一次性闸在引擎的 player.technique。"""
    if state["player"].get("technique"):
        return None
    for triggers, route_name, gname, gdesc in _GONGFA_ROUTES:
        if any(t in action for t in triggers):
            return {
                "story_text": (
                    f"你屏退杂念，在心底默念出修炼意向。系统面板应声亮起：【检测到宿主意向·{route_name}】"
                    f"【初始功法发放中……】一束青光没入眉心，海量的行功路线在识海里铺开——"
                    f"正是《{gname}》。{gdesc}。系统轻响：【功法已录入，可随时行功修炼】。"
                ),
                "narration_world": state["player"]["world"],
                "choices": [
                    "就地盘膝，按功法行功修炼",
                    "先打开背包试试抽奖，看看运气",
                    "带着功法去荒野里探索",
                    "返回都市，先消化今晚的一切",
                ],
                "state_updates": {
                    **_EMPTY_UPDATES,
                    "realm_progress_delta": 3,
                    "technique_grant": {"route": route_name, "name": gname, "desc": gdesc + "。"},
                    "location": dict(state["player"]["location"]),
                },
                "system_notice": "",
            }
    return None

_URBAN_SEG = {
    "story_text": (
        "晚自习的钟声把你拉回教室，白炽灯依旧刺眼，仿佛刚才的一切只是一场走神。陈锐凑过来："
        "\"你刚才脸色白得吓人，没事吧？\"后排，苏晚晴安静地做着卷子，却在你看来的一瞬抬起了眼。"
        "下课前，一张折成方块的纸条从后排传到你手心，字迹清秀：\"放学别走，天台，有话问你。——苏\"。"
        "你摸了摸口袋——不知何时，多了一枚温润的灵石。"
    ),
    "narration_world": WORLD_URBAN,
    "choices": [
        "放学后天台赴约",
        "回消息婉拒，先回家研究系统",
        "把灵石拿给陈锐看，试探他的反应",
        "当晚再次穿越去修仙界修炼",
    ],
    "state_updates": {
        **_EMPTY_UPDATES,
        "realm_progress_delta": 3,
        "item_gained": [{"name": "下品灵石", "desc": "修仙界通用货币"}],
        "affinity_changes": [{"npc": "苏晚晴", "delta": 3, "reason": "主动递纸条约谈，心事重重"}],
        "new_side_quest": {"title": "天台之约", "desc": "苏晚晴明早天台有话要问——她似乎察觉了什么。"},
        "location": {"world": WORLD_URBAN, "place": "青临市"},
    },
    "system_notice": "",
}

_MARKET_SEG = {
    "story_text": (
        "你循着兽径向东方走了半日，荒草渐稀，土路上有了车辙——前面是一座溪畔青瓦的边陲小镇："
        "白溪镇。镇口商贩的吆喝、牲口的响鼻和油炸糕的香气一齐涌来，人间烟火扑面而至。"
        "你攥着仅有的几枚灵石，在集市里穿行，花两块灵石从一个啰嗦的摊主手里买下一份手绘舆图。"
        "拐角处，一名锦衣少年正与黑袍人低声交易，见到你，他脸色一沉，甩袖而去。"
        "那黑袍人却朝你微微颔首，转身没入巷影，只留一句飘忽的话：\"两界之钥，慎用。\""
        "系统面板悄然亮起：【检测到未知注视·线索已记录】。"
    ),
    "narration_world": WORLD_XIANXIA,
    "choices": [
        "追上去问黑袍人\"两界之钥\"是什么",
        "向摊主打听这座城和附近势力",
        "先在集市买些修炼资源",
        "不动声色，出城回荒野",
    ],
    "state_updates": {
        **_EMPTY_UPDATES,
        "realm_progress_delta": 2,
        "item_gained": [{"name": "白溪镇舆图", "desc": "摊主手绘的白溪镇舆图，标着几处不起眼的小铺", "count": 1}],
        "item_spent": [{"name": "下品灵石", "count": 2, "reason": "向摊主买下白溪镇舆图"}],
        "new_npc": [{"name": "黑袍人", "world": WORLD_XIANXIA, "role": "身份不明的黑袍客",
                     "persona": "白溪镇暗巷里与锦衣少年低声交易的神秘人，知晓\"两界之钥\"，对主角意味深长",
                     "place": "白溪镇", "label": "神秘注视", "affinity": 30}],
        "new_places": [{"world": WORLD_XIANXIA, "name": "白溪镇",
                        "desc": "荒野以东最近的凡人聚居地，边陲城池，鱼龙混杂、消息灵通。"}],
        "location": {"world": WORLD_XIANXIA, "place": "白溪镇"},
        "fact_record": "神秘黑袍人临别警告\"两界之钥，慎用\"——来历不明，是未回收的伏笔",
    },
    "system_notice": "【系统】发现新地点：白溪镇。主线线索已记录：\"两界之钥\"。",
}

_TIANTAI_SEG = {
    "story_text": (
        "放学后的天台，晚风把苏晚晴的马尾吹起一角。她盯着你看了很久，终于开口："
        "\"你最近……很不对劲。晚自习消失、成绩不降反升、连走路的样子都变了。\""
        "她往前一步，声音压得很低：\"我梦见你站在一座云里的山门 前——那是什么地方？\""
        "系统面板悄悄亮起：【检测到关键人物关注·剧情分支开启】。"
    ),
    "narration_world": WORLD_URBAN,
    "choices": [
        "坦白一部分：\"我确实遇到了奇遇\"",
        "敷衍过去：\"只是最近睡得好\"",
        "反问她梦里的细节",
        "沉默地看着远处的江面",
    ],
    "state_updates": {
        **_EMPTY_UPDATES,
        "affinity_changes": [{"npc": "苏晚晴", "delta": 5, "reason": "天台相见，交心之言"}],
        "quest_complete": "天台之约",
        "location": {"world": WORLD_URBAN, "place": "青临市"},
    },
    "system_notice": "",
}

_CYCLE = [_XIANYXIA_SEG, _URBAN_SEG, _MARKET_SEG]

_CULTIVATE_SEG = {
    "story_text": (
        "你寻了处避风的岩凹盘膝而坐，按系统发放的功法吐纳行功。系统的辅助视界悄然亮起，"
        "将周身灵气（都市里则是稀薄的游离能量）一丝丝引入经脉。丹田渐暖，气感壮大了一分，"
        "疲惫也随之消散。系统面板轻闪：修炼完成，修为提升。"
    ),
    "choices": [
        "继续修炼一个时辰",
        "起身活动，去别处看看",
        "查看系统面板，检视收获",
        "留意四周动静",
    ],
    "state_updates": {**_EMPTY_UPDATES, "realm_progress_delta": 6},
    "system_notice": "【系统】修炼完成：修为 +6（当前环境影响效率）。",
}


def _explore_segment(state: dict) -> dict:
    world = state["player"]["world"]
    places = state.get("map", {}).get(world, [])
    fog = next((p for p in places if not p.get("discovered")), None)
    if fog is None:
        return {
            "story_text": (
                "你沿着周围仔细走了一圈：街角的老店、桥下的暗渠、无人留意的小径……"
                "没有新的发现，倒是在石缝里捡到一枚被人遗落的灵石。"
            ),
            "choices": ["换个方向再探索", "前往别处", "打坐修炼", "查看系统面板"],
            "state_updates": {**_EMPTY_UPDATES,
                              "item_gained": [{"name": "下品灵石", "desc": "修仙界通用货币"}]},
            "system_notice": "",
        }
    name = fog["name"]
    return {
        "story_text": (
            f"你朝着地图上迷雾笼罩的方向一路探索过去。走着走着，眼前豁然开朗——"
            f"系统提示音随之响起：【发现新地点·{name}·已录入地图】。"
            f"{fog.get('desc') or '这片区域终于向你揭开了面纱。'}"
        ),
        "choices": [
            f"进入『{name}』一探究竟",
            "记下位置，先返回原地",
            "在附近小心侦查一圈",
            "打坐调息，恢复状态",
        ],
        "state_updates": {**_EMPTY_UPDATES,
                          "new_places": [{"world": world, "name": name,
                                          "desc": fog.get("desc", "")}]},
        "system_notice": f"【系统】探索成功：新地点『{name}』已揭示。",
    }


def next_segment(state: dict, action: str) -> dict:
    # 按行动类型分派演示段落
    gongfa = _gongfa_segment(state, action)
    if gongfa is not None:
        seg = gongfa
    elif "抽奖" in action:
        # 抽奖本身走背包通道（使用抽奖券），这里只给剧情反馈
        seg = {
            "story_text": (
                "你点开系统面板的抽奖页——【请在背包中使用\"系统抽奖券\"完成抽取】。"
                "指尖划过那叠薄薄的券纸，你决定找个安静时刻再试手气。"
            ),
            "choices": ["打开背包使用抽奖券", "先去做别的事", "打坐修炼", "查看系统面板"],
            "state_updates": {**_EMPTY_UPDATES},
            "system_notice": "【系统】提示：抽奖请在背包中选择\"系统抽奖券\"并点击使用。",
        }
    elif "天台" in action or "苏晚晴" in action and "赴" in action:
        seg = _TIANTAI_SEG
    elif "修炼" in action or "打坐" in action:
        seg = _CULTIVATE_SEG
    elif "探索" in action:
        seg = _explore_segment(state)
    elif "穿越" in action or "回去" in action or "返回" in action:
        seg = _XIANYXIA_SEG if state["player"]["world"] == WORLD_URBAN else _URBAN_SEG
    else:
        seg = _CYCLE[state["turn"] % len(_CYCLE)]
    # 演示模式每次也给一点修为，保证面板有变化
    updates = dict(seg["state_updates"])
    target_world = seg.get("narration_world", state["player"]["world"])
    if target_world != state["player"]["world"]:
        anchor = state["player"].get("places_memory", {}).get(target_world) or (
            "落星荒野" if target_world == WORLD_XIANXIA else "青临市")
        if (updates.get("location") or {}).get("place") != anchor:
            updates["location"] = {"world": target_world, "place": anchor}
            seg = dict(seg, story_text=f"穿越的白光散去，你回到了上次离开时的「{anchor}」。熟悉的景物没有变成别处；接下来的路仍需亲自走过。")
    updates["realm_progress_delta"] = updates.get("realm_progress_delta", 0) + 1
    return {**seg, "narration_world": seg.get("narration_world", state["player"]["world"]),
            "state_updates": updates,
            "story_text": f"（演示模式·内置示例剧情）{seg['story_text']}"}


def offline_result(state: dict, urban_days: float, xianxia_days: int) -> dict:
    return {
        "events": [
            {"world": WORLD_URBAN, "title": "陈锐替你值日",
             "text": f"你不在的{urban_days}天里，陈锐默默替你值了日，还在班群里帮你圆了请假的事，只发来一句：\"回来请我喝奶茶。\""},
            {"world": WORLD_URBAN, "title": "苏晚晴的欲言又止",
             "text": "苏晚晴给你发了两条消息又撤回，最后只留下一句：\"回来记得找我。\""},
            {"world": WORLD_XIANXIA, "title": "荒野并不平静",
             "text": f"修仙界已过{xianxia_days}天：落星荒野的兽群换了迁徙路线，夜里嚎声更近了；白溪镇集市正招募熟悉兽径的向导。"},
            {"world": WORLD_XIANXIA, "title": "白溪镇的风声",
             "text": "镇口贴出了新的悬赏：灵草溪谷深处的妖兽伤了两拨采药人，赏格是五十枚灵石。"},
        ],
        "messages": [
            {"npc": "陈锐", "title": "微信消息",
             "text": "人呢？？三天没回消息。再玩消失我可直接去你家找周阿姨问了啊。"},
        ],
        "affinity_changes": [
            {"npc": "陈锐", "delta": 2, "reason": "替你值日圆谎，讲义气"},
            {"npc": "苏晚晴", "delta": 3, "reason": "离线期间多次欲言又止，牵挂渐深"},
            {"npc": "周母", "delta": 1, "reason": "给你房间通风换洗了床单，念叨你住校辛苦"},
        ],
        "npc_events": ["赵擎在青玄宗外门月考核中拔得头名，风头正劲，放话\"某些不见了踪影的杂役最好别再出现\"（此事暂与主角无关，只是宗门风向）"],
    }
