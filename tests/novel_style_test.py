"""场景契约、文风信号与提示词接入；不请求模型、不使用正式存档。"""
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
    from app import lore, memory, narrative, prompts
    from app.models import default_state


class NovelStyleTests(unittest.TestCase):
    def fresh(self):
        return default_state("林川")

    def test_scene_card_is_nine_constraints_not_an_outcome(self):
        state = self.fresh()
        state["story"] = [{"turn": 4, "text": "她将未签字的报价单退回来。\n“渠道的事，你还没答我。”"}]
        before = deepcopy(state)
        card = narrative.scene_card(state, "我想先问工作室的融资条件")
        self.assertEqual(len(card), 9)
        self.assertIn("未签字", card["carry"])
        self.assertIn("尚未核验", card["change"])
        self.assertIn("不越过授权", card["limits"])
        self.assertEqual(state, before)

    def test_quiet_scene_can_remain_quiet(self):
        card = narrative.scene_card(self.fresh(), "在街角歇一会，随便聊聊")
        self.assertIn("不强造意外", card["change"])
        self.assertIn("别硬塞悬念", card["stop"])
        self.assertIn("80~180", card["stop"])

    def test_scene_opens_at_current_place_and_protects_player(self):
        state = self.fresh()
        state["player"]["location"] = {"world": "urban", "country": "东瀛", "city": "樱京", "place": "樱京音乐学园"}
        state["time"]["day"] = 21
        card = narrative.scene_card(state, "练习声乐")
        self.assertIn("第21天", card["time_place"])
        self.assertIn("樱京音乐学园", card["time_place"])
        self.assertIn("别一练即成名", card["change"])
        self.assertIn("玩家尚未决定", card["viewpoint"])
        canon = lore.canon_block(state)
        self.assertIn("当前区域：东瀛·樱京", canon)
        self.assertNotIn("A层已细化；主角常在京都", canon)

    def test_voice_follows_edited_persona_instead_of_name(self):
        npc = {"name": "梁雅婷", "persona": "消息灵通，话多但可靠"}
        talkative = narrative.voice_hint(npc)
        npc["persona"] = "寡言内向，只说必要的话"
        quiet = narrative.voice_hint(npc)
        self.assertNotEqual(talkative, quiet)
        self.assertIn("话少", quiet)

    def test_soft_patterns_do_not_delete_or_rewrite_story_or_rewards(self):
        data = {"story_text": "\r\n命运的齿轮开始转动。\r\n她说：“先把东西拿来。”\r\n", "state_updates": {"item_gained": [{"name": "华夏币", "count": 12}]}}
        before = deepcopy(data)
        result = narrative.prepare_result(data, self.fresh())
        self.assertEqual(data, before)
        self.assertIn("命运的齿轮", result["story_text"])
        self.assertEqual(result["state_updates"], data["state_updates"])
        self.assertIn("fate_closing", result["_narrative_quality"]["signals"])
        self.assertEqual(len(result["_narrative_quality"]["fingerprint"]), 64)

    def test_planning_contamination_is_distinguished_from_system_and_dialogue(self):
        for text in ("<think>先分析人设</think>\n正文", "【写作计划】\n先制造矛盾", "起因：排队\n发展：交谈\n高潮：表态"):
            with self.subTest(text=text), self.assertRaises(narrative.NarrativeFormatError):
                narrative.prepare_result({"story_text": text}, self.fresh())
        text = "【心动系统·绑定成功】\n“这张纸写着自检结果，不是我的签名。”她说。"
        self.assertEqual(narrative.prepare_result({"story_text": text}, self.fresh())["story_text"], text)

    def test_repeated_entry_or_closing_is_visible_to_local_checker(self):
        old = "报价单第三次被退回，她把其中那行付款条件圈出来让你再看一遍。"
        state = self.fresh()
        state["story"] = [{"text": old}]
        result = narrative.prepare_result({"story_text": old}, state)
        self.assertIn("repeated_opening", result["_narrative_quality"]["signals"])
        self.assertIn("repeated_closing", result["_narrative_quality"]["signals"])
        self.assertEqual(result["story_text"], old)

    def test_turn_and_opening_prompts_actually_receive_contract(self):
        state = self.fresh()
        with patch.object(memory, "retrieve_archive", return_value=[]):
            turn = prompts.build_turn_user(state, "找梁雅婷归还乐谱")
        self.assertIn("本回合场景卡", turn)
        self.assertIn("归还乐谱", turn)
        self.assertIn("玩家主动参与", turn)
        self.assertIn("本回合场景卡", prompts.build_opening_user(state))
        system = prompts.build_system_prompt(state)
        self.assertIn("都市连载写法", system)
        self.assertIn("不轮流用阳光", system)
        self.assertIn("派生索引", system)
        self.assertLessEqual(len(system), 12000)

    def test_chat_has_own_voice_and_only_own_knowledge(self):
        state = self.fresh()
        npc = state["npcs"][0]
        memory.append_fact(state, "私下商定收购北岸公司", 0, scope="private", known_by=["梁雅婷"])
        memory.append_fact(state, "收到寄回的旧乐谱", 0, scope="private", known_by=[npc["name"]])
        with patch.object(memory, "retrieve_archive", return_value=[]) as retrieve:
            system, user = prompts.build_chat_prompt(state, npc, "乐谱收到了吗")
        self.assertIn("收到寄回的旧乐谱", system)
        self.assertNotIn("私下商定收购北岸公司", system)
        self.assertIn("声口", system)
        self.assertIn("不能编造", system)
        self.assertIn("乐谱收到了吗", user)
        self.assertEqual(retrieve.call_args.kwargs["viewer"], npc["name"])

    def test_recent_context_keeps_real_last_line_even_when_long(self):
        state = self.fresh()
        state["story"] = [{"turn": 3, "text": "开头" + "中间经过。" * 150 + "末尾：她还在等你答复。", "chosen": "先看收据"}]
        block = prompts._recent_story(state)
        self.assertIn("末尾：她还在等你答复", block)
        self.assertIn("玩家随后行动：先看收据", block)
        self.assertLess(len(block), 600)


if __name__ == "__main__":
    unittest.main(verbosity=2)
