import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import time
from flask import Flask
from threading import Thread

# --- WEB SERVER FOR RENDER ---
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
ADMIN_ID = int(os.environ.get("ADMIN_USER_ID", "0"))
bot = telebot.TeleBot(TOKEN)

# --- GAME DATA ---
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
    return int(bet * (1 + (opened_count * per_tile)))

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
    if stats["opened"]:
        win = calculate_win(stats["bet"], len(stats["opened"]), stats.get("mine_count", 3))
        markup.add(InlineKeyboardButton(f"💰 Cash Out ({win} credits)", callback_data="cashout"))
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# --- HANDLERS ---
@bot.message_handler(commands=["start"])
def welcome(message):
    get_stats(message.from_user.id, message.from_user.username)
    bot.reply_to(message, "🎮 Welcome! Use `/mines <bet>` to start.")

@bot.message_handler(commands=["mines"])
def start_game(message):
    user_id = message.from_user.id
    stats = get_stats(user_id, message.from_user.username)
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/mines 100`")
        return
    bet = int(args[1])
    if bet > stats["balance"]:
        bot.reply_to(message, "❌ Not enough credits!")
        return
    stats["balance"] -= bet
    stats["bet"], stats["active_game"], stats["opened"] = bet, True, []
    stats["mine_count"], stats["mines"] = 3, random.sample(range(25), 3)
    send_board(message.chat.id, user_id, "🎮 Game Started!")

@bot.callback_query_handler(func=lambda call: True)
def handle_clicks(call):
    user_id = call.from_user.id
    stats = get_stats(user_id)
    if not stats["active_game"]: return
    if call.data.startswith("click_"):
        idx = int(call.data.split("_")[1])
        if idx in stats["mines"]:
            stats["active_game"] = False
            bot.edit_message_text(f"💥 BOOM! Lost {stats['bet']}.", call.message.chat.id, call.message.message_id)
        else:
            stats["opened"].append(idx)
            send_board(call.message.chat.id, user_id, "💎 Safe!", call.message.message_id)
    elif call.data == "cashout":
        win = calculate_win(stats["bet"], len(stats["opened"]), 3)
        stats["balance"] += win
        stats["active_game"] = False
        bot.edit_message_text(f"✅ Won {win}!", call.message.chat.id, call.message.message_id)

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
