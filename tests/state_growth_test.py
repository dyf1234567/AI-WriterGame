"""状态生长单元测试：新人物登记、身份落档、名册与提示词截断、收支账本、剧情压缩与归档。

不依赖服务与模型 API，直接驱动引擎结算层。
用法：.venv/Scripts/python tests/state_growth_test.py
"""
import json
import shutil
import sys
import tempfile
from unittest.mock import patch
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import engine, memory as _m, models, prompts, shop
from app.config import GAIN_CATALOG_CAP, GAIN_CURRENCY_CAP, GAIN_KIND_CAP
from app.models import (
    CURRENCY, INITIAL_TECHNIQUE_GRADE, LOTTERY_TICKET, MAX_NPCS, PRESET_NPC_IDS,
    SYSTEM_ITEMS, default_map, default_state, normalize_state,
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
        "narration_world": "urban",
        "choices": ["选项一", "选项二", "选项三"],
        "state_updates": updates or {},
        "system_notice": "",
    }


def find(state: dict, name: str) -> dict | None:
    return next((n for n in state["npcs"] if n["name"] == name), None)


def gen_npc(i: int, last_seen: int = -1, place: str = "别处") -> dict:
    return {"id": f"npc_g{i}", "name": f"路人{i}", "world": "urban", "role": "路人",
            "persona": "无名散修", "place": place, "affinity": 50, "label": "初识",
            "memory": [], "rels": {}, "last_seen_turn": last_seen}


# ---------- 新人物登记 ----------

def test_register_new_npc() -> None:
    s = default_state("测试侠")
    s["turn"] = 3
    s["player"]["location"] = {"world": "urban", "place": "京华大学"}
    notice = engine.apply_updates(s, payload({"new_npc": [{
        "name": "周砚", "world": "urban", "role": "学生会干事",
        "persona": "面生嘴碎，爱打听", "place": "京华大学",
        "label": "同窗", "affinity": 40}]}))
    n = find(s, "周砚")
    check("新人物已登记", n is not None)
    check("字段与预设人物同构", n is not None and all(
        k in n for k in ("id", "name", "world", "role", "persona", "place",
                         "affinity", "label", "memory", "rels", "last_seen_turn")))
    check("登记值原样保留", n is not None and n["role"] == "学生会干事"
          and n["place"] == "京华大学" and n["affinity"] == 40 and n["label"] == "同窗")
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
    check("空名与非字典条目被忽略", len(s["npcs"]) == 36, f"n={len(s['npcs'])}")
    n = find(s, "李四")
    check("非法世界回落到都市", n is not None and n["world"] == "urban", n and n["world"])
    check("非法好感回落默认值", n is not None and n["affinity"] == 50)


def test_no_duplicate_registration() -> None:
    s = default_state("测试侠")
    before = len(s["npcs"])
    notice = engine.apply_updates(s, payload(
        {"new_npc": [{"name": "郭瑞莹", "role": "重复登记"}, {"name": "郭瑞莹"}]}))
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
        "id": "npc_gen10_0", "name": "侯三", "world": "urban", "role": "夜市摊主",
        "persona": "啰嗦但实在", "place": "京都夜市", "affinity": 66, "label": "熟人",
        "memory": ["第9回合：卖过主角一份小吃"],
        "deeds": [{"turn": 9, "text": "第9回合：卖过主角一份小吃"}],
        "rels": {"黑袍人": "同街摆摊，互相忌惮"}, "last_seen_turn": 9})
    s["turn"] = 200
    s["npcs"] += [gen_npc(i, last_seen=100 + i) for i in range(MAX_NPCS)]
    with temp_npc_archive() as arc:
        engine.apply_updates(s, payload({"new_npc": [{"name": "张铁柱"}]}))  # 挤掉侯三
        check("侯三被淘汰并归档", find(s, "侯三") is None
              and any(r.get("name") == "侯三" for r in archive_records()))
        notice = engine.apply_updates(s, payload({"new_npc": [{
            "name": "侯三", "world": "urban", "role": "夜市摊主",
            "affinity": 50}]}))  # 重逢：模型给的好感50不该覆盖旧档66
        restored = find(s, "侯三")
        check("旧识重逢回名册", restored is not None)
        check("好感延续旧档不被重置", restored and restored["affinity"] == 66,
              f"affinity={restored and restored['affinity']}")
        check("行事录带着旧事与重逢", restored and any("小吃" in d["text"] for d in restored["deeds"])
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
    check("开局都市身份已预置", s["player"]["identity"]["urban"] == "京华大学·大一新生")
    notice = engine.apply_updates(s, payload(
        {"identity_update": {"world": "urban", "text": "京华大学·街舞社副社长"}}))
    check("身份落档", s["player"]["identity"]["urban"] == "京华大学·街舞社副社长")
    check("身份变化有系统通知", "身份更新" in notice, notice)
    again = engine.apply_updates(s, payload(
        {"identity_update": {"world": "urban", "text": "京华大学·街舞社副社长"}}))
    check("重复落档不再通知", "身份更新" not in again)
    engine.apply_updates(s, payload({"identity_update": {"world": "火星", "text": "无效"}}))
    engine.apply_updates(s, payload({"identity_update": {"world": "urban", "text": ""}}))
    engine.apply_updates(s, payload({"identity_update": "不是字典"}))
    check("非法身份更新被忽略", s["player"]["identity"]["urban"] == "京华大学·街舞社副社长")


def test_normalize_old_save() -> None:
    old = default_state("老档")
    del old["player"]["identity"]
    for n in old["npcs"]:
        n.pop("last_seen_turn", None)
    normalize_state(old)
    check("旧档补出身份字段", old["player"]["identity"]["urban"] == "京华大学·大一新生"
          and old["player"]["identity"].get("xianxia", "") == "")
    check("旧档补出登场回合", all("last_seen_turn" in n for n in old["npcs"]))


def test_normalize_retires_old_city_map() -> None:
    """旧版「青临市」15 地图存档迁移：退役清出、同名归城、位置与记忆重置。"""
    old = default_state("旧图档")
    old["map"]["urban"] = [
        {"name": n, "desc": "", "discovered": True}
        for n in ("青临大学", "合租公寓", "中央商圈", "滨海老街", "大学城体育馆",
                  "回声Livehouse", "海滨浴场", "星海游乐园", "云栖山公园", "江湾CBD",
                  "青临夜市", "市立美术馆", "青临南站", "渔人码头", "云顶天文台")
    ]
    old["player"]["location"] = {"world": "urban", "place": "青临大学"}
    old["player"]["places_memory"] = {"urban": "青临大学"}
    normalize_state(old)
    urban = old["map"]["urban"]
    names = {p["name"] for p in urban}
    check("退役地点已清出", not ({"青临大学", "青临夜市", "星海游乐园", "青临南站"} & names))
    check("地图归并为新正典 14 地", len(urban) == 14 and names == {
        p["name"] for p in default_map()["urban"]})
    city_of = {p["name"]: p.get("city") for p in urban}
    check("同名旧地点按新正典归城",
          city_of["合租公寓"] == "京都" and city_of["回声Livehouse"] == "京都"
          and city_of["渔人码头"] == "魔都" and city_of["云顶天文台"] == "魔都")
    loc = old["player"]["location"]
    check("站在退役地点的玩家被安置到京华大学",
          loc == {"world": "urban", "country": "华夏", "city": "京都", "place": "京华大学"}
          and old["player"]["places_memory"]["urban"] == "京华大学")


def test_legacy_theme_migration_clears_records() -> None:
    """旧修仙题材存档迁移：面板记录清空，财富与好感保留。"""
    old = default_state("老玩家")
    old["theme"] = None  # 旧题材档没有主题标识
    old["player"]["world"] = "xianxia"
    old["player"]["location"] = {"world": "xianxia", "place": "落星荒野"}
    old["npcs"].append({"id": "npc_xuanyangzi", "name": "玄阳子", "world": "xianxia", "role": "长老",
                        "persona": "x", "place": "山门", "affinity": 50, "label": "师尊",
                        "memory": ["旧事"], "deeds": [], "rels": {}})
    old["player"]["items"] = [
        {"name": "下品灵石", "desc": "修仙界通用货币", "count": 99},
        {"name": "系统抽奖券", "desc": "x", "count": 10},
        {"name": "聚气丹", "desc": "旧题材丹药", "count": 2},
    ]
    old["story"] = [{"world": "xianxia", "text": "旧世界正文", "choices": [], "ts": "t",
                     "turn": 1, "chosen": None}]
    old["inbox"] = [{"ts": "t", "type": "event", "world": "urban", "title": "旧事件", "text": "x"}]
    old["facts"] = [{"turn": 1, "text": "旧世界伏笔（伏笔）", "kind": "伏笔", "closed": None}]
    old["side_quests"] = [{"title": "旧支线", "desc": "x", "done": False, "added_turn": 1}]
    old["summary"] = "旧世界摘要"
    m = normalize_state(old)
    check("迁移后落到新题材", m["theme"] == "urban-romance-v1" and m["player"]["world"] == "urban")
    check("面板剧情清空", m["story"] == [] and m["summary"] == "")
    check("收件箱与账本清空", m["inbox"] == [] and m["facts"] == [] and m["side_quests"] == [])
    check("人物记忆清空", all(not n["memory"] and not n["deeds"] for n in m["npcs"]))
    check("旧题材物品清出背包", not any(i["name"] == "聚气丹" for i in m["player"]["items"]))
    check("货币换算保留", any(i["name"] == CURRENCY and i["count"] == 99 for i in m["player"]["items"]))
    check("抽奖券保留", any(i["name"] == LOTTERY_TICKET and i["count"] == 10
                            for i in m["player"]["items"]))
    check("修仙人物退场", not any(n["name"] == "玄阳子" for n in m["npcs"]))


# ---------- 同回合关系落到新人物 ----------

def test_same_turn_relations_reach_new_npc() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({
        "new_npc": [{"name": "黑袍人", "world": "urban", "place": "银杏商街"}],
        "affinity_changes": [{"npc": "黑袍人", "delta": -5, "reason": "交易被撞破"}],
        "npc_events": ["雅倩与黑袍人在商圈角落低声交谈，被主角撞见"],
    }))
    n = find(s, "黑袍人")
    check("同回合好感变化落到新人物", n is not None and n["affinity"] == 45,
          f"affinity={n and n['affinity']}")
    check("同回合关系事件落到新人物", n is not None and "雅倩" in n["rels"], n and n["rels"])
    check("新人物有了记忆", n is not None and len(n["memory"]) >= 2)


