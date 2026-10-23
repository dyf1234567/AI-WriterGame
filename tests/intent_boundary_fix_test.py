"""Player questions cannot authorize transactions or fulfill promises; no model calls."""
import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_BASE_URL="", LLM_API_KEY="", LLM_MODEL="")
os.environ.setdefault("SJL_DATA_DIR", str(ROOT / "artifacts" / "intent-boundary-tests"))
_exists = Path.exists


def without_env(path):
    return False if path == ROOT / ".env" else _exists(path)


with patch.object(Path, "exists", without_env):
    from app import actions, engine, memory, storage
    from app.economy import balance
    from app.models import default_state


def response(updates=None, text="你把问题问清楚，暂时没有办理任何事。"):
    return {"story_text": text, "narration_world": "urban",
            "choices": ["核对条件", "先做别的事"], "state_updates": updates or {}}


class IntentBoundaries(unittest.TestCase):
    def run_turn(self, text, updates=None, state=None, story=None):
        state = state or default_state("选择边界")
        original = deepcopy(state)
        data = response(updates, story) if story else response(updates)
        with patch.object(storage, "save"), patch.object(engine, "DEMO_MODE", False), patch.object(
            engine, "_call_llm_json", return_value=data
        ):
            final, notice = engine.take_turn(state, text)
        self.assertEqual(state, original, "take_turn must not mutate its input")
        return final, notice

    def assert_no_company(self, text, updates=None):
        initial = default_state("选择边界")
        final, notice = self.run_turn(text, updates, state=initial)
        self.assertEqual(balance(final), balance(initial))
        self.assertFalse(final["player"].get("enterprises"))
        return final, notice

    def test_deliberation_never_spends_cash_or_creates_a_company(self):
        for text in ("我要不要创办一家星河工作室", "我该不该成立一家星河公司",
                     "应不应该注册一家星河公司", "我要不要创办一家星河公司好吗"):
            with self.subTest(text=text):
                self.assertTrue(actions._not_an_order(text))
                self.assert_no_company(text)

    def test_unverified_conditions_do_not_execute_the_main_clause(self):
        for text in ("如果账户有十万元就创办一家星河公司", "要是郭瑞莹同意就成立星河公司",
                     "只要账户有钱就注册星河公司", "假如价格合适便创办星河工作室"):
            with self.subTest(text=text):
                self.assert_no_company(text)

    def test_negation_survives_polite_endings(self):
        for text in ("不要创办星河公司好吗", "先别注册星河公司行不行", "暂不成立星河公司嘛"):
            with self.subTest(text=text):
                self.assert_no_company(text)

    def test_ability_questions_do_not_become_commands(self):
        for text in ("我能不能创办星河公司", "可不可以注册一家星河公司",
                     "是否该成立星河工作室", "成立星河公司需要什么"):
            with self.subTest(text=text):
                self.assert_no_company(text)

    def test_explicit_polite_order_still_executes_without_a_model(self):
        for text in ("创办一家星河工作室好吗", "创办一家星河工作室行不行", "创办一家星河工作室"):
            with self.subTest(text=text), patch.object(storage, "save"), patch.object(
                engine, "_call_llm_json", side_effect=AssertionError("structured action called model")
            ):
                final, _ = engine.take_turn(default_state("明确选择"), text)
                self.assertEqual(balance(final), 0)
                self.assertEqual(final["player"]["enterprises"][0]["name"], "星河工作室")

    def test_mistaken_model_proposal_on_question_is_discarded_without_failing_turn(self):
        final, notice = self.assert_no_company("创办星河公司需要什么？", {
            "action_request": {"kind": "career", "command": "创办 星河公司"}})
        self.assertEqual(final["turn"], 1)
        self.assertIn("只是在询问", notice)

    def test_structured_prefix_does_not_override_an_explicit_question(self):
        self.assert_no_company("【事业】创办 星河公司？")

    def test_date_button_compensation_cannot_turn_an_inquiry_into_a_date(self):
        state = default_state("邀约边界")
        npc = state["npcs"][0]
        npc.update(known_to_player=True)
        final, _ = self.run_turn("【约会】邀请郭瑞莹来约会需要什么？", state=state,
                                 story="郭瑞莹点头答应了正式约会。")
        self.assertFalse(final.get("dates"))

    def test_question_cannot_resolve_an_unfulfilled_promise(self):
        state = default_state("履约边界")
        state["turn"] = 5
        memory.append_fact(state, "答应梁雅婷归还蓝色相机", 2, known_by=["梁雅婷"])
        final, notice = self.run_turn("归还蓝色相机需要什么？", {"fact_resolved": "归还蓝色相机"}, state,
                                      "你只问还相机要注意什么，并没有归还。")
        self.assertIsNone(memory.all_facts(final)[0]["closed"])
        self.assertNotIn("事实了结", notice)

    def test_question_does_not_complete_its_linked_appointment(self):
        state = default_state("履约边界")
        text = "玩家答应梁雅婷明晚归还蓝色相机"
        memory.append_fact(state, text, 0, kind="承诺", known_by=["梁雅婷"])
        state["appointments"] = [{"npc": "梁雅婷", "text": "明晚归还蓝色相机", "turn": 0,
                                  "status": "pending", "fact_text": text}]
        final, _ = self.run_turn("归还蓝色相机要注意什么？", {"fact_resolved": "归还蓝色相机"}, state)
        self.assertEqual(final["appointments"][0]["status"], "pending")

    def test_real_dialogue_facts_are_retained_during_a_question(self):
        fact = "你向梁雅婷询问蓝色相机的使用方法"
        final, _ = self.run_turn("蓝色相机怎么使用？", {"fact_record": fact, "scene_npcs": ["梁雅婷"]},
                                 story="你向梁雅婷询问蓝色相机的使用方法，她给你说明按钮的用途。")
        self.assertTrue(any(f["text"] == fact for f in memory.all_facts(final)))

    def test_actual_fulfillment_on_explicit_action_can_still_resolve_a_promise(self):
        state = default_state("履约边界")
        memory.append_fact(state, "答应梁雅婷归还蓝色相机", 0, known_by=["梁雅婷"])
        final, _ = self.run_turn("把蓝色相机还给梁雅婷", {"fact_resolved": "归还蓝色相机"}, state,
                                 "你把蓝色相机交还梁雅婷，她检查完后收进相机包。")
        self.assertIsNotNone(memory.all_facts(final)[0]["closed"])

    def test_asking_for_advice_can_keep_actual_skill_progress(self):
        final, _ = self.run_turn("怎么提升声乐？", {
            "skill_progress": [{"skill": "vocal", "xp": 5, "reason": "听完示范后练了呼吸"}]})
        self.assertIn("vocal", final["player"].get("skills", {}))


if __name__ == "__main__":
    unittest.main()
