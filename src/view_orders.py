import sqlite3


conn = sqlite3.connect(
    "data/shop.db"
)

cursor = conn.cursor()


cursor.execute(
    """
    SELECT
        id,
        customer_name,
        phone_number,
        delivery_location,
        total_amount,
        payment_status
    FROM orders
    """
)

orders = cursor.fetchall()


for order in orders:

    print(order)


conn.close()