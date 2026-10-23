"""Offline demo continuity and grounded dialogue; no model, credentials, or saves."""
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
    from app import demo, engine
    from app.contracts import validate_turn
    from app.models import default_state


class DemoSerialStyle(unittest.TestCase):
    def setUp(self):
        self.state = default_state("试读者")
        self.state["player"]["technique"] = {"name": "已有天赋", "route": "音乐"}
        for npc in self.state["npcs"]:
            npc["known_to_player"] = npc["name"] in ("梁雅婷", "郭瑞莹", "邓碧瑶", "雅倩")

    def person(self, name):
        return next(npc for npc in self.state["npcs"] if npc["name"] == name)

    def test_opening_has_a_scene_paragraphs_and_canonical_connections(self):
        result = demo.opening_segment("试读者")
        text = result["story_text"]
        self.assertIn("砖缝", text)
        self.assertIn("试读者", text)
        self.assertIn("第一次搭话", text)
        self.assertIn("青梅竹马郭瑞莹", text)
        self.assertIn("尚未线下见过的邓碧瑶", text)
        self.assertGreaterEqual(text.count("\n"), 3)
        self.assertEqual(text.count("系统抽奖券×10"), 1)
        self.assertEqual(result["state_updates"]["item_gained"], [])
        self.assertEqual(result["state_updates"]["scene_npcs"], ["梁雅婷"])
        validate_turn(result)
        opening = default_state("试读者")
        engine.apply_updates(opening, result)
        known = {npc["name"] for npc in opening["npcs"] if npc.get("known_to_player")}
        self.assertTrue({"梁雅婷", "郭瑞莹", "邓碧瑶"}.issubset(known))

    def test_unmatched_action_keeps_the_current_foreign_city_at_every_turn(self):
        self.state["player"]["location"] = {"world": "urban", "country": "东瀛", "city": "樱京", "place": "樱川录音室"}
        before = deepcopy(self.state)
        for turn in range(1, 10):
            self.state["turn"] = turn
            result = demo.next_segment(self.state, "我想想接下来先做哪件事")
            self.assertEqual(result["state_updates"]["location"], self.state["player"]["location"])
            self.assertIn("樱川录音室", result["story_text"])
            for stale in ("第二天清晨", "周六的", "第一次", "初识", "指尖", "系统面板轻闪"):
                self.assertNotIn(stale, result["story_text"])
            self.assertFalse(result["state_updates"]["new_side_quest"])
            self.assertFalse(result["state_updates"].get("date_with"))
            self.assertEqual(result["state_updates"]["item_gained"], [])
            validate_turn(result)
        self.state["turn"] = before["turn"]
        self.assertEqual(self.state, before)

    def test_named_local_person_can_respond_without_becoming_a_first_meeting(self):
        result = demo.next_segment(self.state, "我和梁雅婷打招呼")
        self.assertIn("梁雅婷", result["story_text"])
        self.assertIn("在呢", result["story_text"])
        self.assertEqual(result["state_updates"]["scene_npcs"], ["梁雅婷"])
        self.assertNotIn("第二天", result["story_text"])

    def test_remote_person_does_not_appear_or_communicate_without_a_request(self):
        result = demo.next_segment(self.state, "走过去和郭瑞莹打招呼")
        self.assertIn("没有郭瑞莹的身影", result["story_text"])
        self.assertIn("消息没有发出去", result["story_text"])
        self.assertEqual(result["state_updates"]["scene_npcs"], [])
        result = demo.next_segment(self.state, "给郭瑞莹发消息说你好")
        self.assertIn("发去消息", result["story_text"])
        self.assertEqual(result["state_updates"]["scene_npcs"], ["郭瑞莹"])

    def test_remembering_a_person_is_not_a_new_conversation(self):
        result = demo.next_segment(self.state, "回想上周和梁雅婷说过的话")
        self.assertEqual(result["state_updates"]["scene_npcs"], [])

    def test_practice_has_a_concrete_attempt_without_generic_system_speech(self):
        self.state["player"]["location"]["place"] = "樱川录音室"
        result = demo.next_segment(self.state, "弹琴")
        self.assertIn("樱川录音室", result["story_text"])
        self.assertIn("换指", result["story_text"])
        self.assertNotIn("成长这种事", result["story_text"])
        self.assertNotIn("指尖（或喉头）", result["story_text"])
        self.assertEqual(result["state_updates"]["skill_progress"][0]["xp"], 15)
        result = demo.next_segment(self.state, "自习")
        self.assertIn("樱川录音室", result["story_text"])
        self.assertNotIn("操场夜的跑道", result["story_text"])

    def test_greeting_follows_persona_and_does_not_replay_the_arrival(self):
        brisk = demo.chat_reply(self.state, self.person("梁雅婷"), "在吗")
        precise = demo.chat_reply(self.state, self.person("雅倩"), "在吗")
        familiar = demo.chat_reply(self.state, self.person("郭瑞莹"), "在吗")
        self.assertNotEqual(brisk, precise)
        self.assertNotIn("行李", familiar)
        self.assertNotIn("刚看到你在忙", brisk)

    def test_gift_preference_cannot_fabricate_a_received_gift(self):
        npc = self.person("郭瑞莹")
        npc["likes"] = "情趣"
        npc["affinity"] = 100
        result = demo.chat_reply(self.state, npc, "上次送的礼物还记得吗")
        self.assertNotIn("还留着", result)
        self.assertIn("哪份", result)
        npc["deeds"] = [{"turn": 3, "text": "送礼：收到礼物『手写贺卡』，好感+3"}]
        self.assertIn("手写贺卡", demo.chat_reply(self.state, npc, "上次送的礼物还记得吗"))
        self.assertNotIn("手写贺卡", demo.chat_reply(self.state, self.person("梁雅婷"), "上次送的礼物还记得吗"))
        self.assertNotIn("收到了", demo.chat_reply(self.state, npc, "想送你一份礼物"))

    def test_proposed_cancelled_and_confirmed_appointments_stay_distinct(self):
        npc = self.person("梁雅婷")
        self.state["appointments"] = [{"npc": npc["name"], "text": "周六琴房见", "status": "proposed"}]
        result = demo.chat_reply(self.state, npc, "我们约好了吧？")
        self.assertIn("还在商量", result)
        self.state["appointments"][0]["status"] = "cancelled"
        self.assertIn("还没说定", demo.chat_reply(self.state, npc, "我们约好了吗"))
        self.state["appointments"][0]["status"] = "pending"
        self.assertIn("周六琴房见", demo.chat_reply(self.state, npc, "还记得约定吗"))
        self.assertNotIn("就这么说定", demo.chat_reply(self.state, npc, "今晚一起吃饭吗"))

    def test_affection_is_not_a_confirmed_romantic_relationship(self):
        npc = self.person("郭瑞莹")
        npc["affinity"] = 100
        self.assertIn("还没有", demo.chat_reply(self.state, npc, "你是我的女朋友吗"))
        npc["relationship"] = {"status": "partner"}
        self.assertIn("已经认真说定", demo.chat_reply(self.state, npc, "你是我的女朋友吗"))

    def test_archived_shared_evidence_can_be_recalled_but_private_unknown_facts_cannot(self):
        npc = self.person("梁雅婷")
        self.state["facts_history"] = [{"turn": 1, "text": "梁雅婷归还了蓝色相机", "scope": "private", "known_by": ["郭瑞莹"]}]
        result = demo.chat_reply(self.state, npc, "还记得蓝色相机吗")
        self.assertNotIn("归还了蓝色相机", result)
        self.state["facts_history"][0]["known_by"] = [npc["name"]]
        self.assertIn("归还了蓝色相机", demo.chat_reply(self.state, npc, "还记得蓝色相机吗"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
