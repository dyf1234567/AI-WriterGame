"""第一学期主线：显式行动、共同经历与玩家选择驱动，和等级成长分别记账。"""
from copy import deepcopy

TITLE = "星河计划 · 第一学期"
CHAPTERS = ("第一章 · 写下名字", "第二章 · 一起准备", "第三章 · 两个约定",
            "第四章 · 灯亮之前", "第五章 · 把话说完", "本季终章 · 新的起点")
ROUTES = {
    "学业": ("城市生活调研", "头脑", "把调研里的真实问题讲清楚"),
    "运动": ("校园公益跑", "体魄", "让第一次参加的人也能跑到终点"),
    "音乐": ("原创音乐演出", "魅力", "让一首自己的歌被认真听见"),
    "创业": ("校园公益市集", "情商", "让一笔收支透明的小生意真正运转"),
    "厨艺": ("校园深夜食堂", "体魄", "用一份热饭接住晚归的人"),
    "摄影": ("新生影像展", "头脑", "留下校园里容易被忽略的人"),
}
PREPARATION_TASKS = {
    "学业": ("完成第一轮访谈，保留不同立场的原话", "核对数据，重新推敲被反例推翻的结论", "试讲调研报告，回答现场追问"),
    "运动": ("实地走完路线，标出补给与安全点", "核对物资和人手，调整新手也能参加的配速", "完成一次全流程试跑，补上遗漏的接应"),
    "音乐": ("把旋律写成能听见的第一版小样", "重录不稳定的段落，重新安排编曲", "完成一次整场试演，练习失误时怎样接下去"),
    "创业": ("写出预算和进货清单，算清每一笔成本", "做一次小范围试卖，按反馈调整方案", "核对收支与分工，公开完整账本"),
    "厨艺": ("试做第一份菜单，记录口味和份量", "核对成本与卫生流程，改掉忙时容易出错的步骤", "邀请同学试吃，完成一轮真实出餐"),
    "摄影": ("确定影像主题，拍下第一组样片", "征得被摄者授权，按反馈重新选片", "完成编排与装裱，测试展览的观看顺序"),
}
ARCS = {
    "梁雅婷": {
        "wish": "这一次，她想在作品上写自己的名字，而不只是替别人收尾",
        "promise": "陪她把第一次独立策划的开场排练完",
        "scene": "梁雅婷把写了又划掉的策划书摊在桌上，手指停在署名栏。",
        "closing": "她终于把自己的名字写进负责人一栏，也学会把做不到的事坦白说出来",
    },
    "郭瑞莹": {
        "wish": "她想试一次不依靠完美演奏、也能表达自己的合作",
        "promise": "准时接通她为你们留出的线上试演",
        "scene": "郭瑞莹从魔都发来一段有错音的录音，罕见地没有撤回。",
        "closing": "她把那段带着错音的初稿留了下来，因为你们都记得它后来怎样完成",
    },
    "邓碧瑶": {
        "wish": "她想从游戏语音里的队友，成为能被认真介绍的项目伙伴",
        "promise": "按约定上线，陪她完成第一次公开远程介绍",
        "scene": "邓碧瑶在群里发了自我介绍，又私聊问你：这样说，会不会很奇怪？",
        "closing": "她在远程回顾会上开口介绍自己，屏幕那头的关系终于有了生活中的位置",
    },
}
PREFIX = "【主线】"


def default_campaign() -> dict:
    return {"version": 1, "chapter": 0, "route": "", "companion": "",
            "preparations": 0, "approaches": [], "conflict": "", "show_result": "",
            "resolution": "", "completed": [], "evidence": [], "finale_notified": False,
            "started_day": None, "paused": False}


