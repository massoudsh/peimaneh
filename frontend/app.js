const view = document.querySelector('#view');
const feedback = document.querySelector('#feedback');
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date = value => value ? new Date(value).toLocaleString() : '—';
const field = (name, label, type = 'text', value = '') => `<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}" required></label>`;
const select = (name, label, options) => `<label>${label}<select name="${name}">${options.map(([value,text]) => `<option value="${esc(value)}">${esc(text)}</option>`).join('')}</select></label>`;
async function api(path, method = 'GET', body) {
  const token = localStorage.getItem('peimaneh_token');
  const headers = body ? {'Content-Type':'application/json'} : {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api${path}`, {method, headers, body: body ? JSON.stringify(body) : undefined});
  const data = await response.json();
  if (response.status === 401 && !path.startsWith('/auth/')) { location.hash = '#/login'; throw new Error('authentication required'); }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
  return data;
}
function table(headers, rows) {
  return rows.length ? `<div class="panel table-wrap"><table><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : '<div class="panel">No records yet.</div>';
}
function form(id, content, button) { return `<form id="${id}">${content}<button>${button}</button></form>`; }
function bind(id, action) {
  document.getElementById(id)?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.target.querySelector('button');
    button.disabled = true;
    try { await action(Object.fromEntries(new FormData(event.target))); await render(); feedback.innerHTML = '<p class="success">Saved successfully.</p>'; }
    catch (error) { feedback.innerHTML = `<p class="error">${esc(error.message)}</p>`; }
    finally { button.disabled = false; }
  });
}
const stages = ['inquiry','quote','sample','payment_terms','shipping','proforma','confirmation'];
let revision = 0;
async function render() {
  const current = ++revision;
  const [page = 'dashboard', id] = location.hash.slice(2).split('/');
  feedback.innerHTML = '';
  view.innerHTML = '<p>Loading workspace…</p>';
  document.querySelectorAll('nav a').forEach(a => a.classList.toggle('active', a.hash === `#/${page}`));
  try {
    let html = '';
    let setup = () => {};
    if (page === 'login') {
      html = '<h1>Sign in to Peimaneh</h1><p>Access is private and every commercial action remains human-reviewed.</p>' + form('login',field('email','Email','email')+field('password','Password','password'),'Sign in') + '<h2>First-time setup</h2><p>The first account becomes the manager. Later registrations create sales users.</p>' + form('register',field('email','Email','email')+field('password','Password','password'),'Create first account');
      setup = () => {
        bind('login', async data => { const result = await api('/auth/login','POST',data); localStorage.setItem('peimaneh_token',result.access_token); location.hash = '#/dashboard'; });
        bind('register', async data => { const result = await api('/auth/register','POST',{...data,role:'manager'}); localStorage.setItem('peimaneh_token',result.access_token); location.hash = '#/dashboard'; });
      };
    } else if (page === 'dashboard') {
      const data = await api('/dashboard/summary');
      html = '<h1>Your trade overview</h1><p>Real opportunities, clear next steps. Every commercial decision stays with your team.</p>';
      html += `<div class="grid">${[['Contacts',data.contacts],['Open opportunities',data.open_threads],['Due follow-ups',data.due_follow_ups],['Confirmed',data.stages.confirmation]].map(([label,value]) => `<div class="card">${label}<strong>${value}</strong></div>`).join('')}</div>`;
      html += '<h2>Negotiation pipeline</h2>' + table(['Stage','Opportunities'],Object.entries(data.stages).map(([stage,count]) => [esc(stage),count]));
    } else if (page === 'contacts') {
      const contacts = await api('/contacts');
      html = '<h1>Contacts</h1><p>Your international buyers and suppliers.</p>' + table(['Name','Company','Country','Channel'],contacts.map(c => [esc(c.name),esc(c.company),esc(c.country),esc(c.channel)]));
      html += '<h2>Add a contact</h2>' + form('contact',field('name','Name')+field('company','Company')+field('country','Country')+select('channel','Channel',['email','whatsapp','linkedin','other'].map(c => [c,c])), 'Create contact');
      setup = () => bind('contact', data => api('/contacts','POST',data));
    } else if (page === 'threads' && id) {
      const path = `/threads/${encodeURIComponent(id)}`;
      const [thread,messages,audit,contact] = await (async () => { const thread = await api(path); return [thread,await api(path+'/messages'),await api(path+'/audit'),await api('/contacts/'+encodeURIComponent(thread.contact_id))]; })();
      html = `<a href="#/threads">← All opportunities</a><h1>${esc(contact.name)}</h1><p>Stage: ${esc(thread.stage)} · Follow-up: ${esc(date(thread.next_follow_up_at))}</p>`;
      html += '<h2>Conversation</h2><div class="panel">' + (messages.map(m => `<div class="message" dir="auto"><span class="muted">${esc(m.sender)} · ${esc(m.status)} · ${esc(date(m.created_at))}</span><p>${esc(m.text)}</p></div>`).join('') || 'No messages yet.') + '</div>';
      html += form('message',select('sender','Record type',[['contact','Received from contact'],['human','Already sent manually'],['agent_draft','Unapproved draft']])+'<label>Message<textarea name="text" required maxlength="50000" dir="auto"></textarea></label>','Save message (does not send)');
      html += '<h2>Next action</h2>' + form('schedule',field('due_at','Follow-up time','datetime-local'),'Schedule follow-up');
      if (thread.next_follow_up_at) html += form('complete','','Mark follow-up complete')+form('cancel','','Cancel follow-up');
      html += '<h2>Negotiation stage</h2><p>This private pilot records your manual decision; it does not establish a binding order or send a message.</p>' + form('stage',select('stage','Next stage',stages.map(s => [s,s])),'Record stage');
      html += '<h2>Audit trail</h2>' + table(['Action','Actor','Details'],audit.map(a => [esc(a.action),esc(a.actor),esc(JSON.stringify(a.detail))]));
      setup = () => {
        bind('message',data => api(path+'/messages','POST',data));
        bind('schedule',data => api(path+'/follow-up','PUT',{due_at:new Date(data.due_at).toISOString()}));
        bind('complete',() => api(path+'/follow-up/complete','POST'));
        bind('cancel',() => api(path+'/follow-up','DELETE'));
        bind('stage',data => api(path+'/transition?target_stage='+encodeURIComponent(data.stage),'POST'));
      };
    } else if (page === 'threads' || page === 'follow-ups') {
      const offset = Math.max(0, Number(new URLSearchParams(location.search).get('offset')) || 0);
      const [threads,contacts] = await Promise.all([api(`/threads?limit=50&offset=${offset}${page === 'follow-ups' ? '&due_only=true' : ''}`),api('/contacts')]);
      const names = Object.fromEntries(contacts.map(c => [c.id,c.name]));
      html = `<h1>${page === 'follow-ups' ? 'Due follow-ups' : 'Opportunities'}</h1><p>${page === 'follow-ups' ? 'Overdue reminders for open conversations.' : 'Move conversations forward, one reviewed step at a time.'}</p>`;
      html += table(['Contact','Stage','Next follow-up',''],threads.map(t => [esc(names[t.contact_id] || t.contact_id),esc(t.stage),esc(date(t.next_follow_up_at)),`<a href="#/threads/${encodeURIComponent(t.id)}">Open conversation</a>`]));
      html += `<div class="actions">${offset ? `<a href="?offset=${Math.max(0,offset-50)}#/${page}">Previous</a>` : ''}${threads.length === 50 ? `<a href="?offset=${offset+50}#/${page}">Next</a>` : ''}</div>`;
      if (page === 'threads') html += contacts.length ? '<h2>Start an opportunity</h2>'+form('thread',select('contact_id','Contact',contacts.map(c => [c.id,c.name])),'Create opportunity') : '<p>Add a contact first.</p>';
      setup = () => bind('thread',data => api('/threads','POST',data));
    } else if (page === 'policy') {
      let policy = null;
      try { policy = await api('/policy/active'); } catch(error) { if (error.message !== 'no active policy configured') throw error; }
      html = '<h1>Company policy</h1><p>Define commercial boundaries. Each save creates a new version; an evaluation is not an approval.</p>';
      if (policy) html += `<div class="panel">Active version ${policy.version} · ${esc(policy.product_category)} · Price floor ${esc(policy.price_floor)}</div>`;
      html += form('policy',field('product_category','Product category','text',policy?.product_category)+field('price_floor','Price floor','number',policy?.price_floor ?? 0)+field('max_discount_pct','Maximum discount %','number',policy?.max_discount_pct ?? 0)+field('allowed_payment_terms','Allowed payment terms (comma separated)','text',policy?.allowed_payment_terms?.join(', '))+ '<label>Sensitive countries (comma separated)<input name="sensitive_countries" value="'+esc(policy?.sensitive_countries?.join(', '))+'"></label>','Save new policy version');
      html += '<h2>Evaluate an offer</h2>' + form('evaluate',field('price','Price','number')+field('payment_term','Payment term')+field('discount_pct','Discount %','number',0)+'<label>Country<input name="country"></label><label>Customer name<input name="customer_name"></label>','Evaluate offer') + '<div id="decision" role="status"></div>';
      setup = () => {
        document.querySelectorAll('input[type=number]').forEach(input => { input.min = '0'; input.step = 'any'; if(input.name.includes('discount')) input.max = '100'; });
        bind('policy',data => api('/policy','POST',{...data,price_floor:Number(data.price_floor),max_discount_pct:Number(data.max_discount_pct),allowed_payment_terms:data.allowed_payment_terms.split(',').map(s => s.trim()).filter(Boolean),sensitive_countries:data.sensitive_countries.split(',').map(s => s.trim()).filter(Boolean)}));
        document.getElementById('evaluate').onsubmit = async event => {
          event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true;
          try { const data = Object.fromEntries(new FormData(event.target)); const result = await api('/policy/evaluate-offer','POST',{...data,price:Number(data.price),discount_pct:Number(data.discount_pct)}); document.getElementById('decision').innerHTML = `<div class="panel"><h2>${esc(result.status)}</h2>${result.reasons.map(r => `<p>${esc(r)}</p>`).join('')}</div>`; }
          catch(error) { feedback.innerHTML = `<p class="error">${esc(error.message)}</p>`; } finally { button.disabled = false; }
        };
      };
    } else { html = '<h1>Page not found</h1><a href="#/dashboard">Return to overview</a>'; }
    if (current !== revision) return;
    view.innerHTML = html; setup();
  } catch(error) { if(current === revision) view.innerHTML = `<h1>Unable to load this page</h1><p class="error">${esc(error.message)}</p><button id="retry">Retry</button>`; document.getElementById('retry')?.addEventListener('click',render); }
}
window.addEventListener('hashchange',render);
render();
