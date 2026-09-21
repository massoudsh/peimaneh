# Backend — پیمانه (اسکلت فاز ۱)

اسکلت اولیه API طبق `docs/architecture.md`. شامل مدل‌های داده اصلی (Contact, Thread, Message, PolicyConfig, AuditLog)، موتور سیاست (Policy Engine) و state machine مذاکره.

## اجرا (روی سرور، نه داخل کانتینر بیلد سنگین)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

سپس مستندات تعاملی API در `http://localhost:8000/docs` در دسترس است.

## ساختار

```
app/
  database.py          اتصال SQLAlchemy (پیش‌فرض SQLite برای توسعه)
  models.py             مدل‌های داده (Contact, Thread, Message, PolicyConfig, AuditLog)
  schemas.py             Pydantic schemas برای API
  negotiation/
    state_machine.py     مراحل مذاکره + قوانین انتقال بین مراحل
  policy/
    engine.py             Guardrail — ارزیابی پیشنهاد در برابر سیاست شرکت
  routers/
    contacts.py, threads.py, policy.py
  main.py                 نقطه ورود FastAPI
```

## چیزهایی که عمداً هنوز پیاده نشده (فاز‌های بعدی نقشه‌راه)
- اتصال واقعی به کانال‌ها (واتساپ بیزینس API، ایمیل) — فعلاً فقط API داخلی برای ثبت پیام دستی/تستی.
- NLU/NLG واقعی (تشخیص نیاز، تولید پاسخ چندزبانه) — فعلاً فقط ذخیره متن خام پیام.
- Follow-up Scheduler و escalation rules خودکار.
- Auth/نقش‌بندی کاربران (مدیر بازرگانی در برابر عضو تیم فروش).
- Alembic migrations — فعلاً جدول‌ها مستقیم از مدل با `create_all` ساخته می‌شوند؛ برای پروداکشن باید migration اضافه شود.

## پیگیری و audit

- `GET /threads` — فهرست threadها با فیلتر مرحله، مخاطب، باز یا موعددار و pagination.
- `PUT/DELETE /threads/{id}/follow-up` — زمان‌بندی یا لغو پیگیری.
- `POST /threads/{id}/follow-up/complete` — ثبت انجام پیگیری.
- `GET /threads/{id}/audit` — تاریخچه تصمیم‌ها و رویدادهای thread.

جزئیات کامل هر فاز: `../docs/roadmap.md`.
