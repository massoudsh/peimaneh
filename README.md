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
  migrations/              migrationهای نسخه‌دار Alembic
  entrypoint.sh            اجرای migration سپس uvicorn
  test_*.py                تست‌های integration
frontend/
  index.html               میز کار فارسی و RTL
  app.js                   صفحات، نقش‌ها و اتصال واقعی به API
  style.css                رابط responsive
  test-app.cjs             تست‌های جریان بدون مرورگر
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

کانتینر backend پیش از اجرای API، `alembic upgrade head` را اجرا می‌کند؛ ساخت جدول در startup انجام نمی‌شود.

اجرای تست‌های backend و frontend داخل container:

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

رابط شامل صفحات نمای کلی، مخاطبان، فرصت‌ها، پیگیری‌ها، مکالمه، سیاست شرکت و اعضای تیم است و همهٔ فرم‌ها endpointهای واقعی backend را فراخوانی می‌کنند. زبان پیش‌فرض رابط فارسی و جهت آن RTL است؛ محتوای پیام‌های خارجی با `dir="auto"` نمایش داده می‌شود.

### ورود، راه‌اندازی و نقش‌ها

ثبت‌نام عمومی وجود ندارد. برای ساخت نخستین حساب مدیر، در `.env` مقدار `ALLOW_BOOTSTRAP_REGISTRATION=true` بگذارید، سرویس را اجرا کنید و از فرم «راه‌اندازی اولیه» یک حساب بسازید. سپس مقدار را به `false` برگردانید و سرویس را دوباره بالا بیاورید.

مدیر می‌تواند از صفحهٔ «اعضای تیم» حساب‌های `sales` یا `manager` بسازد، نقش را تغییر دهد یا حساب را غیرفعال کند. تمام APIهای contacts، threads و dashboard به bearer token نیاز دارند؛ سیاست شرکت، کاربران و تأیید نهایی فقط برای مدیر مجاز است. رمزها با PBKDF2 و salt ذخیره می‌شوند، فقط hash توکن در دیتابیس می‌ماند و پس از پنج تلاش ناموفق حساب برای ۱۵ دقیقه قفل می‌شود. خروج، نشست جاری را باطل می‌کند و «خروج از همهٔ دستگاه‌ها» همهٔ نشست‌های کاربر را.


دادهٔ PostgreSQL در volume منطقی `postgres_data` نگهداری می‌شود (نام واقعی شامل نام پروژه Compose است). مقادیر `.env.example` صرفاً نمونه‌اند؛ `POSTGRES_PASSWORD` و رمز URL-encoded در `DATABASE_URL` باید هماهنگ باشند و با تغییر user/db نیز URL اصلاح شود. تغییر رمز env رمز دیتابیسِ موجود در volume را تغییر نمی‌دهد. `.env` را commit نکنید. پورت‌های وب و API فقط روی loopback میزبان bind می‌شوند و دیتابیس پورت عمومی ندارد؛ انتشار نیازمند reverse proxy امن و رفع موانع امنیتی roadmap است. `down -v` همه داده‌های volume را حذف می‌کند؛ قبل از آن backup لازم است.

## اجرای backend بدون Docker

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
DATABASE_URL=sqlite:///./peimaneh.db .venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/python -m unittest discover -p 'test_*.py' -v
ALLOW_BOOTSTRAP_REGISTRATION=true .venv/bin/uvicorn app.main:app --reload
```

مستندات تعاملی API: `http://localhost:8000/docs`

برای اجرای بدون Docker، frontend را با هر static server سرو کنید یا از nginx container استفاده کنید؛ مسیر `/api` باید به backend proxy شود. تست‌های frontend بدون مرورگر اجرا می‌شوند:

```bash
node --check frontend/app.js
node --test frontend/test-app.cjs
```

جزئیات بیشتر: [`backend/README.md`](backend/README.md)

## وضعیت پروژه

فاز ۱/۲ نقشه‌راه — API پیگیری، audit، policy، مخاطب و مذاکره به همراه میز کار فارسی RTL، احراز هویت bearer-token با نقش‌ها، migrationهای Alembic و compose آماده است. اتصال واقعی کانال‌های خارجی، NLU/NLG، worker اعلان، جداسازی سازمانی (multi-tenant) و آزمون deployment روی PostgreSQL هنوز باقی است. Human-in-the-loop همچنان اجباری است.

## نقشه‌راه

نقشه‌راه کامل ۸ فازی محصول: [`docs/roadmap.md`](docs/roadmap.md)
