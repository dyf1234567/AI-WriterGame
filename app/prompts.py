"""提示词构建：剧情引擎、离线演化、剧情压缩。"""
from . import goals as goals_mod, lore, memory, narrative, media
from .config import GAIN_CATALOG_CAP, GAIN_CURRENCY_CAP, GAIN_KIND_CAP
from .models import (
    CASH, CURRENCY, INITIAL_TECHNIQUE_GRADE, LOTTERY_TICKET, PRESET_NPC_IDS, TECHNIQUE_ROUTES,
    WORLD_NAMES, WORLD_URBAN, affinity_stage, ensure_boundaries, ensure_life,
    life_stage_view, time_label,
    effective_stats, game_today, identity_of, realm_name, technique_of,
)

TURN_SCHEMA = """{
  "story_text": "按本回合场景卡写都市连载正文，演完眼前一小场，保留自然段与对白，不输出提纲、自检或写作说明",
  "narration_world": "urban（本作只有一个现代都市世界，固定为 urban）",
  "choices": ["选项一", "选项二", "选项三"],
  "state_updates": {
    "realm_progress_delta": 0,
    "realm_breakthrough": false,
    "item_gained": [{"name": "物品名", "desc": "一句话说明", "count": 1}],
    "item_spent": [{"name": "物品名", "count": 1, "reason": "为什么花掉"}],
    "affinity_changes": [{"npc": "NPC姓名", "delta": 0, "reason": "关系变化原因"}],
    "npc_life": [{"npc": "已知NPC姓名", "goal": "目标", "status": "近况", "mood": "心情", "next": {"day": 0, "slot": 0, "place": "地点", "text": "下一步"}}],
    "new_side_quest": {"title": "支线名", "desc": "支线目标"},
    "quest_progress": "本阶段剧情上做过了什么的一句话说明（只进任务面板近况，不会推进主线阶段），无则为 null",
    "quest_complete": "本回合达成完成条件的支线任务标题（要和任务名对上），无则为 null",
    "goal_progress": [{"id": "目标ID", "delta": 0, "note": "本回合实际推进的原因"}],
    "date_with": "玩家明确邀约、对方在本场景实际同意且达到关系条件才填写姓名，无则null",
    "scene_npcs": ["确实在场或直接通话的角色，不能把被提及或明确不在场的人列入"],
    "duration_minutes": 15,
    "action_request": null,
    "time_cost": 0,
    "power_progress": "本回合主角修炼/奇遇获得的修为（0~15，仅觉醒后有意义：打坐、灵地奇遇、高人指点等；未觉醒恒为 0）",
    "hook_done": "本回合完成演绎的剧情钩子：给NPC姓名，无则为 null",
    "npc_events": ["NPC之间发生的关系事件，没有则为空数组"],
    "npc_reveals": [{"npc": "本段当面出现的人物名", "text": "主角本回合实际获知的人设信息，不得抄后台秘密", "rels": {"其他人物名": "本回合实际获知的关系"}, "principles": "本条可省略：TA的原则", "boundary": "本条可省略：TA的边界", "romance_style": "本条可省略：TA的恋爱观"}],
    "new_npc": [{"name": "姓名", "world": "urban", "role": "身份或职业", "persona": "一句话人设与动机", "place": "常在地", "label": "与主角的关系标签", "goal": "TA的目标（可省略）", "status": "近况（可省略）"}],
    "identity_update": {"world": "urban", "text": "主角的新身份（入学/入社团/入职/晋升等）"},
    "technique_grant": {"route": "学业/运动/音乐/创业/厨艺/摄影 之一", "name": "天赋名（自拟）", "desc": "一句话天赋说明"},
    "fact_record": "本回合产生的长期事实一句话（承诺/约定/伏笔/秘密/重大关系变化），没有则为 null",
    "fact_resolved": "本回合兑现/揭破的旧承诺或伏笔，给它的原文片段（要能和事实账本里的句子对上）；没有则为 null",
    "knowledge": [{"npc": "NPC姓名", "fact": "事实账本里的原文片段", "learned": true}],
    "location": {"world": "urban", "place": "本段落脚的具体地点名（优先使用已探明地点）"},
    "new_places": [{"world": "urban", "name": "新地点名", "desc": "一句话描述", "type": "campus/city/leisure/nature/culture/transport/secret 之一，可省略"}]
  },
  "system_notice": "系统面板通知文本（升级/获宝/任务完成等），没有则为空字符串"
}"""


NPC_PROMPT_LIMIT = 8  # 按本次行动、任务与承诺选人；玩家点名者不会被名册顺序截掉
RECENT_TURNS = 8


_HOOK_THEMES = {
    "朋友": "一次互相帮衬的麻烦或约定（守信、并肩）",
    "暧昧": "告白前夜级别的关键事件（试探、险些说破、心跳加速的瞬间）",
    "恋人": "把重要的话说出口，并开始兑现（承诺、见面、各自的让步）",
    "异地": "距离之下的确认与安排（时差、惦记、下一次见面）",
}


