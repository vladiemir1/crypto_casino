from abc import ABC, abstractmethod
from typing import Dict
from aiogram.types import Message

class TelegramDiceGame(ABC):
    """Базовый класс для игр на основе Telegram Dice"""
    
    PAYOUTS = {}
    
    def __init__(self, bet_amount: float, currency: str):
        self.bet_amount = bet_amount
        self.currency = currency
        self.house_edge = 0.10  # 10% комиссия казино (было 0.05)
    
    @abstractmethod
    def get_emoji(self) -> str:
        """Возвращает эмодaзи для игры"""
        pass
    
    @abstractmethod
    def analyze_result(self, value: int, user_bet: dict) -> Dict:
        """Анализирует результат игры"""
        pass
    
    def calculate_payout(self, multiplier: float) -> float:
        """
        Рассчитать выплату с учетом комиссии 10% ОТ ДЕПОЗИТА.
        
        Пример:
        - Депозит: 1.00 USD
        - Комиссия: 0.10 USD (вычитается сразу)
        - Чистая ставка: 0.90 USD
        - При выигрыше 2.0x: 0.90 * 2.0 = 1.80 USD
        """
        if multiplier == 0:
            return 0
        
        # Вычитаем комиссию ИЗ СТАВКИ (не из выигрыша!)
        net_bet = self.bet_amount * (1 - self.house_edge)
        payout = net_bet * multiplier
        return round(payout, 2)