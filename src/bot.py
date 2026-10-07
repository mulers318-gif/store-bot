import sqlite3
from datetime import datetime

import os
from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)


# ============================================================
# 1. SETTINGS
# ============================================================
# Load variables from .env file
load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))



# ============================================================
# 2. TEMPORARY STORAGE
# ============================================================

# Cart structure:
#
# carts = {
#     user_id: {
#         product_id: quantity
#     }
# }

carts = {}


# Checkout information:
#
# checkout_data = {
#     user_id: {
#         "name": "...",
#         "phone": "...",
#         "location": "...",
#         "payment_reference": "..."
#     }
# }

checkout_data = {}


# ============================================================
# 3. CHECKOUT STATES
# ============================================================

NAME, PHONE, LOCATION, PAYMENT, SUPPORT = range(5)


# ============================================================
# 4. DATABASE CONNECTION
# ============================================================

def get_connection():

    return sqlite3.connect(
        "data/shop.db"
    )


# ============================================================
# 5. GET PRODUCTS
# ============================================================

def get_products():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            price,
            stock
        FROM products
        ORDER BY id
    """)

    products = cursor.fetchall()

    conn.close()

    return products


# ============================================================
# 6. MAIN CUSTOMER MENU
# ============================================================
def create_menu():

    keyboard = [
        ["🛍️ Browse Catalog"],
        ["🛒 My Cart"],
        ["📋 My Orders"],
        ["📦 Track Order"],
        ["📞 Contact Store"],
        ["📩 My Support Tickets"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# ============================================================
# 7. /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        """
👋 Welcome to our store!

🛍️ Browse our products
🛒 Add products to your cart
📦 Place an order easily

What would you like to do?
""",
        reply_markup=create_menu()
    )


# ============================================================
# 8. SHOW CATALOG
# ============================================================

async def show_catalog(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    products = get_products()

    if not products:

        await update.message.reply_text(
            "❌ No products are available right now."
        )

        return


    await update.message.reply_text(
        "🛍️ PRODUCT CATALOG"
    )


    for product in products:

        product_id = product[0]
        name = product[1]
        price = product[2]
        stock = product[3]


        message = (
            f"🛍️ {name}\n"
            f"💰 Price: {price} ETB\n"
            f"📦 Stock: {stock}"
        )


        # Don't allow customers to add
        # an out-of-stock product.

        if stock <= 0:

            message += "\n❌ OUT OF STOCK"

            await update.message.reply_text(
                message
            )

            continue


        keyboard = [

            [
                InlineKeyboardButton(
                    f"➕ Add {name}",
                    callback_data=f"add_{product_id}"
                )
            ]

        ]


        reply_markup = InlineKeyboardMarkup(
            keyboard
        )


        await update.message.reply_text(
            message,
            reply_markup=reply_markup
        )


# ============================================================
# 9. ADD PRODUCT TO CART
# ============================================================
async def add_to_cart(update, context):

    query = update.callback_query

    user_id = query.from_user.id

    product_id = int(
        query.data.split("_")[1]
    )

    # -----------------------------
    # Get product information
    # -----------------------------

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT name, price, stock
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    conn.close()

    # -----------------------------
    # Product doesn't exist
    # -----------------------------

    if product is None:

        await query.answer(
            "❌ Product not found.",
            show_alert=True
        )

        return

    name, price, stock = product

    # -----------------------------
    # Check stock
    # -----------------------------

    if stock <= 0:

        await query.answer(
            f"❌ {name} is out of stock.",
            show_alert=True
        )

        return

    # -----------------------------
    # Create user's cart
    # -----------------------------

    if user_id not in carts:

        carts[user_id] = {}

    # -----------------------------
    # Current quantity
    # -----------------------------

    current_quantity = carts[user_id].get(
        product_id,
        0
    )

    # -----------------------------
    # Stock protection
    # -----------------------------

    if current_quantity >= stock:

        await query.answer(
            f"❌ Only {stock} available.",
            show_alert=True
        )

        return

    # -----------------------------
    # Add product
    # -----------------------------

    carts[user_id][product_id] = (
        current_quantity + 1
    )

    await query.answer(
        f"✅ {name} added to cart."
    )

# ============================================================
# 10. SHOW CART
# ============================================================
async def show_cart(update, context):

    user_id = update.effective_user.id

    cart = carts.get(user_id, {})

    # -----------------------------
    # Check if cart is empty
    # -----------------------------

    if not cart:

        await update.message.reply_text(
            "🛒 Your cart is empty."
        )

        return

    # -----------------------------
    # Prepare cart message
    # -----------------------------

    message = "🛒 YOUR CART\n\n"

    total = 0

    keyboard = []

    # -----------------------------
    # Connect to database
    # -----------------------------

    conn = get_connection()

    cursor = conn.cursor()

    # -----------------------------
    # Get every product in cart
    # -----------------------------

    for product_id, quantity in cart.items():

        cursor.execute(
            """
            SELECT name, price, stock
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        )

        product = cursor.fetchone()

        if product is None:
            continue

        name, price, stock = product

        subtotal = price * quantity

        total += subtotal

        # -----------------------------
        # Add product to message
        # -----------------------------

        message += (
            f"🛍️ {name}\n"
            f"💰 Price: {price} ETB\n"
            f"🔢 Quantity: {quantity}\n"
            f"💵 Subtotal: {subtotal} ETB\n\n"
        )

        # -----------------------------
        # Quantity buttons
        # -----------------------------

        keyboard.append([
            InlineKeyboardButton(
                "➖",
                callback_data=f"decrease_{product_id}"
            ),

            InlineKeyboardButton(
                f"{quantity}",
                callback_data="nothing"
            ),

            InlineKeyboardButton(
                "➕",
                callback_data=f"increase_{product_id}"
            )
        ])

        # -----------------------------
        # Remove button
        # -----------------------------

        keyboard.append([
            InlineKeyboardButton(
                "🗑️ Remove",
                callback_data=f"remove_{product_id}"
            )
        ])

    conn.close()

    # -----------------------------
    # Total
    # -----------------------------

    message += (
        "━━━━━━━━━━━━━━━━━━\n"
        f"💵 TOTAL: {total} ETB\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    # -----------------------------
    # Checkout button
    # -----------------------------

    keyboard.append([
        InlineKeyboardButton(
            "🛒 CHECKOUT",
            callback_data="checkout"
        )
    ])

    # -----------------------------
    # Send cart
    # -----------------------------

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )




# ============================================================
# 11. START CHECKOUT
# ============================================================

async def checkout_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id


    cart = carts.get(
        user_id,
        {}
    )


    if not cart:

        await update.message.reply_text(
            "🛒 Your cart is empty."
        )

        return ConversationHandler.END


    checkout_data[user_id] = {}


    await update.message.reply_text(
        "👤 Please enter your full name:"
    )


    return NAME


# ============================================================
# 12. GET NAME
# ============================================================
async def get_name(update, context):

    user_id = update.effective_user.id

    name = update.message.text.strip()

    # -----------------------------
    # Check empty name
    # -----------------------------

    if not name:

        await update.message.reply_text(
            "❌ Please enter your name."
        )

        return NAME

    # -----------------------------
    # Check name length
    # -----------------------------

    if len(name) < 2:

        await update.message.reply_text(
            "❌ Name is too short.\n\n"
            "Please enter your full name."
        )

        return NAME

    # -----------------------------
    # Make sure name contains
    # letters
    # -----------------------------

    if not any(character.isalpha() for character in name):

        await update.message.reply_text(
            "❌ Please enter a valid name."
        )

        return NAME

    # -----------------------------
    # Save name
    # -----------------------------

    checkout_data[user_id]["name"] = name

    await update.message.reply_text(
        "📱 Please enter your phone number:"
    )

    return PHONE


# ============================================================
# 13. GET PHONE
# ============================================================
async def get_phone(update, context):

    user_id = update.effective_user.id

    phone = update.message.text.strip()

    # -----------------------------
    # Remove spaces and symbols
    # -----------------------------

    cleaned_phone = (
        phone
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    # -----------------------------
    # Check that phone contains
    # only numbers and +
    # -----------------------------

    if not cleaned_phone.startswith("+"):

        if not cleaned_phone.isdigit():

            await update.message.reply_text(
                "❌ Invalid phone number.\n\n"
                "Example:\n"
                "0912345678"
            )

            return PHONE

    # -----------------------------
    # Check length
    # -----------------------------

    if cleaned_phone.startswith("+"):

        number_part = cleaned_phone[1:]

    else:

        number_part = cleaned_phone

    if not number_part.isdigit():

        await update.message.reply_text(
            "❌ Please enter a valid phone number."
        )

        return PHONE

    if len(number_part) < 9 or len(number_part) > 15:

        await update.message.reply_text(
            "❌ Phone number length is invalid.\n\n"
            "Please enter a valid phone number."
        )

        return PHONE

    # -----------------------------
    # Save phone
    # -----------------------------

    checkout_data[user_id]["phone"] = phone

    await update.message.reply_text(
        "📍 Please enter your delivery location:"
    )

    return LOCATION


# ============================================================
# 14. GET LOCATION
# ============================================================
async def get_location(update, context):

    user_id = update.effective_user.id

    location = update.message.text.strip()

    # -----------------------------
    # Check empty location
    # -----------------------------

    if not location:

        await update.message.reply_text(
            "❌ Please enter your delivery location."
        )

        return LOCATION

    # -----------------------------
    # Check minimum length
    # -----------------------------

    if len(location) < 3:

        await update.message.reply_text(
            "❌ Location is too short.\n\n"
            "Please enter a more detailed location."
        )

        return LOCATION

    # -----------------------------
    # Save location
    # -----------------------------

    checkout_data[user_id]["location"] = location

    await update.message.reply_text(
        """
💳 PAYMENT

Please pay using:

Telebirr:
0950080374

CBE Birr:
1000595998062

After payment, send your
Transaction ID / Reference Number.
"""
    )

    return PAYMENT


# ============================================================
# 15. SAVE ORDER
# ============================================================

def save_order(user_id):

    cart = carts.get(
        user_id,
        {}
    )


    if not cart:

        return None, 0


    products = get_products()


    product_dict = {

        product[0]: {

            "name": product[1],
            "price": product[2],
            "stock": product[3]

        }

        for product in products

    }


    total = 0


    # --------------------------------------------------------
    # Calculate total
    # --------------------------------------------------------

    for product_id, quantity in cart.items():

        if product_id not in product_dict:

            continue


        price = product_dict[
            product_id
        ]["price"]


        stock = product_dict[
            product_id
        ]["stock"]


        if quantity > stock:

            return None, 0


        total += price * quantity


    # --------------------------------------------------------
    # Get customer information
    # --------------------------------------------------------

    customer = checkout_data.get(
        user_id,
        {}
    )


    name = customer.get(
        "name",
        ""
    )


    phone = customer.get(
        "phone",
        ""
    )


    location = customer.get(
        "location",
        ""
    )


    # --------------------------------------------------------
    # Save order
    # --------------------------------------------------------

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        INSERT INTO orders (
            user_id,
            customer_name,
            phone_number,
            delivery_location,
            total_amount,
            payment_status
        )

        VALUES (?, ?, ?, ?, ?, ?)
        """,

        (
            user_id,
            name,
            phone,
            location,
            total,
            "Pending"
        )
    )


    order_id = cursor.lastrowid


    # --------------------------------------------------------
    # Save order items
    # --------------------------------------------------------

    for product_id, quantity in cart.items():

        price = product_dict[
            product_id
        ]["price"]


        cursor.execute(
            """
            INSERT INTO order_items (
                order_id,
                product_id,
                quantity,
                price
            )

            VALUES (?, ?, ?, ?)
            """,

            (
                order_id,
                product_id,
                quantity,
                price
            )
        )


    conn.commit()

    conn.close()


    return order_id, total


# ============================================================
# 16. PAYMENT INSTRUCTIONS
# ============================================================

async def show_payment_instructions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        """
💳 PAYMENT INSTRUCTIONS

Please make your payment using:

🏦 Payment Method:
Telebirr:
0950080374

📱 Account:
1000595998062

👤 Account Name:
Mulugita Simegnew Abebe

━━━━━━━━━━━━━━━━━━

After completing payment,
send your transaction/reference number.

Example:

TXN123456789
"""
    )


    return PAYMENT


# ============================================================
# 17. GET PAYMENT REFERENCE
# ============================================================
async def get_payment_reference(update, context):

    user_id = update.effective_user.id

    payment_reference = update.message.text.strip()

    # Check if payment reference is empty
    if not payment_reference:

        await update.message.reply_text(
            "❌ Payment reference cannot be empty.\n\n"
            "Please enter your transaction ID:"
        )

        return PAYMENT

    # Check if reference is too short
    if len(payment_reference) < 4:

        await update.message.reply_text(
            "❌ Payment reference is too short.\n\n"
            "Please enter the correct transaction ID:"
        )

        return PAYMENT

    # Save payment reference temporarily
    checkout_data[user_id]["payment_reference"] = (
        payment_reference
    )

    # Create the order
    await create_order(
        update,
        context
    )

    return ConversationHandler.END
#-------------------------------------------------------------
# VALIDATE CART STOCK
#-------------------------------------------------------------
def validate_cart_stock(user_id):

    # Get customer's cart
    cart = carts.get(user_id, {})

    # Check if cart is empty
    if not cart:

        return False, "🛒 Your cart is empty."

    # Connect to database
    conn = get_connection()

    cursor = conn.cursor()

    # Check every product in the cart
    for product_id, quantity in cart.items():

        cursor.execute(
            """
            SELECT name, stock
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        )

        product = cursor.fetchone()

        # Product doesn't exist
        if product is None:

            conn.close()

            return False, (
                "❌ One of the products "
                "no longer exists."
            )

        name, stock = product

        # Customer requested more than available
        if quantity > stock:

            conn.close()

            return False, (
                f"❌ Not enough stock for {name}.\n\n"
                f"Available: {stock}\n"
                f"Requested: {quantity}"
            )

    # Close database
    conn.close()

    # Everything is okay
    return True, "OK"
