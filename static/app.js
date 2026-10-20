/* 双界录 前端逻辑：三栏分格 + 阅读式剧情流 + 地图系统 + 点击式风格切换 */
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const REALMS = ["无名路人", "初露锋芒", "校园新星", "崭露头角", "风云人物", "校园传奇",
  "城市新锐", "万众瞩目", "众星捧月", "城市传奇", "人生赢家"];
const WORLD_NAMES = { urban: "都市" };
const THEME_NAMES = { night: "深夜", ink: "墨纸", parchment: "羊皮卷", qinglan: "青岚" };
const PLACE_TYPES = { campus: "校园", city: "城区", leisure: "休闲", nature: "郊野", culture: "人文", transport: "交通", secret: "秘境" };

let S = null;            // 服务端状态镜像
let busy = false;        // 回合进行中
let DEMO = false;        // 演示模式：自由输入为示例剧情，预期要管理
let typingTimer = null;  // 打字机定时器
let SHOP = null;         // 商城目录缓存
let CATALOG_META = null; // 目录元信息（货币名等），货币改名不至于让界面静默归零
let pendingRequest = false;
let catalogError = "";
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const EQUIP_SLOTS = ["上装", "鞋履", "配饰", "座驾"];
const GIFT_CATS = ["约会", "情趣", "特殊"];
const TIME_SLOTS = ["清晨", "上午", "下午", "傍晚", "夜晚"];
const STAT_TIPS = {
  体魄: "运动与体力的底气：兼职体力活、运动线剧情的主持人参考项；约会相处时高体魄最多 +1 熨帖",
  头脑: "学业与分析的根基：考试、竞赛与研究类剧情的主持人参考项",
  情商: "会说话的艺术：正式约会的相处好感真实加成（≥60 时 +1）",
  魅力: "仪表与气场：正式约会的第一印象真实加成（≥60 时 +1）",
};
const statTip = (k) => esc(STAT_TIPS[k] || "属性会随课程与穿搭成长，影响对应剧情走向");
const AFFINITY_STAGES = [[0, "初识"], [25, "熟识"], [50, "朋友"], [70, "亲近"], [85, "心动"], [100, "羁绊"]];

/* 好感数值 → 阶段标签与序号（和后端 models.affinity_stage 同口径） */
function npcStage(affinity) {
  let idx = 0;
  AFFINITY_STAGES.forEach(([t], i) => { if (affinity >= t) idx = i; });
  return { idx, label: AFFINITY_STAGES[idx][1] };
}

/* 属性加成（基础 + 装备） */
function statBonus() {
  const bonus = {};
  const eq = (S && S.player.equipped) || {};
  Object.values(eq).forEach((name) => {
    const g = (SHOP || []).find((x) => x.name === name);
    const st = g && g.equip && g.equip.stats;
    if (st) Object.entries(st).forEach(([k, v]) => (bonus[k] = (bonus[k] || 0) + v));
  });
  return bonus;
}


/* ==================== 内置图片库：NPC 专属自拍 ==================== */
/* 每个 NPC 一套独属配置（场景底色+符号+发色+衣色），同库不同图；
   纯 SVG 程序化生成，data-uri 直出，离线可用。 */

const PHOTO_SCENES = {
  琴房:   { bg: ["#2b2440", "#584a7e"], syms: ["note", "note", "window"] },
  教室:   { bg: ["#243447", "#4a6d8c"], syms: ["book", "board"] },
  办公室: { bg: ["#31343d", "#5b6270"], syms: ["doc", "cup"] },
  图书馆: { bg: ["#26303a", "#4d5e6e"], syms: ["book", "shelf", "lamp"] },
  操场:   { bg: ["#1f3d2e", "#4a7d5c"], syms: ["track", "sun"] },
  奶茶店: { bg: ["#43293a", "#8c5a74"], syms: ["cup", "cup", "heart"] },
  深夜房: { bg: ["#141826", "#2c3654"], syms: ["moon", "star", "headset"] },
  练舞室: { bg: ["#3a2030", "#7a4460"], syms: ["mirror", "note"] },
  漫展:   { bg: ["#33203e", "#6e4483"], syms: ["star", "heart", "spark"] },
  电竞馆: { bg: ["#10202e", "#1f4d63"], syms: ["monitor", "spark"] },
  解说台: { bg: ["#1d2740", "#3f5b91"], syms: ["mic", "monitor"] },
  livehouse: { bg: ["#1c1524", "#4a3060"], syms: ["note", "spot"] },
  片场:   { bg: ["#2e2a20", "#6b5e3f"], syms: ["clap", "spot"] },
  外滩:   { bg: ["#16233e", "#3d5a8a"], syms: ["bridge", "star"] },
  美术馆: { bg: ["#2c2c34", "#5c5c6e"], syms: ["frame", "frame"] },
  游乐园: { bg: ["#37243f", "#7c4a8a"], syms: ["ferris", "balloon"] },
  商街:   { bg: ["#24303f", "#557095"], syms: ["shop", "lamp"] },
  天文台: { bg: ["#0f1830", "#26355e"], syms: ["star", "star", "scope"] },
  音乐厅: { bg: ["#2a1c30", "#5f3f6e"], syms: ["note", "spot", "note"] },
  录音棚: { bg: ["#1e2430", "#43536b"], syms: ["mic", "wave"] },
  音乐节: { bg: ["#31203a", "#6b4480"], syms: ["note", "stage"] },
  直播间: { bg: ["#251a33", "#513a70"], syms: ["heart", "spark", "ring"] },
  餐桌:   { bg: ["#33261c", "#705136"], syms: ["bowl", "chop"] },
  水族:   { bg: ["#12283a", "#2c5a80"], syms: ["bubble", "bubble", "fish"] },
  网咖:   { bg: ["#1b2030", "#3d4a6b"], syms: ["monitor", "cup"] },
  摊位:   { bg: ["#26263a", "#565680"], syms: ["lamp", "star"] },
};

/* 35 人专属配置：场景 / 发色 / 上衣色 / 配饰符号 */
const NPC_PHOTOS = {
  郭瑞莹: ["琴房", "#3b2b20", "#e8e4f0"], 梁雅婷: ["教室", "#2b2018", "#d9705f"],
  小朱: ["办公室", "#241b14", "#7f9bc4"], 雅倩: ["图书馆", "#1c1620", "#c9c2d8"],
  王德芙: ["操场", "#31261c", "#e07850"], 花碎花: ["奶茶店", "#3a2a22", "#e995b5"],
  邓碧瑶: ["深夜房", "#26201c", "#8a90b8"], 炭炭: ["练舞室", "#1f1a1e", "#d85a7a"],
  走路摇: ["漫展", "#3d2c46", "#b48ae0"], 张琦: ["图书馆", "#2e2218", "#a8c4b0"],
  绿小林子: ["漫展", "#2c5231", "#7ac98a"], 韩冰: ["电竞馆", "#20242e", "#6a9bd8"],
  小杨: ["电竞馆", "#31241c", "#e0975f"], 车车: ["解说台", "#2a2018", "#d87850"],
  灵儿: ["解说台", "#241c2e", "#9a8ad8"], 傲寒: ["livehouse", "#1e1822", "#8a8ad0"],
  杨幂: ["片场", "#241c16", "#c05050"], 刘亦菲: ["外滩", "#221c16", "#a8c8d8"],
  宋轶: ["美术馆", "#26201c", "#b09870"], 杨超越: ["游乐园", "#2c2030", "#e08ab0"],
  章若楠: ["商街", "#2e241c", "#d8a888"], 赵丽颖: ["片场", "#241e18", "#c09858"],
  赵今麦: ["教室", "#2a2018", "#88b090"], 迪丽热巴: ["天文台", "#201826", "#c88ab0"],
  张靓颖: ["音乐厅", "#221a24", "#b090d0"], 邓紫棋: ["录音棚", "#1c1c26", "#d05080"],
  鞠婧祎: ["外滩", "#26202a", "#e0b0c8"], 单依纯: ["音乐节", "#20242e", "#7ab8a0"],
  乌苏苏: ["直播间", "#241c2c", "#9a7ad0"], 乐乐: ["直播间", "#2c2230", "#e09595"],
  吃不饱: ["餐桌", "#2c2018", "#d8a860"], 吐泡泡: ["水族", "#1c2430", "#7ab8d8"],
  歪歪: ["网咖", "#26202a", "#c88ab8"], 小新: ["摊位", "#2a2420", "#98b878"],
  慕慕: ["练舞室", "#2e2028", "#d890a8"],
};

const PHOTO_SYM = {
  note: '<path d="M{x} {y} v-16 l12 -3 v14 a4 4 0 1 0 2 3 v-18 l-16 4 v16 a4 4 0 1 0 2 3Z" fill="{c}" opacity=".8"/>',
  book: '<rect x="{x}" y="{y}" width="16" height="12" rx="1.5" fill="{c}" opacity=".75"/><line x1="{x8}" y1="{y}" x2="{x8}" y2="{y12}" stroke="#0006"/>',
  board: '<rect x="{x}" y="{y}" width="22" height="13" rx="1.5" fill="{c}" opacity=".5"/><line x1="{x3}" y1="{y4}" x2="{x18}" y2="{y9}" stroke="#fff5" stroke-width="1.5"/>',
  cup: '<path d="M{x} {y} h11 v9 a5 5 0 0 1 -11 0 Z" fill="{c}" opacity=".8"/><path d="M{x11} {y2} q4 1 0 4" stroke="{c}" fill="none" opacity=".6"/>',
  doc: '<rect x="{x}" y="{y}" width="12" height="16" rx="1" fill="{c}" opacity=".7"/><line x1="{x2}" y1="{y4}" x2="{x10}" y2="{y4}" stroke="#0004"/><line x1="{x2}" y1="{y8}" x2="{x10}" y2="{y8}" stroke="#0004"/>',
  lamp: '<circle cx="{x8}" cy="{y}" r="4" fill="{c}" opacity=".9"/><path d="M{x8} {y4} v8" stroke="{c}" opacity=".5"/>',
  shelf: '<rect x="{x}" y="{y}" width="18" height="4" fill="{c}" opacity=".6"/><rect x="{x}" y="{y7}" width="18" height="4" fill="{c}" opacity=".45"/>',
  sun: '<circle cx="{x8}" cy="{y5}" r="5" fill="{c}" opacity=".85"/>',
  track: '<path d="M{x} {y12} q9 -8 18 0" stroke="{c}" fill="none" stroke-width="2" opacity=".5"/>',
  heart: '<path d="M{x8} {y10} c-5 -4 -7 -8 -3.5 -9.5 c2 -.7 3.5 1 3.5 1 s1.5 -1.7 3.5 -1 c3.5 1.5 1.5 5.5 -3.5 9.5Z" fill="{c}" opacity=".8"/>',
  moon: '<path d="M{x10} {y} a8 8 0 1 0 8 10 a7 7 0 1 1 -8 -10Z" fill="{c}" opacity=".9"/>',
  star: '<path d="M{x8} {y} l1.8 4.2 4.2.6 -3 3 .7 4.2 -3.7 -2 -3.7 2 .7 -4.2 -3 -3 4.2 -.6Z" fill="{c}" opacity=".85"/>',
  headset: '<path d="M{x} {y8} a7 7 0 0 1 14 0" stroke="{c}" fill="none" stroke-width="2.4" opacity=".8"/><rect x="{x1}" y="{y8}" width="3.5" height="6" rx="1.5" fill="{c}" opacity=".8"/><rect x="{x12}" y="{y8}" width="3.5" height="6" rx="1.5" fill="{c}" opacity=".8"/>',
  mirror: '<rect x="{x}" y="{y}" width="14" height="18" rx="2" fill="{c}" opacity=".35" stroke="{c}" stroke-opacity=".6"/>',
  spark: '<path d="M{x8} {y} l1.4 4 4 1.4 -4 1.4 -1.4 4 -1.4 -4 -4 -1.4 4 -1.4Z" fill="{c}" opacity=".8"/>',
  monitor: '<rect x="{x}" y="{y}" width="18" height="12" rx="1.5" fill="{c}" opacity=".55" stroke="{c}" stroke-opacity=".7"/><path d="M{x6} {y16} h6" stroke="{c}" opacity=".6"/>',
  mic: '<rect x="{x6}" y="{y}" width="5" height="10" rx="2.5" fill="{c}" opacity=".8"/><path d="M{x3} {y8} q5 6 10 0 M{x8} {y14} v4" stroke="{c}" fill="none" opacity=".6"/>',
  spot: '<path d="M{x} {y} l6 20 h-12Z" fill="{c}" opacity=".4"/>',
  clap: '<rect x="{x}" y="{y}" width="16" height="10" fill="{c}" opacity=".6" transform="rotate(-14 {x} {y})"/><rect x="{x2}" y="{y12}" width="16" height="4" fill="{c}" opacity=".8"/>',
  bridge: '<path d="M{x} {y8} q10 -12 20 0" stroke="{c}" fill="none" stroke-width="2" opacity=".6"/><line x1="{x5}" y1="{y8}" x2="{x5}" y2="{y16}" stroke="{c}" opacity=".4"/><line x1="{x15}" y1="{y8}" x2="{x15}" y2="{y16}" stroke="{c}" opacity=".4"/>',
  frame: '<rect x="{x}" y="{y}" width="13" height="10" fill="{c}" opacity=".55" stroke="{c}" stroke-opacity=".7"/>',
  ferris: '<circle cx="{x8}" cy="{y6}" r="6" stroke="{c}" fill="none" opacity=".7"/><line x1="{x8}" y1="{y}" x2="{x8}" y2="{y14}" stroke="{c}" opacity=".6"/>',
  balloon: '<circle cx="{x8}" cy="{y4}" r="4.5" fill="{c}" opacity=".7"/><path d="M{x8} {y8} q1 3 0 5" stroke="{c}" fill="none" opacity=".5"/>',
  shop: '<rect x="{x}" y="{y4}" width="16" height="10" fill="{c}" opacity=".5"/><path d="M{x2} {y4} l2 -4 h12 l2 4" stroke="{c}" fill="none" opacity=".6"/>',
  scope: '<line x1="{x}" y1="{y10}" x2="{x14}" y2="{y}" stroke="{c}" stroke-width="2" opacity=".7"/><circle cx="{x13}" cy="{y1}" r="2.5" fill="{c}" opacity=".8"/>',
  wave: '<path d="M{x} {y6} q3 -4 6 0 t6 0" stroke="{c}" fill="none" stroke-width="1.6" opacity=".7"/>',
  stage: '<rect x="{x}" y="{y10}" width="18" height="3" fill="{c}" opacity=".6"/>',
  ring: '<circle cx="{x8}" cy="{y5}" r="5" stroke="{c}" fill="none" stroke-width="1.6" opacity=".6"/>',
  bowl: '<path d="M{x} {y} h14 a7 5 0 0 1 -14 0Z" fill="{c}" opacity=".8"/>',
  chop: '<line x1="{x4}" y1="{y}" x2="{x2}" y2="{y10}" stroke="{c}" stroke-width="1.6" opacity=".7"/><line x1="{x7}" y1="{y}" x2="{x9}" y2="{y10}" stroke="{c}" stroke-width="1.6" opacity=".7"/>',
  bubble: '<circle cx="{x8}" cy="{y5}" r="3.5" stroke="{c}" fill="none" opacity=".6"/>',
  fish: '<path d="M{x} {y5} q4 -4 8 0 q-4 4 -8 0Z" fill="{c}" opacity=".7"/><path d="M{x} {y5} l-3 -2 v4Z" fill="{c}" opacity=".7"/>',
};

