import os
import tempfile
import traceback

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

RENDER_EXTERNAL_URL = os.getenv(
    "RENDER_EXTERNAL_URL",
    "https://smartnote-bot-gb2i.onrender.com"
)

# Модель можно изменить в Render Environment
# через переменную OPENAI_MODEL
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna"
)

# Модель распознавания голоса
TRANSCRIBE_MODEL = os.getenv(
    "TRANSCRIBE_MODEL",
    "gpt-4o-mini-transcribe"
)


# =========================================================
# ПРОВЕРКА НАСТРОЕК
# =========================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "❌ TELEGRAM_TOKEN не найден в Environment"
    )

if not OPENAI_API_KEY:
    raise RuntimeError(
        "❌ OPENAI_API_KEY не найден в Environment"
    )

if not RENDER_EXTERNAL_URL:
    raise RuntimeError(
        "❌ RENDER_EXTERNAL_URL не найден"
    )


# =========================================================
# OPENAI CLIENT
# =========================================================

client = OpenAI(
    api_key=OPENAI_API_KEY
)


# =========================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ МАТЕРИАЛОВ
# =========================================================

materials = {}


# =========================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
# =========================================================

def split_text(text, chunk_size=3800):
    """
    Разбивает длинный текст на части,
    чтобы не превысить лимит Telegram.
    """

    return [
        text[i:i + chunk_size]
        for i in range(0, len(text), chunk_size)
    ]


