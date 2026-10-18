"""仓储操作：周目/分支/实体/状态/事件/回合提交。字段口径见 content/protocols.md。"""

import datetime
import json
import sqlite3


class VersionConflict(Exception):
    """提交时的世界版本与行动基准版本不一致（并发或旧页面）。"""


class RequestMismatch(Exception):
    """同一 action_id 对应了不同请求内容。"""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class CampaignRepo:
    def __init__(self, conn: sqlite3.Connection, campaign: str, branch: str = "br:main"):
        self.conn = conn
        self.campaign = campaign
        self.branch = branch

    # -- 周目与身份 -------------------------------------------------------
    @staticmethod
    def create_campaign(conn: sqlite3.Connection, campaign: str, note: str = "") -> str:
        conn.execute("INSERT INTO campaigns (id, created_at, note) VALUES (?, ?, ?)", (campaign, _now(), note))
        conn.execute("INSERT INTO branches (id, campaign, parent, fork_seq, created_at) VALUES (?, ?, NULL, NULL, ?)",
                     ("br:main", campaign, _now()))
        conn.commit()
        return campaign

    def fork_branch(self, branch: str, fork_seq: int) -> str:
        """从本分支 fork_seq 处开新分支：只继承该序号之前的事件，其余状态由事件重放获得。"""
        row = self.conn.execute("SELECT MAX(seq) FROM events WHERE campaign=? AND branch=?", (self.campaign, self.branch)).fetchone()
        if row[0] is not None and not (0 <= fork_seq <= row[0]):
            raise ValueError(f"fork_seq {fork_seq} 超出本分支事件范围 0..{row[0]}")
        self.conn.execute("INSERT INTO branches (id, campaign, parent, fork_seq, created_at) VALUES (?, ?, ?, ?, ?)",
                          (branch, self.campaign, self.branch, fork_seq, _now()))
        self.conn.commit()
        return branch

    def add_entity(self, entity_id: str, kind: str, display_name: str, aliases=()) -> None:
        self.conn.execute("INSERT INTO entities VALUES (?, ?, ?, ?)", (self.campaign, entity_id, kind, display_name))
        for alias in aliases:
            self.conn.execute("INSERT INTO aliases VALUES (?, ?, ?)", (self.campaign, alias, entity_id))
        self.conn.commit()

    def resolve(self, alias: str) -> str | None:
        row = self.conn.execute("SELECT entity_id FROM aliases WHERE campaign=? AND alias=?",
                                (self.campaign, alias)).fetchone()
        return row[0] if row else None

    # -- 当前状态 ----------------------------------------------------------
    def set_state(self, entity: str, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO actor_state VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(campaign, branch, entity_id, key) DO UPDATE SET value=excluded.value",
            (self.campaign, self.branch, entity, key, json.dumps(value, ensure_ascii=False)))

    def get_state(self, entity: str, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM actor_state WHERE campaign=? AND branch=? AND entity_id=? AND key=?",
            (self.campaign, self.branch, entity, key)).fetchone()
        return json.loads(row[0]) if row else default

    def set_world(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO world_state VALUES (?, ?, ?, ?) "
            "ON CONFLICT(campaign, branch, key) DO UPDATE SET value=excluded.value",
            (self.campaign, self.branch, key, json.dumps(value, ensure_ascii=False)))

    def get_world(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM world_state WHERE campaign=? AND branch=? AND key=?",
                                (self.campaign, self.branch, key)).fetchone()
        return json.loads(row[0]) if row else default

    def add_item(self, owner: str, item: str, count: int) -> None:
        if count < 0:
            raise ValueError("count 不能为负")
        self.conn.execute(
            "INSERT INTO inventory VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(campaign, branch, owner, item) DO UPDATE SET count = count + excluded.count",
            (self.campaign, self.branch, owner, item, count))

    def count_item(self, owner: str, item: str) -> int:
        row = self.conn.execute("SELECT count FROM inventory WHERE campaign=? AND branch=? AND owner=? AND item=?",
                                (self.campaign, self.branch, owner, item)).fetchone()
        return row[0] if row else 0

    # -- 事件与版本 ---------------------------------------------------------
    def version(self) -> int:
        return self.get_world("world_version", 0)

    def next_seq(self) -> int:
        row = self.conn.execute("SELECT MAX(seq) FROM events WHERE campaign=? AND branch=?",
                                (self.campaign, self.branch)).fetchone()
        return (row[0] or 0) + 1

    def append_event(self, *, base_time: int, world: str, kind: str, actors=(), location=None,
                     payload=None, witnesses=(), caused_by=None, rule_version="v1", rng_seed=None) -> int:
        seq = self.next_seq()
        self.conn.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.campaign, self.branch, seq, base_time, world, kind,
             json.dumps(list(actors), ensure_ascii=False), location,
             json.dumps(payload or {}, ensure_ascii=False),
             json.dumps(list(witnesses), ensure_ascii=False),
             caused_by, rule_version, rng_seed))
        return seq

    def events(self, world: str | None = None) -> list[sqlite3.Row]:
        if world:
            return self.conn.execute(
                "SELECT * FROM events WHERE campaign=? AND branch=? AND world=? ORDER BY seq",
                (self.campaign, self.branch, world)).fetchall()
        return self.conn.execute(
            "SELECT * FROM events WHERE campaign=? AND branch=? ORDER BY seq",
            (self.campaign, self.branch)).fetchall()

    # -- 回合提交（幂等＋乐观版本） ------------------------------------------
    def claim_action(self, action_id: str, request_digest: str, base_version: int) -> str:
        """登记/复用待处理行动。返回 'pending'（首次）或 'done'（已处理完，结果可复用）。"""
        row = self.conn.execute(
            "SELECT request_digest, status FROM pending_actions WHERE campaign=? AND branch=? AND action_id=?",
            (self.campaign, self.branch, action_id)).fetchone()
        if row is None:
            self.conn.execute("INSERT INTO pending_actions VALUES (?,?,?,?,?, 'pending', NULL)",
                              (self.campaign, self.branch, action_id, request_digest, base_version))
            self.conn.commit()
            return "pending"
        if row["request_digest"] != request_digest:
            raise RequestMismatch(f"action_id {action_id} 已绑定不同请求")
        return row["status"]

    def commit_turn(self, action_id: str, outcome: dict, event_seqs: list[int], base_version: int) -> dict:
        """短事务提交：版本检查 → 落结果 → 版本+1。失败抛 VersionConflict，不写任何数据。"""
        current = self.version()
        if current != base_version:
            raise VersionConflict(f"世界版本已从 {base_version} 推进到 {current}")
        version_after = current + 1
        self.set_world("world_version", version_after)
        self.conn.execute(
            "INSERT INTO turns (campaign, branch, turn_id, action_id, outcome, events, version_after) "
            "SELECT ?, ?, COALESCE(MAX(turn_id),0)+1, ?, ?, ?, ? FROM turns WHERE campaign=? AND branch=?",
            (self.campaign, self.branch, action_id,
             json.dumps(outcome, ensure_ascii=False), json.dumps(event_seqs), version_after,
             self.campaign, self.branch))
        self.conn.execute(
            "UPDATE pending_actions SET status='done', result=? WHERE campaign=? AND branch=? AND action_id=?",
            (json.dumps(outcome, ensure_ascii=False), self.campaign, self.branch, action_id))
        self.conn.commit()
        return outcome

    def cached_outcome(self, action_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT result FROM pending_actions WHERE campaign=? AND branch=? AND action_id=? AND status='done'",
            (self.campaign, self.branch, action_id)).fetchone()
        return json.loads(row[0]) if row else None

    # -- 知识与承诺 ----------------------------------------------------------
    def add_knowledge(self, *, kid: str, owner: str, content: str, epistemic: str, source_event: int,
                      learned_at: int, confidence: float = 1.0) -> None:
        self.conn.execute("INSERT INTO knowledge VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (self.campaign, self.branch, kid, owner, content, epistemic,
                           source_event, learned_at, "active", confidence))

    def knowledge_of(self, owner: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM knowledge WHERE campaign=? AND branch=? AND owner=? AND status='active' ORDER BY learned_at",
            (self.campaign, self.branch, owner)).fetchall()

    def add_commitment(self, *, cid: str, promisor: str, promisee: str, condition: str,
                       deadline_base: int | None, created_event: int) -> None:
        self.conn.execute("INSERT INTO commitments VALUES (?,?,?,?,?,?,?,?,?)",
                          (self.campaign, self.branch, cid, promisor, promisee, condition,
                           deadline_base, "open", created_event, None))
