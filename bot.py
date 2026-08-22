import os
import tempfile
import asyncio
import traceback

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from google import genai
from groq import Groq
from openai import OpenAI


# =========================================================
# НАСТРОЙКИ
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")


# =========================================================
# ПРОВЕРКА TELEGRAM
# =========================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "❌ TELEGRAM_TOKEN не найден в Environment Variables"
    )


# =========================================================
# ПРОВЕРКА RENDER
# =========================================================

if not RENDER_EXTERNAL_URL:
    raise RuntimeError(
        "❌ RENDER_EXTERNAL_URL не найден в Environment Variables"
    )


# =========================================================
# AI КЛИЕНТЫ
# =========================================================

gemini_client = None
groq_client = None
openrouter_client = None


if GEMINI_API_KEY:

    try:

        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print(
            "✅ Gemini API подключен",
            flush=True
        )

    except Exception as error:

        print(
            "❌ Gemini initialization error:",
            repr(error),
            flush=True
        )


if GROQ_API_KEY:

    try:

        groq_client = Groq(
            api_key=GROQ_API_KEY
        )

        print(
            "✅ Groq API подключен",
            flush=True
        )

    except Exception as error:

        print(
            "❌ Groq initialization error:",
            repr(error),
            flush=True
        )


if OPENROUTER_API_KEY:

    try:

        openrouter_client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )

        print(
            "✅ OpenRouter API подключен",
            flush=True
        )

    except Exception as error:

        print(
            "❌ OpenRouter initialization error:",
            repr(error),
            flush=True
        )


# =========================================================
# ХРАНИЛИЩЕ МАТЕРИАЛОВ
# =========================================================

materials = {}


# =========================================================
# START
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

        "Я помогу превратить его в удобный "
        "материал для обучения.\n\n"

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
# КЛАВИАТУРА
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

        if not update.message:
            return

        if not update.message.text:
            return

        user_id = update.effective_user.id

        text = update.message.text.strip()

        if not text:
            return

        materials[user_id] = text

        print(
            f"📥 Получен текст от пользователя {user_id}",
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


# =========================================================
# РАСПОЗНАВАНИЕ ГОЛОСА
# =========================================================

async def transcribe_voice(
    audio_path
):

    if not groq_client:

        raise RuntimeError(
            "GROQ_API_KEY не настроен. "
            "Для голосовых сообщений нужен Groq."
        )

    def do_transcription():

        with open(
            audio_path,
            "rb"
        ) as audio_file:

            result = groq_client.audio.transcriptions.create(

                file=audio_file,

                model="whisper-large-v3-turbo",

                language="ru",

                response_format="json",

                temperature=0
            )

        return result.text.strip()

    return await asyncio.to_thread(
        do_transcription
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
        "🎤 <b>Голосовое получено.</b>\n\n"
        "⏳ Распознаю речь...",
        parse_mode="HTML"
    )

    voice = update.message.voice

    audio_path = None

    try:

        telegram_file = await context.bot.get_file(
            voice.file_id
        )

        with tempfile.NamedTemporaryFile(
            suffix=".ogg",
            delete=False
        ) as temp:

            audio_path = temp.name

        await telegram_file.download_to_drive(
            audio_path
        )

        print(
            f"🎤 Распознавание голосового: {audio_path}",
            flush=True
        )

        text = await transcribe_voice(
            audio_path
        )

        if not text:

            await update.message.reply_text(
                "❌ Не удалось распознать голосовое сообщение."
            )

            return

        materials[user_id] = text

        preview = text[:3000]

        if len(text) > 3000:

            preview += "\n\n…"

        await update.message.reply_text(

            "✅ <b>Голос успешно распознан.</b>\n\n"

            "📄 <b>Распознанный текст:</b>\n\n"

            + preview

            + "\n\n"
            "Выберите, что сделать с материалом:",

            reply_markup=get_keyboard(),

            parse_mode="HTML"
        )

        print(
            f"✅ Голос успешно распознан "
            f"для пользователя {user_id}",
            flush=True
        )

    except Exception as error:

        print(
            "❌ VOICE ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(

            "❌ Не удалось обработать голосовое сообщение.\n\n"
            "Проверьте настройки GROQ_API_KEY."
        )

    finally:

        if (
            audio_path
            and os.path.exists(audio_path)
        ):

            try:

                os.remove(
                    audio_path
                )

            except Exception:
                pass


# =========================================================
# PROMPTS
# =========================================================

prompts = {

    "referat":
        """
Создай качественный учебный реферат
по предоставленному материалу.

Структура:

1. Название
2. Введение
3. Основная часть
4. Основные идеи
5. Заключение

Пиши связно, грамотно и понятно.

Не выдумывай факты.

Основывайся прежде всего
на предоставленном материале.

Если информации недостаточно,
не добавляй выдуманные сведения.
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

Конспект должен быть удобен
для последующего изучения.
""",

    "summary":
        """
Сделай краткую и очень полезную
выжимку материала.

Оставь только действительно
важную информацию.

Убери повторы и второстепенные детали.

Сохрани основной смысл материала.
""",

    "theses":
        """
Выдели главные тезисы материала.

Сделай от 5 до 20 коротких,
конкретных и информативных тезисов.

Каждый тезис должен передавать
отдельную важную мысль.
""",

    "questions":
        """
Создай вопросы для проверки знаний
по предоставленному материалу.

Сделай вопросы разного уровня сложности.

После каждого вопроса
дай правильный ответ.

В конце добавь 5 наиболее важных
вопросов для подготовки к экзамену.
""",

    "simple":
        """
Объясни материал простыми словами.

Представь, что человек
впервые изучает эту тему.

Сложные термины объясняй
понятным языком.

Используй простые примеры,
если они помогают понять тему.

Не искажай исходную информацию.
"""
}


# =========================================================
# GEMINI
# =========================================================

async def ask_gemini(
    instruction,
    material
):

    if not gemini_client:

        raise RuntimeError(
            "Gemini API не настроен."
        )

    full_prompt = (

        "Ты — SmartNote AI, "
        "интеллектуальный учебный ассистент.\n\n"

        "Работай прежде всего "
        "с материалом пользователя.\n"

        "Не выдумывай факты.\n"

        "Не добавляй информацию, "
        "которой нет в материале, "
        "если она не нужна для объяснения.\n"

        "Отвечай на русском языке.\n"

        "Используй понятную структуру.\n\n"

        + instruction

        + "\n\n"
        "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"

        + material
    )

    def generate():

        response = gemini_client.models.generate_content(

            model="gemini-2.5-flash-lite",

            contents=full_prompt
        )

        return response.text

    result = await asyncio.to_thread(
        generate
    )

    if not result:

        raise RuntimeError(
            "Gemini вернул пустой ответ."
        )

    return result.strip()


# =========================================================
# GROQ
# =========================================================

async def ask_groq(
    instruction,
    material
):

    if not groq_client:

        raise RuntimeError(
            "Groq API не настроен."
        )

    system_prompt = """
Ты — SmartNote AI,
интеллектуальный учебный ассистент.

Работай прежде всего
с материалом пользователя.

Не выдумывай факты.

Если информации недостаточно,
не придумывай отсутствующие сведения.

Отвечай на русском языке.

Используй понятную структуру.
"""

    user_prompt = (
        instruction
        + "\n\n"
        + "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"
        + material
    )

    def generate():

        response = groq_client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content": user_prompt
                }

            ],

            temperature=0.2
        )

        return response.choices[
            0
        ].message.content

    result = await asyncio.to_thread(
        generate
    )

    if not result:

        raise RuntimeError(
            "Groq вернул пустой ответ."
        )

    return result.strip()


