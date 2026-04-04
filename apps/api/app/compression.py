"""
Compression middleware and utilities
=====================================
Adds transparent HTTP response compression to the FastAPI application.

Strategy
--------
* **Brotli** (``br``) — best compression ratio; used when the client signals
  ``Accept-Encoding: br``.  Requires the ``brotli`` package.
* **GZip** — universal fallback; FastAPI ships with Starlette's built-in
  ``GZipMiddleware``.

Only responses larger than ``MIN_SIZE`` bytes are compressed; small responses
(< 512 B) are sent as-is to avoid CPU overhead for negligible savings.

Only content types that benefit from compression are targeted
(``application/json``, ``text/*``).  Binary assets (images, PDFs) are skipped.

Usage
-----
Call ``add_compression_middleware(app)`` from ``main.py`` **before** any other
middleware so compression wraps the outermost layer.

DB-side compression helpers
-----------------------------
``compress_json_field`` / ``decompress_json_field`` wrap Python-level gzip
compression for large JSON blobs stored in the DB (e.g. ``source_map``).
Not applied automatically — use explicitly for fields that grow large.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
from typing import Callable

from starlette.datastructures import Headers
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MIN_SIZE = 512          # bytes — don't compress responses smaller than this
GZIP_LEVEL = 6          # 1 (fastest) – 9 (best compression); 6 is the sweet spot
BROTLI_QUALITY = 4      # 0 – 11; 4 balances speed vs ratio for API responses

_COMPRESSIBLE_TYPES = frozenset([
    "application/json",
    "application/javascript",
    "application/xml",
    "application/x-ndjson",
    "text/html",
    "text/plain",
    "text/css",
    "text/xml",
    "text/csv",
])


def _is_compressible(content_type: str) -> bool:
    """Return True if the content-type is worth compressing."""
    mime = content_type.split(";")[0].strip().lower()
    return mime in _COMPRESSIBLE_TYPES


# ---------------------------------------------------------------------------
# Brotli middleware
# ---------------------------------------------------------------------------

class BrotliMiddleware:
    """
    ASGI middleware that compresses responses with Brotli when the client
    advertises ``Accept-Encoding: br``.

    Falls back transparently if the ``brotli`` package is not installed.
    """

    def __init__(self, app: ASGIApp, quality: int = BROTLI_QUALITY, min_size: int = MIN_SIZE) -> None:
        self.app = app
        self.quality = quality
        self.min_size = min_size
        try:
            import brotli as _brotli  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
            logger.warning("brotli package not installed — BrotliMiddleware disabled")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._available or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = Headers(scope=scope)
        accept_encoding = request_headers.get("accept-encoding", "")
        if "br" not in accept_encoding:
            await self.app(scope, receive, send)
            return

        responder = _BrotliResponder(self.app, self.quality, self.min_size)
        await responder(scope, receive, send)


class _BrotliResponder:
    def __init__(self, app: ASGIApp, quality: int, min_size: int) -> None:
        self.app = app
        self.quality = quality
        self.min_size = min_size
        self._initial_message: Message = {}
        self._body_parts: list[bytes] = []
        self._started = False
        self._compressible = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, self._intercept(send))

    def _intercept(self, send: Send) -> Send:
        async def sender(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                ct = headers.get(b"content-type", b"").decode()
                self._compressible = _is_compressible(ct)
                self._initial_message = message

            elif message["type"] == "http.response.body":
                body: bytes = message.get("body", b"")
                more_body: bool = message.get("more_body", False)
                self._body_parts.append(body)

                if not more_body:
                    full_body = b"".join(self._body_parts)
                    if self._compressible and len(full_body) >= self.min_size:
                        compressed = self._compress(full_body)
                        # Rewrite headers
                        headers = dict(self._initial_message.get("headers", []))
                        headers[b"content-encoding"] = b"br"
                        headers[b"content-length"] = str(len(compressed)).encode()
                        headers.pop(b"content-range", None)
                        self._initial_message["headers"] = list(headers.items())
                        await send(self._initial_message)
                        await send({
                            "type": "http.response.body",
                            "body": compressed,
                            "more_body": False,
                        })
                        logger.debug(
                            "Brotli: %d → %d bytes (%.1f%%)",
                            len(full_body), len(compressed),
                            100 * len(compressed) / len(full_body) if full_body else 0,
                        )
                        return
                    # Not compressing — send original
                    await send(self._initial_message)
                    await send({
                        "type": "http.response.body",
                        "body": full_body,
                        "more_body": False,
                    })
            else:
                await send(message)

        return sender

    def _compress(self, data: bytes) -> bytes:
        import brotli
        return brotli.compress(data, quality=self.quality)


# ---------------------------------------------------------------------------
# Public setup function
# ---------------------------------------------------------------------------

def add_compression_middleware(app) -> None:
    """
    Attach Brotli + GZip compression middleware to a FastAPI app.

    Call this **once** from ``main.py``.  Brotli is tried first (better ratio);
    GZip handles clients that don't support Brotli.

    Both layers use ``MIN_SIZE=512`` so tiny JSON responses are not touched.
    """
    # GZip as the inner layer (handles Accept-Encoding: gzip)
    app.add_middleware(GZipMiddleware, minimum_size=MIN_SIZE, compresslevel=GZIP_LEVEL)
    # Brotli as the outer layer (checked first; skips if client doesn't advertise br)
    app.add_middleware(BrotliMiddleware, quality=BROTLI_QUALITY, min_size=MIN_SIZE)
    logger.info("Compression middleware registered (Brotli + GZip, min_size=%d B)", MIN_SIZE)


# ---------------------------------------------------------------------------
# DB-level JSON field compression helpers
# ---------------------------------------------------------------------------

def compress_json_field(data: dict | list | None) -> bytes | None:
    """
    Gzip-compress a Python dict/list to bytes for storage in a LargeBinary
    column.  Returns None if ``data`` is None.

    Use this for large JSON blobs (e.g. raw merchant API responses) that you
    want to store without inflating row size.
    """
    if data is None:
        return None
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=GZIP_LEVEL) as gz:
        gz.write(raw)
    return buf.getvalue()


def decompress_json_field(blob: bytes | None) -> dict | list | None:
    """Decompress bytes produced by :func:`compress_json_field`."""
    if blob is None:
        return None
    buf = io.BytesIO(blob)
    with gzip.GzipFile(fileobj=buf, mode="rb") as gz:
        raw = gz.read()
    return json.loads(raw.decode())
