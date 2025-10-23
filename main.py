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
user_state = {}

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
#   COMANDI
# ===========================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_cart[chat_id] = []
    user_state.pop(chat_id, None)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("/shop", "/cart", "/info", "/contacts")
    bot.send_message(chat_id, "👋 Benvenuto! Scegli un'opzione:", reply_markup=markup)

@bot.message_handler(commands=['shop'])
def shop(message):
    chat_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for qty in PRODUCTS["zafferano"]:
        markup.add(qty)
    markup.add("⬅️ Indietro")
    bot.send_message(chat_id, "🌿 Scegli la quantità di zafferano:", reply_markup=markup)
    user_state[chat_id] = "select_qty"

@bot.message_handler(commands=['cart'])
def show_cart(message):
    chat_id = message.chat.id
    text, total = format_cart(chat_id)
    markup = types.InlineKeyboardMarkup()
    if total > 0:
        text += f"\n\n📦 Dopo il pagamento ti verrà chiesto l’indirizzo di spedizione."
        markup.add(
            types.InlineKeyboardButton("💸 PayPal", callback_data="paypal_payment"),
            types.InlineKeyboardButton("💳 Carta (Stripe)", callback_data="card_payment")
        )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# ===========================
#   LOGICA SELEZIONE PRODOTTI
# ===========================
@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    chat_id = message.chat.id
    state = user_state.get(chat_id)

    if state == "select_qty":
        if message.text == "⬅️ Indietro":
            start(message)
            return
        if message.text in PRODUCTS["zafferano"]:
            user_cart[chat_id].append({"product": "zafferano", "qty": message.text})
            now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            bot.send_message(chat_id, f"✅ Aggiunto {message.text} di zafferano al carrello.\n🕒 {now}\nUsa /cart per vedere il carrello.")
            user_state.pop(chat_id, None)
            return

    elif state == "awaiting_address":
        address = message.text.strip()
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        bot.send_message(chat_id, f"🏠 Indirizzo ricevuto:\n{address}\n\n✅ L’ordine è stato registrato con successo!\n🕒 {now}")
        bot.send_message(ADMIN_ID, f"📦 Nuovo ordine da @{message.from_user.username or message.chat.first_name}\n\n🏠 {address}")
        user_state.pop(chat_id, None)

# ===========================
#   PAGAMENTI
# ===========================
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id
    _, total = format_cart(chat_id)

    if call.data == "paypal_payment":
        paypal_url = f"https://paypal.me/ChristianMadafferi/{total}"
        bot.send_message(
            chat_id,
            f"💸 *Pagamento PayPal*\n\n➡️ [Paga qui]({paypal_url})\n\nDopo aver pagato, invia l’indirizzo di spedizione.",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        user_state[chat_id] = "awaiting_address"

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
                success_url=f"https://telegram-bot-sohm.onrender.com/success?chat_id={chat_id}",
                cancel_url='https://telegram-bot-sohm.onrender.com/cancel'
            )

            bot.send_message(
                chat_id,
                f"💳 *Pagamento con Carta*\n\n➡️ [Paga in sicurezza]({session.url})\n\nDopo il pagamento, inserisci il tuo indirizzo di spedizione.",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            user_state[chat_id] = "awaiting_address"

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
    chat_id = request.args.get("chat_id")
    if chat_id:
        bot.send_message(chat_id, "✅ Pagamento completato! Ora inviami il tuo indirizzo di spedizione 🏠")
        user_state[int(chat_id)] = "awaiting_address"
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
        bot.send_message(ADMIN_ID, f"✅ Pagamento ricevuto da Stripe!\n💰 Totale: {session['amount_total']/100}€")
    return jsonify(success=True), 200

# ===========================
#   AVVIO SERVER
# ===========================
WEBHOOK_URL = "https://telegram-bot-sohm.onrender.com"
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)