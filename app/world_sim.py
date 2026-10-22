"""随游戏日推进的分层人物生活和可选都市暗线，无现实离线计时。"""
from .models import ensure_life, find_npc
from . import character_arcs, memory, relationships


def _known(npc):
    return bool(npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0))


def _seed(npc):
    return sum(ord(c) for c in str(npc.get("id") or npc.get("name", "")))


def _precision(state, npc):
    if not _known(npc):
        return "background"
    location = (state.get("player", {}).get("location") or {}).get("place")
    rel = relationships.ensure_relationship(npc)
    return ("close" if npc.get("place") == location or int(npc.get("encounters", 0)) >= 6
            or rel["status"] in ("partner", "distance") else "milestone")


def _plan(npc, day, cycle=0, precision="background"):
    """只为角色安排角色自己的行动，不替玩家答应邀约。"""
    role = str(npc.get("role", ""))
    if any(x in role for x in ("歌", "乐", "团", "舞", "唱", "演员", "明星")):
        items = [("准备新的作品", "完成作品小样并收到同行反馈"),
                 ("参加外地演出或工作交流", "完成一次外地工作，认识新的创作伙伴"),
                 ("调整合作合同与休息安排", "重新确认合作边界，留出日常生活的时间")]
    elif any(x in role for x in ("电竞", "游戏", "陪玩", "解说")):
        items = [("复盘近期比赛", "整理比赛复盘，调整下一轮训练"),
                 ("参与城市赛事工作", "完成赛事工作，与新的队伍建立联系"),
                 ("考虑训练与职业分工", "重新确定队伍分工，保留自己的职业决定权")]
    elif any(x in role for x in ("学生", "同学", "学姐", "校花", "保研", "辅导", "社长", "学妹")):
        items = [("推进自己的课题或工作", "完成阶段材料，得到导师或同事的反馈"),
                 ("参加校外实习或交流", "完成校外交流，与城市里的同行建立联系"),
                 ("商量接下来的学习与工作", "按自己的意愿调整深造、实习与生活计划")]
    else:
        items = [("整理近期的工作与生活", "完成一项手头工作，调整下周计划"),
                 ("与朋友参加城市交流", "认识新的同行，与旧朋友继续保持联络"),
                 ("尝试新的合作与生活安排", "完成一次新的合作，保留自己的休息时间")]
    text, outcome = items[cycle % len(items)]
    gap = {"close": 7 + _seed(npc) % 7, "milestone": 21, "background": 30}[precision]
    return {"day": day + gap, "slot": 2, "place": npc.get("place", ""), "text": text,
            "outcome": outcome, "source": "world", "cycle": cycle, "precision": precision}


def ensure_world(state):
    day = max(1, int((state.get("time") or {}).get("day", 1)))
    world = state.setdefault("world_sim", {})
    world.setdefault("last_day", day)
    world.setdefault("background", {})
    world.setdefault("history", [])
    world.setdefault("mystery", {"status": "dormant", "stage": 0, "clues": [],
                                 "history": [], "choice": "", "permissions": []})
    character_arcs.ensure_arcs(state, int(world["last_day"]))
    for npc in state.get("npcs", []):
        relationships.ensure_relationship(npc)
        life = ensure_life(npc, day)
        life.setdefault("completed", [])
        life.setdefault("cycle", 0)
        npc.setdefault("autonomy", {"work_progress": 0, "education_progress": 0,
                                    "connections": [], "achievements": [], "social_status": "独立生活"})
        if not life.get("goal"):
            life["goal"] = "把自己的工作与日常逐步安顿下来"
        # 不覆盖模型已经安排的具体日程；到期时同样由引擎回收。
        if not life.get("next"):
            life["next"] = _plan(npc, int(world["last_day"]), int(life["cycle"]), _precision(state, npc))
            life["world_plan"] = dict(life["next"])
    return world


