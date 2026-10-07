import sqlite3


conn = sqlite3.connect("data/shop.db")

cursor = conn.cursor()


cursor.execute("""
ALTER TABLE orders
ADD COLUMN order_status TEXT DEFAULT 'Pending'
""")


conn.commit()

conn.close()


print("✅ order_status column added successfully!")