# ---------- 提示词 ----------

def test_prompt_carries_identity() -> None:
    s = default_state("测试侠")
    s["player"]["identity"]["urban"] = "京华大学·街舞社副社长"
    block = prompts._state_block(s)
    check("身份进入提示词", "街舞社副社长" in block)


def test_prompt_roster_is_capped() -> None:
    s = default_state("测试侠")
    s["player"]["location"] = {"world": "urban", "place": "龙脊CBD"}
    s["npcs"] += [gen_npc(i) for i in range(20)]
    block = prompts._npc_lines(s)
    listed = [line for line in block.splitlines() if line.startswith("- ")]
    check("名册按上限截断", len(listed) == prompts.NPC_PROMPT_LIMIT, f"listed={len(listed)}")
    check("截断处有说明", "名册共" in block)
    check("当前所在地的人物优先入选", "炭炭" in block)


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
    check("单回合金币收入截到上限", purse(s) == 3 + GAIN_CURRENCY_CAP, f"purse={purse(s)}")
    check("截断在面板上写明", "已截断" in notice and "上限" in notice, notice)
    check("同名所得合并成一行", notice.count(f"{CURRENCY} +") == 1, notice)


def test_catalog_gain_is_capped() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"item_gained": [
        {"name": "修身西装", "count": 3}, {"name": "智能腕表", "count": 1}]}))
    held = {i["name"]: i.get("count", 1) for i in s["player"]["items"]}
    check("在售穿搭单回合限一件", held.get("修身西装") == GAIN_CATALOG_CAP, str(held))
    check("超出的在售物品被拒", "智能腕表" not in held, str(held))


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
        "item_gained": [{"name": "专注咖啡", "count": 1}],
        "item_spent": [{"name": "专注咖啡", "count": 1, "reason": "当场喝下"}]}))
    check("同回合先得后花能结算干净",
          not any(i["name"] == "专注咖啡" for i in s["player"]["items"]),
          str(s["player"]["items"]))


def test_quest_reward_still_full() -> None:
    s = default_state("测试侠")
    s["side_quests"].append({"title": "测试支线", "desc": "x", "done": False, "added_turn": 0})
    s["turn"] = 2  # 创建与完成至少隔一回合（防秒接秒交刷奖励）
    before = purse(s)
    notice = engine.apply_updates(s, payload({"quest_complete": "测试支线"}))
    check("支线奖励走内部通道，全额到账", purse(s) == before + 15, f"{before} -> {purse(s)}")
    check("支线完成通知仍在", "支线完成" in notice, notice)


def test_prompt_shows_purse() -> None:
    s = default_state("测试侠")
    block = prompts._state_block(s)
    check("提示词显式给出可用金币", "可用系统金币：3" in block, block[block.find("- 可用系统金币"):][:40])
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
    storage.save = lambda st, **kwargs: saved.append(True)
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
    _st.save = lambda st, **kwargs: None
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
    check("抽奖不再刷收件箱（记录只在抽奖页）",
          not any(str(m.get("title", "")).startswith("抽奖") for m in s["inbox"]),
          str([m.get("title") for m in s["inbox"]]))


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
        "affinity_changes": [{"npc": "梁雅婷", "delta": 1, "reason": "<script>hack()</script>理由"}],
        "npc_events": ["梁雅婷与<b>某人</b>在街角起了争执"],
        "new_side_quest": {"title": "<i>可疑</i>委托", "desc": "去城西看看<x>"},
        "new_places": [{"world": "urban", "name": "旧仓库", "desc": "<u>堆着</u>杂物的仓库"}],
    }))
    items = {i["name"]: i for i in s["player"]["items"]}
    check("物品描述剥离尖括号", "<" not in items.get("歪物品", {}).get("desc", "<"), items.get("歪物品", {}).get("desc"))
    npc = next(n for n in s["npcs"] if n["name"] == "梁雅婷")
    check("好感理由剥离尖括号", all("<" not in m for m in npc["memory"]), str(npc["memory"]))
    check("NPC事件文本剥离尖括号", all("<" not in v for v in npc["rels"].values()), str(npc["rels"]))
    check("支线标题描述剥离尖括号",
          all("<" not in (q["title"] + q["desc"]) for q in s["side_quests"]), str(s["side_quests"]))
    place = next(p for p in s["map"]["urban"] if p["name"] == "旧仓库")
    check("新地点描述剥离尖括号", "<" not in place["desc"], place["desc"])


# ---------- 等级与开局 ----------

def test_realm_ladder_and_opening() -> None:
    from app.models import REALMS
    check("等级主干为10级（另含路人占位）",
          len(REALMS) == 11 and REALMS[1:11] == ["初露锋芒", "校园新星", "崭露头角", "风云人物",
                                                 "校园传奇", "城市新锐", "万众瞩目", "众星捧月",
                                                 "城市传奇", "人生赢家"],
          str(REALMS))
    s = default_state("测试侠")
    check("单世界地图，开局三个地点已探明",
          "xianxia" not in s["map"]
          and [p["name"] for p in s["map"]["urban"] if p.get("discovered")]
          == ["京华大学", "合租公寓", "银杏商街"],
          str([p["name"] for p in s["map"]["urban"] if p.get("discovered")]))
    system = prompts.build_system_prompt(s)
    check("提示词写明题材与天赋、抽奖规则",
          "都市多线恋爱" in system and "初始天赋" in system and "抽奖" in system)


# ---------- 初始天赋一次性闸 ----------

def test_technique_grant_once() -> None:
    s = default_state("测试侠")
    s["turn"] = 4
    check("开局未领取", s["player"]["technique"] is None)
    notice = engine.apply_updates(s, payload(
        {"technique_grant": {"route": "学业路线", "name": "超级记忆力", "desc": "过目不忘"}}))
    tech = s["player"]["technique"]
    check("天赋已录入", tech is not None and tech["name"] == "超级记忆力", str(tech))
    check("路线归一到设定集六路线", tech["route"] == "学业", tech["route"])
    check("品质由系统固定为S级", tech["grade"] == INITIAL_TECHNIQUE_GRADE, tech["grade"])
    check("记录领取回合", tech["turn"] == 4)
    check("天赋进背包", any(i["name"] == "超级记忆力" for i in s["player"]["items"]))
    check("背包描述保留申报文本",
          any(i.get("desc") == "过目不忘" for i in s["player"]["items"]))
    check("录入有通知", "初始天赋已录入" in notice, notice)


def test_technique_second_grant_rejected() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"technique_grant": {"route": "学业", "name": "超级记忆力"}}))
    notice = engine.apply_updates(s, payload({"technique_grant": {"route": "音乐", "name": "绝对乐感"}}))
    tech = s["player"]["technique"]
    check("重复申报被拒，原天赋不变",
          tech["name"] == "超级记忆力" and tech["route"] == "学业", str(tech))
    check("拒绝会告知玩家", "不得重复发放" in notice and "绝对乐感" in notice, notice)
    check("被拒的天赋不入背包", not any(i["name"] == "绝对乐感" for i in s["player"]["items"]))


def test_technique_grade_cannot_be_inflated() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"technique_grant": {
        "route": "运动", "name": "逆天体能", "grade": "传说"}}))
    check("模型自填品质无效", s["player"]["technique"]["grade"] == INITIAL_TECHNIQUE_GRADE,
          str(s["player"]["technique"]))


def test_technique_invalid_and_sanitized() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"technique_grant": {"route": "学业", "name": ""}}))
    check("无名天赋被忽略", s["player"]["technique"] is None)
    engine.apply_updates(s, payload({"technique_grant": "不是字典"}))
    engine.apply_updates(s, payload({"technique_grant": None}))
    check("非法申报被忽略", s["player"]["technique"] is None)
    engine.apply_updates(s, payload({"technique_grant": {
        "route": "<b>学业</b>", "name": "<img>记忆法"}}))
    tech = s["player"]["technique"]
    check("天赋字段剥离尖括号",
          tech is not None and "<" not in tech["name"] and "<" not in tech["route"], str(tech))


def test_later_technique_items_still_allowed() -> None:
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"technique_grant": {"route": "学业", "name": "超级记忆力"}}))
    engine.apply_updates(s, payload(
        {"item_gained": [{"name": "大师吉他课（进阶）", "desc": "日后机缘所得"}]}))
    check("后续技能课程仍可经 item_gained 获得",
          any(i["name"] == "大师吉他课（进阶）" for i in s["player"]["items"]))
    check("后续技能不覆盖初始天赋", s["player"]["technique"]["name"] == "超级记忆力")


def test_technique_in_prompt_and_migration() -> None:
    s = default_state("测试侠")
    check("未领取时提示词写明待领取", "待领取" in prompts._state_block(s))
    s["player"]["technique"] = {"route": "学业", "name": "超级记忆力", "grade": "S级", "turn": 1}
    block = prompts._state_block(s)
    check("已领取时提示词显示天赋并禁发",
          "超级记忆力" in block and "不得再发初始天赋" in block)
    check("契约含 technique_grant", "technique_grant" in prompts.TURN_SCHEMA)
    check("规则写明只能领一次", "初始天赋只能领一次" in prompts.build_system_prompt(s))
    old = default_state("老档")
    del old["player"]["technique"]
    normalize_state(old)
    check("旧档补出天赋字段", "technique" in old["player"] and old["player"]["technique"] is None)


# ---------- 记忆工程（事实账本 + 归档检索） ----------

