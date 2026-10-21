"""世界事件：日历驱动的周期活动＋导演层偶遇注入。

事件的参与选项带技能/属性门槛（skills.skill_check 门控），
结果由引擎结算——技能经验、金币（内部通道）、名望、机遇标记
（写入 career.opportunities，事业入门的钥匙）、在场 NPC 好感。
行动前缀【活动】由 before_turn 拦截，模板叙事不经过模型。
"""
from datetime import date

from . import skills as sk
from .models import WORLD_URBAN, find_npc, game_today, now_iso

PREFIX = "【活动】"
DROUGHT_TURNS = 10  # 连续未参加活动的回合数阈值（导演层注入用）
DIRECTOR_COOLDOWN = 6  # 两次导演事件之间至少隔多少回合
DIRECTOR_HISTORY_KEPT = 6

# 事件定义：id → {name, cat, desc, options:[{id,label,req:{skill,diff}|None,
#   win:{text,xp,gold,fame,opp,npcs}, half:..., lose:...}]}
_EVENTS = {
    "gala": {
        "name": "校园晚会", "cat": "娱乐", "npcs": ["梁雅婷", "傲寒", "乐乐"],
        "desc": "周五晚的大礼堂灯火通明，节目单还缺一个压轴。",
        "options": [
            {"id": "sing", "label": "登台唱一首", "req": ("vocal", 2),
             "win": {"text": "你的嗓音镇住了全场，谢幕时礼堂的掌声久久不停——后台角落里，一位戴着工牌的经纪公司星探朝你递来了名片。",
                     "xp": ("vocal", 40), "gold": 0, "fame": ("娱乐", 8),
                     "opp": "经纪公司试镜邀请"},
             "half": {"text": "副歌唱到一半破了音，好在台下掌声还算善意——同班的梁雅婷在侧幕冲你比了个加油的手势。",
                      "xp": ("vocal", 20), "gold": 0, "fame": ("娱乐", 3), "opp": None},
             "lose": {"text": "你在台上脑子一片空白，草草唱完逃下台——有些事，果然要练过再上。",
                      "xp": ("vocal", 10), "gold": 0, "fame": None, "opp": None}},
            {"id": "host", "label": "毛遂自荐当主持", "req": ("speech", 2),
             "win": {"text": "你串场救了两次冷场，晚会导演散场后拍着你的肩说下次校庆还找你。",
                     "xp": ("speech", 40), "gold": 30, "fame": ("娱乐", 5), "opp": None},
             "half": {"text": "念错了一个赞助商的名字，全场笑成一片——也算留下了印象。",
                      "xp": ("speech", 20), "gold": 15, "fame": None, "opp": None},
             "lose": {"text": "你在台上腿肚子转筋，把话筒递给了救场的学长。",
                      "xp": ("speech", 10), "gold": 0, "fame": None, "opp": None}},
            {"id": "watch", "label": "坐在台下看热闹", "req": None,
             "win": {"text": "你在台下嗑着瓜子看完了整场，跟旁边音乐系的女生聊得很开心。",
                     "xp": None, "gold": 0, "fame": None, "opp": None},
             "half": None, "lose": None},
        ],
    },
    "arena": {
        "name": "电竞擂台赛", "cat": "电竞", "npcs": ["小杨", "韩冰", "歪歪"],
        "desc": "周六的电竞馆人声鼎沸，擂台赛的报名处排着长队，冠军奖金五百。",
        "options": [
            {"id": "solo", "label": "报名单人赛", "req": ("mech", 2),
             "win": {"text": "决胜局一波三杀收割比赛，全场喊你 ID 的声音盖过解说——青训营的教练在场边记下了你的名字。",
                     "xp": ("mech", 40), "gold": 80, "fame": ("电竞", 8),
                     "opp": "青训营测试资格"},
             "half": {"text": "你打进了四强，倒在了一个套路极其脏的老哥手里——电竞社的小杨场外直呼可惜。",
                      "xp": ("mech", 20), "gold": 30, "fame": ("电竞", 3), "opp": None},
             "lose": {"text": "小组赛两连败出局——手速这东西，骗不了人。",
                      "xp": ("mech", 10), "gold": 0, "fame": None, "opp": None}},
            {"id": "cast", "label": "蹭解说席分析战术", "req": ("sense", 2),
             "win": {"text": "你的局势预判连解说都跟着点头，直播间弹幕刷起了\"这兄弟懂游戏\"。",
                     "xp": ("sense", 40), "gold": 20, "fame": ("电竞", 4), "opp": None},
             "half": {"text": "你预言的翻盘没来，弹幕笑称你是\"毒奶\"——车车转发了你的片段。",
                      "xp": ("sense", 20), "gold": 10, "fame": None, "opp": None},
             "lose": None},
        ],
    },
    "market": {
        "name": "创意集市", "cat": "商业", "npcs": ["花碎花", "吃不饱", "小新"],
        "desc": "周日的步行街支起了集市摊位，人流量正旺，摊位费五十。",
        "options": [
            {"id": "stall", "label": "支个小摊试水", "req": ("manage", 1),
             "win": {"text": "你挑的货和喊的价都对了路，收摊时数钱数到手软——花碎花隔壁摊的奶茶都跟着多卖了几杯。",
                     "xp": ("manage", 40), "gold": 120, "fame": ("商业", 5), "opp": None},
             "half": {"text": "不算亏，但也只赚回了摊位费——隔壁吃不饱的摊位排着队，你默默记下了她的选品。",
                      "xp": ("manage", 20), "gold": 50, "fame": None, "opp": None},
             "lose": {"text": "进货砸在手里了，收摊时你把剩下的货半卖半送。",
                      "xp": ("manage", 10), "gold": 20, "fame": None, "opp": None}},
            {"id": "busk", "label": "街头卖艺", "req": ("vocal", 1),
             "win": {"text": "你的吉他弹唱围起了里三层外三层，琴盒里的零钱铺满了底。",
                     "xp": ("vocal", 30), "gold": 60, "fame": None, "opp": None},
             "half": {"text": "唱了三首，赚了份奶茶钱——路过的小新给你直播刷了个火箭。",
                      "xp": ("vocal", 15), "gold": 25, "fame": None, "opp": None},
             "lose": None},
        ],
    },
    "roadshow": {
        "name": "商业路演日", "cat": "商业", "npcs": ["炭炭", "杨幂", "邓碧瑶"],
        "desc": "月末的路演厅里挤满了投资人和创业者，五分钟一个项目。",
        "options": [
            {"id": "pitch", "label": "上台讲一个点子", "req": ("speech", 3),
             "win": {"text": "你的五分钟讲得全场安静，散场后两位投资人主动交换了联系方式——炭炭在台下朝你举了举咖啡。",
                     "xp": ("speech", 50), "gold": 0, "fame": ("商业", 10), "opp": "天使投资人名片"},
             "half": {"text": "点子被夸了，但商业模式被问得体无完肤——评委建议你先从练摊开始。",
                      "xp": ("speech", 25), "gold": 0, "fame": ("商业", 3), "opp": None},
             "lose": {"text": "PPT 翻到第三页你就忘了词，全场礼貌的掌声像在送葬。",
                      "xp": ("speech", 10), "gold": 0, "fame": None, "opp": None}},
            {"id": "network", "label": "混进茶歇社交", "req": None,
             "win": {"text": "你端着咖啡蹭了三轮谈资，加到了五个微信——其中一个备注写着\"投资人\"。",
                     "xp": None, "gold": 0, "fame": ("商业", 3), "opp": None},
             "half": None, "lose": None},
        ],
    },
    # 偶遇型（导演层注入）
    "street": {
        "name": "街头演出", "cat": "偶遇", "npcs": ["乐乐"],
        "desc": "路过商街时，一台突然罢工的音响前站着不知所措的街头歌手。",
        "options": [
            {"id": "help", "label": "上去救场唱两首", "req": ("vocal", 1),
             "win": {"text": "你接过失灵的话筒救了场，围观人群里的欢呼声比原主唱还响。",
                     "xp": ("vocal", 25), "gold": 20, "fame": ("娱乐", 3), "opp": None},
             "half": {"text": "你唱得磕磕绊绊，但好歹把场子救回来了。",
                      "xp": ("vocal", 12), "gold": 10, "fame": None, "opp": None},
             "lose": None},
        ],
    },
    # ---- 导演层事件：没有固定活动的日子，按世界状态择机出现 ----
    "relation_window": {
        "name": "关系契机", "cat": "关系", "npcs": [], "dynamic_npc": True,
        "desc": "夜色正好，{npc}发来一条消息：想和你单独走走。",
        "options": [
            {"id": "walk", "label": "赴约，认真听她说话", "req": None,
             "win": {"text": "你和{npc}沿着江边走了很久。她说起最近一直没对别人说过的事，也问起你的打算。你们没有急着给关系下定义，但回去时都走得比来时慢。",
                     "affinity": 2, "bond": {"familiarity": 3, "trust": 2, "attraction": 2},
                     "fact": "{npc}在夜里向主角说起一件没对别人说过的事"},
             "half": {"text": "你们走了一段路，话题几次停住。{npc}没有勉强自己，你也没有追问。",
                      "affinity": 1, "bond": {"familiarity": 1, "trust": 1}},
             "lose": None},
            {"id": "decline", "label": "今晚先不去了", "req": None,
             "win": {"text": "你回消息说今晚想一个人待着。{npc}只回了一个“好”，没有追问。你看着屏幕，隐约觉得错过了一点什么。",
                     "affinity": -1, "bond": {"trust": -1}}},
        ],
    },
    "industry_offer": {
        "name": "行业机会", "cat": "事业", "npcs": ["炭炭", "杨幂", "车车"],
        "desc": "一场圈内小聚上，一位前辈叫住了你：手头有个位置，想先听听你的想法。",
        "options": [
            {"id": "talk", "label": "坐下来认真聊", "req": ("speech", 2),
             "win": {"text": "你把眼下在做的事讲得很清楚，也坦白了自己还缺什么。前辈没有当场许诺，但把联系方式留给了你，说下次有合适的位置会再找你。",
                     "xp": ("speech", 30), "gold": 30, "fame_any": 5},
             "half": {"text": "你聊得有些急，前辈听完只点了点头。临走时他说：先把手上那件事做完，再谈下一步。",
                      "xp": ("speech", 15), "gold": 15, "fame_any": 2},
             "lose": {"text": "你准备得不够，话到一半就被带了过去。前辈客气地结束了话题，你在门口站了一会儿。",
                      "xp": ("speech", 8)}},
            {"id": "observe", "label": "先听听别人怎么说", "req": None,
             "win": {"text": "你没有急着递话，而是听完了整场。散场时你记下了三条有用的判断，也认清了谁在说真话。",
                     "xp": ("speech", 15), "fame_any": 1}},
        ],
    },
    "competition": {
        "name": "同行竞争", "cat": "事业", "npcs": ["车车", "小杨", "炭炭"],
        "desc": "你的名字开始被人拿来比较。对手放出话，要在下一场活动上压你一头。",
        "options": [
            {"id": "fight", "label": "正面接招", "req": ("speech", 2),
             "win": {"text": "你没有回避，把该拿出的东西都拿了出来。结果不算碾压，但对手收回了那句大话，圈里也记住了你的名字。",
                     "xp": ("speech", 25), "gold": 20, "fame_any": 4},
             "half": {"text": "你接住了场面，却没有赢下所有回合。对手在散场时和你握了手，说下次再来。",
                      "xp": ("speech", 12), "fame_any": 1},
             "lose": {"text": "你被对方的节奏带着走，结束时才想起自己原本想说什么。回去的路上，你把复盘记在了手机里。",
                      "xp": ("speech", 8)}},
            {"id": "study", "label": "先研究对手", "req": ("sense", 2),
             "win": {"text": "你没有急着应战，而是把对手最近的动作拆开来看。第二天你带着一套更有针对性的方案出现，风向开始变了。",
                     "xp": ("sense", 25), "fame_any": 2},
             "half": {"text": "你看出了对手的一个习惯，但还没想好怎么用。至少这一次，你没有盲目跟着跑。",
                      "xp": ("sense", 12)}},
        ],
    },
    "hidden_clue": {
        "name": "深夜微光", "cat": "探索", "npcs": [],
        "desc": "云顶天文台的方向又亮起微光。你翻出手机里那张旧照片，轮廓和记忆里的某一晚对上了。",
        "options": [
            {"id": "go", "label": "今晚去看看", "req": None,
             "win": {"text": "你独自上了山。天文台的铁门没有锁，里面却干净得不像废弃多年。你在一台旧仪器的底座上看见一串刻痕，和系统偶尔闪过的字符很像。",
                     "fact": "云顶天文台的旧仪器刻痕与主角的系统字符相似（未解线索）"},
             "half": {"text": "你走到半山腰就起了雾，只能远远看见那点微光。下山时它已经灭了，但你知道自己还会再来。"}},
            {"id": "ignore", "label": "当作没看见", "req": None,
             "win": {"text": "你把照片翻了过去，继续做眼前的事。那点微光在窗外亮了一夜，第二天早上又恢复成一段普通的传闻。"}},
        ],
    },
    "craft_showcase": {
        "name": "作品被看见", "cat": "成长", "npcs": ["乐乐", "小杨", "炭炭"],
        "desc": "你长期投入的东西终于有了一个能被看见的窗口：有人愿意给你十分钟。",
        "options": [
            {"id": "show", "label": "把作品拿出来", "req": None,
             "win": {"text": "你没有再等一个更完美的版本。十分钟里，你把最想让人看见的部分完整地展示了出来；有人认真问了细节，这比客套的夸奖更让你踏实。",
                     "xp_any": 20, "gold": 10, "fame_any": 2},
             "half": {"text": "展示到一半你发现了明显的瑕疵。你还是把它讲完了，也在反馈里记下了下一次要改的地方。",
                      "xp_any": 10}},
            {"id": "polish", "label": "再打磨一轮", "req": None,
             "win": {"text": "你婉拒了这次窗口，把时间留给手上的作品。没有人看见，但你自己知道它比昨天更完整了一点。",
                     "xp_any": 25}},
        ],
    },
}

