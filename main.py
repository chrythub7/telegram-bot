from flask import Flask, request, jsonify
from telebot import TeleBot, types
import os
import stripe
import smtplib
from email.message import EmailMessage
from datetime import datetime
import uuid
import re

# ---------------------------
# Config (via ENV on Render)
# ---------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET")
PAYPAL_ME_USERNAME = os.getenv("PAYPAL_ME_USERNAME")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Check envs
missing = [k for k, v in {
    "BOT_TOKEN": BOT_TOKEN,
    "ADMIN_ID": ADMIN_ID,
    "ADMIN_EMAIL": ADMIN_EMAIL,
    "EMAIL_USER": EMAIL_USER,
    "EMAIL_PASS": EMAIL_PASS,
    "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
    "STRIPE_ENDPOINT_SECRET": STRIPE_ENDPOINT_SECRET,
    "PAYPAL_ME_USERNAME": PAYPAL_ME_USERNAME,
    "WEBHOOK_URL": WEBHOOK_URL
}.items() if not v]
if missing:
    print(f"⚠️ Missing ENV vars: {missing}")

# ---------------------------
# Init
# ---------------------------
bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)
stripe.api_key = STRIPE_SECRET_KEY

# ---------------------------
# Products/prices
# ---------------------------
PRODUCTS = {
    "saffron": {
        "1g": 8,
        "3g": 24,
        "5g": 40,
        "10g": 80,
        "30g": 216,
        "50g": 320,
        "70g": 448,
        "100g": 600
    }
}

# ---------------------------
# Storage
# ---------------------------
user_cart = {}
user_stage = {}
pending_orders = {}

# ---------------------------
# Helpers
# ---------------------------
def now_str():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def get_price(product, qty):
    return PRODUCTS[product][qty]

def calc_cart_total(chat_id):
    total = 0
    for it in user_cart.get(chat_id, []):
        total += get_price(it['product'], it['qty'])
    return total

def format_cart(chat_id):
    cart = user_cart.get(chat_id, [])
    if not cart:
        return "🛒 Your cart is empty.", 0
    text = "🛒 *Your cart:*\n\n"
    total = 0
    for i, item in enumerate(cart, 1):
        price = get_price(item['product'], item['qty'])
        text += f"{i}) {item['product'].capitalize()} — {item['qty']} → {price}€\n"
        total += price
    text += f"\n💰 *Total:* {total}€"
    return text, total

def send_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.set_content(body)
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.starttls()
            s.login(EMAIL_USER, EMAIL_PASS)
            s.send_message(msg)
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Email error: {e}")

def generate_order(chat_id):
    order_id = str(uuid.uuid4())[:8]
    order = {
        'order_id': order_id,
        'chat_id': chat_id,
        'cart': user_cart.get(chat_id, []).copy(),
        'total': calc_cart_total(chat_id),
        'created_at': now_str(),
        'paid': False,
        'payment_method': None,
        'shipping': None
    }
    pending_orders[order_id] = order
    return order

# ---------------------------
# Commands
# ---------------------------
@bot.message_handler(commands=['start'])
def start(msg):
    chat_id = msg.chat.id
    user_cart[chat_id] = []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍️ Shop", "🛒 Cart", "ℹ️ Info", "📞 Contacts")
    bot.send_message(chat_id, "👋 Welcome to *BrandingShopy*!", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['shop'])
def shop(msg):
    chat_id = msg.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for qty in PRODUCTS['saffron'].keys():
        markup.add(qty)
    markup.add("⬅️ Back")
    bot.send_message(chat_id, "🌿 Choose the saffron quantity:", reply_markup=markup)

@bot.message_handler(commands=['cart'])
def cart(msg):
    chat_id = msg.chat.id
    text, total = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    if total > 0:
        markup.add(
            types.InlineKeyboardButton("💰 Pay with PayPal", callback_data="paypal_payment"),
            types.InlineKeyboardButton("💳 Pay with Card (Stripe)", callback_data="stripe_payment")
        )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['info'])
def info(msg):
    txt = "ℹ️ *100% pure Italian saffron*\n\nPrices:\n"
    for k, v in PRODUCTS['saffron'].items():
        txt += f"- {k}: {v}€\n"
    bot.send_message(msg.chat.id, txt, parse_mode="Markdown")

@bot.message_handler(commands=['contacts'])
def contacts(msg):
    bot.send_message(msg.chat.id, "📞 Contacts:\nTelegram: @SlyanuS7\nEmail: brandingshopy@gmail.com")

# ---------------------------
# Product selection
# ---------------------------
@bot.message_handler(func=lambda m: m.text in PRODUCTS['saffron'] or m.text == "⬅️ Back")
def select_qty(msg):
    chat_id = msg.chat.id
    if msg.text == "⬅️ Back":
        start(msg)
        return
    user_cart.setdefault(chat_id, []).append({'product': 'saffron', 'qty': msg.text})
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 View Cart", callback_data="open_cart"))
    bot.send_message(
        chat_id,
        f"✅ Added {msg.text} of saffron to your cart! Tap below to view your cart.",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "open_cart")
