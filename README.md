# 🛍️ Telegram Store & Support Bot

A feature-complete, production-ready Telegram Store Bot built with Python and SQLite. Includes full e-commerce checkout logic, real-time inventory and stock protection, an admin order management dashboard, and an integrated customer support ticketing system with full conversation history.

---

## ✨ Features

### 🛒 E-Commerce & Checkout
* Interactive Catalog & Cart: Browsable products with real-time cart management.
* Stock Protection: Automatic pre-checkout validation (validate_cart_stock) to prevent overselling.
* Order Status Tracking: Customers receive instant notification updates on payment verification and fulfillment.

### 🛠️ Admin Dashboard
* **Order Management (/orders): View, filter, and process incoming store orders directly from Telegram.
* Automatic Stock Restoration: Order cancellations dynamically restore reserved items back into the database inventory.

### 💬 Support Ticket System
* Ticketing Desk: Customers can open support tickets and view full multi-turn conversation logs.
* Admin Ticket Desk:** Support staff can view tickets, reply directly to users, mark ticket priority, or toggle ticket status (Open/Closed/Reopened).

---

## 📁 Project Structure

```text
store-bot/
├── data/
│   └── shop.db               # SQLite database (Orders, Products, Tickets, Messages)
├── src/
│   ├── bot.py                # Main Telegram bot application & handler registration
│   ├── update_db.py          # Database schema migration script
│   └── view_orders.py        # Terminal utility for database inspection
├── .env                      # Local environment secrets (ignored by Git)
├── .env.example              # Template for environment variables
├── .gitignore                # Rules for excluding secrets and local data
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
telegram_bot_link=@ethiomullerboutique_store_bot