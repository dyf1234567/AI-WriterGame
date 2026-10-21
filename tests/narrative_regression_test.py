"""叙事上下文、开局正典与短信契约回归；不读取密钥，不调用模型或正式存档。"""
import os
import sys
import unittest
from copy import deepcopy
from itertools import product
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
    from app import memory, prompts
    from app.contracts import ChatResult
    from app.models import default_state, game_today, time_label
from pydantic import ValidationError


class NarrativeRegressions(unittest.TestCase):
    def test_action_named_tail_npc_keeps_complete_persona_and_recent_memory(self):
        state = default_state("测试")
        target = state["npcs"][-1]
        target["persona"] = "独有经历" * 25
        target["memory"] = ["第一次共同处理排练表", "雨中等车后交换想法", "后来归还借用的相机"]
        target["deeds"] = [{"turn": 1, "text": "记住了相机的归还日"}]
        # 其余十二人同时关联任务、承诺和约定，也不能挤掉本次明确点名者。
        for npc in state["npcs"][:12]:
            npc["place"] = state["player"]["location"]["place"]
            state["side_quests"].append({"title": f"寻找{npc['name']}", "desc": "交接材料", "done": False})
            memory.append_fact(state, f"答应与{npc['name']}交接材料", 1)
        state["appointments"] = [{"npc": npc["name"], "status": "pending", "text": "交接材料"}
                                  for npc in state["npcs"][:12]]
        action = f"我去找{target['name']}归还相机"
        block = prompts._npc_lines(state, action)
        self.assertTrue(block.startswith(f"- {target['name']}（"))
        self.assertIn(target["persona"], block)
        for item in target["memory"]:
            self.assertIn(item, block)
        self.assertIn("记住了相机的归还日", block)
        # 用户提示同样携带本次点名者，即使调用者尚未传 action 给系统提示。
        with patch.object(memory, "retrieve_archive", return_value=[]):
            self.assertIn(target["persona"], prompts.build_turn_user(state, action))

    def test_quest_and_open_promise_people_outrank_roster_and_location(self):
        state = default_state("测试")
        quest_target, promise_target = state["npcs"][-2:]
        state["side_quests"] = [{"title": "归还排练表", "desc": f"找到{quest_target['name']}", "done": False}]
        memory.append_fact(state, f"答应替{promise_target['name']}归还相机", 2)
        block = prompts._npc_lines(state)
        self.assertIn(f"- {quest_target['name']}（", block)
        self.assertIn(f"- {promise_target['name']}（", block)
        self.assertTrue(block.startswith(f"- {quest_target['name']}（"))
        state["side_quests"][0]["done"] = True
        self.assertGreater(prompts._npc_relevance(state, promise_target),
                           prompts._npc_relevance(state, quest_target))
        state["campaign"]["companion"] = quest_target["name"]
        self.assertGreater(prompts._npc_relevance(state, quest_target),
                           prompts._npc_relevance(state, state["npcs"][0]))

    def test_opening_uses_current_date_time_and_character_canon(self):
        state = default_state("测试")
        state["time"] = {"day": 7, "slot": 2}
        user = prompts.build_opening_user(state)
        self.assertIn(game_today(state), user)
        self.assertIn(time_label(state), user)
        self.assertIn("初识同班新生梁雅婷", user)
        self.assertIn("青梅竹马郭瑞莹在魔都音乐学院", user)
        self.assertIn("邓碧瑶是在魔都的游戏网友", user)
        self.assertIn("尚未线下见面", user)
        self.assertNotIn("就在这个夜晚", user)
        self.assertNotIn("隔壁合租公寓的插画师", user)

    def test_shared_appointment_and_chat_keep_confirmation_and_speakers(self):
        state = default_state("测试")
        state["appointments"] = [
            {"npc": "郭瑞莹", "turn": 3, "text": "周末在琴房碰面", "status": "pending"},
            {"npc": "邓碧瑶", "turn": 4, "text": "要不要连麦", "status": "proposed"},
        ]
        state["chats"] = {"郭瑞莹": {"msgs": [
            {"from": "me", "text": "周末我去琴房找你", "ts": "1"},
            {"from": "npc", "text": "好，我把乐谱带上", "ts": "2"}]}}
        block = memory.appointments_block(state)
        self.assertIn("郭瑞莹〔已确认，待兑现〕", block)
        self.assertIn("邓碧瑶〔仅邀约提议，尚未确认〕", block)
        state["appointments"].extend({"npc": "梁雅婷", "turn": turn, "text": "上交材料", "status": "done"}
                                      for turn in range(5, 20))
        self.assertIn("郭瑞莹〔已确认，待兑现〕", memory.appointments_block(state))
        chat = memory.chat_context_block(state, "去找郭瑞莹")
        self.assertIn("玩家：周末我去琴房找你", chat)
        self.assertIn("郭瑞莹：好，我把乐谱带上", chat)
        self.assertIn("未执行的计划不等于任务已完成", chat)
        memory.append_fact(state, "答应郭瑞莹周末归还乐谱", 3)
        memory.resolve_fact(state, "答应郭瑞莹周末归还乐谱", 6)
        facts = memory.facts_block(state)
        self.assertIn("（已了结）：答应郭瑞莹周末归还乐谱", facts)

    def test_system_context_knows_ending_and_action_named_person(self):
        state = default_state("测试")
        target = state["npcs"][-1]
        state["ending"] = {"title": "新篇章", "partner": target["name"], "turn": 20}
        system = prompts.build_system_prompt(state, f"我去找{target['name']}")
        self.assertIn(f"玩家选择的同行者：{target['name']}", system)
        self.assertIn("当前为番外", system)
        self.assertIn("不能靠等级", system)
        self.assertIn(f"- {target['name']}（", system)
        self.assertNotIn("由等级主干自动派生", system)

    def test_main_scene_includes_confirmed_sms_and_related_history(self):
        state = default_state("测试")
        memory.append_fact(state, "答应郭瑞莹周末到琴房归还乐谱", 2)
        state["appointments"] = [{"npc": "郭瑞莹", "text": "周末到琴房归还乐谱", "turn": 2, "status": "pending"}]
        state["chats"] = {"郭瑞莹": {"msgs": [{"from": "me", "text": "周末我带乐谱去琴房", "ts": "2"}]}}
        state["campaign"]["completed"] = ["plan:学业"]
        system = prompts.build_system_prompt(state, "去找郭瑞莹")
        self.assertIn("答应郭瑞莹周末到琴房归还乐谱", system)
        self.assertIn("已确认，待兑现", system)
        self.assertIn("玩家：周末我带乐谱去琴房", system)
        self.assertIn("等级成长目标", system)
        self.assertIn("本季已完结：False", system)
        self.assertNotIn("第0章", system)
        self.assertNotIn("主线面板", system)

    def test_chat_schema_is_backward_compatible_and_bounded(self):
        minimal = ChatResult.model_validate({"reply": "收到"})
        self.assertEqual((minimal.memory, minimal.fact_record, minimal.appointment), ("", None, None))
        full = ChatResult.model_validate({"reply": "周末见", "memory": "讨论了排练",
                                          "fact_record": "玩家确认归还乐谱", "appointment": "周末到琴房"})
        self.assertEqual(full.appointment, "周末到琴房")
        with self.assertRaises(ValidationError):
            ChatResult.model_validate({"reply": "收到", "appointment": {"place": "琴房"}})
        with self.assertRaises(ValidationError):
            ChatResult.model_validate({"reply": "收到", "memory": "长" * 241})

    def test_chat_cannot_turn_npc_reply_into_player_promise_or_quest_result(self):
        state = default_state("测试")
        npc = state["npcs"][0]
        memory.append_fact(state, "答应邓碧瑶替她保守家庭秘密", 1)
        system, user = prompts.build_chat_prompt(state, npc, "周末你有空吗？")
        self.assertIn("不得代玩家承诺", system)
        self.assertIn("appointment 必须为 null", system)
        self.assertIn("不得靠 reply 编造已经赴约", system)
        self.assertIn("周末你有空吗？", user)
        self.assertNotIn("答应邓碧瑶替她保守家庭秘密", system)

    def test_all_288_main_story_paths_reach_player_chosen_ending(self):
        """遍历路线、搭档和四组关键取舍；只在内存里走真实结算，不运行模型或存档。"""
        from app import campaign, engine
        from app.contracts import validate_turn
        cases = product(campaign.ROUTES, campaign.ARCS, ("skill", "team"),
                        ("promise", "deadline"), ("steady", "bold"), ("honest", "future"))
        count = 0
        for route, companion, prep, conflict, show, resolution in cases:
            with self.subTest(route=route, companion=companion, prep=prep,
                              conflict=conflict, show=show, resolution=resolution):
                state = default_state("路径测试")
                steps = [f"plan:{route}", f"team:{companion}", *[f"prepare:{prep}"] * 3,
                         f"conflict:{conflict}", f"present:{show}", f"resolve:{resolution}", "review"]
                for step in steps:
                    previous_day = state["time"]["day"]
                    state["turn"] += 1
                    action = campaign.PREFIX + step
                    data = validate_turn(campaign.before_turn(state, action))
                    engine.apply_updates(state, data, action=action)
                    self.assertGreaterEqual(state["time"]["day"], previous_day)
                self.assertTrue(campaign.campaign_view(state)["finale_ready"])
                self.assertFalse(state.get("ending"), "完成主线不能自动替玩家选择终章")
                # 每条路线允许独行；解锁恋爱选项时也逐一确认选的是玩家指定的人。
                for selected in [None] + [option["name"] for option in campaign.ending_options(state)]:
                    final_state = deepcopy(state)
                    result = campaign.choose_ending(final_state, selected)
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(final_state["ending"]["partner"], selected)
                    self.assertFalse(campaign.campaign_view(final_state)["finale_ready"])
                count += 1
        self.assertEqual(count, 288)


if __name__ == "__main__":
    unittest.main(verbosity=2)
