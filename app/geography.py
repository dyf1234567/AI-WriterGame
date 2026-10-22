"""A persistent travel atlas. Places carry activities, rather than empty map pins."""
from copy import deepcopy

COUNTRIES = [
    ("华夏", 66, 36, "校园、城市与产业交汇，人生从这里出发"),
    ("东瀛", 84, 33, "音乐现场、动画工房与职业联赛兴盛的群岛"),
    ("法兰西", 43, 29, "独立电影、艺术展览与设计品牌的交流之地"),
    ("星联", 17, 38, "科技投资、国际赛事与流行音乐蓬勃的大陆"),
    ("南洋", 73, 64, "港口贸易、海岛度假与跨国创业的交汇处"),
    ("北境", 53, 14, "冬季运动、研究站与漫长极夜中的安静生活"),
]

# name, country, country-map coordinates, character, six local destinations
CITIES = [
    ("京都", "华夏", 48, 24, "学术与文化", ("京华创业园", "长安电竞馆", "星桥录音棚", "西河旧书街", "北湖运动场", "青年公寓", "城市人才中心", "国立档案馆", "京都国际机场", "南锣夜市")),
    ("魔都", "华夏", 74, 58, "金融与娱乐", ("魔都音乐学院", "星海传媒园", "虹湾竞技中心", "滨江创投中心", "海风摄影街", "繁星演艺厅", "魔都国际机场", "远航港", "江畔公寓", "云端书店")),
    ("深港", "华夏", 68, 85, "科技创业", ("深港科技园", "南山孵化器", "海岸电竞基地", "创客工坊", "蓝湾公园", "深港高铁站")),
    ("临安", "华夏", 62, 54, "创作与数字产业", ("西湖书院", "运河创意园", "临安直播基地", "青禾市集", "湖畔美术馆", "临安东站")),
    ("蓉城", "华夏", 28, 58, "音乐与慢生活", ("玉林音乐街", "西岭训练馆", "锦里小剧场", "天府创业园", "青城步道", "蓉城车站")),
    ("江海", "华夏", 88, 44, "校园与海港", ("江海大学", "潮汐咖啡馆", "海角电竞中心", "白帆贸易港", "灯塔海滩", "江海总站")),
    ("樱京", "东瀛", 55, 32, "流行音乐", ("樱京音乐学园", "秋叶制作工房", "银座演出厅", "樱川录音室", "晴空商业街", "樱京机场")),
    ("海湾", "东瀛", 38, 65, "游戏与赛事", ("海湾游戏学院", "霓虹电竞馆", "海湾开发者中心", "潮音直播间", "月见公园", "海湾航站楼")),
    ("鸢尾", "法兰西", 49, 29, "艺术与独立电影", ("鸢尾艺术学院", "光影电影宫", "河岸画廊", "左岸设计工坊", "晨光咖啡馆", "鸢尾机场")),
    ("蔚蓝", "法兰西", 65, 73, "电影节与海岸", ("蔚蓝电影节宫", "海风制片基地", "港湾商务中心", "滨海摄影长廊", "橄榄公园", "蔚蓝交通港")),
    ("新港", "星联", 73, 37, "投资与传媒", ("新港商学院", "时代创投中心", "国际媒体大厦", "新港音乐工场", "中央公园", "新港国际机场")),
    ("星湾", "星联", 27, 53, "科技与国际电竞", ("星湾理工学院", "世界电竞中心", "星湾科技园", "独立游戏工坊", "海岸绿道", "星湾国际机场")),
    ("狮城", "南洋", 47, 58, "贸易与国际合作", ("狮城大学", "海峡交易中心", "南洋赛事馆", "国际艺术仓库", "滨海花园", "狮城机场")),
    ("椰湾", "南洋", 70, 35, "海岛与旅行创作", ("椰湾设计学校", "海岛影像基地", "珊瑚创业营", "港口市集", "白沙海滩", "椰湾码头")),
    ("极光", "北境", 43, 23, "科研与冬季运动", ("极光研究学院", "北境研究站", "冰原运动中心", "极光创客屋", "星空观测营", "极光机场")),
    ("松港", "北境", 60, 66, "独立创作与生活", ("松港艺术学校", "森林录音小屋", "松港商务港", "冬日电竞馆", "白桦森林", "松港交通站")),
]

POSITIONS = [(18, 25), (46, 19), (75, 28), (22, 53), (53, 50), (82, 58), (15, 78), (47, 81), (76, 81), (66, 65)]


