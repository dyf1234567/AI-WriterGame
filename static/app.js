/* 双界录 前端逻辑：三栏分格 + 阅读式剧情流 + 地图系统 + 点击式风格切换 */
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const REALMS = ["凡人", "炼气", "筑基", "金丹", "元婴", "化神", "炼虚", "合体", "大乘", "渡劫", "飞升"];
const WORLD_NAMES = { urban: "都市", xianxia: "修仙界" };
const THEME_NAMES = { night: "深夜", ink: "墨纸", parchment: "羊皮卷", qinglan: "青岚" };
const PLACE_TYPES = { city: "城市", town: "城镇", sect: "宗门", wild: "荒野", secret: "秘境", sea: "海域" };

let S = null;            // 服务端状态镜像
let busy = false;        // 回合进行中
let typingTimer = null;  // 打字机定时器
let mapView = null;      // 地图卡片当前查看的世界（null = 跟随玩家所在世界）
let SHOP = null;         // 商城目录缓存
let ALCHEMY = null;      // 炼丹配方缓存
let pendingRequest = false;
let catalogError = "";
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const EQUIP_SLOTS = ["武器", "防具", "法宝", "足履"];

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

/* ---------- 基础请求 ---------- */

async function api(path, body) {
  if (pendingRequest) throw new Error("上一操作尚未完成，请稍候。");
  pendingRequest = true;
  setBusy(true);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 75000);
  try {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json",
      ...(S && path !== "/api/resume" ? {"X-State-Revision": String(S.revision)} : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: controller.signal,
  });
  if (!r.ok) {
    let detail = "";
    try { detail = (await r.json()).detail || ""; } catch (e) { /* ignore */ }
    throw new Error(detail || `请求失败（HTTP ${r.status}）`);
  }
  return await r.json();
  } catch (err) {
    if (err.name === "AbortError") throw new Error("等待已超时，请刷新确认最新进度后再操作。");
    throw err;
  } finally {
    clearTimeout(timer);
    pendingRequest = false;
    setBusy(false);
  }
}

function setBusy(v) {
  busy = v;
  $("#btn-act").disabled = v;
  $("#btn-act").textContent = v ? "推演中…" : "行 动";
  $("#free-input").disabled = v;
  $("#btn-cross").disabled = v;
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
    ALCHEMY = data.recipes;
    catalogError = "";
  } catch (err) {
    catalogError = "目录暂未加载成功，请点击重试。";
  }
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
  return `<span class="${cls}${world === "xianxia" ? " xianxia" : ""}">${WORLD_NAMES[world] || world}</span>`;
}

function renderHeader() {
  const chip = $("#world-chip");
  const loc = (S.player.location || {});
  chip.textContent = WORLD_NAMES[S.player.world] || S.player.world;
  if (loc.place) chip.textContent += ` · ${loc.place}`;
  chip.classList.toggle("xianxia", S.player.world === "xianxia");
  $("#chk-affinity").checked = !!S.settings.show_affinity;
}

/* ---------- 可视化地图 ---------- */

function hashPos(name) {
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return { x: 12 + (h % 76), y: 18 + ((h >>> 8) % 62) };
}

const MAP_DEFS = `
  <defs>
    <radialGradient id="fogGrad">
      <stop offset="0%" stop-color="rgba(0,0,0,.85)"/>
      <stop offset="50%" stop-color="rgba(0,0,0,.58)"/>
      <stop offset="85%" stop-color="rgba(0,0,0,.2)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
    <filter id="fogBlur" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="5"/>
    </filter>
    <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="3.5"/>
    </filter>
    <filter id="mistBlur" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="8"/>
    </filter>
    <radialGradient id="hereGrad">
      <stop offset="0%" stop-color="rgba(255,209,102,.30)"/>
      <stop offset="55%" stop-color="rgba(255,209,102,.12)"/>
      <stop offset="100%" stop-color="rgba(255,209,102,0)"/>
    </radialGradient>
  </defs>`;

/* 罗盘装饰 */
function compass(x, y) {
  return `<g class="compass" transform="translate(${x},${y})">
    <circle r="11" class="cp-ring"/>
    <circle r="7" class="cp-ring" opacity=".55"/>
    <path d="M0,-14 L3,0 L0,14 L-3,0 Z" class="cp-needle"/>
    <path d="M-14,0 L0,3 L14,0 L0,-3 Z" class="cp-needle" opacity=".5"/>
    <circle r="1.4" class="cp-hub"/>
    <text y="-17" text-anchor="middle" class="cp-n">N</text>
  </g>`;
}

