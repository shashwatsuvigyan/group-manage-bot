from keep_alive import keep_alive
keep_alive()  # Starts the web server
import logging
import os
from datetime import timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIGURATION ---
BOT_TOKEN = "8421190336:AAE-8Enbh8dPDPuirVZvz1IEQWrjN9zO4yA"
MONGO_URI = "mongodb+srv://shashwat:Te1q2vgQO8MM6iVd@antibanall.yv1qgd6.mongodb.net/?appName=antibanall"

# --- DATABASE SETUP ---
client = AsyncIOMotorClient(MONGO_URI)
db = client.group_bot_db
warns_collection = db.warns

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- HELPER FUNCTIONS ---
async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the user triggering the command is an admin."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Get admins
    admins = await context.bot.get_chat_administrators(chat_id)
    admin_ids = [admin.user.id for admin in admins]
    return user_id in admin_ids

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 I am your Group Manager. Give me Admin permissions to start!")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcomes new members."""
    for member in update.message.new_chat_members:
        await update.message.reply_text(f"Welcome {member.mention_html()} to the group!", parse_mode='HTML')

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bans a user by reply."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("❌ You are not an admin.")
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text("Please reply to the user you want to ban.")
        return

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, reply.from_user.id)
        await update.message.reply_text(f"🔨 Banned {reply.from_user.first_name}.")
    except Exception as e:
        await update.message.reply_text(f"Failed to ban: {e}")

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kicks (unbans) a user so they can rejoin."""
    if not await is_user_admin(update, context):
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text("Reply to a user to kick.")
        return

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, reply.from_user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, reply.from_user.id)
        await update.message.reply_text(f"🦶 Kicked {reply.from_user.first_name}.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mutes a user (restrict sending messages)."""
    if not await is_user_admin(update, context):
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text("Reply to a user to mute.")
        return

    permissions = ChatPermissions(can_send_messages=False)
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            reply.from_user.id,
            permissions=permissions
        )
        await update.message.reply_text(f"🤐 Muted {reply.from_user.first_name}.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warns a user. 3 warnings = Ban."""
    if not await is_user_admin(update, context):
        return

    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text("Reply to a user to warn.")
        return

    user_id = reply.from_user.id
    chat_id = update.effective_chat.id
    user_name = reply.from_user.first_name

    # Database Operation: Find and update warning count
    user_record = await warns_collection.find_one({"user_id": user_id, "chat_id": chat_id})
    
    current_warns = user_record["warns"] + 1 if user_record else 1
    
    if current_warns >= 3:
        # Reset warnings and Ban
        await warns_collection.delete_one({"user_id": user_id, "chat_id": chat_id})
        await context.bot.ban_chat_member(chat_id, user_id)
        await update.message.reply_text(f"🚫 {user_name} has reached 3 warnings and is BANNED.")
    else:
        # Update warnings in DB
        await warns_collection.update_one(
            {"user_id": user_id, "chat_id": chat_id},
            {"$set": {"warns": current_warns}},
            upsert=True
        )
        await update.message.reply_text(f"⚠️ Warned {user_name}. ({current_warns}/3)")

# --- MAIN APP LOOP ---
if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("kick", kick_user))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("warn", warn_user))
    
    # Message Handler for Welcome
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    print("Bot is running...")
    application.run_polling()
