"""演示模式内置剧情：未配置模型 API 时使用，保证全流程可跑通。"""
import zlib
from .models import WORLD_URBAN

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
            f"报到日的清晨，你——{name}，拖着半人高的行李箱走进京华大学的银杏大道。军训服还没领，"
            "校园卡刚捂热，迎新横幅在晨风里哗啦啦地响——大一新生的生活，就这样开始了。"
            "就在这时，视野里忽然浮起一行只有你能看见的淡金色小字：【心动系统·绑定成功】"
            "【初始等级：初露锋芒】【功能解锁：状态面板 / 任务 / 每日签到 / 系统商城 / 抽奖】。"
            "紧接着，手机轻轻一震——【开局礼包已发放：系统抽奖券×10，已入背包，随时可抽取】"
            "【初始天赋领取资格已激活：表达你的培养意向（学业/运动/音乐/创业/厨艺/摄影），"
            "即可领取对应路线的初始天赋（S级）】。"
            "锁屏上还压着两条未读：青梅竹马郭瑞莹从魔都发来的「到了吗？」，"
            "和游戏里认识两年的网友邓碧瑶发来的「开学快乐，晚上连麦？」——她们都是你早已熟识的人。"
            "不远处，一个拖着同款行李箱的身影正朝你用力挥手——是同班同学梁雅婷。"
        ),
        "narration_world": WORLD_URBAN,
        "choices": [
            "跑过去和梁雅婷一起排队办手续",
            "先打开背包，试试系统抽奖",
            "默念：我想走学业路线，领取初始天赋",
            "让梁雅婷先排着，自己找个安静角落研究系统",
        ],
        "state_updates": {
            **_EMPTY_UPDATES,
            "location": {"world": WORLD_URBAN, "place": "京华大学"},
        },
        "system_notice": "【系统】绑定完成。开局礼包已发放：系统抽奖券×10（背包或抽奖页使用）；初始天赋待表达培养意向后领取。每日签到已开启。",
    }


_WANQING_SEG = {
    "story_text": (
        "琴行的暖光落在郭瑞莹的马尾上。\"这么晚才从图书馆回来？\"她合上琴谱，"
        "顺手把一罐热牛奶塞进你手里，\"隔壁奶茶店买多了。\"你注意到她的指尖在琴谱封面上"
        "轻轻敲着——那是她有心事时的老习惯。\"周六老街咖啡馆，新出的手冲套餐，\"她别过脸，"
        "\"要来的话……提前说一声，我占位。\"你的口袋里，不知何时多出了三枚温热的系统金币。"
    ),
    "narration_world": WORLD_URBAN,
    "choices": [
        "答应她：周六老街咖啡馆见",
        "先打开背包试试抽奖，看看运气",
        "试探一句：\"你今晚好像有心事？\"",
        "婉拒，先回公寓研究系统",
    ],
    "state_updates": {
        **_EMPTY_UPDATES,
        "realm_progress_delta": 7,
        "item_gained": [{"name": "系统金币", "desc": "系统商城通用货币"}],
        "affinity_changes": [{"npc": "郭瑞莹", "delta": 3, "reason": "深夜琴行门口的偶遇，递来热牛奶与邀约"}],
        "new_side_quest": {"title": "周六的咖啡馆", "desc": "郭瑞莹约你周六去老街咖啡馆——她似乎有话想说。"},
        "location": {"world": WORLD_URBAN, "place": "外滩滨江"},
    },
    "system_notice": "",
}


