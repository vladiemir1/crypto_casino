from .engine import TelegramDiceGame
from typing import Dict

class DartsGame(TelegramDiceGame):
    """
    🎯 Дартс (1-6)
    
    1 - Мимо (2.5x)
    2 - Красное (1.8x)
    3 - Белое (1.8x)
    4 - Красное (1.8x)
    5 - Белое (1.8x)
    6 - Центр/Bullseye (2.5x)
    """
    
    PAYOUTS = {
        1: 2.5,
        2: 1.8,
        3: 1.8,
        4: 1.8,
        5: 1.8,
        6: 2.5
    }
    
    def __init__(self, bet_amount: float, currency: str, bet_value: int):
        super().__init__(bet_amount, currency)
        if bet_value not in range(1, 7):
            raise ValueError("Bet value must be 1-6")
        self.bet_value = bet_value
    
    def get_emoji(self) -> str:
        return "🎯"
    
    def analyze_result(self, value: int, user_bet: dict) -> Dict:
        """Проверяет выигрыш"""
        
        result = "win" if value == self.bet_value else "loss"
        multiplier = self.PAYOUTS[self.bet_value] if result == "win" else 0
        payout = self.calculate_payout(multiplier)
        
        outcome_names = {
            1: "Мимо",
            2: "Красное",
            3: "Белое",
            4: "Красное",
            5: "Белое",
            6: "🎯 Центр!"
        }
        
        return {
            "result": result,
            "payout": payout,
            "multiplier": multiplier,
            "details": {
                "dart_value": value,
                "dart_outcome": outcome_names[value],
                "bet_value": self.bet_value,
                "bet_outcome": outcome_names[self.bet_value]
            }
        }