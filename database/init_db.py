"""
Скрипт для инициализации базы данных
Запускать перед первым запуском бота: python -m database.init_db
"""

import asyncio
from database.database import engine
from database.models import Base


async def init_database():
    """Создает все таблицы в базе данных"""
    async with engine.begin() as conn:
        # Удаляем старые таблицы (ОСТОРОЖНО! Удалит все данные)
        # await conn.run_sync(Base.metadata.drop_all)
        
        # Создаем новые таблицы
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ База данных успешно инициализирована!")


if __name__ == "__main__":
    asyncio.run(init_database())