def ensure_campaign(state: dict) -> dict:
    current = state.get("campaign")
    if not isinstance(current, dict):
        current = default_campaign()
        # 已经发生的旧结局原样保留，绝不替玩家重选或抹掉旧周目。
        if state.get("ending"):
            current.update(chapter=5, legacy_ending=True)
        state["campaign"] = current
    for key, value in default_campaign().items():
        current.setdefault(key, deepcopy(value))
    try:
        current["chapter"] = max(0, min(5, int(current["chapter"])))
        current["preparations"] = max(0, min(3, int(current["preparations"])))
    except (ValueError, TypeError):
        current["chapter"], current["preparations"] = 0, 0
    for key in ("completed", "evidence", "approaches"):
        if not isinstance(current[key], list):
            current[key] = []
    if current.get("started_day") is not None:
        try:
            current["started_day"] = max(1, int(current["started_day"]))
        except (TypeError, ValueError):
            current["started_day"] = max(1, int(state.get("time", {}).get("day", 1)))
    if state.get("ending"):
        current["chapter"] = 5
        if current["route"] not in ROUTES:
            current["legacy_ending"] = True
        return current
    if current["route"] not in ROUTES:
        current["route"] = ""
        if not current.get("legacy_ending"):
            current["chapter"] = 0
    if current["companion"] not in ARCS:
        current["companion"] = ""
        if current["chapter"] >= 2:
            current["chapter"] = 1
    if current["chapter"] >= 2 and current["preparations"] < 3:
        current["chapter"] = 1
    if current["chapter"] >= 3 and current["conflict"] not in ("promise", "deadline"):
        current["chapter"] = 2
    if current["chapter"] >= 4 and not current["show_result"]:
        current["chapter"] = 3
    if current["chapter"] >= 5 and current["resolution"] not in ("honest", "future"):
        current["chapter"] = 4
    return current


def _npc(state: dict, name: str) -> dict | None:
    return next((n for n in state.get("npcs", []) if n.get("name") == name), None)


def _actions(state: dict) -> list[dict]:
    c = ensure_campaign(state)
    ch = c["chapter"]
    if state.get("ending") or ch >= 5:
        return []
    if c.get("paused"):
        return [{"id": "resume", "label": "继续参加校园星河计划"}]
    if ch == 0:
        return [{"id": f"plan:{route}", "label": f"选择{route} · {info[0]}"}
                for route, info in ROUTES.items()]
    if ch == 1:
        if not c["companion"]:
            return [{"id": f"team:{name}", "label": f"邀请{name}共同筹备"}
                    for name in ARCS if _npc(state, name)]
        return [{"id": "prepare:skill", "label": "打磨作品（推进一周，专项属性 +2）"},
                {"id": "prepare:team", "label": "共同排练（推进一周，情商 +2、增进了解）"}]
    if ch == 2:
        return [{"id": "conflict:promise", "label": "先兑现与搭档的约定，接受少一轮打磨"},
                {"id": "conflict:deadline", "label": "优先赶完作品，坦白告知搭档会缺席"}]
    if ch == 3:
        stat = ROUTES[c["route"]][1]
        return [{"id": "present:steady", "label": "按计划稳妥呈现（推进到展演日）"},
                {"id": "present:bold", "label": f"展演尝试突破（推进日期；{stat} ≥12 可获提名，不足会救场）"}]
    if not c["resolution"]:
        if c["conflict"] == "promise":
            return [{"id": "resolve:honest", "label": "回看守约的代价，说出当时的担心"},
                    {"id": "resolve:future", "label": "认真听她的未来打算，约定坦诚沟通"}]
        return [{"id": "resolve:honest", "label": "把遗漏和失望说清楚，补上那次约定"},
                {"id": "resolve:future", "label": "听她的打算，协商放下旧约并坦诚沟通"}]
    return [{"id": "review", "label": "赴期末回顾会（推进日期，解锁终章选择）"}]


def action_label(state: dict, action: str) -> str | None:
    """剧情回看也使用玩家看见的行动名称，不暴露内部节点标识。"""
    if action.startswith(PREFIX):
        action_id = action[len(PREFIX):].strip()
        return next((a["label"] for a in _actions(state) if a["id"] == action_id), "查看当前主线行动")
    return None


