# 数据与行为协议（P1-07）

实体身份用稳定 ID：`npc:温掌柜→npc:wen_zhanggui`、`place:baixi_town`、`item:qian_nian_ling_zhi`、`faction:hei_feng_lin`、`event:e01`、`player:hero`（周目内唯一）。姓名/别名只用于显示与解析，不承担唯一性。以下结构为阶段 2 SQLite 与阶段 3 行动服务的契约定稿；字段可增不可改义。

## Action（玩家或 NPC 的行动请求）

```json
{
  "action_id": "uuid4",            // 幂等键：同 ID 重复提交返回同一结果
  "campaign": "cmp:xxx", "branch": "br:main",
  "actor": "player:hero",
  "type": "move|cross|buy|sell|use|equip|talk|deliver|promise|wait|rest|cultivate|investigate|deter|melee|flee|aid|free",
  "target": "place:baixi_town | npc:wen_zhanggui | item:xxx | null",
  "params": { "route": "place:heifeng_ridge", "amount": 2, "say": "…" },
  "source": "button|freeform|npc_plan|offline",
  "base_version": 128,             // 提交时的世界版本号，提交时不一致→409
  "issued_at_base": 3600           // 基准秒
}
```

## Outcome（裁决结果；叙事另生）

```json
{
  "action_id": "…", "status": "success|partial|refused|clarify|tech_error",
  "effects": [ {"kind": "move|wallet|inventory|relation|knowledge|commitment|event_state|injury|clock",
                "entity": "…", "set|delta": …, "detail": "契约签署"} ],
  "time_cost": { "world": "xianxia", "base_seconds": 43200 },
  "events": [ 123, 124 ],          // 本结果落账的事件 seq
  "narration_hint": { "scene": "谈判", "facts_only": true }  // 交给叙事服务的边界
}
```

`refused` 是游戏结果（商贩拒售、人不在场），是否耗时按动作规则；`tech_error` 不改变任何状态且不耗时。

## Event（唯一事实来源，只追加）

```json
{
  "seq": 124, "campaign": "…", "branch": "…",
  "base_time": 3600, "world": "xianxia", "world_time": "玄灵历4071-03-12",
  "kind": "move|trade|talk|promise|combat|injury|discovery|world_tick|story",
  "actors": ["player:hero"], "location": "place:heifeng_ridge",
  "payload": { "…": "自由结构，按 kind 定义" },
  "witnesses": ["npc:wu_sanye", "npc:guard_b"],
  "caused_by": 123, "rule_version": "v1", "rng_seed": 8842
}
```

更正以新事件表达（`kind:"retraction"` 指向被更正 seq），不修改旧事件。世界当前状态由事件流＋快照派生。

## Knowledge（知情与信念，按拥有者隔离）

```json
{
  "owner": "npc:wu_sanye",
  "content": "生面孔能拿出青玄宗的名头",
  "epistemic": "factual|hearsay|inference",
  "source_event": 124, "learned_at": 3600,
  "status": "active|corrected|void",
  "confidence": 0.6                  // 仅展示辅助，不作真实性依据
}
```

规则：秘密不存在于“世界”，只存在于某 owner 的这条记录；`hearsay` 可以是假的（世界事实不变）；更正后旧条转 `corrected` 保留可追溯。NPC 上下文装配只取该 owner 的 `active` 记录。

## Commitment（承诺状态机）

```json
{
  "id": "cmt:0031", "promisor": "player:hero", "promisee": "npc:ayan_niang",
  "condition": "找回阿岩或带回消息", "deadline_base": 7200,
  "status": "open|fulfilled|broken|waived|expired",
  "evidence_event": 130, "created_event": 121
}
```

状态迁移只能由事件触发（fulfilled 需证据事件）；过期≠自动 broken，按卡定义决定。

## SceneContext（单次叙事调用的全部输入边界）

```json
{
  "location": "place:baixi_town", "world": "xianxia",
  "present": ["npc:wen_zhanggui", "npc:mo_lao"],
  "recent_events": [120,124],
  "visible_commitments": ["cmt:0031"],
  "knowledge_scope": "player:hero",     // 装配该 owner 可知的 Knowledge
  "event_cards": ["event:e01"],         // 当前可触发/进行中卡
  "boundaries": { "fixed_effects": [/* Outcome.effects 原样 */],
                  "may_improvise": ["路人反应","环境细节"] }
}
```

叙事服务输出只有 `story_text / choices / suggested_actions`，**没有任何 state_updates 通道**；模型提出的新实体一律进候选（`candidate` 状态），经命名/区域校验后才转正。

## 存储映射（阶段 2 落地用）

| 协议 | 表 | 主键 |
|---|---|---|
| campaign/branch | `campaigns`, `branches` | id（branch 记 parent 与分叉 seq） |
| 实体与别名 | `entities`, `aliases` | entity_id / (alias, campaign) |
| 当前状态 | `actor_state`, `relations`, `inventory`, `world_state`(K/V) | entity_id |
| Event | `events` | seq（campaign+branch 内单调） |
| Knowledge / Commitment | `knowledge`, `commitments` | id |
| 行动与结果 | `pending_actions`, `turns` | action_id / turn_id |
| 恢复点 | `snapshots` | id（记 base_version） |
