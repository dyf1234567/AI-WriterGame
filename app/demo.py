"""演示模式内置剧情：未配置模型 API 时使用，保证全流程可跑通。"""
import re
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
            "报到日的清晨，行李箱的轮子卡进了京华大学银杏大道的砖缝。你刚把箱子提起来，"
            "夹在拉杆上的登记表又掉了。\n"
            f"一个女生替你捡起表，先看了眼姓名栏：“{name}？咱们一个班。我叫梁雅婷，"
            "迎新处在那边，跟我排吧。”这是你们第一次搭话。\n"
            "手机上还有两条未读。青梅竹马郭瑞莹从魔都音乐学院发来一句“到了吗”；"
            "游戏里认识两年、尚未线下见过的邓碧瑶发来一句“开学快乐，晚上连麦？”\n"
            "你正要回消息，一行淡金色小字挡住了输入框：【心动系统·绑定成功】。"
            "初始等级是“初露锋芒”，状态面板、任务、每日签到、系统商城和抽奖依次亮起。"
            "开局礼包已发放：系统抽奖券×10，放在背包里；初始天赋尚待你从学业、运动、音乐、"
            "创业、厨艺、摄影中表达培养意向。\n"
            "“看什么呢？队伍要拐弯了。”梁雅婷拿着你的登记表，已经替你留了一个位置。"
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
            "scene_npcs": ["梁雅婷"],
        },
        "system_notice": "【系统】绑定完成。开局礼包已发放：系统抽奖券×10（背包或抽奖页使用）；初始天赋待表达培养意向后领取。每日签到已开启。",
    }


_WANQING_SEG = {
    "story_text": (
        "郭瑞莹趁周末来京都看你，约你在银杏商街的琴行碰面。暖光落在她的马尾上。\"这么晚才从图书馆回来？\"她合上琴谱，"
        "顺手把一罐热牛奶塞进你手里，\"隔壁奶茶店买多了。\"你注意到她的指尖在琴谱封面上"
        "轻轻敲着——那是她有心事时的老习惯。\"周六老街咖啡馆，新出的手冲套餐，\"她别过脸，"
        "\"要来的话……提前说一声，我占位。\"系统面板轻闪：记录一次共同经历，系统积分 +1。"
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
        "item_gained": [{"name": "系统积分", "desc": "系统商城通用货币"}],
        "affinity_changes": [{"npc": "郭瑞莹", "delta": 3, "reason": "深夜琴行门口的偶遇，递来热牛奶与邀约"}],
        "new_side_quest": {"title": "周六的咖啡馆", "desc": "郭瑞莹约你周六去老街咖啡馆——她似乎有话想说。"},
        "location": {"world": WORLD_URBAN, "place": "银杏商街"},
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
        "item_gained": [{"name": "华夏币", "desc": "发传单的兼职工资", "count": 18},
                        {"name": "系统积分", "desc": "系统商城通用货币", "count": 2}],
        "duration_minutes": 60,
        "affinity_changes": [{"npc": "花碎花", "delta": 3, "reason": "发传单初识，出丑被撞见却不恼，反而觉得你有趣"}],
        "location": {"world": WORLD_URBAN, "place": "银杏商街"},
    },
    "system_notice": "【系统】兼职工资：华夏币 +18；成长奖励：系统积分 +2。",
}


