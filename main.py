import os
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import stripe

# ========= CONFIGURAZIONE =========
BOT_TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
STRIPE_SECRET_KEY = "INSERISCI_LA_TUA_CHIAVE_STRIPE"
EMAIL_USER = "madafferichristian@gmail.com"
EMAIL_PASS = "zaze mcbc yzle rsug"
ADMIN_EMAIL = "brandingshopy@gmail.com"

stripe.api_key = STRIPE_SECRET_KEY
app = Flask(__name__)

# ========= FASI DELLA CONVERSAZIONE =========
ASK_PAYMENT, ASK_SHIPPING = range(2)

# ========= FUNZIONI DI SUPPORTO =========
def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
    except Exception as e:
        print(f"Errore invio email: {e}")

# ========= BOT TELEGRAM =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 Paga ora", callback_data="pay")]
    ]
    await update.message.reply_text(
        "Benvenuto! Premi il pulsante qui sotto per completare il pagamento.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "pay":
        await query.edit_message_text("Perfetto! Inserisci qui il tuo nome e cognome per procedere con il pagamento.")
        return ASK_PAYMENT

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = update.message.text
    context.user_data["name"] = user_info

    # Simulazione pagamento completato
    await update.message.reply_text("✅ Pagamento ricevuto correttamente! Ora inserisci i tuoi dati di spedizione (indirizzo completo, CAP, città, numero di telefono).")
    return ASK_SHIPPING

async def handle_shipping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shipping_info = update.message.text
    name = context.user_data.get("name")

    # Invia email al cliente
    user_email_body = f"""
Ciao {name},

✅ Il tuo pagamento è stato completato con successo!

Grazie per aver acquistato da noi. Ti ricontatteremo appena la spedizione sarà pronta.

Dettagli spedizione:
{shipping_info}

- Team BrandingShopy
"""
    send_email(to_email=context.user_data.get("email", EMAIL_USER), subject="Pagamento completato ✅", body=user_email_body)

    # Invia email all'admin
    admin_email_body = f"""
📦 Nuovo ordine ricevuto!

Cliente: {name}
Dettagli spedizione:
{shipping_info}

Email cliente: {context.user_data.get("email", "non specificata")}
"""
    send_email(to_email=ADMIN_EMAIL, subject="Nuovo ordine ricevuto 📦", body=admin_email_body)

    await update.message.reply_text("Perfetto! Tutto completato ✅ Ti arriverà un'email di conferma a breve.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operazione annullata.")
    return ConversationHandler.END

# ========= FLASK (PER STRIPE O WEBHOOKS) =========
@app.route('/')
def home():
    return "Bot attivo!"

# ========= MAIN =========
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment)],
            ASK_SHIPPING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shipping)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button))

    print("Bot avviato 🚀")
    application.run_polling()

if __name__ == "__main__":
    main()