OPTION_NPCS_AFFINITY = 2  # 在场 NPC 好感（命中 win/half 时 +2）


def _iso(state: dict) -> tuple:
    d = date.fromisoformat(game_today(state))
    iso = d.isocalendar()
    return iso  # (year, week, weekday 1=一 … 7=日)


def scheduled_for(state: dict) -> list[str]:
    """当日排期：周五晚=晚会/联谊（按周奇偶）、周六=擂台（非月末）/路演（月末）、
    周日=集市（每月第一个周日）。同日确定、跨日轮换。"""
    year, week, wd = _iso(state)
    day = date.fromisoformat(game_today(state))
    out = []
    if wd == 5:  # 周五
        out.append("gala" if week % 2 == 0 else None or _alt_gala(week))
    if wd == 6:  # 周六：月末最后一个周六走路演，其余擂台
        nxt = date.fromordinal(day.toordinal() + 7)
        out.append("roadshow" if nxt.month != day.month else "arena")
    if wd == 7 and day.day <= 7:  # 每月第一个周日
        out.append("market")
    return [e for e in out if e]


def _alt_gala(week: int) -> str:
    return "gala"  # 奇数周暂共用晚会模板（社团联谊后续可独立）；保持返回值稳定


def _director_state(state: dict) -> dict:
    director = state.setdefault("director", {})
    if not isinstance(director, dict):
        director = {}
        state["director"] = director
    director.setdefault("active", None)
    director.setdefault("history", [])
    director.setdefault("last_event_turn", -999)
    director.setdefault("last_npc", "")
    director.setdefault("last_place_count", 0)
    return director


