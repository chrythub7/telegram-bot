from flask import Flask, request, jsonify
from telebot import TeleBot, types
import stripe
import os
from datetime import datetime

# ===========================
#   Environment Variables
# ===========================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # Inserisci su Render
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6497093715"))
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")
ENDPOINT_SECRET = os.environ.get("ENDPOINT_SECRET")

# ===========================
#   Setup
# ===========================
bot = TeleBot(TOKEN)
app = Flask(__name__)
stripe.api_key = STRIPE_SECRET_KEY

# ===========================
#   Product List (Zafferano)
# ===========================
PRODUCTS = {
    "Zafferano": {
        "1g": 8,
        "3g": 24,
        "5g": 40,
        "10g": 75,
        "30g": 200,   # Sconto ~17%
        "50g": 310,   # Sconto ~22%
        "70g": 410,   # Sconto ~27%
        "100g": 500   # Sconto ~37%
    }
}

# ===========================
#   User carts (temporary)
# ===========================
user_cart = {}

# ===========================
#   Commands
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛍️ Acquista Zafferano", callback_data="buy_zafferano"))
    markup.add(types.InlineKeyboardButton("🧾 Carrello", callback_data="view_cart"))
    markup.add(types.InlineKeyboardButton("ℹ️ Info", callback_data="info"))
    markup.add(types.InlineKeyboardButton("📞 Contatti", callback_data="contacts"))

    bot.send_message(
        message.chat.id,
        "👋 Benvenuto nel bot ufficiale dello *Zafferano dell’Aquila Premium*!\n\n"
        "Scegli un’opzione qui sotto:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "Comandi disponibili:\n/start - Avvia il bot\n/help - Mostra i comandi\n")

# ===========================
#   Callback Buttons
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id

    if call.data == "buy_zafferano":
        markup = types.InlineKeyboardMarkup()
        for size in PRODUCTS["Zafferano"]:
            price = PRODUCTS["Zafferano"][size]
            markup.add(types.InlineKeyboardButton(f"{size} - {price}€", callback_data=f"add_{size}"))
        markup.add(types.InlineKeyboardButton("⬅️ Indietro", callback_data="back_home"))
        bot.edit_message_text("📦 Seleziona la quantità di *Zafferano* che vuoi acquistare:", chat_id, call.message.id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("add_"):
        size = call.data.replace("add_", "")
        if chat_id not in user_cart:
            user_cart[chat_id] = []
        user_cart[chat_id].append(size)
        bot.answer_callback_query(call.id, f"{size} aggiunto al carrello ✅")

    elif call.data == "view_cart":
        if chat_id not in user_cart or not user_cart[chat_id]:
            bot.answer_callback_query(call.id, "🛒 Il tuo carrello è vuoto.")
        else:
            total = sum(PRODUCTS["Zafferano"][s] for s in user_cart[chat_id])
            items = "\n".join([f"- {s}" for s in user_cart[chat_id]])
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💳 Paga con Carta (Stripe)", callback_data="pay_card"))
            markup.add(types.InlineKeyboardButton("💸 Paga con PayPal", url="https://paypal.me/ChristianMadafferi"))
            markup.add(types.InlineKeyboardButton("⬅️ Indietro", callback_data="back_home"))
            bot.edit_message_text(
                f"🛍️ *Carrello:*\n{items}\n\n💰 *Totale:* {total}€",
                chat_id, call.message.id, reply_markup=markup, parse_mode="Markdown"
            )

    elif call.data == "info":
        bot.edit_message_text(
            "ℹ️ *Informazioni sul prodotto:*\n\n"
            "🌸 Zafferano purissimo dell’Aquila, raccolto a mano e confezionato con cura.\n"
            "Prezzo base: *8€/g*\nSconti disponibili per quantità maggiori.\n\n"
            "📦 Spedizione tracciata in tutta Italia.\n"
            "⏰ Data e ora: " + datetime.now().strftime("%d/%m/%Y - %H:%M"),
            chat_id, call.message.id, parse_mode="Markdown"
        )

    elif call.data == "contacts":
        bot.edit_message_text(
            "📞 *Contatti:*\n\n"
            "📧 Email: support@zafferanobot.it\n"
            "📱 Telegram: @ChristianMadafferi\n"
            "🌐 Sito: www.zafferanobot.it\n"
            "⏰ Data e ora: " + datetime.now().strftime("%d/%m/%Y - %H:%M"),
            chat_id, call.message.id, parse_mode="Markdown"
        )

    elif call.data == "back_home":
        start(call.message)

    elif call.data == "pay_card":
        total = sum(PRODUCTS["Zafferano"][s] for s in user_cart.get(chat_id, []))
        if total == 0:
            bot.answer_callback_query(call.id, "Il carrello è vuoto!")
            return
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {'name': 'Zafferano dell’Aquila'},
                        'unit_amount': int(total * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url="https://telegram.me/your_bot_username?start=success",
                cancel_url="https://telegram.me/your_bot_username?start=cancel",
            )
            bot.send_message(chat_id, f"💳 Paga in sicurezza con Stripe:\n{session.url}")
        except Exception as e:
            bot.send_message(chat_id, f"❌ Errore durante la creazione del pagamento: {e}")

# ===========================
#   Flask server
# ===========================
@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# ===========================
#   Set webhook
# ===========================
WEBHOOK_URL = f"https://telegram-bot-sohm.onrender.com/webhook/{TOKEN}"
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# ===========================
#   Run Flask
# ===========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)