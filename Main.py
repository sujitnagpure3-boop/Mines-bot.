import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import time
from flask import Flask
from threading import Thread

# --- RENDER WEB SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Mines Bot is Online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- BOT CONFIGURATION ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set.")

ADMIN_ID = int(os.environ.get("ADMIN_USER_ID", "0"))

bot = telebot.TeleBot(TOKEN)

# --- YOUR GAME DATA & LOGIC ---
user_data = {}
username_index = {}
DAILY_BONUS = 500
DAILY_COOLDOWN = 86400
CLICK_COOLDOWN = 1.5

def get_stats(user_id, username=None):
    if user_id not in user_data:
        user_data[user_id] = {
            "balance": 1000, "active_game": False, "mines": [], "opened": [],
            "bet": 0, "last_daily": 0, "username": username or f"Player{user_id}",
            "games_played": 0, "wins": 0, "losses": 0, "biggest_win": 0,
            "last_click": 0, "mine_count": 3,
        }
    if username:
        user_data[user_id]["username"] = username
        username_index[username.lower()] = user_id
    return user_data[user_id]

def calculate_win(bet, opened_count, mine_count=3):
    per_tile = round(mine_count * 0.05, 2)
    multiplier = 1 + (opened_count * per_tile)
    return int(bet * multiplier)

def multiplier_per_tile(mine_count):
    return round(mine_count * 0.05, 2)

def send_board(chat_id, user_id, text, message_id=None):
    stats = user_data[user_id]
    markup = InlineKeyboardMarkup()
    for r in range(5):
        row_btns = []
        for c in range(5):
            idx = r * 5 + c
            if idx in stats["opened"]:
                row_btns.append(InlineKeyboardButton("💎", callback_data="none"))
            else:
                row_btns.append(InlineKeyboardButton("❎", callback_data=f"click_{idx}"))
        markup.row(*row_btns)
    if len(stats["opened"]) > 0:
        current_win = calculate_win(stats["bet"], len(stats["opened"]), stats.get("mine_count", 3))
        markup.add(InlineKeyboardButton(f"💰 Cash Out ({current_win} credits)", callback_data="cashout"))
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def reveal_board(chat_id, user_id, message_id, hit_index=None):
    stats = user_data[user_id]
    markup = InlineKeyboardMarkup()
    for r in range(5):
        row_btns = []
        for c in range(5):
            idx = r * 5 + c
            if idx in stats["mines"]:
                label = "💥" if idx == hit_index else "💣"
                row_btns.append(InlineKeyboardButton(label, callback_data="none"))
            elif idx in stats["opened"]:
                row_btns.append(InlineKeyboardButton("💎", callback_data="none"))
            else:
                row_btns.append(InlineKeyboardButton("❎", callback_data="none"))
        markup.row(*row_btns)
    bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)

# --- COMMAND HANDLERS ---

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    user = message.from_user
    stats = get_stats(user.id, user.username or user.first_name)
    bot.reply_to(message, f"👋 Hey *{user.first_name}*!\n\n💣 Use `/mines <bet>` to play!", parse_mode="Markdown")

@bot.message_handler(commands=["mines"])
def start_game(message):
    user = message.from_user
    stats = get_stats(user.id, user.username or user.first_name)
    if stats["active_game"]:
        bot.reply_to(message, "❌ Finish your current game first!")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/mines <amount>`", parse_mode="Markdown")
        return
    bet = int(args[1])
    if bet > stats["balance"]:
        bot.reply_to(message, "❌ Insufficient balance!")
        return
    stats["balance"] -= bet
    stats["bet"] = bet
    stats["active_game"] = True
    stats["opened"] = []
    stats["mine_count"] = 3
    stats["mines"] = random.sample(range(25), 3)
    send_board(message.chat.id, user.id, "🎮 *Game Started!*")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    stats = get_stats(user_id)
    if not stats["active_game"]: return
    if call.data.startswith("click_"):
        idx = int(call.data.split("_")[1])
        if idx in stats["mines"]:
            stats["active_game"] = False
            reveal_board(call.message.chat.id, user_id, call.message.message_id, hit_index=idx)
            bot.edit_message_text(f"💥 *BOOM!* You lost *{stats['bet']} credits*.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        else:
            stats["opened"].append(idx)
            send_board(call.message.chat.id, user_id, "💎 *Safe!*", call.message.message_id)
    elif call.data == "cashout":
        win = calculate_win(stats["bet"], len(stats["opened"]), 3)
        stats["balance"] += win
        stats["active_game"] = False
        bot.edit_message_text(f"✅ *Cashed Out!* +{win} credits.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# --- STARTUP ---
if __name__ == "__main__":
    keep_alive() # Essential for Render
    print("Bot is starting...")
    bot.infinity_polling()
