/* 双界录 前端逻辑：三栏分格 + 阅读式剧情流 + 地图系统 + 点击式风格切换 */
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const REALMS = ["无名路人", "初露锋芒", "校园新星", "崭露头角", "风云人物", "校园传奇",
  "城市新锐", "万众瞩目", "众星捧月", "城市传奇", "人生赢家"];
const WORLD_NAMES = { urban: "都市" };
const THEME_NAMES = { night: "深海蓝", ink: "暮紫", parchment: "云白", qinglan: "松青" };
const PLACE_TYPES = { campus: "校园", city: "城区", leisure: "休闲", nature: "郊野", culture: "人文", transport: "交通", secret: "秘境" };

let S = null;            // 服务端状态镜像
let busy = false;        // 回合进行中
let DEMO = false;        // 演示模式：自由输入为示例剧情，预期要管理
let typingTimer = null;  // 打字机定时器
let SHOP = null;         // 当期货架（限时轮换）
let SHOP_ALL = null;     // 全目录（"全部"视图）
let CATALOG_META = null; // 目录元信息（货币名等），货币改名不至于让界面静默归零
let pendingRequest = false;
let catalogError = "";
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const EQUIP_SLOTS = ["上装", "鞋履", "配饰", "座驾"];
const GIFT_CATS = ["约会", "情趣", "特殊"];
const TIME_SLOTS = ["清晨", "上午", "下午", "傍晚", "夜晚"];
const STAT_TIPS = {
  体魄: "运动与体力的底气：运动、厨艺方向的项目突破展示参考这一项；体力活也会提供给主持人参考",
  头脑: "学业与分析的根基：考试、竞赛与研究类剧情的主持人参考项",
  情商: "会说话的艺术：正式约会的相处好感真实加成（≥60 时 +1）",
  魅力: "仪表与气场：正式约会的第一印象真实加成（≥60 时 +1）",
};
const statTip = (k) => esc(STAT_TIPS[k] || "属性会随课程与穿搭成长，影响对应剧情走向");
const AFFINITY_STAGES = [[0, "初识"], [25, "熟识"], [50, "朋友"], [70, "亲近"], [85, "心动"], [100, "羁绊"]];

/* 关系阶段：由协商出的关系状态推导（和后端 models.relation_stage 同口径） */
const REL_STAGES = [["尚未相识", 0], ["初识", 1], ["朋友", 2], ["暧昧", 3], ["恋人", 4], ["异地", 4], ["分开", 5]];
function npcStage(npc) {
  const rel = (npc && npc.relationship) || {};
  const map = { friend: "朋友", flirt: "暧昧", partner: "恋人", distance: "异地", breakup: "分开" };
  const label = map[rel.status] || "初识";
  const hit = REL_STAGES.find(([l]) => l === label) || REL_STAGES[1];
  return { idx: hit[1], label };
}

