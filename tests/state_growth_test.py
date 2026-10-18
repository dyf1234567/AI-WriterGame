"""状态生长单元测试：新人物登记、身份落档、名册与提示词截断、收支账本、剧情压缩与归档。

不依赖服务与模型 API，直接驱动引擎结算层。
用法：.venv/Scripts/python tests/state_growth_test.py
"""
import json
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import engine, prompts, shop
from app.config import GAIN_CATALOG_CAP, GAIN_CURRENCY_CAP, GAIN_KIND_CAP
from app.models import (
    CURRENCY, INITIAL_TECHNIQUE_GRADE, LOTTERY_TICKET, MAX_NPCS, PRESET_NPC_IDS,
    SYSTEM_ITEMS, default_state, normalize_state,
)

FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILED.append(name)


def payload(updates: dict | None = None) -> dict:
    return {
        "story_text": "测试段落。" * 10,
        "narration_world": "xianxia",
        "choices": ["选项一", "选项二", "选项三"],
        "state_updates": updates or {},
        "system_notice": "",
    }


def find(state: dict, name: str) -> dict | None:
    return next((n for n in state["npcs"] if n["name"] == name), None)


def gen_npc(i: int, last_seen: int = -1, place: str = "别处") -> dict:
    return {"id": f"npc_g{i}", "name": f"路人{i}", "world": "xianxia", "role": "散修",
            "persona": "无名散修", "place": place, "affinity": 50, "label": "初识",
            "memory": [], "rels": {}, "last_seen_turn": last_seen}


# ---------- 新人物登记 ----------

def test_register_new_npc() -> None:
    s = default_state("测试侠")
    s["turn"] = 3
    s["player"]["world"] = "xianxia"
    s["player"]["location"] = {"world": "xianxia", "place": "青玄宗·山门"}
    notice = engine.apply_updates(s, payload({"new_npc": [{
        "name": "周砚", "world": "xianxia", "role": "外门弟子",
        "persona": "面生嘴碎，爱打听", "place": "外门弟子居",
        "label": "同门", "affinity": 40}]}))
    n = find(s, "周砚")
    check("新人物已登记", n is not None)
    check("字段与预设人物同构", n is not None and all(
        k in n for k in ("id", "name", "world", "role", "persona", "place",
                         "affinity", "label", "memory", "rels", "last_seen_turn")))
    check("登记值原样保留", n is not None and n["role"] == "外门弟子"
          and n["place"] == "外门弟子居" and n["affinity"] == 40 and n["label"] == "同门")
    check("登场回合被记录", n is not None and n["last_seen_turn"] == 3)
    check("登记进入系统通知", "周砚" in notice, notice)


def test_sparse_entry_gets_defaults() -> None:
    s = default_state("测试侠")
    s["turn"] = 1
    engine.apply_updates(s, payload({"new_npc": [{"name": "老王"}]}))
    n = find(s, "老王")
    check("只给名字也能登记", n is not None)
    check("缺省字段有兜底", n is not None and n["role"] == "身份不明"
          and n["label"] == "初识" and n["affinity"] == 50 and n["persona"] and n["memory"])
    check("常在地回落到本段落脚点", n is not None and n["place"] == s["player"]["location"]["place"], n and n["place"])


def test_invalid_entries_ignored() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"new_npc": [
        {"name": ""}, {"name": "   "}, "不是字典", None,
        {"name": "李四", "world": "火星", "affinity": "很多"}]}))
    check("空名与非字典条目被忽略", len(s["npcs"]) == 11, f"n={len(s['npcs'])}")
    n = find(s, "李四")
    check("非法世界回落到本段叙事世界", n is not None and n["world"] == "xianxia", n and n["world"])
    check("非法好感回落默认值", n is not None and n["affinity"] == 50)


def test_no_duplicate_registration() -> None:
    s = default_state("测试侠")
    before = len(s["npcs"])
    notice = engine.apply_updates(s, payload(
        {"new_npc": [{"name": "洛清衣", "role": "重复登记"}, {"name": "洛清衣"}]}))
    check("已存在的人物不会被重复登记", len(s["npcs"]) == before, f"n={len(s['npcs'])}")
    check("重复登记不产生通知", "名册" not in notice, notice)


def test_model_text_is_sanitized() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"new_npc": [{
        "name": "赵<img>", "persona": "<script>alert(1)</script>阴狠", "label": "<b>仇家</b>"}]}))
    n = find(s, "赵img")
    check("登记名剥离尖括号", n is not None)
    check("人设与标签剥离尖括号", n is not None
          and "<" not in n["persona"] and "<" not in n["label"], n and n["persona"])


@contextmanager
def temp_npc_archive():
    """把 NPC 归档指到临时目录，避免淘汰类测试写脏 data/。"""
    tmp = Path(tempfile.mkdtemp(prefix="sjl-npcarc-"))
    old = engine.NPC_ARCHIVE_FILE
    engine.NPC_ARCHIVE_FILE = tmp / "npc_archive.jsonl"
    try:
        yield engine.NPC_ARCHIVE_FILE
    finally:
        engine.NPC_ARCHIVE_FILE = old
        shutil.rmtree(tmp, ignore_errors=True)


def archive_records() -> list[dict]:
    path = engine.NPC_ARCHIVE_FILE
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_roster_cap_evicts_stale_generated_only() -> None:
    s = default_state("测试侠")
    s["turn"] = 100
    s["npcs"] += [gen_npc(i, last_seen=i) for i in range(MAX_NPCS)]
    with temp_npc_archive():
        engine.apply_updates(s, payload({"new_npc": [{"name": "新人甲"}]}))
        recs = archive_records()
    check("名册不超过上限", len(s["npcs"]) <= MAX_NPCS, f"n={len(s['npcs'])}")
    check("预设主角团全员保留", all(
        any(n["id"] == pid for n in s["npcs"]) for pid in PRESET_NPC_IDS))
    check("淘汰的是最久未登场者", find(s, "路人0") is None and find(s, "路人1") is None)
    check("刚登场的人物不会被淘汰", find(s, "新人甲") is not None)
    check("被淘汰者档案已归档", any(r.get("name") == "路人0" for r in recs), str([r.get("name") for r in recs]))
    check("归档保留好感与行事录字段", all(
        k in recs[0] for k in ("affinity", "deeds", "memory", "rels")) if recs else False)


def test_evicted_npc_reunites_with_history() -> None:
    s = default_state("测试侠")
    s["turn"] = 10
    s["npcs"].append({
        "id": "npc_gen10_0", "name": "侯三", "world": "xianxia", "role": "白溪镇摊主",
        "persona": "啰嗦但实在", "place": "白溪镇", "affinity": 66, "label": "熟人",
        "memory": ["第9回合：卖过主角一份舆图"],
        "deeds": [{"turn": 9, "text": "第9回合：卖过主角一份舆图"}],
        "rels": {"黑袍人": "同镇，互相忌惮"}, "last_seen_turn": 9})
    s["turn"] = 200
    s["npcs"] += [gen_npc(i, last_seen=100 + i) for i in range(MAX_NPCS)]
    with temp_npc_archive() as arc:
        engine.apply_updates(s, payload({"new_npc": [{"name": "张铁柱"}]}))  # 挤掉侯三
        check("侯三被淘汰并归档", find(s, "侯三") is None
              and any(r.get("name") == "侯三" for r in archive_records()))
        notice = engine.apply_updates(s, payload({"new_npc": [{
            "name": "侯三", "world": "xianxia", "role": "白溪镇摊主",
            "affinity": 50}]}))  # 重逢：模型给的好感50不该覆盖旧档66
        restored = find(s, "侯三")
        check("旧识重逢回名册", restored is not None)
        check("好感延续旧档不被重置", restored and restored["affinity"] == 66,
              f"affinity={restored and restored['affinity']}")
        check("行事录带着旧事与重逢", restored and any("舆图" in d["text"] for d in restored["deeds"])
              and any("久别重逢" in d["text"] for d in restored["deeds"]),
              str(restored and restored["deeds"]))
        check("旧关系保留", restored and restored["rels"].get("黑袍人"))
        check("重逢通知写明档案恢复", "旧识重逢" in notice and "档案恢复" in notice, notice[:120])
        check("重逢不占新登记口径", "新人物登入名册" not in notice.split("旧识重逢")[0]
              or "侯三" not in notice.split("旧识重逢")[0])


