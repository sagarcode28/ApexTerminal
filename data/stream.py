# data/stream.py
import asyncio
import json
import logging
from typing import List, Callable, Awaitable, Dict
import websockets

logger = logging.getLogger(__name__)

class BybitKlineStream:
    def __init__(self, symbols: List[str], timeframe: str):
        self.symbols = symbols
        self.timeframe = timeframe
        self.ws_url = "wss://stream.bybit.com/v5/public/spot"
        self.callbacks: List[Callable[[Dict], Awaitable[None]]] = []
        self.websocket = None
        self._stop = False

    def on_kline(self, callback: Callable[[Dict], Awaitable[None]]):
        self.callbacks.append(callback)

    async def connect(self):
        # Subscribe to kline topics for all symbols
        subscribe_msg = {
            "op": "subscribe",
            "args": [f"kline.{self.timeframe}.{s}" for s in self.symbols]
        }
        logger.info(f"Connecting to Bybit WebSocket for {self.timeframe} minute candles")
        while not self._stop:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self.websocket = ws
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(f"Connected to Bybit WebSocket for {self.timeframe}")
                    async for message in ws:
                        if self._stop:
                            break
                        data = json.loads(message)
                        # Bybit kline push format
                        if 'topic' in data and 'data' in data:
                            topic = data['topic']
                            # topic: "kline.15.BTCUSDT"
                            parts = topic.split('.')
                            tf = parts[1]
                            symbol = parts[2]
                            k = data['data'][0]   # list of one kline
                            candle = {
                                'symbol': symbol,
                                'open': float(k['open']),
                                'high': float(k['high']),
                                'low': float(k['low']),
                                'close': float(k['close']),
                                'volume': float(k['volume']),
                                'timestamp': k['start'],
                                'is_closed': k['confirm']  # true when closed
                            }
                            if candle['is_closed']:
                                for cb in self.callbacks:
                                    await cb(candle)
            except Exception as e:
                logger.error(f"Error in WebSocket: {e}")
                if not self._stop:
                    await asyncio.sleep(5)

    def stop(self):
        self._stop = True
        if self.websocket:
            asyncio.create_task(self.websocket.close())