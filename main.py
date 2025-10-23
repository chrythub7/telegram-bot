from flask import Flask, request, jsonify
from telebot import TeleBot, types
import os
import stripe
import smtplib
from email.message import EmailMessage
from datetime import datetime
import uuid

# ---------------------------
# Config (via ENV on Render)
# ---------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")  # app password
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET")  # whsec_...
PAYPAL_ME_USERNAME = os.getenv("PAYPAL_ME_USERNAME")  # e.g. ChristianMadafferi
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com

# Quick sanity check
missing = [k for k,v in {
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
    print(f"⚠️ Missing ENV vars: {missing}  — the app may not work until you set them on Render.")

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
        "30g": 216,   # 10% discount
        "50g": 320,   # 20% discount
        "70g": 448,   # 20% discount
        "100g": 600   # 25% discount
    }
}

# Per-utente storage (in-memory; persist elsewhere for production)
user_cart = {}            # chat_id -> [ {product, qty} ... ]
user_stage = {}           # chat_id -> stage string
pending_orders = {}       # order_id -> order dict (for lookup after payment)

# ---------------------------
# Helpers
# ---------------------------
def now_str():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def get_price(product, qty):
    return PRODUCTS[product][qty]

def calc_cart_total(chat_id):
    cart = user_cart.get(chat_id, [])
    total = 0
    for it in cart:
        total += get_price(it['product'], it['qty'])
    return total

def format_cart(chat_id):
    cart = user_cart.get(chat_id, [])
    if not cart:
        return "🛒 Your cart is empty.", 0
    text = "🛒 Your cart:\n\n"
    total = 0
    for i, item in enumerate(cart, 1):
        price = get_price(item['product'], item['qty'])
        text += f"{i}) {item['product'].capitalize()} — {item['qty']} → {price}€\n"
        total += price
    text += f"\n💰 Total: {total}€"
    return text, total

def send_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.set_content(body)
        # Gmail SMTP
        with smtplib.SMTP('smtp.gmail.com', 587) as s:
            s.ehlo()
            s.starttls()
            s.login(EMAIL_USER, EMAIL_PASS)
            s.send_message(msg)
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Email error to {to_email}: {e}")

def generate_order(chat_id):
    order_id = str(uuid.uuid4())[:8]
    cart = user_cart.get(chat_id, []).copy()
    total = calc_cart_total(chat_id)
    order = {
        'order_id': order_id,
        'chat_id': chat_id,
        'cart': cart,
        'total': total,
        'created_at': now_str(),
        'paid': False,
        'payment_method': None,
        'shipping': None
    }
    pending_orders[order_id] = order
    return order

# ---------------------------
# Bot Commands
# ---------------------------
@bot.message_handler(commands=['start'])
def cmd_start(msg):
    chat_id = msg.chat.id
    user_cart[chat_id] = []
    user_stage[chat_id] = 'start'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("/shop", "/cart", "/info", "/contacts")
    bot.send_message(chat_id, "👋 Welcome to BrandingShop — choose an option:", reply_markup=markup)

@bot.message_handler(commands=['help'])
def cmd_help(msg):
    bot.reply_to(msg, "Commands:\n/start - start\n/shop - browse\n/cart - view cart\n/info - product info\n/contacts - contact info")

@bot.message_handler(commands=['shop'])
def cmd_shop(msg):
    chat_id = msg.chat.id
    user_stage[chat_id] = 'shop'
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for qty in PRODUCTS['zafferano'].keys():
        markup.add(qty)
    markup.add("⬅️ Back")
    bot.send_message(chat_id, "🌿 Choose zafferano quantity:", reply_markup=markup)

@bot.message_handler(commands=['cart'])
def cmd_cart(msg):
    chat_id = msg.chat.id
    text, total = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    if total > 0:
        markup.add(
            types.InlineKeyboardButton("💸 PayPal (manual)", callback_data="paypal_payment"),
            types.InlineKeyboardButton("💳 Card (Stripe)", callback_data="stripe_payment")
        )
        text += f"\n\n💳 Choose a payment method and pay exactly *{total}€*."
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['info'])
def cmd_info(msg):
    chat_id = msg.chat.id
    text = "ℹ️ Product: Zafferano 100% puro (Italian saffron)\n\nPrices:\n"
    for qty, price in PRODUCTS['zafferano'].items():
        text += f"- {qty}: {price}€\n"
    bot.send_message(chat_id, text)

@bot.message_handler(commands=['contacts'])
def cmd_contacts(msg):
    bot.send_message(msg.chat.id, "📞 Contacts:\nTelegram: @SlyanuS7\nEmail: brandingshopy@gmail.com")

# ---------------------------
# Handling quantity picks & simple flow
# ---------------------------
@bot.message_handler(func=lambda m: (m.text in PRODUCTS['zafferano'].keys()) or (m.text == "⬅️ Back"))
def handle_selection(msg):
    chat_id = msg.chat.id
    text = msg.text
    if text == "⬅️ Back":
        cmd_start(msg)
        return
    # Add to cart
    user_cart.setdefault(chat_id, []).append({"product": "zafferano", "qty": text})
    user_stage[chat_id] = 'idle'
    bot.send_message(chat_id, f"✅ Added {text} of zafferano to your cart. Use /cart to view.")