# ============================================================
#  CREATE ORDER
#-----------------------------------------------------------
async def create_order(update, context):

    user_id = update.effective_user.id

    # --------------------------------
    # STEP 1: Check the cart
    # --------------------------------

    cart = carts.get(user_id, {})

    if not cart:

        await update.message.reply_text(
            "🛒 Your cart is empty."
        )

        return


    # --------------------------------
    # STEP 2: Check stock
    # --------------------------------

    is_valid, message = validate_cart_stock(
        user_id
    )

    if not is_valid:

        await update.message.reply_text(
            message
        )

        return


    # --------------------------------
    # STEP 3: Get customer information
    # --------------------------------

    customer_data = checkout_data.get(
        user_id,
        {}
    )

    customer_name = customer_data.get(
        "name"
    )

    phone_number = customer_data.get(
        "phone"
    )

    delivery_location = customer_data.get(
        "location"
    )

    payment_reference = customer_data.get(
        "payment_reference"
    )


    # --------------------------------
    # STEP 4: Make sure information exists
    # --------------------------------

    if not customer_name:

        await update.message.reply_text(
            "❌ Customer name is missing."
        )

        return

    if not phone_number:

        await update.message.reply_text(
            "❌ Phone number is missing."
        )

        return

    if not delivery_location:

        await update.message.reply_text(
            "❌ Delivery location is missing."
        )

        return

    if not payment_reference:

        await update.message.reply_text(
            "❌ Payment reference is missing."
        )

        return


    # --------------------------------
    # STEP 5: Connect to database
    # --------------------------------

    conn = get_connection()

    cursor = conn.cursor()


    # --------------------------------
    # STEP 6: Calculate total
    # --------------------------------

    total_amount = 0

    for product_id, quantity in cart.items():

        cursor.execute(
            """
            SELECT price
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        )

        product = cursor.fetchone()

        if product is None:

            conn.close()

            await update.message.reply_text(
                "❌ Product not found."
            )

            return

        price = product[0]

        subtotal = price * quantity

        total_amount += subtotal


    # --------------------------------
    # STEP 7: Create order
    # --------------------------------

    cursor.execute(
        """
        INSERT INTO orders (
            user_id,
            customer_name,
            phone_number,
            delivery_location,
            total_amount,
            payment_status,
            payment_reference,
            order_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            customer_name,
            phone_number,
            delivery_location,
            total_amount,
            "Pending Verification",
            payment_reference,
            "Pending"
        )
    )


    # Get newly created order ID
    order_id = cursor.lastrowid


    # --------------------------------
    # STEP 8: Save order items
    # --------------------------------

    for product_id, quantity in cart.items():

        cursor.execute(
            """
            SELECT price
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        )

        product = cursor.fetchone()

        if product is None:
            continue

        price = product[0]

        cursor.execute(
            """
            INSERT INTO order_items (
                order_id,
                product_id,
                quantity,
                price
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                order_id,
                product_id,
                quantity,
                price
            )
        )


    # --------------------------------
    # STEP 9: Save database changes
    # --------------------------------

    conn.commit()

    conn.close()


    # --------------------------------
    # STEP 10: Clear customer's cart
    # --------------------------------

    carts[user_id] = {}

    checkout_data[user_id] = {}


    # --------------------------------
    # STEP 11: Tell customer
    # --------------------------------

    await update.message.reply_text(
        f"""
✅ ORDER CREATED SUCCESSFULLY!

🧾 Order ID: #{order_id}

👤 Customer: {customer_name}

📱 Phone: {phone_number}

📍 Location: {delivery_location}

💵 Total: {total_amount} ETB

💳 Payment Reference:
{payment_reference}

💰 Payment Status:
Pending Verification

📦 Order Status:
Pending

⏳ Please wait while the store
verifies your payment.
"""
    )


#-------------------------------------------------------------
# CHECKOUT BUTTON
#-------------------------------------------------------------
async def checkout_button(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    cart = carts.get(user_id, {})

    if not cart:

        await query.message.reply_text(
            "🛒 Your cart is empty."
        )

        return ConversationHandler.END

    checkout_data[user_id] = {}

    await query.message.reply_text(
        "👤 Please enter your full name:"
    )

    return NAME


# ============================================================
# 18. SAVE PAYMENT REFERENCE
# ============================================================

def save_payment_reference(
    user_id,
    payment_reference
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT id
        FROM orders
        WHERE user_id = ?
        AND payment_status = 'Pending'
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,)
    )


    result = cursor.fetchone()


    if result is None:

        conn.close()

        return None


    order_id = result[0]


    cursor.execute(
        """
        UPDATE orders

        SET
            payment_reference = ?,
            payment_status = ?

        WHERE id = ?
        """,

        (
            payment_reference,
            "Pending Verification",
            order_id
        )
    )


    conn.commit()

    conn.close()


    return order_id


# ============================================================
# 19. CANCEL CHECKOUT
# ============================================================

async def cancel_checkout(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id


    checkout_data.pop(
        user_id,
        None
    )


    await update.message.reply_text(
        "❌ Checkout cancelled."
    )


    return ConversationHandler.END


# ============================================================
# 20. TRACK ORDER
# ============================================================
async def track_order(update, context):

    user_id = update.effective_user.id

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            total_amount,
            payment_status,
            order_status,
            timestamp
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    )

    orders_list = cursor.fetchall()

    conn.close()

    if not orders_list:

        await update.message.reply_text(
            """
📦 TRACK ORDER

You don't have any orders yet.

🛍️ Place an order first!
"""
        )

        return

    message = """
📦 TRACK ORDER

Select an order to track:

"""

    keyboard = []

    for order in orders_list:

        (
            order_id,
            total_amount,
            payment_status,
            order_status,
            timestamp
        ) = order

        message += (
            f"🧾 Order #{order_id}\n"
            f"💵 {total_amount} ETB\n"
            f"📦 {order_status}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"👁️ Track Order #{order_id}",
                callback_data=(
                    f"trackorder_{order_id}"
                )
            )
        ])

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

#--------------------------------------------------------------
# SHOW ORDER TRACK
#--------------------------------------------------------------
async def show_order_tracking(update, context):

    query = update.callback_query

    user_id = query.from_user.id

    await query.answer()

    order_id = int(
        query.data.split("_")[1]
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            total_amount,
            payment_status,
            order_status,
            timestamp
        FROM orders
        WHERE id = ?
        AND user_id = ?
        """,
        (
            order_id,
            user_id
        )
    )

    order = cursor.fetchone()

    conn.close()

    if order is None:

        await query.message.reply_text(
            "❌ Order not found."
        )

        return

    (
        order_id,
        total_amount,
        payment_status,
        order_status,
        timestamp
    ) = order

    # Cancelled order
    if order_status == "Cancelled":

        message = f"""
🧾 ORDER #{order_id}

💵 Total:
{total_amount} ETB

💳 Payment:
{payment_status}

━━━━━━━━━━━━━━━━━━

📦 ORDER STATUS

❌ CANCELLED

━━━━━━━━━━━━━━━━━━

🕐 Order Date:
{timestamp}
"""

        await query.message.reply_text(
            message
        )

        return

    status_steps = [
        "Pending",
        "Confirmed",
        "Preparing",
        "Out for Delivery",
        "Delivered"
    ]

    current_index = status_steps.index(
        order_status
    )

    message = f"""
🧾 ORDER #{order_id}

💵 Total:
{total_amount} ETB

💳 Payment:
{payment_status}

━━━━━━━━━━━━━━━━━━

📦 ORDER PROGRESS

"""

    for index, status in enumerate(
        status_steps
    ):

        if index < current_index:

            message += (
                f"✅ {status}\n"
                f"   ↓\n"
            )

        elif index == current_index:

            message += (
                f"🔵 {status} ← CURRENT\n"
            )

            if index < len(status_steps) - 1:
                message += "   ↓\n"

        else:

            message += (
                f"⚪ {status}\n"
            )

            if index < len(status_steps) - 1:
                message += "   ↓\n"

    message += f"""
━━━━━━━━━━━━━━━━━━

📍 CURRENT STATUS:
{order_status}

🕐 ORDER DATE:
{timestamp}
"""

    await query.message.reply_text(
        message
    )


# ============================================================
# 21. CUSTOMER MENU HANDLER
# ============================================================

async def handle_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text


    if text == "🛍️ Browse Catalog":

        await show_catalog(
            update,
            context
        )


    elif text == "🛒 My Cart":

        await show_cart(
            update,
            context
        )


    elif text == "📦 Track Order":

        await track_order(
            update,
            context
        )


   
    elif text == "📋 My Orders":

        await my_orders(
        update,
        context
    )

    elif text == "📞 Contact Store":
                await contact_store(
                   update,
                   context
                    )
    elif text == "📩 My Support Tickets":
                await my_support_tickets(
                    update,
                    context
                    )
                
    
        



# ============================================================
# ============================================================
#                 ADMIN SECTION
# ============================================================
# ============================================================


# ============================================================
# 22. CHECK ADMIN
# ============================================================

def is_admin(update):

    return (
        update.effective_user.id
        == ADMIN_ID
    )


# ============================================================
# 23. /ADMIN
# ============================================================

async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update):

        await update.message.reply_text(
            "❌ You are not authorized to access the admin panel."
        )

        return


    await update.message.reply_text(
        """
👨‍💼 ADMIN PANEL

Welcome, Store Owner.

Available commands:

/orders
/pending
"""
    )


# ============================================================
# 24. GET ALL ORDERS
# ============================================================

def get_orders():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            customer_name,
            phone_number,
            delivery_location,
            total_amount,
            payment_status,
            payment_reference,
            order_status,
            timestamp

        FROM orders

        ORDER BY id DESC
        """
    )

    orders = cursor.fetchall()

    conn.close()

    return orders

