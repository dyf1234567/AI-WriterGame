"""记忆工程（参考 novel-writer skill 的长篇项目记忆模式）。

四层记忆装配，防止长局失忆：
1. 滚动摘要（已有）：压缩管线的粗粒度记忆；
2. 事实账本 state["facts"]：承诺/伏笔/秘密等长期事实，回合内即时记录、压缩时批量萃取；
   账本分两类——未了结的承诺/伏笔常驻提示词（不随时间淡出），普通事实只带最近若干条；
3. 归档检索：按"行动中提到的人物/地点/物品"搜 story_archive.jsonl，把相关旧正文捞回上下文；
4. 冲突裁决：检索片段只是证据，与状态账本冲突时以账本为准（skill 的"冲突摆出来不调和"）。
"""
import json
import os
import re
import tempfile
from datetime import datetime, timezone

from .config import MEMORY_MANUAL_FILE, MEMORY_STATUS_FILE, NPC_ARCHIVE_FILE, STORY_ARCHIVE_FILE

FACTS_KEEP_IN_PROMPT = 8    # 提示词携带的近期普通事实条数
FACTS_HARD_CAP = 60         # 账本硬上限（超出按"已了结 > 普通事实 > 未了结承诺"的顺序淘汰）
RESIDENT_CAP = 12           # 常驻提示词的未了结承诺/伏笔上限（防无限膨胀）
RESIDENT_KINDS = ("承诺", "伏笔")
ARCHIVE_SCAN_LINES = 200    # 检索时回看的归档行数
ARCHIVE_HITS = 3            # 注入提示词的命中片段数
ARCHIVE_SNIPPET = 160       # 每个命中片段的截断长度

# 分类靠线索词判定，不额外花模型调用；承诺优先于伏笔（需要被了结的先占位）
_PROMISE_CUES = ("答应", "承诺", "约定", "约好", "说好", "保证", "发誓", "欠", "嘱托", "托我", "交代")
_SEED_CUES = ("伏笔", "来历不明", "未回收", "未知", "不明", "秘密", "传闻", "疑似", "似乎", "谜", "线索")
# 归一化去掉标点/空白/尾注，让"答应替陈某保密"与"答应替陈某保密（承诺）"视为同一条
_STRIP_TAIL = re.compile(r"[（(](?:承诺|约定|伏笔|秘密|事实)[)）]$")


def _clean(value, limit: int) -> str:
    return str(value or "").replace("<", "").replace(">", "").strip()[:limit]


def _norm_key(text) -> str:
    """比对键：只留汉字与字母数字，并剥掉（承诺）这类尾注。"""
    raw = _STRIP_TAIL.sub("", str(text or "").strip())
    return re.sub(r"[\W_]+", "", raw).lower()


def classify_fact(text: str) -> str:
    for cue in _PROMISE_CUES:
        if cue in text:
            return "承诺"
    for cue in _SEED_CUES:
        if cue in text:
            return "伏笔"
    return "事实"


def _kind_of(fact: dict) -> str:
    return fact.get("kind") or classify_fact(fact.get("text", ""))


def _open(fact: dict) -> bool:
    """未了结判定。closed 存的是了结回合号，第 0 回合了结时真值为假，只能与 None 比。"""
    return fact.get("closed") is None


def _evict_facts(state: dict) -> None:
    facts = state["facts"]
    overflow = len(facts) - FACTS_HARD_CAP
    if overflow <= 0:
        return
    resolved = [f for f in facts if not _open(f)]
    ordinary = [f for f in facts if _open(f) and _kind_of(f) not in RESIDENT_KINDS]
    open_resident = [f for f in facts if _open(f) and _kind_of(f) in RESIDENT_KINDS]
    doomed = {id(f) for f in (resolved + ordinary + open_resident)[:overflow]}
    state["facts"] = [f for f in facts if id(f) not in doomed]


def append_fact(state: dict, text, turn: int, kind: str | None = None) -> str | None:
    """追加一条长期事实；返回清洗后的文本，无效或重复输入返回 None。"""
    fact = _clean(text, 60)
    if not fact:
        return None
    facts = state.setdefault("facts", [])
    key = _norm_key(fact)
    if not key or any(_norm_key(f.get("text")) == key for f in facts):
        return None
    facts.append({"turn": turn, "text": fact,
                  "kind": kind if kind in ("承诺", "伏笔", "事实") else classify_fact(fact),
                  "closed": None})
    _evict_facts(state)
    return fact


def resolve_fact(state: dict, text, turn: int) -> str | None:
    """把一条已兑现/已揭破的承诺或伏笔记为了结；返回被了结的事实原文，没对上返回 None。

    了结不删条目——账本要留着"这事已经办过"，否则模型会以为承诺还在。
    """
    key = _norm_key(text)
    if len(key) < 4:  # 太短的片段会撞上一切，宁可不认
        return None
    for fact in reversed(state.get("facts") or []):
        if not _open(fact):
            continue
        fk = _norm_key(fact.get("text"))
        if fk == key or key in fk:
            fact["closed"] = turn
            return fact.get("text")
    return None