_GUQINGYAN_SEG = {
    "story_text": (
        "第二天清晨的图书馆四楼，你刚落座，对面就传来一声极轻的叩桌。学生会长雅倩"
        "抱着两摞竞赛报名表站在你桌前，目光在你的摊开的高数书页上停了半秒：\"这道题，"
        "你的解法绕了远路。\"她放下一张写得密密麻麻的草稿纸，转身前留下一句：\"全国数学建模"
        "竞赛，京华大学还缺人。有兴趣，拿着纸来找我。\"整个四楼的目光都聚了过来。"
        "系统面板悄悄亮起：【检测到关键机遇·竞赛邀请】。"
    ),
    "narration_world": WORLD_URBAN,
    "choices": [
        "追上去答应她，报名建模竞赛",
        "先把草稿纸上的解法看懂再说",
        "苦笑婉拒：\"会长，我先保住绩点再说\"",
        "向旁边同学打听雅倩的传闻",
    ],
    "state_updates": {
        **_EMPTY_UPDATES,
        "realm_progress_delta": 6,
        "affinity_changes": [{"npc": "雅倩", "delta": 2, "reason": "图书馆主动点拨，留下竞赛邀约"}],
        "location": {"world": WORLD_URBAN, "place": "京华大学"},
    },
    "system_notice": "【系统】检测到机遇：数学建模竞赛（支线可接）。",
}


_SONGYUTANG_SEG = {
    "story_text": (
        "银杏商街的周六人潮汹涌。你替奶茶店发传单兼职工资一小时十八，隔壁摊位却来了个"
        "手忙脚乱的生面孔——戴着鸭舌帽的花碎花把试饮杯打翻了三排，正努力用店里的话术"
        "向路人道歉：\"抱歉，本店第二杯……第二杯真的半价。\"看到你憋笑的样子，她叉起腰："
        "\"笑什么！打工体验懂不懂！\"你们的摊位前，渐渐排起了看热闹的队。"
        "系统面板轻闪：【兼职收入已入账】。"
    ),
    "narration_world": WORLD_URBAN,
    "choices": [
        "帮她把摊位收拾利索，教她两句摊贩话术",
        "打趣她：\"大小姐，试饮杯不是这么摆的\"",
        "专心发自己的传单，各挣各的",
        "收工后请她喝一杯本店的奶茶",
    ],
    "state_updates": {
        **_EMPTY_UPDATES,
        "realm_progress_delta": 6,
        "item_gained": [{"name": "系统金币", "desc": "系统商城通用货币", "count": 2}],
        "affinity_changes": [{"npc": "花碎花", "delta": 3, "reason": "发传单初识，出丑被撞见却不恼，反而觉得你有趣"}],
        "location": {"world": WORLD_URBAN, "place": "银杏商街"},
    },
    "system_notice": "【系统】兼职结算：系统金币 +2。",
}


_COFFEE_SEG = {
    "story_text": (
        "周六的老街咖啡馆，郭瑞莹坐在窗边，面前摆着两杯手冲。\"我妈想让我转去国外的音乐学院，\""
        "她搅着咖啡，声音很轻，\"可我走了，这边就真的只剩你一个人了。\"窗外海风掠过风铃，"
        "叮的一声。她抬起眼看你，那双总是清亮的眼睛里第一次有了藏不住的期待："
        "\"你说，我该怎么选？\"系统面板悄悄亮起：【重要人物的人生抉择·你的回答将影响关系走向】。"
    ),
    "narration_world": WORLD_URBAN,
    "choices": [
        "认真替她分析两条路的利弊",
        "\"无论你怎么选，我都支持你\"",
        "\"留下来——我舍不得你走\"",
        "沉默片刻，先问她自己心里想要什么",
    ],
    "state_updates": {
        **_EMPTY_UPDATES,
        "affinity_changes": [{"npc": "郭瑞莹", "delta": 5, "reason": "咖啡馆交心，把人生抉择说给你听"}],
        "quest_complete": "周六的咖啡馆",
        "location": {"world": WORLD_URBAN, "place": "外滩滨江"},
    },
    "system_notice": "",
}


