"""剧情引擎：回合推进、状态结算、剧情压缩、每日签到。"""
import json
import random
from copy import deepcopy
from pydantic import ValidationError
from itertools import combinations

from . import demo, llm, memory, prompts, storage
from .contracts import ChatResult, validate_turn
from .config import (
    DATA_DIR, DEMO_MODE, GAIN_CATALOG_CAP, GAIN_CURRENCY_CAP, GAIN_KIND_CAP,
    NPC_ARCHIVE_FILE, STORY_ARCHIVE_FILE,
)
from .models import (
    ACHIEVEMENTS, AFFINITY_DATE_CAP, AFFINITY_TURN_CAP, CHAT_HISTORY_KEPT, CURRENCY,
    DATE_AFFINITY_REQUIREMENT, HOOK_THEMES, INITIAL_TECHNIQUE_GRADE, MAIN_QUEST_NOTES,
    MAX_DATES_KEPT, MAX_HOOKS, MAX_NPCS, PLACE_TYPES_KNOWN, POWER_PROGRESS_PER_STAGE,
    POWER_STAGE_EFFECTS, POWER_STAGES, PRESET_NPC_IDS, PROGRESS_TURN_CAP, REALMS,
    LOTTERY_TICKET,
    SYSTEM_ITEMS, TECHNIQUE_ROUTES, WORLD_URBAN, advance_time, affinity_stage,
    effective_stats, is_romanceable, time_label,
    clamp, default_state, find_npc, now_iso, refresh_main_quest, game_today,
)

MAX_STORY = 60          # 剧情日志硬上限
COMPACT_THRESHOLD = 30  # 超过则触发压缩
COMPACT_KEEP = 12       # 压缩后保留最近段数

FALLBACK_CHOICES = ["谨慎观察四周", "按兵不动，静待变化"]


class EngineError(RuntimeError):
    """模型调用或输出解析失败。"""


def _call_llm_json(system: str, user: str, attempts: int = 2) -> dict:
    # 固定尝试两次（首次＋一次重试）；历史参数名 retries 名不副实，一并正名
    last_err: Exception | None = None
    for _ in range(max(1, min(attempts, 2))):
        try:
            data = llm.chat_json(system, user)
            return data if system == prompts.COMPACT_SYSTEM else validate_turn(data)
        except llm.ModelServiceError as e:
            raise EngineError(str(e)) from e
        except Exception as e:  # 网络/解析错误均重试
            last_err = e
    raise EngineError("模型输出格式不正确，请重试本回合（存档未改变）。") from last_err


# ---------- 回合推进 ----------

def start_game(name: str, show_affinity: bool = True) -> dict:
    state = default_state(name, show_affinity)
    if DEMO_MODE:
        data = demo.opening_segment(name)
    else:
        data = _call_llm_json(prompts.build_system_prompt(state), prompts.build_opening_user(state))
    try:
        data = validate_turn(data)
    except ValidationError as e:
        raise EngineError("开局数据格式不正确，原存档和归档已保留。") from e
    apply_updates(state, data)
    state["last_active"] = now_iso()
    storage.replace_game(state, (STORY_ARCHIVE_FILE, NPC_ARCHIVE_FILE))
    return state


def _ensure_date_from_action(state: dict, data: dict, action: str) -> None:
    """约会按钮保成：玩家用「【约会】邀请××」明确邀约且条件满足（已认识、好感≥亲近、
    非家人）而模型没输出 date_with 时，由引擎补上——按钮点了就该算数，不凭模型自觉。"""
    su = data.setdefault("state_updates", {})
    if su.get("date_with") or "【约会】邀请" not in action:
        return
    seg = str(action).split("【约会】邀请", 1)[1]
    name = _clean_text(seg.split("来", 1)[0], 12)
    npc = find_npc(state, name)
    if (npc is not None
            and npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0)
            and npc["affinity"] >= DATE_AFFINITY_REQUIREMENT
            and is_romanceable(npc)):
        su["date_with"] = npc["name"]


def take_turn(state: dict, action: str) -> tuple[dict, str]:
    """推进一回合，返回 (state, system_notice)。"""
    state = deepcopy(state)
    state["turn"] += 1
    if state["story"]:
        state["story"][-1]["chosen"] = action[:80]

    if DEMO_MODE:
        data = demo.next_segment(state, action)
    else:
        data = _call_llm_json(prompts.build_system_prompt(state), prompts.build_turn_user(state, action))

    try:
        data = validate_turn(data)
    except ValidationError as e:
        raise EngineError("回合数据格式不正确，原存档已保留，请重试。") from e
    _ensure_date_from_action(state, data, action)
    notice = apply_updates(state, data)
    compact_notice = maybe_compact(state)
    if compact_notice:
        notice = f"{notice} {compact_notice}".strip()
    state["last_active"] = now_iso()
    # 剧情回合做全量快照：恢复点面板才有东西可恢复（轻量操作仍 backup=False）
    storage.save(state, backup=True)
    return state, notice


# ---------- 状态结算 ----------

def _clean_text(value, limit: int) -> str:
    """清洗模型产出的字符串：剥掉尖括号（前端按 innerHTML 渲染）并截断。"""
    return str(value or "").replace("<", "").replace(">", "").strip()[:limit]


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _add_realm_progress(state: dict, delta: int) -> None:
    p = state["player"]
    p["realm_progress"] = clamp(p["realm_progress"] + clamp(delta, -100, 100), 0, 100)


def _breakthrough(state: dict) -> bool:
    p = state["player"]
    if p["realm"] >= len(REALMS) - 1 or p["realm_progress"] < 100:
        return False
    p["realm"] += 1
    p["realm_progress"] = 0
    refresh_main_quest(state)  # 主线只在这里推进：等级真升了，目标才换下一档
    return True


def npc_remember(npc: dict, turn: int, text: str, prefix: str | None = None) -> None:
    """NPC 记忆统一落点：短期记忆（提示词窗口，6条）+ 长期行事录（记忆手册，20条）。"""
    note = f"{prefix if prefix is not None else f'第{turn}回合：'}{text}"[:80]
    mem = npc.setdefault("memory", [])
    if not mem or mem[-1] != note:
        mem.append(note)
        npc["memory"] = mem[-6:]
    deeds = npc.setdefault("deeds", [])
    if not deeds or deeds[-1].get("text") != note:
        deeds.append({"turn": turn, "text": note})
        npc["deeds"] = deeds[-20:]


