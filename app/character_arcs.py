"""八位核心人物的独立成长经历；支持、竞争或不参与都能继续。"""
from .models import ensure_life, find_npc
from . import memory, skills

# 每一步都有自己的工作、困难和去处，恋爱与这些人生结果相互独立。
ARCS = {
    "梁雅婷": {"skill": "speech", "channels": ("校园", "志愿活动", "朋友介绍"), "place": "京华大学", "goal": "做出署名属于自己的城市人物作品", "steps": [
        ("第一次署名", "梁雅婷想把校园采访交到校刊，编辑要求重写。", "她完成采访并获得独立署名", "她请编辑逐段修改，独自完成了初稿"),
        ("谁的故事", "实习编辑希望删掉受访者不够漂亮的经历，她要守住事实。", "她保留关键事实，赢得受访者的信任", "她选择小型独立刊物，保住了报道原貌"),
        ("自己的栏目", "城市编辑部给出长期邀请，但意味着离开熟悉的校园。", "她在京都建立城市人物栏目，开始独立采编", "她前往魔都做记者，以另一种方式走进城市")], "end_place": "龙脊CBD"},
    "郭瑞莹": {"skill": "instrument", "channels": ("旧友联络", "音乐现场", "朋友介绍"), "place": "外滩滨江", "goal": "用自己的解释完成一次室内乐巡演", "steps": [
        ("不够完美的合奏", "郭瑞莹的合奏伙伴临时缺席，她第一次考虑不靠独奏撑完整场。", "她完成一场有呼吸和失误的合奏", "她找来新的学院伙伴，重新安排合奏"),
        ("自己的诠释", "老师建议沿用稳妥版本，郭瑞莹却想加入自己的处理。", "她在公开课坚持自己的诠释并接受专业批评", "她把作品投给独立音乐节，得到首次回应"),
        ("远方的舞台", "室内乐团邀请她参加异地巡演，生活与舞台都要重新安排。", "她带着自己的版本开始巡演", "她加入外地室内乐团，独立完成巡演")], "end_place": "回声Livehouse"},
    "邓碧瑶": {"skill": "sense", "channels": ("旧友联络", "电竞活动", "朋友介绍"), "place": "魔都南站", "goal": "把深夜队伍变成能独立参赛的团队", "steps": [
        ("走出语音", "邓碧瑶要为固定队报名线下赛，队友却只想继续随便玩。", "她组织队友完成第一场线下赛", "她自己去现场，认识了愿意认真参赛的新队友"),
        ("队伍的边界", "有人提出让她兼任陪玩与领队，她需要区分工作和朋友。", "她明确队伍分工与付费边界", "她拒绝含糊合作，加入有明确规则的新队伍"),
        ("成为伙伴", "城市俱乐部邀请她做战术分析，她要决定是否离开原来的圈子。", "她成为俱乐部战术分析，仍为朋友保留日常队", "她前往京都战队开始新的分析工作")], "end_place": "京华大学"},
    "雅倩": {"skill": "coding", "channels": ("校园", "学术活动", "朋友介绍"), "place": "京华大学", "goal": "证明自己能承担研究中的不确定", "steps": [
        ("不漂亮的数据", "雅倩的课题结果并不显著，竞赛答辩临近。", "她保留负结果并完成诚实的答辩", "她向导师申请补充实验，独自重做分析"),
        ("比较之外", "研究组只剩一个展示名额，她与花碎花的旧比较又被提起。", "她明确分工与署名，停止用朋友的成败衡量自己", "她退出无谓比较，把成果改投开放工作坊"),
        ("研究者的选择", "跨城研究团队发来邀请，名气与研究自由难以两全。", "她选择有研究自主权的团队继续深造", "她前往魔都研究所，从新的课题开始")], "end_place": "魔都大学"},
    "王德芙": {"skill": "stage", "channels": ("校园", "运动活动", "朋友介绍"), "place": "京华大学", "goal": "跑出能长久坚持的运动生涯", "steps": [
        ("停下的勇气", "王德芙的旧伤在选拔前复发，她不想轻易退出。", "她遵守康复计划，保住了下一季的参赛资格", "她向队医求助，暂时退出本次选拔"),
        ("另一个位置", "康复期间，队里邀请她带新生热身，她不确定这是否算退步。", "她在带队与恢复训练之间找到节奏", "她开始学习运动康复，重新理解训练"),
        ("自己的赛道", "城市田径队和校园教练助理都向她发来邀请。", "她回归比赛，同时参与公益训练营", "她加入城市运动康复团队，继续参加公开赛")], "end_place": "燕山枫林"},
    "韩冰": {"skill": "manage", "channels": ("校园", "电竞活动", "朋友介绍"), "place": "京华大学", "goal": "成为不靠关系也能带好队伍的经理", "steps": [
        ("混乱的赛表", "韩冰发现两场比赛撞期，队员训练安排也已冲突。", "她重排赛表并与所有队员确认", "她向赛事方争取改期，独自处理了冲突"),
        ("姐姐之外", "赞助商更想借姐姐的人气宣传，她想让队员的成绩被看见。", "她谈下以队伍成绩为主的赞助条件", "她拒绝捆绑宣传，寻找规模更小的赞助"),
        ("职业经理", "魔都俱乐部邀请她管理青训，她必须把校园队交给接班人。", "她完成交接，开始职业青训管理", "她自己培养接班人，随后赴魔都任职")], "end_place": "龙脊CBD"},
    "傲寒": {"skill": "vocal", "channels": ("音乐现场", "网络创作", "朋友介绍"), "place": "回声Livehouse", "goal": "让自己的原创歌离开直播间", "steps": [
        ("第一首原创", "傲寒攒了很久的原创终于成形，直播平台却只想听熟悉的翻唱。", "她在小现场唱完自己的原创", "她上传独立录音，接受第一批陌生听众的评价"),
        ("唱给谁听", "发行方希望她改成更容易传播的版本，她不想抹掉原来的故事。", "她保留核心歌词，协商出两版编曲", "她选择独立发行，承担宣传和制作的压力"),
        ("自己的现场", "巡演邀约与固定直播时段冲突，她需要重建收入与生活节奏。", "她完成小型巡演，建立自己的听众群", "她与独立音乐人合作，带着原创走向外地")], "end_place": "外滩滨江"},
    "炭炭": {"skill": "manage", "channels": ("商业活动", "音乐现场", "朋友介绍"), "place": "龙脊CBD", "goal": "建立能保护新人创作者的工作室", "steps": [
        ("退团之后", "炭炭的工作室收到第一份新人合约，对方要求高额违约条款。", "她删去不对等条款，与新人重新签约", "她放弃这笔资金，先以小规模团队开工"),
        ("团队的代价", "第一场演出预算超支，团队开始质疑她的理想。", "她公开预算并重订分工，团队决定继续", "她缩小演出规模，保住了员工报酬"),
        ("独立的名字", "集团提出收购，她要在扩张与独立之间作出取舍。", "她保留经营决定权，工作室完成首年运营", "她拒绝收购，和团队共同运营独立厂牌")], "end_place": "龙脊CBD"},
}