#============================================================
# 25. SHOW ALL ORDERS
# ============================================================
async def orders(update, context):

    # Check admin
    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "❌ You are not authorized."
        )

        return

    message = """
📦 ORDER MANAGEMENT

Choose what you want to view:
"""

    keyboard = [
        [
            InlineKeyboardButton(
                "⏳ Pending Payments",
                callback_data="orders_pending_payment"
            )
        ],
        [
            InlineKeyboardButton(
                "📦 Active Orders",
                callback_data="orders_active"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Completed Orders",
                callback_data="orders_completed"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Cancelled Orders",
                callback_data="orders_cancelled"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 All Orders",
                callback_data="orders_all"
            )
        ]
    ]

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# ============================================================
# 26. GET PENDING PAYMENTS
# ============================================================

def get_pending_orders():

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT
            id,
            customer_name,
            phone_number,
            delivery_location,
            total_amount,
            payment_reference,
            timestamp

        FROM orders

        WHERE payment_status = 'Pending Verification'

        ORDER BY id DESC
        """
    )


    orders = cursor.fetchall()


    conn.close()


    return orders


# ============================================================
# 27. SHOW PENDING PAYMENTS
# ============================================================

async def show_pending_payments(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update):

        await update.message.reply_text(
            "❌ Unauthorized."
        )

        return


    orders = get_pending_orders()


    if not orders:

        await update.message.reply_text(
            "✅ No pending payments."
        )

        return


    for order in orders:

        order_id = order[0]

        customer = order[1]

        phone = order[2]

        location = order[3]

        total = order[4]

        reference = order[5]

        timestamp = order[6]


        message = f"""
⏳ PENDING PAYMENT

📦 Order:
#{order_id}

👤 Customer:
{customer}

📱 Phone:
{phone}

📍 Location:
{location}

💰 Amount:
{total} ETB

🧾 Reference:
{reference}

🕐 Time:
{timestamp}
"""


        keyboard = [

            [
                InlineKeyboardButton(
                    "✅ Verify",
                    callback_data=f"verify_{order_id}"
                ),

                InlineKeyboardButton(
                    "❌ Reject",
                    callback_data=f"reject_{order_id}"
                )
            ]

        ]


        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

#-----------------------------------------------------------
# CREATE REDUCE  PRODUCT STOCK FUNCTION
#-----------------------------------------------------------
def reduce_product_stock(order_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # Get all products in this order
        cursor.execute(
            """
            SELECT product_id, quantity
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,)
        )

        items = cursor.fetchall()

        if not items:
            raise Exception(
                "Order contains no products."
            )

        # Check stock first
        for product_id, quantity in items:

            cursor.execute(
                """
                SELECT name, stock
                FROM products
                WHERE id = ?
                """,
                (product_id,)
            )

            product = cursor.fetchone()

            if product is None:
                raise Exception(
                    "Product not found."
                )

            name, stock = product

            if stock < quantity:

                raise Exception(
                    f"Not enough stock for {name}."
                )

        # Reduce stock
        for product_id, quantity in items:

            cursor.execute(
                """
                UPDATE products
                SET stock = stock - ?
                WHERE id = ?
                """,
                (
                    quantity,
                    product_id
                )
            )

        conn.commit()

        return True

    except Exception as error:

        conn.rollback()

        print(
            f"❌ Stock update failed: {error}"
        )

        return False

    finally:

        conn.close()

#-----------------------------------------------------------
# ORDER DETAILS FUNCTION
#----------------------------------------------------------
def get_order_details(order_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            user_id,
            customer_name,
            phone_number,
            delivery_location,
            total_amount,
            payment_status,
            payment_reference,
            order_status,
            timestamp
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    )

    order = cursor.fetchone()

    if order is None:
        conn.close()
        return None

    cursor.execute(
        """
        SELECT
            products.name,
            order_items.quantity,
            order_items.price
        FROM order_items
        JOIN products
        ON order_items.product_id = products.id
        WHERE order_items.order_id = ?
        """,
        (order_id,)
    )

    items = cursor.fetchall()

    conn.close()

    return order, items


#-----------------------------------------------------------
# ORDER MESSAGE FUNCTION
#-----------------------------------------------------------
def format_order_details(order_id):

    result = get_order_details(order_id)

    if result is None:
        return "❌ Order not found."

    order, items = result

    (
        order_id,
        user_id,
        customer_name,
        phone_number,
        delivery_location,
        total_amount,
        payment_status,
        payment_reference,
        order_status,
        timestamp
    ) = order

    message = f"""
🧾 ORDER #{order_id}

👤 Customer:
{customer_name}

📱 Phone:
{phone_number}

📍 Delivery Location:
{delivery_location}

🛍️ PRODUCTS
"""

    for name, quantity, price in items:

        subtotal = quantity * price

        message += (
            f"\n• {name}\n"
            f"  Quantity: {quantity}\n"
            f"  Price: {price} ETB\n"
            f"  Subtotal: {subtotal} ETB\n"
        )

    message += f"""
━━━━━━━━━━━━━━━━━━

💵 TOTAL:
{total_amount} ETB

💳 PAYMENT REFERENCE:
{payment_reference}

💰 PAYMENT STATUS:
{payment_status}

📦 ORDER STATUS:
{order_status}

🕐 CREATED:
{timestamp}
"""

    return message

#-----------------------------------------------------------
# ADMIN ORDER BUTTON FUNCTION
# ----------------------------------------------------------
def order_admin_keyboard(order_id):

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ VERIFY PAYMENT",
                callback_data=f"verify_{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ REJECT PAYMENT",
                callback_data=f"reject_{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "📌 UPDATE STATUS",
                callback_data=f"status_{order_id}"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)    


#-----------------------------------------------------------
# VIEW ORDER DETAILS FUNCTION
#----------------------------------------------------------
async def view_order(update, context):

    query = update.callback_query

    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )
        return

    await query.answer()

    order_id = int(
        query.data.split("_")[1]
    )

    message = format_order_details(
        order_id
    )

    await query.message.reply_text(
        message,
        reply_markup=order_admin_keyboard(
            order_id
        )
    )



#----------------------------------------------------------
# VERIFY PAYMENT AND UPDATE STOCK
#-----------------------------------------------------------
def verify_payment_and_update_stock(order_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # --------------------------------
        # 1. Get current payment status
        # --------------------------------

        cursor.execute(
            """
            SELECT payment_status
            FROM orders
            WHERE id = ?
            """,
            (order_id,)
        )

        order = cursor.fetchone()

        if order is None:
            raise Exception(
                "Order not found."
            )

        payment_status = order[0]

        # --------------------------------
        # 2. Prevent double verification
        # --------------------------------

        if payment_status == "Paid":

            conn.close()

            return False, (
                "already_paid"
            )

        # --------------------------------
        # 3. Get order products
        # --------------------------------

        cursor.execute(
            """
            SELECT product_id, quantity
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,)
        )

        items = cursor.fetchall()

        if not items:

            raise Exception(
                "Order contains no products."
            )

        # --------------------------------
        # 4. Check stock
        # --------------------------------

        for product_id, quantity in items:

            cursor.execute(
                """
                SELECT name, stock
                FROM products
                WHERE id = ?
                """,
                (product_id,)
            )

            product = cursor.fetchone()

            if product is None:

                raise Exception(
                    "Product not found."
                )

            name, stock = product

            if stock < quantity:

                raise Exception(
                    f"Not enough stock for {name}."
                )

        # --------------------------------
        # 5. Mark payment as Paid
        # --------------------------------

        cursor.execute(
            """
            UPDATE orders
            SET payment_status = ?
            WHERE id = ?
            """,
            (
                "Paid",
                order_id
            )
        )

        # --------------------------------
        # 6. Reduce stock
        # --------------------------------

        for product_id, quantity in items:

            cursor.execute(
                """
                UPDATE products
                SET stock = stock - ?
                WHERE id = ?
                """,
                (
                    quantity,
                    product_id
                )
            )

        # --------------------------------
        # 7. Save everything
        # --------------------------------

        conn.commit()

        conn.close()

        return True, "success"

    except Exception as error:

        # --------------------------------
        # Something went wrong
        # --------------------------------

        conn.rollback()

        conn.close()

        print(
            f"❌ Transaction failed: {error}"
        )

        return False, str(error)

#-----------------------------------------------------------
# STOCK RESTORATION FUNCTION(CANCEL ORDER AND RESTORE STOCK)
#-----------------------------------------------------------
def cancel_order_and_restore_stock(order_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # --------------------------------
        # 1. Get order information
        # --------------------------------

        cursor.execute(
            """
            SELECT
                payment_status,
                order_status,
                stock_restored
            FROM orders
            WHERE id = ?
            """,
            (order_id,)
        )

        order = cursor.fetchone()

        if order is None:

            raise Exception(
                "Order not found."
            )

        payment_status = order[0]
        order_status = order[1]
        stock_restored = order[2]

        # --------------------------------
        # 2. Check current status
        # --------------------------------

        if order_status == "Cancelled":

            conn.close()

            return False, "already_cancelled"

        # --------------------------------
        # 3. Make sure order can be
        #    cancelled
        # --------------------------------

        if order_status == "Delivered":

            conn.close()

            return False, "already_delivered"

        # --------------------------------
        # 4. If stock was already
        #    restored, don't restore again
        # --------------------------------

        if stock_restored == 1:

            conn.close()

            return False, "stock_already_restored"

        # --------------------------------
        # 5. Get order products
        # --------------------------------

        cursor.execute(
            """
            SELECT
                product_id,
                quantity
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,)
        )

        items = cursor.fetchall()

        # --------------------------------
        # 6. Restore stock only if
        #    payment was already made
        # --------------------------------

        if payment_status == "Paid":

            for product_id, quantity in items:

                cursor.execute(
                    """
                    UPDATE products
                    SET stock = stock + ?
                    WHERE id = ?
                    """,
                    (
                        quantity,
                        product_id
                    )
                )

            # Mark stock as restored
            cursor.execute(
                """
                UPDATE orders
                SET stock_restored = 1
                WHERE id = ?
                """,
                (order_id,)
            )

        # --------------------------------
        # 7. Cancel order
        # --------------------------------

        cursor.execute(
            """
            UPDATE orders
            SET order_status = ?
            WHERE id = ?
            """,
            (
                "Cancelled",
                order_id
            )
        )

        # --------------------------------
        # 8. Save everything
        # --------------------------------

        conn.commit()

        conn.close()

        return True, "success"

    except Exception as error:

        conn.rollback()

        conn.close()

        print(
            f"❌ Cancellation failed: {error}"
        )

        return False, str(error)


# ============================================================
# 28. VERIFY PAYMENT
# ============================================================
async def verify_payment(update, context):

    query = update.callback_query

    user_id = query.from_user.id

    # --------------------------------
    # Check admin
    # --------------------------------

    if user_id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )

        return

    await query.answer()

    # --------------------------------
    # Get order ID
    # --------------------------------

    order_id = int(
        query.data.split("_")[1]
    )

    # --------------------------------
    # Verify payment + update stock
    # --------------------------------

    success, result = (
        verify_payment_and_update_stock(
            order_id
        )
    )

    # --------------------------------
    # Already paid
    # --------------------------------

    if result == "already_paid":

        await query.message.reply_text(
            f"""
⚠️ PAYMENT ALREADY VERIFIED

🧾 Order: #{order_id}

💰 Payment Status:
Paid

📦 Stock was NOT reduced again.
"""
        )

        return

    # --------------------------------
    # Transaction failed
    # --------------------------------

    if not success:

        await query.message.reply_text(
            f"""
❌ PAYMENT VERIFICATION FAILED

🧾 Order: #{order_id}

Reason:
{result}

Nothing was permanently changed.
"""
        )

        return

    # --------------------------------
    # Get customer
    # --------------------------------

    customer_id = get_order_customer(
        order_id
    )

    # --------------------------------
    # Admin confirmation
    # --------------------------------

    await query.message.reply_text(
        f"""
✅ PAYMENT VERIFIED

🧾 Order: #{order_id}

💰 Payment Status:
Paid

📦 Stock:
Updated

🔒 Transaction:
Successful
"""
    )

    # --------------------------------
    # Notify customer
    # --------------------------------

    if customer_id:

        await send_order_notification(
            context,
            customer_id,
            order_id,
            f"""
💳 PAYMENT CONFIRMED ✅

Your payment for Order #{order_id}
has been verified successfully.

💰 Payment Status:
Paid

📦 Your order is now being processed.

Thank you for your purchase! 🛍️
"""
        )


