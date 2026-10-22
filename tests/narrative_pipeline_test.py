"""叙事链路与压缩事务回归：模型用替身，所有文件只写独立临时目录。"""
import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_BASE_URL="", LLM_API_KEY="", LLM_MODEL="")
_read_text = Path.read_text


def _without_env(path, *args, **kwargs):
    if path == ROOT / ".env":
        return ""
    return _read_text(path, *args, **kwargs)


with patch.object(Path, "read_text", _without_env):
    from app import engine, llm, memory, narrative, prompts, storage
    from app.models import default_state, public_state


def payload(text="梁雅婷把报名表压在课本下，指了指最后一格。\n\n“这儿还空着。”"):
    return {"story_text": text, "narration_world": "urban",
            "choices": ["拿起笔看报名要求", "问她准备报哪个项目"],
            "state_updates": {}, "system_notice": ""}


class NarrativePipelineTests(unittest.TestCase):
    def test_a_remote_greeting_does_not_share_an_unrelated_local_secret(self):
        state = default_state("链路验收")
        data = payload("你把隐藏坐标告诉了梁雅婷。手机上郭瑞莹发来一句问候。")
        data["state_updates"] = {"fact_record": "你向梁雅婷透露了隐藏坐标"}
        engine.apply_updates(state, data)
        self.assertEqual(state["facts"][-1]["known_by"], ["梁雅婷"])
        guo = next(npc for npc in state["npcs"] if npc["name"] == "郭瑞莹")
        self.assertIn("郭瑞莹发来一句问候", guo["known_memory"][-1])
        self.assertNotIn("隐藏坐标", guo["known_memory"][-1])

    def setUp(self):
        target = ROOT / "artifacts" / "narrative-pipeline-temp"
        target.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=target)
        self.folder = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        for module in (engine, memory):
            for name, relative in (("DATA_DIR", "."), ("STORY_ARCHIVE_FILE", "story_archive.jsonl")):
                if hasattr(module, name):
                    self.enterContext(patch.object(module, name, self.folder / relative))

    def old_story(self):
        state = default_state("链路验收")
        state["turn"] = engine.COMPACT_THRESHOLD
        state["summary"] = "开学后，他们先交接过一本旧乐谱。"
        state["story"] = [
            {"turn": turn, "world": "urban", "text": f"第{turn}段：同学把当天的排练表夹进蓝色文件袋。",
             "choices": ["观察", "提问"], "chosen": "提问", "ts": "test"}
            for turn in range(engine.COMPACT_THRESHOLD + 1)
        ]
        return state

    def test_real_compaction_wrapper_accepts_attempts_and_calls_transport_once(self):
        """不能mock掉_call_llm_json，否则错误关键字会被旧假函数掩盖。"""
        state = self.old_story()
        old_count = len(state["story"])
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value={"summary": "他们把排练顺序逐一敲定。", "facts": []}) as transport:
            self.assertIsNone(engine.maybe_compact(state))
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(state["summary"], "他们把排练顺序逐一敲定。")
        self.assertEqual(len(state["story"]), engine.COMPACT_KEEP)
        archived = [json.loads(row) for row in engine.STORY_ARCHIVE_FILE.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(archived), old_count - engine.COMPACT_KEEP)
        self.assertEqual(archived[0]["turn"], 0)
        self.assertEqual(archived[0]["run_created_at"], state["created_at"])
        self.assertEqual(archived[0]["scope"], "private")
        self.assertEqual(archived[0]["known_by"], [])
        source = state["summary_source"]
        self.assertEqual(source["kind"], "derived")
        self.assertEqual((source["first_turn"], source["last_turn"]),
                         (0, old_count - engine.COMPACT_KEEP - 1))
        self.assertEqual(len(source["sha256"]), 64)

    def test_compaction_service_failure_preserves_story_and_backs_off(self):
        state = self.old_story()
        before = deepcopy(state)
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", side_effect=llm.ModelServiceError("测试服务失败")) as transport:
            notice = engine.maybe_compact(state)
        self.assertEqual(transport.call_count, 1)
        self.assertIn("压缩失败", notice)
        self.assertEqual(state["story"], before["story"])
        self.assertEqual(state["summary"], before["summary"])
        self.assertFalse(engine.STORY_ARCHIVE_FILE.exists())
        self.assertEqual(state["compact_retry_at_turn"], state["turn"] + engine.COMPACT_RETRY_INTERVAL)

    def test_summary_model_cannot_promote_a_proposal_into_confirmed_facts(self):
        state = self.old_story()
        state["story"][0]["text"] = "郭瑞莹问：明天要不要来琴房？你还没有回答。"
        memory.append_fact(state, "玩家答应替梁雅婷保管相机", 1, known_by=["梁雅婷"])
        before = deepcopy(state["facts"])
        with patch.object(engine, "DEMO_MODE", False), patch.object(llm, "chat_json", return_value={
                "summary": "郭瑞莹提出了琴房邀约。", "facts": ["玩家答应郭瑞莹明天在琴房见面", "全校都知道相机的秘密"]}):
            self.assertIsNone(engine.maybe_compact(state))
        self.assertEqual(state["facts"], before)

    def test_archive_failure_keeps_previous_summary_source_and_entire_story(self):
        state = self.old_story()
        state["summary_source"] = {"kind": "derived", "sha256": "old"}
        before = deepcopy(state)
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value={"summary": "新的派生摘要"}), patch.object(
                engine, "_archive_segments", return_value=False):
            notice = engine.maybe_compact(state)
        self.assertIn("归档写入失败", notice)
        for key in ("story", "summary", "summary_source", "facts"):
            self.assertEqual(state[key], before[key])

    def test_non_text_summary_is_not_accepted_as_a_checkpoint(self):
        state = self.old_story()
        before = deepcopy(state)
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value={"summary": {"plan": "尚未生成"}}):
            notice = engine.maybe_compact(state)
        self.assertIn("压缩失败", notice)
        self.assertEqual(state["summary"], before["summary"])
        self.assertEqual(state["story"], before["story"])

    def test_normal_scene_does_not_gain_a_second_model_review_call(self):
        state = default_state("链路验收")
        before = deepcopy(state)
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value=payload()) as transport, patch.object(storage, "save") as save:
            result, _ = engine.take_turn(state, "我问梁雅婷，最后一格要填什么")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result["turn"], state["turn"] + 1)
        self.assertEqual(state, before, "生成失败保护要求调用者的原state不被改动")
        save.assert_called_once()
        self.assertIn("fingerprint", result["story"][-1]["narrative_quality"])
        self.assertEqual(result["story"][-1]["scope"], "private")
        self.assertEqual(result["story"][-1]["known_by"], [],
                         "在场不能让NPC读到整段旁白和玩家内心")

    def test_opening_is_validated_before_replacing_any_save(self):
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value=payload()) as transport, patch.object(storage, "replace_game") as replace:
            result = engine.start_game("链路验收")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result["story"][0]["text"], payload()["story_text"])
        replace.assert_called_once()

    def test_sms_stays_one_call_without_advancing_world_turn(self):
        state = default_state("链路验收")
        npc = state["npcs"][0]
        npc["known_to_player"] = True
        before_turn = state["turn"]
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value={"reply": "等会儿，我把谱架收一下。"}) as transport, patch.object(storage, "save"):
            result = engine.send_chat(state, npc["name"], "现在方便说话吗？")
        self.assertTrue(result["ok"])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(state["turn"], before_turn)
        self.assertEqual(state["chats"][npc["name"]]["msgs"][-1]["text"], result["reply"])

    def test_internal_process_pollution_uses_the_existing_single_format_retry(self):
        state = default_state("链路验收")
        bad = payload("<think>先设计她的反应，再写台词。</think>梁雅婷推来一张表。")
        good = payload()
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", side_effect=[bad, good]) as transport, patch.object(storage, "save"):
            result, _ = engine.take_turn(state, "我问梁雅婷最后一格的事")
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(result["story"][-1]["text"], good["story_text"])
        self.assertNotIn("<think>", result["story"][-1]["text"])

    def test_repeated_internal_process_pollution_does_not_submit_a_turn(self):
        state = default_state("链路验收")
        before = deepcopy(state)
        bad = payload("<analysis>目标情绪：拉扯；接下来构造矛盾。</analysis>")
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value=bad) as transport, patch.object(storage, "save") as save:
            with self.assertRaises(engine.EngineError):
                engine.take_turn(state, "我继续问她")
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(state, before)
        save.assert_not_called()

    def test_polluted_opening_cannot_replace_the_previous_save(self):
        bad = payload("<think>写一段都市开局。</think>")
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value=bad) as transport, patch.object(storage, "replace_game") as replace:
            with self.assertRaises(engine.EngineError):
                engine.start_game("链路验收")
        self.assertEqual(transport.call_count, 2)
        replace.assert_not_called()

    def test_soft_style_warnings_neither_rewrite_the_story_nor_call_a_reviewer(self):
        state = default_state("链路验收")
        text = "你忽然意识到，命运的齿轮已经转动。她把最后一张表塞进文件夹，仍没交给你。"
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value=payload(text)) as transport, patch.object(storage, "save"):
            result, _ = engine.take_turn(state, "我看看那张表")
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(result["story"][-1]["text"], text)
        self.assertTrue(result["story"][-1]["narrative_quality"]["signals"])

    def test_polluted_sms_is_not_sent_or_saved_and_has_no_automatic_retry(self):
        state = default_state("链路验收")
        npc = state["npcs"][0]
        npc["known_to_player"] = True
        before = deepcopy(state)
        with patch.object(engine, "DEMO_MODE", False), patch.object(
                llm, "chat_json", return_value={"reply": "<think>我要温柔地安慰玩家。</think>"}) as transport, patch.object(storage, "save") as save:
            result = engine.send_chat(state, npc["name"], "现在方便说话吗？")
        self.assertFalse(result["ok"])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(state["chats"], before["chats"])
        self.assertEqual(state["turn"], before["turn"])
        save.assert_not_called()

    def test_narrative_metadata_survives_archiving_without_changing_world_updates(self):
        state = default_state("链路验收")
        original = payload()
        original["state_updates"] = {"realm_progress_delta": 2}
        prepared = narrative.prepare_result(original, state)
        self.assertEqual(prepared["state_updates"], original["state_updates"])
        engine.apply_updates(state, prepared)
        segment = state["story"][-1]
        self.assertTrue(engine._archive_segments(state, [segment]))
        archived = json.loads(engine.STORY_ARCHIVE_FILE.read_text(encoding="utf-8"))
        self.assertEqual(archived["narrative_quality"], segment["narrative_quality"])
        self.assertEqual(archived["known_by"], [])
        state["summary_source"] = {"kind": "derived", "sha256": "private provenance"}
        shown = public_state(state)
        self.assertNotIn("narrative_quality", shown["story"][-1])
        self.assertNotIn("summary_source", shown)
        self.assertIn("narrative_quality", state["story"][-1], "前台投影不能反过来删后台记录")


if __name__ == "__main__":
    unittest.main(verbosity=2)
