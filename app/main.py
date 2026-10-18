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


def mutation(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        try:
            with storage.transaction(), llm.request_budget():
                expected = _expected_revision.get()
                if expected is not None:
                    try:
                        current = storage.load()
                    except OSError:
                        if fn.__name__ != "api_restore":
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
        except OSError as e:
            raise HTTPException(503, "存档读写失败，原进度已保留，请检查磁盘后重试。") from e
    return run


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
        "recipes": shop.RECIPES,
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


@app.get("/api/alchemy")
def api_alchemy():
    state = storage.load() or {"player": {"items": []}}
    return shop.alchemy_view(state)


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


@app.post("/api/craft")
@mutation
def api_craft(req: NameReq):
    state = _load_or_404()
    result = shop.craft(state, req.name.strip())
    return {"demo_mode": DEMO_MODE, "result": result, "state": state}


@app.get("/api/history")
def api_history():
    """当前周目已归档正文，按回合读取；不返回主持人秘密。附约会回合标记。"""
    from .config import STORY_ARCHIVE_FILE
    entries = []
    if STORY_ARCHIVE_FILE.exists():
        for line in STORY_ARCHIVE_FILE.read_text(encoding="utf-8").splitlines():
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
@mutation
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
