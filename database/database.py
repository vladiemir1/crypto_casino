from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

# ========================== 
# Настройки подключения к базе данных
# ==========================

DATABASE_URL = "postgresql+asyncpg://postgres:root@localhost:5432/crypto_casino"

# Создание асинхронного движка
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# Базовый класс для моделей
Base = declarative_base()

# Создание асинхронной фабрики сессий
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


# ==========================
# Функции для работы с БД
# ==========================

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Асинхронный генератор сессий"""
    async with async_session_maker() as session:
        yield session


async def init_db():
    """Создает все таблицы, если они ещё не существуют"""
    from database.models import Base as ModelsBase
    
    async with engine.begin() as conn:
        await conn.run_sync(ModelsBase.metadata.create_all, checkfirst=True)
    
    print("✅ База данных инициализирована!")


# Для обратной совместимости со старым кодом
async_session = async_session_maker