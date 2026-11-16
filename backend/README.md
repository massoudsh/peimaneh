# Backend — پیمانه

API واقعی FastAPI + SQLAlchemy طبق `docs/architecture.md`. شامل مدل‌های داده (Contact, Thread, Message, PolicyConfig, AuditLog, User, SessionToken)، موتور سیاست، state machine مذاکره، احراز هویت و migrationهای Alembic.

## اجرا

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
DATABASE_URL=sqlite:///./peimaneh.db .venv/bin/alembic upgrade head
ALLOW_BOOTSTRAP_REGISTRATION=true .venv/bin/uvicorn app.main:app --reload
```

سپس اولین حساب مدیر را از `POST /auth/bootstrap` بسازید و متغیر `ALLOW_BOOTSTRAP_REGISTRATION` را به `false` برگردانید. مستندات تعاملی API: `http://localhost:8000/docs`.

## ساختار

```
app/
  database.py            اتصال SQLAlchemy (SQLite برای توسعه، PostgreSQL در compose)
  models.py              مدل‌های داده و ایندکس‌ها
  schemas.py             Pydantic schemas و اعتبارسنجی ورودی
  auth.py                hash رمز/توکن، نشست bearer، نقش‌ها، قفل ورود
  negotiation/
    state_machine.py      مراحل مذاکره و انتقال‌های مجاز
  policy/
    engine.py             Guardrail ارزیابی پیشنهاد
  routers/
    auth.py, contacts.py, threads.py, policy.py
  main.py                 نقطه ورود FastAPI و خلاصه dashboard
migrations/               baseline و migrationهای نسخه‌دار Alembic
entrypoint.sh             alembic upgrade head سپس uvicorn
```

## احراز هویت و نقش‌ها

- `POST /auth/bootstrap` — ساخت نخستین مدیر؛ فقط با `ALLOW_BOOTSTRAP_REGISTRATION=true` و وقتی هیچ کاربری وجود ندارد.
- `POST /auth/login` — دریافت bearer token هفت‌روزه؛ پس از ۵ تلاش ناموفق، حساب ۱۵ دقیقه قفل می‌شود.
- `POST /auth/logout` — باطل‌کردن نشست جاری؛ `POST /auth/logout-all` همهٔ نشست‌ها.
- `GET /auth/me` — کاربر جاری.
- `GET/POST /auth/users` و `PATCH /auth/users/{id}` — مدیریت اعضا، فقط مدیر.

تمام endpointهای contacts، threads و dashboard به توکن نیاز دارند. سیاست شرکت و مدیریت کاربران فقط برای مدیر است. تأیید نهایی یک فرصت (`confirmation`) نیز فقط با نقش مدیر انجام می‌شود. هویت ثبت‌شده در audit ایمیل کاربر تأییدشده است، نه مقداری از بدنهٔ درخواست.

## APIهای اصلی

- `GET /contacts` — جست‌وجو (`q`) و pagination.
- `GET /threads` — فیلتر مرحله، مخاطب، باز/موعددار، جست‌وجو و pagination.
- `GET /threads/{id}/transitions` — انتقال‌های مجاز از سمت سرور.
- `POST /threads/{id}/transition` با بدنهٔ `{"target_stage": "..."}`.
- `PUT/DELETE /threads/{id}/follow-up` — زمان‌بندی یا لغو پیگیری.
- `POST /threads/{id}/follow-up/complete` — ثبت انجام پیگیری.
- `GET /threads/{id}/audit` — تاریخچه رویدادها با pagination.
- `GET/POST /policy` و `POST /policy/evaluate-offer` — فقط مدیر.

## Docker

از ریشه پروژه:

```bash
cp .env.example .env
docker compose up --build
docker compose --profile test run --build --rm backend-tests
```

`Dockerfile` migrationها را قبل از اجرای API اعمال می‌کند و با کاربر غیر root اجرا می‌شود؛ `Dockerfile.test` فقط برای تست است و env/cache وارد image نمی‌شوند.

## تست‌ها

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m unittest discover -p 'test_*.py' -v
```

تست‌ها روی SQLite در حافظه اجرا می‌شوند و دیتابیس برنامه را تغییر نمی‌دهند. پوشش: احراز هویت/نقش‌ها/قفل ورود/لغو نشست، سیاست و نسخه‌بندی، follow-up، audit، جست‌وجو، pagination و انتقال مرحله.

## موارد باقی‌مانده (فازهای بعدی)

- اتصال رسمی کانال‌ها (واتساپ بیزینس API، ایمیل) و NLU/NLG واقعی.
- worker اعلان پیگیری با idempotency و inbox.
- جداسازی سازمانی (multi-tenant) و دعوت‌نامهٔ امن به‌جای ساخت حساب مستقیم توسط مدیر.
- آزمون runtime روی PostgreSQL و سخت‌سازی secretهای deployment؛ CI فعلی compose را validate می‌کند اما imageها را اجرا نمی‌کند.

پیش‌نویس issueهای اجرایی: `../docs/github-issues.json`. جزئیات فازها: `../docs/roadmap.md`.
