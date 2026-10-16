"""Private Telegram interface for the local UTM checker."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from checker import MAX_BYTES, analyze

BASE_DIR = Path(__file__).resolve().parent
LOGGER = logging.getLogger("utm_bot")


def allowed_ids(value: str) -> frozenset[int]:
    ids = frozenset(int(part.strip()) for part in value.split(",") if part.strip())
    if any(user_id <= 0 for user_id in ids):
        raise ValueError("ALLOWED_USER_IDS должен содержать положительные Telegram user ID.")
    return ids


def has_access(update: Update, ids: frozenset[int]) -> bool:
    return bool(update.effective_chat and update.effective_chat.type == "private"
                and update.effective_user and update.effective_user.id in ids)


def text_parts(text: str):
    # 1800 code points also fit Telegram's limit for non-BMP characters.
    while len(text) > 1800:
        boundary = text.rfind("\n", 0, 1800)
        if boundary <= 0:
            boundary = 1800
        yield text[:boundary]
        text = text[boundary:].lstrip("\n")
    if text:
        yield text


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    # Check identity and private chat before getFile or processing any input.
    if not has_access(update, context.bot_data["allowed_ids"]):
        if update.effective_chat and update.effective_chat.type == "private":
            await message.reply_text("Доступ закрыт. Обратись к администратору.")
        return
    if not message.document:
        await message.reply_text(
            "Пришли Excel-файл .xls или .xlsx до 15 МБ.\n"
            "Сначала беру UTM Campaign, если пусто, ищу в комментарии, затем в других полях.\n"
            "Одна строка = один лид. Результат отправлю текстом."
        )
        return
    document = message.document
    if Path(document.file_name or "").suffix.lower() not in {".xls", ".xlsx"}:
        await message.reply_text("Нужен Excel-файл с расширением .xls или .xlsx.")
        return
    if document.file_size is None or document.file_size > MAX_BYTES:
        await message.reply_text("Файл должен быть не больше 15 МБ.")
        return
    await message.reply_text("Файл принят. Считаю кампании.")
    try:
        remote_file = await document.get_file()
        data = await remote_file.download_as_bytearray()
        result = await asyncio.to_thread(analyze, bytes(data))
    except ValueError as error:
        await message.reply_text(f"Не удалось обработать файл: {str(error)[:500]}")
        return
    except Exception as error:
        LOGGER.error("File processing failed: %s", type(error).__name__)
        await message.reply_text("Не удалось прочитать файл. Проверь, что он открывается в Excel, и отправь еще раз.")
        return
    for part in text_parts(result.text()):
        await message.reply_text(part, parse_mode=None)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Exception text and tracebacks may contain API URLs with the bot token.
    LOGGER.error("Telegram handler failed: %s", type(context.error).__name__)


async def on_ready(application: Application) -> None:
    LOGGER.warning("Ready: @%s; allowed accounts: %s", application.bot.username,
                   len(application.bot_data["allowed_ids"]))


def main() -> None:
    load_dotenv(BASE_DIR / ".env")
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Заполни BOT_TOKEN в .env.")
    try:
        ids = allowed_ids(os.environ.get("ALLOWED_USER_IDS", ""))
    except ValueError:
        raise SystemExit("ALLOWED_USER_IDS: укажи Telegram ID через запятую.") from None
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    logging.getLogger("httpcore").setLevel(logging.CRITICAL)
    app = Application.builder().token(token).post_init(on_ready).build()
    app.bot_data["allowed_ids"] = ids
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    app.add_error_handler(on_error)
    app.run_polling(allowed_updates=["message"], drop_pending_updates=False)


if __name__ == "__main__":
    main()
