"""长局记忆检索与来源/知情边界：只使用内存状态和临时归档，不调用模型。"""
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
    return "" if path == ROOT / ".env" else _read_text(path, *args, **kwargs)


with patch.object(Path, "read_text", _without_env):
    from app import engine, memory, models


class SerialMemoryTests(unittest.TestCase):
    def setUp(self):
        self.state = models.default_state("隔离记忆测试")
        self.state["created_at"] = "2026-10-01T00:00:00+00:00"
        self.state["turn"] = 1000
        task_temp = ROOT / "artifacts" / "serial-memory-tests"
        task_temp.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=task_temp)
        self.archive = Path(self.temp.name) / "story_archive.jsonl"
        self.patch_archive = patch.object(memory, "STORY_ARCHIVE_FILE", self.archive)
        self.patch_archive.start()
        self.addCleanup(self.patch_archive.stop)
        self.addCleanup(self.temp.cleanup)

    def write_archive(self, records):
        self.archive.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")

    def record(self, turn, text, **extra):
        return {"turn": turn, "text": text, "player": self.state["player"]["name"],
                "run_created_at": self.state["created_at"], **extra}

    def test_evicted_promises_remain_queryable_and_can_be_resolved(self):
        old = "答应梁雅婷归还那台蓝色相机"
        memory.append_fact(self.state, old, 1, known_by=["梁雅婷"])
        for turn in range(2, 95):
            memory.append_fact(self.state, f"答应第{turn}位摊主按时提交材料", turn)
        self.assertEqual(len(self.state["facts"]), memory.FACTS_HARD_CAP)
        self.assertEqual(len(memory.all_facts(self.state)), 94)
        self.assertTrue(any(f["text"] == old for f in self.state["facts_history"]))
        self.assertIn(old, memory.facts_block(self.state, action="找梁雅婷归还蓝色相机"))
        self.assertNotIn(old, memory.facts_block(self.state, viewer="郭瑞莹", action="蓝色相机"))
        self.assertEqual(memory.resolve_fact(self.state, "归还那台蓝色相机", 100), old)
        block = memory.facts_block(self.state, action="归还那台蓝色相机")
        self.assertIn(f"（已了结）：{old}", block)
        self.assertEqual(memory.set_fact_knowledge(self.state, old, "郭瑞莹"), old)
        self.assertIn(old, memory.facts_block(self.state, viewer="郭瑞莹", action="蓝色相机"))
        memory.set_fact_knowledge(self.state, old, "郭瑞莹", False)
        self.assertNotIn(old, memory.facts_block(self.state, viewer="郭瑞莹", action="蓝色相机"))

    def test_history_dedup_keeps_scope_and_closed_state(self):
        memory.append_fact(self.state, "答应替梁雅婷保守相机秘密", 1, known_by=["梁雅婷"])
        for turn in range(2, 75):
            memory.append_fact(self.state, f"答应第{turn}位同学递交稿件", turn)
        before = len(memory.all_facts(self.state))
        self.assertIsNone(memory.append_fact(self.state, "答应替梁雅婷保守相机秘密（承诺）", 900))
        self.assertEqual(len(memory.all_facts(self.state)), before)
        snapshot = models.normalize_state(deepcopy(self.state))
        fact = memory.all_facts(snapshot)[0]
        self.assertEqual((fact["turn"], fact["scope"], fact["known_by"], fact["closed"]), (1, "private", ["梁雅婷"], None))

    def test_public_response_and_new_run_do_not_expose_history_or_debug(self):
        self.state["facts_history"] = [{"turn": 1, "text": "不可公开的后台真相", "scope": "private", "known_by": []}]
        self.state["summary_source"] = {"sha256": "internal"}
        self.state["story"] = [{"turn": 1, "text": "玩家正文", "narrative_quality": {"signals": ["internal"]}}]
        response = models.public_state(self.state)
        self.assertNotIn("facts_history", response)
        self.assertNotIn("summary_source", response)
        self.assertNotIn("narrative_quality", response["story"][0])
        self.assertIn("narrative_quality", self.state["story"][0])
        models._clear_run_records(self.state)
        self.assertEqual(self.state["facts_history"], [])

    def test_hundreds_of_recent_mentions_do_not_hide_old_relevant_object(self):
        target = "郭瑞莹把蓝色琴谱压在第三排琴键下面，封底写着八月七日。"
        records = [self.record(1, "前文。" * 180 + target, chosen="我打算下周归还琴谱")]
        records += [self.record(turn, f"郭瑞莹聊起天气，随后第{turn}次告别。") for turn in range(2, 360)]
        self.write_archive(records)
        before = deepcopy(self.state)
        hits = memory.retrieve_archive(self.state, "去找郭瑞莹问那张蓝色琴谱上的日期")
        self.assertEqual(hits[0]["turn"], 1)
        self.assertIn("八月七日", hits[0]["text"])
        self.assertLessEqual(len(hits[0]["text"]), memory.ARCHIVE_SNIPPET)
        block = memory.archive_block(hits)
        self.assertIn("原文#", block)
        self.assertIn("只证明意图", block)
        self.assertIn("以账本为准", block)
        self.assertEqual(self.state, before)

    def test_topic_can_retrieve_without_npc_or_catalog_item(self):
        self.write_archive([self.record(2, "柜台下面藏着蓝色琴谱，封底有日期。")])
        self.assertTrue(memory.retrieve_archive(self.state, "那张蓝色琴谱上写了什么"))
        self.assertEqual(memory.retrieve_archive(self.state, "随便走走"), [])

    def test_old_uncompacted_story_is_retrieved_without_archive(self):
        self.state["story"] = [{"turn": 1, "text": "你把蓝色琴谱交给了梁雅婷。"}]
        self.state["story"] += [{"turn": turn, "text": "路过街头。"} for turn in range(2, 14)]
        hits = memory.retrieve_archive(self.state, "蓝色琴谱放在哪里")
        self.assertEqual((hits[0]["turn"], hits[0]["source"]), (1, "当前存档旧正文"))

    def test_archive_run_player_and_future_boundaries(self):
        self.write_archive([
            self.record(2, "蓝色琴谱是当前周目的材料"),
            self.record(1001, "蓝色琴谱未来才会发生的结果"),
            self.record(3, "蓝色琴谱属于另一周目", run_created_at="2025-01-01T00:00:00+00:00"),
            self.record(4, "蓝色琴谱属于别人", player="另一位玩家"),
            {"turn": 5, "text": "蓝色琴谱来源无法确认"},
        ])
        hits = memory.retrieve_archive(self.state, "蓝色琴谱")
        self.assertEqual([hit["turn"] for hit in hits], [2])

    def test_legacy_archive_requires_verifiable_timestamp(self):
        self.write_archive([
            {"turn": 2, "text": "旧乐谱在开局之前", "archived_at": "2026-09-01T00:00:00+00:00"},
            {"turn": 3, "text": "旧乐谱在本周目归档", "archived_at": "2026-10-02T00:00:00+00:00"},
        ])
        self.assertEqual([hit["turn"] for hit in memory.retrieve_archive(self.state, "旧乐谱")], [3])

    def test_viewer_cannot_read_private_story_or_infer_knowledge_from_presence(self):
        self.write_archive([
            self.record(1, "蓝色琴谱里夹着玩家没说出口的秘密", scene_npcs=["梁雅婷"], scope="private", known_by=[]),
            self.record(2, "蓝色琴谱交给了梁雅婷", scope="private", known_by=["梁雅婷"]),
            self.record(3, "蓝色琴谱在公开节目册展示", scope="public"),
        ])
        self.assertEqual({hit["turn"] for hit in memory.retrieve_archive(self.state, "蓝色琴谱", viewer="梁雅婷")}, {2, 3})
        self.assertEqual({hit["turn"] for hit in memory.retrieve_archive(self.state, "蓝色琴谱", viewer="郭瑞莹")}, {3})

    def test_content_bound_index_invalidates_even_if_size_and_mtime_match(self):
        self.write_archive([self.record(2, "蓝色琴谱放在木桌")])
        before = self.archive.stat()
        self.assertIn("木桌", memory.retrieve_archive(self.state, "蓝色琴谱")[0]["text"])
        self.write_archive([self.record(2, "蓝色琴谱放在纸箱")])
        os.utime(self.archive, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.archive.stat().st_size, before.st_size)
        self.assertIn("纸箱", memory.retrieve_archive(self.state, "蓝色琴谱")[0]["text"])

    def test_relevant_old_appointments_and_messages_keep_speaker_and_proposal(self):
        self.state["appointments"] = [{"turn": 1, "npc": "梁雅婷", "text": "归还蓝色相机", "status": "pending"}]
        self.state["appointments"] += [{"turn": turn, "npc": "郭瑞莹", "text": "讨论天气", "status": "pending"} for turn in range(2, 40)]
        self.assertIn("梁雅婷〔已确认，待兑现〕：归还蓝色相机", memory.appointments_block(self.state, action="蓝色相机"))
        messages = [{"from": "me", "text": "要不周末归还蓝色相机？"}, {"from": "npc", "text": "可以，到时再定。"}]
        messages += [{"from": "me" if turn % 2 else "npc", "text": "晚安"} for turn in range(25)]
        self.state["chats"] = {"梁雅婷": {"msgs": messages}}
        block = memory.chat_context_block(self.state, "问梁雅婷那台蓝色相机")
        self.assertIn("玩家：要不周末归还蓝色相机？", block)
        self.assertIn("未执行的计划不等于任务已完成", block)
        self.assertNotIn("已确认，待兑现", block)

    def test_prompt_outputs_and_query_are_bounded(self):
        for turn in range(90):
            memory.append_fact(self.state, f"答应第{turn}位同学明天去还相机", turn, known_by=["梁雅婷"])
        self.assertLessEqual(len(memory.facts_block(self.state, action="相机" * 5000)), memory.FACTS_PROMPT_BUDGET)
        self.assertLessEqual(len(memory._query_terms(self.state, "相机" * 5000)), memory.QUERY_TERMS)
        self.assertLessEqual(len(memory.archive_block([{"turn": i, "text": "文" * 1000, "chosen": "问" * 300} for i in range(30)])), memory.ARCHIVE_PROMPT_BUDGET)

    def test_old_phone_messages_survive_hot_window_and_keep_speaker_and_owner(self):
        engine._chat_append(self.state, "梁雅婷", "me", "蓝色相机先放在雨棚旁的木柜里，我明天再问你。")
        engine._chat_append(self.state, "梁雅婷", "npc", "先确认清楚，别急着搬。")
        for index in range(models.CHAT_HISTORY_KEPT + 20):
            engine._chat_append(self.state, "梁雅婷", "me", f"第{index}次说晚安")
        self.assertEqual(len(self.state["chats"]["梁雅婷"]["msgs"]), models.CHAT_HISTORY_KEPT)
        self.assertIn("蓝色相机", self.state["chat_history"]["梁雅婷"][0]["text"])
        restored = models.normalize_state(json.loads(json.dumps(self.state)))
        block = memory.chat_context_block(restored, "蓝色相机放在哪里", "梁雅婷")
        self.assertIn("玩家：蓝色相机", block)
        self.assertIn("未执行的计划不等于任务已完成", block)
        self.assertNotIn("蓝色相机", memory.chat_context_block(restored, "蓝色相机", "郭瑞莹"))
        self.assertNotIn("chat_history", models.public_state(restored))
        models._clear_run_records(restored)
        self.assertEqual(restored["chat_history"], {})


if __name__ == "__main__":
    unittest.main()
