import logging
import os
import platform
import asyncio
import html
from collections import deque
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from openai import AsyncOpenAI, APIError

# Настройка для Windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Загрузка конфигурации
load_dotenv()

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Config:
    # Telegram
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
    ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID'))
    DONATE_LINK = os.getenv('DONATE_LINK', 'https://example.com/donate')
    PROJECT_INFO = os.getenv('PROJECT_INFO', '🌟 <b>Наш проект</b>\n\nРазработка умного чат-бота с ИИ')

    # Список API ключей
    API_KEYS = [key for key in [
        os.getenv('API_KEY1'),
        os.getenv('API_KEY2'),
        os.getenv('API_KEY3')
    ] if key]  # Только непустые ключи
    BASE_URL = os.getenv('BASE_URL', 'https://api.langdock.com/openai/eu/v1')
    MODEL = os.getenv('MODEL', 'gpt-4o-mini')


# Проверка наличия ключей
if not Config.API_KEYS:
    logger.error("Не найдено ни одного API ключа! Проверьте .env файл")
    exit(1)

# Инициализация
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Хранилище данных
user_dialogs = {}
code_storage = {}
current_api_key_index = 0
api_clients = [AsyncOpenAI(api_key=key, base_url=Config.BASE_URL) for key in Config.API_KEYS]


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def check_subscription(user_id: int) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    try:
        if not Config.CHANNEL_ID:
            return True

        member = await bot.get_chat_member(chat_id=Config.CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False


def get_main_keyboard():
    """Возвращает основную клавиатуру"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="💬 Задать вопрос")
    builder.button(text="💰 Поддержка")
    builder.button(text="📢 Реклама")
    builder.button(text="ℹ️ О проекте")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)


def get_cancel_keyboard():
    """Возвращает клавиатуру с кнопкой отмены"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚫 Отмена")
    return builder.as_markup(resize_keyboard=True)


def update_dialog_history(user_id: int, role: str, content: str):
    """Обновляет историю диалога пользователя"""
    if user_id not in user_dialogs:
        user_dialogs[user_id] = deque(maxlen=10)
    user_dialogs[user_id].append({"role": role, "content": content})


def format_code(text: str) -> str:
    """Форматирует код с HTML-тегами для подсветки"""
    if not text or "```" not in text:
        return text or "Пустой ответ"

    try:
        parts = text.split("```")
        result = []

        for i, part in enumerate(parts):
            if i % 2 == 1:
                # Блок кода
                lines = part.split('\n')
                language = lines[0] if lines else ''
                code = '\n'.join(lines[1:]) if len(lines) > 1 else part
                result.append(f'<pre><code class="language-{language}">{html.escape(code)}</code></pre>')
            else:
                # Обычный текст
                result.append(part)

        return ''.join(result)
    except Exception as e:
        logger.error(f"Ошибка форматирования кода: {e}")
        return text


def create_copy_button(code_text: str) -> types.InlineKeyboardMarkup:
    """Создает кнопку для копирования кода"""
    if not code_text:
        return None

    code_id = abs(hash(code_text))
    code_storage[code_id] = code_text
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать код", callback_data=f"copy_{code_id}")
    return builder.as_markup()


async def rotate_api_key():
    """Переключается на следующий доступный API ключ"""
    global current_api_key_index
    current_api_key_index = (current_api_key_index + 1) % len(api_clients)
    logger.info(f"Переключено на API ключ #{current_api_key_index + 1}")


async def get_ai_response(messages: list) -> str:
    """Получает ответ от ИИ с автоматическим переключением ключей"""
    if not messages:
        return "Не получены сообщения для обработки"

    max_retries = len(api_clients) * 2  # Две попытки на каждый ключ
    last_error = None

    for attempt in range(max_retries):
        try:
            client = api_clients[current_api_key_index]
            response = await client.chat.completions.create(
                model=Config.MODEL,
                messages=messages,
                max_tokens=1500
            )

            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or "Пустой ответ от ИИ"
            else:
                raise APIError("Пустой ответ от API")

        except APIError as e:
            last_error = str(e)
            logger.error(f"Ошибка API (ключ #{current_api_key_index + 1}, попытка {attempt + 1}): {last_error}")
            await rotate_api_key()
            await asyncio.sleep(1)  # Задержка между попытками

    raise APIError(f"Все попытки исчерпаны. Последняя ошибка: {last_error}")


# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    if not await check_subscription(message.from_user.id):
        channel_link = f"https://t.me/{Config.CHANNEL_ID[1:]}" if Config.CHANNEL_ID and Config.CHANNEL_ID.startswith(
            '@') else Config.CHANNEL_ID
        await message.answer(
            "📢 Для использования бота подпишитесь на наш канал:",
            reply_markup=InlineKeyboardBuilder()
            .button(text="Подписаться", url=channel_link)
            .as_markup()
        )
        return

    await message.answer(
        f"🤖 <b>Добро пожаловать в AI-бота</b> (модель: {Config.MODEL})\n\n"
        f"Доступно API ключей: {len(api_clients)}\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text == '💰 Поддержка')
async def support(message: types.Message):
    await message.answer(
        f"❤️ <b>Поддержать проект:</b>\n{Config.DONATE_LINK}",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text == 'ℹ️ О проекте')
async def project_info(message: types.Message):
    await message.answer(
        Config.PROJECT_INFO,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text == '📢 Реклама')
async def advertise(message: types.Message):
    await message.answer(
        "✉️ Отправьте текст рекламного сообщения:",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(F.text == '🚫 Отмена')
async def cancel_action(message: types.Message):
    await message.answer(
        "Действие отменено",
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text == '💬 Задать вопрос')
async def ask_question(message: types.Message):
    await message.answer(
        "📝 Введите ваш вопрос:",
        reply_markup=get_cancel_keyboard()
    )


@dp.callback_query(F.data.startswith("copy_"))
async def copy_code_handler(callback: types.CallbackQuery):
    try:
        code_id = int(callback.data.split("_")[1])
        if code_id in code_storage:
            await callback.answer(
                "Код скопирован в буфер обмена!\n\n"
                "Для вставки используйте Ctrl+V",
                show_alert=True
            )
        else:
            await callback.answer("Код не найден")
    except Exception as e:
        logger.error(f"Ошибка обработки копирования: {e}")
        await callback.answer("Ошибка копирования")


@dp.message()
async def handle_message(message: types.Message):
    # Игнорируем команды навигации
    if message.text in ['💰 Поддержка', '📢 Реклама', '💬 Задать вопрос', '🚫 Отмена', 'ℹ️ О проекте']:
        return

    if not await check_subscription(message.from_user.id):
        return

    try:
        msg = await message.answer("⏳ Обрабатываю запрос...")

        update_dialog_history(message.from_user.id, "user", message.text)
        dialog_history = list(user_dialogs.get(message.from_user.id, []))

        answer = await get_ai_response(dialog_history)
        formatted_answer = format_code(answer)

        update_dialog_history(message.from_user.id, "assistant", answer)

        reply_markup = None
        if answer and "```" in answer:
            try:
                code_blocks = [block.split('```')[1] for block in answer.split('```')[1::2] if
                               len(block.split('```')) > 1]
                clean_code = '\n\n'.join(code_blocks) if code_blocks else answer
                reply_markup = create_copy_button(clean_code)
            except Exception as e:
                logger.error(f"Ошибка обработки кода: {e}")

        await message.answer(
            formatted_answer,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

        await msg.delete()

    except Exception as e:
        logger.error(f"Ошибка обработки запроса: {str(e)}", exc_info=True)
        await message.answer(
            "⚠️ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже.",
            reply_markup=get_main_keyboard()
        )


async def main():
    logger.info(f"Запуск бота с {len(api_clients)} API ключами")
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("Бот остановлен")