def _director_context(state: dict, ev_id: str | None = None) -> dict | None:
    director = _director_state(state)
    active = director.get("active")
    if not isinstance(active, dict) or not active.get("id"):
        return None
    if active.get("day") != game_today(state):
        director["active"] = None
        return None
    if ev_id and active.get("id") != ev_id:
        return None
    return active


def _format_event(text, ctx: dict | None) -> str:
    return str(text or "").replace("{npc}", str((ctx or {}).get("npc") or ""))


def _top_relationship_npc(state: dict) -> dict | None:
    known = [n for n in state.get("npcs", [])
             if n.get("known_to_player") and int(n.get("affinity", 0)) >= 65]
    if not known:
        return None
    known.sort(key=lambda n: (int(n.get("affinity", 0)),
                              int((n.get("bond") or {}).get("trust", 0))), reverse=True)
    last = _director_state(state).get("last_npc", "")
    return next((n for n in known if n["name"] != last), known[0])


def _top_skill(state: dict) -> tuple[str, int]:
    best = ("vocal", 0)
    for skill_id in sk.SKILLS:
        level = sk.level(state, skill_id)
        if level > best[1]:
            best = (skill_id, level)
    return best


def _discovered_count(state: dict) -> int:
    return sum(1 for place in (state.get("map", {}).get(WORLD_URBAN) or [])
               if place.get("discovered"))