def _apply_plan(state, npc, plan, due_day):
    life = ensure_life(npc, due_day)
    saved_plan = life.get("world_plan") or {}
    planned_outcome = saved_plan.get("outcome") if saved_plan.get("text") == plan.get("text") else None
    outcome = str(plan.get("outcome") or planned_outcome or f"完成了「{plan.get('text', '原定安排')}」，正在决定下一步")[:100]
    life["cycle"] = int(life.get("cycle", 0)) + 1
    life.setdefault("completed", []).append({"day": due_day, "text": str(plan.get("text", ""))[:80], "outcome": outcome})
    life["completed"] = life["completed"][-8:]
    life.update(status=outcome[:80], mood="平静", updated_day=due_day)
    autonomy = npc.setdefault("autonomy", {})
    autonomy["work_progress"] = int(autonomy.get("work_progress", 0)) + 1
    if any(x in npc.get("role", "") for x in ("学", "保研")) and due_day < 1461:
        autonomy["education_progress"] = min(100, int(autonomy.get("education_progress", 0)) + 5)
    if life["cycle"] % 3 == 0:
        achievements = autonomy.setdefault("achievements", [])
        achievements.append({"day": due_day, "text": "完成一轮独立工作或学习计划"})
        autonomy["achievements"] = achievements[-6:]
        colleagues = [n for n in state.get("npcs", []) if n is not npc and
                      n.get("place") == npc.get("place") and n["name"] not in (npc.get("rels") or {})]
        if colleagues:
            other = colleagues[_seed(npc) % len(colleagues)]
            npc.setdefault("rels", {})[other["name"]] = "工作或学习交流中认识的朋友"
            other.setdefault("rels", {}).setdefault(npc["name"], "工作或学习交流中认识的朋友")
            connections = autonomy.setdefault("connections", [])
            if other["name"] not in connections:
                connections.append(other["name"])
            autonomy["connections"] = connections[-8:]
    life["next"] = _plan(npc, due_day, life["cycle"], _precision(state, npc))
    life["world_plan"] = dict(life["next"])
    rel = relationships.ensure_relationship(npc)
    if rel["status"] in ("partner", "distance"):
        player_place = (state.get("player", {}).get("location") or {}).get("place")
        if npc.get("place") != player_place and "外地" in str(plan.get("text", "")):
            rel["status"] = "distance"
    if _known(npc):
        memory.append_fact(state, f"{npc['name']}：{outcome}", int(state.get("turn", 0)),
                           known_by=[npc["name"]], scope="private")
    return f"{npc['name']}：{outcome}。"


def advance_world(state, from_day, to_day):
    """日界线按顺序执行；last_day 防止重复读取/结算制造平行人生。"""
    from_day, to_day = max(1, int(from_day)), max(1, int(to_day))
    if not isinstance(state.get("world_sim"), dict):
        state["world_sim"] = {"last_day": from_day}
    world = ensure_world(state)
    start = max(from_day, int(world.get("last_day", from_day)))
    if to_day < start:
        return []
    cutoff_slot = int((state.get("time") or {}).get("slot", 4))
    notices = []
    # 统一按日期回收，不能先把人物三阶段走完、再让早先的日程覆盖结局。
    while True:
        dues = [max(start, int(n["life"]["next"]["day"])) for n in state.get("npcs", [])
                if isinstance((n.get("life") or {}).get("next"), dict)
                and (int(n["life"]["next"]["day"]) < to_day or
                     int(n["life"]["next"].get("slot", 0)) <= cutoff_slot)]
        dues += [max(start, int(a["due_day"])) for a in state["character_arcs"].values()
                 if not a.get("completed")]
        due_day = min(dues, default=to_day + 1)
        if due_day > to_day:
            break
        for npc in state.get("npcs", []):
            life = ensure_life(npc, due_day)
            plan = life.get("next")
            if not isinstance(plan, dict) or int(plan["day"]) > due_day:
                continue
            if int(plan["day"]) == to_day and int(plan.get("slot", 0)) > cutoff_slot:
                continue
            text = _apply_plan(state, npc, plan, due_day)
            if _known(npc):
                notices.append(text)
            else:
                background = world["background"].setdefault(npc.get("id", npc["name"]), {"cycles": 0, "last_day": start})
                background.update(cycles=background["cycles"] + 1, last_day=due_day)
        notices.extend(character_arcs.advance_arcs(state, start, due_day))
    for npc in state.get("npcs", []):
        life = ensure_life(npc, to_day)
        # 校园篇之后仍有职业去向，已完成的人物成长经历不随年级重置。
        if to_day >= 1461 and npc.get("place") == "京华大学" and "辅导员" not in npc.get("role", ""):
            npc["place"] = "银杏商街" if _seed(npc) % 2 else "龙脊CBD"
            life["status"] = "完成校园阶段，开始自己的城市工作与生活"
    world["last_day"] = to_day
    if to_day > start or notices:
        world["history"] = (world["history"] + [{"from_day": start, "to_day": to_day, "events": len(notices)}])[-12:]
    # 即使跨过几年，也保留后台完整结果；消息只展示最近的变动，避免刷屏。
    if len(notices) > 12:
        return [f"这段时间，熟悉的人共完成{len(notices)}项生活与成长安排。"] + notices[-11:]
    return notices


