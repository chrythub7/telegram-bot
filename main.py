from telebot import TeleBot, types

# Insert your bot token from @BotFather
TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
bot = TeleBot(TOKEN)

# ===========================
#   /start
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Hi! Welcome to the bot.\nUse /pay to make a PayPal payment or /help to see all commands.")

# ===========================
#   /help
# ===========================
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "📖 Available commands:\n/start - Start the bot\n/help - Show this message\n/pay - Pay via PayPal")

# ===========================
#   /pay
# ===========================
@bot.message_handler(commands=['pay'])
def pay(message):
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton(
        text="💸 Pay with PayPal",
        url="https://www.paypal.me/YOUR_USERNAME/10"  # <-- Replace with your PayPal.me link
    )
    markup.add(button)
    bot.send_message(
        message.chat.id,
        "Choose a payment method:",
        reply_markup=markup
    )

# ===========================
#   Auto reply (echo)
# ===========================
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"You said: {message.text}")

# ===========================
#   Start bot
# ===========================
print("✅ Bot is running...")
bot.infinity_polling()


from flask import Flask, request

app = Flask(__name__)

@app.route('/paypal-webhook', methods=['POST'])
def paypal_webhook():
    data = request.json
    print("📩 PayPal Webhook received:", data)

    # Check if it's a completed payment
    if data.get('event_type') == 'PAYMENT.CAPTURE.COMPLETED':
        payer_email = data['resource']['payer']['email_address']
        amount = data['resource']['amount']['value']
        currency = data['resource']['amount']['currency_code']

        print(f"✅ Payment received from {payer_email}: {amount} {currency}")

    return "OK", 200

if __name__ == "__main__":
    # Run both the bot and the webhook server
    import threading
    threading.Thread(target=lambda: bot.infinity_polling()).start()
    app.run(host="0.0.0.0", port=10000)
