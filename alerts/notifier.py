# alerts/notifier.py
import asyncio
import logging
from typing import Optional
from plyer import notification
from telegram import Bot
from config import settings
from paper_trader import PaperTrader

logger = logging.getLogger(__name__)

class AlertNotifier:
    def __init__(self, paper_trader: Optional[PaperTrader] = None):
        self.paper_trader = paper_trader
        self.bot = None
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            logger.info("Telegram bot ready for sending messages")

    async def send_startup_message(self):
        if self.bot and settings.TELEGRAM_CHAT_ID:
            try:
                text = (
                    "🤖 *Apex Trading Bot Started*\n"
                    f"Mode: {'PAPER' if settings.PAPER_TRADING else 'LIVE'}\n"
                    f"Symbols: {', '.join(settings.SYMBOLS)}\n"
                    f"Timeframes: {settings.TIMEFRAMES}\n"
                    f"Initial capital: ₹{settings.PAPER_BALANCE:,.2f}\n"
                    "Waiting for signals..."
                )
                await self.bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text=text, parse_mode='Markdown')
                logger.info("Startup message sent to Telegram")
            except Exception as e:
                logger.error(f"Failed to send startup message: {e}")

    async def send_alert(self, signal: dict):
        message = self._format_message(signal)
        if self.bot and settings.TELEGRAM_CHAT_ID:
            try:
                await self.bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Telegram send error: {e}")
        try:
            notification.notify(
                title=f"🚀 {signal['direction']} {signal['symbol']}",
                message=message[:200],
                timeout=10
            )
        except Exception as e:
            logger.debug(f"Desktop notification failed: {e}")
        logger.info(f"ALERT: {message}")

    async def send_text(self, text: str):
        if self.bot and settings.TELEGRAM_CHAT_ID:
            try:
                await self.bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text=text, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Telegram send error: {e}")

    def _format_message(self, signal: dict) -> str:
        return (f"🚀 *{signal['direction']}* `{signal['symbol']}`\n"
                f"Entry: `{signal['entry']:.2f}`\n"
                f"Stop: `{signal['stop_loss']:.2f}`\n"
                f"Target: `{signal['take_profit']:.2f}`\n"
                f"RR: `1:{signal['rr_ratio']}`\n"
                f"Confidence: `{signal['confidence']}`\n"
                f"Reasons: {', '.join(signal['reasons'])}")