from fastapi import FastAPI, Request, BackgroundTasks
import json
import traceback
import logging
import aiohttp

from database.database import async_session_maker
from database.crud import TransactionCRUD, GameCRUD
from database.models import GameResult, User, Game, TransactionStatus
from payment.cryptobot import cryptobot
from config import settings
from aiogram import Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logger = logging.getLogger(__name__)

# Глобальные переменные
bot = None
dp = None

# Определение описаний игр
GAME_DESCRIPTIONS = {
    "dice_high": {"emoji": "🎲", "name": "Больше (4-5-6)", "coef": "1.8x"},
    "dice_low": {"emoji": "🎲", "name": "Меньше (1-2-3)", "coef": "1.8x"},
    "dice_even": {"emoji": "🎲", "name": "Четное", "coef": "1.8x"},
    "dice_odd": {"emoji": "🎲", "name": "Нечетное", "coef": "1.8x"},
    "dice_exact": {"emoji": "🎲", "name": "Точное число", "coef": "3.1x"},
    "darts_red": {"emoji": "🎯", "name": "Красное", "coef": "1.8x"},
    "darts_white": {"emoji": "🎯", "name": "Белое", "coef": "1.8x"},
    "darts_6": {"emoji": "🎯", "name": "Попадание в 6", "coef": "2.5x"},
    "darts_1": {"emoji": "🎯", "name": "Попадание в 1", "coef": "2.5x"},
    "basketball_goal": {"emoji": "🏀", "name": "Попадание", "coef": "1.8x"},
    "basketball_miss": {"emoji": "🏀", "name": "Промах", "coef": "1.3x"},
    "football_goal": {"emoji": "⚽", "name": "Гол", "coef": "1.8x"},
    "football_miss": {"emoji": "⚽", "name": "Промах", "coef": "1.3x"},
    "bowling_strike": {"emoji": "🎳", "name": "Страйк", "coef": "4.0x"},
    "bowling_nonstrike": {"emoji": "🎳", "name": "Не страйк", "coef": "1.2x"}
}


# --- Установка экземпляров ---
def set_webhook_bot(bot_instance):
    global bot
    bot = bot_instance
    logger.info("Экземпляр бота успешно установлен")


def set_webhook_dispatcher(dispatcher):
    global dp
    dp = dispatcher
    logger.info("Dispatcher успешно установлен")


# --- Регистрация эндпоинтов ---
def setup_webhooks(app: FastAPI):
    @app.post(settings.WEBHOOK_PATH)
    async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
        body = await request.body()
        logger.info(f"Получен запрос webhook: {body.decode('utf-8')}")
        try:
            data = json.loads(body)

            if data.get("update_type") == "invoice_paid":
                payload = data.get("payload", {})
                background_tasks.add_task(process_payment, payload)

            elif bot and dp:
                await dp.feed_raw_update(bot, data)
                logger.info("Обновление передано в роутеры для обработки")
            else:
                logger.warning("Обновление не обработано: bot или dp не инициализированы")

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}")
            return {"error": "Invalid JSON"}, 400
        except Exception as e:
            logger.error(f"Ошибка в webhook: {e}")
            traceback.print_exc()
        return {"ok": True}

    logger.info("Webhook endpoints registered")


