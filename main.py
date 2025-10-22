from flask import Flask, request, jsonify
from telebot import TeleBot, types
import os
from datetime import datetime
import stripe

# ===========================
#   Bot setup
# ===========================
TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
ADMIN_ID = 6497093715
bot = TeleBot(TOKEN)
app = Flask(__name__)

# ===========================
#   Stripe setup
# ===========================
STRIPE_SECRET_KEY = "sk_test.
_51SLBdNJjMidYjUi4laG8TntwHT1IHZ
2QcSiVZdXR6E81VpNehJ0DJDkox73xlmV6Kgo8k
QtapAH5eGjtNdoRØvukØ0gu4aqlHE"
STRIPE_PUBLISHABLE_KEY = "pk_test_51SLBdNJjMidYjUi4u1ChN08rQWh007
N3egMVN5RfLbQwbPyQ1RqB4gwvTnx7Q7JXwCJdd
3JxdMjmU0kzRDydtc1a00GEzbg9gР"
stripe.api_key = STRIPE_SECRET_KEY

# ===========================
#   Products and prices
# ===========================
PRODUCTS = {
    "zafferano": {
        "1g": 8,
        "3g": 24,
        "5g": 40,
        "10g": 80,
        "30g": 216,   # 10% discount
        "50g": 320,   # 20% discount
        "70g": 448,   # 20% discount
        "100g": 600   # 25% discount
    }
}

# Cart per user
user_cart = {}
user_stage = {}  # track user's section

# ===========================
#   Helper functions
# ===========================
def get_price(product, qty):
    return PRODUCTS[product][qty]

def format_cart(chat_id):
    cart = user_cart.get(chat_id, [])
    if not cart:
        return "🛒 Your cart is empty.", 0
    text = "🛒 Your cart:\n\n"
    total = 0
    for item in cart:
        price = get_price(item['product'], item['qty'])
        text += f"{item['product'].capitalize()} - {item['qty']} - {price}€\n"
        total += price
    text += f"\n💰 Total: {total}€"
    return text, total

# ===========================
#   Bot commands
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_cart[chat_id] = []
    user_stage[chat_id] = "start"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("/shop", "/cart", "/info", "/contacts")
    bot.send_message(chat_id, "👋 Welcome! Choose an option:", reply_markup=markup)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "📖 Available commands:\n/start - Start\n/shop - Shop products\n/cart - View cart\n/info - Info\n/contacts - Contacts")

@bot.message_handler(commands=['shop'])
def shop(message):
    chat_id = message.chat.id
    user_stage[chat_id] = "shop"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for qty in PRODUCTS["zafferano"]:
        markup.add(f"{qty}")
    markup.add("Back")
    bot.send_message(chat_id, "Choose zafferano quantity:", reply_markup=markup)

@bot.message_handler(commands=['cart'])
def show_cart(message):
    chat_id = message.chat.id
    text, total = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    if total > 0:
        markup.add(types.InlineKeyboardButton("💸 Pay with PayPal", url=f"https://paypal.me/ChristianMadafferi/{total}"))
        markup.add(types.InlineKeyboardButton("💳 Pay with Card", callback_data="card_payment"))
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['info'])
def info(message):
    chat_id = message.chat.id
    text = "ℹ️ Info:\nThis bot sells high-quality zafferano.\nPrices:\n"
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
    stage = user_stage.get(chat_id)
    
    if message.text == "Back":
        if stage == "shop":
            start(message)
        return

    if stage == "shop":
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
    elif call.data == "card_payment":
        _, total = format_cart(chat_id)
        # Create Stripe checkout session
        line_items = []
        for item in user_cart.get(chat_id, []):
            line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f"{item['product'].capitalize()} {item['qty']}"},
                    'unit_amount': get_price(item['product'], item['qty'])*100,  # in cents
                },
                'quantity': 1,
            })
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url='https://telegram-bot-sohm.onrender.com/success',
            cancel_url='https://telegram-bot-sohm.onrender.com/cancel',
        )
        bot.send_message(chat_id, f"💳 Complete your payment here:\n{session.url}")
        bot.answer_callback_query(call.id, "Stripe payment link sent.")

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

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = "YOUR_STRIPE_ENDPOINT_SECRET"  # From Stripe dashboard
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        return jsonify(success=False), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        bot.send_message(ADMIN_ID, f"✅ Stripe Payment received!\n💰 Amount: {session['amount_total']/100} EUR\n🕒 {now}")
    return jsonify(success=True), 200

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