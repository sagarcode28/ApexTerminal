# data/stream.py
import asyncio
import json
import logging
from typing import List, Callable, Awaitable, Dict
import websockets

logger = logging.getLogger(__name__)

class BinanceKlineStream:
    def __init__(self, symbols: List[str], timeframe: str):
        self.symbols = symbols
        self.timeframe = timeframe
        self.ws_url = "wss://stream.binance.com:9443/stream"
        self.stream_names = []
        self.symbol_map = {}
        for s in symbols:
            stream_name = s.replace('/', '').lower()
            self.stream_names.append(f"{stream_name}@kline_{timeframe}")
            self.symbol_map[stream_name] = s
        self.callbacks: List[Callable[[Dict], Awaitable[None]]] = []
        self.websocket = None
        self._stop = False

    def on_kline(self, callback: Callable[[Dict], Awaitable[None]]):
        self.callbacks.append(callback)

    async def connect(self):
        streams = "/".join(self.stream_names)
        uri = f"{self.ws_url}?streams={streams}"
        logger.info(f"Connecting to {uri}")
        while not self._stop:
            try:
                async with websockets.connect(uri) as ws:
                    self.websocket = ws
                    logger.info(f"Connected to Binance WebSocket for {self.timeframe}")
                    async for message in ws:
                        if self._stop:
                            break
                        data = json.loads(message)
                        stream = data.get('stream', '')
                        kline_data = data['data']['k']
                        symbol_stream = stream.split('@')[0]
                        original_symbol = self.symbol_map.get(symbol_stream, symbol_stream)
                        candle = {
                            'symbol': original_symbol,
                            'open': float(kline_data['o']),
                            'high': float(kline_data['h']),
                            'low': float(kline_data['l']),
                            'close': float(kline_data['c']),
                            'volume': float(kline_data['v']),
                            'timestamp': kline_data['t'],
                            'is_closed': kline_data['x']
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