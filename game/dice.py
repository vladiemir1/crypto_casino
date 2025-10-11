from .engine import TelegramDiceGame
from typing import Dict

class DiceGame(TelegramDiceGame):
    """
    🎲 Кости (1-6)
    
    Варианты ставок:
    - Больше/Меньше (4-5-6 / 1-2-3) - x1.9
    - Четное/Нечетное - x1.9
    - Конкретное число - x5.5
    """
    
    def __init__(self, bet_amount: float, currency: str, bet_type: str, bet_value=None):
        super().__init__(bet_amount, currency)
        self.bet_type = bet_type  # 'high_low', 'even_odd', 'exact'
        self.bet_value = bet_value
    
    def get_emoji(self) -> str:
        return "🎲"
    
    def analyze_result(self, value: int, user_bet: dict) -> Dict:
        """Проверяет выигрыш"""
        
        result = "loss"
        multiplier = 0
        details = {"dice_value": value, "bet_type": self.bet_type, "bet_value": self.bet_value}
        
        if self.bet_type == "high_low":
            if self.bet_value == "high" and value in [4, 5, 6]:
                result = "win"
                multiplier = 1.9
            elif self.bet_value == "low" and value in [1, 2, 3]:
                result = "win"
                multiplier = 1.9
        
        elif self.bet_type == "even_odd":
            if self.bet_value == "even" and value % 2 == 0:
                result = "win"
                multiplier = 1.9
            elif self.bet_value == "odd" and value % 2 != 0:
                result = "win"
                multiplier = 1.9
        
        elif self.bet_type == "exact":
            if value == self.bet_value:
                result = "win"
                multiplier = 5.5
        
        payout = self.calculate_payout(multiplier)
        
        return {
            "result": result,
            "payout": payout,
            "multiplier": multiplier,
            "details": details
        }