_COFFEE_SEG = {
    "story_text": (
        "周六的老街咖啡馆，郭瑞莹坐在窗边，面前摆着两杯手冲。\"我妈想让我转去国外的音乐学院，\""
        "她搅着咖啡，声音很轻，\"可我走了，就不能像现在这样抽个周末来京都找你了。\"窗外街风掠过风铃，"
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
        "location": {"world": WORLD_URBAN, "place": "银杏商街"},
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


def _cultivate_segment(state: dict, action: str) -> dict:
    place = (state["player"].get("location") or {}).get("place") or "当前地点"
    if "自习" in action:
        attempt = "你把刚才答错的那一步遮住，重新推了一遍。第二次仍卡在同一处，于是翻回前一页，把漏掉的条件圈出来。"
        stop = "这回没急着往后翻。你在空白处写下了第一行。"
    elif any(word in action for word in ("健身", "运动", "跑步")):
        attempt = "第一组还没结束，节奏就乱了。你停下来把目标减了一点，重新数数；这次只管把眼前的一组做完整。"
        stop = "记录里多了一组完成数，下一组还没开始。"
    else:
        attempt = "你先试了一遍，把最不顺的地方单独记下。重来时没再从头赶进度，只盯着那一处，直到能完整做过去。"
        stop = "你在这次的记录末尾留了一行：下次从这里接着来。"
    return {**_CULTIVATE_SEG, "story_text": f"你在{place}给这次练习划了一个小目标。\n{attempt}\n{stop}",
            "choices": ["再练一小段", "歇一会再继续", "看看刚才的练习记录"],
            "system_notice": "【系统】本次训练已记录。"}


def _explore_segment(state: dict) -> dict:
    world = state["player"]["world"]
    places = state.get("map", {}).get(world, [])
    fog = next((p for p in places if not p.get("discovered")), None)
    if fog is None:
        return {
            "story_text": (
                "你沿着周围仔细逛了一圈：街角的老店、桥洞下的涂鸦、无人留意的小巷……"
                "没有新的发现，倒是在共享单车的车筐里捡到一枚没人认领的系统积分。"
            ),
            "choices": ["换个方向再探索", "前往别处", "回学校训练", "查看系统面板"],
            "state_updates": {**_EMPTY_UPDATES,
                              "item_gained": [{"name": "系统积分", "desc": "系统商城通用货币"}]},
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
    attempts = {
        "vocal": "唱到换气的地方，最后一个字没能落稳。你把那一句截出来，放慢再唱，先把气息接上，才重新放回整段。",
        "instrument": "连过去时总抢半拍，你干脆停在换指的地方。两个音、四个音，再把前后接起来；这一次终于没断。",
        "mech": "回放停在交手前一秒。你把刚才漏看的位置记下来，重新试了一次，没有再照着旧路线往里冲。",
        "sense": "你把那段回放倒回去，先不看输赢，只找第一个改变局面的决定。写下理由后，原先想当然的一步就显得不太对了。",
        "manage": "纸上原先只写了售价，成本却漏了一项。补进去以后，刚才还像样的利润薄了一截，你把那行报价重新算了一遍。",
        "invest": "你把原先只盯着的涨幅遮住，先列可能亏在哪里。算到自己能承受的上限时，拟好的计划被划掉了半行。",
        "coding": "报错又停在同一行。你没有继续往上补代码，而是把输入缩成最小的一组；那个不起眼的条件终于露了出来。",
        "cooking": "照着步骤做了一遍，味道仍差一点。你先把原因记下，再单独调整一处，没有急着把所有调料都往里加。",
        "photo": "第一张照片里该看的东西反而不显眼。你换了取景范围，把多余的一角让出去，再拍一张，留下两张慢慢比。",
        "speech": "录音放到第二遍，你才发现一句话里塞了三个意思。删去前面的铺垫，再说一遍，要紧的那句话终于不用等到结尾。",
        "acting": "同一句台词试了两遍，重音一换，意思也跟着偏了。你把夸张的语气收掉，先想清楚这句话到底想让对方做什么。",
        "stage": "你把刚才乱掉的那一小段拆开，记住起点和接续的位置。再连起来时，终于不用靠临时猜下一步。",
    }
    place = (state["player"].get("location") or {}).get("place") or "当前地点"
    return {
        "story_text": (
            f"你在{place}停下别的安排，给{name}留出一段时间。\n"
            + attempts.get(sid, "你把最拿不准的一步单独试了几次，记下问题，再重新接上前后。")
            + "\n这一处先记下来，接着练还是暂时歇会儿，你还没决定。"
        ),
        "narration_world": WORLD_URBAN,
        "choices": [f"继续练{name}", "休息一下去干别的", "查看系统面板"],
        "state_updates": {**_EMPTY_UPDATES,
                          "skill_progress": [{"skill": sid, "xp": 15, "reason": f"练习{name}"}]},
        "system_notice": "",
    }


def _everyday_segment(state: dict, action: str) -> dict:
    """A local scene for unsupported free input; never replay an unrelated first meeting."""
    location = dict(state["player"].get("location") or {})
    place = location.get("place") or "眼前这处地方"
    clean = re.sub(r"[<>\r\n]+", "", str(action)).strip()[:90].rstrip("。！？!?")
    known = [npc for npc in state.get("npcs", [])
             if npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0)]
    target = next((npc for npc in known if npc.get("name") and npc["name"] in clean), None)
    if not re.search(r"问|聊|说|打招呼|找|发消息|短信|微信|电话|连麦|通话|联系", clean) or re.search(r"回想|想起|如果|假如|考虑|不去找|不想见", clean):
        target = None
    updates = {**_EMPTY_UPDATES, "location": location, "scene_npcs": []}
    if target is not None:
        name = target["name"]
        messaging = any(word in clean for word in ("发消息", "短信", "微信", "打电话", "连麦", "通话"))
        if target.get("place") == place or messaging:
            channel = f"你在{place}给{name}发去消息" if messaging else f"你在{place}找到{name}，把话题接了下去"
            reply = chat_reply(state, target, clean)
            story = f"{channel}。\n“{reply}”"
            updates["scene_npcs"] = [name]
            choices = [f"接着和{name}聊刚才的话题", "先说清自己想做的事", "在当前地点看看"]
        else:
            story = (f"你还在{place}，眼前没有{name}的身影。\n"
                     f"你打开和她的对话框，想说的话还留在输入栏。消息没有发出去。")
            choices = [f"给{name}发消息", f"前往{target['place']}" if target.get("place") else "先确认她在哪里",
                       "留在当前地点"]
        return {"story_text": story, "narration_world": WORLD_URBAN, "choices": choices,
                "state_updates": updates, "system_notice": ""}

    entry = next((row for row in state.get("map", {}).get(WORLD_URBAN, []) if row.get("name") == place), {})
    setting = {
        "campus": "公告栏前换了一拨人，一张写着截止日期的通知还夹在旧海报下面。",
        "transport": "广播报过一趟班次，检票口前的队伍往前挪了一截。",
        "nature": "前面的路分成两岔，路牌上标着各自通往的方向。",
        "culture": "入口的告示列着今天开放的区域，你把其中一行重新看了一遍。",
        "leisure": "旁边的招牌已经亮了，门口有人在等同伴。",
    }.get(entry.get("type"), "街上的人各有去处，路边店铺的价目牌就立在门口。")
    if any(word in clean for word in ("考虑", "打算", "计划", "整理", "想一想")):
        story = f"你在{place}重新理了理打算：‘{clean}’。\n{setting}\n手机上的备忘录还开着，第一件要做的事尚未选定。"
    elif any(word in clean for word in ("休息", "歇会", "等一等", "等等", "不动", "坐一会")):
        story = f"你留在{place}，暂时停下手头的事。\n{setting}这会儿你没有接下新的安排。"
    elif re.search(r"[?？]|怎么|为什么|能不能|可不可以|多少|是否", str(action)):
        story = f"你在{place}把问题想得更具体了一些：‘{clean}’。\n{setting}\n你还需要一个确切的答复，事情暂时没有往下办。"
    else:
        story = f"你没有急着离开{place}。\n{setting}\n眼下惦记的还是‘{clean or '接下来做什么'}’这件事，下一步还留在你手里。"
    return {"story_text": story, "narration_world": WORLD_URBAN,
            "choices": ["在当前地点看看", "给熟悉的人发消息", "打开地图，选下一站"],
            "state_updates": updates, "system_notice": ""}


def next_segment(state: dict, action: str) -> dict:
    # 按行动类型分派演示段落
    talent = _talent_segment(state, action)
    if talent is not None:
        seg = talent
    elif "约会" in action:
        seg = _date_segment(state, action) or _everyday_segment(state, action)
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
        seg = _cultivate_segment(state, action)
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
        seg = _everyday_segment(state, action)
    # 演示模式每次也给一点等级进度，保证面板有变化
    updates = dict(seg["state_updates"])
    updates["realm_progress_delta"] = updates.get("realm_progress_delta", 0) + 4
    # 演示节奏：段落 6-8 + 尾 4 ≈ 每回合 10-12，首升恰在第 10 回合前后
    return {**seg, "narration_world": seg.get("narration_world", state["player"]["world"]),
            "state_updates": updates,
            "story_text": seg["story_text"]}


def _chat_voice(npc: dict) -> str:
    traits = str(npc.get("role", "")) + str(npc.get("persona", ""))
    if any(word in traits for word in ("辅导员", "老师", "教授")):
        return "teacher"
    if any(word in traits for word in ("话多", "嘴碎", "热心", "消息灵通", "记者")):
        return "brisk"
    if any(word in traits for word in ("网友", "队友", "电竞", "游戏")):
        return "gamer"
    if any(word in traits for word in ("高冷", "克制", "理性", "学霸")):
        return "precise"
    return "familiar" if "青梅竹马" in traits else "plain"


def _chat_memory(state: dict, npc: dict, text: str) -> str:
    """Recall dated, shared evidence only; affection and gift preferences prove no event."""
    name = npc["name"]
    if re.search(r"(?:想|准备|打算|要)送|喜欢什么.{0,5}礼物", text):
        return "不用急着买。你先说想送什么，我再告诉你合不合适。"
    if any(word in text for word in ("礼物", "送你", "送的", "送给")):
        for deed in reversed(npc.get("deeds") or []):
            note = deed.get("text", "") if isinstance(deed, dict) else str(deed)
            gift = re.search(r"送礼：收到礼物『([^』]+)』", note)
            if gift:
                return f"记得，你送的{gift.group(1)}。那份心意我收到了。"
        return "你说的是哪份礼物？把名字告诉我，免得我记错。"
    if any(word in text for word in ("约好", "约定", "说好", "几点见", "还去吗")):
        entries = [entry for entry in state.get("appointments", []) if isinstance(entry, dict) and entry.get("npc") == name]
        active = next((entry for entry in reversed(entries) if entry.get("status") == "pending"), None)
        if active:
            return f"我记着的是‘{str(active.get('text', ''))[:90]}’。你要改哪个地方？"
        proposed = next((entry for entry in reversed(entries) if entry.get("status") == "proposed"), None)
        if proposed:
            return f"‘{str(proposed.get('text', ''))[:90]}’还在商量，时间地点没有说定。"
        return "我们还没说定这件事。你把时间和地点发来，我们再商量。"
    if not any(word in text for word in ("记得", "上次", "以前", "那次", "还记着")):
        return ""
    query = re.sub(r"你|我|还|记得|上次|以前|那次|的事|吗|[\W_]", "", text)
    terms = {query[index:index + 2] for index in range(len(query) - 1)}
    candidates = []
    for fact in list(state.get("facts_history") or []) + list(state.get("facts") or []):
        if not isinstance(fact, dict) or fact.get("scope") == "private" and name not in (fact.get("known_by") or []):
            continue
        body = str(fact.get("text", ""))
        if name not in body and name not in (fact.get("known_by") or []):
            continue
        score = sum(term in body for term in terms)
        if score >= 2:
            try:
                turn = int(fact.get("turn", 0))
            except (TypeError, ValueError):
                turn = 0
            candidates.append((score, turn, body))
    if candidates:
        body = max(candidates)[2]
        return f"我记着‘{body[:90]}’这件事。你问的是这一段吗？"
    return "你再提一句是哪件事吧。我不想把别的事记到你头上。"


def chat_reply(state: dict, npc: dict, text: str) -> str:
    """Small semantic demo responses, grounded in this person's recorded state."""
    text = str(text).strip()
    voice = _chat_voice(npc)
    recalled = _chat_memory(state, npc, text)
    if recalled:
        return recalled
    if re.search(r"不(?:去|想|约|能|愿意)|取消|改天|别约", text):
        return {"brisk": "行，不催你。你先把自己的事忙完。", "precise": "好，那就先不往下安排。",
                "gamer": "行，先不约。你忙你的。"}.get(voice, "好，不勉强。你先忙自己的。")
    if any(word in text for word in ("女朋友", "男朋友", "恋人", "我们在一起了吗")):
        status = (npc.get("relationship") or {}).get("status")
        if status in ("partner", "distance"):
            return "我们已经认真说定过关系了。有哪里让你不踏实，直接问我。"
        return "我们还没有把关系说定。喜欢是一回事，要不要在一起得两个人都点头。"
    if any(word in text for word in ("我喜欢你", "我爱你", "想和你在一起")):
        return "这句话我听见了。可我不想隔着一条消息就把我们的关系定下来，等认真聊过再说。"
    if any(word in text for word in ("一起", "约你", "见面", "陪我", "有空吗")):
        return {"brisk": "想约我就把时间地点发来，我看看能不能排开。", "precise": "先说具体时间和地点，我再确认。",
                "gamer": "哪天，去哪儿？先把时间对上，别各等各的。"}.get(voice, "你想约哪天，去哪里？我们先把时间对一对。")
    if any(word in text for word in ("累", "难受", "烦", "考砸", "失眠", "失败")):
        return {"brisk": "先别把所有事揽一块儿。是哪件最烦？说来听听。", "precise": "先说出了什么问题。能处理的，我们一件一件看。",
                "gamer": "不顺就先歇一局。要吐槽哪件事，我听着。"}.get(voice, "不想硬撑就先歇会儿。发生什么了，愿意说就说。")
    if any(word in text for word in ("在哪", "在干嘛", "在做什么")):
        return "你是想过来找我，还是有事要问？我先确认一下，省得你白跑。"
    if "晚安" in text:
        return {"brisk": "晚安，别说完又熬夜。", "gamer": "晚安，明天再聊。", "teacher": "早点休息，明天的事明天再做。"}.get(voice, "晚安，睡个好觉。")
    if any(word in text for word in ("你好", "在吗", "早安", "打招呼")):
        return {"brisk": "在呢。怎么，找我打听什么？", "precise": "在。什么事？", "gamer": "在，能聊。你说。",
                "teacher": "在，有什么事直接说。", "familiar": "在呢，想和我说什么？"}.get(voice, "在。你说，我听着。")
    if any(word in text for word in ("练琴", "编曲", "练声", "演出", "排练")):
        return "先挑你最拿不准的一段说，别急着整首从头再来。" if any(word in str(npc.get("persona", "")) + str(npc.get("role", "")) for word in ("音乐", "钢琴", "歌手")) else "你卡在哪一步了？先说具体的那一处。"
    return {"brisk": "你先说最想弄明白的那一件，别一口气全挤过来。", "precise": "你想先处理哪一件？说具体一点。",
            "gamer": "你想怎么弄？先把目标说清楚，别各打各的。", "teacher": "把具体情况说一下，我先看看。",
            "familiar": "你先说自己的打算，我听完再开口。"}.get(voice, "你是怎么想的？我想先听你把话说完。")


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