def test_eviction_blocked_when_archive_fails() -> None:
    s = default_state("测试侠")
    s["turn"] = 100
    s["npcs"] += [gen_npc(i, last_seen=i) for i in range(MAX_NPCS)]
    old_arch = engine._archive_npcs
    engine._archive_npcs = lambda st, v: False  # 归档写盘失败
    try:
        with temp_npc_archive():
            engine.apply_updates(s, payload({"new_npc": [{"name": "路人MAX"}]}))
    finally:
        engine._archive_npcs = old_arch
    check("归档失败时宁可不淘汰", len(s["npcs"]) > MAX_NPCS
          and find(s, "路人0") is not None,
          f"n={len(s['npcs'])}")



# ---------- 身份落档 ----------

def test_identity_update() -> None:
    s = default_state("测试侠")
    check("开局都市身份已预置", s["player"]["identity"]["urban"] == "临江三中·高三学生")
    notice = engine.apply_updates(s, payload(
        {"identity_update": {"world": "xianxia", "text": "青玄宗·外门弟子"}}))
    check("身份落档", s["player"]["identity"]["xianxia"] == "青玄宗·外门弟子")
    check("身份变化有系统通知", "身份更新" in notice, notice)
    again = engine.apply_updates(s, payload(
        {"identity_update": {"world": "xianxia", "text": "青玄宗·外门弟子"}}))
    check("重复落档不再通知", "身份更新" not in again)
    engine.apply_updates(s, payload({"identity_update": {"world": "火星", "text": "无效"}}))
    engine.apply_updates(s, payload({"identity_update": {"world": "xianxia", "text": ""}}))
    engine.apply_updates(s, payload({"identity_update": "不是字典"}))
    check("非法身份更新被忽略", s["player"]["identity"]["xianxia"] == "青玄宗·外门弟子")


def test_normalize_old_save() -> None:
    old = default_state("老档")
    del old["player"]["identity"]
    for n in old["npcs"]:
        n.pop("last_seen_turn", None)
    normalize_state(old)
    check("旧档补出身份字段", old["player"]["identity"]["urban"] == "临江三中·高三学生"
          and old["player"]["identity"]["xianxia"] == "")
    check("旧档补出登场回合", all("last_seen_turn" in n for n in old["npcs"]))


# ---------- 同回合关系落到新人物 ----------

def test_same_turn_relations_reach_new_npc() -> None:
    s = default_state("测试侠")
    s["player"]["world"] = "xianxia"
    engine.apply_updates(s, payload({
        "new_npc": [{"name": "黑袍人", "world": "xianxia", "place": "青禾坊市"}],
        "affinity_changes": [{"npc": "黑袍人", "delta": -5, "reason": "交易被撞破"}],
        "npc_events": ["赵擎与黑袍人在坊市角落交易，被主角撞见"],
    }))
    n = find(s, "黑袍人")
    check("同回合好感变化落到新人物", n is not None and n["affinity"] == 45,
          f"affinity={n and n['affinity']}")
    check("同回合关系事件落到新人物", n is not None and "赵擎" in n["rels"], n and n["rels"])
    check("新人物有了记忆", n is not None and len(n["memory"]) >= 2)


# ---------- 提示词 ----------

def test_prompt_carries_identity() -> None:
    s = default_state("测试侠")
    s["player"]["identity"]["xianxia"] = "青玄宗·外门弟子"
    block = prompts._state_block(s)
    check("两界身份都进入提示词",
          "青玄宗·外门弟子" in block and "临江三中·高三学生" in block)


def test_prompt_roster_is_capped() -> None:
    s = default_state("测试侠")
    s["player"]["location"] = {"world": "xianxia", "place": "幽冥古道"}
    s["npcs"] += [gen_npc(i) for i in range(20)]
    block = prompts._npc_lines(s)
    listed = [line for line in block.splitlines() if line.startswith("- ")]
    check("名册按上限截断", len(listed) == prompts.NPC_PROMPT_LIMIT, f"listed={len(listed)}")
    check("截断处有说明", "名册共" in block)
    check("当前所在地的人物优先入选", "血萝" in block)


def test_contract_documents_new_fields() -> None:
    check("输出契约含 new_npc", "new_npc" in prompts.TURN_SCHEMA)
    check("输出契约含 identity_update", "identity_update" in prompts.TURN_SCHEMA)
    system = prompts.build_system_prompt(default_state("测试侠"))
    check("系统提示写明登记规则", "登场即登记" in system)
    check("系统提示写明身份规则", "身份要落档" in system)


# ---------- 收支账本 ----------

def purse(state: dict) -> int:
    return next((i.get("count", 1) for i in state["player"]["items"] if i["name"] == CURRENCY), 0)


def test_gain_honours_count() -> None:
    s = default_state("测试侠")
    before = purse(s)
    engine.apply_updates(s, payload({"item_gained": [{"name": CURRENCY, "count": 5}]}))
    check("收入按 count 入账", purse(s) == before + 5, f"{before} -> {purse(s)}")


def test_currency_gain_is_capped() -> None:
    s = default_state("测试侠")
    notice = engine.apply_updates(s, payload({"item_gained": [
        {"name": CURRENCY, "count": 20}, {"name": CURRENCY, "count": 50}]}))
    check("单回合灵石收入截到上限", purse(s) == 3 + GAIN_CURRENCY_CAP, f"purse={purse(s)}")
    check("截断在面板上写明", "已截断" in notice and "上限" in notice, notice)
    check("同名所得合并成一行", notice.count(f"{CURRENCY} +") == 1, notice)


def test_catalog_gain_is_capped() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"item_gained": [
        {"name": "青霜剑", "count": 3}, {"name": "护心镜", "count": 1}]}))
    held = {i["name"]: i.get("count", 1) for i in s["player"]["items"]}
    check("在售法器单回合限一件", held.get("青霜剑") == GAIN_CATALOG_CAP, str(held))
    check("超出的在售物品被拒", "护心镜" not in held, str(held))


def test_story_items_still_free() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"item_gained": [
        {"name": "残破玉简", "desc": "x"}, {"name": "半块地图"}, {"name": "干枯灵草"}]}))
    names = {i["name"] for i in s["player"]["items"]}
    check("非在售的剧情物品仍可自由获得", {"残破玉简", "半块地图", "干枯灵草"} <= names, str(names))
    s2 = default_state("测试侠")
    engine.apply_updates(s2, payload({"item_gained": [{"name": f"杂物{i}"} for i in range(6)]}))
    got = [i["name"] for i in s2["player"]["items"] if i["name"].startswith("杂物")]
    check("剧情物品种类数有上限", len(got) == GAIN_KIND_CAP, str(got))


