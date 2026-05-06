/* The Daily — frontend renderer.
   Pulls /local/the-daily/data.json (composed by scripts/the_daily/compose.py)
   and binds it to DOM via data-* directives. No HA token in browser. */

const DATA_URL = './data.json';
const POLL_MS = 30_000;
const STALE_AFTER_S = 600;

const TEMPLATE_MAP = {
  'wire.headlines': 'tpl-headline',
  'wire.social':    'tpl-pulse',
  'wire.bulletin':  'tpl-bulletin',
  'calendar.events':'tpl-event',
  'tasks.items':    'tpl-task',
};
const STAT_ROW_TPL = 'tpl-stat-row';

let lastData = null;
let pollTimer = null;

/* ---------- helpers ---------- */
function getPath(obj, path) {
  if (obj == null || !path) return undefined;
  return path.split('.').reduce((o, k) => (o == null ? o : o[k]), obj);
}

function setText(el, value) {
  if (value === null || value === undefined || value === '') {
    el.textContent = '—';
    el.dataset.missing = 'true';
  } else {
    el.textContent = String(value);
    delete el.dataset.missing;
  }
}

function humanAge(generatedAtIso) {
  if (!generatedAtIso) return 'refreshed —';
  const ts = Date.parse(generatedAtIso);
  if (isNaN(ts)) return 'refreshed —';
  const sec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  let text;
  if (sec < 60) text = `${sec}s`;
  else if (sec < 3600) text = `${Math.floor(sec / 60)}m`;
  else text = `${Math.floor(sec / 3600)}h`;
  return `refreshed ${text} ago`;
}

/* ---------- bindings on a single element ---------- */
function applyBindOn(el, ctx) {
  // data-bind: textContent or special $age
  if (el.hasAttribute('data-bind')) {
    const path = el.getAttribute('data-bind');
    if (path === '$age') {
      el.textContent = humanAge(lastData?.generated_at);
    } else {
      setText(el, getPath(ctx, path));
    }
  }
  // data-bind-html: raw HTML injection
  if (el.hasAttribute('data-bind-html')) {
    const v = getPath(ctx, el.getAttribute('data-bind-html'));
    if (v == null || v === '') {
      el.innerHTML = '—';
      el.dataset.missing = 'true';
    } else {
      el.innerHTML = String(v);
      delete el.dataset.missing;
    }
  }
  // data-bind-hidden: hide element if value falsy/zero
  if (el.hasAttribute('data-bind-hidden')) {
    const v = getPath(ctx, el.getAttribute('data-bind-hidden'));
    el.hidden = !v;
  }
  // data-attr-href: set href attribute
  if (el.hasAttribute('data-attr-href')) {
    const v = getPath(ctx, el.getAttribute('data-attr-href'));
    if (v) el.setAttribute('href', v);
    else el.removeAttribute('href');
  }
  // data-class-XXX (except data-class-kind-from)
  for (const attr of Array.from(el.attributes)) {
    if (!attr.name.startsWith('data-class-')) continue;
    if (attr.name === 'data-class-kind-from') continue;
    const cls = attr.name.slice('data-class-'.length);
    const v = getPath(ctx, attr.value);
    el.classList.toggle(cls, !!v);
  }
  // data-class-kind-from: add class equal to the resolved string value
  if (el.hasAttribute('data-class-kind-from')) {
    // first remove any prior such class we set (track via dataset)
    const prior = el.dataset.kindClass;
    if (prior) el.classList.remove(prior);
    const v = getPath(ctx, el.getAttribute('data-class-kind-from'));
    if (typeof v === 'string' && v) {
      el.classList.add(v);
      el.dataset.kindClass = v;
    } else {
      delete el.dataset.kindClass;
    }
  }
  // data-meter-on / data-meter-total (rebuild children)
  if (el.hasAttribute('data-meter-on') || el.hasAttribute('data-meter-total')) {
    const on = Number(getPath(ctx, el.getAttribute('data-meter-on'))) || 0;
    const total = Number(getPath(ctx, el.getAttribute('data-meter-total'))) || 20;
    el.innerHTML = '';
    const cap = Math.max(total, on, 8);
    for (let i = 0; i < cap; i++) {
      const span = document.createElement('span');
      if (i < on) span.classList.add('on');
      el.appendChild(span);
    }
  }
  // data-bars: render bar chart
  if (el.hasAttribute('data-bars')) {
    const arr = getPath(ctx, el.getAttribute('data-bars')) || [];
    el.innerHTML = '';
    for (const bar of arr) {
      const span = document.createElement('span');
      const h = Math.max(2, Math.min(100, Number(bar.h) || 0));
      span.style.height = `${h}%`;
      if (bar.kind === 'hi') span.classList.add('hi');
      else if (bar.kind === 'mid') span.classList.add('mid');
      el.appendChild(span);
    }
    if (arr.length === 0) {
      // placeholder bars when no data
      for (let i = 0; i < 12; i++) {
        const span = document.createElement('span');
        span.style.height = `${10 + Math.sin(i) * 5 + 10}%`;
        el.appendChild(span);
      }
    }
  }
}

