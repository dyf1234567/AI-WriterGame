"""Game-clock, migration, privacy and in-process endpoint boundaries; no sockets."""
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import actions, economy, engine, life_clock, main, memory, models, shop, storage, world_sim


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.state = models.default_state('边界验证')

    def test_wallet_migration_preserves_points_without_reseeding_cash(self):
        s = self.state
        s['player']['items'] = [{'name': '系统金币', 'count': 40}, {'name': models.CURRENCY, 'count': 2}]
        s['player'].pop('wallets_version')
        economy.ensure_wallets(s)
        self.assertEqual(economy.balance(s, models.CURRENCY), 42)
        self.assertEqual(economy.balance(s), 200)
        before = deepcopy(s)
        economy.ensure_wallets(s)
        self.assertEqual(s, before)

    def test_money_cannot_be_sold_as_inventory(self):
        before = deepcopy(self.state)
        for currency in (models.CURRENCY, models.CASH):
            self.assertFalse(shop.sell(self.state, currency)['ok'])
        self.assertEqual(self.state, before)

    def test_reference_future_and_hearsay_are_not_witnesses(self):
        texts = ['你回想起上周和梁雅婷在琴房说过的话，独自整理了笔记。',
                 '你独自写下秘密，想着明天告诉梁雅婷。',
                 '郭瑞莹在电话里提到梁雅婷说过的话。']
        for text in texts:
            self.assertNotIn('梁雅婷', engine._witnesses(self.state, text))
        self.assertIn('梁雅婷', engine._witnesses(self.state, '你把秘密告诉了梁雅婷。'))

    def test_mentioned_person_cannot_learn_private_fact(self):
        s = self.state
        engine.apply_updates(s, {'story_text': '郭瑞莹不在现场。我单独告诉梁雅婷真实身份，不要告诉郭瑞莹。',
                                'narration_world': 'urban', 'choices': ['继续', '离开'],
                                'state_updates': {'fact_record': '我向梁雅婷透露真实身份，要求对郭瑞莹保密'}})
        self.assertEqual(s['facts'][-1]['known_by'], ['梁雅婷'])
        self.assertNotIn('真实身份', memory.facts_block(s, viewer='郭瑞莹'))

    def test_people_and_foreign_places_survive_normalization(self):
        s = self.state
        npc = models.find_npc(s, '梁雅婷')
        npc.update(place='星湾理工学院', role='独立策划人', persona='已有生活经历形成的人格')
        s['player']['location'] = {'world': 'urban', 'country': '星联', 'city': '星湾', 'place': '星湾理工学院'}
        models.normalize_state(s)
        self.assertEqual(npc['place'], '星湾理工学院')
        self.assertEqual(npc['role'], '独立策划人')
        self.assertEqual(s['player']['location']['country'], '星联')
        self.assertEqual(len(s['map']['urban']), 118)

    def test_plan_runs_at_its_slot_and_not_on_an_earlier_read(self):
        s = self.state
        npc = models.find_npc(s, '梁雅婷')
        npc['known_to_player'] = True
        npc['life']['next'] = {'day': 1, 'slot': 2, 'place': '京华大学', 'text': '提交今日采访稿'}
        s['time'].update(slot=1, minute=600, clock_slot=1)
        world_sim.advance_world(s, 1, 1)
        self.assertFalse(npc['life'].get('completed'))
        life_clock.advance_minutes(s, 300)
        world_sim.advance_world(s, 1, 1)
        self.assertTrue(npc['life']['completed'])
        before = deepcopy(s)
        self.assertEqual(world_sim.advance_world(s, 1, 1), [])
        self.assertEqual(s, before)

    def test_subday_long_work_cannot_grant_whole_day_wage(self):
        before = deepcopy(self.state)
        with patch.object(storage, 'save'):
            for action in ('【时间】工作 1分钟', '【时间】训练 声乐 2小时', '【时间】上课 半天'):
                with self.assertRaises(engine.EngineError):
                    engine.take_turn(self.state, action)
        self.assertEqual(self.state, before)

    def test_world_actions_do_not_gain_transaction_authority_from_narrator(self):
        from app.actions import proposal_command
        with self.assertRaises(ValueError):
            proposal_command(self.state, '向她问好', {'kind': 'career', 'command': '融资 ent_1 60'})
        with self.assertRaises(ValueError):
            proposal_command(self.state, '我只是问怎么成立公司', {'kind': 'career', 'command': '创办 公司'})

    def test_questions_and_hypotheses_do_not_execute_world_actions(self):
        for text in ('去合租公寓需要多少钱？', '前往樱京音乐学园需要什么',
                     '如果成立一家传媒公司，需要准备什么？', '能否加入娱乐行业',
                     '假如工作十天会怎么样', '申请休学需要哪些材料'):
            self.assertEqual(actions.resolve_action(self.state, text), text)
            with self.assertRaises(ValueError):
                actions.proposal_command(self.state, text, {'kind': 'career', 'command': '创办 公司'})
        self.assertEqual(actions.resolve_action(self.state, '【旅行】合租公寓'), '【旅行】合租公寓')
        self.assertEqual(actions.resolve_action(self.state, '前往合租公寓'), '【旅行】合租公寓')

    def test_inquiry_cannot_gain_mutation_authority_from_ordinary_model_updates(self):
        before = deepcopy(self.state)
        data = {'story_text': '梁雅婷在电话里回答了你关于去合租公寓的交通问题。',
                'narration_world': 'urban', 'choices': ['继续聊天', '了解其他安排'],
                'state_updates': {'location': {'place': '合租公寓'},
                                  'item_spent': [{'name': models.CASH, 'count': 8, 'reason': '交通费'}],
                                  'item_gained': [{'name': models.CASH, 'count': 100}],
                                  'identity_update': {'world': 'urban', 'title': '未经同意的公司创始人'},
                                  'duration_minutes': 600, 'scene_npcs': ['梁雅婷']}}
        with patch.object(engine, 'DEMO_MODE', False), patch.object(engine, '_call_llm_json', return_value=data), \
             patch.object(storage, 'save'), patch.object(engine, 'maybe_compact', return_value=''):
            result, _ = engine.take_turn(self.state, '去合租公寓需要多少钱？')
        self.assertEqual(result['player']['location'], before['player']['location'])
        self.assertEqual(result['player']['identity'], before['player']['identity'])
        self.assertEqual(economy.wallets_view(result), economy.wallets_view(before))
        self.assertEqual(life_clock.absolute_minute(result) - life_clock.absolute_minute(before), 15)
        self.assertTrue(models.find_npc(result, '梁雅婷')['known_to_player'])

    def test_verified_zero_minute_trip_matches_map_quote(self):
        s = self.state
        s['power']['stage'] = 5
        before = life_clock.absolute_minute(s)
        with patch.object(storage, 'save'), patch.object(engine, 'maybe_compact', return_value=''):
            result, _ = engine.take_turn(s, '【旅行】合租公寓')
        self.assertEqual(life_clock.absolute_minute(result), before)
        self.assertEqual(economy.balance(result), economy.balance(s))
        engine.apply_updates(s, {'story_text': '你安静地整理了刚才的见闻。', 'state_updates': {'duration_minutes': 0}})
        self.assertEqual(life_clock.absolute_minute(s) - before, 15)

    def test_model_trip_charges_transport_once_before_spend_validation(self):
        s = self.state
        s['player']['items'] = [{'name': models.CASH, 'count': 8}]
        before = life_clock.absolute_minute(s)
        engine.apply_updates(s, {'story_text': '你乘车来到合租公寓。', 'state_updates': {
            'location': {'world': 'urban', 'place': '合租公寓'}, 'duration_minutes': 30,
            'item_spent': [{'name': models.CASH, 'count': 8, 'reason': '市内交通费'}]}})
        self.assertEqual(economy.balance(s), 0)
        self.assertEqual(life_clock.absolute_minute(s) - before, 30)

    def test_model_trip_preserves_other_consumption_and_uses_route_minimum(self):
        for reason in ('餐饮', '交通与餐饮'):
            s = models.default_state('消费边界')
            before = life_clock.absolute_minute(s)
            engine.apply_updates(s, {'story_text': '你乘车来到合租公寓，吃了一份早餐。', 'state_updates': {
                'location': {'place': '合租公寓'}, 'duration_minutes': 20,
                'item_spent': [{'name': models.CASH, 'count': 8, 'reason': reason}]}})
            self.assertEqual(economy.balance(s), 184)
            self.assertEqual(life_clock.absolute_minute(s) - before, 30)

    def test_new_destination_uses_same_quote_for_deduplication(self):
        s = self.state
        engine.apply_updates(s, {'story_text': '你乘车来到小巷的新书店。', 'state_updates': {
            'location': {'place': '小巷书店'}, 'duration_minutes': 30,
            'new_places': [{'name': '小巷书店', 'desc': '新开的小书店', 'type': 'culture'}],
            'item_spent': [{'name': models.CASH, 'count': 8, 'reason': '交通费'}]}})
        self.assertEqual(economy.balance(s), 192)
        self.assertEqual(s['player']['location']['place'], '小巷书店')

    def test_legacy_scene_defaults_keep_activity_time_beside_travel(self):
        for date_with, expected in ((None, 45), ('郭瑞莹', 150)):
            s = models.default_state('默认耗时')
            npc = models.find_npc(s, '郭瑞莹')
            npc.update(known_to_player=True, affinity=80)
            npc['bond'].update(trust=40, attraction=30)
            before = life_clock.absolute_minute(s)
            engine.apply_updates(s, {'story_text': '郭瑞莹答应了邀约，你们在合租公寓相聚。',
                                    'state_updates': {'location': {'place': '合租公寓'}, 'date_with': date_with}})
            self.assertEqual(life_clock.absolute_minute(s) - before, expected)

    def test_life_action_history_uses_readable_labels(self):
        self.assertEqual(engine._chain_action_label(self.state, '【时间】工作 vocal 10天'), '工作10天')
        self.assertEqual(engine._chain_action_label(self.state, '【时间】训练 vocal 10天'), '声乐训练10天')
        self.assertEqual(engine._chain_action_label(self.state, '【旅行】合租公寓'), '前往合租公寓')
        self.assertEqual(engine._chain_action_label(self.state, '【生活】练习 vocal'), '练习声乐')

    def test_direct_endpoints_use_one_persistent_isolated_save(self):
        directory = ROOT / 'artifacts' / 'sandbox-boundary-temp'
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            path = Path(temporary)
            with patch.object(storage, 'DATA_DIR', path), patch.object(storage, 'STATE_FILE', path/'state.json'), \
                 patch.object(engine, 'STORY_ARCHIVE_FILE', path/'story.jsonl'), \
                 patch.object(engine, 'NPC_ARCHIVE_FILE', path/'npc.jsonl'), \
                 patch.object(memory, 'export_manual', return_value=True):
                created = main.api_new(main.NewReq(name='接口行程'))
                self.assertEqual(created['state']['wallets']['cash'], 200)
                advanced = main.api_time(main.TimeReq(days=10, activity='work'))
                self.assertEqual(advanced['state']['time']['day'], 11)
                traveled = main.api_travel(main.TravelReq(destination='星湾理工学院'))
                self.assertEqual(traveled['state']['player']['location']['country'], '星联')
                points = traveled['state']['wallets']['points']
                self.assertEqual(traveled['state']['wallets']['cash'], 200+10*35-480)
                self.assertEqual(points, 3)
                restored = main.api_resume()
                self.assertEqual(restored['state']['time'], traveled['state']['time'])
                routes = [r for r in main.app.routes if getattr(r,'path','') == '/api/signin']
                self.assertEqual(len(routes), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