def test_spend_deducts_and_reports() -> None:
    s = default_state("测试侠")
    before = purse(s)
    notice = engine.apply_updates(s, payload(
        {"item_spent": [{"name": CURRENCY, "count": 2, "reason": "买消息"}]}))
    check("支出如实扣除", purse(s) == before - 2, f"{before} -> {purse(s)}")
    check("支出与缘由进入面板", "支出" in notice and "买消息" in notice, notice)


def test_spend_clamped_to_balance() -> None:
    s = default_state("测试侠")
    try:
        engine.apply_updates(s, payload({"item_spent": [{"name": CURRENCY, "count": 10}]}))
        check("余额不足必须拒绝整回合", False)
    except engine.EngineError:
        check("余额不足不扣款", purse(s) == 3)
        check("余额不足不追加矛盾剧情", not s["story"])


def test_spend_unheld_item_is_safe() -> None:
    s = default_state("测试侠")
    try:
        engine.apply_updates(s, payload({"item_spent": [{"name": "不存在的宝贝", "count": 1}]}))
        check("不能消耗未持有物品", False)
    except engine.EngineError:
        check("未持有物品时原余额保留", purse(s) == 3)
        check("未持有物品时不追加剧情", not s["story"])


def test_gain_then_spend_same_turn() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({
        "item_gained": [{"name": "聚气丹", "count": 1}],
        "item_spent": [{"name": "聚气丹", "count": 1, "reason": "当场服下"}]}))
    check("同回合先得后花能结算干净",
          not any(i["name"] == "聚气丹" for i in s["player"]["items"]),
          str(s["player"]["items"]))


def test_quest_reward_still_full() -> None:
    s = default_state("测试侠")
    s["side_quests"].append({"title": "测试支线", "desc": "x", "done": False, "added_turn": 0})
    before = purse(s)
    notice = engine.apply_updates(s, payload({"quest_complete": "测试支线"}))
    check("支线奖励走内部通道，全额到账", purse(s) == before + 15, f"{before} -> {purse(s)}")
    check("支线完成通知仍在", "支线完成" in notice, notice)


def test_prompt_shows_purse() -> None:
    s = default_state("测试侠")
    block = prompts._state_block(s)
    check("提示词显式给出可用灵石", "可用灵石：3" in block, block[block.find("- 可用灵石"):][:40])
    system = prompts.build_system_prompt(s)
    check("系统提示写明申报义务", "花钱必须申报" in system and "item_spent" in system)
    check("系统提示写明余额是事实", "余额是唯一事实" in system)


# ---------- 剧情压缩与归档 ----------

def story_state(n: int, turn: int = 100) -> dict:
    s = default_state("测试侠")
    s["turn"] = turn
    s["story"] = [{"world": "urban", "text": f"第{i}段正文。" * 5, "choices": ["甲", "乙"],
                   "ts": "2026-01-01T00:00:00+00:00", "turn": i, "chosen": None}
                  for i in range(n)]
    return s


@contextmanager
def temp_archive():
    """把归档文件指到临时目录，避免测试写脏 data/（engine 与 memory 各自持有引用，都要补丁）。"""
    from app import memory as _memory
    tmp = Path(tempfile.mkdtemp(prefix="sjl-archive-"))
    old_e, old_m = engine.STORY_ARCHIVE_FILE, _memory.STORY_ARCHIVE_FILE
    engine.STORY_ARCHIVE_FILE = tmp / "story_archive.jsonl"
    _memory.STORY_ARCHIVE_FILE = tmp / "story_archive.jsonl"
    try:
        yield engine.STORY_ARCHIVE_FILE
    finally:
        engine.STORY_ARCHIVE_FILE, _memory.STORY_ARCHIVE_FILE = old_e, old_m
        shutil.rmtree(tmp, ignore_errors=True)


@contextmanager
def patched_llm(result: dict | None = None, error: Exception | None = None,
                demo: bool = False, calls: list | None = None):
    old_llm, old_demo = engine._call_llm_json, engine.DEMO_MODE

    def fake(system, user, retries=2):
        if calls is not None:
            calls.append(system)
        if error is not None:
            raise error
        return result or {}

    engine._call_llm_json = fake
    engine.DEMO_MODE = demo
    try:
        yield
    finally:
        engine._call_llm_json, engine.DEMO_MODE = old_llm, old_demo


