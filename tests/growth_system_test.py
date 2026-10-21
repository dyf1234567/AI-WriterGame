# -*- coding: utf-8 -*-
"""技能／世界事件／事业引擎回归测试（state_growth 风格，直接执行）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import career, engine, prompts, shop, skills, world_events  # noqa: E402
from app.models import default_state, normalize_state  # noqa: E402

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
    s2["time"] = {"day": 2, "slot": 0}  # 周二无排期
    world_events.on_new_day(s2)
    check("无排期无横幅", world_events.event_today(s2) is None)


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


def test_prompt_lines():
    s = default_state("丑")
    sp = prompts.build_system_prompt(s)
    for key in ("- 技能：", "- 事业：", "- 近期活动：", "13. 技能与事业", "skill_progress"):
        check(f"提示词含 {key}", key in sp)
    skills.add_xp(s, "vocal", 40)
    check("技能行反映等级", "声乐L1" in prompts._state_block(s))


def main() -> int:
    for fn in [test_skills_growth_and_check, test_skill_view_and_prompt_line,
               test_event_calendar_determinism, test_event_participation_gating,
               test_event_banner_and_inbox, test_career_entry_paths,
               test_career_weekly_settle, test_career_promotion_and_assets,
               test_career_train_caps, test_engine_integration,
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
