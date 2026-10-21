# -*- coding: utf-8 -*-
"""技能／世界事件／事业引擎回归测试（state_growth 风格，直接执行）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import career, engine, goals, prompts, shop, skills, world_events  # noqa: E402
from app.models import default_npcs, default_state, life_stage_view, normalize_state, public_state  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILED.append(name)


def no_storage():
    """临时屏蔽存档写入。"""
    from contextlib import contextmanager
    import app.storage as st

    @contextmanager
    def _ctx():
        old = st.save
        st.save = lambda s, **k: None
        try:
            yield
        finally:
            st.save = old
    return _ctx()


# ---------- 技能 ----------

def test_skills_growth_and_check():
    s = default_state("技")
    check("从零练习即建条目", skills.level(s, "vocal") == 0
          and skills.add_xp(s, "vocal", 10) == [] and skills.level(s, "vocal") == 1)
    ns = skills.add_xp(s, "vocal", 100)
    check("满百升级并通知", skills.level(s, "vocal") == 2 and any("声乐" in n for n in ns), str(ns))
    check("检定三档", skills.skill_check(s, "vocal", 2) == "pass"
          and skills.skill_check(s, "vocal", 3) == "half"
          and skills.skill_check(s, "vocal", 5) == "fail")
    check("属性加成等效等级", skills.attr_bonus(s, "vocal") >= 0)  # 魅力6→0；10→1
    s["player"]["stats"]["魅力"] = 10
    check("魅力10=+1 等效", skills.attr_bonus(s, "vocal") == 1)
    caps = skills.apply_model_progress(s, [
        {"skill": "vocal", "xp": 999, "reason": "x"},
        {"skill": "mech", "xp": 30, "reason": "x"},
        {"skill": "coding", "xp": 20, "reason": "x"},   # 第三项应被丢弃
        {"skill": "nope", "xp": 20, "reason": "x"},])   # 白名单外丢弃
    check("申报钳制：≤2项/≤25xp/白名单",
          skills.ensure_skills(s)["vocal"]["xp"] <= 100  # 10+100→L2 余10；+25→35
          and "mech" in skills.ensure_skills(s) and "coding" not in skills.ensure_skills(s),
          str(skills.ensure_skills(s)))


def test_skill_view_and_prompt_line():
    s = default_state("视")
    skills.add_xp(s, "vocal", 30)
    line = skills.skills_line(s)
    view = skills.skills_view(s)
    check("提示词行只列已学", "声乐L1" in line and "操作" not in line, line)
    check("视图含未学淡显项", any(v["id"] == "mech" and not v["learned"] for v in view))


# ---------- 世界事件 ----------

def test_event_calendar_determinism():
    s1, s2 = default_state("甲"), default_state("乙")
    for day in range(1, 29):
        s1["time"] = {"day": day, "slot": 0}
        s2["time"] = {"day": day, "slot": 3}
        a, b = world_events.scheduled_for(s1), world_events.scheduled_for(s2)
        check(f"day{day} 同日同时段排期一致", a == b, f"{a} vs {b}")


def test_event_npcs_exist_in_roster():
    """世界事件的在场角色必须来自当前名册，避免旧阵容残留。"""
    roster = {n["name"] for n in default_npcs()}
    missing = [(ev_id, name) for ev_id, ev in world_events._EVENTS.items()
               for name in ev.get("npcs", []) if name not in roster]
    check("世界事件在场角色都在名册", not missing, str(missing))


def test_event_participation_gating():
    s = default_state("丙")
    s["time"] = {"day": 4, "slot": 0}  # 周五·晚会
    with no_storage():
        # 无声乐：差≥2级 → lose 文案＋安慰经验
        data = world_events.before_turn(s, "【活动】gala:sing")
        check("低技能走 lose 线", "L1" not in data["story_text"] and data["_notices"], data["story_text"][:30])
        skills.add_xp(s, "vocal", 100)  # L2 → pass
        data2 = world_events.before_turn(s, "【活动】gala:sing")
        joined = " ".join(data2["_notices"])
        check("达线走 win 线＋机遇落档",
              "经纪公司试镜邀请" in joined
              and "娱乐名望 +8" in joined, joined[:80])
        check("机遇写进 career", "经纪公司试镜邀请" in career.ensure_career(s)["opportunities"])
        check("活动记录参加回合", s["events"]["last_join_turn"] == s["turn"])
    try:
        world_events.before_turn(s, "【活动】market:stall")
        check("非当日活动被拒", False)
    except ValueError:
        check("非当日活动被拒", True)
    label = world_events.action_label(s, "【活动】gala:sing")
    check("label 翻译", label and "校园晚会" in label, str(label))
    check("非本前缀返回 None", world_events.action_label(s, "随便走走") is None)


def test_event_banner_and_inbox():
    s = default_state("丁")
    s["time"] = {"day": 4, "slot": 0}
    note = world_events.on_new_day(s)
    check("横幅通知生成", "校园晚会" in note, note[:40])
    check("收件箱入账", any("今日活动" in m.get("title", "") for m in s["inbox"]))
    check("event_today 供前端", (world_events.event_today(s) or {}).get("id") == "gala")
    s2 = default_state("戊")
    s2["turn"] = 1
    s2["events"] = {"last_join_turn": 1}  # 刚参加过活动：导演冷却与干旱都不触发
    s2["time"] = {"day": 2, "slot": 0}  # 周二无固定排期
    world_events.on_new_day(s2)
    check("无排期且无触发信号时无横幅", world_events.event_today(s2) is None)


# ---------- 事业 ----------

def test_career_entry_paths():
    s = default_state("己")
    with no_storage():
        try:
            career.before_turn(s, "【事业】入门 娱乐")
            check("无技能无机遇被拒", False)
        except ValueError as e:
            check("无技能无机遇被拒", "声乐" in str(e), str(e)[:40])
        career.give_opportunity(s, "经纪公司试镜邀请")
        career.before_turn(s, "【事业】入门 娱乐")
        c = career.ensure_career(s)
        check("机遇直入练习生", c["domain"] == "娱乐" and c["stage"] == 1)
        check("机遇幂等", not career.give_opportunity(s, "经纪公司试镜邀请"))
        try:
            career.before_turn(s, "【事业】入门 电竞")
            check("已入行换领域被拒", False)
        except ValueError:
            check("已入行换领域被拒", True)
        # 硬门槛路径：商业（经营≥2＋金币200）
        s2 = default_state("庚")
        skills.add_xp(s2, "manage", 30)  # L1
        ok, _ = career.entry_check(s2, "商业")
        check("经营不足被拒", not ok)
        skills.add_xp(s2, "manage", 80)  # L2
        for i in s2["player"]["items"]:
            if i["name"] == "系统金币":
                i["count"] += 300
        ok2, msg2 = career.entry_check(s2, "商业")
        check("硬门槛＋启动资金通过", ok2, msg2[:50])


def test_career_weekly_settle():
    s = default_state("辛")
    career.give_opportunity(s, "青训营测试资格")
    career.before_turn(s, "【事业】入门 电竞")
    with no_storage():
        n1 = career.settle_week(s, "2026-W02")
        gold1 = shop.currency_count(s)
        n2 = career.settle_week(s, "2026-W02")  # 同周幂等
        check("周薪入账（内部通道）", any("周结算" in x for x in n1)
              and gold1 >= 35 and n2 == [], f"{n1} gold={gold1}")
        n3 = career.settle_week(s, "2026-W03")
        check("跨周再结算", any("周结算" in x for x in n3), str(n3))


def test_career_promotion_and_assets():
    s = default_state("壬")
    career.give_opportunity(s, "青训营测试资格")
    career.before_turn(s, "【事业】入门 电竞")
    c = career.ensure_career(s)
    with no_storage():
        skills.add_xp(s, "mech", 250)  # L3（青训→替补的技能线）
        try:
            career.before_turn(s, "【事业】晋升")
            check("名望不足晋升被拒", False)
        except ValueError as e:
            check("名望不足晋升被拒", "名望" in str(e), str(e)[:40])
        career.add_fame(s, "电竞", 12)
        for i in s["player"]["items"]:
            if i["name"] == "系统金币":
                i["count"] += 100
        data = career.before_turn(s, "【事业】晋升")
        check("晋升到替补并涨周薪", c["stage"] == 2
              and any("替补选手" in x for x in data["_notices"]), str(data["_notices"])[:60])
        # 一路推到明星（stage4）验证资产发放（st3 需 200 金、st4 需 500 金）
        for need_lv, fame, gold in ((6, 40, 300), (8, 60, 600)):
            skills.add_xp(s, "mech", (need_lv - skills.level(s, "mech")) * 100)
            career.add_fame(s, "电竞", max(0, fame - c["fame"]["电竞"]))
            for i in s["player"]["items"]:
                if i["name"] == "系统金币":
                    i["count"] += gold
            career.before_turn(s, "【事业】晋升")
        check("电竞明星发战队股份", c["stage"] == 4
              and any(a["type"] == "战队股份" for a in s["player"]["assets"]),
              str(s["player"]["assets"]))


def test_career_train_caps():
    s = default_state("癸")
    career.give_opportunity(s, "天使投资人名片")
    career.before_turn(s, "【事业】入门 商业")
    for i in s["player"]["items"]:
        if i["name"] == "系统金币":
            i["count"] += 200
    with no_storage():
        for i in range(3):
            career.before_turn(s, "【事业】特训")
        try:
            career.before_turn(s, "【事业】特训")
            check("特训每周限3次", False)
        except ValueError as e:
            check("特训每周限3次", "3 次" in str(e) or "满" in str(e), str(e)[:40])
        lv_xp = s["player"]["skills"].get("manage", {})
        check("特训涨了核心技能", lv_xp.get("lv", 0) >= 1 and lv_xp.get("xp", 0) >= 60,
              str(lv_xp))


# ---------- 引擎整合 ----------

def test_engine_integration():
    s = default_state("子")
    s["player"]["technique"] = {"route": "音乐", "name": "绝对音感", "grade": "S级", "turn": 1}
    s["time"] = {"day": 4, "slot": 0}  # 周五
    with no_storage():
        s2, n = engine.take_turn(s, "【活动】gala:watch")   # 看热闹：无门槛
        check("【活动】经 take_turn 全链路", "校园晚会" in n or "灯火通明" in n, n[:50])
        s3, n3 = engine.take_turn(s, "练一会儿唱歌")          # 演示练习段
        check("练习段落账技能", s3["player"]["skills"].get("vocal", {}).get("xp", 0) > 0,
              str(s3["player"]["skills"]))
        try:
            engine.take_turn(s, "【事业】入门 娱乐")           # 无资格 → EngineError 拒整回合
            check("【事业】无资格被 EngineError 拒绝", False)
        except engine.EngineError as e:
            check("【事业】无资格被 EngineError 拒绝", "声乐" in str(e), str(e)[:50])


def test_normalize_and_public():
    old = default_state("旧档")
    old["player"].pop("skills", None)
    old["player"].pop("career", None)
    old["player"].pop("assets", None)
    normalize_state(old)
    check("旧档惰性补齐三键", isinstance(old["player"].get("skills"), dict)
          and old["player"].get("career", {}).get("domain") is None
          and old["player"]["assets"] == [])
    from app.models import public_state
    pub = public_state(old)
    check("public_state 附三视图", "skills_view" in pub and "career_view" in pub
          and "event_today" in pub)


def test_goals_and_life_stages():
    s = default_state("目标")
    r = goals.create_goal(s, "三年内做出一款自己的游戏", "想做出能让人记住的东西", 1095)
    check("目标创建成功", r["ok"] and len(s["goals"]) == 1, str(r))
    g = s["goals"][0]
    check("目标带领域/计划/三里程碑",
          g["domain"] == "电竞" and bool(g["plan"]) and len(g["milestones"]) == 3, str(g))
    check("目标日期按游戏日计算", g["target_day"] == s["time"]["day"] + 1095)
    check("重名目标被拒", not goals.create_goal(s, "三年内做出一款自己的游戏", "", 30)["ok"])
    for i in range(4):
        goals.create_goal(s, f"目标{i}", "", 30)
    check("进行中目标上限 5",
          not goals.create_goal(s, "第六个目标", "", 30)["ok"] and len(s["goals"]) == 5)

    before = g["progress"]
    r2 = goals.manual_progress(s, g["id"], "写完第一版策划")
    check("手动推进 5%", r2["ok"] and g["progress"] == before + 5)
    check("同一天手动二次被拒", not goals.manual_progress(s, g["id"], "")["ok"])
    s["time"]["day"] += 1
    goals.manual_progress(s, g["id"], "继续")
    check("次日可继续记录", g["progress"] == before + 10)

    s["turn"] = 1
    before_model = g["progress"]
    goals.advance_goal(s, g["id"], 99, "模型推进")
    after_first = g["progress"]
    goals.advance_goal(s, g["id"], 99, "模型推进")
    check("模型单回合推进 ≤25", after_first - before_model == 25
          and g["progress"] == after_first, f"{before_model}->{g['progress']}")
    check("里程碑按进度自动完成", g["milestones"][0]["done"])
    for turn in range(2, 6):
        s["turn"] = turn
        goals.advance_goal(s, g["id"], 25, "继续推进")
    check("进度满 100 自动完成",
          g["status"] == "completed" and g["progress"] == 100
          and all(m["done"] for m in g["milestones"]), str(g))
    check("完成后不能再推进", not goals.advance_goal(s, g["id"], 5, "")["ok"])

    extra = goals.create_goal(s, "试着坚持一件事", "", 7)
    check("可创建第二个目标", extra["ok"] and len(s["goals"]) == 6)
    check("放弃目标成功", goals.abandon_goal(s, extra["goal"]["id"])["ok"]
          and s["goals"][-1]["status"] == "abandoned")
    check("放弃后不能再推进", not goals.advance_goal(s, extra["goal"]["id"], 5, "")["ok"])

    overdue = goals.create_goal(s, "七天内完成一件小事", "", 7)["goal"]
    s["time"]["day"] = overdue["target_day"] + 1
    view = next(v for v in goals.goals_view(s) if v["id"] == overdue["id"])
    check("超期目标被标记且不惩罚", view["overdue"] and view["status"] == "active")

    s["time"] = {"day": 1, "slot": 0}
    check("18 岁在大学阶段", life_stage_view(s)["age"] == 18
          and life_stage_view(s)["stage"] == "大学阶段")
    s["time"] = {"day": 365 * 4 + 1, "slot": 0}
    check("22 岁进入社会起点", life_stage_view(s)["age"] == 22
          and life_stage_view(s)["stage"] == "社会起点")
    s["time"] = {"day": 365 * 10 + 1, "slot": 0}
    check("28 岁进入社会影响力", life_stage_view(s)["age"] == 28
          and life_stage_view(s)["stage"] == "社会影响力")
    s["time"] = {"day": 365 * 17 + 1, "slot": 0}
    check("35 岁进入无限人生", life_stage_view(s)["age"] == 35
          and life_stage_view(s)["stage"] == "无限人生")

    pub = public_state(s)
    check("公开档案带目标与人生阶段", "goals" in pub and "life_stage" in pub)
    old = default_state("旧档")
    old.pop("goals", None)
    normalize_state(old)
    check("旧档自动补齐目标列表", old.get("goals") == [])

    p = default_state("提示")
    goals.create_goal(p, "把一部小说写完", "先写到十万字", 90)
    sp = prompts.build_system_prompt(p)
    check("提示词含人生目标与人生阶段",
          "人生目标" in sp and "把一部小说写完" in sp and "人生阶段" in sp)

    c = default_state("契约目标")
    goals.create_goal(c, "完成一次公开演出", "", 30)
    gid = c["goals"][0]["id"]
    engine.apply_updates(c, {
        "story_text": "你在排练厅把整首歌走了一遍。",
        "narration_world": "urban",
        "choices": ["继续练", "回去休息"],
        "state_updates": {"goal_progress": [{
            "id": gid, "delta": 5, "note": "完整走了一遍"}]},
        "system_notice": "",
    })
    check("主剧情 goal_progress 接线", c["goals"][0]["progress"] == 5,
          str(c["goals"][0]))


def test_career_operations():
    s = default_state("经营")
    career.give_opportunity(s, "青训营测试资格")
    career.before_turn(s, "【事业】入门 电竞")
    for item in s["player"]["items"]:
        if item["name"] == "系统金币":
            item["count"] += 1000
    c = career.ensure_career(s)
    check("经营三键默认落档", c["ops"] == {"staff": 0, "quality": 0, "marketing": 0}
          and c["projects"] == [])
    options = career.project_options(s)
    check("经营项目目录有三项", len(options) == 3, str(options))
    check("阶段不足的项目不可接",
          any(not p["available"] and "阶段" in p["reason"] for p in options), str(options))

    data = career.before_turn(s, "【事业】经营 招聘")
    check("招聘消耗金币并加团队", c["ops"]["staff"] == 1
          and any("团队人数" in n for n in data["_notices"]), str(data["_notices"]))
    for _ in range(4):
        career.before_turn(s, "【事业】经营 招聘")
    check("团队人数封顶 5", c["ops"]["staff"] == 5, str(c["ops"]))
    try:
        career.before_turn(s, "【事业】经营 招聘")
        check("团队超上限被拒", False)
    except ValueError:
        check("团队超上限被拒", True)

    before_gold = next(i["count"] for i in s["player"]["items"] if i["name"] == "系统金币")
    start = career.before_turn(s, "【事业】经营 项目 city_cup steady")
    active = c["projects"][0]
    after_gold = next(i["count"] for i in s["player"]["items"] if i["name"] == "系统金币")
    check("项目启动扣款并进入进行中",
          active["status"] == "active" and active["plan"] == "steady"
          and before_gold - after_gold == 80, str(active))
    check("项目启动有面板说明", any("经营项目" in n for n in start["_notices"]))
    try:
        career.before_turn(s, "【事业】经营 项目 bootcamp steady")
        check("同时只允许一个项目", False)
    except ValueError:
        check("同时只允许一个项目", True)

    s["time"]["day"] += 7
    settle = career.settle_projects(s)
    check("到期项目自动结算", active["status"] == "completed"
          and active["outcome"] in ("success", "partial", "fail"), str(active))
    check("结算进面板与收件箱", any("经营项目" in n for n in settle)
          and any("经营结算" in m.get("title", "") for m in s["inbox"]))
    check("结算后可以接下一个项目", active["status"] != "active")
    cv = career.career_view(s)
    check("事业视图带经营信息", "ops" in cv and "project_options" in cv
          and "completed_projects" in cv and cv["completed_projects"])

    # 成功/失败：高技能团队成功，低技能进取失败
    def project_state(name, skill_level, plan):
        st = default_state(name)
        cc = career.ensure_career(st)
        cc.update({"domain": "电竞", "stage": 1})
        for item in st["player"]["items"]:
            if item["name"] == "系统金币":
                item["count"] += 1000
        skills.add_xp(st, "mech", skill_level * 100)
        ok, _story, _n = career.start_project(st, "city_cup", plan)
        check(f"{name} 项目可启动", ok)
        st["time"]["day"] += 7
        career.settle_projects(st)
        return st["player"]["career"]["projects"][0]["outcome"]

    check("高技能项目成功", project_state("成功项目", 6, "steady") == "success")
    check("低技能进取项目失败", project_state("失败项目", 0, "bold") == "fail")

    # 团队周薪：账面不足则解散
    w = default_state("周薪")
    wc = career.ensure_career(w)
    wc.update({"domain": "电竞", "stage": 1})
    wc["ops"]["staff"] = 5
    notices = career.settle_week(w, "2026-W10")
    check("团队周薪入账", any("团队周薪" in n for n in notices)
          and wc["ops"]["staff"] == 0, str(notices))

    old = default_state("旧经营")
    old["player"].pop("career", None)
    normalize_state(old)
    oc = old["player"].get("career") or {}
    check("旧档补齐经营三键", isinstance(oc.get("ops"), dict)
          and isinstance(oc.get("projects"), list))


def test_director_layer():
    # 关系升温 + 无排期：导演给出可选的单独相处，而不是强制事件
    s = default_state("导演")
    s["turn"] = 8
    s["time"] = {"day": 2, "slot": 0}
    s["events"] = {"last_join_turn": 8}
    npc = next(n for n in s["npcs"] if n["name"] == "郭瑞莹")
    npc["known_to_player"] = True
    npc["affinity"] = 80
    ev = world_events.event_today(s)
    check("关系升温触发导演事件", ev and ev["id"] == "relation_window", str(ev))
    check("动态文本换成具体人物", ev and "郭瑞莹" in ev["desc"] and "{npc}" not in ev["desc"], ev and ev["desc"])
    active = s["director"]["active"]
    check("导演记录选中人物", active and active.get("npc") == "郭瑞莹", str(active))
    before_aff = npc["affinity"]
    before_bond = dict(npc["bond"])
    data = world_events.before_turn(s, "【活动】relation_window:walk")
    check("动态关系事件可结算", data and "郭瑞莹" in data["story_text"])
    check("事件后六维与好感变化",
          npc["affinity"] == before_aff + 2
          and npc["bond"]["trust"] == before_bond["trust"] + 2
          and npc["bond"]["familiarity"] == before_bond["familiarity"] + 3,
          str(npc["bond"]))
    check("事件事实按知情人落账",
          any("没对别人说过的事" in f["text"] and "郭瑞莹" in f["known_by"] for f in s["facts"]))
    check("参与后事件关闭并进入冷却",
          s["director"]["active"] is None and world_events.event_today(s) is None)

    # 事业：有领域且到主力阶段，导演给行业机会；下次换成竞争
    s2 = default_state("导演事业")
    s2["turn"] = 8
    s2["time"] = {"day": 2, "slot": 0}
    s2["events"] = {"last_join_turn": 8}
    c = career.ensure_career(s2)
    c.update({"domain": "娱乐", "stage": 2})
    c["fame"]["娱乐"] = 30
    ev2 = world_events.event_today(s2)
    check("事业顺利触发行业机会", ev2 and ev2["id"] == "industry_offer", str(ev2))
    s2["director"]["history"] = [{"id": "industry_offer", "category": "事业", "turn": 1}]
    s2["director"]["active"] = None
    s2["director"]["last_event_turn"] = 0
    ev3 = world_events.event_today(s2)
    check("事业连续触发改为竞争", ev3 and ev3["id"] == "competition", str(ev3))

    # 探索：近期探明新地点
    s3 = default_state("导演探索")
    s3["turn"] = 8
    s3["time"] = {"day": 2, "slot": 0}
    s3["events"] = {"last_join_turn": 8}
    for place in s3["map"]["urban"][:6]:
        place["discovered"] = True
    ev4 = world_events.event_today(s3)
    check("探索新地点触发深夜微光", ev4 and ev4["id"] == "hidden_clue", str(ev4))

    # 专注：技能等级足够高
    s4 = default_state("导演专注")
    s4["turn"] = 8
    s4["time"] = {"day": 2, "slot": 0}
    s4["events"] = {"last_join_turn": 8}
    skills.add_xp(s4, "vocal", 400)
    ev5 = world_events.event_today(s4)
    check("长期专注触发作品机会", ev5 and ev5["id"] == "craft_showcase", str(ev5))

    # 干旱：长期没参加活动
    s5 = default_state("导演干旱")
    s5["turn"] = 12
    s5["time"] = {"day": 2, "slot": 0}
    s5["events"] = {"last_join_turn": -999}
    ev6 = world_events.event_today(s5)
    check("长期无活动触发街头偶遇", ev6 and ev6["id"] == "street", str(ev6))

    # 固定日历优先：周五晚会不被导演覆盖
    s6 = default_state("导演排期")
    s6["turn"] = 8
    s6["time"] = {"day": 4, "slot": 0}
    npc6 = next(n for n in s6["npcs"] if n["name"] == "郭瑞莹")
    npc6["known_to_player"] = True
    npc6["affinity"] = 80
    check("固定活动优先于导演", (world_events.event_today(s6) or {}).get("id") == "gala")

    old = default_state("旧导演")
    old.pop("director", None)
    normalize_state(old)
    check("旧档补齐导演状态", isinstance(old.get("director"), dict)
          and "active" in old["director"] and "history" in old["director"])


def test_prompt_lines():
    s = default_state("丑")
    for npc in s["npcs"]:
        npc["life"]["status"] = "在忙自己的事"
    sp = prompts.build_system_prompt(s)
    for key in ("- 技能：", "- 事业：", "- 近期活动：", "13. 技能与事业", "skill_progress",
                "bond_changes", "npc_life", "knowledge", "六维 信", "近况：", "边界："):
        check(f"提示词含 {key}", key in sp)
    skills.add_xp(s, "vocal", 40)
    check("技能行反映等级", "声乐L1" in prompts._state_block(s))


def main() -> int:
    for fn in [test_skills_growth_and_check, test_skill_view_and_prompt_line,
               test_event_calendar_determinism, test_event_npcs_exist_in_roster,
               test_event_participation_gating,
               test_event_banner_and_inbox, test_career_entry_paths,
               test_career_weekly_settle, test_career_promotion_and_assets,
               test_career_train_caps, test_engine_integration,
               test_goals_and_life_stages, test_director_layer,
               test_career_operations,
               test_normalize_and_public, test_prompt_lines]:
        print(f"== {fn.__name__} ==")
        fn()
    print()
    if FAILED:
        print(f"结果：{len(FAILED)} 项失败 -> {FAILED}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