/* ---------- list templates ---------- */
function renderTemplate(host, path, data) {
  const items = getPath(data, path);
  const tplId = TEMPLATE_MAP[path] || (path.endsWith('.rows') ? STAT_ROW_TPL : null);
  if (!tplId) {
    console.warn('No template for', path);
    return;
  }
  const tpl = document.getElementById(tplId);
  if (!tpl) {
    console.warn('Template not found:', tplId);
    return;
  }
  host.innerHTML = '';
  if (!items || items.length === 0) {
    const empty = document.createElement('div');
    empty.className = host.classList.contains('feed') || host.classList.contains('pulse') || host.classList.contains('bulletin') ? 'empty-feed' : 'empty';
    empty.textContent = host.getAttribute('data-empty') || '—';
    host.appendChild(empty);
    return;
  }
  for (const item of items) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    walkAndApply(node, item);
    host.appendChild(node);
  }
}

/* ---------- walk and apply to a subtree ---------- */
function walkAndApply(root, ctx) {
  applyBindOn(root, ctx);
  for (const el of root.querySelectorAll('*')) {
    applyBindOn(el, ctx);
  }
}

/* ---------- main render ---------- */
function render(data) {
  lastData = data;

  // Top-level scalar bindings (page-wide ctx = data)
  document.querySelectorAll('[data-bind],[data-bind-html],[data-bind-hidden],[data-meter-on],[data-bars]').forEach(el => {
    if (el.closest('[data-template]') && !el.matches('[data-template]')) return; // skip nodes inside list hosts (they re-render via template)
    applyBindOn(el, data);
  });

  // Templates
  document.querySelectorAll('[data-template]').forEach(host => {
    renderTemplate(host, host.getAttribute('data-template'), data);
  });

  // Stale check
  const ts = Date.parse(data.generated_at || '');
  const ageS = isNaN(ts) ? Infinity : (Date.now() - ts) / 1000;
  let state = 'ok';
  if (data?.masthead?.status_dot === 'error') state = 'error';
  else if (ageS > STALE_AFTER_S) state = 'stale';
  document.body.dataset.state = state;
}

/* ---------- fetch & poll ---------- */
async function refresh() {
  try {
    const resp = await fetch(`${DATA_URL}?_=${Date.now()}`, { cache: 'no-cache' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    render(data);
  } catch (err) {
    console.error('Failed to load data.json:', err);
    if (lastData) {
      // re-render with last known data, but mark stale
      document.body.dataset.state = 'error';
    } else {
      document.body.dataset.state = 'error';
      // show inline error in masthead
      const left = document.querySelector('.masthead .left span:not(.dot)');
      if (left) left.textContent = `data.json unreachable — ${String(err).slice(0, 60)}`;
    }
  }
}

function startPolling() {
  refresh();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => {
    if (document.hidden) return;
    refresh();
  }, POLL_MS);
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refresh();
});

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startPolling);
} else {
  startPolling();
}
