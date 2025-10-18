from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import uuid
import logging
from datetime import datetime
from sqlalchemy.sql import text
from aiocryptopay import Networks
from asyncio import sleep

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
    'dice_high': {'emoji': '🎲', 'name': 'КОСТИ: Больше', 'coef': '1.8x'},
    'dice_low': {'emoji': '🎲', 'name': 'КОСТИ: Меньше', 'coef': '1.8x'},
    'dice_odd': {'emoji': '🎲', 'name': 'КОСТИ: Нечетное', 'coef': '1.8x'},
    'dice_even': {'emoji': '🎲', 'name': 'КОСТИ: Четное', 'coef': '1.8x'},
    'dice_num_1': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 1', 'coef': '3.1x'},
    'dice_num_2': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 2', 'coef': '3.1x'},
    'dice_num_3': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 3', 'coef': '3.1x'},
    'dice_num_4': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 4', 'coef': '3.1x'},
    'dice_num_5': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 5', 'coef': '3.1x'},
    'dice_num_6': {'emoji': '🎲', 'name': 'КОСТИ: Угадать число 6', 'coef': '3.1x'},
    'darts_red': {'emoji': '🎯', 'name': 'ДАРТС: Красное', 'coef': '1.8x'},
    'darts_white': {'emoji': '🎯', 'name': 'ДАРТС: Белое', 'coef': '1.8x'},
    'darts_6': {'emoji': '🎯', 'name': 'ДАРТС: Центр', 'coef': '2.5x'},
    'darts_1': {'emoji': '🎯', 'name': 'ДАРТС: Мимо', 'coef': '2.5x'},
    'basketball_goal': {'emoji': '🏀', 'name': 'БАСКЕТБОЛ: Гол', 'coef': '1.8x'},
    'basketball_miss': {'emoji': '🏀', 'name': 'БАСКЕТБОЛ: Мимо', 'coef': '1.3x'},
    'football_goal': {'emoji': '⚽️', 'name': 'ФУТБОЛ: Гол', 'coef': '1.8x'},
    'football_miss': {'emoji': '⚽️', 'name': 'ФУТБОЛ: Мимо', 'coef': '1.3x'},
    'bowling_strike': {'emoji': '🎳', 'name': 'БОУЛИНГ: Страйк', 'coef': '4.0x'},
    'bowling_nonstrike': {'emoji': '🎳', 'name': 'БОУЛИНГ: Не страйк', 'coef': '1.2x'},
}

def get_game_description(game_type: str, amount: float = None) -> str:
    """Генерирует описание игры на основе game_type и суммы"""
    game_info = GAME_DESCRIPTIONS.get(game_type, {'emoji': '🎮', 'name': game_type, 'coef': '?'})
    description = f"{game_info['emoji']} <b>{game_info['name']}</b>\n⚡️ Коэффициент: <b>{game_info['coef']}</b>"
    if amount:
        description += f"\n\n💵 Сумма ставки: <b>{amount} USD</b>"
    return description

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
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при создании инвойса: {e}")
        await callback.message.edit_text(
            "Ошибка при создании счёта. Попробуй позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_amount")
            ]]),
            parse_mode="HTML"
        )
        await callback.answer("Ошибка", show_alert=True)

# ==================== СОЗДАНИЕ ИГРЫ И ИНВОЙСА ====================

