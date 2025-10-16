from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import uuid
import logging
from datetime import datetime
from sqlalchemy.sql import text
from aiocryptopay import Networks

from .keyboards import *
from .states import BetFlow
from game.football import FootballGame
from database.database import async_session_maker
from database.crud import UserCRUD, GameCRUD, TransactionCRUD
from database.models import GameResult, GameStatus, TransactionStatus
from payment.cryptobot import cryptobot

router = Router()
bot_instance = None
MIN_BET = 0.05
logger = logging.getLogger(__name__)

def set_bot(bot):
    global bot_instance
    bot_instance = bot


GAME_DESCRIPTIONS = {
    'dice_high': {'emoji': '🎲', 'name': 'КОСТИ: Больше (4-5-6)', 'coef': '1.8x'},
    'dice_low': {'emoji': '🎲', 'name': 'КОСТИ: Меньше (1-2-3)', 'coef': '1.8x'},
    'dice_odd': {'emoji': '🎲', 'name': 'КОСТИ: Нечетное (1-3-5)', 'coef': '1.8x'},
    'dice_even': {'emoji': '🎲', 'name': 'КОСТИ: Четное (2-4-6)', 'coef': '1.8x'},
    'dice_num_1': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 1', 'coef': '3.1x'},
    'dice_num_2': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 2', 'coef': '3.1x'},
    'dice_num_3': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 3', 'coef': '3.1x'},
    'dice_num_4': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 4', 'coef': '3.1x'},
    'dice_num_5': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 5', 'coef': '3.1x'},
    'dice_num_6': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 6', 'coef': '3.1x'},
    'darts_red': {'emoji': '🎯', 'name': 'ДАРТС: Красное (2,4)', 'coef': '1.8x'},
    'darts_white': {'emoji': '🎯', 'name': 'ДАРТС: Белое (3,5)', 'coef': '1.8x'},
    'darts_6': {'emoji': '🎯', 'name': 'ДАРТС: Центр (6)', 'coef': '2.5x'},
    'darts_1': {'emoji': '🎯', 'name': 'ДАРТС: Мимо (1)', 'coef': '2.5x'},
    'basketball_goal': {'emoji': '🏀', 'name': 'БАСКЕТБОЛ: Гол (4-5)', 'coef': '1.8x'},
    'basketball_miss': {'emoji': '🏀', 'name': 'БАСКЕТБОЛ: Мимо (1-2-3)', 'coef': '1.3x'},
    'football_goal': {'emoji': '⚽️', 'name': 'ФУТБОЛ: Гол (4-5)', 'coef': '1.8x'},
    'football_miss': {'emoji': '⚽️', 'name': 'ФУТБОЛ: Мимо (1-2-3)', 'coef': '1.3x'},
    'bowling_strike': {'emoji': '🎳', 'name': 'БОУЛИНГ: Страйк (6)', 'coef': '4.0x'},
    'bowling_nonstrike': {'emoji': '🎳', 'name': 'БОУЛИНГ: Не страйк (1-5)', 'coef': '1.2x'},
}

# ==================== КОМАНДЫ ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Регистрация пользователя при /start"""
    await state.clear()
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
async def show_games(message: Message, state: FSMContext):
    """Показать список доступных игр"""
    await state.clear()
    await message.answer(
        "🎮 <b>Выбери игру:</b>",
        reply_markup=get_games_menu(),
        parse_mode="HTML"
    )

