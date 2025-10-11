from abc import ABC, abstractmethod
from typing import Dict
from aiogram.types import Message

class TelegramDiceGame(ABC):
    """Базовый класс для игр на основе Telegram Dice"""
    
    PAYOUTS = {}
    
    def __init__(self, bet_amount: float, currency: str):
        self.bet_amount = bet_amount
        self.currency = currency
        self.house_edge = 0.05  # 5% преимущество дома
    
    @abstractmethod
    def get_emoji(self) -> str:
        """Возвращает эмодзи для игры"""
        pass
    
    @abstractmethod
    def analyze_result(self, value: int, user_bet: dict) -> Dict:
        """Анализирует результат игры"""
        pass
    
    def calculate_payout(self, multiplier: float) -> float:
        """Рассчитать выплату с учетом house edge"""
        if multiplier == 0:
            return 0
        return round(self.bet_amount * multiplier * (1 - self.house_edge), 2)