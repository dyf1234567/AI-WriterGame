"""Turn everyday player intentions into validated, persistent world actions."""
import re

from . import career, goals, skills, world_events
from .economy import balance, credit, debit
from .geography import travel_quote
from .models import CASH, CURRENCY, find_npc

NUMBERS = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '半': .5}


_SOFT_TRAIL = re.compile(r'[?？]?(?:好吗|好不好|行吗|行不行|可以吗|嘛)[?？。！!~～\s]*$')
_COND_EXEC = re.compile(r'(?:如果|要是|假如|若是|只要)[^，。？！]*?[就便再]')
_SELF_DELIB = re.compile(r'^(?:我(?:在想|想想|考虑)?|到底)?(?:要不要|该不该|应不应该)')
_CLAUSE_EDGE = re.compile(r'(?:^|[，。！？；;、\s])(怎么|如何)')

_INQUIRY = re.compile(r'不想|不要|先不|暂不|先别|再说|下次再|改天再|回头再|取消|只是问|考虑一下|能否|可否|是否|能不能|可不可以|要不要|该不该|应不应该|如果|要是|假如|假设|若是|愿不愿|肯不肯|[?？]|吗|多久|几天|什么时候|有没有|多少钱|需要多少钱|需要多少|需要什么|需要哪些')

# 询问回合不得代玩家执行的更新：花钱领物、赶路、改身份、接任务、
# 申报结构化行动、动别人的生活、兑现承诺。实际对话中的事实和知情变化仍可记录。
TRANSACTION_UPDATE_KEYS = frozenset({
    'item_gained', 'item_spent', 'location', 'identity_update', 'date_with',
    'technique_grant', 'new_side_quest', 'quest_complete', 'action_request',
    'duration_minutes', 'npc_life', 'fact_resolved',
})


def _not_an_order(text: str) -> bool:
    """判断玩家这句话是询问/拒绝而非执行指令。

    句末「好吗/行不行」可以软化明确的祈使，但不能抹掉犹豫、否定
    和前置条件。当前没有条件求值器，带条件的表达只讨论、不结算；
    玩家可以在核对条件后直接下达执行指令。
    """
    t = text.strip()
    if not t:
        return False
    if _SELF_DELIB.match(t):
        return True
    if _COND_EXEC.search(t):
        return True
    t = _SOFT_TRAIL.sub('', t)
    return bool(_INQUIRY.search(t) or _CLAUSE_EDGE.search(t))


def _number(text: str) -> float:
    if text in NUMBERS:
        return NUMBERS[text]
    if '十' in text:
        first, _, last = text.partition('十')
        return NUMBERS.get(first, 1) * 10 + NUMBERS.get(last, 0)
    return float(text)


def duration(text: str, default: int = 1440) -> int:
    match = re.search(r'(\d+(?:\.\d+)?|[一二两三四五六七八九十半]{1,3})\s*(分钟|小时|天|周|个月|月|年)', text)
    if not match:
        return default
    factors = {'分钟': 1, '小时': 60, '天': 1440, '周': 10080, '个月': 43200, '月': 43200, '年': 525600}
    return max(1, min(1576800, round(_number(match[1]) * factors[match[2]])))


