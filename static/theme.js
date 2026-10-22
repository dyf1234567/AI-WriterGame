/* Shared appearance controls for the game and the GM workspace. */
(() => {
  "use strict";
  const themes = Object.freeze(["night", "ink", "parchment", "qinglan"]);
  const names = Object.freeze({night:"夜蓝", ink:"墨纸", parchment:"书页", qinglan:"青岚"});
  const key = "sjl-theme";
  const valid = value => themes.includes(value) ? value : "night";
  const stored = () => { try { return valid(localStorage.getItem(key)); } catch (_) { return "night"; } };
  let selected = stored();
  const current = () => valid(document.body?.dataset.theme || selected);
  function sync(value) {
    selected = valid(value);
    if (document.documentElement.dataset.theme !== selected) document.documentElement.dataset.theme = selected;
    document.documentElement.style.colorScheme = selected === "parchment" ? "light" : "dark";
    document.querySelectorAll("[data-theme-choice], button[data-theme]").forEach(button => {
      const choice = button.dataset.themeChoice || button.dataset.theme;
      const active = choice === selected;
      button.setAttribute("aria-pressed", String(active));
      button.classList.toggle("active", active);
    });
  }
  function apply(value, options = {}) {
    const next = valid(value);
    if (document.body && document.body.dataset.theme !== next) document.body.dataset.theme = next;
    sync(next);
    if (options.persist !== false) {
      try { localStorage.setItem(key, next); } catch (_) { /* Appearance still works without storage. */ }
    }
    return next;
  }
  function bind() {
    apply(selected, {persist:false});
    document.addEventListener("click", event => {
      const button = event.target.closest("[data-theme-choice], button[data-theme]");
      if (!button) return;
      apply(button.dataset.themeChoice || button.dataset.theme);
    });
    if (typeof MutationObserver !== "undefined") {
      new MutationObserver(() => sync(document.body.dataset.theme)).observe(document.body, {
        attributes:true, attributeFilter:["data-theme"],
      });
    }
  }
  window.CityTheme = Object.freeze({apply, current, themes, names});
  sync(selected);
  window.addEventListener("storage", event => {
    if (event.key === key) apply(event.newValue, {persist:false});
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind, {once:true});
  else bind();
})();
