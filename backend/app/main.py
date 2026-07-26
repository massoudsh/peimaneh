from fastapi import FastAPI

from app.database import Base, engine
from app.routers import contacts, policy, threads

app = FastAPI(title="پیمانه — Peimaneh API", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    # فاز اسکلت: جدول‌ها مستقیم از مدل‌ها ساخته می‌شوند.
    # وقتی schema پایدار شد، باید به Alembic migration مهاجرت شود.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok", "product": "peimaneh"}


app.include_router(contacts.router)
app.include_router(threads.router)
app.include_router(policy.router)