/* 生成 NPC 专属图片（自拍构图：场景渐变+符号+人物剪影+闪光），返回 data-uri */
function npcImage(name, captionText) {
  const conf = NPC_PHOTOS[name] || ["直播间", "#2c2430", "#8a8aa8"];
  const scene = PHOTO_SCENES[conf[0]] || PHOTO_SCENES.直播间;
  const cap = esc(captionText || `${conf[0]} · 自拍`);
  const syms = scene.syms.map((s, i) => {
    const tpl = PHOTO_SYM[s] || PHOTO_SYM.spark;
    const x = 34 + i * 52, y = 44 + (i % 2) * 26;
    return tpl.replace(/\{x(\d*)\}/g, (m, d) => x + (d ? +d : 0))
              .replace(/\{y(\d*)\}/g, (m, d) => y + (d ? +d : 0))
              .replace(/\{c\}/g, "rgba(255,255,255,.5)");
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150">
  <defs><linearGradient id="g" x1="0" y1="0" x2="0.4" y2="1">
    <stop offset="0" stop-color="${scene.bg[0]}"/><stop offset="1" stop-color="${scene.bg[1]}"/>
  </linearGradient></defs>
  <rect width="200" height="150" fill="url(#g)"/>
  <g>${syms}</g>
  <g opacity=".18" fill="#fff"><rect x="0" y="112" width="200" height="38"/></g>
  <!-- 人物剪影（肩上自拍构图） -->
  <g>
    <path d="M100 150 q0 -34 30 -40 q22 -5 34 8 q10 10 12 32 Z" fill="${conf[2]}" opacity=".95"/>
    <path d="M100 150 q0 -34 -30 -40 q-22 -5 -34 8 q-10 10 -12 32 Z" fill="${conf[2]}" opacity=".9"/>
    <circle cx="100" cy="74" r="26" fill="${conf[1]}"/>
    <path d="M74 70 q4 -22 26 -22 q22 0 26 22 q2 -26 -26 -28 q-28 2 -26 28Z" fill="${conf[1]}"/>
    <circle cx="100" cy="70" r="21" fill="#e8cdb5"/>
    <path d="M79 66 q3 -18 21 -18 q18 0 21 18 q1 -8 -4 -13 q-7 -7 -17 -7 q-10 0 -17 7 q-5 5 -4 13Z" fill="${conf[1]}"/>
  </g>
  <!-- 自拍闪光与水印 -->
  <circle cx="176" cy="20" r="7" fill="#fff" opacity=".9"/>
  <circle cx="176" cy="20" r="12" fill="#fff" opacity=".25"/>
  <rect x="0" y="132" width="200" height="18" fill="#0009"/>
  <text x="10" y="144" font-size="10.5" fill="#fffd" font-family="sans-serif">${esc(name)} · ${cap}</text>
</svg>`;
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}

/* ---------- 基础请求 ---------- */

/* 轻量操作：完成前会提示稍候，但不再整页锁死剧情输入（串行仍由 pendingRequest 保证） */
const LIGHT_PATHS = ["/api/chat", "/api/gift", "/api/lottery", "/api/buy", "/api/use",
  "/api/sell", "/api/equip", "/api/unequip", "/api/signin", "/api/settings"];

async function api(path, body) {
  if (pendingRequest) throw new Error("上一操作尚未完成，请稍候。");
  pendingRequest = true;
  const light = LIGHT_PATHS.some((p) => path.startsWith(p));
  if (!light) setBusy(true);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 75000);
  try {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json",
      // new/restore 有意覆盖当前进度，不带乐观锁头；resume 读取时无档可对
      ...(S && !["/api/resume", "/api/new", "/api/restore"].includes(path)
        ? {"X-State-Revision": String(S.revision)} : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: controller.signal,
  });
  if (!r.ok) {
    let detail = "";
    try { detail = (await r.json()).detail || ""; } catch (e) { /* ignore */ }
    // 乐观锁冲突自愈：拉取最新进度重绘，玩家重试即可，不必刷新整页
    if (detail.includes("存档已被另一操作更新") && await syncLatestState()) {
      throw new Error("进度已在另一处更新，已为你同步到最新——请重试本次操作。");
    }
    throw new Error(detail || `请求失败（HTTP ${r.status}）`);
  }
  return await r.json();
  } catch (err) {
    if (err.name === "AbortError") throw new Error("等待已超时，请刷新确认最新进度后再操作。");
    throw err;
  } finally {
    clearTimeout(timer);
    pendingRequest = false;
    if (!light) setBusy(false);
  }
}

/* 只读拉取最新进度（乐观锁 409 后自愈用，不推进世界） */
async function syncLatestState() {
  try {
    const r = await fetch("/api/state/full");
    if (!r.ok) return false;
    const data = await r.json();
    if (!data.exists) return false;
    S = data.state;
    renderAll();
    return true;
  } catch (e) {
    return false;
  }
}

function setBusy(v) {
  busy = v;
  $("#btn-act").disabled = v;
  $("#btn-act").textContent = v ? "推演中…" : "行 动";
  $("#free-input").disabled = v;
  $("#btn-start").disabled = v;
  $("#busy-hint").hidden = !v;
  $("#story-flow").setAttribute("aria-busy", String(v));
  document.querySelectorAll(".choice-btn").forEach((b) => (b.disabled = v));
  $("#btn-signin").disabled = v || $("#btn-signin").dataset.signed === "1";
  if (S) renderSys();
}

async function loadCatalog() {
  try {
    const response = await fetch("/api/shop");
    if (!response.ok) throw new Error("目录获取失败");
    const data = await response.json();
    SHOP = data.catalog;
    CATALOG_META = { currency_name: data.currency_name || "系统金币" };
    catalogError = "";
  } catch (err) {
    catalogError = "目录暂未加载成功，请点击重试。";
  }
  loadLottery();
  if (S) { renderSys(); renderSystem(); }
}

function toast(msg, err = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("err", err);
  el.hidden = false;
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.hidden = true), 4200);
}

/* ---------- 界面风格（点击切换） ---------- */

function applyTheme(key) {
  const valid = ["night", "ink", "parchment", "qinglan"].includes(key) ? key : "night";
  document.body.dataset.theme = valid;
  localStorage.setItem("sjl-theme", valid);
  $$(".theme-dot").forEach((d) => d.classList.toggle("active", d.dataset.theme === valid));
}

/* ---------- 渲染 ---------- */

function worldChip(world, cls = "wchip") {
  return `<span class="${cls}">${WORLD_NAMES[world] || "都市"}</span>`;
}

function renderHeader() {
  const chip = $("#world-chip");
  const loc = (S.player.location || {});
  const gd = String(S.game_date || "").split("-");
  const dateTxt = gd.length === 3 ? `${+gd[1]}月${+gd[2]}日·` : "";
  const t = S.time ? `${dateTxt}第${S.time.day}天·${TIME_SLOTS[S.time.slot % 5]} · ` : "";
  chip.textContent = t + (loc.place || "都市");
  chip.title = `游戏内日历：${S.game_date || "?"}（开局 2026-09-01）`;
  // 天际线随游戏时段换色：清晨/上午/下午/傍晚/夜晚
  const SLOT_SKY = ["清晨", "上午", "下午", "傍晚", "夜晚"];
  document.body.dataset.slot = SLOT_SKY[(S.time || {}).slot % 5] || "夜晚";
  $("#chk-affinity").checked = !!S.settings.show_affinity;
  const inp = $("#free-input");
  if (inp) inp.placeholder = DEMO
    ? "演示模式：试试 约会 / 训练 / 探索 / 天赋 / 抽奖 · 配置 LLM 后解锁自由输入"
    : "……或者，写下你想做的任何事";
}

/* ---------- 可视化地图 ---------- */

/* ---------- 三级地图：世界 → 国家 → 城市 ---------- */

const MAP_DEFS = `
  <defs>
    <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="3.5"/>
    </filter>
    <filter id="bldShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="1" stdDeviation="1" flood-color="rgba(0,0,0,.4)"/>
    </filter>
    <radialGradient id="hereGrad">
      <stop offset="0%" stop-color="rgba(255,209,102,.30)"/>
      <stop offset="55%" stop-color="rgba(255,209,102,.12)"/>
      <stop offset="100%" stop-color="rgba(255,209,102,0)"/>
    </radialGradient>
    <radialGradient id="wmVig" cx="50%" cy="46%" r="72%">
      <stop offset="0%" stop-color="rgba(0,0,0,0)"/>
      <stop offset="72%" stop-color="rgba(0,0,0,0)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,.30)"/>
    </radialGradient>
    <linearGradient id="wmOcean" x1="0" y1="0" x2="0.3" y2="1">
      <stop offset="0%" stop-color="var(--wm-ocean-hi, #164e63)"/>
      <stop offset="55%" stop-color="var(--wm-ocean, #0e3748)"/>
      <stop offset="100%" stop-color="var(--wm-ocean-lo, #092634)"/>
    </linearGradient>
    <linearGradient id="wmLand" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="var(--wm-land-hi, #4d8f6a)"/>
      <stop offset="100%" stop-color="var(--wm-land-lo, #27584a)"/>
    </linearGradient>
    <linearGradient id="wmLand2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="var(--wm-land2-hi, #6b9d72)"/>
      <stop offset="100%" stop-color="var(--wm-land2-lo, #3a6b52)"/>
    </linearGradient>
    <linearGradient id="cnLand" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="var(--cn-land-hi, #8fbc8f)"/>
      <stop offset="100%" stop-color="var(--cn-land-lo, #2d5a3d)"/>
    </linearGradient>
    <radialGradient id="cityGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(255,209,102,.45)"/>
      <stop offset="100%" stop-color="rgba(255,209,102,0)"/>
    </radialGradient>
    <radialGradient id="bldHi" cx="30%" cy="20%" r="80%">
      <stop offset="0%" stop-color="rgba(255,255,255,.25)"/>
      <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
    </radialGradient>
    <linearGradient id="ctBgKyoto" x1="0" y1="0" x2="0.2" y2="1">
      <stop offset="0%" stop-color="var(--cn-city-bg, #1d2f27)"/>
      <stop offset="100%" stop-color="var(--cn-city-bg-lo, #101d18)"/>
    </linearGradient>
    <linearGradient id="ctBgModu" x1="0" y1="0" x2="0.2" y2="1">
      <stop offset="0%" stop-color="var(--cn-city-bg2, #1a2537)"/>
      <stop offset="100%" stop-color="var(--cn-city-bg2-lo, #0d1420)"/>
    </linearGradient>
    <linearGradient id="waterGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="rgba(125,190,255,.42)"/>
      <stop offset="100%" stop-color="rgba(59,130,246,.14)"/>
    </linearGradient>
    <linearGradient id="glassGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="rgba(148,197,255,.42)"/>
      <stop offset="100%" stop-color="rgba(94,150,220,.12)"/>
    </linearGradient>
    <linearGradient id="neonGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#f472b6"/>
      <stop offset="100%" stop-color="#22d3ee"/>
    </linearGradient>
  </defs>`;

/* 标注牌：圆角底＋文字，CJK 按全宽、ASCII 按 0.56 宽估算 */
function textW(t, fs) {
  let w = 0;
  for (const ch of String(t)) w += ch.charCodeAt(0) > 255 ? 1 : 0.56;
  return w * fs;
}
function labelPlate(x, y, text, opts = {}) {
  const fs = opts.fs || 11;
  const w = textW(text, fs) + 10;
  return `<g class="lp ${opts.cls || ""}">
    <rect x="${(x - w / 2).toFixed(1)}" y="${y}" width="${w.toFixed(1)}" height="15" rx="7.5" class="lp-bg"/>
    <text x="${x}" y="${y + 11.2}" text-anchor="middle" class="lp-t" font-size="${fs}">${esc(text)}</text>
  </g>`;
}

/* ===== 世界层 SVG（大陆轮廓 + 华夏高亮） ===== */

/* 风格化大陆：西陆（南北美）、欧非、东亚大陆（华夏所在）、群岛与岛弧 */
const W_LANDS = [
  "M22,64 Q16,46 30,34 Q44,20 66,20 Q92,18 108,30 Q120,40 116,54 Q112,66 96,70 Q88,78 80,92 Q74,104 66,118 L58,112 Q60,96 52,86 Q40,80 32,76 Q24,72 22,64 Z",
  "M78,128 Q90,122 100,130 Q108,140 106,154 Q102,170 94,184 Q88,196 84,208 Q82,216 78,212 Q74,204 76,190 Q78,172 74,156 Q70,140 78,128 Z",
  "M182,34 Q192,26 206,28 Q218,30 224,38 Q228,46 222,52 Q212,58 200,56 Q190,54 184,48 Q180,42 182,34 Z",
  "M196,66 Q212,60 226,68 Q236,76 234,90 Q232,104 226,118 Q222,132 218,146 Q216,156 212,154 Q208,146 208,134 Q206,118 200,104 Q194,88 192,78 Q192,70 196,66 Z",
  "M238,74 Q232,56 244,40 Q258,26 282,24 Q308,20 330,28 Q348,34 352,50 Q354,66 344,78 Q338,90 328,100 Q336,108 332,118 Q326,128 314,126 Q302,124 296,134 Q288,146 276,142 Q262,138 254,128 Q246,120 240,108 Q236,92 238,74 Z",
  "M344,124 Q352,120 358,126 Q364,132 358,138 Q350,142 344,136 Q340,130 344,124 Z",
  "M362,138 Q370,136 374,142 Q376,150 368,152 Q360,150 360,144 Z",
  "M322,178 Q334,170 350,174 Q364,178 366,190 Q366,202 354,206 Q340,210 330,202 Q320,192 322,178 Z",
  "M362,66 Q368,62 372,68 Q374,76 370,84 Q366,90 362,84 Q360,74 362,66 Z",
  "M356,90 Q360,88 362,94 Q362,100 358,100 Q354,96 356,90 Z",
  "M150,10 Q160,4 170,8 Q176,14 172,22 Q166,28 156,26 Q148,22 150,10 Z",
  "M172,40 Q176,38 178,44 Q177,50 172,50 Q168,46 172,40 Z",
];

function worldSVG() {
  const countries = (S.map.countries || []);
  const loc = S.player.location || {};
  // 大陆架光晕（每块大陆外圈一圈浅海）＋陆地本体
  const shelf = W_LANDS.map(d =>
    `<path d="${d}" fill="none" stroke="rgba(125,211,252,.14)" stroke-width="5" stroke-linejoin="round"/>`).join("");
  const lands = W_LANDS.map((d, i) =>
    `<path d="${d}" fill="url(#${i % 3 === 2 ? "wmLand2" : "wmLand"})" stroke="rgba(255,255,255,.14)" stroke-width=".6"/>`).join("");
  const markers = countries.map(c => {
    const px = c.x * 4, py = c.y * 2.6;
    const isCur = loc.country === c.name;
    const und = c.discovered === false;
    return `<g class="mcountry${und ? " undisc" : ""}" data-country="${esc(c.name)}" transform="translate(${px},${py})" style="cursor:pointer">
      <title>${esc(c.desc || c.name)}</title>
      ${isCur ? '<circle r="42" fill="url(#cityGlow)" filter="url(#softGlow)"/>' : ""}
      <circle r="24" fill="none" stroke="var(--gold)" stroke-width=".6" opacity=".28"/>
      <circle r="17" fill="none" stroke="var(--gold)" stroke-width="1" opacity=".55"${und ? ' stroke-dasharray="3 4"' : ""}/>
      <circle r="6.5" fill="var(--gold)" filter="url(#softGlow)"/>
      <path d="M0,-24 L3,-14 L0,-9 L-3,-14 Z" fill="var(--gold)" opacity=".9"/>
      ${labelPlate(0, 28, c.name, { fs: 13, cls: isCur ? "lp-gold" : "" })}
    </g>`;
  }).join("");
  return `<svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg">${MAP_DEFS}
    <rect width="400" height="260" fill="url(#wmOcean)" rx="10"/>
    <g class="wm-graticule" fill="none" pointer-events="none">
      <path d="M0,52 Q200,44 400,52"/><path d="M0,91 Q200,84 400,91"/>
      <path class="wm-equator" d="M0,130 Q200,124 400,130"/>
      <path d="M0,169 Q200,163 400,169"/><path d="M0,208 Q200,203 400,208"/>
      <path d="M67,0 Q61,130 67,260"/><path d="M134,0 Q129,130 134,260"/>
      <path d="M200,0 Q196,130 200,260"/><path d="M266,0 Q263,130 266,260"/>
      <path d="M333,0 Q331,130 333,260"/>
    </g>
    <g class="wm-waves" fill="none" pointer-events="none">
      <path d="M40,150 q4,-4 8,0 q4,4 8,0"/><path d="M130,192 q4,-4 8,0 q4,4 8,0"/>
      <path d="M300,38 q4,-4 8,0 q4,4 8,0"/><path d="M56,222 q4,-4 8,0 q4,4 8,0"/>
      <path d="M322,214 q4,-4 8,0 q4,4 8,0"/><path d="M168,120 q4,-4 8,0 q4,4 8,0"/>
      <path d="M388,120 q4,-4 8,0 q4,4 8,0"/><path d="M16,102 q4,-4 8,0 q4,4 8,0"/>
    </g>
    <g class="wm-land" filter="url(#softGlow)" pointer-events="none">${shelf}${lands}</g>
    <g class="wm-clouds" pointer-events="none">
      <g class="wm-cloud">
        <ellipse cx="70" cy="88" rx="14" ry="4"/><ellipse cx="80" cy="84" rx="9" ry="3.2"/><ellipse cx="61" cy="85" rx="7" ry="2.6"/>
      </g>
      <g class="wm-cloud c2">
        <ellipse cx="310" cy="140" rx="16" ry="4.4"/><ellipse cx="320" cy="136" rx="10" ry="3.4"/><ellipse cx="301" cy="137" rx="8" ry="2.8"/>
      </g>
      <g class="wm-cloud c3">
        <ellipse cx="190" cy="178" rx="12" ry="3.6"/><ellipse cx="198" cy="175" rx="8" ry="2.8"/>
      </g>
    </g>
    <g class="wm-arcs" fill="none" pointer-events="none">
      <path d="M264,94 Q170,40 84,72"/>
      <path d="M264,94 Q330,150 368,192"/>
    </g>
    ${markers}
    <g class="wm-compass" transform="translate(374,230)" pointer-events="none">
      <circle r="13" class="cp-ring"/><circle r="9" class="cp-ring" opacity=".4"/>
      <path d="M0,-13V-10M9.2,-9.2L7.1,-7.1M13,0H10M9.2,9.2L7.1,7.1M0,13V10M-9.2,9.2L-7.1,7.1M-13,0H-10M-9.2,-9.2L-7.1,-7.1"
            stroke="var(--dim)" stroke-width=".8" fill="none" opacity=".7"/>
      <path d="M0,-11 L3,0 L0,11 L-3,0 Z" class="cp-needle"/>
      <path d="M0,-11 L3,0 L0,2 Z" fill="var(--gold)" opacity=".9"/>
      <circle r="1.6" class="cp-hub"/><text y="-18" text-anchor="middle" class="cp-n">N</text>
    </g>
    <rect width="400" height="260" fill="url(#wmVig)" rx="10" pointer-events="none"/>
  </svg>`;
}

/* ===== 国家层 SVG（华夏：山川河流 + 城市节点） ===== */

/* 雪峰群：主脊线＋雪帽 */
function peaks(x, y, s = 1) {
  return `<g transform="translate(${x},${y}) scale(${s})">
    <path d="M-20,8 L-9,-12 L-3,-2 L6,-16 L20,8 Z" fill="none" stroke="var(--dim)" stroke-width="1.1" stroke-linejoin="round"/>
    <path d="M-12,-7 L-9,-12 L-6,-7 M2,-11 L6,-16 L10,-11" fill="none" stroke="rgba(255,255,255,.75)" stroke-width="1.1" stroke-linecap="round"/>
    <path d="M-3,-2 L2,2 L6,-2" fill="none" stroke="var(--dim)" stroke-width=".7" opacity=".6"/>
  </g>`;
}
/* 森林：一排小树 */
function forest(x, y) {
  let t = "";
  for (let i = 0; i < 5; i++)
    t += `<path d="M${i * 7 - 14},4 L${i * 7 - 11},-4 L${i * 7 - 8},4 Z" fill="var(--tintA-bd)" opacity=".45"/>`;
  return `<g transform="translate(${x},${y})">${t}</g>`;
}

function countrySVG(countryName) {
  const cities = ((S.map.cities || {})[countryName] || []);
  const loc = S.player.location || {};
  const LAND = "M56,58 Q60,36 88,30 Q120,22 152,30 Q186,24 216,32 Q252,26 284,36 Q318,42 336,62 "
    + "Q348,78 340,92 Q352,102 346,118 Q354,132 342,146 Q334,164 316,166 Q320,180 306,188 "
    + "Q290,196 274,188 Q266,200 250,196 Q238,206 222,198 Q204,206 190,194 Q168,198 154,186 "
    + "Q130,190 116,174 Q94,176 82,160 Q62,156 56,138 Q42,130 46,112 Q36,98 46,84 Q40,70 56,58 Z";
  const markers = cities.map(c => {
    const px = c.x * 4, py = c.y * 2.6;
    const isCur = loc.city === c.name;
    const und = c.discovered === false;
    const glyph = c.name === "京都"
      ? `<g transform="translate(0,-13)" class="city-glyph">
          <path d="M-10,0 L-6,-5 L6,-5 L10,0 Z" fill="var(--gold)" opacity=".8"/>
          <rect x="-5" y="-8" width="10" height="3" fill="var(--tintG-bd)"/>
          <path d="M-7,-8 L0,-13 L7,-8 Z" fill="var(--gold)"/>
          <line x1="0" y1="-13" x2="0" y2="-16" stroke="var(--gold)" stroke-width=".8"/>
          <circle cx="0" cy="-17" r="1.1" fill="var(--gold)"/>
        </g>`
      : c.name === "魔都"
      ? `<g transform="translate(0,-11)" class="city-glyph">
          <rect x="-11" y="-4" width="4" height="9" fill="url(#glassGrad)" stroke="var(--tintU-bd)" stroke-width=".5"/>
          <rect x="6" y="-6" width="4" height="11" fill="url(#glassGrad)" stroke="var(--tintU-bd)" stroke-width=".5"/>
          <rect x="-3" y="-9" width="6" height="14" fill="url(#glassGrad)" stroke="var(--tintU-bd)" stroke-width=".5"/>
          <line x1="0" y1="-9" x2="0" y2="-14" stroke="var(--tintU-bd)" stroke-width=".8"/>
          <circle cx="-1" cy="-5" r=".8" fill="var(--gold)"/><circle cx="1.5" cy="-2" r=".8" fill="var(--gold)"/>
          <circle cx="-9" cy="-1" r=".7" fill="var(--gold)" opacity=".8"/><circle cx="8" cy="-3" r=".7" fill="var(--gold)" opacity=".8"/>
        </g>`
      : `<path d="M-6,-12 L0,-18 L6,-12 Z" fill="var(--gold)" opacity=".8"/>`;
    return `<g class="mcity${und ? " undisc" : ""}" data-city="${esc(c.name)}" transform="translate(${px},${py})" style="cursor:pointer">
      <title>${esc(c.desc || c.name)}</title>
      ${isCur ? '<circle r="36" fill="url(#cityGlow)" filter="url(#softGlow)"/>' : ""}
      <circle r="11" fill="none" stroke="var(--tintA-bd)" stroke-width="1.1"${und ? ' stroke-dasharray="3 4"' : ""}/>
      <circle r="4.5" fill="var(--accent)" filter="url(#softGlow)"/>
      ${glyph}
      ${labelPlate(0, 18, c.name, { fs: 12, cls: isCur ? "lp-gold" : "" })}
    </g>`;
  }).join("");

  // 城际铁路（双层：路基＋轨心）＋中点列车
  const c1 = cities.find(c => c.name === "京都");
  const c2 = cities.find(c => c.name === "魔都");
  const rail = c1 && c2 ? (() => {
    const x1 = c1.x * 4, y1 = c1.y * 2.6, x2 = c2.x * 4, y2 = c2.y * 2.6;
    const cx = (x1 + x2) / 2, cy = Math.min(c1.y, c2.y) * 2.6 - 34;
    const d = `M${x1},${y1} Q${cx},${cy} ${x2},${y2}`;
    const midY = (y1 + 2 * cy + y2) / 4;
    return `<g class="cn-rail">
      <path d="${d}" fill="none" stroke="var(--dim)" stroke-width="2.6" opacity=".3"/>
      <path d="${d}" fill="none" stroke="rgba(255,255,255,.35)" stroke-width=".9" stroke-dasharray="4 4"/>
      <g transform="translate(${cx},${midY - 7})">
        <rect x="-6" y="-3.5" width="12" height="7" rx="2.5" fill="var(--tintU-bg)" stroke="var(--tintU-bd)" stroke-width=".6"/>
        <rect x="-3.6" y="-1.8" width="2.6" height="3" fill="var(--tintU-bd)" opacity=".6"/>
        <rect x="0.6" y="-1.8" width="2.6" height="3" fill="var(--tintU-bd)" opacity=".6"/>
        <circle cx="5.4" cy="0" r=".9" fill="var(--gold)"/>
      </g>
    </g>`;
  })() : "";

  return `<svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg">${MAP_DEFS}
    <rect width="400" height="260" fill="url(#wmOcean)" rx="10"/>
    <g fill="none" opacity=".35" pointer-events="none">
      <path d="M0,130 Q200,124 400,130"/><path d="M200,0 Q196,130 200,260"/>
    </g>
    <g pointer-events="none">
      <path d="${LAND}" fill="none" stroke="var(--cn-land-hi, #8fbc8f)" stroke-width="7" opacity=".16" filter="url(#softGlow)"/>
      <path d="${LAND}" fill="url(#cnLand)" stroke="var(--tintA-bd)" stroke-width=".9" opacity=".94"/>
      <path d="M340,92 Q326,100 320,114 Q332,120 344,112 Z" fill="url(#wmOcean)" opacity=".85"/>
      <ellipse cx="352" cy="74" rx="8" ry="4" fill="url(#wmLand)" stroke="var(--tintA-bd)" stroke-width=".5"/>
      <ellipse cx="330" cy="196" rx="7" ry="3.5" fill="url(#wmLand2)" stroke="var(--tintA-bd)" stroke-width=".5"/>
      <ellipse cx="270" cy="214" rx="5" ry="2.6" fill="url(#wmLand)" stroke="var(--tintA-bd)" stroke-width=".5"/>
      <ellipse cx="104" cy="118" rx="13" ry="7" class="ct-lake"/>
      <path d="M96,115 Q102,111 110,114" fill="none" stroke="rgba(255,255,255,.3)" stroke-width=".8"/>
      <ellipse cx="252" cy="176" rx="9" ry="5" class="ct-lake" opacity=".8"/>
    </g>
    <g class="cn-terrain" pointer-events="none">
      ${peaks(98, 82)}${peaks(148, 54, .8)}${peaks(212, 128, .75)}
      ${forest(72, 138)}${forest(244, 92)}${forest(132, 168)}
      <!-- 西部沙丘与高原台地 -->
      <g class="cn-dunes" fill="none" stroke="var(--gold)" stroke-width=".8" opacity=".22">
        <path d="M70,96 q6,-5 12,0 q6,5 12,0"/><path d="M66,106 q6,-5 12,0 q6,5 12,0"/>
        <path d="M74,116 q5,-4 10,0 q5,4 10,0"/>
      </g>
      <path d="M58,84 Q76,74 96,80 L92,86 Q74,82 62,90 Z" fill="var(--gold)" opacity=".08"/>
      <path class="cn-wall" d="M64,52 L104,46 L142,50 L178,42"/>
      <rect x="82" y="43" width="4" height="6" class="cn-wall-tower"/>
      <rect x="150" y="39" width="4" height="6" class="cn-wall-tower"/>
    </g>
    <g class="cn-rivers" pointer-events="none">
      <path d="M110,98 Q160,112 210,106 Q258,100 292,132 Q306,144 316,158" fill="none" stroke="var(--tintU-bd)" stroke-width="1.7" opacity=".55"/>
      <path d="M112,100 Q160,113 208,108" fill="none" stroke="rgba(255,255,255,.22)" stroke-width=".7"/>
      <path d="M162,160 Q202,140 226,112" fill="none" stroke="var(--tintU-bd)" stroke-width="1.1" opacity=".45"/>
      <!-- 北部支流与出海支汊 -->
      <path d="M150,64 Q186,72 214,88 Q228,96 236,106" fill="none" stroke="var(--tintU-bd)" stroke-width="1" opacity=".4"/>
      <path d="M316,158 l8,6 M316,158 l10,2 M316,158 l4,9" stroke="var(--tintU-bd)" stroke-width="1" opacity=".5" fill="none"/>
    </g>
    ${rail}
    ${markers}
    ${labelPlate(200, 234, countryName, { fs: 15 })}
    <g pointer-events="none" opacity=".45">
      <line x1="118" y1="241.5" x2="176" y2="241.5" stroke="var(--dim)" stroke-width=".8"/>
      <line x1="${224 + textW(countryName, 15) / 2 + 8}" y1="241.5" x2="282" y2="241.5" stroke="var(--dim)" stroke-width=".8"/>
    </g>
  </svg>`;
}

/* ===== 城市层 SVG（建筑图标式城市） ===== */

/* 一棵行道树 */
function tree(x, y, s = 1) {
  return `<g transform="translate(${x},${y}) scale(${s})" class="ct-tree-g">
    <path d="M-3,3 L0,-4 L3,3 Z" class="ct-tree"/>
    <line x1="0" y1="3" x2="0" y2="5" stroke="var(--tintA-bd)" stroke-width=".7"/>
  </g>`;
}

/* 背景楼群：一排低透明度的小楼剪影，撑起城市密度（不与可点建筑争位） */
function fillerRow(x, y, hs) {
  return `<g transform="translate(${x},${y})" class="ct-fillers">` +
    hs.map((h, i) => `<rect x="${i * 9}" y="${-h}" width="7.5" height="${h}" rx=".8"/>`).join("") +
    `</g>`;
}
/* 斑马线：路口的短条纹 */
function crosswalk(x, y) {
  return `<g class="ct-cross">${[0, 3.2, 6.4, 9.6].map(o =>
    `<line x1="${x + o}" y1="${y}" x2="${x + o}" y2="${y + 7}"/>`).join("")}</g>`;
}

const CITY_BG_ART = {
  "京都": `
    <rect width="400" height="260" fill="url(#ctBgKyoto)" rx="10"/>
    <g class="ct-blocks" fill="var(--tintA-bd)" opacity=".07">
      <rect x="24" y="40" width="60" height="36" rx="3"/><rect x="106" y="28" width="52" height="30" rx="3"/>
      <rect x="178" y="44" width="64" height="40" rx="3"/><rect x="262" y="30" width="56" height="34" rx="3"/>
      <rect x="332" y="46" width="46" height="30" rx="3"/>
      <rect x="36" y="152" width="70" height="44" rx="3"/><rect x="150" y="146" width="56" height="36" rx="3"/>
      <rect x="250" y="150" width="66" height="40" rx="3"/><rect x="338" y="142" width="42" height="30" rx="3"/>
      <rect x="60" y="212" width="60" height="34" rx="3"/><rect x="160" y="208" width="70" height="38" rx="3"/>
      <rect x="272" y="212" width="62" height="32" rx="3"/>
    </g>
    <path class="ct-ring" d="M118,22 Q58,62 62,132 Q66,198 140,240" fill="none"/>
    <g class="ct-roads">
      <path d="M0,124 Q200,112 400,124" class="ct-road-main"/>
      <path d="M0,124 Q200,112 400,124" class="ct-dash"/>
      <path d="M96,0 Q104,124 96,260" class="ct-road"/>
      <path d="M212,0 Q204,124 212,260" class="ct-road"/>
      <path d="M316,0 Q322,124 316,260" class="ct-road"/>
      <path d="M0,56 Q200,64 400,56" class="ct-road"/>
      <path d="M0,192 Q200,184 400,192" class="ct-road"/>
    </g>
    <g class="ct-river">
      <path d="M354,0 Q342,80 358,140 Q366,200 350,260" fill="none" stroke="var(--tintU-bd)" stroke-width="6" opacity=".35"/>
      <path d="M354,0 Q342,80 358,140 Q366,200 350,260" fill="none" stroke="rgba(255,255,255,.16)" stroke-width="1.2"/>
      <g class="ct-bridge" stroke="var(--tintG-bd)" stroke-width="1.2" opacity=".7">
        <path d="M332,96 h34 M334,102 h30"/>
        <path d="M336,196 h30 M338,202 h26"/>
      </g>
    </g>
    <ellipse cx="58" cy="74" rx="24" ry="12" class="ct-lake"/>
    <path d="M46,71 Q56,65 68,69" fill="none" stroke="rgba(255,255,255,.28)" stroke-width=".8"/>
    ${fillerRow(28, 104, [7, 11, 6, 12, 8, 10])}
    ${fillerRow(294, 64, [9, 6, 12, 7])}
    ${fillerRow(146, 232, [6, 9, 7])}
    <g class="ct-round-g" transform="translate(200,116)" pointer-events="none">
      <circle r="7" class="ct-round"/><circle r="2.6" class="ct-tree"/>
    </g>
    ${crosswalk(140, 109)}${crosswalk(268, 120)}
    <g class="ct-trees">
      ${tree(84, 118)}${tree(108, 116, .9)}${tree(246, 108)}${tree(270, 106, .9)}
      ${tree(150, 188)}${tree(176, 186, .9)}${tree(300, 186)}${tree(324, 188, .9)}
    </g>
    <g class="ct-lanterns">
      <circle cx="128" cy="116" r="2" class="ct-lantern"/><circle cx="152" cy="114" r="2" class="ct-lantern"/>
      <circle cx="220" cy="112" r="2" class="ct-lantern"/><circle cx="288" cy="118" r="2" class="ct-lantern"/>
    </g>
    <g class="ct-pagoda" transform="translate(378,34)" opacity=".22">
      <path d="M-8,0 h16 M-6,-6 h12 M-4,-12 h8 M-2,-18 h4" stroke="var(--text)" stroke-width="1.4"/>
      <line x1="0" y1="-18" x2="0" y2="-24" stroke="var(--text)" stroke-width="1"/>
    </g>`,
  "魔都": `
    <rect width="400" height="260" fill="url(#ctBgModu)" rx="10"/>
    <g class="ct-blocks" fill="var(--tintU-bd)" opacity=".08">
      <rect x="26" y="34" width="56" height="34" rx="2"/><rect x="102" y="26" width="48" height="40" rx="2"/>
      <rect x="170" y="38" width="60" height="30" rx="2"/><rect x="330" y="30" width="44" height="36" rx="2"/>
      <rect x="30" y="120" width="64" height="40" rx="2"/><rect x="150" y="128" width="56" height="34" rx="2"/>
      <rect x="334" y="118" width="46" height="36" rx="2"/>
      <rect x="238" y="58" width="12" height="34" rx="1"/><rect x="258" y="46" width="14" height="46" rx="1"/>
      <rect x="282" y="60" width="12" height="30" rx="1"/><rect x="228" y="104" width="70" height="26" rx="2"/>
    </g>
    <g class="ct-roads">
      <path d="M0,96 Q200,80 400,96" class="ct-road-main"/>
      <path d="M0,96 Q200,80 400,96" class="ct-dash"/>
      <path d="M120,0 Q126,120 120,240" class="ct-road"/>
      <path d="M268,0 Q262,120 268,240" class="ct-road"/>
      <path d="M0,170 Q200,158 400,170" class="ct-road"/>
      <path d="M60,224 Q200,150 340,224" class="ct-road"/>
    </g>
    <g class="ct-skyline" opacity=".3">
      <rect x="18" y="188" width="10" height="18" fill="var(--tintU-bd)"/>
      <rect x="34" y="178" width="8" height="28" fill="var(--tintU-bd)"/>
      <rect x="150" y="182" width="12" height="24" fill="var(--tintU-bd)"/>
      <rect x="250" y="176" width="10" height="30" fill="var(--tintU-bd)"/>
      <rect x="300" y="180" width="12" height="26" fill="var(--tintU-bd)"/>
      <line x1="226" y1="206" x2="226" y2="186" stroke="var(--tintU-bd)" stroke-width="1.6"/>
      <circle cx="226" cy="182" r="3.4" fill="var(--tintU-bd)"/>
      <circle cx="226" cy="192" r="2.4" fill="var(--tintU-bd)"/>
    </g>
    <path d="M0,208 Q200,194 400,208 L400,260 L0,260 Z" fill="url(#waterGrad)" opacity=".55"/>
    <g fill="none" stroke="rgba(255,255,255,.18)" stroke-width=".9">
      <path d="M40,224 q6,-4 12,0 q6,4 12,0"/><path d="M180,232 q6,-4 12,0 q6,4 12,0"/>
      <path d="M300,226 q6,-4 12,0 q6,4 12,0"/><path d="M110,244 q6,-4 12,0 q6,4 12,0"/>
    </g>
    <g class="ct-boat" transform="translate(340,236)">
      <path d="M-8,0 Q0,5 8,0 L5,-3 L-5,-3 Z" fill="var(--tintG-bd)" opacity=".7"/>
      <line x1="0" y1="-3" x2="0" y2="-12" stroke="var(--tintG-bd)" stroke-width=".8"/>
      <path d="M0,-12 L6,-4 L0,-4 Z" fill="var(--tintA-bg)" opacity=".8"/>
    </g>
    <g class="ct-neon" stroke="url(#neonGrad)" stroke-width="1.6" stroke-linecap="round" opacity=".7">
      <line x1="238" y1="72" x2="252" y2="72"/><line x1="262" y1="56" x2="276" y2="56"/>
      <line x1="286" y1="74" x2="296" y2="74"/>
    </g>
    ${fillerRow(24, 150, [8, 12, 6, 9])}
    ${fillerRow(160, 122, [7, 10, 6, 9, 8])}
    ${fillerRow(356, 118, [10, 7, 12])}
    <g class="ct-round-g" transform="translate(200,88)" pointer-events="none">
      <circle r="7" class="ct-round"/><circle r="2.6" class="ct-tree"/>
    </g>
    ${crosswalk(126, 100)}${crosswalk(282, 92)}
    <g class="ct-streetlights">
      <circle cx="64" cy="90" r="1.2" class="ct-lantern"/><circle cx="152" cy="84" r="1.2" class="ct-lantern"/>
      <circle cx="226" cy="80" r="1.2" class="ct-lantern"/><circle cx="322" cy="90" r="1.2" class="ct-lantern"/>
    </g>`,
};

const BUILDING_ICONS = {
  /* 校园：山花讲堂＋钟楼时钟＋旗杆 */
  campus: (x, y) => `<g class="bld" transform="translate(${x},${y})" filter="url(#bldShadow)">
    <ellipse cx="0" cy="12" rx="16" ry="3.5" class="bld-shadow"/>
    <rect x="-13" y="-4" width="26" height="15" rx="1" class="bwall"/>
    <g stroke="var(--tintG-bd)" stroke-width="1" opacity=".5">
      <line x1="-9" y1="-1" x2="-9" y2="10"/><line x1="-3" y1="-1" x2="-3" y2="10"/>
      <line x1="3" y1="-1" x2="3" y2="10"/><line x1="9" y1="-1" x2="9" y2="10"/>
    </g>
    <path d="M-15,-4 L0,-13 L15,-4 Z" class="broof"/>
    <rect x="-2.5" y="-21" width="5" height="8" class="bwall"/>
    <path d="M-4,-21 L0,-26 L4,-21 Z" class="broof"/>
    <circle cx="0" cy="-17" r="2.2" fill="var(--gold)" opacity=".92"/>
    <path d="M0,-17 L0,-18.5 M0,-17 L1,-16.6" stroke="rgba(0,0,0,.5)" stroke-width=".5"/>
    <line x1="0" y1="-26" x2="0" y2="-30" stroke="var(--gold)" stroke-width=".8"/>
    <path d="M0,-30 L5,-28.5 L0,-27 Z" fill="var(--accent)"/>
  </g>`,
  /* 商街：两层商铺＋雨棚＋招牌 */
  city: (x, y) => `<g class="bld" transform="translate(${x},${y})" filter="url(#bldShadow)">
    <ellipse cx="0" cy="12" rx="15" ry="3.5" class="bld-shadow"/>
    <rect x="-12" y="-7" width="24" height="18" rx="1" fill="url(#glassGrad)" stroke="var(--tintU-bd)" stroke-width=".7"/>
    <g fill="var(--tintU-bd)" opacity=".45">
      <rect x="-9.5" y="-5" width="4" height="3.4"/><rect x="-2" y="-5" width="4" height="3.4"/><rect x="5.5" y="-5" width="4" height="3.4"/>
      <rect x="-9.5" y="-0.5" width="4" height="3.4"/><rect x="5.5" y="-0.5" width="4" height="3.4"/>
    </g>
    <path d="M-13.5,3.5 h27 l2,4.5 h-31 z" fill="var(--tintU-bd)" opacity=".35"/>
    <g fill="var(--tintU-bd)" opacity=".4">
      <circle cx="-9" cy="8" r="1.3"/><circle cx="-4.5" cy="8" r="1.3"/><circle cx="0" cy="8" r="1.3"/>
      <circle cx="4.5" cy="8" r="1.3"/><circle cx="9" cy="8" r="1.3"/>
    </g>
    <rect x="-2.5" y="5.5" width="5" height="5.5" rx=".8" fill="var(--tintU-bd)" opacity=".65"/>
    <rect x="-6" y="-11.5" width="12" height="3.6" rx="1" fill="var(--gold)" opacity=".85"/>
  </g>`,
  /* 休闲：摩天轮 */
  leisure: (x, y) => `<g class="bld" transform="translate(${x},${y})" filter="url(#bldShadow)">
    <ellipse cx="0" cy="12" rx="13" ry="3" class="bld-shadow"/>
    <path d="M-6,11 L0,0 L6,11" fill="none" stroke="var(--tintA-bd)" stroke-width="1.2"/>
    <circle r="9" class="brim"/>
    <g stroke="var(--tintA-bd)" stroke-width=".7" opacity=".8">
      <line x1="0" y1="-9" x2="0" y2="9"/><line x1="-7.8" y1="-4.5" x2="7.8" y2="4.5"/>
      <line x1="-7.8" y1="4.5" x2="7.8" y2="-4.5"/>
    </g>
    <g fill="var(--gold)" opacity=".9">
      <circle cx="0" cy="-9" r="1.5"/><circle cx="7.8" cy="-4.5" r="1.5"/><circle cx="7.8" cy="4.5" r="1.5"/>
      <circle cx="0" cy="9" r="1.5"/><circle cx="-7.8" cy="4.5" r="1.5"/><circle cx="-7.8" cy="-4.5" r="1.5"/>
    </g>
    <circle r="1.6" fill="var(--tintA-bd)"/>
  </g>`,
  /* 自然：双松＋溪流 */
  nature: (x, y) => `<g class="bld" transform="translate(${x},${y})" filter="url(#bldShadow)">
    <ellipse cx="0" cy="12" rx="14" ry="3" class="bld-shadow"/>
    <path d="M-13,11 Q0,8 13,11" fill="none" stroke="var(--dim)" stroke-width=".9" opacity=".6"/>
    <path d="M-6,11 L-6,8 M-3,8.6 L-3,6" stroke="var(--tintA-bd)" stroke-width=".9"/>
    <path d="M-11,8 L-6,-4 L-1,8 Z" fill="var(--tintA-bg)" stroke="var(--tintA-bd)" stroke-width=".8"/>
    <path d="M-10,5.5 L-6,0 L-2,5.5 Z" fill="var(--tintA-bg)" stroke="var(--tintA-bd)" stroke-width=".7" opacity=".85"/>
    <line x1="-6" y1="8" x2="-6" y2="11" stroke="var(--tintA-bd)" stroke-width="1"/>
    <path d="M1,11 L1,9 M4,9.6 L4,8" stroke="var(--tintA-bd)" stroke-width=".8"/>
    <path d="M-2.5,9 L1,0 L4.5,9 Z" fill="var(--tintA-bg)" stroke="var(--tintA-bd)" stroke-width=".8"/>
    <line x1="1" y1="9" x2="1" y2="11" stroke="var(--tintA-bd)" stroke-width="1"/>
    <path d="M-12,4 Q-7,2 -2,4" fill="none" stroke="var(--tintU-bd)" stroke-width=".8" opacity=".6"/>
  </g>`,
  /* 文化：柱廊美术馆 */
  culture: (x, y) => `<g class="bld" transform="translate(${x},${y})" filter="url(#bldShadow)">
    <ellipse cx="0" cy="12" rx="16" ry="3.5" class="bld-shadow"/>
    <path d="M-15,12 h30 M-13,9 h26" stroke="var(--tintG-bd)" stroke-width="1" opacity=".7"/>
    <g fill="var(--tintG-bd)" opacity=".55">
      <rect x="-10.5" y="-2" width="2.6" height="11"/><rect x="-4.3" y="-2" width="2.6" height="11"/>
      <rect x="1.9" y="-2" width="2.6" height="11"/><rect x="8.1" y="-2" width="2.6" height="11"/>
    </g>
    <rect x="-12" y="-3" width="24" height="2.4" fill="var(--tintG-bg)" stroke="var(--tintG-bd)" stroke-width=".6"/>
    <path d="M-16,-3 L0,-12 L16,-3 Z" class="broof"/>
    <circle cx="0" cy="-6.5" r="1.5" fill="var(--gold)" opacity=".9"/>
  </g>`,
  /* 交通：车站拱顶＋时钟＋站台列车 */
  transport: (x, y) => `<g class="bld" transform="translate(${x},${y})" filter="url(#bldShadow)">
    <ellipse cx="0" cy="12" rx="16" ry="3.5" class="bld-shadow"/>
    <path d="M-13,2 Q-13,-9 0,-9 Q13,-9 13,2 Z" fill="var(--tintU-bg)" stroke="var(--tintU-bd)" stroke-width=".8"/>
    <rect x="-13" y="2" width="26" height="6" fill="var(--tintU-bg)" stroke="var(--tintU-bd)" stroke-width=".7"/>
    <circle cx="0" cy="-2.5" r="2.2" fill="var(--gold)" opacity=".92"/>
    <path d="M0,-2.5 L0,-4 M0,-2.5 L1,-2.1" stroke="rgba(0,0,0,.5)" stroke-width=".5"/>
    <rect x="-8" y="4" width="4" height="4" rx=".6" fill="var(--tintU-bd)" opacity=".5"/>
    <rect x="4" y="4" width="4" height="4" rx=".6" fill="var(--tintU-bd)" opacity=".5"/>
    <line x1="-16" y1="10.5" x2="16" y2="10.5" stroke="var(--dim)" stroke-width="1.2" opacity=".6"/>
    <g transform="translate(0,14.5)">
      <rect x="-7" y="-2.5" width="14" height="5" rx="2.2" fill="url(#glassGrad)" stroke="var(--tintU-bd)" stroke-width=".6"/>
      <rect x="-4" y="-1.4" width="3" height="2.6" fill="var(--tintU-bd)" opacity=".55"/>
      <rect x="0.5" y="-1.4" width="3" height="2.6" fill="var(--tintU-bd)" opacity=".55"/>
      <circle cx="6" cy="0" r=".8" fill="var(--gold)"/>
    </g>
  </g>`,
  /* 秘境：天文台圆顶＋望远镜＋星光 */
  secret: (x, y) => `<g class="bld" transform="translate(${x},${y})" filter="url(#bldShadow)">
    <ellipse cx="0" cy="12" rx="14" ry="3.5" class="bld-shadow"/>
    <rect x="-9" y="2" width="18" height="9" rx="1" class="bwall"/>
    <path d="M-9,2 Q-9,-9 0,-9 Q9,-9 9,2 Z" fill="url(#glassGrad)" stroke="var(--tintG-bd)" stroke-width=".8"/>
    <line x1="2.5" y1="-8" x2="2.5" y2="2" stroke="var(--tintG-bd)" stroke-width=".8" opacity=".7"/>
    <rect x="2" y="-13.5" width="9" height="3" rx="1.5" fill="var(--tintG-bd)" transform="rotate(-30 6 -12)" opacity=".9"/>
    <g stroke="var(--gold)" stroke-width=".9" opacity=".85">
      <line x1="9" y1="-16" x2="9" y2="-12"/><line x1="7" y1="-14" x2="11" y2="-14"/>
    </g>
    <circle cx="-6" cy="6" r=".8" fill="var(--tintG-bd)" opacity=".6"/>
    <circle cx="0" cy="6" r=".8" fill="var(--tintG-bd)" opacity=".6"/>
    <circle cx="6" cy="6" r=".8" fill="var(--tintG-bd)" opacity=".6"/>
  </g>`,
};

function citySVG(cityName) {
  const places = (S.map.urban || []).filter(p => p.city === cityName);
  const loc = S.player.location || {};
  const markers = places.map(p => {
    const px = p.x * 4, py = p.y * 2.6;
    const isCur = loc.place === p.name;
    const und = p.discovered === false;
    const icon = (BUILDING_ICONS[p.type] || BUILDING_ICONS.city)(px, py);
    return `<g class="mplace${und ? " undisc" : ""}" role="button" tabindex="0" aria-label="查看${esc(p.name)}" data-world="urban" data-place="${esc(p.name)}" data-city="${esc(cityName)}" style="cursor:pointer">
      <title>${esc(p.desc || p.name)}</title>
      ${isCur ? `<circle cx="${px}" cy="${py}" r="24" fill="url(#hereGrad)"/>` : ""}
      ${isCur ? `<circle cx="${px}" cy="${py}" r="15" fill="none" stroke="var(--gold)" stroke-width="1.2" stroke-dasharray="4 3" opacity=".8"/>` : ""}
      ${und ? `<circle cx="${px}" cy="${py}" r="15" class="undisc-ring"/>` : ""}
      ${icon}
      ${und ? labelPlate(px, py - 34, "未探明", { fs: 8, cls: "lp-und" }) : ""}
      ${labelPlate(px, py + 16, p.name, { cls: isCur ? "lp-gold" : "" })}
    </g>`;
  }).join("");

  // 走过的路：已探明地点之间的足迹线
  const disc = places.filter(p => p.discovered);
  const routes = [];
  for (let i = 0; i < disc.length - 1; i++) {
    const a = disc[i], b = disc[i + 1];
    routes.push(`<path class="route" d="M${a.x * 4},${a.y * 2.6} Q${(a.x + b.x) * 2},${Math.min(a.y, b.y) * 2.6 - 14} ${b.x * 4},${b.y * 2.6}"/>`);
  }

  return `<svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg">${MAP_DEFS}
    ${CITY_BG_ART[cityName] || CITY_BG_ART["京都"]}
    ${routes.join("")}
    ${markers}
    ${labelPlate(200, 240, cityName, { fs: 14 })}
  </svg>`;
}

/* 地图层级路由 */
let mapLevel = "city";  // "world" | "country" | "city"
let mapCountry = "华夏";
let mapCity = "京都";

function mapSVGByLevel() {
  if (mapLevel === "world") return worldSVG();
  if (mapLevel === "country") return countrySVG(mapCountry);
  return citySVG(mapCity);
}

function mapBreadcrumb() {
  const loc = S.player.location || {};
  return `世界 › ${esc(mapCountry)}${mapLevel === "city" ? ` › ${esc(mapCity)}` : ""}`;
}

function renderMap() {
  const loc = S.player.location || {};
  $("#map-now").textContent = `当前位置：${loc.city || ""} · ${loc.place || "未知"}`;
  // 小地图显示玩家所在城市层
  mapCity = loc.city || "京都";
  mapCountry = loc.country || "华夏";
  mapLevel = "city";
  $("#map-canvas").innerHTML = citySVG(mapCity);
}

/* ---------- 地图大图查看界面 ---------- */

let mapModalView = null;

function openMapModal(focusPlace) {
  const loc = S.player.location || {};
  mapCountry = loc.country || "华夏";
  mapCity = loc.city || "京都";
  mapLevel = "city";
  $("#map-modal").hidden = false;
  renderBigMap();
  if (focusPlace) showPlaceDetail(mapCity, focusPlace);
  else $("#map-detail").hidden = true;
}

function closeMapModal() { $("#map-modal").hidden = true; }

function renderBigMap() {
  const loc = S.player.location || {};
  $("#map-now-big").textContent = `当前位置：${loc.city || ""} · ${loc.place || "未知"}`;
  $("#map-canvas-big").innerHTML = mapSVGByLevel();
  // 面包屑按钮
  const crumbs = $("#map-crumbs");
  if (crumbs) {
    crumbs.innerHTML = `
      <button class="crumb${mapLevel === "world" ? " active" : ""}" data-lv="world">🌍 世界</button>
      <span class="crumb-sep">›</span>
      <button class="crumb${mapLevel === "country" ? " active" : ""}" data-lv="country">${esc(mapCountry)}</button>
      ${mapLevel === "city" ? `<span class="crumb-sep">›</span>
      <button class="crumb active">${esc(mapCity)}</button>` : ""}`;
  }
}

function showPlaceDetail(cityName, name) {
  const p = (S.map.urban || []).find(x => x.name === name);
  if (!p) return;
  const loc = S.player.location || {};
  const isCur = loc.place === name;
  const known = p.discovered !== false;
  const hereNpcs = known
    ? (S.npcs || []).filter(n => n.place === name).map(n => n.name) : [];
  const detail = $("#map-detail");
  detail.hidden = false;
  detail.innerHTML = `
    <div class="md-head">
      <span class="md-name">${esc(name)}</span>
      <span class="md-city">${esc(cityName)}</span>
      ${p.type ? `<span class="md-type">${PLACE_TYPES[p.type] || esc(p.type)}</span>` : ""}
      ${isCur ? `<span class="md-cur">◈ 当前所在</span>` : ""}
      ${!known ? `<span class="md-und">未探明</span>` : ""}
    </div>
    ${known
      ? `<div class="md-desc dim">${esc(p.desc || "这里还没有留下任何记载。")}</div>`
      : `<div class="md-desc dim">🌫 还未踏足的角落——亲自前往，才能揭开它真实的模样。</div>`}
    ${hereNpcs.length ? `<div class="md-npcs">常在此地：${hereNpcs.map(esc).join("、")}</div>` : ""}
    <div class="md-actions">
      ${isCur ? `<button class="btn btn-ghost md-explore">🔎 在此探索</button>` : ""}
      ${!isCur ? `<button class="btn btn-accent md-go" data-place="${esc(name)}">${known ? "前往此地" : "前往探秘"}</button>` : ""}
    </div>`;
}


function renderSystem() {
  const p = S.player;
  $("#realm-name").textContent = REALMS[p.realm] || "？？";
  $("#realm-progress-num").textContent = p.realm_progress + "%";
  $("#realm-bar").style.width = p.realm_progress + "%";
  // 常驻资产行：金币/抽奖券随时可见，不必进商城翻（货币名以服务端目录为准）
  const curName = (CATALOG_META && CATALOG_META.currency_name) || "系统金币";
  const bagCount = (n) => {
    const it = (p.items || []).find((i) => i.name === n);
    return it ? it.get?.("count") ?? it.count ?? 0 : 0;
  };
  const purseLine = $("#purse-line");
  if (purseLine) {
    purseLine.textContent = `💎 ${curName} ×${bagCount(curName)}　🎟 抽奖券 ×${bagCount("系统抽奖券")}`;
    purseLine.title = "金币：商城通货，签到/任务/剧情可得；抽奖券：背包使用即抽";
  }
  const idt = p.identity || {};
  const idLine = $("#identity-line");
  idLine.textContent = idt.urban || "尚无正式身份";
  idLine.title = `身份：${idt.urban || "尚无"}`;
  const tech = p.technique;
  $("#technique-line").textContent = tech && tech.name
    ? `${tech.route || "未定路线"}·《${tech.name}》${tech.grade ? `（${tech.grade}）` : ""}`
    : "初始天赋待领取——在剧情里表达培养意向";
  const pw = S.power || {};
  const PW_STAGES = ["凡人", "灵觉初醒", "淬体", "他心通", "灵犀", "御气"];
  $("#power-line").textContent = pw.awakened
    ? `⚡ 灵能觉醒 · ${PW_STAGES[pw.stage] || "？"}（修为 ${pw.progress || 0}/100）——保密`
    : "系统深处似乎沉睡着什么……（商城·特殊：觉醒·灵种）";
  $("#power-line").title = pw.awakened
    ? "灵能觉醒：修仙是心动系统的隐藏功能，全世界只有你知晓"
    : "传闻：系统深处沉睡着一个隐藏功能";
  const bonus = statBonus();
  $("#stats").innerHTML = Object.entries(p.stats)
    .map(([k, v]) => `<div class="stat" title="${statTip(k)}"><span>${k}</span><b>${v}${bonus[k] ? `<i class="stat-b">+${bonus[k]}</i>` : ""}</b></div>`)
    .join("");

  const today = S.game_date || S.server_date;
  const signed = S.last_sign_in === today;
  const btn = $("#btn-signin");
  btn.textContent = signed ? "今日已签到" : "今日签到";
  btn.dataset.signed = signed ? "1" : "0";
  btn.disabled = signed || busy;
}

function questHTML() {
  const mq = S.main_quest;
  const notes = (mq.notes || []).slice(-3);
  const main = `<div class="q-title">★ ${esc(mq.title)}（第${mq.stage}阶段 · 随等级推进）</div>
     <div class="q-desc">${esc(mq.desc)}</div>` +
     (notes.length ? `<div class="q-desc dim">近况：${notes.map(esc).join("；")}</div>` : "");
  const active = S.side_quests.filter((q) => !q.done);
  const done = S.side_quests.filter((q) => q.done);
  const side = [
    ...active.map((q) =>
      `<div class="quest-side"><div class="q-title">◆ 进行中 · ${esc(q.title)}</div>
       <div class="q-desc">${esc(q.desc)}</div></div>`),
    ...done.map((q) =>
      `<div class="quest-side quest-done"><div class="q-title">✔ 已完成 · ${esc(q.title)}</div>
       <div class="q-desc">${esc(q.desc)}</div></div>`),
  ].join("");
  return { main, side };
}

function renderQuests() {
  const q = questHTML();
  $("#quest-main").innerHTML = q.main;
  $("#quest-side").innerHTML = q.side
    || `<div class="dim small">暂无支线。自由探索世界，可能触发新的际遇。</div>`;
}

/* ---------- 系统界面（状态 / 背包 / 任务） ---------- */

/* 商品图标：按目录精确映射，一物一图标不重复；未知物品兜底问号 */
const ITEM_ICONS = {
  // 修炼（含六路线）
  "专注咖啡": "☕", "提神能量饮": "🥤", "一对一辅导课时": "👩‍🏫", "名师精品网课": "💻",
  "冲刺计划表": "🗓️", "便携医药包": "🩹", "感冒冲剂": "💊", "错题精析手册": "📕",
  "考研真题精讲": "📚", "运动蛋白粉": "🥛", "体测冲刺训练营": "🏃‍♀️",
  "吉他进阶单曲课": "🎸", "深夜食堂食谱": "🍜", "街头摄影实战课": "📷",
  // 属性
  "健身月卡": "🏋️‍♀️", "精读书单": "📖", "沟通表达课": "🗣️", "形象改造套餐": "💇",
  // 约会
  "手写贺卡": "💌", "电影票": "🎬", "游乐园双日票": "🎡", "惊喜盲盒": "🎁",
  // 情趣（氛围→直白）
  "心形暖手宝": "❤️‍🔥", "香薰蜡烛": "🕯️", "玫瑰花瓣浴盐": "🛁", "按摩精油": "🧴",
  "真丝眼罩": "🌙", "情侣对香": "🌸", "情趣骰子": "🎲", "冰火润滑剂": "🧊",
  "情侣手铐": "⛓️", "遥控跳蛋": "📳", "情趣内衣": "🩱", "深层按摩棒": "🪄",
  // 穿搭
  "运动夹克": "🧥", "修身西装": "👔", "轻便跑鞋": "👟", "智能腕表": "⌚", "城市单车": "🚲",
  // 特殊
  "系统抽奖券": "🎟️", "心动雷达": "📡", "好运徽章": "🍀", "时光胶卷": "🎞️",
  "神秘钥匙": "🗝️", "觉醒·灵种": "🌱",
  // 修行丹药
  "引气散": "🍃", "聚灵阵盘": "🧿", "洗髓丹": "🌟",
  // 货币与奖池专属
  "系统金币": "🪙", "便利店饭团": "🍙", "自习室月卡": "🪑",
  "大师吉他课（进阶）": "🎵", "精品摄影套装（高阶）": "📸",
  "传奇钢琴大师课（传承）": "🎹", "限量款行李箱": "🧳", "系统积分×50": "🏅",
  "《心动笔记·残页》": "📜", "下品灵石": "💎",
};

function itemIcon(name) {
  return ITEM_ICONS[name] || (String(name).includes("金币") ? "🪙" : "❔");
}

function renderSys() {
  if (!S) return;
  const p = S.player;
  $("#sys-realm-name").textContent = REALMS[p.realm] || "？？";
  $("#sys-realm-pct").textContent = p.realm_progress + "%";
  $("#sys-realm-bar").style.width = p.realm_progress + "%";
  const bonus = statBonus();
  $("#sys-stats").innerHTML = Object.entries(p.stats)
    .map(([k, v]) => `<div class="stat" title="${statTip(k)}"><span>${k}</span><b>${v}${bonus[k] ? `<i class="stat-b">+${bonus[k]}</i>` : ""}</b></div>`)
    .join("");

  // 装备栏
  const eq = p.equipped || {};
  $("#sys-equip").innerHTML = EQUIP_SLOTS.map((slot) => {
    const name = eq[slot];
    if (!name) {
      return `<div class="equip-slot"><div class="equip-slot-name">${slot}</div>
        <div class="dim small">空</div></div>`;
    }
    const g = (SHOP || []).find((x) => x.name === name);
    const st = g && g.equip ? g.equip.stats : {};
    const bt = Object.entries(st).map(([k, v]) => `${k}+${v}`).join(" ") || "";
    return `<div class="equip-slot filled">
      <div class="equip-slot-name">${slot}</div>
      <div class="equip-item-name">${name}</div>
      <div class="equip-bonus">${bt}</div>
      <button class="bag-use unequip" data-slot="${slot}">卸下</button>
    </div>`;
  }).join("");
  const q = questHTML();
  $("#sys-quest-main").innerHTML = `<div class="quest-main">${q.main}</div>`;
  $("#sys-quest-side").innerHTML = q.side
    || `<div class="dim small">暂无支线。自由探索世界，可能触发新的际遇。</div>`;
  $("#sys-bag").innerHTML = p.items.length
    ? p.items.map((i) => {
        const goods = (SHOP || []).find((g) => g.name === i.name);
        const usable = i.name === "系统抽奖券" || !!(goods && goods.type === "consumable" && goods.use);
        const equippable = !!(goods && goods.type === "equipment");
        const storyUse = !!goods && !usable && ["tool", "consumable"].includes(goods.type);
        const sellable = !!goods && i.name !== "系统金币";
        const giftable = !!goods && GIFT_CATS.includes(goods.cat) && i.name !== "系统抽奖券";
        return `<div class="bag-item" title="${esc(i.desc || "")}">
          <div class="bag-icon">${itemIcon(i.name)}</div>
          <div class="bag-name">${esc(i.name)}</div>
          <div class="bag-count">×${i.count}</div>
          <div class="bag-ops">
            ${usable ? `<button class="bag-use" data-name="${esc(i.name)}">使用</button>` : ""}
            ${storyUse ? `<button class="bag-story" data-name="${esc(i.name)}">在剧情中使用</button>` : ""}
            ${giftable ? `<button class="bag-gift" data-name="${esc(i.name)}">赠送</button>` : ""}
            ${equippable ? `<button class="bag-equip" data-name="${esc(i.name)}">装备</button>` : ""}
            ${sellable ? `<button class="bag-sell" data-name="${esc(i.name)}" title="半价回收">卖出</button>` : ""}
          </div>
        </div>`;
      }).join("")
    : `<div class="dim small">空空如也。签到和探索都能获得物品。</div>`;

  const spirit = p.items.find((i) => i.name === ((CATALOG_META && CATALOG_META.currency_name) || "系统金币"));
  const cur = spirit ? spirit.count : 0;
  $("#sys-currency").textContent = `持有：💎 ${(CATALOG_META && CATALOG_META.currency_name) || "系统金币"} ×${cur}（商城通货；背包内商品可半价卖出）`;
  // 分类筛选：全部/修炼/属性/约会/情趣/穿搭/特殊
  const cats = ["全部", ...new Set((SHOP || []).map((g) => g.cat).filter(Boolean))];
  $("#shop-cats").innerHTML = cats.map((c) =>
    `<button class="shop-cat chip${c === shopCat ? " active" : ""}" data-cat="${c}">${c}</button>`).join("");
  const shown = (SHOP || []).filter((g) => shopCat === "全部" || g.cat === shopCat);
  $("#sys-shop").innerHTML = shown.map((g) => `
    <div class="shop-item${g.cat === "特殊" ? " shop-special" : ""}" title="${g.desc}">
      <div class="bag-icon">${itemIcon(g.name)}</div>
      <div class="bag-name">${g.name}${g.cat ? `<span class="shop-cat-tag">${g.cat}</span>` : ""}</div>
      <div class="shop-desc dim small">${g.desc}</div>
      <div class="shop-foot">
        <span class="shop-price">💎${g.price}</span>
        <button class="btn btn-accent shop-buy" data-name="${g.name}"${cur < g.price ? " disabled" : ""}>购买</button>
      </div>
    </div>`).join("") || `<div class="dim small">${catalogError || "商城目录加载中……"}</div><button class="catalog-retry btn">重试加载</button>`;
  renderLottery();
  const today = S.game_date || S.server_date;
  const signed = S.last_sign_in === today;
  const sb = $("#sys-btn-signin");
  sb.textContent = signed ? "今日已签到" : "今日签到";
  sb.disabled = signed || busy;
  if (busy) $$(".bag-use, .bag-story, .bag-equip, .bag-sell, .bag-gift, .shop-buy, .lot-draw-btn").forEach((b) => (b.disabled = true));
}

/* ---------- 系统抽奖（转盘） ---------- */

let LOTTERY = null;      // /api/lottery 缓存
let shopCat = "全部";    // 商城分类筛选（会话内记忆）

const LOT_QTY_CLASS = { "普通": "q-common", "稀有": "q-rare", "史诗": "q-epic", "传说": "q-legend" };
const LOT_QTY_ICON = { "普通": "🎯", "稀有": "💎", "史诗": "✨", "传说": "👑" };
/* 八扇区：普通×3 / 稀有×2 / 史诗×2 / 传说×1，转盘落点与后端抽出的品质对齐 */
const SLOT_CELL = 62;   // 滚轮单元高（px，与 CSS 保持一致）
const SLOT_LEN = 22;   // 每轮滚动符号数

/* 老虎机符号清单：全部奖池物品（开局加载奖池后重建） */
let slotSymbols = ["系统金币", "专注咖啡", "电影票", "香薰蜡烛", "运动夹克", "自习室月卡",
                   "便利店饭团", "心形暖手宝", "名师精品网课", "限量款行李箱", "手写贺卡"];

function slotCellHTML(name) {
  return `<div class="slot-cell">${itemIcon(name)}<span>${esc(String(name).slice(0, 6))}</span></div>`;
}

function buildSlots() {
  const strips = document.querySelectorAll(".slot-strip");
  if (!strips.length) return;
  strips.forEach((strip, i) => {
    strip.style.transition = "none";
    strip.style.transform = "translateY(0)";
    const names = Array.from({length: SLOT_LEN},
      () => slotSymbols[Math.floor(Math.random() * slotSymbols.length)]);
    strip.innerHTML = names.map(slotCellHTML).join("");
    strip.dataset.ready = "1";
  });
}

/* 从奖池数据刷新符号表并重建滚轮 */
function refreshSlotSymbols() {
  if (!LOTTERY || !LOTTERY.pool) return;
  const names = Object.values(LOTTERY.pool).flatMap((items) => items.map((i) => i.name));
  if (names.length) slotSymbols = [...new Set(names)];
  buildSlots();
}

/* 单轮滚动：把目标符号停在付款线（窗口中列），返回该轮停稳所需毫秒 */
function spinReel(reelIdx, targetName, delayMs) {
  const strip = document.querySelector(`.slot-strip[data-reel="${reelIdx}"]`);
  const wrap = strip.closest(".slot-reel");
  const names = Array.from({length: SLOT_LEN},
    () => slotSymbols[Math.floor(Math.random() * slotSymbols.length)]);
  names[SLOT_LEN - 2] = targetName;               // 停稳时中列对准付款线
  strip.style.transition = "none";
  strip.style.transform = "translateY(0)";
  strip.innerHTML = names.map(slotCellHTML).join("");
  strip.getBoundingClientRect();                   // 强制回流，过渡才会生效
  const duration = 1650;  // 单轮：一次到位的滚动时长
  const targetY = -((SLOT_LEN - 2) - 1) * SLOT_CELL;
  return new Promise((resolve) => {
    setTimeout(() => {
      strip.style.transition = `transform ${duration}ms cubic-bezier(.16,.84,.24,1)`;
      strip.style.transform = `translateY(${targetY}px)`;
      wrap.classList.add("spinning");
      setTimeout(() => {
        wrap.classList.remove("spinning");
        wrap.classList.add("stopped");
        setTimeout(() => wrap.classList.remove("stopped"), 500);
        resolve();
      }, duration);
    }, delayMs);
  });
}

async function loadLottery() {
  try {
    const r = await fetch("/api/lottery");
    if (r.ok) { LOTTERY = await r.json(); renderLottery(); }
  } catch (e) { /* 面板显示占位 */ }
}

function renderLottery() {
  const box = $("#lot-pools");
  if (!box) return;
  refreshSlotSymbols();
  if (!LOTTERY) { box.innerHTML = `<div class="dim small">奖池加载中……</div>`; return; }
  const tickets = (S && S.player && S.player.items
    ? S.player.items.find((i) => i.name === "系统抽奖券") : null);
  $("#lot-tickets").textContent = tickets ? tickets.count : LOTTERY.tickets || 0;
  const btn = $("#lot-draw");
  btn.disabled = busy || !tickets || tickets.count < 1;
  btn.textContent = tickets && tickets.count > 0 ? "立 即 抽 奖" : "没有抽奖券了";
  box.innerHTML = (LOTTERY.qualities || []).map((q) => `
    <div class="lot-pool ${LOT_QTY_CLASS[q] || ""}">
      <div class="lot-pool-title">${LOT_QTY_ICON[q] || ""} ${q}</div>
      <div class="lot-pool-items">${(LOTTERY.pool[q] || [])
        .map((it) => `<span class="lot-pool-item">${esc(it.name)}${it.count > 1 ? `×${it.count}` : ""}</span>`)
        .join("")}</div>
    </div>`).join("");
  const hist = $("#lot-history");
  const h = LOTTERY.history || [];
  hist.innerHTML = h.length
    ? h.map((rec) => `<div class="lot-hist-item ${LOT_QTY_CLASS[rec.quality] || ""}">
        <span class="lot-hist-q">【${rec.quality}】</span>${esc(rec.name)}×${rec.count}
        <span class="dim small">第${rec.no}次</span></div>`).join("")
    : `<div class="dim small">还没有抽过奖——开局送的 10 张券还在等你。</div>`;
  const total = $("#lot-total");
  if (total) total.textContent = `累计抽取 ${LOTTERY.total_drawn || 0} 次`;
}

function revealLotteryResult(r) {
  const card = $("#lot-result");
  card.hidden = false;
  card.className = `lot-result ${LOT_QTY_CLASS[r.quality] || ""}`;
  card.innerHTML = `<div class="lot-card-face">
    <div class="lot-card-quality">${r.quality}</div>
    <div class="lot-card-icon">${itemIcon(r.prize.name)}</div>
    <div class="lot-card-name">${esc(r.prize.name)} ×${r.prize.count}</div>
    <div class="lot-card-desc dim small">${esc(r.prize.desc || "")}</div>
  </div>`;
}

async function drawLottery() {
  if (busy) return;
  const btn = $("#lot-draw");
  const card = $("#lot-result");
  const wrap = $("#lot-slot-wrap");
  btn.disabled = true;
  card.hidden = true;
  try {
    const data = await api("/api/lottery/draw", {});
    S = data.state;
    const r = data.result;
    const reduced = typeof matchMedia === "function"
      && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) { revealLotteryResult(r); renderAll(); loadLottery(); return; }
    // 单滚轮：直接对准真实奖品停稳
    wrap.classList.add("disabled");
    await spinReel(0, r.prize.name, 60);
    revealLotteryResult(r);
    wrap.classList.remove("disabled");
    renderAll();
    loadLottery();
  } catch (e) {
    if (wrap) wrap.classList.remove("disabled");
    toast("抽奖失败：" + e.message, true);
  } finally {
    btn.disabled = busy;
  }
}

function switchSysTab(name) {
  $$(".sys-tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".sys-pane").forEach((p) => p.classList.toggle("active", p.id === `sys-tab-${name}`));
}

function openSysModal(tab) {
  if (!S) { $("#modal").hidden = false; toast("先开始游戏，系统面板才有意义"); return; }
  renderSys();
  $("#sys-modal").hidden = false;
  switchSysTab(tab || "status");
  if (tab === "lottery" && !LOTTERY) loadLottery();
}

function closeSysModal() {
  $("#sys-modal").hidden = true;
}

/* ---------- NPC 详情弹窗 ---------- */

function showNpcDetail(name) {
  const n = (S.npcs || []).find((x) => x.name === name);
  if (!n) return;
  const st = npcStage(n.affinity);
  $("#npc-m-title").innerHTML =
    `<span class="md-name" style="font-size:20px">${esc(n.name)}</span>
     <span class="md-type">${esc(n.role)}</span>
     <span class="md-cur">${esc(n.label)}</span>
     <span class="npc-stage st-${st.idx}">${st.label}</span>`;
  const show = !!S.settings.show_affinity;
  const rels = Object.entries(n.rels || {})
    .map(([k, v]) => `<div class="npc-mem"><b>${esc(k)}</b>：${esc(v)}</div>`).join("");
  const myDates = (S.dates || []).filter((d) => d.npc === n.name);
  const lastDate = myDates[myDates.length - 1];
  const dateInfo = myDates.length
    ? `<div class="npc-mem">共 ${myDates.length} 次约会${lastDate
        ? ` · 最近：第${lastDate.turn}回合在${esc(lastDate.place)}` : ""}</div>
       <div class="npc-mem dim small">${esc(lastDate?.text || "")}</div>`
    : `<div class="npc-mem dim">还没有一起留下过约会回忆。</div>`;
  const canDate = n.affinity >= 70;
  // 背包里可直接赠送的礼物（与背包页同一判定口径）
  const giftable = (S.player.items || []).filter((i) => {
    const goods = (SHOP || []).find((g) => g.name === i.name);
    return goods && GIFT_CATS.includes(goods.cat) && i.name !== "系统抽奖券";
  });
  // 他心通（第3境）：听得见 TA 对你的真实心声
  const pwStage = (S.power || {}).stage || 0;
  const HEART_VOICE = {
    初识: "……这个人，还在我的故事外面。",
    熟识: "有点意思，但也就到此为止——大概。",
    朋友: "可靠的家伙。有 TA 在的地方，事情总会简单一点。",
    亲近: "不知道从什么时候起，一天里最松弛的时刻，是和 TA 说话的时候。",
    心动: "心跳……为什么每次都骗不了自己。再靠近一点，就一点。",
    羁绊: "是 TA 了。往后所有的打算里，都理所当然有 TA 的位置。",
  };
  const heartLine = pwStage >= 3
    ? `<div class="npc-sec">◈ 心声（他心通）</div>
       <div class="npc-mem heart-voice">「${HEART_VOICE[st.label] || "……"}」</div>` : "";
  $("#npc-m-body").innerHTML = `
    <div class="npc-persona">${esc(n.persona)}</div>
    ${show ? `<div class="npc-aff"><div class="bar"><div class="bar-fill" style="width:${n.affinity}%"></div></div>
       <span class="npc-aff-num">${n.affinity}</span></div>` : ""}
    ${heartLine}
    <div class="npc-sec">◈ 好感阶段</div>
    <div class="npc-mem"><span class="npc-stage st-${st.idx}">${st.label}</span>
      ${show ? `（好感 ${n.affinity}）` : ""}——下一阶段见于一言一行的累积。</div>
    <div class="npc-sec">◈ 常在地</div>
    <div class="npc-mem">${esc(n.place || "行踪不定")}</div>
    <div class="npc-sec">◈ 礼物偏好</div>
    ${n.likes ? `<div class="npc-mem">听说 TA 偏爱<b>${esc(n.likes)}</b>类礼物——投其所好，心意加倍。</div>`
      : `<div class="npc-mem dim">还未听说 TA 的喜好，慢慢相处就知道了。</div>`}
    <div class="npc-sec">◈ 约会回忆</div>
    ${dateInfo}
    <div class="npc-date-action">
      <button class="btn btn-accent btn-invite-date" data-npc="${esc(n.name)}"${canDate ? "" : " disabled"}>邀请约会</button>
      <button class="btn btn-ghost btn-msg-npc" data-npc="${esc(n.name)}">发消息</button>
      ${canDate ? "" : show ? `<span class="dim small">需关系达到「亲近」（好感70）</span>` : ""}
    </div>
    <div class="npc-sec">◈ 送礼物</div>
    ${giftable.length
      ? `<div class="npc-gift-chips">${giftable.map((i) =>
          `<button class="chip npc-gift-chip" data-item="${esc(i.name)}" data-npc="${esc(n.name)}">${esc(i.name)} ×${i.count || 1}</button>`).join("")}</div>
         <div class="dim small">同一人每天限 1 份、每周 2 份${n.likes ? `；TA 偏爱${esc(n.likes)}类` : ""}</div>`
      : `<div class="dim small">背包里还没有可赠送的礼物——商城的「约会 / 情趣 / 特殊」分类可以挑选。</div>`}
    <div class="npc-sec">◈ 近期记忆</div>
    ${(n.memo && n.memo.length ? n.memo : n.memory || []).slice(-6)
      .map((m) => `<div class="npc-mem">${esc(m)}</div>`).join("")
      || `<div class="dim small">尚无深刻记忆——去创造吧。</div>`}
    <div class="npc-sec">◈ 人物关系</div>
    ${rels || `<div class="dim small">暂无已知关系。</div>`}`;
  $("#npc-modal").hidden = false;
}

function renderBag() {
  $("#bag").innerHTML = S.player.items.length
    ? S.player.items.map((i) =>
        `<div class="item-row" title="${esc(i.desc || "")}">
           <span>${esc(i.name)}<div class="item-desc">${esc(i.desc || "")}</div></span>
           <span class="item-count">×${i.count}</span>
         </div>`).join("")
    : `<div class="dim small">空空如也。</div>`;
}

function typewrite(el, text) {
  clearInterval(typingTimer);
  el.dataset.fullText = text;
  if (localStorage.getItem("sjl-typing") === "off" || matchMedia("(prefers-reduced-motion: reduce)").matches) {
    el.textContent = text;
    return;
  }
  let i = 0;
  el.textContent = "";
  const flow = $("#story-flow");
  const nearBottom = () => flow.scrollHeight - flow.scrollTop - flow.clientHeight < 90;
  // 点击剧情区立即显示全文（视觉小说标配）；自然打完时同步摘掉监听
  const skip = () => {
    clearInterval(typingTimer);
    el.textContent = text;
    flow.removeEventListener("click", skip);
  };
  flow.addEventListener("click", skip);
  typingTimer = setInterval(() => {
    i = Math.min(text.length, i + 3);
    el.textContent = text.slice(0, i);
    // 只有读者本来就在底部时才跟随滚动，避免打断用户滚动/点击
    if (nearBottom()) flow.scrollTop = flow.scrollHeight;
    if (i >= text.length) {
      clearInterval(typingTimer);
      flow.removeEventListener("click", skip);
    }
  }, 16);
}

function renderStory(animate = false) {
  clearInterval(typingTimer);  // 旧打字机不得在重绘后继续把滚动拽到底
  const flow = $("#story-flow");
  flow.innerHTML = "";
  if (!S.story.length) {
    // 空剧情不再是一句死文案：给出第一步的明确入口
    flow.innerHTML = `
      <div class="seg">
        <div class="seg-head"><span>第 0 幕</span>${worldChip(S.player.world || "urban")}</div>
        <div class="seg-text">故事尚未开始——舞台已就绪：${esc(S.player.name)}，${esc((S.player.identity || {}).urban || "京华大学的新生")}。</div>
        <div class="npc-date-action" style="margin-top:12px">
          <button class="btn btn-accent" id="story-start-btn">启程 · 迈出第一步</button>
          <span class="dim small">${DEMO ? "演示模式为示例剧情：支持关键词行动，配置 LLM 后解锁自由输入" : "或在下方输入框写下你想做的任何事"}</span>
        </div>
      </div>`;
    $("#choices").innerHTML = "";
    $("#story-start-btn").onclick = () =>
      act("在新学期的清晨醒来，整理好心情，主动去认识这个新环境和新的人");
    return;
  }
  const dateTurns = new Map((S.dates || []).map((d) => [d.turn, d.npc]));
  S.story.forEach((seg, idx) => {
    const div = document.createElement("div");
    div.className = "seg";
    const head = document.createElement("div");
    head.className = "seg-head";
    const dateTag = dateTurns.has(seg.turn)
      ? `<span class="seg-date" title="约会回忆">❤ ${esc(dateTurns.get(seg.turn))}</span>` : "";
    head.innerHTML = `<span>第${seg.turn}幕</span>${dateTag}${worldChip(seg.world)}`;
    const text = document.createElement("div");
    text.className = "seg-text";
    text.textContent = seg.text;
    div.append(head, text);
    if (seg.chosen) {
      const c = document.createElement("div");
      c.className = "seg-chosen";
      c.textContent = seg.chosen;
      div.append(c);
    }
    flow.append(div);
    if (animate && idx === S.story.length - 1 && seg.text.length > 40) {
      typewrite(text, seg.text);
    }
  });
  flow.scrollTop = flow.scrollHeight;

  const last = S.story[S.story.length - 1];
  const box = $("#choices");
  box.innerHTML = "";
  (last.choices || []).forEach((c) => {
    const b = document.createElement("button");
    b.className = "choice-btn";
    b.textContent = c;
    b.onclick = () => act(c);
    box.append(b);
  });
}

function renderRelations() {
  // 只显示认识的人；没人时卡片保留并给出方向，而不是整块消失
  const known = S.npcs || [];
  const box = $("#relations");
  const card = $("#relations-card");
  if (card) card.hidden = false;
  if (!known.length) {
    box.innerHTML = `<div class="dim small" style="padding:6px 2px">还未结识任何人——出门走走、在剧情里主动搭话，认识的她会出现在这里。</div>`;
    return;
  }
  const show = !!S.settings.show_affinity;
  $("#relations").innerHTML = S.npcs
    .map((n) => {
      const rels = Object.entries(n.rels || {})
        .map(([k, v]) => `与<b>${esc(k)}</b>：${esc(v)}`)
        .join("<br>");
      const st = npcStage(n.affinity);
      return `<div class="npc-card" data-name="${esc(n.name)}" title="点击查看详情">
        <div class="npc-head">
          <span class="npc-name">${esc(n.name)}</span>
          <span class="npc-role">${esc(n.role)}</span>
          <span class="npc-label">${esc(n.label)}</span>
          <span class="npc-stage st-${st.idx}">${st.label}</span>
        </div>
        <div class="npc-place">${n.place ? `常在 · ${esc(n.place)}` : "行踪不定"}</div>
        ${show
          ? `<div class="npc-aff"><div class="bar"><div class="bar-fill" style="width:${n.affinity}%"></div></div>
             <span class="npc-aff-num">${n.affinity}</span></div>`
          : `<div class="dim small">关系隐于言行之中</div>`}
        ${rels ? `<div class="npc-rels">${rels}</div>` : ""}
      </div>`;
    })
    .join("");
}

function renderInbox(newCount = 0) {
  const all = [...(S.inbox || [])].reverse();
  renderInboxList($("#inbox"), all.filter((m) => m.type !== "moment"),
                  "暂无消息。你离开的时光里，世界会留下痕迹。");
  renderInboxList($("#moments"), all.filter((m) => m.type === "moment"),
                  "暂无动态。TA 们的朋友圈还很安静。");
  $("#inbox-dot").hidden = newCount <= 0;
}

function renderInboxList(el, items, emptyText) {
  if (!el) return;
  el.innerHTML = items.length
    ? items
        .map((m) =>
          `<div class="inbox-item${m.type === "message" ? " msg" : ""}${m.type === "moment" ? " moment" : ""}"
                data-ts="${esc(m.ts || "")}" data-title="${esc(m.title || "")}" role="button" tabindex="0">
             <div class="inbox-title">${esc(m.title)}
               ${m.from ? `<span class="inbox-from"> · ${esc(m.from)}</span>` : worldChip(m.world)}
               ${m.type === "message" && m.from
                 ? `<button class="chip inbox-reply" data-npc="${esc(m.from)}">回复</button>` : ""}
               ${m.type === "moment" && m.from
                 ? `<button class="chip inbox-reply" data-npc="${esc(m.from)}">私聊</button>` : ""}
             </div>
             <div class="inbox-text">${esc(m.text)}</div>
           </div>`)
        .join("")
    : `<div class="dim small">${emptyText}</div>`;
}

/* 打开一条消息/动态的全文详情；有来源人物的可直接发起私聊 */
function openMsgDetail(ts, title) {
  const m = (S.inbox || []).find((x) => (ts && x.ts === ts) || (!ts && x.title === title));
  if (!m) return;
  const isMoment = m.type === "moment";
  $("#msg-m-title").innerHTML =
    `<span class="md-name">${esc(m.title)}</span>
     ${m.from ? `<span class="md-type">${esc(m.from)}</span>` : ""}
     <span class="md-city">${isMoment ? "朋友圈动态" : "收件"}</span>`;
  $("#msg-m-body").innerHTML = `
    <div class="chat-row">
      <div class="chat-ava npc">${esc((m.from || m.title || "?").slice(0, 1))}</div>
      <div class="bub bub-npc">${esc(m.text)}
        ${m.image ? `<img class="chat-photo" src="${npcImage(m.from || m.title, m.image)}" alt="${esc(m.image)}">
           <div class="chat-photo-cap">📷 ${esc(m.image)}</div>` : ""}
      </div>
    </div>
    <div class="msg-m-meta dim small" style="text-align:right">${esc((m.ts || "").replace("T", " ").slice(0, 19) || "时间不详")}</div>
    ${m.from
      ? `<div class="md-actions"><button class="btn btn-accent" id="msg-chat">💬 和${esc(m.from)}私聊</button></div>`
      : ""}`;
  $("#msg-modal").hidden = false;
  const chatBtn = $("#msg-chat");
  if (chatBtn) chatBtn.onclick = () => { $("#msg-modal").hidden = true; openChat(m.from); };
}

function renderAll(newInbox = 0, story = false, animate = false) {
  renderHeader();
  renderMap();
  renderSystem();
  renderQuests();
  renderBag();
  if (story) renderStory(animate);
  renderRelations();
  renderPhone();
  renderInbox(newInbox);
  renderSys();
  renderCodex();
  maybeShowEnding();
}

/* ---------- 动作 ---------- */

async function act(text) {
  if (busy || !text.trim()) return;
  if (!S) { $("#modal").hidden = false; toast("先开始游戏，再行动"); return; }
  if (DEMO && localStorage.getItem("sjl-demo-hint") !== "shown") {
    localStorage.setItem("sjl-demo-hint", "shown");
    toast("演示模式为内置示例剧情：识别「约会 / 训练 / 探索 / 天赋 / 抽奖」等关键词，其余为轮换片段。配置 LLM 后即可自由输入任何行动", true);
  }
  setBusy(true);
  try {
    const data = await api("/api/act", { text });
    S = data.state;
    DEMO = !!data.demo_mode;
    $("#demo-badge").hidden = !DEMO;
    renderAll(0, true, true);
    if ($("#free-input").value.trim() === text.trim()) $("#free-input").value = "";
    if (data.system_notice) toast(data.system_notice);
  } catch (e) {
    toast("行动失败：" + e.message, true);
  } finally {
    setBusy(false);
  }
}

async function resume() {
  try {
    const data = await api("/api/resume");
    S = data.state;
    DEMO = !!data.demo_mode;
    $("#demo-badge").hidden = !DEMO;
    const n = (data.offline_events || []).length;
    renderAll(n, true);
    if (data.system_notice) toast(data.system_notice);
    if (!SHOP) await loadCatalog();
    if (n > 0) {
      toast(`你不在的时候，世界发生了 ${n} 件事——详见收件箱`);
      $("#inbox-dot").hidden = false;
    }
  } catch (e) {
    // 读档失败不能只剩一句会消失的 toast：给出明确的出路
    $("#story-flow").innerHTML = `
      <div class="seg">
        <div class="seg-text">
          <b>存档读取失败</b>：${esc(e.message)}<br><br>
          你的进度仍在磁盘上，通常可以从恢复点找回。
        </div>
        <div class="npc-date-action" style="margin-top:12px">
          <button class="btn btn-accent" id="load-retry">重试读取</button>
          <button class="btn btn-ghost" id="load-restore">从恢复点还原</button>
        </div>
      </div>`;
    $("#choices").innerHTML = "";
    $("#load-retry").onclick = () => resume();
    $("#load-restore").onclick = () => $("#btn-backups").click();
  }
}

async function doSignIn() {
  if (busy) return;
  if (!S) { $("#modal").hidden = false; toast("先开始游戏，再签到"); return; }
  setBusy(true);
  try {
    const data = await api("/api/signin");
    S = data.state;
    renderAll();
    toast(data.result.msg);
  } catch (e) {
    toast("签到失败：" + e.message, true);
  } finally {
    setBusy(false);
  }
}

async function newGame() {
  if (busy) return;
  const name = ($("#inp-name").value || "").trim() || "林川";
  const btn = $("#btn-start");
  btn.textContent = "正在生成开局剧情…首次约需 10~30 秒";
  try {
    const data = await api("/api/new", { name, show_affinity: $("#chk-affinity").checked });
    S = data.state;
    endingShown = false;  // 二周目结局弹窗重新可用
    DEMO = !!data.demo_mode;
    $("#demo-badge").hidden = !DEMO;
    $("#modal").hidden = true;
    renderAll(0, true, true);
    await loadCatalog();
    toast(`新的故事开始了。欢迎，${S.player.name}。`);
  } catch (e) {
    toast("开局失败：" + e.message, true);
  } finally {
    btn.textContent = "开始游戏";
  }
}

/* ---------- 赠送礼物 ---------- */

let giftingItem = null;  // 正在选择受赠人的物品名

function openGiftPicker(itemName) {
  giftingItem = itemName;
  const list = $("#gift-pick");
  const npcs = S.npcs || [];
  if (!npcs.length) {
    list.innerHTML = `<div class="dim small">名册上还没有认识的人——先去结识吧。</div>`;
  } else {
    list.innerHTML = npcs.map((n) => {
      const st = npcStage(n.affinity);
      return `<button class="gift-row" data-npc="${esc(n.name)}">
        <span class="gift-row-name">${esc(n.name)}</span>
        <span class="gift-row-role">${esc(n.role)}</span>
        <span class="npc-stage st-${st.idx}">${st.label}</span>
        ${n.likes ? `<span class="gift-row-likes">偏爱${esc(n.likes)}</span>` : ""}
        <span class="gift-row-go">赠送 →</span>
      </button>`;
    }).join("");
  }
  $("#gift-title").textContent = `把『${itemName}』送给谁？`;
  $("#gift-modal").hidden = false;
}

async function confirmGift(npcName, item) {
  const gift = item || giftingItem;
  if (!gift) return;
  try {
    const data = await api("/api/gift", { npc: npcName, item: gift });
    $("#gift-modal").hidden = true;
    $("#npc-modal").hidden = true;
    S = data.state;
    renderAll();
    toast(data.result.msg);
  } catch (e) {
    toast("赠送失败：" + e.message, true);
  }
}

/* ---------- 手机（短信会话） ---------- */

let chatWith = null;  // 当前会话对象名

function renderPhone() {
  const box = $("#phone-list");
  if (!box) return;
  const chats = (S.chats && Object.entries(S.chats)) || [];
  const rows = chats
    .filter(([, c]) => (c.msgs || []).length)
    .map(([name, c]) => {
      const last = c.msgs[c.msgs.length - 1];
      const preview = (last.from === "me" ? "我：" : "") + last.text;
      return { name, preview, ts: last.ts };
    })
    .sort((a, b) => (a.ts < b.ts ? 1 : -1));
  box.innerHTML = rows.length
    ? rows.map((r) => `<button class="phone-row" data-npc="${esc(r.name)}">
        <span class="phone-name">${esc(r.name)}</span>
        <span class="phone-preview">${esc(r.preview.slice(0, 24))}</span>
      </button>`).join("")
    : `<div class="dim small">还没有会话——点人物卡片里的"发消息"开始聊天。</div>`;
}

function openChat(name) {
  chatWith = name;
  $("#chat-title").textContent = `短信 · ${name}`;
  renderChatBody();
  $("#chat-modal").hidden = false;
  $("#chat-input").focus();
}

function renderChatBody(typing) {
  const body = $("#chat-body");
  const msgs = ((S.chats || {})[chatWith] || {}).msgs || [];
  const avaNpc = esc((chatWith || "?").slice(0, 1));
  const row = (me, m, cls = "") =>
    `<div class="chat-row${me ? " me" : ""}">
       <div class="chat-ava ${me ? "me" : "npc"}">${me ? "我" : avaNpc}</div>
       <div class="bub ${me ? "bub-me" : "bub-npc"} ${cls}">
         ${esc(m.text)}
         ${!me && m.image ? `<img class="chat-photo" src="${npcImage(chatWith, m.image)}" alt="${esc(m.image)}">
            <div class="chat-photo-cap">📷 ${esc(m.image)}</div>` : ""}
       </div>
     </div>`;
  body.innerHTML = msgs.map((m) => row(m.from === "me", m)).join("")
    + (typing ? row(false, { text: "对方正在输入…" }, "bub-typing") : "");
  body.scrollTop = body.scrollHeight;
}

async function sendChatMessage() {
  const input = $("#chat-input");
  const text = input.value.trim();
  if (!text || !chatWith || busy) return;
  input.value = "";
  // 先乐观显示我的消息，等待对方回复
  (S.chats = S.chats || {})[chatWith] = S.chats[chatWith] || { msgs: [] };
  S.chats[chatWith].msgs.push({ ts: new Date().toISOString(), from: "me", text });
  renderChatBody(true);
  try {
    const data = await api("/api/chat", { npc: chatWith, text });
    S = data.state;
    renderAll();
    renderChatBody(false);
    if (!data.result.ok) toast(data.result.msg, true);
  } catch (e) {
    // 失败回滚乐观气泡并还回输入——玩家的话不能凭空消失
    const msgs = (S.chats[chatWith] || {}).msgs || [];
    const i = msgs.findIndex((m) => m.from === "me" && m.text === text);
    if (i >= 0) msgs.splice(i, 1);
    renderChatBody(false);
    input.value = text;
    toast("发送失败（消息未发出，已还回输入框）：" + e.message, true);
  }
}

/* ---------- 图鉴 / 成就 / 结局（阶段F） ---------- */

let endingShown = false;

function renderCodex() {
  const people = $("#codex-people");
  if (!people) return;
  const known = S.npcs || [];
  const allKnownCount = known.length;
  const rosterTotal = allKnownCount + 3;  // 未知的花名册余量提示（保守展示）
  people.innerHTML = known.map((n) => {
    const st = npcStage(n.affinity);
    const dates = (S.dates || []).filter((d) => d.npc === n.name).length;
    return `<div class="codex-card">
      <div class="codex-name">${esc(n.name)}</div>
      <div class="dim small">${esc(n.role)}</div>
      <span class="npc-stage st-${st.idx}">${st.label}</span>
      ${dates ? `<div class="dim small">约会 ×${dates}</div>` : ""}
    </div>`;
  }).join("") + `<div class="codex-card codex-unknown"><div class="codex-name">？</div>
    <div class="dim small">尚未相遇的人</div></div>`;
  const places = (S.map && S.map.urban) || [];
  const found = places.filter((p) => p.discovered).length;
  $("#codex-places").textContent =
    `已探明 ${found} / ${places.length} 处${found < places.length ? "——迷雾之下还有未知的角落" : "——这座城已经没有秘密"}`;
  const got = new Set(S.achievements || []);
  const defs = S.achievement_defs || [];
  $("#codex-achievements").innerHTML = defs.map((a) =>
    `<div class="codex-ach-item${got.has(a.id) ? " got" : ""}">
      <b>${got.has(a.id) ? "✦" : "✧"} ${esc(a.title)}</b>
      <span class="dim small">${got.has(a.id) ? esc(a.desc) : "？？？"}</span>
    </div>`).join("");
}

function maybeShowEnding() {
  if (!S || !S.ending || endingShown) return;
  endingShown = true;
  $("#ending-title").textContent = `大结局 ·《${S.ending.title}》`;
  $("#ending-text").textContent = S.ending.partner
    ? `这一程的终点，身边站着${S.ending.partner}（好感 ${S.ending.affinity}）。`
    : "这一程的终点，你选择了属于自己的人生。";
  $("#ending-modal").hidden = false;
}

/* ---------- 事件绑定与启动 ---------- */

function bind() {
  $("#btn-act").onclick = () => {
    const t = $("#free-input").value.trim();
    if (t) act(t);
  };
  $("#free-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) $("#btn-act").click();
  });
  $("#btn-signin").onclick = doSignIn;
  $("#sys-btn-signin").onclick = doSignIn;
  $("#btn-sys").onclick = () => openSysModal();
  $("#bag-card-title").onclick = () => openSysModal("bag");
  $("#sys-modal-close").onclick = closeSysModal;
  $("#sys-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeSysModal();
  });
  $$(".sys-tab").forEach((t) => {
    t.onclick = () => switchSysTab(t.dataset.tab);
  });
  $("#shop-cats").addEventListener("click", (e) => {
    const c = e.target.closest(".shop-cat");
    if (!c) return;
    shopCat = c.dataset.cat;
    renderSys();
  });
  $("#lot-draw").onclick = drawLottery;
  $("#sys-shop").addEventListener("click", async (e) => {
    const b = e.target.closest(".shop-buy");
    if (!b || busy || b.disabled) return;
    try {
      const data = await api("/api/buy", { name: b.dataset.name });
      S = data.state;
      renderAll();
      toast(data.result.msg);
    } catch (err) {
      toast("购买失败：" + err.message, true);
    }
  });
  $("#sys-bag").addEventListener("click", async (e) => {
    const storyUse = e.target.closest(".bag-story");
    if (storyUse && !busy) {
      closeSysModal();
      act(`尝试使用『${storyUse.dataset.name}』处理眼前的情况；如当前不需要使用则保留物品。`);
      return;
    }
    const use = e.target.closest(".bag-use");
    if (use && !busy) {
      if (use.dataset.name === "系统抽奖券") {
        // 抽奖券走独立抽奖面板，不直接在背包里抽
        switchSysTab("lottery");
        if (!LOTTERY) loadLottery();
        return;
      }
      try {
        const data = await api("/api/use", { name: use.dataset.name });
        S = data.state;
        renderAll();
        toast(data.result.msg);
      } catch (err) {
        toast("使用失败：" + err.message, true);
      }
      return;
    }
    const sell = e.target.closest(".bag-sell");
    if (sell && !busy) {
      try {
        const data = await api("/api/sell", { name: sell.dataset.name });
        S = data.state;
        renderAll();
        toast(data.result.msg);
      } catch (err) {
        toast("卖出失败：" + err.message, true);
      }
      return;
    }
    const gift = e.target.closest(".bag-gift");
    if (gift && !busy) {
      closeSysModal();
      openGiftPicker(gift.dataset.name);
    }
  });
  $("#gift-close").onclick = () => ($("#gift-modal").hidden = true);
  $("#gift-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) ($("#gift-modal").hidden = true);
    const row = e.target.closest(".gift-row");
    if (row) confirmGift(row.dataset.npc);
  });
  $("#sys-equip").addEventListener("click", async (e) => {
    const b = e.target.closest("button.unequip");
    if (!b || busy) return;
    try {
      const data = await api("/api/unequip", { slot: b.dataset.slot });
      S = data.state;
      renderAll();
      toast(data.result.msg);
    } catch (err) {
      toast("卸装失败：" + err.message, true);
    }
  });
  $("#sys-bag").addEventListener("click", async (e) => {
    const eq = e.target.closest(".bag-equip");
    if (eq && !busy) {
      try {
        const data = await api("/api/equip", { name: eq.dataset.name });
        S = data.state;
        renderAll();
        toast(data.result.msg);
      } catch (err) {
        toast("装备失败：" + err.message, true);
      }
    }
  });
  $("#relations").addEventListener("click", (e) => {
    const card = e.target.closest(".npc-card");
    if (card) showNpcDetail(card.dataset.name);
  });
  $("#npc-modal-close").onclick = () => ($("#npc-modal").hidden = true);
  $("#npc-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) ($("#npc-modal").hidden = true);
  });
  $("#npc-m-body").addEventListener("click", (e) => {
    const gc = e.target.closest(".npc-gift-chip");
    if (gc) {
      confirmGift(gc.dataset.npc, gc.dataset.item);
      return;
    }
    const btn = e.target.closest(".btn-invite-date");
    if (btn && !btn.disabled && !busy) {
      $("#npc-modal").hidden = true;
      act(`【约会】邀请${btn.dataset.npc}来一场正式的约会`);
      return;
    }
    const msg = e.target.closest(".btn-msg-npc");
    if (msg && !busy) {
      $("#npc-modal").hidden = true;
      openChat(msg.dataset.npc);
    }
  });
  $("#phone-list").addEventListener("click", (e) => {
    const row = e.target.closest(".phone-row");
    if (row) openChat(row.dataset.npc);
  });
  $("#chat-close").onclick = () => ($("#chat-modal").hidden = true);
  $("#chat-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) ($("#chat-modal").hidden = true);
  });
  $("#chat-send").onclick = sendChatMessage;
  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) sendChatMessage();
  });
  const inboxClick = (e) => {
    const btn = e.target.closest(".inbox-reply");
    if (btn) { openChat(btn.dataset.npc); return; }
    const item = e.target.closest(".inbox-item");
    if (item) openMsgDetail(item.dataset.ts || "", item.dataset.title || "");
  };
  $("#inbox").addEventListener("click", inboxClick);
  $("#moments").addEventListener("click", inboxClick);
  $("#msg-modal-close").onclick = () => ($("#msg-modal").hidden = true);
  $("#msg-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) ($("#msg-modal").hidden = true);
  });
  $("#ending-close").onclick = () => ($("#ending-modal").hidden = true);
  $("#chk-affinity").onchange = async (e) => {
    if (!S || busy) return;
    try {
      const data = await api("/api/settings", { show_affinity: e.target.checked });
      S = data.state;
      renderRelations();
    } catch (err) {
      toast("设置失败：" + err.message, true);
    }
  };
  $("#btn-new").onclick = () => {
    if (busy) return;
    if (S && S.story.length && !confirm("开始新游戏会覆盖当前存档，确定吗？")) return;
    $("#modal").hidden = false;
  };
  $("#btn-start").onclick = newGame;
  $("#btn-cancel-new").onclick = () => {
    if (S) { $("#modal").hidden = true; return; }
    // 无存档时这是唯一的开始入口——不关闭，只解释
    toast("还没有存档——写下名字，点「开始游戏」开启你的故事");
  };
  $("#chk-typing").checked = localStorage.getItem("sjl-typing") !== "off";
  $("#chk-typing").onchange = (e) => {
    localStorage.setItem("sjl-typing", e.target.checked ? "on" : "off");
    if (!e.target.checked) $("#btn-reveal").click();
  };
  $("#btn-reveal").onclick = () => {
    clearInterval(typingTimer);
    const last = document.querySelector("#story-flow .seg:last-child .seg-text");
    if (last && last.dataset.fullText) last.textContent = last.dataset.fullText;
  };
  $("#btn-history").onclick = async () => {
    $("#history-modal").hidden = false;
    $("#history-title").textContent = "往事回看";
    $("#history-body").textContent = "正在读取往事……";
    try {
      const response = await fetch("/api/history");
      if (!response.ok) throw new Error("读取失败");
      const data = await response.json();
      const all = [...data.entries, ...(S?.story || [])];
      const dates = new Map((data.dates || []).map((d) => [d.turn, d.npc]));
      $("#history-body").innerHTML = all.map((s) => {
        const tag = dates.has(s.turn)
          ? `<div class="seg-date" title="约会回忆">❤ 与${esc(dates.get(s.turn))}的约会</div>` : "";
        return `<div class="hist-entry">${tag}第${s.turn}幕<br>${esc(s.text)}${s.chosen ? `<br><span class="dim">行动：${esc(s.chosen)}</span>` : ""}</div>`;
      }).join('<hr class="hist-sep">') || "还没有故事。";
    } catch (err) { $("#history-body").textContent = "往事读取失败，请关闭后重试。"; }
  };
  $("#btn-backups").onclick = async () => {
    $("#history-modal").hidden = false;
    $("#history-title").textContent = "恢复存档";
    $("#history-body").textContent = "正在读取存档备份……";
    try {
      const response = await fetch("/api/backups");
      if (!response.ok) throw new Error("读取失败");
      const data = await response.json();
      // 备份号 20261019T224915123456 → 「10-19 22:49」玩家可读
      const fmt = (id) => {
        const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/.exec(String(id));
        return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : String(id);
      };
      $("#history-body").innerHTML = data.backups.map((b) =>
        `<p>💾 第${b.turn}回合 · ${esc(fmt(b.id))} <button class="btn restore-save" data-id="${esc(b.id)}">恢复</button></p>`).join("") || "还没有恢复点——每个剧情回合都会自动留档，先去推进一段故事吧（最近 50 份可恢复）。";
    } catch (err) { $("#history-body").textContent = "备份读取失败，请关闭后重试。"; }
  };
  $("#history-body").addEventListener("click", async (e) => {
    const button = e.target.closest(".restore-save");
    if (!button || busy || !confirm("恢复此进度？当前进度会先自动备份。")) return;
    try {
      const data = await api("/api/restore", {name:button.dataset.id});
      S = data.state;
      $("#history-modal").hidden = true;
      renderAll(0, true);
      toast(data.system_notice);
    } catch (err) { toast("恢复失败：" + err.message, true); }
  });
  $("#history-close").onclick = () => $("#history-modal").hidden = true;
  document.addEventListener("click", (e) => {
    if (e.target.closest(".catalog-retry")) loadCatalog();
  });
  $$(".mobile-tab").forEach((b) => b.onclick = () => {
    document.body.dataset.mobile = b.dataset.panel;
    $$(".mobile-tab").forEach((t) => t.setAttribute("aria-pressed", String(t === b)));
  });
  $("#inp-name").addEventListener("keydown", (e) => {
    if (e.key === "Enter") newGame();
  });
  $$(".theme-dot").forEach((d) => {
    d.onclick = () => {
      applyTheme(d.dataset.theme);
      toast(`界面风格：${THEME_NAMES[d.dataset.theme]}`);
    };
  });
  $("#map-canvas").addEventListener("click", (e) => {
    const g = e.target.closest("g.mplace");
    if (!g) return;  // 点空白不开大图——入口只在地标上
    openMapModal(g.dataset.place);
  });
  $("#map-canvas-big").addEventListener("click", (e) => {
    // 三级钻取：世界→国家→城市→地点
    const country = e.target.closest("g.mcountry");
    if (country) { mapLevel = "country"; mapCountry = country.dataset.country; $("#map-detail").hidden = true; renderBigMap(); return; }
    const city = e.target.closest("g.mcity");
    if (city) { mapLevel = "city"; mapCity = city.dataset.city; $("#map-detail").hidden = true; renderBigMap(); return; }
    const place = e.target.closest("g.mplace");
    if (place) showPlaceDetail(place.dataset.city || mapCity, place.dataset.place);
  });
  $("#map-crumbs").addEventListener("click", (e) => {
    const c = e.target.closest("button.crumb");
    if (!c || !c.dataset.lv) return;
    mapLevel = c.dataset.lv;
    $("#map-detail").hidden = true;
    renderBigMap();
  });
  $("#map-detail").addEventListener("click", (e) => {
    const go = e.target.closest("button.md-go");
    if (go && !busy) {
      closeMapModal();
      act(`前往『${go.dataset.place}』`);
      return;
    }
    const ex = e.target.closest("button.md-explore");
    if (ex && !busy) {
      const place = S.player.location?.place || "此地";
      closeMapModal();
      act(`探索『${place}』周边，寻找机缘与发现`);
    }
  });
  $$(".quick-row .chip").forEach((c) => {
    c.onclick = () => {
      if (busy) return;
      if (!S) { $("#modal").hidden = false; toast("先开始游戏，再行动"); return; }
      const place = (S.player.location && S.player.location.place) || "此地";
      if (c.dataset.qa === "cultivate") act("投入训练——健身或自习，稳步提升自己");
      else if (c.dataset.qa === "explore") act(`探索『${place}』周边，寻找机缘与发现`);
      else act("警惕地环顾四周，观察人与环境的细节");
    };
  });
  $("#map-modal-close").onclick = closeMapModal;
  $("#map-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeMapModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      const target = e.target.closest('.npc-card[role="button"], .mplace[role="button"]');
      if (target) { e.preventDefault(); target.dispatchEvent(new MouseEvent("click", {bubbles:true})); }
    }
    const dialogs = [...$$('[role="dialog"]')].filter((d) => !d.hidden);
    const dialog = dialogs[dialogs.length - 1];
    if (e.key === "Tab" && dialog) {
      const fields = [...dialog.querySelectorAll('button:not(:disabled), input:not(:disabled), [tabindex="0"]')].filter((el) => el.getClientRects().length);
      const first = fields[0], last = fields[fields.length - 1];
      if (e.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) { e.preventDefault(); last?.focus(); }
      else if (!e.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) { e.preventDefault(); first?.focus(); }
    }
    if (e.key !== "Escape") return;
    if (!$("#map-modal").hidden) closeMapModal();
    if (!$("#sys-modal").hidden) closeSysModal();
    if (!$("#npc-modal").hidden) ($("#npc-modal").hidden = true);
    $("#gift-modal").hidden = true;
    $("#chat-modal").hidden = true;
    $("#history-modal").hidden = true;
    if (S && !busy) $("#modal").hidden = true;
  });
  $$('[role="dialog"]').forEach((dialog) => {
    let restoreFocus = null;
    new MutationObserver(() => {
      if (!dialog.hidden) {
        restoreFocus = document.activeElement;
        dialog.querySelector('input, button')?.focus();
      } else if (restoreFocus?.isConnected) restoreFocus.focus();
    }).observe(dialog, {attributes:true, attributeFilter:["hidden"]});
  });
}

async function init() {
  try { applyTheme(localStorage.getItem("sjl-theme")); }
  catch (e) { /* 隐私模式/存储异常不该废掉整页 */ }
  bind();
  loadCatalog();
  try {
    const response = await fetch("/api/state");
    const info = await response.json();
    if (!response.ok) throw new Error(info.detail || "状态读取失败");
    DEMO = !!info.demo_mode;
    $("#demo-badge").hidden = !DEMO;
    if (info.exists) {
      await resume();
    } else {
      $("#modal").hidden = false;
    }
  } catch (e) {
    toast("无法连接服务：" + e.message, true);
  }
}

init();