def resolve_action(state: dict, text: str) -> str:
    """Conservative routing: expressions of refusal remain narrative, never transactions."""
    if text.startswith('【') or _not_an_order(text):
        return text
    event = world_events.resolve_action(state, text)
    if event:
        return event
    if re.search(r'快进|跳过|休息\d|训练.+(?:天|周|月|年)|(?:学习|工作|上课).+(?:天|周|月|年)', text):
        mode = '训练' if any(w in text for w in ('训练', '练习')) else '上课' if any(w in text for w in ('学习', '上课')) else '工作' if '工作' in text else '休息'
        return f'【时间】{mode} {text}'
    if re.search(r'^(?:我(?:想|要|打算)?|现在|直接)?(?:前往|去往|赶往|乘车去|坐飞机去|去)', text):
        place = next((p for p in sorted(state.get('map', {}).get('urban', []), key=lambda p: -len(p['name'])) if p['name'] in text), None)
        if place:
            return '【旅行】' + place['name']
    for verb in ('休学', '退学', '复学', '毕业'):
        if re.search(r'(?:申请|办理|决定|我要|我想)' + verb, text):
            return '【生活】' + verb
    if re.search(r'^(?:我(?:想|要)?|去)?(?:做兼职|打工|兼职)', text):
        return '【生活】兼职'
    if re.search(r'^(?:我(?:想|要)?|去)?(?:上课|听课|参加课程)', text):
        return '【生活】上课'
    if re.search(r'^(?:我(?:想|要)?|去)?(?:练习|练|训练)', text):
        for sid, (name, *_rest) in skills.SKILLS.items():
            if name in text or sid in text:
                return f'【生活】练习 {sid}'
    for npc in state.get('npcs', []):
        if npc['name'] not in text:
            continue
        for words, verb in ((('分手',), '分手'), (('复合',), '复合'),
                            (('确认关系', '正式交往', '确立恋爱'), '确认'),
                            (('相处模式', '专一', '开放关系', '多人关系', '商量开放关系'), '协商')):
            if any(word in text for word in words):
                mode = ('poly' if '多人' in text else 'open' if '开放' in text
                        else 'exclusive')
                return f'【关系】{npc["name"]}:{verb}:{mode}'
    if re.search(r'(?:创办|成立|注册).{0,12}(?:公司|工作室)', text):
        name = re.sub(r'^(?:我(?:想|要|打算)?|现在|直接)', '', _SOFT_TRAIL.sub('', text)).strip('。！ ')
        name = re.sub(r'^(?:创办|成立|注册)(?:一家|一个)?', '', name)
        return f'【事业】创办 {name or "我的传媒公司"}'
    if re.search(r'(?:收购|买下|购买).{0,12}战队', text):
        return '【事业】收购战队 城市新星战队'
    if re.search(r'(?:进入|加入|从事|入门).{0,8}(?:娱乐|电竞|商业)', text):
        domain = next(d for d in career.DOMAINS if d in text)
        return f'【事业】入门 {domain}'
    if re.search(r'(?:发行|发布).{0,8}(?:作品|单曲|歌曲)', text):
        return '【事业】发行'
    return text


def action_label(state: dict, action: str) -> str | None:
    if action.startswith('【旅行】'):
        return '前往' + action[len('【旅行】'):].strip()
    if action.startswith('【生活】'):
        body = action[len('【生活】'):].strip()
        if body.startswith('练习 '):
            sid = body.split(maxsplit=1)[1]
            return '练习' + skills.SKILLS.get(sid, (sid,))[0]
        return body
    if action.startswith('【地点】'):
        place = next((p for p in state.get('map', {}).get('urban', [])
                      if p['name'] == state['player'].get('location', {}).get('place')), {})
        try:
            return place['activities'][int(action[len('【地点】'):])]['label']
        except (KeyError, IndexError, TypeError, ValueError):
            return '参加当地活动'
    if action.startswith('【时间】'):
        body = action[len('【时间】'):].strip()
        mode = next((mode for mode in ('训练', '工作', '上课', '休息') if body.startswith(mode)), '休息')
        minutes = duration(body)
        span = f'{minutes // 1440}天' if minutes % 1440 == 0 else f'{minutes // 60}小时' if minutes % 60 == 0 else f'{minutes}分钟'
        if mode == '训练':
            sid = next((sid for sid, (name, *_r) in skills.SKILLS.items() if sid in body or name in body), 'vocal')
            return f'{skills.SKILLS[sid][0]}训练{span}'
        return f'{mode}{span}'
    return None


def _result(story: str, minutes: int = 15, notices=None, choices=None, updates=None) -> dict:
    return {'story_text': story, 'narration_world': 'urban',
            'choices': choices or ['继续今天的行程', '看看认识的人的近况'],
            'state_updates': {'duration_minutes': minutes, **(updates or {})},
            'system_notice': '', '_notices': notices or []}


def proposal_command(state: dict, text: str, proposal: dict) -> str:
    """The narrator may interpret an intention; it cannot grant itself authority."""
    if not isinstance(proposal, dict) or _not_an_order(text):
        raise ValueError('这次表达没有授权实际办理，请明确你想执行的行动。')
    command = str(proposal.get('command', '')).strip()[:160]
    kind = proposal.get('kind')
    prefixes = {'career': '【事业】', 'event': '【活动】', 'relationship': '【关系】', 'travel': '【旅行】', 'life': '【生活】'}
    if kind not in prefixes:
        raise ValueError('该世界行动尚无可核验的结算方式，请选择具体目标和方式。')
    if command.startswith('【') and not command.startswith(prefixes[kind]):
        raise ValueError('行动类型与请求不一致。')
    body = command.removeprefix(prefixes[kind])
    permissions = {
        '创办': r'创办|成立|注册|创业', '收购': r'收购|买下|购买', '融资': r'融资|出让股权',
        '买股': r'买股|增持|购入股份', '注资': r'注资|投入资金', '发行': r'发行|发布作品|发布单曲',
        '招聘': r'招聘|雇佣', '委托': r'委托|聘请经理', '定价': r'定价|调整价格',
        '分手': r'分手|结束关系', '确认': r'确认关系|正式交往|接受提议', '表白': r'表白|告白',
        '退学': r'决定退学|办理退学|申请退学', '休学': r'办理休学|申请休学',
    }
    for verb, permission in permissions.items():
        if body.startswith(verb) and not re.search(permission, text):
            raise ValueError('这次表达没有明确授权这项交易或关系变更。')
    if kind == 'travel' and not re.search(r'前往|去往|旅行|乘车|坐飞机|我要去|我去', text):
        raise ValueError('请明确目的地后再出行。')
    return prefixes[kind] + body


