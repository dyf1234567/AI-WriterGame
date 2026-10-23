"""双方同意的长期关系。好感是感受，不是玩家支配 NPC 的权限。"""
from .models import ensure_boundaries, find_npc, is_romanceable
from . import memory

MODES = {"exclusive": "专一", "open": "开放", "poly": "多人"}
MODE_ALIASES = {"专一": "exclusive", "独占": "exclusive", "开放": "open", "多人": "poly"}
STATUS_LABELS = {"friend": "朋友", "flirt": "暧昧", "partner": "恋人",
                 "breakup": "分手", "distance": "异地恋人"}


def _day(state):
    return max(1, int((state.get("time") or {}).get("day", 1)))


def ensure_relationship(npc):
    rel = npc.get("relationship")
    if not isinstance(rel, dict):
        rel = {}
    if rel.get("status") not in STATUS_LABELS:
        rel["status"] = "friend"
    if rel.get("mode") not in MODES:
        rel["mode"] = "exclusive"
    rel.setdefault("history", [])
    rel.setdefault("proposal", None)
    rel.setdefault("since_day", 0)
    rel.setdefault("last_talk_day", 0)
    npc["relationship"] = rel
    return rel


def _record(state, npc, text):
    rel = ensure_relationship(npc)
    rel["history"].append({"day": _day(state), "text": text[:160]})
    rel["history"] = rel["history"][-16:]
    rel["last_talk_day"] = _day(state)
    npc["relationship_status"] = STATUS_LABELS[rel["status"]]
    partners = [n["name"] for n in state.get("npcs", []) if ensure_relationship(n)["status"] in ("partner", "distance")]
    state["partners"] = partners
    if state.get("partner") not in partners:
        state.pop("partner", None)
    if rel["status"] in ("partner", "distance") and rel.get("mode") == "exclusive":
        state["partner"] = npc["name"]
    memory.append_fact(state, f"玩家与{npc['name']}：{text}", int(state.get("turn", 0)),
                       known_by=[npc["name"]], scope="private")


def _mode_consent(npc, mode):
    boundary = ensure_boundaries(npc)
    text = " ".join(str(boundary.get(k, "")) for k in ("principles", "boundary", "romance_style"))
    if mode == "exclusive":
        return True, "愿意认真讨论一对一关系"
    refusals = ("专一", "不接受多人", "不接受开放", "不做备选", "不接受被当成备选", "排他")
    if any(x in text for x in refusals):
        return False, "这与自己的关系原则不符"
    explicit = (("接受开放", "认可开放", "开放关系", "非排他") if mode == "open"
                else ("接受多人", "认可多人", "多人关系", "非排他"))
    if not any(x in text for x in explicit):
        return False, "没有表达过接受非排他关系，需要尊重目前的边界"
    return True, "愿意在知情、可撤回的前提下讨论"


CONFIRM_AFFINITY_GATE = 85   # 确立恋人需达到「心动」
CONFIRM_DATES_GATE = 2       # 且至少两次真实共同经历


def _readiness(state, npc):
    dates = max(int(npc.get("date_count", 0)), sum(1 for d in state.get("dates", []) if d.get("npc") == npc["name"]))
    arc = (state.get("character_arcs") or {}).get(npc["name"], {})
    shared = sum(1 for h in arc.get("history", []) if h.get("choice") in ("合作", "支持", "竞争"))
    if npc.get("project_arc_complete"):
        shared = max(shared, 3)
    if int(npc.get("affinity", 0)) < CONFIRM_AFFINITY_GATE:
        return False, "现在还没有到彼此心动的那一步，先继续好好相处"
    if dates < 2 and shared < 2:
        return False, "还需要至少两次真实的共同经历，好感不能代替了解"
    return True, "愿意认真回应这段感情"


