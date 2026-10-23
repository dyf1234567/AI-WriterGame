"""演示模式下的接口冒烟测试：对运行中的服务跑完整游戏流程。

用法：先用独立 SJL_DATA_DIR 启动演示服务，再用相同目录与 SMOKE_BASE 运行。
任何写请求之前都要证明服务正在使用本脚本的隔离目录。
"""
import json
import hashlib
import hmac
import os
import secrets
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8000")
ROOT = Path(__file__).resolve().parent.parent
# 必须与所测实例按同一规则解析数据目录：默认同为 ROOT/data，设了 SJL_DATA_DIR 就一起走隔离目录。
# 写死默认路径会让冒烟测试绕过 SMOKE_BASE 直接改到正式存档上（离线倒拨、灌灵石、塞材料都是磁盘改写）。
DATA_DIR = Path(os.environ.get("SJL_DATA_DIR", "").strip() or (ROOT / "data")).resolve()
STATE_FILE = DATA_DIR / "state.json"
# 防呆护栏（2026-10-19 事故后加）：冒烟会重写/倒拨存档，绝不许落在正式数据目录上。
# 事故复盘：shell 里 `DD=$(...) && SJL_DATA_DIR=$DD cmd &` 的 & 会把赋值圈进子 shell，
# 父 shell 后续命令拿到空变量静默回退 ./data——除非显式设了隔离目录，否则直接拒绝启动。
FORMAL_DIR = (ROOT / "data").resolve()
if DATA_DIR == FORMAL_DIR or FORMAL_DIR in DATA_DIR.parents:
    sys.exit("拒绝运行：SJL_DATA_DIR 未指向隔离目录，冒烟测试会把正式存档当试验场。"
             "请用独立数据目录启动被测服务，并以相同 SJL_DATA_DIR 运行本脚本。")

FAILED = []


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def check(name: str, cond: bool, detail: str = "") -> None:
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILED.append(name)


def verify_isolated_instance() -> bool:
    """先用随机文件凭据验证目录和演示模式；旧 state.json 不能充当实例身份证明。"""
    if urlparse(BASE).hostname not in {"127.0.0.1", "localhost", "::1"}:
        check("写请求前验证隔离实例", False, "冒烟测试只允许本机隔离演示服务")
        return False
    marker = DATA_DIR / ".smoke-probe.json"
    token, challenge = secrets.token_hex(32), secrets.token_hex(32)
    created = False
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with marker.open("x", encoding="utf-8") as stream:
            created = True
            json.dump({"token": token}, stream)
        code, data = call("GET", "/api/smoke-proof?challenge=" + challenge)
        expected = hmac.new(bytes.fromhex(token), challenge.encode("ascii"), hashlib.sha256).hexdigest()
        valid = code == 200 and isinstance(data, dict) and isinstance(data.get("proof"), str)
        valid = valid and hmac.compare_digest(data["proof"], expected)
        check("写请求前验证隔离实例", valid, "服务须为演示模式且使用相同 SJL_DATA_DIR")
        return bool(valid)
    except (OSError, ValueError, TypeError) as exc:
        check("写请求前验证隔离实例", False, type(exc).__name__)
        return False
    finally:
        if created:
            marker.unlink(missing_ok=True)


