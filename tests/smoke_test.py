"""演示模式下的接口冒烟测试：对运行中的服务跑完整游戏流程。

用法：先启动服务（uvicorn app.main:app --port 8000），再运行本脚本。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8000")
ROOT = Path(__file__).resolve().parent.parent
# 必须与所测实例按同一规则解析数据目录：默认同为 ROOT/data，设了 SJL_DATA_DIR 就一起走隔离目录。
# 写死默认路径会让冒烟测试绕过 SMOKE_BASE 直接改到正式存档上（离线倒拨、灌灵石、塞材料都是磁盘改写）。
DATA_DIR = Path(os.environ.get("SJL_DATA_DIR", "").strip() or (ROOT / "data"))
STATE_FILE = DATA_DIR / "state.json"
# 防呆护栏（2026-10-19 事故后加）：冒烟会重写/倒拨存档，绝不许落在正式数据目录上。
# 事故复盘：shell 里 `DD=$(...) && SJL_DATA_DIR=$DD cmd &` 的 & 会把赋值圈进子 shell，
# 父 shell 后续命令拿到空变量静默回退 ./data——除非显式设了隔离目录，否则直接拒绝启动。
if DATA_DIR == ROOT / "data":
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


def main() -> int:
    # 1. 状态探测
    code, data = call("GET", "/api/state")
    check("GET /api/state", code == 200 and "exists" in data)
    demo = data.get("demo_mode")

    # 2. 新游戏
    code, data = call("POST", "/api/new", {"name": "测试侠", "show_affinity": True})
    check("POST /api/new", code == 200, f"http={code}")
    # 后面的离线倒拨/灌灵石/补材料三步是直接改磁盘，必须先确认本脚本与所测实例看的是同一个目录
    check("存档目录与本实例一致", STATE_FILE.exists(),
          f"未找到 {STATE_FILE}；服务器与本脚本必须设同一个 SJL_DATA_DIR（不设则同为项目 data/）")
    s = data["state"]
    check("开局剧情已生成", len(s["story"]) >= 1 and len(s["story"][0]["text"]) > 50)
    check("开局选项>=3", len(s["story"][0]["choices"]) >= 3)
    check("前台只显示已知人物", len(s["npcs"]) >= 5 and not any(n["name"] == "沈曼" for n in s["npcs"]))
    check("NPC均有常在地", all(n.get("place") for n in s["npcs"]))
    check("主角信息正确", s["player"]["name"] == "测试侠" and s["player"]["world"] == "urban")
    check("单世界地图数据就位", len(s["map"]["urban"]) >= 10 and "xianxia" not in s["map"])
    check("城市内容规模（≥12地）", len(s["map"]["urban"]) >= 12)
    check("初始位置已设置", s["player"]["location"]["place"] == "京华大学")
    check("地图地点含坐标",
          all(("x" in p and "y" in p) for p in s["map"]["urban"]))

    # 3. 行动推进（剧情选项）
    code, data = call("POST", "/api/act", {"text": "走过去和苏晚晴打招呼"})
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
                  if i["name"] == "系统金币"), 0)
    check("剧情所得如实入账", purse >= 1, f"金币={purse}")

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

    # 4d. 支线完成
    code, data = call("POST", "/api/act", {"text": "答应她：周六老街咖啡馆见"})
    check("支线完成结算", any(q.get("done") for q in data["state"]["side_quests"]))

    # 4e. 探索行动：应揭示一处迷雾地点
    code, data = call("POST", "/api/act", {"text": "在老街附近探索四周，寻找机缘与发现"})
    check("POST /api/act 探索", code == 200 and len(data["state"]["story"]) == 8)
    revealed = [p["name"] for p in data["state"]["map"]["urban"] if p["discovered"]]
    check("探索揭示迷雾地点", "紫宸美术馆" in revealed, f"revealed={revealed}")

    # 4f. 训练行动
    code, data = call("POST", "/api/act", {"text": "投入训练——健身或自习，稳步提升自己"})
    check("POST /api/act 训练", code == 200 and len(data["state"]["story"]) == 9)

    # 5. 每日签到（两次，第二次应失败）
    code, data = call("POST", "/api/signin")
    check("签到成功", code == 200 and data["result"]["ok"] is True, data["result"]["msg"])
    code, data = call("POST", "/api/signin")
    check("重复签到被拒", data["result"]["ok"] is False)

    # 5b. 系统抽奖：开局 10 张，用一张扣一张并入账
    s = data["state"]
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
    check("抽奖记录与入账", lot.get("total_drawn") == 1 and len(lot.get("history", [])) == 1
          and any(m.get("title", "").startswith("抽奖") for m in s["inbox"]),
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

    # 8. 篡改存档时间模拟离开2天 → 离线演化
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    aff_before = {n["name"]: n["affinity"] for n in state["npcs"]}
    state["last_active"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    code, data = call("POST", "/api/resume")
    events = data.get("offline_events", [])
    check("离线演化触发", code == 200 and len(events) >= 3, f"events={len(events)}")
    check("收件箱入账", len(data["state"]["inbox"]) >= 3)
    # 好感断言按名字取人（不依赖 NPC 列表顺序），对比离线前后快照
    aff_after = {n["name"]: n["affinity"] for n in data["state"]["npcs"]}
    if demo:
        rui = aff_after.get("陈芮")
        check("陈芮离线好感变化", rui is not None and rui != aff_before.get("陈芮"),
              f"陈芮 {aff_before.get('陈芮')} -> {rui}")
    else:
        changed = [k for k, v in aff_after.items() if aff_before.get(k) != v]
        if changed:
            check("离线好感变化（按名落位）", all(k in aff_before for k in changed), f"changed={changed}")
        else:
            print("[SKIP] 离线好感变化（真实模型本次未给出好感变化，属合法输出）")

    # 8b. 商城：先给玩家充足金币
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    for it in state["player"]["items"]:
        if it["name"] == "系统金币":
            it["count"] = 500
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    code, data = call("GET", "/api/shop")
    check("商城目录（≥18件）", code == 200 and len(data["catalog"]) >= 18 and data["currency"] == 500)
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
    cur_before = next(i["count"] for i in data["state"]["player"]["items"] if i["name"] == "系统金币")
    code, data = call("POST", "/api/sell", {"name": "运动夹克"})
    cur_after = next(i["count"] for i in data["state"]["player"]["items"] if i["name"] == "系统金币")
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

    # 手作工坊：直改存档补材料后合成
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    state["player"]["items"] += [{"name": "手冲咖啡豆", "desc": "x", "count": 3},
                                 {"name": "永生花材", "desc": "x", "count": 3}]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    code, data = call("GET", "/api/alchemy")
    check("手作配方就位", code == 200 and len(data["recipes"]) >= 5)
    code, data = call("POST", "/api/craft", {"name": "烘焙曲奇礼盒"})
    check("手作成品", data["result"]["ok"] is True, data["result"].get("msg", ""))

    # 8c. 送礼（恋爱核心循环）：买两份手作礼物送苏晚晴（偏爱手作，加成）
    for _ in range(2):
        code, data = call("POST", "/api/buy", {"name": "永生花束"})
        check("购买礼物", code == 200 and data["result"]["ok"] is True, data["result"].get("msg", ""))
    code, data = call("POST", "/api/gift", {"npc": "苏晚晴", "item": "永生花束"})
    r = data["result"]
    check("赠送礼物成功", code == 200 and r["ok"] is True and r["delta"] == 6 and r["liked"] is True,
          str(r))
    left = next((i["count"] for i in data["state"]["player"]["items"] if i["name"] == "永生花束"), 0)
    check("送礼后礼物数量扣减（买2送1剩1）", left == 1, f"left={left}")
    code, data = call("POST", "/api/gift", {"npc": "苏晚晴", "item": "永生花束"})
    check("同人当日二次赠送被拒", data["result"]["ok"] is False and "今天" in data["result"]["msg"],
          data["result"]["msg"][:40])
    code, data = call("POST", "/api/gift", {"npc": "沈曼", "item": "永生花束"})
    check("未认识的人不可赠送", data["result"]["ok"] is False and "认识" in data["result"]["msg"],
          data["result"]["msg"][:40])

    # 8d. 约会（阶段B）：好感达亲近后邀约 → 正式约会入档并揭示约会圣地
    code, data = call("POST", "/api/act", {"text": "【约会】邀请苏晚晴来一场正式的约会"})
    s = data["state"]
    check("约会行动成功", code == 200 and len(s["story"]) == 10, f"story={len(s['story'])}")
    check("约会回忆入档", any(d["npc"] == "苏晚晴" for d in s.get("dates", [])),
          str(s.get("dates")))
    check("约会揭示新地点", any(p["name"] == "星愿游乐园" and p["discovered"]
                                for p in s["map"]["urban"]))
    check("约会公告可见", "约会时刻" in (data.get("system_notice") or ""), data.get("system_notice", "")[:60])

    # 8e. 手机短信（阶段C）：不推进剧情回合
    story_before = len(s["story"])
    code, data = call("POST", "/api/chat", {"npc": "苏晚晴", "text": "今晚月色真美"})
    check("发送短信并收到回复", code == 200 and data["result"]["ok"] is True
          and bool(data["result"].get("reply")), str(data["result"])[:60])
    msgs = data["state"]["chats"]["苏晚晴"]["msgs"]
    check("短信双向入档且不占回合",
          len(msgs) == 2 and msgs[0]["from"] == "me" and msgs[1]["from"] == "npc"
          and len(data["state"]["story"]) == story_before, f"msgs={len(msgs)}")
    code, data = call("POST", "/api/chat", {"npc": "沈曼", "text": "你好"})
    check("未认识者不可发短信", data["result"]["ok"] is False)

    # 8f. 时间与日程（阶段D）＋ 成就（阶段F）
    s = data["state"]
    check("时间随行动推进并跨日", s.get("time", {}).get("day", 1) >= 2, str(s.get("time")))
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

    print()
    print(f"演示模式: {demo}")
    if FAILED:
        print(f"结果：{len(FAILED)} 项失败 -> {FAILED}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
