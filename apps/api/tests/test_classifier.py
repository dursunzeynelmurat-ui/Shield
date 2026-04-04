"""Unit tests for the CategoryClassifier (no DB required for parsing/text helpers)."""
import pytest
from app.catalog.classifier import (
    _slugify,
    _jaccard,
    _tokenize,
    parse_merchant_path,
    extract_trendyol_category,
    extract_hepsiburada_category,
    extract_category_string,
)


# ---------------------------------------------------------------------------
# Slug / normalisation
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic_turkish(self):
        assert _slugify("Cep Telefonu") == "cep-telefonu"

    def test_ampersand_connector(self):
        assert _slugify("Bilgisayar & Tablet") == "bilgisayar-tablet"

    def test_plus_connector(self):
        assert _slugify("Anne + Bebek") == "anne-bebek"

    def test_uppercase_i_dotless(self):
        # Turkish "İ" (dotted capital I) → lowercase "i"
        assert _slugify("İstanbul") == "istanbul"
        # Turkish "I" (dotless capital I) → "ı" → "i" via map
        assert _slugify("Işık") == "isik"

    def test_special_chars_stripped(self):
        assert _slugify("Spor & Outdoor!") == "spor-outdoor"

    def test_multiple_spaces(self):
        assert _slugify("Ev   Yaşam") == "ev-yasam"

    def test_leading_trailing_hyphen(self):
        assert not _slugify("").startswith("-")


# ---------------------------------------------------------------------------
# Jaccard similarity
# ---------------------------------------------------------------------------

class TestJaccard:
    def test_identical(self):
        tokens = _tokenize("Laptop")
        assert _jaccard(tokens, tokens) == 1.0

    def test_disjoint(self):
        assert _jaccard(_tokenize("Laptop"), _tokenize("Ayakkabı")) < 0.1

    def test_partial_overlap(self):
        score = _jaccard(_tokenize("Cep Telefonu"), _tokenize("Akıllı Telefon"))
        assert 0.2 < score < 0.8

    def test_empty_set(self):
        assert _jaccard(set(), {"laptop"}) == 0.0


# ---------------------------------------------------------------------------
# Path parser
# ---------------------------------------------------------------------------

class TestParseMerchantPath:
    def test_trendyol_gt_delimiter(self):
        p = parse_merchant_path("Elektronik > Bilgisayar & Tablet > Laptop", "trendyol")
        assert p is not None
        assert p.segments == ["Elektronik", "Bilgisayar & Tablet", "Laptop"]
        assert p.slugs == ["elektronik", "bilgisayar-tablet", "laptop"]
        assert p.paths == [
            "elektronik",
            "elektronik/bilgisayar-tablet",
            "elektronik/bilgisayar-tablet/laptop",
        ]

    def test_hepsiburada_slash_delimiter(self):
        p = parse_merchant_path("Elektronik/Bilgisayar/Laptop", "hepsiburada")
        assert p is not None
        assert p.segments == ["Elektronik", "Bilgisayar", "Laptop"]
        assert p.paths[-1] == "elektronik/bilgisayar/laptop"

    def test_single_segment(self):
        p = parse_merchant_path("Laptop", "trendyol")
        assert p is not None
        assert len(p.segments) == 1
        assert p.slugs[0] == "laptop"

    def test_numeric_path_returns_none(self):
        p = parse_merchant_path("3/38/1009", "trendyol")
        assert p is None

    def test_empty_returns_none(self):
        assert parse_merchant_path("", "trendyol") is None
        assert parse_merchant_path("   ", "trendyol") is None

    def test_depth_cap(self):
        long_path = " > ".join([f"Cat{i}" for i in range(20)])
        p = parse_merchant_path(long_path, "trendyol")
        assert p is not None
        assert len(p.segments) <= 5  # MAX_DEPTH

    def test_turkish_chars_in_slugs(self):
        p = parse_merchant_path("Giyim & Aksesuar > Kadın Giyim > Elbise", "trendyol")
        assert p is not None
        assert p.slugs[1] == "kadin-giyim"


# ---------------------------------------------------------------------------
# Merchant extractors
# ---------------------------------------------------------------------------

class TestTrendyolExtractor:
    def test_hierarchy_preferred(self):
        product = {
            "categoryHierarchy": "Elektronik > Laptop",
            "categoryName": "Laptop",
        }
        assert extract_trendyol_category(product) == "Elektronik > Laptop"

    def test_nested_category_object(self):
        product = {
            "category": {
                "name": "Laptop",
                "parentCategory": {
                    "name": "Bilgisayar",
                    "parentCategory": {"name": "Elektronik"},
                },
            }
        }
        result = extract_trendyol_category(product)
        assert result == "Elektronik > Bilgisayar > Laptop"

    def test_flat_fallback(self):
        product = {"categoryName": "Laptop"}
        assert extract_trendyol_category(product) == "Laptop"

    def test_missing_returns_none(self):
        assert extract_trendyol_category({}) is None


class TestHepsiburadaExtractor:
    def test_category_path(self):
        product = {"categoryPath": "Elektronik/Laptop"}
        assert extract_hepsiburada_category(product) == "Elektronik/Laptop"

    def test_breadcrumb(self):
        product = {
            "breadCrumb": [
                {"name": "Elektronik"},
                {"name": "Bilgisayar"},
                {"name": "Laptop"},
            ]
        }
        assert extract_hepsiburada_category(product) == "Elektronik > Bilgisayar > Laptop"

    def test_flat_fallback(self):
        product = {"categoryName": "Ayakkabı"}
        assert extract_hepsiburada_category(product) == "Ayakkabı"

    def test_missing_returns_none(self):
        assert extract_hepsiburada_category({}) is None


class TestGenericExtractor:
    def test_dispatch_trendyol(self):
        product = {"categoryName": "Laptop"}
        result = extract_category_string(product, "trendyol")
        assert result == "Laptop"

    def test_dispatch_hepsiburada(self):
        product = {"categoryPath": "Elektronik/Laptop"}
        result = extract_category_string(product, "hepsiburada")
        assert result == "Elektronik/Laptop"

    def test_generic_fallback_keys(self):
        product = {"category_name": "Laptop"}
        result = extract_category_string(product, "amazon")
        assert result == "Laptop"
