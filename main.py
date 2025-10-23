import os
import smtplib
from email.mime.text import MIMEText
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import stripe

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
PAYPAL_URL = os.getenv("PAYPAL_URL")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

stripe.api_key = STRIPE_API_KEY

# Stati conversazione spedizione
NAME, ADDRESS, CITY, PHONE = range(4)
user_shipping_data = {}

# -------- FUNZIONE EMAIL --------
def send_email(subject, body, recipient):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

# -------- START --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛍️ Acquista ora", callback_data="buy_product")]
    ]
    await update.message.reply_text("Benvenuto! Scegli un prodotto per iniziare:", reply_markup=InlineKeyboardMarkup(keyboard))

# -------- SELEZIONE PRODOTTO --------
async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = 19.99  # prezzo esempio

    keyboard = [
        [InlineKeyboardButton("💳 Paga con Stripe", callback_data=f"stripe_{price}")],
        [InlineKeyboardButton("🅿️ Paga con PayPal", callback_data=f"paypal_{price}")]
    ]
    await query.message.reply_text(
        f"💰 Prezzo totale: {price}€\nScegli il metodo di pagamento:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# -------- PAGAMENTO STRIPE --------
async def handle_stripe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = float(query.data.split("_")[1])

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {"name": "Ordine Premium"},
                    "unit_amount": int(amount * 100)
                },
                "quantity": 1
            }],
            mode="payment",
            success_url="https://t.me/tuobotusername?start=success",
            cancel_url="https://t.me/tuobotusername?start=cancel"
        )

        img_url = "https://upload.wikimedia.org/wikipedia/commons/a/a3/Stripe_logo%2C_revised_2016.png"
        keyboard = [[InlineKeyboardButton("🔗 Procedi al pagamento", url=session.url)]]
        await query.message.reply_photo(
            img_url,
            caption=f"💳 Clicca qui sotto per completare il pagamento di *{amount}€* su Stripe:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        await query.message.reply_text(f"❌ Errore Stripe: {e}")

# -------- PAGAMENTO PAYPAL --------
async def handle_paypal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = float(query.data.split("_")[1])

    img_url = "https://upload.wikimedia.org/wikipedia/commons/b/b5/PayPal.svg"
    keyboard = [[InlineKeyboardButton("🔗 Paga con PayPal", url=PAYPAL_URL)]]
    await query.message.reply_photo(
        img_url,
        caption=f"🅿️ Completa il pagamento di *{amount}€* con PayPal.\n\nDopo aver pagato, torna qui e scrivi /spedizione per inserire i tuoi dati.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# -------- RACCOLTA DATI DOPO PAGAMENTO --------
async def start_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Pagamento ricevuto!\nOra inserisci i tuoi *dati di spedizione*.\n\nScrivi il tuo *nome e cognome*:", parse_mode="Markdown")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_shipping_data[update.effective_user.id] = {"name": update.message.text}
    await update.message.reply_text("🏠 Ora scrivi il *tuo indirizzo completo*:", parse_mode="Markdown")
    return ADDRESS

async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_shipping_data[update.effective_user.id]["address"] = update.message.text
    await update.message.reply_text("🏙️ Inserisci *città e CAP*:", parse_mode="Markdown")
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_shipping_data[update.effective_user.id]["city"] = update.message.text
    await update.message.reply_text("📞 Infine, scrivi *il tuo numero di telefono*:", parse_mode="Markdown")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_shipping_data[update.effective_user.id]["phone"] = update.message.text
    data = user_shipping_data[update.effective_user.id]

    # Email all'utente
    user_email_text = (
        f"Grazie per il tuo ordine!\n\n"
        f"I tuoi dati di spedizione:\n"
        f"👤 {data['name']}\n🏠 {data['address']}\n🏙️ {data['city']}\n📞 {data['phone']}\n\n"
        f"Ti contatteremo appena la spedizione sarà partita 🚚"
    )
    send_email("Conferma ordine", user_email_text, update.effective_user.first_name + "@example.com")

    # Email all'amministratore
    admin_email_text = (
        f"📦 NUOVO ORDINE RICEVUTO\n\n"
        f"👤 Nome: {data['name']}\n"
        f"🏠 Indirizzo: {data['address']}\n"
        f"🏙️ Città: {data['city']}\n"
        f"📞 Telefono: {data['phone']}\n\n"
        f"Effettuato tramite bot Telegram."
    )
    send_email("Nuovo ordine ricevuto", admin_email_text, ADMIN_EMAIL)

    await update.message.reply_text("📦 Perfetto! Dati inviati correttamente.\nRiceverai un’email di conferma.")
    return ConversationHandler.END

# -------- HANDLERS --------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buy_product, pattern="^buy_product$"))
    app.add_handler(CallbackQueryHandler(handle_stripe, pattern="^stripe_"))
    app.add_handler(CallbackQueryHandler(handle_paypal, pattern="^paypal_"))

    checkout_conv = ConversationHandler(
        entry_points=[CommandHandler("spedizione", start_shipping)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[]
    )
    app.add_handler(checkout_conv)

    app.run_polling()

if __name__ == "__main__":
    main()