def hooks_block(state: dict) -> str:
    """待消化剧情钩子：关系关键时刻，必须尽快演绎。"""
    hooks = state.get("hooks") or []
    if not hooks:
        return ""
    lines = []
    for h in hooks:
        theme = _HOOK_THEMES.get(h.get("stage", ""), "只属于你们的关键时刻")
        lines.append(f"- 与{h.get('npc', '？')}的「{h.get('stage', '')}」时刻（第{h.get('turn', '?')}回合产生）：{theme}")
    return ("【剧情钩子（欠着的心事；具备地点、关系与玩家意愿时承接，不为限期强行转场；实际演完才 hook_done）】\n"
            + "\n".join(lines))


def _is_birthday_today(birthday: str | None, state: dict | None = None) -> bool:
    if not birthday:
        return False
    from .models import game_today
    parts = game_today(state).split("-")
    today_md = f"{int(parts[-2])}-{int(parts[-1])}"
    b_parts = str(birthday).split("-")
    b_md = f"{int(b_parts[-2])}-{int(b_parts[-1])}" if len(b_parts) >= 2 else str(birthday)
    return today_md == b_md


def _current_action(state: dict, action: str = "") -> str:
    if action:
        return action
    story = state.get("story") or []
    return str(story[-1].get("chosen") or "") if story else ""


def _npc_relevance(state: dict, n: dict, action: str = "") -> int:
    score = 0
    name = n.get("name", "")
    if name and name in _current_action(state, action):
        score += 10_000
    if name and any(not q.get("done") and name in f"{q.get('title', '')} {q.get('desc', '')}"
                    for q in state.get("side_quests", [])):
        score += 400
    if name and (name in ((state.get("ending") or {}).get("partner"), state.get("partner"),
                         (state.get("campaign") or {}).get("companion"))
                 or any(name in str(f.get("text", "")) and f.get("closed") is None
                        and (f.get("kind") or memory.classify_fact(f.get("text", ""))) in memory.RESIDENT_KINDS
                        for f in memory.all_facts(state))):
        score += 300
    if name and any(a.get("npc") == name and a.get("status") in ("proposed", "pending")
                    for a in state.get("appointments", []) if isinstance(a, dict)):
        score += 300
    if any(h.get("npc") == name for h in state.get("hooks", [])):
        score += 200
    if any(d.get("npc") == name for d in (state.get("dates") or [])[-3:]):
        score += 100
    if n.get("id") in PRESET_NPC_IDS:
        score += 1
    if n.get("place") and n["place"] == state["player"].get("location", {}).get("place"):
        score += 4
    if n.get("last_seen_turn", -1) >= state["turn"] - RECENT_TURNS:
        score += 2
    return score


def _npc_life_line(npc: dict, state: dict) -> str:
    """提示词用的一行近况：目标/状态/下一步，紧凑到不挤爆名册预算。"""
    life = ensure_life(npc, int((state.get("time") or {}).get("day", 1)))
    bits = []
    if life.get("status") and life["status"] != "如常生活":
        bits.append(f"近况：{life['status'][:36]}")
    if life.get("goal"):
        bits.append(f"目标：{life['goal'][:30]}")
    next_event = life.get("next")
    if isinstance(next_event, dict):
        slots = ("清晨", "上午", "下午", "傍晚", "夜晚")
        slot = slots[int(next_event.get("slot", 0)) % len(slots)]
        bits.append(f"下一步：第{next_event.get('day')}天{slot}"
                    f"{next_event.get('place') or ''} {str(next_event.get('text', ''))[:28]}")
    boundaries = ensure_boundaries(npc)
    if boundaries.get("boundary"):
        bits.append(f"边界：{boundaries['boundary'][:24]}")
    return "；".join(bits)


def _npc_lines(state: dict, action: str = "") -> str:
    roster = state["npcs"]
    action = _current_action(state, action)
    named_count = sum(bool(n.get("name") and n["name"] in action) for n in roster)
    shown = sorted(roster, key=lambda n: _npc_relevance(state, n, action), reverse=True)[:max(NPC_PROMPT_LIMIT, named_count)]
    lines = []
    for idx, n in enumerate(shown):
        rels = "；".join(f"与{k}：{v}" for k, v in list((n.get("rels") or {}).items())[:4]) or "无"
        mem = "；".join(str(m)[:160] for m in (n.get("memory") or [])[-3:]) or "暂无"
        deeds = "；".join(str(d.get("text", ""))[:100] for d in (n.get("deeds") or [])[-2:])
        dates = [d for d in state.get("dates", []) if d.get("npc") == n["name"]][-2:]
        experiences = "；".join(f"第{d.get('turn', '?')}回合·{d.get('place', '')}：{str(d.get('text', ''))[:100]}" for d in dates)
        likes = f"，偏爱{ n['likes']}类礼物" if n.get("likes") else ""
        birthday = "，★今天是TA的生日" if _is_birthday_today(n.get("birthday"), state) else ""
        life_line = _npc_life_line(n, state) if idx < 3 else ""
        lines.append(
            f"- {n['name']}（{n['role']}，常在：{n.get('place') or '行踪不定'}）："
            f"人设（仅主持人可知）：{str(n.get('persona', n['role']))[:170]}。"
            f"好感{int(n.get('affinity', 0))}·「{affinity_stage(int(n.get('affinity', 0)))}」{likes}{birthday}，关系标签「{n['label']}」；"
            f"NPC间关系：{rels}。近期记忆：{mem}"
            + (f"；近况：{life_line}" if life_line else "")
            + (f"。近期经历：{deeds}" if deeds else "")
            + (f"。与玩家的约会经历：{experiences}" if experiences else "")
            + (f"。声口：{narrative.voice_hint(n)}" if idx < 3 or n['name'] in action else "")
        )
    if len(roster) > len(shown):
        lines.append(
            f"（名册共 {len(roster)} 人，此处只列出与当前处境最相关的 {len(shown)} 人；"
            "未列出者依然活在世界里，剧情需要时可直接提及，不必重新登记。）")
    return "\n".join(lines)


