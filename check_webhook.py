import asyncio
import aiohttp
from config import settings

async def check_cryptobot_webhook():
    url = "https://pay.crypt.bot/api/getWebhookInfo"
    headers = {
        "Crypto-Pay-API-Token": settings.cryptobot_token,
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            result = await resp.json()
            print("="*60)
            print("ПРОВЕРКА CRYPTOBOT WEBHOOK")
            print("="*60)
            if result.get('ok'):
                webhook_url = result['result'].get('webhook_url')
                print(f"Текущий webhook URL: {webhook_url or 'НЕ УСТАНОВЛЕН'}")
            else:
                print(f"Ошибка: {result}")
            print("="*60)

if __name__ == "__main__":
    asyncio.run(check_cryptobot_webhook())
