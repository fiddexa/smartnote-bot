import os
import asyncio
import traceback
import re

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
    print("❌ GEMINI INITIALIZATION ERROR", flush=True)
    print("TYPE:", type(error).__name__, flush=True)
    print("ERROR:", str(error), flush=True)
    print("====================================", flush=True)

    raise


# =========================================================
# ХРАНИЛИЩЕ МАТЕРИАЛОВ
# =========================================================

materials = {}


# =========================================================
# НАЗВАНИЯ ДЕЙСТВИЙ
# =========================================================

ACTION_TITLES = {

    "referat":
        "📚 РЕФЕРАТ",

    "conspect":
        "📝 КОНСПЕКТ",

    "summary":
        "⚡ КРАТКАЯ ВЫЖИМКА",

    "theses":
        "🎯 ГЛАВНЫЕ ТЕЗИСЫ",

    "questions":
        "❓ ВОПРОСЫ И ОТВЕТЫ",

    "simple":
        "🧠 ПРОСТЫМИ СЛОВАМИ",
}


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

        "📖 Отправьте учебный материал "
        "<b>текстом</b>.\n\n"

        "Я могу превратить его в:\n\n"

        "📚 Реферат\n"
        "📝 Конспект\n"
        "⚡ Краткую выжимку\n"
        "🎯 Главные тезисы\n"
        "❓ Вопросы и ответы\n"
        "🧠 Объяснение простыми словами\n\n"

        "🎤 Голосовые сообщения появятся "
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

        if update.message:

            await update.message.reply_text(
                "❌ Не удалось получить материал."
            )


# =========================================================
# ИНСТРУКЦИИ ДЛЯ РЕЖИМОВ
# =========================================================

PROMPTS = {

    "referat": """
Создай качественный учебный реферат.

Структура:

Название

1. Введение
2. Основная часть
3. Основные факты и идеи
4. Заключение

Пиши связно и понятно.

Не добавляй вступление от имени ассистента.

Не пиши фразы вроде:
"Привет!"
"Я SmartNote AI..."
"Я подготовил..."
"Если у тебя появятся вопросы..."

Сразу начинай с содержания реферата.

Используй только информацию из материала пользователя.

Не выдумывай факты.
""",

    "conspect": """
Создай подробный и удобный учебный конспект.

Структура:

Название темы

1. Основной раздел
2. Подразделы
3. Важные факты
4. Определения
5. Причинно-следственные связи
6. Выводы

Используй короткие абзацы и списки.

Выделяй действительно важные сведения.

Не добавляй вступление от имени ассистента.

Не пиши заключительные фразы вроде:
"Надеюсь, это поможет..."
"Если у тебя появятся вопросы..."
"Обращайся..."

Сразу начинай с конспекта.

Не выдумывай информацию.
""",

    "summary": """
Сделай краткую и максимально полезную
выжимку материала.

Оставь только самое важное.

Удали повторы и второстепенные детали.

Сохрани основной смысл.

Формат:

⚡ Главное

• пункт
• пункт
• пункт
• пункт

Не добавляй вступление или заключение от себя.

Не выдумывай факты.
""",

    "theses": """
Выдели главные тезисы материала.

Сделай от 5 до 20 тезисов.

Каждый тезис должен быть:
• коротким;
• конкретным;
• информативным.

Каждый пункт должен передавать
одну важную мысль.

Не добавляй информацию,
которой нет в исходном материале.
""",

    "questions": """
Создай вопросы для проверки знаний
по предоставленному материалу.

Сделай вопросы разного уровня сложности.

Формат:

❓ Вопрос 1
Ответ: ...

❓ Вопрос 2
Ответ: ...

После основных вопросов
добавь раздел:

🎯 Важные вопросы для экзамена

Сделай 5 наиболее важных вопросов
с ответами.

Все ответы должны основываться
на предоставленном материале.

Не выдумывай информацию.
""",

    "simple": """
Объясни материал простыми словами.

Представь, что человек
впервые изучает эту тему.

Сложные термины объясняй
простым языком.

Используй простые примеры,
только если они помогают
понять информацию.

Структура:

🧠 Главное

Затем объяснение по пунктам.

В конце:

📌 Коротко

и несколько предложений
с самым главным.

Не выдумывай факты.
""",
}


# =========================================================
# СИСТЕМНАЯ ИНСТРУКЦИЯ
# =========================================================

SYSTEM_PROMPT = """
Ты — учебный AI-ассистент SmartNote AI.

Твоя задача — превращать предоставленный
пользователем учебный материал
в полезный учебный контент.

ОСНОВНЫЕ ПРАВИЛА:

1. Работай прежде всего с материалом пользователя.

2. Не выдумывай факты.

3. Не добавляй неподтвержденную информацию
   только для того, чтобы сделать ответ длиннее.

4. Если материала недостаточно,
   честно укажи это.

5. Не меняй смысл исходного материала.

6. Не добавляй личные комментарии.

7. Не обращайся к пользователю
   в начале или в конце ответа.

8. Не пиши:
   "Привет!"
   "Я SmartNote AI..."
   "Я подготовил..."
   "Надеюсь, это поможет..."
   "Если у тебя есть вопросы..."
   "Обращайся..."

9. Сразу начинай с результата.

10. Отвечай на русском языке.

11. Используй понятную структуру.

12. Не используй Markdown-заголовки
    с символами #.

13. Не используй Markdown жирный текст
    вида **текст**.

14. Не используй Markdown-курсив
    вида *текст*.

15. Используй обычные заголовки,
    списки и пустые строки.

16. Результат должен быть удобен
    для чтения непосредственно
    в Telegram.
"""


# =========================================================
# ОЧИСТКА ОТ MARKDOWN
# =========================================================

def clean_ai_text(text):

    if not text:
        return ""

    # Убираем Markdown-заголовки
    text = re.sub(
        r"^\s*#{1,6}\s*",
        "",
        text,
        flags=re.MULTILINE
    )

    # Убираем **жирный текст**
    text = text.replace("**", "")

    # Убираем __жирный текст__
    text = text.replace("__", "")

    # Убираем одиночные Markdown *
    text = re.sub(
        r"(?<!\w)\*(?!\s)",
        "",
        text
    )

    # Убираем лишние горизонтальные линии
    text = re.sub(
        r"^\s*[-_]{3,}\s*$",
        "",
        text,
        flags=re.MULTILINE
    )

    # Убираем повторяющиеся пустые строки
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


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

            model="gemini-3.5-flash-lite",

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


    return clean_ai_text(
        result
    )


# =========================================================
# ОТПРАВКА ДЛИННОГО ТЕКСТА
# =========================================================

async def send_long_message(
    message,
    text
):

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

            "Старый материал удалён.\n\n"

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

            "Сначала отправьте новый текст."
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


        # =================================================
        # ЗАГОЛОВОК
        # =================================================

        title = ACTION_TITLES.get(
            action,
            "🧠 РЕЗУЛЬТАТ"
        )


        await query.message.reply_text(
            title
        )


        # =================================================
        # РЕЗУЛЬТАТ
        # =================================================

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


        # =================================================
        # МЕНЮ ПОСЛЕ РЕЗУЛЬТАТА
        # =================================================

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
        "🤖 Gemini",
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
    # START
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