# ---------------------------
# Callbacks (payments)
# ---------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    data = call.data
    # Prepare an order snapshot
    order = generate_order(chat_id)

    if data == "paypal_payment":
        # PayPal.me link (manual)
        total = order['total']
        paypal_url = f"https://paypal.me/{PAYPAL_ME_USERNAME}/{total}"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔗 Open PayPal.me", url=paypal_url))
        keyboard.add(types.InlineKeyboardButton("✅ I've paid (I will send TX ID)", callback_data=f"paypal_paid|{order['order_id']}"))
        bot.send_photo(chat_id,
                       "https://upload.wikimedia.org/wikipedia/commons/b/b5/PayPal.svg",
                       caption=f"💸 PayPal — please pay *exactly {total}€* for order {order['order_id']}. After payment press \"I've paid\" and send the transaction id or screenshot.",
                       parse_mode="Markdown",
                       reply_markup=keyboard)
        bot.answer_callback_query(call.id, "PayPal instructions sent.")

    elif data == "stripe_payment":
        # Create Stripe Checkout session with metadata (chat_id + order_id)
        try:
            line_items = []
            for item in order['cart']:
                price_eur = get_price(item['product'], item['qty'])
                line_items.append({
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {'name': f"{item['product'].capitalize()} {item['qty']}"},
                        'unit_amount': int(price_eur * 100),
                    },
                    'quantity': 1,
                })
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=f"{WEBHOOK_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{WEBHOOK_URL}/cancel",
                metadata={'chat_id': str(chat_id), 'order_id': order['order_id']}
            )
            # Send compact UI: logo + button
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("🔗 Open secure card payment", url=session.url))
            bot.send_photo(chat_id,
                           "https://files.stripe.com/docs/stripe_logo.png",
                           caption=f"💳 Stripe Checkout — order {order['order_id']}\nAmount: {order['total']}€",
                           reply_markup=keyboard)
            bot.answer_callback_query(call.id, "Stripe checkout created.")
        except Exception as e:
            print("Stripe session error:", e)
            bot.send_message(chat_id, f"❌ Error creating Stripe session: {e}")
            bot.answer_callback_query(call.id, "Error")

    elif data.startswith("paypal_paid|"):
        # user clicked "I've paid" — ask for tx id
        _, order_id = data.split("|", 1)
        user_stage[chat_id] = f'awaiting_paypal_tx|{order_id}'
        bot.send_message(chat_id, "✉️ Send here your PayPal transaction ID or a screenshot link. After verification we'll ask shipping details.")

