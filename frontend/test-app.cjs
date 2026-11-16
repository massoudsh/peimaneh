const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(__dirname + '/app.js', 'utf8');

class FakeFormData extends Map {}

const submitTarget = pairs => ({
  preventDefault() {},
  querySelector: () => ({disabled: false}),
  *[Symbol.iterator]() { yield* pairs; },
});

function element(id) {
  return {
    id, innerHTML: '', textContent: '', hidden: false, disabled: false, dataset: {},
    listeners: {},
    addEventListener(event, handler) { this.listeners[event] = handler; },
    querySelector() { return {disabled: false}; },
  };
}

async function flush() {
  for (let index = 0; index < 30; index += 1) await new Promise(resolve => setImmediate(resolve));
}

async function run(hash, handler, {token = 'test-token'} = {}) {
  const elements = new Map();
  const get = selector => {
    if (!elements.has(selector)) elements.set(selector, element(selector));
    return elements.get(selector);
  };
  const storage = new Map(token ? [['peimaneh_token', token]] : []);
  const requests = [];
  const location = {
    _hash: hash,
    get hash() { return this._hash; },
    set hash(value) {
      if (this._hash === value) return;
      this._hash = value;
      context.window.listeners?.hashchange?.();
    },
  };
  const context = vm.createContext({
    document: {
      querySelector: get,
      querySelectorAll: selector => selector === '[data-role]' ? [] : [],
      getElementById: get,
    },
    location,
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    window: {addEventListener(event, handler) { (this.listeners ||= {})[event] = handler; }},
    URLSearchParams, Intl, Map, FormData: FakeFormData,
    fetch: async (url, options = {}) => {
      requests.push({url, options});
      const result = await handler(url, options);
      if (result === undefined) throw new Error(`Unexpected URL: ${url}`);
      const envelope = result !== null && typeof result === 'object'
        && (Object.prototype.hasOwnProperty.call(result, 'body') || Object.prototype.hasOwnProperty.call(result, 'status'));
      const status = envelope ? (result.status ?? 200) : 200;
      const payload = envelope ? result.body : result;
      return {
        status, ok: status < 400,
        text: async () => payload === undefined ? '' : JSON.stringify(payload),
      };
    },
  });
  vm.runInContext(source, context);
  await flush();
  return {elements, requests, context, storage, get};
}

const user = role => ({id: 'u1', email: `${role}@example.com`, role, is_active: true});
const summary = {contacts: 1, open_threads: 1, due_follow_ups: 0, stages: {inquiry: 1, quote: 0, sample: 0, payment_terms: 0, shipping: 0, proforma: 0, confirmation: 0}};
const thread = (stage = 'inquiry') => ({id: 't1', contact_id: 'c1', stage, next_follow_up_at: null, summary: null});

function threadHandler({role = 'manager', stage = 'inquiry', allowed = ['quote'], requiresManager = false, messages = [], audit = [], threadOverride = {}} = {}) {
  return (url, options) => {
    const table = {
      '/api/auth/me': user(role),
      '/api/threads/t1': {...thread(stage), ...threadOverride},
      '/api/threads/t1/messages?limit=200': messages,
      '/api/threads/t1/audit?limit=50&offset=0': audit,
      '/api/contacts/c1': {id: 'c1', name: 'Buyer', company: 'ACME', country: 'UAE', channel: 'email', is_sensitive: false},
      '/api/threads/t1/transitions': {current_stage: stage, allowed_stages: allowed, requires_manager: requiresManager},
    };
    return table[url];
  };
}

test('logged-out users are sent to the login page', async () => {
  const result = await run('', () => ({status: 401, body: {detail: 'authentication required'}}), {token: null});
  assert.equal(result.context.location.hash, '#/login');
  assert.match(result.get('#view').innerHTML, /ورود به پیمانه/);
});

test('manager sees policy and team navigation; sales does not', async () => {
  const manager = await run('#/dashboard', url => url === '/api/auth/me' ? user('manager') : summary);
  assert.equal(manager.get('[data-role]').hidden, false);

  const roleElements = [{dataset: {role: 'manager'}, hidden: false}, {dataset: {role: 'manager'}, hidden: false}];
  const sales = await run('#/dashboard', url => url === '/api/auth/me' ? user('sales') : summary);
  const inspect = vm.runInContext('nav', sales.context);
  const contextDocument = sales.context.document;
  contextDocument.querySelectorAll = () => roleElements;
  inspect();
  assert.deepEqual(roleElements.map(el => el.hidden), [true, true]);
});

test('dashboard renders pipeline labels in Persian', async () => {
  const result = await run('#/dashboard', url => url === '/api/auth/me' ? user('manager') : summary);
  const html = result.get('#view').innerHTML;
  assert.match(html, /نمای کلی تجارت/);
  assert.match(html, /استعلام/);
  assert.match(html, /فرصت‌های باز/);
});

test('list pagination uses route-local offsets', async () => {
  for (const [hash, offset] of [['#/threads?offset=50', 50], ['#/threads', 0], ['#/threads?offset=Infinity', 0], ['#/threads?offset=-1', 0], ['#/threads?offset=1.5', 0]]) {
    const result = await run(hash, url => {
      if (url === '/api/auth/me') return user('manager');
      if (url === '/api/contacts?limit=200') return [];
      if (url.startsWith('/api/threads?limit=50')) return [];
      return undefined;
    }, {token: null});
    const listCall = result.requests.find(request => request.url.startsWith('/api/threads?limit=50'));
    assert.equal(listCall.url, `/api/threads?limit=50&offset=${offset}&q=`);
  }
});