def _director_pick(state: dict) -> dict | None:
    """按关系/事业/探索/专注/干旱五类信号择机给一次可选事件。

    只写入 director.active，不直接改玩家状态；玩家可以选择不参加。
    固定日历活动优先，导演层只在没有排期的日子出现。
    """
    director = _director_state(state)
    active = _director_context(state)
    if active and active.get("id"):
        return active
    turn = int(state.get("turn", 0))
    if turn - int(director.get("last_event_turn", -999)) < DIRECTOR_COOLDOWN:
        return None

    candidates: list[tuple[int, str, str, str]] = []
    npc = _top_relationship_npc(state)
    if npc:
        score = 4
        if any(h.get("npc") == npc["name"] for h in state.get("hooks", [])):
            score += 2
        candidates.append((score, "relation_window", npc["name"], "关系"))

    from . import career as career_mod
    career = career_mod.ensure_career(state)
    fame = max((career.get("fame") or {}).values() or [0])
    if career.get("domain") and (int(career.get("stage", 0)) >= 2 or fame >= 25):
        prior = [h for h in director.get("history", []) if h.get("category") == "事业"]
        event_id = ("competition" if prior and prior[-1].get("id") == "industry_offer"
                    else "industry_offer")
        candidates.append((3, event_id, "", "事业"))

    discovered = _discovered_count(state)
    if discovered >= 6 and director.get("last_place_count") != discovered:
        candidates.append((3, "hidden_clue", "", "探索"))

    if _top_skill(state)[1] >= 4:
        candidates.append((2, "craft_showcase", "", "成长"))

    last_join = int((state.get("events") or {}).get("last_join_turn", -999))
    if turn >= DROUGHT_TURNS and turn - last_join >= DROUGHT_TURNS:
        candidates.append((2, "street", "", "偶遇"))
    if not candidates:
        return None

    history = director.get("history") or []
    last_category = history[-1].get("category") if history else ""
    recent_high = (len(history) >= 2
                   and all(h.get("category") in ("关系", "事业", "成长") for h in history[-2:]))
    scored = []
    for score, event_id, npc_name, category in candidates:
        if category == last_category:
            score -= 2
        if recent_high and category in ("关系", "事业", "成长"):
            score -= 1
        scored.append((score, event_id, npc_name, category))
    scored.sort(key=lambda item: (-item[0], item[1]))
    score, event_id, npc_name, category = scored[0]
    if score <= 0:
        return None

    picked = {"id": event_id, "npc": npc_name, "category": category,
              "day": game_today(state), "turn": turn}
    director["active"] = picked
    director["last_event_turn"] = turn
    if npc_name:
        director["last_npc"] = npc_name
    if event_id == "hidden_clue":
        director["last_place_count"] = discovered
    director["history"] = (history + [{
        "id": event_id, "category": category, "day": picked["day"], "turn": turn}])[-DIRECTOR_HISTORY_KEPT:]
    return picked