# 培养路线 -> 初始天赋（按意向发放对应路线初始最高品质天赋）
# 触发词必须是明确的路线表述，避免"上自习"之类的泛用词误判
_TALENT_ROUTES = [
    (["学业", "学习路线", "学霸"], "学业", "过目成诵（S级）", "学业天赋：记忆与理解力大幅强化，刷题如饮水，绩点如探囊取物"),
    (["运动", "健身", "体育"], "运动", "钢筋铁骨（S级）", "运动天赋：体能恢复与肌肉记忆远超常人，任何运动上手极快"),
    (["音乐", "吉他", "钢琴", "唱歌"], "音乐", "绝对音感（S级）", "音乐天赋：绝对音感与乐感加持，作曲演唱乐器皆如有神助"),
    (["创业", "生意", "搞钱"], "创业", "商业嗅觉（S级）", "创业天赋：对商机与人心异常敏锐，小本经营也能嗅出风口"),
    (["厨艺", "做饭", "做菜", "烹饪"], "厨艺", "黄金味觉（S级）", "厨艺天赋：味觉与火候掌控天赋，家常菜也能做出让人落泪的味道"),
    (["摄影", "拍照"], "摄影", "决定性瞬间（S级）", "摄影天赋：对光线与瞬间的直觉惊人，随手一拍都是大片"),
]


def _talent_segment(state: dict, action: str) -> dict | None:
    """玩家表达了明确的培养意向时发放初始天赋；一次性闸在引擎的 player.technique。"""
    if state["player"].get("technique"):
        return None
    for triggers, route_name, tname, tdesc in _TALENT_ROUTES:
        if any(t in action for t in triggers):
            return {
                "story_text": (
                    f"你在心底默念出培养意向。系统面板应声亮起：【检测到宿主意向·{route_name}路线】"
                    f"【初始天赋发放中……】一阵暖流从后颈漫上头顶，仿佛有人把你这些年模糊的\"想做\""
                    f"一次性擦亮——【{tname}】已录入。{tdesc}。"
                    f"系统轻响：【天赋已录入，配合日常训练逐步兑现】。"
                ),
                "narration_world": WORLD_URBAN,
                "choices": [
                    "当晚就去图书馆/操场试一试天赋",
                    "先打开背包试试抽奖，看看运气",
                    "带着新目标出门探索这座城市",
                    "给梁雅婷发消息，分享今晚的好心情",
                ],
                "state_updates": {
                    **_EMPTY_UPDATES,
                    "realm_progress_delta": 8,
                    "technique_grant": {"route": route_name, "name": tname, "desc": tdesc + "。"},
                    "location": dict(state["player"]["location"]),
                },
                "system_notice": "",
            }
    return None


_CYCLE = [_WANQING_SEG, _GUQINGYAN_SEG, _SONGYUTANG_SEG]


_CULTIVATE_SEG = {
    "story_text": (
        "你按天赋路线开始自我提升：图书馆的角落、操场夜的跑道，或公寓里练到手酸的琴弦。"
        "系统的辅助视界悄悄亮起，把每一次重复折算成肉眼可见的成长曲线。汗水落地的声音里，"
        "疲惫退去，某种笃定的东西正在长出来。系统面板轻闪：训练完成，等级进度提升。"
    ),
    "narration_world": WORLD_URBAN,
    "choices": [
        "再加练一小时",
        "起身活动，去别处看看",
        "查看系统面板，检视收获",
        "约梁雅婷出来吃顿夜宵犒劳自己",
    ],
    "state_updates": {**_EMPTY_UPDATES, "realm_progress_delta": 8},
    "system_notice": "【系统】训练完成：等级进度 +8（贵在坚持）。",
}


def _explore_segment(state: dict) -> dict:
    world = state["player"]["world"]
    places = state.get("map", {}).get(world, [])
    fog = next((p for p in places if not p.get("discovered")), None)
    if fog is None:
        return {
            "story_text": (
                "你沿着周围仔细逛了一圈：街角的老店、桥洞下的涂鸦、无人留意的小巷……"
                "没有新的发现，倒是在共享单车的车筐里捡到一枚没人认领的系统金币。"
            ),
            "choices": ["换个方向再探索", "前往别处", "回学校训练", "查看系统面板"],
            "state_updates": {**_EMPTY_UPDATES,
                              "item_gained": [{"name": "系统金币", "desc": "系统商城通用货币"}]},
            "system_notice": "",
        }
    name = fog["name"]
    return {
        "story_text": (
            f"你朝着地图上迷雾笼罩的方向一路探索过去。转过最后一个街角，眼前豁然开朗——"
            f"系统提示音随之响起：【发现新地点·{name}·已录入地图】。"
            f"{fog.get('desc') or '这片区域终于向你揭开了面纱。'}"
        ),
        "choices": [
            f"走进『{name}』好好逛逛",
            "记下位置，先返回原地",
            "在附近打听打听有什么好玩的好吃的",
            "拍张照发给梁雅婷，约她下次一起来",
        ],
        "state_updates": {**_EMPTY_UPDATES,
                          "new_places": [{"world": world, "name": name,
                                          "desc": fog.get("desc", "")}]},
        "system_notice": f"【系统】探索成功：新地点『{name}』已揭示。",
    }


