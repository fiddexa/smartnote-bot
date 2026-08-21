import os
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from openai import OpenAI


# =========================================================
# НАСТРОЙКИ
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не найден")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY не найден")

if not RENDER_EXTERNAL_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL не найден")


client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ МАТЕРИАЛОВ
# =========================================================

materials = {}


# =========================================================
# КОМАНДА /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "🧠 <b>SmartNote AI</b>\n\n"
        "Отправьте мне информацию:\n\n"
        "🎤 <b>голосовым сообщением</b>\n"
        "📝 <b>текстом</b>\n\n"
        "Я превращу её в удобный материал для обучения.\n\n"
        "После загрузки вы сможете выбрать:\n"
        "📚 Реферат\n"
        "📝 Конспект\n"
        "⚡ Выжимка\n"
        "🎯 Тезисы\n"
        "❓ Вопросы\n"
        "🧠 Простыми словами"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# КНОПКИ
# =========================================================

def get_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "📚 Реферат",
                callback_data="referat"
            ),
            InlineKeyboardButton(
                "📝 Конспект",
                callback_data="conspect"
            ),
        ],
        [
            InlineKeyboardButton(
                "⚡ Выжимка",
                callback_data="summary"
            ),
            InlineKeyboardButton(
                "🎯 Тезисы",
                callback_data="theses"
            ),
        ],
        [
            InlineKeyboardButton(
                "❓ Вопросы",
                callback_data="questions"
            ),
            InlineKeyboardButton(
                "🧠 Простыми словами",
                callback_data="simple"
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# ПОЛУЧЕНИЕ ТЕКСТА
# =========================================================

async def receive_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not text:
        return

    materials[user_id] = text

    await update.message.reply_text(
        "✅ <b>Материал получен.</b>\n\n"
        "Теперь выберите, что нужно сделать:",
        reply_markup=get_keyboard(),
        parse_mode="HTML"
    )


# =========================================================
# ПОЛУЧЕНИЕ ГОЛОСОВОГО
# =========================================================

async def receive_voice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    await update.message.reply_text(
        "🎤 Получил голосовое сообщение.\n"
        "⏳ Распознаю речь..."
    )

    voice = update.message.voice

    telegram_file = await context.bot.get_file(
        voice.file_id
    )

    audio_path = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".ogg",
            delete=False
        ) as temp:

            audio_path = temp.name

        await telegram_file.download_to_drive(
            audio_path
        )

        with open(audio_path, "rb") as audio:

            transcription = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio,
                language="ru"
            )

        text = transcription.text.strip()

        if not text:

            await update.message.reply_text(
                "❌ Не удалось получить текст из голосового сообщения."
            )

            return

        materials[user_id] = text

        # Telegram ограничивает размер сообщения,
        # поэтому показываем только начало распознанного текста.
        preview = text[:3000]

        if len(text) > 3000:
            preview += "\n\n…"

        await update.message.reply_text(
            "🎤 <b>Голос успешно распознан.</b>\n\n"
            "📄 <b>Распознанный текст:</b>\n\n"
            f"{preview}\n\n"
            "Выберите, что сделать с материалом:",
            reply_markup=get_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
    import traceback
    print("❌ ERROR:", repr(e), flush=True)
    traceback.print_exc()
    await message.answer(
        "❌ Произошла ошибка при обработке материала.\n\n"
        "Попробуйте ещё раз."
    )

    finally:

        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


# =========================================================
# ОБРАБОТКА МАТЕРИАЛА
# =========================================================

async def process_material(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    material = materials.get(user_id)

    if not material:

        await query.message.reply_text(
            "❗ Сначала отправьте текст или голосовое сообщение."
        )

        return

    action = query.data

    prompts = {

        "referat":
            """
Создай качественный реферат по предоставленному материалу.

Структура:
1. Название
2. Введение
3. Основная часть
4. Основные идеи
5. Заключение

Пиши связно и понятно.
Не добавляй выдуманные факты.
Сохраняй важную информацию исходного материала.
""",

        "conspect":
            """
Создай подробный структурированный конспект.

Используй:
- заголовки;
- подзаголовки;
- маркированные пункты;
- определения;
- важные факты;
- причинно-следственные связи;
- выводы.

Конспект должен быть удобен для последующего изучения.
""",

        "summary":
            """
Сделай краткую и очень полезную выжимку материала.

Оставь только действительно важную информацию.
Убери повторы и второстепенные детали.
Сохрани смысл материала.
""",

        "theses":
            """
Выдели главные тезисы материала.

Сделай 5–20 коротких, конкретных и информативных тезисов.
Каждый тезис должен передавать отдельную важную мысль.
""",

        "questions":
            """
Создай вопросы для проверки знаний по материалу.

Сделай вопросы разного уровня сложности.
После каждого вопроса дай правильный ответ.

В конце добавь 5 наиболее важных вопросов для подготовки к экзамену.
""",

        "simple":
            """
Объясни материал простыми словами.

Представь, что человек впервые изучает эту тему.
Сложные термины объясняй понятным языком.
Используй простые примеры, если они помогают понять тему.
Не искажай исходную информацию.
"""
    }

    instruction = prompts.get(action)

    if not instruction:
        return

    await query.message.reply_text(
        "🧠 Анализирую материал...\n"
        "⏳ Пожалуйста, подождите."
    )

    try:

        response = client.responses.create(

            model="gpt-5.6-luna",

            instructions=(
                "Ты — SmartNote AI, интеллектуальный учебный "
                "ассистент.\n\n"
                "Работай прежде всего с предоставленным "
                "пользователем материалом.\n"
                "Не выдумывай факты.\n"
                "Если в материале недостаточно информации, "
                "не придумывай отсутствующие сведения.\n"
                "Отвечай на русском языке.\n"
                "Используй понятную структуру."
            ),

            input=(
                instruction
                + "\n\n"
                + "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"
                + material
            )
        )

        result = response.output_text.strip()

        if not result:

            await query.message.reply_text(
                "❌ ИИ не вернул результат. Попробуйте ещё раз."
            )

            return

        # Отправляем результат частями,
        # чтобы не превысить лимит Telegram.
        chunk_size = 3800

        for start_index in range(
            0,
            len(result),
            chunk_size
        ):

            await query.message.reply_text(
                result[
                    start_index:
                    start_index + chunk_size
                ]
            )

    except Exception as error:

        print("OPENAI ERROR:", repr(error))

        await query.message.reply_text(
            "❌ Произошла ошибка при обработке материала.\n\n"
            "Попробуйте ещё раз."
        )


# =========================================================
# ЗАПУСК
# =========================================================

def main():

    webhook_url = (
        RENDER_EXTERNAL_URL.rstrip("/")
        + "/telegram"
    )

    print("====================================")
    print("SmartNote AI запускается...")
    print("Webhook:", webhook_url)
    print("Port:", PORT)
    print("====================================")

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # Команда /start
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # Голосовые сообщения
    application.add_handler(
        MessageHandler(
            filters.VOICE,
            receive_voice
        )
    )

    # Текстовые сообщения
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_text
        )
    )

    # Кнопки
    application.add_handler(
        CallbackQueryHandler(
            process_material
        )
    )

    # Webhook для Render
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="telegram",
        webhook_url=webhook_url,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