def set_persona(state: dict, npc_name: str, text: str) -> dict:
    """GM 后台为角色改写性格：真档案即时生效于提示词，并以记忆告知模型切换演绎。
    面向主持人工具，未登场的隐藏角色也可预设。"""
    npc = find_npc(state, npc_name)
    if npc is None:
        return {"ok": False, "msg": "名册上没有这个人。"}
    text = _clean_text(text, 200)
    if len(text) < 2:
        return {"ok": False, "msg": "性格描述太短了，至少写一句她是什么样的女孩。"}
    npc["persona"] = text
    npc["public_persona"] = text
    # 痕迹只进 DM 手册（deeds），不写玩家可见的 memory——persona 本身就会进提示词
    deeds = npc.setdefault("deeds", [])
    deeds.append({"turn": state["turn"], "text": "主持人在后台改写了性格设定"})
    npc["deeds"] = deeds[-20:]
    storage.save(state, backup=False)  # 可逆小操作
    return {"ok": True, "msg": f"已更新『{npc['name']}』的性格，模型将从之后的剧情按新设定演绎。"}


def gm_grant(state: dict, *, gold: int = 0, item: str = "", item_count: int = 1,
             stat: str = "", stat_value: int = 0, progress: int = 0, power: int = 0,
             ticket: int = 0) -> dict:
    """管理员发放：金币/道具/属性/等级进度/修为/抽奖券，绕过玩家侧一切护栏。
    入账走既有内部通道（_apply_items/_add_realm_progress/add_power_progress），
    收件箱留痕一笔，面板与剧情账本对得上。"""
    p = state["player"]
    msgs = []
    gold = clamp(int(gold or 0), -999999, 999999)
    if gold:
        _apply_items(state, [{"name": CURRENCY, "desc": "系统商城通用货币", "count": gold}])
        msgs.append(f"系统金币 {gold:+d}")
    if ticket:
        _apply_items(state, [{"name": LOTTERY_TICKET, "desc": "多一次转动命运转盘的机会",
                              "count": clamp(int(ticket), 1, 999)}])
        msgs.append(f"系统抽奖券 +{int(ticket)}")
    item = _clean_text(item, 40)
    if item:
        from .shop import CATALOG_BY_NAME
        if item not in CATALOG_BY_NAME and item != CURRENCY:
            return {"ok": False, "msg": f"商城目录里没有『{item}』——发放在售道具请从下拉框选。"}
        _apply_items(state, [{"name": item, "desc": CATALOG_BY_NAME.get(item, {}).get("desc", ""),
                              "count": clamp(int(item_count), 1, 999)}])
        msgs.append(f"{item} ×{clamp(int(item_count), 1, 999)}")
    stat = _clean_text(stat, 10)
    if stat and stat_value:
        stats = p.setdefault("stats", {})
        stats[stat] = clamp(stats.get(stat, 0) + int(stat_value), 0, 99)
        msgs.append(f"{stat} {stat_value:+d}")
    if progress:
        _add_realm_progress(state, int(progress))
        msgs.append(f"等级进度 {int(progress):+d}%")
        while p["realm_progress"] >= 100 and _breakthrough(state):
            msgs.append(f"触发提升——当前等级：{REALMS[p['realm']]}！")
    if power:
        power = clamp(int(power), 0, 999)
        if (state.get("power") or {}).get("awakened"):
            power_msgs = add_power_progress(state, power)
            msgs.append(f"修为 +{power}")
            msgs.extend(power_msgs)
        else:
            pw = state.setdefault("power", {"awakened": False, "stage": 0, "progress": 0})
            pw["progress"] = clamp(pw.get("progress", 0) + power, 0, 100)
            msgs.append(f"修为 +{power}（未觉醒，暂存而不炼化）")
    if not msgs:
        return {"ok": False, "msg": "没有填写任何要发放的内容。"}
    state["inbox"] = (state.get("inbox") or [])[-49:] + [{
        "ts": now_iso(), "type": "event", "world": state["player"]["world"],
        "title": "GM 后台 · 管理员发放",
        "text": "；".join(msgs) + "。",
    }]
    storage.save(state, backup=False)
    return {"ok": True, "msg": "已发放：" + "；".join(msgs)}


def _apply_affinity(state: dict, changes, date_target: str | None = None) -> list[str]:
    """结算好感变化，返回公告文案（含跨阶段与截断提示），并注入待消化剧情钩子。

    单回合护栏（规则侧）：同一 NPC 的多条申报按累计值钳制——
    普通回合 ±AFFINITY_TURN_CAP、约会对象 ±AFFINITY_DATE_CAP。
    提示词里的"通常 -10~+10"只是软约束，模型不听时在这里硬拦，
    否则一回合 +100 就能从「朋友」直跳「羁绊」，送礼限额与约会门槛形同虚设。
    """
    stage_msgs: list[str] = []
    applied: dict[str, int] = {}   # 本回合每 NPC 的累计好感变化
    clipped: list[str] = []
    for ch in changes or []:
        if not isinstance(ch, dict):
            continue
        npc = find_npc(state, str(ch.get("npc", "")))
        delta = ch.get("delta", 0)
        if npc is None or not isinstance(delta, (int, float)):
            continue
        cap = AFFINITY_DATE_CAP if npc["name"] == date_target else AFFINITY_TURN_CAP
        # 约会里的真实属性加成：会说话（情商）与好仪态（魅力）让相处更熨帖，
        # 在 ±15 的钳制口径内各最多 +2（负面表现仍由模型自报负值）
        if npc["name"] == date_target and int(delta) > 0:
            stats = effective_stats(state)
            bonus = (1 if stats.get("情商", 0) >= 60 else 0) + (1 if stats.get("魅力", 0) >= 60 else 0)
            if bonus:
                delta = int(delta) + bonus
        done = applied.get(npc["name"], 0)
        total = clamp(done + int(delta), -cap, cap)
        eff = total - done
        applied[npc["name"]] = total
        if eff != int(delta):
            clipped.append(f"{npc['name']}（限±{cap}）")
        before = affinity_stage(npc["affinity"])
        npc["affinity"] = clamp(npc["affinity"] + eff, 0, 100)
        npc["last_seen_turn"] = state["turn"]
        after = affinity_stage(npc["affinity"])
        if after != before:
            stage_msgs.append(f"【系统】你与{npc['name']}的关系升温：{before} → {after}。")
            if after in HOOK_THEMES:
                hooks = state.setdefault("hooks", [])
                hooks.append({"npc": npc["name"], "stage": after, "turn": state["turn"]})
                state["hooks"] = hooks[-MAX_HOOKS:]
        reason = _clean_text(ch.get("reason"), 60)
        if reason:
            npc_remember(npc, state["turn"], reason)
    if clipped:
        stage_msgs.append("【系统】好感变化超出单回合上限，已按上限结算：" + "、".join(clipped))
    return stage_msgs


