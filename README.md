# Fiyat Kalkanı

Post-purchase price protection for Turkish e-commerce. Upload an order receipt or screenshot, track the price for 14 days, and get alerted the moment the price drops — with a concrete recommendation to request a refund, return and rebuy, or ask for a price match.

## Features

- **Upload & parse** — drag-and-drop order screenshots (PNG/JPG/WebP/PDF); AI (GPT-4o or Claude) extracts merchant, product, price, and return deadline automatically
- **Product matching** — searches Trendyol and Hepsiburada for the same product; scores candidates by token overlap, brand, model, variant, and price proximity
- **Price monitoring** — daily background job re-fetches live prices via multi-strategy scraping (JSON API → embedded JS state → JSON-LD → regex fallback)
- **Alerts** — price-drop alert when savings ≥ 1 ₺ / 1 %; return-deadline alert when ≤ 3 days remain; deduplicated per order
- **Action recommendations** — deterministic engine recommends: ask price match (same seller), return & rebuy (different seller), or manual review
- **Catalog** — product search with fuzzy Turkish text matching; per-product offer comparison with Offers table sorted by effective price
- **Category classifier** — auto-classifies products into a canonical tree using Turkish-aware transliteration + 5-char prefix Jaccard similarity; caches merchant raw strings in `source_map` JSON column
- **Deals** — coupon/offer listings scraped every 6 h via `fetch_deals()` on each connector; filterable by merchant and discount type
- **Discovery feed** — personalised recommendation feed built every 12 h; weighted by category interest signals from user interaction events; accessible at `/for-you` (not linked in the main nav — reach via direct URL or homepage recommendations)
- **Watchlist** — track catalog products with optional target price; highlights when `lowest_price ≤ target_price`; accessible at `/watchlist` (not linked in the main nav — reach via the "Takip Et" toggle on any product page)
- **Affiliate click tracking** — `POST /affiliate/click` records clicks with hashed IP for attribution; write-only (no analytics UI)
- **Compression** — Brotli preferred, GZip fallback via middleware; ETag / 304 Not Modified support for all JSON responses
- **Cache** — in-process async TTL cache (LRU, configurable per function) for catalog reads

## Architecture

```
apps/
  api/          FastAPI backend (Python 3.12)
    app/        Application modules (auth, orders, catalog, deals, …)
    worker/     Celery tasks (inside api image)
    migrations/ Alembic migrations (0001 → 0004)
    tests/      pytest test suite (8 files)
  web/          Next.js 15 frontend (TypeScript + Tailwind CSS)
docker-compose.yml   5 services: db · redis · api · worker · beat · web
```

**Stack:** FastAPI · PostgreSQL 16 · SQLAlchemy 2 (async/asyncpg) · Alembic · Redis 7 · Celery 5 · Next.js 15 · Tailwind CSS · httpx · Pydantic v2

## Local Setup

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local API dev)
- Node.js 22+ (for local web dev)

### 1. Environment

```bash
cp .env.example .env
# Set at minimum: OPENAI_API_KEY or ANTHROPIC_API_KEY
# SECRET_KEY should be a long random string in production
```

### 2. Full stack via Docker Compose

```bash
docker compose up --build
```

Services:
- Web: http://localhost:3000
- API + Swagger UI: http://localhost:8000/docs
- Worker (Celery): processes background tasks
- Beat (Celery): runs scheduled jobs

### 3. Local API dev (no Docker)

```bash
# Start dependencies
docker compose up -d db redis

# Install and migrate
cd apps/api
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://shield:shield@localhost:5432/shield \
  alembic upgrade head

# Start API
uvicorn app.main:app --reload
```

### 4. Local web dev

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### 5. Local worker dev

```bash
cd apps/api
celery -A worker.celery_app worker --loglevel=info

# Scheduler (beat) — separate terminal
celery -A worker.celery_app beat --loglevel=info
```

### 6. Tests

```bash
cd apps/api
pytest
```

Test files cover: auth/security, upload MIME validation, file storage, AI parsing adapter, product matching, category classifier, compression + cache, action recommendations.

## User Flow

