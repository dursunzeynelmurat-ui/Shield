"""
CategoryClassifier
==================
Automatically resolves (and creates) categories from raw merchant category
strings returned by Trendyol, Hepsiburada, and other Turkish e-commerce APIs.

Algorithm overview
------------------
1. **Parse** — split raw merchant string into a path of segments
   (handles ">", "/", " > ", " / " delimiters; normalises Turkish chars).
2. **Source-map cache** — look up the raw string in ``categories.source_map``
   JSON column for this merchant.  Exact cache hit → return immediately.
3. **Slug match** — build the expected slug for each depth level and query
   by ``categories.path``.  On hit, update source_map and return.
4. **Fuzzy match** — token-overlap Jaccard similarity against existing
   category names at the same depth (no external library needed).
   If score ≥ FUZZY_THRESHOLD, treat as match.
5. **Auto-create** — nothing matched: insert new Category row(s) walking
   the path top-down; parent must exist before child is created.
6. **Assign** — the leaf category is returned as the canonical one.

The entire pipeline is async and uses a single DB session passed in from the
caller (catalog ingest task / product upsert endpoint).

Turkish character normalisation
--------------------------------
No third-party library required.  A hand-coded table covers the characters
that appear in Trendyol / Hepsiburada category strings.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FUZZY_THRESHOLD = 0.50   # Jaccard token-overlap threshold for fuzzy matching
MAX_DEPTH = 5             # Safety cap against pathological merchant trees

# Turkish → ASCII transliteration table used for slug/normalisation
_TR_MAP: dict[int, str] = str.maketrans(
    # source (22 chars): ç ğ ı İ ö ş ü Ç Ğ Ö Ş Ü  â ê î ô û  Â Ê Î Ô Û
    "çğıİöşüÇĞÖŞÜâêîôûÂÊÎÔÛ",
    # target (22 chars): c g i i o s u C G O S U  a e i o u  A E I O U
    "cgiiosuCGOSUaeiouAEIOU",
)
# Supplement: some Trendyol category strings use & or + as connectors
_CONNECTOR_RE = re.compile(r"\s*[&+]\s*")
_WHITESPACE_RE = re.compile(r"[\s_]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9-]")

# Delimiters Trendyol / Hepsiburada use between hierarchy levels
_PATH_DELIMITERS = re.compile(r"\s*[>/|\\]\s*|>\s*")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _tr_lower(text: str) -> str:
    """Lowercase with correct Turkish İ→i mapping before ASCII conversion."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def _slugify(text: str) -> str:
    """Convert a category label to a URL-safe ASCII slug."""
    s = _tr_lower(text)
    s = s.translate(_TR_MAP)
    s = _CONNECTOR_RE.sub("-", s)
    s = _WHITESPACE_RE.sub("-", s)
    s = _NON_ALNUM_RE.sub("", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def _tokenize(text: str) -> set[str]:
    """Return a set of tokens for Jaccard similarity."""
    s = _tr_lower(text).translate(_TR_MAP)
    return set(re.findall(r"[a-z0-9]+", s))


def _jaccard(a: set[str], b: set[str]) -> float:
    """
    Soft Jaccard with 5-char prefix matching to handle Turkish morphology.

    Turkish agglutination means the same stem appears with many suffixes:
    ``telefon`` ↔ ``telefonu``, ``telefonda``, ``telefonla``.
    We count two tokens as matching when the first 5 characters are shared,
    which is long enough to avoid false positives for short common words.
    """
    if not a or not b:
        return 0.0
    # Expand each set with 5-char prefixes for stem matching
    def _prefixed(tokens: set[str]) -> set[str]:
        out: set[str] = set()
        for t in tokens:
            out.add(t)
            if len(t) >= 5:
                out.add(t[:5])  # stem proxy
        return out

    pa, pb = _prefixed(a), _prefixed(b)
    inter = len(pa & pb)
    union = len(pa | pb)
    return inter / union if union else 0.0


# ---------------------------------------------------------------------------
# Path parser
# ---------------------------------------------------------------------------

@dataclass
class MerchantPath:
    """Parsed and normalised category path from a merchant."""
    raw: str
    merchant: str
    segments: list[str]   # e.g. ["Elektronik", "Bilgisayar & Tablet", "Laptop"]
    slugs: list[str]      # slugified segments
    paths: list[str]      # cumulative materialized paths per depth


def parse_merchant_path(raw: str, merchant: str) -> MerchantPath | None:
    """
    Parse a raw merchant category string into a structured path.

    Supports formats:
    - ``"Elektronik > Bilgisayar & Tablet > Laptop"``  (Trendyol)
    - ``"Elektronik/Bilgisayar-Tablet/Laptop"``        (Hepsiburada)
    - ``"3/38/1009"``                                   (numeric ID path — unusable)
    - ``["Elektronik", "Laptop"]``                      (already a list)
    """
    if not raw or not raw.strip():
        return None

    # If it looks like a pure numeric ID path, skip — no meaningful labels
    if re.fullmatch(r"[\d/]+", raw.strip()):
        logger.debug("Skipping numeric-only category path: %s", raw)
        return None

    # Split into segments
    parts = _PATH_DELIMITERS.split(raw.strip())
    parts = [p.strip() for p in parts if p.strip()]

    if not parts:
        return None

    # Cap depth
    parts = parts[:MAX_DEPTH]

    slugs: list[str] = []
    paths: list[str] = []
    for i, part in enumerate(parts):
        slug = _slugify(part)
        if not slug:
            continue
        slugs.append(slug)
        paths.append("/".join(slugs))

    if not slugs:
        return None

    return MerchantPath(
        raw=raw,
        merchant=merchant,
        segments=parts[:len(slugs)],
        slugs=slugs,
        paths=paths,
    )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _get_by_path(db: AsyncSession, path: str) -> Category | None:
    result = await db.execute(select(Category).where(Category.path == path))
    return result.scalar_one_or_none()


async def _get_children_at_depth(db: AsyncSession, depth: int) -> Sequence[Category]:
    result = await db.execute(select(Category).where(Category.depth == depth))
    return result.scalars().all()


async def _update_source_map(db: AsyncSession, cat: Category, merchant: str, raw: str) -> None:
    """Add merchant→raw to source_map without overwriting other keys."""
    current: dict = cat.source_map or {}
    if current.get(merchant) == raw:
        return
    current[merchant] = raw
    await db.execute(
        update(Category).where(Category.id == cat.id).values(source_map=current)
    )
    cat.source_map = current


async def _find_by_source_map(
    db: AsyncSession, merchant: str, raw: str
) -> Category | None:
    """Fast cache lookup: find category whose source_map[merchant] == raw."""
    # JSON contains query — works on PostgreSQL; falls back gracefully on SQLite
    try:
        from sqlalchemy import cast, String as SAString
        result = await db.execute(
            select(Category).where(
                Category.source_map[merchant].as_string() == raw
            )
        )
        return result.scalar_one_or_none()
    except Exception:
        return None


async def _fuzzy_match(
    db: AsyncSession, label: str, depth: int, parent_id: int | None
) -> Category | None:
    """
    Find the best fuzzy-matching category at ``depth``.
    Only considers children of ``parent_id`` (or root if None).
    """
    stmt = select(Category).where(Category.depth == depth)
    if parent_id is not None:
        stmt = stmt.where(Category.parent_id == parent_id)
    else:
        stmt = stmt.where(Category.parent_id == None)  # noqa: E711

    result = await db.execute(stmt)
    candidates = result.scalars().all()

    query_tokens = _tokenize(label)
    best: Category | None = None
    best_score = 0.0

    for cat in candidates:
        score = _jaccard(query_tokens, _tokenize(cat.name))
        if score > best_score:
            best_score = score
            best = cat

    if best and best_score >= FUZZY_THRESHOLD:
        logger.debug("Fuzzy match: '%s' → '%s' (score=%.2f)", label, best.name, best_score)
        return best
    return None


async def _create_category(
    db: AsyncSession,
    name: str,
    slug: str,
    path: str,
    depth: int,
    parent_id: int | None,
    merchant: str,
    raw: str,
) -> Category:
    cat = Category(
        name=name,
        slug=slug,
        path=path,
        depth=depth,
        parent_id=parent_id,
        source_map={merchant: raw},
    )
    db.add(cat)
    await db.flush()  # get generated id without committing
    logger.info("Created new category: path='%s' (from merchant='%s')", path, merchant)
    return cat


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def classify(
    db: AsyncSession,
    raw_category: str,
    merchant: str,
) -> Category | None:
    """
    Resolve ``raw_category`` (e.g. ``"Elektronik > Bilgisayar & Tablet > Laptop"``)
    from merchant ``merchant`` to a canonical :class:`Category` row.

    Creates new rows if no match is found.  Returns the **leaf** category
    (deepest match).  Returns ``None`` only if the raw string is unusable
    (empty, numeric-only).

    The caller is responsible for committing the session.
    """
    parsed = parse_merchant_path(raw_category, merchant)
    if parsed is None:
        return None

    # 1. Source-map cache hit (entire raw path → leaf category)
    cached = await _find_by_source_map(db, merchant, raw_category)
    if cached:
        logger.debug("Cache hit for merchant='%s' raw='%s'", merchant, raw_category)
        return cached

    # 2. Walk path level by level, resolving or creating each node
    parent_id: int | None = None
    leaf: Category | None = None

    for depth, (segment, slug, path) in enumerate(
        zip(parsed.segments, parsed.slugs, parsed.paths)
    ):
        # 2a. Exact path match
        cat = await _get_by_path(db, path)
        if cat:
            await _update_source_map(db, cat, merchant, raw_category)
            parent_id = cat.id
            leaf = cat
            continue

        # 2b. Fuzzy match among siblings at this depth
        cat = await _fuzzy_match(db, segment, depth, parent_id)
        if cat:
            await _update_source_map(db, cat, merchant, raw_category)
            parent_id = cat.id
            leaf = cat
            continue

        # 2c. No match — auto-create
        cat = await _create_category(
            db, name=segment, slug=slug, path=path,
            depth=depth, parent_id=parent_id,
            merchant=merchant, raw=raw_category,
        )
        parent_id = cat.id
        leaf = cat

    return leaf


async def classify_batch(
    db: AsyncSession,
    items: list[dict],
    merchant: str,
    category_key: str = "categoryName",
) -> dict[str, Category | None]:
    """
    Classify a batch of merchant API result dicts.

    Parameters
    ----------
    items
        List of raw product dicts as returned by the merchant API.
    merchant
        Merchant name (``"trendyol"`` / ``"hepsiburada"`` / …).
    category_key
        Key in each dict that contains the category string.

    Returns
    -------
    Mapping of raw category string → resolved :class:`Category` (or None).
    """
    raw_values: set[str] = {
        str(item[category_key])
        for item in items
        if item.get(category_key)
    }
    results: dict[str, Category | None] = {}
    for raw in raw_values:
        results[raw] = await classify(db, raw, merchant)
    return results


# ---------------------------------------------------------------------------
# Merchant-specific path extractors
# ---------------------------------------------------------------------------

def extract_trendyol_category(product: dict) -> str | None:
    """
    Extract a human-readable category path from a Trendyol API product dict.

    Trendyol's public API returns categories in several formats:
      - ``categoryName``: ``"Laptop"`` (leaf only)
      - ``categoryHierarchy``: ``"Elektronik > Bilgisayar & Tablet > Laptop"``
      - ``category.name``, ``category.parentCategory.name``, … (nested)
    """
    # Prefer full hierarchy string
    if h := product.get("categoryHierarchy"):
        return str(h)

    # Build from nested category objects
    hier_parts: list[str] = []
    cat = product.get("category") or {}
    while cat:
        name = cat.get("name")
        if name:
            hier_parts.insert(0, str(name))
        cat = cat.get("parentCategory") or {}
    if hier_parts:
        return " > ".join(hier_parts)

    # Fallback to flat leaf name
    if leaf := product.get("categoryName"):
        return str(leaf)

    return None


def extract_hepsiburada_category(product: dict) -> str | None:
    """
    Extract category path from a Hepsiburada API product dict.

    Hepsiburada uses:
      - ``categoryPath``: ``"Elektronik/Bilgisayar/Laptop"``
      - ``categoryName``: leaf name
      - ``breadCrumb``: list of ``{name, url}`` dicts
    """
    if cp := product.get("categoryPath"):
        return str(cp)

    breadcrumb = product.get("breadCrumb") or []
    if isinstance(breadcrumb, list) and breadcrumb:
        names = [b.get("name") for b in breadcrumb if b.get("name")]
        if names:
            return " > ".join(names)

    if leaf := product.get("categoryName"):
        return str(leaf)

    return None


_MERCHANT_EXTRACTORS = {
    "trendyol": extract_trendyol_category,
    "hepsiburada": extract_hepsiburada_category,
}


def extract_category_string(product: dict, merchant: str) -> str | None:
    """Dispatch to the correct extractor based on merchant name."""
    extractor = _MERCHANT_EXTRACTORS.get(merchant.lower())
    if extractor:
        return extractor(product)
    # Generic fallback: try common keys
    for key in ("categoryHierarchy", "categoryPath", "categoryName", "category_name", "cat"):
        if val := product.get(key):
            return str(val)
    return None


# ---------------------------------------------------------------------------
# High-level product ingest helper
# ---------------------------------------------------------------------------

async def assign_category_to_product(
    db: AsyncSession,
    product,          # app.models.Product instance
    raw_category: str | None,
    merchant: str,
) -> None:
    """
    Classify ``raw_category`` and set ``product.category_id`` + ``product.category``
    (the denormalised label).  Flushes but does NOT commit.
    """
    if not raw_category:
        return

    cat = await classify(db, raw_category, merchant)
    if cat is None:
        return

    product.category_id = cat.id
    # Keep the denormalised string as a readable label for search
    if not product.category:
        product.category = cat.name
