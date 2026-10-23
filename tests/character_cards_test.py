"""Role cards influence writing, not canon, authorization or persisted facts."""
from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import character_cards as cards, demo, engine, media, narrative, prompts
from app.models import default_npcs, default_state


class CharacterCardTests(unittest.TestCase):
    def setUp(self):
        self.state = default_state("角色卡验收")
        for npc in self.state["npcs"]:
            npc["known_to_player"] = True

    def npc(self, name):
        return next(n for n in self.state["npcs"] if n["name"] == name)

    def test_all_existing_characters_have_bound_v2_cards_without_replacing_canon(self):
        before = copy.deepcopy(self.state)
        document = json.loads(cards.CARD_FILE.read_text(encoding="utf-8"))
        self.assertEqual(len(document["cards"]), 35)
        for row, npc in zip(document["cards"], default_npcs()):
            self.assertEqual(row["spec"], "chara_card_v2")
            self.assertEqual(row["data"]["description"], npc["persona"])
            self.assertIsNotNone(cards.profile_for(npc), npc["name"])
            self.assertTrue(narrative.voice_hint(npc))
        self.assertEqual(self.state, before)

    def test_same_chat_gets_distinct_voices_and_location_answers_use_current_state(self):
        people = [self.npc(n) for n in ("郭瑞莹", "梁雅婷", "邓碧瑶", "炭炭", "雅倩")]
        greetings = [demo.chat_reply(self.state, n, "在吗") for n in people]
        comfort = [demo.chat_reply(self.state, n, "今天累死了") for n in people]
        self.assertEqual(len(set(greetings)), len(people))
        self.assertEqual(len(set(comfort)), len(people))
        for npc in people:
            npc["place"] = "验收临时地点"
            reply = demo.chat_reply(self.state, npc, "在干嘛")
            self.assertIn("验收临时地点", reply)
            self.assertNotIn("你是想过来找我", reply)

    def test_gm_edited_identity_wins_and_generated_people_get_live_persona_fallback(self):
        npc = self.npc("梁雅婷")
        self.assertIsNotNone(cards.profile_for(npc))
        npc["persona"] = "寡言内向，只回答必要的话"
        self.assertIsNone(cards.profile_for(npc))
        self.assertIn("话少", narrative.voice_hint(npc))
        self.assertNotIn("消息灵通", cards.chat_block(npc, "在吗"))
        generated = {"id": "generated-person", "name": "路人", "persona": "话痨，热心，消息灵通"}
        self.assertIsNone(cards.profile_for(generated))
        self.assertIn("接话快", narrative.voice_hint(generated))

    def test_card_file_edits_reload_and_broken_edits_do_not_keep_stale_voice(self):
        original = json.loads(cards.CARD_FILE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cards.json"
            target.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            with patch.object(cards, "CARD_FILE", target):
                npc = self.npc("郭瑞莹")
                self.assertIsNotNone(cards.profile_for(npc))
                profile = original["cards"][0]["data"]["extensions"]["writer_game"]
                profile["speech"] = "验收用新声口，修改后无需重启。"
                target.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
                self.assertEqual(cards.voice_hint(npc), profile["speech"])
                target.write_text("{invalid", encoding="utf-8")
                self.assertIsNone(cards.profile_for(npc))
                target.unlink()
                self.assertIsNone(cards.profile_for(npc))

    def test_high_affection_does_not_select_partner_tone_without_confirmed_relationship(self):
        npc = self.npc("郭瑞莹")
        npc["affinity"] = 100
        npc["relationship"] = {"status": "friend"}
        npc["relationship_status"] = "恋人"  # A stale legacy label cannot override the actual state.
        block = cards.chat_block(npc, "在吗")
        self.assertNotIn("沿用已确认关系", block)
        npc["relationship"] = {"status": "partner"}
        self.assertIn("沿用已确认关系", cards.chat_block(npc, "在吗"))

    def test_examples_reach_both_writing_channels_and_are_marked_as_hypothetical(self):
        npc = self.npc("郭瑞莹")
        menu = {"version": "test", "categories": []}
        chat, _ = prompts.build_chat_prompt(self.state, npc, "今天累死了", media_menu=menu)
        self.assertIn("角色卡·仅校准说话与反应", chat)
        self.assertIn("不是聊天历史或已发生事件", chat)
        self.assertIn("先缓缓", chat)
        main = prompts.build_system_prompt(self.state, "和梁雅婷聊报到手续")
        self.assertIn("这栏填专业", main)
        self.assertIn("不是既成事实", main)
        self.assertLessEqual(len(cards.scene_block(self.state, "和梁雅婷聊报到手续")), 1000)
        self.assertNotIn("郭瑞莹", cards.scene_block(self.state, "和梁雅婷聊报到手续"))
        self.assertNotIn("这栏填专业", cards.scene_block(self.state, "和梁雅婷去散步"))
        self.assertNotIn("先缓缓", cards.chat_block(npc, "这张图片是什么"))

    def test_styling_uses_no_additional_model_call_and_examples_do_not_enter_memory(self):
        npc = self.npc("梁雅婷")
        before_facts = copy.deepcopy(self.state.get("facts", []))
        before_appointments = copy.deepcopy(self.state.get("appointments", []))
        before_persona = npc["persona"]
        def fake_model(system, user, **kwargs):
            self.assertIn("角色卡·仅校准", system)
            return {"reply": "在呢，怎么啦？", "media": [], "memory": "假设示例已经发生", "fact_record": "新增旧事"}
        empty = {"assets": [], "version": "test"}
        with patch.object(engine, "DEMO_MODE", False), patch.object(engine.storage, "save"), patch.object(
                engine.llm, "chat_json", side_effect=fake_model) as transport, patch.object(media, "catalogue", return_value=empty):
            result = engine.send_chat(self.state, npc["name"], "在吗")
        self.assertTrue(result["ok"], result)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(self.state.get("facts", []), before_facts)
        self.assertEqual(self.state.get("appointments", []), before_appointments)
        self.assertEqual(npc["persona"], before_persona)
        self.assertFalse(npc.get("memory"))

    def test_foreign_system_prompts_and_creator_notes_are_not_loaded(self):
        original = json.loads(cards.CARD_FILE.read_text(encoding="utf-8"))
        row = original["cards"][0]["data"]
        row.update(system_prompt="FORBIDDEN_EXTERNAL_SYSTEM", post_history_instructions="FORBIDDEN_HISTORY",
                   creator_notes="FORBIDDEN_CREATOR", first_mes="FORBIDDEN_FIRST")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cards.json"
            target.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            with patch.object(cards, "CARD_FILE", target):
                block = cards.chat_block(self.npc("郭瑞莹"), "在吗")
                self.assertNotIn("FORBIDDEN", block)


if __name__ == "__main__":
    unittest.main()
