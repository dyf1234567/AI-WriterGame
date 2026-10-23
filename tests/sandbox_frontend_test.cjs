// Exercise the real UI against a small DOM fixture and representative server state.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
function el(selector) {
  if (!elements.has(selector)) elements.set(selector, {
    innerHTML:'', textContent:'', dataset:{}, style:{}, hidden:true, disabled:false,
    value:'', max:'', scrollTop:0, scrollHeight:100, classList:{toggle(){}},
    events:{},setAttribute(){}, getClientRects(){return [{}]}, addEventListener(type,handler){this.events[type]=handler},
    querySelector(){return null}, focus(){}, insertAdjacentHTML(){},
  });
  return elements.get(selector);
}
const documentEvents={};
const context = vm.createContext({document:{querySelector:el,querySelectorAll:()=>[],body:{dataset:{}},addEventListener(type,handler){documentEvents[type]=handler}},
  localStorage:{getItem:()=> 'off',setItem(){}},matchMedia:()=>({matches:false}),
  setTimeout,clearTimeout,setInterval,clearInterval,AbortController,MouseEvent:class {constructor(type,options){this.type=type;this.bubbles=options.bubbles}},
  fetch:async()=>({ok:true,json:async()=>({catalog:[]})}),
});
const js = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/atlas.js'),'utf8'),context);
vm.runInContext(js.replace(/\ninit\(\);\s*$/,'\n'),context);
context.fixture = {
  turn:5,game_date:'2026-09-06',time:{day:6,slot:2},settings:{show_affinity:true},
  player:{realm:1,realm_progress:5,stats:{体魄:5},identity:{urban:'京华大学学生'},equipped:{},
    items:[{name:'系统积分',count:80},{name:'华夏币',count:25},{name:'专注咖啡',count:1}],
    location:{country:'华夏',city:'京都',place:'京华大学'}},
  wallets:{cash_name:'华夏币',cash:25,points_name:'系统积分',points:80},
  clock_view:{day:6,hour:12,minute:0,label:'第6天 12:00',max_skip_days:1095,recent:[]},
  map:{countries:[{name:'华夏',x:66,y:36},{name:'东瀛',x:84,y:33}],cities:{华夏:[{name:'京都',x:48,y:24},{name:'魔都',x:74,y:58}],东瀛:[{name:'樱京',x:55,y:32}]},urban:[
    {name:'京华大学',country:'华夏',city:'京都',type:'campus',discovered:true,desc:'这里是校园',activities:[{label:'学习',minutes:90,fee:0}]},
    {name:'星桥录音棚',country:'华夏',city:'京都',type:'leisure',discovered:false,desc:'音乐创作',activities:[{label:'练习声乐',minutes:120,fee:15}]},
    {name:'星海传媒园',country:'华夏',city:'魔都',type:'city',desc:'制作与发行',activities:[]},
    {name:'樱京音乐学园',country:'东瀛',city:'樱京',type:'campus',desc:'音乐课程',activities:[]}]},
  atlas:{countries:2,cities:3,places:4,routes:{'京华大学':{cost:0,minutes:0,affordable:true},'星桥录音棚':{cost:0,minutes:30,mode:'步行',affordable:true},'星海传媒园':{cost:100,minutes:240,mode:'高铁',affordable:false}}},
  career_view:{domain:'娱乐',active_domain:'娱乐',stage_name:'歌手',role_options:{娱乐:['歌手','演员']},
    all_positions:[{domain:'娱乐',stage_name:'歌手',active_role:'歌手',weekly_income:30,ops:{},employees:[]},{domain:'商业',stage_name:'创业者',weekly_income:40,ops:{},employees:[]}],
    active_projects:[{name:'第一张单曲',domain:'娱乐',days_left:7,end_day:13},{name:'独立应用',domain:'商业',days_left:3,end_day:9}],
    enterprises:[{id:'ent_1',name:'星河传媒',kind:'company',cash:40,valuation:300,equity:{player:100},employees:[],ledger:[]},{id:'ent_2',name:'第一张单曲',kind:'work',cash:0,valuation:100,equity:{player:100},status:'draft',employees:[],ledger:[]}]},
  main_quest:{title:'成长',notes:[]},campaign:{title:'校园展演',objective:'选择方向',paused:false,actions:[{id:'route_music',label:'音乐方向'}]},
  world_view:{people:[{name:'梁雅婷',status:'正在采访',goal:'完成作品',next:{text:'去文化馆'},relationship:{status:'friend',label:'朋友'}}],
    arcs:[{name:'梁雅婷',title:'第一次采访',goal:'完成作品',stage:0,total:3,desc:'采访的人还没找到',due_day:20,choices:['【人物】梁雅婷:合作']}],
    mystery:{status:'active',stage:1,clues:['微光与设备短波同时出现'],choices:['【暗线】查阅','【暗线】搁置']}},
  npcs:[{name:'梁雅婷',role:'同学',affinity:75,bond:{trust:50,attraction:40},life:{status:'采访中'},boundaries:{},relationship:{status:'partner',label:'恋人',mode:'exclusive',mode_label:'专一',proposal:null},place:'京华大学',persona:'记者',memo:[],rels:{}}],
  goals:[],side_quests:[],story:[],inbox:[],dates:[],chats:{},
};
vm.runInContext('S=fixture;SHOP=[{name:"系统积分",price:1},{name:"华夏币",price:1},{name:"专注咖啡",price:20,type:"consumable",use:{progress:5}}];renderHeader();renderSystem();renderMap();renderSys();renderWorldLife();',context);
assert.match(el('#wallets').innerHTML,/华夏币/);
assert.match(el('#wallets').innerHTML,/系统积分/);
assert.match(el('#today-clock').textContent,/12:00/);
assert.match(el('#sys-currency').textContent,/系统积分 80/);
assert.match(el('#sys-career').innerHTML,/切换 商业/);
assert.match(el('#sys-career').innerHTML,/第一张单曲/);
assert.match(el('#sys-career').innerHTML,/独立应用/);
assert.match(el('#sys-career').innerHTML,/发行 ent_2 流媒体/);
assert.match(el('#sys-career').innerHTML,/收购战队/);
assert.match(el('#sys-career').innerHTML,/name="operation"/);
assert.doesNotMatch(el('#sys-bag').innerHTML,/bag-sell[^>]*data-name="(?:系统积分|华夏币)"/);
assert.match(el('#world-people').innerHTML,/正在采访/);
assert.match(el('#sys-world-arcs').innerHTML,/【人物】梁雅婷:合作/);
assert.match(el('#world-mystery').innerHTML,/【暗线】搁置/);
vm.runInContext('openMapModal();',context);
assert.match(el('#map-place-list').innerHTML,/星桥录音棚/);
assert.doesNotMatch(el('#map-place-list').innerHTML,/樱京音乐学园/);
vm.runInContext('mapSearch="音乐";renderBigMap();',context);
assert.match(el('#map-place-list').innerHTML,/樱京音乐学园/);
assert.match(el('#map-results').textContent,/全世界搜索/);
vm.runInContext('mapSearch="没有这个地点";renderBigMap();',context);
assert.match(el('#map-place-list').innerHTML,/清空筛选/);
vm.runInContext('mapSearch="";mapLevel="world";mapType="campus";renderBigMap();',context);
assert.match(el('#map-place-list').innerHTML,/京华大学/);
assert.match(el('#map-place-list').innerHTML,/樱京音乐学园/);
assert.doesNotMatch(el('#map-place-list').innerHTML,/星海传媒园/);
vm.runInContext('showPlaceDetail("魔都","星海传媒园")',context);
assert.match(el('#map-detail').innerHTML,/4小时/);
assert.match(el('#map-detail').innerHTML,/华夏币不足/);
assert.match(el('#map-detail').innerHTML,/md-go[^>]*disabled/);
vm.runInContext('showPlaceDetail("京都","星桥录音棚")',context);
assert.match(el('#map-detail').innerHTML,/30分钟/);
assert.match(el('#map-detail').innerHTML,/md-local[^>]*disabled/);
vm.runInContext('showPlaceDetail("京都","京华大学")',context);
assert.doesNotMatch(el('#map-detail').innerHTML,/md-local[^>]*disabled/);
assert.match(vm.runInContext('countrySVG("东瀛")',context),/data-city="樱京"/);
assert.doesNotMatch(vm.runInContext('countrySVG("东瀛")',context),/data-city="京都"/);
// Scope/filter changes reset both desktop and phone scroll containers and remove the old destination.
vm.runInContext('bind()',context);
for (const [selector,type,value] of [
  ['#map-country-select','change','东瀛'],['#map-city-select','change','魔都'],
  ['#map-type-select','change','campus'],['#map-search','input','音乐'],
]) {
  vm.runInContext('openMapModal();showPlaceDetail("京都","京华大学")',context);
  el('.atlas-geography').scrollTop=280;el('.atlas-layout').scrollTop=180;
  el(selector).events[type]({target:{value}});
  assert.equal(el('.atlas-geography').scrollTop,0,selector);
  assert.equal(el('.atlas-layout').scrollTop,0,selector);
  assert.equal(el('#map-detail').dataset.empty,'true',selector);
  assert.doesNotMatch(el('#map-detail').innerHTML,/京华大学/,selector);
  assert.equal(vm.runInContext('mapSelectedPlace',context),'',selector);
}
vm.runInContext('openMapModal();showPlaceDetail("京都","京华大学")',context);
el('.atlas-geography').scrollTop=280;el('.atlas-layout').scrollTop=180;
el('#map-crumbs').events.click({target:{closest:()=>({dataset:{lv:'world'}})}});
assert.equal(el('.atlas-geography').scrollTop,0);
assert.equal(el('#map-detail').dataset.empty,'true');
// Selecting a result after scrolling on a phone reveals the newly selected detail above the list.
el('.atlas-layout').scrollTop=500;
vm.runInContext('showPlaceDetail("樱京","樱京音乐学园")',context);
assert.equal(el('.atlas-layout').scrollTop,0);
assert.equal(el('#map-detail').dataset.empty,'false');
assert.match(el('#map-detail').innerHTML,/樱京音乐学园/);
// The focusable SVG nodes already support keyboard activation through the shared handler.
for (const kind of ['mplace','mcountry','mcity']) for(const key of ['Enter',' ']) {
  let prevented=false;let dispatched=null;
  const node={closest:selector=>selector.includes(`.${kind}[role="button"]`)?node:null,dispatchEvent:event=>{dispatched=event}};
  documentEvents.keydown({key,target:node,preventDefault(){prevented=true}});
  assert.equal(prevented,true,`${kind} ${key}`);
  assert.equal(dispatched.type,'click');assert.equal(dispatched.bubbles,true);
}
vm.runInContext('S.campaign.paused=true;renderQuests()',context);
assert.match(el('#quest-main').innerHTML,/data-campaign-action="resume"/);
assert.doesNotMatch(el('#quest-main').innerHTML,/data-campaign-action="route_music"/);
vm.runInContext('showNpcDetail("梁雅婷")',context);
assert.match(el('#npc-m-body').innerHTML,/你们的关系/);
assert.doesNotMatch(el('#npc-m-body').innerHTML,/data-relation=/);
assert.match(el('#npc-m-body').innerHTML,/【人物】梁雅婷:合作/);
// Server text is escaped in map and enterprise panels.
vm.runInContext('S.map.urban[1].name=\'坏" onclick="alert(1)\';mapLevel="world";mapType="";renderBigMap()',context);
assert.doesNotMatch(el('#map-place-list').innerHTML,/onclick="alert\(1\)/);
assert.match(el('#map-place-list').innerHTML,/&quot;/);
// The world shortcut opens the atlas; a named destination opens its actual city.
el('#btn-atlas').onclick();
assert.equal(vm.runInContext('mapLevel',context),'world');
assert.match(el('#map-canvas-big').innerHTML,/data-country="东瀛"/);
assert.match(el('#map-country-select').innerHTML,/<option value="" selected>全部国家/);
assert.match(el('#map-city-select').innerHTML,/樱京/);
assert.doesNotMatch(el('#map-crumbs').innerHTML,/data-lv="country"/);
el('#map-city-select').events.change({target:{value:'樱京'}});
assert.equal(vm.runInContext('mapCountry',context),'东瀛');
assert.equal(vm.runInContext('mapLevel',context),'city');
el('#map-country-select').events.change({target:{value:''}});
assert.equal(vm.runInContext('mapLevel',context),'world');
vm.runInContext('openMapModal("樱京音乐学园")',context);
assert.equal(vm.runInContext('mapCountry',context),'东瀛');
assert.equal(vm.runInContext('mapCity',context),'樱京');
assert.match(el('#map-canvas-big').innerHTML,/data-place="樱京音乐学园"/);
assert.doesNotMatch(el('#map-place-list').innerHTML,/京华大学/);
async function run() {
  vm.runInContext('globalThis.calls=[];api=async(path,body)=>{calls.push({path,body});return {state:S,result:{ok:true,msg:"已安排"}}};renderAll=()=>{};openLifeModal("train");',context);
  el('#time-days').value='30';el('#time-activity').value='train';el('#time-skill').value='vocal';
  await vm.runInContext('advanceGameTime({preventDefault(){}})',context);
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(calls[0])',context)),{path:'/api/time',body:{days:30,activity:'train',skill:'vocal'}});
  el('#time-days').value='1096';
  await vm.runInContext('advanceGameTime({preventDefault(){}})',context);
  assert.equal(vm.runInContext('calls.length',context),1);
  await vm.runInContext('travelTo("京华大学")',context);
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(calls[1])',context)),{path:'/api/travel',body:{destination:'京华大学'}});
  const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
  const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(ids.length,new Set(ids).size,'HTML IDs must be unique');
  for(const id of ['map-search','map-country-select','map-city-select','map-place-list','wallets','time-form','world-people','sys-world-arcs']) assert.ok(ids.includes(id));
  const css=fs.readFileSync(path.join(__dirname,'../static/style.css'),'utf8');
  assert.match(css,/prefers-reduced-motion/);assert.match(css,/min-height:48px/);assert.match(css,/max-width:640px/);
  assert.equal((css.match(/\{/g)||[]).length,(css.match(/\}/g)||[]).length,'CSS blocks must balance');
  console.log('PASS: 双钱包、多事业与资产入口、全世界搜索与筛选、路费/耗时/余额说明、地点活动、校园暂缓、关系协商与人物线、时间/旅行API、地图标注防重叠与转义、地图滚动与详情同步、地图键盘操作、响应式基础');
}
run().catch(err=>{console.error(err);process.exitCode=1;});