# =========================================================
# КОМАНДА /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🧠 <b>SmartNote AI</b>\n\n"

        "Отправьте мне учебный материал:\n\n"

        "🎤 <b>голосовым сообщением</b>\n"
        "📝 <b>текстом</b>\n\n"

        "Я помогу превратить его "
        "в удобный материал для обучения.\n\n"

        "После загрузки доступны:\n\n"

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

    try:

        user_id = update.effective_user.id

        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()

        if not text:
            return

        # Сохраняем материал
        materials[user_id] = text

        print(
            f"📝 Получен текст от пользователя {user_id}. "
            f"Длина: {len(text)} символов",
            flush=True
        )

        await update.message.reply_text(
            "✅ <b>Материал получен.</b>\n\n"
            "Теперь выберите, что нужно сделать:",
            reply_markup=get_keyboard(),
            parse_mode="HTML"
        )

    except Exception as error:

        print(
            "❌ TEXT ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()

        if update.message:

            await update.message.reply_text(
                "❌ Произошла ошибка при получении текста.\n\n"
                "Попробуйте ещё раз."
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

    telegram_file = None
    audio_path = None

    try:

        print(
            f"🎤 Начинаю обработку голосового "
            f"от пользователя {user_id}",
            flush=True
        )

        # Получаем файл Telegram
        telegram_file = await context.bot.get_file(
            voice.file_id
        )

        # Создаём временный файл
        with tempfile.NamedTemporaryFile(
            suffix=".ogg",
            delete=False
        ) as temp:

            audio_path = temp.name

        # Скачиваем голосовое
        await telegram_file.download_to_drive(
            audio_path
        )

        print(
            f"🎤 Голосовой файл скачан: {audio_path}",
            flush=True
        )

        # Открываем аудио
        with open(
            audio_path,
            "rb"
        ) as audio:

            transcription = (
                client.audio.transcriptions.create(
                    model=TRANSCRIBE_MODEL,
                    file=audio,
                    language="ru"
                )
            )

        text = transcription.text.strip()

        print(
            f"🎤 Распознавание завершено. "
            f"Длина текста: {len(text)}",
            flush=True
        )

        if not text:

            await update.message.reply_text(
                "❌ Не удалось получить текст "
                "из голосового сообщения."
            )

            return

        # Сохраняем материал
        materials[user_id] = text

        # Показываем первые 3000 символов
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

    except Exception as error:

        print(
            "====================================",
            flush=True
        )

        print(
            "❌ VOICE ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()

        print(
            "====================================",
            flush=True
        )

        await update.message.reply_text(
            "❌ Произошла ошибка при обработке "
            "голосового сообщения.\n\n"
            "Попробуйте ещё раз."
        )

    finally:

        # Удаляем временный файл
        if (
            audio_path
            and os.path.exists(audio_path)
        ):

            try:

                os.remove(audio_path)

                print(
                    "🗑 Временный аудиофайл удалён.",
                    flush=True
                )

            except Exception as cleanup_error:

                print(
                    "⚠️ Не удалось удалить "
                    "временный файл:",
                    repr(cleanup_error),
                    flush=True
                )


# =========================================================
# ПРОМПТЫ
# =========================================================

PROMPTS = {

    "referat": """
Создай качественный реферат по предоставленному материалу.

Структура:

1. Название
2. Введение
3. Основная часть
4. Основные идеи
5. Заключение

Требования:

- Пиши связно и понятно.
- Сохраняй важную информацию исходного материала.
- Не выдумывай факты.
- Не добавляй сведения, которых нет в материале,
  если они не нужны для понимания.
- Используй логичную структуру.
""",

    "conspect": """
Создай подробный структурированный конспект.

Используй:

- заголовки;
- подзаголовки;
- маркированные пункты;
- определения;
- важные факты;
- причинно-следственные связи;
- выводы.

Конспект должен быть удобен
для последующего изучения и повторения.

Не выдумывай отсутствующую информацию.
""",

    "summary": """
Сделай краткую и очень полезную выжимку материала.

Оставь только действительно важную информацию.

Убери:

- повторы;
- второстепенные детали;
- лишние пояснения.

Сохрани основной смысл материала.

В начале дай краткое резюме темы,
а затем перечисли ключевые факты.
""",

    "theses": """
Выдели главные тезисы материала.

Сделай от 5 до 20 коротких,
конкретных и информативных тезисов.

Каждый тезис должен передавать
отдельную важную мысль.

Не повторяй одну и ту же мысль разными словами.
""",

    "questions": """
Создай вопросы для проверки знаний
по предоставленному материалу.

Сделай вопросы разного уровня сложности:

1. Простые
2. Средние
3. Сложные

После каждого вопроса
дай правильный ответ.

В конце добавь:

"⭐ 5 главных вопросов для подготовки"

и выбери 5 наиболее важных вопросов.
""",

    "simple": """
Объясни материал простыми словами.

Представь, что человек впервые
изучает эту тему.

Сложные термины объясняй понятным языком.

Используй простые примеры,
если они помогают понять тему.

Не искажай исходную информацию.

В конце сделай короткий блок:

"💡 Главное, что нужно запомнить"
"""
}


# =========================================================
# ОБРАБОТКА МАТЕРИАЛА
# =========================================================

async def process_material(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    user_id = query.from_user.id

    material = materials.get(user_id)

    # -----------------------------------------------------
    # ПРОВЕРКА МАТЕРИАЛА
    # -----------------------------------------------------

    if not material:

        await query.message.reply_text(
            "❗ Сначала отправьте текст "
            "или голосовое сообщение."
        )

        return

    action = query.data

    instruction = PROMPTS.get(action)

    if not instruction:

        print(
            f"❌ Неизвестная команда кнопки: {action}",
            flush=True
        )

        return

    # -----------------------------------------------------
    # СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ
    # -----------------------------------------------------

    await query.message.reply_text(
        "🧠 Анализирую материал...\n"
        "⏳ Пожалуйста, подождите."
    )

    print(
        "====================================",
        flush=True
    )

    print(
        f"🧠 Начинаю AI обработку",
        flush=True
    )

    print(
        f"👤 User ID: {user_id}",
        flush=True
    )

    print(
        f"🎯 Action: {action}",
        flush=True
    )

    print(
        f"🤖 Model: {OPENAI_MODEL}",
        flush=True
    )

    print(
        f"📄 Material length: {len(material)}",
        flush=True
    )

    print(
        "====================================",
        flush=True
    )

    # -----------------------------------------------------
    # ЗАПРОС К OPENAI
    # -----------------------------------------------------

    try:

        response = client.responses.create(

            model=OPENAI_MODEL,

            instructions=(
                "Ты — SmartNote AI, "
                "интеллектуальный учебный ассистент.\n\n"

                "Твоя задача — помогать пользователю "
                "изучать предоставленный материал.\n\n"

                "Работай прежде всего "
                "с материалом пользователя.\n\n"

                "Не выдумывай факты.\n"

                "Если в материале недостаточно информации, "
                "не придумывай отсутствующие сведения.\n\n"

                "Отвечай на русском языке.\n\n"

                "Используй понятную структуру.\n\n"

                "Если материал содержит ошибки или "
                "неоднозначные утверждения, "
                "не исправляй их молча — "
                "при необходимости укажи на это."
            ),

            input=(
                "ЗАДАНИЕ:\n\n"
                + instruction
                + "\n\n"
                + "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"
                + material
            )
        )

        # -------------------------------------------------
        # ПОЛУЧАЕМ РЕЗУЛЬТАТ
        # -------------------------------------------------

        result = response.output_text.strip()

        print(
            "====================================",
            flush=True
        )

        print(
            "✅ OPENAI RESPONSE ПОЛУЧЕН",
            flush=True
        )

        print(
            f"📄 Result length: {len(result)}",
            flush=True
        )

        print(
            "====================================",
            flush=True
        )

        # -------------------------------------------------
        # ПРОВЕРКА ПУСТОГО ОТВЕТА
        # -------------------------------------------------

        if not result:

            print(
                "❌ OpenAI вернул пустой результат.",
                flush=True
            )

            await query.message.reply_text(
                "❌ ИИ не вернул результат.\n\n"
                "Попробуйте ещё раз."
            )

            return

        # -------------------------------------------------
        # ОТПРАВКА РЕЗУЛЬТАТА ЧАСТЯМИ
        # -------------------------------------------------

        chunks = split_text(
            result,
            3800
        )

        print(
            f"📤 Отправляю {len(chunks)} частей "
            "пользователю.",
            flush=True
        )

        for index, chunk in enumerate(
            chunks,
            start=1
        ):

            await query.message.reply_text(
                chunk
            )

            print(
                f"📤 Отправлена часть "
                f"{index}/{len(chunks)}",
                flush=True
            )

        print(
            "✅ Обработка успешно завершена.",
            flush=True
        )

    # -----------------------------------------------------
    # ОШИБКА OPENAI
    # -----------------------------------------------------

    except Exception as error:

        print(
            "====================================",
            flush=True
        )

        print(
            "❌ OPENAI ERROR:",
            repr(error),
            flush=True
        )

        print(
            "❌ ERROR TYPE:",
            type(error).__name__,
            flush=True
        )

        traceback.print_exc()

        print(
            "====================================",
            flush=True
        )

        await query.message.reply_text(
            "❌ Произошла ошибка при обработке материала.\n\n"
            "Техническая информация записана "
            "в Render Logs."
        )


# =========================================================
# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК
# =========================================================

async def error_handler(
    update,
    context
):

    print(
        "====================================",
        flush=True
    )

    print(
        "❌ GLOBAL BOT ERROR:",
        repr(context.error),
        flush=True
    )

    traceback.print_exception(
        type(context.error),
        context.error,
        context.error.__traceback__
    )

    print(
        "====================================",
        flush=True
    )


# =========================================================
# ЗАПУСК
# =========================================================

def main():

    webhook_url = (
        RENDER_EXTERNAL_URL.rstrip("/")
        + "/telegram"
    )

    print(
        "====================================",
        flush=True
    )

    print(
        "🧠 SmartNote AI запускается...",
        flush=True
    )

    print(
        f"🌐 Webhook: {webhook_url}",
        flush=True
    )

    print(
        f"🔌 Port: {PORT}",
        flush=True
    )

    print(
        f"🤖 AI Model: {OPENAI_MODEL}",
        flush=True
    )

    print(
        f"🎤 Transcription Model: {TRANSCRIBE_MODEL}",
        flush=True
    )

    print(
        "====================================",
        flush=True
    )

    # -----------------------------------------------------
    # СОЗДАНИЕ APPLICATION
    # -----------------------------------------------------

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # КОМАНДА /START
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # -----------------------------------------------------
    # ГОЛОСОВЫЕ
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.VOICE,
            receive_voice
        )
    )

    # -----------------------------------------------------
    # ТЕКСТ
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_text
        )
    )

    # -----------------------------------------------------
    # INLINE BUTTONS
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            process_material
        )
    )

    # -----------------------------------------------------
    # GLOBAL ERROR HANDLER
    # -----------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    # -----------------------------------------------------
    # WEBHOOK
    # -----------------------------------------------------

    print(
        "🚀 Запускаю Telegram webhook...",
        flush=True
    )

    application.run_webhook(

        listen="0.0.0.0",

        port=PORT,

        url_path="telegram",

        webhook_url=webhook_url,

        drop_pending_updates=True
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