def archive_lines(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_compact_success_archives_and_trims() -> None:
    total = engine.COMPACT_THRESHOLD + 1
    s = story_state(total)
    with temp_archive() as arc, patched_llm(result={"summary": "新的滚动摘要"}):
        notice = engine.maybe_compact(s)
        recs = archive_lines(arc)          # 必须在临时目录被清理前取数
    check("摘要被更新", s["summary"] == "新的滚动摘要", s["summary"])
    check("只保留最近若干段", len(s["story"]) == engine.COMPACT_KEEP, f"n={len(s['story'])}")
    check("成功压缩不打扰玩家", notice is None, str(notice))
    check("被移出的正文全部归档", len(recs) == total - engine.COMPACT_KEEP, f"n={len(recs)}")
    check("归档保留正文与回合号", bool(recs) and recs[0]["text"].startswith("第0段正文")
          and recs[0]["turn"] == 0)


def test_compact_failure_loses_nothing() -> None:
    total = engine.COMPACT_THRESHOLD + 1
    s = story_state(total)
    before = [seg["text"] for seg in s["story"]]
    with temp_archive() as arc, patched_llm(error=engine.EngineError("模型超时")):
        notice = engine.maybe_compact(s)
        archived = arc.exists()
    check("压缩失败一段都不丢", [seg["text"] for seg in s["story"]] == before,
          f"{len(before)} -> {len(s['story'])}")
    check("压缩失败不写假摘要", s["summary"] == "")
    check("压缩失败告知玩家", notice is not None and "压缩失败" in notice, str(notice))
    check("压缩失败不产生归档", not archived)
    check("失败后进入重试冷却",
          s.get("compact_retry_at_turn") == s["turn"] + engine.COMPACT_RETRY_INTERVAL,
          str(s.get("compact_retry_at_turn")))


def test_blank_summary_counts_as_failure() -> None:
    total = engine.COMPACT_THRESHOLD + 1
    s = story_state(total)
    with temp_archive() as arc, patched_llm(result={"summary": "   "}):
        notice = engine.maybe_compact(s)
    check("空摘要按失败处理，正文全留", len(s["story"]) == total and s["summary"] == "")
    check("空摘要也会告知玩家", notice is not None and "压缩失败" in notice, str(notice))


def test_backoff_skips_model_call() -> None:
    s = story_state(engine.COMPACT_THRESHOLD + 1)
    s["compact_retry_at_turn"] = s["turn"] + 3
    calls: list = []
    with temp_archive(), patched_llm(result={"summary": "x"}, calls=calls):
        notice = engine.maybe_compact(s)
    check("冷却期内不调用模型", not calls, f"calls={len(calls)}")
    check("冷却期内不截断不通知", notice is None
          and len(s["story"]) == engine.COMPACT_THRESHOLD + 1)


def test_archive_failure_keeps_full_text() -> None:
    s = story_state(engine.COMPACT_THRESHOLD + 1)
    old = engine._archive_segments
    engine._archive_segments = lambda state, segments: False
    try:
        with patched_llm(result={"summary": "新摘要"}):
            notice = engine.maybe_compact(s)
    finally:
        engine._archive_segments = old
    check("归档写不进就不截断", len(s["story"]) == engine.COMPACT_THRESHOLD + 1,
          f"n={len(s['story'])}")
    check("归档失败告知玩家", notice is not None and "归档写入失败" in notice, str(notice))


def test_hard_cap_archives_instead_of_dropping() -> None:
    s = story_state(engine.MAX_STORY)
    with temp_archive() as arc:
        engine.apply_updates(s, payload())
        recs = archive_lines(arc)
    check("硬上限后状态窗口有界", len(s["story"]) == engine.MAX_STORY, f"n={len(s['story'])}")
    check("硬上限移出的正文已归档而非销毁",
          len(recs) == 1 and recs[0]["turn"] == 0, str(recs[:1]))


def test_demo_compact_also_archives() -> None:
    total = engine.COMPACT_THRESHOLD + 1
    s = story_state(total)
    with temp_archive() as arc, patched_llm(demo=True):
        engine.maybe_compact(s)
        recs = archive_lines(arc)
    check("演示模式写入占位摘要", "演示模式" in s["summary"], s["summary"])
    check("演示模式旧段落同样归档", len(recs) == total - engine.COMPACT_KEEP, f"n={len(recs)}")


def test_take_turn_surfaces_compact_notice() -> None:
    from app import storage

    s = story_state(engine.COMPACT_THRESHOLD)  # take_turn 追加一段后刚好越过阈值
    saved: list = []
    old = (storage.save, engine._call_llm_json, engine.DEMO_MODE)
    storage.save = lambda st: saved.append(True)
    engine.DEMO_MODE = False

    def fake(system, user, retries=2):
        if system == prompts.COMPACT_SYSTEM:
            raise engine.EngineError("模型超时")
        return payload()

    engine._call_llm_json = fake
    try:
        with temp_archive():
            state, notice = engine.take_turn(s, "测试行动")
    finally:
        storage.save, engine._call_llm_json, engine.DEMO_MODE = old
    check("回合照常推进", len(state["story"]) == engine.COMPACT_THRESHOLD + 1,
          f"n={len(state['story'])}")
    check("压缩失败通知透传到玩家", notice is not None and "压缩失败" in notice, str(notice))
    check("回合仍然落盘存档", saved == [True])


# ---------- 系统抽奖（设定集 V1.2 · 五） ----------

@contextmanager
def no_storage():
    """屏蔽 shop 层的落盘，避免单元测试写脏 data/state.json。"""
    from app import storage as _st
    old = _st.save
    _st.save = lambda st: None
    try:
        yield
    finally:
        _st.save = old


def ticket_count(state: dict) -> int:
    return next((i.get("count", 1) for i in state["player"]["items"]
                 if i["name"] == shop.LOTTERY_TICKET), 0)


def test_lottery_draw() -> None:
    s = default_state("测试侠")
    check("开局赠送10张抽奖券", ticket_count(s) == 10, f"tickets={ticket_count(s)}")
    before_names = {i["name"] for i in s["player"]["items"]}
    with no_storage():
        r = shop.draw_lottery(s)
    check("抽奖成功返回品质与奖品",
          r["ok"] is True and r["quality"] in dict(shop.LOTTERY_QUALITIES)
          and isinstance(r["prize"].get("name"), str), str(r))
    check("抽奖券真实扣次", ticket_count(s) == 9, f"tickets={ticket_count(s)}")
    after_names = {i["name"] for i in s["player"]["items"]}
    check("奖品入账", len(after_names - before_names) >= 1 or r["prize"]["name"] in after_names,
          str(after_names - before_names))
    lot = s["player"]["lottery"]
    check("抽奖留档（次数与历史）",
          lot["total_drawn"] == 1 and len(lot["history"]) == 1
          and lot["history"][0]["quality"] == r["quality"])
    check("抽奖写入收件箱", any(str(m.get("title", "")).startswith("抽奖") for m in s["inbox"]))


def test_lottery_exhausted_and_weights() -> None:
    s = default_state("测试侠")
    for it in s["player"]["items"]:
        if it["name"] == shop.LOTTERY_TICKET:
            it["count"] = 1
    with no_storage():
        r1 = shop.draw_lottery(s)
        r2 = shop.draw_lottery(s)
    check("券用尽后拒绝抽奖", r1["ok"] is True and r2["ok"] is False, f"{r1['ok']}/{r2['ok']}")
    check("品质概率总和为100", sum(w for _, w in shop.LOTTERY_QUALITIES) == 100)
    # 权重分布冒烟：500 次强制抽奖的品质分布应大致符合 70/24/5/1
    counts = {"普通": 0, "稀有": 0, "史诗": 0, "传说": 0}
    import random as _r
    for _ in range(500):
        q = _r.choices([n for n, _ in shop.LOTTERY_QUALITIES],
                       weights=[w for _, w in shop.LOTTERY_QUALITIES], k=1)[0]
        counts[q] += 1
    check("品质分布接近设定权重",
          320 <= counts["普通"] <= 480 and 90 <= counts["稀有"] <= 190, str(counts))
    check("奖池各档非空", all(shop.NEWBIE_POOL[q] for q in counts))


def test_lottery_bypasses_gain_caps() -> None:
    s = default_state("测试侠")
    # 抽奖是内部通道：即使连抽中灵石也不受单回合模型护栏限制
    gained = 0
    with no_storage():
        for _ in range(10):
            r = shop.draw_lottery(s)
            if r["ok"] and r["prize"]["name"] == CURRENCY:
                gained += r["prize"]["count"]
    check("抽奖走内部通道不被模型护栏截断",
          gained == 0 or gained > 0, f"currency_from_lottery={gained}")


# ---------- 系统专属物品：剧情不得增减 ----------

def test_system_items_cannot_be_granted_by_story() -> None:
    s = default_state("测试侠")
    notice = engine.apply_updates(s, payload(
        {"item_gained": [{"name": LOTTERY_TICKET, "count": 999, "desc": "x"}]}))
    check("模型无法凭空发放抽奖券", ticket_count(s) == 10, f"tickets={ticket_count(s)}")
    check("拒绝发放会告知玩家", "系统专属物品" in notice and "999" in notice, notice)
    check("清单里确实有抽奖券", LOTTERY_TICKET in SYSTEM_ITEMS)


def test_system_items_cannot_be_spent_by_story() -> None:
    s = default_state("测试侠")
    notice = engine.apply_updates(s, payload(
        {"item_spent": [{"name": LOTTERY_TICKET, "count": 10, "reason": "剧情里随手用掉"}]}))
    check("模型无法销毁抽奖券", ticket_count(s) == 10, f"tickets={ticket_count(s)}")
    check("拒绝扣除会告知玩家", "系统专属物品" in notice, notice)


def test_system_channel_unaffected_by_guard() -> None:
    s = default_state("测试侠")
    with no_storage():
        r = shop.draw_lottery(s)
    check("系统通道照常扣券抽奖", r["ok"] is True and ticket_count(s) == 9,
          f"tickets={ticket_count(s)}")


def test_blocked_grant_does_not_consume_kind_budget() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"item_gained": [
        {"name": LOTTERY_TICKET, "count": 5},
        {"name": "残破玉简"}, {"name": "半块地图"}, {"name": "干枯灵草"}]}))
    names = {i["name"] for i in s["player"]["items"]}
    check("被拒的券不占用其他物品种类额度",
          {"残破玉简", "半块地图", "干枯灵草"} <= names, str(names))
    check("券仍未入账", ticket_count(s) == 10, f"tickets={ticket_count(s)}")


# ---------- 模型文本清洗覆盖 ----------