# ============================================================
# 29. REJECT PAYMENT
# ============================================================

async def reject_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query


    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ Unauthorized.",
            show_alert=True
        )

        return


    await query.answer()


    order_id = int(
        query.data.split("_")[1]
    )


    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        UPDATE orders

        SET payment_status = ?

        WHERE id = ?
        """,
        (
            "Rejected",
            order_id
        )
    )


    conn.commit()

    conn.close()


    await query.message.reply_text(
        f"""
❌ PAYMENT REJECTED

📦 Order:
#{order_id}

⏳ Payment Status:
Rejected
"""
    )


# ============================================================
# 30. /MYID
# ============================================================

async def my_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id


    await update.message.reply_text(
        f"Your Telegram ID is:\n\n{user_id}"
    )

# -----------------------------------------------------------
# SHOW STATUS UPDATE BUTTONS
# -----------------------------------------------------------
async def show_status_options(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query


    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ Unauthorized.",
            show_alert=True
        )

        return


    await query.answer()


    order_id = int(
        query.data.split("_")[1]
    )


    keyboard = [

        [
            InlineKeyboardButton(
                "✅ Confirmed",
                callback_data=f"setstatus_{order_id}_Confirmed"
            )
        ],

        [
            InlineKeyboardButton(
                "👨‍🍳 Preparing",
                callback_data=f"setstatus_{order_id}_Preparing"
            )
        ],

        [
            InlineKeyboardButton(
                "🚚 Out for Delivery",
                callback_data=f"setstatus_{order_id}_Out for Delivery"
            )
        ],

        [
            InlineKeyboardButton(
                "🎉 Delivered",
                callback_data=f"setstatus_{order_id}_Delivered"
            )
        ],

        [
            InlineKeyboardButton(
                "❌ Cancelled",
                callback_data=f"setstatus_{order_id}_Cancelled"
            )
        ]

    ]


    await query.message.reply_text(
        f"""
📌 UPDATE ORDER STATUS

Order:
#{order_id}

Choose the new status:
""",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

#------------------------------------------------------------
# VALID STATUS TRANSITION
#------------------------------------------------------------
VALID_STATUS_TRANSITIONS = {
    "Pending": [
        "Confirmed",
        "Cancelled"
    ],

    "Confirmed": [
        "Preparing",
        "Cancelled"
    ],

    "Preparing": [
        "Out for Delivery",
        "Cancelled"
    ],

    "Out for Delivery": [
        "Delivered"
    ],

    "Delivered": [],

    "Cancelled": []
}

#-------------------------------------------------------------
# VALIDATION FUNCTION
#-------------------------------------------------------------
def is_valid_status_transition(
    current_status,
    new_status
):

    allowed_statuses = (
        VALID_STATUS_TRANSITIONS.get(
            current_status,
            []
        )
    )

    return new_status in allowed_statuses

#-----------------------------------------------------------
# UPDATE ORDER STATUS
#----------------------------------------------------------
async def set_order_status(update, context):

    query = update.callback_query

    user_id = query.from_user.id

    # --------------------------------
    # Check admin
    # --------------------------------

    if user_id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )

        return

    await query.answer()

    # --------------------------------
    # Read callback data
    # --------------------------------

    parts = query.data.split(
        "_",
        2
    )

    order_id = int(parts[1])
    new_status = parts[2]

    # --------------------------------
    # Get current status
    # --------------------------------

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT order_status
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    )

    result = cursor.fetchone()

    conn.close()

    # --------------------------------
    # Order does not exist
    # --------------------------------

    if result is None:

        await query.message.reply_text(
            "❌ Order not found."
        )

        return

    current_status = result[0]

    # --------------------------------
    # Check status transition
    # --------------------------------

    if not is_valid_status_transition(
        current_status,
        new_status
    ):

        await query.message.reply_text(
            f"""
❌ INVALID STATUS CHANGE

🧾 Order:
#{order_id}

Current:
{current_status}

Requested:
{new_status}

This status change is not allowed.
"""
        )

        return
     # --------------------------------
     # Handle cancellation
     # --------------------------------

    if new_status == "Cancelled":

       success, result = (
        cancel_order_and_restore_stock(
            order_id
        )
    )

    if result == "already_cancelled":

        await query.message.reply_text(
            f"""
⚠️ ORDER ALREADY CANCELLED

🧾 Order:
#{order_id}

The stock has already been
handled.
"""
        )

        return

    if result == "already_delivered":

        await query.message.reply_text(
            f"""
❌ ORDER CANNOT BE CANCELLED

🧾 Order:
#{order_id}

This order has already
been delivered.
"""
        )

        return

    if not success:

        await query.message.reply_text(
            f"""
❌ CANCELLATION FAILED

🧾 Order:
#{order_id}

Reason:
{result}
"""
        )

        return

    else:

    # --------------------------------
    # Normal status update
    # --------------------------------

     conn = get_connection()
     cursor = conn.cursor()

     cursor.execute(
        """
        UPDATE orders
        SET order_status = ?
        WHERE id = ?
        """,
        (
            new_status,
            order_id
        )
    )

    conn.commit()
    conn.close()
    
    

    
    # --------------------------------
    # Get customer
    # --------------------------------

    customer_id = get_order_customer(
        order_id
    )

    # --------------------------------
    # Admin confirmation
    # --------------------------------

    await query.message.reply_text(
        f"""
✅ ORDER STATUS UPDATED

🧾 Order:
#{order_id}

Previous:
{current_status}

New:
{new_status}
"""
    )

    # --------------------------------
    # Customer notification
    # --------------------------------

    if customer_id:

        if new_status == "Confirmed":

            notification = f"""
📦 ORDER CONFIRMED ✅

Your Order #{order_id}
has been confirmed.

We will begin preparing
your order soon.
"""

        elif new_status == "Preparing":

            notification = f"""
👨‍🍳 ORDER BEING PREPARED

Your Order #{order_id}
is now being prepared.

We'll notify you when it
is ready for delivery.
"""

        elif new_status == "Out for Delivery":

            notification = f"""
🚚 ORDER OUT FOR DELIVERY

Your Order #{order_id}
is now on the way! 🛵

Please be available to
receive your order.
"""

        elif new_status == "Delivered":

            notification = f"""
✅ ORDER DELIVERED

Your Order #{order_id}
has been marked as delivered.

Thank you for shopping
with us! 🛍️
"""

        elif new_status == "Cancelled":

            notification = f"""
❌ ORDER CANCELLED

Your Order #{order_id}
has been cancelled.

Please contact the store
if you have any questions.
"""

        else:

            notification = f"""
📦 ORDER UPDATE

Your Order #{order_id}
status is now:

{new_status}
"""

        await send_order_notification(
            context,
            customer_id,
            order_id,
            notification
        )

#-----------------------------------------------------------
# NOTIFICATION FUNCTION
#-----------------------------------------------------------
async def send_order_notification(
    context,
    user_id,
    order_id,
    message
):

    try:

        await context.bot.send_message(
            chat_id=user_id,
            text=message
        )

        print(
            f"✅ Notification sent to user {user_id}"
        )

    except Exception as error:

        print(
            f"❌ Could not send notification: {error}"
        )


# ============================================================
# GET CUSTOMER ID FOR AN ORDER
# ============================================================

def get_order_customer(order_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    )

    result = cursor.fetchone()

    conn.close()

    if result is None:
        return None

    return result[0]

#-----------------------------------------------------------
# INCREASE QUANTITY
#-----------------------------------------------------------
async def increase_quantity(update, context):

    query = update.callback_query

    user_id = query.from_user.id

    product_id = int(
        query.data.split("_")[1]
    )

    # -----------------------------
    # Check if product is in cart
    # -----------------------------

    if user_id not in carts:
        await query.answer(
            "🛒 Your cart is empty.",
            show_alert=True
        )
        return

    if product_id not in carts[user_id]:
        await query.answer(
            "❌ Product not found in cart.",
            show_alert=True
        )
        return

    # -----------------------------
    # Get current stock
    # -----------------------------

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT name, stock
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    )

    product = cursor.fetchone()

    conn.close()

    # -----------------------------
    # Product doesn't exist
    # -----------------------------

    if product is None:

        await query.answer(
            "❌ Product no longer exists.",
            show_alert=True
        )

        return

    name, stock = product

    current_quantity = carts[user_id][product_id]

    # -----------------------------
    # Stock protection
    # -----------------------------

    if current_quantity >= stock:

        await query.answer(
            f"❌ Only {stock} {name} available.",
            show_alert=True
        )

        return

    # -----------------------------
    # Increase quantity
    # -----------------------------

    carts[user_id][product_id] += 1

    await query.answer()

    # -----------------------------
    # Refresh cart
    # -----------------------------

    await update_cart_message(
        query,
        user_id
    )


#-----------------------------------------------------------
# DECREASE QUANTITY
#-----------------------------------------------------------
async def decrease_quantity(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    product_id = int(
        query.data.split("_")[1]
    )

    if user_id not in carts:
        return

    if product_id not in carts[user_id]:
        return

    # Decrease quantity
    carts[user_id][product_id] -= 1

    # Remove if quantity reaches zero
    if carts[user_id][product_id] <= 0:

        del carts[user_id][product_id]

    # Refresh the cart
    await update_cart_message(
        query,
        user_id
    )


#-----------------------------------------------------------
# REMOVE FROM CART
#-----------------------------------------------------------
async def remove_from_cart(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    product_id = int(
        query.data.split("_")[1]
    )

    if user_id not in carts:
        return

    if product_id in carts[user_id]:

        del carts[user_id][product_id]

    # Refresh the cart
    await update_cart_message(
        query,
        user_id
    )


#-----------------------------------------------------------
# NOTHING
#-----------------------------------------------------------
async def nothing_button(update, context):

    query = update.callback_query

    await query.answer()

#-----------------------------------------------------------
#UPDATE CART MESSAGE
#-----------------------------------------------------------
async def update_cart_message(query, user_id):

    cart = carts.get(user_id, {})

    # -----------------------------
    # Cart is empty
    # -----------------------------

    if not cart:

        await query.edit_message_text(
            "🛒 Your cart is empty."
        )

        return

    message = "🛒 YOUR CART\n\n"

    total = 0

    keyboard = []

    # -----------------------------
    # Database
    # -----------------------------

    conn = get_connection()

    cursor = conn.cursor()

    # -----------------------------
    # Get products
    # -----------------------------

    for product_id, quantity in cart.items():

        cursor.execute(
            """
            SELECT name, price
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        )

        product = cursor.fetchone()

        if product is None:
            continue

        name, price = product

        subtotal = price * quantity

        total += subtotal

        # -----------------------------
        # Product information
        # -----------------------------

        message += (
            f"🛍️ {name}\n"
            f"💰 Price: {price} ETB\n"
            f"🔢 Quantity: {quantity}\n"
            f"💵 Subtotal: {subtotal} ETB\n\n"
        )

        # -----------------------------
        # Quantity buttons
        # -----------------------------

        keyboard.append([
            InlineKeyboardButton(
                "➖",
                callback_data=f"decrease_{product_id}"
            ),

            InlineKeyboardButton(
                f"{quantity}",
                callback_data="nothing"
            ),

            InlineKeyboardButton(
                "➕",
                callback_data=f"increase_{product_id}"
            )
        ])

        # -----------------------------
        # Remove
        # -----------------------------

        keyboard.append([
            InlineKeyboardButton(
                "🗑️ Remove",
                callback_data=f"remove_{product_id}"
            )
        ])

    conn.close()

    # -----------------------------
    # Total
    # -----------------------------

    message += (
        "━━━━━━━━━━━━━━━━━━\n"
        f"💵 TOTAL: {total} ETB\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    # -----------------------------
    # Checkout
    # -----------------------------

    keyboard.append([
        InlineKeyboardButton(
            "🛒 CHECKOUT",
            callback_data="checkout"
        )
    ])

    # -----------------------------
    # Update existing message
    # -----------------------------

    await query.edit_message_text(
        text=message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# -----------------------------------------------------------
# ORDER FILTERING FUNCTION
#------------------------------------------------------------
async def show_filtered_orders(
    update,
    context
):

    query = update.callback_query

    user_id = query.from_user.id

    # Check admin
    if user_id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )

        return

    await query.answer()

    filter_type = query.data

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------
    # Pending payments
    # --------------------------------

    if filter_type == "orders_pending_payment":

        cursor.execute(
            """
            SELECT
                id,
                customer_name,
                total_amount,
                payment_status,
                order_status
            FROM orders
            WHERE payment_status = ?
            ORDER BY id DESC
            """,
            ("Pending Verification",)
        )

        title = "⏳ PENDING PAYMENTS"

    # --------------------------------
    # Active orders
    # --------------------------------

    elif filter_type == "orders_active":

        cursor.execute(
            """
            SELECT
                id,
                customer_name,
                total_amount,
                payment_status,
                order_status
            FROM orders
            WHERE order_status IN (
                'Pending',
                'Confirmed',
                'Preparing',
                'Out for Delivery'
            )
            ORDER BY id DESC
            """
        )

        title = "📦 ACTIVE ORDERS"

    # --------------------------------
    # Completed orders
    # --------------------------------

    elif filter_type == "orders_completed":

        cursor.execute(
            """
            SELECT
                id,
                customer_name,
                total_amount,
                payment_status,
                order_status
            FROM orders
            WHERE order_status = ?
            ORDER BY id DESC
            """,
            ("Delivered",)
        )

        title = "✅ COMPLETED ORDERS"

    # --------------------------------
    # Cancelled orders
    # --------------------------------

    elif filter_type == "orders_cancelled":

        cursor.execute(
            """
            SELECT
                id,
                customer_name,
                total_amount,
                payment_status,
                order_status
            FROM orders
            WHERE order_status = ?
            ORDER BY id DESC
            """,
            ("Cancelled",)
        )

        title = "❌ CANCELLED ORDERS"

    # --------------------------------
    # All orders
    # --------------------------------

    elif filter_type == "orders_all":

        cursor.execute(
            """
            SELECT
                id,
                customer_name,
                total_amount,
                payment_status,
                order_status
            FROM orders
            ORDER BY id DESC
            """
        )

        title = "📋 ALL ORDERS"

    else:

        conn.close()

        return

    orders_list = cursor.fetchall()

    conn.close()

    # --------------------------------
    # No orders
    # --------------------------------

    if not orders_list:

        await query.message.reply_text(
            f"""
{title}

No orders found.
"""
        )

        return

    # --------------------------------
    # Build message
    # --------------------------------

    message = f"{title}\n\n"

    keyboard = []

    for order in orders_list:

        (
            order_id,
            customer_name,
            total_amount,
            payment_status,
            order_status
        ) = order

        message += (
            f"🧾 Order #{order_id}\n"
            f"👤 {customer_name}\n"
            f"💵 {total_amount} ETB\n"
            f"💰 {payment_status}\n"
            f"📦 {order_status}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"👁️ View Order #{order_id}",
                callback_data=(
                    f"vieworder_{order_id}"
                )
            )
        ])

    await query.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

