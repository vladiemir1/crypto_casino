from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str
    
    # CryptoBot API
    cryptobot_token: str
    
    # Admin ID
    admin_id: Optional[str] = None
    
    # Debug mode
    debug: Optional[bool] = False
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:root@localhost:5432/crypto_casino"
    
    # Webhook
    WEBHOOK_URL: str = "https://twelve-ducks-chert.loca.lt"
    WEBHOOK_PORT: int = 8000
    WEBHOOK_PATH: str = "/webhook-secret-path"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Экспортируем для обратной совместимости
BOT_TOKEN = settings.BOT_TOKEN
WEBHOOK_URL = settings.WEBHOOK_URL
WEBHOOK_PATH = settings.WEBHOOK_PATH