def facts_block(state: dict) -> str:
    """提示词用的事实账本块：未了结的承诺/伏笔常驻，普通事实只带最近若干条。"""
    facts = state.get("facts") or []
    if not facts:
        return ""
    resident, ordinary = [], []
    for f in facts:
        (resident if (_kind_of(f) in RESIDENT_KINDS and _open(f)) else ordinary).append(f)
    parts = ["【长期记忆·事实账本（已确认的事实，剧情不得与之矛盾）】"]
    if resident:
        parts.append("〔未了结的承诺／伏笔——迟早要兑现或被玩家追问，不得随回合推进淡出〕")
        parts.extend(f"★ 第{f['turn']}回合（{_kind_of(f)}）：{f['text']}" for f in resident[-RESIDENT_CAP:])
    if ordinary:
        parts.append("〔近期事实〕")
        parts.extend(f"- 第{f['turn']}回合：{f['text']}" for f in ordinary[-FACTS_KEEP_IN_PROMPT:])
    return "\n".join(parts) if len(parts) > 1 else ""


def _entity_keywords(state: dict, action: str) -> list[str]:
    """从玩家行动里挑出实体名（NPC/已探明地点/背包物品）作检索关键词。"""
    keywords: list[str] = []
    for n in state.get("npcs", []):
        if n.get("name") and n["name"] in action:
            keywords.append(n["name"])
    for w in ("urban", "xianxia"):
        for p in state.get("map", {}).get(w, []):
            if p.get("discovered") and p.get("name") and p["name"] in action:
                keywords.append(p["name"])
    for it in state["player"].get("items", []):
        name = it.get("name", "")
        if len(name) >= 3 and name in action:  # 过滤"下品灵石"这类高频短词由长度挡一道
            keywords.append(name)
    return keywords


