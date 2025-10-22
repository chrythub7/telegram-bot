from flask import Flask, request
from telebot import TeleBot, types
import os
from datetime import datetime

TOKEN = "8075827806:AAFLwKd9_jJ2s39eGK_64gs2X3CWJPlwwso"
ADMIN_ID = 6497093715
bot = TeleBot(TOKEN)

# Prodotto di esempio
PRODUCTS = {
    "Zafferano": {
        "1g": {"price": 8, "discount": 0},
        "3g": {"price": 24, "discount": 0},
        "5g": {"price": 40, "discount": 0},
        "10g": {"price": 80, "discount": 0},
        "30g": {"price": 216, "discount": 10},
        "50g": {"price": 340, "discount": 15},
        "70g": {"price": 448, "discount": 20},
        "100g": {"price": 600, "discount": 25},
    }
}

USER_CART = {}

# ===========================
# MENU PRINCIPALE
# ===========================
def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🛍 Shop", "🛒 Cart")
    markup.row("ℹ️ Info", "📞 Contacts")
    bot.send_message(chat_id, "👋 Benvenuto! Seleziona un'opzione:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    main_menu(message.chat.id)

# ===========================
# INFO E CONTACTS
# ===========================
@bot.message_handler(commands=['info'])
@bot.message_handler(func=lambda m: m.text == "ℹ️ Info")
def info_command(message):
    text = "🌿 *Listino Zafferano Italiano:*\n\n"
    for grams, data in PRODUCTS["Zafferano"].items():
        if data["discount"] > 0:
            text += f"• {grams} – {data['price']}€  (🟢 Sconto {data['discount']}%)\n"
        else:
            text += f"• {grams} – {data['price']}€\n"
    text += "\n💰 Prezzo base: 8€/g\n🇮🇹 100% Zafferano dell’Aquila"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['contacts'])
@bot.message_handler(func=lambda m: m.text == "📞 Contacts")
def contacts_command(message):
    contact_text = (
        "📞 *Contatti:*\n\n"
        "👤 Admin: @ChristianMadafferi\n"
        "✉️ Email: example@email.com\n"
        "📦 Spedizioni in tutta Italia."
    )
    bot.send_message(message.chat.id, contact_text, parse_mode="Markdown")

# ===========================
# SHOP
# ===========================
@bot.message_handler(func=lambda m: m.text == "🛍 Shop")
def open_shop(message):
    markup = types.InlineKeyboardMarkup()
    for product in PRODUCTS.keys():
        markup.add(types.InlineKeyboardButton(text=product, callback_data=f"product_{product}"))
    bot.send_message(message.chat.id, "🛍 Scegli un prodotto:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("product_"))
def choose_quantity(call):
    product = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup()
    for grams, data in PRODUCTS[product].items():
        discount_text = f" ({data['discount']}% off)" if data["discount"] > 0 else ""
        markup.add(types.InlineKeyboardButton(
            text=f"{grams} - {data['price']}€{discount_text}",
            callback_data=f"add_{product}_{grams}"
        ))
    markup.add(types.InlineKeyboardButton(text="⬅️ Menu principale", callback_data="back_main"))
    bot.edit_message_text(chat_id=call.message.chat.id,
                          message_id=call.message.message_id,
                          text=f"Scegli la quantità di *{product}:*",
                          parse_mode="Markdown",
                          reply_markup=markup)

# Aggiungi al carrello
@bot.callback_query_handler(func=lambda c: c.data.startswith("add_"))
def add_to_cart(call):
    _, product, grams = call.data.split("_")
    price = PRODUCTS[product][grams]["price"]
    if call.from_user.id not in USER_CART:
        USER_CART[call.from_user.id] = []
    USER_CART[call.from_user.id].append({"product": product, "quantity": grams, "price": price})
    bot.send_message(call.message.chat.id, f"✅ Aggiunto {grams} di {product} al carrello!")
    main_menu(call.message.chat.id)

# Visualizza carrello
@bot.message_handler(commands=['cart'])
@bot.message_handler(func=lambda m: m.text == "🛒 Cart")
def view_cart(message):
    user_id = message.from_user.id
    if user_id not in USER_CART or len(USER_CART[user_id]) == 0:
        bot.send_message(message.chat.id, "🛒 Il tuo carrello è vuoto.")
        return
    cart_items = USER_CART[user_id]
    total = sum(item["price"] for item in cart_items)
    text = "🛍 *Il tuo carrello:*\n\n"
    for item in cart_items:
        text += f"- {item['product']} {item['quantity']} → {item['price']}€\n"
    text += f"\n💰 Totale: {total:.2f}€"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ===========================
# FLASK SERVER
# ===========================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200

@app.route("/", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    update = types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# ===========================
WEBHOOK_URL = "https://telegram-bot-sohm.onrender.com"
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)