@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    """Вывод статистики пользователя в новом формате"""
    async with async_session_maker() as session:
        user = await UserCRUD.get_or_create(session, message.from_user.id)
        username = user.username or "Без имени"

        total_games = user.games_played

        game_names = {
            'dice_high': '🎲 Кости (Больше)',
            'dice_low': '🎲 Кости (Меньше)',
            'dice_odd': '🎲 Кости (Нечетное)',
            'dice_even': '🎲 Кости (Четное)',
            'dice_exact': '🎲 Кости (Точное число)',
            'darts': '🎯 Дартс',
            'basketball': '🏀 Баскетбол',
            'football': '⚽️ Футбол',
            'bowling': '🎳 Боулинг'
        }

        favorite_game_query = await session.execute(
            text("""
                SELECT game_type, COUNT(*) as count 
                FROM games 
                WHERE user_id = :user_id AND status = 'COMPLETED' 
                GROUP BY game_type 
                ORDER BY count DESC 
                LIMIT 1
            """),
            {"user_id": user.id}
        )
        favorite_game_result = favorite_game_query.fetchone()
        
        if favorite_game_result:
            favorite_game_type = favorite_game_result[0]
            favorite_game = game_names.get(favorite_game_type, favorite_game_type)
            favorite_game_count = favorite_game_result[1]
        else:
            favorite_game = "Не определена"
            favorite_game_count = 0

        max_win_query = await session.execute(
            text("""
                SELECT MAX(payout - bet_amount) as max_win 
                FROM games 
                WHERE user_id = :user_id 
                AND status = 'COMPLETED' 
                AND result = 'WIN'
                AND payout > bet_amount
            """),
            {"user_id": user.id}
        )
        max_win = max_win_query.scalar() or 0.0

        stats_message = (
            f"Информация по пользователю {username}\n\n"
            f"📊 Статистика\n"
            f"┣ Любимая игра: {favorite_game} [{favorite_game_count}]\n"
            f"┣ Сыгранные игры: {total_games}\n"
            f"┗ Самый большой выигрыш: {max_win:.2f}$"
        )

        await message.answer(stats_message, parse_mode="HTML")

@router.message(F.text == "ℹ️ Помощь")
async def show_help(message: Message):
    """Инструкция по использованию казино"""
    await message.answer(
        "ℹ️ <b>Как играть:</b>\n\n"
        "1️⃣ Выбери игру из меню\n"
        "2️⃣ Выбери тип ставки\n"
        f"3️⃣ Выбери сумму (минимум {MIN_BET} USD)\n"
        "4️⃣ Выбери валюту для оплаты\n"
        "5️⃣ Оплати счёт через @CryptoBot\n"
        "6️⃣ Смотри результат в виде анимации!\n"
        "7️⃣ Если выиграл — деньги придут автоматически\n\n"
        "🎲 Все игры используют Telegram Dice API\n"
        "✅ Результат генерирует Telegram (не мы!)\n"
        "🔒 Полная честность и прозрачность\n"
        "💼 Комиссия казино: 10% (вычитается из депозита)\n\n"
        "Поддержка: @yoursupport",
        parse_mode="HTML"
    )

# ==================== КОСТИ ====================

@router.callback_query(F.data == "game_dice")
async def game_dice(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🎲 <b>КОСТИ</b>\n\nВыбери тип ставки:",
        reply_markup=get_dice_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_high")
async def dice_high_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "dice_high"
    await state.update_data(game_type=game_type, description="🎲 <b>КОСТИ: Больше (4-5-6)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎲 <b>КОСТИ: Больше (4-5-6)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_low")
async def dice_low_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "dice_low"
    await state.update_data(game_type=game_type, description="🎲 <b>КОСТИ: Меньше (1-2-3)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎲 <b>КОСТИ: Меньше (1-2-3)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_even")
async def dice_even_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "dice_even"
    await state.update_data(game_type=game_type, description="🎲 <b>КОСТИ: Четное (2-4-6)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎲 <b>КОСТИ: Четное (2-4-6)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_odd")
async def dice_odd_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "dice_odd"
    await state.update_data(game_type=game_type, description="🎲 <b>КОСТИ: Нечетное (1-3-5)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎲 <b>КОСТИ: Нечетное (1-3-5)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_exact")
async def dice_exact_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎲 КОСТИ: Угадай число\n\n"
        "⚡️Коэффициент: 3.1x\n"
        "Выбери число:",
        reply_markup=get_dice_exact_numbers()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("dice_num_"))