#--------------------------------------------------------------
# MY ORDER
#========================================================
async def my_orders(update, context):

    user_id = update.effective_user.id

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            total_amount,
            payment_status,
            order_status,
            timestamp
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    )

    orders_list = cursor.fetchall()

    conn.close()

    # --------------------------------
    # No orders
    # --------------------------------

    if not orders_list:

        await update.message.reply_text(
            """
📋 MY ORDERS

You don't have any orders yet.

🛍️ Start shopping and place
your first order!
"""
        )

        return

    # --------------------------------
    # Build order history
    # --------------------------------

    message = "📋 MY ORDERS\n\n"
    keyboard = []

    for order in orders_list:
     (
        order_id,
        total_amount,
        payment_status,
        order_status,
        timestamp
    ) = order

    message += (
        f"🧾 Order #{order_id}\n"
        f"💵 Total: {total_amount} ETB\n"
        f"💰 Payment: {payment_status}\n"
        f"📦 Status: {order_status}\n"
        f"🕐 Date: {timestamp}\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    keyboard.append([
        InlineKeyboardButton(
            f"👁️ View Order #{order_id}",
            callback_data=f"customerorder_{order_id}"
        )
    ])

    await update.message.reply_text(
      message,
      reply_markup=InlineKeyboardMarkup(
        keyboard
    )
)

#----------------------------------------------------------
# CUSTOMER ORDER DETAIL
#----------------------------------------------------------
async def customer_order_detail(update, context):

    query = update.callback_query

    user_id = query.from_user.id

    await query.answer()

    order_id = int(
        query.data.split("_")[1]
    )

    conn = get_connection()
    cursor = conn.cursor()

    # Get order information
    cursor.execute(
        """
        SELECT
            id,
            customer_name,
            phone_number,
            delivery_location,
            total_amount,
            payment_status,
            payment_reference,
            order_status,
            timestamp
        FROM orders
        WHERE id = ?
        AND user_id = ?
        """,
        (
            order_id,
            user_id
        )
    )

    order = cursor.fetchone()

    if order is None:

        conn.close()

        await query.message.reply_text(
            "❌ Order not found."
        )

        return

    # Get products in this order
    cursor.execute(
        """
        SELECT
            products.name,
            order_items.quantity,
            order_items.price
        FROM order_items

        JOIN products
        ON order_items.product_id = products.id

        WHERE order_items.order_id = ?
        """,
        (order_id,)
    )

    items = cursor.fetchall()

    conn.close()

    (
        order_id,
        customer_name,
        phone_number,
        delivery_location,
        total_amount,
        payment_status,
        payment_reference,
        order_status,
        timestamp
    ) = order

    message = f"""
🧾 ORDER #{order_id}

👤 CUSTOMER
{customer_name}

📱 PHONE
{phone_number}

📍 DELIVERY LOCATION
{delivery_location}

━━━━━━━━━━━━━━━━━━

🛍️ PRODUCTS
"""

    for name, quantity, price in items:

        subtotal = quantity * price

        message += (
            f"\n🛍️ {name}\n"
            f"   Quantity: {quantity}\n"
            f"   Price: {price} ETB\n"
            f"   Subtotal: {subtotal} ETB\n"
        )

    message += f"""
━━━━━━━━━━━━━━━━━━

💵 TOTAL
{total_amount} ETB

💳 PAYMENT STATUS
{payment_status}

🔖 PAYMENT REFERENCE
{payment_reference}

📦 ORDER STATUS
{order_status}

🕐 ORDER DATE
{timestamp}
"""

    await query.message.reply_text(
        message
    )

#----------------------------------------------------------
# CONTACT STORE
#----------------------------------------------------------
async def contact_store(update, context):

    await update.message.reply_text(
        """
📞 CONTACT STORE

Please type your message below.

For example:

• I want to change my order.
• Where is my order?
• I have a payment problem.
• I want to ask about a product.
• I need help with delivery.

💬 Send your message now:
"""
    )

    return SUPPORT

#-----------------------------------------------------------
# RECEIVE CUSTOMER MESSAGE
#-----------------------------------------------------------
async def receive_customer_message(
    update,
    context
):

    user = update.effective_user

    customer_id = user.id
    customer_name = user.full_name

    message_text = update.message.text.strip()

    if not message_text:

        await update.message.reply_text(
            "❌ Your message cannot be empty."
        )

        return ConversationHandler.END

    # Save message to database
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO support_messages (
            customer_id,
            customer_name,
            message,
            status
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            customer_id,
            customer_name,
            message_text,
            "Open"
        )
    )

    support_message_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # SAVE SUPPORT REPLY
    save_support_reply(
        customer_id,
        "Customer",
        customer_id,
        message_text
    )
    

    # Reply button for admin
    keyboard = [
        [
            InlineKeyboardButton(
                "💬 REPLY",
                callback_data=(
                    f"supportreply_{support_message_id}"
                )
            )
        ]
    ]

    # Tell customer
    await update.message.reply_text(
        """
✅ MESSAGE SENT

Thank you!

Your message has been sent
to the store.

The store will reply to you soon. 💬
"""
    )

    # Send message to admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"""
📩 NEW CUSTOMER MESSAGE

🆔 Support Message:
#{support_message_id}

👤 Customer:
{customer_name}

🆔 Telegram ID:
{customer_id}

━━━━━━━━━━━━━━━━━━

💬 MESSAGE:

{message_text}

━━━━━━━━━━━━━━━━━━
""",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    return ConversationHandler.END



#------------------------------------------------------------
# SUPPORT REPLY BUTTON (ADMIN REPLY FUNCTION)
#------------------------------------------------------------
async def support_reply_button(
    update,
    context
):

    query = update.callback_query

    admin_id = query.from_user.id

    if admin_id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )

        return

    await query.answer()

    support_message_id = int(
        query.data.split("_")[1]
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            customer_id,
            customer_name,
            message,
            status
        FROM support_messages
        WHERE id = ?
        """,
        (support_message_id,)
    )

    support_message = cursor.fetchone()

    conn.close()

    if support_message is None:

        await query.message.reply_text(
            "❌ Support message not found."
        )

        return

    (
        customer_id,
        customer_name,
        message_text,
        status
    ) = support_message

    if status == "Closed":

        await query.message.reply_text(
            """
⚠️ This support message
has already been closed.
"""
        )

        return

    context.user_data[
        "support_message_id"
    ] = support_message_id

    context.user_data[
        "support_customer_id"
    ] = customer_id

    await query.message.reply_text(
        f"""
💬 REPLY TO CUSTOMER

🆔 Support Message:
#{support_message_id}

👤 Customer:
{customer_name}

💬 Original Message:

{message_text}

━━━━━━━━━━━━━━━━━━

✏️ Type your reply:
"""
    )

#------------------------------------------------------------
# SEND SUPPORT REPLY
#------------------------------------------------------------
async def send_support_reply(update, context):

    admin_id = update.effective_user.id

    if admin_id != ADMIN_ID:

        await update.message.reply_text(
            "❌ You are not authorized."
        )
        return

    support_message_id = context.user_data.get(
        "support_message_id"
    )

    customer_id = context.user_data.get(
        "support_customer_id"
    )

    if not support_message_id or not customer_id:

        await update.message.reply_text(
            """
❌ No support ticket is selected.

Please open a support ticket
and press Reply first.
"""
        )
        return

    admin_reply = update.message.text.strip()

    if not admin_reply:

        await update.message.reply_text(
            "❌ Reply cannot be empty."
        )
        return
    save_support_reply(
    support_message_id,
    "Admin",
    admin_id,
    admin_reply
)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE support_messages
        SET
            admin_reply = ?,
            status = ?,
            replied_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            admin_reply,
            "Replied",
            support_message_id
        )
    )

    conn.commit()
    conn.close()

    # Notify customer
    notification = f"""
💬 SUPPORT REPLY

The store has replied to your
support ticket.

🎫 Ticket #{support_message_id}

━━━━━━━━━━━━━━━━━━

💬 REPLY:

{admin_reply}

━━━━━━━━━━━━━━━━━━

If you need more help, please
contact the store again. 📞
"""

    await notify_support_customer(
        context,
        customer_id,
        support_message_id,
        notification
    )

    await update.message.reply_text(
        f"""
✅ REPLY SENT

🎫 Ticket #{support_message_id}

Your reply was sent to the customer.
"""
    )

    # Clear temporary support state
    context.user_data.pop(
        "support_message_id",
        None
    )

    context.user_data.pop(
        "support_customer_id",
        None
    )


