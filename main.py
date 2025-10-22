from flask import Flask, request
from telebot import TeleBot, types
import os

# ===========================
#   BOT SETUP
# ===========================
TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
ADMIN_ID = 6497093715
bot = TeleBot(TOKEN)

# ===========================
#   PRODUCT DATA
# ===========================
PRODUCTS = {
    "Saffron": {
        "1g": {"price": 8, "discount": 0},
        "3g": {"price": 24, "discount": 0},
        "5g": {"price": 40, "discount": 0},
        "10g": {"price": 80, "discount": 0},
        "30g": {"price": 216, "discount": 10},
        "50g": {"price": 340, "discount": 15},
        "70g": {"price": 448, "discount": 20},
        "100g": {"price": 600, "discount": 25}
    }
}

USER_CART = {}

# ===========================
#   COMMANDS
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🛍 Shop", "🛒 Cart")
    markup.row("ℹ️ Info", "📞 Contacts")
    bot.send_message(message.chat.id, "👋 Welcome! Choose an option below:", reply_markup=markup)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "📖 Commands:\n/start - Main menu\n/info - Product info\n/cart - View cart\n/contacts - Contact admin")

@bot.message_handler(commands=['info'])
def info_command(message):
    info = "🌿 *Saffron Pricing List:*\n\n"
    for grams, data in PRODUCTS["Saffron"].items():
        price = data["price"]
        discount = data["discount"]
        if discount > 0:
            info += f"• {grams} – {price}€  _(−{discount}% discount)_\n"
        else:
            info += f"• {grams} – {price}€\n"
    info += "\n100% pure Italian saffron 🇮🇹"
    bot.send_message(message.chat.id, info, parse_mode="Markdown")

@bot.message_handler(commands=['contacts'])
def contacts_command(message):
    contact_text = (
        "📞 *Contact Info:*\n\n"
        "👤 Admin: @ChristianMadafferi\n"
        "✉️ Email: example@email.com\n"
        "💬 For questions, message the admin directly."
    )
    bot.send_message(message.chat.id, contact_text, parse_mode="Markdown")

@bot.message_handler(commands=['cart'])
def view_cart_cmd(message):
    show_cart(message.chat.id, message.from_user.id)

# ===========================
#   SHOPPING FLOW
# ===========================
@bot.message_handler(func=lambda m: m.text == "🛍 Shop")
def open_shop(message):
    markup = types.InlineKeyboardMarkup()
    for product in PRODUCTS.keys():
        markup.add(types.InlineKeyboardButton(text=product, callback_data=f"product_{product}"))
    bot.send_message(message.chat.id, "🛍 Choose a product:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("product_"))
def choose_quantity(call):
    product = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup()
    for grams, data in PRODUCTS[product].items():
        label = f"{grams} ({data['price']}€"
        if data['discount'] > 0:
            label += f" -{data['discount']}%)"
        else:
            label += ")"
        markup.add(types.InlineKeyboardButton(text=label, callback_data=f"add_{product}_{grams}"))
    markup.add(types.InlineKeyboardButton(text="⬅️ Back", callback_data="back_main"))
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Select quantity for *{product}:*",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
def add_to_cart(call):
    _, product, grams = call.data.split("_")
    price = PRODUCTS[product][grams]["price"]

    if call.from_user.id not in USER_CART:
        USER_CART[call.from_user.id] = []

    USER_CART[call.from_user.id].append({"product": product, "quantity": grams, "price": price})

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="🛒 View Cart", callback_data="view_cart"))
    markup.add(types.InlineKeyboardButton(text="🛍 Continue Shopping", callback_data="continue_shop"))
    markup.add(types.InlineKeyboardButton(text="⬅️ Back to Menu", callback_data="back_main"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"✅ Added *{grams}* of *{product}* to your cart.",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "view_cart")
def view_cart(call):
    show_cart(call.message.chat.id, call.from_user.id)

def show_cart(chat_id, user_id):
    if user_id not in USER_CART or len(USER_CART[user_id]) == 0:
        bot.send_message(chat_id, "🛒 Your cart is empty.")
        return

    cart_items = USER_CART[user_id]
    total = sum(item["price"] for item in cart_items)
    text = "🛍 *Your Cart:*\n\n"
    for item in cart_items:
        text += f"- {item['product']} {item['quantity']} → {item['price']}€\n"
    text += f"\n💰 *Total:* {total:.2f}€"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💸 Proceed to Payment", callback_data="checkout"))
    markup.add(types.InlineKeyboardButton(text="🧹 Clear Cart", callback_data="clear_cart"))
    markup.add(types.InlineKeyboardButton(text="⬅️ Back", callback_data="back_main"))

    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "clear_cart")
def clear_cart(call):
    USER_CART[call.from_user.id] = []
    bot.send_message(call.message.chat.id, "🧹 Cart cleared.")

@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def checkout(call):
    user_id = call.from_user.id
    cart = USER_CART.get(user_id, [])
    total = sum(item["price"] for item in cart)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="💳 PayPal", callback_data="pay_paypal"))
    markup.add(types.InlineKeyboardButton(text="💸 Revolut", callback_data="pay_revolut"))
    markup.add(types.InlineKeyboardButton(text="🏦 Bank Transfer", callback_data="pay_bank"))
    markup.add(types.InlineKeyboardButton(text="⬅️ Back", callback_data="back_main"))

    bot.send_message(
        call.message.chat.id,
        f"💰 *Total:* {total:.2f}€\nChoose your payment method:",
        parse_mode="Markdown",
        reply_markup=markup
    )

# ===========================
#   PAYMENT METHODS
# ===========================
def notify_admin(user, method):
    cart = USER_CART.get(user.id, [])
    total = sum(item["price"] for item in cart)
    order_details = "\n".join([f"- {i['product']} {i['quantity']} → {i['price']}€" for i in cart])

    bot.send_message(
        ADMIN_ID,
        f"🛒 *New Order!*\n\n"
        f"👤 User: @{user.username or 'No username'} (ID: {user.id})\n"
        f"💰 Total: {total:.2f}€\n"
        f"💳 Payment Method: {method}\n\n"
        f"📦 Items:\n{order_details}",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def payment_selected(call):
    method = call.data.split("_")[1]
    notify_admin(call.from_user, method)

    if method == "paypal":
        text = "💳 *Pay via PayPal:*\nhttps://paypal.me/ChristianMadafferi"
    elif method == "revolut":
        text = "💸 *Pay via Revolut:*\nUsername: @christianmadafferi\nPhone: +39XXXXXXXXXX"
    else:
        text = "🏦 *Bank Transfer:*\nIBAN: IT00A000000000000000000000\nName: Christian Madafferi\nReason: Saffron Purchase"

    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_main")
def back_main(call):
    start(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "continue_shop")
def continue_shop(call):
    open_shop(call.message)

# ===========================
#   FLASK SERVER
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
#   WEBHOOK
# ===========================
WEBHOOK_URL = "https://telegram-bot-sohm.onrender.com"
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# ===========================
#   RUN FLASK
# ===========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)