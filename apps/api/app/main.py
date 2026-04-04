import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.rate_limit import limiter
from app.compression import add_compression_middleware
from app.cache import add_etag_middleware

from app.auth.router import router as auth_router
from app.uploads.router import router as uploads_router
from app.orders.router import router as orders_router
from app.alerts.router import router as alerts_router
from app.users.router import router as users_router
from app.merchants.router import router as merchants_router
from app.price_checks.router import router as price_checks_router
from app.catalog.router import router as catalog_router
from app.deals.router import router as deals_router
from app.discovery.router import router as discovery_router
from app.affiliate.router import router as affiliate_router

app = FastAPI(title="Fiyat Kalkanı API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Transparent response compression (Brotli preferred, GZip fallback)
add_compression_middleware(app)
# ETag conditional GET support (304 Not Modified for unchanged responses)
add_etag_middleware(app)

import os

_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(uploads_router)
app.include_router(orders_router)
app.include_router(alerts_router)
app.include_router(merchants_router)
app.include_router(price_checks_router)
app.include_router(catalog_router)
app.include_router(deals_router)
app.include_router(discovery_router)
app.include_router(affiliate_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
