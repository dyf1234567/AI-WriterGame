"""规则边界、失败恢复和并发回归；所有文件写入项目内临时测试目录。"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_BASE_URL="", LLM_API_KEY="", LLM_MODEL="")
from app import engine, storage, memory, config, offline, llm
from app.models import default_state, public_state
from app.main import app
from app.contracts import validate_turn
from fastapi.testclient import TestClient
from pydantic import ValidationError


def payload(updates=None, world="urban", text="测试剧情"):
    return dict(story_text=text, narration_world=world, choices=["观察", "等待"],
                state_updates=updates or {}, system_notice="")


class Regressions(unittest.TestCase):
    def setUp(self):
        root = ROOT / "artifacts" / "regression-temp"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.path = Path(self.temp.name)
        self.patches = []
        for module in (config, storage, memory, engine):
            for attr, relative in {
                "DATA_DIR": ".", "STATE_FILE": "state.json",
                "STORY_ARCHIVE_FILE": "story_archive.jsonl", "NPC_ARCHIVE_FILE": "npc_archive.jsonl",
                "MEMORY_MANUAL_FILE": "memory/manual.md", "MEMORY_STATUS_FILE": "memory/status.json",
            }.items():
                if hasattr(module, attr):
                    item = patch.object(module, attr, self.path / relative)
                    item.start()
                    self.patches.append(item)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def new(self):
        response = self.client.post("/api/new", json={"name": "回归侠"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["state"]

    def test_catalog_before_new_and_no_secrets(self):
        self.assertEqual(self.client.get("/api/shop").status_code, 200)
        self.assertEqual(self.client.get("/api/lottery").status_code, 200)
        state = self.new()
        self.assertEqual(len(storage.load()["npcs"]), 9)
        # 新档预设全员未结识：前台关系网只出现剧情里登场的人（开局剧情最多点亮个别）
        self.assertLessEqual(len(state["npcs"]), 4)
        self.assertNotIn("不得了的人脉", json.dumps(state, ensure_ascii=False))
        self.assertNotIn("装作不认识", json.dumps(state, ensure_ascii=False))
        self.assertIn("server_date", state)

    def test_unfunded_trade_rolls_back_everything(self):
        state = default_state("测试")
        before = deepcopy(state)
        with self.assertRaises(engine.EngineError):
            engine.apply_updates(state, payload({"item_gained": [{"name": "修身西装", "count": 1}],
                "item_spent": [{"name": "系统金币", "count": 400}], "realm_progress_delta": 10}))
        self.assertEqual(state, before)

    def test_same_turn_gain_and_use(self):
        state = default_state("测试")
        engine.apply_updates(state, payload({"item_gained": [{"name": "专注咖啡"}],
            "item_spent": [{"name": "专注咖啡"}]}))
        self.assertFalse(any(i["name"] == "专注咖啡" for i in state["player"]["items"]))

    def test_premature_breakthrough_rejected(self):
        state = default_state("测试")
        before = deepcopy(state)
        with self.assertRaises(engine.EngineError):
            engine.apply_updates(state, payload({"realm_breakthrough": True}))
        self.assertEqual(state, before)
        state["player"]["realm_progress"] = 100
        engine.apply_updates(state, payload({"realm_breakthrough": True}))
        self.assertEqual(state["player"]["realm"], 2)

    def test_location_moves_stay_in_single_world(self):
        state = default_state("测试")
        state["player"]["location"]["place"] = "京华大学"
        # 模型即使申报别的世界，也只会落回唯一的都市世界
        engine.apply_updates(state, payload({"location": {"world": "xianxia", "place": "银杏商街"}}))
        self.assertEqual(state["player"]["world"], "urban")
        self.assertEqual(state["player"]["location"]["place"], "银杏商街")
        self.assertEqual(state["player"]["location"]["city"], "京都")
        self.assertTrue(any(p["name"] == "银杏商街" and p["discovered"]
                            for p in state["map"]["urban"]))

    def test_failed_opening_preserves_state_and_archives(self):
        self.new()
        for path in (engine.STORY_ARCHIVE_FILE, engine.NPC_ARCHIVE_FILE):
            path.write_text("old archive", encoding="utf-8")
        before = {p: p.read_bytes() for p in (storage.STATE_FILE, engine.STORY_ARCHIVE_FILE, engine.NPC_ARCHIVE_FILE)}
        with patch.object(engine, "DEMO_MODE", False), patch.object(engine, "_call_llm_json", side_effect=engine.EngineError("失败")):
            response = self.client.post("/api/new", json={"name": "新局"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_commit_failure_restores_archives(self):
        self.new()
        engine.STORY_ARCHIVE_FILE.write_text("old", encoding="utf-8")
        before = storage.STATE_FILE.read_bytes()
        with patch.object(storage, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                storage.replace_game(default_state("新局"), (engine.STORY_ARCHIVE_FILE, engine.NPC_ARCHIVE_FILE))
        self.assertEqual(storage.STATE_FILE.read_bytes(), before)
        self.assertEqual(engine.STORY_ARCHIVE_FILE.read_text(), "old")

    def test_restore_includes_archives_and_version(self):
        old = self.new()
        engine.STORY_ARCHIVE_FILE.write_text('{"turn":0,"text":"old"}\n', encoding="utf-8")
        backup = storage.snapshot()
        self.new()
        revision = storage.load()["revision"]
        restored = storage.restore(Path(backup).name)
        self.assertGreater(restored["revision"], revision)
        self.assertEqual(restored["player"]["name"], old["player"]["name"])
        self.assertIn("old", engine.STORY_ARCHIVE_FILE.read_text())
        with self.assertRaises(ValueError):
            storage.restore("../../data")

    def test_malformed_turn_cannot_write(self):
        self.new()
        before = storage.STATE_FILE.read_bytes()
        broken = payload({"realm_progress_delta": "a lot"})
        with self.assertRaises(ValidationError):
            validate_turn(broken)
        with patch.object(engine, "DEMO_MODE", False), patch.object(engine, "_call_llm_json", return_value=broken):
            self.assertEqual(self.client.post("/api/act", json={"text": "修炼"}).status_code, 503)
        self.assertEqual(storage.STATE_FILE.read_bytes(), before)

    def test_revision_stops_stale_tab(self):
        state = self.new()
        headers = {"X-State-Revision": str(state["revision"])}
        first = self.client.post("/api/use", json={"name": "系统抽奖券"}, headers=headers)
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/api/use", json={"name": "系统抽奖券"}, headers=headers)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(storage.load()["player"]["lottery"]["total_drawn"], 1)

    def test_concurrent_mutations_are_serialized(self):
        self.new()
        def draw(_):
            return self.client.post("/api/use", json={"name": "系统抽奖券"}).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(draw, range(4)))
        self.assertEqual(codes, [200] * 4)
        self.assertEqual(storage.load()["player"]["lottery"]["total_drawn"], 4)

    def test_offline_failure_preserves_elapsed_time(self):
        state = default_state("测试")
        old = "2026-01-01T00:00:00+00:00"
        state["last_active"] = old
        with patch.object(offline, "DEMO_MODE", False), patch.object(llm, "chat_json", side_effect=llm.ModelServiceError("失败")):
            with self.assertRaises(offline.OfflineError):
                offline.check_offline(state)
        self.assertEqual(state["last_active"], old)

    def test_sdk_auth_errors_do_not_fallback(self):
        class FakeFailure(Exception):
            status_code = 401
        from unittest.mock import MagicMock
        client = MagicMock()
        client.chat.completions.create.side_effect = FakeFailure("bad key")
        with patch.object(llm, "get_client", return_value=client):
            with self.assertRaises(llm.ModelServiceError):
                llm.chat_json("test", "test")
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_failed_transaction_rolls_back_archive_and_state(self):
        self.new()
        before = storage.STATE_FILE.read_bytes()
        with self.assertRaises(RuntimeError):
            with storage.transaction():
                storage.STATE_FILE.write_text("broken", encoding="utf-8")
                storage.STORY_ARCHIVE_FILE.write_text("future event", encoding="utf-8")
                raise RuntimeError("simulated commit failure")
        self.assertEqual(storage.STATE_FILE.read_bytes(), before)
        self.assertFalse(storage.STORY_ARCHIVE_FILE.exists())

    def test_restore_can_recover_a_damaged_current_save(self):
        state = self.new()
        folder = storage.snapshot()
        storage.STATE_FILE.write_text("broken", encoding="utf-8")
        response = self.client.post("/api/restore", json={"name": Path(folder).name},
                                    headers={"X-State-Revision": str(state["revision"])})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(storage.load()["player"]["name"], "回归侠")

    def test_incomplete_backup_is_not_restorable(self):
        self.new()
        folder = Path(storage.snapshot())
        (folder / "complete").unlink()
        self.assertFalse(any(b["id"] == folder.name for b in storage.backups()))
        with self.assertRaises(ValueError):
            storage.restore(folder.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
