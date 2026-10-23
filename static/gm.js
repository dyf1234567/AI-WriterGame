"use strict";

const $id = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g,
  (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const money = (value) => Math.max(0, Number(value) || 0).toLocaleString("zh-CN");
const num = (id) => Number.parseInt($id(id).value || "0", 10) || 0;
const signed = (value) => `${Number(value) > 0 ? "+" : ""}${Number(value).toLocaleString("zh-CN")}`;
const GM = { revision:null, roster:[], selected:"", drafts:new Map(), customItems:[], shopDirty:false, pending:false };

function showMessage(id, message, error = false) {
  const node = $id(id);
  node.textContent = message;
  node.classList.toggle("err", error);
}
function errorMessage(data) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(row => row.msg || "请检查输入内容").join("；");
  return data?.result?.msg || "未能完成这次操作，请稍后重试。";
}
async function request(path, body) {
  const options = body === undefined ? {} : { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) };
  if (body !== undefined && GM.revision != null) options.headers["X-State-Revision"] = String(GM.revision);
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); }
  catch (_) { throw new Error("服务暂时无法返回结果，请重新读取后重试。"); }
  if (!response.ok || data.result?.ok === false) {
    if (response.status === 409) await loadGrantPanel().catch(() => {});
    throw new Error(errorMessage(data));
  }
  if (data.state) updateSummary(data.state);
  return data;
}
function updateSummary(state) {
  const player = state.player || {};
  const wallets = state.wallets || {};
  const count = (name) => (player.items || []).find(item => item.name === name)?.count || 0;
  GM.revision = state.revision ?? GM.revision;
  $id("player-name").textContent = player.name || "我的人生";
  $id("player-initial").textContent = (player.name || "人").slice(-1);
  const location = player.location || {};
  $id("player-detail").textContent = [player.identity?.urban, [location.city, location.place].filter(Boolean).join(" / ")].filter(Boolean).join(" · ");
  $id("summary-cash").textContent = money(wallets.cash ?? count("华夏币"));
  $id("summary-points").textContent = money(wallets.points ?? count("系统积分"));
  $id("connection-label").textContent = state.game_date ? `游戏日期 ${state.game_date}` : "当前存档已连接";
  $id("pinfo").textContent = "存档在线";
  $id("last-sync").textContent = "最近读取 " + new Date().toLocaleTimeString("zh-CN", {hour:"2-digit",minute:"2-digit"});
}
async function loadGrantPanel() {
  const [catalog, current] = await Promise.all([request("/api/gm/catalog"),request("/api/state/full")]);
  const selected = $id("g-item").value;
  $id("g-item").innerHTML = '<option value="">不发放物品</option>' + (catalog.items || []).map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join("");
  $id("g-item").value = (catalog.items || []).includes(selected) ? selected : "";
  if (current.exists && current.state) updateSummary(current.state);
  else {
    GM.revision = null;
    $id("pinfo").textContent = "尚无存档";
    $id("connection-label").textContent = "先在游戏中开启新的故事";
  }
  renderGrantPreview();
}
function grantEntries() {
  const entries = [];
  for (const [id,label] of [["g-cash","华夏币"],["g-gold","系统积分"],["g-ticket","抽奖券"],["g-prog","等级进度"],["g-power","修为"]]) {
    const value = num(id);
    if (value) entries.push([label,signed(value) + (id === "g-prog" ? "%" : "")]);
  }
  if ($id("g-item").value) entries.push([$id("g-item").value,"×" + Math.max(1,num("g-count"))]);
  if ($id("g-stat").value && num("g-statv")) entries.push([$id("g-stat").value,signed(num("g-statv"))]);
  return entries;
}
function renderGrantPreview() {
  const entries = grantEntries();
  $id("grant-preview").innerHTML = entries.length
    ? entries.map(([label,value]) => `<div class="receipt-line"><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("")
    : '<p class="preview-empty">填写左侧项目，<br>在这里查看调整内容。</p>';
}
async function submitGrant(event) {
  event.preventDefault();
  if (GM.pending) return;
  if (!grantEntries().length) { showMessage("grant-msg","先填写要调整的项目。",true); return; }
  const body = { gold:num("g-gold"), cash:num("g-cash"), ticket:num("g-ticket"), item:$id("g-item").value,
    item_count:Math.max(1,num("g-count")), stat:$id("g-stat").value, stat_value:num("g-statv"), progress:num("g-prog"), power:num("g-power") };
  GM.pending = true; $id("grant-btn").disabled = true; showMessage("grant-msg","正在调整…");
  try {
    const data = await request("/api/gm/grant",body);
    showMessage("grant-msg",data.result?.msg || "资源已调整。");
    for (const id of ["g-cash","g-gold","g-ticket","g-statv","g-prog","g-power"]) $id(id).value = "0";
    $id("g-item").value = ""; $id("g-stat").value = "";
    renderGrantPreview();
  } catch (error) { showMessage("grant-msg",error.message,true); }
  finally { GM.pending = false; $id("grant-btn").disabled = false; }
}
function markShopDirty() {
  GM.shopDirty = true;
  $id("shop-draft").textContent = "有尚未保存的配置";
  $id("shop-draft").classList.add("dirty");
}
function renderWeights() {
  const values = [0,1,2,3].map(index => Math.max(0,num("w-" + index)));
  const total = values.reduce((sum,value) => sum + value,0);
  const labels = ["普通","稀有","史诗","传说"];
  $id("weight-chart").innerHTML = values.map((value,index) => `<span class="${["common","rare","epic","legend"][index]}" style="width:${total ? value/total*100 : 0}%" title="${labels[index]} ${total ? (value/total*100).toFixed(1) : 0}%"></span>`).join("");
  $id("weight-chart").setAttribute("aria-label", total ? labels.map((label,index) => `${label}${(values[index]/total*100).toFixed(1)}%`).join("，") : "所有品质权重为零，请至少填写一项正数。");
}
function renderCustom(items) {
  GM.customItems = items;
  $id("custom-count").textContent = `${items.length} 件`;
  $id("c-list").innerHTML = items.length ? items.map((item,index) => `<div class="custom-item"><div><b>${esc(item.name)}</b><small>${esc(item.cat || "特殊")} · ${money(item.price)} 系统积分</small></div><div class="custom-actions"><button class="text-button" type="button" data-edit-item="${index}" aria-label="编辑${esc(item.name)}">编辑</button><button class="text-button remove-item" type="button" data-remove-item="${index}" aria-label="移除${esc(item.name)}">移除</button></div></div>`).join("") : '<p class="custom-empty">还没有自定义商品，可以在上方添加。</p>';
}
function editCustom(index) {
  const item = GM.customItems[index]; if (!item) return;
  $id("c-name").value = item.name;
  $id("c-price").value = item.price;
  $id("c-cat").value = item.cat || "特殊";
  $id("c-desc").value = item.desc || "";
  $id("c-use").value = item.use?.progress === 10 ? "progress10" : item.use?.progress === 5 ? "progress" : item.use?.stat?.["体魄"] === 1 ? "stat" : "";
  $id("c-name").focus();
  showMessage("c-msg","修改后加入清单，将替换同名商品。");
}
function addCustom() {
  const name = $id("c-name").value.trim();
  const price = num("c-price");
  if (!name) { showMessage("c-msg","请先填写商品名称。",true); $id("c-name").focus(); return; }
  if (price < 1 || price > 9999) { showMessage("c-msg","商品价格应为1—9999系统积分。",true); return; }
  const use = $id("c-use").value;
  const item = {name,desc:$id("c-desc").value.trim() || `${name}（主持人上架）`,price,cat:$id("c-cat").value};
  if (use === "progress") item.use = {progress:5};
  if (use === "progress10") item.use = {progress:10};
  if (use === "stat") item.use = {stat:{体魄:1}};
  renderCustom(GM.customItems.filter(row => row.name !== name).concat(item));
  markShopDirty();
  showMessage("c-msg",`「${name}」已加入清单，保存商城配置后生效。`);
  $id("c-name").value = ""; $id("c-desc").value = "";
}
async function loadShopPanel() {
  if (GM.shopDirty) return false;
  const data = await request("/api/gm/shop");
  const config = data.config || {}, rotation = config.rotation || {};
  $id("r-enabled").checked = rotation.enabled !== false;
  $id("r-slots").value = rotation.slots || 14;
  $id("r-period").value = rotation.period || "day";
  $id("r-pinned").value = (config.pinned || []).join("，");
  const weights = config.lottery?.weights || data.default_weights || {};
  ["普通","稀有","史诗","传说"].forEach((quality,index) => { $id("w-" + index).value = weights[quality] ?? 0; });
  $id("w-perday").checked = config.lottery?.per_day !== false;
  renderCustom(config.custom_items || []); renderWeights();
  $id("shop-note").textContent = "配置已连接";
  return true;
}
async function saveShop(event) {
  event.preventDefault();
  if (GM.pending) return;
  const weights = Object.fromEntries(["普通","稀有","史诗","传说"].map((quality,index) => [quality,num("w-" + index)]));
  if (Object.values(weights).some(value => value < 0 || value > 1000) || !Object.values(weights).some(value => value > 0)) {
    showMessage("shop-msg","品质权重须在0—1000之间，且至少一项大于零。",true); return;
  }
  const body = {rotation:{enabled:$id("r-enabled").checked,slots:num("r-slots"),period:$id("r-period").value},
    pinned:$id("r-pinned").value.split(/[,，]/).map(row => row.trim()).filter(Boolean),custom_items:GM.customItems,
    lottery:{weights,per_day:$id("w-perday").checked}};
  GM.pending = true; $id("shop-save").disabled = true; showMessage("shop-msg","正在保存…");
  try {
    const data = await request("/api/gm/shop",body);
    GM.shopDirty = false; $id("shop-draft").classList.remove("dirty");
    $id("shop-draft").textContent = "所有配置已保存";
    showMessage("shop-msg",data.result?.msg || "商城配置已保存。");
    await loadShopPanel();
    await loadGrantPanel();
  } catch (error) { showMessage("shop-msg",error.message,true); }
  finally { GM.pending = false; $id("shop-save").disabled = false; }
}
function currentDraft() {
  const person = GM.roster.find(row => row.name === GM.selected);
  if (!person || !$id("npc-persona")) return;
  const draft = {persona:$id("npc-persona").value,role:$id("npc-role").value,likes:$id("npc-likes").value};
  const changed = ["persona","role","likes"].some(key => draft[key] !== (person[key] || ""));
  if (changed) GM.drafts.set(person.name,draft); else GM.drafts.delete(person.name);
  if ($id("npc-draft")) $id("npc-draft").textContent = changed ? "有未保存修改" : "";
}
function filteredRoster() {
  const search = $id("roster-search").value.trim().toLocaleLowerCase();
  const filter = $id("roster-filter").value;
  return GM.roster.filter(person => (!search || [person.name,person.role,person.place].join(" ").toLocaleLowerCase().includes(search)) && (filter === "all" || filter === "known" && person.known || filter === "unknown" && !person.known));
}
function renderRoster() {
  const people = filteredRoster();
  $id("grid").innerHTML = people.length ? people.map(person => `<button type="button" class="roster-person" data-npc="${esc(person.name)}" aria-pressed="${person.name === GM.selected}" aria-label="编辑${esc(person.name)}的档案"><span class="person-monogram" aria-hidden="true">${esc(person.name.slice(-1))}</span><span class="person-info"><span class="person-title">${esc(person.name)}${person.known ? '<i title="已登场"></i>' : ''}${GM.drafts.has(person.name) ? '<small class="draft-badge">未保存</small>' : ''}</span><small>${esc(person.role || "身份待定")} · ${person.known ? "已登场" : "尚未登场"}</small></span><span class="person-place">${esc(person.place || "行踪未定")}</span></button>`).join("") : '<p class="roster-empty">没有找到符合条件的角色。<br>可以更换关键词或出场状态。</p>';
  $id("roster-count").textContent = `${people.length} / ${GM.roster.length} 位`;
  $id("summary-known").textContent = GM.roster.filter(person => person.known).length;
  $id("summary-total").textContent = " / " + GM.roster.length;
}
function selectPerson(name, focus = false, captureDraft = true) {
  if (captureDraft) currentDraft();
  const person = GM.roster.find(row => row.name === name); if (!person) return;
  GM.selected = name;
  const draft = GM.drafts.get(name) || person;
  $id("npc-editor").innerHTML = `<form id="npc-form"><div class="dossier-heading"><div><h3>${esc(name)}</h3><div class="dossier-meta"><span>${person.known ? "已登场" : "尚未登场"}</span><span>${esc(person.place || "行踪未定")}</span></div></div><span class="dossier-seal" aria-hidden="true">${esc(name.slice(-1))}</span></div><div class="dossier-fields"><label class="field" for="npc-persona">性格与行为方式<textarea id="npc-persona" data-k="persona" maxlength="200" required placeholder="写下她的性格、动机与说话习惯">${esc(draft.persona || "")}</textarea><small>描述会用于之后的剧情演绎，最多200字。</small></label><div class="field-row"><label class="field" for="npc-role">身份<input id="npc-role" data-k="role" maxlength="30" value="${esc(draft.role || "")}"></label><label class="field" for="npc-likes">礼物偏好<input id="npc-likes" data-k="likes" maxlength="10" value="${esc(draft.likes || "")}"></label><label class="field" for="npc-affinity">好感（0-100）<input id="npc-affinity" data-k="affinity" type="number" min="0" max="100" step="1" value="${Number(draft.affinity ?? person.affinity ?? 0)}"></label></div></div><div class="form-footer"><button type="submit" class="button button-accent" id="npc-save">保存角色档案</button><span class="draft-badge" id="npc-draft">${GM.drafts.has(name) ? "有未保存修改" : ""}</span></div><p class="msg" id="npc-msg" role="status" aria-live="polite"></p><p class="dossier-footnote">切换角色或管理分区会保留本页尚未保存的修改。</p></form>`;
  $id("npc-form").addEventListener("submit",savePerson);
  $id("npc-form").addEventListener("input",() => { currentDraft(); renderRoster(); });
  renderRoster();
  if (focus && window.matchMedia("(max-width:980px)").matches) $id("npc-editor").scrollIntoView({block:"start",behavior:"auto"});
}
async function savePerson(event) {
  event.preventDefault();
  if (GM.pending) return;
  currentDraft();
  const name = GM.selected;
  const person = GM.roster.find(row => row.name === name);
  const values = GM.drafts.get(name) || person;
  const body = {npc:name,persona:String(values.persona || "").trim(),role:String(values.role || "").trim(),likes:String(values.likes || "").trim()};
  const aff = parseInt(String(values.affinity ?? ""), 10);
  if (!Number.isNaN(aff)) body.affinity = Math.max(0, Math.min(100, aff));
  if (!body.persona) { showMessage("npc-msg","请填写角色的性格与行为方式。",true); return; }
  GM.pending = true; $id("npc-save").disabled = true; showMessage("npc-msg","正在保存…");
  try {
    const data = await request("/api/gm/npc",body);
    Object.assign(person,data.result?.npc || body);
    GM.drafts.delete(name);
    selectPerson(name,false,false);
    showMessage("npc-msg",data.result?.msg || "角色档案已更新。");
  } catch (error) { showMessage("npc-msg",error.message,true); }
  finally { GM.pending = false; if ($id("npc-save")) $id("npc-save").disabled = false; }
}
async function loadRoster() {
  currentDraft();
  const data = await request("/api/gm/roster");
  GM.roster = data.npcs || [];
  renderRoster();
  if (GM.roster.length) {
    if (!GM.roster.some(person => person.name === GM.selected)) GM.selected = (GM.roster.find(person => person.known) || GM.roster[0]).name;
    // Keep active edits before the selected dossier is rebuilt.
    const form = $id("npc-form");
    if (form) form.remove();
    selectPerson(GM.selected);
  }
}
function switchSection(section) {
  if (!["grant","shop","roster"].includes(section)) return;
  currentDraft();
  document.querySelectorAll("[data-section]").forEach(button => {
    const active = button.dataset.section === section;
    button.classList.toggle("active",active);
    if (active) button.setAttribute("aria-current","page"); else button.removeAttribute("aria-current");
  });
  for (const name of ["grant","shop","roster"]) $id(name + "-section").hidden = name !== section;
}
async function reloadAll() {
  if (GM.pending) return;
  $id("reload").disabled = true;
  showMessage("hint","正在读取存档与配置…");
  const operations = [loadGrantPanel(),loadRoster(),loadShopPanel()];
  const results = await Promise.allSettled(operations);
  const failures = results.filter(result => result.status === "rejected");
  if (failures.length) showMessage("hint",failures.map(result => result.reason.message).join("；"),true);
  else showMessage("hint",GM.shopDirty || GM.drafts.size ? "最新数据已读取，本页尚未保存的编辑已保留。" : "存档、商城与角色档案已同步。");
  $id("reload").disabled = false;
}
function initGM() {
  document.querySelectorAll("[data-section]").forEach(button => button.addEventListener("click",() => switchSection(button.dataset.section)));
  $id("reload").addEventListener("click",reloadAll);
  $id("grant-form").addEventListener("submit",submitGrant);
  $id("grant-form").addEventListener("input",renderGrantPreview);
  $id("grant-form").addEventListener("change",renderGrantPreview);
  $id("shop-form").addEventListener("submit",saveShop);
  $id("shop-form").addEventListener("input",() => { markShopDirty(); renderWeights(); });
  $id("shop-form").addEventListener("change",markShopDirty);
  $id("c-add").addEventListener("click",addCustom);
  $id("c-list").addEventListener("click",event => {
    const edit = event.target.closest("[data-edit-item]"); if (edit) { editCustom(Number(edit.dataset.editItem)); return; }
    const remove = event.target.closest("[data-remove-item]");
    if (remove) { renderCustom(GM.customItems.filter((_row,index) => index !== Number(remove.dataset.removeItem))); markShopDirty(); }
  });
  $id("roster-search").addEventListener("input",renderRoster);
  $id("roster-filter").addEventListener("change",renderRoster);
  $id("grid").addEventListener("click",event => { const button = event.target.closest("[data-npc]"); if (button) selectPerson(button.dataset.npc,true); });
  reloadAll();
}
initGM();
