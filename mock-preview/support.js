// Runtime tối giản để xem mock `.dc.html` ở local (thay cho runtime của canvas claude.ai).
// Chỉ hỗ trợ phần cú pháp các màn mock đang dùng: {{path}}, <sc-for>, <sc-if>, sự kiện onX,
// class Component extends DCLogic { renderVals() } và setState. Không dùng cho production.
(function () {
  'use strict';

  const HOLE = /\{\{([^}]+)\}\}/g;
  const ONLY_HOLE = /^\s*\{\{([^}]+)\}\}\s*$/;
  const PROPS = new Set(['value', 'checked', 'disabled', 'selected', 'defaultvalue']);
  let template = null;
  let instance = null;
  let mount = null;

  class DCLogic {
    constructor(props) {
      this.props = props || {};
      this.state = {};
    }
    setState(patch) {
      const next = typeof patch === 'function' ? patch(this.state, this.props) : patch;
      this.state = Object.assign({}, this.state, next);
      render();
    }
    forceUpdate() { render(); }
  }
  window.DCLogic = DCLogic;

  function lookup(ctx, expr) {
    const path = expr.trim();
    if (path === 'true') return true;
    if (path === 'false') return false;
    if (path === 'null') return null;
    if (/^-?\d+(\.\d+)?$/.test(path)) return Number(path);
    if (/^'.*'$|^".*"$/.test(path)) return path.slice(1, -1);
    return path.split('.').reduce((obj, key) => (obj == null ? undefined : obj[key]), ctx);
  }

  function resolve(text, ctx) {
    const only = text.match(ONLY_HOLE);
    if (only) return { raw: true, value: lookup(ctx, only[1]) };
    return { raw: false, value: text.replace(HOLE, (_, p) => { const v = lookup(ctx, p); return v == null ? '' : String(v); }) };
  }

  function holeOf(attr) {
    return (attr || '').replace(/^\s*\{\{|\}\}\s*$/g, '');
  }

  function build(node, ctx, out) {
    if (node.nodeType === Node.TEXT_NODE) {
      const r = resolve(node.textContent, ctx);
      out.appendChild(document.createTextNode(r.raw ? (r.value == null ? '' : String(r.value)) : r.value));
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;

    if (node.tagName === 'TEMPLATE' && node.hasAttribute('data-sc-for')) {
      const list = lookup(ctx, holeOf(node.getAttribute('list'))) || [];
      const as = node.getAttribute('as') || 'item';
      list.forEach((item, index) => {
        const child = Object.create(ctx);
        child[as] = item;
        child.$index = index;
        node.content.childNodes.forEach((n) => build(n, child, out));
      });
      return;
    }
    if (node.tagName === 'TEMPLATE' && node.hasAttribute('data-sc-if')) {
      if (lookup(ctx, holeOf(node.getAttribute('value')))) node.content.childNodes.forEach((n) => build(n, ctx, out));
      return;
    }

    const el = document.createElementNS(node.namespaceURI, node.localName);
    const deferred = [];
    for (const attr of Array.from(node.attributes)) {
      const name = attr.name;
      if (name.startsWith('hint-')) continue;
      const r = resolve(attr.value, ctx);
      if (name.startsWith('on') && r.raw) {
        if (typeof r.value === 'function') el.addEventListener(name.slice(2), r.value);
        continue;
      }
      if (PROPS.has(name)) {
        if (r.raw && (r.value === false || r.value == null)) continue;
        deferred.push([name === 'defaultvalue' ? 'value' : name, r.raw ? r.value : r.value]);
        continue;
      }
      if (r.raw && (r.value === false || r.value == null) && !name.startsWith('aria-')) continue;
      let v = r.raw ? String(r.value) : r.value;
      // Ảnh tải lên canvas (/_blob/<id>) nằm ở mock-preview/_blob/<id>.png khi xem local.
      if (name === 'src' && /^\/_blob\/[0-9a-f]{32}$/.test(v)) v += '.png';
      el.setAttribute(name, v);
    }
    const children = node.tagName === 'TEMPLATE' ? node.content.childNodes : node.childNodes;
    children.forEach((n) => build(n, ctx, el));
    for (const [prop, value] of deferred) {
      if (prop === 'value') el.value = value == null ? '' : String(value);
      else el[prop] = value === '' ? true : !!value;
      if (prop === 'disabled' || prop === 'checked' || prop === 'selected') el.setAttribute(prop, '');
    }
    out.appendChild(el);
  }

  function render() {
    const scrollers = Array.from(mount.querySelectorAll('*')).filter((e) => e.scrollTop > 0).map((e) => [pathOf(e), e.scrollTop]);
    const windowY = window.scrollY;
    // Giữ focus + vị trí con trỏ khi vẽ lại toàn bộ (React giữ được, runtime này thì không).
    const active = mount.contains(document.activeElement) ? document.activeElement : null;
    const focusPath = active ? pathOf(active) : null;
    const selection = active && 'selectionStart' in active ? [active.selectionStart, active.selectionEnd] : null;
    const hadAutofocus = !!mount.querySelector('[data-autofocus]');
    const ctx = instance.renderVals();
    const frag = document.createDocumentFragment();
    template.content.childNodes.forEach((n) => build(n, ctx, frag));
    mount.replaceChildren(frag);
    for (const [path, top] of scrollers) {
      const target = byPath(path);
      if (target) target.scrollTop = top;
    }
    window.scrollTo(0, windowY);
    const auto = mount.querySelector('[data-autofocus]');
    if (auto && !hadAutofocus) {
      auto.focus();
    } else if (focusPath) {
      const target = byPath(focusPath);
      if (target && target.focus) {
        target.focus();
        if (selection && 'setSelectionRange' in target) {
          try { target.setSelectionRange(selection[0], selection[1]); } catch (e) { /* input type=date */ }
        }
      }
    }
  }

  function pathOf(el) {
    const path = [];
    while (el && el !== mount) {
      path.unshift(Array.prototype.indexOf.call(el.parentNode.children, el));
      el = el.parentNode;
    }
    return path;
  }

  function byPath(path) {
    let el = mount;
    for (const i of path) {
      el = el && el.children[i];
    }
    return el;
  }

  async function start() {
    const source = await (await fetch(location.href, { cache: 'no-store' })).text();
    const body = source.match(/<x-dc>([\s\S]*)<\/x-dc>/);
    const script = source.match(/<script type="text\/x-dc"[^>]*data-props='([^']*)'[^>]*>([\s\S]*?)<\/script>/);
    if (!body || !script) throw new Error('Không tìm thấy <x-dc> hoặc script data-dc-script');

    // <sc-for>/<sc-if> → <template> để parser HTML không đẩy chúng ra khỏi <table>/<select>.
    const markup = body[1]
      .replace(/<sc-for\b/g, '<template data-sc-for').replace(/<\/sc-for>/g, '</template>')
      .replace(/<sc-if\b/g, '<template data-sc-if').replace(/<\/sc-if>/g, '</template>');
    template = document.createElement('template');
    template.innerHTML = markup;

    const helmet = template.content.querySelector('helmet');
    if (helmet) {
      Array.from(helmet.children).forEach((child) => document.head.appendChild(child.cloneNode(true)));
      helmet.remove();
    }

    const Component = new Function('DCLogic', script[2] + '\nreturn Component;')(DCLogic);
    instance = new Component({});
    mount = document.createElement('div');
    mount.id = 'dc-root';
    document.body.replaceChildren(mount);
    document.body.style.visibility = '';
    render();
    if (typeof instance.componentDidMount === 'function') instance.componentDidMount();
  }

  document.documentElement.style.background = '#F5F6F8';
  // Canvas tự thêm viewport; file .dc.html không có, thiếu thì mobile vẽ ở 980px.
  if (!document.querySelector('meta[name="viewport"]')) {
    const meta = document.createElement('meta');
    meta.name = 'viewport';
    meta.content = 'width=device-width, initial-scale=1';
    document.head.appendChild(meta);
  }
  document.addEventListener('DOMContentLoaded', () => {
    document.body.style.visibility = 'hidden';
    start().catch((error) => {
      document.body.style.visibility = '';
      document.body.textContent = 'Lỗi runtime mock: ' + error.message;
      console.error(error);
    });
  });
})();
