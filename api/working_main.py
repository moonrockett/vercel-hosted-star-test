import os
import logging
import asyncio
import nest_asyncio
import random
import string
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)
from .database import (
    init_db, 
    increment_referral_count, 
    get_referral_count, 
    get_usage_stats, 
    cleanup_old_stats, 
    get_unique_users_count, 
    add_new_user
)
from fastapi import FastAPI

"""
Telegram Star Shop Bot - Main Bot File
Version: 1.0

Description:
A Telegram bot for purchasing and earning Telegram stars through referrals.
Features a user-friendly interface with secure payment processing and 
affiliate program management.

Key Features:
1. Star Purchase System:
   - Processes star purchases (minimum 50 stars)
   - Price calculation (0.00255 USD per star)
   - Generates unique order IDs for tracking
   - 15-minute payment window
   - TON network payments

2. Affiliate Program:
   - Earn 1 star per successful referral
   - 5% commission on referral's first purchase
   - Minimum withdrawal: 100 stars
   - Anti-self-referral protection
   - Referral tracking and statistics

3. Admin Features:
   - Real-time usage statistics
   - Concurrent user monitoring
   - Performance metrics via /stats command

Technical Implementation:
- Async/await pattern for efficient handling
- Connection pooling for concurrent users
- Markdown V2 formatting for messages
- Persistent SQLite database storage
- Environment variable based configuration
"""

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
EXPECTING_NUMBER = 1

ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0'))  # Get from environment variable

