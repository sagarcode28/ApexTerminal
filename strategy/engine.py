# strategy/engine.py
import pandas as pd
import logging
from typing import Optional, Dict, Any
from indicators.calculator import IndicatorCalculator
from config import settings

logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self):
        self.calc = IndicatorCalculator()
        self._cache = {}
        self._last_signal_time = {}

    async def process_candle(self, symbol: str, candle: dict, tf: str):
        key = f"{symbol}_{tf}"
        if key not in self._cache:
            self._cache[key] = []
        self._cache[key].append(candle)
        if len(self._cache[key]) > 500:
            self._cache[key] = self._cache[key][-500:]

        if tf == settings.TIMEFRAMES['entry']:
            await self._check_signal(symbol)

    async def _check_signal(self, symbol: str):
        df_15m = self._build_df(symbol, settings.TIMEFRAMES['entry'])
        df_1h = self._build_df(symbol, settings.TIMEFRAMES['intermediate'])
        df_4h = self._build_df(symbol, settings.TIMEFRAMES['trend'])
        if df_15m is None or df_1h is None or df_4h is None:
            return
        if len(df_15m) < 50 or len(df_1h) < 50 or len(df_4h) < 50:
            return

        df_15m = self._add_indicators(df_15m)
        df_1h = self._add_indicators(df_1h)
        df_4h = self._add_indicators(df_4h)

        # 1. 4H trend (EMA50 > EMA200)
        ema50_4h = df_4h['ema50'].iloc[-1]
        ema200_4h = df_4h['ema200'].iloc[-1]
        if ema50_4h > ema200_4h:
            trend_4h = "bullish"
        elif ema50_4h < ema200_4h:
            trend_4h = "bearish"
        else:
            trend_4h = "neutral"
        if trend_4h == "neutral":
            return

        # 2. 1H ADX
        adx_1h = df_1h['adx'].iloc[-1]
        if adx_1h < settings.MIN_ADX:
            return

        # 3. 15m volume spike
        last_15m = df_15m.iloc[-1]
        vol_ratio = last_15m['volume'] / df_15m['volume_ma'].iloc[-1]
        if vol_ratio < settings.MIN_VOLUME_RATIO:
            return

        # 4. 15m entry
        rsi_15m = last_15m['rsi']
        if trend_4h == "bullish":
            if not (last_15m['close'] > last_15m['ema21'] and 40 < rsi_15m < 70):
                return
            direction = "LONG"
        else:
            if not (last_15m['close'] < last_15m['ema21'] and 30 < rsi_15m < 60):
                return
            direction = "SHORT"

        # Confidence
        confidence = 70
        if vol_ratio > 1.5:
            confidence += 10
        if adx_1h > 30:
            confidence += 10
        if confidence < settings.MIN_CONFIDENCE:
            return

        # Avoid duplicate signals within 5 minutes
        now = pd.Timestamp.utcnow()
        last_signal = self._last_signal_time.get(symbol)
        if last_signal and (now - last_signal).total_seconds() < 300:
            logger.debug(f"Duplicate signal for {symbol} – skipping")
            return
        self._last_signal_time[symbol] = now

        # Levels
        entry = last_15m['close']
        atr = last_15m['atr']
        stop_dist = atr * settings.ATR_STOP_MULT
        if direction == "LONG":
            stop = entry - stop_dist
            target = entry + stop_dist * settings.RR_RATIO
        else:
            stop = entry + stop_dist
            target = entry - stop_dist * settings.RR_RATIO

        signal = {
            'symbol': symbol,
            'direction': direction,
            'entry': round(entry, 2),
            'stop_loss': round(stop, 2),
            'take_profit': round(target, 2),
            'rr_ratio': settings.RR_RATIO,
            'confidence': confidence,
            'timestamp': now.isoformat(),
            'reasons': [f"{trend_4h} trend", f"ADX {adx_1h:.0f}",
                        f"Volume spike {vol_ratio:.1f}x", f"RSI {rsi_15m:.0f}"]
        }
        await self._emit_signal(signal)

    async def _emit_signal(self, signal):
        # To be overwritten by main system (we set a placeholder)
        logger.info(f"Signal ready: {signal['symbol']} {signal['direction']}")

    def _build_df(self, symbol: str, tf: str) -> Optional[pd.DataFrame]:
        key = f"{symbol}_{tf}"
        if key not in self._cache:
            return None
        candles = self._cache[key]
        if not candles:
            return None
        df = pd.DataFrame(candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df['ema21'] = self.calc.ema(df['close'], 21)
        df['ema50'] = self.calc.ema(df['close'], 50)
        df['ema200'] = self.calc.ema(df['close'], 200)
        df['volume_ma'] = df['volume'].rolling(20).mean()
        df['rsi'] = self.calc.rsi(df['close'], 14)
        df['atr'] = self.calc.atr(df, 14)
        df['adx'] = self.calc.adx(df, 14)
        return df