def relationship_action(state, npc_name, action, mode="exclusive"):
    npc = find_npc(state, npc_name)
    if not npc or not npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0):
        return {"ok": False, "msg": "先通过实际相处认识对方。"}
    if not is_romanceable(npc):
        return {"ok": False, "msg": "这段关系不进入恋爱协商。"}
    mode = MODE_ALIASES.get(mode, mode)
    if mode not in MODES:
        return {"ok": False, "msg": "请选择专一、开放或多人，并明确告诉涉及的每个人。"}
    rel = ensure_relationship(npc)
    if action in ("分手", "结束"):
        if rel["status"] not in ("partner", "distance", "flirt"):
            return {"ok": False, "msg": "目前没有需要结束的恋爱关系。"}
        rel.update(status="breakup", proposal=None, since_day=_day(state))
        _record(state, npc, "明确结束恋爱关系，各自保留自己的生活与选择")
        return {"ok": True, "msg": f"你把决定说清楚了。{npc_name}接受关系已经结束，往后的距离由双方重新决定。"}
    if action in ("朋友", "友谊"):
        if rel["status"] in ("partner", "distance"):
            return {"ok": False, "msg": "先认真结束现有恋爱关系，再讨论朋友的距离。"}
        rel.update(status="friend", proposal=None)
        _record(state, npc, "双方将相处定位为朋友")
        return {"ok": True, "msg": f"你与{npc_name}把朋友的边界说清楚，事业合作和日常往来仍可继续。"}
    if action == "异地":
        if rel["status"] != "partner":
            return {"ok": False, "msg": "只有已经确认的恋人才能约定异地相处。"}
        rel["status"] = "distance"
        _record(state, npc, "共同确认异地相处，保留联络与见面的协商空间")
        return {"ok": True, "msg": f"你与{npc_name}明确了异地关系。距离不会自动抹去承诺，也不能代替相处。"}
    if action in ("重逢", "结束异地"):
        if rel["status"] != "distance":
            return {"ok": False, "msg": "目前没有异地关系。"}
        if npc.get("place") != (state.get("player", {}).get("location") or {}).get("place"):
            return {"ok": False, "msg": "先到对方现在的地点见面，再商量结束异地生活。"}
        rel["status"] = "partner"
        _record(state, npc, "见面确认重新在同一处生活，结束异地状态")
        return {"ok": True, "msg": f"见面后，你与{npc_name}重新确认了往后的相处安排。"}
    if action == "复合":
        if rel["status"] != "breakup":
            return {"ok": False, "msg": "目前没有结束过的关系。"}
        ready, reason = _readiness(state, npc)
        if not ready:
            return {"ok": False, "msg": f"{npc_name}认真听完后没有答应：{reason}。"}
        rel.update(status="partner", mode="exclusive", proposal=None, since_day=_day(state))
        _record(state, npc, "分开后重新确认了恋爱关系")
        return {"ok": True, "msg": f"你与{npc_name}重新确定了恋爱关系。这一次的相处，从你们各自的成长开始。"}
    if action == "协商":
        if rel["status"] not in ("partner", "distance"):
            return {"ok": False, "msg": "先确立恋爱关系，再商量相处模式。"}
        partners = [n for n in state.get("npcs", []) if n is not npc and
                    ensure_relationship(n)["status"] in ("partner", "distance")]
        participants = [npc] + partners
        consents = {}
        for person in participants:
            permitted, why = _mode_consent(person, mode)
            consents[person["name"]] = {"accepted": permitted, "reason": why}
        refused = [name for name, answer in consents.items() if not answer["accepted"]]
        if refused:
            rel["proposal"] = None
            return {"ok": False, "msg": "、".join(refused) + "没有同意这项关系约定，各人的现有关系保持原状。", "consents": consents}
        rel["proposal"] = {"mode": mode, "day": _day(state), "consents": consents,
                           "participants": [n["name"] for n in participants]}
        return {"ok": True, "pending": True, "msg": f"涉及的每个人都已听清并愿意接受{MODES[mode]}关系；仍需你明确确认，尚未改变现有关系。", "consents": consents}
    if action in ("确认", "接受", "确立", "确立恋爱"):
        proposal = rel.get("proposal")
        if isinstance(proposal, dict):
            # 协商产生的相处模式提议：确认前重检时限、原则与在场成员
            mode = proposal.get("mode", "exclusive")
            if _day(state) - int(proposal.get("day", 0)) > 7:
                rel["proposal"] = None
                return {"ok": False, "msg": "时间已经变化，请重新确认彼此现在的意愿。"}
            active_names = {n["name"] for n in state.get("npcs", []) if n is not npc and
                            ensure_relationship(n)["status"] in ("partner", "distance")}
            if not active_names.issubset(set(proposal.get("participants", []))):
                rel["proposal"] = None
                return {"ok": False, "msg": "关系情况已经变化，请让所有涉及的人重新知情协商。"}
            for name in proposal.get("participants", []):
                person = find_npc(state, name)
                if not person or not _mode_consent(person, mode)[0]:
                    rel["proposal"] = None
                    return {"ok": False, "msg": "有人改变了意愿，不能继续使用旧的同意。"}
            for name in proposal["participants"]:
                person = find_npc(state, name)
                current = ensure_relationship(person)
                current.update(status="partner" if name == npc_name else current["status"],
                               mode=mode, proposal=None, since_day=current.get("since_day") or _day(state))
                _record(state, person, f"知情并明确确认{MODES[mode]}关系；各方可以撤回同意")
            return {"ok": True, "msg": f"你与{npc_name}明确确认了{MODES[mode]}关系。承诺现在有了具体边界，任何改变都要再次商量。"}
        # 直接确立恋爱：彼此心动＋共同经历，不需要先经过表白流程
        if rel["status"] in ("partner", "distance"):
            return {"ok": False, "msg": "你们已经是彼此确认的恋人。"}
        ready, reason = _readiness(state, npc)
        if not ready:
            return {"ok": False, "msg": f"{npc_name}认真听完后没有答应：{reason}。"}
        partners = [n for n in state.get("npcs", []) if n is not npc and
                    ensure_relationship(n)["status"] in ("partner", "distance")]
        if mode == "exclusive" and partners:
            return {"ok": False, "msg": "仍有其他恋爱承诺，不能在隐瞒或未结束关系的情况下确立专一关系。"}
        for person in [npc] + partners:
            permitted, why = _mode_consent(person, mode)
            if not permitted:
                return {"ok": False, "msg": f"{person['name']}没有同意这项关系约定：{why}。"}
        rel.update(status="partner", mode=mode, proposal=None, since_day=_day(state))
        for person in partners:
            ensure_relationship(person).update(mode=mode)
            _record(state, person, f"知情并明确确认{MODES[mode]}关系；各方可以撤回同意")
        _record(state, npc, f"知情并明确确认{MODES[mode]}关系；双方可以再协商改变")
        return {"ok": True, "msg": f"你与{npc_name}明确确认了{MODES[mode]}关系。承诺现在有了具体边界，任何改变都要再次商量。"}
    return {"ok": False, "msg": "请选择朋友、确认、协商、分手、复合、异地或重逢。"}


def relationship_view(npc):
    rel = ensure_relationship(npc)
    return {"status": rel["status"], "label": STATUS_LABELS[rel["status"]],
            "mode": rel["mode"], "mode_label": MODES[rel["mode"]],
            "since_day": rel["since_day"], "proposal": rel.get("proposal"),
            "history": rel["history"][-4:]}


def before_turn(state, action):
    if not action.startswith("【关系】"):
        return None
    bits = action[len("【关系】"):].split(":")
    name, verb = (bits + [""])[:2]
    mode = bits[2] if len(bits) > 2 else "exclusive"
    result = relationship_action(state, name, verb, mode)
    choices = ([f"【关系】{name}:确认", f"【关系】{name}:朋友"] if result.get("pending") else
               [f"【关系】{name}:协商:exclusive", "继续自己的生活"])
    return {"story_text": result["msg"], "narration_world": "urban", "choices": choices,
            "state_updates": {}, "system_notice": "", "_notices": []}