1. Register / Login
2. Upload order screenshot → AI extracts all fields automatically
3. Review and edit extracted data → Verify
4. Run product matching → system finds the same product on Trendyol/Hepsiburada
5. Start monitoring (14-day window)
6. Daily price check runs automatically (or trigger manually from the order page)
7. Alert fires when price drops → recommendation shown (price match / return & rebuy / manual review)
8. Browse **Fırsatlar** (`/deals`) for coupons and discount codes
9. Browse **Karşılaştır** (`/compare`) to search the catalog; click a product to compare offers across merchants
10. On any product page, toggle **Takip Et** to add it to your watchlist (`/watchlist`)
11. Visit `/for-you` directly to see your personalised recommendation feed (built every 12 h from your interaction history)

## API Reference

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Login → JWT |

### Users
| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/me` | Current user |
| PATCH | `/users/me` | Update email |
| POST | `/users/me/change-password` | Change password |
| DELETE | `/users/me` | Delete account |
| GET | `/users/me/dashboard` | Dashboard cards (list) |
| GET | `/users/me/summary` | Homepage aggregate stats + recent orders |

### Uploads & Orders
| Method | Path | Description |
|--------|------|-------------|
| POST | `/uploads` | Upload file (magic-byte MIME validation) |
| GET | `/uploads/{id}` | Get upload metadata |
| GET | `/uploads/files/{key}` | Serve file (owner-scoped) |
| POST | `/orders/from-upload/{upload_id}` | Parse upload → create order |
| GET | `/orders/{id}` | Get order |
| PATCH | `/orders/{id}/verify` | Edit + verify order fields |
| POST | `/orders/{id}/match` | Run product matching |
| POST | `/orders/{id}/start-monitoring` | Begin price monitoring |
| POST | `/orders/{id}/stop-monitoring` | Stop monitoring |
| GET | `/orders/{id}/recommendation` | Get action recommendation |
| GET | `/orders/{id}/matches` | List product matches |

### Price Checks & Alerts
| Method | Path | Description |
|--------|------|-------------|
| POST | `/price-checks/run/{order_id}` | Trigger manual price check |
| GET | `/price-checks/{order_id}` | List price check history |
| GET | `/alerts` | List alerts (scoped to user) |
| PATCH | `/alerts/{id}/status` | Update alert status |

### Catalog
| Method | Path | Description |
|--------|------|-------------|
| GET | `/catalog/categories` | List categories (root or children of `parent_id`) |
| POST | `/catalog/classify` | Resolve raw merchant category string → canonical category |
| POST | `/catalog/ingest` | Bulk ingest raw merchant product dicts |
| GET | `/catalog/search` | Full-text + category + brand search |
| GET | `/catalog/products/{id}` | Product detail with all merchant offers |

### Deals, Discovery, Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/deals/offers` | Paginated active deals (filter by merchant / discount type) |
| GET | `/discovery/feed` | Personalised product recommendations |
| POST | `/discovery/interest-events` | Record user interest event |
| GET | `/watchlist` | List watchlist with lowest prices |
| POST | `/watchlist` | Add product to watchlist |
| DELETE | `/watchlist/{product_id}` | Remove from watchlist |

### Merchants & Affiliate
| Method | Path | Description |
|--------|------|-------------|
| GET | `/merchants` | List registered merchants |
| POST | `/affiliate/click` | Record affiliate click event (write-only; no read/analytics endpoint exists) |

## Background Jobs (Celery Beat)

| Schedule | Task | Description |
|----------|------|-------------|
| Every 24 h | `daily_price_check_job` | Re-fetch prices for all monitored orders; fire alerts |
| Every 1 h | `refresh_prices_job` | Update `merchant_offers` with live connector prices; append to `price_history` |
| Every 6 h | `ingest_offers_job` | Expire stale deals; fetch new coupons via `fetch_deals()` on each connector |
| Every 12 h | `build_feed_job` | Rebuild personalised recommendation feed per user using interest event history |

## Frontend Pages

Nav links (Desktop Navbar): **Dashboard · Karşılaştır · Fırsatlar · Sipariş Ekle · Uyarılar**

Pages not in the Navbar are marked *(unlisted)* — reachable via direct URL or in-page links only.

