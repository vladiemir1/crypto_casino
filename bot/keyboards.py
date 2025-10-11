from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ==================== ГЛАВНОЕ МЕНЮ ====================

def get_main_menu():
    """Главное меню с кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎰 Играть")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

# ==================== МЕНЮ ИГР ====================

def get_games_menu():
    """Меню выбора игры"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎲 Кости", callback_data="game_dice")],
    [
        InlineKeyboardButton(text="🎯 Дартс", callback_data="game_darts"),
        InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basketball")
    ],
    [
        InlineKeyboardButton(text="⚽️ Футбол", callback_data="game_football"),
        InlineKeyboardButton(text="🎳 Боулинг", callback_data="game_bowling")
    ],
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
])
    return keyboard

# ==================== КОСТИ ====================

def get_dice_bet_types():
    """Типы ставок для костей"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="⬆️ Больше (4-5-6) - 1.8x", callback_data="dice_high"),
        InlineKeyboardButton(text="⬇️ Меньше (1-2-3) - 1.8x", callback_data="dice_low")
    ],
    [   InlineKeyboardButton(text="1️⃣ Нечетное - 1.8x", callback_data="dice_odd"),
        InlineKeyboardButton(text="2️⃣ Четное - 1.8x", callback_data="dice_even")
        
    ],
    [InlineKeyboardButton(text="🎯 Угадать число - 3.1x", callback_data="dice_exact")],
    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
])
    return keyboard

def get_dice_exact_numbers():
    """Выбор конкретного числа для костей"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1", callback_data="dice_num_1"),
            InlineKeyboardButton(text="2", callback_data="dice_num_2"),
            InlineKeyboardButton(text="3", callback_data="dice_num_3")
        ],
        [
            InlineKeyboardButton(text="4", callback_data="dice_num_4"),
            InlineKeyboardButton(text="5", callback_data="dice_num_5"),
            InlineKeyboardButton(text="6", callback_data="dice_num_6")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="game_dice")]
    ])
    return keyboard

# ==================== ДАРТС ====================

def get_darts_bet_types():
    """Типы ставок для дартс"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красное (2,4) - 1.8x", callback_data="darts_red")],
        [InlineKeyboardButton(text="⚪️ Белое (3,5) - 1.8x", callback_data="darts_white")],
        [InlineKeyboardButton(text="🎯 Центр (6) - 2.5x", callback_data="darts_6")],
        [InlineKeyboardButton(text="❌ Мимо (1) - 2.5x", callback_data="darts_1")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
    ])
    return keyboard

# ==================== БАСКЕТБОЛ ====================

def get_basketball_bet_types():
    """Типы ставок для баскетбола"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Гол (4-5) - 1.8x", callback_data="basketball_goal")],
        [InlineKeyboardButton(text="❌ Мимо (1-2-3) - 1.3x", callback_data="basketball_miss")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
    ])
    return keyboard

# ==================== ФУТБОЛ ====================  ✅ ИСПРАВЛЕНО!

def get_football_bet_types():  # ОШИБКА: опечатка в названии (ф вместо f)
    """Типы ставок для футбола"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Гол (4-5) - 1.8x", callback_data="football_goal")],  # ✅ ИСПРАВЛЕНО: было 1.3x
        [InlineKeyboardButton(text="❌ Мимо (1-2-3) - 1.3x", callback_data="football_miss")],  # ✅ ИСПРАВЛЕНО: было 1.8x
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
    ])
    return keyboard

# ==================== БОУЛИНГ ====================

def get_bowling_bet_types():
    """Типы ставок для боулинга"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎳 Страйк (6) - 4.0x", callback_data="bowling_strike")],
        [InlineKeyboardButton(text="❌ Не страйк (1-5) - 1.2x", callback_data="bowling_nonstrike")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_games")]
    ])
    return keyboard

# ==================== СУММА СТАВКИ ====================  ✅ НОВОЕ!

def get_amount_keyboard():
    """Быстрые кнопки для выбора суммы"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="0.5 USDT", callback_data="amount_0.5"),
            InlineKeyboardButton(text="1 USDT", callback_data="amount_1"),
            InlineKeyboardButton(text="5 USDT", callback_data="amount_5")
        ],
        [
            InlineKeyboardButton(text="10 USDT", callback_data="amount_10"),
            InlineKeyboardButton(text="50 USDT", callback_data="amount_50"),
            InlineKeyboardButton(text="100 USDT", callback_data="amount_100")
        ],
        [InlineKeyboardButton(text="✍️ Своя сумма", callback_data="amount_custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    return keyboard

# ==================== ВАЛЮТА ====================  ✅ НОВОЕ!

def get_currency_keyboard():
    """Выбор валюты для оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
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
        [InlineKeyboardButton(text="BUSD", callback_data="currency_BUSD")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    return keyboard