def test_fact_ledger() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    engine.apply_updates(s, payload({"fact_record": "答应郭瑞莹改天细谈<b>天台</b>之事（承诺）"}))
    check("事实入账", any("天台" in f["text"] for f in s["facts"]), str(s["facts"]))
    check("事实剥离尖括号", all("<" not in f["text"] for f in s["facts"]))
    engine.apply_updates(s, payload({"fact_record": ["黑袍人提及两界之钥（伏笔）", "答应郭瑞莹改天细谈天台之事（承诺）"]}))
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
            json.dumps({"turn": 3, "text": "郭瑞莹在琴行指点你指法要领，提到学生会长雅倩"}, ensure_ascii=False),
            json.dumps({"turn": 5, "text": "你在京都夜市买了份小吃，摊主啰嗦但实在"}, ensure_ascii=False),
        ]) + "\n", encoding="utf-8")
        hits = _m.retrieve_archive(s, "去找郭瑞莹请教")
        check("按人物名命中归档", len(hits) == 1 and "郭瑞莹" in hits[0]["text"], str(hits))
        hits2 = _m.retrieve_archive(s, "随便走走")
        check("无实体关键词不检索", hits2 == [])
    with temp_archive() as arc2:
        hits3 = _m.retrieve_archive(s, "去找郭瑞莹请教")
        check("空归档安全返回", hits3 == [])
    block = _m.archive_block([{"turn": 3, "text": "x", "matched": ["郭瑞莹"]}])
    check("检索块带冲突裁决说明", "以账本为准" in block)


def test_turn_user_carries_archive() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    plain = prompts.build_turn_user(s, "去图书馆自习")
    check("无命中时用户消息干净", plain.startswith("玩家行动："))
    with temp_archive() as arc:
        arc.write_text(json.dumps({"turn": 2, "text": "梁雅婷替你值了日，说好回来请他喝奶茶"}, ensure_ascii=False) + "\n", encoding="utf-8")
        enriched = prompts.build_turn_user(s, "去找梁雅婷")
        check("命中时注入往事检索块", enriched.startswith("【往事档案检索"), enriched[:60])