async def dice_exact_bet(callback: CallbackQuery, state: FSMContext):
    number = callback.data.split("_")[-1]
    game_type = f"dice_num_{number}"
    await state.update_data(game_type=game_type, description=f"🎲 <b>КОСТИ: Угадать число {number}</b>\n💰 Коэффициент: <b>3.1x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        f"🎲 <b>КОСТИ: Угадать число {number}</b>\n💰 Коэффициент: <b>3.1x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== ДАРТС ====================

@router.callback_query(F.data == "game_darts")
async def game_darts(callback: CallbackQuery):
    await callback.message.answer(
        "🎯 <b>ДАРТС</b>\n\nВыбери тип ставки:",
        reply_markup=get_darts_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_red")
async def darts_red_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "darts_red"
    await state.update_data(game_type=game_type, description="🎯 <b>ДАРТС: Красное (2,4)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎯 <b>ДАРТС: Красное (2,4)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_white")
async def darts_white_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "darts_white"
    await state.update_data(game_type=game_type, description="🎯 <b>ДАРТС: Белое (3,5)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎯 <b>ДАРТС: Белое (3,5)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_6")
async def darts_center_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "darts_6"
    await state.update_data(game_type=game_type, description="🎯 <b>ДАРТС: Центр (6)</b>\n💰 Коэффициент: <b>2.5x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎯 <b>ДАРТС: Центр (6)</b>\n💰 Коэффициент: <b>2.5x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_1")
async def darts_miss_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "darts_1"
    await state.update_data(game_type=game_type, description="🎯 <b>ДАРТС: Мимо (1)</b>\n💰 Коэффициент: <b>2.5x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎯 <b>ДАРТС: Мимо (1)</b>\n💰 Коэффициент: <b>2.5x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== БАСКЕТБОЛ ====================

@router.callback_query(F.data == "game_basketball")
async def game_basketball(callback: CallbackQuery):
    await callback.message.answer(
        "🏀 <b>БАСКЕТБОЛ</b>\n\nВыбери тип ставки:",
        reply_markup=get_basketball_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "basketball_goal")
async def basketball_goal_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "basketball_goal"
    await state.update_data(game_type=game_type, description="🏀 <b>БАСКЕТБОЛ: Гол (4-5)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🏀 <b>БАСКЕТБОЛ: Гол (4-5)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "basketball_miss")
async def basketball_miss_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "basketball_miss"
    await state.update_data(game_type=game_type, description="🏀 <b>БАСКЕТБОЛ: Мимо (1-2-3)</b>\n💰 Коэффициент: <b>1.3x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🏀 <b>БАСКЕТБОЛ: Мимо (1-2-3)</b>\n💰 Коэффициент: <b>1.3x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== ФУТБОЛ ====================

@router.callback_query(F.data == "game_football")
async def game_football(callback: CallbackQuery):
    await callback.message.answer(
        "⚽️ <b>ФУТБОЛ</b>\n\nВыбери тип ставки:",
        reply_markup=get_football_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "football_goal")
async def football_goal_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "football_goal"
    await state.update_data(game_type=game_type, description="⚽️ <b>ФУТБОЛ: Гол (4-5)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "⚽️ <b>ФУТБОЛ: Гол (4-5)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "football_miss")
async def football_miss_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "football_miss"
    await state.update_data(game_type=game_type, description="⚽️ <b>ФУТБОЛ: Мимо (1-2-3)</b>\n💰 Коэффициент: <b>1.3x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "⚽️ <b>ФУТБОЛ: Мимо (1-2-3)</b>\n💰 Коэффициент: <b>1.3x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== БОУЛИНГ ====================

@router.callback_query(F.data == "game_bowling")
async def game_bowling(callback: CallbackQuery):
    await callback.message.answer(
        "🎳 <b>БОУЛИНГ</b>\n\nВыбери тип ставки:",
        reply_markup=get_bowling_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "bowling_strike")
async def bowling_strike_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "bowling_strike"
    await state.update_data(game_type=game_type, description="🎳 <b>БОУЛИНГ: Страйк (6)</b>\n💰 Коэффициент: <b>4.0x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎳 <b>БОУЛИНГ: Страйк (6)</b>\n💰 Коэффициент: <b>4.0x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "bowling_nonstrike")
async def bowling_nonstrike_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "bowling_nonstrike"
    await state.update_data(game_type=game_type, description="🎳 <b>БОУЛИНГ: Не страйк (1-5)</b>\n💰 Коэффициент: <b>1.2x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎳 <b>БОУЛИНГ: Не страйк (1-5)</b>\n💰 Коэффициент: <b>1.2x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== ОБРАБОТКА СУММЫ ====================

@router.callback_query(F.data.startswith("amount_"), BetFlow.entering_amount)
async def process_amount_button(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора суммы через кнопки"""
    if callback.data == "amount_custom":
        await callback.message.answer(
            f"✍️ Введи свою сумму (минимум {MIN_BET} USD):\n\n"
            "<i>Пример: 0.1 или 2.5 или 15</i>",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    amount_str = callback.data.replace("amount_", "")
    try:
        amount = float(amount_str)
    except ValueError:
        await callback.answer("❌ Ошибка суммы", show_alert=True)
        return

    if amount < MIN_BET:
        await callback.answer(f"❌ Минимум {MIN_BET} USD", show_alert=True)
        return

    await state.update_data(amount=amount)
    await state.set_state(BetFlow.choosing_currency)
    
    data = await state.get_data()
    description = data.get("description", "")
    game_type = data.get("game_type", "")
    
    await callback.message.answer(
        f"{description}\n\n"
        f"💰 Сумма ставки: <b>{amount} USD</b>\n\n"
        "Выбери валюту для оплаты:",
        reply_markup=get_currency_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(BetFlow.entering_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    """Обработка кастомной суммы"""
    text = message.text.strip().replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        await message.reply("❌ Неправильный формат. Введи число, например: 0.1")
        return

    if amount < MIN_BET:
        await message.reply(f"❌ Минимальная ставка: {MIN_BET} USD")
        return

    await state.update_data(amount=amount)
    await state.set_state(BetFlow.choosing_currency)
    
    data = await state.get_data()
    description = data.get("description", "")
    game_type = data.get("game_type", "")
    
    await message.answer(
        f"{description}\n\n"
        f"💰 Сумма ставки: <b>{amount} USD</b>\n\n"
        "Выбери валюту для оплаты:",
        reply_markup=get_currency_keyboard(game_type),
        parse_mode="HTML"
    )

# ==================== ОБРАБОТКА ВАЛЮТЫ ====================

@router.callback_query(F.data.startswith("currency_"), BetFlow.choosing_currency)
async def process_currency(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора валюты"""
    currency = callback.data.replace("currency_", "")
    
    data = await state.get_data()
    game_type = data.get("game_type")
    description = data.get("description")
    amount = data.get("amount")

    try:
        await create_game_and_invoice(callback, game_type, description, amount, currency, state)
        await state.clear()
        await callback.answer()
    except Exception as e:
        logger.error(f"❌ Ошибка при создании инвойса: {e}")
        await callback.message.answer("❌ Ошибка при создании счёта. Попробуй позже.")
        await callback.answer("Ошибка", show_alert=True)

# ==================== СОЗДАНИЕ ИГРЫ И ИНВОЙСА ====================

async def create_game_and_invoice(callback: CallbackQuery, game_type: str, description: str, amount: float, currency: str, state: FSMContext):
    """Создаёт запись игры, инвойс и отправляет ссылку пользователю"""
    async with async_session_maker() as session:
        user = await UserCRUD.get_or_create(
            session,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name
        )

        game_id = str(uuid.uuid4())
        
        game = await GameCRUD.create(
            session=session,
            game_id=game_id,
            user_id=user.id,
            game_type=game_type,
            bet_amount=amount,
            currency=currency
        )

        invoice_response = await cryptobot.create_invoice(
            asset=currency,
            amount=amount,
            description=f"Ставка в казино: {game_type}"
        )

        invoice_id = str(invoice_response.get('invoice_id') or invoice_response.get('id') or uuid.uuid4())
        pay_url = invoice_response.get('bot_invoice_url') or invoice_response.get('pay_url') or invoice_response.get('url')

        if not pay_url:
            raise ValueError("Не удалось получить URL для оплаты")

        await TransactionCRUD.create(
            session=session,
            user_id=user.id,
            invoice_id=invoice_id,
            amount=amount,
            currency=currency,
            status=TransactionStatus.PENDING,
            game_id=game_id,
            pay_url=pay_url
        )

        # Получаем информацию об игре
        game_info = GAME_DESCRIPTIONS.get(game_type, {'emoji': '🎮', 'name': game_type, 'coef': '?'})
        
        # Расчёт комиссии и чистой ставки
        commission = amount * 0.10
        net_bet = amount * 0.90
        
        await session.commit()

        # ✅ НОВОЕ СООБЩЕНИЕ С ЭМОДЗИ
        await callback.message.answer(
            f"✅ <b>Счёт создан!</b>\n\n"
            f"{game_info['emoji']} Игра: <b>{game_info['name']}</b>\n"
            f"⚡️ Коэффициент: <b>{game_info['coef']}</b>\n\n"
            f"💵 Сумма ставки: <b>{amount} {currency}</b>\n"
            f"🏦 Комиссия казино: <b>{commission:.4f} {currency}</b> (10%)\n"
            f"🚀 Чистая ставка: <b>{net_bet:.4f} {currency}</b>\n\n"
            f"Оплати счёт по кнопке ниже:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💳 Оплатить", url=pay_url)
            ]]),
            parse_mode="HTML"
        )

# ==================== НАВИГАЦИЯ НАЗАД ====================

@router.callback_query(F.data.startswith("back_to_bet_"))
async def back_to_bet_selection(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору типа ставки из выбора суммы"""
    await state.clear()
    
    # Извлекаем game_type из callback_data
    game_type = callback.data.replace("back_to_bet_", "")
    
    # Определяем к какой игре вернуться
    if game_type.startswith("dice"):
        if game_type.startswith("dice_num"):
            # Если было выбрано конкретное число, возвращаемся к выбору чисел
            await callback.message.edit_text(
                "🎲 КОСТИ: Угадай число\n\n⚡️Коэффициент: 3.1x\nВыбери число:",
                reply_markup=get_dice_exact_numbers()
            )
        else:
            # Иначе возвращаемся к типам ставок на кости
            await callback.message.edit_text(
                "🎲 <b>КОСТИ</b>\n\nВыбери тип ставки:",
                reply_markup=get_dice_bet_types(),
                parse_mode="HTML"
            )
    elif game_type.startswith("darts"):
        await callback.message.edit_text(
            "🎯 <b>ДАРТС</b>\n\nВыбери тип ставки:",
            reply_markup=get_darts_bet_types(),
            parse_mode="HTML"
        )
    elif game_type.startswith("basketball"):
        await callback.message.edit_text(
            "🏀 <b>БАСКЕТБОЛ</b>\n\nВыбери тип ставки:",
            reply_markup=get_basketball_bet_types(),
            parse_mode="HTML"
        )
    elif game_type.startswith("football"):
        await callback.message.edit_text(
            "⚽️ <b>ФУТБОЛ</b>\n\nВыбери тип ставки:",
            reply_markup=get_football_bet_types(),
            parse_mode="HTML"
        )
    elif game_type.startswith("bowling"):
        await callback.message.edit_text(
            "🎳 <b>БОУЛИНГ</b>\n\nВыбери тип ставки:",
            reply_markup=get_bowling_bet_types(),
            parse_mode="HTML"
        )
    else:
        # Если game_type неизвестен, возвращаемся к выбору игр
        await callback.message.edit_text(
            "🎮 <b>Выбери игру:</b>",
            reply_markup=get_games_menu(),
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.callback_query(F.data == "back_to_amount")
async def back_to_amount_selection(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору суммы из выбора валюты"""
    data = await state.get_data()
    game_type = data.get("game_type", "")
    description = data.get("description", "Выбери сумму ставки")
    
    # Возвращаемся в состояние выбора суммы
    await state.set_state(BetFlow.entering_amount)
    
    await callback.message.edit_text(
        f"{description}\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== ОТМЕНА И НАВИГАЦИЯ ====================

@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    """Полная отмена - возврат в главное меню"""
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "❌ Действие отменено.\n\nВыбери действие:",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "🏠 Главное меню:",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_games")
async def back_to_games(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку игр"""
    await state.clear()
    await callback.message.edit_text(
        "🎮 <b>Выбери игру:</b>",
        reply_markup=get_games_menu(),
        parse_mode="HTML"
    )
    await callback.answer()