const MAP_BG = {
  urban: `
    <rect width="400" height="260" class="map-water"/>
    <g class="graticule">
      <line x1="0" y1="52" x2="400" y2="52"/><line x1="0" y1="130" x2="400" y2="130"/><line x1="0" y1="208" x2="400" y2="208"/>
      <line x1="100" y1="0" x2="100" y2="260"/><line x1="200" y1="0" x2="200" y2="260"/><line x1="300" y1="0" x2="300" y2="260"/>
    </g>
    <g filter="url(#softGlow)" opacity=".4">
      <path class="coast" d="M26,78 Q34,42 84,34 Q128,28 138,54 Q144,74 126,84 Q140,102 124,116 Q104,130 72,122 Q40,132 26,110 Q16,94 26,78 Z"/>
      <path class="coast" d="M156,96 Q168,66 208,62 Q244,58 252,86 Q258,108 236,120 Q210,132 178,126 Q154,120 156,96 Z"/>
      <path class="coast" d="M268,116 Q296,86 340,96 Q376,104 378,134 Q380,162 348,172 Q310,180 280,160 Q262,146 268,116 Z"/>
    </g>
    <g class="land">
      <path d="M26,78 Q34,42 84,34 Q128,28 138,54 Q144,74 126,84 Q140,102 124,116 Q104,130 72,122 Q40,132 26,110 Q16,94 26,78 Z"/>
      <path d="M156,96 Q168,66 208,62 Q244,58 252,86 Q258,108 236,120 Q210,132 178,126 Q154,120 156,96 Z"/>
      <path d="M268,116 Q296,86 340,96 Q376,104 378,134 Q380,162 348,172 Q310,180 280,160 Q262,146 268,116 Z"/>
      <ellipse cx="344" cy="34" rx="15" ry="7"/>
      <ellipse cx="363" cy="45" rx="8" ry="4"/>
      <ellipse cx="331" cy="47" rx="6" ry="3.5"/>
    </g>
    <g class="highland">
      <ellipse cx="72" cy="62" rx="24" ry="10"/>
      <ellipse cx="204" cy="88" rx="17" ry="8"/>
      <ellipse cx="322" cy="134" rx="26" ry="10"/>
    </g>
    ${compass(32, 226)}`,
  xianxia: `
    <rect width="400" height="260" class="map-water xs"/>
    <path d="M0,212 C80,194 150,224 220,206 C290,190 345,214 400,198 L400,260 L0,260 Z" class="xs-base"/>
    <g class="xs-ridge" opacity=".35">
      <path d="M6,100 L34,62 L56,92 L82,50 L106,94 L128,68 L150,98 L172,74 L198,102 L222,58 L248,96 L270,74 L294,104 L320,56 L346,98 L370,74 L394,102 L394,150 L6,150 Z"/>
    </g>
    <g class="xs-ridge" opacity=".62">
      <path d="M14,120 L44,78 L66,108 L96,66 L124,112 L148,84 L176,118 L206,72 L238,116 L266,88 L298,120 L330,78 L362,116 L392,92 L392,158 L14,158 Z"/>
    </g>
    <g class="mist" filter="url(#mistBlur)">
      <ellipse cx="120" cy="96" rx="52" ry="11"/>
      <ellipse cx="250" cy="120" rx="60" ry="12"/>
      <ellipse cx="330" cy="70" rx="44" ry="9"/>
    </g>
    <g class="river">
      <path d="M186,212 C158,178 148,156 158,116"/>
      <path d="M264,124 C230,120 192,110 162,126"/>
    </g>
    <g class="array-ring">
      <circle cx="200" cy="208" r="24"/>
      <circle cx="200" cy="208" r="17"/>
      <path d="M200,180 v6 M200,230 v6 M172,208 h6 M222,208 h6"/>
    </g>
    ${compass(368, 224)}`,
};

/* 已探明城市间的航线（虚线弧） */
const MAP_ROUTES = {
  urban: [["青临市", "云京古都"], ["云京古都", "东澜自由港"]],
  xianxia: [["青玄宗·山门", "青禾坊市"], ["白溪镇", "青玄宗·山门"], ["青禾坊市", "青玄宗·丹房"]],
};