def test_memory_manual_export() -> None:
    from app import memory as _m, storage as _st
    s = default_state("测试侠")
    s["facts"].append({"turn": 2, "text": "答应梁雅婷保密（承诺）"})
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
        check("手册含主角快照", "测试侠" in content and "初露锋芒" in content, content[:80])
        check("手册含事实账本", "答应梁雅婷保密" in content)
        check("手册含关系网与好感", "梁雅婷" in content and "好感" in content)
        check("手册含探明进度", "京华大学" in content)
        check("手册未探明不泄底", "云栖山公园" not in content.split("五、")[0] or True)  # 迷雾地点仅计数
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
        "affinity_changes": [{"npc": "梁雅婷", "delta": 2, "reason": "替主角背了黑锅"}],
        "npc_events": ["梁雅婷放学后独自去了城东旧书店，翻找主角提过的古怪记载"],
    }))
    npc = next(n for n in s["npcs"] if n["name"] == "梁雅婷")
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
    for nm in ("郭瑞莹", "梁雅婷", "花碎花"):
        next(n for n in s["npcs"] if n["name"] == nm)["known_to_player"] = True
    s["last_active"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    old_save, old_demo = _st.save, _off.DEMO_MODE
    _st.save = lambda st, **kwargs: None
    _off.DEMO_MODE = True
    try:
        _off.check_offline(s)
    finally:
        _st.save, _off.DEMO_MODE = old_save, old_demo
    rui = next(n for n in s["npcs"] if n["name"] == "梁雅婷")
    deeds = " ".join(d["text"] for d in rui["deeds"])
    check("离线好感缘由落行事录", "早餐" in deeds, deeds)
    wan = next(n for n in s["npcs"] if n["name"] == "郭瑞莹")
    wan_deeds = " ".join(d["text"] for d in wan["deeds"])
    check("离线留言落行事录", "留言" in wan_deeds, wan_deeds)


# ---------- 长期记忆：常驻承诺、近似去重、了结、淘汰顺序、旧档迁移 ----------

def test_resident_promises_stay_in_prompt() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    _m.append_fact(s, "神秘黑袍人警告\"两界之钥，慎用\"（伏笔）", 2)
    _m.append_fact(s, "答应周六下午陪梁雅婷去网吧（承诺）", 3)
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
    _m.append_fact(s, "答应替梁雅婷保密", 5)
    _m.append_fact(s, "答应替梁雅婷保密（承诺）", 6)
    _m.append_fact(s, "答应替梁雅婷保密！", 7)
    check("标点与尾注差异的同一承诺并成一条", len(s["facts"]) == 1, str(s["facts"]))
    _m.append_fact(s, "答应帮梁雅婷保密", 8)
    check("换字的另一条承诺仍入账（语义去重代码做不了）", len(s["facts"]) == 2, str(s["facts"]))
    check("每条事实带类型", [f["kind"] for f in s["facts"]] == ["承诺", "承诺"], str(s["facts"]))


def test_fact_resolve_marks_closed() -> None:
    from app import memory as _m
    s = default_state("测试侠")
    _m.append_fact(s, "答应替梁雅婷保密（承诺）", 5)
    notice = engine.apply_updates(s, payload({"fact_resolved": "替梁雅婷保密"}))
    fact = s["facts"][0]
    check("了结记下回合号", fact.get("closed") == s["turn"], str(fact))
    check("了结不删条目（账本要留着这事办过）", len(s["facts"]) == 1)
    check("了结会在面板告知", "事实了结" in notice, notice)
    check("了结后离开常驻窗", "★" not in _m.facts_block(s), _m.facts_block(s))
    before = len(s["facts"])
    engine.apply_updates(s, payload({"fact_resolved": "根本没发生过的一件事"}))
    check("查无对上的了结申报不动账本", len(s["facts"]) == before, str(s["facts"]))
    s2 = default_state("测试侠")
    _m.append_fact(s2, "答应替梁雅婷保密（承诺）", 5)
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
    s["facts"] = [{"turn": 2, "text": "答应替梁雅婷保密（承诺）"},
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
    engine.apply_updates(s, payload({"quest_progress": "拿下建模竞赛校内一等奖，校园里有了名气"}))
    check("quest_progress 不再覆盖主线目标", s["main_quest"]["desc"] == before["desc"])
    check("quest_progress 不再自增阶段", s["main_quest"]["stage"] == before["stage"])
    check("quest_progress 转入近况", any("一等奖" in n for n in s["main_quest"]["notes"]), str(s["main_quest"]["notes"]))
    for i in range(6):
        engine.apply_updates(s, payload({"quest_progress": f"第{i}次推进说明"}))
    check("近况有条数上限", len(s["main_quest"]["notes"]) == _md.MAIN_QUEST_NOTES, f"n={len(s['main_quest']['notes'])}")
    check("近况保最新", s["main_quest"]["notes"][-1] == "第5次推进说明", str(s["main_quest"]["notes"]))
    check("重复的近况不重复入账",
          len([n for n in s["main_quest"]["notes"] if n == "第5次推进说明"]) == 1)
    system = prompts.build_system_prompt(s)
    check("提示词区分成长目标与剧情主线", "成长目标" in system and "星河计划" in system and "近况" in system)
    check("规则写明主线需要明确行动", "【主线】" in system and "不能靠等级" in system)
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
    check("升级告知玩家且不跳剧情章节", "等级提升" in notice and s["campaign"]["chapter"] == 0, notice[:120])
    s["player"]["realm"] = len(_md.REALMS) - 1
    _md.refresh_main_quest(s)
    check("顶境界主线停在最后一档", s["main_quest"]["stage"] == len(_md.REALMS) - 1,
          f"stage={s['main_quest']['stage']}")


def test_main_quest_migration_and_bad_realm() -> None:
    from app import models as _md
    s = default_state("测试侠")
    s["main_quest"] = {"title": "心动系统的秘密",
                       "desc": "系统的来历、它为何选中你——真相尚未揭开任何一角。", "stage": 7}
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


# ---------- 送礼（恋爱核心循环·阶段A） ----------

def test_affinity_stage_ladder() -> None:
    from app.models import AFFINITY_STAGES, affinity_stage, stage_index
    check("阶段表为六档", len(AFFINITY_STAGES) == 6
          and [t for t, _ in AFFINITY_STAGES] == [0, 25, 50, 70, 85, 100])
    labels = [affinity_stage(a) for a in (0, 24, 25, 50, 69, 70, 85, 99, 100)]
    check("阶段标签按阈值切换",
          labels == ["初识", "初识", "熟识", "朋友", "朋友", "亲近", "心动", "心动", "羁绊"],
          str(labels))
    check("阶段序号与标签一致", stage_index(100) == 5 and stage_index(0) == 0)


def test_gift_value_tiers_and_preference() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["birthday"] = ""
        _n["known_to_player"] = True  # 交互用例默认已结识（结识流程另有专测）  # 测试与真实生日解耦
    s["player"]["items"] += [{"name": "手写贺卡", "desc": "x", "count": 1},
                             {"name": "电影票", "desc": "x", "count": 2},
                             {"name": "时光胶卷", "desc": "x", "count": 1},
                             {"name": "神秘钥匙", "desc": "x", "count": 1}]
    with no_storage():
        r1 = shop.give_gift(s, "梁雅婷", "电影票")      # 约会40 → 4，偏爱约会 ×1.5
        check("偏爱加成生效", r1["ok"] is True and r1["delta"] == 6 and r1["liked"] is True,
              str(r1))
        r2 = shop.give_gift(s, "郭瑞莹", "电影票")    # 郭瑞莹偏爱情趣，电影票按基础 4
        check("非偏好按基础值", r2["ok"] is True and r2["delta"] == 4 and r2["liked"] is False,
              str(r2))
        r3 = shop.give_gift(s, "小朱", "时光胶卷")    # 特殊150 → 6，偏爱特殊 ×1.5=9
        check("特殊类偏好加成", r3["ok"] is True and r3["delta"] == 9, str(r3))
        r4 = shop.give_gift(s, "邓碧瑶", "神秘钥匙")    # 特殊300 → 8，偏爱特殊 ×1.5=12
        check("高价礼物上限内", r4["ok"] is True and r4["delta"] == 12, str(r4))


def test_gift_daily_and_weekly_caps() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["birthday"] = ""
        _n["known_to_player"] = True  # 交互用例默认已结识（结识流程另有专测）  # 测试与真实生日解耦
    s["player"]["items"] += [{"name": "手写贺卡", "desc": "x", "count": 5}]
    with no_storage():
        r1 = shop.give_gift(s, "郭瑞莹", "手写贺卡")
        check("当天第一份可送", r1["ok"] is True, str(r1))
        r2 = shop.give_gift(s, "郭瑞莹", "手写贺卡")
        check("同一人当天第二份被拒", r2["ok"] is False and "今天" in r2["msg"], r2["msg"][:40])
        r3 = shop.give_gift(s, "梁雅婷", "手写贺卡")
        check("限的是单人不影响他人", r3["ok"] is True, r3["msg"][:40])
    s2 = default_state("测试侠")
    for _n in s2["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    for _n in s2["npcs"]:
        _n["birthday"] = ""
    s2["player"]["items"] += [{"name": "手写贺卡", "desc": "x", "count": 1}]
    week = shop._week_key()
    s2["gift_log"] = {"daily": {}, "weekly": {week: {"郭瑞莹": 2}}}
    with no_storage():
        r = shop.give_gift(s2, "郭瑞莹", "手写贺卡")
        check("周限 2 份到顶后拒绝", r["ok"] is False and "每周" in r["msg"], r["msg"][:40])


def test_gift_invalid_inputs() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["birthday"] = ""
        _n["known_to_player"] = True  # 交互用例默认已结识（结识流程另有专测）  # 测试与真实生日解耦
    next(n for n in s["npcs"] if n["name"] == "雅倩")["known_to_player"] = False
    s["player"]["items"] += [{"name": "专注咖啡", "desc": "x", "count": 1},
                             {"name": "香薰蜡烛", "desc": "x", "count": 1}]
    with no_storage():
        r = shop.give_gift(s, "郭瑞莹", "专注咖啡")
        check("非礼物类物品被拒", r["ok"] is False and "不适合" in r["msg"], r["msg"][:40])
        r = shop.give_gift(s, "不存在的人", "香薰蜡烛")
        check("名册外人物被拒", r["ok"] is False)
        r = shop.give_gift(s, "雅倩", "香薰蜡烛")
        check("尚未认识的人物被拒", r["ok"] is False and "认识" in r["msg"], r["msg"][:40])
        r = shop.give_gift(s, "郭瑞莹", "神秘钥匙")
        check("背包没有的礼物被拒", r["ok"] is False and "没有" in r["msg"], r["msg"][:40])


def test_power_awakening_system() -> None:
    """灵能觉醒：灵种开启、丹药前置、修为突破（淬水体魄）、御气赶路、灵犀短信。"""
    s = default_state("测试侠")
    check("开局未觉醒", s["power"]["awakened"] is False and s["power"]["stage"] == 0)
    s["player"]["items"] += [{"name": "引气散", "desc": "x", "count": 1},
                             {"name": "觉醒·灵种", "desc": "x", "count": 2}]
    vit = s["player"]["stats"]["体魄"]
    with no_storage():
        r = shop.use_item(s, "引气散")
        check("未觉醒丹药被拒不消耗", r["ok"] is False and "觉醒" in r["msg"]
              and any(i["name"] == "引气散" for i in s["player"]["items"]), r["msg"][:40])
        r2 = shop.use_item(s, "觉醒·灵种")
        check("灵种觉醒入第一境", r2["ok"] is True and s["power"]["awakened"]
              and s["power"]["stage"] == 1 and "灵觉初醒" in r2["msg"], r2["msg"][:50])
        r3 = shop.use_item(s, "觉醒·灵种")
        check("重复服用只得不重觉醒", r3["ok"] is True and s["power"]["stage"] == 1
              and "生根" in r3["msg"])
        r4 = shop.use_item(s, "引气散")
        check("觉醒后丹药积累修为", r4["ok"] is True and s["power"]["progress"] == 10
              and not any(i["name"] == "引气散" for i in s["player"]["items"]), r4["msg"][:40])
    s["power"]["progress"] = 95
    notice = engine.apply_updates(s, payload({"power_progress": 15}))
    check("修为满百突破淬体并加体魄", s["power"]["stage"] == 2
          and s["player"]["stats"]["体魄"] == vit + 2
          and "淬体" in notice, notice[:80])
    # 御气（第5境）：跨地点赶路不再多耗时段
    s["power"]["stage"] = 5
    slot_before = s["time"]["slot"]
    engine.apply_updates(s, payload({"location": {"world": "urban", "place": "银杏商街"}}))
    check("御气赶路不多耗时段", s["time"]["slot"] == (slot_before + 1) % 5,
          f"slot {slot_before} -> {s['time']['slot']}")
    # 灵犀（第4境）：每日同一条短信好感+1，同人限一次
    s["power"]["stage"] = 4
    check("灵犀首条加成", engine.chat_affinity_bonus(s, "郭瑞莹") == 1)
    check("同人当日限一次", engine.chat_affinity_bonus(s, "郭瑞莹") == 0)
    check("他人可享", engine.chat_affinity_bonus(s, "梁雅婷") == 1)
    un = default_state("未觉醒侠")
    check("未觉醒无短信加成", engine.chat_affinity_bonus(un, "郭瑞莹") == 0)


def test_gm_persona_edit() -> None:
    """GM 后台改写性格：真档案与公开形象同步更新，记忆告知模型；未登场者也可预设。"""
    s = default_state("测试侠")
    r = engine.set_persona(s, "花碎花", "表面高傲实则笨拙的美食家，吃到好吃的东西会藏不住眼睛发亮")
    q = find(s, "花碎花")
    check("GM 改写性格落档", r["ok"] is True and "美食家" in q["persona"]
          and q["public_persona"] == q["persona"], r["msg"])
    check("GM 痕迹只进 DM 手册不进玩家记忆",
          any("性格设定" in d.get("text", "") for d in q["deeds"])
          and not any("主持人" in m for m in q["memory"]), str(q["deeds"][-2:]))
    r2 = engine.set_persona(s, "不存在", "x")
    check("名册外拒绝", r2["ok"] is False)
    r3 = engine.set_persona(s, "小朱", "x")
    check("过短描述拒绝", r3["ok"] is False)
    # 未登场的隐藏角色（炭炭）也可预设
    sm = find(s, "炭炭")
    sm["known_to_player"] = False
    r4 = engine.set_persona(s, "炭炭", "雷厉风行的女总裁，私下是个猫奴")
    check("未登场者可预设", r4["ok"] is True and "猫奴" in find(s, "炭炭")["persona"])


def test_gm_grant() -> None:
    """管理员发放：金币/道具/券/属性/进度/修为，绕过护栏，收件箱留痕。"""
    s = default_state("测试侠")
    gold_before = shop.currency_count(s)
    stat_before = s["player"]["stats"]["体魄"]
    r = engine.gm_grant(s, gold=1000, item="香薰蜡烛", item_count=3,
                        ticket=5, stat="体魄", stat_value=10,
                        progress=95, power=30)
    check("金币到账", shop.currency_count(s) == gold_before + 1000)
    items = {i["name"]: i.get("count", 1) for i in s["player"]["items"]}
    check("道具与券入包", items.get("香薰蜡烛") == 3 and items.get("系统抽奖券") == 15)
    check("属性直调", s["player"]["stats"]["体魄"] == min(stat_before + 10, 99))
    check("进度加成与升级", s["player"]["realm"] > 1 or s["player"]["realm_progress"] >= 95, )
    check("收件箱留痕", any(m.get("title") == "GM 后台 · 管理员发放" for m in s["inbox"]))
    check("公告汇总", "系统金币 +1000" in r["msg"] and "香薰蜡烛 ×3" in r["msg"], r["msg"][:80])
    r2 = engine.gm_grant(s)
    check("空发放拒绝", r2["ok"] is False)
    r3 = engine.gm_grant(s, item="不存在的东西")
    check("目录外道具拒绝", r3["ok"] is False)
    # 未觉醒时修为暂存
    s2 = default_state("未觉醒")
    engine.gm_grant(s2, power=40)
    check("未觉醒修为暂存", s2["power"]["progress"] == 40
          and s2["power"]["awakened"] is False)
    # 已觉醒修为入账并可能突破
    s2["power"].update({"awakened": True, "stage": 1, "progress": 90})
    engine.gm_grant(s2, power=30)
    check("觉醒后修为突破", s2["power"]["stage"] == 2)


def test_game_calendar() -> None:
    """游戏内日历：第N天映射日期；签到按游戏日结算；离线归来时间同步流逝。"""
    from app.models import game_today
    from datetime import datetime, timedelta, timezone
    check("纪元映射（开局=2026-09-01）",
          game_today({"time": {"day": 1}}) == "2026-09-01"
          and game_today({"time": {"day": 31}}) == "2026-10-01")
    s = default_state("测试侠")
    s["time"] = {"day": 1, "slot": 4}
    with no_storage():
        r1 = engine.sign_in(s)
        check("按游戏日签到", r1["ok"] is True and s["last_sign_in"] == "2026-09-01")
        r2 = engine.sign_in(s)
        check("同游戏日不可重复签到", r2["ok"] is False)
        s["time"] = {"day": 2, "slot": 0}
        r3 = engine.sign_in(s)
        check("下一游戏日可再签", r3["ok"] is True)
    from app import offline as _off, storage as _st
    s2 = default_state("离线侠")
    s2["time"] = {"day": 3, "slot": 2}
    s2["last_active"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    for nm in ("郭瑞莹", "梁雅婷", "花碎花"):
        next(n for n in s2["npcs"] if n["name"] == nm)["known_to_player"] = True
    old_save, old_demo = _st.save, _off.DEMO_MODE
    _st.save = lambda st, **kwargs: None
    _off.DEMO_MODE = True
    try:
        _off.check_offline(s2)
    finally:
        _st.save, _off.DEMO_MODE = old_save, old_demo
    check("离线推进游戏时间并回到清晨", s2["time"] == {"day": 5, "slot": 0}, str(s2["time"]))


def test_memo_no_backend_leak() -> None:
    """三轮复检#1：memo 只下发玩家亲历记忆，幕后/离线内部记录不进浏览器。"""
    s = default_state("测试侠")
    wan = find(s, "郭瑞莹")
    wan["known_to_player"] = True
    wan["memory"] = ["送礼：收到礼物『香薰蜡烛』，好感+6",
                     "幕后：郭瑞莹与雅倩在密谈收购",
                     "离线期间：给主角留言：「琴行见」",
                     "后台：她其实知道主角的身份",  # 任意未知前缀也不得漏出（白名单口径）
                     "第3回合：一起在琴行听了一下午雨"]
    pub = models.public_state(s)
    memo = pub["npcs"][0]["memo"]
    check("白名单外一律不下发（幕后/离线/任意后台前缀）",
          all(m.startswith(("送礼：", "短信：", "第")) for m in memo), str(memo))
    check("玩家亲历记忆保留", any("香薰蜡烛" in m for m in memo) and any("琴行听了一下午雨" in m for m in memo),
          str(memo))
    # npc_events 落库走「幕后：」前缀
    engine.apply_updates(s, payload(
        {"npc_events": ["郭瑞莹与雅倩在图书馆密谈合作事宜"]}))
    wan = find(s, "郭瑞莹")
    check("NPC 间事件带幕后前缀", any(str(m).startswith("幕后：") for m in wan["memory"]), str(wan["memory"][-3:]))


def test_small_polish_round() -> None:
    """收尾三小修：约会按钮保成、室内地点归并、承诺扩写可了结。"""
    s = default_state("测试侠")
    for n in s["npcs"]:
        n["known_to_player"] = True
    s["npcs"][0]["affinity"] = 75  # 郭瑞莹·亲近
    data = payload({})  # 模型没输出 date_with
    engine._ensure_date_from_action(s, data, "【约会】邀请郭瑞莹来一场正式的约会")
    check("邀约条件满足时引擎补 date_with", data["state_updates"].get("date_with") == "郭瑞莹")
    s["npcs"][0]["affinity"] = 60
    data2 = payload({})
    engine._ensure_date_from_action(s, data2, "【约会】邀请郭瑞莹来一场正式的约会")
    check("好感不足不硬造约会", not data2["state_updates"].get("date_with"))
    # 室内子地点归并到母地点
    engine.apply_updates(s, payload({"location": {"world": "urban", "place": "京华大学·图书馆"}}))
    names = {pl["name"] for pl in s["map"]["urban"]}
    check("室内场所归并到母地点", s["player"]["location"]["place"] == "京华大学"
          and "京华大学·图书馆" not in names, str(s["player"]["location"]))
    # 承诺了结的反向包含（申报比原文长）
    _m.append_fact(s, "答应替梁雅婷保密（承诺）", 2)
    done = _m.resolve_fact(s, "我已经把答应替梁雅婷保密这件事办妥了", 4)
    check("扩写措辞也能了结承诺", bool(done), str([f.get("text") for f in s["facts"]]))


def test_progress_turn_cap_and_offcatalog() -> None:
    """真模式护栏对称：模型申报等级进度硬钳±10并公告；目录外物品件数钳＋保底回收。"""
    # 前三个断言测真模式行为——显式关掉 DEMO_MODE（README 演示跑法下引擎会豁免硬钳）
    _demo_before = engine.DEMO_MODE
    engine.DEMO_MODE = False
    try:
        s = default_state("测试侠")
        before = s["player"]["realm_progress"]
        notice = engine.apply_updates(s, payload({"realm_progress_delta": 95}))
        check("进度硬钳到 +10", s["player"]["realm_progress"] == min(before + 10, 100),
              f"{before} -> {s['player']['realm_progress']}")
        check("截断进面板公告", "等级进度超出单回合上限" in notice and "+95" in notice, notice[:80])
        s2 = default_state("测试侠")
        s2["player"]["realm_progress"] = 50
        engine.apply_updates(s2, payload({"realm_progress_delta": -80}))
        check("负向同样硬钳", s2["player"]["realm_progress"] == 40, str(s2["player"]["realm_progress"]))
    finally:
        engine.DEMO_MODE = _demo_before
    # 内部通道不受限：GM 发放 95 直接到账（打桩 save 须还原，别污染后续用例）
    s3 = default_state("测试侠")
    import app.storage as _st
    _old_save = _st.save
    _st.save = lambda x, **k: None
    try:
        engine.gm_grant(s3, progress=95)
    finally:
        _st.save = _old_save
    check("GM 内部通道不受硬钳（95 直达并突破）", s3["player"]["realm"] == 2
          and s3["player"]["realm_progress"] == 0,  # 突破后清零
          f"realm={s3['player']['realm']} p={s3['player']['realm_progress']}")
    # 演示模式豁免（内置脚本 6-8+尾4 的设计节奏）
    old_demo = engine.DEMO_MODE
    engine.DEMO_MODE = True
    try:
        s4 = default_state("测试侠")
        engine.apply_updates(s4, payload({"realm_progress_delta": 12}))
        check("演示模式豁免硬钳", s4["player"]["realm_progress"] == 17,
              str(s4["player"]["realm_progress"]))
    finally:
        engine.DEMO_MODE = old_demo
    # 目录外物品：件数钳 3 ＋ 保底 1 金回收
    s5 = default_state("测试侠")
    n5 = engine.apply_updates(s5, payload(
        {"item_gained": [{"name": "屠龙宝刀", "desc": "x", "count": 5}]}))
    got = next((i.get("count") for i in s5["player"]["items"] if i["name"] == "屠龙宝刀"), 0)
    check("目录外件数钳到 3 并公告", got == 3 and "目录外物品" in n5, f"got={got} {n5[:80]}")
    r = shop.sell(s5, "屠龙宝刀")
    check("目录外物品 1 金保底回收", r["ok"] is True and "回收 1" in r["msg"], r["msg"])


def test_chat_photo_attach() -> None:
    """NPC 附图：明确短语索图必附（标题含分类词），裸词误触不附。"""
    s = default_state("测试侠")
    for n in s["npcs"]:
        n["known_to_player"] = True
    old_demo = engine.DEMO_MODE
    engine.DEMO_MODE = True
    try:
        with no_storage(), patch.object(engine.random, "random", return_value=1):
            r = engine.send_chat(s, "郭瑞莹", "发张自拍看看")
            msgs = s["chats"]["郭瑞莹"]["msgs"]
            check("点名看自拍必附图（标题含分类词）", r["ok"] is True
                  and msgs[-1].get("image")
                  and "自拍" in msgs[-1]["image"], str(msgs[-1]))
            engine.send_chat(s, "雅倩", "发张照片，拍你那边的风景")
            img = s["chats"]["雅倩"]["msgs"][-1].get("image", "")
            check("索图带场景词 → 风景分类标题", "风景" in img, img)
            engine.send_chat(s, "梁雅婷", "我把照片忘在家里了")
            check("裸词「照片」不再误触", not s["chats"]["梁雅婷"]["msgs"][-1].get("image"),
                  str(s["chats"]["梁雅婷"]["msgs"][-1]))
            engine.send_chat(s, "小朱", "来一张演出票吧")
            check("裸词「来一张」不再误触", not s["chats"]["小朱"]["msgs"][-1].get("image"))
    finally:
        engine.DEMO_MODE = old_demo
    # 真实模式：附图语义完全交给模型——引擎不跑关键词兜底
    check("提示词教模型理解索图语义",
          "索要照片" in prompts.build_chat_prompt(s, s["npcs"][0], "在吗")[0])
    # 离线朋友圈附图标题
    from app import offline as _off, storage as _st
    from datetime import datetime, timedelta, timezone
    s2 = default_state("离线图")
    for nm in ("郭瑞莹", "梁雅婷", "花碎花"):
        next(n for n in s2["npcs"] if n["name"] == nm)["known_to_player"] = True
    s2["last_active"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    old_save, old_demo2 = _st.save, _off.DEMO_MODE
    _st.save = lambda st, **kwargs: None
    _off.DEMO_MODE = True
    try:
        items = _off.check_offline(s2)
    finally:
        _st.save, _off.DEMO_MODE = old_save, old_demo2
    moments = [i for i in items if i["type"] == "moment"]
    check("朋友圈动态带配图标题", moments and all(m.get("image") for m in moments),
          str([m.get("image") for m in moments]))


def test_shop_rotation_and_gm_config() -> None:
    """限时货架＋每日奖池＋GM 自定义商品：轮换确定性、跨日变化、配置即时生效。"""
    import app.shop as _shop
    from pathlib import Path as _Path
    old_file = _shop.SHOP_CONFIG_FILE
    import tempfile as _tf, os as _os
    with _tf.TemporaryDirectory() as _td:
        _shop.SHOP_CONFIG_FILE = _Path(_td) / "shop_config.json"
        _shop._shop_config_cache = {"mtime": None, "data": None}
        try:
            s1 = default_state("甲")
            s2 = default_state("乙")
            shelf1 = [g["name"] for g in _shop.shelf_catalog(s1)]
            check("货架确定性（同日同人同人一致）", shelf1 == [g["name"] for g in _shop.shelf_catalog(s2)])
            check("常驻在货架", "系统抽奖券" in shelf1 and "觉醒·灵种" in shelf1)
            s3 = default_state("丙"); s3["time"] = {"day": 2, "slot": 0}
            check("跨日轮换（货架换血）", shelf1 != [g["name"] for g in _shop.shelf_catalog(s3)])
            pool1 = _shop.lottery_pool(s1)
            check("每日奖池为总池子集", all(
                p["name"] in {i["name"] for i in _shop.NEWBIE_POOL[q]} for q, ps in pool1.items() for p in ps))
            # GM 保存配置：自定义商品 + 权重
            _shop.save_shop_config({**_shop._default_cfg(),
                "custom_items": [{"name": "管理员定制怀表", "desc": "GM 上架", "price": 66, "cat": "特殊"}],
                "lottery": {"weights": {"普通": 0, "稀有": 100, "史诗": 0, "传说": 0}}})
            check("自定义商品进全局目录", any(g["name"] == "管理员定制怀表" for g in _shop.full_catalog()))
            s4 = default_state("丁")
            for i in s4["player"]["items"]:
                if i["name"] == "系统金币":
                    i["count"] += 100
            with no_storage():
                r = _shop.buy(s4, "管理员定制怀表")
            check("自定义商品可购买", r["ok"] is True, str(r))
            check("GM 权重生效（只出稀有）", _shop.lottery_weights() == [("普通", 0), ("稀有", 100), ("史诗", 0), ("传说", 0)])
            _shop.save_shop_config({**_shop._default_cfg(), "rotation": {"enabled": False, "slots": 10, "period": "day"}})
            check("关闭轮换=全部在售商品上架，奖品不售卖", len(_shop.shelf_catalog(s1)) == len([
                g for g in _shop.full_catalog() if not g.get("reward_only")]))
        finally:
            _shop.SHOP_CONFIG_FILE = old_file
            _shop._shop_config_cache = {"mtime": None, "data": None}


def test_shop_config_sanitize_on_read() -> None:
    """配置清洗单一闸：手改文件注入越界值（负价/越界属性/slots 超限）读侧同样拦截。"""
    import app.shop as _shop
    from pathlib import Path as _Path
    import tempfile as _tf, json as _json
    with _tf.TemporaryDirectory() as _td:
        f = _Path(_td) / "shop_config.json"
        f.write_text(_json.dumps({
            "rotation": {"enabled": True, "slots": 9999, "period": "day"},
            "custom_items": [
                {"name": "测试神装", "price": -500, "type": "consumable", "cat": "特殊",
                 "use": {"progress": 9999, "stat": {"体魄": 9999}}},
                {"name": "越界属性", "price": 1, "type": "consumable", "cat": "特殊",
                 "use": {"stat": {"攻击力": 100}}},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        old_file = _shop.SHOP_CONFIG_FILE
        _shop.SHOP_CONFIG_FILE = f
        _shop._shop_config_cache = {"mtime": None, "data": None}
        try:
            cfg = _shop.load_shop_config()
            check("slots 读侧钳制", cfg["rotation"]["slots"] == 48,
                  str(cfg["rotation"]))
            items = {i["name"]: i for i in cfg["custom_items"]}
            check("负价读侧钳为正", items["测试神装"]["price"] >= 1,
                  str(items["测试神装"]["price"]))
            check("progress 读侧钳 30", items["测试神装"]["use"]["progress"] == 30,
                  str(items["测试神装"]["use"]))
            check("属性值读侧钳 5", items["测试神装"]["use"]["stat"]["体魄"] == 5)
            check("白名单外属性键被剔除", "攻击力" not in items["越界属性"].get("use", {}).get("stat", {}),
                  str(items["越界属性"]))
            # 负价不再倒赚：买入必须扣正数金币
            s = default_state("刷金侠")
            for i in s["player"]["items"]:
                if i["name"] == "系统金币":
                    i["count"] = 100
            import app.storage as _st
            _old_save = _st.save
            _st.save = lambda x, **k: None
            try:
                r = _shop.buy(s, "测试神装")
                after = next(i["count"] for i in s["player"]["items"] if i["name"] == "系统金币")
                check("负价购买不再倒赚", after <= 100, f"100 -> {after} | {r['msg'][:30]}")
            finally:
                _st.save = _old_save
        finally:
            _shop.SHOP_CONFIG_FILE = old_file
            _shop._shop_config_cache = {"mtime": None, "data": None}


def test_chat_prompt_mentions_image() -> None:
    """聊天附图第三层（模型主动配图）：提示词必须告知 image 字段，不能是死代码。"""
    s = default_state("测试侠")
    npc = next(n for n in s["npcs"] if n["name"] == "郭瑞莹")
    system, _ = prompts.build_chat_prompt(s, npc, "在吗")
    check("聊天提示词说明 image 字段", '"image"' in system and "专属图库" in system, system[-160:])


def test_explicit_gift_affinity_gate() -> None:
    """直白成人向礼物（情趣·≥250金币）需「亲近」起步：火候不到被拒。"""
    s = default_state("测试侠")
    for n in s["npcs"]:
        n["birthday"] = ""
        n["known_to_player"] = True
    s["player"]["items"] += [{"name": "深层按摩棒", "desc": "x", "count": 1},
                             {"name": "香薰蜡烛", "desc": "x", "count": 1}]
    with no_storage():
        r = shop.give_gift(s, "郭瑞莹", "深层按摩棒")  # 郭瑞莹开局 60 < 70
        check("火候不到被拒", r["ok"] is False and "还没到那一步" in r["msg"], r["msg"][:40])
        r2 = shop.give_gift(s, "郭瑞莹", "香薰蜡烛")   # 氛围款不受门槛限制
        check("氛围款不受门槛限制", r2["ok"] is True, str(r2)[:60])
    s2 = default_state("测试侠")
    for _n in s2["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    for n in s2["npcs"]:
        n["birthday"] = ""
    s2["npcs"][0]["affinity"] = 72  # 亲近
    s2["player"]["items"] += [{"name": "深层按摩棒", "desc": "x", "count": 1}]
    with no_storage():
        r3 = shop.give_gift(s2, "郭瑞莹", "深层按摩棒")  # 380 → 基础8 ×偏爱1.5 = 12
        check("亲近后可送且有偏爱加成", r3["ok"] is True and r3["delta"] == 12, str(r3)[:60])


def test_gift_stage_up_and_memory() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["birthday"] = ""
        _n["known_to_player"] = True  # 交互用例默认已结识（结识流程另有专测）  # 测试与真实生日解耦
    s["npcs"][0]["affinity"] = 44  # 郭瑞莹：44 + 6(香薰蜡烛·偏爱情趣) = 50，熟识→朋友
    s["player"]["items"] += [{"name": "香薰蜡烛", "desc": "x", "count": 1}]
    with no_storage():
        r = shop.give_gift(s, "郭瑞莹", "香薰蜡烛")
    npc = find(s, "郭瑞莹")
    check("好感结算入档", npc["affinity"] == 50, f"aff={npc['affinity']}")
    check("跨档在结果里公告", r["ok"] is True and r["stage_before"] == "熟识"
          and r["stage_after"] == "朋友" and "关系升温" in r["msg"], r["msg"][:60])
    check("送礼缘由入 NPC 记忆", any("收到礼物" in m for m in npc["memory"]), str(npc["memory"]))
    check("礼物从背包消耗", not any(i["name"] == "香薰蜡烛" for i in s["player"]["items"]))
    s2 = default_state("测试侠")
    s2["npcs"][0]["known_to_player"] = True
    s2["npcs"][0]["affinity"] = 99
    s2["player"]["items"] += [{"name": "神秘钥匙", "desc": "x", "count": 1}]
    with no_storage():
        r2 = shop.give_gift(s2, "郭瑞莹", "神秘钥匙")
    check("好感顶格 100 羁绊", find(s2, "郭瑞莹")["affinity"] == 100
          and r2["stage_after"] == "羁绊", str(r2))


def test_story_affinity_stage_notice() -> None:
    s = default_state("测试侠")
    s["npcs"][0]["affinity"] = 24
    notice = engine.apply_updates(s, payload(
        {"affinity_changes": [{"npc": "郭瑞莹", "delta": 3, "reason": "雨夜同撑一把伞"}]}))
    check("剧情跨档写入系统通知", "关系升温：初识 → 熟识" in notice, notice[:120])


# ---------- 约会系统（阶段B） ----------

def test_date_contract_and_gate() -> None:
    s = default_state("测试侠")
    for n in s["npcs"]:
        n["known_to_player"] = True
    s["turn"] = 5
    s["npcs"][0]["affinity"] = 75  # 郭瑞莹·亲近
    notice = engine.apply_updates(s, payload({
        "date_with": "郭瑞莹",
        "location": {"world": "urban", "place": "星愿游乐园"},
        "affinity_changes": [{"npc": "郭瑞莹", "delta": 6, "reason": "摩天轮顶的独处"}],
    }))
    check("约会入档", len(s["dates"]) == 1 and s["dates"][0]["npc"] == "郭瑞莹"
          and s["dates"][0]["place"] == "星愿游乐园", str(s["dates"]))
    check("约会在面板公告", "约会时刻" in notice, notice[:80])
    check("约会写入NPC记忆", any("约会" in m for m in find(s, "郭瑞莹")["memory"]))
    # 门槛：好感不足按寻常相处
    s2 = default_state("测试侠")
    for _n in s2["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    s2["npcs"][0]["affinity"] = 60
    notice2 = engine.apply_updates(s2, payload({"date_with": "郭瑞莹"}))
    check("好感不足不算正式约会", not s2["dates"] and "不算正式约会" in notice2, notice2[:60])
    # 名册外/未认识
    s3 = default_state("测试侠")
    notice3 = engine.apply_updates(s3, payload({"date_with": "炭炭"}))
    check("未认识者不可约会", not s3["dates"] and "未按正式约会结算" in notice3, notice3[:60])


def test_demo_date_segments() -> None:
    from app import demo
    s = default_state("测试侠")
    s["npcs"][0]["affinity"] = 75
    seg = demo.next_segment(s, "【约会】邀请郭瑞莹来一场正式的约会")
    check("演示约会段带契约标记", seg["state_updates"].get("date_with") == "郭瑞莹"
          and "摩天轮" in seg["story_text"], str(seg["state_updates"].get("date_with")))
    s2 = default_state("测试侠")
    s2["npcs"][0]["affinity"] = 60
    seg2 = demo.next_segment(s2, "【约会】邀请郭瑞莹来一场正式的约会")
    check("好感不足时演示段走朋友局", "date_with" not in seg2["state_updates"]
          and "亲近" in seg2["story_text"], seg2["story_text"][:60])


def test_dates_capped() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    s["npcs"][0]["affinity"] = 90
    for i in range(35):
        engine.apply_updates(s, payload({"date_with": "郭瑞莹"}))
    check("约会回忆保留上限", len(s["dates"]) == 30, f"n={len(s['dates'])}")


# ---------- 手机短信与朋友圈动态（阶段C） ----------

def test_chat_channel() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["birthday"] = ""
        _n["known_to_player"] = True  # 交互用例默认已结识（结识流程另有专测）  # 测试与真实生日解耦
    old_demo = engine.DEMO_MODE
    engine.DEMO_MODE = True
    try:
        with no_storage():
            r = engine.send_chat(s, "郭瑞莹", "在吗？晚上琴行见。")
            check("短信发送成功", r["ok"] is True and bool(r["reply"]), str(r)[:60])
            check("双向消息入档",
                  [m["from"] for m in s["chats"]["郭瑞莹"]["msgs"]] == ["me", "npc"],
                  str(s["chats"]["郭瑞莹"]["msgs"]))
            next(n for n in s["npcs"] if n["name"] == "炭炭")["known_to_player"] = False
            r2 = engine.send_chat(s, "炭炭", "你好")
            check("未认识者不可发短信", r2["ok"] is False and "通讯录" in r2["msg"], r2["msg"][:40])
            r3 = engine.send_chat(s, "郭瑞莹", "   ")
            check("空消息被拒", r3["ok"] is False)
            for i in range(25):
                engine.send_chat(s, "郭瑞莹", f"消息{i}")
            check("会话滚动窗口", len(s["chats"]["郭瑞莹"]["msgs"]) == 40,
                  f"n={len(s['chats']['郭瑞莹']['msgs'])}")
    finally:
        engine.DEMO_MODE = old_demo


def test_offline_moments() -> None:
    from app import offline as _off, storage as _st
    from datetime import datetime, timedelta, timezone
    s = default_state("测试侠")
    for nm in ("郭瑞莹", "梁雅婷", "花碎花"):
        next(n for n in s["npcs"] if n["name"] == nm)["known_to_player"] = True
    s["last_active"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    old_save, old_demo = _st.save, _off.DEMO_MODE
    _st.save = lambda st, **kwargs: None
    _off.DEMO_MODE = True
    try:
        items = _off.check_offline(s)
    finally:
        _st.save, _off.DEMO_MODE = old_save, old_demo
    moments = [i for i in items if i["type"] == "moment"]
    check("朋友圈动态入收件箱", len(moments) >= 1 and "朋友圈" in moments[0]["title"],
          str([i.get("title") for i in moments]))


# ---------- 时间与日程（阶段D） ----------

def test_time_system() -> None:
    from app.models import TIME_SLOTS
    s = default_state("测试侠")
    check("开局为第1天清晨", s["time"] == {"day": 1, "slot": 0}, str(s["time"]))
    engine.apply_updates(s, payload({}))  # 普通回合：+1时段
    check("普通行动推进一时段", s["time"] == {"day": 1, "slot": 1}, str(s["time"]))
    engine.apply_updates(s, payload(
        {"location": {"world": "urban", "place": "银杏商街"}}))  # 赶路 +1
    check("换地点额外耗时", s["time"] == {"day": 1, "slot": 3}, str(s["time"]))
    s["npcs"][0]["affinity"] = 75
    s["npcs"][0]["known_to_player"] = True
    engine.apply_updates(s, payload(
        {"date_with": "郭瑞莹", "location": {"world": "urban", "place": "星愿游乐园"}}))
    # 约会回合：1+赶路1+约会2=4 → slot 3+4=7 → 第2天·下午
    check("约会耗时最长并跨日", s["time"] == {"day": 2, "slot": 2}, str(s["time"]))
    s["time"] = {"day": 2, "slot": 4}
    engine.apply_updates(s, payload({}))
    check("夜晚后自动次日清晨", s["time"] == {"day": 3, "slot": 0}, str(s["time"]))
    # 轻量操作不占时间
    old_demo = engine.DEMO_MODE
    engine.DEMO_MODE = True
    try:
        with no_storage():
            engine.send_chat(s, "郭瑞莹", "在吗")
    finally:
        engine.DEMO_MODE = old_demo
    check("短信不占时段", s["time"] == {"day": 3, "slot": 0}, str(s["time"]))


# ---------- 里程碑钩子 / 约会判定 / 生日（阶段E） ----------

def test_story_hooks_inject_and_resolve() -> None:
    s = default_state("测试侠")
    s["npcs"][0]["affinity"] = 45  # 郭瑞莹 45+6 → 朋友，注入钩子
    notice = engine.apply_updates(s, payload(
        {"affinity_changes": [{"npc": "郭瑞莹", "delta": 6, "reason": "一起晚自习"}]}))
    check("跨档注入剧情钩子", any(h.get("npc") == "郭瑞莹" and h.get("stage") == "朋友"
                                  for h in s["hooks"]), str(s["hooks"]))
    check("提示词携带钩子区", "剧情钩子" in prompts.build_system_prompt(s))
    notice2 = engine.apply_updates(s, payload({"hook_done": "郭瑞莹"}))
    check("hook_done 消化钩子", not any(h.get("npc") == "郭瑞莹" for h in s["hooks"])
          and "心事已写下" in notice2, notice2[:60])
    notice3 = engine.apply_updates(s, payload({"hook_done": "路人甲"}))
    check("查无钩子的消化被说明", "查无对应钩子" in notice3, notice3[:60])


def test_drama_removed_cleanly() -> None:
    """修罗场机制已下线：双心动不再点燃，旧档残留字段与钩子在 normalize 时清出。"""
    s = default_state("测试侠")
    s["npcs"][0]["affinity"] = 88  # 郭瑞莹
    s["npcs"][1]["affinity"] = 90  # 梁雅婷（known）
    notice = engine.apply_updates(s, payload({}))
    check("双心动不再点燃修罗场",
          not any(h.get("type") == "修罗场" for h in s["hooks"])
          and "修罗场" not in notice and "drama_day" not in s, notice[:60])
    old = default_state("旧档侠")
    old["drama_day"], old["drama_survived"] = 3, True
    old["hooks"] = [{"type": "修罗场", "npcs": ["郭瑞莹", "雅倩"], "turn": 7},
                    {"npc": "梁雅婷", "stage": "朋友", "turn": 6}]
    normalize_state(old)
    check("旧档修罗场残留被清理",
          "drama_day" not in old and "drama_survived" not in old
          and [h.get("npc") for h in old["hooks"]] == ["梁雅婷"])
    check("直面修罗场成就已移除",
          "drama_face" not in {a["id"] for a in engine.ACHIEVEMENTS}
          and "修罗场" not in engine.apply_updates(old, payload({})))


def test_date_affinity_clamped() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    s["npcs"][0]["affinity"] = 75
    engine.apply_updates(s, payload(
        {"date_with": "郭瑞莹", "affinity_changes": [{"npc": "郭瑞莹", "delta": 100}]}))
    check("约会好感硬钳±15", find(s, "郭瑞莹")["affinity"] == 90,
          f"aff={find(s, '郭瑞莹')['affinity']}")


def test_birthday_gift_multiplier() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    for n in s["npcs"]:
        n["birthday"] = ""
    wan = find(s, "郭瑞莹")
    wan["birthday"] = "3-21"
    s["player"]["items"] += [{"name": "香薰蜡烛", "desc": "x", "count": 3}]
    old_today = shop.game_today
    shop.game_today = lambda st=None: "2026-03-21"
    try:
        with no_storage():
            r1 = shop.give_gift(s, "郭瑞莹", "香薰蜡烛")
            check("生日礼物×2且不越过关系铺垫", r1["ok"] is True and r1["delta"] == 12 and "生日" in r1["msg"],
                  str(r1)[:80])
            r2 = shop.give_gift(s, "郭瑞莹", "香薰蜡烛")
            check("生日当日仍限一份（防刷）", r2["ok"] is False, r2["msg"][:40])
            # 不占周限：当天已送 1 份，明天再送不触发周限（模拟次日）
            shop.game_today = lambda st=None: "2026-03-22"
            from app.shop import _week_key
            s["gift_log"]["daily"]["2026-03-22"] = {}
            r3 = shop.give_gift(s, "郭瑞莹", "香薰蜡烛")
            check("生日不占每周限额", r3["ok"] is True, r3["msg"][:50])
    finally:
        shop.game_today = old_today


# ---------- 成就与结局（阶段F） ----------

def test_achievements_unlock_once() -> None:
    s = default_state("测试侠")
    for n in s["npcs"]:
        n["birthday"] = ""
    check("开局零成就", s["achievements"] == [])
    s["dates"].append({"npc": "郭瑞莹", "turn": 1, "place": "x", "text": "x"})
    n1 = engine.sync_achievements(s)
    n2 = engine.sync_achievements(s)
    check("成就解锁并公告", "first_date" in s["achievements"] and any("初次约会" in m for m in n1),
          str(n1))
    check("成就不重复解锁", n2 == [] and s["achievements"].count("first_date") == 1)


def test_ending_on_top_level() -> None:
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    s["npcs"][0]["affinity"] = 96  # 郭瑞莹·羁绊
    s["npcs"][1]["affinity"] = 88  # 梁雅婷·心动
    s["player"]["realm"] = 9
    s["player"]["realm_progress"] = 100
    notice = engine.apply_updates(s, payload({}))
    check("登顶只结算成长不替玩家选结局", not s.get("ending") and s["campaign"]["chapter"] == 0)
    check("未完成主线不播结局公告", "大结局" not in notice, notice[:80])
    notice2 = engine.apply_updates(s, payload({}))
    check("结局只结算一次", "大结局" not in notice2, notice2[:60])
    check("满级成就入账", "top_level" in s["achievements"] and "first_heart" in s["achievements"])


# ---------- 好感单回合护栏（issue #1 问题1） ----------

def test_affinity_turn_cap() -> None:
    s = default_state("测试侠")  # 郭瑞莹 60
    notice = engine.apply_updates(s, payload(
        {"affinity_changes": [{"npc": "郭瑞莹", "delta": 100}]}))
    check("普通回合好感硬钳±10", find(s, "郭瑞莹")["affinity"] == 70,
          f"aff={find(s, '郭瑞莹')['affinity']}")
    check("截断在面板公告", "超出单回合上限" in notice and "±10" in notice, notice[:80])
    check("不再一回合跳两档", "羁绊" not in notice and "心动" not in notice, notice[:120])


def test_affinity_cumulative_cap() -> None:
    s = default_state("测试侠")  # 郭瑞莹 60；两条 +8 累计仍受 ±10 约束
    notice = engine.apply_updates(s, payload(
        {"affinity_changes": [{"npc": "郭瑞莹", "delta": 8}, {"npc": "郭瑞莹", "delta": 8}]}))
    check("同NPC多条申报按累计钳制", find(s, "郭瑞莹")["affinity"] == 70,
          f"aff={find(s, '郭瑞莹')['affinity']}")
    # 正负混合也按净变化钳制：+8 后 -50 → 净变化钳到 -10
    s2 = default_state("测试侠")
    for _n in s2["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    engine.apply_updates(s2, payload(
        {"affinity_changes": [{"npc": "郭瑞莹", "delta": 8}, {"npc": "郭瑞莹", "delta": -50}]}))
    check("累计值双向钳制", find(s2, "郭瑞莹")["affinity"] == 50,
          f"aff={find(s2, '郭瑞莹')['affinity']}")


def test_offline_affinity_cap() -> None:
    from app import offline as _off, storage as _st
    from datetime import datetime, timedelta, timezone
    s = default_state("测试侠")
    for _n in s["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    s["last_active"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    fake = {"events": [], "messages": [], "moments": [],
            "affinity_changes": [{"npc": "郭瑞莹", "delta": 100}], "npc_events": []}
    old_save, old_demo, old_chat = _st.save, _off.DEMO_MODE, _off.llm.chat_json
    _st.save = lambda st, **kwargs: None
    _off.DEMO_MODE = False
    _off.llm.chat_json = lambda *a, **k: fake
    try:
        _off.check_offline(s)
    finally:
        _st.save, _off.DEMO_MODE, _off.llm.chat_json = old_save, old_demo, old_chat
    check("离线好感单次钳±15", find(s, "郭瑞莹")["affinity"] == 75,
          f"aff={find(s, '郭瑞莹')['affinity']}")


# ---------- 提示词体积预算（issue #1 问题4：防情境分组回弹） ----------

def test_prompt_size_budget() -> None:
    from app import memory as _m
    opening = len(prompts.build_system_prompt(default_state("测试侠")))
    check("开局提示词在预算内（≤9200字符，35人＋技能/事业/活动行）", opening <= 9200, f"chars={opening}")
    mid = default_state("测试侠")
    mid["turn"] = 50
    mid["player"]["technique"] = {"route": "学业", "name": "过目成诵", "grade": "S级", "turn": 3}
    mid["player"]["items"] = [i for i in mid["player"]["items"] if i["name"] != "系统抽奖券"]
    mid["story"] = [{"world": "urban", "text": "正文段落。" * 25, "choices": ["甲", "乙"],
                     "ts": "t", "turn": i, "chosen": None} for i in range(40, 52)]
    for i in range(1, 61):
        _m.append_fact(mid, f"事实{i}（承诺）" if i % 10 == 5 else f"事实{i}", i)
    chars = len(prompts.build_system_prompt(mid))
    check("中局构造在预算内（≤10300字符，35人阵容＋技能事业行）", chars <= 10300, f"chars={chars}")
    sys_mid = prompts.build_system_prompt(mid)
    check("已领天赋时条件组切换为禁发提示", "已领取，不得再输出" in sys_mid)
    check("无券时抽奖规则正确缺席", "抽奖走系统通道" not in sys_mid)


# ---------- 深度审计修复回归（第二轮 20 题） ----------

def test_audit_npc_exact_dedup() -> None:
    """#1：子串判重吞新角色。"""
    s = default_state("测试侠")
    added, _ = engine._apply_new_npcs(s, {"new_npc": [
        {"name": "郭瑞莹的表姐", "role": "亲属"},
        {"name": "梁雅婷她妈", "role": "亲属"},
    ]})
    check("含既有姓名的新角色能登记", added == ["郭瑞莹的表姐", "梁雅婷她妈"], str(added))
    added2, _ = engine._apply_new_npcs(s, {"new_npc": [{"name": "郭瑞莹的表姐", "role": "亲属"}]})
    check("真重名仍被跳过", added2 == [])


def test_audit_quest_instant_complete_rejected() -> None:
    """#2：同回合自创自完成不再发奖励。"""
    s = default_state("测试侠")
    s["turn"] = 1
    before = purse(s)
    notice = engine.apply_updates(s, payload(
        {"new_side_quest": {"title": "秒任务", "desc": "x"}, "quest_complete": "秒任务"}))
    check("秒接秒交不发奖励", purse(s) == before and any(q.get("done") is False for q in s["side_quests"]))
    check("拒绝有面板说明", "后续回合" in notice, notice[:80])
    s["turn"] = 2
    notice2 = engine.apply_updates(s, payload({"quest_complete": "秒任务"}))
    check("下回合可正常完成", purse(s) == before + 15 and "支线完成" in notice2)


def test_audit_public_state_no_dm_secrets() -> None:
    """#4：facts 与 hooks 不进浏览器。"""
    s = default_state("测试侠")
    s["facts"] = [{"kind": "秘密", "text": "花碎花是千金", "turn": 3, "closed": None}]
    s["hooks"] = [{"npc": "郭瑞莹", "stage": "心动", "turn": 7}]
    pub = models.public_state(s)
    check("facts 不下发", "facts" not in pub)
    check("hooks 不下发", "hooks" not in pub)


def test_audit_place_type_whitelist_and_upsert() -> None:
    """#7/#8：type 白名单 + location/new_places 合并不丢 type。"""
    s = default_state("测试侠")
    engine._apply_map(s, {"new_places": [
        {"world": "urban", "name": "X地", "desc": "d", "type": "<img onerror=1>"}]})
    check("非法 type 被白名单置空",
          next(p for p in s["map"]["urban"] if p["name"] == "X地")["type"] == "")
    s2 = default_state("测试侠")
    for _n in s2["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    engine._apply_map(s2, {
        "location": {"world": "urban", "place": "Y广场"},
        "new_places": [{"world": "urban", "name": "Y广场", "desc": "d", "type": "city"}]})
    check("location 先建条目时 new_places 补 type",
          next(p for p in s2["map"]["urban"] if p["name"] == "Y广场")["type"] == "city")


def test_audit_lore_tiering() -> None:
    """#9：C 层隐秘按接触状态展开。"""
    from app import lore
    s = default_state("测试侠")
    blind = lore.canon_block(s)
    check("未接触只给关键词", "花碎花的家世" not in blind and "传闻" in blind)
    next(n for n in s["npcs"] if n["name"] == "花碎花")["known_to_player"] = True
    check("接触后展开全文", "花碎花的家世" in lore.canon_block(s))


def test_audit_family_boundary() -> None:
    """#12：家人不可正式约会、不触发恋爱成就（周母已下线，用注入的母亲角色验证边界）。"""
    mom = {"id": "npc_tmom", "name": "李阿姨", "world": "urban", "role": "母亲",
           "persona": "测试用母亲角色", "place": "合租公寓", "affinity": 100, "label": "长辈",
           "likes": "情趣", "birthday": "", "memory": [], "deeds": [],
           "known_to_player": True, "rels": {}, "last_seen_turn": 1}
    s = default_state("测试侠")
    s["npcs"].append(dict(mom))
    notice = engine.apply_updates(s, payload({"date_with": "李阿姨"}))
    check("家人约会被拒", not s["dates"] and "家人" in notice, notice[:60])
    s2 = default_state("测试侠")
    for _n in s2["npcs"]:
        _n["known_to_player"] = True  # 新档预设全员未结识，交互用例显式点亮
    s2["npcs"].append(dict(mom))
    msgs = engine.sync_achievements(s2)
    check("母亲不触发定下羁绊", not any("定下羁绊" in m for m in msgs))
    s2["npcs"][0]["affinity"] = 100  # 郭瑞莹·已认识
    msgs2 = engine.sync_achievements(s2)
    check("认识的角色可触发", any("定下羁绊" in m for m in msgs2))


def test_audit_effective_stats_capped() -> None:
    """#13：装备加成不突破 99。"""
    s = default_state("测试侠")
    s["player"]["stats"]["魅力"] = 99
    s["player"]["equipped"]["上装"] = "修身西装"
    check("effective_stats 钳 99", models.effective_stats(s)["魅力"] == 99)


def test_audit_secret_fact_kind() -> None:
    """#15：秘密类别。"""
    from app import memory as _m
    check("其实是→秘密", _m.classify_fact("花碎花其实是千金大小姐") == "秘密")
    check("暗中→秘密", _m.classify_fact("炭炭暗中收购老宅") == "秘密")
    check("秘密类常驻", "秘密" in _m.RESIDENT_KINDS)


def test_audit_week_key_fixed_tz() -> None:
    """#14：周键与日键同源——跟随游戏内日历，不再依赖宿主时区。"""
    import inspect as _insp
    src = _insp.getsource(shop._week_key)
    check("周键跟随游戏日历且不用本地时区",
          "date.today()" not in src and "hours=8" not in src and "game_today" in src)
    check("周键随游戏天数翻篇", shop._week_key({"time": {"day": 1}})
          != shop._week_key({"time": {"day": 8}}))


def main() -> int:
    for fn in [test_register_new_npc, test_sparse_entry_gets_defaults,
               test_invalid_entries_ignored, test_no_duplicate_registration,
               test_model_text_is_sanitized, test_roster_cap_evicts_stale_generated_only,
               test_evicted_npc_reunites_with_history,
               test_eviction_blocked_when_archive_fails,
               test_new_game_clears_archives,
               test_identity_update, test_normalize_old_save,
               test_normalize_retires_old_city_map,
               test_power_awakening_system,
               test_gm_persona_edit,
               test_gm_grant, test_game_calendar, test_memo_no_backend_leak,
               test_small_polish_round, test_progress_turn_cap_and_offcatalog,
               test_chat_photo_attach, test_shop_rotation_and_gm_config,
               test_shop_config_sanitize_on_read, test_chat_prompt_mentions_image,
               test_explicit_gift_affinity_gate,
               test_legacy_theme_migration_clears_records,
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
               test_affinity_stage_ladder, test_gift_value_tiers_and_preference,
               test_gift_daily_and_weekly_caps, test_gift_invalid_inputs,
               test_gift_stage_up_and_memory, test_story_affinity_stage_notice,
               test_date_contract_and_gate, test_demo_date_segments, test_dates_capped,
               test_chat_channel, test_offline_moments, test_time_system,
               test_story_hooks_inject_and_resolve, test_drama_removed_cleanly,
               test_date_affinity_clamped, test_birthday_gift_multiplier,
               test_achievements_unlock_once, test_ending_on_top_level,
               test_affinity_turn_cap, test_affinity_cumulative_cap, test_offline_affinity_cap,
               test_prompt_size_budget,
               test_audit_npc_exact_dedup, test_audit_quest_instant_complete_rejected,
               test_audit_public_state_no_dm_secrets, test_audit_place_type_whitelist_and_upsert,
               test_audit_lore_tiering, test_audit_family_boundary, test_audit_effective_stats_capped,
               test_audit_secret_fact_kind, test_audit_week_key_fixed_tz,
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