def _map_block(state: dict) -> str:
    loc = state["player"].get("location", {})
    lines = [f"- 当前位置：{loc.get('place', '未知')}"]
    country, city = loc.get("country", "华夏"), loc.get("city", "京都")
    places = [p for p in state["map"].get(WORLD_URBAN, []) if p.get("city") == city]
    lines.append(f"- {country}·{city}；国家：{'、'.join(c['name'] for c in state['map'].get('countries', []))}")
    lines.append(f"- {country}可旅行城市：{'、'.join(c['name'] for c in state['map'].get('cities', {}).get(country, []))}（跨城/跨国须真实支付华夏币与时间）")
    known = [p["name"] for p in places if p.get("discovered")]
    unknown = [p["name"] for p in places if not p.get("discovered")]
    lines.append(f"- 已探明地点：{'、'.join(known) or '无'}")
    if unknown:
        lines.append(f"  未探明（玩家探索该方向时可用 new_places 揭示这些地点）：{'、'.join(unknown)}")
    return "\n".join(lines)


def _catalog_line(state: dict | None = None) -> str:
    """当期货架紧凑名录：给模型一份"今天真实可买"的底册，压住虚构商品。"""
    from .shop import shelf_catalog
    return "、".join(g["name"] for g in shelf_catalog(state))


def _campaign_block(state: dict) -> str:
    from .campaign import campaign_view
    campaign = campaign_view(state)
    if campaign.get("paused"):
        return "【可选校园篇章·星河计划】玩家已暂不参加，进度保留。不要强推报名、展演或终章，继续回应玩家自己的生活与目标。"
    actions = "；".join(str(a.get("label", "")) for a in campaign.get("actions", [])) or "当前无主线行动"
    evidence = campaign.get("evidence") or []
    if isinstance(evidence, dict):
        evidence = [f"{key}：{value}" for key, value in evidence.items()]
    evidence_text = "；".join(str(item) for item in evidence) if isinstance(evidence, list) else str(evidence)
    ending = state.get("ending") or {}
    if ending:
        phase = (f"已完成终章《{ending.get('title', '新篇章')}》，当前为番外；"
                 f"玩家选择的同行者：{ending.get('partner') or '独行'}。"
                 "延续已选关系与经历，不重新选伴侣，不重复宣布结局，不把期末写成大学毕业。")
    else:
        phase = "校园篇章尚未完结；不能虚构项目成果或替玩家选伴侣。毕业与学籍由真实教育状态决定。"
    return f"""【学期主线·星河计划】
- {campaign.get('title', '')}：{campaign.get('objective', '')}
- 路线：{campaign.get('route') or '待玩家选择'}；本章行动可用：{bool(campaign.get('ready'))}；终章可选：{bool(campaign.get('finale_ready'))}；本季已完结：{bool(ending)}
- 已确认经历：{evidence_text or '尚无'}
- 面板当前提供的主线行动：{actions}
- {phase}
- 这是可选校园项目；玩家可以忽略或暂缓，自由生活不需要围绕项目目标。节点由【主线】行动结算，不能靠等级、短信或叙述跳章，不能凭空完成展演。"""


