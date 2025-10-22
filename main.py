from telebot import TeleBot

bot = TeleBot("INSERISCI_IL_TUO_TOKEN")  # <-- metti qui il token di BotFather

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Ciao! Il mio bot è online 24/7 su Render!")

bot.polling()