| Route | Nav | Description |
|-------|-----|-------------|
| `/` | — | Homepage: search bar, stats, recent orders, deals preview, recommendations preview |
| `/login` `/register` | — | Auth |
| `/upload` | ✓ Sipariş Ekle | Drag-and-drop order upload with AI parse progress |
| `/dashboard` | ✓ Dashboard | All orders as cards with price comparison |
| `/orders/[id]` | *(unlisted)* | Full order detail, verify/match/monitor/price-check flow |
| `/alerts` | ✓ Uyarılar | All alerts with dismiss/seen actions |
| `/compare` | ✓ Karşılaştır | Catalog search with category filter |
| `/compare/[id]` | *(unlisted)* | Product detail with merchant offer table; Schema.org `Product` JSON-LD (client-rendered) |
| `/deals` | ✓ Fırsatlar | Active coupons and discount codes; Schema.org `ItemList` JSON-LD (client-rendered) |
| `/for-you` | *(unlisted)* | Personalised discovery feed — no Navbar entry; link from homepage "Senin İçin" section goes to individual product pages, not this route |
| `/watchlist` | *(unlisted)* | Watched products with target price — no Navbar entry; reachable via "Takip Et" toggle on `/compare/[id]` |
| `/settings` | *(unlisted)* | Profile, password, account deletion |

## Known Limitations

- **`/for-you` and `/watchlist` are not linked in the Navbar.** Both pages are fully implemented (API + UI), but users must know the URL or find the Watchlist toggle on a product page. Adding them to `NAV_LINKS` in `apps/web/src/components/Navbar.tsx` is the only change required to surface them.

- **Dynamic SEO for `/compare/[id]` always falls back to static.** `generateMetadata` in `apps/web/src/app/compare/[id]/layout.tsx` fetches `/catalog/products/{id}` without an auth token. The endpoint requires authentication, so the fetch returns 401 and the title is always "Ürün Detayı | Fiyat Kalkanı". To fix: make the catalog product endpoint public for reads, or pass a service token in the server-side fetch.

- **JSON-LD structured data is client-rendered.** The Schema.org `Product` block in `/compare/[id]` and `ItemList` block in `/deals` are injected after React hydration. Most crawlers will not see them. To fix: move them into the server-side layout.

- **Affiliate click tracking is write-only.** `POST /affiliate/click` persists `AffiliateClick` rows; there is no read endpoint, admin view, or per-product click count exposed anywhere.

- **Onboarding only fires on `/`.** The 4-step modal in `apps/web/src/components/Onboarding.tsx` is mounted only in `apps/web/src/app/page.tsx`. Users who register and land on `/upload` or `/dashboard` directly never see it. The onboarding steps also do not mention `/for-you` or `/watchlist`.

- **Deal scraping is regex-dependent.** `TrendyolConnector.fetch_deals()` and `HepsiburadaConnector.fetch_deals()` parse embedded JS state; if the merchant page structure changes, scraping silently returns empty results with no fallback or monitoring.

## AI Provider Configuration

Set `AI_PROVIDER=openai` (default) or `AI_PROVIDER=anthropic` in `.env`.

| Provider | Key variable | Default model |
|----------|-------------|---------------|
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` |

If no key is configured, the `StubParsingAdapter` is used — returns `confidence=0.1` and a placeholder title, which lets you test the full order flow without an AI key.

## Adding a Merchant Connector

Implement `BaseConnector` in `apps/api/app/merchants/connector.py`:

```python
class MyMerchantConnector(BaseConnector):
    merchant_name = "mymerchant"
    domain = "mymerchant.com"

    async def search(self, title: str, brand: str | None, model: str | None) -> list[dict]:
        # Return [{url, title, seller, price, currency, image_url}]
        ...

    async def fetch_price(self, url: str) -> dict:
        # Return {listed_price, shipping_price, final_price, currency,
        #         seller, stock_status, success, error_message}
        ...

    async def fetch_deals(self) -> list[dict]:
        # Optional: return [{title, code, discount_type, discount_value,
        #                     minimum_spend, conditions, url, expires_at}]
        return []
```

Register it in `_CONNECTORS` at the bottom of the file.

## Database Migrations

```bash
cd apps/api
alembic upgrade head          # apply all migrations
alembic revision --autogenerate -m "description"  # generate new migration
```

Migrations: `0001` initial schema · `0002` indexes · `0003` catalog + watchlist + discovery · `0004` categories tree with materialized paths
