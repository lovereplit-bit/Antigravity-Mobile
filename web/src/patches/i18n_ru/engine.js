/* Перевод текстов и атрибутов интерфейса на русский. */
var RU_ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
var RU_SKIP = 'pre, code, textarea, script, style, .xterm, .monaco-editor, .markdown, [contenteditable="true"], [data-no-i18n]';
var RU_RULES_C = RU_RULES.map(function (r) { return [new RegExp(r[0]), r[1]]; });
var RU_CACHE = Object.create(null);
var RU_MISSING = {};

function ruTranslate(s) {
  if (!s || s.length > 600) return s;
  var m = s.match(/^(\s*)([\s\S]*?)(\s*)$/);
  var core = m[2];
  if (!core || !/[A-Za-z]{2}/.test(core) || /[\u0400-\u04FF]/.test(core)) return s;
  var hit = RU_CACHE[core];
  if (hit === undefined) {
    hit = Object.prototype.hasOwnProperty.call(RU_DICT, core) ? RU_DICT[core] : null;
    if (hit === null) {
      for (var i = 0; i < RU_RULES_C.length; i++) {
        if (RU_RULES_C[i][0].test(core)) {
          hit = core.replace(RU_RULES_C[i][0], RU_RULES_C[i][1])
            .replace(/(\d+)\s*s\b/g, '$1 с').replace(/(\d+)\s*m\b/g, '$1 мин').replace(/(\d+)\s*h\b/g, '$1 ч');
          break;
        }
      }
    }
    if (hit === null && Object.prototype.hasOwnProperty.call(RU_DICT, core + ' ')) hit = RU_DICT[core + ' '].replace(/\s+$/, '');
    RU_CACHE[core] = hit;
  }
  if (hit === null) { RU_MISSING[core] = 1; return s; }
  return m[1] + hit + m[3];
}

function ruSkip(el) {
  try { return !!(el && el.closest && el.closest(RU_SKIP)); } catch (e) { return false; }
}

function ruNode(n) {
  if (n.nodeType === 3) {
    var p = n.parentNode;
    if (p && ruSkip(p)) return;
    var t = ruTranslate(n.nodeValue);
    if (t !== n.nodeValue) n.nodeValue = t;
  } else if (n.nodeType === 1) {
    if (ruSkip(n)) return;
    for (var i = 0; i < RU_ATTRS.length; i++) {
      var v = n.getAttribute && n.getAttribute(RU_ATTRS[i]);
      if (v) { var tv = ruTranslate(v); if (tv !== v) n.setAttribute(RU_ATTRS[i], tv); }
    }
    for (var c = n.firstChild; c; c = c.nextSibling) ruNode(c);
  }
}

var ruQueue = [], ruTimer = 0;
function ruFlush() {
  ruTimer = 0;
  var q = ruQueue; ruQueue = [];
  for (var i = 0; i < q.length; i++) { try { ruNode(q[i]); } catch (e) {} }
}
function ruSchedule(n) {
  ruQueue.push(n);
  if (!ruTimer) ruTimer = (window.requestAnimationFrame || setTimeout)(ruFlush);
}

function ruInstall() {
  if (window.__AG_I18N_RU__) return;
  window.__AG_I18N_RU__ = true;
  try { document.documentElement.lang = 'ru'; } catch (e) {}
  var obs = new MutationObserver(function (list) {
    for (var i = 0; i < list.length; i++) {
      var r = list[i];
      if (r.type === 'childList') { for (var j = 0; j < r.addedNodes.length; j++) ruSchedule(r.addedNodes[j]); }
      else if (r.type === 'characterData') ruSchedule(r.target);
      else if (r.type === 'attributes') ruSchedule(r.target);
    }
  });
  function start() {
    ruNode(document.body || document.documentElement);
    obs.observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: RU_ATTRS });
  }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
  window.__agI18n = { translate: ruTranslate, missing: function () { return Object.keys(RU_MISSING); } };
}
ruInstall();