/* 称呼与数值阶段分别说明；旧存档里的阶段词不再充当关系称呼。 */
function npcLabelHTML(n, cls = "npc-label") {
  const label = String(n.label || "").trim();
  if (!label || AFFINITY_STAGES.some(([, name]) => name === label)) return "";
  return `<span class="${cls}" title="剧情中的关系称呼">称呼 · ${esc(label)}</span>`;
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

/* ==================== NPC 图片装载：文件夹优先，生成图兜底 ==================== */
/* 手动放图：static/images/npc/<NPC名>.<ext>（支持 svg/jpg/jpeg/png/webp/gif，
   按 svg→jpg→jpeg→png→webp→gif 依次尝试，全部 404 回退内置生成图）。 */

const PHOTO_DIR = "/static/images/npc/";
const PHOTO_EXTS = ["svg", "jpg", "jpeg", "png", "webp", "gif"];
let PHOTOS = {};          // {npc: {分类: [url,...]}}，/api/photos 拉取
let VIDEOS = {};          // {npc: [url,...]}，NPC 专属视频库
let STICKERS = [];        // [{name, url}]，聊天共用表情包库
let mediaStatus = "idle", mediaError = "", mediaLoading = null;
const photoLastPick = {}; // 同人避免连续撞同一张
const videoLastPick = {};

async function loadPhotos() {
  if (mediaLoading) return mediaLoading;
  mediaStatus = "loading"; mediaError = "";
  mediaLoading = (async () => {
    try {
      const r = await fetch("/api/photos", {cache:"no-store"});
      if (!r.ok) throw Error("素材目录暂时无法读取");
      const data = await r.json();
      PHOTOS = data.photos || {}; VIDEOS = data.videos || {}; STICKERS = data.stickers || [];
      mediaStatus = "ready";
    } catch (e) { mediaStatus = "error"; mediaError = "素材读取失败，请刷新重试。"; }
    finally { mediaLoading = null; renderStickerPanel(); }
  })();
  renderStickerPanel();
  return mediaLoading;
}

function mediaLoadError(el) {
  const figure = el.closest(".message-media");
  if (!figure) return;
  el.hidden = true;
  const status = figure.querySelector(".media-status");
  if (status) { status.hidden = false; status.textContent = "素材无法播放或加载，请检查文件是否移除及格式是否支持。"; }
}

function attachmentHTML(item) {
  const labels = {image:"图片", video:"视频", sticker:"表情包"};
  const label = labels[item.type];
  if (!label) return "";
  const caption = item.caption || item.name || label;
  const url = String(item.url || "");
  if (item.missing || !url.startsWith("/static/")) return `<div class="media-missing">[${label}：${esc(caption)}] 暂无匹配素材</div>`;
  const src = esc(url + (item.version ? `?v=${encodeURIComponent(item.version)}` : ""));
  return `<figure class="message-media media-${item.type}">${item.type === "video"
    ? `<video class="chat-photo" src="${src}" controls playsinline preload="metadata" onerror="mediaLoadError(this)"></video>`
    : `<img class="${item.type === "sticker" ? "chat-sticker" : "chat-photo"}" src="${src}" alt="${esc(caption)}" loading="lazy" onerror="mediaLoadError(this)">`}
    ${item.type === "sticker" ? "" : `<figcaption>${esc(caption)}</figcaption>`}<span class="media-status" role="status" hidden></span></figure>`;
}

function messageMediaHTML(message, owner) {
  if (Array.isArray(message.attachments)) return message.attachments.map(attachmentHTML).join("");
  // Older read-only views can precede resume migration. Choose consistently, never randomly on render.
  return ["image", "video", "sticker"].filter(kind => message[kind]).map(kind => {
    const caption = String(message[kind]);
    const match = kind === "sticker" ? STICKERS.find(s => s.name === caption) : null;
    const category = kind === "image" ? Object.keys(PHOTOS[owner] || {}).find(c => caption.includes(c)) : null;
    const url = match?.url || (category ? PHOTOS[owner][category][0] : "");
    return attachmentHTML({type:kind, caption, url, missing:!url});
  }).join("");
}

/* 从 NPC 图库选一张：caption 关键词匹配分类（自拍/美食/风景/日常），
   命中类优先、否则随机类；同人记住上一张避免连发同图 */
function npcPickPhoto(name, caption = "") {
  const cats = PHOTOS[name];
  if (!cats) return "";
  const keys = Object.keys(cats).filter((key) => Array.isArray(cats[key]) && cats[key].length);
  if (!keys.length) return "";
  const cap = String(caption);
  const requested = ["自拍", "美食", "风景", "日常"].find(k => cap.includes(k));
  // 明确请求的分类缺图时使用同类示意图，避免把自拍配在美食/风景说明下。
  if (requested && !keys.includes(requested)) return "";
  let cat = requested || keys.find(k => cap.includes(k));
  if (!cat) cat = ["自拍", "日常", "风景", "美食"].find(k => keys.includes(k)) || keys[0];
  const pool = cats[cat] || [];
  if (!pool.length) return "";
  let url = pool[Math.floor(Math.random() * pool.length)];
  if (pool.length > 1 && url === photoLastPick[name]) {
    url = pool[(pool.indexOf(url) + 1) % pool.length];
  }
  photoLastPick[name] = url;
  return url;
}

/* 统一出图 HTML：先从图库索引选（多人多分类多张），无索引走扁平文件回退链，最后生成图 */
function photoImgHTML(name, caption, cls = "chat-photo") {
  const cap = esc(caption || "");
  const picked = npcPickPhoto(name, caption);
  const genericScene = /美食|风景/.test(String(caption || ""));
  const src = picked || (genericScene ? npcImage(name, caption) : `${PHOTO_DIR}${encodeURIComponent(name)}.svg`);
  return `<img class="${cls}" src="${src}" alt="${cap}"
    data-pname="${esc(name)}" data-pcap="${cap}" data-ext-idx="${picked ? -1 : genericScene ? PHOTO_EXTS.length : 0}"
    onerror="photoFallback(this)">`;
}

/* NPC 视频消息：从专属视频库随机选一条；没库就整段跳过（不硬造假视频） */
function npcPickVideo(name) {
  const pool = VIDEOS[name];
  if (!Array.isArray(pool) || !pool.length) return "";
  let url = pool[Math.floor(Math.random() * pool.length)];
  if (pool.length > 1 && url === videoLastPick[name]) {
    url = pool[(pool.indexOf(url) + 1) % pool.length];
  }
  videoLastPick[name] = url;
  return url;
}

function videoHTML(name, caption) {
  const src = npcPickVideo(name);
  if (!src) return "";
  return `<video class="chat-photo" src="${src}" controls playsinline preload="metadata"></video>
          <div class="chat-photo-cap">🎥 ${esc(caption || "")}</div>`;
}

/* 表情包：按名字精确→包含匹配→随机兜底；库空返回空（消息退化为纯文字） */
function stickerHTML(ref, cls = "chat-sticker") {
  if (!Array.isArray(STICKERS) || !STICKERS.length || !ref) return "";
  const want = String(ref);
  let hit = STICKERS.find(s => s.name === want)
    || STICKERS.find(s => want.includes(s.name) || s.name.includes(want));
  if (!hit) hit = STICKERS[Math.floor(Math.random() * STICKERS.length)];
  return `<img class="${cls}" src="${hit.url}" alt="${esc(hit.name)}" title="${esc(hit.name)}">`;
}

function photoFallback(el) {
  const idx = Number(el.dataset.extIdx || 0) + 1;
  const name = el.dataset.pname || "?";
  if (/美食|风景/.test(el.dataset.pcap || "")) {
    el.onerror = null;
    el.src = npcImage(name, el.dataset.pcap || "");
  } else if (idx < PHOTO_EXTS.length) {
    el.dataset.extIdx = String(idx);
    el.src = PHOTO_DIR + encodeURIComponent(name) + "." + PHOTO_EXTS[idx];
  } else {
    el.onerror = null;
    el.src = npcImage(name, el.dataset.pcap || "");
  }
}

/* 生成 NPC 专属图片（自拍构图：场景渐变+符号+人物剪影+闪光），返回 data-uri。
   variant 0-2 微调符号位置/渐变方向/人物大小——预置图库的一人多张变体靠它。 */
function npcImage(name, captionText, variant = 0) {
  const conf = NPC_PHOTOS[name] || ["直播间", "#2c2430", "#8a8aa8"];
  const scene = PHOTO_SCENES[conf[0]] || PHOTO_SCENES.直播间;
  const cap = esc(captionText || `${conf[0]} · 自拍`);
  const symDy = variant === 1 ? 14 : variant === 2 ? -10 : 0;
  const gradDir = variant === 1 ? 'x1="0.6" y1="0" x2="0" y2="1"'
                 : variant === 2 ? 'x1="0" y1="0" x2="0.8" y2="0.8"' : 'x1="0" y1="0" x2="0.4" y2="1"';
  const zoom = variant === 2 ? ' transform="translate(100,150) scale(1.12) translate(-100,-150)"' : "";
  const food = String(captionText || "").includes("美食");
  const landscape = String(captionText || "").includes("风景");
  const subject = food
    ? `<ellipse cx="100" cy="103" rx="61" ry="19" fill="#f5ead9"/><ellipse cx="100" cy="97" rx="42" ry="14" fill="#b46f42"/><path d="M64 90q36-40 72 0" fill="#dcb46f"/><path d="M86 50q-7-10 0-20m15 22q-7-10 0-20m15 22q-7-10 0-20" stroke="#fff9" fill="none" stroke-width="2"/>`
    : landscape
      ? `<circle cx="151" cy="40" r="17" fill="#f4d58b"/><path d="M0 112 50 53 102 112 144 66 200 112v38H0Z" fill="#8a9eb1"/><path d="M0 119q48-24 100 0t100 0v31H0Z" fill="#4b718a"/>`
      : `<g${zoom}>
    <path d="M100 150 q0 -34 30 -40 q22 -5 34 8 q10 10 12 32 Z" fill="${conf[2]}" opacity=".95"/>
    <path d="M100 150 q0 -34 -30 -40 q-22 -5 -34 8 q-10 10 -12 32 Z" fill="${conf[2]}" opacity=".9"/>
    <circle cx="100" cy="74" r="26" fill="${conf[1]}"/>
    <circle cx="100" cy="70" r="21" fill="#e8cdb5"/>
    <path d="M79 66 q3 -18 21 -18 q18 0 21 18 q1 -8 -4 -13 q-7 -7 -17 -7 q-10 0 -17 7 q-5 5 -4 13Z" fill="${conf[1]}"/>
  </g>`;
  const syms = scene.syms.map((s, i) => {
    const tpl = PHOTO_SYM[s] || PHOTO_SYM.spark;
    const x = 34 + i * 52, y = 44 + (i % 2) * 26 + symDy;
    return tpl.replace(/\{x(\d*)\}/g, (m, d) => x + (d ? +d : 0))
              .replace(/\{y(\d*)\}/g, (m, d) => y + (d ? +d : 0))
              .replace(/\{c\}/g, "rgba(255,255,255,.5)");
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150">
  <defs><linearGradient id="g" ${gradDir}>
    <stop offset="0" stop-color="${scene.bg[0]}"/><stop offset="1" stop-color="${scene.bg[1]}"/>
  </linearGradient></defs>
  <rect width="200" height="150" fill="url(#g)"/>
  <g>${syms}</g>
  <g opacity=".18" fill="#fff"><rect x="0" y="112" width="200" height="38"/></g>
  ${subject}
  <!-- 自拍闪光与水印 -->
  <circle cx="176" cy="20" r="7" fill="#fff" opacity=".9"/>
  <circle cx="176" cy="20" r="12" fill="#fff" opacity=".25"/>
  <rect x="0" y="132" width="200" height="18" fill="#0009"/>
  <text x="10" y="144" font-size="10.5" fill="#fffd" font-family="sans-serif">${esc(name)} · ${cap}（示意）</text>
</svg>`;
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}

/* ---------- 基础请求 ---------- */

/* 轻量操作：完成前会提示稍候，但不再整页锁死剧情输入（串行仍由 pendingRequest 保证） */
const LIGHT_PATHS = ["/api/chat", "/api/gift", "/api/lottery", "/api/buy", "/api/use",
  "/api/sell", "/api/equip", "/api/unequip", "/api/signin", "/api/settings", "/api/goal"];

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
  $("#btn-act").textContent = v ? "进行中…" : "行动";
  $("#free-input").disabled = v;
  $("#btn-start").disabled = v;
  $("#busy-hint").hidden = !v;
  $("#story-flow").setAttribute("aria-busy", String(v));
  document.querySelectorAll(".choice-btn, .campaign-action, .ending-choice").forEach((b) => (b.disabled = v));
  $("#btn-signin").disabled = v || $("#btn-signin").dataset.signed === "1";
  if (S) renderSys();
}

async function loadCatalog() {
  try {
    const response = await fetch("/api/shop");
    if (!response.ok) throw new Error("目录获取失败");
    const data = await response.json();
    SHOP = data.catalog || [];
    SHOP_ALL = data.all_catalog || data.catalog || [];
    CATALOG_META = { currency_name: data.currency_name || "系统积分",
                     rotation_note: data.rotation_note || "" };
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
  if (typeof CityTheme !== "undefined") { CityTheme.apply(valid); return; }
  document.body.dataset.theme = valid;
  localStorage.setItem("sjl-theme", valid);
  $$(".theme-dot").forEach((d) => d.classList.toggle("active", d.dataset.theme === valid));
}

function setReadingFocus(enabled, persist = true) {
  document.body.dataset.readingFocus = enabled ? "true" : "false";
  const button = $("#btn-reading-focus");
  if (button) {
    button.textContent = enabled ? "返回互动" : "专注阅读";
    button.setAttribute("aria-pressed", String(!!enabled));
  }
  if (persist) { try { localStorage.setItem("sjl-reading-focus", enabled ? "on" : "off"); } catch (_) {} }
}

/* ---------- 渲染 ---------- */

function worldChip(world, cls = "wchip") {
  return `<span class="${cls}">${WORLD_NAMES[world] || "都市"}</span>`;
}

function renderHeader() {
  if ($("#system-link-state")) { $("#system-link-state").textContent = "系统已连接"; $("#system-link-state").dataset.status = "ready"; }
  const chip = $("#world-chip");
  const loc = (S.player.location || {});
  const gd = String(S.game_date || "").split("-");
  const dateTxt = gd.length === 3 ? `${+gd[1]}月${+gd[2]}日·` : "";
  const t = S.clock_view?.label ? `${dateTxt}${S.clock_view.label} · ` : S.time ? `${dateTxt}第${S.time.day}天·${TIME_SLOTS[S.time.slot % 5]} · ` : "";
  chip.textContent = t + (loc.place || "都市");
  chip.title = `游戏内日历：${S.game_date || "?"}`;
  $("#reader-location").textContent = `${loc.city || "京都"} / ${loc.place || "我的生活"}`;
  $("#reader-turn").textContent = `第 ${S.turn || 0} 幕`;
  $("#today-date").textContent = S.game_date ? `${gd[0]}年${Number(gd[1])}月${Number(gd[2])}日` : `第${S.time?.day || 1}天`;
  $("#today-clock").textContent = S.clock_view?.label || `${TIME_SLOTS[(S.time?.slot || 0) % 5]} · 第${S.time?.day || 1}天`;
  const wallet = walletView();
  $("#wallets").innerHTML = `<div><span>华夏币</span><b>${moneyText(wallet.cash)}</b><small>生活与事业</small></div><div><span>系统积分</span><b>${moneyText(wallet.points)}</b><small>心动系统商城</small></div>`;
  // 天际线随游戏时段换色：清晨/上午/下午/傍晚/夜晚
  const SLOT_SKY = ["清晨", "上午", "下午", "傍晚", "夜晚"];
  document.body.dataset.slot = SLOT_SKY[(S.time || {}).slot % 5] || "夜晚";
  const inp = $("#free-input");
  if (inp) inp.placeholder = DEMO
    ? "演示模式：试试 约会 / 训练 / 探索 / 天赋 / 抽奖 · 配置 LLM 后解锁自由输入"
    : "……或者，写下你想做的任何事";
}

/* ---------- 世界地图与旅程规划 ---------- */
let mapLevel = "city";
let mapCountry = "华夏";
let mapCity = "京都";
let mapSearch = "";
let mapType = "";
let mapSelectedPlace = "";
let mapModalView = null;
const moneyText = (value) => Math.max(0, Number(value) || 0).toLocaleString("zh-CN");
function walletView() {
  const p = S?.player || {};
  const count = (name) => (p.items || []).find((i) => i.name === name)?.count || 0;
  return { cash_name:"华夏币", points_name:"系统积分", cash:count("华夏币"), points:count("系统积分"), ...(S?.wallets || {}) };
}
function durationText(minutes) {
  const n = Math.max(0, Math.round(Number(minutes) || 0));
  if (n >= 1440) return `${Math.floor(n / 1440)}天${n % 1440 >= 60 ? Math.floor(n % 1440 / 60) + "小时" : ""}`;
  return n >= 60 ? `${Math.floor(n / 60)}小时${n % 60 ? n % 60 + "分钟" : ""}` : `${n}分钟`;
}
function routeFor(name) { return (S?.atlas?.routes || {})[name] || null; }
function atlasCountries() { return S?.map?.countries || []; }
function atlasCities(country) { return (S?.map?.cities || {})[country] || []; }
function allPlaces() { return S?.map?.urban || []; }
function mapScopePlaces() {
  const query = mapSearch.trim().toLocaleLowerCase();
  return allPlaces().filter((p) => {
    const scope = query ? true : mapLevel === "world" ? true : mapLevel === "country" ? p.country === mapCountry || atlasCities(mapCountry).some(c => c.name === p.city) : p.city === mapCity;
    return scope && (!query || [p.name, p.city, p.country, p.desc, PLACE_TYPES[p.type]].join(" ").toLocaleLowerCase().includes(query));
  });
}
function filteredPlaces() { return mapScopePlaces().filter(p => !mapType || p.type === mapType); }
function mapVisiblePlaces() { return mapType || mapSearch.trim() ? filteredPlaces() : null; }
function worldSVG() { return CityAtlas.world(S,mapVisiblePlaces()); }
function countrySVG(countryName) { return CityAtlas.country(S,countryName,mapVisiblePlaces()); }
function citySVG(cityName, compact = false) { return CityAtlas.city(S,cityName,compact,compact ? "" : mapType,compact ? null : mapVisiblePlaces()); }
function mapSVGByLevel() { return mapLevel === "world" ? worldSVG() : mapLevel === "country" ? countrySVG(mapCountry) : citySVG(mapCity); }
function mapBreadcrumb() { return `世界 › ${mapCountry}${mapLevel === "city" ? ` › ${mapCity}` : ""}`; }
function renderMap() {
  const loc = S.player.location || {};
  $("#map-now").textContent = `${loc.country || "华夏"} / ${loc.city || "京都"} / ${loc.place || "未定"}`;
  $("#map-canvas").innerHTML = citySVG(loc.city || "京都", true);
  const atlas = S.atlas || {};
  $("#atlas-summary").textContent = `${atlas.countries || atlasCountries().length}个国家 · ${atlas.cities || Object.values(S.map?.cities || {}).flat().length}座城市 · ${atlas.places || allPlaces().length}个去处`;
  if (!$("#map-modal").hidden) { renderBigMap(); if (mapSelectedPlace) showPlaceDetail(mapCity,mapSelectedPlace,false); }
}
function openMapModal(focusPlace, level = "city") {
  if (!S) return;
  const loc = S.player.location || {};
  const focus = allPlaces().find(p => p.name === focusPlace);
  mapCountry = focus?.country || loc.country || "华夏"; mapCity = focus?.city || loc.city || "京都"; mapLevel = level;
  mapSearch = ""; mapType = ""; mapSelectedPlace = "";
  $("#map-search").value = "";
  $("#map-modal").hidden = false;
  renderBigMap(true);
  if (mapLevel === "city") showPlaceDetail(mapCity, focusPlace || loc.place || allPlaces()[0]?.name,false);
}
function closeMapModal() { $("#map-modal").hidden = true; }
function renderAtlasSelectors() {
  $("#map-country-select").innerHTML = `<option value=""${mapLevel === "world" ? " selected" : ""}>全部国家</option>` + atlasCountries().map(c => `<option value="${esc(c.name)}"${mapLevel !== "world" && c.name === mapCountry ? " selected" : ""}>${esc(c.name)}</option>`).join("");
  const cities = mapLevel === "world" ? Object.values(S.map?.cities || {}).flat() : atlasCities(mapCountry);
  $("#map-city-select").innerHTML = `<option value="">全部城市</option>` + cities.map(c => `<option value="${esc(c.name)}"${mapLevel === "city" && c.name === mapCity ? " selected" : ""}>${esc(c.name)}</option>`).join("");
  const scoped = mapScopePlaces();
  const types = Object.keys(PLACE_TYPES).filter(type => allPlaces().some(p => p.type === type));
  const counts = Object.fromEntries(types.map(type => [type, scoped.filter(p => p.type === type).length]));
  $("#map-type-select").innerHTML = `<option value="">全部类型（${scoped.length}）</option>` + types.map(t => `<option value="${esc(t)}"${t === mapType ? " selected" : ""}>${esc(PLACE_TYPES[t])}（${counts[t]}）</option>`).join("");
  $("#map-type-select").value = mapType;
  $("#map-type-filters").innerHTML = [["", "全部", scoped.length], ...types.map(t => [t, PLACE_TYPES[t], counts[t]])].map(([type, label, count]) => `<button type="button" class="map-type-chip${mapType === type ? " active" : ""}" data-map-type="${esc(type)}" aria-pressed="${mapType === type}"><span>${esc(label)}</span><span class="map-type-count">${count}</span></button>`).join("");
}
function setMapType(type) {
  mapType = Object.prototype.hasOwnProperty.call(PLACE_TYPES,type) ? type : "";
  renderBigMap(true);
}
function focusMapPlace(cityName, name) {
  const place = allPlaces().find(p => p.name === name && (!cityName || p.city === cityName));
  if (!place) return;
  if (mapLevel !== "city" || mapCity !== place.city) {
    mapLevel = "city"; mapCity = place.city; mapCountry = place.country || mapCountry;
    renderBigMap(true);
  }
  showPlaceDetail(place.city,place.name);
}
function clearMapSelection() {
  mapSelectedPlace = "";
  const detail = $("#map-detail");
  detail.dataset.empty = "true";
  detail.hidden = false;
  detail.scrollTop = 0;
  const loc = S.player.location || {};
  detail.innerHTML = `<div class="atlas-overview"><span class="atlas-overview-kicker">世界导航</span><h3>下一站，由你选择</h3><p>${atlasCountries().length}个国家、${Object.values(S.map?.cities || {}).flat().length}座城市，沿着城市与街巷继续自己的人生。</p><dl><div><dt>当前所在</dt><dd>${esc(loc.country || "华夏")} / ${esc(loc.city || "京都")}</dd></div><div><dt>旅行预算</dt><dd>${moneyText(walletView().cash)} 华夏币</dd></div></dl><div class="atlas-guide-step"><i>◎</i><span>选择国家，展开城市地图</span></div><div class="atlas-guide-step"><i>⌖</i><span>选择地标，查看活动与行程</span></div><div class="atlas-guide-step"><i>＋</i><span>放大或拖动，探索地图细节</span></div><p class="atlas-overview-foot">每次出发前，都能确认所需时间与华夏币。</p></div>`;
}
function renderBigMap(resetView = false) {
  const loc = S.player.location || {};
  const places = filteredPlaces();
  if (resetView || !places.some(p => p.name === mapSelectedPlace)) clearMapSelection();
  if (resetView) {
    $(".atlas-geography").scrollTop = 0;
    $(".atlas-layout").scrollTop = 0;
  }
  $("#map-now-big").textContent = `现在：${loc.city || ""} / ${loc.place || "未知"} · 华夏币 ${moneyText(walletView().cash)}`;
  $("#map-canvas-big").innerHTML = mapSVGByLevel();
  $("#map-crumbs").innerHTML = `<button class="crumb${mapLevel === "world" ? " active" : ""}" data-lv="world">世界</button>${mapLevel !== "world" ? `<span aria-hidden="true">/</span><button class="crumb${mapLevel === "country" ? " active" : ""}" data-lv="country">${esc(mapCountry)}</button>` : ""}${mapLevel === "city" ? `<span aria-hidden="true">/</span><span class="crumb active">${esc(mapCity)}</span>` : ""}`;
  renderAtlasSelectors();
  const filterLabel = mapType ? ` · ${PLACE_TYPES[mapType] || mapType}` : "";
  $("#map-results").textContent = mapSearch ? `全世界搜索「${mapSearch}」${filterLabel}：${places.length}个去处` : `${mapLevel === "world" ? "世界" : mapLevel === "country" ? mapCountry : mapCity}${filterLabel} · ${places.length}个去处`;
  $("#map-place-list").innerHTML = places.length ? places.map(p => {
    const route = routeFor(p.name); const here = p.name === loc.place;
    return `<button class="place-list-item${here ? " current" : ""}${mapSelectedPlace === p.name ? " selected" : ""}" data-place="${esc(p.name)}" data-city="${esc(p.city)}"><span><b>${esc(p.name)}</b><small>${esc(p.country || "")} / ${esc(p.city)} · ${PLACE_TYPES[p.type] || esc(p.type)}</small></span><span class="place-cost">${here ? "当前所在" : route ? `${durationText(route.minutes)}<small>${route.cost ? `${moneyText(route.cost)} 华夏币` : "免费"}</small>` : "查看旅程"}</span></button>`;
  }).join("") : `<div class="atlas-empty">没有找到符合条件的去处。试试城市名或「音乐」「公园」，也可以清空筛选。<button class="btn btn-ghost" data-map-reset>清空筛选</button></div>`;
}
function showPlaceDetail(cityName, name, reveal = true) {
  const p = allPlaces().find(x => x.name === name); if (!p) return;
  mapSelectedPlace = name;
  const isCur = S.player.location?.place === name;
  const route = routeFor(name); const cash = Number(walletView().cash);
  const affordable = !route || (route.affordable !== false && cash >= Number(route.cost || 0));
  const npcs = (S.npcs || []).filter(n => n.place === name).map(n => n.name);
  const acts = (p.activities || []).map((a,i) => {
    const fee = Number(a.fee || 0); const label = typeof a === "string" ? a : a.label;
    return `<button class="btn btn-ghost md-local" data-activity="${i}"${!isCur || cash < fee || busy ? " disabled" : ""}><span>${esc(label)}</span><small>${a.minutes ? durationText(a.minutes) : ""}${fee ? ` · ${fee} 华夏币` : " · 免费"}${a.income ? ` · 收入 ${a.income} 华夏币` : ""}</small></button>`;
  }).join("");
  $("#map-detail").hidden = false;
  $("#map-detail").dataset.empty = "false";
  $("#map-detail").scrollTop = 0;
  $(".atlas-layout").scrollTop = 0;
  $("#map-detail").innerHTML = `<div class="detail-place-kind">${esc(p.country || "")} / ${esc(p.city)} · ${PLACE_TYPES[p.type] || esc(p.type)}</div><h3 class="md-name">${esc(name)}</h3><span class="place-visited">${isCur ? "当前所在" : p.discovered ? "已经到访" : "等待初次到访"}</span><p class="md-desc dim">${esc(p.desc || "亲自去走走，认识这里的人与事。")}</p>${npcs.length ? `<div class="md-npcs">熟人在这里：${npcs.map(esc).join("、")}</div>` : ""}${!isCur ? `<div class="travel-quote"><span>${esc(route?.mode || "规划旅程")}</span><b>${route ? durationText(route.minutes) : "到达时结算"}</b><span>${route ? moneyText(route.cost) + " 华夏币" : "路费以实际旅程为准"}</span></div><button class="btn btn-accent md-go full" data-place="${esc(name)}"${!affordable || busy ? " disabled" : ""}>${affordable ? "出发去这里" : "华夏币不足"}</button>${!affordable ? `<p class="dim small">还需要 ${moneyText(Number(route?.cost || 0) - cash)} 华夏币。可以先在当地兼职，或选择附近免费去处。</p>` : ""}` : `<button class="btn btn-ghost md-explore full">探索周边</button>`}<div class="npc-sec">在这里可以做</div><div class="place-activities">${acts || `<p class="dim small">可以散步、观察周围，或自由输入你的行动。</p>`}</div>${!isCur && acts ? `<p class="dim small">到达后即可参加当地活动。</p>` : ""}`;
  $$(".place-list-item").forEach(el => el.classList.toggle("selected",el.dataset.place === name));
  CityAtlas.highlight($("#map-canvas-big"),name);
  if (reveal && matchMedia("(max-width:640px)").matches) $("#map-detail").scrollIntoView?.({block:"nearest"});
}
async function travelTo(destination) {
  if (busy) return;
  setBusy(true);
  try { const data = await api("/api/travel",{destination}); S = data.state; renderAll(0,true); closeMapModal(); toast(data.system_notice || data.result?.msg || `已经来到${destination}`); }
  catch(err) { toast("旅程未能开始：" + err.message,true); }
  finally { setBusy(false); }
}

function renderSystem() {
  const p = S.player;
  $("#realm-name").textContent = REALMS[p.realm] || "？？";
  $("#realm-progress-num").textContent = p.realm_progress + "%";
  $("#realm-bar").style.width = p.realm_progress + "%";
  const wallet = walletView();
  $("#purse-line").textContent = `系统积分 ${moneyText(wallet.points)} · 抽奖券 ${(p.items || []).find(i => i.name === "系统抽奖券")?.count || 0}`;
  $("#purse-line").title = "系统积分用于商城和系统奖励；华夏币用于生活、旅行和事业。";
  const idt = p.identity || {};
  const idLine = $("#identity-line");
  idLine.textContent = idt.urban || "尚无正式身份";
  idLine.title = `身份：${idt.urban || "尚无"}`;
  const stage = S.life_stage || {};
  const lifeLine = $("#life-stage-line");
  if (lifeLine) {
    lifeLine.textContent = stage.age
      ? `${stage.age}岁 · ${stage.stage}（${stage.theme}）${stage.next_age ? ` ／ ${stage.next_age}岁进入${stage.next_stage}` : ""}`
      : "";
    lifeLine.title = "年龄与人生阶段随游戏内日期推进，不按剧情章节强切";
  }
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
    ? "灵能觉醒：修仙是心动系统的隐藏功能，由你决定是否追寻更深的线索"
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

function goalCardHTML(g) {
  const pct = Math.max(0, Math.min(100, Number(g.progress) || 0));
  const left = Number(g.days_left) >= 0 ? `剩余 ${g.days_left} 天` : `已超期 ${-Number(g.days_left)} 天`;
  const milestones = (g.milestones || []).map((m) =>
    `<div class="goal-ms${m.done ? " done" : ""}">${m.done ? "✔" : "○"} ${esc(m.text)}</div>`).join("");
  const notes = (g.notes || []).length
    ? `<div class="goal-notes">${g.notes.map((n) => esc(n)).join("<br>")}</div>` : "";
  const finished = g.status !== "active";
  return `<div class="goal-card${finished ? " goal-done" : ""}">
    <div class="goal-head">
      <span class="goal-title">${esc(g.title)}</span>
      <span class="goal-pct">${finished ? (g.status === "completed" ? "已完成" : "已放下") : pct + "%"}</span>
    </div>
    ${finished ? "" : `<div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div>`}
    <div class="goal-meta">第${g.target_day}天目标 · ${left}${g.overdue ? " · 已超期" : ""} · ${esc(g.domain || "其他")}</div>
    ${g.desc ? `<div class="goal-desc">${esc(g.desc)}</div>` : ""}
    ${g.plan ? `<div class="goal-plan">系统建议：${esc(g.plan)}</div>` : ""}
    ${g.mode === "objective" ? `<div class="goal-proof"><span class="dim small">根据实际成果核验</span>${(g.actual || []).map(a=>`<p class="dim small">${esc(a.label)}：${Number(a.actual) || 0} / ${Number(a.target) || 0}${a.met ? " · 已达到" : ""}</p>`).join("")}</div>` : ""}
    <div class="goal-ms-list">${milestones}</div>
    ${notes}
    ${finished ? "" : `<div class="goal-actions">
      <button class="btn btn-ghost" data-goal-advance="${esc(g.id)}"${busy ? " disabled" : ""}>${g.mode === "objective" ? "记录过程与感想" : "记一笔进展"}</button>
      <button class="btn btn-ghost" data-goal-abandon="${esc(g.id)}"${busy ? " disabled" : ""}>放弃</button>
    </div>`}
  </div>`;
}

function questHTML() {
  const mq = S.main_quest || {};
  const notes = (mq.notes || []).slice(-3);
  const campaign = S.campaign;
  const actions = campaign && !campaign.paused && !S.ending ? (campaign.actions || []) : [];
  const endingOptions = campaign?.finale_ready && !S.ending ? (S.ending_options || []) : [];
  const goals = S.goals || [];
  const activeGoals = goals.filter((g) => g.status === "active");
  const finishedGoals = goals.filter((g) => g.status !== "active");
  const goalsHtml = `<div class="npc-sec">◈ 人生目标 <span class="dim small">自己定义</span></div>
    <button class="btn btn-ghost full" data-new-goal${busy ? " disabled" : ""}>＋ 定一个人生目标</button>
    ${activeGoals.map(goalCardHTML).join("")}
    ${finishedGoals.length ? `<details><summary class="dim small">已结束的目标（${finishedGoals.length}）</summary>${finishedGoals.map(goalCardHTML).join("")}</details>` : ""}
    ${!goals.length ? `<div class="dim small">还没有目标。系统可以记录，但不会替你决定。</div>` : ""}`;
  const goalsCompact = `<div class="npc-sec">◈ 人生目标</div>
    ${activeGoals.length
      ? activeGoals.map((g) => `<div class="goal-compact"><b>${esc(g.title)}</b> · ${g.progress}%${g.overdue ? " · 超期" : ""}</div>`).join("")
      : `<div class="dim small">还没有目标</div>`}
    <button class="chip" data-new-goal${busy ? " disabled" : ""}>＋ 新增</button>`;
  const main = `<div class="campus-optional">校园篇章 · 自由参与</div><div class="q-title">${esc(campaign?.title || mq.title || "新学期的约定")}</div>
     <div class="q-desc">${esc(campaign?.objective || mq.desc || "走出宿舍，开始你的新生活。")}</div>` +
     (campaign?.route ? `<div class="q-desc">参与方向：${esc(campaign.route)}</div>` : "") +
     (campaign && !S.ending ? `<button class="chip" data-campaign-action="${campaign.paused ? "resume" : "pause"}">${campaign.paused ? "继续校园篇章" : "暂不参加，过自己的生活"}</button>` : "") +
     (actions.length ? `<div class="quest-actions">${actions.map((action) =>
       `<button class="campaign-action btn btn-ghost" data-campaign-action="${esc(action.id)}"${busy ? " disabled" : ""}>${esc(action.label)}</button>`).join("")}</div>` : "") +
     (campaign?.finale_ready && !S.ending ? `<div class="q-desc finale-hint">这一段经历即将落幕。由你决定与谁同行，也可以独自启程。</div>
       <div class="quest-actions">${endingOptions.map((option) =>
         `<button class="ending-choice btn btn-ghost" data-partner="${esc(option.name)}"${busy ? " disabled" : ""}>${esc(option.label || `与${option.name}同行`)}</button>`).join("")}
       <button class="ending-choice btn btn-accent" data-partner=""${busy ? " disabled" : ""}>独自启程</button></div>` : "") +
     (S.ending ? `<div class="q-desc">已完成 · ${esc(S.ending.title)}，生活继续由你安排。</div><button class="btn btn-ghost" data-view-ending>重温终章</button>` : "") +
     (campaign && mq.title ? `<details class="growth-goal"><summary>成长目标 · 等级 ${Number(S.player.realm || 0)}</summary><div class="q-desc">${esc(mq.title)}：${esc(mq.desc)}</div></details>` : "") +
     (notes.length ? `<div class="q-desc dim">近况：${notes.map(esc).join("；")}</div>` : "");
  const active = (S.side_quests || []).filter((q) => !q.done);
  const done = (S.side_quests || []).filter((q) => q.done);
  const side = [
    ...active.map((q) =>
      `<div class="quest-side"><div class="q-title">◆ 进行中 · ${esc(q.title)}</div>
       <div class="q-desc">${esc(q.desc)}</div></div>`),
    ...done.map((q) =>
      `<div class="quest-side quest-done"><div class="q-title">✔ 已完成 · ${esc(q.title)}</div>
       <div class="q-desc">${esc(q.desc)}</div></div>`),
  ].join("");
  return { main, side, goals: goalsHtml, goalsCompact };
}

function renderQuests() {
  const q = questHTML();
  $("#quest-main").innerHTML = q.main;
  if ($("#quest-goals")) $("#quest-goals").innerHTML = q.goalsCompact;
  $("#quest-side").innerHTML = q.side
    || `<div class="dim small">暂无支线。自由探索世界，可能触发新的际遇。</div>`;
  const shortcut = $("#btn-main-quest");
  shortcut.textContent = S.ending ? "重温终章" : S.campaign?.finale_ready ? "选择终章" : "主线任务";
  shortcut.title = S.campaign?.objective || S.main_quest?.desc || "查看目标与可进行的主线行动";
}

/* ---------- 系统界面（状态 / 背包 / 任务） ---------- */

/* 商品图标：按目录精确映射，一物一图标不重复；未知物品兜底问号 */
const ITEM_ICONS = {
  // 系统特供
  "经验卡（小）": "🃏", "经验卡（中）": "🎴", "经验卡（大）": "🀄",
  "双倍经验时段卡": "⚡", "强化胶囊·体魄": "💪", "强化胶囊·头脑": "🧠",
  "强化胶囊·情商": "💬", "强化胶囊·魅力": "✨", "技能灌顶卡": "🔯",
  "幸运药剂（小）": "🧪", "SSR保底券": "🏆",
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
  "系统积分": "🪙", "便利店饭团": "🍙", "自习室月卡": "🪑",
  "大师吉他课（进阶）": "🎵", "精品摄影套装（高阶）": "📸",
  "传奇钢琴大师课（传承）": "🎹", "限量款行李箱": "🧳", "系统积分×50": "🏅",
  "《心动笔记·残页》": "📜", "下品灵石": "💎",
};

function itemIcon(name) {
  return ITEM_ICONS[name] || (["华夏币", "系统积分"].includes(String(name)) ? "🪙" : "❔");
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

  // 技能格（未学的淡显；等级＋经验条）
  const skillView = S.skills_view || [];
  $("#sys-skills").innerHTML = skillView.map((sk) => `
    <div class="skill-chip${sk.learned ? "" : " unlearned"}" title="${sk.name}（关联${sk.attr}·${sk.domain}）${sk.learned ? ` L${sk.lv}（${sk.xp}/100）` : "：练习可习得"}">
      <span class="skill-name">${sk.name}</span>
      <b>${sk.learned ? "L" + sk.lv : "—"}</b>
      ${sk.learned ? `<i class="skill-xp" style="width:${Math.min(100, sk.xp)}%"></i>` : ""}
    </div>`).join("") || `<div class="dim small">还没练过任何技能——试试「练一会儿唱歌」「弹琴」「排位」…</div>`;

  renderCareer();

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
  $("#sys-quest-goals").innerHTML = q.goals;
  $("#sys-quest-main").innerHTML = `<div class="quest-main">${q.main}</div>`;
  $("#sys-quest-side").innerHTML = q.side
    || `<div class="dim small">暂无支线。自由探索世界，可能触发新的际遇。</div>`;
  $("#sys-bag").innerHTML = p.items.length
    ? p.items.map((i) => {
        const goods = (SHOP || []).find((g) => g.name === i.name);
        const usable = i.name === "系统抽奖券" || !!(goods && goods.type === "consumable" && goods.use);
        const equippable = !!(goods && goods.type === "equipment");
        const storyUse = !!goods && !usable && ["tool", "consumable"].includes(goods.type);
        const sellable = !!goods && !["系统积分", "华夏币", "系统金币", "下品灵石"].includes(i.name);
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

  const cur = Number(walletView().points) || 0;
  $("#sys-currency").textContent = `系统积分 ${moneyText(cur)} · 商城使用系统积分；生活与事业使用华夏币。`;
  // 分类筛选：全部/修炼/属性/约会/情趣/穿搭/特殊
  const cats = ["货架", ...new Set((SHOP || []).map((g) => g.cat).filter(Boolean))];
  $("#shop-cats").innerHTML = cats.map((c) =>
    `<button class="shop-cat chip${c === shopCat ? " active" : ""}" data-cat="${c}">${c}</button>`).join("");
  const shown = (SHOP || []).filter((g) => shopCat === "货架" || g.cat === shopCat);
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
let shopCat = "货架";    // 商城当前视图：货架(限时) | 全部 | 分类

const LOT_QTY_CLASS = { "普通": "q-common", "稀有": "q-rare", "史诗": "q-epic", "传说": "q-legend" };
const LOT_QTY_ICON = { "普通": "🎯", "稀有": "💎", "史诗": "✨", "传说": "👑" };
/* 八扇区：普通×3 / 稀有×2 / 史诗×2 / 传说×1，转盘落点与后端抽出的品质对齐 */
const SLOT_CELL = 62;   // 滚轮单元高（px，与 CSS 保持一致）
const SLOT_LEN = 22;   // 每轮滚动符号数

/* 老虎机符号清单：全部奖池物品（开局加载奖池后重建） */
let slotSymbols = ["系统积分", "专注咖啡", "电影票", "香薰蜡烛", "运动夹克", "自习室月卡",
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

/* ---------- 多领域事业与生活入口 ---------- */
function careerButton(command,label,disabled=false) { return `<button class="btn btn-ghost cbtn" data-cop="${esc(command)}"${disabled || busy ? " disabled" : ""}>${esc(label)}</button>`; }
function renderCareer() {
  const cv = S.career_view || {};
  const positions = cv.all_positions || (cv.domain ? [{domain:cv.domain,stage_name:cv.stage_name,weekly_income:cv.weekly_income,ops:cv.ops,employees:[]}] : []);
  const projects = cv.active_projects || (cv.active_project ? [cv.active_project] : []);
  const active = cv.active_domain || cv.domain;
  const positionHTML = positions.map(p => `<section class="career-position${p.domain === active ? " current" : ""}"><div class="career-head"><div><span class="dim small">${esc(p.domain)}${p.delegated ? " · 已委托" : ""}</span><h4>${esc(p.active_role || p.stage_name || "新的起点")}</h4></div>${p.domain === active ? `<span class="md-cur">当前关注</span>` : careerButton("切换 " + p.domain,"切换到这里")}</div><p class="dim small">${esc(p.stage_name || "")} · 周收入 ${moneyText(p.weekly_income)} 华夏币</p><p class="dim small">团队 ${p.ops?.staff || 0} / 品质 ${p.ops?.quality || 0} / 宣传 ${p.ops?.marketing || 0}</p>${p.employees?.length ? `<p class="dim small">${p.employees.map(e => `${esc(e.name)}${e.role ? `（${esc(e.role)}）` : ""}`).join("、")}</p>` : ""}</section>`).join("");
  const missing = ["娱乐","商业","电竞"].filter(d => !positions.some(p => p.domain === d));
  const roles = (cv.role_options || {})[active] || [];
  const projectHTML = projects.map(p => `<div class="career-project"><div class="career-project-head"><b>${esc(p.domain || "")} / ${esc(p.name)}</b><span class="dim small">剩余${Math.max(0,p.days_left || 0)}天</span></div><p class="dim small">第${p.end_day}天结算 · ${p.plan === "bold" ? "进取" : "稳妥"}方案</p></div>`).join("");
  const options = (cv.project_options || []).map(p => `<div class="career-project-opt"><div class="career-head"><b>${esc(p.name)}</b><span>${p.days}天 · ${p.cost} 华夏币</span></div><p class="dim small">${esc(p.skill_name)} L${p.skill_need} · ${p.skill_ok ? "技能已达标" : `目前 L${p.skill_level || 0}，风险较高`}${p.reason ? ` · ${esc(p.reason)}` : ""}</p><div class="career-acts">${careerButton(`经营 项目 ${p.id} steady`,"稳妥开展",!p.available)}${careerButton(`经营 项目 ${p.id} bold`,"进取开展",!p.available)}</div></div>`).join("");
  const entities = (cv.enterprises || []).map(e => {
    const kind = {company:"公司",team:"战队",work:"作品",contract:"合同"}[e.kind] || e.kind;
    const controls = e.kind === "work" ? (e.status === "released" ? `<p class="dim small">受众 ${moneyText(e.audience)} · 已发行</p>` : `<div class="career-acts">${careerButton(`发行 ${e.id} 流媒体`,"发行到流媒体")}${careerButton(`发行 ${e.id} 院线`,"尝试院线发行")}</div>`) : e.kind === "team" ? careerButton(`参赛 ${e.id}`,"报名参加赛事") : "";
    return `<details class="enterprise-card"><summary><span><small>${esc(kind)}</small><b>${esc(e.name)}</b></span><span class="dim small">持股 ${Number(e.equity?.player) || 0}%</span></summary><div class="enterprise-body"><div class="enterprise-metrics"><span>估值 <b>${moneyText(e.valuation)} 华夏币</b></span><span>账上 <b>${moneyText(e.cash)} 华夏币</b></span><span>状态 <b>${esc(({operating:"经营中",ready:"待发行",released:"已发行",expired:"已到期",suspended:"暂停经营"})[e.status] || e.status || "经营中")}</b></span></div>${e.employees?.length ? `<p class="dim small">成员：${e.employees.map(x=>esc(typeof x === "string" ? x : x.name)).join("、")}</p>` : ""}${controls}<form class="enterprise-operation" data-enterprise="${esc(e.id)}"><label>资产安排<select name="operation"><option value="注资">注资（华夏币）</option><option value="融资">融资（股权百分比）</option><option value="增持">增持（股权百分比）</option>${e.kind === "work" ? `<option value="定价">发行定价（华夏币）</option>` : ""}</select></label><label>数量<input name="amount" type="number" min="1" max="1000000000" value="10" required></label><button class="btn btn-ghost" type="submit"${busy ? " disabled" : ""}>执行安排</button></form>${e.ledger?.length ? `<details class="quiet-details"><summary>最近账目</summary>${e.ledger.slice(-5).map(l=>`<p class="dim small">${esc(l.label || l.text || l.reason || l.type || "账目")} ${l.amount != null ? `${Number(l.amount) < 0 ? "−" : Number(l.amount) > 0 ? "+" : ""}${moneyText(Math.abs(Number(l.amount)))}` : ""}</p>`).join("")}</details>` : ""}</div></details>`;
  }).join("");
  $("#sys-career").innerHTML = `<p class="dim">可以同时保留多个事业身份。切换当前关注领域，不会放弃已有事业。</p><div class="career-positions">${positionHTML || `<p class="dim small">从一场活动、一项技能，或自己的第一家公司开始。</p>`}</div><div class="career-acts">${missing.map(d=>careerButton("入门 " + d,"进入" + d)).join("")}</div>${cv.opportunities?.length ? `<p class="career-opp">已有机会：${cv.opportunities.map(esc).join("、")}</p>` : ""}${active ? `<div class="npc-sec">${esc(active)} / 当前安排</div><div class="career-acts">${careerButton("晋升","申请晋升")}${careerButton("特训","特训 · 15 华夏币")}${careerButton(positions.find(p=>p.domain===active)?.delegated ? "收回委托" : "委托",positions.find(p=>p.domain===active)?.delegated ? "亲自经营" : "委托经营")}</div>${roles.length ? `<div class="career-acts">${roles.map(r=>careerButton("职业 " + r,r)).join("")}</div>` : ""}<div class="career-acts">${careerButton("经营 招聘","招聘 · 50 华夏币")}${careerButton("经营 培训","培训 · 20 华夏币")}${careerButton("经营 宣传","宣传 · 30 华夏币")}</div>` : ""}<div class="npc-sec">进行中的项目</div>${projectHTML || `<p class="dim small">没有进行中的项目。不同领域可以同时开展项目。</p>`}${options ? `<details class="quiet-details"><summary>可以开展的项目</summary>${options}</details>` : ""}<div class="npc-sec">我的经营资产</div>${entities || `<p class="dim small">公司、作品、战队与合同，会持续记录在这里。</p>`}<form id="enterprise-create" class="enterprise-create"><label>新事业<select id="enterprise-kind"><option value="company">创办公司 · 200 华夏币</option><option value="team">收购战队 · 800 华夏币</option></select></label><label>名称<input id="enterprise-name" type="text" maxlength="24" placeholder="例如：星河传媒" required></label><button class="btn btn-ghost" type="submit"${busy ? " disabled" : ""}>开始筹办</button></form>${(cv.assets || []).length ? `<details class="quiet-details"><summary>其他资产</summary>${cv.assets.map(a=>`<p>${esc(a.name)} · 每周 ${moneyText(a.weekly)} 华夏币</p>`).join("")}</details>` : ""}${(cv.completed_projects || []).length ? `<details class="quiet-details"><summary>项目回顾</summary>${cv.completed_projects.map(p=>`<p>${esc(p.name)} · ${p.outcome === "success" ? "成功" : p.outcome === "partial" ? "部分完成" : "未达预期"}<small class="dim">${esc(p.result || "")}</small></p>`).join("")}</details>` : ""}`;
}
const TIME_SKILLS = {vocal:"声乐",instrument:"乐器",acting:"演技",stage:"台风",mech:"操作",sense:"意识",manage:"经营",invest:"投资",coding:"编程",cooking:"厨艺",photo:"摄影",speech:"演讲"};
function openLifeModal(activity) {
  if (!S) return;
  $("#life-modal").hidden = false;
  $("#time-skill").innerHTML = Object.entries(TIME_SKILLS).map(([id,name])=>`<option value="${id}">${name}</option>`).join("");
  if (activity) $("#time-activity").value = activity;
  $("#time-days").max = String(S.clock_view?.max_skip_days || 1095);
  updateTimePreview();
}
function updateTimePreview() {
  const activity = $("#time-activity").value || "rest";
  $("#time-skill-field").hidden = activity !== "train";
  const days = Number($("#time-days").value);
  const day = Number(S?.clock_view?.day || S?.time?.day || 1);
  $("#time-preview").textContent = Number.isInteger(days) && days > 0 && days <= Number(S?.clock_view?.max_skip_days || 1095) ? `从第${day}天安排到第${day + days}天。未到期的项目与人物行程将继续推进；收入和费用按实际条件结算。` : "请输入有效天数（1—1095天）。";
}
async function advanceGameTime(event) {
  event?.preventDefault(); if (!S || busy) return;
  const days = Number($("#time-days").value);
  if (!Number.isInteger(days) || days < 1 || days > Number(S.clock_view?.max_skip_days || 1095)) { toast("请输入1—1095之间的整天数",true); return; }
  setBusy(true);
  $("#time-submit").disabled = true;
  try { const data = await api("/api/time",{days,activity:$("#time-activity").value || "rest",skill:$("#time-skill").value || "vocal"}); S = data.state; $("#life-modal").hidden = true; renderAll(0,true); toast(data.system_notice || data.result?.msg || "这段时间已经记入生活。"); }
  catch(err) { toast("时间安排未能开始：" + err.message,true); }
  finally { setBusy(false); $("#time-submit").disabled = false; }
}
function worldActionLabel(action) { return String(action).replace(/^【人物】[^:]+:/,"").replace(/^【暗线】/,""); }
function renderWorldLife() {
  const world = S.world_view || {};
  const people = world.people || [];
  $("#world-people").innerHTML = people.slice(0,5).map(p=>`<button class="world-person" data-person="${esc(p.name)}"><span class="world-person-avatar">${esc(p.name?.slice(-1) || "人")}</span><span><b>${esc(p.name)}</b><small>${esc(p.status || p.goal || "过着自己的生活")}</small>${p.next?.text ? `<small class="dim">接下来：${esc(p.next.text)}</small>` : ""}</span></button>`).join("") || `<p class="dim small">认识更多的人后，可以在这里关注他们的生活。</p>`;
  const projects = S.career_view?.active_projects || [];
  $("#today-next").textContent = projects.length ? `最近项目：${projects[0].name}，${Math.max(0,projects[0].days_left || 0)}天后结算。` : "留一点时间给自己，也可以去看看朋友。";
  const arcs = world.arcs || [];
  const arcHTML = arcs.map(a=>`<details class="character-arc"${a.completed ? "" : " open"}><summary><b>${esc(a.name)}</b><span class="dim small">${a.completed ? "经历已完成" : `${Math.min(a.stage || 0,a.total || 0)}/${a.total || 0}`}</span></summary><p>${esc(a.title || a.goal || "")}</p><p class="dim small">${esc(a.desc || "")}</p><div class="arc-actions">${(a.choices || []).map(c=>`<button class="btn btn-ghost" data-world-action="${esc(c)}"${busy ? " disabled" : ""}>${esc(worldActionLabel(c))}</button>`).join("")}</div></details>`).join("");
  const arcEl = $("#sys-world-arcs"); if (arcEl) arcEl.innerHTML = arcHTML || `<p class="dim small">与核心人物相识后，他们自己的故事会在这里展开。</p>`;
  const mystery = world.mystery || {};
  const mChoices = mystery.choices || [];
  $("#world-mystery").innerHTML = `<p class="dim small">${mystery.status === "closed" ? "这段传闻已有答案，生活仍在继续。" : mystery.status === "paused" ? "调查暂时搁置，等你想起时再继续。" : mystery.clues?.length ? esc(mystery.clues[mystery.clues.length - 1]) : "城市里偶有无法解释的传闻。是否追寻，由你决定。"}</p>${!mChoices.length && mystery.status !== "closed" ? `<button class="btn btn-ghost full" data-mystery-place>去天文台走走</button>` : ""}<div class="arc-actions">${mChoices.map(c=>`<button class="btn btn-ghost" data-world-action="${esc(c)}"${busy ? " disabled" : ""}>${esc(worldActionLabel(c))}</button>`).join("")}</div>`;
  const recent = S.clock_view?.recent || [];
  $("#time-recent").innerHTML = recent.length ? `<div class="npc-sec">最近的时间记录</div>${recent.slice(-4).map(r=>`<p class="dim small">${esc(typeof r === "string" ? r : r.text || r.label || r.activity || "生活向前了一段时间")}</p>`).join("")}` : "";
}
function npcArcHTML(name) {
  const arc = S.world_view?.arcs?.find(a=>a.name === name);
  if (!arc) return "";
  return `<div class="npc-sec">她自己的计划</div><p>${esc(arc.title || arc.goal || "")}</p><p class="dim small">${esc(arc.desc || "")}</p><p class="dim small">${arc.completed ? "这一段经历已经完成" : `第${arc.due_day}天回收当前计划`}</p><div class="arc-actions">${(arc.choices || []).map(c=>`<button class="btn btn-ghost" data-world-action="${esc(c)}"${busy ? " disabled" : ""}>${esc(worldActionLabel(c))}</button>`).join("")}</div>`;
}
function relationshipHTML(n) {
  const rel = n.relationship || S.world_view?.people?.find(p=>p.name===n.name)?.relationship || {};
  const mode = rel.mode || "exclusive";
  return `<div class="npc-sec">你们的关系</div><div class="relationship-state"><b>${esc(rel.label || "尚未确认")}</b><span>${esc(rel.mode_label || "关系约定由双方决定")}</span></div><p class="dim small">表达意愿后，对方会按自己的原则回应。涉及其他伴侣的安排，需要所有相关者知情并同意。</p><div class="relationship-controls"><label>希望讨论的相处方式<select id="relationship-mode"><option value="exclusive"${mode === "exclusive" ? " selected" : ""}>排他交往</option><option value="open"${mode === "open" ? " selected" : ""}>开放关系</option><option value="poly"${mode === "poly" ? " selected" : ""}>知情多伴侣</option></select></label><div class="arc-actions">${["朋友","暧昧","表白","协商"].map(verb=>`<button class="btn btn-ghost" data-relation="${verb}" data-npc="${esc(n.name)}">${verb === "朋友" ? "保持朋友" : verb === "协商" ? "讨论关系约定" : verb}</button>`).join("")}${rel.proposal ? `<button class="btn btn-accent" data-relation="确认" data-npc="${esc(n.name)}">确认已达成的约定</button>` : ""}${["partner","distance"].includes(rel.status) ? `<button class="btn btn-ghost" data-relation="${rel.status === "distance" ? "重逢" : "异地"}" data-npc="${esc(n.name)}">${rel.status === "distance" ? "安排重逢" : "谈谈异地安排"}</button><button class="btn btn-ghost" data-relation="分手" data-npc="${esc(n.name)}">认真谈分手</button>` : rel.status === "breakup" ? `<button class="btn btn-ghost" data-relation="复合" data-npc="${esc(n.name)}">尝试重新开始</button>` : ""}</div>${rel.proposal ? `<p class="dim small">关系讨论已有回应，请查看本次对话后再确认。确认前不会自动改变约定。</p>` : ""}</div>`;
}

/* ---------- NPC 详情弹窗 ---------- */

function showNpcDetail(name) {
  const n = (S.npcs || []).find((x) => x.name === name);
  if (!n) return;
  const st = npcStage(n);
  $("#npc-m-title").innerHTML =
    `<span class="md-name" style="font-size:20px">${esc(n.name)}</span>
     <span class="md-type">${esc(n.role)}</span>
     ${npcLabelHTML(n, "md-cur")}
     <span class="npc-stage st-${st.idx}" title="关系由相处与协商确认">关系 · ${st.label}</span>`;
  const life = n.life || {};
  const slotNames = ["清晨", "上午", "下午", "傍晚", "夜晚"];
  const nextEvent = life.next;
  const nextText = nextEvent
    ? `第${nextEvent.day}天·${slotNames[nextEvent.slot] || ""}${nextEvent.place ? ` · ${nextEvent.place}` : ""}：${nextEvent.text || ""}`
    : "暂时没有下一步安排。";
  const lifeHTML = `<div class="npc-sec">◈ 近况</div>
    <div class="npc-mem">${esc(life.status || "如常生活")}${life.mood ? ` · 心情：${esc(life.mood)}` : ""}</div>
    <div class="npc-mem">${life.goal ? `目标：${esc(life.goal)}` : `<span class="dim">目标尚未了解。</span>`}</div>
    <div class="npc-mem dim small">下一步：${esc(nextText)}</div>`;
  const bounds = n.boundaries || {};
  const boundariesHTML = `<div class="npc-sec">◈ 相处原则</div>
    <div class="npc-mem">${bounds.principles ? `原则：${esc(bounds.principles)}` : `<span class="dim">原则尚未了解。</span>`}</div>
    <div class="npc-mem">${bounds.boundary ? `边界：${esc(bounds.boundary)}` : `<span class="dim">边界尚未了解。</span>`}</div>
    <div class="npc-mem">${bounds.romance_style ? `恋爱观：${esc(bounds.romance_style)}` : `<span class="dim">恋爱观尚未了解。</span>`}</div>`;
  const rels = Object.entries(n.rels || {})
    .map(([k, v]) => `<div class="npc-mem"><b>${esc(k)}</b>：${esc(v)}</div>`).join("");
  const myDates = (S.dates || []).filter((d) => d.npc === n.name);
  const lastDate = myDates[myDates.length - 1];
  const dateInfo = myDates.length
    ? `<div class="npc-mem">共 ${myDates.length} 次约会${lastDate
        ? ` · 最近：第${lastDate.turn}回合在${esc(lastDate.place)}` : ""}</div>
       <div class="npc-mem dim small">${esc(lastDate?.text || "")}</div>`
    : `<div class="npc-mem dim">还没有一起留下过约会回忆。</div>`;
  const canDate = true;
  // 背包里可直接赠送的礼物（与背包页同一判定口径）
  const giftable = (S.player.items || []).filter((i) => {
    const goods = (SHOP || []).find((g) => g.name === i.name);
    return goods && GIFT_CATS.includes(goods.cat) && i.name !== "系统抽奖券";
  });
  // 他心通从共同经历中感受关系，不把好感数值写成未经确认的承诺。
  const pwStage = (S.power || {}).stage || 0;
  const sharedMemory = n.heart_voice || (n.memo?.length ? n.memo : n.memory || []).slice(-1)[0] || lastDate?.text;
  const heartLine = pwStage >= 3
    ? `<div class="npc-sec">◈ 记忆回声（他心通）</div>
       <div class="npc-mem heart-voice">${sharedMemory ? esc(sharedMemory) : "共同经历尚少，还没有清晰的记忆回声。"}</div>
       <div class="dim small">你们留下的经历，会成为回声的线索。</div>` : "";
  $("#npc-m-body").innerHTML = `
    <div class="npc-persona">${esc(n.persona)}</div>
    ${heartLine}
    <div class="npc-sec">◈ 关系</div>
    <div class="npc-mem"><span class="npc-stage st-${st.idx}">${st.label}</span>
      ——关系由相处与协商确认；经历与承诺以实际发生为准。</div>
    ${relationshipHTML(n)}
    <div class="npc-sec">◈ 常在地</div>
    <div class="npc-mem">${esc(n.place || "行踪不定")}</div>
    ${lifeHTML}
    ${npcArcHTML(n.name)}
    ${boundariesHTML}
    <div class="npc-sec">◈ 礼物偏好</div>
    ${n.likes ? `<div class="npc-mem">听说 TA 偏爱<b>${esc(n.likes)}</b>类礼物——投其所好，心意加倍。</div>`
      : `<div class="npc-mem dim">还未听说 TA 的喜好，慢慢相处就知道了。</div>`}
    <div class="npc-sec">◈ 约会回忆</div>
    ${dateInfo}
    <div class="npc-date-action">
      <button class="btn btn-accent btn-invite-date" data-npc="${esc(n.name)}"${canDate ? "" : " disabled"}>邀请约会</button>
      <button class="btn btn-ghost btn-msg-npc" data-npc="${esc(n.name)}">发消息</button>
      ${canDate ? "" : show ? `<span class="dim small">需好感70、信任30、吸引20</span>` : ""}
    </div>
    <div class="npc-sec">◈ 送礼物</div>
    ${giftable.length
      ? `<div class="npc-gift-chips">${giftable.map((i) =>
          `<button class="chip npc-gift-chip" data-item="${esc(i.name)}" data-npc="${esc(n.name)}">${esc(i.name)} ×${i.count || 1}</button>`).join("")}</div>
         <div class="dim small">同一人每天限 1 份、每周 2 份；生日心意 ×2，最多 +15，不占每周限额${n.likes ? `；TA 偏爱${esc(n.likes)}类` : ""}</div>`
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

function storyChoiceLabel(raw) {
  const text = String(raw || "");
  if (text.startsWith("【主线】")) {
    const id = text.slice("【主线】".length);
    return ({pause:"暂不参加校园篇章",resume:"继续校园篇章"})[id] || (S?.campaign?.actions || []).find(a=>a.id===id)?.label || "继续主线";
  }
  if (text.startsWith("【活动】")) {
    const [eid,oid] = text.slice(4).split(":");
    return S?.event_today?.id === eid ? (S.event_today.options || []).find(o=>o.id===oid)?.label || "参加活动" : "参加活动";
  }
  if (text.startsWith("【人物】")) { const [name,verb,channel] = text.slice(4).split(":"); return verb === "相识" ? `通过${channel || "交流"}认识${name}` : `${verb}${name}的计划`; }
  if (text.startsWith("【关系】")) { const [name,verb,mode] = text.slice(4).split(":"); const methods={exclusive:"专一",open:"开放",poly:"知情多伴侣"}; return `和${name}${verb === "协商" ? `讨论${methods[mode] || "相处"}关系` : verb === "确认" ? "确认关系约定" : verb}`; }
  if (text.startsWith("【地点】")) { const activity = allPlaces().find(p=>p.name === S?.player?.location?.place)?.activities?.[Number(text.slice(4))]; return activity?.label || "参加当地活动"; }
  if (text.startsWith("【旅行】")) return "前往" + text.slice(4);
  if (text.startsWith("【暗线】")) return "调查：" + text.slice(4);
  return text.replace(/^【(?:生活|事业|时间|约会)】/,"");
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
      c.textContent = storyChoiceLabel(seg.chosen);
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
    b.textContent = storyChoiceLabel(c);
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
  $("#relations").innerHTML = S.npcs
    .map((n) => {
      const rels = Object.entries(n.rels || {})
        .map(([k, v]) => `与<b>${esc(k)}</b>：${esc(v)}`)
        .join("<br>");
      const st = npcStage(n);
      const life = n.life || {};
      return `<div class="npc-card" data-name="${esc(n.name)}" title="点击查看详情" role="button" tabindex="0" aria-label="查看${esc(n.name)}的近况与关系">
        <div class="npc-head">
          <span class="npc-name">${esc(n.name)}</span>
          <span class="npc-role">${esc(n.role)}</span>
          ${npcLabelHTML(n)}
          <span class="npc-stage st-${st.idx}" title="关系由相处与协商确认">关系 · ${st.label}</span>
        </div>
        <div class="npc-place">${n.place ? `常在 · ${esc(n.place)}` : "行踪不定"}</div>
        ${life.status && life.status !== "如常生活" ? `<div class="npc-life">近况 · ${esc(life.status)}</div>` : ""}
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
        ${m.image ? `${photoImgHTML(m.from || m.title, m.image)}
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

function renderEventBanner() {
  const el = $("#event-banner");
  if (!el) return;
  const ev = S && S.event_today;
  if (!ev) { el.hidden = true; return; }
  const opts = (ev.options || []).map((o) =>
    `<button class="chip ev-opt" data-eid="${esc(ev.id)}" data-oid="${esc(o.id)}"${busy ? " disabled" : ""}>${esc(o.label)}${o.need ? `<i class="dim small"> ${esc(o.need)}</i>` : ""}</button>`).join("");
  el.innerHTML = `<span class="ev-name">🎪 今日活动 · ${esc(ev.name)}</span><span class="dim small ev-desc">${esc(ev.desc.slice(0, 26))}…</span><span class="ev-opts">${opts}</span>`;
  el.hidden = false;
}

function renderAll(newInbox = 0, story = false, animate = false) {
  renderHeader();
  renderMap();
  renderSystem();
  renderQuests();
  renderBag();
  renderEventBanner();
  renderWorldLife();
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

async function chooseEnding(partner) {
  if (busy || pendingRequest || !S?.campaign?.finale_ready || S.ending) return;
  try {
    const data = await api("/api/ending", { partner: partner || null });
    S = data.state;
    if (!data.result?.ok) {
      renderAll();
      toast(data.result?.msg || "这次选择尚未满足条件，请继续完成共同经历。", true);
      return;
    }
    closeSysModal();
    renderAll(0, true);
    if (data.result.msg) toast(data.result.msg);
  } catch (err) {
    toast("终章未能写入：" + err.message, true);
  }
}

async function newGame() {
  if (busy) return;
  const name = ($("#inp-name").value || "").trim() || "林川";
  const btn = $("#btn-start");
  btn.textContent = "正在生成开局剧情…首次约需 10~30 秒";
  try {
    const data = await api("/api/new", { name });
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
      const st = npcStage(n);
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
      const body = last.text || (last.sticker ? `[表情包] ${last.sticker}`
        : last.video ? "[视频]" : last.image ? "[图片]" : "");
      const preview = (last.from === "me" ? "我：" : "") + body;
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
       <div class="bub ${me ? "bub-me" : "bub-npc"} ${cls}${!m.text && m.sticker ? " bub-sticker" : ""}">
         ${m.text ? `<div class="message-text">${esc(m.text)}</div>` : ""}
         ${messageMediaHTML(m, chatWith)}
       </div>
     </div>`;
  const entries = msgs.map((m, i) => ({key:m.id || `${m.ts}|${m.from}|${i}`, html:row(m.from === "me", m)}));
  if (typing) entries.push({key:"typing", html:row(false, {text:"对方正在输入…"}, "bub-typing")});
  // Reconcile individual messages: an unchanged video node keeps its playback position.
  if (typeof document.createElement === "function" && body.children) {
    if (body.dataset.conversation !== chatWith) { body.replaceChildren(); body.dataset.conversation = chatWith; }
    const existing = new Map(Array.from(body.children).map(el => [el.dataset.messageKey, el]));
    const wanted = new Set(entries.map(entry => entry.key));
    for (const [key, el] of existing) if (!wanted.has(key)) el.remove();
    entries.forEach((entry, i) => {
      let el = existing.get(entry.key);
      if (!el || el._messageHTML !== entry.html) {
        const host = document.createElement("div"); host.innerHTML = entry.html;
        const replacement = host.firstElementChild;
        replacement.dataset.messageKey = entry.key; replacement._messageHTML = entry.html;
        if (el) el.replaceWith(replacement);
        el = replacement;
      }
      if (body.children[i] !== el) body.insertBefore(el, body.children[i] || null);
    });
  } else body.innerHTML = entries.map(entry => entry.html).join("");
  body.scrollTop = body.scrollHeight;
}

async function sendChatMessage(stickerName = "", stickerId = "") {
  const input = $("#chat-input");
  const text = input.value.trim();
  const sticker = String(stickerName || "").trim();
  if ((!text && !sticker) || !chatWith || busy) return;
  input.value = "";
  toggleStickerPanel(false);
  // 先乐观显示我的消息，等待对方回复
  (S.chats = S.chats || {})[chatWith] = S.chats[chatWith] || { msgs: [] };
  const optimistic = { ts: new Date().toISOString(), from: "me", text };
  if (sticker) optimistic.sticker = sticker;
  const selected = STICKERS.find(s => s.id === stickerId || (!stickerId && s.name === sticker));
  optimistic.attachments = selected ? [{...selected, type:"sticker", caption:selected.name}] : [];
  S.chats[chatWith].msgs.push(optimistic);
  renderChatBody(true);
  try {
    const data = await api("/api/chat", { npc: chatWith, text, sticker, sticker_id:stickerId });
    S = data.state;
    renderAll();
    renderChatBody(false);
    if (!data.result.ok) toast(data.result.msg, true);
  } catch (e) {
    // 失败回滚乐观气泡并还回输入——玩家的话不能凭空消失
    const msgs = (S.chats[chatWith] || {}).msgs || [];
    const i = msgs.findIndex((m) => m.from === "me" && m === optimistic);
    if (i >= 0) msgs.splice(i, 1);
    renderChatBody(false);
    input.value = text;
    toast("发送失败（消息未发出，已还回输入框）：" + e.message, true);
  }
}

/* 表情包面板：点开选一张直接发送 */
function toggleStickerPanel(show) {
  const panel = $("#sticker-panel");
  if (!panel) return;
  const open = show === undefined ? panel.style.display === "none" : show;
  panel.style.display = open ? "block" : "none";
  if (open) { renderStickerPanel(); if (mediaStatus === "idle") loadPhotos(); }
}

function renderStickerPanel() {
  const panel = $("#sticker-panel");
  if (!panel || panel.style.display === "none") return;
  panel.innerHTML = `<div class="sticker-tools"><span>${mediaStatus === "loading" ? "正在读取素材…" : `表情包 ${STICKERS.length}`}</span><button type="button" data-media-refresh ${mediaStatus === "loading" ? "disabled" : ""}>刷新素材</button></div>`
    + (mediaStatus === "error" ? `<p role="status">${esc(mediaError)}</p>` : STICKERS.length
      ? `<div class="sticker-grid">${STICKERS.map(s => `<button type="button" class="sticker-choice" data-sticker-id="${esc(s.id || "")}" data-sticker-name="${esc(s.name)}" title="${esc(s.name)}"><img class="sticker-opt" src="${esc(s.url)}" alt="${esc(s.name)}" loading="lazy"></button>`).join("")}</div>`
      : mediaStatus !== "loading" ? '<p role="status">表情包库为空。添加文件后点击刷新素材。</p>' : "");
  if (!panel._mediaBound) {
    panel.addEventListener("click", e => {
      if (e.target.closest("[data-media-refresh]")) { loadPhotos(); return; }
      const choice = e.target.closest("[data-sticker-name]");
      if (choice) sendChatMessage(choice.dataset.stickerName, choice.dataset.stickerId);
    });
    panel._mediaBound = true;
  }
}

/* ---------- 图鉴 / 成就 / 结局（阶段F） ---------- */

let endingShown = false;

function renderCodex() {
  const people = $("#codex-people");
  if (!people) return;
  const known = S.npcs || [];
  const rosterTotal = Number.isInteger(S.npc_total) ? Math.max(S.npc_total, known.length) : null;
  const unknownCount = rosterTotal === null ? 0 : rosterTotal - known.length;
  people.innerHTML = known.map((n) => {
    const st = npcStage(n);
    const dates = (S.dates || []).filter((d) => d.npc === n.name).length;
    return `<div class="codex-card">
      <div class="codex-name">${esc(n.name)}</div>
      <div class="dim small">${esc(n.role)}</div>
      <span class="npc-stage st-${st.idx}">${st.label}</span>
      ${dates ? `<div class="dim small">约会 ×${dates}</div>` : ""}
    </div>`;
  }).join("") + (unknownCount > 0 ? `<div class="codex-card codex-unknown"><div class="codex-name">尚未相遇</div>
    <div class="dim small">还有 ${unknownCount} 人等待相识</div></div>` : known.length ? "" : `<div class="dim small">还未结识人物，出门走走吧。</div>`);
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
  $("#ending-title").textContent = `终章 ·《${S.ending.title}》`;
  $("#ending-text").textContent = S.ending.text || (S.ending.partner
    ? `这一程的终点，身边站着${S.ending.partner}。`
    : "这一程的终点，你选择了属于自己的人生。");
  $("#ending-modal").hidden = false;
}

/* ---------- 人生目标 ---------- */

function openGoalModal() {
  if (!S) { openSysModal("quest"); return; }
  closeSysModal();
  $("#goal-title").value = "";
  $("#goal-desc").value = "";
  $("#goal-days").value = "30";
  $("#goal-modal").hidden = false;
  $("#goal-title").focus();
}

async function submitGoal() {
  const title = $("#goal-title").value.trim();
  if (title.length < 2) { toast("目标至少写两个字", true); return; }
  try {
    const data = await api("/api/goal", {
      title,
      desc: $("#goal-desc").value.trim(),
      target_days: Number($("#goal-days").value) || 30,
    });
    S = data.state;
    $("#goal-modal").hidden = true;
    renderAll();
    toast(data.result.msg || "目标已写入系统");
    if (data.result.ok) openSysModal("quest");
  } catch (err) {
    toast("目标写入失败：" + err.message, true);
  }
}

async function recordGoalProgress(id) {
  if (busy || !id) return;
  const objective = (S?.goals || []).find(g=>g.id === id)?.mode === "objective";
  const note = window.prompt(objective ? "记录过程与感想（完成度按真实成果核验）：" : "记一笔进展（可留空）：", "");
  if (note === null) return;
  try {
    const data = await api("/api/goal/progress", { id, note });
    S = data.state;
    renderAll();
    toast(data.result.msg || "目标进展已记录");
  } catch (err) {
    toast("记录失败：" + err.message, true);
  }
}

async function abandonGoal(id) {
  if (busy || !id) return;
  if (!window.confirm("确定放下这个目标？它会保留在已结束列表里。")) return;
  try {
    const data = await api("/api/goal/status", { id, status: "abandoned" });
    S = data.state;
    renderAll();
    toast(data.result.msg || "目标已放下");
  } catch (err) {
    toast("操作失败：" + err.message, true);
  }
}

/* ---------- 事件绑定与启动 ---------- */

function bind() {
  $("#btn-main-quest").onclick = () => {
    if (S?.ending) { endingShown = false; maybeShowEnding(); }
    else openSysModal("quest");
  };
  document.addEventListener("click", (e) => {
    const action = e.target.closest("[data-campaign-action]");
    if (action && !busy && !action.disabled) {
      closeSysModal();
      act("【主线】" + action.dataset.campaignAction);
      return;
    }
    const ending = e.target.closest(".ending-choice");
    if (ending && !ending.disabled) { chooseEnding(ending.dataset.partner); return; }
    const newGoal = e.target.closest("[data-new-goal]");
    if (newGoal && !newGoal.disabled) { openGoalModal(); return; }
    const advanceGoalBtn = e.target.closest("[data-goal-advance]");
    if (advanceGoalBtn && !advanceGoalBtn.disabled) {
      recordGoalProgress(advanceGoalBtn.dataset.goalAdvance);
      return;
    }
    const abandonGoalBtn = e.target.closest("[data-goal-abandon]");
    if (abandonGoalBtn && !abandonGoalBtn.disabled) {
      abandonGoal(abandonGoalBtn.dataset.goalAbandon);
      return;
    }
    if (e.target.closest("[data-view-ending]")) {
      closeSysModal();
      endingShown = false;
      maybeShowEnding();
    }
  });
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
  $("#goal-cancel").onclick = () => ($("#goal-modal").hidden = true);
  $("#goal-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) $("#goal-modal").hidden = true;
  });
  $("#goal-create").onclick = submitGoal;
  $("#sys-career").addEventListener("click", (e) => {
    const b = e.target.closest("button.cbtn");
    if (!b || busy) return;
    closeSysModal();
    act(`【事业】${b.dataset.cop}`);
  });
  $("#event-banner").addEventListener("click", (e) => {
    const b = e.target.closest("button.ev-opt");
    if (!b || busy) return;
    act(`【活动】${b.dataset.eid}:${b.dataset.oid}`);
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
  $("#chat-send").onclick = () => sendChatMessage();
  $("#sticker-btn").onclick = () => toggleStickerPanel();
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
  try { setReadingFocus(localStorage.getItem("sjl-reading-focus") === "on", false); } catch (_) { setReadingFocus(false, false); }
  $("#btn-reading-focus").onclick = () => setReadingFocus(document.body.dataset.readingFocus !== "true");
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
        return `<div class="hist-entry">${tag}第${s.turn}幕<br>${esc(s.text)}${s.chosen ? `<br><span class="dim">行动：${esc(storyChoiceLabel(s.chosen))}</span>` : ""}</div>`;
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
    if (e.target.closest("[data-atlas-control], .atlas-control")) return;
    const point = e.target.closest(".mplace");
    openMapModal(point?.dataset.place);
  });
  $("#map-canvas-big").addEventListener("click", (e) => {
    const country = e.target.closest(".mcountry");
    if (country) { mapLevel = "country"; mapCountry = country.dataset.country; mapCity = atlasCities(mapCountry)[0]?.name || ""; mapSearch = ""; $("#map-search").value = ""; renderBigMap(true); return; }
    const city = e.target.closest(".mcity");
    if (city) { mapLevel = "city"; mapCity = city.dataset.city; mapSearch = ""; $("#map-search").value = ""; renderBigMap(true); return; }
    const place = e.target.closest(".mplace");
    if (place) showPlaceDetail(place.dataset.city || mapCity,place.dataset.place);
  });
  $("#map-crumbs").addEventListener("click", (e) => {
    const c = e.target.closest("button.crumb"); if (!c || !c.dataset.lv) return;
    mapLevel = c.dataset.lv; mapSearch = ""; $("#map-search").value = ""; renderBigMap(true);
  });
  $("#map-search").addEventListener("input", (e) => { mapSearch = e.target.value; renderBigMap(true); });
  $("#map-country-select").addEventListener("change", (e) => {
    mapCountry = e.target.value || S.player.location?.country || "华夏"; mapCity = atlasCities(mapCountry)[0]?.name || ""; mapLevel = e.target.value ? "country" : "world";
    mapSearch = ""; $("#map-search").value = ""; renderBigMap(true);
  });
  $("#map-city-select").addEventListener("change", (e) => { mapCity = e.target.value; if (mapCity) mapCountry = allPlaces().find(p => p.city === mapCity)?.country || mapCountry; mapLevel = mapCity ? "city" : mapLevel === "world" ? "world" : "country"; mapSearch = ""; $("#map-search").value = ""; renderBigMap(true); });
  $("#map-type-select").addEventListener("change", (e) => { setMapType(e.target.value); });
  $("#map-type-filters").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-map-type]");
    if (chip) setMapType(chip.dataset.mapType);
  });
  $("#map-place-list").addEventListener("click", (e) => {
    const p = e.target.closest("[data-place]"); if (p) { focusMapPlace(p.dataset.city,p.dataset.place); return; }
    if (e.target.closest("[data-map-reset]")) { mapSearch = ""; mapType = ""; $("#map-search").value = ""; renderBigMap(true); }
  });
  $("#map-detail").addEventListener("click", (e) => {
    const go = e.target.closest("button.md-go"); if (go && !busy && !go.disabled) { travelTo(go.dataset.place); return; }
    const local = e.target.closest("button.md-local");
    if (local && !local.disabled && !busy) { closeMapModal(); act(`【地点】${local.dataset.activity}`); return; }
    if (e.target.closest("button.md-explore") && !busy) { closeMapModal(); act(`探索『${S.player.location?.place || "此地"}』周边`); }
  });
  $("#btn-atlas").onclick = () => openMapModal(undefined,"world");
  $("#btn-time").onclick = () => openLifeModal();
  $("#life-close").onclick = () => $("#life-modal").hidden = true;
  $("#life-modal").addEventListener("click", e => { if (e.target === e.currentTarget) $("#life-modal").hidden = true; });
  $("#time-form").addEventListener("submit", advanceGameTime);
  $("#time-activity").addEventListener("change",updateTimePreview);
  $("#time-days").addEventListener("input",updateTimePreview);
  $("#sys-career").addEventListener("submit",(e) => {
    e.preventDefault(); if (busy) return;
    const create = e.target.closest("#enterprise-create");
    if (create) { const name = $("#enterprise-name").value.trim(); if (!name) { toast("先为这份事业起个名字",true); return; } closeSysModal(); act(`【事业】${$("#enterprise-kind").value === "team" ? "收购战队" : "创办"} ${name}`); return; }
    const op = e.target.closest(".enterprise-operation");
    if (op) { const amount = Number(op.elements.namedItem("amount").value); if (!Number.isInteger(amount) || amount <= 0) { toast("请输入有效的正整数",true); return; } const verb = op.elements.namedItem("operation").value; closeSysModal(); act(`【事业】${verb} ${op.dataset.enterprise} ${amount}`); }
  });
  document.addEventListener("click",e => {
    if (e.target.closest("[data-open-map]")) { openMapModal(undefined,"world"); return; }
    if (e.target.closest("[data-open-life], [data-open-time]")) { openLifeModal(); return; }
    if (e.target.closest("[data-open-career], [data-open-status]")) { openSysModal("status"); return; }
    const preset = e.target.closest("[data-time-days]"); if (preset) { $("#time-days").value = preset.dataset.timeDays; updateTimePreview(); return; }
    const person = e.target.closest("[data-person]"); if (person) { showNpcDetail(person.dataset.person); return; }
    const rel = e.target.closest("[data-relation]");
    if (rel && !busy && !rel.disabled) { const mode = $("#relationship-mode")?.value || "exclusive"; $("#npc-modal").hidden = true; act(`【关系】${rel.dataset.npc}:${rel.dataset.relation}:${mode}`); return; }
    const action = e.target.closest("[data-world-action]");
    if (action && !busy && !action.disabled) { $("#life-modal").hidden = true; $("#npc-modal").hidden = true; closeSysModal(); act(action.dataset.worldAction); return; }
    if (e.target.closest("[data-mystery-place]")) { openMapModal("云顶天文台"); return; }
  });
  $$(".quick-row .chip[data-qa]").forEach((c) => c.onclick = () => {
    if (busy) return; if (!S) { $("#modal").hidden = false; return; }
    if (c.dataset.qa === "cultivate") { openLifeModal("train"); return; }
    act(c.dataset.qa === "explore" ? `探索『${S.player.location?.place || "此地"}』周边，寻找新的发现` : "环顾四周，观察人与环境的细节");
  });
  $("#map-modal-close").onclick = closeMapModal;
  $("#map-modal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeMapModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      const target = e.target.closest('.npc-card[role="button"], .mplace[role="button"], .mcountry[role="button"], .mcity[role="button"]');
      if (target) { e.preventDefault(); target.dispatchEvent(new MouseEvent("click", {bubbles:true})); }
    }
    const dialogs = [...$$('[role="dialog"]')].filter((d) => !d.hidden);
    const dialog = dialogs[dialogs.length - 1];
    if (e.key === "Tab" && dialog) {
      const fields = [...dialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, a[href], [tabindex="0"]')].filter((el) => el.getClientRects().length);
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
    $("#life-modal").hidden = true;
    $("#goal-modal").hidden = true;
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
  CityAtlas.mount(document);
  try { applyTheme(localStorage.getItem("sjl-theme")); }
  catch (e) { /* 隐私模式/存储异常不该废掉整页 */ }
  bind();
  loadCatalog();
  loadPhotos();
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
