"""Cross-channel identity and memory regressions; no real model or save access."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copy import deepcopy
import unittest
from unittest.mock import patch

from app import character_cards, engine, lore, media, memory, prompt_context, prompts
from app.contracts import validate_turn
from app.models import default_state


class PromptConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.state = default_state("渠道验收")
        self.npc = self.state["npcs"][0]
        self.npc["known_to_player"] = True
        self.menu = {"version": "test", "categories": []}
        # Never read the project's persisted archive in these tests.
        self.enterContext(patch.object(memory, "retrieve_archive", return_value=[]))

    def channels(self, text="在吗"):
        return (prompts.build_system_prompt(self.state, f"和{self.npc['name']}聊{text}"),
                prompts.build_chat_prompt(self.state, self.npc, text, media_menu=self.menu)[0])

    def test_scene_phone_and_offline_use_the_same_canon_and_relationship_rules(self):
        for system in (*self.channels(), prompts.build_offline_prompt(self.state, 1)[0]):
            self.assertIn(prompt_context.shared_rules_block(), system)
            self.assertIn(f"《{prompt_context.GAME_TITLE}》", system)
            self.assertNotIn("双界录", system)
            self.assertNotIn("关系亲近，可以自然亲昵", system)
        self.assertNotIn("必须让所有涉及的人知情并同意", lore.canon_block(self.state))

    def test_affection_stages_do_not_create_a_partner_in_either_channel(self):
        self.npc["relationship"] = {"status": "friend", "mode": "exclusive"}
        self.npc["relationship_status"] = "恋人"  # stale migrated display value
        for affection in (0, 25, 50, 69, 70, 84, 85, 100):
            with self.subTest(affection=affection):
                self.npc["affinity"] = affection
                for system in self.channels():
                    self.assertIn("正式关系：朋友（friend），尚无已确认恋爱关系", system)
                    self.assertIn(f"好感{affection}·", system)
                self.assertNotEqual(character_cards._tone(self.npc), "partner")

    def test_confirmed_partner_distance_and_breakup_survive_channel_switch(self):
        for status, label in (("partner", "恋人"), ("distance", "异地恋人"), ("breakup", "分手")):
            with self.subTest(status=status):
                self.npc["relationship"] = {"status": status, "mode": "poly", "label": "旧标签"}
                self.npc["affinity"] = 20
                for system in self.channels():
                    self.assertIn(f"正式关系：{label}（{status}）", system)
                    self.assertNotIn("正式关系：旧标签", system)
                    if status != "breakup":
                        self.assertIn("相处模式：多人", system)
                self.assertEqual(character_cards._tone(self.npc), "new" if status == "breakup" else "partner")

    def test_gm_persona_boundaries_and_voice_reach_both_channels(self):
        self.npc.update(persona="寡言内向，谈事直接，主动表达自己的想法",
                        persona_directive="主持人已改写人设：从现在起按新设定演绎。",
                        boundaries={"principles": "说到做到", "boundary": "不代替我做决定", "romance_style": "直接"})
        dossier = prompt_context.character_block(self.npc)
        for system in self.channels():
            self.assertIn(dossier, system)
            self.assertIn("话少", system)
            self.assertIn(self.npc["persona_directive"], system)
        self.assertIsNone(character_cards.profile_for(self.npc))

    def test_family_relationship_cannot_turn_romantic_with_high_affection(self):
        self.npc["role"] = "母亲"
        self.npc["affinity"] = 100
        for system in self.channels():
            self.assertIn("正式关系：家人，不进入恋爱线", system)

    def test_formal_status_is_read_without_mutating_or_repairing_a_save(self):
        npc = {"role": "同学", "relationship_status": "异地恋人"}
        before = deepcopy(npc)
        self.assertIn("异地恋人（distance）", prompt_context.relationship_line(npc))
        self.assertEqual(npc, before)

    def test_phone_includes_current_personal_experience_without_other_peoples_secrets(self):
        self.npc["memory"] = ["已一起核对过蓝色乐谱"]
        self.npc["deeds"] = [{"turn": 1, "text": "刚在琴房交接过备用琴谱"}]
        other = next(n for n in self.state["npcs"] if n["name"] == "邓碧瑶")
        memory.append_fact(self.state, "封存暗号甲乙丙", 0, scope="private", known_by=[other["name"]])
        self.state["chats"] = {other["name"]: {"msgs": [{"from": "npc", "text": "仅在另一私聊的密码丁戊己"}]}}
        self.state["story"] = [{"turn": 0, "text": "你心想：只有主角知道的庚辛壬。", "scene_npcs": [self.npc["name"]]}]
        main, chat = self.channels("备用琴谱呢")
        for text in ("已一起核对过蓝色乐谱", "刚在琴房交接过备用琴谱"):
            self.assertIn(text, main)
            self.assertIn(text, chat)
        self.assertIn("封存暗号甲乙丙", main)
        for secret in ("封存暗号甲乙丙", "仅在另一私聊的密码丁戊己", "只有主角知道的庚辛壬", "灯塔观测组"):
            self.assertNotIn(secret, chat)

    def test_scene_fact_reaches_phone_and_explicit_phone_promise_reaches_scene(self):
        """Exercise the actual state writers in both directions, not fabricated summaries."""
        name = self.npc["name"]
        self.state["turn"] = 1
        data = validate_turn({"story_text": f"{name}把蓝色乐谱递给你：‘先替我保管。’",
                              "choices": ["收好乐谱", "问排练安排"], "narration_world": "urban",
                              "state_updates": {"scene_npcs": [name], "duration_minutes": 15,
                                                "fact_record": f"{name}把蓝色乐谱交给玩家保管"}})
        engine.apply_updates(self.state, data, action=f"与{name}核对乐谱")

        def reply(system, user, **kwargs):
            self.assertIn(f"{name}把蓝色乐谱交给玩家保管", system)
            return {"reply": "行，到时还我。", "media": [], "memory": "", "fact_record": None}

        with patch.object(engine, "DEMO_MODE", False), patch.object(engine.storage, "save"), patch.object(
                engine.llm, "chat_json", side_effect=reply) as transport, patch.object(
                media, "catalogue", return_value={"assets": [], "version": "test"}):
            result = engine.send_chat(self.state, name, "我答应明天到琴房归还蓝色乐谱")
        self.assertTrue(result["ok"], result)
        self.assertEqual(transport.call_count, 1)
        main = prompts.build_system_prompt(self.state, f"去找{name}还乐谱")
        self.assertIn("我答应明天到琴房归还蓝色乐谱", main)
        self.assertIn("已确认，待兑现", main)
        self.assertEqual(self.state["turn"], 1, "SMS must not advance a story turn")

    def test_channel_outputs_keep_their_own_contracts(self):
        main, chat = self.channels()
        self.assertIn('"story_text"', main)
        self.assertIn('"state_updates"', main)
        self.assertNotIn('"state_updates"', chat)
        self.assertIn('"reply"', chat)
        self.assertIn('"media": []', chat)
        self.assertIn("不写动作舞台说明", chat)
        self.assertIn("不得靠 reply 编造已经赴约", chat)


if __name__ == "__main__":
    unittest.main()