def retrieve_archive(state: dict, action: str) -> list[dict]:
    """按实体关键词检索归档正文，返回最近命中的片段。无关键词或无归档时为空。"""
    keywords = _entity_keywords(state, action)
    if not keywords:
        return []
    try:
        lines = STORY_ARCHIVE_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    hits: list[dict] = []
    for line in lines[-ARCHIVE_SCAN_LINES:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = rec.get("text", "")
        matched = [k for k in keywords if k in text]
        if not matched:
            continue
        hits.append({"turn": rec.get("turn"), "text": text[:ARCHIVE_SNIPPET],
                     "matched": matched})
    return hits[-ARCHIVE_HITS:]


def archive_block(hits: list[dict]) -> str:
    """提示词用的往事检索块；空命中返回空串。"""
    if not hits:
        return ""
    lines = [f"- 【第{h['turn']}回合】{h['text']}" for h in hits]
    return ("【往事档案检索（自动捞回的相关旧剧情，仅供参考证据；若与当前状态账本冲突，"
            "以账本为准，并在剧情中明示记忆的出入，不得悄悄调和）】\n" + "\n".join(lines))


# ---------- 记忆手册（人可读文档，随每次存档自动导出） ----------

def _manual_lines(state: dict) -> list[str]:
    from .models import REALMS, WORLD_NAMES, technique_of
    p = state["player"]
    loc = p.get("location") or {}
    ident = p.get("identity") or {}
    tech = technique_of(state)
    out: list[str] = []
    out.append("# 《双界录》记忆手册")
    out.append("")
    out.append(f"> 自动导出 · 第 {state.get('turn', 0)} 回合 · {state.get('last_active', '')[:19]}Z "
               "（每次存档后刷新，手写内容会被下次导出覆盖）")
    out.append("")
    out.append("## 一、主角快照")
    out.append("")
    out.append(f"- **{p.get('name', '')}** · {WORLD_NAMES.get(p.get('world'), '')}·{loc.get('place', '未知')}")
    out.append(f"- 境界：{REALMS[p.get('realm', 0)]}（本境进度 {p.get('realm_progress', 0)}%）")
    out.append(f"- 身份：都市「{ident.get('urban') or '尚无'}」｜修仙界「{ident.get('xianxia') or '尚无'}」")
    if tech:
        out.append(f"- 初始功法：{tech.get('route', '')}·《{tech.get('name', '')}》（{tech.get('grade', '')}）")
    out.append(f"- 抽奖：已抽 {int((p.get('lottery') or {}).get('total_drawn', 0))} 次")
    out.append("")
    out.append("## 二、剧情摘要")
    out.append("")
    summary = (state.get("summary") or "").strip()
    out.append(summary if summary else "*（尚无摘要——剧情还短，或压缩未触发）*")
    out.append("")
    facts = state.get("facts") or []
    out.append("## 三、事实账本（承诺 / 伏笔 / 事实）")
    out.append("")
    if facts:
        open_items, resolved, rest = [], [], []
        for f in facts:
            if not _open(f):
                resolved.append(f)
            elif _kind_of(f) in RESIDENT_KINDS:
                open_items.append(f)
            else:
                rest.append(f)
        if open_items:
            out.append("**未了结（常驻提示词，必须兑现）**")
            out.append("")
            for f in open_items:
                out.append(f"- 第{f.get('turn', '?')}回合（{_kind_of(f)}）：{f.get('text', '')}")
        if rest:
            out.append("**近期事实**")
            out.append("")
            for f in rest:
                out.append(f"- 第{f.get('turn', '?')}回合（{_kind_of(f)}）：{f.get('text', '')}")
        if resolved:
            out.append(f"**已了结 {len(resolved)} 条**")
            out.append("")
            for f in resolved:
                out.append(f"- 第{f.get('turn', '?')}回合→第{f.get('closed', '?')}回合结：{f.get('text', '')}")
    else:
        out.append("*（账本为空——还没有沉淀出承诺与伏笔）*")
    out.append("")
    out.append("## 四、关系网")
    out.append("")
    for n in state.get("npcs", []):
        rels = "；".join(f"与{k}：{v}" for k, v in list((n.get("rels") or {}).items())[:3]) or "无"
        mem = "；".join((n.get("memory") or [])[-2:]) or "暂无"
        out.append(f"- **{n['name']}**（{WORLD_NAMES.get(n.get('world'), '')}·{n.get('role', '')}，"
                   f"常在 {n.get('place') or '行踪不定'}）好感 {n.get('affinity', '?')}·「{n.get('label', '')}」")
        out.append(f"  - NPC间关系：{rels}")
        out.append(f"  - 近期记忆：{mem}")
        deeds = (n.get("deeds") or [])[-10:]
        if deeds:
            out.append("  - 行事录（近10条）：" + "；".join(
                f"第{d.get('turn', '?')}回合{d.get('text', '').split('：', 1)[-1]}" for d in deeds))
    out.append("")
    out.append("## 五、两界探明进度")
    out.append("")
    for w in ("urban", "xianxia"):
        places = state.get("map", {}).get(w, [])
        known = [pl for pl in places if pl.get("discovered")]
        fog = [pl for pl in places if not pl.get("discovered")]
        out.append(f"### {WORLD_NAMES.get(w, w)}（已探明 {len(known)} / 未探明 {len(fog)}）")
        out.append("")
        for pl in known:
            out.append(f"- ✅ **{pl['name']}**：{pl.get('desc', '')}")
        for pl in fog:
            out.append(f"- 🌫 未探明之地 ×1")
        out.append("")
    out.append("## 六、离场人物（名册淘汰后归档，重逢时恢复旧档）")
    out.append("")
    departed = _departed_npcs()
    if departed:
        for rec in departed[-10:]:
            last_deed = (rec.get("deeds") or [{}])[-1].get("text", "")
            out.append(f"- **{rec.get('name', '?')}**（{rec.get('world', '')}·{rec.get('role', '')}）"
                       f"离场好感 {rec.get('affinity', '?')}·「{rec.get('label', '')}」"
                       f"｜最后一事：{last_deed or '无记录'}")
    else:
        out.append("*（还没有人被名册淘汰）*")
    out.append("")
    return out


def _departed_npcs() -> list[dict]:
    """归档里的离场人物，按姓名去重取最近一份。"""
    try:
        lines = NPC_ARCHIVE_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    latest: dict[str, dict] = {}
    order: list[str] = []
    for line in lines[-400:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = str(rec.get("name", ""))
        if not name:
            continue
        if name not in latest:
            order.append(name)
        latest[name] = rec
    return [latest[n] for n in order]


def _write_status(ok: bool, state: dict, error: str = "") -> None:
    """把导出成败写进 sidecar 文件——失败本身不该阻塞游戏，但不该毫无痕迹。"""
    try:
        turn = state.get("turn", 0) if isinstance(state, dict) else 0
        payload = json.dumps({
            "ok": ok,
            "ts": datetime.now(timezone.utc).isoformat(),
            "turn": turn,
            "manual": str(MEMORY_MANUAL_FILE),
            "error": error[:200],
        }, ensure_ascii=False, indent=1)
        MEMORY_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_STATUS_FILE.write_text(payload, encoding="utf-8")
    except OSError:
        pass


def export_manual(state: dict) -> bool:
    """把记忆导出为人可读的记忆手册；失败返回 False（绝不阻塞存档）。

    这里捕的是 Exception 而不是 OSError：手册只是导出产物，
    任何渲染意外都不该冒泡到存档路径上——但要写进 _导出状态.json 留痕。
    """
    try:
        manual = MEMORY_MANUAL_FILE
        manual.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(_manual_lines(state)).rstrip() + "\n"
        fd, tmp = tempfile.mkstemp(dir=str(manual.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, manual)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        _write_status(True, state)
        return True
    except Exception as e:
        _write_status(False, state, f"{type(e).__name__}: {e}")
        return False