# =========================================================
# OPENROUTER FREE
# =========================================================

async def ask_openrouter(
    instruction,
    material
):

    if not openrouter_client:

        raise RuntimeError(
            "OpenRouter API не настроен."
        )

    system_prompt = """
Ты — SmartNote AI,
интеллектуальный учебный ассистент.

Работай прежде всего
с материалом пользователя.

Не выдумывай факты.

Отвечай на русском языке.

Используй понятную структуру.
"""

    user_prompt = (
        instruction
        + "\n\n"
        + "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"
        + material
    )

    def generate():

        response = openrouter_client.chat.completions.create(

            model="openrouter/free",

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content": user_prompt
                }

            ],

            temperature=0.2
        )

        return response.choices[
            0
        ].message.content

    result = await asyncio.to_thread(
        generate
    )

    if not result:

        raise RuntimeError(
            "OpenRouter вернул пустой ответ."
        )

    return result.strip()


# =========================================================
# AI СИСТЕМА С РЕЗЕРВНЫМИ ВАРИАНТАМИ
# =========================================================

async def generate_ai_result(
    instruction,
    material
):

    errors = []


    # =====================================================
    # 1. GEMINI
    # =====================================================

    if gemini_client:

        try:

            print(
                "🤖 Пробуем Gemini...",
                flush=True
            )

            result = await ask_gemini(
                instruction,
                material
            )

            print(
                "✅ Ответ получен через Gemini",
                flush=True
            )

            return result

        except Exception as error:

            print(
                "⚠️ Gemini ERROR:",
                repr(error),
                flush=True
            )

            errors.append(
                "Gemini: "
                + repr(error)
            )


    # =====================================================
    # 2. GROQ
    # =====================================================

    if groq_client:

        try:

            print(
                "🤖 Пробуем Groq...",
                flush=True
            )

            result = await ask_groq(
                instruction,
                material
            )

            print(
                "✅ Ответ получен через Groq",
                flush=True
            )

            return result

        except Exception as error:

            print(
                "⚠️ Groq ERROR:",
                repr(error),
                flush=True
            )

            errors.append(
                "Groq: "
                + repr(error)
            )


    # =====================================================
    # 3. OPENROUTER
    # =====================================================

    if openrouter_client:

        try:

            print(
                "🤖 Пробуем OpenRouter Free...",
                flush=True
            )

            result = await ask_openrouter(
                instruction,
                material
            )

            print(
                "✅ Ответ получен через OpenRouter",
                flush=True
            )

            return result

        except Exception as error:

            print(
                "⚠️ OpenRouter ERROR:",
                repr(error),
                flush=True
            )

            errors.append(
                "OpenRouter: "
                + repr(error)
            )


    # =====================================================
    # НИ ОДИН AI НЕ СРАБОТАЛ
    # =====================================================

    print(
        "❌ ВСЕ AI ПРОВАЙДЕРЫ НЕДОСТУПНЫ",
        flush=True
    )

    for error in errors:

        print(
            error,
            flush=True
        )

    raise RuntimeError(
        "Все AI-провайдеры недоступны."
    )


