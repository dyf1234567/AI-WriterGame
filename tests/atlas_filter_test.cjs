// Run the real map UI and SVG renderers in a small DOM fixture; no service or saves.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const nodes = new Map();
function el(selector) {
  if (!nodes.has(selector)) nodes.set(selector, {
    innerHTML: '', textContent: '', dataset: {}, style: {}, hidden: true, disabled: false,
    value: '', scrollTop: 0, scrollHeight: 100, events: {},
    classList: {toggle(){}}, setAttribute(){}, getClientRects(){return [{}];},
    addEventListener(type, handler){this.events[type]=handler;},
    querySelector(){return null;}, focus(){}, insertAdjacentHTML(){},
  });
  return nodes.get(selector);
}
const context = vm.createContext({
  document: {querySelector: el, querySelectorAll: () => [], body: {dataset:{}}, addEventListener(){}},
  localStorage: {getItem(){return 'off';}, setItem(){}}, matchMedia: () => ({matches:false}),
  setTimeout, clearTimeout, setInterval, clearInterval, AbortController,
  fetch: async () => ({ok:true, json:async()=>({catalog:[]})}),
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/atlas.js'),'utf8'),context);
const source = fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
vm.runInContext(source.replace(/\ninit\(\);\s*$/, '\n'),context);
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/atlas_state.json'),'utf8'));
fixture.player.items = [{name:'华夏币',count:1000}];
fixture.npcs = [];
fixture.atlas = {routes:{}};
context.fixture = fixture;
vm.runInContext('S=fixture;bind();openMapModal();',context);

const run = code => vm.runInContext(code,context);
const read = code => JSON.parse(run(`JSON.stringify(${code})`));
const sorted = values => [...new Set(values)].sort();
function attributeNames(html, kind, attribute) {
  return [...html.matchAll(new RegExp(`<[^>]+class="${kind}\\b[^>]*\\b${attribute}="([^"]+)"`, 'g'))].map(match=>match[1]);
}
function listNames() { return attributeNames(el('#map-place-list').innerHTML,'place-list-item','data-place'); }
function pinNames(kind, attribute) { return attributeNames(el('#map-canvas-big').innerHTML,kind,attribute); }
function chooseType(type) {
  const select=el('#map-type-select');select.value=type;
  select.events.change({target:select});
}
function clickType(type) {
  el('#map-type-filters').events.click({target:{closest:selector=>selector==='[data-map-type]'?{dataset:{mapType:type}}:null}});
}
function assertTypeSelected(type) {
  assert.equal(run('mapType'),type);
  assert.equal(el('#map-type-select').value,type,'dropdown must follow shortcut selection');
  assert.match(el('#map-type-filters').innerHTML,new RegExp(`data-map-type="${type}" aria-pressed="true"`));
  assert.equal((el('#map-type-filters').innerHTML.match(/aria-pressed="true"/g)||[]).length,1);
}
function pointMap(svg) {
  return Object.fromEntries([...svg.matchAll(/class="mplace\b[^>]*data-place="([^"]+)"[^>]*data-map-point="([^"]+)"/g)].map(match=>[match[1],match[2]]));
}

// The native dropdown and one-click type chips operate on the same map state.
chooseType('nature');assertTypeSelected('nature');
const nature=fixture.map.urban.filter(place=>place.city==='京都'&&place.type==='nature');
assert.deepEqual(sorted(listNames()),sorted(nature.map(place=>place.name)));
assert.deepEqual(sorted(pinNames('mplace','data-place')),sorted(nature.map(place=>place.name)));
assert.ok(!listNames().includes(fixture.player.location.place),'current campus is not a nature result');
assert.ok(!pinNames('mplace','data-place').includes(fixture.player.location.place),'current pin must not bypass type filtering');
clickType('culture');assertTypeSelected('culture');
assert.deepEqual(sorted(listNames()),sorted(fixture.map.urban.filter(place=>place.city==='京都'&&place.type==='culture').map(place=>place.name)));

// Type counts use the geographical/search scope, before filtering by the chosen type.
const kyotoCount=fixture.map.urban.filter(place=>place.city==='京都').length;
assert.match(el('#map-type-filters').innerHTML,new RegExp(`data-map-type=""[^>]*><span>全部</span><span class="map-type-count">${kyotoCount}</span>`));
assert.match(el('#map-type-filters').innerHTML,new RegExp(`data-map-type="nature"[^>]*><span>郊野</span><span class="map-type-count">${nature.length}</span>`));

// Kyoto has no secret location; the empty state still exposes reset and other types.
chooseType('secret');assertTypeSelected('secret');
assert.deepEqual(listNames(),[]);
assert.deepEqual(pinNames('mplace','data-place'),[]);
assert.match(el('#map-place-list').innerHTML,/data-map-reset/);
assert.match(el('#map-type-filters').innerHTML,/data-map-type="campus"/);
el('#map-place-list').events.click({target:{closest:selector=>selector==='[data-map-reset]'?{}:null}});
assertTypeSelected('');
assert.equal(listNames().length,kyotoCount);
assert.equal(pinNames('mplace','data-place').length,kyotoCount);

// Filtering a world map suppresses unrelated countries, then a country suppresses
// unrelated cities. The matching place list is the common source at both levels.
run('mapLevel="world";mapSearch="";setMapType("secret");');
const secrets=fixture.map.urban.filter(place=>place.type==='secret');
assert.deepEqual(sorted(listNames()),sorted(secrets.map(place=>place.name)));
assert.deepEqual(sorted(pinNames('mcountry','data-country')),sorted(secrets.map(place=>place.country)));
run('mapLevel="country";mapCountry="华夏";renderBigMap(true);');
const domesticSecrets=secrets.filter(place=>place.country==='华夏');
assert.deepEqual(sorted(listNames()),sorted(domesticSecrets.map(place=>place.name)));
assert.deepEqual(sorted(pinNames('mcity','data-city')),sorted(domesticSecrets.map(place=>place.city)));
assert.ok(!pinNames('mcity','data-city').includes('京都'),'current city is not a secret destination');

// Explicit empty visible-place sets must remain empty, rather than mean no filter.
assert.deepEqual(attributeNames(run('CityAtlas.world(S,[])'),'mcountry','data-country'),[]);
assert.deepEqual(attributeNames(run('CityAtlas.country(S,"华夏",[])'),'mcity','data-city'),[]);
assert.deepEqual(attributeNames(run('CityAtlas.city(S,"京都",false,"",[])'),'mplace','data-place'),[]);

// Shared entities cannot keep the current country visible when all matches are abroad.
const foreign=fixture.map.urban.find(place=>place.country==='东瀛');
context.onlyForeign=[foreign];
assert.deepEqual(attributeNames(run('CityAtlas.world(S,onlyForeign)'),'mcountry','data-country'),['东瀛']);

// A type changes visibility, never the geographical pin placement. Colliding real
// locations exercise label avoidance, where computing layout after filtering moved pins.
const colliding=structuredClone(fixture);
const pair=colliding.map.urban.filter(place=>place.city==='京都').slice(0,2);
assert.notEqual(pair[0].type,pair[1].type,'fixture needs two distinct destination types');
for(const place of pair){place.x=50;place.y=50;}
context.colliding=colliding;
const allPoints=pointMap(run('CityAtlas.city(colliding,"京都")'));
context.secondType=pair[1].type;
const filteredPoints=pointMap(run('CityAtlas.city(colliding,"京都",false,secondType)'));
assert.ok(filteredPoints[pair[1].name]);
for(const [name,point] of Object.entries(filteredPoints)) assert.equal(point,allPoints[name],`${name}: filtering must not relocate the landmark`);

// Search remains global and type constrained; choosing a remote result switches
// the actual city chart before showing detail, rather than only swapping text.
run('mapLevel="city";mapCountry="华夏";mapCity="京都";mapSearch="樱京";setMapType("city");');
const remoteResults=fixture.map.urban.filter(place=>place.city==='樱京'&&place.type==='city');
assert.ok(remoteResults.length);
assert.deepEqual(sorted(listNames()),sorted(remoteResults.map(place=>place.name)));
assert.match(el('#map-results').textContent,/全世界搜索/);
const destination=remoteResults[0];
el('#map-place-list').events.click({target:{closest:selector=>selector==='[data-place]'?{dataset:{city:destination.city,place:destination.name}}:null}});
assert.equal(run('mapCountry'),'东瀛');assert.equal(run('mapCity'),'樱京');assert.equal(run('mapLevel'),'city');
assert.equal(run('mapSelectedPlace'),destination.name);
assert.equal(el('#map-detail').dataset.empty,'false');
assert.ok(el('#map-detail').innerHTML.includes(destination.name));
assert.ok(pinNames('mplace','data-place').includes(destination.name));
assert.deepEqual(sorted(pinNames('mplace','data-place')),sorted(remoteResults.map(place=>place.name)));
assertTypeSelected('city');

// The actual HTML must expose both forms of the control to users.
const html=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
assert.match(html,/id="map-type-select"/);assert.match(html,/id="map-type-filters"/);
console.log('PASS: 地图下拉与类型快捷筛选同步、类型计数、三级地图与列表一致、空结果清空、当前点不混入、坐标稳定、跨城搜索定位与详情');