async def get_usd_to_rub_rate():
    """Получает текущий курс USD -> RUB через API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('rates', {}).get('RUB', 82.0)
    except Exception as e:
        logger.error(f"Ошибка получения курса USD/RUB: {e}")
    return 82.0


# --- Обработка платежа ---
async def process_payment(payload: dict):
    logger.info(f"Начало обработки платежа: {payload}")
    try:
        invoice_id = payload.get("invoice_id") or payload.get("id")
        if not invoice_id:
            logger.error("invoice_id не найден")
            return

        async with async_session_maker() as session:
            tx = await TransactionCRUD.get_by_invoice_id(session, str(invoice_id))
            if not tx:
                logger.error(f"Транзакция не найдена: {invoice_id}")
                return

            if tx.status != TransactionStatus.PENDING:
                logger.warning(f"Транзакция не в статусе PENDING, invoice={invoice_id}")
                return

            await TransactionCRUD.update_status(session, tx, TransactionStatus.PAID)

            game = await session.get(Game, tx.game_id)
            if not game:
                logger.error(f"Игра не найдена для транзакции {invoice_id}")
                return

            user = await session.get(User, game.user_id)
            if not user:
                logger.error(f"Пользователь не найден для игры {game.game_id}")
                return

            await send_dice_and_wait_result(user.telegram_id, game, tx, session)

    except Exception as exc:
        logger.error(f"Исключение в process_payment: {exc}")
        traceback.print_exc()


# --- Логика игры ---
async def send_dice_and_wait_result(user_telegram_id: int, game: Game, tx, session):
    if bot is None:
        logger.error("Экземпляр бота не установлен")
        return

    emoji_map = {
        "dice": "🎲",
        "darts": "🎯",
        "basketball": "🏀",
        "football": "⚽️",
        "bowling": "🎳"
    }

    game_type = (game.game_type or "").split("_")[0]
    emoji = emoji_map.get(game_type, "🎲")

    try:
        await bot.send_message(user_telegram_id, "🔥Ставка принята! Игра уже запущена...", parse_mode="HTML")
        dice_message = await bot.send_dice(chat_id=user_telegram_id, emoji=emoji)
        dice_value = dice_message.dice.value if dice_message and dice_message.dice else None

        if dice_value is None:
            logger.error(f"Не удалось получить значение Dice для игры {game.game_id}")
            await bot.send_message(user_telegram_id, "❌ Ошибка при броске кубика.", parse_mode="HTML")
            return

        win, multiplier = evaluate_game_result(game.game_type, dice_value)
        bet_amount = float(game.bet_amount or 0.0)
        payout = 0.0

        if win and multiplier and bet_amount > 0:
            net_bet = bet_amount * 0.90  # 10% комиссия
            payout = round(net_bet * float(multiplier), 2)

        result_enum = GameResult.WIN if win else GameResult.LOSS

        await GameCRUD.complete_game(session, game, result_enum, payout)
        logger.info(f"Игра завершена: game_id={game.game_id}, result={result_enum}, payout={payout}")

        game_info = GAME_DESCRIPTIONS.get(game.game_type, {'emoji': '🎮', 'name': game.game_type, 'coef': '?'})

        # === Подготовка клавиатуры с кнопкой "Играть снова" ===
        play_again_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть снова", callback_data="back_to_games")]
        ])

        if payout > 100:  # Крупный выигрыш — ручная выплата
            usd_to_rub = await get_usd_to_rub_rate()
            payout_rub = payout * usd_to_rub
            text = (
                f"🎉 <b>Вы выиграли {payout:.2f} USD ({payout_rub:.2f} RUB)!</b>\n\n"
                f"<blockquote>💸 Ваш выигрыш будет зачислен администраторами вручную.\n"
                f"🚀 Удачи в следующих ставках!\n\n"
                f"Тех.поддержка: @yoursupport</blockquote>"
            )
            await bot.send_message(user_telegram_id, text, reply_markup=play_again_kb, parse_mode="HTML")
            logger.warning(f"Крупный выигрыш ({payout} USD) у пользователя {user_telegram_id}")
            return

        # --- Выплата через чек ---
        if payout > 0:
            try:
                check_result = await cryptobot.create_check(asset=game.currency, amount=payout)
                check_url = check_result.get('bot_check_url') or check_result.get('url')
                if not check_url:
                    raise ValueError("URL чека не получен")

                usd_to_rub = await get_usd_to_rub_rate()
                payout_rub = payout * usd_to_rub

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Получить выигрыш", url=check_url)],
                    [InlineKeyboardButton(text="🎮 Играть снова", callback_data="back_to_games")]
                ])

                text = (
                    f"🎉 <b>Вы выиграли {payout:.2f} USD ({payout_rub:.2f} RUB)!</b>\n\n"
                    f"<blockquote>💸 Получите ваш выигрыш по кнопке ниже.\n"
                    f"🚀 Удачи в следующих ставках!</blockquote>"
                )
                await bot.send_message(user_telegram_id, text, reply_markup=keyboard, parse_mode="HTML")

            except Exception as e:
                logger.error(f"Ошибка при создании чека: {e}")
                await bot.send_message(
                    user_telegram_id,
                    f"❌ Ошибка при создании чека выплаты: {e}",
                    reply_markup=play_again_kb,
                    parse_mode="HTML"
                )
        else:
            # Проигрыш
            text = (
                f"❌ <b>Проигрыш</b>\n\n"
                f"{game_info['emoji']} Результат: <b>{dice_value}</b>\n\n"
                f"Попробуй еще раз! 🍀"
            )
            await bot.send_message(user_telegram_id, text, reply_markup=play_again_kb, parse_mode="HTML")

    except Exception as exc:
        logger.error(f"Ошибка в send_dice_and_wait_result: {exc}")
        traceback.print_exc()
        play_again_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть снова", callback_data="back_to_games")]
        ])
        await bot.send_message(
            user_telegram_id,
            f"❌ Ошибка обработки игры: {exc}",
            reply_markup=play_again_kb,
            parse_mode="HTML"
        )


# --- Результаты ---
def evaluate_game_result(game_type: str, dice_value: int):
    if dice_value is None:
        return False, None

    parts = (game_type or "").split("_")
    game = parts[0] if parts else ""

    if game == "dice":
        mode = parts[1] if len(parts) > 1 else ""
        if mode == "high":
            return dice_value >= 4, 1.8
        elif mode == "low":
            return dice_value <= 3, 1.8
        elif mode == "even":
            return dice_value % 2 == 0, 1.8
        elif mode == "odd":
            return dice_value % 2 == 1, 1.8
        elif mode == "num":
            target = int(parts[2]) if len(parts) > 2 else 0
            return dice_value == target, 3.1
    elif game == "darts":
        mode = parts[1] if len(parts) > 1 else ""
        if mode == "red":
            return dice_value in [2, 4], 1.8
        elif mode == "white":
            return dice_value in [3, 5], 1.8
        elif mode == "6":
            return dice_value == 6, 2.5
        elif mode == "1":
            return dice_value == 1, 2.5
    elif game == "basketball":
        mode = parts[1] if len(parts) > 1 else ""
        if mode == "goal":
            return dice_value in [4, 5], 1.8
        elif mode == "miss":
            return dice_value in [1, 2, 3], 1.3
    elif game == "football":
        mode = parts[1] if len(parts) > 1 else ""
        if mode == "goal":
            return dice_value in [4, 5], 1.8
        elif mode == "miss":
            return dice_value in [1, 2, 3], 1.3
    elif game == "bowling":
        mode = parts[1] if len(parts) > 1 else ""
        if mode == "strike":
            return dice_value == 6, 4.0
        elif mode == "nonstrike":
            return dice_value in [1, 2, 3, 4, 5], 1.2
    return False, None