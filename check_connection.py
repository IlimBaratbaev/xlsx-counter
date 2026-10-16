"""Verify Telegram credentials without printing the token."""
import asyncio
import os

from dotenv import load_dotenv
from telegram import Bot

from bot import BASE_DIR


async def main():
    load_dotenv(BASE_DIR / ".env")
    try:
        async with Bot(os.environ["BOT_TOKEN"]) as bot:
            me = await bot.get_me()
            info = await bot.get_webhook_info()
            print(f"BOT_USERNAME={me.username}")
            print(f"WEBHOOK_CONFIGURED={bool(info.url)}")
    except Exception as error:
        raise SystemExit(f"Connection failed: {type(error).__name__}") from None


if __name__ == "__main__":
    asyncio.run(main())