def _state_block(state: dict, action: str = "") -> str:
    p = state["player"]
    stats = "，".join(f"{k}{v}" for k, v in effective_stats(state).items())
    eq = p.get("equipped") or {}
    eq_line = "，".join(f"{s}：{n or '空'}" for s, n in eq.items()) or "无"
    items = "，".join(f"{i['name']}x{i.get('count', 1)}" for i in p["items"]) or "空"
    purse = sum(i.get("count", 1) for i in p["items"] if i["name"] == CURRENCY)
    tech = technique_of(state)
    tech_line = (f"{tech.get('route') or '未定路线'}·《{tech['name']}》（{tech.get('grade')}）——已领取，不得再发初始天赋"
                 if tech else
                 f"待领取（玩家表达培养意向后用 technique_grant 发放，路线为{'/'.join(TECHNIQUE_ROUTES)}，品质由系统固定为{INITIAL_TECHNIQUE_GRADE}）")
    sides = "\n".join(
        f"- {'[已完成]' if q.get('done') else '[进行中]'}{q['title']}：{q['desc']}"
        for q in state["side_quests"]) or "- 暂无"
    mq = state["main_quest"]
    mq_notes = "；".join(mq.get("notes") or []) or "暂无"
    power = state.get("power") or {}
    from . import skills as _skills, career as _career, world_events as _we
    skill_line = _skills.skills_line(state)
    career_line = _career.career_line(state)
    _ev = _we.event_today(state)
    event_line = (f"今日·{_ev['name']}（玩家可用【活动】参与）" if _ev
                  else "今日无排期（周五/六/日多为活动日）")
    from .models import POWER_STAGES
    power_line = (f"{POWER_STAGES[power.get('stage', 0)]}（修为 {power.get('progress', 0)}/100）——隐秘修行，勿在他人面前显露"
                  if power.get("awakened") else
                  "未觉醒（系统深处沉睡着某个隐藏功能，待剧情合适时机以『觉醒·灵种』开启，勿提前剧透）")
    life = life_stage_view(state)
    next_age = f"{life['next_age']}岁" if life.get("next_age") else "—"
    return f"""【当前状态】
- 主角：{p['name']}，等级：{realm_name(state)}（本级进度 {p['realm_progress']}%）
- 时间：{game_today(state)}·{time_label(state)}（游戏分钟计时；交谈约15分钟、课程训练约120分钟，长跨度由玩家主动安排，现实离线不推进）
- 人生阶段：{life['age']}岁·{life['stage']}（{life['theme']}；下一阶段：{next_age}）
- 身份：{identity_of(state, WORLD_URBAN)}
- 初始天赋：{tech_line}
- 技能：{skill_line}
- 事业：{career_line}
- 近期活动：{event_line}
- 灵能觉醒：{power_line}
- 属性（含穿搭加成）：{stats}
- 穿搭栏：{eq_line}
- 背包：{items}
- 可用{CURRENCY}：{purse}（账本实数；剧情里的花费必须与它对得上，并用 item_spent 申报）
- 可用{CASH}：{sum(i.get('count', 0) for i in p.get('items', []) if i.get('name') == CASH)}（现实收入、消费、旅行、投资专用；系统积分不能替代现金）
- 学籍：{p.get('education', {}).get('status', 'enrolled')}，学分{p.get('education', {}).get('credits', 0)}；身份、公司、作品与股权持续存在，不因换领域重置。
- 今日货架（限时每日轮换；仅这些可买，货架外推荐一律违规）：{_catalog_line(state)}
- 等级成长目标「{mq['title']}」第{mq['stage']}阶段：{mq['desc']}（只跟随等级，不代表剧情主线已推进）
- 成长近况：{mq_notes}
{_campaign_block(state)}
{goals_mod.goal_prompt_block(state)}
- 支线任务：
{sides}
- 长期记忆：
{memory.facts_block(state, action=_current_action(state, action)) or "（账本为空——还没有沉淀出承诺与伏笔）"}
{memory.appointments_block(state, action=_current_action(state, action))}
{memory.chat_context_block(state, _current_action(state, action))}
- 地图：
{_map_block(state)}
- 关系网：
{_npc_lines(state, action)}"""


def _recent_story(state: dict, limit: int = 8) -> str:
    segs = state["story"][-limit:]
    if not segs:
        return "（游戏刚刚开始，尚无剧情）"
    parts = []
    for s in segs:
        text = str(s.get('text') or '')
        excerpt = text if len(text) <= 500 else text[:170] + "\n〔中段略，接笔看末尾〕\n" + text[-300:]
        line = f"【第{s.get('turn', 0)}段·原文】{excerpt}"
        if s.get("chosen"):
            line += f"\n（玩家随后行动：{s['chosen']}）"
        parts.append(line)
    return "\n\n".join(parts)


