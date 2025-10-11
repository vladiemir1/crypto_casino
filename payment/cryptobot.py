import aiohttp
import hmac
import hashlib
import uuid
from typing import Dict, Optional
from config import settings
from utils.logger import logger
from database.crud import UserCRUD, GameCRUD, TransactionCRUD
from database.database import async_session_maker
from datetime import datetime


class CryptoBotAPI:
    BASE_URL = "https://pay.crypt.bot/api"
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Crypto-Pay-API-Token": token,
            "Content-Type": "application/json"
        }

    async def create_invoice(self, asset: str, amount: float, description: str) -> Dict:
        """Создать счёт на оплату"""
        url = f"{self.BASE_URL}/createInvoice"
        data = {
            "asset": asset,
            "amount": str(amount),
            "description": description
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=data) as resp:
                result = await resp.json()
                if not result.get('ok'):
                    raise Exception(f"CryptoBot error: {result}")
                return result['result']

    async def transfer(self, user_id: int, asset: str, amount: float, spend_id: str) -> Dict:
        """Перевести средства пользователю"""
        url = f"{self.BASE_URL}/transfer"
        data = {
            "user_id": user_id,
            "asset": asset,
            "amount": str(amount),
            "spend_id": spend_id,
            "comment": "Выигрыш в казино"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=data) as resp:
                result = await resp.json()
                if not result.get('ok'):
                    raise Exception(f"Transfer error: {result}")
                return result['result']

    @staticmethod
    def verify_signature(body: bytes, signature: str, token: str) -> bool:
        """Проверить подпись webhook"""
        expected = hmac.new(token.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)


# =====================================================
# ✅ Добавляем функцию для создания пользователя и игры
# =====================================================

async def create_game_and_invoice(telegram_id: int, game_type: str, bet_amount: float, currency: str):
    """
    Создаёт пользователя (если его нет), создаёт игру и выставляет счёт через CryptoBot.
    """
    async with async_session_maker() as session:
        try:
            # ✅ Проверяем/создаём пользователя
            user = await UserCRUD.get_or_create(session, telegram_id)
            logger.info(f"✅ Пользователь {telegram_id} проверен/создан")

            # ✅ Создаём игру
            game_id = str(uuid.uuid4())
            game = await GameCRUD.create(
                session=session,
                game_id=game_id,
                user_id=user.id,
                game_type=game_type,
                bet_amount=bet_amount,
                currency=currency
            )
            logger.info(f"🎮 Игра {game_type} создана (id={game_id})")

            # ✅ Создаём инвойс
            crypto_api = CryptoBotAPI(settings.cryptobot_token)
            invoice = await crypto_api.create_invoice(
                asset=currency,
                amount=bet_amount,
                description=f"Игра {game_type}"
            )

            pay_url = invoice.get("pay_url")
            invoice_id = invoice.get("invoice_id")

            # ✅ Сохраняем транзакцию
            await TransactionCRUD.create(
                session=session,
                invoice_id=str(invoice_id),
                user_id=user.id,
                game_id=game.id,
                amount=bet_amount,
                currency=currency,
                pay_url=pay_url
            )

            logger.info(f"💰 Счёт создан успешно. Pay URL: {pay_url}")
            return pay_url

        except Exception as e:
            logger.error(f"❌ Ошибка в create_game_and_invoice: {e}")
            raise


# Глобальный экземпляр CryptoBot API
cryptobot = CryptoBotAPI(settings.cryptobot_token)
