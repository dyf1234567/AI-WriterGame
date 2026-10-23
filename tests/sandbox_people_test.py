"""人物自主生活、八条成长弧、关系同意与可选暗线的离线规则验证。"""
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["SJL_DATA_DIR"] = tempfile.mkdtemp(prefix="sandbox-people-")
for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
    os.environ[key] = ""
_path_exists = Path.exists
with patch.object(Path, "exists", lambda p: False if p == ROOT / ".env" else _path_exists(p)):
    from app.models import default_state, find_npc
    from app import character_arcs, lore, relationships, world_sim


class PeopleTests(unittest.TestCase):
    def fresh(self):
        state = default_state("人物验证")
        world_sim.ensure_world(state)
        return state

    def known(self, state, name="梁雅婷"):
        npc = find_npc(state, name)
        npc["known_to_player"] = True
        return npc

    def ready(self, state, name="梁雅婷"):
        npc = self.known(state, name)
        state["dates"] += [{"npc": name, "day": 1}, {"npc": name, "day": 2}]
        return npc

    def test_plans_execute_and_repeat_is_idempotent(self):
        state = self.fresh()
        npc = self.known(state)
        npc["life"]["next"] = {"day": 3, "slot": 2, "place": "京华大学", "text": "递交采访稿"}
        notices = world_sim.advance_world(state, 1, 4)
        self.assertTrue(any("递交采访稿" in n for n in notices))
        self.assertEqual(npc["life"]["completed"][0]["day"], 3)
        self.assertGreater(npc["life"]["next"]["day"], 4)
        snapshot = deepcopy(state)
        self.assertEqual(world_sim.advance_world(state, 1, 4), [])
        self.assertEqual(state, snapshot)

    def test_first_time_advance_uses_from_day(self):
        state = default_state("迁移")
        state["time"]["day"] = 90
        world_sim.advance_world(state, 1, 90)
        self.assertEqual(state["world_sim"]["last_day"], 90)
        self.assertTrue(state["character_arcs"]["梁雅婷"]["completed"])

    def test_unknown_people_not_in_public_view(self):
        state = self.fresh()
        world_sim.advance_world(state, 1, 120)
        self.assertEqual(world_sim.people_view(state), [])
        self.assertEqual(world_sim.world_view(state)["arcs"], [])
        self.assertTrue(state["world_sim"]["background"])
        self.assertFalse(state.get("facts"))
        self.assertEqual(world_sim.mystery_view(state)["status"], "dormant")

    def test_each_core_arc_all_four_choices_and_ignore(self):
        self.assertEqual(len(character_arcs.ARCS), 8)
        for name in character_arcs.ARCS:
            for choice in ("合作", "支持", "竞争", "放手", "忽略"):
                with self.subTest(name=name, choice=choice):
                    state = self.fresh()
                    npc = self.known(state, name)
                    for stage in range(3):
                        arc = state["character_arcs"][name]
                        state["time"]["day"] = arc["available_day"]
                        if choice != "忽略":
                            character_arcs.before_turn(state, f"【人物】{name}:{choice}")
                            with self.assertRaises(ValueError):
                                character_arcs.before_turn(state, f"【人物】{name}:{choice}")
                        due = arc["due_day"]
                        world_sim.advance_world(state, state["world_sim"]["last_day"], due)
                    self.assertTrue(arc["completed"])
                    self.assertEqual([h["stage"] for h in arc["history"]], [1, 2, 3])
                    self.assertTrue(all(h["choice"] == choice for h in arc["history"]))
                    self.assertEqual(relationships.ensure_relationship(npc)["status"], "friend")

    def test_meeting_channels_have_real_requirements(self):
        state = self.fresh()
        with self.assertRaises(ValueError):
            character_arcs.before_turn(state, "【人物】傲寒:相识:音乐现场")
        state["player"]["location"]["place"] = "回声Livehouse"
        character_arcs.before_turn(state, "【人物】傲寒:相识:音乐现场")
        self.assertTrue(find_npc(state, "傲寒")["known_to_player"])
        character_arcs.before_turn(state, "【人物】郭瑞莹:相识:旧友联络")
        self.assertTrue(find_npc(state, "郭瑞莹")["known_to_player"])

    def test_high_affinity_does_not_force_relationship(self):
        state = self.fresh()
        npc = self.known(state)
        answer = relationships.relationship_action(state, npc["name"], "表白")
        self.assertFalse(answer["ok"])
        self.assertEqual(npc["relationship"]["status"], "friend")

    def test_explicit_confirmation_breakup_and_distance(self):
        state = self.fresh()
        npc = self.ready(state)
        answer = relationships.relationship_action(state, npc["name"], "表白")
        self.assertTrue(answer["pending"])
        self.assertEqual(npc["relationship"]["status"], "friend")
        self.assertTrue(relationships.relationship_action(state, npc["name"], "确认")["ok"])
        self.assertEqual(npc["relationship"]["status"], "partner")
        self.assertTrue(relationships.relationship_action(state, npc["name"], "异地")["ok"])
        state["player"]["location"]["place"] = "云顶天文台"
        self.assertFalse(relationships.relationship_action(state, npc["name"], "重逢")["ok"])
        state["player"]["location"]["place"] = npc["place"]
        self.assertTrue(relationships.relationship_action(state, npc["name"], "重逢")["ok"])
        self.assertTrue(relationships.relationship_action(state, npc["name"], "分手")["ok"])
        self.assertTrue(relationships.relationship_action(state, npc["name"], "复合")["pending"])

    def test_nonexclusive_needs_each_person_consent(self):
        state = self.fresh()
        first = self.ready(state, "梁雅婷")
        second = self.ready(state, "郭瑞莹")
        self.assertFalse(relationships.relationship_action(state, first["name"], "协商", "poly")["ok"])
        first["boundaries"] = {"principles": "知情同意", "boundary": "可撤回", "romance_style": "接受开放关系与多人关系"}
        relationships.relationship_action(state, first["name"], "表白")
        relationships.relationship_action(state, first["name"], "确认")
        self.assertFalse(relationships.relationship_action(state, second["name"], "表白")["ok"])
        second["boundaries"] = {"principles": "知情同意", "boundary": "可撤回", "romance_style": "接受多人关系"}
        self.assertTrue(relationships.relationship_action(state, second["name"], "协商", "poly")["pending"])
        first["boundaries"]["romance_style"] = "专一"
        self.assertFalse(relationships.relationship_action(state, second["name"], "确认")["ok"])
        self.assertEqual(second["relationship"]["status"], "friend")
        first["boundaries"]["romance_style"] = "接受多人关系"
        relationships.relationship_action(state, second["name"], "协商", "poly")
        self.assertTrue(relationships.relationship_action(state, second["name"], "确认")["ok"])
        self.assertEqual(first["relationship"]["mode"], "poly")
        self.assertEqual(second["relationship"]["mode"], "poly")

    def test_old_consent_expires(self):
        state = self.fresh()
        self.ready(state)
        relationships.relationship_action(state, "梁雅婷", "表白")
        state["time"]["day"] += 8
        self.assertFalse(relationships.relationship_action(state, "梁雅婷", "确认")["ok"])

    def test_optional_mystery_requires_three_evidence_and_resolves(self):
        for ending in ("合作", "旁观"):
            state = self.fresh()
            with self.assertRaises(ValueError):
                world_sim.before_turn(state, "【暗线】核对")
            state["player"]["location"]["place"] = "云顶天文台"
            world_sim.before_turn(state, "【暗线】观察")
            world_sim.before_turn(state, "【暗线】搁置")
            world_sim.advance_world(state, 1, 365)
            self.assertEqual(state["world_sim"]["mystery"]["stage"], 1)
            with self.assertRaises(ValueError):
                world_sim.before_turn(state, "【暗线】查阅")
            world_sim.before_turn(state, "【暗线】继续")
            state["player"]["location"]["place"] = "京华大学"
            world_sim.before_turn(state, "【暗线】查阅")
            state["player"]["location"]["place"] = "云顶天文台"
            world_sim.before_turn(state, "【暗线】接触")
            world_sim.before_turn(state, "【暗线】核对")
            mystery = state["world_sim"]["mystery"]
            self.assertEqual(len(mystery["resolved_clues"]), 3)
            world_sim.before_turn(state, f"【暗线】{ending}")
            self.assertEqual(mystery["status"], "closed")
            self.assertEqual(bool(mystery["permissions"]), ending == "合作")
            self.assertTrue(all(f["closed"] is not None for f in state["facts"]))

    def test_lore_has_restrained_other_power_users(self):
        block = lore.canon_block(self.fresh())
        self.assertNotIn("再无第二个修行者", block)
        self.assertIn("约束", block)
        self.assertIn("玩家尚未取得调查证据", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
