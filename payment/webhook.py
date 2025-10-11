from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import json
import asyncio

from config import settings
from database.database import async_session_maker
from database.crud import TransactionCRUD, GameCRUD, UserCRUD
from database.models import GameResult
from payment.cryptobot import cryptobot

app = FastAPI(title="Casino Webhook Server")

# Импортируем бот для отправки сообщений
bot = None

def set_bot(bot_instance):
    """Установить экземпляр бота"""
    global bot
    bot = bot_instance

@app.post("/webhook/cryptobot")
async def cryptobot_webhook(request: Request, background_tasks: BackgroundTasks):
    """Обработчик webhook от CryptoBot"""
    
    body = await request.body()
    signature = request.headers.get("crypto-pay-api-signature", "")
    
    # Проверка подписи
    if not cryptobot.verify_signature(body, signature, settings.cryptobot_token):
        print(f"❌ Invalid webhook signature")
        raise HTTPException(403, "Invalid signature")
    
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")
    
    print(f"📥 Webhook received: {data.get('update_type')}")
    
    # Обрабатываем событие оплаты
    if data['update_type'] == 'invoice_paid':
        background_tasks.add_task(process_payment, data['payload'])
    
    return {"ok": True}

async def process_payment(payload: dict):
    """Обработка оплаченного инвойса"""
    invoice_id = payload['invoice_id']
    
    print(f"💳 Processing payment: {invoice_id}")
    
    async with async_session_maker() as session:
        # Находим транзакцию
        tx = await TransactionCRUD.get_by_invoice_id(session, invoice_id)
        
        if not tx:
            print(f"❌ Transaction not found: {invoice_id}")
            return
        
        if tx.status != "pending":
            print(f"⚠️ Duplicate webhook: {invoice_id}")
            return
        
        # Отмечаем как оплаченную
        await TransactionCRUD.mark_as_paid(session, invoice_id)
        
        # Получаем игру
        game = await GameCRUD.get_by_game_id(session, str(tx.game_id))
        
        if not game:
            print(f"❌ Game not found for transaction {invoice_id}")
            return
        
        # Уведомляем пользователя и ОТПРАВЛЯЕМ DICE
        await send_dice_and_wait_result(tx.user_id, game)

async def send_dice_and_wait_result(user_id: int, game):
    """Отправить Telegram Dice и дождаться результата"""
    
    # Определяем эмодзи по типу игры
    emoji_map = {
        "dice": "🎲",
        "darts": "🎯",
        "basketball": "🏀",
        "football": "⚽",
        "bowling": "🎳"
    }
    
    game_type = game.game_type.split("_")[0]
    emoji = emoji_map.get(game_type, "🎲")
    
    # Отправляем уведомление
    await bot.send_message(
        user_id,
        "✅ <b>Платеж получен!</b>\n"
        "🎮 Бросаем...",
        parse_mode="HTML"
    )
    
    # ОТПРАВЛЯЕМ DICE
    dice_message = await bot.send_dice(user_id, emoji=emoji)
    dice_value = dice_message.dice.value
    
    print(f"🎲 Dice result: {dice_value} for game {game.game_id}")
    
    # Ждем пока анимация закончится
    await asyncio.sleep(4)
    
    # Обрабатываем результат
    from bot.handlers import process_game_result
    await process_game_result(user_id, game.game_id, dice_value)