def campaign_view(state: dict) -> dict:
    c = ensure_campaign(state)
    ch, name = c["chapter"], c["companion"]
    objectives = ["报名星河计划：选一个你愿意做完的方向，等级不会替你完成项目。",
                  (f"与{name}完成三周筹备：{c['preparations']}/3。打磨作品与共同排练会留下不同成果。"
                   if name else "邀请一位搭档，先了解她这一次想完成什么。"),
                  "截稿和约定撞在一起。作出选择，并承担它对作品与搭档的影响。",
                  "选择展示方式：稳妥完成，或根据能力尝试突破；受挫也有继续的故事。",
                  ("已经把话说完，参加期末回顾会，为这一季写下结尾。" if c["resolution"] else
                   "展演结束了，和搭档回看那次选择，完成修复或新的约定。"),
                  "本季关键经历已完成。选择愿意认真开始的关系，或带着成果独自出发。"]
    if state.get("ending"):
        objectives[5] = "本季已完结。你可以继续探索、相处与成长，往后的故事属于番外。"
    if c.get("paused"):
        objectives[ch] = "你暂时不参加星河计划，已有经历保留。可以发展事业、旅行和自己的生活，愿意时再回来。"
    return {**deepcopy(c), "title": CHAPTERS[ch], "objective": objectives[ch],
            "actions": _actions(state), "ready": ch < 5 and not state.get("ending") and not c.get("paused"),
            "finale_ready": ch == 5 and not state.get("ending") and not c.get("paused"), "campaign_title": TITLE, "optional": True}


def _change_stat(state: dict, key: str, amount: int) -> None:
    stats = state["player"].setdefault("stats", {})
    stats[key] = max(0, min(99, stats.get(key, 0) + amount))


def _record(state: dict, text: str, *, promise: bool = False) -> None:
    from . import memory
    known_by = [n["name"] for n in state.get("npcs", [])
                if n.get("name") and n["name"] in text]
    memory.append_fact(state, text, state.get("turn", 0),
                       "承诺" if promise else "事实", known_by=known_by)


def _advance_to(state: dict, day: int) -> None:
    clock = state.setdefault("time", {"day": 1, "slot": 0})
    if int(clock["day"]) < day:
        clock.update(day=day, slot=3)


def _commit(state: dict, action_id: str) -> list[str]:
    """只处理已经核验的主线行动；预演仅操作深拷贝，无存档/模型副作用。"""
    c = ensure_campaign(state)
    name = c["companion"]
    label = ""
    if action_id.startswith("plan:"):
        c["route"] = action_id.split(":", 1)[1]
        c["started_day"] = int(state.get("time", {}).get("day", 1))
        c["chapter"] = 1
        label = f"报名{c['route']}方向：{ROUTES[c['route']][0]}"
        for known_name in ARCS:
            person = _npc(state, known_name)
            if person:
                person["known_to_player"] = True
                person["last_seen_turn"] = state.get("turn", 0)
    elif action_id.startswith("team:"):
        name = c["companion"] = action_id.split(":", 1)[1]
        label = f"与{name}组队，听见她的目标：{ARCS[name]['wish']}"
        _record(state, f"与{name}的星河计划约定：{ARCS[name]['promise']}。", promise=True)
    elif action_id.startswith("prepare:"):
        approach = action_id.split(":", 1)[1]
        c["preparations"] += 1
        c["approaches"].append(approach)
        stat = ROUTES[c["route"]][1] if approach == "skill" else "情商"
        _change_stat(state, stat, 2)
        _advance_to(state, int(state["time"]["day"]) + 7)
        label = f"第{c['preparations']}周筹备：{'作品打磨' if approach == 'skill' else '共同排练'}，{stat}+2"
        if c["preparations"] == 3:
            c["chapter"] = 2
    elif action_id.startswith("conflict:"):
        c["conflict"] = action_id.split(":", 1)[1]
        c["chapter"] = 3
        _advance_to(state, int(c.get("started_day") or 1) + 41)
        if c["conflict"] == "promise":
            label = f"兑现了与{name}的约定，作品少了一轮打磨"
            from . import memory
            memory.resolve_fact(state, f"与{name}的星河计划约定：{ARCS[name]['promise']}。", state.get("turn", 0))
        else:
            _change_stat(state, ROUTES[c["route"]][1], 2)
            label = f"优先赶稿并提前说明缺席，{name}仍然感到失落，作品专项属性+2"
    elif action_id.startswith("present:"):
        from .models import effective_stats
        approach = action_id.split(":", 1)[1]
        stat = ROUTES[c["route"]][1]
        if approach == "steady":
            result = "稳妥完成了完整展示"
        elif effective_stats(state).get(stat, 0) >= 12:
            result = "突破版本获得最佳创意提名"
        else:
            result = "突破版本现场失误，你和搭档一起完成救场"
        c["show_result"], c["chapter"] = result, 4
        _advance_to(state, int(c.get("started_day") or 1) + 55)
        label = f"{ROUTES[c['route']][0]}：{result}"
        identities = state["player"].setdefault("identity", {})
        membership = f"星河计划{c['route']}组成员"
        current_identity = identities.get("urban", "")
        if membership not in current_identity:
            identities["urban"] = "·".join(filter(None, (current_identity, membership)))
    elif action_id.startswith("resolve:"):
        c["resolution"] = action_id.split(":", 1)[1]
        if c["conflict"] == "promise":
            label = (f"和{name}回看守约的代价，说出当时的担心" if c["resolution"] == "honest" else
                     f"认真听取{name}的未来打算，约定继续坦诚沟通")
        else:
            label = (f"和{name}补上遗漏的约定，承认选择的代价" if c["resolution"] == "honest" else
                     f"与{name}协商不再补办旧约，承认遗憾并约定提前沟通")
        person = _npc(state, name)
        if person:
            person["project_arc_complete"] = True
        from . import memory
        memory.resolve_fact(state, f"与{name}的星河计划约定：{ARCS[name]['promise']}。", state.get("turn", 0))
        _record(state, f"我与{name}约定，今后遇到冲突提前说明，不擅自替彼此决定。", promise=True)
    elif action_id == "review":
        c["chapter"] = 5
        _advance_to(state, int(c.get("started_day") or 1) + 119)
        label = f"第一学期期末回顾：{c['show_result']}；{ARCS[name]['closing']}"
    if label:
        event = f"{action_id}:{c['preparations']}" if action_id.startswith("prepare:") else action_id
        c["completed"].append(event)
        c["evidence"].append(label)
        _record(state, f"星河计划：{label}。")
        person = _npc(state, name)
        if person:
            note = f"第{state.get('turn', 0)}回合：{label}"[:140]
            person.setdefault("memory", []).append(note)
            person["memory"] = person["memory"][-6:]
            person.setdefault("known_memory", []).append(note)
            person["known_memory"] = person["known_memory"][-12:]
            person.setdefault("deeds", []).append({"turn": state.get("turn", 0), "text": note})
            person["deeds"] = person["deeds"][-20:]
    return [f"【主线】{label}。"] if label else []


