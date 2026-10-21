"""世界事件：日历驱动的周期活动＋导演层偶遇注入。

事件的参与选项带技能/属性门槛（skills.skill_check 门控），
结果由引擎结算——技能经验、金币（内部通道）、名望、机遇标记
（写入 career.opportunities，事业入门的钥匙）、在场 NPC 好感。
行动前缀【活动】由 before_turn 拦截，模板叙事不经过模型。
"""
import zlib
from datetime import date

from . import skills as sk
from .models import WORLD_URBAN, game_today, now_iso

PREFIX = "【活动】"
DROUGHT_TURNS = 10  # 连续未参加活动的回合数阈值（导演层注入用）

# 事件定义：id → {name, cat, desc, options:[{id,label,req:{skill,diff}|None,
#   win:{text,xp,gold,fame,opp,npcs}, half:..., lose:...}]}
_EVENTS = {
    "gala": {
        "name": "校园晚会", "cat": "娱乐", "npcs": ["苏晚晴", "傲寒", "乐乐"],
        "desc": "周五晚的大礼堂灯火通明，节目单还缺一个压轴。",
        "options": [
            {"id": "sing", "label": "登台唱一首", "req": ("vocal", 2),
             "win": {"text": "你的嗓音镇住了全场，谢幕时礼堂的掌声久久不停——后台角落里，一位戴着工牌的经纪公司星探朝你递来了名片。",
                     "xp": ("vocal", 40), "gold": 0, "fame": ("娱乐", 8),
                     "opp": "经纪公司试镜邀请"},
             "half": {"text": "副歌唱到一半破了音，好在台下掌声还算善意——音乐系的苏晚晴在侧幕冲你比了个加油的手势。",
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


def active_events(state: dict) -> list[str]:
    """当日可用事件 = 排期 ∪ 导演层注入（干旱判定）。"""
    ids = scheduled_for(state)
    st = state.setdefault("events", {})
    last_join = int(st.get("last_join_turn", -999))
    if not ids and state["turn"] - last_join >= DROUGHT_TURNS:
        seed = zlib.crc32(game_today(state).encode("utf-8"))
        ids = ["street"] if seed % 3 == 0 else []
    return ids


def event_today(state: dict) -> dict | None:
    ids = active_events(state)
    if not ids:
        return None
    ev = _EVENTS[ids[0]]
    return {"id": ids[0], "name": ev["name"], "cat": ev["cat"], "desc": ev["desc"],
            "options": [{"id": o["id"], "label": o["label"],
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
    return f"{ev['name']}·{opt['label']}" if opt else ev["name"]


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
    from .engine import _apply_items, change_affinity
    from .models import CURRENCY, find_npc
    if res.get("xp"):
        notices.extend(sk.add_xp(state, res["xp"][0], res["xp"][1]))
    if res.get("gold"):
        _apply_items(state, [{"name": CURRENCY, "desc": "系统商城通用货币",
                              "count": res["gold"]}])
        notices.append(f"【系统】活动收入：系统金币 +{res['gold']}。")
    if res.get("fame"):
        from . import career
        career.add_fame(state, res["fame"][0], res["fame"][1])
        notices.append(f"【系统】{res['fame'][0]}名望 +{res['fame'][1]}。")
    if res.get("opp"):
        from . import career
        if career.give_opportunity(state, res["opp"]):
            notices.append(f"【系统】获得机遇标记：「{res['opp']}」——可用【事业】行动入门对应领域。")
    for npc_name in ev.get("npcs", [])[:2]:
        npc = find_npc(state, npc_name)
        if npc and npc.get("known_to_player"):
            _, aff_notices = change_affinity(state, npc, OPTION_NPCS_AFFINITY)
            notices.extend(aff_notices)
    state.setdefault("events", {})["last_join_turn"] = state["turn"]

    choices = [f"【活动】{ev_id}:{o['id']}" if o["id"] != opt_id else "先休息一下，回味今天"
               for o in ev["options"]][:4]
    while len(choices) < 2:
        choices.append("继续今天的行程")
    return {
        "story_text": f"{ev['desc']}\n\n{res['text']}",
        "narration_world": "urban",
        "choices": choices,
        "state_updates": {},
        "system_notice": "",
        "_notices": notices,  # engine 侧追加进面板（不入契约校验路径）
    }
