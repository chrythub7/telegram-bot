from flask import Flask, request, jsonify
from telebot import TeleBot, types
import os
from datetime import datetime
import stripe

# ===========================
#   CONFIGURAZIONE BASE
# ===========================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET")

# Controllo ENV
missing_env = [k for k, v in {
    "BOT_TOKEN": TOKEN,
    "ADMIN_ID": ADMIN_ID,
    "STRIPE_SECRET_KEY": STRIPE_SECRET_KEY,
    "STRIPE_ENDPOINT_SECRET": STRIPE_ENDPOINT_SECRET
}.items() if not v]
if missing_env:
    print(f"⚠️ ERRORE: mancano variabili ENV -> {', '.join(missing_env)}")
else:
    print("✅ Tutte le variabili ENV trovate!")

bot = TeleBot(TOKEN)
app = Flask(__name__)
stripe.api_key = STRIPE_SECRET_KEY

# ===========================
#   PRODOTTI
# ===========================
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
user_cart = {}

# ===========================
#   FUNZIONI
# ===========================
def get_price(product, qty):
    return PRODUCTS[product][qty]

def format_cart(chat_id):
    cart = user_cart.get(chat_id, [])
    if not cart:
        return "🛒 Il tuo carrello è vuoto.", 0
    text = "🛒 *Carrello:*\n\n"
    total = 0
    for item in cart:
        price = get_price(item['product'], item['qty'])
        text += f"{item['product'].capitalize()} - {item['qty']} → {price}€\n"
        total += price
    text += f"\n💰 *Totale:* {total}€"
    return text, total

# ===========================
#   COMANDI BOT
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_cart[chat_id] = []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("/shop", "/cart", "/info", "/contacts")
    bot.send_message(chat_id, "👋 Benvenuto! Scegli un'opzione:", reply_markup=markup)

@bot.message_handler(commands=['shop'])
def shop(message):
    chat_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for qty in PRODUCTS["zafferano"]:
        markup.add(qty)
    markup.add("⬅️ Indietro")
    bot.send_message(chat_id, "🌿 Scegli la quantità:", reply_markup=markup)

@bot.message_handler(commands=['cart'])
def show_cart(message):
    chat_id = message.chat.id
    text, total = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    if total > 0:
        text += f"\n\n💳 Scegli un metodo di pagamento e paga *esattamente {total}€*:"
        markup.add(
            types.InlineKeyboardButton("💸 PayPal", callback_data="paypal_payment"),
            types.InlineKeyboardButton("💳 Carta (Stripe)", callback_data="card_payment")
        )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in PRODUCTS["zafferano"] or m.text == "⬅️ Indietro")
def select_quantity(message):
    chat_id = message.chat.id
    if message.text == "⬅️ Indietro":
        start(message)
        return
    user_cart[chat_id].append({"product": "zafferano", "qty": message.text})
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    bot.send_message(chat_id, f"✅ Aggiunto {message.text} di zafferano al carrello.\n🕒 {now}\nUsa /cart per vedere il carrello.")

# ===========================
#   CALLBACK PAGAMENTI
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    _, total = format_cart(chat_id)

    if call.data == "paypal_payment":
        paypal_url = f"https://paypal.me/ChristianMadafferi/{total}"
        bot.send_photo(
            chat_id,
            "https://upload.wikimedia.org/wikipedia/commons/b/b5/PayPal.svg",
            caption=f"💸 *Pagamento PayPal*\n\n➡️ [Paga qui]({paypal_url})\n\n⚠️ Invia *esattamente {total}€*.",
            parse_mode="Markdown"
        )

    elif call.data == "card_payment":
        try:
            line_items = [{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': f"{item['product'].capitalize()} {item['qty']}"},
                    'unit_amount': get_price(item['product'], item['qty']) * 100,
                },
                'quantity': 1,
            } for item in user_cart.get(chat_id, [])]

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url='https://telegram-bot-sohm.onrender.com/success',
                cancel_url='https://telegram-bot-sohm.onrender.com/cancel',
            )

            bot.send_photo(
                chat_id,
                "https://files.stripe.com/docs/stripe_logo.png",
                caption=f"💳 *Pagamento con Carta*\n\n➡️ [Paga in sicurezza]({session.url})\n\n⚠️ Paga *esattamente {total}€*.",
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.send_message(chat_id, f"❌ Errore nel pagamento: {str(e)}")

# ===========================
#   FLASK SERVER
# ===========================
@app.route("/", methods=["GET"])
def index():
    return "Bot attivo ✅", 200

@app.route("/", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/success")
def success_page():
    return "<h2>✅ Pagamento completato con successo!</h2>"

@app.route("/cancel")
def cancel_page():
    return "<h2>❌ Pagamento annullato.</h2>"

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_ENDPOINT_SECRET)
    except Exception as e:
        print(f"⚠️ Errore webhook Stripe: {e}")
        return jsonify(success=False), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        bot.send_message(ADMIN_ID, f"✅ Pagamento ricevuto!\n💰 Totale: {session['amount_total']/100}€\n🕒 {now}")
    return jsonify(success=True), 200

# ===========================
#   WEBHOOK TELEGRAM
# ===========================
WEBHOOK_URL = "https://telegram-bot-sohm.onrender.com"
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# ===========================
#   AVVIO SERVER
# ===========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)