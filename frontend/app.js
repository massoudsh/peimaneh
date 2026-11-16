const view = document.querySelector('#view');
const feedback = document.querySelector('#feedback');
const sessionUser = document.querySelector('#session-user');

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const faDate = value => value ? new Intl.DateTimeFormat('fa-IR', {dateStyle: 'medium', timeStyle: 'short'}).format(new Date(value)) : '—';
const labels = {
  inquiry: 'استعلام', quote: 'پیشنهاد قیمت', sample: 'نمونه', payment_terms: 'شرایط پرداخت',
  shipping: 'حمل', proforma: 'پیش‌فاکتور', confirmation: 'تأیید نهایی',
  manager: 'مدیر', sales: 'کارشناس فروش',
  contact: 'دریافتی از مخاطب', human: 'ارسال‌شده به‌صورت دستی', agent_draft: 'پیش‌نویس تأییدنشده',
  received: 'دریافت شد', needs_approval: 'نیازمند تأیید', sent: 'ارسال شد', draft_ready: 'آماده ارسال',
  follow_up_scheduled: 'پیگیری زمان‌بندی شد', follow_up_completed: 'پیگیری انجام شد',
  follow_up_cancelled: 'پیگیری لغو شد', stage_transition: 'تغییر مرحله', thread_created: 'فرصت ایجاد شد',
  policy_version_created: 'نسخه سیاست ثبت شد',
  ready_to_send: 'آماده ارسال', needs_human_approval: 'نیازمند تأیید انسان',
};
const label = value => labels[value] || value;

const field = (name, text, type = 'text', value = '', required = true) =>
  `<label>${esc(text)}<input name="${name}" type="${type}" value="${esc(value)}" ${required ? 'required' : ''}></label>`;
const area = (name, text) => `<label>${esc(text)}<textarea name="${name}" required maxlength="50000" dir="auto"></textarea></label>`;
const choice = (name, text, options, selected) => `<label>${esc(text)}<select name="${name}">${
  options.map(([value, caption]) => `<option value="${esc(value)}" ${value === selected ? 'selected' : ''}>${esc(caption)}</option>`).join('')
}</select></label>`;
const form = (id, content, button) => `<form id="${id}">${content}<button type="submit">${esc(button)}</button></form>`;

function clearToken() {
  localStorage.removeItem('peimaneh_token');
}

