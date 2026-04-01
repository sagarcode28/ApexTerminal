# alerts/notifier.py
import asyncio
import logging
import threading
from typing import Optional
from plyer import notification
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from config import settings
from paper_trader import PaperTrader

logger = logging.getLogger(__name__)

class AlertNotifier:
    def __init__(self, paper_trader: Optional[PaperTrader] = None):
        self.paper_trader = paper_trader
        self.bot = None
        self.app = None
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            self.app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("portfolio", self.cmd_portfolio))
            self.app.add_handler(CommandHandler("trades", self.cmd_trades))
            self.app.add_handler(CommandHandler("summary", self.cmd_summary))
            logger.info("Telegram bot ready for sending messages")

    def start_polling(self):
        """Start the bot polling in a background thread."""
        if self.app:
            def run():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.app.run_polling())
                except Exception as e:
                    logger.error(f"Telegram polling error: {e}")
                finally:
                    loop.close()
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            logger.info("Telegram bot polling started in background thread")

    async def cmd_start(self, update, context):
        await update.message.reply_text("🤖 Apex Paper Trading Bot active.\nUse /portfolio, /trades, /summary")

    async def cmd_portfolio(self, update, context):
        if not self.paper_trader:
            await update.message.reply_text("Paper trader not active.")
            return
        summary = self.paper_trader.get_portfolio_summary()
        text = (f"💰 *Portfolio*\n"
                f"Cash: ₹{summary['cash']:,.2f}\n"
                f"Open positions: {summary['open_positions']}\n"
                f"Total trades: {summary['total_trades']}\n"
                f"Closed P&L: ₹{summary['closed_pnl']:+,.2f}")
        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_trades(self, update, context):
        if not self.paper_trader:
            await update.message.reply_text("Paper trader not active.")
            return
        trades = self.paper_trader.get_trade_history(limit=10)
        if not trades:
            await update.message.reply_text("No trades yet.")
            return
        text = "📋 *Recent Trades*\n"
        for t in trades:
            text += f"{t['exit_time'][:10]} {t['direction']} {t['symbol']} {t['pnl']:+.2f} ({t['reason']})\n"
        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_summary(self, update, context):
        if not self.paper_trader:
            await update.message.reply_text("Paper trader not active.")
            return
        text = self.paper_trader.daily_summary()
        await update.message.reply_text(text, parse_mode='Markdown')

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