def _scene(state: dict, action_id: str) -> str:
    c = ensure_campaign(state)
    name = c["companion"]
    if action_id.startswith("plan:"):
        route = action_id.split(":", 1)[1]
        project, _, purpose = ROUTES[route]
        return (f"报名表停在你面前。星河计划给新生一个学期，把一件自己在乎的事做完。"
                f"你在{route}栏写下名字：{project}。{purpose}，这是你给自己的第一个具体目标。"
                "梁雅婷把空白的组队表推过来：‘这回先找愿意一起做的人。’郭瑞莹从魔都发来语音，"
                "说可以远程参与；邓碧瑶在熟悉的游戏聊天里问，要不要把队友关系延伸到生活里。"
                "你看着三个名字。计划刚刚开始，选择谁，也意味着认真听见她想做什么。")
    if action_id.startswith("team:"):
        name = action_id.split(":", 1)[1]
        arc = ARCS[name]
        return (f"{arc['scene']}你没有急着分派任务，先问了她这一次想要什么。{arc['wish']}。"
                "那一刻，组队表上的名字有了重量。你们把三周的准备拆成三次可以完成的事："
                "有人要把作品打磨得更好，也有人需要一起排练，学会在对方面前出错。"
                f"你认真答应：{arc['promise']}。她确认了时间，才在名单上落下自己的名字。")
    if action_id.startswith("prepare:"):
        count = c["preparations"] + 1
        if action_id.endswith("skill"):
            task = PREPARATION_TASKS[c["route"]][count - 1]
            reactions = ("第一次把想法交给别人看，你发现漂亮的设想和实际完成之间隔着不少细节。",
                         "这一次，意见真正撞在了一起。你解释取舍，也留下对方说得有道理的部分。",
                         "这次练习像正式展示的缩影。你们约好不掩饰失误，出了问题先把事情完成。")
            return (f"你把这一周留给{ROUTES[c['route']][0]}。初稿的漏洞逐一露出来，你没有借系统的光跳过它们。"
                    f"这是第{count}轮筹备，你要{task}，再把能交付的版本给{name}看。{reactions[count - 1]}"
                    "周末收工时，桌上的改动已经能被别人看见。作品进了一步，也提醒你还有一个约定要守。")
        team_tasks = ("你们先把各自想要的结果写下来，重新分配那张看似已经安排好的任务表。",
                      "排练中出现了第一次分歧。你们各自解释最不愿退让的地方，试着找一个双方都能接受的版本。",
                      "你们轮流模拟台下的提问，让对方独立讲完自己的部分，再把失误处重新练了一遍。")
        return (f"你选择把这一周用来和{name}共同排练。你们轮流解释自己的部分，发现彼此并不总能听懂。"
                f"这是第{count}轮筹备。{team_tasks[count - 1]}你问起她最在意哪一点，才知道那些看似琐碎的坚持，"
                "其实和她想在这次合作里成为怎样的人有关。练习结束后，你把共同决定的修改写进清单。"
                "作品推进得慢一些，配合却不再只靠猜测。你开始知道，和一个人一起做事也需要学习。")
    if action_id.startswith("conflict:"):
        moment = ("截稿日临近，" if int(state.get("time", {}).get("day", 1)) < int(c.get("started_day") or 1) + 41
                  else "延期后的截稿日终于到了，")
        if action_id.endswith("promise"):
            return (f"{moment}截稿提醒和{name}确认时间的消息同时亮起。你看着还想重做的最后一部分，"
                    f"最终按原先的约定，{ARCS[name]['promise']}。你提前说明作品会少一轮打磨。"
                    "她没有把这当成理所当然，也没有保证一切都会顺利，只把预留的那一部分认真做完。"
                    "回到作品前，你知道明天交出的版本不会完美，但今晚答应一个人的事已经有了结果。")
        return (f"{moment}你决定先赶完作品，并在约定时间之前联系{name}说明缺席。"
                "消息发出去后，对面安静了一会儿：‘我知道你着急，可我确实等了这一天。’"
                "你没有把提前告知当作已经弥补，也没有让系统替你抹平她的失落。"
                "多出来的一轮打磨让作品更扎实，空下来的那个位置却还在。你把欠着的谈话记在清单上，"
                "准备等展演结束，认真听她把话说完。")
    if action_id.startswith("present:"):
        from .models import effective_stats
        stat = ROUTES[c["route"]][1]
        bold = action_id.endswith("bold")
        capable = effective_stats(state).get(stat, 0) >= 12
        result = ("突破版本拿到了最佳创意提名，评委追问起你们最初的想法" if bold and capable else
                  "突破版本在现场出了岔子，你停下来说明问题，和搭档一起把最后一段救了回来" if bold else
                  "准备过的版本从头到尾完整呈现，掌声没有轰动全场，却有观众留下来认真提问")
        return (f"约定的展演日终于到来，星河计划的成果展示开始。你们把{ROUTES[c['route']][0]}带到台前，"
                f"这一次选择的是{'突破' if bold else '稳妥'}版本。{result}。"
                f"{name}在属于自己的那一部分开口了，声音也许还不够稳，但没有再把名字藏在你的后面。"
                "灯亮了又暗。你第一次能拿出一件具体的事，回答这个学期自己做过什么。"
                "至于那个关于约定的问题，仍然需要你们自己回答。")
    if action_id.startswith("resolve:"):
        if c["conflict"] == "promise":
            if action_id.endswith("honest"):
                return (f"展演之后，{name}重新提起你选择守约的那一晚。她想知道，你有没有因为少打磨了一轮而后悔。"
                        "你没有用一句‘都过去了’带过，认真说出那时对作品的担心，也听她讲为什么那次配合很重要。"
                        f"{ARCS[name]['closing']}。那件已经完成的约定不需要再补做一次，但那些没来得及说的话，"
                        "终于有了位置。你们确认，以后遇到冲突，仍然先把真实打算说出来。")
            return (f"你和{name}回看那次已经兑现的约定，然后认真问起对方下一个学期的打算。"
                    f"她说起这个项目里最难的部分，也提起自己终于靠近的目标：{ARCS[name]['wish']}。"
                    "你们没有用一句包办未来的保证结束谈话，而是确认以后遇到冲突仍提前沟通。"
                    "这次共同完成的事会留在记忆里，下一段经历也可以从真正听懂彼此开始。")
        if action_id.endswith("honest"):
            return (f"展演之后，你约{name}把那次冲突重新说清。你说起自己的着急，也认真听她讲等待时的心情。"
                    "你们把当时没有做完的环节重新安排了一次，没有要求一句道歉立刻抵消所有失落。"
                    f"{ARCS[name]['closing']}。最后，你们确认了一件很小却具体的事："
                    "下次遇到时间冲突，先把真实打算说出来。关系没有被分数宣布完成，"
                    "却有了一段你们都能指认的经历。")
        return (f"你和{name}没有急着定义彼此，而是认真问起对方下一个学期的打算。"
                f"她说起这个项目里最难的部分，也提起那个一直没放下的愿望：{ARCS[name]['wish']}。"
                "你承认自己并非总能兼顾所有事。她决定不再补办已经过去的环节，你们共同确认放下那次旧约，"
                "保留未能兼顾的遗憾，并约定以后提前沟通，不用突然缺席或沉默代替回答。"
                "这次谈话留下的不是一个包办未来的保证，而是彼此都确认过的相处方式。"
                "学期还在继续，你们终于可以带着真实的打算往前走。")
    return (f"这一季结束时，你带着星河计划的记录来到回顾会。三周筹备、一次冲突和那场展示，"
            f"如今都能在清单上找到结果：{c['show_result']}。{ARCS[name]['closing']}。"
            "有人准备假期回家，有人已经在想下一次合作。你自己的生活也会继续，世界没有在这一天结束，"
            "但这个从报名表开始的故事，已经可以由你写下一个完整的句号。"
            "你可以向有过共同经历的人认真表达心意，也可以选择独自出发。接下来的决定，属于你。")