def _resolve_hook(state: dict, done) -> list[str]:
    """消化剧情钩子：hook_done 给 NPC 名。"""
    name = _clean_text(done, 12)
    if not name:
        return []
    hooks = state.setdefault("hooks", [])
    kept = []
    resolved = []
    for h in hooks:
        if h.get("npc") == name:
            resolved.append(f"与{name}的「{h.get('stage', '')}」时刻")
        else:
            kept.append(h)
    if not resolved:
        return [f"【系统】申报消化的心事查无对应钩子：{name}"]
    state["hooks"] = kept
    return [f"【系统】心事已写下：{'；'.join(resolved)}。"]


def _apply_items(state: dict, items) -> None:
    for it in items or []:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name", "")).strip()
        if not name:
            continue
        count = max(1, _as_int(it.get("count"), 1))
        for owned in state["player"]["items"]:
            if owned["name"] == name:
                owned["count"] = owned.get("count", 1) + count
                break
        else:
            state["player"]["items"].append(
                {"name": name, "desc": str(it.get("desc", ""))[:60], "count": count})


def _remove_items(state: dict, name: str, count: int) -> int:
    """从背包扣除物品，返回实际扣到的数量；余额不足时扣到零，账本永不为负。"""
    items = state["player"]["items"]
    entry = next((i for i in items if i["name"] == name), None)
    if entry is None:
        return 0
    got = min(int(entry.get("count", 1)), max(0, count))
    entry["count"] = entry.get("count", 1) - got
    if entry["count"] <= 0:
        items.remove(entry)
    return got


def _catalog_names() -> set[str]:
    """商城在售物品名。延迟导入：shop 依赖本模块的结算函数。"""
    from .shop import CATALOG_BY_NAME
    return set(CATALOG_BY_NAME)


def _apply_model_gains(state: dict, items) -> tuple[list[str], list[str], list[str]]:
    """结算模型申报的所得，按护栏截断。返回（入账明细，被截断明细，被拒绝的系统专属物品）。

    没有护栏时模型可以凭空发放金币与在售穿搭，而穿搭能半价卖出——
    商城定价会被整条绕过。抽奖券更狠：它能经奖池洗成在售物品再变现，
    所以系统专属物品一律拒绝，只能走系统通道。
    """
    catalog = _catalog_names()
    clipped: list[str] = []
    blocked: list[str] = []
    pending: list[dict] = []
    totals: dict[str, int] = {}
    currency_given = catalog_given = 0
    kinds: set[str] = set()

    for it in items or []:
        if not isinstance(it, dict):
            continue
        name = _clean_text(it.get("name"), 20)
        if _as_int(it.get("count"), 1) < 1:
            continue  # count=0 占位条目：丢弃
        if not name:
            continue
        want = clamp(_as_int(it.get("count"), 1), 1, 999)

        if name in SYSTEM_ITEMS:
            blocked.append(f"{name}x{want}")
            continue
        if name == CURRENCY:
            give = min(want, GAIN_CURRENCY_CAP - currency_given)
            if give <= 0:
                clipped.append(f"{name}x{want}（单回合金币上限 {GAIN_CURRENCY_CAP}）")
                continue
            if give < want:
                clipped.append(f"{name}x{want - give}（单回合金币上限 {GAIN_CURRENCY_CAP}）")
            currency_given += give
        elif name in catalog:
            if catalog_given >= GAIN_CATALOG_CAP:
                clipped.append(f"{name}x{want}（单回合在售物品上限 {GAIN_CATALOG_CAP} 件）")
                continue
            catalog_given += 1
            if want > 1:
                clipped.append(f"{name}x{want - 1}（单回合在售物品上限 {GAIN_CATALOG_CAP} 件）")
            give = 1
        else:
            if name not in kinds and len(kinds) >= GAIN_KIND_CAP:
                clipped.append(f"{name}x{want}（单回合其他物品种类上限 {GAIN_KIND_CAP}）")
                continue
            kinds.add(name)
            # 目录外（模型自创）物品同种件数也钳 3：不入护栏的量会是背包垃圾
            give = min(want, GAIN_KIND_CAP)
            if give < want:
                clipped.append(f"{name}x{want - give}（目录外物品单回合至多 {GAIN_KIND_CAP} 件）")

        pending.append({"name": name, "desc": _clean_text(it.get("desc"), 60), "count": give})
        totals[name] = totals.get(name, 0) + give

    _apply_items(state, pending)
    ledger = [f"{name} +{count}" for name, count in totals.items()]
    return ledger, clipped, blocked


def _apply_model_spends(state: dict, items) -> tuple[list[str], list[str], list[str]]:
    """结算模型申报的支出。返回（入账明细，短付明细，被拒绝的系统专属物品）。

    apply_updates 先在状态副本上调用本函数预检，存在短缺则拒绝整个回合；
    正式状态只有在全部支出可支付时才执行，不能把这里的部分扣除当成交易成功。
    """
    ledger: list[str] = []
    short: list[str] = []
    blocked: list[str] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        name = _clean_text(it.get("name"), 20)
        if not name:
            continue
        want = clamp(_as_int(it.get("count"), 1), 1, 9999)
        if want < 1:
            continue  # count=0 的"无花费"占位条目：丢弃，不结算
        if name in SYSTEM_ITEMS:
            blocked.append(f"{name}x{want}")
            continue
        reason = _clean_text(it.get("reason"), 30)
        got = _remove_items(state, name, want)
        if got <= 0:
            short.append(f"{name}x{want}（持有 0）")
            continue
        ledger.append(f"{name} -{got}" + (f"（{reason}）" if reason else ""))
        if got < want:
            short.append(f"{name} 缺 {want - got}")
    return ledger, short, blocked


def _apply_npc_events(state: dict, events) -> None:
    """把 NPC 间事件落到双方的关系与记忆上。"""
    for ev in events or []:
        text = _clean_text(ev, 100)
        if not text:
            continue
        involved = [n for n in state["npcs"] if n["name"] in text]
        for a, b in combinations(involved, 2):
            a["rels"][b["name"]] = text[:80]
            b["rels"][a["name"]] = text[:80]
        for n in involved:
            n["last_seen_turn"] = state["turn"]
            # NPC 间幕后事件：独立前缀，public_state 的 memo 按它过滤不下发
            npc_remember(n, state["turn"], text, prefix="幕后：")


def _clean_place_type(raw) -> str:
    """地点类型只接受图例白名单——它会被前端拼进 innerHTML，且是详情卡的分类标签。"""
    t = str(raw or "").strip()
    return t if t in PLACE_TYPES_KNOWN else ""


def _guess_city(place_name: str) -> str:
    """模型自创地点的城市归属：契约里没有 city 字段，按命名前缀推断，默认京都。"""
    return "魔都" if place_name.startswith("魔都") else "京都"


