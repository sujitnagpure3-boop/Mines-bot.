import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
from flask import Flask
from threading import Thread

# --- WEB SERVER FOR HOSTING ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Mines Bot is Online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- BOT CONFIGURATION ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set.")

bot = telebot.TeleBot(TOKEN)

# --- GAME DATA ---
user_data = {}

# --- FUNCTIONS ---

def get_stats(user_id, username=None):
    if user_id not in user_data:
        user_data[user_id] = {
            "balance": 1000,
            "active_game": False,
            "mines": [],
            "opened": [],
            "bet": 0,
            "username": username or f"Player{user_id}"
        }

    return user_data[user_id]


def calculate_win(bet, opened_count, mine_count=3):
    multiplier = 1 + (opened_count * (mine_count * 0.05))
    return int(bet * multiplier)


def send_board(chat_id, user_id, text, message_id=None):
    stats = user_data[user_id]

    markup = InlineKeyboardMarkup()

    for r in range(5):
        row = []

        for c in range(5):
            idx = r * 5 + c

            if idx in stats["opened"]:
                row.append(
                    InlineKeyboardButton("💎", callback_data="none")
                )
            else:
                row.append(
                    InlineKeyboardButton("❎", callback_data=f"click_{idx}")
                )

        markup.row(*row)

    # Cashout button
    if len(stats["opened"]) > 0:
        current_win = calculate_win(
            stats["bet"],
            len(stats["opened"])
        )

        markup.add(
            InlineKeyboardButton(
                f"💰 Cash Out ({current_win})",
                callback_data="cashout"
            )
        )

    if message_id:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=markup,
            parse_mode="Markdown"
        )


def reveal_board(chat_id, user_id, message_id, hit_index=None):
    stats = user_data[user_id]

    markup = InlineKeyboardMarkup()

    for r in range(5):
        row = []

        for c in range(5):
            idx = r * 5 + c

            if idx in stats["mines"]:
                label = "💥" if idx == hit_index else "💣"
                row.append(
                    InlineKeyboardButton(label, callback_data="none")
                )

            elif idx in stats["opened"]:
                row.append(
                    InlineKeyboardButton("💎", callback_data="none")
                )

            else:
                row.append(
                    InlineKeyboardButton("❎", callback_data="none")
                )

        markup.row(*row)

    return markup

# --- COMMANDS ---

@bot.message_handler(commands=["start", "help"])
def welcome(message):
    user = message.from_user

    get_stats(user.id, user.username or user.first_name)

    bot.reply_to(
        message,
        f"👋 Hey *{user.first_name}*!\n\n"
        "💣 Use `/mines <amount>` to play!",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["balance"])
def balance(message):
    stats = get_stats(message.from_user.id)

    bot.reply_to(
        message,
        f"💰 Balance: *{stats['balance']}* credits",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["mines"])
def start_game(message):
    user = message.from_user
    stats = get_stats(user.id, user.username or user.first_name)

    if stats["active_game"]:
        bot.reply_to(message, "❌ Finish your current game first!")
        return

    args = message.text.split()

    if len(args) < 2:
        bot.reply_to(
            message,
            "Usage: `/mines <amount>`",
            parse_mode="Markdown"
        )
        return

    # Safe number check
    try:
        bet = int(args[1])
    except ValueError:
        bot.reply_to(message, "❌ Enter a valid number!")
        return

    if bet <= 0:
        bot.reply_to(message, "❌ Bet must be greater than 0!")
        return

    if bet > stats["balance"]:
        bot.reply_to(message, "❌ Insufficient balance!")
        return

    # Start game
    stats["balance"] -= bet
    stats["bet"] = bet
    stats["active_game"] = True
    stats["opened"] = []
    stats["mines"] = random.sample(range(25), 3)

    send_board(
        message.chat.id,
        user.id,
        f"🎮 *Game Started!*\n\n💰 Bet: *{bet}* credits"
    )

# --- BUTTON HANDLER ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    stats = get_stats(user_id)

    if not stats["active_game"]:
        bot.answer_callback_query(call.id, "No active game!")
        return

    # Ignore disabled buttons
    if call.data == "none":
        bot.answer_callback_query(call.id)
        return

    # TILE CLICK
    if call.data.startswith("click_"):

        idx = int(call.data.split("_")[1])

        # Prevent duplicate click
        if idx in stats["opened"]:
            bot.answer_callback_query(call.id, "Already opened!")
            return

        # Mine hit
        if idx in stats["mines"]:

            stats["active_game"] = False

            markup = reveal_board(
                call.message.chat.id,
                user_id,
                call.message.message_id,
                hit_index=idx
            )

            bot.edit_message_text(
                f"💥 *BOOM!*\n\nYou lost *{stats['bet']}* credits.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )

        else:
            # Safe tile
            stats["opened"].append(idx)

            send_board(
                call.message.chat.id,
                user_id,
                "💎 *Safe Tile!*",
                call.message.message_id
            )

    # CASHOUT
    elif call.data == "cashout":

        win = calculate_win(
            stats["bet"],
            len(stats["opened"])
        )

        stats["balance"] += win
        stats["active_game"] = False

        markup = reveal_board(
            call.message.chat.id,
            user_id,
            call.message.message_id
        )

        bot.edit_message_text(
            f"✅ *Cashed Out!*\n\n"
            f"💰 Won: *{win}* credits\n"
            f"🏦 Balance: *{stats['balance']}* credits",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

# --- START BOT ---

if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.infinity_polling()
