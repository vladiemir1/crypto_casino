from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
import uuid
import json

from .keyboards import *
from database.database import async_session_maker
from database.crud import UserCRUD, GameCRUD, TransactionCRUD
from database.models import GameResult
from payment.cryptobot import cryptobot
from game.dice import DiceGame
from game.darts import DartsGame
from game.basketball import BasketballGame
from game.football import FootballGame
from game.bowling import BowlingGame

router = Router()
bot_instance = None


# ==================== НАСТРОЙКА БОТА ====================

def set_bot(bot):
    global bot_instance
    bot_instance = bot


# ==================== КОМАНДЫ ====================

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Регистрация пользователя при /start и приветственное меню."""
    async with async_session_maker() as session:
        await UserCRUD.get_or_create(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )

    await message.answer(
        "🎰 <b>Добро пожаловать в Crypto Casino!</b>\n\n"
        "🎮 Играй в честные Telegram-игры\n"
        "💰 Выигрывай криптовалюту\n"
        "⚡️ Мгновенные выплаты\n\n"
        "Все игры используют <b>Telegram Dice API</b> — результат генерируется Telegram!\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@router.message(F.text == "🎰 Играть")
async def show_games(message: Message):
    """Показать список доступных игр."""
    await message.answer(
        "🎮 <b>Выбери игру:</b>\n\n"
        "🎲 <b>Кости</b> — больше/меньше, четное/нечетное\n"
        "🎯 <b>Дартс</b> — попади в цель\n"
        "🏀 <b>Баскетбол</b> — забей мяч\n"
        "⚽️ <b>Футбол</b> — попади в ворота\n"
        "🎳 <b>Боулинг</b> — сбей кегли\n\n"
        "💰 Ставка: <b>5 USDT</b> на все игры",
        reply_markup=get_games_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.answer("🏠 Главное меню:", reply_markup=get_main_menu())
    await callback.answer()


@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    """Вывод статистики пользователя."""
    async with async_session_maker() as session:
        user = await UserCRUD.get_or_create(session, message.from_user.id)

        profit = user.total_won - user.total_wagered
        win_rate = (user.total_won / user.total_wagered * 100) if user.total_wagered > 0 else 0

        await message.answer(
            f"📊 <b>Твоя статистика:</b>\n\n"
            f"🎮 Игр сыграно: {user.games_played}\n"
            f"💰 Всего поставлено: {user.total_wagered:.2f} USDT\n"
            f"💎 Всего выиграно: {user.total_won:.2f} USDT\n"
            f"📈 Прибыль: {profit:+.2f} USDT\n"
            f"🎯 Винрейт: {win_rate:.1f}%",
            parse_mode="HTML"
        )


@router.message(F.text == "ℹ️ Помощь")
async def show_help(message: Message):
    """Инструкция по использованию казино."""
    await message.answer(
        "ℹ️ <b>Как играть:</b>\n\n"
        "1️⃣ Выбери игру из меню\n"
        "2️⃣ Выбери тип ставки\n"
        "3️⃣ Оплати 5 USDT через @CryptoBot\n"
        "4️⃣ Смотри результат в виде анимации!\n"
        "5️⃣ Если выиграл — деньги придут автоматически\n\n"
        "🎲 Все игры используют Telegram Dice API\n"
        "✅ Результат генерирует Telegram (не мы!)\n"
        "🔒 Полная честность и прозрачность\n\n"
        "Поддержка: @yoursupport",
        parse_mode="HTML"
    )


# ==================== КОСТИ ====================

@router.callback_query(F.data == "game_dice")
async def game_dice(callback: CallbackQuery):
    await callback.message.answer(
        "🎲 <b>КОСТИ</b>\n\nВыбери тип ставки:",
        reply_markup=get_dice_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.in_(["dice_high", "dice_low"]))
async def dice_high_low(callback: CallbackQuery):
    bet_value = callback.data.split("_")[1]
    game_type = f"dice_{bet_value}"

    await create_game_and_invoice(
        callback,
        game_type,
        f"🎲 <b>КОСТИ - {'Больше' if bet_value == 'high' else 'Меньше'}</b>\n\n"
        f"{'🔴 Больше: 4-5-6' if bet_value == 'high' else '🔵 Меньше: 1-2-3'}\n\n"
        f"💰 Ставка: 5 USDT\n💎 Выигрыш: 9.5 USDT (x1.9)\n🎯 Шанс: 50%"
    )


@router.callback_query(F.data.in_(["dice_even", "dice_odd"]))
async def dice_even_odd(callback: CallbackQuery):
    bet_value = callback.data.split("_")[1]
    game_type = f"dice_{bet_value}"

    await create_game_and_invoice(
        callback,
        game_type,
        f"🎲 <b>КОСТИ - {'Четное' if bet_value == 'even' else 'Нечетное'}</b>\n\n"
        f"{'⚪️ Четное: 2-4-6' if bet_value == 'even' else '⚫️ Нечетное: 1-3-5'}\n\n"
        f"💰 Ставка: 5 USDT\n💎 Выигрыш: 9.5 USDT (x1.9)\n🎯 Шанс: 50%"
    )


@router.callback_query(F.data == "dice_exact")
async def dice_exact(callback: CallbackQuery):
    await callback.message.answer(
        "🎲 <b>КОСТИ - Точное число</b>\n\nВыбери число от 1 до 6:",
        reply_markup=get_dice_exact_numbers(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dice_num_"))
async def dice_exact_number(callback: CallbackQuery):
    number = callback.data.split("_")[2]
    game_type = f"dice_num_{number}"

    await create_game_and_invoice(
        callback,
        game_type,
        f"🎲 <b>КОСТИ - Число {number}</b>\n\n"
        f"🎯 Твой выбор: <b>{number}</b>\n\n"
        f"💰 Ставка: 5 USDT\n💎 Выигрыш: 27.5 USDT (x5.5)\n🎯 Шанс: 16.67%"
    )


# ==================== ДАРТС ====================

@router.callback_query(F.data == "game_darts")
async def game_darts(callback: CallbackQuery):
    await callback.message.answer(
        "🎯 <b>ДАРТС</b>\n\nВыбери куда попадешь:",
        reply_markup=get_darts_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("darts_"))
async def darts_bet(callback: CallbackQuery):
    bet_value = callback.data.split("_")[1]
    mapping = {
        "red": ("darts_red", "🎯 <b>ДАРТС - Красное</b>\n\n🔴 Красное (2, 4)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 9 USDT (x1.8)\n🎯 Шанс: 33%"),
        "white": ("darts_white", "🎯 <b>ДАРТС - Белое</b>\n\n⚪️ Белое (3, 5)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 9 USDT (x1.8)\n🎯 Шанс: 33%"),
        "6": ("darts_6", "🎯 <b>ДАРТС - Центр</b>\n\n🎯 Bullseye (6)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 12.5 USDT (x2.5)\n🎯 Шанс: 16.67%"),
        "1": ("darts_1", "🎯 <b>ДАРТС - Мимо</b>\n\n❌ Мимо (1)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 12.5 USDT (x2.5)\n🎯 Шанс: 16.67%")
    }

    game_type, text = mapping.get(bet_value, ("darts_1", "🎯 Ошибка выбора"))
    await create_game_and_invoice(callback, game_type, text)


# ==================== БАСКЕТБОЛ ====================

@router.callback_query(F.data == "game_basketball")
async def game_basketball(callback: CallbackQuery):
    await callback.message.answer(
        "🏀 <b>БАСКЕТБОЛ</b>\n\nВыбери результат:",
        reply_markup=get_basketball_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("basketball_"))
async def basketball_bet(callback: CallbackQuery):
    bet_type = callback.data.split("_")[1]
    text = (
        "🏀 <b>БАСКЕТБОЛ - Гол</b>\n\n✅ Попадание (4-5)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 9 USDT (x1.8)\n🎯 Шанс: 40%"
        if bet_type == "goal"
        else "🏀 <b>БАСКЕТБОЛ - Мимо</b>\n\n❌ Промах (1-3)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 6.5 USDT (x1.3)\n🎯 Шанс: 60%"
    )
    await create_game_and_invoice(callback, f"basketball_{bet_type}", text)


# ==================== ФУТБОЛ ====================

@router.callback_query(F.data == "game_football")
async def game_football(callback: CallbackQuery):
    await callback.message.answer(
        "⚽️ <b>ФУТБОЛ</b>\n\nВыбери результат:",
        reply_markup=get_football_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("football_"))
async def football_bet(callback: CallbackQuery):
    bet_type = callback.data.split("_")[1]
    text = (
        "⚽️ <b>ФУТБОЛ - Гол</b>\n\n✅ Попадание (3, 4, 5)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 8.5 USDT (x1.7)\n🎯 Шанс: 50%"
        if bet_type == "goal"
        else "⚽️ <b>ФУТБОЛ - Мимо</b>\n\n❌ Промах (1, 2, 6)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 6.5 USDT (x1.3)\n🎯 Шанс: 50%"
    )
    await create_game_and_invoice(callback, f"football_{bet_type}", text)


# ==================== БОУЛИНГ ====================

@router.callback_query(F.data == "game_bowling")
async def game_bowling(callback: CallbackQuery):
    await callback.message.answer(
        "🎳 <b>БОУЛИНГ</b>\n\nВыбери результат:",
        reply_markup=get_bowling_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bowling_"))
async def bowling_bet(callback: CallbackQuery):
    bet_type = callback.data.split("_")[1]
    text = (
        "🎳 <b>БОУЛИНГ - Страйк</b>\n\n💥 Все кегли (6)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 12.5 USDT (x2.5)\n🎯 Шанс: 16.67%"
        if bet_type == "strike"
        else "🎳 <b>БОУЛИНГ - Не страйк</b>\n\n❌ Не все кегли (1–5)\n\n💰 Ставка: 5 USDT\n💎 Выигрыш: 6.5 USDT (x1.3)\n🎯 Шанс: 83.33%"
    )
    await create_game_and_invoice(callback, f"bowling_{bet_type}", text)


# ==================== ОБЩИЕ ФУНКЦИИ ====================

async def create_game_and_invoice(callback: CallbackQuery, game_type: str, description: str):
    """Создаёт запись игры, инвойс и отправляет ссылку пользователю."""
    try:
        async with async_session_maker() as session:
            # ✅ ШАГ 1: Получаем/создаем пользователя
            user = await UserCRUD.get_or_create(
                session,
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name
            )
            
            # ✅ ШАГ 2: Генерируем UUID для игры
            game_id = str(uuid.uuid4())
            
            # ✅ ШАГ 3: Создаем игру используя user.id (НЕ telegram_id!)
            game = await GameCRUD.create(
                session=session,
                game_id=game_id,
                user_id=user.id,  # ✅ ИСПОЛЬЗУЕМ user.id ИЗ БД!
                game_type=game_type,
                bet_amount=5,
                currency="USDT"
            )

            # ✅ ШАГ 4: Создаем инвойс в CryptoBot
            invoice_response = await cryptobot.create_invoice(
                asset="USDT",  # ✅ asset вместо currency
                amount=5,
                description=f"Ставка в {game_type}"
            )
            
            # ✅ ШАГ 5: Извлекаем данные из ответа
            # CryptoBot возвращает словарь с данными
            invoice_id = str(invoice_response['invoice_id'])  # ✅ Конвертируем в строку!
            pay_url = invoice_response['bot_invoice_url']
            
            print(f"✅ Invoice created: ID={invoice_id}, URL={pay_url}")
            
            # ✅ ШАГ 6: Создаем транзакцию
            await TransactionCRUD.create(
                session, 
                user_id=user.id,  # ✅ ИСПОЛЬЗУЕМ user.id ИЗ БД!
                invoice_id=invoice_id,
                amount=5, 
                currency="USDT", 
                status="pending", 
                game_id=game_id
            )

            # ✅ ШАГ 7: Отправляем ссылку пользователю
            await callback.message.answer(
                description + "\n\n💵 Оплати ставку:",
                reply_markup=get_payment_btn(pay_url),
                parse_mode="HTML"
            )
            await callback.answer()
            
    except Exception as e:
        print(f"❌ Ошибка в create_game_and_invoice: {e}")
        import traceback
        traceback.print_exc()
        await callback.message.answer("⚠️ Ошибка при создании игры. Попробуй снова позже.")
        await callback.answer("Ошибка", show_alert=True)


async def process_game_result(game: GameResult, message: Message, win: bool):
    """Обработка результата игры."""
    if win:
        await send_result_message(message, "✅ Победа!", game)
        await send_payout(game.user_id, game.win_amount)
    else:
        await send_result_message(message, "❌ Проигрыш!", game)


async def send_result_message(message: Message, result_text: str, game: GameResult):
    """Отправка сообщения о результате."""
    await message.answer(
        f"{result_text}\n\n💰 Ставка: {game.bet_amount} USDT\n💎 Выигрыш: {game.win_amount} USDT\n🎮 Игра: {game.game_type}",
        parse_mode="HTML"
    )


async def send_payout(user_id: int, amount: float):
    """Перевод выигрыша пользователю через CryptoBot."""
    await cryptobot.transfer(user_id=user_id, amount=amount, currency="USDT")