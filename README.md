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
  roadmap.md               نقشه‌راه محصول (فاز ۰ تا ۷)
  architecture.md          معماری کامل سیستم
  prd-mvp.md               فرم تعریف دامنه MVP (فاز ۰)
  sample-conversations.md  نمونه مکالمات ساختگی برای تست پرامپت
  wiki-recipe.md           دستورالعمل ویکی دانش پروژه (برای وقتی کدبیس بزرگ شد)
backend/
  app/                     اسکلت API (FastAPI + SQLAlchemy)
    models.py              Contact, Thread, Message, PolicyConfig, AuditLog
    policy/engine.py        Policy Engine (guardrail کف قیمت/شرایط پرداخت/کشور حساس)
    negotiation/state_machine.py   state machine مراحل مذاکره
    routers/                contacts, threads, policy API
```

## شروع سریع (Backend)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

مستندات تعاملی API: `http://localhost:8000/docs`

جزئیات بیشتر: [`backend/README.md`](backend/README.md)

## وضعیت پروژه

فاز ۰/۱ نقشه‌راه — تعریف دامنه MVP و اسکلت اولیه backend آماده است. کانال ارتباطی واقعی (واتساپ/ایمیل)، NLU/NLG واقعی و پیگیری خودکار هنوز پیاده‌سازی نشده‌اند. کارهای باقی‌مانده در [Issues](https://github.com/massoudsh/peimaneh/issues) این ریپو پیگیری می‌شوند.

## نقشه‌راه

نقشه‌راه کامل ۸ فازی محصول: [`docs/roadmap.md`](docs/roadmap.md)
