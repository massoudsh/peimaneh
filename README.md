# پیمانه (Peimaneh)

**ایجنت هوشمند اجرای تجارت خارجی — از مکالمه خارجی تا سفارش قطعی**

AI Trade Execution Agent for Iranian exporters & importers.

---

## مسئله

شرکت‌های ایرانی بعد از پیدا کردن خریدار یا تأمین‌کننده خارجی، ابزار هوشمندی ندارند که مکالمه، پیگیری، مذاکره قیمت، نمونه، شرایط پرداخت، حمل و آماده‌سازی سفارش را حرفه‌ای، چندزبانه و درون چارچوب سیاست‌های شرکت جلو ببرد. فرصت‌های واقعی بین پیام‌های دیرهنگام، ترجمه ضعیف، مذاکره پراکنده و پیگیری فراموش‌شده از بین می‌روند.

## راه‌حل

پیمانه مکالمه با خریدار/فروشنده خارجی را می‌فهمد، نیاز طرف مقابل را تشخیص می‌دهد، به زبان و لحن بازار هدف (انگلیسی، عربی، ترکی و ...) پیام حرفه‌ای پیشنهاد می‌دهد، پیگیری‌ها را یادآوری می‌کند و مذاکره را تا مرحله آماده‌سازی سفارش/پیش‌فاکتور پیش می‌برد — همیشه درون چارچوب سیاست‌های شرکت (کف قیمت، شرایط پرداخت مجاز، ظرفیت واقعی، کشورها/مشتریان حساس).

### اصل محوری — Human-in-the-loop

پیمانه **هیچ‌وقت** به‌جای انسان تعهد تجاری نمی‌دهد یا معامله را نمی‌بندد. هر پیشنهاد خارج از سیاست شرکت باید قبل از ارسال تأیید انسان بگیرد. این محدودیت طراحی اصلی کل معماری است، نه یک فیچر جانبی.

## چرخه مذاکره

```
inquiry → quote → sample → payment_terms → shipping → proforma → confirmation
```

هر انتقال مرحله زیر نظر Policy Engine است — نگاه کن [`docs/architecture.md`](docs/architecture.md).

## ساختار مخزن

```
docs/
  roadmap.md               نقشه‌راه محصول
  architecture.md          معماری سیستم
  github-issues.json       backlog اجرایی issueها
backend/
  app/                     API واقعی FastAPI + SQLAlchemy
  test_followups.py        تست‌های integration endpointها
frontend/
  index.html               dashboard چندصفحه‌ای
  app.js                   صفحات و اتصال واقعی به API
  style.css                رابط responsive و RTL-ready
docker-compose.yml         frontend + backend + PostgreSQL
```

## اجرای کامل با Docker

پیش‌نیاز: Docker و Docker Compose. ابتدا تنظیمات توسعه را بسازید و رمز را عوض کنید:

```bash
cp .env.example .env
docker compose up --build
```

- Dashboard: `http://localhost:8080`
- API و مستندات: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

اجرای تست‌های backend داخل container:

```bash
docker compose --profile test run --build --rm backend-tests
docker compose --profile test run --build --rm frontend-tests
```

توقف سرویس‌ها بدون حذف داده:

```bash
docker compose down
```

حذف volume دیتابیس فقط برای reset توسعه:

```bash
docker compose down -v
```

رابط شامل صفحات Overview، Contacts، Opportunities، Follow-ups، Conversation و Company Policy است و فرم‌های آن مستقیماً endpointهای backend را فراخوانی می‌کنند؛ دکمه‌های نمایشی یا دادهٔ ساختگی در مسیر اصلی وجود ندارد.

### ورود و نقش‌ها

صفحهٔ ورود در اولین اجرا نمایش داده می‌شود. اولین حسابی که ساخته می‌شود باید `manager` باشد؛ ثبت‌نام‌های بعدی فقط `sales` هستند. APIهای contacts، threads و dashboard به bearer token نیاز دارند و تمام policy endpointها فقط برای manager مجازند. رمزها به‌صورت plaintext ذخیره نمی‌شوند و token خام در دیتابیس نگهداری نمی‌شود.


دادهٔ PostgreSQL در volume منطقی `postgres_data` نگهداری می‌شود (نام واقعی شامل نام پروژه Compose است). مقادیر `.env.example` صرفاً نمونه‌اند؛ `POSTGRES_PASSWORD` و رمز URL-encoded در `DATABASE_URL` باید هماهنگ باشند و با تغییر user/db نیز URL اصلاح شود. تغییر رمز env رمز دیتابیسِ موجود در volume را تغییر نمی‌دهد. `.env` را commit نکنید. پورت‌های وب و API فقط روی loopback میزبان bind می‌شوند و دیتابیس پورت عمومی ندارد؛ انتشار نیازمند reverse proxy امن و رفع موانع امنیتی roadmap است. `down -v` همه داده‌های volume را حذف می‌کند؛ قبل از آن backup لازم است.

## اجرای backend بدون Docker

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=. .venv/bin/python -m unittest discover -p 'test_*.py' -v
.venv/bin/uvicorn app.main:app --reload
```

مستندات تعاملی API: `http://localhost:8000/docs`

جزئیات بیشتر: [`backend/README.md`](backend/README.md)

## وضعیت پروژه

فاز ۱/۲ نقشه‌راه — API پیگیری، audit، policy، مخاطب و مذاکره به همراه dashboard، احراز هویت bearer-token و compose آماده است. اتصال واقعی کانال‌های خارجی، NLU/NLG، worker اعلان و migrationهای production هنوز باید در issueهای roadmap پیاده شوند. Human-in-the-loop همچنان اجباری است.

## نقشه‌راه

نقشه‌راه کامل ۸ فازی محصول: [`docs/roadmap.md`](docs/roadmap.md)