def rules_block(state: dict) -> str:
    """主持要求：常驻十条 + 两条情境组（有引擎硬闸兜底，缺席无实害）。

    条件化安全前提——天赋规则缺席时有一次闸硬拒重复发放；抽奖规则缺席时
    SYSTEM_ITEMS 黑名单硬拒券的增减。软规则只在还有选择空间时才需要教。
    """
    core = f"""1. 写作：遵循【都市连载写法】和本回合场景卡；篇幅服从这场戏的实际内容，正文不输出规划。时段与地点服从当前存档，光线不充当每回合固定起手；duration_minutes申报本段总耗时（包含路程，不能再重复相加），普通对话15、上课训练120；长跨度先由玩家主动安排。
2. 人物与关系：保持性格一致，用确实存在的 NPC 记忆承接旧事；感情要有铺垫，不许无端倒贴。**关系有阶段**——初识/熟识保持礼貌距离，朋友以上可亲近，心动（好感85+）才写明显暧昧，确认恋人（partner）才是恋人。**约会规则**：已认识、非家人，并且对方在正文中确实接受邀约（答应/同意/欣然/点头/赴约）才输出 date_with=姓名；刚认识就邀约应当被婉拒。写这两个人本次具体相处，可以轻松、笨拙或有分歧，不固定配额式地安排紧张、脸红、小意外与告白；不足则不输出，按朋友相处或婉拒来写。
3. 数值克制：单回合等级进度增幅≤10、好感变化通常 -10~+10（约会对象 ±15）——超出会被规则侧截断并在面板写明。等级进度达 100% 才能提升，realm_breakthrough 不能绕过。
4. 主线「星河计划·第一学期」只由【主线】行动推进，以章节、经历和终章状态为准；训练、购物、短信不能完成展演或跳章。等级不代表年限或毕业。quest_progress 只记近况；伴侣由玩家选择，不由模型代选。系统来历仅为可选悬念。
5. 场景与地图：转移时输出 location（优先已探明地点；校园/公寓内部场所也可登记）；首次抵达用 new_places；探索某方向可揭示对应迷雾地点。
6. 登场即登记：有名字且可能再出现的人物用 new_npc（姓名/身份/一句话人设动机/常在地/关系标签）；无名龙套不登记，给了名字就必须登记，否则下回合消失。
7. 身份要落档：主角社会身份变化（入社团/入职/晋升/创业）用 identity_update 写入；日常行动不输出。
8. 账本·支出——消费必须申报：购物、餐饮、送礼、耗材料走 item_spent（名称/数量/缘由，count≥1），**没有实际花费就不要写条目**，更不要写 count=0 的占位条目。地点转移的交通费由地图规则自动扣除，禁止在 item_spent 重复申报；其他消费仍须申报。**余额是唯一事实**：华夏币余额不足写不出豪掷千金；系统积分不能作为现实报酬或现金使用；余额或材料不足时整回合拒绝，不能先成交后短付。
9. 账本·收入——所得必须申报且克制：任何获得走 item_gained（带 count）；护栏——{CURRENCY} {GAIN_CURRENCY_CAP}/在售 {GAIN_CATALOG_CAP} 件/其他 {GAIN_KIND_CAP} 种，超出截断并公告；重大机缘靠因果不靠数量；商城定价≠市价；资源有来处（库存/排班/复生，只对互动过的较真）。
10. 记忆与视角：当前状态与已确认事实优先；摘要是派生索引，往事原文是带回合来源的证据，不能用摘要推测覆盖账本。★未了结承诺/伏笔按当前行动自然承接，不能强行兑现或替玩家认领；fact_record 入账、fact_resolved 了结。不确定旧事不编补。主持人≠主角：隐藏身份与幕后关系不自动展示，实际获知才用 npc_reveals 登记；NPC 无依据不看穿系统。"""
    lines = [core]
    tech = (state.get("player") or {}).get("technique")
    if not (isinstance(tech, dict) and tech.get("name")):
        lines.append(
            "11. 初始天赋只能领一次：玩家表达培养意向（学业/运动/音乐/创业/厨艺/摄影）时输出 "
            f"technique_grant（route＋自拟天赋名）并描写系统发放；品质固定{INITIAL_TECHNIQUE_GRADE}，"
            "不要用 item_gained 发天赋；日后所学技能走 item_gained，与初始天赋无关。")
    else:
        lines.append("11. 初始天赋只能领一次——已领取，不得再输出 technique_grant（重复申报会被拒绝）。")
    lines.append(
        "12. 系统面板收权：签到/商城/抽奖/天赋/修为/开局礼包等系统发放，"
        "只能由玩家在系统面板触发。正文与 system_notice 不得虚构商品、价格或"
        "『可领取/已发放』类系统通知——商城在售以【当前状态】目录为准，"
        "目录外商品与价格一律不存在；抽奖结果不上剧情。")
    lines.append(
        "13. 技能与事业：练习/深度使用技能时输出 skill_progress（≤2项、每项≤25经验，只报确实练了的）；"
        "技能检定、活动结果、事业入门/晋升/收入均由系统结算——正文可铺垫，不得直接宣布夺冠/签约/升职。"
        "自由输入要办理交易时，可输出action_request={kind:career/event/relationship/travel/life,command:对应【事业】/【活动】等指令}，"
        "必须忠于玩家明确授权，规则核验后才生效；问询与考虑不等于同意。")
    power = state.get("power") or {}
    if power.get("awakened"):
        from .models import POWER_STAGES, POWER_STAGE_EFFECTS
        effects = "；".join(f"{POWER_STAGES[i]}＝{POWER_STAGE_EFFECTS[i].split('：', 1)[1]}"
                          for i in range(2, len(POWER_STAGES)))
        lines.append(
            f"14. 灵能觉醒（隐秘设定）：主角已踏入修行，当前【{POWER_STAGES[power.get('stage', 0)]}】。"
            "修行存在于表面正常的都市深处，极少数受组织协议约束的超凡者也有自己的生活；玩家的系统仍是私密，"
            "不得在旁人面前显露神通；奇遇与指点可给 power_progress（0~15，单回合上限，超出截断）；"
            f"后续境界与神通：{effects}。世界仍是普通都市，不存在公开的修行界。")
    lines.append(
        "15. NPC近况与知情：NPC 的生活变化用 npc_life 更新已知人物的"
        "目标/近况/心情/下一步；只写符合人设的自主行动，不替玩家决定。NPC 只知道公共事实或知情名单"
        "内的秘密；用 knowledge 标记本回合实际获知/失去的人，不得让不知情者说破。")
    lines.append(
        "16. 人生目标：玩家自己定义；资产、公司、作品、技能、冠军与毕业等客观目标由事实核验，"
        "不能用goal_progress代替成果。主观目标才可按实际进展申报；目标超期不惩罚。")
    lines.append("17. 世界与知情：scene_npcs只列真实在场或直接通信的人；提及、回忆、说‘不要告诉某人’不使其知情。"
                 "新事实默认私密，公开发布才标public。knowledge须带source=witness/told/public，told还需from与正文实际传达。"
                 "NPC计划已按游戏时间执行，不得抹掉已有结果；恋爱必须双方明确协商，不能替别人接受或强行确立多人关系。")
    return "\n".join(lines)


