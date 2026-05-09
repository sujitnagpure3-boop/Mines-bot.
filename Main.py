import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import time

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set.")

ADMIN_ID = int(os.environ.get("ADMIN_USER_ID", "0"))

bot = telebot.TeleBot(TOKEN)

user_data = {}
username_index = {}

DAILY_BONUS = 500
DAILY_COOLDOWN = 86400
CLICK_COOLDOWN = 1.5


def get_stats(user_id, username=None):
    if user_id not in user_data:
        user_data[user_id] = {
            "balance": 1000,
            "active_game": False,
            "mines": [],
            "opened": [],
            "bet": 0,
            "last_daily": 0,
            "username": username or f"Player{user_id}",
            "games_played": 0,
            "wins": 0,
            "losses": 0,
            "biggest_win": 0,
            "last_click": 0,
            "mine_count": 3,
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
                row_btns.append(
                    InlineKeyboardButton("💎", callback_data="none")
                )
            else:
                row_btns.append(
                    InlineKeyboardButton("❎", callback_data=f"click_{idx}")
                )

        markup.row(*row_btns)

    if len(stats["opened"]) > 0:
        current_win = calculate_win(
            stats["bet"],
            len(stats["opened"]),
            stats.get("mine_count", 3)
        )

        markup.add(
            InlineKeyboardButton(
                f"💰 Cash Out ({current_win} credits)",
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
        row_btns = []

        for c in range(5):
            idx = r * 5 + c

            if idx in stats["mines"]:
                label = "💥" if idx == hit_index else "💣"

                row_btns.append(
                    InlineKeyboardButton(label, callback_data="none")
                )

            elif idx in stats["opened"]:
                row_btns.append(
                    InlineKeyboardButton("💎", callback_data="none")
                )

            else:
                row_btns.append(
                    InlineKeyboardButton("❎", callback_data="none")
                )

        markup.row(*row_btns)

    bot.edit_message_reply_markup(
        chat_id,
        message_id,
        reply_markup=markup
    )


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    user = message.from_user

    stats = get_stats(
        user.id,
        user.username or user.first_name
    )

    name = user.first_name or user.username or "Player"

    bot.reply_to(
        message,
        (
            f"👋 Hey *{name}*, welcome!\n\n"
            "💣 *Mines* is here and ready to play!\n\n"
            "This is a fun game — no stress, no pressure.\n"
            "Just tap tiles, find 💎 diamonds, and cash out whenever you feel lucky! 😄\n\n"
            f"🎁 You start with *{stats['balance']} credits* — enjoy!\n\n"
            "Hit /mines <amount> to jump in\n"
            "or /daily for your free credits 💰\n\n"
            "Have fun and good luck! 🍀"
        ),
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["balance"])
def show_balance(message):
    user = message.from_user

    stats = get_stats(
        user.id,
        user.username or user.first_name
    )

    bot.reply_to(
        message,
        f"💰 Your balance: *{stats['balance']} credits*",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["profile"])
def show_profile(message):
    user = message.from_user

    stats = get_stats(
        user.id,
        user.username or user.first_name
    )

    games = stats["games_played"]
    wins = stats["wins"]
    losses = stats["losses"]
    biggest = stats["biggest_win"]

    winrate = (
        f"{(wins / games * 100):.1f}%"
        if games > 0 else "N/A"
    )

    bot.reply_to(
        message,
        (
            f"👤 *{stats['username']}'s Profile*\n\n"
            f"💰 Balance: *{stats['balance']} credits*\n"
            f"🎮 Games played: *{games}*\n"
            f"✅ Wins: *{wins}*\n"
            f"❌ Losses: *{losses}*\n"
            f"📊 Win rate: *{winrate}*\n"
            f"🏆 Biggest win: *{biggest} credits*"
        ),
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["daily"])
def daily_bonus(message):
    user = message.from_user
    user_id = user.id

    stats = get_stats(
        user_id,
        user.username or user.first_name
    )

    now = time.time()
    elapsed = now - stats["last_daily"]

    if elapsed < DAILY_COOLDOWN:
        remaining = int(DAILY_COOLDOWN - elapsed)

        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        seconds = remaining % 60

        bot.reply_to(
            message,
            f"⏳ You already claimed your daily bonus!\nCome back in *{hours}h {minutes}m {seconds}s*.",
            parse_mode="Markdown",
        )

    else:
        stats["balance"] += DAILY_BONUS
        stats["last_daily"] = now

        bot.reply_to(
            message,
            (
                f"🎁 *Daily bonus claimed!*\n"
                f"+*{DAILY_BONUS} credits* added to your balance.\n"
                f"💰 New Balance: *{stats['balance']} credits*"
            ),
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["mines"])
def start_game(message):
    user = message.from_user
    user_id = user.id

    stats = get_stats(
        user_id,
        user.username or user.first_name
    )

    if stats["active_game"]:
        bot.reply_to(
            message,
            "❌ You already have an active game!"
        )
        return

    args = message.text.split()

    if len(args) < 2:
        bot.reply_to(
            message,
            "Usage: /mines <amount>",
            parse_mode="Markdown"
        )
        return

    try:
        bet = int(args[1])

    except ValueError:
        bot.reply_to(
            message,
            "❌ Enter a valid number.",
            parse_mode="Markdown"
        )
        return

    if bet <= 0:
        bot.reply_to(
            message,
            "❌ Bet must be greater than 0."
        )
        return

    if bet > stats["balance"]:
        bot.reply_to(
            message,
            f"❌ Insufficient balance.\n💰 Balance: *{stats['balance']}*",
            parse_mode="Markdown"
        )
        return

    stats["balance"] -= bet
    stats["bet"] = bet
    stats["active_game"] = True
    stats["opened"] = []
    stats["mine_count"] = 3
    stats["mines"] = random.sample(range(25), 3)

    send_board(
        message.chat.id,
        user_id,
        f"🎮 *Game Started!*\n💰 Bet: *{bet} credits*"
    )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id

    stats = get_stats(user_id)

    if call.data == "none":
        bot.answer_callback_query(call.id)
        return

    if not stats["active_game"]:
        bot.answer_callback_query(
            call.id,
            "No active game."
        )
        return

    if call.data.startswith("click_"):

        now = time.time()

        elapsed = now - stats.get("last_click", 0)

        if elapsed < CLICK_COOLDOWN:
            remaining = round(CLICK_COOLDOWN - elapsed, 1)

            bot.answer_callback_query(
                call.id,
                f"⏳ Wait {remaining}s"
            )
            return

        stats["last_click"] = now

        idx = int(call.data.split("_")[1])

        if idx in stats["opened"]:
            bot.answer_callback_query(
                call.id,
                "Already opened!"
            )
            return

        if idx in stats["mines"]:

            stats["active_game"] = False
            stats["games_played"] += 1
            stats["losses"] += 1

            reveal_board(
                call.message.chat.id,
                user_id,
                call.message.message_id,
                hit_index=idx
            )

            bot.edit_message_text(
                (
                    f"💥 *BOOM!*\n"
                    f"You lost *{stats['bet']} credits*.\n"
                    f"💰 Balance: *{stats['balance']} credits*"
                ),
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
            )

        else:
            stats["opened"].append(idx)

            current_win = calculate_win(
                stats["bet"],
                len(stats["opened"]),
                stats["mine_count"]
            )

            send_board(
                call.message.chat.id,
                user_id,
                (
                    f"💎 *Safe!*\n"
                    f"Potential win: *{current_win} credits*"
                ),
                call.message.message_id,
            )

    elif call.data == "cashout":

        win = calculate_win(
            stats["bet"],
            len(stats["opened"]),
            stats["mine_count"]
        )

        stats["balance"] += win
        stats["active_game"] = False
        stats["games_played"] += 1
        stats["wins"] += 1

        if win > stats["biggest_win"]:
            stats["biggest_win"] = win

        bot.edit_message_text(
            (
                f"✅ *Cashed Out!*\n"
                f"💰 Won: *{win} credits*\n"
                f"🏦 Balance: *{stats['balance']} credits*"
            ),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )

    bot.answer_callback_query(call.id)


print("Clearing webhook...")
bot.delete_webhook()

print("Bot is running...")

bot.infinity_polling()
