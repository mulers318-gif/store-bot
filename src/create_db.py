import sqlite3


conn = sqlite3.connect(
    "data/shop.db"
)

cursor = conn.cursor()

#  Reset old tables
cursor.execute("DROP TABLE IF EXISTS order_items")
cursor.execute("DROP TABLE IF EXISTS orders")
cursor.execute("DROP TABLE IF EXISTS products")

# -------------------------
# PRODUCTS TABLE
# -------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (

    id INTEGER PRIMARY KEY,

    name TEXT NOT NULL,

    price REAL NOT NULL,

    stock INTEGER NOT NULL

)
""")


# -------------------------
# ORDERS TABLE
# -------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,

    customer_name TEXT NOT NULL,

    phone_number TEXT NOT NULL,

    delivery_location TEXT NOT NULL,

    total_amount REAL NOT NULL,

    payment_status TEXT DEFAULT 'Pending',

    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

)
""")


# -------------------------
# ORDER ITEMS TABLE
# -------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS order_items (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    order_id INTEGER NOT NULL,

    product_id INTEGER NOT NULL,

    quantity INTEGER NOT NULL,

    price REAL NOT NULL,

    FOREIGN KEY (order_id)
        REFERENCES orders(id),

    FOREIGN KEY (product_id)
        REFERENCES products(id)

)
""")
# Insert  initial products
products = [
    ("White Shoes",2500, 10),
    ("Black Hoodie", 1800, 5),
    ("Blue T-shirt",900,15)

]
cursor.executemany(
    "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", products
)

conn.commit()

conn.close()

print("Database tables created successfully!")