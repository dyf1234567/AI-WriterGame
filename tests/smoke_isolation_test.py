"""验证冒烟实例握手先于任何游戏请求；全程无服务、无正式存档、无模型。"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_exists = Path.exists
with patch.object(Path, "exists", lambda path: False if path == ROOT / ".env" else _exists(path)):
    from app import main, storage


def load_smoke(data_dir):
    spec = importlib.util.spec_from_file_location("isolated_smoke_test", ROOT / "tests" / "smoke_test.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, {"SJL_DATA_DIR": str(data_dir), "SMOKE_BASE": "http://127.0.0.1:18001"}):
        spec.loader.exec_module(module)
    return module


class SmokeIsolationTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "artifacts" / "smoke-isolation-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name) / "local"
        self.other = Path(self.temp.name) / "other"
        self.local.mkdir()
        self.other.mkdir()
        self.smoke = load_smoke(self.local)
        self.calls = []

    def fake_http(self, method, path, body=None):
        self.calls.append((method, path))
        self.assertEqual(method, "GET", "未验证实例时不应出现任何写请求")
        self.assertTrue(path.startswith("/api/smoke-proof?"))
        challenge = parse_qs(urlparse(path).query)["challenge"][0]
        try:
            return 200, main.api_smoke_proof(challenge)
        except main.HTTPException as exc:
            return exc.status_code, {"detail": exc.detail}

    def test_matching_directory_proves_identity_without_game_reads(self):
        with patch.object(storage, "DATA_DIR", self.local), patch.object(main, "DEMO_MODE", True), \
                patch.object(self.smoke, "call", self.fake_http), \
                patch.object(storage, "load", side_effect=AssertionError("握手不读取存档")):
            self.assertTrue(self.smoke.verify_isolated_instance())
        self.assertEqual(len(self.calls), 1)
        self.assertFalse((self.local / ".smoke-probe.json").exists())

    def test_wrong_server_is_rejected_even_with_stale_local_state(self):
        (self.local / "state.json").write_text('{"old_test": true}', encoding="utf-8")
        with patch.object(storage, "DATA_DIR", self.other), patch.object(main, "DEMO_MODE", True), \
                patch.object(self.smoke, "call", self.fake_http):
            self.assertEqual(self.smoke.main(), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((self.local / "state.json").read_text(encoding="utf-8"), '{"old_test": true}')

    def test_formal_instance_cannot_issue_proof(self):
        with patch.object(storage, "DATA_DIR", ROOT / "data"), patch.object(main, "DEMO_MODE", True), \
                patch.object(self.smoke, "call", self.fake_http):
            self.assertEqual(self.smoke.main(), 1)
        self.assertEqual(len(self.calls), 1)

    def test_real_model_instance_cannot_issue_proof(self):
        with patch.object(storage, "DATA_DIR", self.local), patch.object(main, "DEMO_MODE", False), \
                patch.object(self.smoke, "call", self.fake_http):
            self.assertEqual(self.smoke.main(), 1)

    def test_existing_probe_is_never_reused_or_deleted(self):
        marker = self.local / ".smoke-probe.json"
        marker.write_text('{"token": "stale"}', encoding="utf-8")
        with patch.object(self.smoke, "call", side_effect=AssertionError("旧凭据应在请求前拒绝")):
            self.assertEqual(self.smoke.main(), 1)
        self.assertEqual(marker.read_text(encoding="utf-8"), '{"token": "stale"}')

    def test_forged_proof_is_rejected_before_new_game(self):
        with patch.object(self.smoke, "call", return_value=(200, {"proof": "0" * 64})) as request:
            self.assertEqual(self.smoke.main(), 1)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[0], "GET")

    def test_formal_directory_alias_and_subdirectory_are_rejected(self):
        for path in (ROOT / "data" / ".." / "data", ROOT / "data" / "nested"):
            with self.subTest(path=path), self.assertRaises(SystemExit):
                load_smoke(path)


if __name__ == "__main__":
    unittest.main()