def before_turn(state: dict, action: str) -> dict | None:
    if action.startswith('【旅行】'):
        destination = action[len('【旅行】'):].strip()
        quote = travel_quote(state, destination)
        if not quote.get('ok'):
            raise ValueError(quote['msg'])
        if state['player'].get('location', {}).get('place') == destination:
            raise ValueError('你已经在这里，可以选择当地活动。')
        if not debit(state, quote['cost']):
            raise ValueError(f"旅行需要{quote['cost']}{CASH}，当前持有{balance(state)}。")
        place = next(p for p in state['map']['urban'] if p['name'] == destination)
        place['discovered'] = True
        for country in state['map']['countries']:
            if country['name'] == quote['country']:
                country['discovered'] = True
        for city in state['map']['cities'].get(quote['country'], []):
            if city['name'] == quote['city']:
                city['discovered'] = True
        state['player']['location'] = {'world': 'urban', 'country': quote['country'], 'city': quote['city'], 'place': destination}
        state['player'].setdefault('places_memory', {})['urban'] = destination
        return _result(f"你搭乘{quote['mode']}来到{quote['country']}·{quote['city']}的{destination}。\n\n{place['desc']}\n行程耗时{quote['minutes']}分钟，支付{quote['cost']}{CASH}。",
                       quote['minutes'], choices=[f'【地点】{i}' for i, _ in enumerate(place.get('activities', [])[:4])] + ['先看看四周'])
    if action.startswith('【地点】'):
        place = next((p for p in state['map']['urban'] if p['name'] == state['player']['location']['place']), None)
        try:
            activity = place['activities'][int(action[len('【地点】'):])]
        except (TypeError, ValueError, KeyError, IndexError):
            raise ValueError('请选择当前地点提供的活动。')
        if not debit(state, activity.get('fee', 0)):
            raise ValueError(f"这项活动需要{activity['fee']}{CASH}。")
        notices = []
        if activity.get('work'):
            return _daily_work(state, activity.get('minutes', 180), activity.get('income', 35))
        if activity.get('skill'):
            notices.extend(_practice(state, activity['skill'], 20))
        if activity.get('domain'):
            domain = activity['domain']
            career.add_fame(state, domain, 1)
            career.give_opportunity(state, career.ENTRY_OPPORTUNITIES[domain])
            notices.append(f"你通过当地交流获得了{domain}领域的真实联系。")
        candidates = [n for n in state.get('npcs', []) if n.get('place') == place['name'] and not n.get('known_to_player')]
        met = candidates[:1]
        for npc in met:
            npc['known_to_player'] = True
            npc['last_seen_turn'] = state.get('turn', 0)
        scene = [n['name'] for n in met]
        text = f"你在{place['name']}{activity['label']}。这段时间真正用在了眼前的生活上。"
        if met:
            text += f"你与{met[0]['name']}当面认识，留下了以后联系的方式。"
        return _result(text, activity.get('minutes', 60), notices, updates={'scene_npcs': scene})
    if action.startswith('【时间】'):
        body = action[len('【时间】'):].strip()
        minutes = duration(body)
        if body.startswith(('训练', '工作', '上课')) and (minutes < 1440 or minutes % 1440):
            raise ValueError('长期训练、工作或上课请安排完整天数；当天活动可选择练习、兼职或上课。')
        days = max(1, minutes // 1440)
        notices = []
        if body.startswith('训练'):
            skill_id = next((sid for sid, (name, *_r) in skills.SKILLS.items() if sid in body or name in body), 'vocal')
            cost = days * 8
            if not debit(state, cost):
                raise ValueError(f"这份训练计划需预留{cost}{CASH}，可缩短天数或先积累资金。")
            _schedule_activity(state, 'train', days, skill_id)
            text = f"你安排了{days}天{skills.SKILLS[skill_id][0]}训练，预算{cost}{CASH}。训练与世界里的其他日程同时推进。"
        elif body.startswith('工作'):
            _schedule_activity(state, 'work', days)
            text = f"你按计划完成{days}天临时工作，劳动收入{days * 35}{CASH}已经入账。"
        elif body.startswith('上课'):
            education = state['player']['education']
            if education['status'] != 'enrolled':
                raise ValueError('当前学籍不在读，可以选择自主训练或先办理复学。')
            _schedule_activity(state, 'study', days)
            text = f"你把{days}天留给课程与自习，实际学分与学习经验按天记录；毕业后停止学分结算。毕业仍需完成规定的学习年限与学分。"
        else:
            text = '你把接下来的时间留给自己的生活。经营项目、人物计划、赛事和约定会按各自的日期继续。'
        return _result(text, minutes, notices)
    if action.startswith('【生活】'):
        body = action[len('【生活】'):].strip()
        if body == '兼职':
            return _daily_work(state)
        if body.startswith('练习'):
            skill_id = body.split(maxsplit=1)[1] if ' ' in body else 'vocal'
            notices = _practice(state, skill_id, 20)
            return _result(f"你认真练习了{skills.SKILLS[skill_id][0]}，把一段完整时间交给了基本功。", 120, notices)
        education = state['player']['education']
        if body == '上课':
            if education['status'] != 'enrolled':
                raise ValueError('当前不在读，可以复学或安排自主学习。')
            day = state['time']['day']
            if education.get('study_day') == day:
                raise ValueError('今天的课程学分已记录，可以继续自主练习。')
            education.update(study_day=day, credits=min(160, int(education.get('credits', 0)) + 1))
            credit(state, 2, CURRENCY)
            return _result('你参加了课程，完成课堂练习，学分＋1。系统记录这次实际学习，奖励2系统积分。', 120)
        if body in ('休学', '退学', '复学', '毕业'):
            allowed = {'休学': ('enrolled',), '退学': ('enrolled', 'leave'), '复学': ('leave',), '毕业': ('enrolled',)}
            if education['status'] not in allowed[body]:
                raise ValueError('当前学籍状态不能办理这项变更。')
            if body == '毕业' and (state['time']['day'] < 1096 or education.get('credits', 0) < 120):
                raise ValueError('毕业需要至少三个学年与120学分，当前尚未满足。')
            education['status'] = {'休学': 'leave', '退学': 'withdrawn', '复学': 'enrolled', '毕业': 'graduated'}[body]
            education['changed_day'] = state['time']['day']
            state['player'].setdefault('identity', {})['urban'] = {'休学': '休学探索中的青年', '退学': '自主发展的青年', '复学': '京华大学在读生', '毕业': '京华大学毕业生'}[body]
            return _result(f"你在了解后续安排后办妥了{body}手续。原有事业、资产和人际关系继续存在，新的身份会影响之后的生活。", 120)
        raise ValueError('可选择：上课、兼职、练习、休学、复学、退学或毕业。')
    return None


def _schedule_activity(state: dict, kind: str, days: int, skill: str = '') -> None:
    """Reserve a plan; its future income and experience are not available yet."""
    state.setdefault('clock', {})['activity'] = {
        'kind': kind, 'start_day': state['time']['day'], 'days': days,
        'completed_days': 0, 'skill': skill,
    }


def _practice(state: dict, sid: str, xp: int) -> list[str]:
    if sid not in skills.SKILLS:
        raise ValueError('请选择实际存在的技能。')
    day = state['time']['day']
    record = state.setdefault('daily_practice', {})
    if record.get('day') != day:
        record.update(day=day, count=0)
    if record.get('count', 0) >= 3:
        raise ValueError('今天已经完成三次集中练习，休息或安排后续训练计划会更有效。')
    record['count'] = record.get('count', 0) + 1
    return skills.add_xp(state, sid, xp) + [f"{skills.SKILLS[sid][0]}经验＋{xp}。"]


def _daily_work(state: dict, minutes: int = 180, income: int = 35) -> dict:
    day = state['time']['day']
    work = state.setdefault('daily_work', {})
    if work.get('day') != day:
        work.update(day=day, count=0)
    if work.get('count', 0) >= 2:
        raise ValueError('今天已经完成两班兼职，给休息和其他安排留些时间。')
    work['count'] = work.get('count', 0) + 1
    credit(state, income)
    return _result(f"你完成了一班临时工作，按约拿到{income}{CASH}。生活里的收入进入现实账户，系统积分保持独立。", minutes)
