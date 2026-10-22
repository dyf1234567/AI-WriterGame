"""沙盒活动与人生目标的事实约束。所有测试只使用内存存档。"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import goals, world_events as events, skills
from app.models import CASH, CURRENCY, default_state
from app.shop import currency_count


class SandboxEventsGoalsTest(unittest.TestCase):
    def state(self, day=4):
        state = default_state("沙盒验证")
        state["time"] = {"day": day, "slot": 0}
        state["turn"] = 8
        return state

    def present(self, state, eid, npc=""):
        state["director"] = {"active": {"id": eid, "day": events.game_today(state), "npc": npc},
                             "history": [], "last_event_turn": state["turn"]}
        events._instance(state, eid, context=state["director"]["active"])

    def test_result_bands_and_repeat_protection(self):
        low = self.state()
        data = events.before_turn(low, "【活动】gala:sing")
        self.assertIn("脑子一片空白", data["story_text"])
        self.assertNotIn("经纪公司试镜邀请", low["player"].get("career", {}).get("opportunities", []))
        high = self.state()
        skills.add_xp(high, "vocal", 110)
        events.before_turn(high, "【活动】gala:sing")
        self.assertIn("经纪公司试镜邀请", high["player"]["career"]["opportunities"])
        before = copy.deepcopy(high)
        with self.assertRaisesRegex(ValueError, "已经结束"):
            events.before_turn(high, "【活动】gala:sing")
        self.assertEqual(before, high)
        self.assertIsNone(events.event_today(high))

    def test_real_cash_reward_not_system_points(self):
        state = self.state(day=5)
        skills.add_xp(state, "mech", 110)
        cash, points = currency_count(state, CASH), currency_count(state, CURRENCY)
        events.before_turn(state, "【活动】arena:solo")
        self.assertEqual(currency_count(state, CASH), cash + 80)
        self.assertEqual(currency_count(state, CURRENCY), points)
        with self.assertRaises(ValueError):
            events.before_turn(state, "【活动】arena:solo")
        self.assertEqual(currency_count(state, CASH), cash + 80)

    def test_preparation_and_sponsorship_are_factual(self):
        state = self.state()
        skills.add_xp(state, "vocal", 1)  # L1，准备后等效L2
        result = events.before_turn(state, "【活动】gala:prepare")
        self.assertEqual(result["state_updates"]["duration_minutes"], 60)
        with self.assertRaises(ValueError):
            events.before_turn(state, "【活动】gala:prepare")
        events.before_turn(state, "【活动】gala:sing")
        self.assertEqual(state["events"]["experience"][-1]["outcome"], "win")
        sponsor = self.state()
        cash = currency_count(sponsor, CASH)
        affinity = [n["affinity"] for n in sponsor["npcs"]]
        events.before_turn(sponsor, "【活动】gala:sponsor")
        self.assertEqual(currency_count(sponsor, CASH), cash - 30)
        self.assertEqual([n["affinity"] for n in sponsor["npcs"]], affinity)
        poor = self.state()
        for item in poor["player"]["items"]:
            if item["name"] == CASH:
                item["count"] = 0
        with self.assertRaisesRegex(ValueError, "现金不足"):
            events.before_turn(poor, "【活动】gala:sponsor")

    def test_world_moves_without_player_participation(self):
        state = self.state()
        before = currency_count(state, CASH)
        events.event_today(state)
        notices = events.settle_elapsed(state, 4, 8)
        self.assertTrue(notices)
        self.assertEqual(currency_count(state, CASH), before)
        self.assertTrue(any(x["template"] == "gala" and x["role"] == "absent"
                            for x in state["events"]["history"]))
        self.assertEqual(state["events"]["experience"], [])
        count = len(state["events"]["history"])
        self.assertEqual(events.settle_elapsed(state, 4, 8), [])
        self.assertEqual(len(state["events"]["history"]), count)

    def test_forty_distinct_templates_settle_all_result_bands(self):
        self.assertEqual(len(events._EVENTS), 40)
        names = {t["name"] for t in events._EVENTS.values()}
        self.assertEqual(len(names), 40)
        for eid, template in events._EVENTS.items():
            for level in (0, 10):
                with self.subTest(event=eid, level=level):
                    state = self.state(day=2)
                    self.present(state, eid, "郭瑞莹" if template.get("dynamic_npc") else "")
                    for sid in skills.SKILLS:
                        if level:
                            skills.add_xp(state, sid, 1000)
                    choice = template["options"][0]["id"]
                    result = events.before_turn(state, f"【活动】{eid}:{choice}")
                    self.assertTrue(result["story_text"])
                    self.assertNotIn("{npc}", result["story_text"])
                    self.assertEqual(len(state["events"]["experience"]), 1)

    def test_causal_cross_domain_director(self):
        state = self.state(day=2)
        state["events"] = {"experience": [{"id": "past", "template": "gala", "domain": "娱乐", "outcome": "win"}]}
        offer = events.event_today(state)
        self.assertEqual(offer["id"], "media_company")
        self.assertIn("表演经历", offer["reason"])
        self.assertIsNone(events.resolve_action(state, "明天打算参加传媒创业圆桌"))
        self.assertEqual(events.resolve_action(state, "我出资赞助传媒创业圆桌"), "【活动】media_company:sponsor")

    def test_objective_goal_cannot_be_forged_by_diary_or_model(self):
        state = self.state()
        result = goals.create_goal(state, "创办估值十亿元公司")
        self.assertTrue(result["ok"])
        goal = state["goals"][0]
        self.assertEqual(goal["mode"], "objective")
        for index in range(30):
            state["time"]["day"] += 1
            state["turn"] += 1
            self.assertFalse(goals.manual_progress(state, goal["id"], "公司已经估值十亿")["ok"])
            goals.apply_model_progress(state, [{"id": goal["id"], "delta": 100}])
        self.assertEqual(goal["progress"], 0)
        self.assertEqual(goal["status"], "active")
        state["player"]["enterprises"] = [{"id": "ent_1", "kind": "company", "name": "第一家公司",
                                               "valuation": 1e9, "equity": {"player": 60, "external": 40}}]
        goals.sync_objectives(state)
        self.assertEqual(goal["status"], "completed")
        self.assertTrue(all(item["done"] for item in goal["milestones"]))

    def test_skill_work_champion_and_graduation_require_records(self):
        state = self.state()
        result = goals.create_goal(state, "年度真实成果", criteria=[
            {"metric": "skill_level", "skill": "vocal", "target": 3},
            {"metric": "released_works", "target": 1},
            {"metric": "championships", "target": 1},
            {"metric": "graduated", "target": 1}])
        self.assertTrue(result["ok"])
        goal = state["goals"][0]
        skills.add_xp(state, "vocal", 210)
        state["player"]["enterprises"] = [
            {"id": "w", "kind": "work", "status": "ready", "equity": {"player": 100}},
            {"id": "t", "kind": "team", "trophies": 0, "equity": {"player": 100}}]
        goals.sync_objectives(state)
        self.assertEqual(goal["progress"], 25)
        self.assertEqual([x["done"] for x in goal["milestones"]], [True, False, False, False])
        state["player"]["enterprises"][0]["status"] = "released"
        state["player"]["enterprises"][1]["trophies"] = 1
        state["player"]["education"] = {"status": "graduated"}
        goals.sync_objectives(state)
        self.assertEqual(goal["status"], "completed")

    def test_subjective_goals_and_legacy_completions_preserved(self):
        state = self.state()
        result = goals.create_goal(state, "好好整理自己的心情")
        goal = state["goals"][0]
        self.assertTrue(goals.manual_progress(state, goal["id"], "写了一页心情日记")["ok"])
        self.assertEqual(goal["progress"], 5)
        self.assertFalse(any(item["done"] for item in goal["milestones"]))
        state["goals"].append({"id": "old", "title": "创办估值十亿元公司", "status": "completed", "progress": 100})
        goals.ensure_goals(state)
        goals.sync_objectives(state)
        self.assertEqual(state["goals"][-1]["status"], "completed")
        self.assertTrue(state["goals"][-1]["legacy_completion"])
        self.assertFalse(goals.create_goal(state, "无效判据", criteria={"metric": "invented", "target": 1})["ok"])
        self.assertEqual(goals.infer_criteria("三年内发行一首单曲")[0]["target"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
