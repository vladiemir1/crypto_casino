from .engine import TelegramDiceGame
from typing import Dict

class BasketballGame(TelegramDiceGame):
    """
    🏀 Баскетбол (1-5)
    
    4-5 - Гол (1.8x)
    1-3 - Мимо (1.3x)
    """
    
    def __init__(self, bet_amount: float, currency: str, bet_type: str):
        super().__init__(bet_amount, currency)
        if bet_type not in ['goal', 'miss']:
            raise ValueError("Bet type must be 'goal' or 'miss'")
        self.bet_type = bet_type
    
    def get_emoji(self) -> str:
        return "🏀"
    
    def analyze_result(self, value: int, user_bet: dict) -> Dict:
        """Проверяет выигрыш"""
        
        is_goal = value in [4, 5]
        
        if (self.bet_type == "goal" and is_goal) or (self.bet_type == "miss" and not is_goal):
            result = "win"
            multiplier = 1.8 if self.bet_type == "goal" else 1.3
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
                "outcome": "Гол ✅" if is_goal else "Мимо ❌",
                "bet": self.bet_type
            }
        }