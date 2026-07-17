"""
create_sample_db.py  —  Creates sample.db for testing.
Run once:  python create_sample_db.py
"""
import sqlite3, pathlib, random, datetime

DB = pathlib.Path(__file__).parent / "sample.db"

conn = sqlite3.connect(DB)
conn.executescript("""
CREATE TABLE IF NOT EXISTS customers (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    email    TEXT,
    city     TEXT,
    country  TEXT,
    joined   TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    category TEXT,
    price    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    order_date  TEXT,
    status      TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity   INTEGER,
    unit_price REAL
);
""")

customers = [
    (1, "Alice Sharma",   "alice@mail.com",  "Mumbai",    "India",  "2022-03-10"),
    (2, "Bob Chen",       "bob@mail.com",    "Shanghai",  "China",  "2021-11-05"),
    (3, "Carol Nkosi",    "carol@mail.com",  "Cape Town", "SA",     "2023-01-20"),
    (4, "David Müller",   "david@mail.com",  "Berlin",    "Germany","2022-07-14"),
    (5, "Eva Santos",     "eva@mail.com",    "São Paulo", "Brazil", "2023-05-30"),
    (6, "Frank Patel",    "frank@mail.com",  "Pune",      "India",  "2021-09-01"),
    (7, "Grace Kim",      "grace@mail.com",  "Seoul",     "Korea",  "2022-12-18"),
]

products = [
    (1, "Laptop Pro",    "Electronics", 85000),
    (2, "Wireless Mouse","Electronics",  1800),
    (3, "Standing Desk", "Furniture",   22000),
    (4, "Webcam HD",     "Electronics",  4500),
    (5, "Monitor 27\"",  "Electronics", 28000),
    (6, "Keyboard Mech", "Electronics",  7500),
    (7, "Office Chair",  "Furniture",   15000),
]

conn.executemany("INSERT OR IGNORE INTO customers VALUES (?,?,?,?,?,?)", customers)
conn.executemany("INSERT OR IGNORE INTO products  VALUES (?,?,?,?)",     products)

random.seed(42)
orders, items = [], []
oid, iid = 1, 1
for _ in range(30):
    cid   = random.randint(1, len(customers))
    days  = random.randint(0, 500)
    date  = (datetime.date(2023, 1, 1) + datetime.timedelta(days=days)).isoformat()
    status = random.choice(["completed","pending","cancelled"])
    orders.append((oid, cid, date, status))
    for _ in range(random.randint(1, 3)):
        pid = random.randint(1, len(products))
        qty = random.randint(1, 5)
        price = next(p[3] for p in products if p[0] == pid)
        items.append((iid, oid, pid, qty, price))
        iid += 1
    oid += 1

conn.executemany("INSERT OR IGNORE INTO orders      VALUES (?,?,?,?)",     orders)
conn.executemany("INSERT OR IGNORE INTO order_items VALUES (?,?,?,?,?)",   items)
conn.commit()
conn.close()
print(f"✅  sample.db created at {DB}")
print(f"   Tables: customers, products, orders, order_items")
