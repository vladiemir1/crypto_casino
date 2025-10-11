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
    "        🎮 <b>Выбери игру:</b>",
    reply_markup=  get_games_menu(),
    parse_mode="HTML"
)




       
       
        
        
    

@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    """Вывод статистики пользователя в новом формате"""
    async with async_session_maker() as session:
        user = await UserCRUD.get_or_create(session, message.from_user.id)
        username = user.username or "Без имени"
          # Фиксированное значение, уточни, если динамическое

        # Получаем общее количество игр
        total_games = user.games_played

        # Определяем любимую игру (по количеству игр) с использованием text()
        favorite_game_query = await session.execute(
            text("SELECT game_type, COUNT(*) as count FROM games WHERE user_id = :user_id AND status = 'COMPLETED' GROUP BY game_type ORDER BY count DESC LIMIT 1"),
            {"user_id": user.id}
        )
        favorite_game_result = favorite_game_query.fetchone()
        favorite_game = favorite_game_result[0] if favorite_game_result else "Не определена"
        favorite_game_count = favorite_game_result[1] if favorite_game_result else 0

        # Получаем самый большой выигрыш за одну игру (из payout) с использованием text()
        max_win_query = await session.execute(
            text("SELECT MAX(payout) as max_win FROM games WHERE user_id = :user_id AND status = 'COMPLETED' AND payout > 0"),
            {"user_id": user.id}
        )
        max_win = max_win_query.scalar() or 0.0

        # Формируем сообщение
        stats_message = (
            f"Информация по пользователю {username} \n\n"
            f"📊 Статистика\n"
            f"┣ Любимая игра: {favorite_game} [{favorite_game_count}]\n"
            f"┣ Сыгранные игры: {total_games}\n"
            f"┗ Самый большой выигрыш: {max_win:.1f}$"
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
    await state.update_data(game_type="dice_high", description="🎲 <b>КОСТИ: Больше (4-5-6)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎲 <b>КОСТИ: Больше (4-5-6)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_low")
async def dice_low_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="dice_low", description="🎲 <b>КОСТИ: Меньше (1-2-3)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎲 <b>КОСТИ: Меньше (1-2-3)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_even")
async def dice_even_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="dice_even", description="🎲 <b>КОСТИ: Четное (2-4-6)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎲 <b>КОСТИ: Четное (2-4-6)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_odd")
async def dice_odd_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="dice_odd", description="🎲 <b>КОСТИ: Нечетное (1-3-5)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎲 <b>КОСТИ: Нечетное (1-3-5)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_exact")
async def dice_exact_menu(callback: CallbackQuery):
    await callback.message.edit_text(
    "🎲 КОСТИ: Угадай число\n\n",
    "⚡️Коэффициент: 3.1x",
    "Выбери число:",
    reply_markup= get_dice_exact_numbers()
)
    await callback.answer()
    

