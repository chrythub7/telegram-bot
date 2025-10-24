# main.py
from flask import Flask, request, jsonify
from telebot import TeleBot, types
import os
import stripe
import requests
import uuid
from datetime import datetime
from email.message import EmailMessage
import smtplib

# ---------------------------
# Config (ENV)
# ---------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app.onrender.com
SUPPLIER_PHONE = os.getenv("SUPPLIER_PHONE", "+86 183 1657 0442")

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET")

# PayPal
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")  # optional but recommended

# Optional email (admin notifications)
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# quick check
missing = [k for k,v in {
    "BOT_TOKEN": BOT_TOKEN,
    "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
    "STRIPE_ENDPOINT_SECRET": STRIPE_ENDPOINT_SECRET,
    "PAYPAL_CLIENT_ID": PAYPAL_CLIENT_ID,
    "PAYPAL_CLIENT_SECRET": PAYPAL_CLIENT_SECRET,
    "WEBHOOK_URL": WEBHOOK_URL
}.items() if not v]
if missing:
    print("⚠️ Missing env vars (some features may not work):", missing)
else:
    print("✅ Env looks OK")

# ---------------------------
# Init
# ---------------------------
bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)
stripe.api_key = STRIPE_SECRET_KEY

# ---------------------------
# Products (simple)
# ---------------------------
PRODUCTS = {
    "saffron": {
        "1g": 8.00,
        "3g": 24.00,
        "5g": 40.00,
        "10g": 80.00,
        "30g": 216.00,
        "50g": 320.00,
        "70g": 448.00,
        "100g": 600.00
    }
}

# in-memory storage (replace with DB for production)
user_cart = {}        # chat_id -> [ {product, qty} ]
pending_orders = {}   # order_id -> order dict

# ---------------------------
# Helpers
# ---------------------------
def now_str():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def calc_cart_total(chat_id):
    cart = user_cart.get(chat_id, [])
    total = sum(PRODUCTS[item['product']][item['qty']] for item in cart)
    return round(total, 2)

def format_cart(chat_id):
    cart = user_cart.get(chat_id, [])
    if not cart:
        return "🛒 Your cart is empty.", 0.0
    text = "🛒 Your cart:\n\n"
    total = 0.0
    for i, it in enumerate(cart, 1):
        price = PRODUCTS[it['product']][it['qty']]
        text += f"{i}) {it['product'].capitalize()} — {it['qty']} → {price:.2f}€\n"
        total += price
    text += f"\n💰 Total: {total:.2f}€"
    return text, round(total,2)

def send_admin_email(subject, body):
    if not (EMAIL_USER and EMAIL_PASS and ADMIN_EMAIL):
        print("Email not configured; skipping admin email.")
        return
    try:
        msg = EmailMessage()
        msg['From'] = EMAIL_USER
        msg['To'] = ADMIN_EMAIL
        msg['Subject'] = subject
        msg.set_content(body)
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.ehlo()
            s.starttls()
            s.login(EMAIL_USER, EMAIL_PASS)
            s.send_message(msg)
        print("✅ Admin email sent.")
    except Exception as e:
        print("❌ Email error:", e)

def create_order_snapshot(chat_id):
    order_id = str(uuid.uuid4())[:8]
    cart = user_cart.get(chat_id, []).copy()
    total = calc_cart_total(chat_id)
    order = {
        "order_id": order_id,
        "chat_id": chat_id,
        "cart": cart,
        "total": total,
        "created_at": now_str(),
        "paid": False,
        "payment_method": None,
        "payment_info": None
    }
    pending_orders[order_id] = order
    return order

def give_supplier_phone(chat_id, order_id=None):
    text = f"✅ Payment confirmed. Supplier phone: {SUPPLIER_PHONE}\nContact the supplier and provide your order ID: {order_id or 'N/A'}"
    bot.send_message(chat_id, text)
    # notify admin
    try:
        bot.send_message(ADMIN_ID, f"Order {order_id} paid by chat {chat_id}. Supplier phone delivered: {SUPPLIER_PHONE}")
    except Exception as e:
        print("Admin notify error:", e)
    send_admin_email(f"Order {order_id} paid", f"Order {order_id} for chat {chat_id} is paid. Total: {pending_orders[order_id]['total']}€")