async def create_game_and_invoice(callback: CallbackQuery, game_type: str, description: str, amount: float, currency: str, state: FSMContext):
    """Создаёт запись игры, инвойс и обновляет существующее сообщение"""
    async with async_session_maker() as session:
        user = await UserCRUD.get_or_create(
            session,
            telegram_id=callback.from_user.id,
            username=callback.from_user.username or "Unknown",
            first_name=callback.from_user.first_name or "User"
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

        try:
            invoice_response = await cryptobot.create_invoice(
                asset=currency,
                amount=str(amount),
                description=f"Ставка в казино: {game_type}"
            )
        except Exception as e:
            logger.error(f"Ошибка при создании инвойса: {e}")
            raise

        invoice_id = str(invoice_response.get('invoice_id') or invoice_response.get('id') or uuid.uuid4())
        pay_url = invoice_response.get('bot_invoice_url') or invoice_response.get('pay_url') or invoice_response.get('url')

        if not pay_url:
            logger.error("Не удалось получить URL для оплаты")
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

        # Сохраняем ID сообщения и данные инвойса в state
        await state.update_data(
            invoice_message_id=callback.message.message_id,
            game_id=game_id,
            invoice_id=invoice_id,
            pay_url=pay_url,
            game_type=game_type,
            amount=amount,
            currency=currency,
            description=description
        )

        # Обновляем существующее сообщение
        try:
            await callback.message.edit_text(
                f"<b>✅ Счёт создан!</b>\n\n"
                f"<blockquote>🎮 Игра: <b>{game_info['name']}</b>\n"
                f"⚡️ Коэффициент: <b>{game_info['coef']}</b>\n"
                f"💵 Сумма ставки: <b>{amount} {currency}</b>\n"
                f"💼 Комиссия казино: <b>{commission:.4f} {currency}</b> (10%)\n"
                f"🚀 Чистая ставка: <b>{net_bet:.4f} {currency}</b></blockquote>\n\n"
                f"Оплати счёт по кнопке ниже:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="💳 Оплатить", url=pay_url),
                    
                ]]),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            # Fallback: отправляем новое сообщение
            new_message = await callback.message.answer(
                f"<b>Счёт создан!</b>\n\n"
                f"<blockquote>🎮 Игра: <b>{game_info['name']}</b>\n"
                f"⚡️ Коэффициент: <b>{game_info['coef']}</b>\n\n"
                f"💵 Сумма ставки: <b>{amount} {currency}</b>\n"
                f"💼 Комиссия казино: <b>{commission:.4f} {currency}</b> (10%)\n"
                f"🚀 Чистая ставка: <b>{net_bet:.4f} {currency}</b></blockquote>\n\n"
                f"Оплати счёт по кнопке ниже:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="💳 Оплатить", url=pay_url),
                    
                ]]),
                parse_mode="HTML"
            )
            # Сохраняем ID нового сообщения
            await state.update_data(invoice_message_id=new_message.message_id)

# ==================== ПРОВЕРКА ОПЛАТЫ ====================

@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: CallbackQuery, state: FSMContext):
    invoice_id = callback.data.replace("check_payment_", "")
    data = await state.get_data()
    message_id = data.get("invoice_message_id")
    game_id = data.get("game_id")
    game_type = data.get("game_type")
    amount = data.get("amount")
    currency = data.get("currency")
    description = data.get("description")
    pay_url = data.get("pay_url")

    if not all([message_id, game_id, game_type, amount, currency, pay_url]):
        await callback.message.edit_text(
            "Ошибка: данные для проверки отсутствуют. Попробуй снова.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_main")
            ]]),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    async with async_session_maker() as session:
        transaction = await TransactionCRUD.get_by_invoice_id(session, invoice_id)
        if not transaction:
            await callback.message.edit_text(
                "Ошибка: транзакция не найдена.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_main")
                ]]),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        try:
            # Используем метод get_invoices для проверки статуса инвойса
            invoice_response = await cryptobot.get_invoices(invoice_ids=invoice_id)
            logger.info(f"Ответ от CryptoBot API: {invoice_response}")
            invoice_data = invoice_response.get("result", [{}])[0]
            invoice_status = invoice_data.get("status")

            if invoice_status != "paid":
                await callback.message.edit_text(
                    f"Ожидаем оплату...\n\n"
                    f"{description}\n\n"
                    f"💵 Сумма ставки: <b>{amount} {currency}</b>\n"
                    f"Статус: <b>Ожидает оплаты</b>",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="💳 Оплатить", url=pay_url),
                        InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}"),
                        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
                    ]]),
                    parse_mode="HTML"
                )
                await callback.answer("Счёт ещё не оплачен")
                return

            # Если оплата подтверждена, обновляем статус транзакции
            await TransactionCRUD.update_status(session, invoice_id, TransactionStatus.PAID)
            await session.commit()

            await callback.message.edit_text(
                f"Оплата подтверждена!\n\n"
                f"{description}\n\n"
                f"💵 Сумма ставки: <b>{amount} {currency}</b>\n"
                f"Статус: <b>Оплачено</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_main")
                ]]),
                parse_mode="HTML"
            )
            await callback.answer("Оплата успешно подтверждена!")
            await state.clear()

        except Exception as e:
            logger.error(f"Ошибка при проверке оплаты: {e}")
            await callback.message.edit_text(
                "Ошибка при проверке оплаты. Попробуй снова.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_main")
                ]]),
                parse_mode="HTML"
            )
            await callback.answer("Произошла ошибка. Попробуй снова.")

