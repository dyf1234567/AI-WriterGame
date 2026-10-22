"""从真实开局和正常收入走完跨领域人生；无模型、无正式存档写入。"""
import os
import sys
import unittest
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_BASE_URL="", LLM_API_KEY="", LLM_MODEL="")
_exists = Path.exists
with patch.object(Path, "exists", lambda path: False if path == ROOT / ".env" else _exists(path)):
    from app import career, economy, engine, enterprises, geography, goals, life_clock, memory, offline, skills, storage
    from app.models import CASH, CURRENCY, default_state, find_npc


def scene(text, **updates):
    return {"story_text": text, "narration_world": "urban", "choices": ["继续今天的生活", "看看自己的安排"],
            "state_updates": updates, "system_notice": ""}


def durable_state(state):
    """排除查询时间和展示摘要，仅比较有游戏意义的事实。"""
    return {"wallets": economy.wallets_view(state), "time": deepcopy(state["time"]),
            "positions": deepcopy(state["player"]["career"]["positions"]),
            "projects": deepcopy(state["player"]["career"]["projects"]),
            "enterprises": deepcopy(state["player"].get("enterprises", [])),
            "people": [{"name": n["name"], "autonomy": deepcopy(n.get("autonomy")),
                        "life": deepcopy(n.get("life")), "relationship": deepcopy(n.get("relationship"))}
                       for n in state["npcs"]],
            "event_history": deepcopy(state.get("events", {}).get("history", [])),
            "facts": deepcopy(state.get("facts", [])), "arcs": deepcopy(state.get("character_arcs", {}))}


class SandboxIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(storage, "save", return_value=None))
        self.stack.enter_context(patch.object(storage, "replace_game", return_value=None))
        self.stack.enter_context(patch.object(engine, "maybe_compact", return_value=""))
        self.stack.enter_context(patch.object(engine, "_call_llm_json", side_effect=AssertionError("不得调用模型")))
        self.state = engine.start_game("人生链路验证")

    def turn(self, action):
        self.state, notice = engine.take_turn(self.state, action)
        return notice

    def test_cross_domain_second_life_from_initial_funds(self):
        self.assertEqual(economy.balance(self.state, CASH), 200)
        self.assertEqual(economy.balance(self.state, CURRENCY), 3)
        self.assertEqual(len(self.state["map"]["urban"]), 118)
        initial_minute = life_clock.absolute_minute(self.state)
        self.turn("【时间】训练 vocal 9天")
        self.assertEqual(life_clock.absolute_minute(self.state)-initial_minute, 9*1440)
        self.assertGreaterEqual(skills.level(self.state, "vocal"), 2)
        self.turn("【时间】休息 1天")
        self.assertEqual(self.state["time"]["day"], 11)
        self.turn("【活动】gala:sing")
        self.assertIn("经纪公司试镜邀请", career.ensure_career(self.state)["opportunities"])
        self.turn("进入娱乐行业")
        self.assertIn("娱乐", career.ensure_career(self.state)["positions"])
        self.turn("【时间】工作 30天")
        self.assertGreaterEqual(economy.balance(self.state), 1000)
        self.turn("【时间】训练 vocal 20天")
        self.turn("【事业】经营 项目 single steady")
        project = deepcopy(career.ensure_career(self.state)["projects"][0])
        self.turn("快进14天")
        finished = next(p for p in self.state["player"]["career"]["projects"] if p["id"] == project["id"])
        self.assertEqual(finished["status"], "completed")
        self.assertEqual(finished["completed_day"], project["end_day"])
        work_id = finished["work_id"]
        self.turn("发行我的单曲作品")
        work = enterprises.find(self.state, work_id, "work")
        self.assertEqual(work["status"], "released")
        self.assertGreater(work["audience"], 0)
        self.turn("创办星河传媒公司")
        company = enterprises.find(self.state, "", "company")
        company_id = company["id"]
        self.assertEqual(company["equity"]["player"], 100)
        self.turn("收购一支战队")
        team = enterprises.find(self.state, "", "team")
        team_id = team["id"]
        self.turn("前往京华创业园")
        self.turn("【地点】0")  # 实际参加创业交流，取得第三领域机遇。
        self.turn("进入商业行业")
        identities = set(career.ensure_career(self.state)["positions"])
        known_life_before = sum(n.get("autonomy", {}).get("work_progress", 0) for n in self.state["npcs"])
        self.turn("【时间】休息 三个月")
        self.assertEqual(set(career.ensure_career(self.state)["positions"]), identities)
        self.assertEqual(identities, {"娱乐", "电竞", "商业"})
        self.assertEqual(enterprises.find(self.state, company_id)["equity"]["player"], 100)
        self.assertEqual(enterprises.find(self.state, team_id)["equity"]["player"], 100)
        self.assertEqual(enterprises.find(self.state, work_id)["status"], "released")
        self.assertGreater(sum(n.get("autonomy", {}).get("work_progress", 0) for n in self.state["npcs"]), known_life_before)
        self.assertGreater(len(enterprises.find(self.state, company_id)["ledger"]), 1)
        self.assertGreaterEqual(economy.balance(self.state), 0)
        self.assertEqual(economy.balance(self.state, CURRENCY), 3)
        self.assertEqual(self.state["campaign"].get("ending"), None)
        self.assertEqual(self.state["world_sim"]["mystery"]["status"], "dormant")
        before = durable_state(self.state)
        life_clock.settle_world(self.state)
        life_clock.settle_world(self.state)
        self.assertEqual(durable_state(self.state), before)

    def test_first_day_founder_is_not_blocked_by_campus_or_skill(self):
        self.turn("我想创办一家工作室")
        self.assertEqual(self.state["time"]["day"], 1)
        self.assertEqual(skills.level(self.state, "manage"), 0)
        self.assertEqual(economy.balance(self.state), 0)
        self.assertEqual(economy.balance(self.state, CURRENCY), 3)
        self.assertEqual(self.state["player"]["education"]["status"], "enrolled")
        self.assertEqual(len(self.state["player"]["enterprises"]), 1)
        self.assertEqual(self.state["player"]["enterprises"][0]["equity"]["player"], 100)

    def test_reality_offline_does_not_advance_world(self):
        self.turn("【时间】工作 10天")
        self.state["last_active"] = "2000-01-01T00:00:00+00:00"
        before = durable_state(self.state)
        offline.check_offline(self.state)
        offline.check_offline(self.state)
        self.assertEqual(durable_state(self.state), before)

    def test_foreign_travel_charges_cash_and_new_place_keeps_atlas(self):
        original_places = {p["name"] for p in self.state["map"]["urban"]}
        snapshot = deepcopy(self.state)
        with self.assertRaises(engine.EngineError):
            self.turn("【旅行】樱京音乐学园")
        self.assertEqual(self.state, snapshot)
        self.turn("【时间】工作 20天")
        quote = geography.travel_quote(self.state, "樱京音乐学园")
        self.assertEqual((quote["cost"], quote["minutes"]), (480, 600))
        before_cash, before_minute = economy.balance(self.state), life_clock.absolute_minute(self.state)
        self.turn("前往樱京音乐学园")
        self.assertEqual(before_cash-economy.balance(self.state), 480)
        self.assertEqual(life_clock.absolute_minute(self.state)-before_minute, 600)
        self.assertEqual(self.state["player"]["location"]["country"], "东瀛")
        self.assertTrue(next(c for c in self.state["map"]["countries"] if c["name"] == "东瀛")["discovered"])
        with patch.object(engine.demo, "next_segment", return_value=scene(
                "你发现了一家可以交流作品的新书店。", new_places=[{"name": "樱京独立书店", "desc": "创作者交流的小书店", "type": "city"}])):
            self.turn("探索一间当地新书店")
        self.assertTrue(original_places.issubset({p["name"] for p in self.state["map"]["urban"]}))
        self.assertEqual(len(self.state["map"]["urban"]), 119)
        self.assertEqual(economy.balance(self.state, CURRENCY), 3)

    def test_absent_names_and_hallucinated_knowledge_do_not_leak_secret(self):
        secret = "梁雅婷其实正在秘密准备转专业申请"
        result = scene("你与梁雅婷在安静的地方商量转专业申请，她说别让郭瑞莹知道。郭瑞莹不在场。",
                       scene_npcs=["梁雅婷", "郭瑞莹"], fact_records=[{"text": secret, "scope": "private"}],
                       knowledge=[{"npc": "郭瑞莹", "fact": secret, "source": "witness", "learned": True}])
        with patch.object(engine.demo, "next_segment", return_value=result):
            self.turn("和梁雅婷私下聊一件需要保密的事")
        fact = next(f for f in self.state["facts"] if f["text"] == secret)
        self.assertIn("梁雅婷", fact["known_by"])
        self.assertNotIn("郭瑞莹", fact["known_by"])
        self.assertNotIn(secret, memory.facts_block(self.state, viewer="郭瑞莹"))
        self.assertIn(secret, memory.facts_block(self.state, viewer="梁雅婷"))

    def test_objective_goal_is_not_completed_by_declared_progress(self):
        result = goals.create_goal(self.state, "创办估值十亿元公司")
        self.assertTrue(result["ok"])
        goal = self.state["goals"][0]
        self.assertFalse(goals.manual_progress(self.state, goal["id"], "已经完成，估值十亿")["ok"])
        with patch.object(engine.demo, "next_segment", return_value=scene("你写了一页关于未来公司的想法。",
                goal_progress=[{"id": goal["id"], "delta": 100, "note": "公司已值十亿"}])):
            self.turn("写下一页创业目标")
        self.assertEqual(self.state["goals"][0]["progress"], 0)
        self.assertEqual(self.state["goals"][0]["status"], "active")
        self.assertEqual(self.state["player"].get("enterprises", []), [])

    def test_opening_identifies_existing_friends_without_presence_claim(self):
        for name in ("梁雅婷", "郭瑞莹", "邓碧瑶"):
            self.assertTrue(find_npc(self.state, name).get("known_to_player"), name)
        remote = find_npc(self.state, "郭瑞莹")
        self.assertNotEqual(remote.get("place"), self.state["player"]["location"]["place"])

    def test_subday_work_cannot_earn_full_day_wages(self):
        before = economy.balance(self.state)
        try:
            self.turn("【时间】工作 1分钟")
        except engine.EngineError:
            return
        self.assertLess(economy.balance(self.state)-before, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
