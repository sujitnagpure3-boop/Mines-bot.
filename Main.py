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
username_index = {}  # lowercase username -> user_id

DAILY_BONUS = 500
DAILY_COOLDOWN = 86400  # 24 hours in seconds
CLICK_COOLDOWN = 1.5  # seconds between tile clicks


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
                row_btns.append(InlineKeyboardButton("💎", callback_data="none"))
            else:
                row_btns.append(
                    InlineKeyboardButton("❎", callback_data=f"click_{idx}")
                )
        markup.row(*row_btns)

    if len(stats["opened"]) > 0:
        current_win = calculate_win(
            stats["bet"], len(stats["opened"]), stats.get("mine_count", 3)
        )
        markup.add(
            InlineKeyboardButton(
                f"💰 Cash Out ({current_win} credits)", callback_data="cashout"
            )
        )

    if message_id:
        bot.edit_message_text(
            text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
        )
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


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    user = message.from_user
    stats = get_stats(user.id, user.username or user.first_name)
    name = user.first_name or user.username or "Player"
    bot.reply_to(
        message,
        (
            f"👋 Hey *{name}*, welcome!\n\n"
            "💣 *Mines* is here and ready to play!\n\n"
            "This is a fun game — no stress, no pressure.\n"
            "Just tap tiles, find 💎 diamonds, and cash out whenever you feel lucky! 😄\n\n"
            f"🎁 You start with *{stats['balance']} credits* — enjoy!\n\n"
            "Hit `/mines <amount>` to jump in\n"
            "or `/daily` for your free credits 💰\n\n"
            "Have fun and good luck! 🍀"
        ),
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["balance"])
def show_balance(message):
    user = message.from_user
    stats = get_stats(user.id, user.username or user.first_name)
    bot.reply_to(
        message, f"💰 Your balance: *{stats['balance']} credits*", parse_mode="Markdown"
    )


@bot.message_handler(commands=["profile"])
def show_profile(message):
    user = message.from_user
    stats = get_stats(user.id, user.username or user.first_name)
    games = stats["games_played"]
    wins = stats["wins"]
    losses = stats["losses"]
    biggest = stats["biggest_win"]
    winrate = f"{(wins / games * 100):.1f}%" if games > 0 else "N/A"
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


@bot.message_handler(commands=["leaderboard"])
def show_leaderboard(message):
    user = message.from_user
    get_stats(user.id, user.username or user.first_name)

    if not user_data:
        bot.reply_to(message, "No players yet. Be the first to play with /mines!")
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    sorted_players = sorted(
        user_data.items(), key=lambda x: x[1]["balance"], reverse=True
    )[:5]

    lines = ["🏆 *Top 5 Leaderboard*\n"]
    for i, (uid, data) in enumerate(sorted_players):
        name = data.get("username", f"Player{uid}")
        balance = data["balance"]
        lines.append(f"{medals[i]} *{name}* — {balance} credits")

    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=["players"])
