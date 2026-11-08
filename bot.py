import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import BadRequest

# Configure Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Environment Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # e.g., "@yourchannel" or "-100123456789"
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/yourchannel")

# In-memory storage (Replace with SQLite/PostgreSQL for persistent data)
user_balances = {}

def get_balance(user_id: int) -> int:
    return user_balances.get(user_id, 100)  # Default 100 coins start bonus

def update_balance(user_id: int, amount: int):
    user_balances[user_id] = get_balance(user_id) + amount

async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is a member of the required Telegram channel."""
    if not CHANNEL_ID:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logger.error(f"Subscription check error: {e}")
        return True  # Fallback if channel ID misconfigured

async def subscription_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Helper to guard commands/interactions behind channel subscription."""
    user = update.effective_user
    if not await is_subscribed(user.id, context):
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel to Play", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ I Have Joined", callback_data="check_sub")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg_text = (
            "🔒 **Access Restricted!**\n\n"
            "To use the Casino Bot and claim free play points, you must join our official Telegram Channel!"
        )
        if update.callback_query:
            await update.callback_query.answer("Please join the channel first!", show_alert=True)
            await update.callback_query.edit_message_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await subscription_guard(update, context):
        return

    welcome_text = (
        f"🎰 **Welcome to the Casino & Boost Bot, {user.first_name}!** 🎰\n\n"
        f"💰 **Your Balance:** `{get_balance(user.id)}` Coins\n\n"
        "Play interactive casino mini-games, earn rewards, and boost your channel ranking!"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🎰 Slots (Bet 10)", callback_data="play_slot"),
            InlineKeyboardButton("🎲 Dice (Bet 10)", callback_data="play_dice"),
        ],
        [
            InlineKeyboardButton("🎳 Bowling (Bet 10)", callback_data="play_bowling"),
            InlineKeyboardButton("🏀 Basketball (Bet 10)", callback_data="play_basketball"),
        ],
        [
            InlineKeyboardButton("🎯 Darts (Bet 10)", callback_data="play_dart"),
            InlineKeyboardButton("🎁 Daily Bonus (+50)", callback_data="daily_bonus"),
        ],
        [InlineKeyboardButton("📊 My Account", callback_data="account")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data == "check_sub":
        if await is_subscribed(user_id, context):
            await query.answer("Thank you for joining!")
            await start(update, context)
        else:
            await query.answer("❌ You haven't joined the channel yet!", show_alert=True)
        return

    if not await is_subscribed(user_id, context):
        await query.answer("Please join our channel to play!", show_alert=True)
        return

    bet_amount = 10

    if data.startswith("play_"):
        if get_balance(user_id) < bet_amount:
            await query.answer("❌ Insufficient balance! Claim daily bonus or invite friends.", show_alert=True)
            return

        update_balance(user_id, -bet_amount)
        await query.answer()

        game_map = {
            "play_slot": "🎰",
            "play_dice": "🎲",
            "play_bowling": "🎳",
            "play_basketball": "🏀",
            "play_dart": "🎯",
        }
        emoji = game_map.get(data, "🎲")

        # Send native Telegram animated game
        dice_msg = await context.bot.send_dice(chat_id=query.message.chat_id, emoji=emoji)
        score = dice_msg.dice.value

        # Determine payout based on game outcome
        win_amount = 0
        if emoji == "🎰":
            # Slots: 64 = Jackpot (777), 1, 22, 43, etc. are combinations
            if score == 64:
                win_amount = 250
            elif score in [1, 22, 43]:
                win_amount = 50
        else:
            # Dice, Darts, Bowling, Basketball win on 5 or 6 score
            if score >= 5:
                win_amount = bet_amount * 2
            elif score == 4:
                win_amount = bet_amount

        if win_amount > 0:
            update_balance(user_id, win_amount)
            result_text = f"🎉 **YOU WON {win_amount} COINS!** (Score: {score})\nNew Balance: `{get_balance(user_id)}` Coins"
        else:
            result_text = f"❌ **Better luck next time!** (Score: {score})\nNew Balance: `{get_balance(user_id)}` Coins"

        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=result_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "daily_bonus":
        update_balance(user_id, 50)
        await query.answer("🎁 You claimed 50 free coins!", show_alert=True)
        await start(update, context)

    elif data == "account":
        acc_text = (
            f"👤 **Account Overview**\n\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"💵 **Balance:** `{get_balance(user_id)}` Coins\n\n"
            f"📢 **Channel Boost Status:** Verified Subscriber ✅"
        )
        keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
        await query.edit_message_text(acc_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "main_menu":
        await start(update, context)

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN variable missing!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot started successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