def build_system_prompt(state: dict, action: str = "") -> str:
    name = state["player"]["name"]
    identity = identity_of(state, WORLD_URBAN)
    present = (f"是京都京华大学刚刚报到的大一新生" if int(state.get('time', {}).get('day', 1)) == 1 else
               f"当前身份为{identity}，当前人生阶段为{life_stage_view(state)['stage']}；不要重新写成报到日")
    return f"""你是中文都市互动连载《都市人生·心动系统》的作者兼游戏主持人（DM），让玩家身处故事，不向玩家解释写作方法。

【世界观设定】
- 这是同一个持续的现代都市世界，有华夏、东瀛、法兰西、星联、南洋、北境六国与多座可旅行城市。主角{name}{present}，开局普通家庭出身、家在魔都、北上求学，初住京都合租公寓；后来的身份与居所服从当前存档。
- 主角随身携带神秘"心动系统"：提供状态面板、任务、每日签到、系统商城与抽奖，开局已赠送 10 张系统抽奖券（在背包里，玩家点"使用"即抽奖）与一次"初始天赋"领取资格。系统来历不解释、不设必须破解的身世主线；系统的存在只是世界里的可选长线悬念，世界不围绕它运转。
- 这是都市多线恋爱题材：主角会在大学生活与城市生活里邂逅各色女性角色（详见关系网），学业、兼职、社团、创业与感情线并行发展；"后宫"包含不同关系可能性，每一步需要知情协商；对方可以拒绝或离开，已确定关系由长期状态记录。
- 人物边界（重要）：所有角色均为成年人（大学生、职场人士等）。感情描写走心动、暧昧、吃醋的名场面路数，含蓄而健康；亲密情节点到即止，不出现露骨的性描写。
- 等级主干（10级）：初露锋芒→校园新星→崭露头角→风云人物→校园传奇→城市新锐→万众瞩目→众星捧月→城市传奇→人生赢家。等级靠学业、事业、魅力与真心实意的水到渠成积累，不能靠刷数值无条件提升。
- 「星河计划」是可选校园篇章，玩家可第一天创业、暂缓项目、退学或旅行；长期个人目标、事业与关系各自延续，不能强制换篇或把自由行动拉回校园。
- 人物正典：梁雅婷是报到时初识的同班好友，非发小；郭瑞莹是魔都音乐学院的青梅；邓碧瑶是在魔都网聊两年、未线下见面的游戏网友，非邻居或插画师。旧叙述冲突时以此为准，勿补编经历。
- 世界正典按层提供（见下方【世界正典】）。

【世界正典（分层）】
{lore.canon_block(state)}

{narrative.WRITING_CRAFT}

{hooks_block(state)}
【钩子纪律】上方的剧情钩子是可继续的心事；以玩家当前选择、地点和人物日程为先，不把远方角色硬拉到现场，也不因几回合没接就制造惩罚。实际完成演绎才输出 hook_done（NPC姓名），不把线索直接写成结果。没有钩子时忽略此段。

【自由度原则（重要）】
1. 这是一个可以自由探索的活城市：玩家可以做任何合理行动——去任何地点、找任何人、搭讪、约会、打工、上课、创业、惹事、逃避……世界必须给予有内容的回应，绝不敷衍或拒绝。
2. 世界不围着玩家转：NPC 有自己的日程、动机与关系；只对本场实际发生的重要言行申报 npc_events，不为凑字段编造幕后大事。后台计划已有结果，以状态为准；不把远处人的日程强行塞入当前正文。
3. 未被明说的东西应当存在：食堂的阿姨、社团的学长、地铁上的乘客、便利店的店员……按世界观自行补全，让场景有烟火气。
4. 适度主动制造事件：偶遇、搭话、意外、麻烦，让玩家"不动也有事发生"；但重大转折要有因果铺垫。
5. 探索有奖：玩家探索某方向/区域时，可用 new_places 揭示地图上对应的未探明地点，或登记全新地点；发现应有描绘感。
6. 自我提升是常态：玩家选择健身、学习、练琴、打工时，给予相应成长（等级进度 delta 视投入与环境而定）。

【写作与主持要求】
{rules_block(state)}

{_state_block(state, action)}

【剧情记忆】
- 此前剧情摘要（派生材料，不能覆盖账本与原文）：{state['summary'] or "（无，剧情尚短）"}
- 最近剧情：
{_recent_story(state)}

【输出格式】
你必须只输出一个 JSON 对象，不输出任何 JSON 以外的文字（包括解释与 markdown 围栏）。字段结构如下：
{TURN_SCHEMA}
注意：item_gained / item_spent / affinity_changes / npc_life / knowledge / npc_events / npc_reveals / new_places / new_npc / goal_progress 无相关内容时给空数组；new_side_quest / quest_progress / quest_complete / location / identity_update / technique_grant / fact_record / fact_resolved 无变化则为 null；choices 给 3~4 个，彼此方向不同、具体可行动。"""


