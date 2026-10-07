import sqlite3

# Open database connection once
conn = sqlite3.connect("data/shop.db")
cursor = conn.cursor()

# 1. Create support_replies table (if not exists)
cursor.execute("""
CREATE TABLE IF NOT EXISTS support_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    support_message_id INTEGER NOT NULL,
    sender_type TEXT NOT NULL,
    sender_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (support_message_id) REFERENCES support_messages(id)
)
""")
print("✅ support_replies table ready!")

# 2. Add 'priority' column to support_messages (safely)
try:
    cursor.execute("""
    ALTER TABLE support_messages
    ADD COLUMN priority TEXT DEFAULT 'Medium'
    """)
    print("✅ 'priority' column added to support_messages!")
except sqlite3.OperationalError:
    print("ℹ️ 'priority' column already exists in support_messages.")

# 3. Add 'stock_restored' column to orders (safely)
try:
    cursor.execute("""
    ALTER TABLE orders
    ADD COLUMN stock_restored INTEGER DEFAULT 0
    """)
    print("✅ 'stock_restored' column added to orders!")
except sqlite3.OperationalError:
    print("ℹ️ 'stock_restored' column already exists in orders.")

# Commit all changes and close connection once at the end
conn.commit()
conn.close()

print("\n🎉 All database migrations executed successfully!")