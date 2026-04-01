# config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Exchange
    EXCHANGE_ID: str = "binance"
    API_KEY: str = ""
    API_SECRET: str = ""

    # Symbols and timeframes
    SYMBOLS: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
    TIMEFRAMES: dict = {"entry": "15m", "intermediate": "1h", "trend": "4h"}

    # Risk
    RISK_PER_TRADE_PCT: float = 0.01
    MAX_OPEN_POSITIONS: int = 2
    MAX_TRADES_PER_DAY: int = 3
    DAILY_STOP_LOSS_PCT: float = -0.03
    DAILY_PROFIT_TARGET_PCT: float = 0.05
    COMMISSION_PCT: float = 0.0005

    # Strategy
    MIN_ADX: float = 25.0
    MIN_VOLUME_RATIO: float = 1.2
    MIN_CONFIDENCE: int = 75
    ATR_STOP_MULT: float = 1.5
    RR_RATIO: float = 2.0

    # Alerts
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Paper trading
    PAPER_TRADING: bool = True
    PAPER_BALANCE: float = 10000.0
    PAPER_STATE_FILE: str = os.getenv("PAPER_STATE_FILE", "paper_state.json")

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()