def _date_segment(state: dict, action: str) -> dict | None:
    """演示模式的约会段：邀约对象好感≥亲近(70)才算正式约会。"""
    target = next((n for n in state.get("npcs", []) if n["name"] in action), None)
    if target is None or "约会" not in action:
        return None
    place = "星愿游乐园"
    if target["affinity"] < 70:
        return {
            "story_text": (
                f"你鼓起勇气约{target['name']}周末出去玩。她眨眨眼，笑得爽朗：\"出去走走可以呀——"
                "叫上大家一起呗？\"你笑着应下，心里却明白：现在的你们，还只是能一起热闹的朋友。"
                "系统面板安静地亮了一行小字：【正式约会需关系达到「亲近」（好感70）】。"
            ),
            "narration_world": WORLD_URBAN,
            "choices": ["先和朋友们一起出去玩", "送她一份礼物拉近关系", "最近多约她自习", "查看系统面板"],
            "state_updates": {**_EMPTY_UPDATES,
                              "affinity_changes": [{"npc": target["name"], "delta": 1, "reason": "主动邀约，虽是朋友局也不算坏事"}]},
            "system_notice": "",
        }
    return {
        "story_text": (
            f"周六的星愿游乐园，摩天轮缓缓升向全城最高的夜色。你和{target['name']}排到了最后一班——"
            "轿厢里只有你们两个人，她抱着刚赢来的玩偶，耳朵尖有点红。\"其实……\"她望着脚下渐远的灯火，"
            "声音轻得像怕惊动谁，\"今天很开心。\"升到最高点时，整座魔都的灯海铺在脚下，"
            "谁都没有说话。系统面板悄悄亮起：【约会时刻·已存入回忆】。"
        ),
        "narration_world": WORLD_URBAN,
        "choices": [
            "轻声说：\"以后还想一起来。\"",
            "把刚赢的玩偶递给她",
            "安静地陪她看完这片灯海",
            "鼓起勇气，说出那句准备了很久的话",
        ],
        "state_updates": {
            **_EMPTY_UPDATES,
            "affinity_changes": [{"npc": target["name"], "delta": 6, "reason": "摩天轮顶的独处，心意悄悄靠近"}],
            "date_with": target["name"],
            "location": {"world": WORLD_URBAN, "place": place},
            "new_places": [{"world": WORLD_URBAN, "name": place,
                            "desc": "山顶的游乐园，摩天轮据说是全城告白成功率最高的地方。"}],
        },
        "system_notice": "【系统】发现约会圣地：星愿游乐园。",
    }


# 演示练习段：关键词→技能经验（走 skill_progress 契约，与真实模式同一条结算通道）


