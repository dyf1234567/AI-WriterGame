"""FastAPI 接口层与静态页面服务。"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from functools import wraps
from contextvars import ContextVar
import json

from . import engine, offline, shop, storage, llm
from .models import public_state
from .config import DEMO_MODE, STATIC_DIR

app = FastAPI(title="双界录")
_expected_revision = ContextVar("expected_revision", default=None)


@app.middleware("http")
async def version_header(request: Request, call_next):
    token = _expected_revision.set(request.headers.get("X-State-Revision"))
    try:
        return await call_next(request)
    finally:
        _expected_revision.reset(token)


def mutation(fn=None, *, allow_missing_state: bool = False):
    """写操作装饰器。allow_missing_state=True 用于恢复类接口——
    当前存档损坏正是要恢复的场景，不该被乐观锁预检拦下。"""
    if fn is None:                       # 带参用法 @mutation(allow_missing_state=True)
        def deco(f):
            return mutation(f, allow_missing_state=allow_missing_state)
        return deco
    if callable(fn) and not isinstance(fn, bool):   # 裸用法 @mutation
        allow = getattr(fn, "_allow_missing_state", allow_missing_state)
        fn._allow_missing_state = allow  # 属性标注，重命名安全
        @wraps(fn)
        def run(*args, **kwargs):
            try:
                with storage.transaction(), llm.request_budget():
                    expected = _expected_revision.get()
                    if expected is not None:
                        try:
                            current = storage.load()
                        except OSError:
                            if not allow:
                                raise
                            current = None
                        if current is not None and str(current.get("revision", 0)) != expected:
                            raise HTTPException(409, "存档已被另一操作更新，请刷新读取最新进度后重试。")
                    result = fn(*args, **kwargs)
                    if isinstance(result, dict) and "state" in result:
                        result["state"] = public_state(result["state"])
                    return result
            except storage.StorageBusy as e:
                raise HTTPException(409, str(e)) from e
            except storage.RollbackFailed as e:
                raise HTTPException(
                    503, "存档写入中断且回滚失败，进度可能不一致——请从「恢复存档」选择较早的恢复点还原。") from e
            except OSError as e:
                raise HTTPException(503, "存档读写失败，原进度已保留，请检查磁盘后重试。") from e
        return run
    raise TypeError("mutation 用法：@mutation 或 @mutation(allow_missing_state=True)")


class NewReq(BaseModel):
    name: str = "林川"
    show_affinity: bool = True


class ActReq(BaseModel):
    text: str = Field(max_length=1000)


class SettingsReq(BaseModel):
    show_affinity: bool


class NameReq(BaseModel):
    name: str


class GiftReq(BaseModel):
    npc: str
    item: str


class ChatReq(BaseModel):
    npc: str
    text: str = Field(max_length=300)


class GmGrantReq(BaseModel):
    gold: int = Field(default=0, ge=-999999, le=999999)
    item: str = Field(default="", max_length=40)
    item_count: int = Field(default=1, ge=1, le=999)
    stat: str = Field(default="", max_length=10)
    stat_value: int = Field(default=0, ge=-99, le=99)
    progress: int = Field(default=0, ge=-100, le=100)
    power: int = Field(default=0, ge=0, le=999)
    ticket: int = Field(default=0, ge=0, le=999)


class GmNpcReq(BaseModel):
    npc: str
    persona: str = Field(min_length=2, max_length=200)
    role: str = Field(default="", max_length=30)
    likes: str = Field(default="", max_length=10)


class SlotReq(BaseModel):
    slot: str


def _load_or_404() -> dict:
    state = storage.load()
    if state is None:
        raise HTTPException(status_code=404, detail="尚无存档，请先开始新游戏")
    return state


@app.post("/api/new")
@mutation
def api_new(req: NewReq):
    name = (req.name or "").strip()[:12] or "林川"
    try:
        state = engine.start_game(name, req.show_affinity)
    except engine.EngineError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"demo_mode": DEMO_MODE, "state": state}


@app.get("/api/state")
def api_state():
    try:
        state = storage.load()
    except OSError as e:
        raise HTTPException(503, "存档无法读取，请使用“恢复存档”选择之前的备份。") from e
    return {"exists": state is not None, "demo_mode": DEMO_MODE}


@app.get("/api/state/full")
def api_state_full():
    """只读拉取最新玩家档案（乐观锁 409 后前端自愈用）：不跑离线结算、不加 revision。"""
    try:
        state = storage.load()
    except OSError as e:
        raise HTTPException(503, "存档无法读取，请使用“恢复存档”选择之前的备份。") from e
    if state is None:
        return {"exists": False}
    return {"exists": True, "state": public_state(state)}


@app.post("/api/resume")
@mutation
def api_resume():
    state = _load_or_404()
    try:
        new_items = offline.check_offline(state)
    except offline.OfflineError:
        new_items = []  # 结算失败不阻塞继续游戏
        return {"demo_mode": DEMO_MODE, "state": state, "offline_events": [],
                "system_notice": "离线动态暂未生成，已保留待结算时长，下次回来时重试。"}
    return {"demo_mode": DEMO_MODE, "state": state, "offline_events": new_items}


@app.post("/api/act")
@mutation
def api_act(req: ActReq):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="行动内容为空")
    state = _load_or_404()
    try:
        state, notice = engine.take_turn(state, text)
    except engine.EngineError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"demo_mode": DEMO_MODE, "state": state, "system_notice": notice}


@app.post("/api/signin")
@mutation
def api_signin():
    state = _load_or_404()
    result = engine.sign_in(state)
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.post("/api/settings")
@mutation
def api_settings(req: SettingsReq):
    state = _load_or_404()
    state["settings"]["show_affinity"] = bool(req.show_affinity)
    storage.save(state)
    return {"demo_mode": DEMO_MODE, "state": state}


@app.get("/api/shop")
def api_shop():
    state = storage.load()
    return {
        "catalog": shop.SHOP_CATALOG,
        "currency_name": shop.CURRENCY,
        "currency": shop.currency_count(state) if state else 0,
    }


@app.post("/api/buy")
@mutation
def api_buy(req: NameReq):
    state = _load_or_404()
    result = shop.buy(state, req.name.strip())
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.post("/api/use")
@mutation
def api_use(req: NameReq):
    state = _load_or_404()
    result = shop.use_item(state, req.name.strip())
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.post("/api/sell")
@mutation
def api_sell(req: NameReq):
    state = _load_or_404()
    result = shop.sell(state, req.name.strip())
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.post("/api/equip")
@mutation
def api_equip(req: NameReq):
    state = _load_or_404()
    result = shop.equip(state, req.name.strip())
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.post("/api/unequip")
@mutation
def api_unequip(req: SlotReq):
    state = _load_or_404()
    result = shop.unequip(state, req.slot.strip())
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.get("/api/lottery")
def api_lottery():
    state = storage.load() or {"player": {"items": []}}
    return shop.lottery_view(state)


@app.post("/api/lottery/draw")
@mutation
def api_lottery_draw():
    state = _load_or_404()
    result = shop.draw_lottery(state)
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.post("/api/gift")
@mutation
def api_gift(req: GiftReq):
    state = _load_or_404()
    result = shop.give_gift(state, req.npc.strip(), req.item.strip())
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.post("/api/chat")
@mutation
def api_chat(req: ChatReq):
    """手机短信：轻量通道，不推进世界回合。"""
    state = _load_or_404()
    result = engine.send_chat(state, req.npc.strip(), req.text)
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.get("/gm")
def gm_console():
    """GM 后台（DM 工具页）：查看与改写角色档案。仅限本机使用。"""
    return FileResponse(STATIC_DIR / "gm.html")


@app.post("/api/gm/npc")
@mutation
def api_gm_npc(req: GmNpcReq):
    """GM 后台改写角色档案：性格（必填）＋身份/礼物偏好（可选）。"""
    state = _load_or_404()
    result = engine.set_persona(state, req.npc.strip(), req.persona.strip())
    if result.get("ok"):
        npc = engine.find_npc(state, req.npc.strip())
        if req.role.strip():
            npc["role"] = engine._clean_text(req.role.strip(), 30)
        if req.likes.strip():
            npc["likes"] = engine._clean_text(req.likes.strip(), 10)
        storage.save(state, backup=False)
        return {"demo_mode": DEMO_MODE, "result": {**result, "npc": {
            "name": npc["name"], "role": npc["role"], "likes": npc.get("likes", ""),
            "persona": npc["persona"]}}, "state": state}
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.post("/api/gm/grant")
@mutation
def api_gm_grant(req: GmGrantReq):
    """管理员发放：金币/道具/属性/等级进度/修为/抽奖券，绕过玩家侧护栏，收件箱留痕。"""
    state = _load_or_404()
    result = engine.gm_grant(state, gold=req.gold, item=req.item.strip(),
                             item_count=req.item_count, stat=req.stat.strip(),
                             stat_value=req.stat_value, progress=req.progress,
                             power=req.power, ticket=req.ticket)
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.get("/api/gm/catalog")
def api_gm_catalog():
    """GM 发放下拉的道具清单（在售商品名＋货币）。"""
    from .shop import CATALOG_BY_NAME
    return {"items": sorted(CATALOG_BY_NAME)}


@app.get("/api/gm/roster")
def api_gm_roster():
    """GM 后台名册：全量真档案（含未登场者与后台秘密），不脱敏。"""
    state = storage.load()
    if state is None:
        return {"npcs": [], "exists": False}
    return {"exists": True, "npcs": [{
        "name": n["name"], "role": n["role"], "persona": n.get("persona", ""),
        "likes": n.get("likes", ""), "affinity": n["affinity"],
        "known": n.get("known_to_player", False), "place": n.get("place", ""),
    } for n in state["npcs"]]}


@app.get("/api/history")
def api_history():
    """当前周目已归档正文，按回合读取；不返回主持人秘密。附约会回合标记。"""
    from collections import deque
    from .config import STORY_ARCHIVE_FILE
    entries = []
    if STORY_ARCHIVE_FILE.exists():
        # 有界流式读取：长局归档数 MB，read_text 全量入内存会卡顿且峰值翻倍
        with STORY_ARCHIVE_FILE.open("r", encoding="utf-8") as f:
            tail = deque(f, maxlen=600)
        for line in tail:
            try:
                rec = json.loads(line)
                entries.append({k: rec.get(k) for k in ("turn", "world", "text", "chosen")})
            except (ValueError, AttributeError):
                continue
    state = storage.load()
    dates = [{"turn": d.get("turn"), "npc": d.get("npc"), "place": d.get("place")}
             for d in (state.get("dates", []) if state else [])]
    return {"entries": entries, "dates": dates}


@app.get("/api/backups")
def api_backups():
    return {"backups": storage.backups()}


@app.post("/api/restore")
@mutation(allow_missing_state=True)
def api_restore(req: NameReq):
    try:
        state = storage.restore(req.name)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, "备份不存在或无法读取，请重新选择。") from e
    return {"demo_mode": DEMO_MODE, "state": state,
            "system_notice": "已恢复所选进度；恢复前的进度也已保留为备份。"}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