# ==================== НАВИГАЦИЯ НАЗАД ====================

@router.callback_query(F.data.startswith("back_to_bet_"))
async def back_to_bet_selection(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору типа ставки из выбора суммы"""
    await state.clear()
    
    game_type = callback.data.replace("back_to_bet_", "")
    
    if game_type.startswith("dice"):
        if game_type.startswith("dice_num"):
            await callback.message.edit_text(
                "🎲 КОСТИ: Угадай число\n\n⚡️Коэффициент: 3.1x\nВыбери число:",
                reply_markup=get_dice_exact_numbers()
            )
        else:
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
        "Действие отменено.\n\nВыбери действие:",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "💻Выберите действие:",
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

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Регистрация пользователя при /start"""
    await state.clear()
    async with async_session_maker() as session:
        await UserCRUD.get_or_create(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username or "Unknown",
            first_name=message.from_user.first_name or "User"
        )

    await message.answer(
        "🎰 <b>Добро пожаловать в Crypto Casino!</b>\n\n"
        "🎮 Играй в честные Telegram-игры\n"
        "💰 Выигрывай криптовалюту\n"
        "⚡️ Мгновенные выплаты\n\n"
        "Все игры используют <b>Telegram Dice API</b> — результат генерируется Telegram!\n\n"
        "💻Выбери действие:",
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
        user = await UserCRUD.get_or_create(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username or "Unknown",
            first_name=message.from_user.first_name or "User"
        )
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
            f"🗂 Информация по пользователю <b>{username}</b>\n\n"
            f"⚙️ Статистика :\n"
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
    await callback.message.edit_text(
        "🎲 <b>КОСТИ</b>\n\nВыбери тип ставки:",
        reply_markup=get_dice_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_high")
async def dice_high_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "dice_high"
    await state.update_data(game_type=game_type, description="🎲 <b>КОСТИ: Больше </b>\n⚡️ Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎲 <b>КОСТИ: Больше </b>\n⚡️ Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_low")
async def dice_low_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "dice_low"
    await state.update_data(game_type=game_type, description="🎲 <b>КОСТИ: Меньше </b>\n⚡️ Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎲 <b>КОСТИ: Меньше </b>\n⚡️ Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_even")
async def dice_even_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "dice_even"
    await state.update_data(game_type=game_type, description="🎲 <b>КОСТИ: Четное </b>\n⚡️ Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎲 <b>КОСТИ: Четное </b>\n⚡️ Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "dice_odd")
async def dice_odd_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "dice_odd"
    await state.update_data(game_type=game_type, description="🎲 <b>КОСТИ: Нечетное </b>\n⚡️ Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎲 <b>КОСТИ: Нечетное </b>\n⚡️ Коэффициент: <b>1.8x</b>\n\n"
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
    await state.update_data(game_type=game_type, description=f"🎲 <b>КОСТИ: Угадать число {number}</b>\n⚡️ Коэффициент: <b>3.1x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        f"🎲 <b>КОСТИ: Угадать число {number}</b>\n⚡️ Коэффициент: <b>3.1x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== ДАРТС ====================

@router.callback_query(F.data == "game_darts")
async def game_darts(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 <b>ДАРТС</b>\n\nВыбери тип ставки:",
        reply_markup=get_darts_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_red")
async def darts_red_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "darts_red"
    await state.update_data(game_type=game_type, description="🎯 <b>ДАРТС: Красное </b>\n⚡️ Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎯 <b>ДАРТС: Красное </b>\n⚡️ Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_white")
async def darts_white_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "darts_white"
    await state.update_data(game_type=game_type, description="🎯 <b>ДАРТС: Белое </b>\n⚡️ Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎯 <b>ДАРТС: Белое </b>\n⚡️ Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_6")
async def darts_center_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "darts_6"
    await state.update_data(game_type=game_type, description="🎯 <b>ДАРТС: Центр </b>\n⚡️ Коэффициент: <b>2.5x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎯 <b>ДАРТС: Центр </b>\n⚡️ Коэффициент: <b>2.5x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "darts_1")
async def darts_miss_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "darts_1"
    await state.update_data(game_type=game_type, description="🎯 <b>ДАРТС: Мимо </b>\n⚡️ Коэффициент: <b>2.5x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎯 <b>ДАРТС: Мимо </b>\n⚡️ Коэффициент: <b>2.5x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== БАСКЕТБОЛ ====================

@router.callback_query(F.data == "game_basketball")
async def game_basketball(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏀 <b>БАСКЕТБОЛ</b>\n\nВыбери тип ставки:",
        reply_markup=get_basketball_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "basketball_goal")
async def basketball_goal_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "basketball_goal"
    await state.update_data(game_type=game_type, description="🏀 <b>БАСКЕТБОЛ: Гол </b>\n⚡️ Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🏀 <b>БАСКЕТБОЛ: Гол </b>\n⚡️ Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "basketball_miss")
async def basketball_miss_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "basketball_miss"
    await state.update_data(game_type=game_type, description="🏀 <b>БАСКЕТБОЛ: Мимо </b>\n⚡️ Коэффициент: <b>1.3x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🏀 <b>БАСКЕТБОЛ: Мимо </b>\n⚡️ Коэффициент: <b>1.3x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== ФУТБОЛ ====================

@router.callback_query(F.data == "game_football")
async def game_football(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚽️ <b>ФУТБОЛ</b>\n\nВыбери тип ставки:",
        reply_markup=get_football_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "football_goal")
async def football_goal_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "football_goal"
    await state.update_data(game_type=game_type, description="⚽️ <b>ФУТБОЛ: Гол </b>\n⚡️ Коэффициент: <b>1.8x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "⚽️ <b>ФУТБОЛ: Гол </b>\n⚡️ Коэффициент: <b>1.8x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "football_miss")
async def football_miss_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "football_miss"
    await state.update_data(game_type=game_type, description="⚽️ <b>ФУТБОЛ: Мимо </b>\n⚡️ Коэффициент: <b>1.3x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "⚽️ <b>ФУТБОЛ: Мимо </b>\n⚡️ Коэффициент: <b>1.3x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== БОУЛИНГ ====================

@router.callback_query(F.data == "game_bowling")
async def game_bowling(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎳 <b>БОУЛИНГ</b>\n\nВыбери тип ставки:",
        reply_markup=get_bowling_bet_types(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "bowling_strike")
async def bowling_strike_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "bowling_strike"
    await state.update_data(game_type=game_type, description="🎳 <b>БОУЛИНГ: Страйк </b>\n⚡️ Коэффициент: <b>4.0x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎳 <b>БОУЛИНГ: Страйк </b>\n⚡️ Коэффициент: <b>4.0x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "bowling_nonstrike")
async def bowling_nonstrike_bet(callback: CallbackQuery, state: FSMContext):
    game_type = "bowling_nonstrike"
    await state.update_data(game_type=game_type, description="🎳 <b>БОУЛИНГ: Не страйк </b>\n⚡️ Коэффициент: <b>1.2x</b>")
    await state.set_state(BetFlow.entering_amount)
    await callback.message.edit_text(
        "🎳 <b>БОУЛИНГ: Не страйк </b>\n⚡️ Коэффициент: <b>1.2x</b>\n\n"
        f"Выбери сумму ставки (минимум {MIN_BET} USD):",
        reply_markup=get_amount_keyboard(game_type),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== ОБРАБОТКА СУММЫ ====================

@router.callback_query(F.data.startswith("amount_"), BetFlow.entering_amount)
async def process_amount_button(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора суммы через кнопки"""
    logger.info(f"Обработка callback.data: {callback.data}")
    
    if callback.data == "amount_custom":
        await state.update_data(amount_message_id=callback.message.message_id)
        
        await callback.message.edit_text(
            f"✍️ Введи свою сумму (минимум {MIN_BET} USD):\n\n"
            "<i>Пример: 0.1 или 2.5 или 15</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_amount")
            ]]),
            parse_mode="HTML"
        )
        await state.update_data(request_message_id=callback.message.message_id)
        await callback.answer()
        return
    
    amount_str = callback.data.replace("amount_", "")
    try:
        amount = float(amount_str)
        logger.info(f"Выбрана сумма: {amount}")
    except ValueError as e:
        logger.error(f"Ошибка преобразования суммы: {amount_str}, ошибка: {e}")
        await callback.answer("Ошибка суммы. Попробуй снова.", show_alert=True)
        return

    if amount < MIN_BET:
        logger.warning(f"Сумма {amount} меньше минимальной ставки {MIN_BET}")
        await callback.answer(f"Минимум {MIN_BET} USD", show_alert=True)
        return

    await state.update_data(amount=amount)
    await state.set_state(BetFlow.choosing_currency)
    
    data = await state.get_data()
    description = data.get("description", "")
    game_type = data.get("game_type", "")
    
    if not game_type:
        logger.error("game_type отсутствует в состоянии")
        await callback.message.edit_text(
            "Ошибка: тип игры не найден. Попробуй начать заново.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_main")
            ]]),
            parse_mode="HTML"
        )
        await callback.answer("Ошибка", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            f"{description}\n\n"
            f"💵 Сумма ставки: <b>{amount} USD</b>\n"
            "Выбери валюту для оплаты:",
            reply_markup=get_currency_keyboard(game_type),
            parse_mode="HTML"
        )
        logger.info("Сообщение успешно отредактировано на выбор валюты")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await callback.message.answer(
            f"{description}\n\n"
            f"💵 Сумма ставки: <b>{amount} USD</b>\n"
            "Выбери валюту для оплаты:",
            reply_markup=get_currency_keyboard(game_type),
            parse_mode="HTML"
        )
        logger.info("Отправлено новое сообщение как fallback")
    
    await callback.answer()

@router.message(BetFlow.entering_amount, F.text.regexp(r'^\d*\.?\d+$'))
async def process_custom_amount(message: Message, state: FSMContext):
    """Обработка ввода пользовательской суммы"""
    try:
        amount = float(message.text)
        if amount < MIN_BET:
            await message.answer(
                f"Минимальная ставка — {MIN_BET} USD. Введи сумму заново.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_amount")
                ]]),
                parse_mode="HTML"
            )
            return
        await state.update_data(amount=amount)
        await state.set_state(BetFlow.choosing_currency)
        game_type = (await state.get_data()).get("game_type")
        description = get_game_description(game_type, amount=amount)
        data = await state.get_data()
        request_message_id = data.get("request_message_id")
        
        # Удаляем сообщение с пользовательским вводом
        try:
            await bot_instance.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения с пользовательским вводом: {e}")
        
        # Редактируем сообщение с запросом суммы на выбор валюты
        if request_message_id:
            try:
                await bot_instance.edit_message_text(
                    text=f"{description}\n"
                         f"Выбери валюту для оплаты:",
                    chat_id=message.chat.id,
                    message_id=request_message_id,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="USDT", callback_data="currency_USDT"),
                            InlineKeyboardButton(text="TON", callback_data="currency_TON"),
                            InlineKeyboardButton(text="BTC", callback_data="currency_BTC")
                        ],
                        [
                            InlineKeyboardButton(text="ETH", callback_data="currency_ETH"),
                            InlineKeyboardButton(text="LTC", callback_data="currency_LTC"),
                            InlineKeyboardButton(text="TRX", callback_data="currency_TRX")
                        ],
                        [
                            InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_amount")
                        ]
                    ]),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения с запросом суммы: {e}")
                # Fallback: отправляем новое сообщение
                await message.answer(
                    f"{description}\n"
                    f"Выбери валюту для оплаты:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="USDT", callback_data="currency_USDT"),
                            InlineKeyboardButton(text="TON", callback_data="currency_TON"),
                            InlineKeyboardButton(text="BTC", callback_data="currency_BTC")
                        ],
                        [
                            InlineKeyboardButton(text="ETH", callback_data="currency_ETH"),
                            InlineKeyboardButton(text="LTC", callback_data="currency_LTC"),
                            InlineKeyboardButton(text="TRX", callback_data="currency_TRX")
                        ],
                        [
                            InlineKeyboardButton(text="◔ Назад", callback_data="back_to_amount")
                        ]
                    ]),
                    parse_mode="HTML"
                )
    except ValueError:
        await message.answer(
            "Введи корректную сумму (например, 0.05).",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_amount")
            ]]),
            parse_mode="HTML"
        ) 