def before_turn(state: dict, action: str) -> dict | None:
    if not action.startswith(PREFIX):
        return None
    action_id = action[len(PREFIX):].strip()
    if action_id in ("pause", "resume"):
        c = ensure_campaign(state)
        c["paused"] = action_id == "pause"
        story = "你暂时把星河计划放在一旁，接下来先安排自己的生活。已有的共同经历仍会留下。" if c["paused"] else "你重新联系了项目组，准备从上次的进度继续。自己的事业与生活也会同时发展。"
        return {"story_text": story, "narration_world": "urban", "choices": ["继续自己的行程", "看看朋友的近况"], "state_updates": {"duration_minutes": 15}, "system_notice": ""}
    allowed = {a["id"] for a in _actions(state)}
    if action_id not in allowed:
        raise ValueError("这一步的前置经历尚未完成，或已经完成。请查看任务面板的当前主线行动。")
    text = _scene(state, action_id)
    c = ensure_campaign(state)
    name = action_id.split(":", 1)[1] if action_id.startswith("team:") else c["companion"]
    preview = deepcopy(state)
    _commit(preview, action_id)
    next_actions = _actions(preview)
    choices = [PREFIX + a["id"] for a in next_actions[:6]]
    if len(choices) < 2:
        choices += ["回看这段经历，继续自由探索", "给熟悉的人发一条消息"]
    updates = {"realm_progress_delta": 6, "location": {"world": "urban", "place": "京华大学"},
               "affinity_changes": ([{"npc": name, "delta": 3, "reason": "共同完成星河计划的关键经历"}]
                                    if name else [])}
    return {"story_text": text, "narration_world": "urban", "choices": choices[:6],
            "state_updates": updates, "system_notice": ""}


