import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from fastapi import FastAPI

from bot import handlers
from bot.handlers import router
from config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_PATH
from database.database import init_db
from payment.webhook import setup_webhooks, set_webhook_bot, set_webhook_dispatcher

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot: Bot
dp: Dispatcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global bot, dp
    
    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        await init_db()
        print("База данных инициализирована!")
        logger.info("База данных инициализирована!")

        # Инициализация бота
        logger.info("Инициализация бота...")
        bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
        dp = Dispatcher()
        dp.include_router(router)
        
        # Передаём экземпляр бота в хендлеры
        handlers.set_bot(bot)
        
        # Передаём бот и диспетчер в webhook
        set_webhook_bot(bot)
        set_webhook_dispatcher(dp)

        # Установка Telegram webhook
        webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )
        logger.info(f"Telegram webhook установлен: {webhook_url}")
        
        print("\n" + "="*60)
        print("ВАЖНО: Настрой CryptoBot webhook вручную!")
        print("="*60)
        print("1. Открой @CryptoBot в Telegram")
        print("2. Нажми: My Apps -> твой токен -> Webhooks")
        print(f"3. Введи URL: {webhook_url}")
        print("4. Сохрани")
        print("="*60 + "\n")
        
        logger.info(f"Webhook сервер запущен на http://0.0.0.0:8000")
        logger.info(f"Webhook URL: {webhook_url}")
        
        yield
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации: {e}")
        raise
    finally:
        # Очистка при остановке
        if bot:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.session.close()
        logger.info("Бот остановлен")


# Создание FastAPI приложения
app = FastAPI(lifespan=lifespan)

# Настройка роутов для вебхуков
setup_webhooks(app)


async def main():
    """Точка входа"""
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка сервера...")
