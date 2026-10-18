"""首章规则核心的最小切片：移动/购买/穿越（决策表与节点地图口径）。

阶段3将扩展为统一行动服务；本模块先让 M1 前置闭环（移动—购买—穿越—返回—重启恢复）
可以在无模型环境运行与测试。
"""

import hashlib
import json

from .persistence import CampaignRepo
from .persistence.repo import VersionConflict

# 节点地图（content/worlds/qinglin-baixi.md）最小边表：耗时按所在界单位（小时）。
EDGES = {
    ("place:zhou_home", "place:linjiang_school"): 0.7,
    ("place:linjiang_school", "place:qinglin_downtown"): 0.5,
    ("place:zhou_home", "place:qinglin_downtown"): 0.9,
    ("place:luoxing_wild", "place:qingshi_village"): 6.0,
    ("place:qingshi_village", "place:baixi_town"): 6.0,
    ("place:baixi_town", "place:qingxu_sect"): 12.0,
}
WORLD_OF = {
    "place:zhou_home": "urban", "place:linjiang_school": "urban", "place:qinglin_downtown": "urban",
    "place:luoxing_wild": "xianxia", "place:qingshi_village": "xianxia",
    "place:baixi_town": "xianxia", "place:qingxu_sect": "xianxia",
}
URBAN_RATE = 1        # 都市 1 小时 = 基准 1 小时
XIANXIA_RATE = 24     # 玄灵界 1 小时 = 基准 1 小时（现实1h=1天）
SHOP = {"item:water_bottle": {"price": 3, "currency": "cny", "name": "矿泉水"},
        "item:liao_shang_dan": {"price": 15, "currency": "lingshi", "name": "疗伤丹"}}


def _digest(action: dict) -> str:
    return hashlib.sha1(json.dumps(action, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


class RulesCore:
    def __init__(self, repo: CampaignRepo, actor: str = "player:hero"):
        self.repo = repo
        self.actor = actor

    # -- 时钟 ---------------------------------------------------------------
    def base_time(self) -> int:
        return self.repo.get_world("base_time", 0)

    def _advance(self, world: str, world_hours: float) -> int:
        rate = URBAN_RATE if world == "urban" else XIANXIA_RATE
        seconds = int(world_hours * 3600 * rate)
        self.repo.set_world("base_time", self.base_time() + seconds)
        return seconds

    # -- 行动入口 -----------------------------------------------------------
    def act(self, action: dict) -> dict:
        """幂等＋乐观版本检查后执行。返回协议 Outcome；版本冲突回滚全部中间写入。"""
        action_id = action["action_id"]
        declared = action.get("base_version")
        if declared is None:
            declared = self.repo.version()
        state = self.repo.claim_action(action_id, _digest(action), declared)
        if state == "done":
            cached = self.repo.cached_outcome(action_id)
            if cached is not None:
                return {**cached, "from_cache": True}
        handler = getattr(self, "_" + action["type"], None)
        if handler is None:
            outcome = {"action_id": action_id, "status": "refused",
                       "effects": [], "time_cost": None, "events": [],
                       "reason": f"未知或暂不支持的动作类型：{action['type']}"}
            seqs: list[int] = []
        else:
            outcome, seqs = handler(action)
        try:
            return self.repo.commit_turn(action_id, outcome, seqs, declared)
        except VersionConflict:
            self.repo.conn.rollback()
            return {**outcome, "status": "tech_error", "events": [],
                    "reason": "版本冲突，请刷新状态后重试"}

    def _where(self) -> str:
        return self.repo.get_state(self.actor, "position")

    def _record(self, kind: str, **kw) -> int:
        return self.repo.append_event(base_time=self.base_time(), world=kw.pop("world", "urban"),
                                      kind=kind, actors=[self.actor], **kw)

    # -- 动作 ---------------------------------------------------------------
    def _move(self, action: dict):
        target = action["target"]
        here = self._where()
        if here == target:
            return ({"action_id": action["action_id"], "status": "refused", "effects": [],
                     "time_cost": None, "events": [], "reason": "已在目标地点"}, [])
        edge = EDGES.get((here, target)) or EDGES.get((target, here))
        if edge is None:
            return ({"action_id": action["action_id"], "status": "refused", "effects": [],
                     "time_cost": None, "events": [],
                     "reason": f"{here} 与 {target} 之间没有可用路线"}, [])
        world = WORLD_OF[target]
        self.repo.set_state(self.actor, "position", target)
        seconds = self._advance(world, edge)
        seq = self._record("move", world=world, location=target, payload={"from": here, "to": target})
        return ({"action_id": action["action_id"], "status": "success",
                 "effects": [{"kind": "move", "entity": self.actor, "set": target}],
                 "time_cost": {"world": world, "base_seconds": seconds},
                 "events": [seq]}, [seq])

    def _buy(self, action: dict):
        item = action["target"]
        amount = int(action.get("params", {}).get("amount", 1))
        goods = SHOP.get(item)
        here = self._where()
        # 都市货架只在市中心，灵石货架只在白溪济生堂（最小口径，阶段3接入真实库存）
        shelf_ok = here == ("place:qinglin_downtown" if goods and goods["currency"] == "cny"
                            else "place:baixi_town" if goods else None)
        if goods is None or not shelf_ok:
            return ({"action_id": action["action_id"], "status": "refused", "effects": [],
                     "time_cost": None, "events": [],
                     "reason": "此处不售此物（商城/济生堂才有对应货架）"}, [])
        wallet_key = "wallet:cny" if goods["currency"] == "cny" else "wallet:lingshi"
        wallet = self.repo.get_state(self.actor, wallet_key, 0)
        cost = goods["price"] * amount
        if wallet < cost:
            return ({"action_id": action["action_id"], "status": "refused", "effects": [],
                     "time_cost": None, "events": [],
                     "reason": f"{'现金' if goods['currency']=='cny' else '灵石'}不足：需 {cost}，有 {wallet}"}, [])
        self.repo.set_state(self.actor, wallet_key, wallet - cost)
        self.repo.add_item(self.actor, item, amount)
        seconds = self._advance(WORLD_OF[here], 0.2)
        seq = self._record("trade", world=WORLD_OF[here], location=here,
                           payload={"item": item, "amount": amount, "cost": cost})
        return ({"action_id": action["action_id"], "status": "success",
                 "effects": [{"kind": "wallet", "entity": self.actor, "delta": -cost, "detail": wallet_key},
                             {"kind": "inventory", "entity": self.actor, "item": item, "delta": amount}],
                 "time_cost": {"world": WORLD_OF[here], "base_seconds": seconds},
                 "events": [seq]}, [seq])

    def _cross(self, action: dict):
        here = self._where()
        world = WORLD_OF[here]
        other = "xianxia" if world == "urban" else "urban"
        last_key = f"last_pos:{other}"
        target = self.repo.get_state(self.actor, last_key)
        if target is None:  # 首穿：正典落点
            target = "place:luoxing_wild" if other == "xianxia" else "place:zhou_home"
        self.repo.set_state(self.actor, f"last_pos:{world}", here)
        self.repo.set_state(self.actor, "position", target)
        seq = self._record("cross", world=other, location=target,
                           payload={"from": here, "to": target})
        return ({"action_id": action["action_id"], "status": "success",
                 "effects": [{"kind": "move", "entity": self.actor, "set": target, "detail": "穿越，耗时常数0"}],
                 "time_cost": {"world": other, "base_seconds": 0},
                 "events": [seq]}, [seq])