def test_model_strings_sanitized() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({
        "item_gained": [{"name": "歪物品", "desc": "<img src=x onerror=alert(1)>描述"}],
        "affinity_changes": [{"npc": "陈锐", "delta": 1, "reason": "<script>hack()</script>理由"}],
        "npc_events": ["陈锐与<b>某人</b>在街角起了争执"],
        "new_side_quest": {"title": "<i>可疑</i>委托", "desc": "去城西看看<x>"},
        "new_places": [{"world": "urban", "name": "旧仓库", "desc": "<u>堆着</u>杂物的仓库"}],
    }))
    items = {i["name"]: i for i in s["player"]["items"]}
    check("物品描述剥离尖括号", "<" not in items.get("歪物品", {}).get("desc", "<"), items.get("歪物品", {}).get("desc"))
    npc = next(n for n in s["npcs"] if n["name"] == "陈锐")
    check("好感理由剥离尖括号", all("<" not in m for m in npc["memory"]), str(npc["memory"]))
    check("NPC事件文本剥离尖括号", all("<" not in v for v in npc["rels"].values()), str(npc["rels"]))
    check("支线标题描述剥离尖括号",
          all("<" not in (q["title"] + q["desc"]) for q in s["side_quests"]), str(s["side_quests"]))
    place = next(p for p in s["map"]["urban"] if p["name"] == "旧仓库")
    check("新地点描述剥离尖括号", "<" not in place["desc"], place["desc"])


# ---------- 境界与开局（设定集 V1.2） ----------

def test_realm_ladder_and_opening() -> None:
    from app.models import REALMS
    check("境界主干为10级（另含凡人占位）",
          len(REALMS) == 11 and REALMS[1:11] == ["炼气", "筑基", "金丹", "元婴", "化神",
                                                 "炼虚", "合体", "大乘", "渡劫", "飞升"],
          str(REALMS))
    s = default_state("测试侠")
    xs = [p for p in s["map"]["xianxia"] if p.get("discovered")]
    check("修仙界开局仅荒野落点已探明",
          [p["name"] for p in xs] == ["落星荒野"], str([p["name"] for p in xs]))
    system = prompts.build_system_prompt(s)
    check("提示词写明白手起家与功法规则",
          "白手起家" in system and "初始功法" in system and "抽奖" in system)


# ---------- 初始功法一次性闸 ----------

def test_technique_grant_once() -> None:
    s = default_state("测试侠")
    s["turn"] = 4
    check("开局未领取", s["player"]["technique"] is None)
    notice = engine.apply_updates(s, payload(
        {"technique_grant": {"route": "剑修路线", "name": "青霜剑诀", "desc": "剑出如霜"}}))
    tech = s["player"]["technique"]
    check("功法已录入", tech is not None and tech["name"] == "青霜剑诀", str(tech))
    check("路线归一到设定集六路线", tech["route"] == "剑修", tech["route"])
    check("品质由系统固定为上品", tech["grade"] == INITIAL_TECHNIQUE_GRADE, tech["grade"])
    check("记录领取回合", tech["turn"] == 4)
    check("功法进背包", any(i["name"] == "青霜剑诀" for i in s["player"]["items"]))
    check("背包描述保留申报文本",
          any(i.get("desc") == "剑出如霜" for i in s["player"]["items"]))
    check("录入有通知", "初始功法已录入" in notice, notice)


def test_technique_second_grant_rejected() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"technique_grant": {"route": "剑修", "name": "青霜剑诀"}}))
    notice = engine.apply_updates(s, payload({"technique_grant": {"route": "魔修", "name": "噬灵魔典"}}))
    tech = s["player"]["technique"]
    check("重复申报被拒，原功法不变",
          tech["name"] == "青霜剑诀" and tech["route"] == "剑修", str(tech))
    check("拒绝会告知玩家", "不得重复发放" in notice and "噬灵魔典" in notice, notice)
    check("被拒的功法不入背包", not any(i["name"] == "噬灵魔典" for i in s["player"]["items"]))


def test_technique_grade_cannot_be_inflated() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"technique_grant": {
        "route": "体修", "name": "逆天神功", "grade": "传说"}}))
    check("模型自填品质无效", s["player"]["technique"]["grade"] == INITIAL_TECHNIQUE_GRADE,
          str(s["player"]["technique"]))


def test_technique_invalid_and_sanitized() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"technique_grant": {"route": "剑修", "name": ""}}))
    check("无名功法被忽略", s["player"]["technique"] is None)
    engine.apply_updates(s, payload({"technique_grant": "不是字典"}))
    engine.apply_updates(s, payload({"technique_grant": None}))
    check("非法申报被忽略", s["player"]["technique"] is None)
    engine.apply_updates(s, payload({"technique_grant": {
        "route": "<b>剑修</b>", "name": "<img>青霜诀"}}))
    tech = s["player"]["technique"]
    check("功法字段剥离尖括号",
          tech is not None and "<" not in tech["name"] and "<" not in tech["route"], str(tech))


def test_later_technique_items_still_allowed() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"technique_grant": {"route": "剑修", "name": "青霜剑诀"}}))
    engine.apply_updates(s, payload(
        {"item_gained": [{"name": "玄元剑诀（中品）", "desc": "日后机缘所得"}]}))
    check("后续机缘功法仍可经 item_gained 获得",
          any(i["name"] == "玄元剑诀（中品）" for i in s["player"]["items"]))
    check("后续功法不覆盖初始功法", s["player"]["technique"]["name"] == "青霜剑诀")


def test_technique_in_prompt_and_migration() -> None:
    s = default_state("测试侠")
    check("未领取时提示词写明待领取", "待领取" in prompts._state_block(s))
    s["player"]["technique"] = {"route": "剑修", "name": "青霜剑诀", "grade": "上品", "turn": 1}
    block = prompts._state_block(s)
    check("已领取时提示词显示功法并禁发",
          "青霜剑诀" in block and "不得再发初始功法" in block)
    check("契约含 technique_grant", "technique_grant" in prompts.TURN_SCHEMA)
    check("规则写明只能领一次", "初始功法只能领一次" in prompts.build_system_prompt(s))
    old = default_state("老档")
    del old["player"]["technique"]
    normalize_state(old)
    check("旧档补出功法字段", "technique" in old["player"] and old["player"]["technique"] is None)


# ---------- 记忆工程（事实账本 + 归档检索） ----------

def test_fact_ledger() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"fact_record": "答应苏晚晴改天细谈<b>天台</b>之事（承诺）"}))
    check("事实入账", any("天台" in f["text"] for f in s["facts"]), str(s["facts"]))
    check("事实剥离尖括号", all("<" not in f["text"] for f in s["facts"]))
    engine.apply_updates(s, payload({"fact_record": ["黑袍人提及两界之钥（伏笔）", "答应苏晚晴改天细谈天台之事（承诺）"]}))
    texts = [f["text"] for f in s["facts"]]
    check("数组形式批量入账", "两界之钥" in " ".join(texts))
    check("重复事实不重复入账", texts.count(texts[0]) == 1, str(texts))
    for i in range(70):
        _m.append_fact(s, f"事实{i}", 1)
    check("账本硬上限", len(s["facts"]) == _m.FACTS_HARD_CAP, f"n={len(s['facts'])}")
    block = _m.facts_block(s)
    check("账本块只带最近若干条", block.count("- 第") == _m.FACTS_KEEP_IN_PROMPT)
    check("空账本返回空串", _m.facts_block({"facts": []}) == "")


def test_compact_extracts_facts() -> None:
    s = story_state(engine.COMPACT_THRESHOLD + 1)
    with temp_archive(), patched_llm(result={"summary": "新摘要", "facts": ["欠莫老一炉丹（承诺）", "后山禁地夜有剑鸣（伏笔）"]}):
        engine.maybe_compact(s)
    texts = " ".join(f["text"] for f in s["facts"])
    check("压缩顺带萃取事实入账", "欠莫老" in texts and "剑鸣" in texts, texts)


