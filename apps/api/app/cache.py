"""
Response caching utilities
===========================
Two independent mechanisms:

1. **ETag middleware** — computes a fast xxhash/MD5 of every JSON response body
   and attaches ``ETag`` + ``Cache-Control`` headers.  Clients that re-request
   with ``If-None-Match`` matching the current ETag receive a ``304 Not Modified``
   with zero body bytes, cutting bandwidth for unchanged data.

2. **In-process LRU cache** for catalog reads — caches the result of expensive
   SQLAlchemy queries in RAM for a configurable TTL.  Keyed by (function name,
   args).  Safe for read-only data; invalidated on write automatically when
   the caller calls ``invalidate()``.

   Not distributed (single-process only).  For multi-process deployments,
   replace with Redis via the same interface.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, TypeVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ETag middleware
# ---------------------------------------------------------------------------

_ETAG_CONTENT_TYPES = frozenset([
    "application/json",
    "text/plain",
    "text/html",
    "text/csv",
])

_NO_CACHE_PATHS = frozenset([
    "/health",
    "/auth/login",
    "/auth/register",
])

_NO_STORE_METHODS = frozenset(["POST", "PATCH", "DELETE", "PUT"])


class ETagMiddleware(BaseHTTPMiddleware):
    """
    Adds ``ETag``, ``Cache-Control``, and ``Vary`` headers to JSON responses.

    * ``GET`` / ``HEAD`` read-only responses: ``Cache-Control: no-cache``
      (client must revalidate, but can store the response body).
    * Mutating methods and auth endpoints: ``Cache-Control: no-store``.
    * Handles ``If-None-Match`` conditional requests → ``304 Not Modified``.

    The ETag is a truncated MD5 of the response body — deterministic,
    fast, and 16 hex chars long.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        ct = response.headers.get("content-type", "")
        mime = ct.split(";")[0].strip()
        if mime not in _ETAG_CONTENT_TYPES:
            return response

        # Read the body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # No-store paths / mutating methods
        path = request.url.path
        method = request.method.upper()

        if path in _NO_CACHE_PATHS or method in _NO_STORE_METHODS:
            response.headers["Cache-Control"] = "no-store, private"
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=ct,
            )

        # Compute ETag
        etag = '"' + hashlib.md5(body).hexdigest()[:16] + '"'  # noqa: S324 (non-crypto use)

        # Conditional GET
        client_etag = request.headers.get("if-none-match", "")
        if client_etag == etag:
            return Response(status_code=304, headers={"ETag": etag, "Vary": "Accept-Encoding"})

        headers = dict(response.headers)
        headers["ETag"] = etag
        headers["Cache-Control"] = "no-cache, private"
        headers["Vary"] = "Accept-Encoding, Authorization"

        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=ct,
        )


def add_etag_middleware(app) -> None:
    """Register the ETag middleware on a FastAPI app."""
    app.add_middleware(ETagMiddleware)
    logger.info("ETag middleware registered")


# ---------------------------------------------------------------------------
# In-process LRU TTL cache for read-heavy async functions
# ---------------------------------------------------------------------------

_F = TypeVar("_F", bound=Callable[..., Any])


class _TTLCache:
    """Thread-safe (asyncio) LRU cache with per-entry TTL."""

    def __init__(self, maxsize: int = 256, ttl: float = 60.0) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        try:
            payload = json.dumps({"fn": func_name, "a": args, "k": kwargs},
                                  default=str, sort_keys=True)
        except (TypeError, ValueError):
            payload = repr((func_name, args, kwargs))
        return hashlib.md5(payload.encode()).hexdigest()  # noqa: S324

    async def get(self, key: str) -> tuple[bool, Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False, None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return False, None
            self._store.move_to_end(key)
            return True, value

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, time.monotonic() + self._ttl)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    async def evict_expired(self) -> int:
        """Remove all expired entries.  Returns count removed."""
        now = time.monotonic()
        async with self._lock:
            expired = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in expired:
                del self._store[k]
        return len(expired)


# Global default cache (can be overridden per module)
_default_cache = _TTLCache(maxsize=512, ttl=120.0)


def cached(
    ttl: float = 120.0,
    maxsize: int = 512,
    cache: _TTLCache | None = None,
) -> Callable[[_F], _F]:
    """
    Decorator that caches the return value of an **async** function.

    Parameters
    ----------
    ttl
        Seconds before a cached entry expires (default: 120 s).
    maxsize
        Max entries before LRU eviction kicks in.
    cache
        Supply a custom :class:`_TTLCache` instance to namespace the cache.
        Defaults to the module-level ``_default_cache``.

    Example
    -------
    ::

        @cached(ttl=60)
        async def get_category_tree(db: AsyncSession) -> list[dict]:
            ...

    To invalidate manually::

        await cached.invalidate(get_category_tree, db)
    """
    _cache = cache or _TTLCache(maxsize=maxsize, ttl=ttl)

    def decorator(func: _F) -> _F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip DB session objects from cache key (not serialisable)
            safe_args = tuple(
                a for a in args
                if not hasattr(a, "execute")  # exclude AsyncSession etc.
            )
            key = _cache._make_key(func.__qualname__, safe_args, kwargs)
            hit, value = await _cache.get(key)
            if hit:
                logger.debug("Cache HIT  %s", func.__qualname__)
                return value
            logger.debug("Cache MISS %s", func.__qualname__)
            result = await func(*args, **kwargs)
            await _cache.set(key, result)
            return result

        async def invalidate(*args, **kwargs):
            safe_args = tuple(a for a in args if not hasattr(a, "execute"))
            key = _cache._make_key(func.__qualname__, safe_args, kwargs)
            await _cache.delete(key)

        async def clear_all():
            await _cache.clear()

        wrapper.invalidate = invalidate  # type: ignore[attr-defined]
        wrapper.clear_all = clear_all    # type: ignore[attr-defined]
        wrapper._cache = _cache          # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