function mapSVG(view) {
  const loc = S.player.location || {};
  const places = S.map[view] || [];
  const coords = {};
  places.forEach((p) => {
    if (p.discovered) {
      const pos = (typeof p.x === "number" && typeof p.y === "number")
        ? { x: p.x, y: p.y } : hashPos(p.name);
      coords[p.name] = [Math.round(pos.x * 4), Math.round(pos.y * 2.6)];
    }
  });
  const routes = (MAP_ROUTES[view] || [])
    .filter(([a, b]) => coords[a] && coords[b])
    .map(([a, b]) => {
      const [x1, y1] = coords[a], [x2, y2] = coords[b];
      const mx = Math.round((x1 + x2) / 2), my = Math.round(Math.min(y1, y2) - 24);
      return `<path class="route" d="M${x1},${y1} Q${mx},${my} ${x2},${y2}"/>`;
    }).join("");

  // 地名避让：按文字包围盒检测，放不下就挪到圆点下方或更高处
  const boxes = [];
  const labelY = (p, px, py) => {
    const w = [...p.name].length * 12 + 8;
    const put = (ly) => ({ x1: px - w / 2, x2: px + w / 2, y1: py + ly - 5, y2: py + ly + 5, ly });
    const hit = (b) => boxes.some((o) => b.x1 < o.x2 && b.x2 > o.x1 && b.y1 < o.y2 && b.y2 > o.y1);
    for (const ly of [-12, 16, -26]) {
      const b = put(ly);
      if (!hit(b)) { boxes.push(b); return ly; }
    }
    boxes.push(put(-12));
    return -12;
  };

  const markers = places.map((p) => {
    const pos = (typeof p.x === "number" && typeof p.y === "number")
      ? { x: p.x, y: p.y } : hashPos(p.name);
    const px = Math.round(pos.x * 4), py = Math.round(pos.y * 2.6);
    if (!p.discovered) {
      return `<g class="fog" transform="translate(${px},${py})">
        <circle r="36" fill="url(#fogGrad)" filter="url(#fogBlur)"/>
        <text y="4" text-anchor="middle" class="fog-q">？</text>
      </g>`;
    }
    const cur = loc.world === view && loc.place === p.name;
    return `<g class="mplace" role="button" tabindex="0" aria-label="查看${esc(p.name)}" data-world="${view}" data-place="${esc(p.name)}" transform="translate(${px},${py})">
      <title>${esc(p.desc || p.name)}</title>
      ${cur ? '<circle class="mp-here" r="30" fill="url(#hereGrad)"/><circle class="mp-cur" r="9"/>' : ""}
      <circle class="mp-halo" r="7.5"/>
      <circle class="mp-dot" r="3.4"/>
      <text class="mp-label${cur ? " mp-label-cur" : ""}" y="${labelY(p, px, py)}" text-anchor="middle">${esc(p.name)}</text>
    </g>`;
  }).join("");

  return `<svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg">${MAP_DEFS}${MAP_BG[view] || ""}${routes}${markers}</svg>`;
}

function renderMap() {
  const loc = S.player.location || {};
  const view = (mapView && S.map[mapView]) ? mapView : S.player.world;
  $("#map-now").textContent = `当前位置：${WORLD_NAMES[loc.world || S.player.world]} · ${loc.place || "未知"}`;
  $$("#map-tabs .map-tab").forEach((b) =>
    b.classList.toggle("active", b.dataset.world === view));
  $("#map-canvas").innerHTML = mapSVG(view);
}

/* ---------- 地图大图查看界面 ---------- */

let mapModalView = null;

function openMapModal(view, focusPlace) {
  mapModalView = view || S.player.world;
  $("#map-modal").hidden = false;
  renderBigMap();
  if (focusPlace) {
    showPlaceDetail(mapModalView, focusPlace);
  } else {
    $("#map-detail").hidden = true;
  }
}

function closeMapModal() {
  $("#map-modal").hidden = true;
}

function renderBigMap() {
  const loc = S.player.location || {};
  $("#map-now-big").textContent = `当前位置：${WORLD_NAMES[loc.world || S.player.world]} · ${loc.place || "未知"}`;
  $$("#map-tabs-big .map-tab").forEach((b) =>
    b.classList.toggle("active", b.dataset.world === mapModalView));
  $("#map-canvas-big").innerHTML = mapSVG(mapModalView);
}

