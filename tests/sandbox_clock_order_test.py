"""Long plans earn their rewards on completed days, before that day's world settlement."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import actions, career, economy, engine, life_clock, models


def total_xp(state, sid):
    entry = state['player'].get('skills', {}).get(sid)
    return 0 if not entry else (entry['lv'] - 1) * 100 + entry['xp']


class ClockOrderTest(unittest.TestCase):
    def setUp(self):
        self.state = models.default_state('逐日结算')

    def settle_plan(self, command, observer):
        data = actions.before_turn(self.state, command)
        with patch.object(career, 'settle_until', side_effect=observer):
            engine.apply_updates(self.state, data, action=command, trusted_duration=True)

    def test_work_income_is_not_available_to_earlier_days(self):
        seen = {}
        def observe(state, _from_day, day):
            seen[day] = economy.balance(state)
            return []
        data = actions.before_turn(self.state, '【时间】工作 10天')
        self.assertEqual(economy.balance(self.state), 200)
        with patch.object(career, 'settle_until', side_effect=observe):
            engine.apply_updates(self.state, data, action='【时间】工作 10天', trusted_duration=True)
        self.assertEqual(seen, {day: 200 + (day - 1) * 35 for day in range(2, 12)})
        self.assertNotIn('activity', self.state['clock'])
        self.assertEqual(self.state['clock']['last_activity']['completed_days'], 10)
        before = economy.balance(self.state)
        life_clock.settle_world(self.state)
        self.assertEqual(economy.balance(self.state), before)

    def test_training_experience_reaches_projects_day_by_day(self):
        seen = {}
        def observe(state, _from_day, day):
            seen[day] = total_xp(state, 'vocal')
            return []
        data = actions.before_turn(self.state, '【时间】训练 vocal 9天')
        self.assertEqual(economy.balance(self.state), 200 - 9 * 8)
        self.assertEqual(total_xp(self.state, 'vocal'), 0)
        with patch.object(career, 'settle_until', side_effect=observe):
            engine.apply_updates(self.state, data, action='【时间】训练 vocal 9天', trusted_duration=True)
        self.assertEqual(seen, {day: (day - 1) * 12 for day in range(2, 11)})
        before = deepcopy(self.state['player']['skills'])
        life_clock.settle_world(self.state)
        self.assertEqual(self.state['player']['skills'], before)

    def test_graduation_stops_later_course_rewards_in_same_skip(self):
        s = self.state
        s['time'].update(day=1094, clock_day=1094)
        s['clock']['settled_day'] = 1094
        s['world_sim']['last_day'] = 1094
        s['player']['education']['credits'] = 118
        seen = {}
        def observe(state, _from_day, day):
            seen[day] = (state['player']['education']['credits'], total_xp(state, 'coding'))
            return []
        self.settle_plan('【时间】上课 5天', observe)
        self.assertEqual(seen[1095], (119, 8))
        self.assertEqual(seen[1096], (120, 16))
        self.assertEqual(seen[1099], (120, 16))
        self.assertEqual(s['player']['education']['status'], 'graduated')
        self.assertEqual(s['player']['identity']['urban'], '京华大学毕业生')
        self.assertNotIn('activity', s['clock'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
