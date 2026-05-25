import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cafe.db"

MENU_SEED = [
    ("coffee", "COFFEE", [
        ("cf-den-phin", "CF Đen Fin", 14000),
        ("cf-sua-phin", "CF Sữa Fin", 15000),
        ("cf-den-may", "CF Đen Máy / Espresso", 16000),
        ("cf-sua-may", "CF Sữa Máy", 18000),
        ("cf-den-sai-gon", "CF đen Sài Gòn", 20000),
        ("cf-sua-sai-gon", "CF sữa Sài Gòn", 22000),
        ("cf-cot-dua", "CF cốt dừa", 28000),
        ("cf-muoi", "CF muối", 25000),
        ("bac-siu", "Bạc sỉu", 22000),
        ("bac-siu-muoi", "Bạc sỉu muối", 28000),
        ("cacao-muoi", "Ca cao muối", 28000),
        ("cacao", "Cacao", 25000),
        ("matcha-latte", "Matcha latte", 25000),
    ]),
    ("smoothie-yogurt", "SINH TỐ/SỮA CHUA", [
        ("smoothie-xoai", "Sinh tố xoài", 25000),
        ("smoothie-xoai-chanh-day", "Sinh tố xoài chanh dây", 30000),
        ("smoothie-dau", "Sinh tố dâu", 22000),
        ("smoothie-viet-quat", "Sinh tố việt quất", 22000),
        ("yogurt-da", "Sữa chua đá", 22000),
        ("yogurt-chanh-day", "Sữa chua chanh dây", 27000),
        ("yogurt-dau", "Sữa chua dâu", 27000),
        ("yogurt-xoai", "Sữa chua xoài", 27000),
        ("yogurt-viet-quat", "Sữa chua việt quất", 27000),
    ]),
    ("juice", "NƯỚC ÉP", [
        ("juice-cam", "Nước ép cam", 25000),
        ("juice-ca-rot", "Nước ép cà rốt", 22000),
        ("juice-dua", "Nước ép dứa", 22000),
        ("juice-chanh-day", "Nước chanh dây", 22000),
        ("juice-oi", "Ép ổi", 22000),
        ("juice-coc", "Ép cóc", 22000),
        ("juice-chanh", "Nước chanh", 17000),
    ]),
    ("ice-blended", "ĐÁ XAY", [
        ("ice-chanh-tuyet", "Chanh tuyết", 30000),
        ("ice-socola", "Socola đá xay", 28000),
        ("ice-matcha", "Matcha đá xay", 28000),
    ]),
    ("soda", "SODA", [
        ("soda-viet-quat", "Soda việt quất", 20000),
        ("soda-dau", "Soda dâu", 20000),
        ("soda-chanh-day", "Soda chanh dây", 20000),
        ("soda-dao", "Soda đào", 20000),
    ]),
    ("tea", "TRÀ", [
        ("tra-dao-cam-sa", "Trà đào cam sả", 30000),
        ("tra-dau", "Trà dâu", 20000),
        ("tra-dao", "Trà đào", 20000),
        ("tra-viet-quat", "Trà việt quất", 20000),
        ("tra-chanh", "Trà chanh", 20000),
        ("tra-chanh-tac-xi-muoi", "Trà chanh/tắc xí muội", 22000),
        ("tra-gung", "Trà gừng", 20000),
    ]),
    ("soft-drink", "GIẢI KHÁT", [
        ("bia", "Bia", 18000),
        ("revive", "Revive", 16000),
        ("sting", "Sting vàng/dâu", 15000),
        ("pepsi", "Pepsi", 12000),
        ("nutri", "Nutri", 16000),
        ("nuoc-suoi", "Nước suối", 10000),
        ("coca", "Coca", 16000),
        ("nuoc-khoang", "Khoáng lạt/ngọt", 10000),
    ]),
]

TABLE_COUNT = 40


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS menu_items (
            id TEXT PRIMARY KEY,
            category_id TEXT NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        CREATE TABLE IF NOT EXISTS tables (
            id INTEGER PRIMARY KEY,
            label TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            opened_at TEXT,
            note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL,
            menu_item_id TEXT NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (table_id) REFERENCES tables(id)
        );
        CREATE TABLE IF NOT EXISTS inventory (
            menu_item_id TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (menu_item_id) REFERENCES menu_items(id)
        );
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            settled_at TEXT NOT NULL,
            total_revenue INTEGER NOT NULL,
            line_count INTEGER NOT NULL,
            synced_to_sheets INTEGER NOT NULL DEFAULT 0,
            note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sale_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL,
            table_label TEXT NOT NULL,
            menu_item_id TEXT NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            sold_at TEXT NOT NULL,
            settlement_id INTEGER,
            FOREIGN KEY (settlement_id) REFERENCES settlements(id)
        );
        CREATE TABLE IF NOT EXISTS order_cancellations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cancelled_at TEXT NOT NULL,
            table_id INTEGER NOT NULL,
            table_label TEXT NOT NULL,
            opened_at TEXT,
            table_note TEXT DEFAULT '',
            item_line_count INTEGER NOT NULL DEFAULT 0,
            total_value INTEGER NOT NULL DEFAULT 0,
            synced_to_sheets INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS order_cancellation_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cancellation_id INTEGER NOT NULL,
            menu_item_id TEXT NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            note TEXT DEFAULT '',
            FOREIGN KEY (cancellation_id) REFERENCES order_cancellations(id)
        );
        """
    )

    seed_category_ids = []
    seed_item_ids = []
    for i, (cat_id, cat_name, items) in enumerate(MENU_SEED):
        seed_category_ids.append(cat_id)
        conn.execute(
            """
            INSERT INTO categories (id, name, sort_order) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                sort_order = excluded.sort_order
            """,
            (cat_id, cat_name, i),
        )
        for item_id, name, price in items:
            seed_item_ids.append(item_id)
            conn.execute(
                """
                INSERT INTO menu_items (id, category_id, name, price) VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    category_id = excluded.category_id,
                    name = excluded.name,
                    price = excluded.price
                """,
                (item_id, cat_id, name, price),
            )

    if seed_item_ids:
        placeholders = ",".join("?" for _ in seed_item_ids)
        conn.execute(
            f"DELETE FROM inventory WHERE menu_item_id NOT IN ({placeholders})",
            seed_item_ids,
        )
        conn.execute(
            f"DELETE FROM menu_items WHERE id NOT IN ({placeholders})",
            seed_item_ids,
        )

    if seed_category_ids:
        placeholders = ",".join("?" for _ in seed_category_ids)
        conn.execute(
            f"DELETE FROM categories WHERE id NOT IN ({placeholders})",
            seed_category_ids,
        )

    for i in range(1, TABLE_COUNT + 1):
        exists = conn.execute("SELECT 1 FROM tables WHERE id = ?", (i,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO tables (id, label, status) VALUES (?, ?, 'available')",
                (i, f"Bàn {i}"),
            )

    menu_ids = conn.execute("SELECT id FROM menu_items").fetchall()
    for row in menu_ids:
        exists = conn.execute(
            "SELECT 1 FROM inventory WHERE menu_item_id = ?", (row["id"],)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO inventory (menu_item_id, quantity) VALUES (?, ?)",
                (row["id"], 100),
            )

    conn.commit()
    conn.close()