def _fold_indoor_place(places: list, name: str) -> str:
    """「母地点·室内场所」（如 京华大学·图书馆）归并到已存在的母地点——
    室内细节属于剧情描写，不该在地图上另立节点灌水。母地点不存在才原样登记。"""
    if "·" not in name:
        return name
    parent = name.split("·", 1)[0].strip()
    if parent and any(p["name"] == parent for p in places):
        return parent
    return name


def _apply_map(state: dict, updates: dict) -> None:
    """结算位置移动与新地点发现（单世界：一律落在都市）。"""
    loc = updates.get("location")
    if isinstance(loc, dict) and str(loc.get("place", "")).strip():
        place = _clean_text(loc.get("place"), 20)
        places = state["map"].setdefault(WORLD_URBAN, [])
        place = _fold_indoor_place(places, place)
        if not any(p["name"] == place for p in places):
            places.append({"name": place, "desc": "", "discovered": True})
        city = next((pl.get("city") for pl in places if pl["name"] == place), None) \
            or _guess_city(place)
        state["player"]["location"] = {"world": WORLD_URBAN, "country": "华夏",
                                       "city": city, "place": place}
        state["player"]["world"] = WORLD_URBAN
        for existing in places:
            if existing["name"] == place:
                existing["discovered"] = True

    for np in updates.get("new_places") or []:
        if not isinstance(np, dict) or not str(np.get("name", "")).strip():
            continue
        name = _clean_text(np.get("name"), 20)
        desc = _clean_text(np.get("desc"), 60)
        ptype = _clean_place_type(np.get("type"))
        places = state["map"].setdefault(WORLD_URBAN, [])
        name = _fold_indoor_place(places, name)
        for existing in places:
            if existing["name"] == name:
                # 揭示既有迷雾地点（探索发现）；非空字段都补上——
                # location 先建条目、new_places 后到的正常时序里 type 不该被丢
                existing["discovered"] = True
                if not existing.get("city"):
                    existing["city"] = _guess_city(name)
                if desc:
                    existing["desc"] = desc
                if ptype and not existing.get("type"):
                    existing["type"] = ptype
                break
        else:
            places.append({"name": name, "desc": desc or "新探明之地",
                           "type": ptype, "city": _guess_city(name), "discovered": True})
        if len(places) > 24:
            state["map"][WORLD_URBAN] = places[-24:]


