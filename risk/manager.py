import logging
from datetime import datetime, timedelta
from collections import defaultdict
from config import settings

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, initial_capital):
        self.capital = initial_capital
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset = datetime.utcnow().date()
        self.open_positions = {}  # symbol -> position dict

    def can_trade(self, signal) -> bool:
        """Check daily limits, open positions, and capital."""
        today = datetime.utcnow().date()
        if today > self.last_reset:
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset = today

        if self.daily_trades >= settings.MAX_TRADES_PER_DAY:
            return False, "Daily trade limit reached"

        if self.daily_pnl / self.capital <= settings.DAILY_STOP_LOSS_PCT:
            return False, "Daily stop loss hit"

        if len(self.open_positions) >= settings.MAX_OPEN_POSITIONS:
            return False, "Max positions"

        return True, "OK"

    def calculate_position_size(self, entry: float, stop: float) -> float:
        """Calculate quantity based on risk per trade."""
        risk_amount = self.capital * settings.RISK_PER_TRADE_PCT
        stop_distance = abs(entry - stop)
        if stop_distance <= 0:
            return 0
        qty = risk_amount / stop_distance
        # Round to exchange lot size (simplified)
        return round(qty, 3)

    def update_pnl(self, pnl: float):
        self.capital += pnl
        self.daily_pnl += pnl

    def add_position(self, symbol: str, position: dict):
        self.open_positions[symbol] = position

    def remove_position(self, symbol: str):
        if symbol in self.open_positions:
            del self.open_positions[symbol]