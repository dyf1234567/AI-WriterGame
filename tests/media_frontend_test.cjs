const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
class Node {
  constructor(){this.dataset={};this.style={display:'none'};this.children=[];this.events={};this._html='';this.scrollHeight=100;}
  set innerHTML(value){this._html=value;if(this.host){const child=new Node();child.markup=value;child.video=value.includes('<video')?{}:null;this.children=[child];}}
  get innerHTML(){return this._html;}
  get firstElementChild(){return this.children[0];}
  replaceChildren(){this.children=[];}
  insertBefore(child,before){if(child.parent)child.remove();const i=before?this.children.indexOf(before):this.children.length;this.children.splice(i,0,child);child.parent=this;}
  remove(){if(this.parent){this.parent.children=this.parent.children.filter(x=>x!==this);this.parent=null;}}
  replaceWith(child){const parent=this.parent,i=parent.children.indexOf(this);parent.children[i]=child;child.parent=parent;this.parent=null;}
  addEventListener(type,fn){this.events[type]=fn;}
  querySelector(){return null;}
  focus(){}
}
const nodes=new Map(),el=s=>{if(!nodes.has(s))nodes.set(s,new Node());return nodes.get(s);};
let release;
const context=vm.createContext({document:{querySelector:el,querySelectorAll:()=>[],body:{dataset:{}},addEventListener(){},createElement(){const n=new Node();n.host=true;return n;}},localStorage:{getItem(){return 'off';},setItem(){}},setTimeout,clearTimeout,setInterval,clearInterval,AbortController,fetch:()=>new Promise(resolve=>release=resolve)});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8').replace(/\ninit\(\);\s*$/,'\n'),context);
const run=code=>vm.runInContext(code,context);
(async()=>{
  run('loadPhotos(); toggleStickerPanel(true)');
  assert.match(el('#sticker-panel').innerHTML,/正在读取素材/);
  const unsafe="x');globalThis.mediaInjected=1;('.svg";
  release({ok:true,json:async()=>({stickers:[{id:'sticker-one',name:unsafe,url:'/static/stickers/test.svg'}]})});
  await run('mediaLoading');
  const panel=el('#sticker-panel').innerHTML;
  assert.match(panel,/data-sticker-id="sticker-one"/);
  assert.doesNotMatch(panel,/onclick=/);
  assert.match(panel,/&#39;/);
  run(`S={chats:{测试:{msgs:[{id:'old-video',from:'npc',ts:'one',text:'视频给你',attachments:[{type:'video',url:'/static/videos/test.mp4',caption:'练琴'}]}]}}};chatWith='测试';renderChatBody(false)`);
  const message=el('#chat-body').children[0],video=message.video;
  assert.ok(video);
  run('renderChatBody(true)');
  assert.equal(el('#chat-body').children[0],message);
  assert.equal(el('#chat-body').children[0].video,video);
  assert.equal(el('#chat-body').children.length,2);
  run('openChat("测试")');
  assert.equal(el('#chat-body').children[0],message);
  assert.equal(el('#chat-body').children.length,1);
  run(`S.chats.测试.msgs.push({id:'mixed',from:'npc',text:'谢谢你',sticker:'哭哭',attachments:[{type:'sticker',caption:'哭哭',missing:true}]});renderChatBody()`);
  assert.doesNotMatch(el('#chat-body').children[1].markup,/bub-sticker/);
  assert.match(el('#chat-body').children[1].markup,/谢谢你/);
  assert.match(el('#chat-body').children[1].markup,/暂无匹配素材/);
  run(`S.chats.测试.msgs.push({id:'missing',from:'me',text:'',sticker:'未知'});renderChatBody()`);
  assert.match(el('#chat-body').children[2].markup,/表情包：未知/);
  assert.match(run(`attachmentHTML({type:'video',url:'/static/videos/a.mp4',caption:'练琴'})`),/onerror="mediaLoadError\(this\)"/);
  run('loadPhotos()');release({ok:false});await run('mediaLoading');
  assert.match(el('#sticker-panel').innerHTML,/素材读取失败/);
  run('loadPhotos()');release({ok:true,json:async()=>({stickers:[{id:'new-id',name:'新增',url:'/static/stickers/new.png'}]})});await run('mediaLoading');
  assert.match(el('#sticker-panel').innerHTML,/data-sticker-id="new-id"/);
  el('#chat-input').value='文件移除也要保留这段正文';
  run('var rejectedState=JSON.parse(JSON.stringify(S));api=async()=>({state:rejectedState,result:{ok:false,msg:"素材已移除"}});renderAll=()=>{};toast=()=>{}');
  await run('sendChatMessage("新增","new-id")');
  assert.equal(el('#chat-input').value,'文件移除也要保留这段正文');
  assert.equal(run('S.chats.测试.msgs.length'),3,'rejected message must not remain as an optimistic sent bubble');
  console.log('PASS: 素材慢加载恢复、刷新按钮、带引号表情名称、视频节点稳定、重新打开聊天、文字混合表情可读、缺失素材提示、加载失败提示');
})().catch(error=>{console.error(error);process.exitCode=1;});
