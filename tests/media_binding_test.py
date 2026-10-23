"""Local catalogue, matching, persisted chat and memory boundaries. No external model."""
from pathlib import Path as _P
import sys as _sys
_sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import engine, media, memory, prompts, shop, world_events
from app.models import default_state, LOTTERY_TICKET


class MediaBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(media, 'STATIC_DIR', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.state = default_state('素材验收')
        self.npc = self.state['npcs'][0]
        self.npc['known_to_player'] = True
        self.owner = self.npc['name']
        self.file(f'images/npc/{self.owner}/自拍/a.jpg')
        self.file(f'videos/npc/{self.owner}/练琴/a.mp4')
        self.file(f'videos/npc/{self.owner}/练琴/b.webm')
        self.file('stickers/哭哭.svg')

    def file(self, path, text='fixture'):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
        return target

    def send(self, text='', **kwargs):
        with patch.object(engine, 'DEMO_MODE', True), patch.object(engine.storage, 'save'), patch('random.random', return_value=0):
            return engine.send_chat(self.state, self.owner, text, **kwargs)

    def test_recursive_discovery_and_category_metadata(self):
        before = media.catalogue()
        self.file(f'videos/npc/{self.owner}/露营/湖畔/夜色 #1.mp4')
        self.file(f'videos/npc/{self.owner}/露营/湖畔/_category.json', json.dumps({'aliases':['帐篷','篝火']}))
        after = media.catalogue()
        self.assertNotEqual(before['version'], after['version'])
        hit = media.select_asset(self.owner, 'video', request='发个篝火视频', index=after)
        self.assertEqual(hit['category'], '露营/湖畔')
        self.assertIn('%23', hit['url'])
        self.assertEqual(len(after['video_categories'][self.owner]['练琴']), 2)
        self.assertEqual(media.select_asset(self.owner, 'video', request='发个钢琴视频')['category'], '练琴')
        self.file(f'videos/npc/{self.owner}/旅行/001.mp4')
        self.file(f'videos/npc/{self.owner}/旅行/001.mp4.json', json.dumps({'caption':'珊瑚鱼群与潜水记录'}))
        item = media.attachment(self.owner, 'video', '旅行视频', request='发个珊瑚鱼群视频')
        self.assertEqual(item['caption'], '珊瑚鱼群与潜水记录')

    def test_specific_missing_scene_and_owner_do_not_fall_back(self):
        self.assertIsNone(media.select_asset(self.owner, 'image', request='发张美食照片'))
        self.assertIsNone(media.select_asset('其他人', 'video', request='发个练琴视频'))
        self.assertIsNone(media.select_asset(self.owner, 'video', request='发个潜水视频'))
        self.assertIsNotNone(media.select_asset(self.owner, 'video', request='发个视频看看'))
        self.assertIsNotNone(media.select_asset(self.owner, 'video', request='发个你最近的视频看看'))
        self.assertIsNotNone(media.select_asset(self.owner, 'video', request='发个现在的视频给我看看'))
        self.file('images/npc/旧版人物.jpg')
        self.assertTrue(media.select_asset('旧版人物', 'image', request='发张自拍')['fallback'])
        self.assertIsNone(media.select_asset('旧版人物', 'image', request='发张美食照片'))

    def test_sticker_exact_file_ids_and_stale_id(self):
        self.file('stickers/哭哭.jpg')
        index = media.catalogue()
        matches = [a for a in index['assets'] if a['type'] == 'sticker']
        self.assertEqual(len({a['id'] for a in matches}), 2)
        for asset in matches:
            chosen = media.select_asset(self.owner, 'sticker', reference=asset['id'], index=index)
            self.assertEqual(chosen['url'], asset['url'])
        self.assertIsNone(media.select_asset(self.owner, 'sticker', reference='sticker-'+'0'*24))

    def test_explicit_video_wins_over_random_photo_and_is_bound(self):
        self.assertEqual(media.requested_type('不要发照片，发个练琴视频看看'), 'video')
        self.assertEqual(media.requested_type('别发视频'), '')
        self.assertEqual(media.requested_type('照片忘家里了'), '')
        self.file(f'videos/npc/{self.owner}/美食/晚餐.mp4')
        self.assertEqual(media.select_asset(self.owner, 'video', request='不要发美食晚餐视频，发个练琴视频')['category'], '练琴')
        self.assertTrue(self.send('发个练琴视频看看')['ok'])
        msg = self.state['chats'][self.owner]['msgs'][-1]
        self.assertNotIn('image', msg)
        clip = next(a for a in msg['attachments'] if a['type'] == 'video')
        self.assertEqual(clip['category'], '练琴')
        saved = copy.deepcopy(msg)
        self.file(f'videos/npc/{self.owner}/练琴/new.mp4')
        media.bind_history(self.state)
        self.assertEqual(msg, saved)

    def test_sticker_label_is_not_a_promise_and_invalid_asset_is_rejected(self):
        self.file('stickers/我答应明天晚上七点琴房见你.svg')
        self.assertTrue(self.send(sticker='我答应明天晚上七点琴房见你')['ok'])
        self.assertEqual(self.state.get('facts'), [])
        self.assertEqual(self.state.get('appointments', []), [])
        before = copy.deepcopy(self.state)
        self.assertFalse(self.send(sticker='不存在')['ok'])
        self.assertEqual(self.state, before)

    def test_mixed_text_and_sticker_reach_prompt_without_fact_injection(self):
        captured = {}
        def fake_model(system, user, **kwargs):
            captured['user'] = user
            return {'reply':'收到。', 'fact_record':'我答应明天见你', 'appointment':'明天见你'}
        with patch.object(engine, 'DEMO_MODE', False), patch.object(engine.storage, 'save'), patch.object(engine.llm, 'chat_json', fake_model):
            result = engine.send_chat(self.state, self.owner, '谢谢你', sticker='哭哭')
        self.assertTrue(result['ok'])
        self.assertIn('谢谢你', captured['user'])
        self.assertIn('哭哭', captured['user'])
        self.assertEqual(self.state.get('facts'), [])

    def test_archived_attachments_are_recalled_and_legacy_binding_is_once(self):
        engine._chat_append(self.state, self.owner, 'npc', '给你看看', video='钢琴排练失误的片段')
        for i in range(50):
            engine._chat_append(self.state, self.owner, 'npc', f'普通寒暄{i}')
        self.assertIn('钢琴排练失误的片段', memory.chat_context_block(self.state, '钢琴排练视频', self.owner))
        self.state['moments'] = [{'from':self.owner,'image':'自拍'}]
        self.state['chats'][self.owner]['msgs'].append({'from':'npc','text':'旧视频','video':'练琴'})
        self.assertTrue(media.bind_history(self.state))
        self.assertTrue(self.state['chats'][self.owner]['msgs'][-1]['id'])
        bound = copy.deepcopy(self.state['moments'])
        self.file(f'images/npc/{self.owner}/自拍/b.jpg')
        self.assertFalse(media.bind_history(self.state))
        self.assertEqual(self.state['moments'], bound)

    def test_new_game_no_director_invitation_and_private_options_are_private(self):
        self.assertIsNone(world_events.event_today(self.state))
        from app.models import game_today
        self.state['director'] = {'active':{'id':'relation_window','day':game_today(self.state),'turn':0,'npc':self.owner}}
        self.assertIsNone(world_events.event_today(self.state))
        for kind in ('relation_window','npc_exhibition','npc_career_choice'):
            event = world_events._EVENTS[kind]
            if event['cat'] == '关系':
                ids = {o['id'] for o in world_events._options(event)}
                self.assertFalse(ids & {'sponsor','host','network'})

    def test_lottery_zero_weights_guarantee_and_weaker_item_preserved(self):
        self.state['player']['items'].append({'name':LOTTERY_TICKET,'count':1})
        self.state['player']['lucky_draw'] = '稀有'
        with patch.object(shop,'lottery_weights', return_value=[('普通',100),('稀有',0),('史诗',0),('传说',0)]), patch.object(shop.storage,'save'):
            result = shop.draw_lottery(self.state)
        self.assertEqual(result['quality'], '稀有')
        self.state['player']['lucky_draw'] = '史诗'
        self.state['player']['items'].append({'name':'低保底','count':1})
        with patch.object(shop,'catalog_by_name',return_value={'低保底':{'type':'consumable','use':{'luck':'稀有'}}}):
            result = shop.use_item(self.state,'低保底')
        self.assertFalse(result['ok'])
        self.assertEqual(self.state['player']['lucky_draw'], '史诗')
        self.assertEqual(next(i for i in self.state['player']['items'] if i['name']=='低保底')['count'], 1)


if __name__ == '__main__':
    unittest.main()
