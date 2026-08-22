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


# =========================================================
# НАСТРОЙКИ
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")


# =========================================================
# ПРОВЕРКА НАСТРОЕК
# =========================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "TELEGRAM_TOKEN не найден в Render Environment Variables"
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY не найден в Render Environment Variables"
    )

if not RENDER_EXTERNAL_URL:
    raise RuntimeError(
        "RENDER_EXTERNAL_URL не найден в Render Environment Variables"
    )


# =========================================================
# GEMINI
# =========================================================

try:

    gemini_client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    print(
        "✅ Gemini API подключен",
        flush=True
    )

except Exception as error:

    print("====================================", flush=True)
    print("❌ GEMINI ERROR", flush=True)
    print("TYPE:", type(error).__name__, flush=True)
    print("ERROR:", str(error), flush=True)
    print("REPR:", repr(error), flush=True)
    print("====================================", flush=True)

    errors.append(
        "Gemini: "
        + repr(error)
    )

    raise


# =========================================================
# ХРАНИЛИЩЕ МАТЕРИАЛОВ
# =========================================================

materials = {}


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

        [
            InlineKeyboardButton(
                "🔄 Новый материал",
                callback_data="new_material"
            ),
        ],

    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🧠 <b>SmartNote AI</b>\n\n"

        "Ваш интеллектуальный учебный помощник.\n\n"

        "📖 Отправьте мне учебный материал "
        "<b>текстом</b>.\n\n"

        "Я могу превратить его в:\n\n"

        "📚 Реферат\n"
        "📝 Конспект\n"
        "⚡ Краткую выжимку\n"
        "🎯 Главные тезисы\n"
        "❓ Вопросы и ответы\n"
        "🧠 Объяснение простыми словами\n\n"

        "🎤 Голосовые сообщения будут добавлены "
        "в следующей версии."
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


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

        text = update.message.text

        if not text:
            return

        text = text.strip()

        if not text:
            return

        user_id = update.effective_user.id

        materials[user_id] = text

        print(
            "====================================",
            flush=True
        )

        print(
            "📥 Получен новый материал",
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

        await update.message.reply_text(
            "❌ Не удалось получить материал."
        )


# =========================================================
# ИНСТРУКЦИИ
# =========================================================

PROMPTS = {

    "referat": """
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
на материале пользователя.

Не выдумывай факты.
""",

    "conspect": """
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

Не выдумывай информацию.
""",

    "summary": """
Сделай краткую и полезную
выжимку материала.

Оставь только самую важную
информацию.

Удали повторы
и второстепенные детали.

Сохрани основной смысл.

Не выдумывай факты.
""",

    "theses": """
Выдели главные тезисы
из предоставленного материала.

Сделай от 5 до 20 тезисов.

Каждый тезис должен быть:

- коротким;
- конкретным;
- информативным.

Не добавляй выдуманную информацию.
""",

    "questions": """
Создай вопросы для проверки знаний
по предоставленному материалу.

Сделай вопросы разного уровня сложности.

После каждого вопроса
укажи правильный ответ.

В конце добавь 5 наиболее важных
вопросов для подготовки к экзамену.

Ответы должны основываться
на предоставленном материале.
""",

    "simple": """
Объясни предоставленный материал
простыми словами.

Представь, что человек
впервые изучает эту тему.

Сложные термины объясняй
понятным языком.

Если это помогает пониманию,
используй простые примеры.

Не искажай исходную информацию.
"""
}


# =========================================================
# СИСТЕМНАЯ ИНСТРУКЦИЯ
# =========================================================

SYSTEM_PROMPT = """
Ты — SmartNote AI,
интеллектуальный учебный ассистент.

Помогай пользователю изучать
предоставленный им материал.

Работай прежде всего
с информацией пользователя.

Не выдумывай факты.

Если информации недостаточно,
не придумывай отсутствующие сведения.

Отвечай на русском языке.

Используй понятную структуру.

Ответ должен быть полезным
для обучения.
"""


# =========================================================
# GEMINI
# =========================================================

async def ask_gemini(
    instruction,
    material
):

    prompt = (

        SYSTEM_PROMPT

        + "\n\n"

        + instruction

        + "\n\n"

        + "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"

        + material
    )


    def generate():

        response = gemini_client.models.generate_content(

            model="gemini-2.5-flash-lite",

            contents=prompt
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
# ОТПРАВКА ДЛИННОГО ТЕКСТА
# =========================================================

async def send_long_message(
    message,
    text
):

    # Telegram позволяет сообщения
    # примерно до 4096 символов.
    # Оставляем запас.

    chunk_size = 3800


    for start_index in range(
        0,
        len(text),
        chunk_size
    ):

        chunk = text[
            start_index:
            start_index + chunk_size
        ]

        await message.reply_text(
            chunk
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


    # =====================================================
    # НОВЫЙ МАТЕРИАЛ
    # =====================================================

    if query.data == "new_material":

        materials.pop(
            user_id,
            None
        )

        await query.message.reply_text(

            "🔄 <b>Готово.</b>\n\n"

            "Отправьте новый учебный материал "
            "<b>текстом</b>.",

            parse_mode="HTML"
        )

        return


    # =====================================================
    # ПОЛУЧАЕМ МАТЕРИАЛ
    # =====================================================

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

    instruction = PROMPTS.get(
        action
    )


    if not instruction:
        return


    # =====================================================
    # СООБЩЕНИЕ О ПРОЦЕССЕ
    # =====================================================

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
            "🧠 AI ЗАПРОС",
            flush=True
        )

        print(
            f"👤 User ID: {user_id}",
            flush=True
        )

        print(
            f"🎯 Действие: {action}",
            flush=True
        )

        print(
            f"📄 Размер материала: "
            f"{len(material)} символов",
            flush=True
        )


        result = await ask_gemini(

            instruction,

            material
        )


        if not result:

            raise RuntimeError(
                "Пустой результат от Gemini"
            )


        await send_long_message(

            query.message,

            result
        )


        print(
            "✅ Результат успешно отправлен",
            flush=True
        )

        print(
            "====================================",
            flush=True
        )


        # Кнопки после результата

        await query.message.reply_text(

            "Что хотите сделать дальше?",

            reply_markup=get_keyboard()
        )


    except Exception as error:

        print(
            "❌ GEMINI ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()


        await query.message.reply_text(

            "❌ <b>Не удалось обработать материал.</b>\n\n"

            "Возможно, бесплатный лимит Gemini "
            "временно достигнут.\n\n"

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
        "🤖 Gemini only",
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
        "====================================",
        flush=True
    )


    application = (

        Application
        .builder()
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
    # ТЕКСТ
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
