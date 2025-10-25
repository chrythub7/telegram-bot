import os
import stripe
from flask import Flask, request, jsonify
from telegram import Bot

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET")
FORNITORE_NUMERO = os.getenv("FORNITORE_NUMERO", "+39 333 123 4567")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = Bot(token=BOT_TOKEN)
stripe.api_key = STRIPE_SECRET_KEY

app = Flask(__name__)

# === ROUTES ===

@app.route("/")
def home():
    return "✅ Bot Telegram attivo su Render", 200


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)
    if not update or "message" not in update:
        return "no update", 200

    chat_id = update["message"]["chat"]["id"]
    text = update["message"].get("text", "").lower()

    if text == "/start":
        checkout_url = crea_sessione_stripe(chat_id)
        bot.send_message(
            chat_id=chat_id,
            text=(
                "💳 Benvenuto!\n"
                "Per ricevere il numero del fornitore, effettua il pagamento qui:\n\n"
                f"{checkout_url}"
            ),
        )
    else:
        bot.send_message(chat_id=chat_id, text="Scrivi /start per iniziare.")

    return "ok", 200


@app.route("/stripe_webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", None)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_ENDPOINT_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return "Invalid signature", 400
    except Exception:
        return "Webhook error", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        telegram_id = session.get("metadata", {}).get("telegram_id")
        email = session.get("customer_email", "email non disponibile")

        if telegram_id:
            # Invia messaggio all'utente
            bot.send_message(
                chat_id=telegram_id,
                text=(
                    "✅ Pagamento verificato con successo!\n\n"
                    f"Ecco il numero del fornitore:\n📞 {FORNITORE_NUMERO}"
                ),
            )

            # Notifica all'amministratore
            if ADMIN_ID:
                bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=(
                        f"💰 Nuovo pagamento ricevuto da utente {telegram_id}\n"
                        f"📧 Email: {email}"
                    ),
                )

    return jsonify(success=True)


# === FUNZIONE STRIPE ===

def crea_sessione_stripe(telegram_id):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": "Accesso al numero del fornitore"},
                    "unit_amount": 1000,  # 10€ in centesimi
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=f"{WEBHOOK_URL}success",
        cancel_url=f"{WEBHOOK_URL}cancel",
        metadata={"telegram_id": str(telegram_id)},
    )
    return session.url


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)