#-------------------------------------------------------------
# ROUT TEXT MESSAGE
#------------------------------------------------------------
async def route_text_message(update, context):

    user_id = update.effective_user.id

    # Admin replying to support ticket
    if (
        user_id == ADMIN_ID
        and context.user_data.get(
            "support_customer_id"
        )
    ):

        await send_support_reply(
            update,
            context
        )

        return

    # Customer replying to existing ticket
    if context.user_data.get(
        "customer_support_reply_ticket"
    ):

        await send_customer_support_reply(
            update,
            context
        )

        return

    # Normal menu message
    await handle_menu(
        update,
        context
    )



#-------------------------------------------------------------
# SUPPORT INBOX
#-------------------------------------------------------------
async def support_inbox(update, context):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ You are not authorized."
        )
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Count Open tickets
    cursor.execute(
        "SELECT COUNT(*) FROM support_messages WHERE status = ?",
        ("Open",)
    )
    open_count = cursor.fetchone()[0]

    # Count Replied tickets
    cursor.execute(
        "SELECT COUNT(*) FROM support_messages WHERE status = ?",
        ("Replied",)
    )
    replied_count = cursor.fetchone()[0]

    # Count Closed tickets
    cursor.execute(
        "SELECT COUNT(*) FROM support_messages WHERE status = ?",
        ("Closed",)
    )
    closed_count = cursor.fetchone()[0]

    # Count all tickets
    cursor.execute(
        "SELECT COUNT(*) FROM support_messages"
    )
    total_count = cursor.fetchone()[0]

    conn.close()

    message = f"""
📩 SUPPORT INBOX

🔴 Open:
{open_count}

🟡 Replied:
{replied_count}

🟢 Closed:
{closed_count}

📋 Total:
{total_count}

Choose a category:
"""
    keyboard = [
    [
        InlineKeyboardButton(
            "🔴 Open Tickets",
            callback_data="support_open"
        )
    ],
    [
        InlineKeyboardButton(
            "🟡 Replied Tickets",
            callback_data="support_replied"
        )
    ],
    [
        InlineKeyboardButton(
            "🟢 Closed Tickets",
            callback_data="support_closed"
        )
    ],
    [
        InlineKeyboardButton(
            "📋 All Tickets",
            callback_data="support_all"
        )
    ],
    [
        InlineKeyboardButton(
            "📊 Support Analytics",
            callback_data="support_statistics"
        )
    ]
] 
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


#--------------------------------------------------------------
# SHOW SUPPORT TICKETS
#--------------------------------------------------------------
async def show_support_tickets(update, context):

    query = update.callback_query

    await query.answer()

    # -----------------------------------
    # ADMIN SECURITY
    # -----------------------------------

    if query.from_user.id != ADMIN_ID:

        await query.message.reply_text(
            "❌ You are not authorized."
        )

        return

    # -----------------------------------
    # GET FILTER
    # -----------------------------------

    filter_name = query.data

    # -----------------------------------
    # DATABASE CONNECTION
    # -----------------------------------

    conn = get_connection()
    cursor = conn.cursor()

    # -----------------------------------
    # GET TICKETS
    # -----------------------------------

    if filter_name == "support_all":

        cursor.execute(
            """
            SELECT
                id,
                customer_name,
                message,
                status,
                priority,
                created_at
            FROM support_messages
            ORDER BY
                CASE priority
                    WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2
                    WHEN 'Low' THEN 3
                    ELSE 4
                END,
                id DESC
            """
        )

    else:

        # Convert callback into status

        if filter_name == "support_open":

            status_filter = "Open"

        elif filter_name == "support_replied":

            status_filter = "Replied"

        elif filter_name == "support_closed":

            status_filter = "Closed"

        else:

            conn.close()

            await query.message.reply_text(
                "❌ Invalid support filter."
            )

            return

        cursor.execute(
            """
            SELECT
                id,
                customer_name,
                message,
                status,
                priority,
                created_at
            FROM support_messages
            WHERE status = ?
            ORDER BY
                CASE priority
                    WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2
                    WHEN 'Low' THEN 3
                    ELSE 4
                END,
                id DESC
            """,
            (status_filter,)
        )

    tickets = cursor.fetchall()

    conn.close()

    # -----------------------------------
    # NO TICKETS
    # -----------------------------------

    if not tickets:

        await query.message.edit_text(
            """
📩 SUPPORT TICKETS

No tickets found.
"""
        )

        return

    # -----------------------------------
    # CREATE MESSAGE
    # -----------------------------------

    message = """
📩 SUPPORT TICKETS

Tickets are sorted by priority:

🔴 HIGH → first
🟡 MEDIUM → second
🟢 LOW → third

━━━━━━━━━━━━━━━━━━

"""

    keyboard = []

    # -----------------------------------
    # DISPLAY TICKETS
    # -----------------------------------

    for ticket in tickets:

        (
            ticket_id,
            customer_name,
            ticket_message,
            status,
            priority,
            created_at
        ) = ticket

        # Create short preview

        preview = ticket_message[:45]

        if len(ticket_message) > 45:

            preview += "..."

        # Add ticket information

        message += (
            f"🎫 Ticket #{ticket_id}\n"
            f"👤 Customer: {customer_name}\n"
            f"💬 {preview}\n"
            f"📌 Priority: {priority_label(priority)}\n"
            f"📌 Status: {status}\n"
            f"🕐 {created_at}\n\n"
        )

        # Add View button

        keyboard.append([
            InlineKeyboardButton(
                f"👁️ View Ticket #{ticket_id}",
                callback_data=f"viewsupport_{ticket_id}"
            )
        ])

    # -----------------------------------
    # BACK BUTTON
    # -----------------------------------

    keyboard.append([
        InlineKeyboardButton(
            "⬅️ Back to Support Inbox",
            callback_data="support_back"
        )
    ])

    # -----------------------------------
    # SHOW RESULT
    # -----------------------------------

    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


#--------------------------------------------------------------
# VIEW SUPPORT TICKET
#--------------------------------------------------------------
async def view_support_ticket(update, context):

    query = update.callback_query

    await query.answer()

    # ==========================================
    # ADMIN SECURITY CHECK
    # ==========================================

    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )

        return

    # ==========================================
    # GET TICKET ID
    # ==========================================

    ticket_id = int(
        query.data.split("_")[1]
    )

    # ==========================================
    # GET TICKET INFORMATION
    # ==========================================

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            customer_id,
            customer_name,
            message,
            admin_reply,
            status,
            priority,
            created_at,
            replied_at
        FROM support_messages
        WHERE id = ?
        """,
        (ticket_id,)
    )

    ticket = cursor.fetchone()

    # ==========================================
    # TICKET NOT FOUND
    # ==========================================

    if ticket is None:

        conn.close()

        await query.message.reply_text(
            "❌ Support ticket not found."
        )

        return

    # ==========================================
    # UNPACK TICKET INFORMATION
    # ==========================================

    (
        ticket_id,
        customer_id,
        customer_name,
        original_message,
        admin_reply,
        status,
        priority,
        created_at,
        replied_at
    ) = ticket

    # ==========================================
    # GET FULL CONVERSATION
    # ==========================================

    cursor.execute(
        """
        SELECT
            sender_type,
            message,
            created_at
        FROM support_replies
        WHERE support_message_id = ?
        ORDER BY id ASC
        """,
        (ticket_id,)
    )

    conversation = cursor.fetchall()

    conn.close()

    # ==========================================
    # CREATE PRIORITY DISPLAY
    # ==========================================

    priority_text = priority_label(
        priority
    )
    sla_text = calculate_ticket_sla(
    priority,
    created_at
)
    

    # ==========================================
    # CREATE TICKET MESSAGE
    # ==========================================

    message = f"""
🎫 SUPPORT TICKET #{ticket_id}

👤 CUSTOMER:
{customer_name}

🆔 Customer ID:
{customer_id}

📌 PRIORITY:
{priority_text}

📌 STATUS:
{status}

⏱️ SLA:
{sla_text}

━━━━━━━━━━━━━━━━━━

💬 CONVERSATION:
"""

    # ==========================================
    # DISPLAY CONVERSATION
    # ==========================================

    if conversation:

        for sender_type, reply_text, created_at in conversation:

            if sender_type == "Customer":

                message += (
                    f"\n👤 CUSTOMER\n"
                    f"{reply_text}\n"
                    f"🕐 {created_at}\n"
                )

            else:

                message += (
                    f"\n👨‍💼 STORE\n"
                    f"{reply_text}\n"
                    f"🕐 {created_at}\n"
                )

    else:

        message += (
            "\nNo conversation messages yet.\n"
        )

    # ==========================================
    # CREATE BUTTONS
    # ==========================================

    keyboard = []

    # Priority buttons
    keyboard.append([
        InlineKeyboardButton(
            "🔴 HIGH",
            callback_data=f"priority_{ticket_id}_High"
        ),
        InlineKeyboardButton(
            "🟡 MEDIUM",
            callback_data=f"priority_{ticket_id}_Medium"
        ),
        InlineKeyboardButton(
            "🟢 LOW",
            callback_data=f"priority_{ticket_id}_Low"
        )
    ])

    # Reply button
    if status == "Open":

        keyboard.append([
            InlineKeyboardButton(
                "💬 REPLY TO TICKET",
                callback_data=f"ticketreply_{ticket_id}"
            )
        ])

    elif status == "Replied":

        keyboard.append([
            InlineKeyboardButton(
                "💬 REPLY TO TICKET",
                callback_data=f"ticketreply_{ticket_id}"
            )
        ])

    # Close / reopen buttons
    if status != "Closed":

        keyboard.append([
            InlineKeyboardButton(
                "🔒 CLOSE TICKET",
                callback_data=f"closeticket_{ticket_id}"
            )
        ])

    else:

        keyboard.append([
            InlineKeyboardButton(
                "🔓 REOPEN TICKET",
                callback_data=f"reopenticket_{ticket_id}"
            )
        ])

    # Refresh button
    keyboard.append([
        InlineKeyboardButton(
            "🔄 REFRESH",
            callback_data=f"viewsupport_{ticket_id}"
        )
    ])

    # ==========================================
    # SHOW TICKET
    # ==========================================

    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )



#--------------------------------------------------------------
# TICKET REPLY BUTTON
#--------------------------------------------------------------
async def ticket_reply_button(
    update,
    context
):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )

        return

    await query.answer()

    ticket_id = int(
        query.data.split("_")[1]
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            customer_id,
            customer_name,
            message,
            status
        FROM support_messages
        WHERE id = ?
        """,
        (ticket_id,)
    )

    ticket = cursor.fetchone()

    conn.close()

    if ticket is None:

        await query.message.reply_text(
            "❌ Ticket not found."
        )

        return

    (
        customer_id,
        customer_name,
        message_text,
        status
    ) = ticket

    if status != "Open":

        await query.message.reply_text(
            "⚠️ This ticket has already been replied to."
        )

        return

    context.user_data[
        "support_message_id"
    ] = ticket_id

    context.user_data[
        "support_customer_id"
    ] = customer_id

    await query.message.reply_text(
        f"""
💬 REPLY TO TICKET #{ticket_id}

👤 Customer:
{customer_name}

💬 Message:

{message_text}

━━━━━━━━━━━━━━━━━━

✏️ Type your reply:
"""
    )