def generate_random_string(length=15):
    """Generate a random alphanumeric string of given length."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Initialize database when bot starts
async def main() -> None:
    """Start the bot."""
    # Initialize database
    init_db()
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("No token found! Make sure TELEGRAM_BOT_TOKEN is set in .env file")
        return

    try:
        application = Application.builder().token(token).build()

        # Set up bot commands menu
        commands = [
            ("start", "Start the bot and show main menu"),
        ]
        
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands menu set up successfully")

        # Create conversation handler
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
                CallbackQueryHandler(button_callback)
            ],
            states={
                EXPECTING_NUMBER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, process_number),
                    CallbackQueryHandler(button_callback)
                ]
            },
            fallbacks=[CommandHandler("start", start)]
        )

        # Register handler
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("stats", stats))

        logger.info("Starting bot...")
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        raise e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    
    # Track new user
    add_new_user(user.id)
    
    # Check if this is a referral
    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
        try:
            referrer_id = int(referrer_id)
            if referrer_id != user.id:  # Prevent self-referral
                increment_referral_count(referrer_id)
        except ValueError:
            pass

    keyboard = [
        [
            InlineKeyboardButton("Buy ⭐️", callback_data='button1'),
            InlineKeyboardButton("Earn ⭐️", callback_data='button2')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        r'''💫*Welcome*\!

Using *Star Shop bot*, you can purchase Telegram stars ⭐️ without KYC verification\.

❗️*Tap on "Buy Stars ⭐️" and enter the amount of starts you wish to buy\.* \(minimum\: 50 stars\)'''
        .replace(r'\n', '\n'),  # Fix newlines
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ConversationHandler.END

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == 'button1':
        await query.message.reply_text(
            r'''*Please enter the amount of stars ⭐️ you wish to buy* 
\(minimum amount: 50 ⭐️\):''',
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return EXPECTING_NUMBER
    elif query.data == 'button2':
        user = query.from_user  # Use query.from_user to get the user
        user_link = f"[{user.first_name}](tg://user?id={user.id})"
        ref_count = get_referral_count(user.id)
        ref_link = f"https://t.me/{context.bot.username}?start={user.id}"
        
        # Escape special characters for MarkdownV2
        ref_link = ref_link.replace('.', '\.')
        
        # Add withdrawal button
        keyboard = [
            [InlineKeyboardButton("🏦 Withdraw Stars", callback_data='withdraw')],
            [InlineKeyboardButton("🏠 Home", callback_data='home')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"*👥 Affiliate program*\n"
            f"\n"
            f"Invite friends get *REWARDED BIG*\!\n"
            f"_*1* Telegram star ⭐️ per each successful referral *\+* *5%* of your friends first buy_\n"
            f"\n"
            f"\n"
            f"*Your Info:*\n"
            f"📛 Name: {user_link}\n"
            f"🆔 User ID: `{user.id}`\n"
            f"🌿 Successful Referrals: `{ref_count}`\n\n"
            f"🔗 *Your Referral Link* _\(tap to copy\)_:\n"
            f"`{ref_link}`\n\n"
            f"\n"
            f"_minimum withdraw amount: 100 Telegram stars ⭐️ _\n"
        )
        
        await query.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    elif query.data == 'withdraw':
        user = query.from_user  # Use query.from_user to get the user
        ref_count = get_referral_count(user.id)
        
        if ref_count >= 100:
            message = (
                f"*✅ Withdrawal Available\!*\n\n"
                f"Please contact admin \n"  # ADD ADMIN USERNAME
                f"Reference: `WD\-" + generate_random_string(8) + r"`"
            )
        else:
            remaining = 100 - ref_count
            message = (
                f"*❌ Insufficient Referrals*\n\n"
                f"You need `{remaining}` more referrals to withdraw\.\n"
                f"Current referrals: `{ref_count}`/`100`"
            ).format(remaining=remaining, ref_count=ref_count)
        
        # Add home button
        keyboard = [[InlineKeyboardButton("🏠 Home", callback_data='home')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    elif query.data == 'home':
        # Replace the current message with the home menu
        keyboard = [
            [
                InlineKeyboardButton("Buy ⭐️", callback_data='button1'),
                InlineKeyboardButton("Earn ⭐️", callback_data='button2')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.edit_text(
            r'''💫*Welcome*\! 

Using *Star Shop bot*, you can purchase Telegram stars ⭐️ without KYC verification\.
            
❗️*Tap on "Buy Stars ⭐️" and enter the amount of starts you wish to buy\.* \(minimum\: 50 stars\)''',
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

async def process_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the number input from user and maintain the state."""
    try:
        number = float(update.message.text)
        if number >= 50:
            result = number * 0.00255
            formatted_result = f"{result:.2f}"
    
            # Generate random string
            random_string = generate_random_string()
    
            # Get the user's name
            user_name = update.effective_user.first_name  # Get the user's first name
    
            message = (
                f"__*This invoice is valid for the next 15 minutes*__\n\n"
                f"__Order details__\n\n"
                f"Buyer: {user_name}\n"  # Show the user's name here
                f"Amount: `{number}` ⭐️\n\n"
                f"__Payment details__\n\n"
                f"Network: *TON*\n"
                f"Price: `{formatted_result}` TON\n\n"
                f"Address: `UQAV7UvOjM6o2rbU54To9V3GgmFUujbvCczOKB_nYFJwl9CS` \n\n"
                f"Order ID: `{random_string}`\n\n"
            )
            
            # Send the invoice message first without any buttons
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
            # Add home button to the follow-up message
            keyboard = [[InlineKeyboardButton("🏠 Home", callback_data='home')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send the follow-up message with the home button
            await update.message.reply_text(
                "⚠️*Attention*⚠️\n\n"
                "*You *MUST* send the __*EXACT*__ amount, Nothing more, nothing less\!*\n\n"
                "Dont forget to *leave a comment* on the transaction with the *Order ID* provided in the invoice above\n\n"
                "*Tap* the _Wallet address_ to *copy* it, entering the wrong wallet address will lead to __*permanent*__ loss of funds\n\n"
                "_*After making the transaction, please share the screenshot with support @Starshopsupport*\._\n"
                "_If you encounter any problems please contact support\._",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup
            )
            
        else:
            await update.message.reply_text(
                r"*Too low\!* Value must be atleast `50`",
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except ValueError:
        await update.message.reply_text(
            r"*Error:* _Not a number_",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return EXPECTING_NUMBER

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get usage statistics (admin only)."""
    try:
        user = update.effective_user
        if user.id != ADMIN_USER_ID:
            logger.warning(f"Unauthorized stats access attempt by user {user.id}")
            return
        
        logger.info(f"Stats requested by admin {user.id}")
        
        try:
            stats_data = get_usage_stats()
            unique_users = get_unique_users_count()
            
            # Debug log
            logger.info(f"Retrieved stats data: {stats_data}")
            
            # Get values with fallback to 0
            connections = int(stats_data.get('current_connections', 0))
            peak = int(stats_data.get('peak_last_hour', 0))
            avg = float(stats_data.get('avg_last_hour', 0))
            all_time = int(stats_data.get('all_time_max', 0))
            
            message = (
                r"*Bot Usage Statistics*" + "\n\n" +
                r"*Current Status:*" + "\n" +
                f"• Active connections: `{connections}`" + "\n" +
                f"• Total unique users: `{unique_users}`" + "\n\n" +
                r"*Traffic Analysis:*" + "\n" +
                rf"• Peak \(last hour\): `{peak}`" + "\n" +
                rf"• Average \(last hour\): `{avg:.1f}`" + "\n" +
                rf"• All\-time peak: `{max(peak, connections, all_time)}`"
            )
            
            # Simpler keyboard layout
            keyboard = [[InlineKeyboardButton("🏠 Home", callback_data='home')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup
            )
            logger.info("Stats message sent successfully")
            
        except Exception as db_error:
            logger.error(f"Database error in stats: {db_error}")
            await update.message.reply_text(
                r"*Error:* Database connection failed\. Try again later\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        try:
            await update.message.reply_text(
                r"*Error:* Command processing failed\. Try again\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as reply_error:
            logger.error(f"Could not send error message: {reply_error}")