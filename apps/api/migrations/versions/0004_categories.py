"""0004 — category tree + product.category_id FK"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # categories table (self-referential tree)
    # ------------------------------------------------------------------
    op.create_table(
        "categories",
        sa.Column("id",         sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name",       sa.String(200), nullable=False),
        sa.Column("slug",       sa.String(200), nullable=False),
        sa.Column("path",       sa.String(1000), nullable=False),
        sa.Column("depth",      sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_id",  sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_map", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"])
    op.create_index("ix_categories_path", "categories", ["path"], unique=True)
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    # ------------------------------------------------------------------
    # products.category_id FK column
    # ------------------------------------------------------------------
    op.add_column(
        "products",
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])

    # ------------------------------------------------------------------
    # Seed canonical Turkish e-commerce taxonomy
    # ------------------------------------------------------------------
    categories = op.get_bind()

    def ins(id_, name, slug, path, depth, parent_id):
        categories.execute(
            sa.text(
                "INSERT INTO categories (id, name, slug, path, depth, parent_id, source_map) "
                "VALUES (:id, :name, :slug, :path, :depth, :parent_id, :sm)"
            ),
            {"id": id_, "name": name, "slug": slug, "path": path,
             "depth": depth, "parent_id": parent_id, "sm": "{}"},
        )

    # Root categories (depth 0)
    roots = [
        (1,  "Elektronik",               "elektronik"),
        (2,  "Giyim & Aksesuar",         "giyim-aksesuar"),
        (3,  "Ev & Yaşam",               "ev-yasam"),
        (4,  "Spor & Outdoor",           "spor-outdoor"),
        (5,  "Anne & Bebek",             "anne-bebek"),
        (6,  "Kozmetik & Kişisel Bakım", "kozmetik-kisisel-bakim"),
        (7,  "Kitap, Müzik & Film",      "kitap-muzik-film"),
        (8,  "Oyuncak & Hobi",           "oyuncak-hobi"),
        (9,  "Otomotiv",                 "otomotiv"),
        (10, "Süpermarket & Gıda",       "supermarket-gida"),
        (11, "Mobilya & Dekorasyon",     "mobilya-dekorasyon"),
        (12, "Bahçe & Yapı Market",      "bahce-yapi-market"),
        (13, "Pet Shop",                 "pet-shop"),
        (14, "Ofis & Kırtasiye",         "ofis-kirtasiye"),
        (15, "Diğer",                    "diger"),
    ]
    for id_, name, slug in roots:
        ins(id_, name, slug, slug, 0, None)

    # Sub-categories (depth 1) — Elektronik (1)
    elec_subs = [
        (101, "Cep Telefonu",             "cep-telefonu",           "elektronik/cep-telefonu",           1),
        (102, "Bilgisayar & Tablet",      "bilgisayar-tablet",      "elektronik/bilgisayar-tablet",      1),
        (103, "TV & Ses Sistemleri",      "tv-ses-sistemleri",      "elektronik/tv-ses-sistemleri",      1),
        (104, "Beyaz Eşya",               "beyaz-esya",             "elektronik/beyaz-esya",             1),
        (105, "Küçük Ev Aletleri",        "kucuk-ev-aletleri",      "elektronik/kucuk-ev-aletleri",      1),
        (106, "Fotoğraf & Kamera",        "fotograf-kamera",        "elektronik/fotograf-kamera",        1),
        (107, "Oyun & Konsol",            "oyun-konsol",            "elektronik/oyun-konsol",            1),
        (108, "Akıllı Giyilebilir",       "akilli-giyilebilir",     "elektronik/akilli-giyilebilir",     1),
        (109, "Elektrikli Araç & Scooter","elektrikli-arac-scooter","elektronik/elektrikli-arac-scooter",1),
        (110, "Telefon Aksesuar",         "telefon-aksesuar",       "elektronik/telefon-aksesuar",       1),
    ]
    for id_, name, slug, path, depth in elec_subs:
        ins(id_, name, slug, path, depth, 1)

    # Sub-sub (depth 2) — Bilgisayar & Tablet (102)
    pc_subs = [
        (1021, "Laptop",           "laptop",           "elektronik/bilgisayar-tablet/laptop",           2),
        (1022, "Masaüstü Bilgisayar","masaustu-bilgisayar","elektronik/bilgisayar-tablet/masaustu-bilgisayar",2),
        (1023, "Tablet",           "tablet",           "elektronik/bilgisayar-tablet/tablet",           2),
        (1024, "Monitör",          "monitor",          "elektronik/bilgisayar-tablet/monitor",          2),
        (1025, "Bilgisayar Bileşeni","bilgisayar-bileseni","elektronik/bilgisayar-tablet/bilgisayar-bileseni",2),
    ]
    for id_, name, slug, path, depth in pc_subs:
        ins(id_, name, slug, path, depth, 102)

    # Sub-sub (depth 2) — Cep Telefonu (101)
    phone_subs = [
        (1011, "Akıllı Telefon",   "akilli-telefon",   "elektronik/cep-telefonu/akilli-telefon",   2),
        (1012, "Tuşlu Telefon",    "tuslu-telefon",    "elektronik/cep-telefonu/tuslu-telefon",    2),
    ]
    for id_, name, slug, path, depth in phone_subs:
        ins(id_, name, slug, path, depth, 101)

    # Sub-categories — Giyim (2)
    fashion_subs = [
        (201, "Kadın Giyim",   "kadin-giyim",   "giyim-aksesuar/kadin-giyim",   1),
        (202, "Erkek Giyim",   "erkek-giyim",   "giyim-aksesuar/erkek-giyim",   1),
        (203, "Çocuk Giyim",   "cocuk-giyim",   "giyim-aksesuar/cocuk-giyim",   1),
        (204, "Ayakkabı",      "ayakkabi",      "giyim-aksesuar/ayakkabi",      1),
        (205, "Çanta & Cüzdan","canta-cuzdan",  "giyim-aksesuar/canta-cuzdan",  1),
        (206, "Saat",          "saat",          "giyim-aksesuar/saat",          1),
        (207, "Takı & Mücevher","taki-mucevher","giyim-aksesuar/taki-mucevher", 1),
    ]
    for id_, name, slug, path, depth in fashion_subs:
        ins(id_, name, slug, path, depth, 2)

    # Sub-categories — Ev & Yaşam (3)
    home_subs = [
        (301, "Mobilya",         "mobilya",         "ev-yasam/mobilya",         1),
        (302, "Ev Tekstili",     "ev-tekstili",     "ev-yasam/ev-tekstili",     1),
        (303, "Mutfak & Banyo",  "mutfak-banyo",    "ev-yasam/mutfak-banyo",    1),
        (304, "Aydınlatma",      "aydinlatma",      "ev-yasam/aydinlatma",      1),
        (305, "Dekorasyon",      "dekorasyon",      "ev-yasam/dekorasyon",      1),
        (306, "Temizlik",        "temizlik",        "ev-yasam/temizlik",        1),
    ]
    for id_, name, slug, path, depth in home_subs:
        ins(id_, name, slug, path, depth, 3)

    # Sub-categories — Spor (4)
    sport_subs = [
        (401, "Fitness & Kondisyon", "fitness-kondisyon", "spor-outdoor/fitness-kondisyon", 1),
        (402, "Outdoor & Kamp",      "outdoor-kamp",      "spor-outdoor/outdoor-kamp",      1),
        (403, "Bisiklet",            "bisiklet",          "spor-outdoor/bisiklet",          1),
        (404, "Takım Sporları",      "takim-sporlari",    "spor-outdoor/takim-sporlari",    1),
        (405, "Su Sporları",         "su-sporlari",       "spor-outdoor/su-sporlari",       1),
    ]
    for id_, name, slug, path, depth in sport_subs:
        ins(id_, name, slug, path, depth, 4)


def downgrade() -> None:
    op.drop_index("ix_products_category_id", "products")
    op.drop_column("products", "category_id")
    op.drop_index("ix_categories_parent_id", "categories")
    op.drop_index("ix_categories_path", "categories")
    op.drop_index("ix_categories_slug", "categories")
    op.drop_table("categories")
