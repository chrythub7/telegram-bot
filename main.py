import telebot
from telebot import types
import json
import os
from datetime import datetime

# === CONFIGURAZIONE === #
TOKEN = os.getenv("BOT_TOKEN", "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso")
ADMIN_ID = 6497093715  # <-- Inserisci qui il tuo ID Telegram (da @userinfobot)
DATA_FILE = "utenti.json"

bot = telebot.TeleBot(TOKEN)

# === FUNZIONE: Caricamento/Salvataggio utenti === #
def carica_utenti():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def salva_utenti(dati):
    with open(DATA_FILE, "w") as f:
        json.dump(dati, f, indent=4)

utenti = carica_utenti()

# === /start === #
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)
    if user_id not in utenti:
        utenti[user_id] = {
            "nome": message.from_user.first_name,
            "ruolo": "user",
            "data_registrazione": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        salva_utenti(utenti)
        bot.reply_to(message, "🎉 Registrato con successo!")

    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("📋 Menu", callback_data="menu")
    btn2 = types.InlineKeyboardButton("📎 Link utili", callback_data="links")
    btn3 = types.InlineKeyboardButton("💸 Pagamenti", callback_data="pagamenti")
    markup.add(btn1, btn2, btn3)
    bot.send_message(message.chat.id, "👋 Benvenuto nel bot interattivo!", reply_markup=markup)

# === Gestione menu === #
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "menu":
        menu_principale(call)
    elif call.data == "links":
        invia_links(call)
    elif call.data == "pagamenti":
        mostra_pagamenti(call)
    elif call.data == "broadcast":
        if call.message.chat.id == ADMIN_ID:
            bot.send_message(call.message.chat.id, "✉️ Invia ora il messaggio da mandare a tutti gli utenti.")
            bot.register_next_step_handler(call.message, invia_broadcast)
        else:
            bot.answer_callback_query(call.id, "❌ Solo l'admin può usare questo comando!")

# === Menu Principale === #
def menu_principale(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📁 Ricevi file", callback_data="file"))
    markup.add(types.InlineKeyboardButton("❌ Chiudi", callback_data="chiudi"))
    bot.edit_message_text("📋 Menu interattivo:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# === Link automatici === #
def invia_links(call):
    links = "🔗 Link utili:\n\n👉 PayPal: https://paypal.me/esempio\n👉 Crypto Wallet: https://example.com/crypto"
    bot.edit_message_text(links, call.message.chat.id, call.message.message_id)

# === Pagamenti (solo link) === #
def mostra_pagamenti(call):
    text = (
        "💳 Scegli il metodo di pagamento:\n\n"
        "➡️ [PayPal](https://paypal.me/esempio)\n"
        "➡️ [Crypto (USDT)](https://example.com/crypto)"
    )
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

# === Invio file === #
@bot.callback_query_handler(func=lambda c: c.data == "file")
def invia_file(call):
    bot.send_document(call.message.chat.id, open("file_esempio.pdf", "rb"))

# === Broadcast Admin === #
def invia_broadcast(message):
    testo = message.text
    for user_id in utenti.keys():
        try:
            bot.send_message(user_id, f"📢 Messaggio globale:\n\n{testo}")
        except:
            pass
    bot.send_message(ADMIN_ID, "✅ Broadcast inviato a tutti!")

# === Comando /admin === #
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 Invia broadcast", callback_data="broadcast"))
        bot.send_message(message.chat.id, "⚙️ Pannello Admin:", reply_markup=markup)
    else:
        bot.reply_to(message, "❌ Non sei autorizzato.")

# === POLLING === #
if __name__ == "__main__":
    print("✅ Bot avviato, polling in corso...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

