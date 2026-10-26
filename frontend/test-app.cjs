const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(__dirname + '/app.js', 'utf8');

async function run(hash, responses) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {innerHTML: '', addEventListener(event, handler) { this[event] = handler; }});
    return elements.get(id);
  };
  const requests = [];
  const context = vm.createContext({
    document: {querySelector: element, querySelectorAll: () => [], getElementById: element},
    location: {hash, search: '?offset=999'},
    localStorage: {getItem: () => null},
    window: {addEventListener() {}},
    URLSearchParams, FormData: class { constructor(data) { return Object.entries(data); } },
    fetch: async (url, options) => {
      requests.push({url, options});
      const data = responses[url];
      if (data === undefined) throw new Error('Unexpected URL: ' + url);
      return {ok: true, status: 200, json: async () => data};
    },
  });
  vm.runInContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  return {elements, requests, context};
}

test('empty route loads dashboard', async () => {
  const result = await run('', {'/api/dashboard/summary': {contacts:0,open_threads:0,due_follow_ups:0,stages:{confirmation:0}}});
  assert.match(result.elements.get('#view').innerHTML, /Your trade overview/);
});

test('pagination uses route-local safe offsets, never global query', async () => {
  for (const [hash, offset] of [['#/threads?offset=50',50],['#/threads',0],['#/threads?offset=Infinity',0],['#/threads?offset=-1',0],['#/threads?offset=1.5',0]]) {
    const result = await run(hash, {[`/api/threads?limit=50&offset=${offset}`]:[], '/api/contacts':[]});
    assert.equal(result.requests[0].url, `/api/threads?limit=50&offset=${offset}`);
  }
});

test('optional contact inputs do not block submission and names are escaped', async () => {
  const result = await run('#/contacts', {'/api/contacts':[{name:'<script>x</script>'}]});
  const html = result.elements.get('#view').innerHTML;
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /name="company"[^>]*required/);
  assert.doesNotMatch(html, /name="country"[^>]*required/);
});

test('confirmed opportunity does not display impossible scheduling', async () => {
  const result = await run('#/threads/t1', {
    '/api/threads/t1':{contact_id:'c1',stage:'confirmation'},
    '/api/threads/t1/messages':[], '/api/threads/t1/audit':[], '/api/contacts/c1':{name:'Buyer'},
  });
  assert.doesNotMatch(result.elements.get('#view').innerHTML, /id="schedule"/);
});

test('policy save preserves fields absent from the form', async () => {
  const policy = {version:1,product_category:'tea',price_floor:10,capacity_notes:'Limited stock',sensitive_customers:['Sensitive buyer'],allowed_payment_terms:['TT']};
  const result = await run('#/policy', {'/api/policy/active':policy, '/api/policy':policy});
  const button = {disabled:false};
  const form = {price_floor:'12',max_discount_pct:'0',allowed_payment_terms:'TT',sensitive_countries:'',querySelector:()=>button};
  await result.elements.get('policy').submit({preventDefault(){}, target:form});
  const request = result.requests.find(r => r.url === '/api/policy' && r.options.method === 'POST');
  assert.ok(request);
  const payload = JSON.parse(request.options.body);
  assert.equal(payload.capacity_notes,'Limited stock');
  assert.deepEqual(payload.sensitive_customers,['Sensitive buyer']);
});
