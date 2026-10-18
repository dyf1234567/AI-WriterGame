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
    check("前台只显示已知人物", len(s["npcs"]) >= 5 and not any(n["name"] == "玄阳子" for n in s["npcs"]))
    check("NPC均有常在地", all(n.get("place") for n in s["npcs"]))
    check("主角信息正确", s["player"]["name"] == "测试侠" and s["player"]["world"] == "urban")
    check("地图数据就位", len(s["map"]["urban"]) >= 3 and len(s["map"]["xianxia"]) >= 3)
    check("世界内容规模（两界各≥8地）",
          len(s["map"]["urban"]) >= 8 and len(s["map"]["xianxia"]) >= 8)
    check("初始位置已设置", s["player"]["location"]["place"] == "青临市")
    check("地图地点含坐标",
          all(("x" in p and "y" in p) for w in ("urban", "xianxia") for p in s["map"][w]))

    # 3. 行动推进（穿越）
    code, data = call("POST", "/api/act", {"text": "立即穿越，去修仙界看看"})
    check("POST /api/act 穿越", code == 200, f"http={code}")
    s = data["state"]
    check("穿越后世界切换", s["player"]["world"] == "xianxia")
    check("地图位置随剧情更新", s["player"]["location"]["world"] == "xianxia" and s["player"]["location"]["place"])
    check("剧情追加", len(s["story"]) == 2)
    if demo:
        check("穿越落点为荒野（白手起家）",
              s["player"]["location"]["place"] == "落星荒野",
              f"place={s['player']['location']['place']}")
        check("荒野开局无宗门身份", s["player"]["identity"]["xianxia"] == "",
              str(s["player"].get("identity")))

    # 4. 再次行动（自由输入）
    code, data = call("POST", "/api/act", {"text": "打听最近的聚居地，准备启程"})
    check("POST /api/act 自由输入", code == 200 and len(data["state"]["story"]) == 3)
    check("选择记录在案", data["state"]["story"][1].get("chosen") is not None)
    if demo:
        check("剧情新人物登入名册",
              any(n["name"] == "黑袍人" for n in data["state"]["npcs"]),
              f"npcs={[n['name'] for n in data['state']['npcs']]}")
        purse = next((i["count"] for i in data["state"]["player"]["items"]
                      if i["name"] == "下品灵石"), 0)
        check("剧情支出如实扣账", purse == 1, f"灵石={purse}")
        check("剧情所得如实入账",
              any(i["name"] == "白溪镇舆图" for i in data["state"]["player"]["items"]))
        check("剧情揭示新地点", any(p["name"] == "白溪镇" and p["discovered"]
                                    for p in data["state"]["map"]["xianxia"]))
        check("伏笔进事实账本", any("两界之钥" in f.get("text", "")
                                    for f in data["state"].get("facts", [])),
              str(data["state"].get("facts")))

    # 4b. 探索行动：应揭示一处迷雾地点
    code, data = call("POST", "/api/act", {"text": "在荒野中探索四周，寻找机缘与发现"})
    check("POST /api/act 探索", code == 200 and len(data["state"]["story"]) == 4)
    revealed = [p["name"] for p in data["state"]["map"]["xianxia"] if p["discovered"]]
    check("探索揭示迷雾地点", "灵草溪谷" in revealed, f"revealed={revealed}")

    # 4c. 修炼行动
    code, data = call("POST", "/api/act", {"text": "打坐修炼，运转功法，稳固境界"})
    check("POST /api/act 修炼", code == 200 and len(data["state"]["story"]) == 5)

    # 4c2. 表达修炼意向：领取初始功法（设定集 V1.2 · 4.1）
    code, data = call("POST", "/api/act", {"text": "我想走剑修路线，领取初始功法"})
    s = data["state"]
    tech = s["player"].get("technique") or {}
    check("初始功法已录入", bool(tech.get("name")), f"technique={tech}")
    check("路线归一且品质由系统固定",
          tech.get("route") == "剑修" and tech.get("grade") == "上品", str(tech))
    check("功法同时进背包", any(i["name"] == tech.get("name") for i in s["player"]["items"]),
          f"items={[i['name'] for i in s['player']['items']]}")

    # 4c3. 再领一次应被一次性闸拦住
    code, data = call("POST", "/api/act", {"text": "我想改走魔修路线，再领一部初始功法"})
    check("重复领取被拒，原功法不变",
          (data["state"]["player"].get("technique") or {}).get("name") == tech.get("name"),
          str(data["state"]["player"].get("technique")))

    # 4d. 支线触发与完成（演示）
    code, data = call("POST", "/api/act", {"text": "穿越回都市看看"})
    check("返回都市触发支线", any(q["title"] == "天台之约" for q in data["state"]["side_quests"]))
    code, data = call("POST", "/api/act", {"text": "放学后天台赴约，见苏晚晴"})
    check("支线完成结算", any(q.get("done") for q in data["state"]["side_quests"]))

    # 5. 每日签到（两次，第二次应失败）
    code, data = call("POST", "/api/signin")
    check("签到成功", code == 200 and data["result"]["ok"] is True, data["result"]["msg"])
    code, data = call("POST", "/api/signin")
    check("重复签到被拒", data["result"]["ok"] is False)

    # 5b. 系统抽奖（设定集 V1.2 · 五）：开局 10 张，用一张扣一张并入账
    s = data["state"]
    tickets = next((i["count"] for i in s["player"]["items"] if i["name"] == "系统抽奖券"), 0)
    check("开局含10张抽奖券", tickets == 10, f"tickets={tickets}")
    code, data = call("POST", "/api/use", {"name": "系统抽奖券"})
    check("抽奖可用", code == 200 and data["result"]["ok"] is True, data["result"].get("msg", ""))
    s = data["state"]
    tickets = next((i["count"] for i in s["player"]["items"] if i["name"] == "系统抽奖券"), 0)
    check("抽奖真实扣次", tickets == 9, f"tickets={tickets}")
    lot = s["player"].get("lottery", {})
    check("抽奖记录与入账", lot.get("total_drawn") == 1 and len(lot.get("history", [])) == 1
          and any(m.get("title", "").startswith("抽奖") for m in s["inbox"]),
          f"lottery={lot}")

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
        rui = aff_after.get("陈锐")
        check("陈锐离线好感变化", rui is not None and rui != aff_before.get("陈锐"),
              f"陈锐 {aff_before.get('陈锐')} -> {rui}")
    else:
        changed = [k for k, v in aff_after.items() if aff_before.get(k) != v]
        if changed:
            check("离线好感变化（按名落位）", all(k in aff_before for k in changed), f"changed={changed}")
        else:
            print("[SKIP] 离线好感变化（真实模型本次未给出好感变化，属合法输出）")

    # 8b. 商城：先给玩家充足灵石
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    for it in state["player"]["items"]:
        if it["name"] == "下品灵石":
            it["count"] = 500
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    code, data = call("GET", "/api/shop")
    check("商城目录（≥18件）", code == 200 and len(data["catalog"]) >= 18 and data["currency"] == 500)
    code, data = call("POST", "/api/buy", {"name": "聚气丹"})
    check("购买物品", code == 200 and data["result"]["ok"] is True, data["result"].get("msg", ""))
    prog_before = data["state"]["player"]["realm_progress"]
    code, data = call("POST", "/api/use", {"name": "聚气丹"})
    check("使用物品", code == 200 and data["result"]["ok"] is True, data["result"].get("msg", ""))
    check("使用生效", data["state"]["player"]["realm_progress"] >= prog_before)
    # 属性丹：购买并使用，悟性应 +1
    code, data = call("POST", "/api/buy", {"name": "悟道茶"})
    wit_before = data["state"]["player"]["stats"]["悟性"]
    code, data = call("POST", "/api/use", {"name": "悟道茶"})
    check("属性丹生效", data["result"]["ok"] is True and data["state"]["player"]["stats"]["悟性"] == wit_before + 1)
    # 卖出：买入卖出，灵石应回收
    code, data = call("POST", "/api/buy", {"name": "玄铁短剑"})
    cur_before = next(i["count"] for i in data["state"]["player"]["items"] if i["name"] == "下品灵石")
    code, data = call("POST", "/api/sell", {"name": "玄铁短剑"})
    cur_after = next(i["count"] for i in data["state"]["player"]["items"] if i["name"] == "下品灵石")
    has_sword = any(i["name"] == "玄铁短剑" for i in data["state"]["player"]["items"])
    check("卖出回收灵石", data["result"]["ok"] is True and cur_after == cur_before + 60 and not has_sword,
          data["result"].get("msg", ""))
    code, data = call("POST", "/api/use", {"name": "玄铁短剑"})
    check("不可用物品被拒绝", data["result"]["ok"] is False)

    # 装备系统：买剑→装备→卸下
    code, data = call("POST", "/api/buy", {"name": "玄铁短剑"})
    check("购买装备", data["result"]["ok"] is True)
    code, data = call("POST", "/api/equip", {"name": "玄铁短剑"})
    st = data["state"]
    check("装备占武器位", st["player"]["equipped"]["武器"] == "玄铁短剑")
    check("装备后离开背包", not any(i["name"] == "玄铁短剑" for i in st["player"]["items"]))
    code, data = call("POST", "/api/unequip", {"slot": "武器"})
    check("卸下回背包", any(i["name"] == "玄铁短剑" for i in data["state"]["player"]["items"]))

    # 炼丹：直改存档补材料后合成
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    state["player"]["items"] += [{"name": "千年灵芝", "desc": "x", "count": 3},
                                 {"name": "一阶妖丹", "desc": "x", "count": 3}]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    code, data = call("GET", "/api/alchemy")
    check("炼丹配方就位", code == 200 and len(data["recipes"]) >= 5)
    code, data = call("POST", "/api/craft", {"name": "凝元丹"})
    check("炼丹成丹", data["result"]["ok"] is True, data["result"].get("msg", ""))

    # 9. 首页可访问
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