def people_view(state):
    ensure_world(state)
    result = []
    for npc in state.get("npcs", []):
        if not _known(npc):
            continue
        life = ensure_life(npc)
        result.append({"name": npc["name"], "goal": life["goal"], "status": life["status"],
                       "mood": life["mood"], "place": npc.get("place", ""),
                       "next": life.get("next"), "completed": life.get("completed", [])[-3:],
                       "autonomy": {k: v for k, v in (npc.get("autonomy") or {}).items()
                                    if k in ("work_progress", "education_progress", "achievements", "social_status")},
                       "precision": _precision(state, npc),
                       "relationship": relationships.relationship_view(npc),
                       "importance": min(5, 1 + int(npc.get("encounters", 0)) // 3)})
    return result


def mystery_view(state):
    mystery = ensure_world(state)["mystery"]
    active = mystery["status"] not in ("dormant", "paused", "closed")
    choices = []
    if mystery["status"] == "dormant":
        place = (state.get("player", {}).get("location") or {}).get("place")
        if place == "云顶天文台":
            choices = ["【暗线】观察", "继续自己的生活"]
    elif mystery["status"] == "paused":
        choices = ["【暗线】继续", "继续自己的生活"]
    elif active:
        verbs = {1: "查阅", 2: "接触", 3: "核对", 4: "合作"}
        choices = ["【暗线】" + verbs.get(int(mystery["stage"]), "观察"), "【暗线】搁置"]
        if int(mystery["stage"]) == 4:
            choices.insert(1, "【暗线】旁观")
    return {"status": mystery["status"], "stage": mystery["stage"],
            "clues": list(mystery["clues"]), "choice": mystery["choice"],
            "permissions": list(mystery["permissions"]), "choices": choices}


def world_view(state):
    ensure_world(state)
    return {"people": people_view(state), "arcs": character_arcs.arcs_view(state),
            "mystery": mystery_view(state), "last_day": state["world_sim"]["last_day"]}


def _mystery_turn(state, action):
    verb = action[len("【暗线】"):]
    mystery = ensure_world(state)["mystery"]
    place = (state.get("player", {}).get("location") or {}).get("place")
    day = int((state.get("time") or {}).get("day", 1))
    stage = int(mystery["stage"])
    if verb == "搁置":
        if mystery["status"] in ("dormant", "closed"):
            text = "目前没有正在进行的调查。你可以照常安排自己的生活。"
        else:
            mystery["status"] = "paused"
            text = "你把资料收好，暂时停止调查。没有人因此追着你要求继续；日常、事业与关系照常推进。"
    elif verb == "继续":
        if mystery["status"] != "paused":
            raise ValueError("目前没有搁置中的调查。")
        mystery["status"] = "active"
        text = "你重新翻开自己已经拿到的资料，下一步仍由你选择。"
    elif mystery["status"] in ("paused", "closed"):
        raise ValueError("调查已经暂停或结束，不能越过自己的决定继续领取线索。")
    elif verb == "观察" and stage == 0:
        if place != "云顶天文台":
            raise ValueError("先亲自到云顶天文台，才有条件核实微光传闻。")
        mystery.update(status="active", stage=1)
        clue = "天文台异常记录：微光与设备短波同时出现，值班日志并未记录公开事故"
        mystery["clues"].append(clue)
        text = "你在允许进入的观测区记录了微光，确认它与一次短波同频。第一份证据只能说明异常存在，不能证明任何人的身份。公开年鉴可能留下设备记录。"
    elif verb == "查阅" and stage == 1:
        if place not in ("京华大学", "紫宸美术馆"):
            raise ValueError("去京华大学资料室或紫宸美术馆的城市文献区查阅公开记录。")
        mystery["stage"] = 2
        mystery["clues"].append("公开年鉴：灯塔观测组与天文台共同维护短波设备，白塔互助会资助异常感知者的健康研究")
        text = "你找到同一设备编号的公开采购记录。灯塔观测组负责观测，白塔互助会提供匿名健康支持；这只是有来源的组织线索。若想问清，需在天文台自愿登记接触。"
    elif verb == "接触" and stage == 2:
        if place != "云顶天文台":
            raise ValueError("接触窗口设在云顶天文台，不能隔空取得保密档案。")
        mystery["stage"] = 3
        mystery["clues"].append("经同意获得的脱敏记录：少数人有短暂异常感知，能力受疲劳与距离限制，不能操控思想或制造财富")
        text = "你说明自己的调查意愿后，只拿到参与者同意公开的脱敏记录。确有其他异常感知者，但能力有限，不能支配别人的意志。组织提出先核对三份证据，再决定是否接触更深。"
    elif verb == "核对" and stage == 3:
        mystery["stage"] = 4
        mystery["resolved_clues"] = list(mystery["clues"])
        text = "三份记录的日期与设备编号吻合。微光来自观测设备对短暂异常的响应；灯塔观测组与白塔互助会以自愿、保密和健康支持为边界。这条传闻已经得到回收，你可以有限合作，也可以止步旁观。"
    elif verb in ("合作", "旁观", "退出") and stage == 4:
        mystery.update(status="closed", choice=verb)
        mystery["permissions"] = ["信号观测", "匿名求助"] if verb == "合作" else []
        text = ("你同意参与有限的匿名观测。任何活动仍需逐次同意，组织不干涉你的学业、事业或感情，也不给你支配他人的权限。"
                if verb == "合作" else "你保留已核实的经历，结束更深的接触。组织接受你的决定，普通生活不会因此少一条出路。")
        for clue in mystery["clues"]:
            memory.resolve_fact(state, clue, int(state.get("turn", 0)))
    else:
        raise ValueError("现有证据尚不足以执行这一步，请按已取得的线索调查。")
    mystery["history"].append({"day": day, "action": verb, "stage": mystery["stage"]})
    mystery["history"] = mystery["history"][-20:]
    if verb in ("观察", "查阅", "接触"):
        memory.append_fact(state, mystery["clues"][-1], int(state.get("turn", 0)),
                           kind="伏笔", known_by=[], scope="private")
    choices = mystery_view(state)["choices"] or ["继续自己的生活", "看看朋友们的近况"]
    if len(choices) < 2:
        choices.append("继续自己的生活")
    return {"story_text": text, "narration_world": "urban", "choices": choices[:6],
            "state_updates": {"duration_minutes": 60 if verb in ("观察", "查阅", "接触", "核对") else 15},
            "system_notice": "", "_notices": []}


def before_turn(state, action):
    if action.startswith("【暗线】"):
        return _mystery_turn(state, action)
    for module in (relationships, character_arcs):
        result = module.before_turn(state, action)
        if result is not None:
            result.setdefault("state_updates", {}).setdefault("duration_minutes", 60)
            return result
    return None
