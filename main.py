from telebot import TeleBot

bot = TeleBot("8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso")  # <-- metti qui il token di BotFather

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Ciao! Il mio bot è online 24/7 su Render!")


bot.polling()
