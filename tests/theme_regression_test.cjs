const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const source = fs.readFileSync(require('node:path').join(__dirname, '../static/theme.js'), 'utf8');
function page(initial = 'night', blockedStorage = false) {
  const storage = new Map([['sjl-theme', initial]]);
  const buttons = ['night', 'ink', 'parchment', 'qinglan'].map(theme => ({
    dataset:{theme, themeChoice:theme}, attrs:{}, active:false,
    setAttribute(name, value) { this.attrs[name] = value; },
    classList:{toggle(name, active) { this.owner.active = active; }},
  }));
  buttons.forEach(button => button.classList.owner = button);
  // The GM page can use data-theme-choice on its own, without the old .theme-dot hook.
  const gmButton = {dataset:{themeChoice:'parchment'}, attrs:{}, active:false,
    setAttribute(name, value) { this.attrs[name] = value; },
    classList:{toggle(name, active) { gmButton.active = active; }}};
  buttons.push(gmButton);
  const events = {};
  const windowEvents = {};
  let observe;
  const document = {readyState:'complete', body:{dataset:{theme:'night'}},
    documentElement:{dataset:{}, style:{}}, querySelectorAll() { return buttons; },
    addEventListener(type, handler) { events[type] = handler; }};
  const window = {addEventListener(type, handler) { windowEvents[type] = handler; }};
  const context = vm.createContext({document, window,
    localStorage:{getItem(key) { if (blockedStorage) throw Error('disabled'); return storage.get(key); },
      setItem(key,value) { if (blockedStorage) throw Error('disabled'); storage.set(key,value); }},
    MutationObserver:class { constructor(callback) { observe = callback; } observe() {} },
  });
  vm.runInContext(source, context);
  return {document, window, buttons, storage, events, windowEvents, observe};
}

const game = page('parchment');
assert.equal(game.document.body.dataset.theme, 'parchment');
assert.equal(game.document.documentElement.style.colorScheme, 'light');
assert.equal(game.buttons[2].attrs['aria-pressed'], 'true');
assert.equal(game.buttons[0].attrs['aria-pressed'], 'false');
for (const theme of ['night','ink','qinglan','parchment']) {
  const button = game.buttons.find(button => button.dataset.theme === theme);
  game.events.click({target:{closest() { return button; }}});
  assert.equal(game.window.CityTheme.current(), theme);
  assert.equal(game.storage.get('sjl-theme'), theme);
  assert.equal(game.buttons.filter(button => button.dataset.theme).filter(button => button.active).length, 1);
  assert.equal(button.attrs['aria-pressed'], 'true');
}
// A storage event from the GM page changes the live game's appearance immediately.
game.windowEvents.storage({key:'sjl-theme', newValue:'ink'});
assert.equal(game.document.body.dataset.theme, 'ink');
assert.equal(game.document.documentElement.dataset.theme, 'ink');
assert.equal(game.buttons[1].attrs['aria-pressed'], 'true');
// The pre-existing applyTheme function changes body.dataset; the shared observer catches it.
game.document.body.dataset.theme = 'qinglan';
game.observe();
assert.equal(game.document.documentElement.dataset.theme, 'qinglan');
assert.equal(game.buttons[3].attrs['aria-pressed'], 'true');
game.events.click({target:{closest() { return game.buttons[4]; }}});
assert.equal(game.window.CityTheme.current(), 'parchment');
assert.equal(game.buttons[4].attrs['aria-pressed'], 'true');
assert.equal(page('invalid').window.CityTheme.current(), 'night');
const blocked = page('parchment', true);
assert.equal(blocked.window.CityTheme.apply('qinglan'), 'qinglan');
assert.equal(blocked.document.body.dataset.theme, 'qinglan');
console.log('PASS: 四种配色、刷新恢复、按钮选中状态、GM/游戏跨页同步、旧主题逻辑兼容、禁用存储降级');
