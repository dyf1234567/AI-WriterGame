"""Project-owned character cards: voice guidance, never a source of game events."""
import json
import logging
import re
from pathlib import Path

CARD_FILE = Path(__file__).resolve().parent.parent / "content" / "characters" / "cards.json"
_cache = {"stamp": None, "cards": {}}
logger = logging.getLogger(__name__)


def _text(value, limit=160):
    return re.sub(r"\s+", " ", value).strip()[:limit] if isinstance(value, str) else ""


def _cards():
    try:
        stat = CARD_FILE.stat()
        stamp = (str(CARD_FILE), stat.st_mtime_ns, stat.st_size)
        if stamp == _cache["stamp"]:
            return _cache["cards"]
        if stat.st_size > 262144:
            raise ValueError("character card catalogue exceeds 256 KiB")
        document = json.loads(CARD_FILE.read_text(encoding="utf-8-sig"))
        rows = document.get("cards", []) if isinstance(document, dict) else []
        cards = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("spec") != "chara_card_v2":
                continue
            data = row.get("data")
            if not isinstance(data, dict):
                continue
            ext = data.get("extensions")
            profile = ext.get("writer_game") if isinstance(ext, dict) else None
            if (isinstance(profile, dict) and isinstance(profile.get("npc_id"), str)
                    and all(isinstance(profile.get(k), str) for k in ("base_role", "want", "friction", "speech"))
                    and all(isinstance(profile.get(k), dict) for k in ("demo", "relationship_tone"))
                    and isinstance(profile.get("examples"), list)):
                cards[profile["npc_id"]] = (data, profile)
        _cache.update(stamp=stamp, cards=cards)
        return cards
    except (OSError, ValueError, TypeError):
        # Invalid edits must fall back immediately, not silently keep a stale character.
        if _cache["stamp"] is not None:
            logger.warning("character cards unavailable; using current NPC persona")
        _cache.update(stamp=None, cards={})
        return {}


def _document() -> dict:
    try:
        return json.loads(CARD_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"cards": []}


def _write_document(document: dict) -> None:
    CARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    CARD_FILE.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    _cache.update(stamp=None)


def _find_index(document: dict, npc: dict) -> int:
    rows = document.get("cards", []) if isinstance(document, dict) else []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        data = row.get("data") or {}
        profile = (data.get("extensions") or {}).get("writer_game") or {}
        if profile.get("npc_id") == npc.get("id") or data.get("name") == npc.get("name"):
            return idx
    return -1


def sync_card(npc: dict) -> bool:
    """GM 改写角色档案后同步角色卡：描述与人设一致，卡保持生效而不是失效。"""
    document = _document()
    idx = _find_index(document, npc)
    if idx < 0:
        return False
    row = document["cards"][idx]
    data = row.setdefault("data", {})
    data["name"] = npc.get("name", data.get("name", ""))
    data["description"] = npc.get("persona", data.get("description", ""))
    profile = (data.setdefault("extensions", {})).setdefault("writer_game", {})
    profile["npc_id"] = npc.get("id", profile.get("npc_id", ""))
    if npc.get("role"):
        profile["base_role"] = npc["role"]
    data["character_version"] = f"gm-{__import__('time').strftime('%Y%m%d%H%M%S')}"
    _write_document(document)
    return True


def card_for(npc: dict) -> dict | None:
    document = _document()
    idx = _find_index(document, npc)
    return document["cards"][idx] if idx >= 0 else None


def save_card(npc: dict, row: dict) -> tuple[bool, str]:
    """GM 保存整张卡：最小结构校验后按角色替换写回。"""
    if not isinstance(row, dict) or row.get("spec") != "chara_card_v2":
        return False, "卡必须是 chara_card_v2 结构的对象。"
    data = row.get("data")
    if not isinstance(data, dict) or not str(data.get("name", "")).strip():
        return False, "缺少 data.name。"
    profile = (data.get("extensions") or {}).get("writer_game")
    if not isinstance(profile, dict) or not isinstance(profile.get("npc_id"), str):
        return False, "缺少 extensions.writer_game.npc_id。"
    document = _document()
    idx = _find_index(document, npc)
    if idx < 0:
        document.setdefault("cards", []).append(row)
    else:
        document["cards"][idx] = row
    _write_document(document)
    return True, "角色卡已保存。"


def profile_for(npc):
    entry = _cards().get(npc.get("id"))
    if not entry:
        return None
    data, profile = entry
    # The live persona wins when GM edits a character. A preset voice must not undo it.
    if (data.get("name") != npc.get("name") or data.get("description") != npc.get("persona")
            or profile.get("base_role") != npc.get("role")):
        return None
    return profile


