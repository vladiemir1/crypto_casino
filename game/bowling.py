from .engine import TelegramDiceGame
from typing import Dict

class BowlingGame(TelegramDiceGame):
    """
    🎳 Боулинг (1-6)
    
    1 - 0 кеглей (1.5x)
    2 - 1 кегля (2.0x)
    3 - 3 кегли (2.5x)
    4 - 4 кегли (3.0x)
    5 - 5 кеглей (3.5x)
    6 - Страйк! 6 кеглей (4.0x)
    """
    
    PAYOUTS = {
        1: 1.5,
        2: 2.0,
        3: 2.5,
        4: 3.0,
        5: 3.5,
        6: 4.0
    }
    
    KEGELS = {
        1: 0,
        2: 1,
        3: 3,
        4: 4,
        5: 5,
        6: 6
    }
    
    def __init__(self, bet_amount: float, currency: str, bet_value: int):
        super().__init__(bet_amount, currency)
        if bet_value not in range(1, 7):
            raise ValueError("Bet value must be 1-6")
        self.bet_value = bet_value
    
    def get_emoji(self) -> str:
        return "🎳"
    
    def analyze_result(self, value: int, user_bet: dict) -> Dict:
        """Проверяет выигрыш"""
        
        result = "win" if value == self.bet_value else "loss"
        multiplier = self.PAYOUTS[self.bet_value] if result == "win" else 0
        payout = self.calculate_payout(multiplier)
        
        return {
            "result": result,
            "payout": payout,
            "multiplier": multiplier,
            "details": {
                "value": value,
                "kegels_hit": self.KEGELS[value],
                "bet_value": self.bet_value,
                "bet_kegels": self.KEGELS[self.bet_value],
                "is_strike": value == 6
            }
        }