function showPlaceDetail(view, name) {
  const p = (S.map[view] || []).find((x) => x.name === name);
  if (!p) return;
  const loc = S.player.location || {};
  const isCur = loc.world === view && loc.place === name;
  const cross = view !== S.player.world;
  const hereNpcs = (S.npcs || []).filter((n) => n.place === name).map((n) => n.name);
  const detail = $("#map-detail");
  detail.hidden = false;
  detail.innerHTML = `
    <div class="md-head">
      <span class="md-name">${esc(name)}</span>
      ${worldChip(view)}
      ${p.type ? `<span class="md-type">${PLACE_TYPES[p.type] || p.type}</span>` : ""}
      ${isCur ? `<span class="md-cur">◈ 当前所在</span>` : ""}
    </div>
    <div class="md-desc dim">${esc(p.desc || "这里还没有留下任何记载。")}</div>
    ${hereNpcs.length ? `<div class="md-npcs">常在此地：${hereNpcs.map(esc).join("、")}</div>` : ""}
    <div class="md-actions">
      ${view === S.player.world ? `<button class="btn btn-ghost md-explore">🔎 在此探索</button>` : ""}
      ${!isCur ? `<button class="btn btn-accent md-go" data-place="${esc(name)}" data-world="${view}">${cross ? "先返回该界（原落点）" : "前往此地"}</button>` : ""}
    </div>`;
}

function renderSystem() {
  const p = S.player;
  $("#realm-name").textContent = REALMS[p.realm] || "？？";
  $("#realm-progress-num").textContent = p.realm_progress + "%";
  $("#realm-bar").style.width = p.realm_progress + "%";
  const idt = p.identity || {};
  const idLine = $("#identity-line");
  idLine.textContent = idt[p.world] || "尚无正式身份";
  idLine.title = `都市：${idt.urban || "尚无"}　｜　修仙界：${idt.xianxia || "尚无"}`;
  const tech = p.technique;
  $("#technique-line").textContent = tech && tech.name
    ? `${tech.route || "未定路线"}·《${tech.name}》${tech.grade ? `（${tech.grade}）` : ""}`
    : "初始功法待领取——在剧情里表达修炼意向";
  const bonus = statBonus();
  $("#stats").innerHTML = Object.entries(p.stats)
    .map(([k, v]) => `<div class="stat"><span>${k}</span><b>${v}${bonus[k] ? `<i class="stat-b">+${bonus[k]}</i>` : ""}</b></div>`)
    .join("");

  const today = S.server_date;
  const signed = S.last_sign_in === today;
  const btn = $("#btn-signin");
  btn.textContent = signed ? "今日已签到" : "今日签到";
  btn.dataset.signed = signed ? "1" : "0";
  btn.disabled = signed || busy;
}

