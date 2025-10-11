import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from bot.handlers import router, set_bot
from config import settings
from database.database import init_db
from payment.webhook import app as webhook_app, set_bot as set_webhook_bot
import uvicorn

# Настройка логов
logging.basicConfig(level=logging.INFO)
logging.getLogger("aiogram").setLevel(logging.CRITICAL)

TOKEN = settings.bot_token

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

set_bot(bot)
set_webhook_bot(bot)

dp.include_router(router)

async def start_bot():
    """Запуск бота"""
    try:
        print("🤖 Бот запущен и слушает обновления...")
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()
        print("🛑 Бот остановлен.")

async def start_webhook():
    """Запуск webhook сервера"""
    config = uvicorn.Config(
        webhook_app,
        host="0.0.0.0",
        port=settings.webhook_port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    print(f"🌐 Webhook сервер запущен на порту {settings.webhook_port}")
    await server.serve()

async def main():
    print("📦 Инициализация базы данных...")
    await init_db()
    
    # Запускаем бот и webhook параллельно
    await asyncio.gather(
        start_bot(),
        start_webhook()
    )

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()