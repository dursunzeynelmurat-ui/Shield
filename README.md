# Fiyat Kalkanı

Post-purchase price protection for Turkish e-commerce. Upload an order screenshot, track the price for 14 days, and get alerted when the price drops so you can ask for a refund or return and rebuy.

## Architecture

```
apps/
  api/       FastAPI backend (Python 3.12)
  web/       Next.js 15 frontend (TypeScript)
  worker/    Celery background workers
```

**Stack:** FastAPI · PostgreSQL · SQLAlchemy (async) · Alembic · Redis · Celery · Next.js · Tailwind CSS

## Local Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (for local API dev)
- Node.js 22+ (for local web dev)

### 1. Environment

```bash
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY or ANTHROPIC_API_KEY
```

### 2. Run with Docker Compose

```bash
docker compose up -d db redis
# Run migrations
cd apps/api
pip install -r requirements.txt
DATABASE_URL=postgresql+psycopg2://shield:shield@localhost:5432/shield \
  alembic upgrade head
# Start API
uvicorn app.main:app --reload
```

Or run everything with Docker:

```bash
docker compose up --build
```

Then open:
- API: http://localhost:8000/docs
- Web: http://localhost:3000

### 3. Run web locally

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### 4. Run worker

```bash
cd apps/api
celery -A apps.worker.celery_app worker --loglevel=info
```

### 5. Run tests

```bash
cd apps/api
pip install -r requirements.txt
pytest
```

## User Flow

1. Register / Login
2. Upload an order screenshot (PNG/JPG/WebP/PDF)
3. AI extracts order data → review and verify/edit fields
4. Run product matching → confirm the match
5. Start monitoring (14-day window)
6. Manually trigger or wait for daily price check job
7. Alert created if price drops → recommendation shown
8. Take action: price match request, return & rebuy, or manual review

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/register | Register |
| POST | /auth/login | Login (JWT) |
| GET | /users/me | Current user |
| GET | /users/me/dashboard | Dashboard cards |
| POST | /uploads | Upload file |
| GET | /uploads/{id} | Get upload |
| POST | /orders/from-upload/{upload_id} | Parse upload → order |
| GET | /orders/{id} | Get order |
| PATCH | /orders/{id}/verify | Verify/edit order |
| POST | /orders/{id}/match | Run product matching |
| POST | /orders/{id}/start-monitoring | Start monitoring |
| POST | /orders/{id}/stop-monitoring | Stop monitoring |
| GET | /orders/{id}/recommendation | Get recommendation |
| GET | /orders/{id}/matches | List product matches |
| POST | /price-checks/run/{order_id} | Trigger price check |
| GET | /price-checks/{order_id} | List price checks |
| GET | /alerts | List alerts |
| PATCH | /alerts/{id}/status | Update alert status |

## AI Provider Configuration

Set `AI_PROVIDER=openai` (default) or `AI_PROVIDER=anthropic` in `.env`.

If no key is configured, the stub adapter is used (returns low-confidence placeholder data useful for testing the full flow).

## Extending Merchants

Add a connector in `apps/api/app/merchants/connector.py` by implementing `BaseConnector`:

```python
class MyMerchantConnector(BaseConnector):
    merchant_name = "mymerchant"
    domain = "mymerchant.com"

    async def search(self, title, brand, model) -> list[dict]: ...
    async def fetch_price(self, url) -> dict: ...
```

Then register it in `_CONNECTORS`.
