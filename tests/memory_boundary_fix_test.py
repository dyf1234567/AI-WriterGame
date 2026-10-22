"""事实公开、历史知情与重复约定的实际结算回归；仅使用内存状态。"""
import os
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_BASE_URL="", LLM_API_KEY="", LLM_MODEL="")
_read_text = Path.read_text


def _without_env(path, *args, **kwargs):
    return "" if path == ROOT / ".env" else _read_text(path, *args, **kwargs)


with patch.object(Path, "read_text", _without_env):
    from app import engine, life_clock, memory, models


def payload(text, **updates):
    return {"story_text": text, "state_updates": updates}


class MemoryBoundaryFixTests(unittest.TestCase):
    def fresh(self):
        return models.default_state("隔离记忆回归")

    def test_unrelated_news_does_not_publish_a_private_fact(self):
        state = self.fresh()
        secret = "玩家已经觉醒系统，此事从未告诉任何人"
        engine.apply_updates(state, payload(
            "我把系统觉醒的秘密藏在心底，从未告诉任何人。广场的屏幕正在新闻发布会直播。",
            fact_record=secret))
        self.assertEqual(state["facts"][-1]["scope"], "private")
        self.assertNotIn(secret, memory.facts_block(state, viewer="郭瑞莹", action="系统觉醒"))

    def test_structured_public_scope_still_requires_related_publication(self):
        state = self.fresh()
        secret = "父亲留下的蓝色存折藏在旧钢琴里"
        engine.apply_updates(state, payload(
            "你把存折的位置记在心里。广场新闻发布会宣布城市音乐节开幕。",
            fact_records=[{"text": secret, "scope": "public"}]))
        self.assertEqual(state["facts"][-1]["scope"], "private")

    def test_each_fact_gets_its_own_publication_evidence(self):
        state = self.fresh()
        public = "星河工作室正式成立"
        private = "蓝色存折藏在旧钢琴里"
        engine.apply_updates(state, payload(
            "你公开宣布：星河工作室正式成立。蓝色存折仍藏在旧钢琴里。",
            fact_record=[public, private]))
        self.assertEqual([fact["scope"] for fact in state["facts"]], ["public", "private"])
        block = memory.facts_block(state, viewer="郭瑞莹", action="星河工作室 蓝色存折")
        self.assertIn(public, block)
        self.assertNotIn(private, block)

    def test_negated_or_unrelated_same_sentence_publication_is_not_evidence(self):
        for text in ("你没有公开宣布蓝色存折的位置。",
                     "蓝色存折藏在旧钢琴里，你公开宣布音乐节开幕。",
                     "你公开宣布音乐节开幕，仍把蓝色存折藏在旧钢琴里。"):
            with self.subTest(text=text):
                self.assertFalse(engine._fact_is_published("蓝色存折藏在旧钢琴里", text))

    def test_publication_plans_and_questions_do_not_make_a_fact_public(self):
        for text in ("你打算公开宣布蓝色存折藏在旧钢琴里。",
                     "你计划等到下周的工作室会议开始后再公开宣布蓝色存折藏在旧钢琴里。",
                     "如果她同意，你公开宣布蓝色存折藏在旧钢琴里。",
                     "你公开宣布蓝色存折藏在旧钢琴里了吗？",
                     "你问她是否公开宣布蓝色存折藏在旧钢琴里。"):
            with self.subTest(text=text):
                self.assertFalse(engine._fact_is_published("蓝色存折藏在旧钢琴里", text))

    def test_related_moments_post_can_be_public(self):
        self.assertTrue(engine._fact_is_published(
            "星河工作室正式成立", "你把星河工作室正式成立的消息发布到了朋友圈。"))

    def test_shared_entity_or_phrase_does_not_publish_a_different_fact(self):
        for secret, announcement in (
            ("星河工作室的资金来自父亲遗产", "你公开宣布星河工作室正式成立。"),
            ("蓝色存折藏在旧钢琴里", "你公开宣布蓝色存折已经丢失。"),
            ("玩家通过考试靠系统作弊", "你公开宣布姐姐通过考试。"),
            ("玩家通过考试", "你公开宣布姐姐通过考试。"),
        ):
            with self.subTest(secret=secret):
                state = self.fresh()
                engine.apply_updates(state, payload(announcement, fact_record=secret))
                self.assertEqual(state["facts"][-1]["scope"], "private")
                self.assertNotIn(secret, memory.facts_block(state, viewer="郭瑞莹", action=secret))

    def test_history_knowledge_changes_through_the_real_update_chain(self):
        state = self.fresh()
        secret = "父亲留下的蓝色存折藏在旧钢琴里"
        for npc in state["npcs"]:
            npc["known_to_player"] = True
        memory.append_fact(state, secret, 0, kind="秘密", known_by=["郭瑞莹"])
        for turn in range(1, 71):
            memory.append_fact(state, f"我答应第{turn}位同学下周交稿", turn, kind="承诺")
        self.assertNotIn(secret, [fact["text"] for fact in state["facts"]])
        state["turn"] = 71
        engine.apply_updates(state, payload(
            "你把父亲留下的秘密告诉了梁雅婷。", scene_npcs=["梁雅婷"],
            knowledge=[{"npc": "梁雅婷", "fact": secret, "source": "told", "from": "玩家"}]))
        fact = next(fact for fact in memory.all_facts(state) if fact["text"] == secret)
        self.assertIn("梁雅婷", fact["known_by"])
        self.assertIn(secret, memory.facts_block(state, viewer="梁雅婷", action=secret))

    def test_repeated_completed_appointment_creates_new_instance(self):
        state = self.fresh()
        npc = state["npcs"][0]
        words = "我答应明天晚上七点去琴房见你"
        engine._remember_chat(state, npc, words, "明天见")
        old = deepcopy(state["facts"][0])
        state["turn"] = 1
        memory.resolve_fact(state, old["text"], state["turn"])
        engine._complete_chat_appointment(state, old["text"])
        life_clock.advance_minutes(state, 7 * 1440)
        state["turn"] = 10
        engine._remember_chat(state, npc, words, "明天见")
        facts = memory.all_facts(state)
        self.assertEqual([(fact["turn"], fact["closed"]) for fact in facts], [(0, 1), (10, None)])
        self.assertEqual([entry["status"] for entry in state["appointments"]], ["done", "pending"])
        self.assertNotEqual(facts[0]["id"], facts[1]["id"])
        self.assertEqual(state["appointments"][-1]["fact_id"], facts[-1]["id"])
        self.assertEqual(state["appointments"][-1]["day"], 8)

    def test_repeated_pending_words_still_do_not_duplicate_event(self):
        state = self.fresh()
        npc = state["npcs"][0]
        words = "我答应明天晚上七点去琴房见你"
        for turn in (0, 1, 2):
            state["turn"] = turn
            engine._remember_chat(state, npc, words, "明天见")
        self.assertEqual(len(memory.all_facts(state)), 1)
        self.assertEqual(len(state["appointments"]), 1)

    def test_new_chat_appointment_can_follow_completion_without_an_extra_turn(self):
        state = self.fresh()
        npc = state["npcs"][0]
        words = "我答应明天晚上七点去琴房见你"
        engine._remember_chat(state, npc, words, "明天见")
        text = state["facts"][-1]["text"]
        life_clock.advance_minutes(state, 1440)
        state["turn"] = 1
        memory.resolve_fact(state, text, 1)
        engine._complete_chat_appointment(state, text)
        engine._remember_chat(state, npc, words, "那就明天见")
        facts = memory.all_facts(state)
        self.assertEqual([(entry["turn"], entry["closed"]) for entry in facts], [(0, 1), (1, None)])
        self.assertEqual([entry["status"] for entry in state["appointments"]], ["done", "pending"])
        memory.resolve_fact(state, text, 1)
        engine._complete_chat_appointment(state, text)
        engine._remember_chat(state, npc, words, "重新约明天")
        facts = memory.all_facts(state)
        self.assertEqual(len(facts), 3)
        self.assertEqual(len({entry["id"] for entry in facts}), 3)
        self.assertEqual([entry["status"] for entry in state["appointments"]], ["done", "done", "pending"])

    def test_old_and_new_instances_survive_archive_and_normalize(self):
        state = self.fresh()
        words = "我答应下周归还蓝色相机"
        memory.append_fact(state, words, 0, kind="承诺")
        memory.resolve_fact(state, words, 1)
        memory.append_fact(state, words, 10, kind="承诺")
        for turn in range(11, 91):
            memory.append_fact(state, f"我答应第{turn}位同学交稿", turn, kind="承诺")
        snapshot = models.normalize_state(deepcopy(state))
        copies = [fact for fact in memory.all_facts(snapshot) if fact["text"] == words]
        self.assertEqual([(fact["turn"], fact["closed"]) for fact in copies], [(0, 1), (10, None)])

    def test_legacy_instances_are_distinct_and_same_event_hot_copy_wins(self):
        state = self.fresh()
        words = "我答应明天去琴房"
        state["facts_history"] = [{"text": words, "turn": 0, "closed": 1},
                                  {"text": words, "turn": 10, "closed": None}]
        state["facts"] = [{"text": words, "turn": 10, "closed": 12}]
        facts = memory.all_facts(state)
        self.assertEqual([(fact["turn"], fact["closed"]) for fact in facts], [(0, 1), (10, 12)])

    def test_resolving_a_repeated_instance_preserves_other_pending_arrangements(self):
        state = self.fresh()
        npc = state["npcs"][0]
        words = "我答应明天晚上七点去琴房见你"
        engine._remember_chat(state, npc, words, "明天见")
        text = state["facts"][-1]["text"]
        state["turn"] = 1
        memory.resolve_fact(state, text, 1)
        engine._complete_chat_appointment(state, text)
        state["turn"] = 10
        engine._remember_chat(state, npc, words, "明天见")
        engine._remember_chat(state, npc, "我答应今晚八点陪你去咖啡馆", "今晚见")
        state["turn"] = 11
        memory.resolve_fact(state, text, 11)
        engine._complete_chat_appointment(state, text)
        self.assertEqual([entry["status"] for entry in state["appointments"]], ["done", "done", "pending"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
