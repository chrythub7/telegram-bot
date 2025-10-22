from telebot import TeleBot

# Inserisci il tuo token
TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
bot = TeleBot(TOKEN)

# ====== /start ======
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Ciao! Qui ci sono tutti i servizi disponibili!")

# ====== /help ======
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "📖 Comandi disponibili:\n/start - Avvia il bot\n/help - Mostra questo messaggio")

# ====== RISPOSTA AUTOMATICA ======
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Hai scritto: {message.text}")

# ====== AVVIO ======
print("✅ Bot avviato...")
bot.infinity_polling()