# ---------------------------
# Telegram commands / UI
# ---------------------------
@bot.message_handler(commands=['start'])
def handle_start(m):
    chat_id = m.chat.id
    user_cart.setdefault(chat_id, [])
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛍 Shop", "🛒 Cart", "💬 Claim")
    bot.send_message(chat_id, "Welcome — choose an option:", reply_markup=markup)

@bot.message_handler(commands=['shop'])
def cmd_shop(m):
    chat_id = m.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for qty in PRODUCTS['saffron'].keys():
        markup.add(qty)
    markup.add("⬅ Back")
    bot.send_message(chat_id, "Choose quantity:", reply_markup=markup)

@bot.message_handler(commands=['cart'])
def cmd_cart(m):
    chat_id = m.chat.id
    text, total = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    if total > 0:
        markup.add(
            types.InlineKeyboardButton("PayPal", callback_data="pay_paypal"),
            types.InlineKeyboardButton("Stripe", callback_data="pay_stripe")
        )
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in PRODUCTS['saffron'].keys())
def add_to_cart(msg):
    chat_id = msg.chat.id
    qty = msg.text
    user_cart.setdefault(chat_id, []).append({"product":"saffron","qty":qty})
    bot.send_message(chat_id, f"Added {qty} saffron to cart. Use /cart to pay.")

@bot.message_handler(func=lambda msg: msg.text == "💬 Claim")
def claim_phone(msg):
    chat_id = msg.chat.id
    # find paid order for this chat
    paid = [o for o in pending_orders.values() if o['chat_id']==chat_id and o['paid']]
    if paid:
        # give phone for first paid order
        give_supplier_phone(chat_id, paid[0]['order_id'])
    else:
        bot.send_message(chat_id, "No paid order found. If you already paid, wait a moment or use the link you used to pay.")

# ---------------------------
# Callbacks create sessions/links
# ---------------------------
@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    chat_id = c.message.chat.id
    data = c.data

    if data == "pay_paypal":
        order = create_order_snapshot(chat_id)
        total = order['total']
        # Create PayPal order (checkout) - obtain approval link
        try:
            # Get access token
            auth = requests.post(
                "https://api-m.sandbox.paypal.com/v1/oauth2/token",
                data={'grant_type':'client_credentials'},
                auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET)
            )
            auth.raise_for_status()
            token = auth.json()['access_token']
            headers = {
                'Content-Type':'application/json',
                'Authorization': f'Bearer {token}'
            }
            # Build order body (simple)
            body = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {"currency_code":"EUR","value": f"{total:.2f}" },
                    "custom_id": order['order_id']
                }],
                "application_context": {
                    "return_url": f"{WEBHOOK_URL}/paypal-return?order_id={order['order_id']}",
                    "cancel_url": f"{WEBHOOK_URL}/cancel"
                }
            }
            r = requests.post("https://api-m.sandbox.paypal.com/v2/checkout/orders", json=body, headers=headers)
            r.raise_for_status()
            order_data = r.json()
            # find approve link
            approve = next((l['href'] for l in order_data['links'] if l['rel']=='approve'), None)
            if not approve:
                raise Exception("No approve link from PayPal")
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("Open PayPal", url=approve))
            keyboard.add(types.InlineKeyboardButton("I've paid (send tx id)", callback_data=f"paypal_paid|{order['order_id']}"))
            bot.send_message(chat_id, f"PayPal order created for {total:.2f}€. Approve and capture on PayPal. Order ID: {order['order_id']}", reply_markup=keyboard)
        except Exception as e:
            bot.send_message(chat_id, f"PayPal error: {e}")
            print("PayPal error:", e)

    elif data == "pay_stripe":
        order = create_order_snapshot(chat_id)
        line_items = []
        for it in order['cart']:
            price = PRODUCTS[it['product']][it['qty']]
            line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f"{it['product'].capitalize()} {it['qty']}"},
                    'unit_amount': int(price*100)
                },
                'quantity': 1
            })
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=f"{WEBHOOK_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{WEBHOOK_URL}/cancel",
                metadata={'chat_id': str(chat_id), 'order_id': order['order_id']}
            )
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("Pay with card (Stripe)", url=session.url))
            bot.send_message(chat_id, f"Stripe checkout for {order['total']:.2f}€ created. Use the button to pay.", reply_markup=kb)
        except Exception as e:
            bot.send_message(chat_id, f"Stripe error: {e}")
            print("Stripe error:", e)

    elif data.startswith("paypal_paid|"):
        _, order_id = data.split("|",1)
        # put user in stage to send tx
        bot.send_message(chat_id, "Please send the PayPal transaction ID or a screenshot link here. After verification we'll provide the supplier contact.")
        # save a marker on pending order to know we expect tx from this chat
        pending_orders.setdefault(order_id, {})['awaiting_paypal_tx_from'] = chat_id

