"""Unit tests for compression helpers and in-process cache (no DB / HTTP required)."""
import asyncio
import gzip
import pytest

from app.compression import (
    _is_compressible,
    _slugify_not_here,  # will fail gracefully — we inline
    compress_json_field,
    decompress_json_field,
)
from app.cache import _TTLCache, cached


# ---------------------------------------------------------------------------
# compression.py helpers
# ---------------------------------------------------------------------------

class TestIsCompressible:
    def test_json(self):
        from app.compression import _is_compressible
        assert _is_compressible("application/json")

    def test_json_with_charset(self):
        from app.compression import _is_compressible
        assert _is_compressible("application/json; charset=utf-8")

    def test_text_plain(self):
        from app.compression import _is_compressible
        assert _is_compressible("text/plain")

    def test_image_not_compressible(self):
        from app.compression import _is_compressible
        assert not _is_compressible("image/jpeg")

    def test_binary_not_compressible(self):
        from app.compression import _is_compressible
        assert not _is_compressible("application/octet-stream")


class TestJsonFieldCompression:
    def test_round_trip_dict(self):
        data = {"key": "value", "nested": {"a": 1, "b": [1, 2, 3]}}
        compressed = compress_json_field(data)
        assert isinstance(compressed, bytes)
        assert decompress_json_field(compressed) == data

    def test_round_trip_list(self):
        data = [{"id": i, "name": f"item-{i}"} for i in range(50)]
        assert decompress_json_field(compress_json_field(data)) == data

    def test_compression_ratio(self):
        """Repetitive JSON should compress to less than 50% of original."""
        import json
        data = {"items": [{"id": i, "category": "elektronik", "merchant": "trendyol"} for i in range(200)]}
        raw = json.dumps(data).encode()
        compressed = compress_json_field(data)
        assert len(compressed) < len(raw) * 0.5

    def test_none_round_trip(self):
        assert compress_json_field(None) is None
        assert decompress_json_field(None) is None

    def test_turkish_chars_preserved(self):
        data = {"category": "Giyim & Aksesuar", "name": "Çocuk Ayakkabısı"}
        assert decompress_json_field(compress_json_field(data)) == data


# ---------------------------------------------------------------------------
# cache.py — _TTLCache
# ---------------------------------------------------------------------------

class TestTTLCache:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_set_and_get(self):
        cache = _TTLCache(maxsize=10, ttl=60)
        async def _go():
            await cache.set("k1", {"val": 42})
            hit, val = await cache.get("k1")
            assert hit is True
            assert val == {"val": 42}
        self._run(_go())

    def test_miss(self):
        cache = _TTLCache(maxsize=10, ttl=60)
        async def _go():
            hit, val = await cache.get("nonexistent")
            assert hit is False
            assert val is None
        self._run(_go())

    def test_expiry(self):
        import time
        cache = _TTLCache(maxsize=10, ttl=0.05)  # 50 ms TTL
        async def _go():
            await cache.set("k", "value")
            hit, _ = await cache.get("k")
            assert hit is True
            await asyncio.sleep(0.1)
            hit, _ = await cache.get("k")
            assert hit is False
        self._run(_go())

    def test_lru_eviction(self):
        cache = _TTLCache(maxsize=3, ttl=60)
        async def _go():
            await cache.set("a", 1)
            await cache.set("b", 2)
            await cache.set("c", 3)
            await cache.set("d", 4)  # evicts "a" (LRU)
            hit_a, _ = await cache.get("a")
            hit_d, _ = await cache.get("d")
            assert hit_a is False
            assert hit_d is True
        self._run(_go())

    def test_delete(self):
        cache = _TTLCache(maxsize=10, ttl=60)
        async def _go():
            await cache.set("k", "v")
            await cache.delete("k")
            hit, _ = await cache.get("k")
            assert hit is False
        self._run(_go())

    def test_clear(self):
        cache = _TTLCache(maxsize=10, ttl=60)
        async def _go():
            await cache.set("x", 1)
            await cache.set("y", 2)
            await cache.clear()
            hit_x, _ = await cache.get("x")
            assert hit_x is False
        self._run(_go())

    def test_evict_expired(self):
        import time
        cache = _TTLCache(maxsize=10, ttl=0.05)
        async def _go():
            await cache.set("a", 1)
            await cache.set("b", 2)
            await asyncio.sleep(0.1)
            n = await cache.evict_expired()
            assert n == 2
        self._run(_go())


# ---------------------------------------------------------------------------
# cache.py — @cached decorator
# ---------------------------------------------------------------------------

class TestCachedDecorator:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_caches_result(self):
        call_count = {"n": 0}

        @cached(ttl=60)
        async def expensive(x: int) -> int:
            call_count["n"] += 1
            return x * 2

        async def _go():
            r1 = await expensive(5)
            r2 = await expensive(5)
            assert r1 == 10
            assert r2 == 10
            assert call_count["n"] == 1  # only called once

        self._run(_go())

    def test_different_args_not_shared(self):
        @cached(ttl=60)
        async def double(x: int) -> int:
            return x * 2

        async def _go():
            assert await double(3) == 6
            assert await double(7) == 14

        self._run(_go())

    def test_invalidate(self):
        call_count = {"n": 0}

        @cached(ttl=60)
        async def compute(x: int) -> int:
            call_count["n"] += 1
            return x

        async def _go():
            await compute(1)
            await compute.invalidate(1)
            await compute(1)
            assert call_count["n"] == 2

        self._run(_go())