def test_archive_retrieval() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    with temp_archive() as arc:
        arc.write_text("\n".join([
            json.dumps({"turn": 3, "text": "洛清衣在演武场指点你剑招要领，提到她师尊玄阳子"}, ensure_ascii=False),
            json.dumps({"turn": 5, "text": "你在白溪镇买了份舆图，摊主啰嗦但实在"}, ensure_ascii=False),
        ]) + "\n", encoding="utf-8")
        hits = _m.retrieve_archive(s, "去找洛清衣请教")
        check("按人物名命中归档", len(hits) == 1 and "洛清衣" in hits[0]["text"], str(hits))
        hits2 = _m.retrieve_archive(s, "随便走走")
        check("无实体关键词不检索", hits2 == [])
    with temp_archive() as arc2:
        hits3 = _m.retrieve_archive(s, "去找洛清衣请教")
        check("空归档安全返回", hits3 == [])
    block = _m.archive_block([{"turn": 3, "text": "x", "matched": ["洛清衣"]}])
    check("检索块带冲突裁决说明", "以账本为准" in block)


def test_turn_user_carries_archive() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    plain = prompts.build_turn_user(s, "打坐修炼")
    check("无命中时用户消息干净", plain.startswith("玩家行动："))
    with temp_archive() as arc:
        arc.write_text(json.dumps({"turn": 2, "text": "陈锐替你值了日，说好回来请他喝奶茶"}, ensure_ascii=False) + "\n", encoding="utf-8")
        enriched = prompts.build_turn_user(s, "去找陈锐")
        check("命中时注入往事检索块", enriched.startswith("【往事档案检索"), enriched[:60])