#--------------------------------------------------------------
# CLOSE SUPPORT TICKET
#--------------------------------------------------------------
async def close_support_ticket(update, context):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )
        return

    await query.answer()

    ticket_id = int(
        query.data.split("_")[1]
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT customer_id, status
        FROM support_messages
        WHERE id = ?
        """,
        (ticket_id,)
    )

    ticket = cursor.fetchone()

    if ticket is None:

        conn.close()

        await query.message.reply_text(
            "❌ Ticket not found."
        )
        return

    customer_id, current_status = ticket

    if current_status == "Closed":

        conn.close()

        await query.message.reply_text(
            "ℹ️ This ticket is already closed."
        )
        return

    cursor.execute(
        """
        UPDATE support_messages
        SET status = ?
        WHERE id = ?
        """,
        ("Closed", ticket_id)
    )

    conn.commit()
    conn.close()

    # Notify customer
    notification = f"""
🔒 SUPPORT TICKET CLOSED

Your support ticket #{ticket_id}
has been closed.

━━━━━━━━━━━━━━━━━━

If you need more help, please
contact the store again. 📞

Thank you for contacting us. 🙏
"""

    await notify_support_customer(
        context,
        customer_id,
        ticket_id,
        notification
    )

    await query.message.reply_text(
        f"""
🔒 TICKET CLOSED

🎫 Ticket #{ticket_id}

The support ticket has been
successfully closed. ✅

The customer has been notified.
"""
    )


#-------------------------------------------------------------
# REOPEN SUPPORT TICKETS
#-------------------------------------------------------------
async def reopen_support_ticket(update, context):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )
        return

    await query.answer()

    ticket_id = int(
        query.data.split("_")[1]
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT customer_id, status
        FROM support_messages
        WHERE id = ?
        """,
        (ticket_id,)
    )

    ticket = cursor.fetchone()

    if ticket is None:

        conn.close()

        await query.message.reply_text(
            "❌ Ticket not found."
        )
        return

    customer_id, current_status = ticket

    if current_status != "Closed":

        conn.close()

        await query.message.reply_text(
            "ℹ️ Only closed tickets can be reopened."
        )
        return

    cursor.execute(
        """
        UPDATE support_messages
        SET status = ?
        WHERE id = ?
        """,
        ("Open", ticket_id)
    )

    conn.commit()
    conn.close()

    # Notify customer
    notification = f"""
🔓 SUPPORT TICKET REOPENED

Your support ticket #{ticket_id}
has been reopened.

━━━━━━━━━━━━━━━━━━

The store will continue helping
you with your request. 💬

Thank you for your patience. 🙏
"""

    await notify_support_customer(
        context,
        customer_id,
        ticket_id,
        notification
    )

    await query.message.reply_text(
        f"""
🔓 TICKET REOPENED

🎫 Ticket #{ticket_id}

The support ticket is now open again. 📩

The customer has been notified.
"""
    )


#------------------------------------------------------------
# NOTIFY SUPPORT CUSTOMER
#------------------------------------------------------------
async def notify_support_customer(
    context,
    customer_id,
    ticket_id,
    message
):

    try:

        await context.bot.send_message(
            chat_id=customer_id,
            text=message
        )

        print(
            f"✅ Support notification sent "
            f"to customer {customer_id}"
        )

    except Exception as error:

        print(
            f"❌ Could not send support notification: "
            f"{error}"
        )

#------------------------------------------------------------
# SUPPORT STASTICS
#------------------------------------------------------------
async def support_statistics(update, context):

    # Only admin can use support statistics
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ You are not authorized."
        )
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Total tickets
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        """
    )

    total_tickets = cursor.fetchone()[0]

    # Open tickets
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        WHERE status = ?
        """,
        ("Open",)
    )

    open_tickets = cursor.fetchone()[0]

    # Replied tickets
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        WHERE status = ?
        """,
        ("Replied",)
    )

    replied_tickets = cursor.fetchone()[0]

    # Closed tickets
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        WHERE status = ?
        """,
        ("Closed",)
    )

    closed_tickets = cursor.fetchone()[0]

    # Unique customers
    cursor.execute(
        """
        SELECT COUNT(DISTINCT customer_id)
        FROM support_messages
        """
    )

    unique_customers = cursor.fetchone()[0]

    # Tickets created today
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        WHERE DATE(created_at) = DATE('now')
        """
    )

    tickets_today = cursor.fetchone()[0]

    # Recent tickets
    cursor.execute(
        """
        SELECT id, customer_name, status, created_at
        FROM support_messages
        ORDER BY id DESC
        LIMIT 5
        """
    )

    recent_tickets = cursor.fetchall()

    conn.close()

    message = f"""
📊 SUPPORT ANALYTICS

━━━━━━━━━━━━━━━━━━

📋 TOTAL TICKETS
{total_tickets}

🔴 OPEN
{open_tickets}

🟡 REPLIED
{replied_tickets}

🟢 CLOSED
{closed_tickets}

━━━━━━━━━━━━━━━━━━

👥 UNIQUE CUSTOMERS
{unique_customers}

📩 TICKETS TODAY
{tickets_today}

━━━━━━━━━━━━━━━━━━

📌 RECENT ACTIVITY
"""

    if not recent_tickets:

        message += "\nNo support activity yet. 📭"

    else:

        for ticket in recent_tickets:

            ticket_id, customer_name, status, created_at = ticket

            message += (
                f"\n🎫 Ticket #{ticket_id}\n"
                f"👤 {customer_name}\n"
                f"📌 {status}\n"
                f"🕐 {created_at}\n"
            )

    await update.message.reply_text(message)

#-----------------------------------------------------------
# SUPPORT STASTICS BUTTON
#----------------------------------------------------------
async def support_statistics_button(update, context):

    query = update.callback_query

    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )
        return

    await query.answer()

    conn = get_connection()
    cursor = conn.cursor()

    # Total
    cursor.execute(
        "SELECT COUNT(*) FROM support_messages"
    )

    total_tickets = cursor.fetchone()[0]

    # Open
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        WHERE status = ?
        """,
        ("Open",)
    )

    open_tickets = cursor.fetchone()[0]

    # Replied
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        WHERE status = ?
        """,
        ("Replied",)
    )

    replied_tickets = cursor.fetchone()[0]

    # Closed
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        WHERE status = ?
        """,
        ("Closed",)
    )

    closed_tickets = cursor.fetchone()[0]

    # Unique customers
    cursor.execute(
        """
        SELECT COUNT(DISTINCT customer_id)
        FROM support_messages
        """
    )

    unique_customers = cursor.fetchone()[0]

    # Today
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM support_messages
        WHERE DATE(created_at) = DATE('now')
        """
    )

    tickets_today = cursor.fetchone()[0]

    conn.close()

    message = f"""
📊 SUPPORT ANALYTICS

━━━━━━━━━━━━━━━━━━

📋 TOTAL TICKETS
{total_tickets}

🔴 OPEN
{open_tickets}

🟡 REPLIED
{replied_tickets}

🟢 CLOSED
{closed_tickets}

━━━━━━━━━━━━━━━━━━

👥 UNIQUE CUSTOMERS
{unique_customers}

📩 TICKETS TODAY
{tickets_today}

━━━━━━━━━━━━━━━━━━

📈 SUPPORT PERFORMANCE

Open Rate:
{(open_tickets / total_tickets * 100) if total_tickets else 0:.1f}%

Closed Rate:
{(closed_tickets / total_tickets * 100) if total_tickets else 0:.1f}%
"""

    await query.message.reply_text(message)

#---------------------------------------------------------
# MY SUPPORT TICKETS
#---------------------------------------------------------
async def my_support_tickets(update, context):

    user_id = update.effective_user.id

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            message,
            status,
            created_at
        FROM support_messages
        WHERE customer_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    )

    tickets = cursor.fetchall()

    conn.close()

    if not tickets:

        await update.message.reply_text(
            """
📩 MY SUPPORT TICKETS

You don't have any support
tickets yet. 📭

If you need help, choose:

📞 Contact Store
"""
        )

        return

    message = """
📩 MY SUPPORT TICKETS

Here are your support tickets:

"""

    keyboard = []

    for ticket in tickets:

        ticket_id, ticket_message, status, created_at = ticket

        preview = ticket_message[:45]

        if len(ticket_message) > 45:
            preview += "..."

        message += (
            f"🎫 Ticket #{ticket_id}\n"
            f"💬 {preview}\n"
            f"📌 Status: {status}\n"
            f"🕐 {created_at}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"👁️ View Ticket #{ticket_id}",
                callback_data=f"customersupport_{ticket_id}"
            )
        ])

    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

#----------------------------------------------------------
# CUSTOMER SUPPORT TICKET DETAILS
#----------------------------------------------------------
async def customer_support_ticket_detail(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    ticket_id = int(
        query.data.split("_")[1]
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            customer_name,
            message,
            admin_reply,
            status,
            created_at,
            replied_at
        FROM support_messages
        WHERE id = ?
        AND customer_id = ?
        """,
        (ticket_id, user_id)
    )

    ticket = cursor.fetchone()

    if ticket is None:
        conn.close()

        await query.message.reply_text(
            "❌ Ticket not found."
        )

        return

    customer_name, original_message, admin_reply, status, created_at, replied_at = ticket


    # ⭐ NEW CODE STARTS HERE

    cursor.execute(
        """
        SELECT
            sender_type,
            message,
            created_at
        FROM support_replies
        WHERE support_message_id = ?
        ORDER BY id ASC
        """,
        (ticket_id,)
    )

    conversation = cursor.fetchall()

    # ⭐ NEW CODE ENDS HERE


    conn.close()


    message = f"""
🎫 SUPPORT TICKET #{ticket_id}

👤 Customer:
{customer_name}

📌 Status:
{status}
"""


    # ⭐ NEW CONVERSATION DISPLAY

    message += """

━━━━━━━━━━━━━━━━━━

💬 CONVERSATION:
"""

    if conversation:

        for sender_type, reply_text, created_at in conversation:

            if sender_type == "Customer":

                message += (
                    f"\n👤 YOU\n"
                    f"{reply_text}\n"
                    f"🕐 {created_at}\n"
                )

            else:

                message += (
                    f"\n👨‍💼 STORE\n"
                    f"{reply_text}\n"
                    f"🕐 {created_at}\n"
                )

    else:

        message += "\nNo conversation messages yet."


    keyboard = []

    if status != "Closed":

        keyboard.append([
            InlineKeyboardButton(
                "💬 Reply to Ticket",
                callback_data=f"customerreply_{ticket_id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "⬅️ Back to My Tickets",
            callback_data="customersupport_back"
        )
    ])

    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

#----------------------------------------------------------
# CUSTOMER SUPPORT BACK
#-----------------------------------------------------------
async def customer_support_back(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            message,
            status,
            created_at
        FROM support_messages
        WHERE customer_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    )

    tickets = cursor.fetchall()

    conn.close()

    if not tickets:

        await query.message.reply_text(
            "📩 You don't have any support tickets."
        )

        return

    message = """
📩 MY SUPPORT TICKETS

Your previous support tickets:

"""

    keyboard = []

    for ticket in tickets:

        ticket_id, ticket_message, status, created_at = ticket

        preview = ticket_message[:45]

        if len(ticket_message) > 45:
            preview += "..."

        message += (
            f"🎫 Ticket #{ticket_id}\n"
            f"💬 {preview}\n"
            f"📌 {status}\n"
            f"🕐 {created_at}\n\n"
        )

        keyboard.append([
            InlineKeyboardButton(
                f"👁️ View Ticket #{ticket_id}",
                callback_data=f"customersupport_{ticket_id}"
            )
        ])

    await query.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

#------------------------------------------------------------
# SAVE SUPPORT REPLY
#------------------------------------------------------------
def save_support_reply(
    support_message_id,
    sender_type,
    sender_id,
    message
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO support_replies (
            support_message_id,
            sender_type,
            sender_id,
            message
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            support_message_id,
            sender_type,
            sender_id,
            message
        )
    )

    conn.commit()
    conn.close()

