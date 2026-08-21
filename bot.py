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


# =========================
# НАСТРОЙКИ
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================
# ХРАНЕНИЕ МАТЕРИАЛОВ
# =========================

materials = {}


# =========================
# /start
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "🧠 Добро пожаловать в SmartNote AI!\n\n"
        "Отправьте мне:\n\n"
        "🎤 голосовое сообщение\n"
        "📝 или обычный текст\n\n"
        "Я превращу информацию в:\n"
        "📚 реферат\n"
        "📝 конспект\n"
        "⚡ выжимку\n"
        "🎯 тезисы\n"
        "❓ вопросы\n"
        "🧠 объяснение простыми словами"
    )

    await update.message.reply_text(text)


# =========================
# КНОПКИ
# =========================

def get_keyboard():

    keyboard = [
        [
            InlineKeyboardButton("📚 Реферат", callback_data="referat"),
            InlineKeyboardButton("📝 Конспект", callback_data="conspect"),
        ],
        [
            InlineKeyboardButton("⚡ Выжимка", callback_data="summary"),
            InlineKeyboardButton("🎯 Тезисы", callback_data="theses"),
        ],
        [
            InlineKeyboardButton("❓ Вопросы", callback_data="questions"),
            InlineKeyboardButton("🧠 Проще", callback_data="simple"),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# ПОЛУЧЕНИЕ ТЕКСТА
# =========================

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    text = update.message.text

    materials[user_id] = text

    await update.message.reply_text(
        "✅ Материал получен.\n\n"
        "Выберите, что нужно сделать:",
        reply_markup=get_keyboard()
    )


# =========================
# ПОЛУЧЕНИЕ ГОЛОСА
# =========================

async def receive_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    await update.message.reply_text(
        "🎤 Получил голосовое сообщение.\n"
        "⏳ Распознаю речь..."
    )

    voice = update.message.voice

    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(
        suffix=".ogg",
        delete=False
    ) as temp:

        audio_path = temp.name

    await file.download_to_drive(audio_path)

    try:

        with open(audio_path, "rb") as audio:

            transcription = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio
            )

        text = transcription.text

        materials[user_id] = text

        await update.message.reply_text(
            "🎤 Голос успешно распознан.\n\n"
            "📄 Распознанный текст:\n\n"
            f"{text[:3500]}\n\n"
            "Выберите, что сделать с материалом:",
            reply_markup=get_keyboard()
        )

    except Exception as e:

        await update.message.reply_text(
            "❌ Не удалось распознать голосовое сообщение.\n\n"
            "Попробуйте отправить его ещё раз."
        )

        print("VOICE ERROR:", e)

    finally:

        if os.path.exists(audio_path):
            os.remove(audio_path)


# =========================
# ОБРАБОТКА ЗАПРОСА
# =========================

async def process_material(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if user_id not in materials:

        await query.message.reply_text(
            "❗ Сначала отправьте текст или голосовое сообщение."
        )

        return

    material = materials[user_id]

    action = query.data

    prompts = {

        "referat":
            "Создай качественный структурированный реферат по этому материалу. "
            "Выдели введение, основные части, заключение. "
            "Сохрани важную информацию.",

        "conspect":
            "Создай подробный и хорошо структурированный конспект. "
            "Используй заголовки, подзаголовки и маркированные пункты. "
            "Выделяй определения, факты и важные идеи.",

        "summary":
            "Сделай максимально полезную краткую выжимку материала. "
            "Оставь только самую важную информацию.",

        "theses":
            "Выдели главные тезисы материала. "
            "Сделай их короткими, понятными и информативными.",

        "questions":
            "Создай вопросы для проверки знаний по этому материалу. "
            "Добавь правильные ответы после каждого вопроса.",

        "simple":
            "Объясни этот материал простыми словами, "
            "как человеку, который впервые изучает эту тему."
    }

    prompt = prompts.get(action)

    await query.message.reply_text(
        "🧠 Анализирую материал...\n"
        "⏳ Это может занять некоторое время."
    )

    try:

        response = client.responses.create(

            model="gpt-5-mini",

            instructions=(
                "Ты — интеллектуальный учебный ассистент. "
                "Работай только с предоставленным материалом. "
                "Не выдумывай факты. "
                "Отвечай на русском языке. "
                "Делай структуру максимально удобной для обучения."
            ),

            input=(
                f"{prompt}\n\n"
                "МАТЕРИАЛ:\n"
                f"{material}"
            )
        )

        result = response.output_text

        # Telegram ограничивает размер одного сообщения
        chunk_size = 3800

        for i in range(0, len(result), chunk_size):

            await query.message.reply_text(
                result[i:i + chunk_size]
            )

    except Exception as e:

        print("OPENAI ERROR:", e)

        await query.message.reply_text(
            "❌ Произошла ошибка при обработке материала.\n"
            "Попробуйте ещё раз."
        )


# =========================
# ЗАПУСК
# =========================

def main():

    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN не найден")

    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не найден")

    app = Application.builder().token(
        TELEGRAM_TOKEN
    ).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        MessageHandler(
            filters.VOICE,
            receive_voice
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_text
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            process_material
        )
    )

    print("SmartNote AI запущен!")

    app.run_polling()


if __name__ == "__main__":
    main()