# ---------------------------
# Telegram catch-all for PayPal tx
# ---------------------------
@bot.message_handler(func=lambda m: True)
def fallback(m):
    chat_id = m.chat.id
    text = (m.text or "").strip()
    # check if this chat is associated with a pending order awaiting tx
    for oid, order in pending_orders.items():
        if order.get('awaiting_paypal_tx_from') == chat_id:
            # treat text as tx id, mark paid
            order['paid'] = True
            order['payment_method'] = 'paypal_manual'
            order['payment_info'] = {'tx': text, 'verified_at': now_str()}
            # deliver supplier phone
            give_supplier_phone(chat_id, oid)
            return
    # default reply
    bot.send_message(chat_id, "Unknown message. Use /shop to start or /cart to view the cart.")

# ---------------------------
# Stripe webhook
# ---------------------------
@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_ENDPOINT_SECRET)
    except Exception as e:
        print("Stripe webhook signature verification failed:", e)
        return "bad", 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.get('metadata', {})
        order_id = metadata.get('order_id')
        chat_id = int(metadata.get('chat_id', 0))
        order = pending_orders.get(order_id)
        if order:
            order['paid'] = True
            order['payment_method'] = 'stripe'
            order['payment_info'] = {'session_id': session.get('id'), 'paid_at': now_str()}
            # give phone immediately
            try:
                give_supplier_phone(chat_id, order_id)
            except Exception as e:
                print("Error sending supplier phone:", e)
        else:
            print("Stripe webhook: order not found", order_id)

    return jsonify({'status':'ok'}), 200

# ---------------------------
# PayPal webhook - verify and capture
# ---------------------------
@app.route("/paypal-webhook", methods=["POST"])
def paypal_webhook():
    # PayPal sends events; verify signature by asking PayPal (or use SDK)
    data = request.json
    # For production you should verify webhook signatures per PayPal docs.
    # Here we'll accept PAYMENT.CAPTURE.COMPLETED and mark order paid.
    try:
        event_type = data.get('event_type')
        if event_type == "PAYMENT.CAPTURE.COMPLETED" or event_type == "CHECKOUT.ORDER.APPROVED":
            # PayPal structure: resource may contain custom_id (we set custom_id to our order id)
            resource = data.get('resource', {})
            custom_id = None
            # for capture event, often resource['custom_id'] or resource['supplementary_data']...
            if isinstance(resource, dict):
                custom_id = resource.get('custom_id') or resource.get('invoice_id') or resource.get('custom_id')
            if not custom_id:
                # try parent fields
                custom_id = data.get('resource', {}).get('invoice_id')
            if custom_id and custom_id in pending_orders:
                order = pending_orders[custom_id]
                order['paid'] = True
                order['payment_method'] = 'paypal'
                order['payment_info'] = {'paypal_event': data, 'paid_at': now_str()}
                # notify user/admin and give phone
                try:
                    give_supplier_phone(order['chat_id'], custom_id)
                except Exception as e:
                    print("Error delivering phone after PayPal webhook:", e)
            else:
                print("PayPal webhook: custom_id not found or order missing. Data:", data)
        return jsonify({'status':'ok'}), 200
    except Exception as e:
        print("PayPal webhook handling error:", e)
        return jsonify({'status':'error'}), 500

# ---------------------------
# Simple endpoints used by checkouts
# ---------------------------
@app.route("/success")
def success_page():
    return "<h2>Payment successful — go back to Telegram to get supplier contact.</h2>"

@app.route("/cancel")
def cancel_page():
    return "<h2>Payment canceled.</h2>"

# Telegram webhook endpoint (to receive updates from Telegram)
@app.route("/", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    if not json_data:
        return "no json", 400
    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def root():
    return "Bot is running", 200

# Set webhook with Telegram on startup (if WEBHOOK_URL set)
if WEBHOOK_URL:
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print("Telegram webhook set to", WEBHOOK_URL)
    except Exception as e:
        print("Error setting Telegram webhook:", e)
else:
    print("WEBHOOK_URL not configured; Telegram webhook NOT set")

# Run Flask
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("Starting on port", port)
    app.run(host="0.0.0.0", port=port)