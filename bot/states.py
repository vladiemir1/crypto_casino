from aiogram.fsm.state import State, StatesGroup

class BetFlow(StatesGroup):
    """FSM состояния для процесса ставки"""
    choosing_game = State()
    choosing_bet_type = State()
    entering_amount = State()
    choosing_currency = State()
    awaiting_payment = State()