async function api(path, method = 'GET', body) {
  const token = localStorage.getItem('peimaneh_token');
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api${path}`, {method, headers, body: body === undefined ? undefined : JSON.stringify(body)});
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (response.status === 401 && !path.startsWith('/auth/')) {
    clearToken();
    if (location.hash !== '#/login') location.hash = '#/login';
    throw new Error('نشست شما منقضی شده است؛ دوباره وارد شوید.');
  }
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : 'درخواست انجام نشد.');
  }
  return data;
}

function table(headers, rows, empty = 'هنوز رکوردی ثبت نشده است.') {
  if (!rows.length) return `<div class="panel">${esc(empty)}</div>`;
  return `<div class="panel table-wrap"><table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${
    rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')
  }</tbody></table></div>`;
}

let user = null;
let revision = 0;

function bind(id, action) {
  document.getElementById(id)?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.target.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      await action(Object.fromEntries(new FormData(event.target)));
      await render();
      feedback.innerHTML = '<p class="success">با موفقیت ذخیره شد.</p>';
    } catch (error) {
      feedback.innerHTML = `<p class="error">${esc(error.message)}</p>`;
    } finally {
      if (button) button.disabled = false;
    }
  });
}

function nav() {
  document.querySelectorAll('[data-role]').forEach(el => {
    el.hidden = !(user && user.role === el.dataset.role);
  });
  if (user) sessionUser.textContent = `${user.email} · ${label(user.role)}`;
  document.querySelector('#logout').hidden = !user;
}

function offsetFrom(query) {
  const requested = Number(new URLSearchParams(query).get('offset'));
  return Number.isSafeInteger(requested) && requested >= 0 ? requested : 0;
}

function searchFrom(query) {
  return (new URLSearchParams(query).get('q') || '').trim();
}

function pagination(page, offset, count, query) {
  const term = searchFrom(query);
  const suffix = term ? `&q=${encodeURIComponent(term)}` : '';
  return `<div class="actions">
    ${offset ? `<a href="#/${page}?offset=${Math.max(0, offset - 50)}${suffix}">قبلی</a>` : ''}
    ${count === 50 ? `<a href="#/${page}?offset=${offset + 50}${suffix}">بعدی</a>` : ''}
  </div>`;
}

const publicPages = new Set(['login']);

async function render() {
  const current = ++revision;
  const [route, query = ''] = location.hash.slice(2).split('?');
  const [page = 'dashboard', id] = (route || 'dashboard').split('/');
  feedback.innerHTML = '';

  if (!user && !publicPages.has(page)) {
    try {
      user = await api('/auth/me');
    } catch {
      if (current === revision && location.hash !== '#/login') location.hash = '#/login';
      return;
    }
  }
  if (user && page === 'login') {
    location.hash = '#/dashboard';
    return;
  }
  nav();
  view.innerHTML = '<p>در حال بارگذاری…</p>';

  try {
    let html = '';
    let setup = () => {};

    if (page === 'login') {
      html = '<h1>ورود به پیمانه</h1><p>دسترسی خصوصی است و هر اقدام تجاری با تأیید انسان ثبت می‌شود.</p>'
        + form('login', field('email', 'ایمیل', 'email') + field('password', 'گذرواژه', 'password'), 'ورود')
        + '<h2>راه‌اندازی اولیه</h2><p>ساخت نخستین حساب مدیر فقط وقتی فعال است که <code>ALLOW_BOOTSTRAP_REGISTRATION=true</code> باشد.</p>'
        + form('bootstrap', field('email', 'ایمیل', 'email') + field('password', 'گذرواژه', 'password'), 'ساخت حساب مدیر');
      setup = () => {
        bind('login', async data => {
          const result = await api('/auth/login', 'POST', data);
          localStorage.setItem('peimaneh_token', result.access_token);
          user = null;
          location.hash = '#/dashboard';
        });
        bind('bootstrap', async data => {
          const result = await api('/auth/bootstrap', 'POST', data);
          localStorage.setItem('peimaneh_token', result.access_token);
          user = null;
          location.hash = '#/dashboard';
        });
      };
    } else if (page === 'dashboard') {
      const data = await api('/dashboard/summary');
      html = '<h1>نمای کلی تجارت</h1><p>فرصت‌های واقعی، قدم بعدی روشن. هر تصمیم تجاری با تیم شما می‌ماند.</p>';
      html += `<div class="grid">${[
        ['مخاطبان', data.contacts], ['فرصت‌های باز', data.open_threads],
        ['پیگیری‌های سررسید', data.due_follow_ups], ['تأییدشده', data.stages.confirmation],
      ].map(([caption, value]) => `<div class="card">${esc(caption)}<strong>${value}</strong></div>`).join('')}</div>`;
      html += '<h2>قیف مذاکره</h2>' + table(
        ['مرحله', 'تعداد'],
        Object.entries(data.stages).map(([stage, count]) => [esc(label(stage)), count]),
      );
    } else if (page === 'contacts') {
      const term = searchFrom(query);
      const contacts = await api(`/contacts?limit=100&q=${encodeURIComponent(term)}`);
      html = '<h1>مخاطبان</h1><p>خریداران و تأمین‌کنندگان خارجی شما.</p>'
        + `<form id="search-contacts" class="search"><label>جست‌وجو<input name="q" value="${esc(term)}" placeholder="نام، شرکت یا کشور"></label><button type="submit">جست‌وجو</button></form>`
        + table(['نام', 'شرکت', 'کشور', 'کانال', 'حساس'], contacts.map(contact => [
          esc(contact.name), esc(contact.company), esc(contact.country), esc(contact.channel),
          contact.is_sensitive ? 'بله' : 'خیر',
        ]))
        + '<h2>افزودن مخاطب</h2>' + form('contact',
          field('name', 'نام') + field('company', 'شرکت (اختیاری)', 'text', '', false)
          + field('country', 'کشور (اختیاری)', 'text', '', false)
          + choice('channel', 'کانال', [['email', 'ایمیل'], ['whatsapp', 'واتساپ'], ['linkedin', 'لینکدین'], ['other', 'سایر']]),
          'ثبت مخاطب');
      setup = () => {
        bind('contact', data => api('/contacts', 'POST', data));
        document.getElementById('search-contacts').addEventListener('submit', event => {
          event.preventDefault();
          const value = (new FormData(event.target).get('q') || '').trim();
          location.hash = `#/contacts?offset=0&q=${encodeURIComponent(value)}`;
        });
      };
    } else if (page === 'threads' && id) {
      const path = `/threads/${encodeURIComponent(id)}`;
      const auditOffset = Math.max(0, Number(new URLSearchParams(query).get('audit')) || 0);
      const thread = await api(path);
      const [messages, audit, contact, transitions] = await Promise.all([
        api(`${path}/messages?limit=200`), api(`${path}/audit?limit=50&offset=${auditOffset}`),
        api(`/contacts/${encodeURIComponent(thread.contact_id)}`), api(`${path}/transitions`),
      ]);
      const canConfirm = user?.role === 'manager';
      const allowedStages = transitions.allowed_stages.filter(stage => stage !== 'confirmation' || canConfirm);
      const stageOptions = allowedStages.map(stage => [stage, label(stage)]);
      const blockedConfirmation = transitions.allowed_stages.includes('confirmation') && !canConfirm;
      html = `<a href="#/threads">→ همه فرصت‌ها</a><h1>${esc(contact.name)}</h1>
        <p>مرحله: ${esc(label(thread.stage))} · پیگیری بعدی: ${esc(faDate(thread.next_follow_up_at))}</p>
        <p class="muted">شرکت: ${esc(contact.company || '—')} · کشور: ${esc(contact.country || '—')} · کانال: ${esc(contact.channel)}</p>`;
      html += '<h2>مکالمه</h2><div class="panel">' + (messages.length ? messages.map(message =>
        `<div class="message" dir="auto"><span class="muted">${esc(label(message.sender))} · ${esc(label(message.status))} · ${esc(faDate(message.created_at))}</span><p>${esc(message.text)}</p></div>`
      ).join('') : 'هنوز پیامی ثبت نشده است.') + '</div>';
      html += form('message',
        choice('sender', 'نوع ثبت', [['contact', 'دریافتی از مخاطب'], ['human', 'قبلاً دستی ارسال شده'], ['agent_draft', 'پیش‌نویس تأییدنشده']])
        + area('text', 'متن پیام'), 'ثبت پیام (بدون ارسال)');
      if (thread.stage !== 'confirmation') {
        html += '<h2>اقدام بعدی</h2>' + form('schedule', field('due_at', 'زمان پیگیری', 'datetime-local'), 'زمان‌بندی پیگیری');
      }
      if (thread.next_follow_up_at) {
        html += form('complete', '', 'ثبت انجام پیگیری') + form('cancel', '', 'لغو پیگیری');
      }
      html += '<h2>مرحله مذاکره</h2><p>این نسخه آزمایشی تصمیم دستی شما را ثبت می‌کند؛ سفارش الزام‌آور ایجاد نمی‌کند و پیامی نمی‌فرستد.</p>';
      html += stageOptions.length
        ? form('stage', choice('target_stage', 'مرحله بعد', stageOptions)
          + (blockedConfirmation ? '<p class="muted">تأیید نهایی فقط توسط مدیر امکان‌پذیر است؛ این گزینه برای شما نمایش داده نمی‌شود.</p>' : ''),
          'ثبت تغییر مرحله')
        : `<div class="panel">${blockedConfirmation
          ? 'تأیید نهایی فقط توسط مدیر امکان‌پذیر است؛ انتقال دیگری برای شما مجاز نیست.'
          : 'این فرصت در مرحله نهایی است و انتقال دیگری ندارد.'}</div>`;
      html += '<h2>تاریخچه رویدادها</h2>' + table(
        ['رویداد', 'کاربر', 'جزئیات', 'زمان'],
        audit.map(event => [esc(label(event.action)), esc(event.actor), esc(JSON.stringify(event.detail)), esc(faDate(event.created_at))]),
      );
      const auditLinks = [];
      if (auditOffset) auditLinks.push(`<a href="#/threads/${encodeURIComponent(id)}?audit=${Math.max(0, auditOffset - 50)}">رویدادهای جدیدتر</a>`);
      if (audit.length === 50) auditLinks.push(`<a href="#/threads/${encodeURIComponent(id)}?audit=${auditOffset + 50}">رویدادهای قدیمی‌تر</a>`);
      if (auditLinks.length) html += `<div class="actions">${auditLinks.join('')}</div>`;
      setup = () => {
        bind('message', data => api(`${path}/messages`, 'POST', data));
        bind('schedule', data => api(`${path}/follow-up`, 'PUT', {due_at: new Date(data.due_at).toISOString()}));
        bind('complete', () => api(`${path}/follow-up/complete`, 'POST'));
        bind('cancel', () => api(`${path}/follow-up`, 'DELETE'));
        bind('stage', data => api(`${path}/transition`, 'POST', {target_stage: data.target_stage}));
      };
    } else if (page === 'threads' || page === 'follow-ups') {
      const offset = offsetFrom(query);
      const term = searchFrom(query);
      const [threads, contacts] = await Promise.all([
        api(`/threads?limit=50&offset=${offset}${page === 'follow-ups' ? '&due_only=true' : ''}&q=${encodeURIComponent(term)}`),
        api('/contacts?limit=200'),
      ]);
      const names = Object.fromEntries(contacts.map(contact => [contact.id, contact.name]));
      html = `<h1>${page === 'follow-ups' ? 'پیگیری‌های سررسید' : 'فرصت‌ها'}</h1>
        <p>${page === 'follow-ups' ? 'یادآوری‌های سررسیدشده برای مکالمات باز.' : 'هر مکالمه را یک قدم بررسی‌شده جلو ببرید.'}</p>`;
      html += `<form id="search-threads" class="search"><label>جست‌وجو<input name="q" value="${esc(term)}" placeholder="نام مخاطب یا خلاصه"></label><button type="submit">جست‌وجو</button></form>`;
      html += table(['مخاطب', 'مرحله', 'پیگیری بعدی', ''], threads.map(thread => [
        esc(names[thread.contact_id] || thread.contact_id), esc(label(thread.stage)), esc(faDate(thread.next_follow_up_at)),
        `<a href="#/threads/${encodeURIComponent(thread.id)}">بازکردن مکالمه</a>`,
      ]));
      html += pagination(page, offset, threads.length, query);
      if (page === 'threads') {
        html += contacts.length
          ? '<h2>شروع فرصت جدید</h2>' + form('thread', choice('contact_id', 'مخاطب', contacts.map(contact => [contact.id, contact.name])), 'ایجاد فرصت')
          : '<p>ابتدا یک مخاطب ثبت کنید.</p>';
      }
      setup = () => {
        bind('thread', data => api('/threads', 'POST', data));
        document.getElementById('search-threads').addEventListener('submit', event => {
          event.preventDefault();
          const value = (new FormData(event.target).get('q') || '').trim();
          location.hash = `#/${page}?offset=0&q=${encodeURIComponent(value)}`;
        });
      };
    } else if (page === 'policy') {
      let policy = null;
      try {
        policy = await api('/policy/active');
      } catch (error) {
        if (!error.message.includes('no active policy')) throw error;
      }
      html = '<h1>سیاست شرکت</h1><p>مرزهای تجاری را مشخص کنید. هر ذخیره نسخه تازه می‌سازد؛ ارزیابی به معنی تأیید نیست.</p>';
      if (policy) {
        html += `<div class="panel">نسخه فعال ${policy.version} · ${esc(policy.product_category)} · کف قیمت ${esc(policy.price_floor)}</div>`;
      }
      html += form('policy',
        field('product_category', 'دسته محصول', 'text', policy?.product_category)
        + field('price_floor', 'کف قیمت', 'number', policy?.price_floor ?? 0)
        + field('max_discount_pct', 'حداکثر تخفیف (٪)', 'number', policy?.max_discount_pct ?? 0)
        + field('allowed_payment_terms', 'شرایط پرداخت مجاز (با کاما)', 'text', policy?.allowed_payment_terms?.join(', '))
        + field('sensitive_countries', 'کشورهای حساس (با کاما)', 'text', policy?.sensitive_countries?.join(', '), false)
        + field('sensitive_customers', 'مشتریان حساس (با کاما)', 'text', policy?.sensitive_customers?.join(', '), false),
        'ثبت نسخه جدید سیاست');
      html += '<h2>ارزیابی پیشنهاد</h2>' + form('evaluate',
        field('price', 'قیمت', 'number') + field('payment_term', 'شرایط پرداخت')
        + field('discount_pct', 'تخفیف (٪)', 'number', 0)
        + field('country', 'کشور', 'text', '', false) + field('customer_name', 'نام مشتری', 'text', '', false),
        'ارزیابی') + '<div id="decision" role="status"></div>';
      setup = () => {
        document.querySelectorAll('input[type=number]').forEach(input => {
          input.min = '0'; input.step = 'any';
          if (input.name.includes('discount')) input.max = '100';
        });
        const split = value => (value || '').split(',').map(item => item.trim()).filter(Boolean);
        bind('policy', data => api('/policy', 'POST', {
          product_category: data.product_category,
          price_floor: Number(data.price_floor),
          max_discount_pct: Number(data.max_discount_pct),
          allowed_payment_terms: split(data.allowed_payment_terms),
          sensitive_countries: split(data.sensitive_countries),
          sensitive_customers: split(data.sensitive_customers),
          capacity_notes: policy?.capacity_notes ?? null,
        }));
        document.getElementById('evaluate').addEventListener('submit', async event => {
          event.preventDefault();
          const button = event.target.querySelector('button[type="submit"]');
          button.disabled = true;
          try {
            const data = Object.fromEntries(new FormData(event.target));
            const result = await api('/policy/evaluate-offer', 'POST', {
              ...data, price: Number(data.price), discount_pct: Number(data.discount_pct),
            });
            document.getElementById('decision').innerHTML = `<div class="panel"><h2>${esc(label(result.status))}</h2>${
              result.reasons.map(reason => `<p>${esc(reason)}</p>`).join('') || '<p>هیچ نقض سیاستی یافت نشد.</p>'
            }</div>`;
          } catch (error) {
            feedback.innerHTML = `<p class="error">${esc(error.message)}</p>`;
          } finally {
            button.disabled = false;
          }
        });
      };
    } else if (page === 'team') {
      const users = await api('/auth/users');
      html = '<h1>اعضای تیم</h1><p>فقط مدیر می‌تواند حساب بسازد، نقش تغییر دهد یا دسترسی را غیرفعال کند.</p>'
        + table(['ایمیل', 'نقش', 'وضعیت', ''], users.map(member => [
          esc(member.email), esc(label(member.role)), member.is_active ? 'فعال' : 'غیرفعال',
          `<button type="button" class="secondary" data-toggle="${esc(member.id)}" data-active="${member.is_active}">${member.is_active ? 'غیرفعال‌سازی' : 'فعال‌سازی'}</button>`,
        ]))
        + '<h2>افزودن عضو</h2>' + form('member',
          field('email', 'ایمیل', 'email') + field('password', 'گذرواژه', 'password')
          + choice('role', 'نقش', [['sales', 'کارشناس فروش'], ['manager', 'مدیر']]), 'ایجاد حساب');
      setup = () => {
        bind('member', data => api('/auth/users', 'POST', data));
        document.querySelectorAll('[data-toggle]').forEach(button => {
          button.addEventListener('click', async () => {
            try {
              await api(`/auth/users/${encodeURIComponent(button.dataset.toggle)}`, 'PATCH', {is_active: button.dataset.active !== 'true'});
              await render();
              feedback.innerHTML = '<p class="success">وضعیت حساب به‌روزرسانی شد.</p>';
            } catch (error) {
              feedback.innerHTML = `<p class="error">${esc(error.message)}</p>`;
            }
          });
        });
      };
    } else {
      html = '<h1>صفحه پیدا نشد</h1><a href="#/dashboard">بازگشت به نمای کلی</a>';
    }

    if (current !== revision) return;
    view.innerHTML = html;
    setup();
  } catch (error) {
    if (current === revision) {
      view.innerHTML = `<h1>بارگذاری این صفحه ممکن نشد</h1><p class="error">${esc(error.message)}</p><button id="retry" type="button">تلاش دوباره</button>`;
      document.getElementById('retry')?.addEventListener('click', render);
    }
  }
}

document.querySelector('#logout').addEventListener('click', async () => {
  try {
    await api('/auth/logout', 'POST');
  } catch {
    // نشست ممکن است از قبل منقضی شده باشد.
  }
  clearToken();
  user = null;
  location.hash = '#/login';
  await render();
});

window.addEventListener('hashchange', render);
render();
