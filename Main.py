import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import time

# --- CONFIGURATION ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
# Replace '0' with your actual Telegram User ID to use Admin commands
ADMIN_ID = int(os.environ.get("ADMIN_USER_ID", "0")) 

bot = telebot.TeleBot(TOKEN)

user_data = {}
username_index = {}  # Maps lowercase username -> user_id for transfers

# Constants
DAILY_BONUS = 500
DAILY_COOLDOWN = 86400  # 24 hours
CLICK_COOLDOWN = 1.0 

def get_stats(user_id, username=None):
    """Initializes or retrieves user data with a 1000 credit default."""
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

def calculate_win(bet, opened_count, mine_count):
    """Calculates payout based on number of bombs and tiles opened."""
    # More bombs = higher risk = higher reward per tile
    multiplier = 1 + (opened_count * (mine_count * 0.10))
    return int(bet * multiplier)

# --- COMMAND HANDLERS ---

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    user = message.from_user
    stats = get_stats(user.id, user.username or user.first_name)
    bot.reply_to(message, 
        f"🎮 *Welcome to Mines!*\n\n"
        f"💰 Balance: *{stats['balance']} credits*\n"
        f"💣 Bombs: 1 to 24\n\n"
        "Commands:\n"
        "/mines <bet> <bombs> - Start Game\n"
        "/daily - Get 500 free credits\n"
        "/transfer @user <amt> - Send credits\n"
        "/profile - View your stats\n"
        "/leaderboard - See top players", parse_mode="Markdown")

@bot.message_handler(commands=["daily"])
def daily_bonus(message):
    stats = get_stats(message.from_user.id)
    now = time.time()
    if now - stats["last_daily"] < DAILY_COOLDOWN:
        remaining = int(DAILY_COOLDOWN - (now - stats["last_daily"]))
        bot.reply_to(message, f"⏳ Try again in {remaining // 3600}h {(remaining % 3600) // 60}m.")
    else:
        stats["balance"] += DAILY_BONUS
        stats["last_daily"] = now
        bot.reply_to(message, f"✅ Claimed! +{DAILY_BONUS} credits. New balance: {stats['balance']}")

@bot.message_handler(commands=["profile"])
def show_profile(message):
    stats = get_stats(message.from_user.id)
    bot.reply_to(message, 
        f"👤 *Profile: {stats['username']}*\n"
        f"💰 Balance: {stats['balance']}\n"
        f"✅ Wins: {stats['wins']} | ❌ Losses: {stats['losses']}\n"
        f"🏆 Biggest Win: {stats['biggest_win']}", parse_mode="Markdown")

@bot.message_handler(commands=["transfer"])
def transfer(message):
    sender = get_stats(message.from_user.id)
    args = message.text.split()
    if len(args) < 3:
        return bot.reply_to(message, "Usage: `/transfer @username 500`", parse_mode="Markdown")
    
    target_username = args[1].lstrip("@").lower()
    try:
        amount = int(args[2])
    except: return

    target_id = username_index.get(target_username)
    if not target_id or amount <= 0 or amount > sender["balance"]:
        return bot.reply_to(message, "❌ Invalid user or insufficient balance.")

    receiver = get_stats(target_id)
    sender["balance"] -= amount
    receiver["balance"] += amount
    bot.reply_to(message, f"✅ Sent {amount} to @{target_username}!")

@bot.message_handler(commands=["leaderboard"])
def leaderboard(message):
    top = sorted(user_data.values(), key=lambda x: x["balance"], reverse=True)[:5]
    text = "🏆 *Top Players*\n"
    for i, p in enumerate(top, 1):
        text += f"{i}. {p['username']} - {p['balance']} 💰\n"
    bot.reply_to(message, text, parse_mode="Markdown")

# --- ADMIN COMMANDS ---

@bot.message_handler(commands=["give"])
def admin_give(message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    target_id = username_index.get(args[1].lstrip("@").lower())
    if target_id:
        user_data[target_id]["balance"] += int(args[2])
        bot.reply_to(message, "✅ Balance updated.")

@bot.message_handler(commands=["players"])
def admin_players(message):
    if message.from_user.id != ADMIN_ID: return
    text = f"Total Players: {len(user_data)}"
    bot.reply_to(message, text)

# --- GAME LOGIC ---

@bot.message_handler(commands=["mines"])
def start_mines(message):
    user_id = message.from_user.id
    stats = get_stats(user_id, message.from_user.username)
    
    if stats["active_game"]:
        return bot.reply_to(message, "Finish your current game first!")

    args = message.text.split()
    try:
        bet = int(args[1])
        bombs = int(args[2]) if len(args) > 2 else 3
    except:
        return bot.reply_to(message, "Usage: `/mines <bet> <bombs (1-24)>`", parse_mode="Markdown")

    if bombs < 1 or bombs > 24:
        return bot.reply_to(message, "❌ Bombs must be between 1 and 24.")
    if bet < 10 or bet > stats["balance"]:
        return bot.reply_to(message, "❌ Invalid bet amount.")

    stats["balance"] -= bet
    stats["bet"] = bet
    stats["mine_count"] = bombs
    stats["mines"] = random.sample(range(25), bombs)
    stats["opened"] = []
    stats["active_game"] = True
    
    send_board(message.chat.id, user_id, f"🎮 Game started! Bet: {bet} | Bombs: {bombs}")

def send_board(chat_id, user_id, text, message_id=None):
    stats = user_data[user_id]
    markup = InlineKeyboardMarkup()
    for r in range(5):
        btns = []
        for c in range(5):
            idx = r * 5 + c
            char = "💎" if idx in stats["opened"] else "❎"
            btns.append(InlineKeyboardButton(char, callback_data=f"tile_{idx}"))
        markup.row(*btns)
    
    if stats["opened"]:
        win = calculate_win(stats["bet"], len(stats["opened"]), stats["mine_count"])
        markup.add(InlineKeyboardButton(f"💰 Cash Out ({win})", callback_data="cashout"))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_clicks(call):
    user_id = call.from_user.id
    stats = get_stats(user_id)
    if not stats["active_game"]: return

    if call.data.startswith("tile_"):
        idx = int(call.data.split("_")[1])
        if idx in stats["opened"]: return

        if idx in stats["mines"]:
            stats["active_game"] = False
            stats["losses"] += 1
            bot.edit_message_text(f"💥 BOOM! You lost {stats['bet']} credits.", call.message.chat.id, call.message.message_id)
        else:
            stats["opened"].append(idx)
            if len(stats["opened"]) + stats["mine_count"] == 25: # Auto win if all gems found
                cashout_logic(call)
            else:
                send_board(call.message.chat.id, user_id, "💎 Safe! Keep going?", call.message.message_id)

    elif call.data == "cashout":
        cashout_logic(call)

def cashout_logic(call):
    stats = user_data[call.from_user.id]
    win = calculate_win(stats["bet"], len(stats["opened"]), stats["mine_count"])
    stats["balance"] += win
    stats["wins"] += 1
    if win > stats["biggest_win"]: stats["biggest_win"] = win
    stats["active_game"] = False
    bot.edit_message_text(f"✅ Cashed out! Win: {win} credits.\nNew Balance: {stats['balance']}", call.message.chat.id, call.message.message_id)

bot.infinity_polling()
