from flask import Flask, request
from telebot import TeleBot, types
import os
from datetime import datetime

# ===========================
#   Bot setup
# ===========================
TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
ADMIN_ID = 6497093715
bot = TeleBot(TOKEN)

# ===========================
#   Data structures
# ===========================
user_state = {}  # memorizza stato utente per back
user_cart = {}   # memorizza carrello per utente

# Prodotto e prezzi
PRODUCTS = {
    "Zafferano": {
        "base_price": 8,
        "discounts": {30: 0.10, 50: 0.15, 70: 0.20, 100: 0.25},  # percentuali sconto
        "options": [1,3,5,10,30,50,70,100]
    }
}

# ===========================
#   Helper functions
# ===========================
def get_price(product, qty):
    base = PRODUCTS[product]["base_price"]
    discount = 0
    for q, d in sorted(PRODUCTS[product]["discounts"].items()):
        if qty >= q:
            discount = d
    return round(base * qty * (1-discount),2)

def show_main_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 Shop", callback_data="shop"))
    markup.add(types.InlineKeyboardButton("🛍 Cart", callback_data="cart"))
    markup.add(types.InlineKeyboardButton("ℹ️ Info", callback_data="info"))
    markup.add(types.InlineKeyboardButton("📞 Contacts", callback_data="contacts"))
    bot.send_message(chat_id, "👋 Welcome! Choose an option:", reply_markup=markup)
    user_state[chat_id] = "main"

def show_shop(chat_id):
    markup = types.InlineKeyboardMarkup()
    for product in PRODUCTS:
        markup.add(types.InlineKeyboardButton(product, callback_data=f"product_{product}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back"))
    bot.send_message(chat_id, "Select a product:", reply_markup=markup)
    user_state[chat_id] = "shop"

def show_quantity(chat_id, product):
    markup = types.InlineKeyboardMarkup()
    for qty in PRODUCTS[product]["options"]:
        price = get_price(product, qty)
        markup.add(types.InlineKeyboardButton(f"{qty}g - {price}€", callback_data=f"qty_{product}_{qty}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="shop"))
    bot.send_message(chat_id, f"Select quantity for {product}:", reply_markup=markup)
    user_state[chat_id] = f"quantity_{product}"

def show_cart(chat_id):
    cart = user_cart.get(chat_id, [])
    if not cart:
        bot.send_message(chat_id, "🛒 Your cart is empty!")
    else:
        text = "🛒 Your cart:\n"
        total = 0
        for item in cart:
            price = get_price(item['product'], item['qty'])
            total += price
            text += f"{item['product']} {item['qty']}g - {price}€\n"
        text += f"\n💰 Total: {round(total,2)}€"
        bot.send_message(chat_id, text)
    user_state[chat_id] = "cart"

def show_info(chat_id):
    text = "ℹ️ Info:\nThis is a professional bot for ordering Zafferano with multiple payment options."
    bot.send_message(chat_id, text)
    user_state[chat_id] = "info"

def show_contacts(chat_id):
    text = "📞 Contacts:\nAdmin Telegram: @ChristianMadafferi\nEmail: example@mail.com"
    bot.send_message(chat_id, text)
    user_state[chat_id] = "contacts"

# ===========================
#   Bot commands
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    show_main_menu(message.chat.id)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "📖 Available commands:\n/start - Start bot\n/help - Show commands\n/cart - Show cart\n/info - Bot info\n/contacts - Contact info")

@bot.message_handler(commands=['cart'])
def cart_command(message):
    show_cart(message.chat.id)

@bot.message_handler(commands=['info'])
def info_command(message):
    show_info(message.chat.id)

@bot.message_handler(commands=['contacts'])
def contacts_command(message):
    show_contacts(message.chat.id)

# ===========================
#   Callback query handler
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    data = call.data

    # ----- Navigation -----
    if data == "shop":
        show_shop(chat_id)
    elif data == "cart":
        show_cart(chat_id)
    elif data == "info":
        show_info(chat_id)
    elif data == "contacts":
        show_contacts(chat_id)
    elif data == "back":
        # Return to previous state
        prev_state = user_state.get(chat_id, "main")
        if prev_state.startswith("quantity_"):
            show_shop(chat_id)
        else:
            show_main_menu(chat_id)

    # ----- Shop -----
    elif data.startswith("product_"):
        product = data.split("_")[1]
        show_quantity(chat_id, product)

    # ----- Quantity selection -----
    elif data.startswith("qty_"):
        parts = data.split("_")
        product = parts[1]
        qty = int(parts[2])
        if chat_id not in user_cart:
            user_cart[chat_id] = []
        user_cart[chat_id].append({"product": product, "qty": qty})
        price = get_price(product, qty)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot.send_message(chat_id, f"✅ Added {product} {qty}g - {price}€ to cart at {now}")
        show_shop(chat_id)

# ===========================
#   Flask server
# ===========================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

@app.route("/", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# ===========================
#   Set Telegram webhook
# ===========================
WEBHOOK_URL = "https://telegram-bot-sohm.onrender.com"
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# ===========================
#   Run Flask server
# ===========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)