from fastapi import FastAPI, Request, Response
import os
import logging
import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
import json
from .working_main import (
    start, 
    button_callback, 
    process_number, 
    stats, 
    EXPECTING_NUMBER,
    init_db
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Initialize bot application
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN provided")

# Initialize bot application
application = Application.builder().token(TOKEN).build()

# Initialize database
init_db()

# Set up conversation handler
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

# Register handlers
application.add_handler(conv_handler)
application.add_handler(CommandHandler("stats", stats))

@app.post("/webhook")
async def webhook(request: Request):
    """Handle incoming Telegram updates via webhook"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        
        # Process Update
        await application.process_update(update)
        
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return Response(status_code=500)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "alive", "message": "Bot is running"} 