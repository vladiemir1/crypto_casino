from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram
    bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    admin_id: int = Field(..., env="ADMIN_ID")
    
    # CryptoBot
    cryptobot_token: str = Field(..., env="CRYPTOBOT_TOKEN")
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Webhook
    webhook_url: str = Field(..., env="WEBHOOK_URL")
    webhook_port: int = Field(8000, env="WEBHOOK_PORT")
    
    # App
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("production", env="ENVIRONMENT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()