def active_events(state: dict) -> list[str]:
    """当日可用事件 = 日历排期优先；没有排期时由导演层择机注入一次可选机遇。"""
    ids = scheduled_for(state)
    if ids:
        return ids
    active = _director_context(state)
    if active and active.get("id"):
        return [active["id"]]
    picked = _director_pick(state)
    return [picked["id"]] if picked else []


def event_today(state: dict) -> dict | None:
    ids = active_events(state)
    if not ids:
        return None
    ev_id = ids[0]
    ev = _EVENTS[ev_id]
    ctx = _director_context(state, ev_id) if ev.get("dynamic_npc") else None
    return {"id": ev_id, "name": _format_event(ev["name"], ctx), "cat": ev["cat"],
            "desc": _format_event(ev["desc"], ctx),
            "options": [{"id": o["id"], "label": _format_event(o["label"], ctx),
                         "need": f"{sk.SKILLS[o['req'][0]][0]}≥L{o['req'][1]}" if o.get("req") else ""}
                        for o in ev["options"]]}


def on_new_day(state: dict) -> str:
    """新一天：刷新当日活动横幅＋首次排期推收件箱。返回横幅通知（可为空）。"""
    st = state.setdefault("events", {})
    ev = event_today(state)
    st["today"] = ev["id"] if ev else None
    if ev and st.get("notified_day") != game_today(state):
        st["notified_day"] = game_today(state)
        state["inbox"] = (state.get("inbox") or [])[-49:] + [{
            "ts": now_iso(), "type": "event", "world": WORLD_URBAN,
            "title": f"今日活动 · {ev['name']}",
            "text": f"{ev['desc']}（点开中栏活动横幅即可参与）"}]
    return f"【系统】今日活动：{ev['name']}——{ev['desc']}" if ev else ""