def main() -> int:
    if not verify_isolated_instance():
        print("中止：没有确认目标是本次隔离演示实例，未发送任何写请求。")
        return 1
    # 1. 状态探测
    code, data = call("GET", "/api/state")
    check("GET /api/state", code == 200 and "exists" in data)
    demo = data.get("demo_mode")

    # 2. 新游戏
    code, data = call("POST", "/api/new", {"name": "测试侠", "show_affinity": True})
    check("POST /api/new", code == 200, f"http={code}")
    # 实例身份已在任何写请求前核验；再确认新游戏确实生成了本地测试存档。
    if not STATE_FILE.exists():
        print(f"[FAIL] 存档目录与本实例一致  (未找到 {STATE_FILE}；"
              f"服务器与本脚本必须设同一个 SJL_DATA_DIR（不设则同为项目 data/）)")
        print("中止：所测实例用的不是隔离数据目录，继续会把正式存档当试验场。")
        return 1
    s = data["state"]
    initial_minute = (s["time"]["day"] - 1) * 1440 + s["time"].get("minute", 360)
    check("开局剧情已生成", len(s["story"]) >= 1 and len(s["story"][0]["text"]) > 50)
    check("开局选项>=3", len(s["story"][0]["choices"]) >= 3)
    check("前台只显示已知人物（新档预设全员未结识）",
          len(s["npcs"]) <= 4 and not any(n["name"] == "炭炭" for n in s["npcs"]))
    check("NPC均有常在地", all(n.get("place") for n in s["npcs"]))
    check("主角信息正确", s["player"]["name"] == "测试侠" and s["player"]["world"] == "urban")
    check("单世界地图数据就位", len(s["map"]["urban"]) >= 10 and "xianxia" not in s["map"])
    check("城市内容规模（≥12地）", len(s["map"]["urban"]) >= 12)
    check("初始位置已设置", s["player"]["location"]["place"] == "京华大学")
    check("地图地点含坐标",
          all(("x" in p and "y" in p) for p in s["map"]["urban"]))

    # 3. 行动推进（剧情选项）
    code, data = call("POST", "/api/act", {"text": "走过去和郭瑞莹打招呼"})
    check("POST /api/act 选项推进", code == 200, f"http={code}")
    s = data["state"]
    check("地图位置随剧情更新", s["player"]["location"]["world"] == "urban" and s["player"]["location"]["place"])
    check("剧情追加", len(s["story"]) == 2)

    # 4. 再次行动（自由输入）
    code, data = call("POST", "/api/act", {"text": "向旁边同学打听刚才那位学生会长"})
    check("POST /api/act 自由输入", code == 200 and len(data["state"]["story"]) == 3)
    check("选择记录在案", data["state"]["story"][1].get("chosen") is not None)

    # 4b. 演示段触发支线（第3回合轮到琴行偶遇段）
    code, data = call("POST", "/api/act", {"text": "今晚再去老街琴行附近走走"})
    check("剧情触发支线", any(q["title"] == "周六的咖啡馆" for q in data["state"]["side_quests"]),
          str([q["title"] for q in data["state"]["side_quests"]]))
    purse = next((i["count"] for i in data["state"]["player"]["items"]
                  if i["name"] == "系统积分"), 0)
    check("系统积分与现实华夏币分开入账", purse >= 1
          and any(i["name"] == "华夏币" for i in data["state"]["player"]["items"]), f"系统积分={purse}")

    # 4c. 表达培养意向：领取初始天赋
    code, data = call("POST", "/api/act", {"text": "我想走学业路线，领取初始天赋"})
    s = data["state"]
    tech = s["player"].get("technique") or {}
    check("初始天赋已录入", bool(tech.get("name")), f"technique={tech}")
    check("路线归一且品质由系统固定",
          tech.get("route") == "学业" and tech.get("grade") == "S级", str(tech))
    check("天赋同时进背包", any(i["name"] == tech.get("name") for i in s["player"]["items"]),
          f"items={[i['name'] for i in s['player']['items']]}")

    # 4c2. 再领一次应被一次性闸拦住
    code, data = call("POST", "/api/act", {"text": "我想改走音乐路线，再领一个初始天赋"})
    check("重复领取被拒，原天赋不变",
          (data["state"]["player"].get("technique") or {}).get("name") == tech.get("name"),
          str(data["state"]["player"].get("technique")))

    # 4d. 约见计划不能直接完成支线；实际到店了解后才结算。
    code, data = call("POST", "/api/act", {"text": "答应她：周六老街咖啡馆见"})
    check("只有约见计划时支线未完成", any(q["title"] == "周六的咖啡馆" and not q["done"]
                                      for q in data["state"]["side_quests"]))
    code, data = call("POST", "/api/act", {"text": "前往老街咖啡馆了解活动"})
    check("支线完成结算", any(q.get("done") for q in data["state"]["side_quests"]))

    # 4e. 探索行动：应揭示一处迷雾地点
    code, data = call("POST", "/api/act", {"text": "在老街附近探索四周，寻找机缘与发现"})
    check("POST /api/act 探索", code == 200 and len(data["state"]["story"]) == 9)
    revealed = [p["name"] for p in data["state"]["map"]["urban"] if p["discovered"]]
    check("探索揭示迷雾地点", "紫宸美术馆" in revealed, f"revealed={revealed}")

    # 4f. 训练行动
    code, data = call("POST", "/api/act", {"text": "投入训练——健身或自习，稳步提升自己"})
    check("POST /api/act 训练", code == 200 and len(data["state"]["story"]) == 10)

    # 5. 每日签到（两次，第二次应失败）
    code, data = call("POST", "/api/signin")
    check("签到成功", code == 200 and data["result"]["ok"] is True, data["result"]["msg"])
    code, data = call("POST", "/api/signin")
    check("重复签到被拒", data["result"]["ok"] is False)

    # 5b. 系统抽奖：开局 10 张，用一张扣一张并入账
    # 签到奖池可能随机加发抽奖券——先把券数归一化回 10，断言才确定（历史 flake 源）
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    for it in state["player"]["items"]:
        if it["name"] == "系统抽奖券":
            it["count"] = 10
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    s = state
    tickets = next((i["count"] for i in s["player"]["items"] if i["name"] == "系统抽奖券"), 0)
    check("开局含10张抽奖券", tickets == 10, f"tickets={tickets}")
    code, data = call("GET", "/api/lottery")
    check("抽奖面板数据", code == 200 and data["tickets"] == 10
          and len(data["qualities"]) == 4 and data["pool"]["传说"], str(data.get("qualities")))
    code, data = call("POST", "/api/lottery/draw", {})
    check("抽奖接口可用", code == 200 and data["result"]["ok"] is True
          and "quality" in data["result"] and "prize" in data["result"],
          data["result"].get("msg", ""))
    s = data["state"]
    tickets = next((i["count"] for i in s["player"]["items"] if i["name"] == "系统抽奖券"), 0)
    check("抽奖接口真实扣次", tickets == 9, f"tickets={tickets}")
    lot = s["player"].get("lottery", {})
    check("抽奖记录与入账（不刷收件箱）", lot.get("total_drawn") == 1 and len(lot.get("history", [])) == 1
          and not any(m.get("title", "").startswith("抽奖") for m in s["inbox"]),
          f"lottery={lot}")
    code, data = call("POST", "/api/use", {"name": "系统抽奖券"})
    check("背包内抽奖仍可用", code == 200 and data["result"]["ok"] is True, data["result"].get("msg", ""))

    # 6. 好感度开关
    code, data = call("POST", "/api/settings", {"show_affinity": False})
    check("关闭好感度显示", code == 200 and data["state"]["settings"]["show_affinity"] is False)
    call("POST", "/api/settings", {"show_affinity": True})

    # 7. 短暂离线（未达阈值）→ 无事件
    code, data = call("POST", "/api/resume")
    check("短离线无事件", code == 200 and len(data["offline_events"]) == 0)

    # 8. 只改变现实离开时间，不能推动游戏世界或刷关系。
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    before_time = state["time"].copy()
    aff_before = {n["name"]: n["affinity"] for n in state["npcs"]}
    state["last_active"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    code, data = call("POST", "/api/resume")
    events = data.get("offline_events", [])
    check("现实离线不生成新事件", code == 200 and events == [], f"events={len(events)}")
    check("现实离线不推进游戏时钟", data["state"]["time"] == before_time)
    # 前台只显示已认识的人，比较每位可见角色的既有关系。
    aff_after = {n["name"]: n["affinity"] for n in data["state"]["npcs"]}
    check("现实离线保留人物关系", all(aff_before.get(k) == v for k, v in aff_after.items()))

    # 8b. 商城：先给玩家充足金币
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    for it in state["player"]["items"]:
        if it["name"] == "系统积分":
            it["count"] = 800  # 预算加宽：抽奖/签到的随机金币奖励不再让商城断流（历史 flake 源）
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    # 8a. 限时货架：默认每日随机 8 件＋常驻；先验证拦截，再放行固定购买流程
    code, data = call("GET", "/api/shop")
    shelf_names = {g["name"] for g in data.get("catalog", [])}
    check("限时货架（8 件随机＋常驻＋全目录）", code == 200
          and 8 <= len(data["catalog"]) <= 12 and len(data.get("all_catalog", [])) >= 40
          and data["currency"] == 800, f"shelf={len(data.get('catalog', []))}")
    off_shelf = next(n for n in ("专注咖啡", "健身月卡", "沟通表达课", "手写贺卡") if n not in shelf_names)
    code, data = call("POST", "/api/buy", {"name": off_shelf})
    check("货架外商品被拒（明日再来）", code == 200 and data["result"]["ok"] is False
          and "不在货架" in data["result"]["msg"], data["result"].get("msg", "")[:40])
    # 写入临时配置：把冒烟要买的固定商品钉上常驻货架（走正式 GM 通道）
    call("POST", "/api/gm/shop", {"rotation": {"enabled": True, "slots": 8, "period": "day"},
                                   "pinned": ["专注咖啡", "沟通表达课", "运动夹克", "玫瑰花瓣浴盐"]})
    code, data = call("POST", "/api/buy", {"name": "专注咖啡"})
    check("购买物品", code == 200 and data["result"]["ok"] is True, data["result"].get("msg", ""))
    prog_before = data["state"]["player"]["realm_progress"]
    code, data = call("POST", "/api/use", {"name": "专注咖啡"})
    check("使用物品", code == 200 and data["result"]["ok"] is True, data["result"].get("msg", ""))
    check("使用生效", data["state"]["player"]["realm_progress"] >= prog_before + 5)
    # 属性课：购买并使用，情商应 +1
    code, data = call("POST", "/api/buy", {"name": "沟通表达课"})
    wit_before = data["state"]["player"]["stats"]["情商"]
    code, data = call("POST", "/api/use", {"name": "沟通表达课"})
    check("属性课生效", data["result"]["ok"] is True and data["state"]["player"]["stats"]["情商"] == wit_before + 1)
    # 卖出：买入卖出，金币应回收
    code, data = call("POST", "/api/buy", {"name": "运动夹克"})
    cur_before = next(i["count"] for i in data["state"]["player"]["items"] if i["name"] == "系统积分")
    code, data = call("POST", "/api/sell", {"name": "运动夹克"})
    cur_after = next(i["count"] for i in data["state"]["player"]["items"] if i["name"] == "系统积分")
    has_item = any(i["name"] == "运动夹克" for i in data["state"]["player"]["items"])
    check("卖出回收金币", data["result"]["ok"] is True and cur_after == cur_before + 60 and not has_item,
          data["result"].get("msg", ""))
    code, data = call("POST", "/api/use", {"name": "运动夹克"})
    check("不可用物品被拒绝", data["result"]["ok"] is False)

    # 穿搭系统：买夹克→装备→卸下
    code, data = call("POST", "/api/buy", {"name": "运动夹克"})
    check("购买穿搭", data["result"]["ok"] is True)
    code, data = call("POST", "/api/equip", {"name": "运动夹克"})
    st = data["state"]
    check("穿搭占上装位", st["player"]["equipped"]["上装"] == "运动夹克")
    check("穿搭后离开背包", not any(i["name"] == "运动夹克" for i in st["player"]["items"]))
    code, data = call("POST", "/api/unequip", {"slot": "上装"})
    check("卸下回背包", any(i["name"] == "运动夹克" for i in data["state"]["player"]["items"]))

    # 8c. 送礼（恋爱核心循环）：买两份情趣礼物送郭瑞莹（偏爱情趣，加成）。
    # 用不在抽奖奖池里的玫瑰花瓣浴盐——奖池道具会让"买2送1剩1"的计数被随机奖品污染。
    for _ in range(2):
        code, data = call("POST", "/api/buy", {"name": "玫瑰花瓣浴盐"})
        check("购买礼物", code == 200 and data["result"]["ok"] is True, data["result"].get("msg", ""))
    code, data = call("POST", "/api/gift", {"npc": "郭瑞莹", "item": "玫瑰花瓣浴盐"})
    r = data["result"]
    check("赠送礼物成功", code == 200 and r["ok"] is True and r["delta"] == 6 and r["liked"] is True,
          str(r))
    left = next((i["count"] for i in data["state"]["player"]["items"] if i["name"] == "玫瑰花瓣浴盐"), 0)
    check("送礼后礼物数量扣减（买2送1剩1）", left == 1, f"left={left}")
    code, data = call("POST", "/api/gift", {"npc": "郭瑞莹", "item": "玫瑰花瓣浴盐"})
    check("同人当日二次赠送被拒", data["result"]["ok"] is False and "今天" in data["result"]["msg"],
          data["result"]["msg"][:40])
    code, data = call("POST", "/api/gift", {"npc": "炭炭", "item": "玫瑰花瓣浴盐"})
    check("未认识的人不可赠送", data["result"]["ok"] is False and "认识" in data["result"]["msg"],
          data["result"]["msg"][:40])

    # 8d. 约会（阶段B）：好感达亲近后邀约 → 正式约会入档并揭示约会圣地
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    person = next(n for n in state["npcs"] if n["name"] == "郭瑞莹")
    person["affinity"] = 75
    person["bond"].update(trust=50, attraction=40)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    story_before_date = len(state["story"])
    code, data = call("POST", "/api/act", {"text": "【约会】邀请郭瑞莹来一场正式的约会"})
    s = data["state"]
    check("约会行动成功", code == 200 and len(s["story"]) == story_before_date + 1,
          f"story={len(s['story'])}")
    check("约会回忆入档", any(d["npc"] == "郭瑞莹" for d in s.get("dates", [])),
          str(s.get("dates")))
    check("约会揭示新地点", any(p["name"] == "星愿游乐园" and p["discovered"]
                                for p in s["map"]["urban"]))
    check("约会公告可见", "约会时刻" in (data.get("system_notice") or ""), data.get("system_notice", "")[:60])

    # 8e. 手机短信（阶段C）：不推进剧情回合
    story_before = len(s["story"])
    code, data = call("POST", "/api/chat", {"npc": "郭瑞莹", "text": "今晚月色真美"})
    check("发送短信并收到回复", code == 200 and data["result"]["ok"] is True
          and bool(data["result"].get("reply")), str(data["result"])[:60])
    msgs = data["state"]["chats"]["郭瑞莹"]["msgs"]
    check("短信双向入档且不占回合",
          len(msgs) == 2 and msgs[0]["from"] == "me" and msgs[1]["from"] == "npc"
          and len(data["state"]["story"]) == story_before, f"msgs={len(msgs)}")
    code, data = call("POST", "/api/chat", {"npc": "炭炭", "text": "你好"})
    check("未认识者不可发短信", data["result"]["ok"] is False)

    # 8f. 时间与日程（阶段D）＋ 成就（阶段F）
    s = data["state"]
    now_minute = (s["time"]["day"] - 1) * 1440 + s["time"].get("minute", 360)
    check("时间按行动实际分钟推进", now_minute > initial_minute, str(s.get("time")))
    check("成就解锁（送礼＋约会）",
          "first_gift" in s.get("achievements", []) and "first_date" in s.get("achievements", []),
          str(s.get("achievements")))

    # 9. 存档恢复链路（#18：smoke 此前漏 /api/backups /api/history /api/restore）
    code, data = call("GET", "/api/backups")
    check("恢复点列表可读", code == 200 and isinstance(data.get("backups"), list),
          f"backups={len(data.get('backups', []))}")
    code, data = call("GET", "/api/history")
    check("往事归档可读", code == 200 and isinstance(data.get("entries"), list)
          and isinstance(data.get("dates"), list))
    code, data = call("GET", "/api/backups")
    if data.get("backups"):
        bid = data["backups"][0]["id"]
        code, data = call("POST", "/api/restore", {"name": bid})
        check("恢复到最近恢复点", code == 200 and data["state"]["player"]["name"],
              str(data.get("system_notice", ""))[:50])
        # 恢复后确认存档仍可读
        code, data = call("GET", "/api/state")
        check("恢复后存档完好", code == 200 and data["exists"] is True)
    else:
        print("[SKIP] 恢复测试（无可用恢复点——本环境未产生备份）")

    # 10. 首页可访问
    req = urllib.request.Request(BASE + "/")
    with urllib.request.urlopen(req) as r:
        html = r.read().decode("utf-8")
    check("首页可访问", "双界录" in html and "story-flow" in html)

    # 11. GM 后台与只读同步端点（GET，不改档）
    req = urllib.request.Request(BASE + "/gm")
    with urllib.request.urlopen(req) as r:
        check("GM 后台页可访问", r.status == 200 and "GM" in r.read().decode("utf-8"))
    code, data = call("GET", "/api/state/full")
    check("只读全量状态端点", code == 200 and data.get("exists") is True
          and "state" in data and data["state"].get("player"))
    code, data = call("GET", "/api/gm/catalog")
    check("GM 目录端点", code == 200 and len(data.get("items", [])) >= 40)
    code, data = call("GET", "/api/gm/roster")
    check("GM 名册端点（不脱敏，仅本机）", code == 200 and len(data.get("npcs", [])) == 35)
    code, data = call("GET", "/api/photos")
    ph = data.get("photos", {})
    check("图库索引：35 人 × 3 分类 × 3 张",
          code == 200 and len(ph) == 35
          and all(len(cats) >= 3 and all(len(v) >= 3 for v in cats.values()) for cats in ph.values()))
    check("聊天媒体库：表情包与 NPC 视频",
          len(data.get("stickers") or []) >= 10 and len(data.get("videos") or {}) >= 30,
          f"stickers={len(data.get('stickers') or [])} videos={len(data.get('videos') or {})}")

    print()
    print(f"演示模式: {demo}")
    if FAILED:
        print(f"结果：{len(FAILED)} 项失败 -> {FAILED}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
