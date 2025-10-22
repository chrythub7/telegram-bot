from flask import Flask, request
from telebot import TeleBot, types
import os

# ===========================
#   BOT CONFIG
# ===========================
TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
ADMIN_ID = 6497093715
PAYPAL_LINK = "https://paypal.me/ChristianMadafferi?locale.x=it_IT&country.x=IT"
WEBHOOK_URL = "https://telegram-bot-sohm.onrender.com"

bot = TeleBot(TOKEN)
app = Flask(__name__)

# ===========================
#   FAKE DATABASE (products)
# ===========================
PRODUCTS = {
    "Erba": [
        {"name": "Amnesia Haze CBD", "price": 12, "desc": "Aroma forte e agrumato, CBD 14%"},
        {"name": "Gorilla Glue CBD", "price": 14, "desc": "Note terrose e dolci, CBD 18%"},
    ],
    "Olio": [
        {"name": "Olio 10% CBD", "price": 30, "desc": "Ideale per rilassamento quotidiano"},
        {"name": "Olio 20% CBD", "price": 50, "desc": "Alta concentrazione per uso intenso"},
    ],
    "Resina": [
        {"name": "Charas CBD", "price": 15, "desc": "Morbida e profumata, CBD 20%"},
        {"name": "Pollen Hash", "price": 13, "desc": "Aroma naturale e leggero, CBD 16%"},
    ]
}

# ===========================
#   BOT COMMANDS
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍️ Ordina", "ℹ️ Info", "📞 Contatti")
    bot.send_message(
        message.chat.id,
        "👋 Benvenuto nel bot!\nScegli un'opzione dal menu qui sotto 👇",
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(
        message,
        "📖 Comandi disponibili:\n"
        "/start - Riavvia il bot\n"
        "/help - Mostra questo messaggio\n"
        "/ordina - Inizia un ordine"
    )

@bot.message_handler(commands=['ordina'])
def ordina(message):
    send_categories(message)

@bot.message_handler(func=lambda msg: msg.text == "🛍️ Ordina")
def order_from_menu(message):
    send_categories(message)

def send_categories(message):
    markup = types.InlineKeyboardMarkup()
    for category in PRODUCTS.keys():
        markup.add(types.InlineKeyboardButton(category, callback_data=f"cat_{category}"))
    bot.send_message(
        message.chat.id,
        "📦 Scegli una categoria di prodotti:",
        reply_markup=markup
    )

# ===========================
#   CALLBACKS
# ===========================
@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def show_products(call):
    category = call.data.replace("cat_", "")
    markup = types.InlineKeyboardMarkup()
    for prod in PRODUCTS[category]:
        markup.add(types.InlineKeyboardButton(
            f"{prod['name']} - €{prod['price']}",
            callback_data=f"prod_{category}_{prod['name']}"
        ))
    bot.edit_message_text(
        f"📂 *{category}* – scegli un prodotto:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("prod_"))
def show_product_details(call):
    _, category, name = call.data.split("_", 2)
    product = next(p for p in PRODUCTS[category] if p["name"] == name)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💸 Acquista ora", url=PAYPAL_LINK),
        types.InlineKeyboardButton("⬅️ Indietro", callback_data=f"cat_{category}")
    )

    bot.edit_message_text(
        f"🛒 *{product['name']}*\n💰 Prezzo: €{product['price']}\n🧾 {product['desc']}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ===========================
#   PAYPAL WEBHOOK (optional)
# ===========================
@app.route("/paypal-webhook", methods=["POST"])
def paypal_webhook():
    data = request.json
    if data.get('event_type') == 'PAYMENT.CAPTURE.COMPLETED':
        payer_email = data['resource']['payer']['email_address']
        amount = data['resource']['amount']['value']
        currency = data['resource']['amount']['currency_code']
        bot.send_message(ADMIN_ID, f"✅ Pagamento ricevuto!\n💰 {amount} {currency}\n📧 {payer_email}")
    return "OK", 200

# ===========================
#   FLASK ROUTES
# ===========================
@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

@app.route("/", methods=["POST"])
def telegram_webhook():
    update = types.Update.de_json(request.get_json())
    bot.process_new_updates([update])
    return "OK", 200

# ===========================
#   SETUP WEBHOOK
# ===========================
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))