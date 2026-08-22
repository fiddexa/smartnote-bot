import os
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
from openai import OpenAI


# =========================================================
# НАСТРОЙКИ
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")


# =========================================================
# ПРОВЕРКА
# =========================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "TELEGRAM_TOKEN не найден в Render Environment Variables"
    )

if not RENDER_EXTERNAL_URL:
    raise RuntimeError(
        "RENDER_EXTERNAL_URL не найден в Render Environment Variables"
    )


# =========================================================
# AI КЛИЕНТЫ
# =========================================================

gemini_client = None
openrouter_client = None


# =========================================================
# GEMINI
# =========================================================

if GEMINI_API_KEY:

    try:

        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print(
            "✅ Gemini подключен",
            flush=True
        )

    except Exception as error:

        print(
            "❌ Gemini initialization error:",
            repr(error),
            flush=True
        )


# =========================================================
# OPENROUTER
# =========================================================

if OPENROUTER_API_KEY:

    try:

        openrouter_client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )

        print(
            "✅ OpenRouter подключен",
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

        "Отправьте мне учебный материал "
        "<b>текстом</b>.\n\n"

        "Я превращу его в удобный "
        "материал для обучения.\n\n"

        "После отправки доступны:\n\n"

        "📚 Реферат\n"
        "📝 Конспект\n"
        "⚡ Выжимка\n"
        "🎯 Тезисы\n"
        "❓ Вопросы\n"
        "🧠 Простыми словами\n\n"

        "🎤 Голосовые сообщения появятся "
        "в следующей версии."
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

        text = update.message.text.strip()

        if not text:
            return

        user_id = update.effective_user.id

        materials[user_id] = text

        print(
            "====================================",
            flush=True
        )

        print(
            f"📥 Получен материал",
            flush=True
        )

        print(
            f"👤 User ID: {user_id}",
            flush=True
        )

        print(
            f"📄 Размер: {len(text)} символов",
            flush=True
        )

        print(
            "====================================",
            flush=True
        )

        await update.message.reply_text(

            "✅ <b>Материал получен.</b>\n\n"

            "Теперь выберите, "
            "что нужно сделать:",

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


        await update.message.reply_text(
            "❌ Не удалось сохранить материал."
        )


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

Пиши грамотно, связно и понятно.

Основывайся прежде всего
на предоставленном материале.

Не выдумывай факты.
""",

    "conspect":
        """
Создай подробный структурированный
учебный конспект.

Используй:

- заголовки;
- подзаголовки;
- определения;
- важные факты;
- маркированные пункты;
- причинно-следственные связи;
- выводы.

Сделай конспект удобным
для изучения и повторения.
""",

    "summary":
        """
Сделай краткую и полезную
выжимку материала.

Оставь только самую важную
информацию.

Удали повторы
и второстепенные детали.

Сохрани основной смысл.
""",

    "theses":
        """
Выдели главные тезисы
из предоставленного материала.

Сделай от 5 до 20 тезисов.

Каждый тезис должен быть:
- коротким;
- конкретным;
- информативным.

Не добавляй выдуманную информацию.
""",

    "questions":
        """
Создай вопросы для проверки знаний
по предоставленному материалу.

Сделай вопросы разного уровня сложности.

После каждого вопроса
укажи правильный ответ.

В конце добавь 5 наиболее важных
вопросов для подготовки к экзамену.
""",

    "simple":
        """
Объясни предоставленный материал
простыми словами.

Представь, что человек
впервые изучает эту тему.

Сложные термины объясняй
понятным языком.

Если полезно, используй
простые примеры.

Не искажай исходную информацию.
"""
}


# =========================================================
# ОБЩАЯ ИНСТРУКЦИЯ
# =========================================================

SYSTEM_PROMPT = """
Ты — SmartNote AI,
интеллектуальный учебный ассистент.

Твоя задача — помогать пользователю
изучать предоставленный материал.

Работай прежде всего
с материалом пользователя.

Не выдумывай факты.

Не добавляй информацию,
которой нет в материале,
если она не требуется
для понятного объяснения.

Если информации недостаточно,
честно укажи это.

Отвечай на русском языке.

Используй понятную структуру.

Результат должен быть полезным
для обучения.
"""


# =========================================================
# GEMINI
# =========================================================

async def ask_gemini(
    instruction,
    material
):

    if not gemini_client:

        raise RuntimeError(
            "Gemini недоступен."
        )


    prompt = (

        SYSTEM_PROMPT

        + "\n\n"

        + instruction

        + "\n\n"

        + "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"

        + material
    )


    def generate():

        response = (
            gemini_client
            .models
            .generate_content(

                model="gemini-2.5-flash-lite",

                contents=prompt
            )
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
# OPENROUTER FREE
# =========================================================

async def ask_openrouter(
    instruction,
    material
):

    if not openrouter_client:

        raise RuntimeError(
            "OpenRouter недоступен."
        )


    user_prompt = (

        instruction

        + "\n\n"

        + "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"

        + material
    )


    def generate():

        response = (
            openrouter_client
            .chat
            .completions
            .create(

                model="openrouter/free",

                messages=[

                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },

                    {
                        "role": "user",
                        "content": user_prompt
                    }

                ],

                temperature=0.2
            )
        )


        return (
            response
            .choices[0]
            .message
            .content
        )


    result = await asyncio.to_thread(
        generate
    )


    if not result:

        raise RuntimeError(
            "OpenRouter вернул пустой ответ."
        )


    return result.strip()


# =========================================================
# AI FALLBACK
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
                "🤖 Используем Gemini...",
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
    # 2. OPENROUTER
    # =====================================================

    if openrouter_client:

        try:

            print(
                "🤖 Используем OpenRouter Free...",
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
    # ВСЕ AI НЕДОСТУПНЫ
    # =====================================================

    print(
        "❌ Все AI-провайдеры недоступны",
        flush=True
    )

    for error in errors:

        print(
            error,
            flush=True
        )


    raise RuntimeError(
        "Все бесплатные AI-сервисы "
        "временно недоступны."
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

            "❗ Материал не найден.\n\n"
            "Сначала отправьте текст."
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
            f"🧠 Новый запрос: {action}",
            flush=True
        )

        print(
            f"👤 User: {user_id}",
            flush=True
        )

        print(
            f"📄 Размер материала: "
            f"{len(material)} символов",
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
        # ОТПРАВКА ЧАСТЯМИ
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
            "✅ Результат отправлен",
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

            "Бесплатные AI-сервисы сейчас "
            "недоступны или достигли лимита.\n\n"

            "Попробуйте ещё раз немного позже.",

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
        "🧠 SMARTNOTE AI",
        flush=True
    )

    print(
        "📱 TEXT VERSION",
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
        "OpenRouter:",
        "ON" if openrouter_client else "OFF",
        flush=True
    )

    print(
        "====================================",
        flush=True
    )


    application = (
        Application
        .builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )


    # =====================================================
    # START
    # =====================================================

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )


    # =====================================================
    # ТОЛЬКО ТЕКСТ
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
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
