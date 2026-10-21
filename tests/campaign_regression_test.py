"""主线与终章的隔离验收：真实 API 流程、分支后果与旧存档兼容。"""
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TEST_ROOT = ROOT / "artifacts" / "campaign-temp"
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.update(LLM_BASE_URL="", LLM_API_KEY="", LLM_MODEL="")
_exists = Path.exists
with patch.object(Path, "exists", lambda path: False if path == ROOT / ".env" else _exists(path)):
    from app import campaign, config, engine, memory, models, shop, storage
    from app.main import app
from fastapi.testclient import TestClient


class CampaignRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="run-", dir=TEST_ROOT)
        self.directory = Path(self.temp.name)
        self.patches = []
        for module in (config, storage, memory, engine, shop):
            for attr, relative in {
                "DATA_DIR": ".", "STATE_FILE": "state.json", "STORY_ARCHIVE_FILE": "story_archive.jsonl",
                "NPC_ARCHIVE_FILE": "npc_archive.jsonl", "MEMORY_MANUAL_FILE": "memory/manual.md",
                "MEMORY_STATUS_FILE": "memory/status.json", "SHOP_CONFIG_FILE": "shop_config.json",
            }.items():
                if hasattr(module, attr):
                    item = patch.object(module, attr, self.directory / relative)
                    item.start()
                    self.patches.append(item)
        self.no_model = patch.object(engine.llm, "chat_json", side_effect=AssertionError("不允许调用模型"))
        self.no_model.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.no_model.stop()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def new(self):
        response = self.client.post("/api/new", json={"name": "主线验收"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["state"]

    def act(self, action_id, state):
        response = self.client.post("/api/act", json={"text": campaign.PREFIX + action_id},
                                    headers={"X-State-Revision": str(state["revision"])})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["state"]

    def path(self, route="音乐", name="梁雅婷", approach="skill", conflict="promise", show="bold", resolution="honest"):
        return [f"plan:{route}", f"team:{name}"] + [f"prepare:{approach}"] * 3 + [
            f"conflict:{conflict}", f"present:{show}", f"resolve:{resolution}", "review"]

    def test_full_api_path_has_real_evidence_and_explicit_partner_choice(self):
        state = self.new()
        self.assertEqual(state["campaign"]["chapter"], 0)
        self.assertEqual(len(state["campaign"]["actions"]), 6)
        for action_id in self.path():
            state = self.act(action_id, state)
            self.assertNotIn("ending", state)
        self.assertTrue(state["campaign"]["finale_ready"])
        self.assertEqual(state["time"]["day"], 120)
        self.assertGreaterEqual(len(state["campaign"]["evidence"]), 9)
        self.assertIn("梁雅婷", {o["name"] for o in state["ending_options"]})
        response = self.client.post("/api/ending", json={"partner": "梁雅婷"},
                                    headers={"X-State-Revision": str(state["revision"])})
        self.assertEqual(response.status_code, 200, response.text)
        state = response.json()["state"]
        self.assertTrue(response.json()["result"]["ok"])
        self.assertEqual(state["ending"]["partner"], "梁雅婷")
        self.assertIn("原创音乐演出", state["ending"]["text"])
        self.assertIn("少一轮打磨", state["ending"]["text"])
        self.assertIn("守约的代价", state["ending"]["text"])
        self.assertNotIn("补上了那次约定", state["ending"]["text"])
        self.assertIn("大一学生", state["ending"]["text"])
        self.assertNotIn("毕业季", state["ending"]["title"])
        self.assertEqual(state["story"][-1]["text"], state["ending"]["text"])
        self.assertFalse(state["campaign"]["finale_ready"])
        self.assertEqual(next(n for n in state["npcs"] if n["name"] == "梁雅婷")["relationship_status"], "恋人")
        old = storage.STATE_FILE.read_bytes()
        again = self.client.post("/api/ending", json={"partner": None})
        self.assertFalse(again.json()["result"]["ok"])
        self.assertEqual(old, storage.STATE_FILE.read_bytes())

    def test_invalid_skip_and_invalid_partner_do_not_change_save(self):
        state = self.new()
        old = storage.STATE_FILE.read_bytes()
        response = self.client.post("/api/act", json={"text": "【主线】review"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(old, storage.STATE_FILE.read_bytes())
        ending = self.client.post("/api/ending", json={"partner": "郭瑞莹"})
        self.assertFalse(ending.json()["result"]["ok"])
        self.assertEqual(old, storage.STATE_FILE.read_bytes())
        self.assertEqual(self.client.post("/api/ending", json={}).status_code, 422)
        for action_id in self.path():
            state = self.act(action_id, state)
        old = storage.STATE_FILE.read_bytes()
        response = self.client.post("/api/ending", json={"partner": "未相识的人"})
        self.assertFalse(response.json()["result"]["ok"])
        self.assertEqual(old, storage.STATE_FILE.read_bytes())

    def test_level_and_model_claim_cannot_skip_story(self):
        state = models.default_state("成长不跳章")
        state["player"].update(realm=9, realm_progress=100)
        with patch.object(storage, "save"), patch.object(engine, "maybe_compact", return_value=""):
            state, _ = engine.take_turn(state, "训练")
        self.assertEqual(state["player"]["realm"], 10)
        self.assertEqual(state["campaign"]["chapter"], 0)
        self.assertIsNone(state.get("ending"))
        self.assertFalse(campaign.choose_ending(state, None)["ok"])
        self.assertIn("top_level", state["achievements"])

    def test_all_six_routes_have_completable_solo_ending(self):
        for route in campaign.ROUTES:
            with self.subTest(route=route):
                state = models.default_state(route)
                with patch.object(storage, "save"), patch.object(engine, "maybe_compact", return_value=""):
                    for action_id in self.path(route=route, name="郭瑞莹", approach="team", show="steady"):
                        state, _ = engine.take_turn(state, campaign.PREFIX + action_id)
                self.assertTrue(campaign.campaign_view(state)["finale_ready"])
                self.assertTrue(campaign.choose_ending(state, None)["ok"])
                self.assertIn(campaign.ROUTES[route][0], state["ending"]["text"])
                self.assertIsNone(state["ending"]["partner"])
                self.assertEqual(state["time"]["day"], 120)

    def test_bold_low_skill_has_recoverable_distinct_result_and_personal_arc(self):
        state = models.default_state("不同后果")
        with patch.object(storage, "save"), patch.object(engine, "maybe_compact", return_value=""):
            for action_id in self.path(route="摄影", name="邓碧瑶", approach="team", conflict="promise", resolution="future"):
                state, _ = engine.take_turn(state, campaign.PREFIX + action_id)
        self.assertIn("现场失误", state["campaign"]["show_result"])
        self.assertTrue(next(n for n in state["npcs"] if n["name"] == "邓碧瑶")["project_arc_complete"])
        self.assertTrue(campaign.choose_ending(state, None)["ok"])
        self.assertIn("未来的打算", state["ending"]["text"])
        self.assertIn("远程回顾会", state["ending"]["text"])

    def test_old_save_keeps_progress_and_existing_ending(self):
        state = models.default_state("旧档")
        state.pop("campaign")
        state["player"].update(realm=8, realm_progress=73)
        models.normalize_state(state)
        self.assertEqual(state["player"]["realm"], 8)
        self.assertEqual(state["player"]["realm_progress"], 73)
        self.assertEqual(state["campaign"]["chapter"], 0)
        state.pop("campaign")
        state["ending"] = {"title": "旧周目的结局", "partner": "郭瑞莹"}
        models.normalize_state(state)
        self.assertEqual(state["campaign"]["chapter"], 5)
        self.assertEqual(state["ending"]["title"], "旧周目的结局")
        self.assertEqual(campaign.ending_options(state), [])
        self.assertFalse(campaign.choose_ending(state, None)["ok"])

    def test_public_feedback_reveals_only_shared_memory_and_real_roster_size(self):
        state = models.default_state("心声边界")
        npc = state["npcs"][0]
        npc.update(known_to_player=True, memory=["幕后：不可见的秘密", "第3回合：共同排练了一首歌"])
        state["power"].update(awakened=True, stage=3)
        result = models.public_state(state)
        self.assertEqual(result["npc_total"], 35)
        self.assertIn("共同排练", result["npcs"][0]["heart_voice"])
        self.assertNotIn("不可见", result["npcs"][0]["heart_voice"])
        self.assertNotIn("facts", result)
        self.assertNotIn("hooks", result)

    def test_missing_prerequisite_in_old_campaign_recovers_to_available_action(self):
        state = models.default_state("修复不完整旧档")
        state["campaign"].update(route="音乐", chapter=4, companion="已经离场的人", preparations=3)
        models.normalize_state(state)
        view = campaign.campaign_view(state)
        self.assertEqual(view["chapter"], 1)
        self.assertTrue(all(a["id"].startswith("team:") for a in view["actions"]))

    def test_late_start_uses_relative_calendar_and_fulfilled_promise_is_closed(self):
        state = models.default_state("晚些开始")
        state["time"].update(day=90, slot=0)
        with patch.object(storage, "save"), patch.object(engine, "maybe_compact", return_value=""):
            for action_id in self.path()[:6]:
                state, _ = engine.take_turn(state, campaign.PREFIX + action_id)
            original = [f for f in state["facts"] if "与梁雅婷的星河计划约定" in f["text"]]
            self.assertEqual(len(original), 1)
            self.assertIsNotNone(original[0]["closed"])
            self.assertGreaterEqual(state["time"]["day"], 131)
            self.assertNotIn("第六周", state["story"][-1]["text"])
            for action_id in self.path()[6:]:
                state, _ = engine.take_turn(state, campaign.PREFIX + action_id)
        self.assertEqual(state["time"]["day"], 209)
        self.assertTrue(campaign.choose_ending(state, None)["ok"])
        self.assertTrue(all("【主线】" not in (seg.get("chosen") or "") for seg in state["story"]))

    def test_demo_opening_choice_and_post_ending_continue_the_same_story(self):
        state = models.default_state("连续体验")
        with patch.object(storage, "save"), patch.object(engine, "maybe_compact", return_value=""):
            state, _ = engine.take_turn(state, "跑过去和梁雅婷一起排队办手续")
            self.assertIn("手续已经办好", state["story"][-1]["text"])
            self.assertNotIn("第二天清晨", state["story"][-1]["text"])
            for action_id in self.path():
                state, _ = engine.take_turn(state, campaign.PREFIX + action_id)
            self.assertTrue(campaign.choose_ending(state, "梁雅婷")["ok"])
            state, _ = engine.take_turn(state, "和熟悉的人聊聊假期打算")
        self.assertIn("梁雅婷", state["story"][-1]["text"])
        self.assertIn("已经是你认真确认过关系的人", state["story"][-1]["text"])

    def test_zero_gain_placeholders_do_not_create_items(self):
        state = models.default_state("零数量")
        before = deepcopy(state["player"]["items"])
        data = {"story_text": "今天只是看看校园。", "narration_world": "urban", "choices": ["继续", "休息"],
                "state_updates": {"item_gained": [{"name": "系统金币", "count": 0}, {"name": "专注咖啡", "count": 0}]}}
        engine.apply_updates(state, data)
        self.assertEqual(state["player"]["items"], before)

    def test_demo_piano_shop_introduces_side_quest_before_coffee_completion(self):
        state = models.default_state("支线衔接")
        with patch.object(storage, "save"), patch.object(engine, "maybe_compact", return_value=""):
            state, _ = engine.take_turn(state, "今晚再去老街琴行附近走走")
            self.assertTrue(any(q["title"] == "周六的咖啡馆" and not q["done"] for q in state["side_quests"]))
            state, _ = engine.take_turn(state, "答应她：周六老街咖啡馆见")
            self.assertTrue(any(q["title"] == "周六的咖啡馆" and q["done"] for q in state["side_quests"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
