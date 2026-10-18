"""M1 前置闭环：新周目→移动→购买→穿越→返回→重启恢复（无模型）。

另覆盖：action_id 幂等、同 ID 异请求拒绝、乐观版本冲突、分支隔离。
运行：.venv/Scripts/python.exe tests/loop_test.py
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.persistence import CampaignRepo, connect, migrate
from app.persistence.repo import RequestMismatch, VersionConflict
from app.rules_core import RulesCore


def new_campaign(directory: Path) -> tuple:
    path = directory / f"{uuid.uuid4().hex[:8]}.sqlite3"
    conn = connect(path)
    migrate(conn)
    repo = CampaignRepo(conn, "cmp:test")
    CampaignRepo.create_campaign(conn, "cmp:test", note="loop_test")
    repo.add_entity("player:hero", "player", "测试侠", aliases=["我", "主角"])
    repo.set_state("player:hero", "position", "place:zhou_home")
    repo.set_state("player:hero", "wallet:cny", 500)
    repo.set_state("player:hero", "wallet:lingshi", 210)
    return path, conn


def action(core: RulesCore, kind: str, target=None, params=None, base_version=None) -> dict:
    return core.act({"action_id": uuid.uuid4().hex, "type": kind, "target": target,
                     "params": params or {}, "source": "button",
                     "base_version": base_version if base_version is not None else core.repo.version()})


class LoopTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path, self.conn = new_campaign(Path(self.directory.name))
        self.addCleanup(self.conn.close)
        self.core = RulesCore(CampaignRepo(self.conn, "cmp:test"))

    def test_full_loop_and_restart_recovery(self):
        # 移动：家 → 学校（0.7 都市小时）
        out = action(self.core, "move", "place:linjiang_school")
        self.assertEqual(out["status"], "success")
        self.assertEqual(self.core._where(), "place:linjiang_school")
        self.assertEqual(out["time_cost"]["base_seconds"], int(0.7 * 3600))

        # 购买：市中心才有都市货架 → 先移动再买
        action(self.core, "move", "place:qinglin_downtown")
        out = action(self.core, "buy", "item:water_bottle", {"amount": 4})
        self.assertEqual(out["status"], "success")
        self.assertEqual(self.core.repo.get_state("player:hero", "wallet:cny"), 500 - 12)
        self.assertEqual(self.core.repo.count_item("player:hero", "item:water_bottle"), 4)

        # 穿越：都市 → 玄灵界，首穿落点＝落星荒野（正典）
        out = action(self.core, "cross")
        self.assertEqual(out["status"], "success")
        self.assertEqual(self.core._where(), "place:luoxing_wild")
        self.assertEqual(out["time_cost"]["base_seconds"], 0)

        # 玄灵界移动：落星荒野 → 青石村（6 玄灵小时 ×24）
        out = action(self.core, "move", "place:qingshi_village")
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["time_cost"]["base_seconds"], 6 * 3600 * 24)

        # 返回穿越：落点守恒 → 回到离开都市时的地点（市中心）
        out = action(self.core, "cross")
        self.assertEqual(self.core._where(), "place:qinglin_downtown")

        version = self.core.repo.version()
        events_before = [row["seq"] for row in self.core.repo.events()]

        # 重启恢复：关闭连接，重开数据库，状态一致
        self.conn.close()
        conn2 = connect(self.path)
        repo2 = CampaignRepo(conn2, "cmp:test")
        core2 = RulesCore(repo2)
        self.assertEqual(core2._where(), "place:qinglin_downtown")
        self.assertEqual(repo2.get_state("player:hero", "wallet:cny"), 488)
        self.assertEqual(repo2.count_item("player:hero", "item:water_bottle"), 4)
        self.assertEqual(repo2.version(), version)
        self.assertEqual([row["seq"] for row in repo2.events()], events_before)
        self.assertEqual(repo2.get_state("player:hero", "last_pos:xianxia"), "place:qingshi_village")
        conn2.close()

    def test_action_id_is_idempotent(self):
        act = {"action_id": "act-fixed-1", "type": "move", "target": "place:linjiang_school",
               "params": {}, "source": "button", "base_version": self.core.repo.version()}
        first = self.core.act(dict(act))
        version_after = self.core.repo.version()
        second = self.core.act(dict(act))
        self.assertEqual(first["status"], "success")
        self.assertTrue(second.get("from_cache"))
        self.assertEqual(second["events"], first["events"])  # 不重复落事件
        self.assertEqual(self.core.repo.version(), version_after)  # 版本只推进一次
        with self.assertRaises(RequestMismatch):
            self.core.act({**act, "target": "place:qinglin_downtown"})

    def test_version_conflict_rejected_without_side_effects(self):
        # 旧版本提交：handler 执行后提交被拒，全部中间写入回滚
        stale = action(self.core, "move", "place:linjiang_school",
                       base_version=self.core.repo.version() - 1)
        self.assertEqual(stale["status"], "tech_error")
        self.assertEqual(self.core._where(), "place:zhou_home")   # 移动被回滚
        self.assertEqual(self.core.base_time(), 0)                # 时钟未推进
        self.assertEqual(len(self.core.repo.events()), 0)         # 事件未落账

    def test_branch_isolation(self):
        repo = self.core.repo
        action(self.core, "move", "place:linjiang_school")
        repo.fork_branch("br:alt", fork_seq=1)
        alt = CampaignRepo(self.conn, "cmp:test", branch="br:alt")
        alt.set_state("player:hero", "position", "place:qinglin_downtown")
        # 分支各自的世界键隔离；alt 的新增不进 main
        self.assertEqual(alt.get_world("world_version", 0), 0)
        self.assertGreater(repo.get_world("world_version", 0), 0)
        self.assertEqual(alt.get_state("player:hero", "position"), "place:qinglin_downtown")
        self.assertEqual(self.core._where(), "place:linjiang_school")

    def test_refusals_are_game_results(self):
        out = action(self.core, "move", "place:baixi_town")  # 无路线（不同界）
        self.assertEqual(out["status"], "refused")
        self.assertIn("没有可用路线", out["reason"])
        out = action(self.core, "buy", "item:liao_shang_dan")  # 此处不售
        self.assertEqual(out["status"], "refused")
        out = action(self.core, "alchemy")
        self.assertEqual(out["status"], "refused")
        self.assertIn("暂不支持", out["reason"])
        # 拒绝不推进时钟、不落事件
        self.assertEqual(self.core.base_time(), 0)
        self.assertEqual(len(self.core.repo.events()), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