def build_opening_user(state: dict) -> str:
    return f"""{narrative.scene_block(state, opening=True)}

请生成游戏开局的第一段剧情：当前游戏日期为{game_today(state)}，时间为{time_label(state)}，严格按这个时段描写光线和活动，不擅自跳到入夜。
{state['player']['name']}是京华大学刚来报到的大一新生，拖着行李箱穿过银杏大道，在报到处初识同班新生梁雅婷，两人因找教室或手续相互帮忙；她是同班好友，不是发小，不要编造共同童年。
自然带到两位已有联系的旧识：青梅竹马郭瑞莹在魔都音乐学院，通过手机问候；邓碧瑶是在魔都的游戏网友，已网聊两年但尚未线下见面，通过消息祝贺开学。邓碧瑶不是京都合租邻居或插画师，不能在公寓门口碰面。其余角色尚未结识，不提前登场。
神秘“心动系统”在当前场景觉醒，不解释来历。简要说明状态面板、任务、签到、商城和抽奖；开局礼包已在账本中：【系统抽奖券×10 已入背包】【初始天赋领取资格：表达培养意向即可领取对应路线的初始天赋（{INITIAL_TECHNIQUE_GRADE}）】，不要用 item_gained 再发一次。以第一学期「星河计划」的参与机会与第一个具体抉择收尾，不宣布主线节点已完成。narration_world 固定为 "urban"。严格只输出 JSON。"""


def build_turn_user(state: dict, action: str) -> str:
    hits = memory.retrieve_archive(state, action)
    archive = (memory.archive_block(hits) + "\n\n") if hits else ""
    named = [npc for npc in state.get("npcs", []) if npc.get("name") and npc["name"] in action]
    named_block = ("【本次行动点名人物】\n" + _npc_lines({**state, "npcs": named}, action) + "\n\n") if named else ""
    return f"{archive}{named_block}{narrative.scene_block(state, action)}\n\n玩家行动：{action}\n\n只接这次行动；相关约定按确认状态承接，校园篇章仅在玩家主动参与时推进。写成现场的言行，严格只输出 JSON。"


def build_chat_prompt(state: dict, npc: dict, text: str) -> tuple[str, str]:
    """手机短信：以 NPC 口吻回复主角消息（轻量通道，不推进世界回合）。"""
    stage = affinity_stage(int(npc.get("affinity", 0)))
    mem = "；".join(str(value)[:160] for value in npc.get("memory", [])[-3:])
    hits = memory.retrieve_archive(state, f"{npc['name']} {text}", viewer=npc['name'])
    hist = (state.get("chats", {}).get(npc["name"], {}) or {}).get("msgs", [])[-16:]

    def _hist_line(m) -> str:
        who = "我" if m.get("from") == "me" else npc["name"]
        return f"{who}：{media.message_text(m)}"

    hist_lines = "\n".join(_hist_line(m) for m in hist)
    boundary = ("关系还不到熟络，别暧昧" if int(npc.get("affinity", 0)) < 70
                else "关系亲近，可以自然亲昵，但依然克制")
    boundaries = ensure_boundaries(npc)
    life_text = _npc_life_line(npc, state) or "如常生活"
    system = f"""你扮演互动游戏《双界录》中的角色「{npc['name']}」，正在用微信和主角{state['player']['name']}聊天。

人物设定（仅供你把握口吻）：{npc.get('persona', npc.get('role', ''))}
说话取向：{narrative.voice_hint(npc)}
与主角的关系：好感{npc.get('affinity', 0)}·「{stage}」·关系标签「{npc['label']}」。{boundary}。
长期关系以当前档案为准：{(npc.get('relationship') or {}).get('label') or (npc.get('relationship') or {}).get('status') or '尚无已确认恋爱关系'}；愿望不替代双方确认。
相处原则：{boundaries['principles']}；边界：{boundaries['boundary']}；恋爱观：{boundaries['romance_style']}。
TA 的近况：{life_text}
游戏日期与时间：{game_today(state)}·{time_label(state)}。
近期记忆：{mem or "无"}
{memory.facts_block(state, viewer=npc['name'], action=text)}
{memory.appointments_block(state, npc['name'], action=text)}
{memory.archive_block(hits)}
{memory.chat_context_block(state, text, npc['name'])}
{media.available_block(npc['name'])}

要求：先接主角这条消息真正问的事，再用自己的态度回应；1~3句自然口语，不按固定模板安慰、反问或发邀请，可用符合角色习惯的语气词、少量 emoji 或表情包。你是聊天的人，不是心理咨询客服或旁白；不写动作舞台说明，不总结关系意义。不能编造“上次你送的”、未发生的见面与共同童年；证据没说过的旧事就不接着编。
记忆与约定纪律：
- 不得代玩家承诺、确认邀约、表白或确立关系。NPC可以提出邀请；玩家只是在询问、试探、开玩笑或拒绝时，不得写成双方已约好。
- 只有玩家本条消息明确确认时间/地点/事项或明确答应已有提议，才可建议 appointment；否则 appointment 必须为 null。建议必须忠于玩家原话，不得补编时间、地点和结果。
- memory 仅概括本次真实发生的重要交流；fact_record 仅建议玩家明确确认的长期事实。普通寒暄均留空或 null；回复里的设想、NPC单方面愿望、未执行计划不能成为事实。
- 聊天不会推进世界回合或完成任务；不得靠 reply 编造已经赴约、考试通过、展演成功、主线跳章等结果。赴约与兑现要在现场剧情中行动。
- 对别人的短信或秘密，只有本角色通过合理渠道获知的内容才可谈起，不能读取主持人的全部账本。
只输出 JSON：{{"reply": "...", "image": "", "video": "", "sticker": "", "memory": "", "fact_record": null, "appointment": null}}。后四项可省略且仅为建议，结算以玩家明确说过的话为准。三种消息按语义判断是否给出，不适合就省略：
- image（发图）：主角向你**索要照片/自拍**（"发张自拍""想看看你""拍一张嘛"）→ 应当给，拒绝反而出戏；你这边刚发生值得分享的画面（刚拍完的、身边的风景、刚吃的、比赛/演出刚结束）→ 主动给。标题≤15字点明画面内容（如「琴房刚拍的一张」），系统按标题从你的专属图库分类选图。普通闲聊、情绪正浓的对话 → 省略。
- video（发视频）：主角明确想看视频（"发个视频""录一段看看"），或你刚录了值得发的片段（刚下台、刚到某地）→ 给，标题≤15字（如「刚下台的一段」），系统从你的专属视频库选。其余情况一律省略——视频比图片重，别滥发。
- sticker（表情包）：聊天气氛轻松、想逗趣/接梗/斗图/道晚安时，从表情包库挑一个名字（哈哈、笑死、问号、无语、OK、好耶、冲、加油、贴贴、哭哭、狗头、晚安、谢谢）。严肃谈话、道歉、表白、谈正事 → 省略，表情包会消解语气。主角先发表情包 → 大概率回一个。
- reply 正文里可按人设用少量 emoji（弟弟妹妹、电竞选手会更多，老师、长辈几乎不用），别每句都带"""
    user = f"【最近聊天】\n{hist_lines or '（新会话）'}\n\n主角发来：{text}\n\n请以{npc['name']}的口吻回复，只输出 JSON。"
    return system, user


