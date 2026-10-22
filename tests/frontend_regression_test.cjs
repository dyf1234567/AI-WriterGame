// 在轻量 DOM 替身中执行真实前端函数，验证首次加载、材料更新和阅读状态。
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, {
    innerHTML:'', textContent:'', dataset:{}, style:{}, disabled:false, hidden:false,
    scrollTop:37, scrollHeight:100, classList:{toggle(){}}, setAttribute(){},
    querySelector:()=>null, insertAdjacentHTML(){}, addEventListener(){},
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
const atlasSource = fs.readFileSync(require('node:path').join(__dirname,'../static/atlas.js'),'utf8');
// VM 的顶层全局对严格模式赋值有特殊宽容；普通函数执行必须也能通过。
// 旧版 photoFallback = function ... 会在这里直接抛 ReferenceError。
assert.doesNotThrow(() => new Function('document', source.replace(/\ninit\(\);\s*$/, '\n'))({
  querySelector:element, querySelectorAll:()=>[],
}));
vm.runInContext(atlasSource,context);
vm.runInContext(source.replace(/\ninit\(\);\s*$/, '\n'),context);
async function run() {
  const startupElements = new Map();
  const startupElement = (selector) => {
    if (!startupElements.has(selector)) startupElements.set(selector, {
      innerHTML:'', textContent:'', hidden:true, dataset:{}, style:{}, value:'',
      classList:{toggle(){}}, addEventListener(){}, setAttribute(){},
    });
    return startupElements.get(selector);
  };
  const startup = vm.createContext({
    document:{querySelector:startupElement, querySelectorAll:()=>[], body:{dataset:{}}, addEventListener(){}},
    localStorage:{getItem:()=>null,setItem(){}}, matchMedia:()=>({matches:false}),
    setTimeout,clearTimeout,setInterval,clearInterval,AbortController,
    fetch:async(path)=>({ok:true,json:async()=>path==='/api/state'
      ? {exists:false,demo_mode:true} : {catalog:[],photos:{}}}),
  });
  // 执行完整 init 和事件绑定，确保无存档时真正打开新游戏入口。
  vm.runInContext(atlasSource,startup);
  await vm.runInContext('(async function(){\n' + source.replace(/\ninit\(\);\s*$/, '\nawait init();\n') + '\n})()',startup);
  assert.equal(startupElement('#modal').hidden,false);
  assert.equal(typeof startupElement('#btn-start').onclick,'function');
  assert.equal(startupElement('#demo-badge').hidden,false);
  assert.equal(startupElement('#toast').textContent,'');
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
  vm.runInContext('setReadingFocus(true)',context);
  assert.equal(context.document.body.dataset.readingFocus,'true');
  assert.equal(element('#btn-reading-focus').textContent,'返回互动');
  assert.equal(element('#story-flow').scrollTop,37);
  vm.runInContext('setReadingFocus(false)',context);
  assert.equal(context.document.body.dataset.readingFocus,'false');
  assert.equal(element('#btn-reading-focus').textContent,'专注阅读');
  const output = {dataset:{},textContent:''};
  context.output = output;
  vm.runInContext(`typewrite(output,'完整正文')`,context);
  assert.equal(output.textContent,'完整正文');
  vm.runInContext(`S.player.items.push({name:'坏" onmouseover="x',desc:'" title="x',count:1});renderBag();`,context);
  assert.match(element('#bag').innerHTML,/&quot;/);
  assert.doesNotMatch(element('#bag').innerHTML,/onmouseover="x/);
  vm.runInContext(`PHOTOS={测试:{自拍:['/selfie.jpg'],美食:[],风景:['/view.jpg']}}`,context);
  assert.equal(vm.runInContext(`npcPickPhoto('测试','美食')`,context),'');
  assert.equal(vm.runInContext(`npcPickPhoto('测试','风景')`,context),'/view.jpg');
  assert.match(vm.runInContext(`photoImgHTML('测试','自拍')`,context),/data-ext-idx="-1"/);
  const failedPhoto = {dataset:{extIdx:'-1',pname:'测试',pcap:'自拍'},src:'',onerror(){}};
  context.failedPhoto = failedPhoto;
  vm.runInContext(`photoFallback(failedPhoto)`,context);
  assert.equal(failedPhoto.src,'/static/images/npc/%E6%B5%8B%E8%AF%95.svg');
  assert.equal(vm.runInContext(`npcLabelHTML({label:'初识',affinity:80})`,context),'');
  assert.match(vm.runInContext(`npcLabelHTML({label:'同班同学'})`,context),/称呼 · 同班同学/);
  vm.runInContext(`S.campaign={chapter:0,title:'星河计划',objective:'选择参与方向',actions:[{id:'route_study',label:'学业方向'}],finale_ready:false}; S.ending_options=[{name:'梁雅婷',label:'与梁雅婷同行'}]; renderQuests();`,context);
  assert.match(element('#quest-main').innerHTML,/data-campaign-action="route_study"/);
  assert.doesNotMatch(element('#quest-main').innerHTML,/ending-choice/);
  assert.doesNotMatch(element('#quest-main').innerHTML,/随等级推进/);
  assert.equal(vm.runInContext(`storyChoiceLabel('【主线】route_study')`,context),'学业方向');
  assert.equal(vm.runInContext(`storyChoiceLabel('【主线】old_action')`,context),'继续主线');
  vm.runInContext(`S.campaign.finale_ready=true;renderQuests();`,context);
  assert.match(element('#quest-main').innerHTML,/data-partner="梁雅婷"/);
  assert.match(element('#quest-main').innerHTML,/独自启程/);
  vm.runInContext(`S.npc_total=0;renderCodex();`,context);
  assert.doesNotMatch(element('#codex-people').innerHTML,/codex-unknown/);
  vm.runInContext(`S.npc_total=35;renderCodex();`,context);
  assert.match(element('#codex-people').innerHTML,/还有 35 人/);
  vm.runInContext(`S.ending={title:'星河之后',text:'你们完成了这一学期的共同作品。',partner:null};maybeShowEnding();`,context);
  assert.equal(element('#ending-text').textContent,'你们完成了这一学期的共同作品。');
  assert.doesNotMatch(element('#ending-text').textContent,/毕业/);
  vm.runInContext(`S.ending=null;S.campaign.finale_ready=true;
    globalThis.endingChoiceCheck={closed:0,calls:[]};
    renderAll=()=>{};closeSysModal=()=>endingChoiceCheck.closed++;
    api=async(path,body)=>{endingChoiceCheck.calls.push({path,body});return {state:S,result:{ok:false,msg:'还缺少共同经历'}}};`,context);
  await vm.runInContext(`chooseEnding('梁雅婷')`,context);
  assert.equal(vm.runInContext('endingChoiceCheck.closed',context),0);
  assert.equal(element('#toast').textContent,'还缺少共同经历');
  vm.runInContext(`api=async(path,body)=>{endingChoiceCheck.calls.push({path,body});return {state:S,result:{ok:true,msg:'本季终章已写入回忆'}}};`,context);
  await vm.runInContext(`chooseEnding(null)`,context);
  assert.equal(vm.runInContext('endingChoiceCheck.closed',context),1);
  assert.equal(vm.runInContext('endingChoiceCheck.calls[1].body.partner',context),null);
  assert.equal(element('#toast').textContent,'本季终章已写入回忆');
  console.log('PASS: 严格模式与完整启动、目录与礼物入口、阅读位置、图片分类与回退、关系称呼、主线操作、终章选择和图鉴计数');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
