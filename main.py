# main.py
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask
from logs.logger import setup_logging
from config import settings
from data.stream import BinancePollingFeed
from strategy.engine import SignalGenerator
from paper_trader import PaperTrader
from alerts.notifier import AlertNotifier

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def health():
    return "OK", 200

def run_health_server():
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

class TradingSystem:
    def __init__(self):
        self.streams = {}
        self.signal_generator = SignalGenerator()
        self.paper_trader = PaperTrader() if settings.PAPER_TRADING else None
        self.notifier = AlertNotifier(paper_trader=self.paper_trader)
        self._stop = False

    async def on_kline(self, candle: dict, tf: str):
        symbol = candle['symbol']
        await self.signal_generator.process_candle(symbol, candle, tf)

    async def on_signal(self, signal: dict):
        if self.paper_trader and settings.PAPER_TRADING:
            executed = self.paper_trader.execute_signal(signal)
            if executed:
                await self.notifier.send_alert(signal)
                logger.info(f"Paper trade executed: {signal['symbol']} {signal['direction']}")
            else:
                logger.debug(f"Paper trade rejected: {signal['symbol']}")
        else:
            await self.notifier.send_alert(signal)

    async def update_positions(self):
        while not self._stop:
            try:
                if self.paper_trader and self.paper_trader.get_positions():
                    import aiohttp
                    current_prices = {}
                    for symbol in self.paper_trader.get_positions().keys():
                        symbol_clean = symbol.replace('/', '').lower()
                        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol_clean}"
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url) as resp:
                                data = await resp.json()
                                current_prices[symbol] = float(data['price'])
                    self.paper_trader.update_positions(current_prices)
            except Exception as e:
                logger.error(f"Position update error: {e}")
            await asyncio.sleep(60)

    async def daily_summary_sender(self):
        while not self._stop:
            now = datetime.now(timezone.utc)
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            wait_seconds = (midnight - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            if self.paper_trader and self.paper_trader.should_send_daily_summary():
                summary = self.paper_trader.daily_summary()
                await self.notifier.send_text(summary)
                self.paper_trader.reset_daily_flag()

    async def start(self):
        threading.Thread(target=run_health_server, daemon=True).start()
        logger.info("Health check server running on port 8000")

        for tf in settings.TIMEFRAMES.values():
            stream = BinancePollingFeed(settings.SYMBOLS, tf)
            stream.on_kline(lambda candle, tf=tf: self.on_kline(candle, tf))
            self.streams[tf] = stream
            asyncio.create_task(stream.connect())

        asyncio.create_task(self.update_positions())
        asyncio.create_task(self.daily_summary_sender())

        await asyncio.sleep(2)
        await self.notifier.send_startup_message()

        logger.info("Trading system started")
        while not self._stop:
            await asyncio.sleep(1)

    def stop(self):
        self._stop = True
        for stream in self.streams.values():
            stream.stop()

def run():
    system = TradingSystem()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(system.start())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        system.stop()
        loop.stop()

if __name__ == "__main__":
    run()