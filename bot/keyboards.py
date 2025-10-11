from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Главное меню
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎰 Играть")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )

# Меню игр
def get_games_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Кости", callback_data="game_dice"),
            InlineKeyboardButton(text="🎯 Дартс", callback_data="game_darts")
        ],
        [
            InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basketball"),
            InlineKeyboardButton(text="⚽️ Футбол", callback_data="game_football")
        ],
        [
            InlineKeyboardButton(text="🎳 Боулинг", callback_data="game_bowling")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
        ]
    ])

# Кнопка оплаты
def get_payment_btn(url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Оплатить 5 USDT", url=url)]
    ])

# Меню для костей
def get_dice_bet_types():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔺 Больше (4–5–6)", callback_data="dice_high"),
            InlineKeyboardButton(text="🔻 Меньше (1–2–3)", callback_data="dice_low")
        ],
        [
            InlineKeyboardButton(text="⚪️ Чётное (2–4–6)", callback_data="dice_even"),
            InlineKeyboardButton(text="⚫️ Нечётное (1–3–5)", callback_data="dice_odd")
        ],
        [
            InlineKeyboardButton(text="🎯 Точное число", callback_data="dice_exact")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")
        ]
    ])

def get_dice_exact_numbers():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(i), callback_data=f"dice_num_{i}") for i in range(1, 7)],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="game_dice")]
    ])

# Меню для дартса
def get_darts_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Красное", callback_data="darts_red"),
            InlineKeyboardButton(text="⚪️ Белое", callback_data="darts_white"),
            InlineKeyboardButton(text="🎯 Центр", callback_data="darts_6")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])

# Меню для баскетбола
def get_basketball_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Попадание", callback_data="basketball_goal"),
            InlineKeyboardButton(text="❌ Промах", callback_data="basketball_miss")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])

# Меню для футбола
def get_football_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Гол", callback_data="football_goal"),
            InlineKeyboardButton(text="❌ Мимо", callback_data="football_miss")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])

# Меню для боулинга
def get_bowling_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💥 Страйк", callback_data="bowling_strike"),
            InlineKeyboardButton(text="🎳 Не страйк", callback_data="bowling_miss")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