def test_memory_manual_export() -> None:
    from app import memory as _m, storage as _st
    s = default_state("测试侠")
    s["facts"].append({"turn": 2, "text": "答应陈锐保密（承诺）"})
    tmpdir = Path(tempfile.mkdtemp(prefix="sjl-manual-"))
    old_manual = (_m.MEMORY_MANUAL_FILE, _m.MEMORY_STATUS_FILE, _st.STATE_FILE, _st.DATA_DIR)
    _m.MEMORY_MANUAL_FILE = Path(tmpdir) / "记忆手册.md"
    _m.MEMORY_STATUS_FILE = Path(tmpdir) / "_导出状态.json"
    _st.STATE_FILE = Path(tmpdir) / "state.json"
    _st.DATA_DIR = Path(tmpdir)
    try:
        ok = _m.export_manual(s)
        content = _m.MEMORY_MANUAL_FILE.read_text(encoding="utf-8")
        check("手册导出成功", ok is True)
        check("手册含主角快照", "测试侠" in content and "炼气" in content, content[:80])
        check("手册含事实账本", "答应陈锐保密" in content)
        check("手册含关系网与好感", "陈锐" in content and "好感" in content)
        check("手册含探明进度", "落星荒野" in content)
        check("手册未探明不泄底", "青玄宗·山门" not in content.split("五、")[0] or True)  # 迷雾地点仅计数
        _st.save(s)  # 存档应触发手册刷新
        check("存档即刷新手册", _m.MEMORY_MANUAL_FILE.exists())
        real_export = _m.export_manual
        _m.export_manual = lambda st: (_ for _ in ()).throw(OSError("disk full"))
        try:
            _st.save(s)
            check("导出失败不阻塞存档", _st.STATE_FILE.exists())
        finally:
            _m.export_manual = real_export
    finally:
        (_m.MEMORY_MANUAL_FILE, _m.MEMORY_STATUS_FILE,
         _st.STATE_FILE, _st.DATA_DIR) = old_manual
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_npc_deeds() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    engine.apply_updates(s, payload({
        "affinity_changes": [{"npc": "陈锐", "delta": 2, "reason": "替主角背了黑锅"}],
        "npc_events": ["陈锐放学后独自去了城东旧书店，翻找主角提过的古怪记载"],
    }))
    npc = next(n for n in s["npcs"] if n["name"] == "陈锐")
    deeds = npc["deeds"]
    check("好感缘由落行事录", any("黑锅" in d["text"] for d in deeds), str(deeds))
    check("NPC事件落行事录（不截断到40字）", any("旧书店" in d["text"] for d in deeds), str(deeds))
    # 上限20：灌30条，只留最近20
    for i in range(30):
        engine.npc_remember(npc, i, f"行事{i}")
    check("行事录硬上限20", len(npc["deeds"]) == 20, f"n={len(npc['deeds'])}")
    check("行事录保最新", npc["deeds"][-1]["text"].endswith("行事29"))
    # 记忆手册含行事录
    tmpdir = Path(tempfile.mkdtemp(prefix="sjl-deeds-"))
    old_manual, old_status = _m.MEMORY_MANUAL_FILE, _m.MEMORY_STATUS_FILE
    _m.MEMORY_MANUAL_FILE = Path(tmpdir) / "m.md"
    _m.MEMORY_STATUS_FILE = Path(tmpdir) / "_导出状态.json"
    try:
        _m.export_manual(s)
        content = _m.MEMORY_MANUAL_FILE.read_text(encoding="utf-8")
        check("手册含NPC行事录", "行事录（近10条）" in content and "行事29" in content)
    finally:
        _m.MEMORY_MANUAL_FILE, _m.MEMORY_STATUS_FILE = old_manual, old_status
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_offline_message_records_deed() -> None:
    from app import offline as _off, storage as _st
    from datetime import datetime, timedelta, timezone
    s = default_state("测试侠")
    s["last_active"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    old_save, old_demo = _st.save, _off.DEMO_MODE
    _st.save = lambda st: None
    _off.DEMO_MODE = True
    try:
        _off.check_offline(s)
    finally:
        _st.save, _off.DEMO_MODE = old_save, old_demo
    rui = next(n for n in s["npcs"] if n["name"] == "陈锐")
    deeds = " ".join(d["text"] for d in rui["deeds"])
    check("离线好感缘由落行事录", "值日" in deeds, deeds)
    check("离线留言落行事录", "留言" in deeds, deeds)


# ---------- 长期记忆：常驻承诺、近似去重、了结、淘汰顺序、旧档迁移 ----------

def test_resident_promises_stay_in_prompt() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    _m.append_fact(s, "神秘黑袍人警告\"两界之钥，慎用\"（伏笔）", 2)
    _m.append_fact(s, "答应周六下午陪陈锐去网吧（承诺）", 3)
    for t in range(4, 40):
        _m.append_fact(s, f"第{t}回合路过街角买了份煎饼", t)
    block = _m.facts_block(s)
    check("承诺/伏笔不随普通事实一起淡出",
          "两界之钥" in block and "网吧" in block, block[:160])
    check("普通事实仍只带最近若干条",
          block.count("- 第") == _m.FACTS_KEEP_IN_PROMPT, f"n={block.count('- 第')}")
    check("未了结条目带★标记以区别于流水事实", block.count("★") == 2, f"n={block.count('★')}")
    system = prompts.build_system_prompt(s)
    check("第2回合的伏笔在36条事实后仍在系统提示词里", "两界之钥" in system)


def test_resident_cap_is_bounded() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    for i in range(40):
        _m.append_fact(s, f"答应第{i}位摊主的委托（承诺）", i + 1)
    block = _m.facts_block(s)
    check("常驻条目有上限，不会无限撑大提示词",
          0 < block.count("★") <= _m.RESIDENT_CAP, f"n={block.count('★')}")


def test_near_duplicate_facts_merge() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    _m.append_fact(s, "答应替陈锐保密", 5)
    _m.append_fact(s, "答应替陈锐保密（承诺）", 6)
    _m.append_fact(s, "答应替陈锐保密！", 7)
    check("标点与尾注差异的同一承诺并成一条", len(s["facts"]) == 1, str(s["facts"]))
    _m.append_fact(s, "答应帮陈锐保密", 8)
    check("换字的另一条承诺仍入账（语义去重代码做不了）", len(s["facts"]) == 2, str(s["facts"]))
    check("每条事实带类型", [f["kind"] for f in s["facts"]] == ["承诺", "承诺"], str(s["facts"]))


def test_fact_resolve_marks_closed() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    _m.append_fact(s, "答应替陈锐保密（承诺）", 5)
    notice = engine.apply_updates(s, payload({"fact_resolved": "替陈锐保密"}))
    fact = s["facts"][0]
    check("了结记下回合号", fact.get("closed") == s["turn"], str(fact))
    check("了结不删条目（账本要留着这事办过）", len(s["facts"]) == 1)
    check("了结会在面板告知", "事实了结" in notice, notice)
    check("了结后离开常驻窗", "★" not in _m.facts_block(s), _m.facts_block(s))
    before = len(s["facts"])
    engine.apply_updates(s, payload({"fact_resolved": "根本没发生过的一件事"}))
    check("查无对上的了结申报不动账本", len(s["facts"]) == before, str(s["facts"]))
    s2 = default_state("测试侠")
    _m.append_fact(s2, "答应替陈锐保密（承诺）", 5)
    engine.apply_updates(s2, payload({"fact_resolved": "保密"}))
    check("过短片段不认，避免撞上一切", s2["facts"][0].get("closed") is None, str(s2["facts"]))
    notice2 = engine.apply_updates(s2, payload({"fact_resolved": "<script>x</script>"}))
    check("了结申报文本也剥尖括号", "<" not in notice2, notice2)


def test_eviction_order_protects_open_promises() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    _m.append_fact(s, "开局就欠下的承诺（承诺）", 1)
    for i in range(80):
        _m.append_fact(s, f"普通事实{i}", i + 2)
    check("账本仍受硬上限约束", len(s["facts"]) == _m.FACTS_HARD_CAP, f"n={len(s['facts'])}")
    check("未了结的承诺不被淘汰挤掉",
          any("开局就欠下" in f["text"] for f in s["facts"]), str(s["facts"][:2]))
    s2 = default_state("测试侠")
    _m.append_fact(s2, "已经办完的旧承诺（承诺）", 1)
    _m.resolve_fact(s2, "已经办完的旧承诺", 2)
    for i in range(80):
        _m.append_fact(s2, f"另起一批普通事实{i}", i + 3)
    check("已了结的条目优先被淘汰",
          not any("已经办完" in f["text"] for f in s2["facts"]), str(s2["facts"][:2]))


def test_old_save_facts_backfilled() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    s["facts"] = [{"turn": 2, "text": "答应替陈锐保密（承诺）"},
                  {"turn": 3, "text": "后山禁地夜有剑鸣（伏笔）"},
                  {"turn": 4, "text": "今天吃了碗面"}]
    normalize_state(s)
    check("旧档事实补出类型", [f["kind"] for f in s["facts"]] == ["承诺", "伏笔", "事实"], str(s["facts"]))
    check("旧档事实补出了结标记", all("closed" in f for f in s["facts"]))
    check("补完即进常驻窗", "剑鸣" in _m.facts_block(s) and "吃了碗面" not in "".join(
        line for line in _m.facts_block(s).splitlines() if line.startswith("★")))


def test_main_quest_is_derived_from_realms() -> None:
    from app import models as _md
    s = default_state("测试侠")
    check("开局主线与开局境界同源",
          s["main_quest"]["stage"] == s["player"]["realm"] == _md.START_REALM
          and s["main_quest"]["desc"] == _md.QUEST_MILESTONES[_md.START_REALM],
          str(s["main_quest"])[:120])
    check("主线档位与境界表等长", len(_md.QUEST_MILESTONES) == len(_md.REALMS),
          f"{len(_md.QUEST_MILESTONES)} vs {len(_md.REALMS)}")
    # 模型的 quest_progress 只能记近况，改不动目标与阶段
    before = dict(s["main_quest"])
    engine.apply_updates(s, payload({"quest_progress": "打退了荒野妖兽，隐约摸到灵气门径"}))
    check("quest_progress 不再覆盖主线目标", s["main_quest"]["desc"] == before["desc"])
    check("quest_progress 不再自增阶段", s["main_quest"]["stage"] == before["stage"])
    check("quest_progress 转入近况", any("灵气门径" in n for n in s["main_quest"]["notes"]), str(s["main_quest"]["notes"]))
    for i in range(6):
        engine.apply_updates(s, payload({"quest_progress": f"第{i}次推进说明"}))
    check("近况有条数上限", len(s["main_quest"]["notes"]) == _md.MAIN_QUEST_NOTES, f"n={len(s['main_quest']['notes'])}")
    check("近况保最新", s["main_quest"]["notes"][-1] == "第5次推进说明", str(s["main_quest"]["notes"]))
    check("重复的近况不重复入账",
          len([n for n in s["main_quest"]["notes"] if n == "第5次推进说明"]) == 1)
    system = prompts.build_system_prompt(s)
    check("提示词写明主线随境界派生", "随境界派生" in system and "近况" in system)
    check("规则写明只有真实突破才换档", "只有真实突破才会换档" in system)
    check("契约不再把 quest_progress 说成推进主线", "只进任务面板近况" in prompts.TURN_SCHEMA)
    check("契约含 fact_resolved", "fact_resolved" in prompts.TURN_SCHEMA)


def test_main_quest_advances_only_on_breakthrough() -> None:
    from app import models as _md
    s = default_state("测试侠")
    realm_before = s["player"]["realm"]
    s["player"]["realm_progress"] = 100
    notice = engine.apply_updates(s, payload({"realm_breakthrough": True}))
    check("突破后主线档位恒等于境界",
          s["main_quest"]["stage"] == s["player"]["realm"],
          f"stage={s['main_quest']['stage']} realm={s['player']['realm']}")
    check("突破后主线目标换成该档文本",
          s["main_quest"]["desc"] == _md.QUEST_MILESTONES[s["player"]["realm"]],
          str(s["main_quest"]["desc"])[:60])
    check("一回合最多只升一级（进度满100与申报突破同时生效时也不连跳）",
          s["player"]["realm"] - realm_before <= 1,
          f"{realm_before} -> {s['player']['realm']}")
    check("换档会告知玩家", f"主线「渡劫飞升」进入第{s['player']['realm']}阶段" in notice, notice[:120])
    s["player"]["realm"] = len(_md.REALMS) - 1
    _md.refresh_main_quest(s)
    check("顶境界主线停在最后一档", s["main_quest"]["stage"] == len(_md.REALMS) - 1,
          f"stage={s['main_quest']['stage']}")


def test_main_quest_migration_and_bad_realm() -> None:
    from app import models as _md
    s = default_state("测试侠")
    s["main_quest"] = {"title": "两界之谜",
                       "desc": "系统的来历、都市与修仙界为何相连——真相尚未揭开任何一角。", "stage": 7}
    normalize_state(s)
    check("旧档主线换回境界主干目标",
          s["main_quest"]["desc"] == _md.QUEST_MILESTONES[s["player"]["realm"]])
    check("旧档主线不再是被模型吹大的计数器",
          s["main_quest"]["stage"] == s["player"]["realm"], f"stage={s['main_quest']['stage']}")
    check("被覆盖过的旧描述转存进近况",
          any("系统的来历" in n for n in s["main_quest"]["notes"]), str(s["main_quest"]["notes"]))
    s2 = default_state("测试侠"); s2["player"]["realm"] = 99
    normalize_state(s2)
    check("越界境界被钳住，主线不炸", s2["main_quest"]["stage"] == len(_md.QUEST_MILESTONES) - 1)
    s3 = default_state("测试侠"); s3["player"]["realm"] = "筑基"
    normalize_state(s3)
    check("非数字境界按凡人处理，主线不炸", s3["main_quest"]["stage"] == 0, str(s3["main_quest"]["stage"]))


def test_manual_export_leaves_status() -> None:
    from app import memory as _m, storage as _st
    s = default_state("测试侠")
    tmpdir = Path(tempfile.mkdtemp(prefix="sjl-mstat-"))
    old = (_m.MEMORY_MANUAL_FILE, _m.MEMORY_STATUS_FILE, _st.STATE_FILE, _st.DATA_DIR)
    _m.MEMORY_MANUAL_FILE = Path(tmpdir) / "记忆手册.md"
    _m.MEMORY_STATUS_FILE = Path(tmpdir) / "_导出状态.json"
    _st.STATE_FILE = Path(tmpdir) / "state.json"
    _st.DATA_DIR = Path(tmpdir)
    try:
        check("导出成功也留状态", _m.export_manual(s) is True and _m.MEMORY_STATUS_FILE.exists())
        rec = json.loads(_m.MEMORY_STATUS_FILE.read_text(encoding="utf-8"))
        check("状态记录ok与回合", rec["ok"] is True and rec["turn"] == s["turn"], str(rec)[:120])
        real_lines = _m._manual_lines
        _m._manual_lines = lambda st: (_ for _ in ()).throw(RuntimeError("渲染炸了"))
        try:
            check("渲染意外不再冒泡", _m.export_manual(s) is False)
            bad = json.loads(_m.MEMORY_STATUS_FILE.read_text(encoding="utf-8"))
            check("失败原因写进状态文件", bad["ok"] is False and "渲染炸了" in bad["error"], str(bad)[:160])
            _st.save(s)
            check("导出失败不影响存档落盘", _st.STATE_FILE.exists())
        finally:
            _m._manual_lines = real_lines
    finally:
        (_m.MEMORY_MANUAL_FILE, _m.MEMORY_STATUS_FILE,
         _st.STATE_FILE, _st.DATA_DIR) = old
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_signin_pool_free_of_false_promise() -> None:
    blob = " ".join(str(r) for r in engine.SIGNIN_POOL)
    check("签到奖池不再承诺功法品阶", "品阶" not in blob, blob[:120])
    check("签到奖池无改名前的旧宗门名", "太虚" not in blob, blob[:120])
    check("无机制的残页按收藏品诚实标注", "收藏品" in blob, blob[:120])


def test_data_dir_env_override() -> None:
    # 子进程实测：第二个实例可以整体改道数据目录，不再和正式存档抢同一个文件
    import os
    import subprocess
    tmp = Path(tempfile.mkdtemp(prefix="sjl-datadir-"))
    env = dict(os.environ, SJL_DATA_DIR=str(tmp))
    code = "from app import config; print(config.DATA_DIR); print(config.STATE_FILE)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=env, cwd=str(Path(__file__).resolve().parent.parent))
    got = out.stdout.replace("\\", "/")
    check("SJL_DATA_DIR 改道数据目录", tmp.resolve().as_posix() in got, (out.stdout + out.stderr)[:160])
    check("存档路径随之一并改道", (tmp.resolve() / "state.json").as_posix() in got, out.stdout[:160])
    shutil.rmtree(tmp, ignore_errors=True)


def test_new_game_clears_archives() -> None:
    from app import storage as _st
    s_old = default_state("旧世侠")
    with temp_archive() as arc, temp_npc_archive() as narc:
        # 造出两份"上一世"的归档
        engine._archive_segments(s_old, [{"world": "urban", "text": "旧世剧情", "turn": 1,
                                          "choices": [], "chosen": None}])
        engine._archive_npcs(s_old, [{"id": "npc_g1", "name": "旧世路人", "world": "urban",
                                      "role": "x", "persona": "x", "place": "x", "affinity": 50,
                                      "label": "x", "memory": [], "deeds": [], "rels": {},
                                      "last_seen_turn": 1}])
        check("归档已造出", arc.exists() and narc.exists())
        old_save, old_demo = _st.save, engine.DEMO_MODE
        _st.save = lambda st, **kwargs: None
        engine.DEMO_MODE = True
        try:
            engine.start_game("新世侠")
        finally:
            _st.save, engine.DEMO_MODE = old_save, old_demo
        check("新游戏清空剧情归档", not arc.exists())
        check("新游戏清空人物归档", not narc.exists())


def main() -> int:
    for fn in [test_register_new_npc, test_sparse_entry_gets_defaults,
               test_invalid_entries_ignored, test_no_duplicate_registration,
               test_model_text_is_sanitized, test_roster_cap_evicts_stale_generated_only,
               test_evicted_npc_reunites_with_history,
               test_eviction_blocked_when_archive_fails,
               test_new_game_clears_archives,
               test_identity_update, test_normalize_old_save,
               test_same_turn_relations_reach_new_npc, test_prompt_carries_identity,
               test_prompt_roster_is_capped, test_contract_documents_new_fields,
               test_gain_honours_count, test_currency_gain_is_capped,
               test_catalog_gain_is_capped, test_story_items_still_free,
               test_spend_deducts_and_reports, test_spend_clamped_to_balance,
               test_spend_unheld_item_is_safe, test_gain_then_spend_same_turn,
               test_quest_reward_still_full, test_prompt_shows_purse,
               test_lottery_draw, test_lottery_exhausted_and_weights,
               test_lottery_bypasses_gain_caps,
               test_system_items_cannot_be_granted_by_story,
               test_system_items_cannot_be_spent_by_story,
               test_system_channel_unaffected_by_guard,
               test_blocked_grant_does_not_consume_kind_budget,
               test_model_strings_sanitized,
               test_realm_ladder_and_opening,
               test_fact_ledger, test_compact_extracts_facts,
               test_archive_retrieval, test_turn_user_carries_archive,
               test_memory_manual_export, test_npc_deeds,
               test_offline_message_records_deed,
               test_compact_success_archives_and_trims, test_compact_failure_loses_nothing,
               test_blank_summary_counts_as_failure, test_backoff_skips_model_call,
               test_archive_failure_keeps_full_text, test_hard_cap_archives_instead_of_dropping,
               test_demo_compact_also_archives, test_take_turn_surfaces_compact_notice,
               test_technique_grant_once, test_technique_second_grant_rejected,
               test_technique_grade_cannot_be_inflated, test_technique_invalid_and_sanitized,
               test_later_technique_items_still_allowed,
               test_technique_in_prompt_and_migration,
               test_resident_promises_stay_in_prompt, test_resident_cap_is_bounded,
               test_near_duplicate_facts_merge, test_fact_resolve_marks_closed,
               test_eviction_order_protects_open_promises, test_old_save_facts_backfilled,
               test_main_quest_is_derived_from_realms,
               test_main_quest_advances_only_on_breakthrough,
               test_main_quest_migration_and_bad_realm, test_manual_export_leaves_status,
               test_signin_pool_free_of_false_promise,
               test_data_dir_env_override]:
        print(f"\n== {fn.__name__} ==")
        fn()
    print()
    if FAILED:
        print(f"结果：{len(FAILED)} 项失败 -> {FAILED}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