# ---------------------------
# Messages while in stages (PayPal tx, shipping, etc.)
# ---------------------------
@bot.message_handler(func=lambda m: True)
def catch_all(msg):
    chat_id = msg.chat.id
    text = msg.text or ""
    stage = user_stage.get(chat_id, "")

    # PayPal transaction id step
    if stage.startswith('awaiting_paypal_tx'):
        # save tx and ask shipping
        _, order_id = stage.split("|",1)
        pending = pending_orders.get(order_id)
        if not pending:
            bot.send_message(chat_id, "Order not found. Use /cart to start again.")
            user_stage[chat_id] = ''
            return
        pending['paid'] = True
        pending['payment_method'] = 'paypal'
        pending['payment_info'] = {'tx': text, 'paid_at': now_str()}
        # ask shipping
        user_stage[chat_id] = f'awaiting_shipping|{order_id}'
        bot.send_message(chat_id, "✅ Thanks — TX saved. Now please send your shipping details (name, address, postal code, phone).")
        return

    # Shipping data step
    if stage.startswith('awaiting_shipping'):
        _, order_id = stage.split("|",1)
        pending = pending_orders.get(order_id)
        if not pending:
            bot.send_message(chat_id, "Order not found. Use /cart to start again.")
            user_stage[chat_id] = ''
            return
        # store shipping
        pending['shipping'] = {'text': text, 'collected_at': now_str()}
        # mark paid True if not set (stripe webhook should set, but for paypal flow we set earlier)
        pending['paid'] = True
        # notify admin + user via email and telegram
        admin_body = f"""New order received:
Order ID: {pending['order_id']}
Chat ID: {pending['chat_id']}
Created: {pending['created_at']}
Payment method: {pending.get('payment_method')}
Total: {pending['total']} €
Cart:
"""
        for it in pending['cart']:
            admin_body += f" - {it['product']} {it['qty']} -> {get_price(it['product'], it['qty'])}€\n"
        admin_body += f"\nShipping details:\n{pending['shipping']['text']}\nCollected at: {pending['shipping']['collected_at']}\n"
        # send Telegram admin message
        try:
            bot.send_message(ADMIN_ID, f"📦 New order {pending['order_id']} — total {pending['total']}€\nShipping: {pending['shipping']['text']}")
        except Exception as e:
            print("Error sending admin telegram msg:", e)
        # send emails
        if ADMIN_EMAIL:
            send_email(ADMIN_EMAIL, f"New order {pending['order_id']}", admin_body)
        # email to user
        user_email_body = f"Thanks for your order {pending['order_id']}!\nTotal: {pending['total']}€\nShipping details received:\n{pending['shipping']['text']}\nWe'll notify when shipped."
        # we don't have user's email automatically — ask user for email if unknown
        # Try to parse email from shipping text (simple search) - if none, ask:
        user_email = None
        # simple attempt:
        import re
        m = re.search(r'[\w\.-]+@[\w\.-]+', text)
        if m:
            user_email = m.group(0)
        if user_email:
            send_email(user_email, f"Order {pending['order_id']} confirmation", user_email_body)
            bot.send_message(chat_id, "✅ Shipping saved and confirmation email sent. Thank you!")
        else:
            bot.send_message(chat_id, "✅ Shipping saved. *Please reply with your email address* so we can send the receipt.", parse_mode="Markdown")
            user_stage[chat_id] = f'awaiting_user_email|{order_id}'
            return

        # clear stage
        user_stage[chat_id] = ''
        return

    # awaiting user email after shipping
    if stage.startswith('awaiting_user_email'):
        _, order_id = stage.split("|",1)
        pending = pending_orders.get(order_id)
        if not pending:
            user_stage[chat_id] = ''
            bot.send_message(chat_id, "Order not found.")
            return
        # save email and send confirmation
        email = text.strip()
        pending['customer_email'] = email
        user_email_body = f"Thanks for your order {pending['order_id']}!\nTotal: {pending['total']}€\nShipping details received:\n{pending['shipping']['text']}\nWe'll notify when shipped."
        send_email(email, f"Order {pending['order_id']} confirmation", user_email_body)
        bot.send_message(chat_id, "✅ Email saved and receipt sent. Thank you!")
        # notify admin too
        send_email(ADMIN_EMAIL, f"New order {pending['order_id']}", f"Order {pending['order_id']} details\nShipping: {pending['shipping']['text']}\nCustomer email: {email}")
        user_stage[chat_id] = ''
        return

    # default fallback: echo/help
    if text.startswith('/'):
        bot.send_message(chat_id, "Unknown command. Use /shop or /cart.")
    else:
        bot.send_message(chat_id, "I didn't understand that. Use /shop or /cart.")

# ---------------------------
# Stripe webhook endpoint
# ---------------------------
@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_ENDPOINT_SECRET)
    except Exception as e:
        print("❌ Stripe webhook verify failed:", e)
        return jsonify({'status': 'bad signature'}), 400

    # Handle checkout.session.completed
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.get('metadata', {})
        chat_id = int(metadata.get('chat_id', 0))
        order_id = metadata.get('order_id')
        order = pending_orders.get(order_id)
        # mark paid
        if order:
            order['paid'] = True
            order['payment_method'] = 'stripe'
            order['payment_info'] = {'session_id': session.get('id'), 'paid_at': now_str()}
            # ask user for shipping details
            try:
                bot.send_message(chat_id, f"✅ Payment received for order {order_id} ({order['total']}€).\nNow please send your shipping details (name, address, postal code, phone).")
                user_stage[chat_id] = f'awaiting_shipping|{order_id}'
            except Exception as e:
                print("Error sending stripe confirmation to user:", e)
        else:
            print("Stripe webhook: order_id not found in pending_orders:", order_id)

    return jsonify({'status': 'success'}), 200

# ---------------------------
# PayPal webhook (optional) - not implemented validation here
# ---------------------------
@app.route("/paypal-webhook", methods=['POST'])
def paypal_webhook():
    # If you set a PayPal webhook later, validate signatures here and mark orders accordingly.
    print("PayPal webhook received:", request.json)
    return jsonify({'status': 'ok'}), 200

# ---------------------------
# Simple endpoints for success/cancel pages used by Stripe checkout
# ---------------------------
@app.route("/success")
def success_page():
    return "<h2>✅ Payment succeeded. Please go back to the bot to complete shipping details.</h2>"

@app.route("/cancel")
def cancel_page():
    return "<h2>❌ Payment canceled. You can retry from the bot.</h2>"

# ---------------------------
# Telegram webhook root to receive updates from Telegram
# ---------------------------
@app.route("/", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    if not json_data:
        return "no json", 400
    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def root_get():
    return "Bot is live", 200

# ---------------------------
# Set webhook with Telegram (on start)
# ---------------------------
if WEBHOOK_URL:
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook set to", WEBHOOK_URL)
    except Exception as e:
        print("Error setting webhook:", e)
else:
    print("WEBHOOK_URL not set. Telegram webhook not configured.")

# ---------------------------
# Run Flask
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("Starting Flask on port", port)
    app.run(host="0.0.0.0", port=port)