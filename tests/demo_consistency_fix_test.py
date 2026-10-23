"""Offline demo actions must agree with intent, relationship gates and game time."""
import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_BASE_URL="", LLM_API_KEY="", LLM_MODEL="")
_exists = Path.exists
with patch.object(Path, "exists", lambda p: False if p == ROOT / ".env" else _exists(p)):
    from app import demo, engine, life_clock
    from app.contracts import validate_turn
    from app.models import default_state, game_today, time_label


class DemoConsistencyFix(unittest.TestCase):
    def fresh(self):
        state = default_state("离线验收")
        state["player"]["technique"] = {"name": "已有天赋", "route": "学业"}
        npc = next(n for n in state["npcs"] if n["name"] == "郭瑞莹")
        npc.update(known_to_player=True)
        return state

    def act(self, state, action):
        with patch.object(engine, "DEMO_MODE", True), patch.object(engine.storage, "save"), \
                patch.object(engine.llm, "chat_json", side_effect=AssertionError("No model")):
            return engine.take_turn(state, action)

    def person(self, state):
        return next(n for n in state["npcs"] if n["name"] == "郭瑞莹")

    def test_shop_inquiries_do_not_execute_the_named_event(self):
        for question in ("郭瑞莹提过的琴行叫什么？我只是问问。", "老街咖啡馆在哪里？",
                         "我不要去琴行", "如果有空就去咖啡馆", "约会需要什么条件？"):
            with self.subTest(question=question):
                before = self.fresh()
                state, _ = self.act(before, question)
                self.assertEqual(state["player"]["location"], before["player"]["location"])
                self.assertEqual(state["player"]["items"], before["player"]["items"])
                self.assertEqual(state["side_quests"], before["side_quests"])
                self.assertFalse(state["dates"])
                self.assertNotIn("热牛奶", state["story"][-1]["text"])
                self.assertNotIn("已存入回忆", state["story"][-1]["text"])

    def test_questioning_talent_does_not_claim_it_was_granted(self):
        state = self.fresh()
        state["player"]["technique"] = None
        result = demo.next_segment(state, "学业路线的天赋是什么？")
        self.assertFalse(result["state_updates"].get("technique_grant"))
        self.assertNotIn("初始天赋发放中", result["story_text"])

    def test_incidental_shop_mentions_do_not_start_a_visit(self):
        state = self.fresh()
        for action in ("郭瑞莹去年买过琴行里的琴", "想起老街咖啡馆的活动单"):
            result = demo.next_segment(state, action)
            self.assertEqual(result["state_updates"].get("location"), state["player"]["location"])
            self.assertFalse(result["state_updates"].get("new_side_quest"))
            self.assertFalse(result["state_updates"].get("quest_complete"))

    def test_date_checks_all_relationship_gates_before_any_move_or_reward(self):
        for field, value in (("known_to_player", False), ("role", "母亲")):
            with self.subTest(field=field):
                state = self.fresh()
                npc = self.person(state)
                npc[field] = value
                before = deepcopy(state)
                updated, _ = self.act(state, "【约会】邀请郭瑞莹来约会")
                self.assertFalse(updated["dates"])
                self.assertEqual(updated["player"]["location"], before["player"]["location"])
                self.assertNotIn("已存入回忆", updated["story"][-1]["text"])
                self.assertEqual(state, before)

    def test_valid_date_uses_arrival_clock_and_complete_duration(self):
        before = self.fresh()
        state, notice = self.act(before, "【约会】邀请郭瑞莹来约会")
        text = state["story"][-1]["text"]
        expected_arrival = deepcopy(before)
        life_clock.advance_minutes(expected_arrival, 240)
        self.assertIn(game_today(expected_arrival), text)
        self.assertIn(time_label(expected_arrival), text)
        self.assertIn("摩天轮", text)
        self.assertIn("星愿游乐园", text)
        for fixed in ("周六", "夜色", "最后一班", "灯海"):
            self.assertNotIn(fixed, text)
        self.assertEqual(life_clock.absolute_minute(state) - life_clock.absolute_minute(before), 360)
        self.assertEqual(len(state["dates"]), 1)
        self.assertIn("约会时刻", notice)
        self.assertNotIn("这一晚", notice)

    def test_date_crossing_midnight_has_the_correct_arrival_date(self):
        state = self.fresh()
        state["time"].update(day=1, slot=4, minute=1380, clock_day=1, clock_slot=4)
        expected = deepcopy(state)
        life_clock.advance_minutes(expected, 240)
        updated, _ = self.act(state, "【约会】邀请郭瑞莹来约会")
        self.assertIn(game_today(expected), updated["story"][-1]["text"])
        self.assertIn(time_label(expected), updated["story"][-1]["text"])

    def test_date_without_travel_funds_stays_a_plan(self):
        state = self.fresh()
        from app.economy import debit, balance
        debit(state, balance(state))
        updated, _ = self.act(state, "【约会】邀请郭瑞莹来约会")
        self.assertFalse(updated["dates"])
        self.assertEqual(updated["player"]["location"], state["player"]["location"])
        self.assertIn("旅费", updated["story"][-1]["text"])

    def test_local_person_is_not_forced_into_the_magic_city_template(self):
        state = self.fresh()
        npc = self.person(state)
        npc["place"] = "京华大学"
        updated, _ = self.act(state, "【约会】邀请郭瑞莹来约会")
        self.assertEqual(updated["player"]["location"]["city"], "京都")
        self.assertIn("京华大学", updated["story"][-1]["text"])
        self.assertNotIn("魔都", updated["story"][-1]["text"])
        self.assertEqual(len(updated["dates"]), 1)

    def test_shop_activity_keeps_proposal_and_attendance_separate(self):
        state = self.fresh()
        state, _ = self.act(state, "去老街琴行附近走走")
        quest = next(q for q in state["side_quests"] if q["title"] == "周六的咖啡馆")
        self.assertFalse(quest["done"])
        self.assertNotIn("郭瑞莹", state["story"][-1]["text"])
        state, _ = self.act(state, "答应她：周六老街咖啡馆见")
        self.assertFalse(next(q for q in state["side_quests"] if q["title"] == quest["title"])["done"])
        state, _ = self.act(state, "前往老街咖啡馆了解活动")
        self.assertTrue(next(q for q in state["side_quests"] if q["title"] == quest["title"])["done"])

    def test_foreign_shop_keyword_cannot_transport_player_back_to_kyoto(self):
        state = self.fresh()
        state["player"]["location"] = {"world": "urban", "country": "东瀛", "city": "樱京", "place": "樱川录音室"}
        before = deepcopy(state)
        for action in ("去琴行看看", "前往老街咖啡馆赴约"):
            updated, _ = self.act(state, action)
            self.assertEqual(updated["player"]["location"], before["player"]["location"])
            self.assertFalse(updated["side_quests"])

    def test_existing_invitation_is_not_completed_without_the_companion(self):
        state = self.fresh()
        state["side_quests"] = [{"title": "周六的咖啡馆", "desc": "郭瑞莹约你去咖啡馆", "done": False}]
        updated, _ = self.act(state, "前往老街咖啡馆赴约")
        self.assertFalse(updated["side_quests"][0]["done"])
        self.assertIn("没有看见郭瑞莹", updated["story"][-1]["text"])

    def test_direct_demo_results_pass_the_shared_contract_without_mutating_state(self):
        state = self.fresh()
        before = deepcopy(state)
        for action in ("去老街琴行附近走走", "前往老街咖啡馆了解活动", "【约会】邀请郭瑞莹来约会"):
            validate_turn(demo.next_segment(state, action))
            self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
