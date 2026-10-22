"""玩法结算回归。独立临时目录，不读取 .env、不调用模型、不写正式存档。"""
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TEST_ROOT = ROOT / "artifacts" / "gameplay-temp"
TEST_ROOT.mkdir(parents=True, exist_ok=True)
TEMP = tempfile.TemporaryDirectory(prefix="run-", dir=TEST_ROOT)
os.environ.update(SJL_DATA_DIR=TEMP.name, LLM_BASE_URL="", LLM_API_KEY="", LLM_MODEL="")
_exists = Path.exists
with patch.object(Path, "exists", lambda path: False if path.name == ".env" else _exists(path)):
    from app import engine, models, offline, shop, storage


def payload(updates=None):
    return {"story_text": "在校园里度过了充实的一天。", "narration_world": "urban",
            "choices": ["继续准备", "休息片刻"], "state_updates": updates or {}, "system_notice": ""}


class GameplayRegressions(unittest.TestCase):
    def setUp(self):
        self.saved = patch.object(storage, "save")
        self.saved.start()
        self.addCleanup(self.saved.stop)
        self.state = models.default_state("玩法回归")
        self.state["turn"] = 1
        self.npc = self.state["npcs"][0]
        self.npc["known_to_player"] = True
        self.npc["birthday"] = ""

    def give(self, name, count=1):
        engine._apply_items(self.state, [{"name": name, "count": count}])

    def test_zero_spend_placeholder_never_charges_or_rejects(self):
        before = deepcopy(self.state["player"]["items"])
        engine.apply_updates(self.state, payload({"item_spent": [
            {"name": "系统金币", "count": 0}, {"name": "不存在的材料", "count": 0}]}))
        self.assertEqual(self.state["player"]["items"], before)

    def test_turn_aggregates_rewards_then_levels_once_and_checks_achievements(self):
        self.state["player"].update(realm=len(models.REALMS) - 2, realm_progress=95)
        self.state["side_quests"] = [{"title": "整理资料", "done": False, "added_turn": 0}]
        notice = engine.apply_updates(self.state, payload({"realm_progress_delta": 5,
                                                         "quest_complete": "整理资料"}))
        self.assertEqual(self.state["player"]["realm"], len(models.REALMS) - 1)
        self.assertEqual(self.state["player"]["realm_progress"], 0)
        self.assertIn("top_level", self.state["achievements"])
        self.assertIn("等级提升", notice)
        self.assertIsNone(self.state.get("ending"))

    def test_signin_and_item_use_sync_level_achievements(self):
        self.state["player"].update(realm=len(models.REALMS) - 2, realm_progress=95)
        with patch.object(engine.random, "choice", return_value={"type": "progress", "delta": 5, "label": "成长 +5"}):
            result = engine.sign_in(self.state)
        self.assertTrue(result["ok"])
        self.assertIn("top_level", self.state["achievements"])
        self.assertIsNone(self.state.get("ending"))
        second = models.default_state("道具回归")
        second["player"].update(realm=len(models.REALMS) - 2, realm_progress=95)
        engine._apply_items(second, [{"name": "专注咖啡"}])
        self.assertTrue(shop.use_item(second, "专注咖啡")["ok"])
        self.assertIn("top_level", second["achievements"])
        self.assertIsNone(second.get("ending"))

    def test_gift_and_negative_affinity_use_stage_hooks(self):
        self.npc["affinity"] = 24
        self.give("香薰蜡烛")
        result = shop.give_gift(self.state, self.npc["name"], "香薰蜡烛")
        self.assertTrue(result["ok"])
        self.assertTrue(any(h["npc"] == self.npc["name"] and h["stage"] == "熟识" for h in self.state["hooks"]))
        notice = " ".join(engine._apply_affinity(self.state, [{"npc": self.npc["name"], "delta": -10}]))
        self.assertIn("关系变化", notice)
        self.assertNotIn("升温", notice)
        self.assertFalse(any(h["npc"] == self.npc["name"] for h in self.state["hooks"]))

    def test_hook_done_consumes_only_one_event(self):
        self.state["hooks"] = [{"npc": self.npc["name"], "stage": "熟识", "turn": 0},
                               {"npc": self.npc["name"], "stage": "朋友", "turn": 1}]
        engine._resolve_hook(self.state, self.npc["name"])
        self.assertEqual([h["stage"] for h in self.state["hooks"]], ["朋友"])

    def test_birthday_exempts_full_week_but_never_maxes_relationship(self):
        today = models.game_today(self.state)
        week = shop._week_key(self.state)
        self.npc.update(affinity=4, birthday=today[5:], likes="特殊")
        self.state["gift_log"] = {"daily": {}, "weekly": {week: {self.npc["name"]: 2}}}
        self.give("时光胶卷", 2)
        result = shop.give_gift(self.state, self.npc["name"], "时光胶卷")
        self.assertTrue(result["ok"], result)
        self.assertLessEqual(result["delta"], 15)
        self.assertLessEqual(self.npc["affinity"], 19)
        self.assertFalse(shop.give_gift(self.state, self.npc["name"], "时光胶卷")["ok"])

    def test_demo_chat_keeps_explicit_promise_shared_without_farming_affinity(self):
        before = self.npc["affinity"]
        with patch.object(engine, "DEMO_MODE", True), patch.object(engine.random, "random", return_value=1):
            result = engine.send_chat(self.state, self.npc["name"], "我答应你，明天七点在图书馆见。")
            engine.send_chat(self.state, self.npc["name"], "今天天气很好")
        self.assertTrue(result["ok"])
        self.assertEqual(before, self.npc["affinity"])
        self.assertTrue(any(f["kind"] == "承诺" and "图书馆" in f["text"] for f in self.state["facts"]))
        self.assertTrue(any("短信：" in note and "图书馆" in note for note in self.npc["memory"]))
        self.assertEqual(self.state["appointments"][-1]["status"], "pending")
        self.assertEqual(len(self.state["facts"]), 1)

    def test_model_cannot_invent_player_promises_from_an_ordinary_chat(self):
        response = {"reply": "那说定明天我们去海边结婚。", "image": "", "memory": "玩家答应结婚",
                    "fact_record": "玩家答应明天结婚", "appointment": "明天海边结婚"}
        with patch.object(engine, "DEMO_MODE", False), patch.object(engine.llm, "chat_json", return_value=response):
            self.assertTrue(engine.send_chat(self.state, self.npc["name"], "你好")["ok"])
        self.assertEqual(self.state["facts"], [])
        self.assertFalse(self.state.get("appointments"))

    def test_important_disclosure_remembers_player_words_instead_of_model_additions(self):
        response = {"reply": "辛苦了，我会陪着你。", "memory": "妈妈住院了，承诺明天结婚",
                    "fact_record": "玩家承诺明天结婚"}
        with patch.object(engine, "DEMO_MODE", False), patch.object(engine.llm, "chat_json", return_value=response):
            self.assertTrue(engine.send_chat(self.state, self.npc["name"], "我妈妈昨天住院了，有些担心。")["ok"])
        fact = self.state["facts"][-1]
        self.assertIn("我妈妈昨天住院了", fact["text"])
        self.assertNotIn("结婚", fact["text"])
        self.assertEqual(fact["kind"], "事实")
        self.assertFalse(self.state.get("appointments"))

    def test_finale_notice_is_once_and_does_not_choose_for_player(self):
        # 自然完成主线，避免只改章节编号绕过其前置经历校验。
        for action in ("plan:学业", f"team:{self.npc['name']}", "prepare:skill", "prepare:team",
                       "prepare:skill", "conflict:promise", "present:steady", "resolve:honest", "review"):
            data = engine.campaign.before_turn(self.state, "【主线】" + action)
            engine.campaign.after_turn(self.state, data, "【主线】" + action)
        self.assertIn("终章已解锁", engine._maybe_ending(self.state))
        self.assertIsNone(engine._maybe_ending(self.state))
        self.assertIsNone(self.state.get("ending"))

    def test_sms_daily_bonus_uses_stage_hooks_and_real_offline_is_paused(self):
        self.npc["affinity"] = 24
        self.state["power"].update(awakened=True, stage=4)
        with patch.object(engine, "DEMO_MODE", True), patch.object(engine.random, "random", return_value=1):
            engine.send_chat(self.state, self.npc["name"], "你好")
            engine.send_chat(self.state, self.npc["name"], "今天还好吗")
        self.assertEqual(self.npc["affinity"], 25)
        self.assertTrue(any(h["stage"] == "熟识" for h in self.state["hooks"]))
        self.npc["affinity"] = 49
        before = deepcopy(self.state)
        with patch.object(offline, "_elapsed", return_value=48), \
                patch.object(engine.llm, "chat_json", side_effect=AssertionError("现实离线不得调用模型")):
            inbox = offline.check_offline(self.state)
        self.assertEqual(self.npc["affinity"], 49)
        self.assertEqual(self.state["time"], before["time"])
        self.assertEqual(self.state["hooks"], before["hooks"])
        self.assertEqual(inbox, [])

    def test_explicit_acceptance_uses_previous_invite_without_assuming_player_consent(self):
        engine._chat_append(self.state, self.npc["name"], "npc", "明天七点图书馆见，一起看资料好吗？")
        with patch.object(engine, "DEMO_MODE", True), patch.object(engine.random, "random", return_value=1):
            engine.send_chat(self.state, self.npc["name"], "好，明天见")
        self.assertEqual(self.state["appointments"][-1]["status"], "pending")
        self.assertTrue(any(f["kind"] == "承诺" and "图书馆" in f["text"] for f in self.state["facts"]))

    def test_questions_about_npc_promises_never_create_player_commitments(self):
        with patch.object(engine, "DEMO_MODE", True), patch.object(engine.random, "random", return_value=1):
            for text in ("你明天一定会来吗？", "你明天一定会来见我吗？", "我明天一定会去吗？", "你能保证明天一起自习吗？"):
                engine.send_chat(self.state, self.npc["name"], text)
        self.assertFalse(any(f["kind"] == "承诺" for f in self.state["facts"]))
        self.assertFalse(any(a["status"] == "pending" for a in self.state.get("appointments", [])))

    def test_resolved_sms_fact_completes_only_corresponding_appointment(self):
        with patch.object(engine, "DEMO_MODE", True), patch.object(engine.random, "random", return_value=1):
            engine.send_chat(self.state, self.npc["name"], "我答应你，明天七点在图书馆见。")
            engine.send_chat(self.state, self.npc["name"], "我答应你，后天九点在琴行见。")
        first, second = self.state["appointments"]
        engine.apply_updates(self.state, payload({"fact_resolved": first["fact_text"]}))
        self.assertEqual(first["status"], "done")
        self.assertEqual(second["status"], "pending")
        self.assertEqual(first["completed_turn"], self.state["turn"])

    def test_legacy_sms_appointment_resolves_by_its_exact_original_fact(self):
        with patch.object(engine, "DEMO_MODE", True), patch.object(engine.random, "random", return_value=1):
            engine.send_chat(self.state, self.npc["name"], "我明天一定会来图书馆见你。")
        appointment = self.state["appointments"][-1]
        original_fact = appointment.pop("fact_text")
        engine.apply_updates(self.state, payload({"fact_resolved": original_fact}))
        self.assertEqual(appointment["status"], "done")

    def test_courses_have_fair_value_and_matching_route_adds_deterministic_progress(self):
        catalog = shop.catalog_by_name()
        coffee_ratio = 5 / 20
        for goods in shop.SHOP_CATALOG:
            if goods.get("route") and goods.get("use", {}).get("progress"):
                self.assertGreaterEqual(goods["use"]["progress"] / goods["price"], coffee_ratio)
        self.state["player"]["technique"] = {"name": "测试天赋", "route": "音乐"}
        self.state["player"]["realm_progress"] = 0
        self.give("吉他进阶单曲课")
        result = shop.use_item(self.state, "吉他进阶单曲课")
        self.assertTrue(result["ok"])
        self.assertEqual(self.state["player"]["realm_progress"], 30)
        self.assertIn("同路线", result["msg"])

    def test_all_prize_exclusives_are_usable(self):
        for goods in shop.PRIZE_CATALOG:
            with self.subTest(prize=goods["name"]):
                self.give(goods["name"])
                self.assertTrue(shop.use_item(self.state, goods["name"])["ok"])


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        TEMP.cleanup()