def _known(npc):
    return bool(npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0))


def ensure_arcs(state, day=None):
    day = max(1, int(day or (state.get("time") or {}).get("day", 1)))
    arcs = state.setdefault("character_arcs", {})
    for name, config in ARCS.items():
        arc = arcs.setdefault(name, {"stage": 0, "history": [], "pending": None,
                                     "available_day": day, "due_day": day + 14, "completed": False})
        arc.setdefault("history", [])
        arc.setdefault("pending", None)
        npc = find_npc(state, name)
        if npc and not ensure_life(npc, day).get("goal"):
            npc["life"]["goal"] = config["goal"]
    return arcs


def _finish(state, name, arc, choice, day):
    config = ARCS[name]
    npc = find_npc(state, name)
    stage = int(arc["stage"])
    if not npc or stage >= len(config["steps"]):
        return ""
    title, _, shared, independent = config["steps"][stage]
    outcome = shared if choice in ("合作", "支持") else independent
    if choice == "竞争":
        outcome += "；你们各自提交作品或方案，彼此尊重评审结果"
    elif choice == "放手":
        outcome += "；你尊重了她自己决定的去向"
    arc["history"].append({"stage": stage + 1, "title": title, "choice": choice,
                           "day": day, "outcome": outcome})
    arc.update(stage=stage + 1, pending=None, available_day=day + 7, due_day=day + 28,
               completed=stage + 1 >= len(config["steps"]))
    life = ensure_life(npc, day)
    life.update(status=outcome[:80], mood="踏实" if choice != "竞争" else "认真", updated_day=day)
    if arc["completed"]:
        life["goal"] = "在新的生活中延续自己的工作和关系"
        npc["place"] = config["end_place"]
    if _known(npc):
        memory.append_fact(state, f"{name}完成「{title}」：{outcome}", int(state.get("turn", 0)),
                           known_by=[name], scope="private")
    return f"{name}：{outcome}。"


