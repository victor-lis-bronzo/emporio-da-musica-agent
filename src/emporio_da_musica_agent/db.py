import csv
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

SCHEMA = """
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    email       TEXT,
    city        TEXT
);

CREATE TABLE products (
    product_id     INTEGER PRIMARY KEY,
    price_brl      REAL NOT NULL,
    name           TEXT NOT NULL,
    category_id    INTEGER REFERENCES categories(category_id),
    description    TEXT,
    stock_quantity INTEGER NOT NULL,
    status         TEXT NOT NULL,
    specs          TEXT,  -- JSON stored as text
    created_at     TEXT
);

CREATE TABLE orders (
    order_id           INTEGER PRIMARY KEY,
    customer_id        INTEGER REFERENCES customers(customer_id),
    order_date         TEXT,
    status             TEXT,
    total_brl          REAL,
    payment_method     TEXT,
    tracking_code      TEXT,
    estimated_delivery TEXT,
    notes              TEXT
);

CREATE TABLE order_items (
    order_id   INTEGER REFERENCES orders(order_id),
    quantity   INTEGER NOT NULL,
    product_id INTEGER REFERENCES products(product_id)
);

CREATE TABLE promotions (
    promotion_id     INTEGER PRIMARY KEY,
    product_id       INTEGER REFERENCES products(product_id),
    discount_percent REAL NOT NULL,
    description      TEXT,
    is_active        INTEGER NOT NULL
);
"""

# One table per CSV (the file name is the table name).
TABLES = [
    "categories",
    "customers",
    "products",
    "orders",
    "order_items",
    "promotions",
]


def _read_csv(name: str) -> list[dict]:
    path = DATA_DIR / f"{name}.csv"
    with open(path, encoding="utf-8", newline="") as f:
        # Empty fields become None (NULL in SQLite).
        return [
            {k: (v if v != "" else None) for k, v in row.items()}
            for row in csv.DictReader(f)
        ]


def load_database() -> sqlite3.Connection:
    """Create an in-memory SQLite database and load the 6 CSVs from data/."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row  # access columns by name
    conn.executescript(SCHEMA)

    for table in TABLES:
        rows = _read_csv(table)
        columns = list(rows[0].keys())
        placeholders = ", ".join(f":{c}" for c in columns)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        conn.executemany(sql, rows)

    conn.commit()
    return conn