test('search term is forwarded and escaped in the input', async () => {
  const result = await run('#/threads?q=%3Cscript%3E', url => {
    if (url === '/api/auth/me') return user('sales');
    if (url === '/api/contacts?limit=200') return [];
    if (url.startsWith('/api/threads?limit=50')) return [];
    return undefined;
  });
  const html = result.get('#view').innerHTML;
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  const listCall = result.requests.find(request => request.url.startsWith('/api/threads?limit=50'));
  assert.match(listCall.url, /q=%3Cscript%3E/);
});

test('optional contact fields do not block submission', async () => {
  const result = await run('#/contacts', url => {
    if (url === '/api/auth/me') return user('sales');
    if (url.startsWith('/api/contacts?limit=100')) return [];
    return undefined;
  });
  const html = result.get('#view').innerHTML;
  assert.doesNotMatch(html, /name="company"[^>]*required/);
  assert.doesNotMatch(html, /name="country"[^>]*required/);
});

test('confirmed thread hides scheduling and offers no transitions', async () => {
  const result = await run('#/threads/t1', threadHandler({stage: 'confirmation', allowed: []}));
  const html = result.get('#view').innerHTML;
  assert.doesNotMatch(html, /id="schedule"/);
  assert.match(html, /مرحله نهایی/);
});

test('sales user cannot select final confirmation', async () => {
  const result = await run('#/threads/t1', threadHandler({role: 'sales', stage: 'proforma', allowed: ['shipping', 'confirmation'], requiresManager: true}));
  const html = result.get('#view').innerHTML;
  assert.doesNotMatch(html, /value="confirmation"/);
  assert.match(html, /تأیید نهایی فقط توسط مدیر/);
});

test('manager can select final confirmation', async () => {
  const result = await run('#/threads/t1', threadHandler({role: 'manager', stage: 'proforma', allowed: ['shipping', 'confirmation'], requiresManager: true}));
  const html = result.get('#view').innerHTML;
  assert.match(html, /value="confirmation"/);
});

test('stage submission posts the selected stage', async () => {
  const handler = threadHandler();
  const result = await run('#/threads/t1', (url, options) => {
    if (url === '/api/threads/t1/transition') return {body: thread('quote')};
    return handler(url, options);
  });
  const form = result.get('stage');
  await form.listeners.submit({preventDefault() {}, target: submitTarget([['target_stage', 'quote']])});
  const request = result.requests.find(item => item.url === '/api/threads/t1/transition');
  assert.equal(request.options.method, 'POST');
  assert.deepEqual(JSON.parse(request.options.body), {target_stage: 'quote'});
});

test('policy save preserves hidden fields and normalizes lists', async () => {
  const policy = {version: 1, product_category: 'tea', price_floor: 10, max_discount_pct: 5, capacity_notes: 'Limited stock', sensitive_customers: ['Sensitive buyer'], sensitive_countries: ['Iran'], allowed_payment_terms: ['TT']};
  const result = await run('#/policy', (url, options) => {
    if (url === '/api/auth/me') return user('manager');
    if (url === '/api/policy/active') return policy;
    if (url === '/api/policy' && options.method === 'POST') return policy;
    return undefined;
  });
  const form = result.get('policy');
  await form.listeners.submit({
    preventDefault() {},
    target: submitTarget([['product_category', 'tea'], ['price_floor', '12'], ['max_discount_pct', '0'],
      ['allowed_payment_terms', 'TT, LC'], ['sensitive_countries', ''], ['sensitive_customers', 'Risky Buyer']]),
  });
  const request = result.requests.find(item => item.url === '/api/policy' && item.options.method === 'POST');
  const payload = JSON.parse(request.options.body);
  assert.equal(payload.capacity_notes, 'Limited stock');
  assert.deepEqual(payload.sensitive_customers, ['Risky Buyer']);
  assert.deepEqual(payload.sensitive_countries, []);
  assert.deepEqual(payload.allowed_payment_terms, ['TT', 'LC']);
  assert.equal(payload.price_floor, 12);
});

test('audit pagination exposes older events link', async () => {
  const audit = Array.from({length: 50}, (_, index) => ({id: String(index), action: 'stage_transition', actor: 'a@b.co', detail: {}, created_at: '2026-01-01T00:00:00Z'}));
  const result = await run('#/threads/t1', threadHandler({audit}));
  assert.match(result.get('#view').innerHTML, /audit=50/);
});

test('message content is escaped', async () => {
  const result = await run('#/threads/t1', threadHandler({messages: [{id: 'm1', sender: 'contact', status: 'received', text: '<img src=x onerror=alert(1)>', created_at: '2026-01-01T00:00:00Z'}]}));
  const html = result.get('#view').innerHTML;
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img src=x/);
});

test('logout clears the stored token', async () => {
  const result = await run('#/dashboard', (url, options) => {
    if (url === '/api/auth/me') return user('sales');
    if (url === '/api/dashboard/summary') return summary;
    if (url === '/api/auth/logout' && options.method === 'POST') return {status: 204};
    return undefined;
  });
  await result.get('#logout').listeners.click();
  assert.equal(result.storage.has('peimaneh_token'), false);
  assert.equal(result.context.location.hash, '#/login');
});