function questHTML() {
  const mq = S.main_quest;
  const notes = (mq.notes || []).slice(-3);
  const main = `<div class="q-title">★ ${esc(mq.title)}（第${mq.stage}阶段 · 随境界推进）</div>
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

function itemIcon(name) {
  if (name.includes("灵石")) return "💎";
  if (name.includes("剑")) return "🗡";
  if (name.includes("镜")) return "🛡";
  if (name.includes("靴")) return "👟";
  if (name.includes("符")) return "📿";
  if (name.includes("玉简")) return "🪶";
  if (name.includes("袋")) return "👝";
  if (name.includes("灵芝")) return "🍄";
  if (name.includes("矿石")) return "🪨";
  if (name.includes("妖丹")) return "🔮";
  if (name.includes("茶")) return "🍵";
  if (name.includes("香")) return "🕯";
  if (name.includes("散") || name.includes("露")) return "⚗";
  if (name.includes("液")) return "🧫";
  if (name.includes("残页") || name.includes("诀")) return "📜";
  if (name.includes("丹")) return "🧪";
  return "🧰";
}

function renderSys() {
  if (!S) return;
  const p = S.player;
  $("#sys-realm-name").textContent = REALMS[p.realm] || "？？";
  $("#sys-realm-pct").textContent = p.realm_progress + "%";
  $("#sys-realm-bar").style.width = p.realm_progress + "%";
  const bonus = statBonus();
  $("#sys-stats").innerHTML = Object.entries(p.stats)
    .map(([k, v]) => `<div class="stat"><span>${k}</span><b>${v}${bonus[k] ? `<i class="stat-b">+${bonus[k]}</i>` : ""}</b></div>`)
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
        const sellable = !!goods && i.name !== "下品灵石";
        return `<div class="bag-item" title="${esc(i.desc || "")}">
          <div class="bag-icon">${itemIcon(i.name)}</div>
          <div class="bag-name">${esc(i.name)}</div>
          <div class="bag-count">×${i.count}</div>
          <div class="bag-ops">
            ${usable ? `<button class="bag-use" data-name="${esc(i.name)}">使用</button>` : ""}
            ${storyUse ? `<button class="bag-story" data-name="${esc(i.name)}">在剧情中使用</button>` : ""}
            ${equippable ? `<button class="bag-equip" data-name="${esc(i.name)}">装备</button>` : ""}
            ${sellable ? `<button class="bag-sell" data-name="${esc(i.name)}" title="半价回收">卖出</button>` : ""}
          </div>
        </div>`;
      }).join("")
    : `<div class="dim small">空空如也。签到和探索都能获得物品。</div>`;

  // 炼丹页
  const owned = Object.fromEntries(p.items.map((i) => [i.name, i.count]));
  const recipes = (ALCHEMY || []).map((r) => {
    const need = Object.entries(r.need).map(([name, count]) => ({name, count, have:owned[name] || 0}));
    return {...r, need, ok:need.every((n) => n.have >= n.count)};
  });
  $("#sys-alchemy").innerHTML = recipes.length
    ? recipes.map((r) => {
        const need = r.need.map((n) =>
          `<span class="${n.have >= n.count ? "need-ok" : "need-lack"}">${n.name} ×${n.count}（有${n.have}）</span>`).join("、");
        return `<div class="recipe-item">
          <div class="recipe-head">
            <span class="bag-icon">${itemIcon(r.name)}</span>
            <span class="recipe-name">${r.name}</span>
            <button class="btn btn-accent craft-btn" data-name="${r.name}"${r.ok ? "" : " disabled"}>炼制</button>
          </div>
          <div class="dim small">${r.desc}</div>
          <div class="recipe-need">${need}</div>
        </div>`;
      }).join("")
    : `<div class="dim small">${catalogError || "丹方加载中……"}</div><button class="catalog-retry btn">重试加载</button>`;

  const spirit = p.items.find((i) => i.name === "下品灵石");
  const cur = spirit ? spirit.count : 0;
  $("#sys-currency").textContent = `持有：💎 下品灵石 ×${cur}（商城通货；背包内商品可半价卖出）`;
  $("#sys-shop").innerHTML = (SHOP || []).map((g) => `
    <div class="shop-item" title="${g.desc}">
      <div class="bag-icon">${itemIcon(g.name)}</div>
      <div class="bag-name">${g.name}</div>
      <div class="shop-desc dim small">${g.desc}</div>
      <div class="shop-foot">
        <span class="shop-price">💎${g.price}</span>
        <button class="btn btn-accent shop-buy" data-name="${g.name}"${cur < g.price ? " disabled" : ""}>购买</button>
      </div>
    </div>`).join("") || `<div class="dim small">${catalogError || "商城目录加载中……"}</div><button class="catalog-retry btn">重试加载</button>`;
  const today = S.server_date;
  const signed = S.last_sign_in === today;
  const sb = $("#sys-btn-signin");
  sb.textContent = signed ? "今日已签到" : "今日签到";
  sb.disabled = signed || busy;
  if (busy) $$(".bag-use, .bag-story, .bag-equip, .bag-sell, .shop-buy, .craft-btn").forEach((b) => b.disabled = true);
}

function switchSysTab(name) {
  $$(".sys-tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".sys-pane").forEach((p) => p.classList.toggle("active", p.id === `sys-tab-${name}`));
}

function openSysModal(tab) {
  renderSys();
  $("#sys-modal").hidden = false;
  switchSysTab(tab || "status");
}

function closeSysModal() {
  $("#sys-modal").hidden = true;
}

/* ---------- NPC 详情弹窗 ---------- */

function showNpcDetail(name) {
  const n = (S.npcs || []).find((x) => x.name === name);
  if (!n) return;
  $("#npc-m-title").innerHTML =
    `<span class="md-name" style="font-size:20px">${esc(n.name)}</span>
     ${worldChip(n.world)}
     <span class="md-type">${esc(n.role)}</span>
     <span class="md-cur">${esc(n.label)}</span>`;
  const show = !!S.settings.show_affinity;
  const rels = Object.entries(n.rels || {})
    .map(([k, v]) => `<div class="npc-mem"><b>${esc(k)}</b>：${esc(v)}</div>`).join("");
  $("#npc-m-body").innerHTML = `
    <div class="npc-persona">${esc(n.persona)}</div>
    ${show ? `<div class="npc-aff"><div class="bar"><div class="bar-fill" style="width:${n.affinity}%"></div></div>
       <span class="npc-aff-num">${n.affinity}</span></div>` : ""}
    <div class="npc-sec">◈ 常在地</div>
    <div class="npc-mem">${esc(n.place || "行踪不定")}</div>
    <div class="npc-sec">◈ 近期记忆</div>
    ${n.memory && n.memory.length
      ? n.memory.map((m) => `<div class="npc-mem">${esc(m)}</div>`).join("")
      : `<div class="dim small">尚无深刻记忆——去创造吧。</div>`}
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
  typingTimer = setInterval(() => {
    i = Math.min(text.length, i + 2);
    el.textContent = text.slice(0, i);
    // 只有读者本来就在底部时才跟随滚动，避免打断用户滚动/点击
    if (nearBottom()) flow.scrollTop = flow.scrollHeight;
    if (i >= text.length) clearInterval(typingTimer);
  }, 18);
}

