"""连接与递增迁移。每次结构变更追加一条 MIGRATIONS 记录，禁止改历史记录。"""

import sqlite3
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE campaigns (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
  engine TEXT NOT NULL DEFAULT 'rules_v1', note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE branches (
  id TEXT PRIMARY KEY, campaign TEXT NOT NULL REFERENCES campaigns(id),
  parent TEXT, fork_seq INTEGER, created_at TEXT NOT NULL
);
CREATE TABLE entities (
  campaign TEXT NOT NULL REFERENCES campaigns(id),
  entity_id TEXT NOT NULL, kind TEXT NOT NULL, display_name TEXT NOT NULL,
  PRIMARY KEY (campaign, entity_id)
);
CREATE TABLE aliases (
  campaign TEXT NOT NULL, alias TEXT NOT NULL, entity_id TEXT NOT NULL,
  PRIMARY KEY (campaign, alias)
);
CREATE TABLE actor_state (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, entity_id TEXT NOT NULL,
  key TEXT NOT NULL, value TEXT NOT NULL,
  PRIMARY KEY (campaign, branch, entity_id, key)
);
CREATE TABLE relations (
  campaign TEXT NOT NULL, branch TEXT NOT NULL,
  a TEXT NOT NULL, b TEXT NOT NULL, kind TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (campaign, branch, a, b, kind)
);
CREATE TABLE inventory (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, owner TEXT NOT NULL,
  item TEXT NOT NULL, count INTEGER NOT NULL,
  PRIMARY KEY (campaign, branch, owner, item),
  CHECK (count >= 0)
);
CREATE TABLE world_state (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
  PRIMARY KEY (campaign, branch, key)
);
CREATE TABLE events (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, seq INTEGER NOT NULL,
  base_time INTEGER NOT NULL, world TEXT NOT NULL, kind TEXT NOT NULL,
  actors TEXT NOT NULL DEFAULT '[]', location TEXT, payload TEXT NOT NULL DEFAULT '{}',
  witnesses TEXT NOT NULL DEFAULT '[]', caused_by INTEGER,
  rule_version TEXT NOT NULL, rng_seed INTEGER,
  PRIMARY KEY (campaign, branch, seq)
);
CREATE TABLE knowledge (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, id TEXT NOT NULL,
  owner TEXT NOT NULL, content TEXT NOT NULL,
  epistemic TEXT NOT NULL, source_event INTEGER NOT NULL,
  learned_at INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'active',
  confidence REAL NOT NULL DEFAULT 1.0,
  PRIMARY KEY (campaign, branch, id)
);
CREATE TABLE commitments (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, id TEXT NOT NULL,
  promisor TEXT NOT NULL, promisee TEXT NOT NULL, condition TEXT NOT NULL,
  deadline_base INTEGER, status TEXT NOT NULL DEFAULT 'open',
  created_event INTEGER NOT NULL, evidence_event INTEGER,
  PRIMARY KEY (campaign, branch, id)
);
CREATE TABLE pending_actions (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, action_id TEXT NOT NULL,
  request_digest TEXT NOT NULL, base_version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', result TEXT,
  PRIMARY KEY (campaign, branch, action_id)
);
CREATE TABLE turns (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, turn_id INTEGER NOT NULL,
  action_id TEXT NOT NULL, outcome TEXT NOT NULL,
  events TEXT NOT NULL, version_after INTEGER NOT NULL,
  PRIMARY KEY (campaign, branch, turn_id)
);
CREATE TABLE snapshots (
  campaign TEXT NOT NULL, branch TEXT NOT NULL, id TEXT NOT NULL,
  base_version INTEGER NOT NULL, created_at TEXT NOT NULL, label TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (campaign, branch, id)
);
CREATE INDEX idx_events_time ON events(campaign, branch, base_time);
CREATE INDEX idx_knowledge_owner ON knowledge(campaign, branch, owner, status);
CREATE INDEX idx_pending_status ON pending_actions(campaign, branch, status);
"""

MIGRATIONS = [
    (1, SCHEMA_V1),
]


def connect(path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    import datetime
    for version, script in MIGRATIONS:
        if version in applied:
            continue
        conn.executescript(script)
        conn.execute("INSERT INTO schema_migrations VALUES (?, ?)",
                     (version, datetime.datetime.now(datetime.timezone.utc).isoformat()))
        conn.commit()
    # 历史结构被改动时立即失败，而不是带病运行
    expected = {v for v, _ in MIGRATIONS}
    if applied - expected:
        raise RuntimeError(f"数据库包含未知迁移版本：{sorted(applied - expected)}")
