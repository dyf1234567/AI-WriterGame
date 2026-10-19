// 在轻量 DOM 替身中执行真实前端函数，验证首次加载、材料更新和阅读状态。
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, {
    innerHTML:'', textContent:'', dataset:{}, style:{}, disabled:false, hidden:false,
    scrollTop:37, scrollHeight:100, classList:{toggle(){}}, setAttribute(){},
    querySelector:()=>null, insertAdjacentHTML(){},
  });
  return elements.get(selector);
}
const context = vm.createContext({
  document:{querySelector:element, querySelectorAll:()=>[], body:{dataset:{}}, getElementById:element},
  localStorage:{getItem:()=> 'off',setItem(){}}, matchMedia:()=>({matches:false}),
  setTimeout, clearTimeout, setInterval, clearInterval, AbortController,
  fetch:async()=>({ok:true,json:async()=>({catalog:[
    {name:'专注咖啡',type:'consumable',use:{progress:5},price:20,cat:'修炼',desc:'自习'},
    {name:'香薰蜡烛',type:'tool',price:45,cat:'情趣',desc:'氛围'}]})}),
});
const source = fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
vm.runInContext(source.replace(/\ninit\(\);\s*$/, '\n'),context);
async function run() {
  // 没有存档时先取目录，不能因 S=null 中断；开局后同一目录立即可用。
  await vm.runInContext('loadCatalog()',context);
  vm.runInContext(`S={revision:1,server_date:'2026-10-18',last_sign_in:null,
    player:{world:'urban',realm:1,realm_progress:5,stats:{体魄:5},items:[
      {name:'系统抽奖券',count:10},{name:'下品灵石',count:20}],equipped:{},identity:{},location:{}},
    settings:{show_affinity:false},main_quest:{title:'修行',stage:1,desc:'测试',notes:[]},
    side_quests:[],story:[],npcs:[],inbox:[],map:{urban:[],xianxia:[]}};
    renderSys();`,context);
  assert.match(element('#sys-bag').innerHTML,/data-name="系统抽奖券">使用/);
  assert.match(element('#sys-shop').innerHTML,/香薰蜡烛/);
  assert.match(element('#shop-cats').innerHTML,/情趣/);
  vm.runInContext(`S.player.items.push({name:'香薰蜡烛',count:2}); renderSys();`,context);
  assert.match(element('#sys-bag').innerHTML,/bag-gift/);
  vm.runInContext(`S.player.items.find(i=>i.name==='香薰蜡烛').count=0;renderSys();`,context);
  element('#story-flow').innerHTML = 'reader position';
  vm.runInContext('renderAll()',context);
  assert.equal(element('#story-flow').innerHTML,'reader position');
  assert.equal(element('#story-flow').scrollTop,37);
  const output = {dataset:{},textContent:''};
  context.output = output;
  vm.runInContext(`typewrite(output,'完整正文')`,context);
  assert.equal(output.textContent,'完整正文');
  vm.runInContext(`S.player.items.push({name:'坏" onmouseover="x',desc:'" title="x',count:1});renderBag();`,context);
  assert.match(element('#bag').innerHTML,/&quot;/);
  assert.doesNotMatch(element('#bag').innerHTML,/onmouseover="x/);
  console.log('PASS: 首次目录加载、商城情趣分类、礼物入口即时刷新、阅读位置、关闭打字机和字符串转义');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