def _practice_segment(state: dict, action: str) -> dict | None:
    """练习关键词 → 对应技能经验段。命中任一关键词即返回，否则 None。"""
    pairs = [("唱歌", "vocal"), ("练声", "vocal"), ("声乐", "vocal"),
             ("弹琴", "instrument"), ("练琴", "instrument"), ("吉他", "instrument"),
             ("排位", "mech"), ("打游戏", "mech"), ("操作", "mech"),
             ("复盘", "sense"), ("看比赛", "sense"),
             ("摆摊", "manage"), ("生意", "manage"), ("进货", "manage"),
             ("理财", "invest"), ("炒股", "invest"),
             ("编程", "coding"), ("写代码", "coding"), ("敲代码", "coding"),
             ("做菜", "cooking"), ("烹饪", "cooking"), ("做饭", "cooking"),
             ("摄影", "photo"), ("拍照", "photo"),
             ("演讲", "speech"), ("辩论", "speech"),
             ("表演", "acting"), ("演技", "acting"), ("排练", "stage"), ("剧本", "acting")]
    sid = next((s for kw, s in pairs if kw in action), None)
    if sid is None:
        return None
    from .skills import SKILLS
    name = SKILLS[sid][0]
    return {
        "story_text": (
            f"你找了个安静的角落开始练{name}。起初生涩，反复几十遍后指尖（或喉头）渐渐找到了感觉——"
            "系统面板轻闪，一条淡金色的经验提示浮起。成长这种事，从来都是笨功夫堆出来的。"
        ),
        "narration_world": WORLD_URBAN,
        "choices": [f"继续练{name}", "休息一下去干别的", "查看系统面板"],
        "state_updates": {**_EMPTY_UPDATES,
                          "skill_progress": [{"skill": sid, "xp": 15, "reason": f"练习{name}"}]},
        "system_notice": "",
    }


def next_segment(state: dict, action: str) -> dict:
    # 按行动类型分派演示段落
    talent = _talent_segment(state, action)
    if talent is not None:
        seg = talent
    elif "约会" in action:
        seg = _date_segment(state, action) or _CYCLE[state["turn"] % len(_CYCLE)]
    elif "抽奖" in action:
        # 抽奖本身走背包通道（使用抽奖券），这里只给剧情反馈
        seg = {
            "story_text": (
                "你点开系统面板的抽奖页——【请在背包中使用\"系统抽奖券\"完成抽取】。"
                "指尖划过那叠薄薄的券纸，你决定找个安静时刻再试手气。"
            ),
            "choices": ["打开背包使用抽奖券", "先去做别的事", "回学校训练", "查看系统面板"],
            "state_updates": {**_EMPTY_UPDATES},
            "system_notice": "【系统】提示：抽奖请在背包中选择\"系统抽奖券\"并点击使用。",
        }
    elif "琴行" in action:
        seg = _WANQING_SEG
    elif "咖啡馆" in action or ("郭瑞莹" in action and "赴" in action):
        seg = _COFFEE_SEG
    elif "训练" in action or "修炼" in action or "健身" in action or "自习" in action:
        seg = _CULTIVATE_SEG
    elif (p_seg := _practice_segment(state, action)) is not None:
        seg = p_seg
    elif "探索" in action:
        seg = _explore_segment(state)
    elif "办手续" in action or "排队" in action:
        seg = {
            "story_text": "你追上梁雅婷，和她排进迎新处的队伍。她帮你扶住快要滑下去的行李，你替她确认了宿舍登记表。"
                          "校园卡、材料和军训通知一张张收好，刚才还陌生的报到日终于有了可以一起说话的人。"
                          "她指着宣传栏上的星河计划：‘想试试吗？一个学期做完一件事。’你把报名信息记下，"
                          "没有因为这个邀请就替自己选定方向。眼下手续已经办好，接下来可以去看看主线任务，"
                          "也可以先整理行李，慢慢认识这座校园。",
            "choices": ["去看看主线任务，选一个愿意完成的方向", "默念：我想走学业路线，领取初始天赋", "探索校园周边"],
            "state_updates": {**_EMPTY_UPDATES, "affinity_changes": [{"npc": "梁雅婷", "delta": 2, "reason": "报到时互相照应"}],
                              "fact_record": "报到日与梁雅婷一起完成了入学登记。"},
            "system_notice": "入学登记完成；中栏的「主线任务」可以查看报名方向。",
        }
    elif state.get("ending"):
        ending = state["ending"]
        partner = ending.get("partner")
        seg = {
            "story_text": f"《{ending['title']}》之后，生活还在继续。你把星河计划的记录收好，给今天留了一点空白。"
                          + (f"{partner}已经是你认真确认过关系的人，一次闲聊也不需要重新从陌生开始。" if partner else
                             "你记得自己选择独自出发，也依然可以认真对待留在生活里的朋友。")
                          + "这一季发生过的事没有消失：做完的作品、说清的分歧、对未来的打算，都成为接下来相处的背景。"
                          "你决定先从眼前一件小事开始。训练、探索和与熟悉的人约会仍然可以继续，新的日常会在这些行动里展开。",
            "choices": ["投入训练，保持自己的节奏", "探索当前地点周边", "和熟悉的人聊聊假期打算"],
            "state_updates": {**_EMPTY_UPDATES}, "system_notice": "番外生活继续，主线与关系选择已经保留。",
        }
    else:
        seg = _CYCLE[state["turn"] % len(_CYCLE)]
    # 演示模式每次也给一点等级进度，保证面板有变化
    updates = dict(seg["state_updates"])
    updates["realm_progress_delta"] = updates.get("realm_progress_delta", 0) + 4
    # 演示节奏：段落 6-8 + 尾 4 ≈ 每回合 10-12，首升恰在第 10 回合前后
    return {**seg, "narration_world": seg.get("narration_world", state["player"]["world"]),
            "state_updates": updates,
            "story_text": seg["story_text"]}