def admin_players(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ You are not authorized to use this command.")
        return

    if not user_data:
        bot.reply_to(message, "No players registered yet.")
        return

    sorted_players = sorted(
        user_data.items(), key=lambda x: x[1]["balance"], reverse=True
    )

    lines = [f"👥 *All Players ({len(sorted_players)})* — sorted by balance\n"]
    for i, (uid, data) in enumerate(sorted_players, start=1):
        name = data.get("username", f"Player{uid}")
        bal = data["balance"]
        games = data.get("games_played", 0)
        wins = data.get("wins", 0)
        losses = data.get("losses", 0)
        active = " 🎮" if data.get("active_game") else ""
        lines.append(
            f"{i}. *{name}*{active}\n   💰 {bal} credits | ✅ {wins}W / ❌ {losses}L / 🎮 {games} games"
        )

    # Telegram message limit — split if too long
    text = "\n".join(lines)
    if len(text) > 4000:
        chunks = []
        chunk = lines[0]
        for line in lines[1:]:
            if len(chunk) + len(line) + 1 > 4000:
                chunks.append(chunk)
                chunk = line
            else:
                chunk += "\n" + line
        chunks.append(chunk)
        for chunk in chunks:
            bot.send_message(message.chat.id, chunk, parse_mode="Markdown")
    else:
        bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(commands=["give"])
def admin_give(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ You are not authorized to use this command.")
        return

    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(
            message,
            "Admin usage:\n"
            "`/give @username amount` — add credits\n"
            "`/give @username -amount` — remove credits",
            parse_mode="Markdown",
        )
        return

    target_raw = args[1].lstrip("@").lower()
    try:
        amount = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Amount must be a number.")
        return

    target_id = username_index.get(target_raw)
    if not target_id:
        bot.reply_to(
            message,
            f"❌ User *@{target_raw}* not found. They must have used the bot at least once.",
            parse_mode="Markdown",
        )
        return

    target = get_stats(target_id)
    target["balance"] += amount

    if target["balance"] < 0:
        target["balance"] = 0

    action = f"+{amount}" if amount >= 0 else str(amount)
    bot.reply_to(
        message,
        f"✅ *Done!* {action} credits to *{target['username']}*.\n💰 Their new balance: *{target['balance']} credits*",
        parse_mode="Markdown",
    )

    try:
        notice = f"💰 An admin {'added' if amount >= 0 else 'removed'} *{abs(amount)} credits* {'to' if amount >= 0 else 'from'} your balance.\n💰 New Balance: *{target['balance']} credits*"
        bot.send_message(target_id, notice, parse_mode="Markdown")
    except Exception:
        pass


@bot.message_handler(commands=["transfer"])
def transfer_credits(message):
    user = message.from_user
    sender_id = user.id
    sender = get_stats(sender_id, user.username or user.first_name)

    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(
            message,
            "Usage: `/transfer @username amount`\nExample: `/transfer @john 200`",
            parse_mode="Markdown",
        )
        return

    target_raw = args[1].lstrip("@").lower()
    try:
        amount = int(args[2])
    except ValueError:
        bot.reply_to(
            message,
            "❌ Amount must be a number. Example: `/transfer @john 200`",
            parse_mode="Markdown",
        )
        return

    if amount <= 0:
        bot.reply_to(message, "❌ Amount must be greater than 0.")
        return

    if amount > sender["balance"]:
        bot.reply_to(
            message,
            f"❌ Insufficient balance. You have *{sender['balance']} credits*.",
            parse_mode="Markdown",
        )
        return

    target_id = username_index.get(target_raw)
    if not target_id:
        bot.reply_to(
            message,
            f"❌ User *@{target_raw}* not found.\nThey must have used the bot at least once before you can send credits.",
            parse_mode="Markdown",
        )
        return

    if target_id == sender_id:
        bot.reply_to(message, "❌ You can't transfer credits to yourself.")
        return

    receiver = get_stats(target_id)
    sender["balance"] -= amount
    receiver["balance"] += amount

    receiver_name = receiver["username"]
    bot.reply_to(
        message,
        f"✅ *Transfer successful!*\nSent *{amount} credits* to *{receiver_name}*.\n💰 Your new balance: *{sender['balance']} credits*",
        parse_mode="Markdown",
    )

    try:
        bot.send_message(
            target_id,
            f"🎁 *You received {amount} credits* from *{sender['username']}*!\n💰 Your new balance: *{receiver['balance']} credits*",
            parse_mode="Markdown",
        )
    except Exception:
        pass


@bot.message_handler(commands=["daily"])
def daily_bonus(message):
    user = message.from_user
    user_id = user.id
    stats = get_stats(user_id, user.username or user.first_name)
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
            f"🎁 *Daily bonus claimed!*\n+*{DAILY_BONUS} credits* added to your balance.\n💰 New Balance: *{stats['balance']} credits*\n\nCome back tomorrow for more!",
            parse_mode="Markdown",
        )


@bot.message_handler(commands=["mines"])
def start_game(message):
    user = message.from_user
    user_id = user.id
    stats = get_stats(user_id, user.username or user.first_name)

    if stats["active_game"]:
        bot.reply_to(message, "❌ You already have an active game! Finish it first.")
        return

    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(
            message,
            f"💰 Balance: *{stats['balance']} credits*\n\n"
            "Usage: `/mines <amount>` or `/mines <amount> <bombs>`\n"
            "Bombs: min *1*, max *24* (default: 3)\n"
            "More bombs = bigger multiplier per tile! 💥",
            parse_mode="Markdown",
        )
        return

    try:
        bet = int(args[1])
    except ValueError:
        bot.reply_to(
            message,
            "❌ Please enter a valid number. Example: `/mines 100` or `/mines 100 5`",
            parse_mode="Markdown",
        )
        return

    mine_count = 3
    if len(args) >= 3:
        try:
            mine_count = int(args[2])
        except ValueError:
            bot.reply_to(
                message,
                "❌ Bomb count must be a number. Example: `/mines 100 5`",
                parse_mode="Markdown",
            )
            return
        if mine_count < 1 or mine_count > 24:
            bot.reply_to(
                message,
                "❌ Bomb count must be between *1* and *24*.",
                parse_mode="Markdown",
            )
            return

    max_bet = int(stats["balance"] * 0.75)

    if bet < 50:
        bot.reply_to(message, "❌ Minimum bet is *50 credits*.", parse_mode="Markdown")
        return
    if bet > max_bet:
        bot.reply_to(
            message,
            f"❌ Maximum bet is *75% of your balance* (*{max_bet} credits*).\n💰 Your balance: *{stats['balance']} credits*",
            parse_mode="Markdown",
        )
        return
    if bet > stats["balance"]:
        bot.reply_to(
            message,
            f"❌ Insufficient balance. You have *{stats['balance']} credits*.",
            parse_mode="Markdown",
        )
        return

    stats["balance"] -= bet
    stats["bet"] = bet
    stats["active_game"] = True
    stats["opened"] = []
    stats["mine_count"] = mine_count
    stats["mines"] = random.sample(range(25), mine_count)
    per_tile = multiplier_per_tile(mine_count)

    send_board(
        message.chat.id,
        user_id,
        f"🎮 *Game Started!*\nBet: *{bet} credits* | 💣 Bombs: *{mine_count}* | +*{per_tile}×* per 💎\n\nPick tiles and cash out before you hit a mine!",
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
            call.id, "No active game. Use /mines to start.", show_alert=True
        )
        return

    if call.data.startswith("click_"):
        now = time.time()
        elapsed = now - stats.get("last_click", 0)
        if elapsed < CLICK_COOLDOWN:
            remaining = round(CLICK_COOLDOWN - elapsed, 1)
            bot.answer_callback_query(
                call.id,
                f"⏳ Slow down! Wait {remaining}s before clicking again.",
                show_alert=False,
            )
            return
        stats["last_click"] = now

    if call.data.startswith("click_"):
        idx = int(call.data.split("_")[1])

        if idx in stats["mines"]:
            stats["active_game"] = False
            stats["games_played"] += 1
            stats["losses"] += 1
            reveal_board(
                call.message.chat.id, user_id, call.message.message_id, hit_index=idx
            )
            bot.edit_message_text(
                f"💥 *BOOM! You hit a mine!*\nYou lost *{stats['bet']} credits*.\n💰 Balance: *{stats['balance']} credits*\n\nUse /mines to play again.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
            )
        else:
            stats["opened"].append(idx)
            mc = stats.get("mine_count", 3)
            current_win = calculate_win(stats["bet"], len(stats["opened"]), mc)
            per_tile = multiplier_per_tile(mc)
            multiplier = 1 + (len(stats["opened"]) * per_tile)
            send_board(
                call.message.chat.id,
                user_id,
                f"💎 *Safe!* Multiplier: *{multiplier:.2f}×* | Potential win: *{current_win} credits*\n\nKeep going or cash out!",
                call.message.message_id,
            )

    elif call.data == "cashout":
        mc = stats.get("mine_count", 3)
        win = calculate_win(stats["bet"], len(stats["opened"]), mc)
        per_tile = multiplier_per_tile(mc)
        stats["balance"] += win
        stats["active_game"] = False
        stats["games_played"] += 1
        stats["wins"] += 1
        if win > stats["biggest_win"]:
            stats["biggest_win"] = win
        multiplier = 1 + (len(stats["opened"]) * per_tile)
        bot.edit_message_text(
            f"✅ *Cashed Out!*\nTiles revealed: *{len(stats['opened'])}* | Multiplier: *{multiplier:.2f}×*\nPayout: *+{win} credits*\n💰 New Balance: *{stats['balance']} credits*\n\nUse /mines to play again.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )

    bot.answer_callback_query(call.id)


print("Clearing any active webhook...")
bot.delete_webhook()

print("Registering commands...")
bot.set_my_commands(
    [
        telebot.types.BotCommand("mines", "💣 Start a game — /mines <bet>"),
        telebot.types.BotCommand("daily", "🎁 Claim 500 free credits (once per 24h)"),
        telebot.types.BotCommand("transfe
r", "💸 Send credits to another player"),
        telebot.types.BotCommand("profile", "👤 Your personal stats"),
        telebot.types.BotCommand("balance", "💰 Check your current balance"),
        telebot.types.BotCommand("leaderboard", "🏆 Top 5 richest players"),
        telebot.types.BotCommand("players", "👥 [Admin] View all players and balances"),
        telebot.types.BotCommand("give", "🔧 [Admin] Add or remove credits"),
        telebot.types.BotCommand("help", "📖 How to play"),
    ]
)

print("Bot is running...")
bot.infinity_polling()
