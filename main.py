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
app = Flask(__name__)

# ===========================
#   Products and prices
# ===========================
PRODUCTS = {
    "zafferano": {
        "1g": 8,
        "3g": 24,
        "5g": 40,
        "10g": 80,
        "30g": 216,   # 10% sconto
        "50g": 320,   # 20% sconto
        "70g": 448,   # 20% sconto
        "100g": 600   # 25% sconto
    }
}

# Cart per utente
user_cart = {}

# ===========================
#   Helper functions
# ===========================
def get_price(product, qty):
    return PRODUCTS[product][qty]

def format_cart(chat_id):
    cart = user_cart.get(chat_id, [])
    if not cart:
        return "🛒 Your cart is empty."
    text = "🛒 Your cart:\n\n"
    total = 0
    for item in cart:
        price = get_price(item['product'], item['qty'])
        text += f"{item['product'].capitalize()} - {item['qty']} - {price}€\n"
        total += price
    text += f"\n💰 Total: {total}€"
    return text

# ===========================
#   Bot commands
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_cart[chat_id] = []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("/shop", "/cart", "/info", "/contacts")
    bot.send_message(chat_id, "👋 Welcome! Choose an option:", reply_markup=markup)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "📖 Available commands:\n/start - Start\n/shop - Shop products\n/cart - View cart\n/info - Info\n/contacts - Contacts")

@bot.message_handler(commands=['shop'])
def shop(message):
    chat_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for qty in PRODUCTS["zafferano"]:
        markup.add(f"{qty}")
    markup.add("Back")
    bot.send_message(chat_id, "Choose zafferano quantity:", reply_markup=markup)

@bot.message_handler(commands=['cart'])
def show_cart(message):
    chat_id = message.chat.id
    text = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    total = sum([get_price(i['product'], i['qty']) for i in user_cart.get(chat_id, [])])
    if total > 0:
        markup.add(types.InlineKeyboardButton("💸 Pay with PayPal", url=f"https://paypal.me/ChristianMadafferi/{total}"))
        markup.add(types.InlineKeyboardButton("🏦 Bank Transfer", callback_data="bank_transfer"))
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['info'])
def info(message):
    chat_id = message.chat.id
    text = "ℹ️ Info:\nThis bot sells high quality zafferano.\nPrices:\n"
    for qty, price in PRODUCTS["zafferano"].items():
        text += f"{qty}: {price}€\n"
    bot.send_message(chat_id, text)

@bot.message_handler(commands=['contacts'])
def contacts(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "📞 Contacts:\nTelegram: @SlyanuS7 \nEmail: brandingshopy@gmail.com \nInstagram: 1.chr_9")

# ===========================
#   Handle quantity selection
# ===========================
@bot.message_handler(func=lambda message: message.text in PRODUCTS["zafferano"] or message.text == "Back")
def select_quantity(message):
    chat_id = message.chat.id
    if message.text == "Back":
        start(message)
        return
    user_cart[chat_id].append({"product": "zafferano", "qty": message.text})
    bot.send_message(chat_id, f"✅ Added {message.text} zafferano to cart.\nUse /cart to view your cart.")

# ===========================
#   Inline callbacks
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    if call.data == "bank_transfer":
        bot.send_message(chat_id, "🏦 Bank Transfer details:\nIBAN: IT62 P036 6901 6003 0102 0417 476 \nBIC: CHASDEFX \nSend the exact amount and then confirm here.")
        bot.answer_callback_query(call.id, "Bank transfer info sent.")

# ===========================
#   Flask server
# ===========================
@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

@app.route("/", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/paypal-webhook", methods=["POST"])
def paypal_webhook():
    data = request.json
    if data.get('event_type') == 'PAYMENT.CAPTURE.COMPLETED':
        payer_email = data['resource']['payer']['email_address']
        amount = data['resource']['amount']['value']
        currency = data['resource']['amount']['currency_code']
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        message = f"✅ Payment received!\n💰 Amount: {amount} {currency}\n📧 From: {payer_email}\n🕒 {now}"
        bot.send_message(ADMIN_ID, message)
    return "OK", 200

# ===========================
#   Set webhook
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