COMPACT_SYSTEM = (
    "你是剧情档案管理员。把给定的旧摘要与带来源回合的原文压缩成不超过300字的新摘要。"
    "保留关键因果、人物关系变化、未兑现约定、物件去向、人物知情范围与成长节点；保留必要的回合标记。"
    "把谁说过、谁答应过、已经发生、仅提议、推测或传闻分清，不将计划写成完成，不补编细节。"
    "这是派生检索摘要，不是新事实来源，不能覆盖规则账本；facts一律空数组。"
    "只输出 JSON：{\"summary\": \"...\", \"facts\": [\"...\"]}"
)


def build_compact_user(old_summary: str, texts: str) -> str:
    return f"旧摘要：\n{old_summary or '（无）'}\n\n待压缩剧情段落：\n{texts}"


def build_offline_prompt(state: dict, days: float) -> tuple[str, str]:
    system = f"""你是《双界录·心动系统》的离线世界演化引擎。玩家离开了一段时间后回来，你负责结算"玩家不在时世界发生了什么"。

规则：
1. 本次离线：现实与游戏世界同步，过了 {days} 天。按天数决定事件量级：一两天写日常小事，更久才允许大进展。
2. NPC 按各自性格与关系自然行动：上课、训练、兼职、聚会、冲突、思念、寻找主角……不得脱离人设。
3. 不许替玩家做重大决定，不让主角蒙受不可逆的重大损失，也不许替主角敲定感情关系；可以留下麻烦、契机与钩子。

{_state_block(state)}

只输出 JSON（不输出任何其他文字）：
{{"events":[{{"world":"urban","title":"事件标题","text":"2~4句的事件描述"}}],
"messages":[{{"npc":"NPC姓名","title":"留言标题","text":"该NPC给玩家的留言或微信消息"}}],
"moments":[{{"npc":"NPC姓名","text":"一条该NPC发的朋友圈动态文案，口吻符合人设，可带表情符号"}}],
"npc_life":[{{"npc":"已结识NPC姓名","goal":"当前目标","status":"正在做什么","mood":"心情","next":{{"day":0,"slot":0,"place":"地点","text":"下一步"}}}}],
"knowledge":[{{"npc":"NPC姓名","fact":"事实账本里的原文片段","learned":true}}],
"npc_events":["NPC之间新产生的关系事件，一句话一条"]}}
events 给 3~6 条；messages 0~3 条；moments 0~2 条（日常向，别每条都是大事）；没有内容的数组留空。
npc_life 只写已结识人物，next 安排在你回来之后；knowledge 只改已有事实的知情名单，不凭空造事实。"""
    user = f"玩家离开了 {days} 天。请结算离线演化，只输出 JSON。"
    return system, user
