import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, BotCommand
from telegram.ext import Application, CommandHandler

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN", "").strip()
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://etntest8237.netlify.app").strip()

async def start(update, context):
    if not WEBAPP_URL.startswith("https://"):
        await update.effective_message.reply_text(
            "Сайт ещё не настроен. Администратор должен указать HTTPS-адрес в WEBAPP_URL."
        )
        return
    keyboard = [[InlineKeyboardButton("Открыть ETN × RAPIRA", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.effective_message.reply_text(
        "Добро пожаловать в ETN × RAPIRA ONLINE!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update, context):
    await update.effective_message.reply_text(
        "Команды:\n/start — открыть приложение\n/help — помощь\n\n"
        "Если приложение не открывается, сообщите администратору."
    )

async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Открыть приложение"),
        BotCommand("help", "Помощь"),
    ])

def main():
    if not TOKEN:
        raise RuntimeError("Не задана переменная BOT_TOKEN")
    if not WEBAPP_URL.startswith("https://"):
        raise RuntimeError("WEBAPP_URL должен быть HTTPS-адресом Netlify")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    logging.info("Telegram bot is starting in polling mode")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
