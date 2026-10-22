const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/atlas.js'),'utf8'),context);
const atlas = context.CityAtlas;
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/atlas_state.json'),'utf8'));
const world = atlas.world(fixture);
assert.equal((world.match(/class="mcountry /g)||[]).length,6);
for (const country of fixture.map.countries) {
  assert.ok(world.includes(`data-country="${country.name}"`));
  const chart = atlas.country(fixture,country.name);
  assert.equal((chart.match(/class="mcity /g)||[]).length,fixture.map.cities[country.name].length);
  for (const city of fixture.map.cities[country.name]) {
    const html = atlas.city(fixture,city.name);
    const places = fixture.map.urban.filter(p=>p.city===city.name);
    assert.equal((html.match(/class="mplace /g)||[]).length,places.length,city.name);
    const boxes=[...html.matchAll(/data-map-label-box="([^"]+)"/g)].map(m=>m[1].split(',').map(Number));
    for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++) {
      const [x,y,w,h]=boxes[i], [a,b,c,d]=boxes[j];
      assert.ok(x+w<=a||a+c<=x||y+h<=b||b+d<=y,`${city.name}: destination labels overlap`);
    }
    const ids = text=>[...text.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
    const largeIds=ids(html),smallIds=ids(atlas.city(fixture,city.name,true));
    assert.equal(largeIds.length,new Set(largeIds).size);
    assert.ok(smallIds.every(id=>!largeIds.includes(id)),'preview and expanded map must not share definition IDs');
    for(const reference of html.matchAll(/(?:href="#|url\(#)([^"\)]+)["\)]/g)) assert.ok(largeIds.includes(reference[1]),reference[1]);
  }
}
const malicious=structuredClone(fixture);
malicious.map.urban[0].name='坏" onclick="alert(1)';
const escaped=atlas.city(malicious,'京都');
assert.doesNotMatch(escaped,/data-place="坏" onclick=/);
assert.match(escaped,/&quot;/);
assert.doesNotThrow(()=>atlas.city({map:{urban:[]}},'新城市'));
// Verify the shared viewport controller changes viewBox and resets exactly.
const events={};
const root={addEventListener(name,handler){events[name]=handler}};
const attributes={'data-ca-base':'0 0 960 620',viewBox:'0 0 960 620'};
const reset={textContent:'100%'};
const frame={querySelector(selector){return selector==='svg.cartography'?svg:reset}};
const svg={getAttribute:key=>attributes[key],setAttribute(key,value){attributes[key]=value},closest:()=>frame};
atlas.mount(root);
const click=action=>events.click({target:{closest:()=>({dataset:{mapAction:action},closest:()=>frame})},preventDefault(){},stopPropagation(){}});
click('in');assert.ok(Number(attributes.viewBox.split(' ')[2])<960);assert.equal(reset.textContent,'140%');
click('east');assert.ok(Number(attributes.viewBox.split(' ')[0])>100);
click('reset');assert.equal(attributes.viewBox,'0 0 960 620');assert.equal(reset.textContent,'100%');
// Routes belong beside the pins inside the clipped map layer, not directly under SVG.
const layer={children:[],insertBefore(child,before){assert.equal(before.parentNode,this);child.parentNode=this;this.children.splice(this.children.indexOf(before),0,child)}};
const pin=(name,point,current=false)=>{const classes=new Set(current?['current']:[]);return {parentNode:layer,dataset:{place:name,mapPoint:point},classList:{contains:k=>classes.has(k),toggle(k,on){on?classes.add(k):classes.delete(k)}},setAttribute(k,v){this[k]=v}}};
const start=pin('起点','100,100',true),destination=pin('终点','300,200');layer.children=[start,destination];
const routeSvg={querySelectorAll:()=>[start,destination],querySelector:()=>layer.children.find(n=>n.class==='ca-selected-route'),ownerDocument:{createElementNS(){return {children:[],setAttribute(k,v){this[k]=v},appendChild(n){this.children.push(n)},remove(){this.parentNode.children=this.parentNode.children.filter(n=>n!==this)}}}},insertBefore(){throw new Error('reference is inside a nested layer')}};
atlas.highlight({querySelector:()=>routeSvg},'终点');
assert.equal(layer.children[0].children.length,2);
assert.equal(destination['aria-pressed'],'true');
atlas.highlight({querySelector:()=>routeSvg},'起点');
assert.equal(layer.children.length,2,'selecting the current place removes the old route');
// A deliberate pointer drag pans the viewport and releases the dragging state.
const dragClasses=new Set();svg.classList={add:k=>dragClasses.add(k),remove:k=>dragClasses.delete(k)};
svg.closest=selector=>selector==='.ca-compact'?null:frame;svg.getBoundingClientRect=()=>({width:960,height:620});
const ground={closest:selector=>selector==='svg.cartography'?svg:null};
events.pointerdown({target:ground,button:0,pointerId:1,clientX:200,clientY:200});
events.pointermove({pointerId:1,clientX:240,clientY:220,preventDefault(){}});
assert.equal(attributes.viewBox,'-40 -20 960 620');assert.ok(dragClasses.has('ca-dragging'));
events.pointerup();assert.ok(!dragClasses.has('ca-dragging'));
console.log('PASS: 6国16城118地点、地标标签避让、SVG引用隔离、文本转义、路线高亮、地图缩放/平移/复位与拖动');
