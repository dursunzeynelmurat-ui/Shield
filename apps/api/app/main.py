from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.uploads.router import router as uploads_router
from app.orders.router import router as orders_router
from app.alerts.router import router as alerts_router
from app.users.router import router as users_router
from app.merchants.router import router as merchants_router
from app.price_checks.router import router as price_checks_router

app = FastAPI(title="Fiyat Kalkanı API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(uploads_router)
app.include_router(orders_router)
app.include_router(alerts_router)
app.include_router(merchants_router)
app.include_router(price_checks_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