def chat_reply(state: dict, npc: dict, text: str) -> str:
    """演示模式的微信回复：按人设口吻的循环模板，保证流程可跑。"""
    name = npc["name"]
    short = text[:14] + ("…" if len(text) > 14 else "")
    templates = [
        f"「{short}」……你这条消息我盯着看了两遍😄 晚点再聊？",
        f"收到收到。刚看到你在忙这个——{name}我可记下了。",
        f"哈哈，你这人真是。行，就这么说定了？",
        f"嗯，我在。你说，我听着呢。",
   ]
    if npc.get("likes") == "情趣":
        templates.append("对了，上次你送的那个我还留着呢。有心了。")
    if npc.get("affinity", 0) >= 85:
        templates.append("……没什么，就是忽然想看看你有没有在线。")
    return templates[zlib.crc32(text.encode("utf-8")) % len(templates)]


def offline_result(state: dict, days: float) -> dict:
    return {
        "events": [
            {"world": WORLD_URBAN, "title": "梁雅婷替你带了三天早餐",
             "text": f"你消失的{days}天里，梁雅婷每天雷打不动给你带一份豆浆油条，凉了就自己吃掉，"
                     "只发来一句：\"下次玩消失，早餐费结一下。\""},
            {"world": WORLD_URBAN, "title": "社团招新季",
             "text": "京华大学社团招新摊位摆满了银杏大道，学生会的筹备例会开到了深夜；"
                     "听说雅倩亲自盯建模竞赛的报名名单，在你的名字上停了很久。"},
            {"world": WORLD_URBAN, "title": "奶茶店的排班表",
             "text": "银杏商街那家奶茶店把你从兼职群置顶：\"再不来，工时就被别人抢光了。\""
                     "隔壁摊位的花碎花倒是天天全勤，手法已经像模像样。"},
            {"world": WORLD_URBAN, "title": "隔壁的宵夜",
             "text": "合租公寓的门把手上挂过两次还温着的食盒——邓碧瑶阿姨式的投喂从不多问，"
                     "便利贴上只画了一个笑脸。"},
        ],
        "messages": [
            {"npc": "郭瑞莹", "title": "微信消息",
             "text": "好几天没见你人影。琴行新到了一批琴谱……周六还是老时间，别又放我鸽子。"},
        ],
        "moments": [
            {"npc": "花碎花", "text": "奶茶店打工第三天，终于没打翻试饮杯🎉 谁说大小姐不行的！", "image": "工牌+奶茶的自拍"},
            {"npc": "梁雅婷", "text": "抢到了新生篮球赛的现场位！周五走起", "image": "看台视角的球场"},
        ],
        "affinity_changes": [
            {"npc": "梁雅婷", "delta": 2, "reason": "天天带早餐，嘴上嫌弃心里担心"},
            {"npc": "郭瑞莹", "delta": 3, "reason": "离线期间多次点开对话框，欲言又止"},
        ],
        "npc_events": ["学生会筹备招新时，雅倩与前来\"视察\"的花碎花在摊位前表面客气地寒暄，实则互相较劲（与主角暂无直接关系，只是校园风向）"],
    }