def advance_arcs(state, from_day, to_day):
    arcs = ensure_arcs(state, max(1, int(from_day)))
    notices = []
    # 到期事件逐个回收，快进仍会经过三个不同阶段，不会抹掉中间经历。
    for name, arc in arcs.items():
        while not arc.get("completed") and int(arc["due_day"]) <= to_day:
            choice = (arc.get("pending") or {}).get("choice", "忽略")
            text = _finish(state, name, arc, choice, int(arc["due_day"]))
            npc = find_npc(state, name)
            if text and npc and _known(npc):
                notices.append(text)
    return notices


def arcs_view(state):
    arcs = ensure_arcs(state)
    day = int((state.get("time") or {}).get("day", 1))
    result = []
    for name, config in ARCS.items():
        npc = find_npc(state, name)
        if not npc or not _known(npc):
            continue
        arc = arcs[name]
        stage = min(2, int(arc["stage"]))
        step = config["steps"][stage]
        available = not arc["completed"] and day >= int(arc["available_day"]) and not arc.get("pending")
        result.append({"name": name, "goal": config["goal"], "stage": arc["stage"], "total": 3,
                       "completed": arc["completed"], "title": step[0] if not arc["completed"] else "新生活",
                       "desc": step[1] if available else "她正在安排自己的下一步。",
                       "due_day": arc["due_day"], "history": arc["history"][-3:],
                       "choices": [f"【人物】{name}:{c}" for c in ("合作", "支持", "竞争", "放手")] if available else []})
    return result


def before_turn(state, action):
    if not action.startswith("【人物】"):
        return None
    bits = action[len("【人物】"):].split(":")
    name, verb = (bits + [""])[:2]
    config, npc = ARCS.get(name), find_npc(state, name)
    if not config or not npc:
        raise ValueError("这位人物还没有可参与的成长事件。")
    day = int((state.get("time") or {}).get("day", 1))
    arcs = ensure_arcs(state)
    arc = arcs[name]
    notices = []
    if verb == "相识":
        channel = bits[2] if len(bits) > 2 else ""
        if channel not in config["channels"]:
            raise ValueError("请选择这位人物实际参与的相识渠道。")
        if _known(npc):
            text = f"你已经认识{name}，不需要重新制造一次初遇。"
        else:
            location = (state.get("player", {}).get("location") or {}).get("place", "")
            introduced = any(_known(n) and (name in (n.get("rels") or {})) for n in state.get("npcs", []))
            remote = channel in ("旧友联络", "网络创作")
            if not remote and location != npc.get("place") and not (channel == "朋友介绍" and introduced):
                raise ValueError("先去对方所在的地点，或通过真正认识的共同朋友介绍。")
            if channel == "朋友介绍" and not introduced:
                raise ValueError("目前没有认识双方的共同朋友。")
            npc["known_to_player"] = True
            npc["last_seen_turn"] = int(state.get("turn", 0))
            npc["encounters"] = int(npc.get("encounters", 0)) + 1
            text = f"通过{channel}，你与{name}有了真实联系。她正想{config['goal']}；之后是否同行，由你们各自选择。"
    else:
        if not _known(npc):
            raise ValueError("先通过实际相处认识对方，再参与她的计划。")
        if verb not in ("合作", "支持", "竞争", "放手"):
            raise ValueError("请选择合作、支持、竞争或放手。")
        if arc["completed"]:
            raise ValueError("这段成长经历已经完成，她的日常和职业生活仍会继续。")
        if day < int(arc["available_day"]):
            raise ValueError("她还在准备下一步，给彼此一些安排生活的时间。")
        if arc.get("pending"):
            raise ValueError("已经表达过参与方式，等待这次计划实际完成。")
        title, desc, _, _ = config["steps"][int(arc["stage"])]
        arc["pending"] = {"choice": verb, "day": day}
        npc["encounters"] = int(npc.get("encounters", 0)) + 1
        if verb in ("合作", "支持", "竞争"):
            notices.extend(skills.add_xp(state, config["skill"], 10))
        text = f"{desc}\n\n你选择了{verb}。{name}听清你的想法后，仍按自己的目标安排具体工作。计划在第{arc['due_day']}天回收，选择不会立刻变成已完成的成果。"
    choices = ["继续自己的生活", f"【关系】{name}:朋友"]
    return {"story_text": text, "narration_world": "urban", "choices": choices,
            "state_updates": {}, "system_notice": "", "_notices": notices}
