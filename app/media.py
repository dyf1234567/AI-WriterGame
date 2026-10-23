"""Local media catalogue and send-time attachment binding; no model or network calls."""
import hashlib
import json
import random
import re
from pathlib import Path
from urllib.parse import quote

from .config import STATIC_DIR

IMAGE_EXTS = {".svg", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v"}
ALIASES = {
    "自拍": ("自拍", "本人照"), "日常": ("日常", "随手拍", "生活碎片"),
    "风景": ("风景", "旅行", "旅拍", "海边", "天空", "窗外"),
    "美食": ("美食", "吃饭", "晚餐", "午餐", "奶茶"),
    "练琴": ("练琴", "钢琴", "琴房", "弹琴"),
    "演出": ("演出", "舞台", "演唱", "下台"),
    "游戏": ("游戏", "电竞", "排位", "打游戏"),
}


def _text(value, limit=100):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _metadata(path):
    try:
        if path.stat().st_size > 32768:
            return {}
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def catalogue():
    """Scan every request so new folders/files are available without a restart."""
    assets = []
    roots = (("image", STATIC_DIR / "images" / "npc"),
             ("video", STATIC_DIR / "videos" / "npc"),
             ("sticker", STATIC_DIR / "stickers"))
    for kind, root in roots:
        if not root.is_dir():
            continue
        extensions = VIDEO_EXTS if kind == "video" else IMAGE_EXTS
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() not in extensions or not path.is_file():
                continue
            try:
                path.resolve().relative_to(root.resolve())
                relative = path.relative_to(root)
                stat = path.stat()
            except (OSError, ValueError):
                continue
            parts = relative.parts
            if kind != "sticker" and len(parts) < 2:
                continue  # Legacy flat portraits keep their existing frontend fallback.
            owner = parts[0] if kind != "sticker" else ""
            folder = "/".join(parts[1:-1]) if kind != "sticker" else "/".join(parts[:-1])
            category = folder or ("日常" if kind != "sticker" else "通用")
            parent = _metadata(path.parent / "_category.json")
            meta = {**parent, **_metadata(path.with_name(path.name + ".json"))}
            category = _text(meta.get("category") or category, 60)
            tags = [path.stem, *category.split("/")]
            for key in ("tags", "aliases"):
                if isinstance(meta.get(key), list):
                    tags.extend(_text(tag, 60) for tag in meta[key] if isinstance(tag, str))
            rel = path.relative_to(STATIC_DIR).as_posix()
            asset_id = kind + "-" + hashlib.sha256(rel.encode("utf-8")).hexdigest()[:24]
            assets.append({"id": asset_id, "type": kind, "owner": owner,
                           "category": category, "name": _text(path.stem, 80),
                           "caption": _text(meta.get("caption") or path.stem, 100),
                           "tags": list(dict.fromkeys(tag for tag in tags if tag))[:24],
                           "url": "/static/" + "/".join(quote(part, safe="") for part in path.relative_to(STATIC_DIR).parts),
                           "version": f"{stat.st_mtime_ns}-{stat.st_size}"})
    photos, videos, video_categories = {}, {}, {}
    stickers = []
    for asset in assets:
        owner, category, url = asset["owner"], asset["category"], asset["url"]
        if asset["type"] == "image":
            photos.setdefault(owner, {}).setdefault(category, []).append(url)
        elif asset["type"] == "video":
            videos.setdefault(owner, []).append(url)
            video_categories.setdefault(owner, {}).setdefault(category, []).append(url)
        else:
            stickers.append({"id": asset["id"], "name": asset["name"], "url": url,
                             "category": category})
    version = hashlib.sha256(json.dumps(assets, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {"photos": photos, "videos": videos, "video_categories": video_categories,
            "stickers": stickers, "assets": assets, "version": version}


def requested_type(text):
    text = str(text or "")
    if re.search(r"(?:不想|不要|不用|别|不必).{0,8}(?:发|拍|录|照片|视频|图片)", text):
        return ""
    if not re.search(r"发|拍|录|分享|想看|看看|来(?:一|个|段|张|条)", text):
        return ""
    if "视频" in text or "录一段" in text:
        return "video"
    if re.search(r"照片|图片|自拍|拍张照|拍一张|发图", text):
        return "image"
    return ""


def _topic(text):
    text = str(text or "").casefold()
    text = re.sub(r"(?:[。！？!?，,：:；;]|刚刚|刚|今天|今日份|此刻|正在|那边|这边|只发给你|只发你一个人|随手|光线|刚好|一小段|一段|一条|一个|一张|一会儿|一下|看看|想看|可以|能不能|可不可以|请|给我|给你|你们|自己|视频|照片|图片|拍照|小|的|发|拍|录|我|你|个|段|张|条|吗|嘛|吧|了|哦)", "", text)
    return re.sub(r"[\W_]+", "", text)


def _terms(value):
    norm = re.sub(r"[\W_]+", "", str(value).casefold())
    result = {norm} if norm else set()
    for key, aliases in ALIASES.items():
        if any(alias in norm for alias in aliases):
            result.update((key, *aliases))
    return result


def select_asset(owner, kind, caption="", request="", recent=(), index=None, reference=""):
    index = index or catalogue()
    pool = [a for a in index["assets"] if a["type"] == kind and (kind == "sticker" or a["owner"] == owner)]
    if reference:
        exact = next((a for a in pool if a["id"] == reference), None)
        if exact:
            return exact
        # A stale/foreign ID must never fall back to a different named file.
        if re.fullmatch(r"(?:image|video|sticker)-[0-9a-f]{24}", reference):
            return None
    query = reference if kind == "sticker" else request or caption
    if kind == "sticker":
        matches = [a for a in pool if a["name"] == query]
        # Name-only legacy messages choose one format consistently; exact IDs retain each file.
        return sorted(matches, key=lambda a: (a["url"].lower().endswith(".svg"), a["url"]))[0] if matches else None
    # Prefer explicit category names, including newly added custom folders.
    folded = str(query).casefold()
    named = [a for a in pool if a["category"].casefold() in folded or
             any(part.casefold() in folded for part in a["category"].split("/") if len(part) > 1)]
    if named:
        pool = named
    topic = _topic(query)
    words = _terms(query)
    scores = []
    for asset in pool:
        tags = set().union(*(_terms(tag) for tag in [asset["category"], asset["name"], *asset["tags"]]))
        score = sum(5 for word in words if len(word) >= 2 and any(word in tag or tag in word for tag in tags if len(tag) >= 2))
        if topic and any(topic in tag or (len(tag) >= 2 and tag in topic) for tag in tags):
            score += 10
        scores.append((score, asset))
    if not scores:
        return None
    best = max(score for score, _ in scores)
    if not named and topic and best == 0:
        return None  # An explicit missing scene must not turn into an unrelated selfie.
    choices = [a for score, a in scores if score == best]
    fresh = [a for a in choices if a["id"] not in recent]
    return random.choice(fresh or choices)


def attachment(owner, kind, caption, request="", index=None, recent=(), reference=""):
    asset = select_asset(owner, kind, caption, request, recent, index, reference)
    if not asset:
        return {"type": kind, "caption": _text(caption, 100), "missing": True}
    return {key: asset[key] for key in ("id", "type", "owner", "category", "name", "url", "tags", "version")} | {"caption": _text(caption or asset["caption"], 100)}


def message_text(message):
    """Descriptions are recall evidence; an attachment is not a player commitment."""
    parts = [str(message.get("text") or "")]
    labels = {"image": "图片", "video": "视频", "sticker": "表情包"}
    attachments = message.get("attachments") or []
    if attachments:
        for item in attachments:
            if isinstance(item, dict):
                parts.append(f"〔{labels.get(item.get('type'), '附件')}：{item.get('caption') or item.get('name') or ''}；{' '.join(item.get('tags') or [])}〕")
    else:
        for kind, label in labels.items():
            if message.get(kind):
                parts.append(f"〔{label}：{message[kind]}〕")
    return " ".join(parts)


def bind_history(state, index=None):
    """Bind legacy attachments once when resuming/sending, retaining existing bindings."""
    pending = []
    for group in (state.get("chats") or {}, state.get("chat_history") or {}):
        for owner, chat in group.items():
            messages = chat.get("msgs", []) if isinstance(chat, dict) else chat
            for message in messages or []:
                if isinstance(message, dict) and "attachments" not in message and any(message.get(k) for k in ("image", "video", "sticker")):
                    pending.append((owner, message))
    for message in [*(state.get("moments") or []), *(state.get("inbox") or [])]:
        if isinstance(message, dict) and "attachments" not in message and any(message.get(k) for k in ("image", "video", "sticker")):
            pending.append((message.get("from") or message.get("npc") or message.get("title", ""), message))
    if not pending:
        return False
    index = index or catalogue()
    for owner, message in pending:
        message["attachments"] = [attachment(owner, kind, str(message[kind]), index=index,
                                             reference=str(message[kind]) if kind == "sticker" else "")
                                  for kind in ("image", "video", "sticker") if message.get(kind)]
    return True


def available_block(owner):
    index = catalogue()
    grouped = {}
    for asset in index["assets"]:
        if asset["owner"] == owner:
            grouped.setdefault(asset["type"], set()).add(asset["category"])
    return "【可用本地媒体分类】\n" + "\n".join(
        f"{'图片' if kind == 'image' else '视频'}：{'、'.join(sorted(categories))[:300]}"
        for kind, categories in grouped.items()) + "\n标题应包含实际分类或场景；附件仅描述素材，不代表已发生新剧情。"