def after_turn(state: dict, data: dict, action: str = "") -> list[str]:
    if not action.startswith(PREFIX):
        return []
    action_id = action[len(PREFIX):].strip()
    if action_id not in {a["id"] for a in _actions(state)}:
        return []
    return _commit(state, action_id)


def ending_options(state: dict) -> list[dict]:
    if not campaign_view(state)["finale_ready"]:
        return []
    from .relationships import _readiness, ensure_relationship
    from .models import is_romanceable
    options = [{"name": n["name"], "label": f"与{n['name']}认真开始新的关系"}
               for n in state.get("npcs", [])
               if n.get("known_to_player") and is_romanceable(n) and n.get("affinity", 0) >= 85
               and (ensure_relationship(n)["status"] in ("partner", "distance") or _readiness(state, n)[0])]
    return sorted(options, key=lambda option: option["name"])


def choose_ending(state: dict, partner: str | None) -> dict:
    c = ensure_campaign(state)
    if state.get("ending"):
        return {"ok": False, "msg": "本季已经写下结局，可以继续番外，或从恢复点重新选择。"}
    if c["chapter"] != 5:
        return {"ok": False, "msg": "还没有完成本季的关键经历，请先完成任务面板里的主线。"}
    if partner is not None and partner not in {o["name"] for o in ending_options(state)}:
        return {"ok": False, "msg": "这段关系还缺少共同经历或明确心意，暂时不能选择。"}
    from .models import now_iso, advance_time
    route, companion = c["route"], c["companion"]
    if not route or companion not in ARCS or not c["show_result"] or not c["resolution"]:
        return {"ok": False, "msg": "主线记录不完整，请从恢复点继续完成关键经历。"}
    if partner:
        from .relationships import ensure_relationship, relationship_action
        person = _npc(state, partner)
        if ensure_relationship(person)["status"] not in ("partner", "distance"):
            confirmation = relationship_action(state, partner, "确认", "exclusive")
            if not confirmation.get("ok"):
                return confirmation
    title = f"与{partner}的新篇章" if partner else "属于自己的新篇章"
    consequence = ("你记得那晚把约定放在了作品前面，接受了少一轮打磨的遗憾。" if c["conflict"] == "promise" else
                   "你记得自己曾为赶稿缺席，也记得后来没有让失落停在一句解释里。")
    if c["conflict"] == "promise":
        resolution = ("你们后来回看守约的代价，把当时没有说出口的担心也讲给对方听。" if c["resolution"] == "honest" else
                      "你们认真交换了未来的打算，决定以后继续坦诚沟通，不让彼此猜测。")
    else:
        resolution = ("你们后来补上了那次约定，也把自己的难处说给对方听。" if c["resolution"] == "honest" else
                      "你们认真交换了未来的打算，共同决定不再补办旧约、记住遗憾，以后不再让彼此猜测。")
    text = (f"期末回顾会散场，京华大学的灯一盏盏亮起来。你把{ROUTES[route][0]}的记录收好："
            f"{c['show_result']}。{consequence}{resolution}{companion}的变化也留在这些记录里——"
            f"{ARCS[companion]['closing']}。")
    if partner:
        text += (f"你找到{partner}，没有用模糊的玩笑绕开这一次表达：‘我想认真和你在一起。’"
                 "对方认真确认了你的意思，也说出了自己的心意。你们决定从这一天开始，"
                 "把恋人的身份放进以后的安排里；遇到冲突，仍然要说出来、一起作决定。")
        person = _npc(state, partner)
        person["relationship_status"] = "恋人"
        person["label"] = "恋人"
        from .relationships import ensure_relationship
        ensure_relationship(person).update(status="partner", mode="exclusive",
                                           proposal=None)
        state["partner"] = partner
        _record(state, f"我与{partner}互相确认心意，决定正式交往。", promise=True)
    else:
        text += ("你没有为了给故事一个热闹的答案而匆忙开始恋爱。你向同行的人认真道谢，"
                 "也把属于自己的下一步写下来。共同完成的事会留下，朋友也不会因为这个选择消失。")
    education = state["player"].get("education", {})
    text += ("校园里的学习还在继续。" if education.get("status", "enrolled") == "enrolled" else "你已有了新的生活安排。") + "这个校园篇章已经写完，事业、关系与城市生活仍从新的起点继续。"
    state["turn"] = state.get("turn", 0) + 1
    advance_time(state, 1)
    state["ending"] = {"kind": "semester", "title": title, "text": text, "partner": partner,
                       "turn": state["turn"]}
    story = state.setdefault("story", [])
    if story and story[-1].get("chosen") is None:
        story[-1]["chosen"] = f"终章选择：{partner or '独自出发'}"
    story.append({"world": "urban", "text": text, "turn": state["turn"], "ts": now_iso(),
                  "choices": ["和熟悉的人聊聊假期打算", "继续探索城市，开始番外"], "chosen": None})
    state["last_active"] = now_iso()
    _record(state, f"第一学期星河计划结束，选择《{title}》，之后进入番外。")
    return {"ok": True, "msg": f"本季终章《{title}》已写入回忆。接下来可以继续番外。"}