def voice_hint(npc):
    profile = profile_for(npc)
    return _text(profile.get("speech"), 150) if profile else ""


def _tone(npc):
    status = (npc.get("relationship") or {}).get("status")
    if status in ("partner", "distance"):
        return "partner"
    if not status and npc.get("relationship_status") in ("恋人", "异地恋人"):
        return "partner"
    if npc.get("known_to_player") and int(npc.get("affinity", 0)) >= 50:
        return "familiar"
    return "new"


def intent_of(text):
    """Choose relevant writing examples, not the meaning or outcome of a live reply."""
    for intent, pattern in (
        ("decline", r"不(?:去|想|约|能|愿意)|取消|改天|别约"),
        ("where", r"在哪|在干嘛|在做什么"),
        ("night", r"晚安|睡了"),
        ("comfort", r"累|难受|烦|考砸|失眠|失败|没过"),
        ("invite", r"一起|约你|见面|陪我|有空吗"),
        ("greeting", r"你好|在吗|早安|打招呼"),
        ("work", r"练琴|编曲|练声|演出|排练|工作|学习|项目"),
    ):
        if re.search(pattern, str(text)):
            return intent
    return "default"


def _summary(npc, profile):
    life = npc.get("life") or {}
    want = _text(life.get("goal") or profile.get("want"), 65)
    tone = (profile.get("relationship_tone") or {}).get(_tone(npc), "")
    return (f"{npc['name']}：在意{want}；卡住时{_text(profile.get('friction'), 65)}。"
            f"声口：{_text(profile.get('speech'), 150)} 相处：{_text(tone, 70)}")


def _examples(profile, channel, intent, tone, text=""):
    rows = [r for r in profile.get("examples", []) if isinstance(r, dict)
            and r.get("channel") == channel and r.get("tone", "any") in ("any", tone)]
    if channel == "chat":
        return [r for r in rows if r.get("intent") == intent][:2]
    # A registration example must not keep reintroducing forms into unrelated scenes.
    return [r for r in rows if isinstance(r.get("topics"), list)
            and any(isinstance(k, str) and k in text for k in r["topics"])][:1]


def chat_block(npc, text):
    profile = profile_for(npc)
    if not profile:
        return ""
    lines = ["【角色卡·仅校准说话与反应】", _summary(npc, profile),
             "下列均为假设对白，不是聊天历史或已发生事件；示例的时间、物件、关系不能写进事实、记忆或约定。当前状态和玩家原话优先，不能照抄示例答非所问。"]
    for row in _examples(profile, "chat", intent_of(text), _tone(npc)):
        lines.append(json.dumps({"假设条件": _text(row.get("condition"), 85),
                                 "示例来话": _text(row.get("user"), 70),
                                 "示例回复": _text(row.get("reply"), 120)}, ensure_ascii=False))
    return "\n".join(lines)


def scene_block(state, action=""):
    npcs = state.get("npcs") or []
    people = [n for n in npcs if n.get("name") and n["name"] in action]
    if not people:
        if not state.get("story") and state.get("turn", 0) == 0:
            people = [n for n in npcs if n.get("id") == "npc_liangyating"]
        else:
            place = (state.get("player", {}).get("location") or {}).get("place")
            people = [n for n in npcs if n.get("known_to_player") and n.get("place") == place]
    lines = ["【角色卡·场内反应参考】", "仅参考声口与做事方式；不是出场名单。示例是虚构试写，不是既成事实，不能搬用其物件、地点、承诺或结果。"]
    for npc in people[:2]:
        profile = profile_for(npc)
        if not profile:
            continue
        line = _summary(npc, profile)
        cue = action or ("报到手续" if not state.get("story") and state.get("turn", 0) == 0 else "")
        examples = _examples(profile, "scene", intent_of(action), _tone(npc), cue)
        if examples:
            row = examples[0]
            line += f"\n假设条件：{_text(row.get('condition'), 70)}；写法示例：{_text(row.get('reply'), 150)}"
        if len("\n".join([*lines, line])) <= 1000:
            lines.append(line)
    return "\n".join(lines) if len(lines) > 2 else ""


def demo_line(npc, intent):
    profile = profile_for(npc)
    value = (profile.get("demo") or {}).get(intent) if profile else None
    # Demo lines contain no new events, appointments, rewards or implicit relationship changes.
    return _text(value, 180)


def where_reply(npc):
    profile = profile_for(npc)
    place = _text(npc.get("place"), 60)
    if not profile or not place:
        return ""
    return f"在{place}。{_text((profile.get('demo') or {}).get('where_suffix'), 70)}"
