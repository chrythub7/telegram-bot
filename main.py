from flask import Flask, request
from telebot import TeleBot, types
import os

# ===========================
#   Bot setup
# ===========================
TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
ADMIN_ID = 6497093715  # <-- Replace this with your Telegram user ID
bot = TeleBot(TOKEN)

# ===========================
#   Bot commands
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍️ Ordina", "ℹ️ Info", "🛒 Carrello")
    markup.add("📞 Contatti")
    bot.send_message(
        message.chat.id,
        "👋 Benvenuto nel bot!\nScegli un'opzione dal menu qui sotto 👇",
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(
        message,
        "📖 *Comandi disponibili:*\n"
        "/start - Riavvia il bot\n"
        "/help - Mostra questo messaggio\n"
        "/info - Info su spedizioni e pagamenti\n"
        "/contatti - Visualizza contatti di supporto\n"
        "/pay - Paga con PayPal",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['info'])
def info_command(message):
    bot.send_message(
        message.chat.id,
        "ℹ️ *Informazioni utili:*\n"
        "📦 Spedizione: 1-3 giorni lavorativi\n"
        "💸 Pagamento: tramite PayPal\n"
        "📬 Riceverai conferma via messaggio dopo il pagamento\n"
        "❓ Per dubbi o richieste usa /contatti",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['contatti'])
def contacts_command(message):
    bot.send_message(
        message.chat.id,
        "📞 *Contatti di supporto:*\n"
        "👤 Telegram: [@ChristianMadafferi](https://t.me/ChristianMadafferi)\n"
        "📧 Email: supporto@tuodominio.com\n"
        "📸 Instagram: [@tuoprofilo](https://instagram.com/tuoprofilo)",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@bot.message_handler(commands=['pay'])
def pay(message):
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton(
        text="💸 Pay with PayPal",
        url="https://paypal.me/ChristianMadafferi?locale.x=it_IT&country.x=IT"  # <-- Replace with your PayPal.me link
    )
    markup.add(button)
    bot.send_message(
        message.chat.id,
        "Choose a payment method:",
        reply_markup=markup
    )

# ===========================
#   Auto reply for support words
# ===========================
@bot.message_handler(func=lambda msg: any(word in msg.text.lower() for word in ["aiuto", "problema", "supporto", "assistenza", "contatto"]))
def support_auto_reply(message):
    bot.send_message(
        message.chat.id,
        "🧰 Sembra che tu abbia bisogno di aiuto!\n"
        "Puoi contattarci direttamente:\n"
        "👤 Telegram: [@ChristianMadafferi](https://t.me/ChristianMadafferi)\n"
        "📧 Email: supporto@tuodominio.com",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# ===========================
#   General message handler
# ===========================
@bot.message_handler(func=lambda msg: msg.text == "📞 Contatti")
def contacts_from_menu(message):
    contacts_command(message)

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ Info")
def info_from_menu(message):
    info_command(message)

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Hai scritto: {message.text}")

# ===========================
#   Flask server
# ===========================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

# Telegram webhook
@app.route("/", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# PayPal webhook
@app.route("/paypal-webhook", methods=["POST"])
def paypal_webhook():
    data = request.json
    print("📩 PayPal Webhook received:", data)

    if data.get('event_type') == 'PAYMENT.CAPTURE.COMPLETED':
        payer_email = data['resource']['payer']['email_address']
        amount = data['resource']['amount']['value']
        currency = data['resource']['amount']['currency_code']

        message = f"✅ Payment received!\n💰 Amount: {amount} {currency}\n📧 From: {payer_email}"
        print(message)

        # Send notification to admin on Telegram
        bot.send_message(ADMIN_ID, message)

    return "OK", 200

# ===========================
#   Set Telegram webhook
# ===========================
WEBHOOK_URL = "https://telegram-bot-sohm.onrender.com"  # <-- Replace with your Render app URL
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# ===========================
#   Run Flask server
# ===========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)