def _archive_npcs(state: dict, victims: list[dict]) -> bool:
    """被淘汰人物的完整档案（好感/行事录/关系）落盘；写不进去就不允许淘汰。"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with NPC_ARCHIVE_FILE.open("a", encoding="utf-8") as f:
            for n in victims:
                rec = {"archived_at": now_iso(), "evicted_turn": state["turn"]}
                rec.update({k: n.get(k) for k in (
                    "id", "name", "world", "role", "persona", "place",
                    "affinity", "label", "memory", "deeds", "rels", "last_seen_turn")})
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def _find_archived_npc(name: str) -> dict | None:
    """按名册同样的匹配规则（含子串）找最近一份离场档案；没有返回 None。"""
    try:
        lines = NPC_ARCHIVE_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines[-400:]):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        old = str(rec.get("name", ""))
        if old and (old == name or old in name or name in old):
            return rec
    return None


def _restore_npc(state: dict, entry: dict, name: str, rec: dict) -> dict:
    """离场人物重逢：恢复旧档（好感/行事录/关系延续），再用模型给的近况覆盖身份信息。"""
    npc = {k: rec.get(k) for k in (
        "id", "name", "world", "role", "persona", "place",
        "affinity", "label", "memory", "deeds", "rels")}
    npc["memory"] = list(npc.get("memory") or [])
    npc["deeds"] = list(npc.get("deeds") or [])
    npc["rels"] = dict(npc.get("rels") or {})
    npc["world"] = WORLD_URBAN  # 单世界正典：归档恢复的人物一律落在都市
    if _clean_text(entry.get("role"), 16):
        npc["role"] = _clean_text(entry.get("role"), 16)
    if _clean_text(entry.get("persona"), 80):
        npc["persona"] = _clean_text(entry.get("persona"), 80)
    if _clean_text(entry.get("place"), 20):
        npc["place"] = _clean_text(entry.get("place"), 20)
    # 好感走旧档：关系延续是归档的全部意义，模型申报的新初始值不作数
    npc["affinity"] = clamp(_as_int(npc.get("affinity"), 50), 0, 100)
    npc["last_seen_turn"] = state["turn"]
    npc_remember(npc, state["turn"], "久别重逢，重新出现在主角的世界里")
    return npc


def _evict_npcs(state: dict) -> None:
    """名册超上限时淘汰最久未登场的生成人物；预设主角团永不淘汰。

    淘汰前必须先把档案归档——归档写不进去就宁可名册暂时超编，绝不静默销毁人生。
    """
    overflow = len(state["npcs"]) - MAX_NPCS
    if overflow <= 0:
        return
    generated = [n for n in state["npcs"] if n.get("id") not in PRESET_NPC_IDS]
    generated.sort(key=lambda n: n.get("last_seen_turn", -1))
    victims = generated[:overflow]
    if not victims:
        return
    if not _archive_npcs(state, victims):
        return
    for npc in victims:
        state["npcs"].remove(npc)


def _apply_new_npcs(state: dict, updates: dict) -> tuple[list[str], list[str]]:
    """登记剧情中新登场的人物，返回（新登记名单，旧识重逢名单）。

    判重必须用精确匹配——find_npc 的双向子串是给"玩家用简称指代"做容错的，
    拿它判重会把「郭瑞莹的表姐」这类新角色静默吞掉（下一回合人就没了）。
    """
    added: list[str] = []
    reunited: list[str] = []
    for entry in updates.get("new_npc") or []:
        if not isinstance(entry, dict):
            continue
        name = _clean_text(entry.get("name"), 12)
        if not name or any(n["name"] == name for n in state["npcs"]):
            continue
        archived = _find_archived_npc(name)
        if archived is not None:
            state["npcs"].append(_restore_npc(state, entry, name, archived))
            reunited.append(name)
            continue
        world = WORLD_URBAN
        role = _clean_text(entry.get("role"), 16) or "身份不明"
        state["npcs"].append({
            "id": f"npc_gen{state['turn']}_{len(state['npcs'])}",
            "name": name,
            "world": world,
            "role": role,
            "persona": _clean_text(entry.get("persona"), 80) or role,
            "place": _clean_text(entry.get("place"), 20)
            or state["player"].get("location", {}).get("place", ""),
            "affinity": clamp(_as_int(entry.get("affinity"), 50), 0, 100),
            "label": _clean_text(entry.get("label"), 10) or "初识",
            "memory": [f"第{state['turn']}回合：初次登场"],
            "deeds": [{"turn": state["turn"], "text": f"第{state['turn']}回合：初次登场"}],
            "rels": {},
            "last_seen_turn": state["turn"],
        })
        added.append(name)
    _evict_npcs(state)
    return added, reunited


def _apply_identity(state: dict, updates: dict) -> str | None:
    """主角的社会身份变化落档（入门/拜师/晋升/被逐）；返回通知文本，无变化为 None。"""
    up = updates.get("identity_update")
    if not isinstance(up, dict):
        return None
    world = up.get("world")
    text = _clean_text(up.get("text"), 30)
    if world != WORLD_URBAN or not text:
        return None
    ident = state["player"].setdefault("identity", {})
    if ident.get(WORLD_URBAN) == text:
        return None
    ident[WORLD_URBAN] = text
    return f"【系统】身份更新：{text}"


def _canon_route(text: str) -> str:
    """把模型给的路线说法归到设定集的六条路线上；对不上就原样保留。"""
    if not text:
        return ""
    for route in TECHNIQUE_ROUTES:
        if route in text or text in route:
            return route
    return text


def _apply_technique(state: dict, updates: dict) -> str | None:
    """初始天赋一次性闸。返回通知文本，无申报时为 None。

    品质由系统固定为 S 级、发放次数由 player.technique 记账，两者都不交给模型——
    否则"只能领一次"只是提示词里的一句请求，实测可以连领三部。
    """
    grant = updates.get("technique_grant")
    if not isinstance(grant, dict):
        return None
    name = _clean_text(grant.get("name"), 20)
    if not name:
        return None
    p = state["player"]
    owned = p.get("technique")
    if isinstance(owned, dict) and owned.get("name"):
        return (f"【系统】初始天赋已领取（{_canon_route(owned.get('route', '')) or '未定路线'}"
                f"·《{owned['name']}》），不得重复发放——已拒绝《{name}》。")
    route = _canon_route(_clean_text(grant.get("route"), 10))
    p["technique"] = {
        "route": route,
        "name": name,
        "grade": INITIAL_TECHNIQUE_GRADE,
        "turn": state["turn"],
    }
    _apply_items(state, [{
        "name": name,
        "desc": _clean_text(grant.get("desc"), 60)
        or f"{route or '未定路线'}初始天赋（{INITIAL_TECHNIQUE_GRADE}）",
        "count": 1,
    }])
    return (f"【系统】初始天赋已录入：{route or '未定路线'}·《{name}》"
            f"（{INITIAL_TECHNIQUE_GRADE}），已放入背包。")


# ---------- 超凡觉醒（心动系统的隐藏功能） ----------

def awaken_power(state: dict) -> str:
    """服用觉醒灵种：点亮灵根，踏入第一境。重复服用被拒。"""
    power = state.setdefault("power", {"awakened": False, "stage": 0, "progress": 0, "chat_bonus": {}})
    if power.get("awakened"):
        return "【系统】灵种早已在体内生根——境界只能一步一步走，急不得。"
    power.update({"awakened": True, "stage": 1, "progress": 0})
    return ("【系统】隐藏功能解锁·灵能觉醒：一缕暖流自心口炸开，你听见了世界底下的潮声——"
            f"当前境界【{POWER_STAGES[1]}】。此事仅你与系统知晓，谨慎保密。")


def add_power_progress(state: dict, n: int) -> list[str]:
    """修为入账：满 100 突破下一境；淬体境突破时体魄永久 +2。返回公告列表。"""
    power = state.setdefault("power", {"awakened": False, "stage": 0, "progress": 0, "chat_bonus": {}})
    if not power.get("awakened") or n <= 0:
        return []
    msgs = []
    if power["stage"] >= len(POWER_STAGES) - 1:
        power["progress"] = min(power["progress"] + n, POWER_PROGRESS_PER_STAGE)
        return []  # 已至御气圆满，修为只作记录
    power["progress"] += n
    while (power["progress"] >= POWER_PROGRESS_PER_STAGE
           and power["stage"] < len(POWER_STAGES) - 1):
        power["progress"] -= POWER_PROGRESS_PER_STAGE
        power["stage"] += 1
        effect = POWER_STAGE_EFFECTS.get(power["stage"], "")
        msgs.append(f"【系统】修为圆满，突破至【{POWER_STAGES[power['stage']]}】！{effect}")
        if power["stage"] == 2:  # 淬体：气血重铸
            stats = state["player"].setdefault("stats", {})
            stats["体魄"] = clamp(stats.get("体魄", 0) + 2, 0, 99)
    return msgs


def chat_affinity_bonus(state: dict, npc_name: str) -> int:
    """灵犀（第4境）：每日与同一人的第一条短信好感 +1。返回实际加值。"""
    power = state.get("power") or {}
    if not power.get("awakened") or power.get("stage", 0) < 4:
        return 0
    today = game_today(state)
    bonus_log = power.setdefault("chat_bonus", {})
    if bonus_log.get(today) is None:
        bonus_log[today] = []
    if npc_name in bonus_log[today]:
        return 0
    bonus_log[today].append(npc_name)
    if len(bonus_log) > 30:  # 日结账滚动窗口，防无限增长
        for k in sorted(bonus_log)[:-30]:
            bonus_log.pop(k, None)
    return 1


def _apply_date(state: dict, updates: dict, story_text: str) -> str | None:
    """正式约会落档：门槛校验（好感≥亲近70）、入约会回忆、写入 NPC 记忆。"""
    name = _clean_text(updates.get("date_with"), 12)
    if not name:
        return None
    npc = find_npc(state, name)
    if npc is None or not npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0):
        return f"【系统】约会对象「{name}」不在已认识的名册里，本回合未按正式约会结算。"
    if not is_romanceable(npc):
        return f"【系统】{npc['name']}是家人——陪伴可以，正式约会不适用，本回合按寻常相处结算。"
    if npc["affinity"] < DATE_AFFINITY_REQUIREMENT:
        return (f"【系统】与{name}的关系还未到「亲近」（好感{npc['affinity']}/70），"
                "本次只是寻常相处，不算正式约会。")
    place = (state["player"].get("location") or {}).get("place", "某处")
    state.setdefault("dates", []).append({
        "npc": npc["name"], "turn": state["turn"], "ts": now_iso(),
        "place": place, "text": _clean_text(story_text, 120),
    })
    state["dates"] = state["dates"][-MAX_DATES_KEPT:]
    npc["last_seen_turn"] = state["turn"]
    npc_remember(npc, state["turn"], f"在{place}与主角约会")
    return f"【系统】约会时刻：与{npc['name']}在{place}——这一晚已存入回忆。"


# ---------- 成就与结局（阶段F） ----------

def sync_achievements(state: dict) -> list[str]:
    """谓词式检查全部成就，返回新解锁的公告文案。"""
    got = state.setdefault("achievements", [])
    notices = []
    for ach in ACHIEVEMENTS:
        if ach["id"] in got:
            continue
        try:
            hit = ach["check"](state)
        except Exception:
            hit = False
        if hit:
            got.append(ach["id"])
            notices.append(f"【系统】达成成就「{ach['title']}」——{ach['desc']}。")
    return notices


def _maybe_ending(state: dict) -> str | None:
    """结局分支：登顶「人生赢家」时结算——与羁绊最深的人（或只属于自己的答案）。"""
    if state["player"]["realm"] < len(REALMS) - 1 or state.get("ending"):
        return None
    candidates = [n for n in state["npcs"]
                  if n.get("known_to_player", n.get("last_seen_turn", -1) >= 0)
                  and n.get("role") != "母亲" and n["affinity"] >= 85]
    candidates.sort(key=lambda n: n["affinity"], reverse=True)
    partner = candidates[0] if candidates else None
    title = f"与{partner['name']}的毕业季" if partner else "属于自己的毕业季"
    state["ending"] = {"turn": state["turn"], "title": title,
                       "partner": partner["name"] if partner else None,
                       "affinity": partner["affinity"] if partner else None}
    extra = (f"羁绊最深的是{partner['name']}（好感{partner['affinity']}）"
             if partner else "没有谁胜过谁——你选择了自己的人生")
    return (f"【系统】大结局：《{title}》——{extra}。这一程到此画上句点，"
            "往后的每个回合都是番外。")


def apply_updates(state: dict, data: dict) -> str:
    """把模型（或演示）返回的 JSON 契约落到 state，返回 system_notice。"""
    text = str(data.get("story_text", "")).strip()
    if not text:
        raise EngineError("模型未返回剧情正文（story_text 为空）")

    world = data.get("narration_world")
    if world != WORLD_URBAN:
        world = WORLD_URBAN

    choices = [str(c).strip()[:60] for c in (data.get("choices") or []) if str(c).strip()]
    if len(choices) < 2:
        choices = FALLBACK_CHOICES[:]

    updates = data.get("state_updates") or {}
    if not isinstance(updates, dict):
        updates = {}
    # 行动计时起点：位置变化与约会耗时都以进入本回合前的位置为准
    place_before = (state["player"].get("location") or {}).get("place", "")

    # 在任何状态变化前校验完整收支；缺款、缺材料时整回合拒绝，不能先发货。
    probe = deepcopy(state)
    _apply_model_gains(probe, updates.get("item_gained"))
    _, shortages, _ = _apply_model_spends(probe, updates.get("item_spent"))
    if shortages:
        raise EngineError("本回合收支无法成立，未扣款、未发货，请调整行动后重试：" + "；".join(shortages))
    # 等级进度单回合硬钳（与好感对称，兑现提示词规则3的承诺）：
    # 只作用于模型申报的这一路——签到/支线/道具/GM 发放走内部通道不受限；
    # 演示模式是内置脚本而非模型，同样豁免（其节奏 6-8+尾4 是设计值）
    raw_progress = _as_int(updates.get("realm_progress_delta"), 0)
    progress_cap = PROGRESS_TURN_CAP if not DEMO_MODE else 999
    progress_delta = clamp(raw_progress, -progress_cap, progress_cap)
    projected_progress = clamp(state["player"]["realm_progress"] + progress_delta, 0, 100)
    if updates.get("realm_breakthrough") and projected_progress < 100:
        raise EngineError("提升条件未满足：等级进度需达到100%，本回合尚未提交。")

    # 等级进度与提升
    _add_realm_progress(state, progress_delta)
    progress_clip_notice = (
        f"【系统】等级进度超出单回合上限，已按上限结算：申报 {raw_progress:+d}，取 {progress_delta:+d}。"
        if progress_delta != raw_progress else "")
    p = state["player"]
    # 一回合最多只突破一级：进度满100与模型申报突破同时成立时也只走一次，
    # 否则一句"特训一整月"就连跳两级，等级主干与派生出来的主线档位会一起失真。
    broke = _breakthrough(state) if p["realm_progress"] >= 100 else False
    invalid_breakthrough = bool(updates.get("realm_breakthrough")) and not broke

    gained, clipped, gain_blocked = _apply_model_gains(state, updates.get("item_gained"))
    spent, short, spend_blocked = _apply_model_spends(state, updates.get("item_spent"))
    _apply_map(state, updates)
    world = p["world"]
    # 先落位置、再登记新人物，本回合的关系变化才落得到刚登场的人身上
    new_npcs, reunited = _apply_new_npcs(state, updates)
    date_notice = _apply_date(state, updates, text)
    # 时间与日程：基础1时段 + 换地点赶路1（御气境身轻如燕，赶路不再耗时）
    # + 约会2 + 模型申报的额外耗时
    place_after = (p.get("location") or {}).get("place", "")
    _move_cost = 0 if (state.get("power") or {}).get("stage", 0) >= 5 else 1
    time_cost = 1 + (_move_cost if place_after and place_after != place_before else 0) \
        + (2 if date_notice and "约会时刻" in date_notice else 0) \
        + clamp(_as_int(updates.get("time_cost"), 0), 0, 3)
    advance_time(state, time_cost)
    for npc in state["npcs"]:
        if npc["name"] in text:
            if not npc.get("known_to_player", npc.get("world") == WORLD_URBAN):
                npc["label"] = "初识"
            npc["known_to_player"] = True
            npc["known_memory"] = (npc.get("known_memory", []) +
                                   [f"第{state['turn']}回合：{_clean_text(text, 160)}"])[-6:]
    for reveal in updates.get("npc_reveals") or []:
        npc = find_npc(state, str(reveal.get("npc", "")))
        if npc and npc.get("known_to_player") and npc["name"] in text:
            if reveal.get("text"):
                npc["public_persona"] = _clean_text(reveal["text"], 160)
            if isinstance(reveal.get("rels"), dict):
                npc.setdefault("known_rels", {}).update({
                    _clean_text(k, 12): _clean_text(v, 80) for k, v in reveal["rels"].items()})
    # 约会判定（供好感钳制放宽档位与 _apply_date 判定使用）
    date_target_name = None
    _dw = _clean_text(updates.get("date_with"), 12)
    if _dw:
        _dn = find_npc(state, _dw)
        if (_dn is not None and _dn.get("known_to_player", _dn.get("last_seen_turn", -1) >= 0)
                and _dn["affinity"] >= DATE_AFFINITY_REQUIREMENT):
            date_target_name = _dn["name"]

    stage_msgs = _apply_affinity(state, updates.get("affinity_changes"), date_target=date_target_name)
    _apply_npc_events(state, updates.get("npc_events"))
    identity_msg = _apply_identity(state, updates)
    technique_msg = _apply_technique(state, updates)
    # 修为入账（觉醒后才有意义；模型申报的奇遇/修炼收益，硬钳 0-15）
    power_msgs = add_power_progress(state, clamp(_as_int(updates.get("power_progress"), 0), 0, 15))
    # 长期事实账本（记忆工程）：承诺/伏笔/秘密即时入账
    record = updates.get("fact_record")
    records = record if isinstance(record, list) else [record] if record else []
    for fr in records:
        memory.append_fact(state, fr, state["turn"])
    # 兑现了的承诺/揭破的伏笔记账为了结：不再常驻，但账本留着"这事办过"
    resolved_list = updates.get("fact_resolved")
    resolved_list = resolved_list if isinstance(resolved_list, list) else [resolved_list] if resolved_list else []
    resolved_msgs = []
    for fr in resolved_list:
        done = memory.resolve_fact(state, fr, state["turn"])
        if done:
            resolved_msgs.append(f"【系统】事实了结：{done}")
        elif fr:
            resolved_msgs.append(f"【系统】想了结的这段往事没有找到对应记录，暂不了结（{_clean_text(fr, 24)}…）")

    sq = updates.get("new_side_quest")
    if isinstance(sq, dict) and sq.get("title"):
        title = _clean_text(sq["title"], 30)
        if title and not any(q["title"] == title for q in state["side_quests"]):
            state["side_quests"].append(
                {"title": title, "desc": _clean_text(sq.get("desc"), 80), "done": False,
                 "added_turn": state["turn"]})

    qp = updates.get("quest_progress")
    if isinstance(qp, str) and qp.strip():
        # 主线目标由等级主干派生，这里只记"本阶段做了什么"，不再覆盖 desc、不再推 stage
        notes = state["main_quest"].setdefault("notes", [])
        note = _clean_text(qp, 120)
        if note not in notes:
            state["main_quest"]["notes"] = (notes + [note])[-MAIN_QUEST_NOTES:]

    # 支线完成：创建与完成至少隔一回合（秒接秒交是刷奖励的口子），且每回合最多结算一条
    qc = updates.get("quest_complete")
    if isinstance(qc, str):
        qc = [qc]
    done_msgs = []
    reject_msgs = []
    for title in qc or []:
        t = str(title).strip()
        if not t:
            continue
        for q in state["side_quests"]:
            if not q.get("done") and (t in q["title"] or q["title"] in t):
                if q.get("added_turn", 0) >= state["turn"]:
                    reject_msgs.append(
                        f"【系统】支线「{q['title']}」刚发布，需在后续回合才能申报完成（未发奖励）。")
                    break
                q["done"] = True
                _apply_items(state, [{"name": CURRENCY, "desc": "系统商城通用货币"}] * 15)
                _add_realm_progress(state, 8)
                done_msgs.append(f"【系统】支线完成「{q['title']}」：奖励 金币x15、等级进度+8。")
                break
        if done_msgs:
            break

    notice = str(data.get("system_notice", "")).strip()
    if broke:
        msg = (f"【系统】等级提升——当前等级：{REALMS[p['realm']]}！"
               f"主线「{state['main_quest']['title']}」进入第{state['main_quest']['stage']}阶段："
               f"{state['main_quest']['desc']}")
        if "提升" not in notice:
            notice = f"{notice} {msg}".strip()
    tail = list(done_msgs)
    tail.extend(reject_msgs)
    if invalid_breakthrough:
        tail.append("【系统】提升条件未满足：等级进度需达到100%，本次未升级。")
    if gained:
        tail.append("【系统】所得：" + "、".join(gained))
    if spent:
        tail.append("【系统】支出：" + "、".join(spent))
    if clipped:
        tail.append("【系统】所得超出单回合上限，已截断：" + "；".join(clipped))
    if short:
        tail.append("【系统】申报支出超出实有，按余额结算：" + "；".join(short))
    if gain_blocked:
        tail.append("【系统】剧情不得发放系统专属物品，已拒绝：" + "、".join(gain_blocked))
    if spend_blocked:
        tail.append("【系统】系统专属物品只能由系统扣除，已拒绝：" + "、".join(spend_blocked))
    if identity_msg:
        tail.append(identity_msg)
    if technique_msg:
        tail.append(technique_msg)
    tail.extend(power_msgs)
    tail.extend(resolved_msgs)
    tail.extend(stage_msgs)
    if progress_clip_notice:
        tail.append(progress_clip_notice)
    tail.extend(_resolve_hook(state, updates.get("hook_done")))
    if date_notice:
        tail.append(date_notice)
    elif any(k in text for k in ("约会", "邀约", "邀请")) and "邀" in text:
        # 玩家明确邀约但模型没输出 date_with：给一句可感的说明，而不是让按钮像坏了
        invited = next((n for n in state["npcs"]
                        if n["name"] in text and n.get("known_to_player")
                        and n["affinity"] >= DATE_AFFINITY_REQUIREMENT), None)
        if invited is not None:
            tail.append(f"【系统】这次对{invited['name']}的邀约没有成为正式约会——时机或氛围未到，换个场合再试试。")
    tail.extend(sync_achievements(state))
    ending_notice = _maybe_ending(state)
    if ending_notice:
        tail.append(ending_notice)
    if new_npcs:
        tail.append(f"【系统】新人物登入名册：{'、'.join(new_npcs)}")
    if reunited:
        tail.append(f"【系统】旧识重逢：{'、'.join(reunited)}（昔日好感与行事录已从档案恢复）")
    if tail:
        notice = (notice + " " if notice else "") + " ".join(tail)

    state["story"].append({
        "world": world, "text": text, "choices": choices,
        "ts": now_iso(), "turn": state["turn"], "chosen": None,
    })
    _drop_oldest(state, MAX_STORY)  # 硬上限：先归档再移出，归档失败则保留全文
    return notice


# ---------- 剧情压缩 ----------

COMPACT_RETRY_INTERVAL = 5  # 压缩失败后的重试间隔（回合），避免每回合空烧两次模型调用


def _archive_segments(state: dict, segments: list[dict]) -> bool:
    """把即将移出状态窗口的正文追加到归档文件；写不进去就不允许丢。"""
    if not segments:
        return True
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with STORY_ARCHIVE_FILE.open("a", encoding="utf-8") as f:
            for s in segments:
                f.write(json.dumps({
                    "archived_at": now_iso(),
                    "player": state["player"].get("name", ""),
                    "turn": s.get("turn"),
                    "world": s.get("world"),
                    "text": s.get("text", ""),
                    "choices": s.get("choices"),
                    "chosen": s.get("chosen"),
                }, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def _drop_oldest(state: dict, keep: int) -> bool:
    """归档后把旧剧情移出状态窗口；归档失败则保留全文，绝不静默销毁正文。"""
    if len(state["story"]) <= keep:
        return True
    if not _archive_segments(state, state["story"][:-keep]):
        return False
    state["story"] = state["story"][-keep:]
    return True


def maybe_compact(state: dict) -> str | None:
    """超过阈值时把旧剧情压成滚动摘要，返回给玩家的系统通知（无事件为 None）。

    压缩失败时保留全文并延后重试；正文只有在成功归档之后才移出状态窗口。
    """
    if len(state["story"]) <= COMPACT_THRESHOLD:
        return None
    if state["turn"] < state.get("compact_retry_at_turn", 0):
        return None

    older = state["story"][:-COMPACT_KEEP]
    if DEMO_MODE:
        state["summary"] = state["summary"] or "（演示模式：更早剧情已省略）"
        compacted = True
    else:
        texts = "\n\n".join(
            f"【第{s.get('turn', 0)}段】{s['text'][:400]}" for s in older)
        compacted = False
        try:
            data = _call_llm_json(prompts.COMPACT_SYSTEM,
                                  prompts.build_compact_user(state["summary"], texts),
                                  retries=1)
            new_summary = str(data.get("summary") or "").strip()
            if new_summary:
                state["summary"] = new_summary[:800]
                compacted = True
                # 压缩顺带萃取长期事实入账（不额外花模型调用）
                for fr in data.get("facts") or []:
                    memory.append_fact(state, fr, state["turn"])
        except EngineError:
            pass

    if not compacted:
        state["compact_retry_at_turn"] = state["turn"] + COMPACT_RETRY_INTERVAL
        return (f"【系统】剧情压缩失败，已保留全部 {len(state['story'])} 段正文，"
                f"{COMPACT_RETRY_INTERVAL} 回合后重试。")
    if not _drop_oldest(state, COMPACT_KEEP):
        state["compact_retry_at_turn"] = state["turn"] + COMPACT_RETRY_INTERVAL
        return "【系统】剧情归档写入失败，已保留全文，本次不压缩。"
    return None


# ---------- 手机短信（轻量通道：一次模型调用，不推进世界回合） ----------

def _chat_append(state: dict, npc_name: str, sender: str, text: str) -> None:
    chat = state.setdefault("chats", {}).setdefault(npc_name, {"msgs": []})
    chat.setdefault("msgs", []).append({"ts": now_iso(), "from": sender, "text": text[:300]})
    chat["msgs"] = chat["msgs"][-CHAT_HISTORY_KEPT:]


def send_chat(state: dict, npc_name: str, text: str) -> dict:
    """给已知 NPC 发微信并生成回复；失败不落档，可整条重试。"""
    npc = find_npc(state, npc_name)
    if npc is None or not npc.get("known_to_player", npc.get("last_seen_turn", -1) >= 0):
        return {"ok": False, "msg": "通讯录里还没有这个人——先在剧情里结识吧。"}
    text = str(text or "").strip()[:200]
    if not text:
        return {"ok": False, "msg": "消息内容为空。"}

    if DEMO_MODE:
        reply = demo.chat_reply(state, npc, text)
    else:
        system, user = prompts.build_chat_prompt(state, npc, text)
        try:
            data = llm.chat_json(system, user, temperature=0.9, max_tokens=400)
            reply = ChatResult.model_validate(data).reply
        except Exception as e:
            return {"ok": False, "msg": f"对方暂时没有信号（消息未发出，可重试）：{e}"}

    reply = _clean_text(reply, 300)
    if not reply:
        return {"ok": False, "msg": "对方暂时没有信号，消息未发出。"}
    _chat_append(state, npc["name"], "me", text)
    _chat_append(state, npc["name"], "npc", reply)
    # 灵犀（第4境）：每日首条短信，心意顺着言语多走了一分
    bonus = chat_affinity_bonus(state, npc["name"])
    if bonus:
        npc["affinity"] = clamp(npc["affinity"] + bonus, 0, 100)
        npc_remember(npc, state["turn"], "灵犀共鸣，心意微涨", prefix="短信：")
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
    return {"ok": True, "msg": "已送达", "reply": reply}


# ---------- 每日签到 ----------

SIGNIN_POOL = [
    {"type": "item", "name": "系统金币", "desc": "系统商城通用货币", "count": 10,
     "label": "系统金币 x10"},
    {"type": "item", "name": "系统金币", "desc": "系统商城通用货币", "count": 15,
     "label": "系统金币 x15"},
    {"type": "item", "name": "《心动笔记·残页》", "desc": "系统出品的神秘笔记残页，字迹会缓缓浮现（收藏品）",
     "count": 1, "label": "《心动笔记·残页》 x1"},
    {"type": "item", "name": "专注咖啡", "desc": "自习神器，喝完专注拉满：等级进度 +5（背包内可使用）",
     "count": 1, "label": "专注咖啡 x1"},
    {"type": "item", "name": "运动蛋白粉", "desc": "练后半小时的黄金补给：等级进度 +6（背包内可使用）",
     "count": 1, "label": "运动蛋白粉 x1"},
    {"type": "progress", "delta": 8, "label": "系统加成——等级进度 +8"},
    {"type": "progress", "delta": 5, "label": "活力清晨——等级进度 +5"},
    {"type": "item", "name": "系统抽奖券", "desc": "多一次转动命运转盘的机会", "count": 1,
     "label": "系统抽奖券 x1"},
]


def sign_in(state: dict) -> dict:
    today = game_today(state)
    if state.get("last_sign_in") == today:
        return {"ok": False, "msg": "今日已签到，明日再来。"}
    reward = dict(random.choice(SIGNIN_POOL))
    if reward["type"] == "item":
        _apply_items(state, [{"name": reward["name"], "desc": reward["desc"]}] * reward["count"])
    else:
        _add_realm_progress(state, reward["delta"])
        if state["player"]["realm_progress"] >= 100:
            if _breakthrough(state):
                reward["label"] += f"（触发提升：{REALMS[state['player']['realm']]}！）"
    state["last_sign_in"] = today
    storage.save(state, backup=False)  # 可逆小操作：事务回滚已兜底，不做全量快照
    return {"ok": True, "msg": f"签到成功：{reward['label']}"}