# =========================================================
# ОБРАБОТКА КНОПОК
# =========================================================

async def process_material(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    material = materials.get(
        user_id
    )

    if not material:

        await query.message.reply_text(

            "❗ Сначала отправьте "
            "текст или голосовое сообщение."
        )

        return


    action = query.data

    instruction = prompts.get(
        action
    )

    if not instruction:

        return


    await query.message.reply_text(

        "🧠 <b>Анализирую материал...</b>\n\n"
        "⏳ Пожалуйста, подождите.",

        parse_mode="HTML"
    )


    try:

        print(
            "====================================",
            flush=True
        )

        print(
            f"🧠 Новый AI запрос: {action}",
            flush=True
        )

        print(
            f"👤 User ID: {user_id}",
            flush=True
        )

        print(
            f"📄 Размер материала: {len(material)} символов",
            flush=True
        )


        result = await generate_ai_result(

            instruction,

            material
        )


        if not result:

            await query.message.reply_text(

                "❌ ИИ не вернул результат."
            )

            return


        # =================================================
        # ОТПРАВКА РЕЗУЛЬТАТА ЧАСТЯМИ
        # =================================================

        chunk_size = 3800

        for start_index in range(
            0,
            len(result),
            chunk_size
        ):

            chunk = result[
                start_index:
                start_index + chunk_size
            ]

            await query.message.reply_text(
                chunk
            )


        print(
            "✅ Результат отправлен пользователю",
            flush=True
        )

        print(
            "====================================",
            flush=True
        )


    except Exception as error:

        print(
            "❌ PROCESS ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()


        await query.message.reply_text(

            "❌ <b>Не удалось обработать материал.</b>\n\n"

            "Все доступные AI-сервисы сейчас "
            "недоступны или достигли бесплатного лимита.\n\n"

            "Попробуйте немного позже.",

            parse_mode="HTML"
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
        "🧠 SmartNote AI запускается",
        flush=True
    )

    print(
        "====================================",
        flush=True
    )

    print(
        "Webhook:",
        webhook_url,
        flush=True
    )

    print(
        "Port:",
        PORT,
        flush=True
    )

    print(
        "Gemini:",
        "ON" if gemini_client else "OFF",
        flush=True
    )

    print(
        "Groq:",
        "ON" if groq_client else "OFF",
        flush=True
    )

    print(
        "OpenRouter:",
        "ON" if openrouter_client else "OFF",
        flush=True
    )

    print(
        "====================================",
        flush=True
    )


    application = (

        Application.builder()

        .token(
            TELEGRAM_TOKEN
        )

        .build()
    )


    # =====================================================
    # /START
    # =====================================================

    application.add_handler(

        CommandHandler(
            "start",
            start
        )
    )


    # =====================================================
    # ГОЛОС
    # =====================================================

    application.add_handler(

        MessageHandler(
            filters.VOICE,
            receive_voice
        )
    )


    # =====================================================
    # ТЕКСТ
    # =====================================================

    application.add_handler(

        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            receive_text
        )
    )


    # =====================================================
    # КНОПКИ
    # =====================================================

    application.add_handler(

        CallbackQueryHandler(
            process_material
        )
    )


    # =====================================================
    # WEBHOOK
    # =====================================================

    application.run_webhook(

        listen="0.0.0.0",

        port=PORT,

        url_path="telegram",

        webhook_url=webhook_url,

        drop_pending_updates=True
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    main()