def _kind(name: str) -> str:
    for words, kind in ((('大学', '学院', '书院'), 'campus'),
                        (('机场', '航站', '码头', '交通', '总站', '车站', '高铁站', '东站'), 'transport'),
                        (('公园', '步道', '海滩', '森林', '绿道', '花园', '观测营'), 'nature'),
                        (('画廊', '美术', '电影', '档案', '书店', '工坊'), 'culture'),
                        (('电竞', '赛事', '竞技', '训练', '录音', '演出', '剧场', '咖啡', '音乐街'), 'leisure')):
        if any(word in name for word in words):
            return kind
    return 'city'


def activities_for(name: str, kind: str) -> list[dict]:
    if any(word in name for word in ('电竞', '赛事', '竞技', '游戏', '训练馆')):
        return [{"label": "参加公开训练", "skill": "mech", "minutes": 120, "fee": 10},
                {"label": "结识赛事合作方", "domain": "电竞", "minutes": 60, "fee": 0}]
    if any(word in name for word in ('录音', '音乐', '演艺', '演出', '直播', '剧场', '制片', '影像', '电影')):
        return [{"label": "预约创作练习", "skill": "vocal" if '电影' not in name else "acting", "minutes": 120, "fee": 15},
                {"label": "参加创作交流", "domain": "娱乐", "minutes": 60, "fee": 0}]
    if any(word in name for word in ('创业', '创投', '科技', '商务', '贸易', '交易', '商业', '市集', '孵化', '人才')):
        return [{"label": "参加创业交流", "domain": "商业", "minutes": 90, "fee": 0},
                {"label": "做一班临时工作", "work": True, "minutes": 180, "fee": 0, "income": 35}]
    return [{"label": "探索并认识这里的人", "minutes": 60, "fee": 0},
            {"label": "在这里学习练习", "skill": "photo" if kind in ('nature', 'culture') else "coding", "minutes": 90, "fee": 0}]


def expand_map(base: dict) -> dict:
    atlas = deepcopy(base)
    existing_countries = {country['name'] for country in atlas['countries']}
    for name, x, y, desc in COUNTRIES:
        if name not in existing_countries:
            atlas['countries'].append(dict(name=name, x=x, y=y, desc=desc, discovered=False))
    existing_places = {place['name'] for place in atlas['urban']}
    for city, country, x, y, theme, names in CITIES:
        nodes = atlas['cities'].setdefault(country, [])
        if not any(node['name'] == city for node in nodes):
            nodes.append(dict(name=city, x=x, y=y, desc=f"{country}的{theme}之城", discovered=False))
        for index, name in enumerate(names):
            if name in existing_places:
                continue
            px, py = POSITIONS[index % len(POSITIONS)]
            kind = _kind(name)
            atlas['urban'].append(dict(name=name, city=city, country=country, type=kind,
                                      x=px, y=py, discovered=False,
                                      desc=f"{city}的{theme}在这里留下日常的痕迹。可以参与当地活动、学习或结识合作者。",
                                      activities=activities_for(name, kind)))
            existing_places.add(name)
    country_of = {city: country for city, country, *_ in CITIES}
    for place in atlas['urban']:
        place.setdefault('country', country_of.get(place.get('city'), '华夏'))
        place.setdefault('activities', activities_for(place['name'], place.get('type', 'city')))
    return atlas


def travel_quote(state: dict, destination: str) -> dict:
    place = next((place for place in state.get('map', {}).get('urban', []) if place['name'] == destination), None)
    if place is None:
        return {"ok": False, "msg": "没有找到这个目的地，请从地图选择。"}
    origin = state['player'].get('location', {})
    if origin.get('place') == destination:
        minutes, cost, mode = 0, 0, '已在此处'
    elif origin.get('city') == place.get('city'):
        minutes, cost, mode = 30, 8, '市内交通'
        if (state.get('power') or {}).get('stage', 0) >= 5:
            minutes, cost, mode = 0, 0, '御气赶路'
    elif origin.get('country', '华夏') == place.get('country', '华夏'):
        minutes, cost, mode = 240, 80, '城际交通'
    else:
        minutes, cost, mode = 600, 480, '国际航班'
    from .economy import balance
    return {"ok": True, "destination": place['name'], "city": place['city'],
            "country": place.get('country', '华夏'), "minutes": minutes, "cost": cost,
            "mode": mode, "affordable": balance(state) >= cost}


def atlas_view(state: dict) -> dict:
    atlas = state.get('map', {})
    return {"countries": len(atlas.get('countries', [])),
            "cities": sum(len(value) for value in atlas.get('cities', {}).values()),
            "places": len(atlas.get('urban', [])),
            "visited": sum(bool(place.get('discovered')) for place in atlas.get('urban', [])),
            "routes": {place['name']: travel_quote(state, place['name']) for place in atlas.get('urban', [])}}
