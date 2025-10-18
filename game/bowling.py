from .engine import TelegramDiceGame
from typing import Dict

class BowlingGame(TelegramDiceGame):
    """
    🎳 Боулинг (1-6)
    
    6 - Страйк (3.1x)
    1-5 - Не страйк (1.2x)
    """
    
    PAYOUTS = {
        1: 2.0,
        2: 2.0,
        3: 2.0,
        4: 2.0,
        5: 2.0,
        6: 3.1
    }
    
    KEGELS = {
        1: 0,
        2: 1,
        3: 3,
        4: 4,
        5: 5,
        6: 6
    }
    
    def __init__(self, bet_amount: float, currency: str, bet_type: str):
        super().__init__(bet_amount, currency)
        if bet_type not in ['strike', 'nonstrike']:
            raise ValueError("Bet type must be 'strike' or 'nonstrike'")
        self.bet_type = bet_type
    
    def get_emoji(self) -> str:
        return "🎳"
    
    def analyze_result(self, value: int, user_bet: dict) -> Dict:
        """Проверяет выигрыш"""
        
        is_strike = value == 6
        
        if (self.bet_type == "strike" and is_strike) or (self.bet_type == "nonstrike" and not is_strike):
            result = "win"
            multiplier = 3.1 if is_strike else 2.0
        else:
            result = "loss"
            multiplier = 0
        
        payout = self.calculate_payout(multiplier)
        
        return {
            "result": result,
            "payout": payout,
            "multiplier": multiplier,
            "details": {
                "value": value,
                "kegels_hit": self.KEGELS[value],
                "is_strike": is_strike
            }
        }