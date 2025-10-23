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
    "zafferano": {
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
        return "🛒 Il tuo carrello è vuoto.", 0
    text = "🛒 Carrello:\n\n"
    total = 0
    for i, item in enumerate(cart, 1):
        price = get_price(item['product'], item['qty'])
        text += f"{i}) {item['product'].capitalize()} — {item['qty']} → {price}€\n"
        total += price
    text += f"\n💰 Totale: {total}€"
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
        print(f"✅ Email inviata a {to_email}")
    except Exception as e:
        print(f"❌ Errore email: {e}")

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
    markup.add("/shop", "/cart", "/info", "/contacts")
    bot.send_message(chat_id, "👋 Benvenuto su *BrandingShop*!", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['shop'])
def shop(msg):
    chat_id = msg.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for qty in PRODUCTS['zafferano'].keys():
        markup.add(qty)
    markup.add("⬅️ Indietro")
    bot.send_message(chat_id, "🌿 Scegli la quantità di zafferano:", reply_markup=markup)

@bot.message_handler(commands=['cart'])
def cart(msg):
    chat_id = msg.chat.id
    text, total = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    if total > 0:
        markup.add(
            types.InlineKeyboardButton("💰 PayPal", callback_data="paypal_payment"),
            types.InlineKeyboardButton("💳 Carta (Stripe)", callback_data="stripe_payment")
        )
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(commands=['info'])
def info(msg):
    txt = "ℹ️ *Zafferano 100% puro italiano*\n\nPrezzi:\n"
    for k, v in PRODUCTS['zafferano'].items():
        txt += f"- {k}: {v}€\n"
    bot.send_message(msg.chat.id, txt, parse_mode="Markdown")

@bot.message_handler(commands=['contacts'])
def contacts(msg):
    bot.send_message(msg.chat.id, "📞 Contatti:\nTelegram: @SlyanuS7\nEmail: brandingshopy@gmail.com")

# ---------------------------
# Selection handler
# ---------------------------
@bot.message_handler(func=lambda m: m.text in PRODUCTS['zafferano'] or m.text == "⬅️ Indietro")
def select_qty(msg):
    chat_id = msg.chat.id
    if msg.text == "⬅️ Indietro":
        start(msg)
        return
    user_cart.setdefault(chat_id, []).append({'product': 'zafferano', 'qty': msg.text})
    bot.send_message(chat_id, f"✅ Aggiunto {msg.text} di zafferano al carrello!")

# ---------------------------
# Callback (payments)
# ---------------------------
@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    chat_id = call.message.chat.id
    order = generate_order(chat_id)

    if call.data == "paypal_payment":
        total = order['total']
        paypal_link = f"https://www.paypal.me/{PAYPAL_ME_USERNAME}/{total}"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔗 Apri PayPal", url=paypal_link))
        keyboard.add(types.InlineKeyboardButton("✅ Ho pagato", callback_data=f"paypal_paid|{order['order_id']}"))
        bot.send_message(chat_id, f"💸 Paga *{total}€* su PayPal e poi premi 'Ho pagato'.", parse_mode="Markdown", reply_markup=keyboard)

    elif call.data == "stripe_payment":
        try:
            line_items = [{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f"Zafferano {it['qty']}"},
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
            keyboard.add(types.InlineKeyboardButton("🔗 Paga con carta", url=session.url))
            bot.send_message(chat_id, f"💳 Totale: {order['total']}€ — clicca sotto per pagare.", reply_markup=keyboard)
        except Exception as e:
            bot.send_message(chat_id, f"❌ Errore Stripe: {e}")

    elif call.data.startswith("paypal_paid|"):
        _, order_id = call.data.split("|", 1)
        user_stage[chat_id] = f"awaiting_shipping|{order_id}"
        bot.send_message(chat_id, "✅ Inviami ora i dati di spedizione (nome, indirizzo, CAP, telefono).")

# ---------------------------
# Catch-all messages (shipping + email)
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
            bot.send_message(chat_id, "⚠️ Ordine non trovato.")
            return
        order['shipping'] = text
        send_email(ADMIN_EMAIL, f"Nuovo ordine {order_id}", f"Dettagli spedizione:\n{text}\nTotale: {order['total']}€")
        bot.send_message(chat_id, "📦 Spedizione salvata. Ora inviami la tua email per la conferma.")
        user_stage[chat_id] = f"awaiting_email|{order_id}"
        return

    if stage.startswith("awaiting_email"):
        _, order_id = stage.split("|", 1)
        order = pending_orders.get(order_id)
        email = text
        send_email(email, f"Conferma ordine {order_id}", f"Grazie! Il tuo ordine è stato ricevuto e sarà spedito a breve.\nTotale: {order['total']}€")
        bot.send_message(chat_id, "✅ Email di conferma inviata! Grazie per l’acquisto 🙏")
        user_stage[chat_id] = ""
        return

    if text.startswith("/"):
        bot.send_message(chat_id, "❓ Comando non valido. Usa /shop o /cart.")
    else:
        bot.send_message(chat_id, "🛍 Usa /shop per iniziare o /cart per vedere il carrello.")

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
            bot.send_message(chat_id, f"✅ Pagamento Stripe completato ({order['total']}€). Inviami i dati per la spedizione (nome, indirizzo, CAP, telefono).")
            user_stage[chat_id] = f"awaiting_shipping|{order_id}"
    return "ok", 200

# ---------------------------
# Flask routes
# ---------------------------
@app.route("/")
def index():
    return "Bot attivo", 200

@app.route("/", methods=["POST"])
def tg_update():
    update = types.Update.de_json(request.get_json())
    bot.process_new_updates([update])
    return "ok", 200

@app.route("/success")
def success():
    return "<h2>✅ Pagamento riuscito! Torna al bot per completare la spedizione.</h2>"

@app.route("/cancel")
def cancel():
    return "<h2>❌ Pagamento annullato.</h2>"

# ---------------------------
# Webhook
# ---------------------------
if WEBHOOK_URL:
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook impostato su:", WEBHOOK_URL)
    except Exception as e:
        print("Errore webhook:", e)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)