@router.callback_query(F.data.startswith("dice_num_"))
async def dice_exact_bet(callback: CallbackQuery, state: FSMContext):
    number = callback.data.split("_")[-1]
    await state.update_data(game_type=f"dice_num_{number}", description=f"🎲 <b>КОСТИ: Угадать число {number}</b>\n💰 Коэффициент: <b>3.1x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        f"🎲 <b>КОСТИ: Угадать число {number}</b>\n💰 Коэффициент: <b>3.1x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
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
    await state.update_data(game_type="darts_red", description="🎯 <b>ДАРТС: Красное (2,4)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎯 <b>ДАРТС: Красное (2,4)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_white")
async def darts_white_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="darts_white", description="🎯 <b>ДАРТС: Белое (3,5)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎯 <b>ДАРТС: Белое (3,5)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_6")
async def darts_center_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="darts_6", description="🎯 <b>ДАРТС: Центр (6)</b>\n💰 Коэффициент: <b>2.5x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎯 <b>ДАРТС: Центр (6)</b>\n💰 Коэффициент: <b>2.5x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_1")
async def darts_miss_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="darts_1", description="🎯 <b>ДАРТС: Мимо (1)</b>\n💰 Коэффициент: <b>2.5x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎯 <b>ДАРТС: Мимо (1)</b>\n💰 Коэффициент: <b>2.5x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
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
    await state.update_data(game_type="basketball_goal", description="🏀 <b>БАСКЕТБОЛ: Гол (4-5)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🏀 <b>БАСКЕТБОЛ: Гол (4-5)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "basketball_miss")
async def basketball_miss_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="basketball_miss", description="🏀 <b>БАСКЕТБОЛ: Мимо (1-2-3)</b>\n💰 Коэффициент: <b>1.3x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🏀 <b>БАСКЕТБОЛ: Мимо (1-2-3)</b>\n💰 Коэффициент: <b>1.3x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
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
    await state.update_data(game_type="football_goal", description="⚽️ <b>ФУТБОЛ: Гол (4-5)</b>\n💰 Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "⚽️ <b>ФУТБОЛ: Гол (4-5)</b>\n💰 Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "football_miss")
async def football_miss_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="football_miss", description="⚽️ <b>ФУТБОЛ: Мимо (1-2-3)</b>\n💰 Коэффициент: <b>1.3x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "⚽️ <b>ФУТБОЛ: Мимо (1-2-3)</b>\n💰 Коэффициент: <b>1.3x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
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
    await state.update_data(game_type="bowling_strike", description="🎳 <b>БОУЛИНГ: Страйк (6)</b>\n💰 Коэффициент: <b>4.0x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎳 <b>БОУЛИНГ: Страйк (6)</b>\n💰 Коэффициент: <b>4.0x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "bowling_nonstrike")
async def bowling_nonstrike_bet(callback: CallbackQuery, state: FSMContext):
    await state.update_data(game_type="bowling_nonstrike", description="🎳 <b>БОУЛИНГ: Не страйк (1-5)</b>\n💰 Коэффициент: <b>1.2x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.answer(
        "🎳 <b>БОУЛИНГ: Не страйк (1-5)</b>\n💰 Коэффициент: <b>1.2x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(),
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
            "<i>Пример: 0.1 или 2.5 или 10</i>",
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
    
    await callback.message.answer(
        f"{description}\n\n"
        f"💰 Сумма ставки: <b>{amount} USD</b>\n\n"
        "Выбери валюту для оплаты:",
        reply_markup=get_currency_keyboard(),
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
    
    await message.answer(
        f"{description}\n\n"
        f"💰 Сумма ставки: <b>{amount} USD</b>\n\n"
        "Выбери валюту для оплаты:",
        reply_markup=get_currency_keyboard(),
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

        # Расчёт чистой ставки с учётом комиссии 10%
        net_bet = amount * 0.90
        await session.commit()

        # Отправляем сообщение пользователю
        await callback.message.answer(
            f"✅ <b>Счёт создан!</b>\n\n"
            f"🎮 Игра: {description}\n"
            f"💰 Сумма: <b>{amount} {currency}</b>\n"
            f"💼 Комиссия казино: <b>{amount * 0.10:.4f} {currency}</b> (10%)\n"
            f"🎯 Чистая ставка: <b>{net_bet:.4f} {currency}</b>\n\n"
            f"Оплати счёт по кнопке ниже:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💳 Оплатить", url=pay_url)
            ]]),
            parse_mode="HTML"
        )

# ==================== ОБРАБОТКА ОПЛАТЫ И РЕЗУЛЬТАТОВ ====================

@router.callback_query(F.data.startswith("payment_"))
async def process_payment_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка успешной оплаты и запуск игры"""
    payment_id = callback.data.replace("payment_", "")
    async with async_session_maker() as session:
        transaction = await TransactionCRUD.get_by_invoice_id(session, payment_id)
        if not transaction or transaction.status != TransactionStatus.PENDING:
            await callback.answer("Счёт не найден или уже обработан.", show_alert=True)
            return

        game = await GameCRUD.get_by_game_id(session, transaction.game_id)
        if not game:
            await callback.answer("Игра не найдена.", show_alert=True)
            return

        # Обновляем статус транзакции
        await TransactionCRUD.update_status(session, transaction, TransactionStatus.PAID)

        # Симуляция игры (Telegram Dice API)
        await bot_instance.send_dice(chat_id=callback.from_user.id, emoji="🎲")
        dice_value = await get_dice_result(callback.from_user.id)

        # Логика выигрыша
        payout = 0.0
        game_result = GameResult.LOSS
        if game.game_type.startswith("dice"):
            bet_type = game.game_type.split("_")[-1]
            if bet_type == "high" and dice_value >= 4:
                payout = game.bet_amount * 1.8
                game_result = GameResult.WIN
            elif bet_type == "low" and dice_value <= 3:
                payout = game.bet_amount * 1.8
                game_result = GameResult.WIN
            elif bet_type == "even" and dice_value in [2, 4, 6]:
                payout = game.bet_amount * 1.8
                game_result = GameResult.WIN
            elif bet_type == "odd" and dice_value in [1, 3, 5]:
                payout = game.bet_amount * 1.8
                game_result = GameResult.WIN
            elif bet_type.startswith("num") and bet_type.split("_")[-1] == str(dice_value):
                payout = game.bet_amount * 3.1
                game_result = GameResult.WIN
        elif game.game_type.startswith("darts"):
            if game.game_type == "darts_red" and dice_value in [2, 4]:
                payout = game.bet_amount * 1.8
                game_result = GameResult.WIN
            elif game.game_type == "darts_white" and dice_value in [3, 5]:
                payout = game.bet_amount * 1.8
                game_result = GameResult.WIN
            elif game.game_type == "darts_6" and dice_value == 6:
                payout = game.bet_amount * 2.5
                game_result = GameResult.WIN
            elif game.game_type == "darts_1" and dice_value == 1:
                payout = game.bet_amount * 2.5
                game_result = GameResult.WIN
        elif game.game_type.startswith("basketball"):
            if game.game_type == "basketball_goal" and dice_value in [4, 5]:
                payout = game.bet_amount * 1.8
                game_result = GameResult.WIN
            elif game.game_type == "basketball_miss" and dice_value in [1, 2, 3]:
                payout = game.bet_amount * 1.3
                game_result = GameResult.WIN
        elif game.game_type.startswith("football"):
            if game.game_type == "football_goal" and dice_value in [4, 5]:
                payout = game.bet_amount * 1.8
                game_result = GameResult.WIN
            elif game.game_type == "football_miss" and dice_value in [1, 2, 3]:
                payout = game.bet_amount * 1.3
                game_result = GameResult.WIN
        elif game.game_type.startswith("bowling"):
            if game.game_type == "bowling_strike" and dice_value == 6:
                payout = game.bet_amount * 4.0
                game_result = GameResult.WIN
            elif game.game_type == "bowling_nonstrike" and dice_value in [1, 2, 3, 4, 5]:
                payout = game.bet_amount * 1.2
                game_result = GameResult.WIN

        # Учёт комиссии (10%) и завершение игры
        net_payout = payout * 0.9 if payout > 0 else 0.0
        await GameCRUD.complete_game(session, game, game_result, net_payout)

        if net_payout > 0.01:
            await send_winnings_via_check(callback.from_user.id, net_payout, game.currency, game.game_type)
        else:
            await bot_instance.send_message(
                callback.from_user.id,
                "❌ Выигрыш слишком мал для выплаты или проигрыш. Удачи в следующей игре!",
                parse_mode="HTML"
            )

        await callback.answer()

# ==================== ПОЛУЧЕНИЕ РЕЗУЛЬТАТА ДЕЙСА ====================

async def get_dice_result(user_id: int) -> int:
    """Получение результата Telegram Dice (упрощённая реализация)"""
    # Здесь нужна реальная логика получения последнего сообщения с Dice
    # Это упрощённая версия, предполагает polling или webhook
    await bot_instance.send_message(user_id, "🔄 Ожидание результата игры...")
    # Симуляция ожидания (замени на реальную логику получения dice_value)
    import asyncio
    await asyncio.sleep(2)  # Задержка для анимации
    return 4  # Пример значения, замени на реальную логику

# ==================== ВЫПЛАТА ВЫИГРЫША ====================

async def send_winnings_via_check(user_telegram_id: int, amount: float, currency: str, game_type: str):
    """Выплата выигрыша через чек"""
    try:
        check_response = await cryptobot.create_check(
            asset=currency,
            amount=amount,
            description=f"Выигрыш в {game_type}"
        )
        if not check_response.get("ok"):
            raise ValueError(f"Check error: {check_response.get('error')}")

        check_url = check_response.get('check_url')
        check_id = check_response.get('check_id')

        await bot_instance.send_message(
            user_telegram_id,
            f"🎉 Ты выиграл {amount:.4f} {currency} в игре {game_type}!\n\n"
            f"Активируй чек для получения средств:\n{check_url}\n\n"
            f"ID чека: {check_id}\nСрок действия: 30 дней (проверь в @CryptoBot).",
            parse_mode="HTML"
        )
        logger.info(f"Чек создан для пользователя {user_telegram_id}: {amount} {currency}, ID: {check_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании чека: {e}")
        await bot_instance.send_message(
            user_telegram_id,
            f"❌ Ошибка при выплате выигрыша: {str(e)}. Обратитесь в поддержку.",
            parse_mode="HTML"
        )

# ==================== ОТМЕНА ====================

@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Действие отменено.")
    await callback.message.answer("❌ Действие отменено. Начни заново: 🎰 Играть")

@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🏠 Главное меню:", reply_markup=get_main_menu())
    await callback.answer()

@router.callback_query(F.data == "back_to_games")
async def back_to_games(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🎮 <b>Выбери игру:</b>\n\n"
        "🎲 <b>Кости</b> — больше/меньше, четное/нечетное, угадай число\n"
        "🎯 <b>Дартс</b> — попади в цель\n"
        "🏀 <b>Баскетбол</b> — забей мяч\n"
        "⚽️ <b>Футбол</b> — попади в ворота\n"
        "🎳 <b>Боулинг</b> — сбей кегли\n\n"
        f"💰 Минимальная ставка: <b>{MIN_BET} USD</b>\n"
        f"💼 Комиссия казино: <b>10%</b> (вычитается из депозита)",
        reply_markup=get_games_menu(),
        parse_mode="HTML"
    )
    await callback.answer()