def action_label(state: dict, action: str) -> str | None:
    """把【活动】id:option 翻译成可读 label；非本前缀返回 None。"""
    if not action.startswith(PREFIX):
        return None
    body = action[len(PREFIX):]
    ev_id, _, opt_id = body.partition(":")
    ev = _EVENTS.get(ev_id)
    if not ev:
        return None
    opt = next((o for o in ev["options"] if o["id"] == opt_id), None)
    ctx = _director_context(state, ev_id) if ev.get("dynamic_npc") else None
    return (f"{_format_event(ev['name'], ctx)}·{_format_event(opt['label'], ctx)}"
            if opt else _format_event(ev["name"], ctx))


def before_turn(state: dict, action: str) -> dict | None:
    """【活动】拦截：结算选项结果并返回完整 TurnResult（跳过 demo/LLM）。"""
    if not action.startswith(PREFIX):
        return None
    body = action[len(PREFIX):]
    ev_id, _, opt_id = body.partition(":")
    ev = _EVENTS.get(ev_id)
    if ev is None:
        raise ValueError("没有这个活动。")
    if ev_id not in active_events(state):
        raise ValueError(f"「{ev['name']}」今日不在活动表内。")
    opt = next((o for o in ev["options"] if o["id"] == opt_id), None)
    if opt is None:
        raise ValueError("没有这个参与方式。")
    ctx = _director_context(state, ev_id) if ev.get("dynamic_npc") else None
    if ev.get("dynamic_npc") and not (ctx and ctx.get("npc")):
        raise ValueError("这场邂逅已经散场。")

    # 检定：技能等级 + 属性加成（每满10点属性等效+1级）
    result_key = "win"
    if opt.get("req"):
        sid, diff = opt["req"]
        eff = sk.level(state, sid) + sk.attr_bonus(state, sid)
        result_key = "pass" if eff >= diff else ("half" if eff == diff - 1 else "fail")
        if opt.get(result_key) is None:  # 该档位无独立文案时降档
            result_key = "half" if result_key == "fail" and opt.get("half") else result_key
    res = opt.get(result_key) or opt["win"]

    notices = []
    from .engine import _apply_items, change_affinity, change_bond
    from .models import CURRENCY, find_npc
    target = find_npc(state, ctx.get("npc", "")) if ctx else None
    if target is None:
        for npc_name in ev.get("npcs", [])[:2]:
            candidate = find_npc(state, npc_name)
            if candidate and candidate.get("known_to_player"):
                target = candidate
                break
    if res.get("xp"):
        notices.extend(sk.add_xp(state, res["xp"][0], res["xp"][1]))
    if res.get("xp_any"):
        skill_id, _ = _top_skill(state)
        notices.extend(sk.add_xp(state, skill_id, int(res["xp_any"])))
        notices.append(f"【系统】{sk.SKILLS[skill_id][0]}经验 +{res['xp_any']}。")
    if res.get("gold"):
        _apply_items(state, [{"name": CURRENCY, "desc": "系统商城通用货币",
                              "count": res["gold"]}])
        notices.append(f"【系统】活动收入：系统金币 +{res['gold']}。")
    if res.get("fame"):
        from . import career
        career.add_fame(state, res["fame"][0], res["fame"][1])
        notices.append(f"【系统】{res['fame'][0]}名望 +{res['fame'][1]}。")
    if res.get("fame_any"):
        from . import career
        domain = ((state.get("player") or {}).get("career") or {}).get("domain") or "商业"
        career.add_fame(state, domain, int(res["fame_any"]))
        notices.append(f"【系统】{domain}名望 +{res['fame_any']}。")
    if res.get("opp"):
        from . import career
        if career.give_opportunity(state, res["opp"]):
            notices.append(f"【系统】获得机遇标记：「{res['opp']}」——可用【事业】行动入门对应领域。")
    if target is not None:
        if res.get("affinity"):
            _, aff_notices = change_affinity(state, target, int(res["affinity"]))
            notices.extend(aff_notices)
        if res.get("bond"):
            change_bond(target, res["bond"])
    if res.get("fact"):
        from . import memory
        memory.append_fact(state, _format_event(res["fact"], ctx), state["turn"],
                           known_by=[target["name"]] if target else [])
    for npc_name in ev.get("npcs", [])[:2]:
        npc = find_npc(state, npc_name)
        if npc and npc.get("known_to_player"):
            _, aff_notices = change_affinity(state, npc, OPTION_NPCS_AFFINITY)
            notices.extend(aff_notices)
    state.setdefault("events", {})["last_join_turn"] = state["turn"]
    director = _director_state(state)
    active = director.get("active")
    if isinstance(active, dict) and active.get("id") == ev_id:
        director["active"] = None

    choices = [f"【活动】{ev_id}:{o['id']}" if o["id"] != opt_id else "先休息一下，回味今天"
               for o in ev["options"]][:4]
    while len(choices) < 2:
        choices.append("继续今天的行程")
    return {
        "story_text": f"{_format_event(ev['desc'], ctx)}\n\n{_format_event(res['text'], ctx)}",
        "narration_world": "urban",
        "choices": choices,
        "state_updates": {},
        "system_notice": "",
        "_notices": notices,  # engine 侧追加进面板（不入契约校验路径）
    }