#------------------------------------------------------------
# CUSTOMER REPLY BUTTON
#-----------------------------------------------------------
async def customer_reply_button(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    ticket_id = int(
        query.data.split("_")[1]
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT status
        FROM support_messages
        WHERE id = ?
        AND customer_id = ?
        """,
        (ticket_id, user_id)
    )

    ticket = cursor.fetchone()

    conn.close()

    if ticket is None:

        await query.message.reply_text(
            "❌ Ticket not found."
        )
        return

    status = ticket[0]

    if status == "Closed":

        await query.message.reply_text(
            """
🔒 This ticket is closed.

Please contact the store again
if you have a new problem.
"""
        )
        return

    context.user_data[
        "customer_support_reply_ticket"
    ] = ticket_id

    await query.message.reply_text(
        f"""
💬 REPLY TO SUPPORT TICKET

🎫 Ticket #{ticket_id}

Please type your message:

"""
    )

#-----------------------------------------------------------
# SEND CUSTOMER SUPPORT REPLY
#-----------------------------------------------------------
async def send_customer_support_reply(
    update,
    context
):

    # Get the customer's Telegram ID
    user_id = update.effective_user.id

    # Get the support ticket ID
    ticket_id = context.user_data.get(
        "customer_support_reply_ticket"
    )

    # Check if a ticket was selected
    if not ticket_id:

        await update.message.reply_text(
            "❌ No support ticket selected."
        )

        return

    # Get the customer's message
    message_text = update.message.text.strip()

    # Check if message is empty
    if not message_text:

        await update.message.reply_text(
            "❌ Your message cannot be empty."
        )

        return

    # Connect to database
    conn = get_connection()
    cursor = conn.cursor()

    # Check that this ticket belongs to this customer
    cursor.execute(
        """
        SELECT status
        FROM support_messages
        WHERE id = ?
        AND customer_id = ?
        """,
        (ticket_id, user_id)
    )

    ticket = cursor.fetchone()

    conn.close()

    # Ticket does not exist
    if ticket is None:

        await update.message.reply_text(
            "❌ Support ticket not found."
        )

        context.user_data.pop(
            "customer_support_reply_ticket",
            None
        )

        return

    # Get ticket status
    status = ticket[0]

    # Customer cannot reply to closed ticket
    if status == "Closed":

        await update.message.reply_text(
            "🔒 This ticket is already closed."
        )

        context.user_data.pop(
            "customer_support_reply_ticket",
            None
        )

        return

    # ==========================================
    # SAVE CUSTOMER MESSAGE
    # ==========================================

    save_support_reply(
        ticket_id,
        "Customer",
        user_id,
        message_text
    )

    # ==========================================
    # CHANGE TICKET STATUS TO OPEN
    # ==========================================

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE support_messages
        SET status = ?
        WHERE id = ?
        """,
        ("Open", ticket_id)
    )

    conn.commit()
    conn.close()

    # ==========================================
    # TELL CUSTOMER
    # ==========================================

    await update.message.reply_text(
        f"""
✅ MESSAGE SENT

🎫 Ticket #{ticket_id}

Your message has been sent
to the store.

The store will reply soon. 💬
"""
    )

    # ==========================================
    # CREATE ADMIN BUTTONS
    # ==========================================

    keyboard = [
        [
            InlineKeyboardButton(
                "💬 REPLY TO TICKET",
                callback_data=f"ticketreply_{ticket_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👁️ VIEW TICKET",
                callback_data=f"viewsupport_{ticket_id}"
            )
        ]
    ]

    # ==========================================
    # NOTIFY ADMIN
    # ==========================================

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"""
📩 CUSTOMER REPLIED

🎫 Ticket #{ticket_id}

🆔 Customer ID:
{user_id}

━━━━━━━━━━━━━━━━━━

💬 MESSAGE:

{message_text}

━━━━━━━━━━━━━━━━━━

📌 Status:
Open
""",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )

    # ==========================================
    # CLEAR SELECTED TICKET
    # ==========================================

    context.user_data.pop(
        "customer_support_reply_ticket",
        None
    )
  
#-----------------------------------------------------------
# PRIORITY LABEL
#-----------------------------------------------------------
def priority_label(priority):

    if priority == "High":
        return "🔴 HIGH"

    elif priority == "Medium":
        return "🟡 MEDIUM"

    elif priority == "Low":
        return "🟢 LOW"

    return "🟡 MEDIUM"
#-------------------------------------------------------------
# GET SLA HOURS
#-------------------------------------------------------------
def get_sla_hours(priority):

    if priority == "High":
        return 1

    elif priority == "Medium":
        return 4

    elif priority == "Low":
        return 24

    return 4
#-------------------------------------------------------------
# CALCULATE TICKET SLA
#-------------------------------------------------------------
def calculate_ticket_sla(
    priority,
    created_at
):

    try:

        created_time = datetime.strptime(
            created_at,
            "%Y-%m-%d %H:%M:%S"
        )

        current_time = datetime.now()

        waiting_seconds = (
            current_time - created_time
        ).total_seconds()

        waiting_hours = (
            waiting_seconds / 3600
        )

        sla_hours = get_sla_hours(
            priority
        )

        if waiting_hours > sla_hours:

            return (
                f"🚨 OVERDUE\n"
                f"⏱️ Waiting: "
                f"{waiting_hours:.1f} hours\n"
                f"🎯 Target: "
                f"{sla_hours} hour(s)"
            )

        else:

            remaining_hours = (
                sla_hours - waiting_hours
            )

            return (
                f"⏱️ Waiting: "
                f"{waiting_hours:.1f} hours\n"
                f"🟢 Within SLA\n"
                f"🎯 Remaining: "
                f"{remaining_hours:.1f} hours"
            )

    except Exception:

        return "⏱️ SLA information unavailable."

# ----------------------------------------------------------
# SET TICKET PRIORITY
# ---------------------------------------------------------
async def set_ticket_priority(update, context):

    query = update.callback_query

    await query.answer()

    # Only admin can change priority
    if query.from_user.id != ADMIN_ID:

        await query.answer(
            "❌ You are not authorized.",
            show_alert=True
        )

        return

    # Example:
    # priority_15_High

    parts = query.data.split("_", 2)

    ticket_id = int(parts[1])

    new_priority = parts[2]

    # Make sure priority is valid
    if new_priority not in [
        "High",
        "Medium",
        "Low"
    ]:

        await query.message.reply_text(
            "❌ Invalid priority."
        )

        return

    # Update database
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE support_messages
        SET priority = ?
        WHERE id = ?
        """,
        (
            new_priority,
            ticket_id
        )
    )

    conn.commit()
    conn.close()

    await query.message.reply_text(
        f"""
✅ PRIORITY UPDATED

🎫 Ticket #{ticket_id}

📌 New Priority:
{priority_label(new_priority)}
"""
    )



# ============================================================
# 31. MAIN PROGRAM
# ============================================================

def main():

    app = (
        Application
        .builder()
        .token(TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(30.0)
        .build()
    )

    #--------------------------------------------------------
    # CHECKOUT CONVERSATION
    #--------------------------------------------------------
    checkout_conversation = ConversationHandler(

    entry_points=[

        # Old keyboard checkout button
        MessageHandler(
            filters.Regex("^🛒 Checkout$"),
            checkout_start
        ),

        # New inline checkout button
        CallbackQueryHandler(
            checkout_button,
            pattern="^checkout$"
        )
    ],

    states={
        NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                get_name
            )
        ],

        PHONE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                get_phone
            )
        ],

        LOCATION: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                get_location
            )
        ],

        PAYMENT: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                get_payment_reference
            )
        ]
    },

    fallbacks=[],
    per_message=False
)
    app.add_handler(checkout_conversation)

    #------------------------------------------------------
    # SUPPORT CONVERSATION
    #------------------------------------------------------
    support_conversation = ConversationHandler(

    entry_points=[
        MessageHandler(
            filters.Regex(
                "^📞 Contact Store$"
            ),
            contact_store
        )
    ],

    states={

        SUPPORT: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                receive_customer_message
            )
        ]

    },

    fallbacks=[]
)
    app.add_handler(
    support_conversation
)


    # --------------------------------------------------------
    # BASIC COMMANDS
    # --------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    app.add_handler(
        CommandHandler(
            "myid",
            my_id
        )
    )
    app.add_handler(
    CallbackQueryHandler(
        increase_quantity,
        pattern="^increase_"
    )
)

    app.add_handler(
    CallbackQueryHandler(
        decrease_quantity,
        pattern="^decrease_"
    )
)

    app.add_handler(
    CallbackQueryHandler(
        remove_from_cart,
        pattern="^remove_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        nothing_button,
        pattern="^nothing$"
    )
)
    app.add_handler(
    CommandHandler(
        "orders",
        orders
    )
)
    app.add_handler(
    CallbackQueryHandler(
        show_filtered_orders,
        pattern="^orders_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        view_order,
        pattern="^vieworder_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        customer_order_detail,
        pattern="^customerorder_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        show_order_tracking,
        pattern="^trackorder_"
    )
)  


    # --------------------------------------------------------
    # CHECKOUT CONVERSATION
    # --------------------------------------------------------
    
    # --------------------------------------------------------
    # PRODUCT BUTTONS
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            add_to_cart,
            pattern="^add_"
        )
    )


    # --------------------------------------------------------
    # ADMIN PAYMENT BUTTONS
    # --------------------------------------------------------

    app.add_handler(
        CallbackQueryHandler(
            verify_payment,
            pattern="^verify_"
        )
    )


    app.add_handler(
        CallbackQueryHandler(
            reject_payment,
            pattern="^reject_"
        )
    )
    #--------------------------------------------------------
    # REGISTER
    #--------------------------------------------------------
    app.add_handler(
    CallbackQueryHandler(
        show_status_options,
        pattern="^status_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        set_order_status,
        pattern="^setstatus_"
    )
)
    
    


    # --------------------------------------------------------
    # ADMIN COMMANDS
    # --------------------------------------------------------

    app.add_handler(
        CommandHandler(
            "admin",
            admin_panel
        )
    )


    app.add_handler(
        CommandHandler(
            "orders",
            orders
        )
    )


    app.add_handler(
        CommandHandler(
            "pending",
            show_pending_payments
        )
    )
    app.add_handler(
    CallbackQueryHandler(
        support_reply_button,
        pattern="^supportreply_"
    )
)
    app.add_handler(
    CommandHandler(
        "support",
        support_inbox
    )
)
    app.add_handler(
    CommandHandler(
        "support_stats",
        support_statistics
    )
)    
    app.add_handler(
    CallbackQueryHandler(
        show_support_tickets,
        pattern="^support_(open|replied|closed|all)$"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        view_support_ticket,
        pattern="^viewsupport_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        ticket_reply_button,
        pattern="^ticketreply_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        close_support_ticket,
        pattern="^closeticket_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        reopen_support_ticket,
        pattern="^reopenticket_"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        support_statistics_button,
        pattern="^support_statistics$"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        customer_support_ticket_detail,
        pattern="^customersupport_[0-9]+$"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        customer_support_back,
        pattern="^customersupport_back$"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        customer_reply_button,
        pattern="^customerreply_[0-9]+$"
    )
)
    app.add_handler(
    CallbackQueryHandler(
        set_ticket_priority,
        pattern="^priority_[0-9]+_(High|Medium|Low)$"
    )
)
    

    # --------------------------------------------------------
    # CUSTOMER MENU
    # --------------------------------------------------------

    app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        route_text_message
    )
)


    # --------------------------------------------------------
    # START BOT
    # --------------------------------------------------------

    print("🤖 Store Bot is running...")


    app.run_polling()


# ============================================================
# 32. RUN
# ============================================================

if __name__ == "__main__":

    main()