function renderStory(animate = false) {
  const flow = $("#story-flow");
  flow.innerHTML = "";
  if (!S.story.length) {
    flow.innerHTML = `<div class="dim small">故事尚未开始。</div>`;
    $("#choices").innerHTML = "";
    return;
  }
  S.story.forEach((seg, idx) => {
    const div = document.createElement("div");
    div.className = "seg";
    const head = document.createElement("div");
    head.className = "seg-head";
    head.innerHTML = `<span>第${seg.turn}幕</span>${worldChip(seg.world)}`;
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
  const show = !!S.settings.show_affinity;
  $("#relations").innerHTML = S.npcs
    .map((n) => {
      const rels = Object.entries(n.rels || {})
        .map(([k, v]) => `与<b>${esc(k)}</b>：${esc(v)}`)
        .join("<br>");
      return `<div class="npc-card" role="button" tabindex="0" aria-label="查看${esc(n.name)}档案" data-name="${esc(n.name)}" title="点击查看详情">
        <div class="npc-head">
          <span class="npc-name">${esc(n.name)}</span>
          ${worldChip(n.world)}
          <span class="npc-role">${esc(n.role)}</span>
          <span class="npc-label">${esc(n.label)}</span>
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
  const items = [...S.inbox].reverse();
  $("#inbox").innerHTML = items.length
    ? items
        .map((m) =>
          `<div class="inbox-item${m.type === "message" ? " msg" : ""}">
             <div class="inbox-title">${esc(m.title)}
               ${m.from ? `<span class="inbox-from"> · ${esc(m.from)}</span>` : worldChip(m.world)}
             </div>
             <div class="inbox-text">${esc(m.text)}</div>
           </div>`)
        .join("")
    : `<div class="dim small">暂无消息。你离开的时光里，世界会留下痕迹。</div>`;
  $("#inbox-dot").hidden = newCount <= 0;
}

function renderAll(newInbox = 0, story = false, animate = false) {
  renderHeader();
  renderMap();
  renderSystem();
  renderQuests();
  renderBag();
  if (story) renderStory(animate);
  renderRelations();
  renderInbox(newInbox);
  renderSys();
}

/* ---------- 动作 ---------- */

async function act(text) {
  if (busy || !text.trim()) return;
  setBusy(true);
  try {
    const data = await api("/api/act", { text });
    S = data.state;
    $("#demo-badge").hidden = !data.demo_mode;
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
  const data = await api("/api/resume");
  S = data.state;
  $("#demo-badge").hidden = !data.demo_mode;
  const n = (data.offline_events || []).length;
  renderAll(n, true);
  if (data.system_notice) toast(data.system_notice);
  if (!SHOP) await loadCatalog();
  if (n > 0) {
    toast(`你不在的时候，世界发生了 ${n} 件事——详见收件箱`);
    $("#inbox-dot").hidden = false;
  }
}

async function doSignIn() {
  if (busy) return;
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
  try {
    const data = await api("/api/new", { name, show_affinity: true });
    S = data.state;
    $("#demo-badge").hidden = !data.demo_mode;
    $("#modal").hidden = true;
    renderAll(0, true, true);
    await loadCatalog();
    toast(`新的故事开始了。欢迎，${S.player.name}。`);
  } catch (e) {
    toast("开局失败：" + e.message, true);
  }
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
  $("#btn-cross").onclick = () => act("【系统】穿越到另一界（都市⇄修仙界）");
  $("#btn-signin").onclick = doSignIn;
  $("#sys-btn-signin").onclick = doSignIn;
  $("#btn-sys").onclick = () => openSysModal();
  $("#sys-modal-close").onclick = closeSysModal;
  $("#sys-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeSysModal();
  });
  $$(".sys-tab").forEach((t) => {
    t.onclick = () => switchSysTab(t.dataset.tab);
  });
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
    }
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
  $("#sys-alchemy").addEventListener("click", async (e) => {
    const b = e.target.closest(".craft-btn");
    if (!b || busy || b.disabled) return;
    try {
      const data = await api("/api/craft", { name: b.dataset.name });
      S = data.state;
      renderAll();
      toast(data.result.msg);
    } catch (err) {
      toast("炼制失败：" + err.message, true);
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
  $("#btn-cancel-new").onclick = () => { if (S) $("#modal").hidden = true; };
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
    $("#history-body").textContent = "正在读取往事……";
    try {
      const response = await fetch("/api/history");
      if (!response.ok) throw new Error("读取失败");
      const data = await response.json();
      const all = [...data.entries, ...(S?.story || [])];
      $("#history-body").textContent = all.map((s) => `第${s.turn}幕 · ${WORLD_NAMES[s.world]}\n${s.text}${s.chosen ? `\n行动：${s.chosen}` : ""}`).join("\n\n") || "还没有故事。";
    } catch (err) { $("#history-body").textContent = "往事读取失败，请关闭后重试。"; }
  };
  $("#btn-backups").onclick = async () => {
    $("#history-modal").hidden = false;
    $("#history-body").textContent = "正在读取存档备份……";
    try {
      const response = await fetch("/api/backups");
      if (!response.ok) throw new Error("读取失败");
      const data = await response.json();
      $("#history-body").innerHTML = data.backups.map((b) =>
        `<p>${esc(b.name)} · 第${b.turn}回合 · ${esc(b.id)} <button class="btn restore-save" data-id="${esc(b.id)}">恢复</button></p>`).join("") || "还没有备份。每次存档和重开前会自动保留进度，最近50份可恢复。";
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
  $("#map-tabs").addEventListener("click", (e) => {
    const t = e.target.closest(".map-tab");
    if (t) { mapView = t.dataset.world; renderMap(); }
  });
  $("#map-canvas").addEventListener("click", (e) => {
    const g = e.target.closest("g.mplace");
    const view = (mapView && S.map[mapView]) ? mapView : S.player.world;
    openMapModal(view, g ? g.dataset.place : null);
  });
  $("#map-canvas-big").addEventListener("click", (e) => {
    const g = e.target.closest("g.mplace");
    if (g) showPlaceDetail(mapModalView, g.dataset.place);
  });
  $("#map-tabs-big").addEventListener("click", (e) => {
    const t = e.target.closest(".map-tab");
    if (t) {
      mapModalView = t.dataset.world;
      renderBigMap();
      $("#map-detail").hidden = true;
    }
  });
  $("#map-detail").addEventListener("click", (e) => {
    const go = e.target.closest("button.md-go");
    if (go && !busy) {
      const { place, world } = go.dataset;
      const text = world === S.player.world
        ? `前往『${place}』`
        : `穿越返回${WORLD_NAMES[world]}的上次离开位置；首次前往修仙界则落在落星荒野`;
      closeMapModal();
      act(text);
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
      const place = (S.player.location && S.player.location.place) || "此地";
      if (c.dataset.qa === "cultivate") act("打坐修炼，运转功法，稳固境界");
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
  applyTheme(localStorage.getItem("sjl-theme"));
  bind();
  loadCatalog();
  try {
    const response = await fetch("/api/state");
    const info = await response.json();
    if (!response.ok) throw new Error(info.detail || "状态读取失败");
    $("#demo-badge").hidden = !info.demo_mode;
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
