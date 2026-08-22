import os
import asyncio
import traceback
import re
import io

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
from google.genai import types


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
# ПАКЕТЫ ФОТО
# =========================================================

photo_batches = {}

# Задачи ожидания завершения загрузки фотографий
photo_batch_tasks = {}

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
        "<b>текстом, фотографией, PDF или DOCX</b>.\n\n"

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
# ПОЛУЧЕНИЕ PDF
# =========================================================
# =========================================================
# ПОЛУЧЕНИЕ ДОКУМЕНТА
# PDF / DOCX
# =========================================================

async def receive_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    try:
        if not update.message:
            return

        document = update.message.document

        if not document:
            return

        file_name = document.file_name or ""

        print("====================================", flush=True)
        print("📎 ПОЛУЧЕН ДОКУМЕНТ", flush=True)
        print(f"📄 Имя: {file_name}", flush=True)
        print(f"📦 MIME: {document.mime_type}", flush=True)
        print(f"📏 Размер: {document.file_size}", flush=True)
        print(f"👤 User ID: {update.effective_user.id}", flush=True)
        print("====================================", flush=True)

        if file_name.lower().endswith(".pdf"):
            await receive_pdf(update, context)
            return

        if file_name.lower().endswith(".docx"):
            await receive_docx(update, context)
            return

        await update.message.reply_text(
            "❌ <b>Этот формат пока не поддерживается.</b>\n\n"
            "Поддерживаемые форматы:\n"
            "📄 PDF\n"
            "📝 DOCX",
            parse_mode="HTML"
        )

    except Exception as error:
        print(
            "❌ DOCUMENT ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()

        if update.message:
            await update.message.reply_text(
                "❌ <b>Не удалось получить документ.</b>\n\n"
                "Попробуйте отправить файл ещё раз.",
                parse_mode="HTML"
            )

async def receive_pdf(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        if not update.message:
            return

        document = update.message.document

        if not document:
            return

        file_name = document.file_name or "document.pdf"

        if not file_name.lower().endswith(".pdf"):

            await update.message.reply_text(
                "❌ Поддерживается только PDF."
            )

            return

        if document.file_size and document.file_size > 20 * 1024 * 1024:

            await update.message.reply_text(
                "❌ PDF слишком большой.\n\n"
                "Максимальный размер — 20 МБ."
            )

            return

        await update.message.reply_text(
            "📄 <b>Получил PDF.</b>\n\n"
            "⏳ Извлекаю текст из документа...",
            parse_mode="HTML"
        )

        print("====================================", flush=True)
        print("📄 ПОЛУЧЕН PDF", flush=True)
        print(f"📎 Файл: {file_name}", flush=True)
        print(
            f"👤 User ID: {update.effective_user.id}",
            flush=True
        )
        print("====================================", flush=True)

        telegram_file = await document.get_file()

        file_path = (
            f"/tmp/"
            f"{update.effective_user.id}_"
            f"{file_name}"
        )

        await telegram_file.download_to_drive(
            file_path
        )

        from pypdf import PdfReader

        reader = PdfReader(file_path)

        pages_text = []

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                pages_text.append(
                    page_text.strip()
                )

        material = "\n\n".join(
            pages_text
        ).strip()

        try:
            os.remove(file_path)
        except Exception:
            pass

        if not material:

            await update.message.reply_text(
                "⚠️ <b>Не удалось извлечь текст из PDF.</b>\n\n"
                "Возможно, PDF является сканом или "
                "содержит только изображения.",
                parse_mode="HTML"
            )

            return

        user_id = update.effective_user.id

        materials[user_id] = material

        print("✅ Текст PDF извлечён", flush=True)
        print(
            f"📄 Страниц: {len(reader.pages)}",
            flush=True
        )
        print(
            f"📝 Размер текста: {len(material)} символов",
            flush=True
        )
        print("====================================", flush=True)

        await update.message.reply_text(
            "✅ <b>PDF успешно обработан.</b>\n\n"
            f"📄 Файл: {file_name}\n"
            f"📑 Страниц: {len(reader.pages)}\n"
            f"📝 Текста извлечено: {len(material)} символов\n\n"
            "Теперь выберите, что нужно сделать:",
            reply_markup=get_keyboard(),
            parse_mode="HTML"
        )

    except Exception as error:

        print(
            "❌ PDF ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()

        if update.message:

            await update.message.reply_text(
                "❌ <b>Не удалось обработать PDF.</b>\n\n"
                "Попробуйте другой файл.",
                parse_mode="HTML"
            )

# =========================================================
# ПОЛУЧЕНИЕ ФОТО
# =========================================================

async def receive_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        if not update.message:
            return

        if not update.message.photo:
            return

        user_id = update.effective_user.id

        # =====================================================
        # ОПРЕДЕЛЯЕМ ПАКЕТ
        # =====================================================
        #
        # Если пользователь отправил несколько фото
        # одним альбомом Telegram — у них будет одинаковый
        # media_group_id.
        #
        # Если фото отправлено отдельно — используем user_id.
        #

        media_group_id = update.message.media_group_id

        if media_group_id:

            batch_id = f"{user_id}_{media_group_id}"

        else:

            batch_id = str(user_id)

        # =====================================================
        # БЕРЁМ ФОТО МАКСИМАЛЬНОГО КАЧЕСТВА
        # =====================================================

        photo = update.message.photo[-1]

        print(
            "====================================",
            flush=True
        )

        print(
            "📸 ПОЛУЧЕНО ФОТО",
            flush=True
        )

        print(
            f"👤 User ID: {user_id}",
            flush=True
        )

        print(
            f"🆔 Message ID: "
            f"{update.message.message_id}",
            flush=True
        )

        print(
            f"🗂 Media Group ID: "
            f"{media_group_id}",
            flush=True
        )

        print(
            f"📐 Разрешение: "
            f"{photo.width}x{photo.height}",
            flush=True
        )

        print(
            f"📦 Batch ID: {batch_id}",
            flush=True
        )

        print(
            "====================================",
            flush=True
        )

        # =====================================================
        # ПОЛУЧАЕМ ФАЙЛ TELEGRAM
        # =====================================================

        telegram_file = await photo.get_file()

        image_bytes = await telegram_file.download_as_bytearray()

        # =====================================================
        # ОПТИМИЗАЦИЯ ИЗОБРАЖЕНИЯ
        # =====================================================

        def optimize_image():

            try:

                from PIL import Image

                image = Image.open(
                    io.BytesIO(
                        bytes(image_bytes)
                    )
                )

                # Исправляем ориентацию фотографии
                try:

                    from PIL import ImageOps

                    image = ImageOps.exif_transpose(
                        image
                    )

                except Exception:
                    pass

                # Переводим в RGB
                if image.mode != "RGB":

                    image = image.convert(
                        "RGB"
                    )

                # =================================================
                # Максимальный размер одной стороны
                # =================================================

                max_dimension = 2200

                if (
                    image.width > max_dimension
                    or
                    image.height > max_dimension
                ):

                    image.thumbnail(
                        (
                            max_dimension,
                            max_dimension
                        ),
                        Image.Resampling.LANCZOS
                    )

                # =================================================
                # Сохраняем JPEG
                # =================================================

                output = io.BytesIO()

                image.save(
                    output,
                    format="JPEG",
                    quality=85,
                    optimize=True
                )

                return output.getvalue()

            except Exception as error:

                print(
                    "⚠️ IMAGE OPTIMIZATION ERROR:",
                    repr(error),
                    flush=True
                )

                # Если оптимизация не удалась,
                # возвращаем оригинал
                return bytes(image_bytes)

        optimized_image = await asyncio.to_thread(
            optimize_image
        )

        print(
            f"📦 Исходный размер: "
            f"{len(image_bytes)} байт",
            flush=True
        )

        print(
            f"📦 Оптимизированный размер: "
            f"{len(optimized_image)} байт",
            flush=True
        )

        # =====================================================
        # СОЗДАЁМ ПАКЕТ
        # =====================================================

        if batch_id not in photo_batches:

            photo_batches[batch_id] = {

                "user_id": user_id,

                "images": [],

                "message": update.message,

                "media_group_id": media_group_id,

                "started": asyncio.get_event_loop().time(),

            }

        # =====================================================
        # ДОБАВЛЯЕМ ФОТО
        # =====================================================

        photo_batches[batch_id]["images"].append(
            optimized_image
        )

        image_count = len(
            photo_batches[batch_id]["images"]
        )

        print(
            f"📚 Фото в текущем пакете: {image_count}",
            flush=True
        )

        # =====================================================
        # ОГРАНИЧЕНИЕ
        # =====================================================

        MAX_PHOTOS = 10

        if image_count > MAX_PHOTOS:

            await update.message.reply_text(

                f"❌ Слишком много фотографий.\n\n"
                f"Максимум за один материал: "
                f"{MAX_PHOTOS} фотографий.",

                parse_mode="HTML"
            )

            photo_batches.pop(
                batch_id,
                None
            )

            old_task = photo_batch_tasks.pop(
                batch_id,
                None
            )

            if old_task:
                old_task.cancel()

            return

        # =====================================================
        # ОТМЕНЯЕМ СТАРЫЙ ТАЙМЕР
        # =====================================================

        old_task = photo_batch_tasks.get(
            batch_id
        )

        if old_task:

            old_task.cancel()

        # =====================================================
        # НОВЫЙ ТАЙМЕР
        # =====================================================
        #
        # Ждём 10 секунд после последней фотографии.
        #
        # Если приходит следующая фотография —
        # предыдущий таймер отменяется и запускается заново.
        #

        async def wait_and_process():

            try:

                print(
                    f"⏳ Ждём завершения пакета "
                    f"{batch_id}",
                    flush=True
                )

                await asyncio.sleep(10)

                await process_photo_batch(
                    batch_id
                )

            except asyncio.CancelledError:

                print(
                    f"🔄 Таймер пакета {batch_id} "
                    f"перезапущен",
                    flush=True
                )

            except Exception as error:

                print(
                    "❌ PHOTO BATCH ERROR:",
                    repr(error),
                    flush=True
                )

                traceback.print_exc()

        photo_batch_tasks[batch_id] = asyncio.create_task(
            wait_and_process()
        )

    except Exception as error:

        print(
            "❌ PHOTO RECEIVE ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()

        if update.message:

            await update.message.reply_text(

                "❌ <b>Не удалось получить фотографию.</b>\n\n"
                "Попробуйте отправить её ещё раз.",

                parse_mode="HTML"
        )
# =========================================================
# ОБРАБОТКА ВСЕХ ФОТО ОДНИМ ЗАПРОСОМ
# ЧЕРЕЗ GEMINI FILES API
# =========================================================

async def process_photo_batch(
    batch_id
):

    batch = photo_batches.get(
        batch_id
    )

    if not batch:
        print(
            f"⚠️ Пакет {batch_id} не найден",
            flush=True
        )
        return

    user_id = batch["user_id"]
    images = batch["images"]
    message = batch["message"]

    image_count = len(images)

    print(
        "====================================",
        flush=True
    )

    print(
        "🧠 НАЧИНАЮ ОБРАБОТКУ ПАКЕТА",
        flush=True
    )

    print(
        f"👤 User ID: {user_id}",
        flush=True
    )

    print(
        f"📚 ВСЕГО ФОТО: {image_count}",
        flush=True
    )

    print(
        f"🆔 Batch ID: {batch_id}",
        flush=True
    )

    print(
        "====================================",
        flush=True
    )

    try:

        # =====================================================
        # ПРОВЕРКА
        # =====================================================

        if not images:

            raise RuntimeError(
                "Пакет фотографий пуст."
            )

        # =====================================================
        # СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ
        # =====================================================

        if image_count == 1:

            await message.reply_text(

                "📸 <b>Фото получено.</b>\n\n"

                "🧠 Распознаю текст и анализирую страницу...\n\n"

                "⏳ Пожалуйста, подождите.",

                parse_mode="HTML"
            )

        else:

            await message.reply_text(

                f"📚 <b>Получено фотографий: "
                f"{image_count}</b>\n\n"

                "🧠 Обрабатываю все страницы "
                "как единый материал...\n\n"

                "⏳ Пожалуйста, подождите.",

                parse_mode="HTML"
            )

        # =====================================================
        # GEMINI FILES API
        # =====================================================

        def upload_and_recognize():

            uploaded_files = []

            # =================================================
            # ЗАГРУЖАЕМ КАЖДОЕ ФОТО В GEMINI
            # =================================================

            for index, image_bytes in enumerate(images):

                print(
                    "------------------------------------",
                    flush=True
                )

                print(
                    f"📤 Загружаю фото "
                    f"{index + 1}/{image_count}",
                    flush=True
                )

                print(
                    f"📦 Размер: "
                    f"{len(image_bytes)} байт",
                    flush=True
                )

                try:

                    uploaded_file = (
                        gemini_client.files.upload(
                            file=io.BytesIO(
                                image_bytes
                            ),
                            config={
                                "mime_type": "image/jpeg"
                            }
                        )
                    )

                    if not uploaded_file:

                        raise RuntimeError(
                            f"Gemini не вернул файл "
                            f"{index + 1}"
                        )

                    uploaded_files.append(
                        uploaded_file
                    )

                    print(
                        f"✅ Фото "
                        f"{index + 1}/{image_count} "
                        f"загружено",
                        flush=True
                    )

                    print(
                        f"🆔 Gemini File: "
                        f"{uploaded_file.name}",
                        flush=True
                    )

                except Exception as upload_error:

                    print(
                        f"❌ ОШИБКА ЗАГРУЗКИ "
                        f"ФОТО {index + 1}",
                        flush=True
                    )

                    print(
                        "TYPE:",
                        type(upload_error).__name__,
                        flush=True
                    )

                    print(
                        "ERROR:",
                        repr(upload_error),
                        flush=True
                    )

                    raise

            # =================================================
            # ЕДИНАЯ ИНСТРУКЦИЯ
            # =================================================

            prompt = f"""
Ты работаешь как высокоточный OCR-модуль
SmartNote AI.

Перед тобой {image_count} фотографий.

КРИТИЧЕСКИ ВАЖНО:

Все фотографии являются страницами ОДНОГО
учебного материала.

Обработай ВСЕ {image_count} фотографий
В ОДНОМ ЗАПРОСЕ.

Порядок фотографий соответствует порядку страниц:

ФОТО 1 → первая страница
ФОТО 2 → вторая страница
ФОТО 3 → третья страница
и так далее.

ТВОЯ ЗАДАЧА:

1. Распознай текст со ВСЕХ фотографий.

2. Объедини весь распознанный текст
   в ОДИН единый материал.

3. Строго соблюдай порядок страниц.

4. Если предложение начинается на одной странице
   и продолжается на следующей,
   объедини его правильно.

5. Если абзац продолжается на следующей странице,
   не создавай искусственный новый смысловой блок.

6. Сохрани:
   - заголовки;
   - подзаголовки;
   - абзацы;
   - списки;
   - определения;
   - даты;
   - цифры;
   - названия;
   - формулы;
   - важные обозначения.

7. Если присутствуют таблицы,
   передай их содержание максимально точно
   в текстовом виде.

8. Если присутствуют несколько колонок,
   определи правильный порядок чтения.

9. Если часть текста невозможно прочитать,
   НЕ ПРИДУМЫВАЙ её.

10. Не добавляй информацию от себя.

11. Не делай реферат.

12. Не делай конспект.

13. Не делай выжимку.

14. Не делай анализ.

15. Не сокращай материал.

16. Не повторяй текст страниц.

17. Не создавай отдельный ответ
    для каждой фотографии.

18. Верни ОДИН единый текст,
    содержащий материал ВСЕХ страниц.

ГЛАВНАЯ ЦЕЛЬ:

Максимально точно распознать текст
со всех {image_count} фотографий
и объединить его в один последовательный
учебный материал.

Верни только единый распознанный текст.
"""

            # =================================================
            # ФОРМИРУЕМ ОДИН ЗАПРОС
            # =================================================

            contents = []

            # Сначала все страницы
            for uploaded_file in uploaded_files:

                contents.append(
                    uploaded_file
                )

            # Затем инструкция
            contents.append(
                prompt
            )

            print(
                "====================================",
                flush=True
            )

            print(
                "🚀 ОТПРАВЛЯЮ ВСЕ ФОТО GEMINI "
                "ОДНИМ ЗАПРОСОМ",
                flush=True
            )

            print(
                f"📚 Страниц: {image_count}",
                flush=True
            )

            print(
                "====================================",
                flush=True
            )

            # =================================================
            # ОДИН GEMINI REQUEST
            # =================================================

            response = gemini_client.models.generate_content(

                model="gemini-3.5-flash-lite",

                contents=contents,

                config=types.GenerateContentConfig(

                    system_instruction=SYSTEM_PROMPT

                )

            )

            if not response:

                raise RuntimeError(
                    "Gemini вернул пустой response."
                )

            if not response.text:

                raise RuntimeError(
                    "Gemini вернул пустой текст."
                )

            print(
                "✅ Gemini вернул единый результат",
                flush=True
            )

            return response.text

        # =====================================================
        # ЗАПУСК В ОТДЕЛЬНОМ ПОТОКЕ
        # =====================================================

        material = await asyncio.to_thread(
            upload_and_recognize
        )

        # =====================================================
        # ПРОВЕРКА
        # =====================================================

        if not material:

            raise RuntimeError(
                "Gemini не вернул распознанный материал."
            )

        # =====================================================
        # ОЧИСТКА
        # =====================================================

        material = clean_ai_text(
            material
        )

        if not material:

            raise RuntimeError(
                "После очистки материал оказался пустым."
            )

        # =====================================================
        # СОХРАНЯЕМ ЕДИНЫЙ МАТЕРИАЛ
        # =====================================================

        materials[user_id] = material

        print(
            "====================================",
            flush=True
        )

        print(
            "✅ ВСЕ ФОТО ОБРАБОТАНЫ ОДНИМ ЗАПРОСОМ",
            flush=True
        )

        print(
            f"📚 Страниц обработано: "
            f"{image_count}",
            flush=True
        )

        print(
            f"📝 Размер единого материала: "
            f"{len(material)} символов",
            flush=True
        )

        print(
            "====================================",
            flush=True
        )

        # =====================================================
        # ОТВЕТ ПОЛЬЗОВАТЕЛЮ
        # =====================================================

        if image_count == 1:

            result_message = (

                "✅ <b>Страница распознана.</b>\n\n"

                f"📝 Текста получено: "
                f"{len(material)} символов\n\n"

                "Теперь выберите, что нужно сделать:"

            )

        else:

            result_message = (

                "✅ <b>Материал успешно распознан.</b>\n\n"

                f"📚 Страниц обработано: "
                f"{image_count}\n"

                f"📝 Текста получено: "
                f"{len(material)} символов\n\n"

                "Все фотографии объединены "
                "в один учебный материал.\n\n"

                "Теперь выберите, что нужно сделать:"

            )

        await message.reply_text(

            result_message,

            reply_markup=get_keyboard(),

            parse_mode="HTML"

        )

    except Exception as error:

        # =====================================================
        # ПОДРОБНЫЙ ЛОГ ОШИБКИ
        # =====================================================

        print(
            "====================================",
            flush=True
        )

        print(
            "❌ PHOTO OCR ERROR",
            flush=True
        )

        print(
            f"👤 User ID: {user_id}",
            flush=True
        )

        print(
            f"📚 Фото в пакете: {image_count}",
            flush=True
        )

        print(
            "TYPE:",
            type(error).__name__,
            flush=True
        )

        print(
            "ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()

        print(
            "====================================",
            flush=True
        )

        await message.reply_text(

            "❌ <b>Не удалось обработать "
            "фотографии.</b>\n\n"

            f"📚 Получено фотографий: "
            f"{image_count}\n\n"

            "Попробуйте отправить страницы "
            "ещё раз.",

            parse_mode="HTML"
        )

    finally:

        # =====================================================
        # УДАЛЯЕМ ПАКЕТ
        # =====================================================

        photo_batches.pop(
            batch_id,
            None
        )

        photo_batch_tasks.pop(
            batch_id,
            None
        )

        print(
            f"🗑 Пакет {batch_id} очищен",
            flush=True
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
# ПОЛУЧЕНИЕ DOCX
# =========================================================
async def receive_docx(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        if not update.message:
            return

        document = update.message.document

        if not document:
            return

        file_name = document.file_name or "document.docx"

        if not file_name.lower().endswith(".docx"):

            await update.message.reply_text(
                "❌ Поддерживается только DOCX."
            )

            return

        if document.file_size and document.file_size > 20 * 1024 * 1024:

            await update.message.reply_text(
                "❌ DOCX слишком большой.\n\n"
                "Максимальный размер — 20 МБ."
            )

            return

        await update.message.reply_text(
            "📄 <b>Получил DOCX.</b>\n\n"
            "⏳ Извлекаю текст из документа...",
            parse_mode="HTML"
        )

        print("====================================", flush=True)
        print("📄 ПОЛУЧЕН DOCX", flush=True)
        print(f"📎 Файл: {file_name}", flush=True)
        print(
            f"👤 User ID: {update.effective_user.id}",
            flush=True
        )
        print("====================================", flush=True)

        telegram_file = await document.get_file()

        file_path = (
            f"/tmp/"
            f"{update.effective_user.id}_"
            f"{file_name}"
        )

        await telegram_file.download_to_drive(
            file_path
        )

        from docx import Document

        doc = Document(file_path)

        paragraphs = []

        for paragraph in doc.paragraphs:

            text = paragraph.text.strip()

            if text:
                paragraphs.append(text)

        material = "\n\n".join(
            paragraphs
        ).strip()

        try:
            os.remove(file_path)
        except Exception:
            pass

        if not material:

            await update.message.reply_text(
                "⚠️ <b>DOCX не содержит доступного текста.</b>\n\n"
                "Попробуйте другой документ.",
                parse_mode="HTML"
            )

            return

        user_id = update.effective_user.id

        materials[user_id] = material

        print("✅ Текст DOCX извлечён", flush=True)
        print(
            f"📝 Размер текста: {len(material)} символов",
            flush=True
        )
        print("====================================", flush=True)

        await update.message.reply_text(
            "✅ <b>DOCX успешно обработан.</b>\n\n"
            f"📄 Файл: {file_name}\n"
            f"📝 Текста извлечено: {len(material)} символов\n\n"
            "Теперь выберите, что нужно сделать:",
            reply_markup=get_keyboard(),
            parse_mode="HTML"
        )

    except Exception as error:

        print(
            "❌ DOCX ERROR:",
            repr(error),
            flush=True
        )

        traceback.print_exc()

        if update.message:

            await update.message.reply_text(
                "❌ <b>Не удалось обработать DOCX.</b>\n\n"
                "Попробуйте другой файл.",
                parse_mode="HTML"
            )

# =========================================================
# ИНСТРУКЦИИ ДЛЯ РЕЖИМОВ
# =========================================================

PROMPTS = {

    "referat": """
Создай полноценный учебный реферат на основе
предоставленного пользователем материала.

Самостоятельно определи логичную структуру текста.
Не используй шаблонные разделы, если информации
для них недостаточно.

Структура может включать:

• название темы;
• введение;
• основные разделы и подразделы;
• важные факты;
• заключение.

Требования:

- Пиши связно и естественно.
- Не повторяй одну и ту же информацию.
- Используй только информацию из материала пользователя.
- Не выдумывай факты.
- Не добавляй сведения только ради увеличения объёма.
- Если материала мало, сделай короткий, но качественный реферат.
- Сохраняй смысл исходного материала.
- Используй понятный учебный стиль.
- Не пиши фразы вроде «материал пользователя недостаточен»,
  если можно просто не создавать соответствующий раздел.

В конце сделай краткий вывод по теме.
""",


    "conspect": """
Создай качественный структурированный учебный конспект
на основе материала пользователя.

Самостоятельно определи наиболее подходящую структуру.

Используй:

• заголовки;
• подзаголовки;
• маркированные списки;
• нумерованные пункты;
• определения;
• важные факты;
• даты и имена, если они есть в материале;
• причинно-следственные связи, если они действительно
  присутствуют в материале.

ВАЖНО:

Не создавай обязательные разделы только ради шаблона.

Если в материале нет информации для определённого раздела,
просто не создавай этот раздел.

Не повторяй информацию.

Не добавляй выдуманные факты.

Конспект должен быть похож на качественные записи студента,
которые удобно читать, изучать и повторять перед экзаменом.

В конце добавь раздел:

📌 Главное для запоминания

В нём перечисли 3–7 самых важных мыслей материала.
""",


    "summary": """
Сделай максимально полезную краткую выжимку
предоставленного материала.

Цель — дать человеку возможность быстро понять
основную суть текста.

Правила:

• оставь только действительно важную информацию;
• убери повторы;
• убери второстепенные детали;
• сохрани ключевые факты;
• сохрани даты, цифры и названия, если они важны;
• не выдумывай информацию.

Начни с короткого блока:

⚡ Кратко

Затем дай основные пункты.

В конце добавь:

📌 Главное

с 3–5 наиболее важными мыслями.

Если исходный материал очень короткий,
не расширяй его искусственно.
""",


    "theses": """
Выдели главные тезисы из предоставленного материала.

Создай от 5 до 20 тезисов в зависимости от объёма
и содержания материала.

Не нужно всегда создавать 20 тезисов.

Каждый тезис должен:

• содержать одну основную мысль;
• быть коротким;
• быть конкретным;
• быть информативным;
• легко запоминаться.

Используй нумерованный список.

Не повторяй одну мысль разными словами.

Не добавляй информацию, которой нет
в предоставленном материале.

В конце добавь:

🎯 Самый важный тезис

и выдели одну главную мысль всего материала.
""",


    "questions": """
Создай систему вопросов для проверки знаний
по предоставленному материалу.

Раздели вопросы на три уровня:

🟢 Базовые
Вопросы на понимание основных фактов.

🟡 Средние
Вопросы на понимание связей и содержания.

🔴 Сложные
Вопросы, требующие более глубокого понимания
материала.

После каждого вопроса сразу укажи:

✅ Ответ:

Ответ должен основываться только
на предоставленном материале.

Не выдумывай отсутствующую информацию.

Количество вопросов определи самостоятельно
в зависимости от объёма материала.

В конце добавь:

🎓 Вопросы для экзамена

Выбери 5 наиболее важных вопросов,
которые лучше всего проверяют знание темы.
""",


    "simple": """
Объясни предоставленный материал максимально
простыми и понятными словами.

Представь, что человек впервые сталкивается
с этой темой.

Правила:

• объясняй сложные термины простым языком;
• разбивай сложную информацию на небольшие части;
• используй короткие предложения;
• сохраняй смысл исходного материала;
• не искажай факты;
• не добавляй неподтверждённую информацию.

Структура:

🧠 Простыми словами

Объясни основную идею темы.

📌 Главное

Перечисли основные факты.

💡 Как это понять

Объясни наиболее сложные моменты простым языком.

В конце сделай короткий вывод.

Не используй этот шаблон механически.
Если какой-либо раздел не нужен,
его можно пропустить.
"""
}

# =========================================================
# СИСТЕМНАЯ ИНСТРУКЦИЯ
# =========================================================

SYSTEM_PROMPT = """
Ты — SmartNote AI, интеллектуальный учебный ассистент.

Твоя задача — превращать учебные материалы пользователя
в качественные, понятные и полезные материалы для обучения.

ГЛАВНЫЙ ПРИНЦИП:

Работай прежде всего с предоставленным пользователем
материалом.

Не выдумывай факты.

Не добавляй сведения, которых нет в исходном материале,
если они не требуются для понятного объяснения.

Если информации мало — не увеличивай ответ искусственно.

КАЧЕСТВО:

- Не повторяй одну и ту же информацию.
- Не используй механические шаблоны.
- Самостоятельно определяй логичную структуру ответа.
- Не создавай разделы, для которых нет информации.
- Не пиши фразы вроде «материал недостаточен»,
  если можно просто пропустить ненужный раздел.
- Сохраняй важные факты, даты, цифры, названия и определения.
- Пиши естественным языком.
- Используй Markdown для удобного чтения в Telegram.
- Используй эмодзи только там, где они действительно
  улучшают навигацию.
- Не начинай ответ с длинного приветствия.
- Не обращайся к пользователю без необходимости.
- Не говори о своей работе как об ИИ внутри результата.

ЯЗЫК:

Отвечай на языке исходного материала,
если пользователь явно не попросил другой язык.

Если материал написан на русском — отвечай на русском.

ФОРМАТ:

Ответ должен быть удобен для чтения
на экране мобильного телефона.

Используй короткие абзацы,
заголовки и списки.

Не используй таблицы,
если они не являются действительно необходимыми.

Главная цель — помочь человеку
понять, запомнить и повторить материал.
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

    # Убираем жирное Markdown
    text = text.replace("**", "")

    # Убираем подчёркивания Markdown
    text = text.replace("__", "")

    # Превращаем Markdown-списки:
    # * текст
    # - текст
    # + текст
    # в нормальные маркеры
    lines = []

    for line in text.splitlines():

        stripped = line.strip()

        if stripped.startswith("* "):
            line = "• " + stripped[2:]

        elif stripped.startswith("- "):
            line = "• " + stripped[2:]

        elif stripped.startswith("+ "):
            line = "• " + stripped[2:]

        lines.append(line)

    text = "\n".join(lines)

    # Убираем горизонтальные линии
    text = re.sub(
        r"^\s*[-_]{3,}\s*$",
        "",
        text,
        flags=re.MULTILINE
    )

    # Убираем лишние пустые строки
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

    user_prompt = (
        instruction
        + "\n\n"
        + "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ:\n\n"
        + material
    )

    def generate():

        response = gemini_client.models.generate_content(

            model="gemini-3.5-flash-lite",

            contents=user_prompt,

            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT
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

    print("====================================", flush=True)
    print("🧠 SMARTNOTE AI", flush=True)
    print("📱 TEXT VERSION", flush=True)
    print("🤖 Gemini", flush=True)
    print("====================================", flush=True)

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

    print("====================================", flush=True)

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
    # ТЕКСТ
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_text
    )
    )

    # =====================================================
    # ФОТО / СКАНЫ
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_photo
        )
    )

    print(
        "📸 PHOTO HANDLER ENABLED",
        flush=True
    )

    # =====================================================
    # PDF / DOCX
    # =====================================================
    application.add_handler(
        MessageHandler(
            filters.Document.ALL,
            receive_document
        )
    )

    print(
        "📎 DOCUMENT HANDLER ENABLED",
        flush=True
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
