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
- دعوت اعضا، جداسازی سازمان‌ها، لغو نشست و محدودیت تلاش ورود هنوز تکمیل نشده‌اند؛ bearer-token و نقش‌های manager/sales موجودند.
- Alembic migrations — فعلاً جدول‌ها مستقیم از مدل با `create_all` ساخته می‌شوند؛ برای پروداکشن باید migration اضافه شود.

- `GET /auth/me` — اطلاعات کاربر جاری.
- `POST /auth/register` — ساخت حساب اول به‌عنوان manager؛ حساب‌های بعدی sales هستند.
- `POST /auth/login` — دریافت bearer token هفت‌روزه.

تمام endpointهای contacts، threads و dashboard به توکن نیاز دارند؛ policy فقط manager است. `/health` و endpointهای auth عمومی‌اند.


- `GET /threads` — فهرست threadها با فیلتر مرحله، مخاطب، باز یا موعددار و pagination.
- `PUT/DELETE /threads/{id}/follow-up` — زمان‌بندی یا لغو پیگیری.
- `POST /threads/{id}/follow-up/complete` — ثبت انجام پیگیری.
- `GET /threads/{id}/audit` — تاریخچه تصمیم‌ها و رویدادهای thread.

## تست‌ها

از ریشه مخزن، پس از ساخت محیط مجازی:

```bash
backend/.venv/bin/pip install -r backend/requirements-dev.txt
PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend -p 'test_*.py' -v
```

تست‌های auth و follow-up روی SQLite مستقل اجرا می‌شوند؛ دیتابیس برنامه تغییر نمی‌کند.
زمان `due_at` باید آینده و دارای timezone باشد. پاسخ مخاطب reminder فعال را لغو می‌کند؛ draft این کار را نمی‌کند. تکمیل پیگیری فقط انجام کار دستی را ثبت می‌کند و پیامی نمی‌فرستد.

API دارای احراز هویت اولیه و رابط چندصفحه‌ای است، اما برای انتشار عمومی آماده نیست: ثبت‌نام عمومی و داده مشترک نیازمند بازطراحی دسترسی هستند. مقدار actor در audit فعلاً نقش اعلام‌شده مسیر است، نه هویت تأییدشده کاربر. صف اعلان و worker خودکار هنوز ساخته نشده‌اند.

پیش‌نویس issueهای اجرایی، وابستگی‌ها و معیارهای پذیرش: `../docs/github-issues.json`. این فایل به معنی ثبت issue در GitHub نیست؛ پیش از انتشار باید با issueهای موجود تطبیق داده شود.

جزئیات کامل هر فاز: `../docs/roadmap.md`.
