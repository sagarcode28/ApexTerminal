# data/stream.py
import asyncio
import logging
from typing import List, Callable, Awaitable, Dict
import ccxt

logger = logging.getLogger(__name__)

class BinancePollingFeed:
    def __init__(self, symbols: List[str], timeframe: str):
        self.symbols = symbols
        self.timeframe = timeframe
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.callbacks: List[Callable[[Dict], Awaitable[None]]] = []
        self._stop = False
        self._last_candle_times = {}  # symbol -> timestamp of last processed candle

    def on_kline(self, callback: Callable[[Dict], Awaitable[None]]):
        self.callbacks.append(callback)

    async def _poll(self):
        while not self._stop:
            try:
                for symbol in self.symbols:
                    # Fetch the latest 2 candles to detect new closed candles
                    candles = await asyncio.get_event_loop().run_in_executor(
                        None, self.exchange.fetch_ohlcv, symbol, self.timeframe, None, 2
                    )
                    if not candles:
                        continue
                    # The last candle may still be open; we only process closed ones
                    for candle in candles:
                        ts = candle[0]
                        is_closed = (ts + self.exchange.parse_timeframe(self.timeframe)*1000) <= self.exchange.milliseconds()
                        if is_closed:
                            last_ts = self._last_candle_times.get(symbol)
                            if last_ts is None or ts > last_ts:
                                self._last_candle_times[symbol] = ts
                                candle_dict = {
                                    'symbol': symbol,
                                    'open': candle[1],
                                    'high': candle[2],
                                    'low': candle[3],
                                    'close': candle[4],
                                    'volume': candle[5],
                                    'timestamp': ts,
                                    'is_closed': True
                                }
                                for cb in self.callbacks:
                                    await cb(candle_dict)
                await asyncio.sleep(60)  # poll every 60 seconds
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(10)

    async def connect(self):
        await self._poll()

    def stop(self):
        self._stop = True