def open_cart(call):
    chat_id = call.message.chat.id
    text, total = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    if total > 0:
        markup.add(
            types.InlineKeyboardButton("💰 Pay with PayPal", callback_data="paypal_payment"),
            types.InlineKeyboardButton("💳 Pay with Card (Stripe)", callback_data="stripe_payment")
        )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# ---------------------------
# Callback payments
# ---------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("paypal") or call.data.startswith("stripe") or call.data.startswith("paypal_paid"))
def cb(call):
    chat_id = call.message.chat.id
    order = generate_order(chat_id)

    if call.data == "paypal_payment":
        total = order['total']
        paypal_link = f"https://www.paypal.me/{PAYPAL_ME_USERNAME}/{total}"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔗 Open PayPal", url=paypal_link))
        keyboard.add(types.InlineKeyboardButton("✅ I have paid", callback_data=f"paypal_paid|{order['order_id']}"))
        bot.send_message(chat_id, f"💸 Pay *{total}€* via PayPal, then press the button below once payment is done.", parse_mode="Markdown", reply_markup=keyboard)

    elif call.data == "stripe_payment":
        try:
            line_items = [{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f"Saffron {it['qty']}"},
                    'unit_amount': int(get_price(it['product'], it['qty']) * 100),
                },
                'quantity': 1
            } for it in order['cart']]

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=f"{WEBHOOK_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{WEBHOOK_URL}/cancel",
                metadata={'chat_id': str(chat_id), 'order_id': order['order_id']}
            )

            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("🔗 Pay with Card", url=session.url))
            bot.send_message(chat_id, f"💳 Total: {order['total']}€ — click below to pay.", reply_markup=keyboard)
        except Exception as e:
            bot.send_message(chat_id, f"❌ Stripe Error: {e}")

    elif call.data.startswith("paypal_paid|"):
        _, order_id = call.data.split("|", 1)
        user_stage[chat_id] = f"awaiting_shipping|{order_id}"
        bot.send_message(chat_id, "✅ Please send your shipping details (full name, address, city, ZIP, phone number).")

# ---------------------------
# Shipping + Email
# ---------------------------
@bot.message_handler(func=lambda m: True)
def all_msg(msg):
    chat_id = msg.chat.id
    text = msg.text.strip()
    stage = user_stage.get(chat_id, "")

    if stage.startswith("awaiting_shipping"):
        _, order_id = stage.split("|", 1)
        order = pending_orders.get(order_id)
        if not order:
            bot.send_message(chat_id, "⚠️ Order not found.")
            return
        order['shipping'] = text
        send_email(ADMIN_EMAIL, f"New Order {order_id}", f"Shipping details:\n{text}\nTotal: {order['total']}€")
        bot.send_message(chat_id, "📦 Shipping info saved. Please send your email for confirmation.")
        user_stage[chat_id] = f"awaiting_email|{order_id}"
        return

    if stage.startswith("awaiting_email"):
        _, order_id = stage.split("|", 1)
        order = pending_orders.get(order_id)
        email = text
        send_email(email, f"Order confirmation {order_id}", f"Thank you! Your order has been received and will be shipped soon.\nTotal: {order['total']}€")
        bot.send_message(chat_id, "✅ Confirmation email sent! Thank you for your purchase 🙏")
        user_stage[chat_id] = ""
        return

    if text.startswith("/"):
        bot.send_message(chat_id, "❓ Unknown command. Use /shop or /cart.")
    else:
        bot.send_message(chat_id, "🛍 Use /shop to start or /cart to see your cart.")

# ---------------------------
# Stripe webhook
# ---------------------------
@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_ENDPOINT_SECRET)
    except Exception as e:
        print("Stripe error:", e)
        return "bad", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        chat_id = int(session["metadata"]["chat_id"])
        order_id = session["metadata"]["order_id"]
        order = pending_orders.get(order_id)
        if order:
            order["paid"] = True
            order["payment_method"] = "stripe"
            bot.send_message(chat_id, f"✅ Stripe payment completed ({order['total']}€). Please send your shipping details (full name, address, ZIP, phone number).")
            user_stage[chat_id] = f"awaiting_shipping|{order_id}"
    return "ok", 200

# ---------------------------
# Flask routes
# ---------------------------
@app.route("/")
def index():
    return "Bot is running", 200

@app.route("/", methods=["POST"])
def tg_update():
    update = types.Update.de_json(request.get_json())
    bot.process_new_updates([update])
    return "ok", 200

@app.route("/success")
def success():
    return "<h2>✅ Payment successful! Return to Telegram to complete the shipping details.</h2>"

@app.route("/cancel")
def cancel():
    return "<h2>❌ Payment cancelled.</h2>"

# ---------------------------
# Webhook
# ---------------------------
if WEBHOOK_URL:
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook set to:", WEBHOOK_URL)
    except Exception as e:
        print("Webhook error:", e)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)