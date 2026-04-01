# paper_trader.py
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from config import settings

logger = logging.getLogger(__name__)

class PaperTrader:
    def __init__(self, state_file: str = None):
        self.state_file = state_file or settings.PAPER_STATE_FILE
        self.state = self._load_state()
        self._last_daily_summary = self.state.get('last_daily_summary', None)

    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'capital': settings.PAPER_BALANCE,
            'positions': {},
            'trades': [],
            'last_daily_summary': None
        }

    def _save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)

    def get_capital(self) -> float:
        return self.state['capital']

    def get_positions(self) -> Dict:
        return self.state['positions']

    def get_trades(self) -> List:
        return self.state['trades']

    def execute_signal(self, signal: dict) -> bool:
        symbol = signal['symbol']
        if symbol in self.state['positions']:
            logger.info(f"Position already exists for {symbol}, ignoring signal")
            return False

        entry = signal['entry']
        stop = signal['stop_loss']
        target = signal['take_profit']
        direction = signal['direction']

        risk_amount = self.state['capital'] * settings.RISK_PER_TRADE_PCT
        stop_distance = abs(entry - stop)
        if stop_distance <= 0:
            return False
        qty = risk_amount / stop_distance
        min_qty = 0.001 if 'BTC' in symbol else 1.0
        qty = max(qty, min_qty)

        commission = qty * entry * settings.COMMISSION_PCT
        if commission > self.state['capital']:
            return False

        self.state['capital'] -= commission
        self.state['positions'][symbol] = {
            'symbol': symbol,
            'direction': direction,
            'entry': entry,
            'stop': stop,
            'target': target,
            'qty': qty,
            'open_time': datetime.now(timezone.utc).isoformat(),
            'confidence': signal.get('confidence', 70)
        }
        self._save_state()
        logger.info(f"PAPER: Opened {direction} {symbol} @ {entry:.2f}, qty={qty:.4f}")
        return True

    def update_positions(self, current_prices: Dict[str, float]):
        closed = []
        capital = self.state['capital']
        for symbol, pos in list(self.state['positions'].items()):
            price = current_prices.get(symbol)
            if not price:
                continue
            direction = pos['direction']
            sl_hit = (direction == "LONG" and price <= pos['stop']) or \
                     (direction == "SHORT" and price >= pos['stop'])
            tp_hit = (direction == "LONG" and price >= pos['target']) or \
                     (direction == "SHORT" and price <= pos['target'])
            if sl_hit or tp_hit:
                if direction == "LONG":
                    pnl = (price - pos['entry']) * pos['qty']
                else:
                    pnl = (pos['entry'] - price) * pos['qty']
                pnl -= pos['qty'] * price * settings.COMMISSION_PCT
                capital += pnl
                closed_trade = {
                    'symbol': symbol,
                    'direction': direction,
                    'entry': pos['entry'],
                    'exit': price,
                    'qty': pos['qty'],
                    'pnl': pnl,
                    'exit_time': datetime.now(timezone.utc).isoformat(),
                    'reason': 'SL' if sl_hit else 'TP'
                }
                self.state['trades'].append(closed_trade)
                closed.append(symbol)
                logger.info(f"PAPER: Closed {symbol} {direction} @ {price:.2f}, PnL={pnl:.2f}")
        for sym in closed:
            del self.state['positions'][sym]
        self.state['capital'] = capital
        self._save_state()

    def get_portfolio_summary(self) -> dict:
        return {
            'cash': self.state['capital'],
            'open_positions': len(self.state['positions']),
            'total_trades': len(self.state['trades']),
            'closed_pnl': sum(t['pnl'] for t in self.state['trades']),
            'equity': self.state['capital']
        }

    def get_trade_history(self, limit: int = 20) -> List[dict]:
        return self.state['trades'][-limit:]

    def daily_summary(self) -> str:
        today = datetime.now(timezone.utc).date().isoformat()
        today_trades = [t for t in self.state['trades'] if t['exit_time'].startswith(today)]
        pnl_today = sum(t['pnl'] for t in today_trades)
        summary = (f"📊 *Daily Portfolio Summary* ({today})\n"
                   f"Initial capital: ₹{settings.PAPER_BALANCE:,.2f}\n"
                   f"Current cash: ₹{self.state['capital']:,.2f}\n"
                   f"Open positions: {len(self.state['positions'])}\n"
                   f"Trades today: {len(today_trades)}\n"
                   f"PnL today: ₹{pnl_today:+,.2f}\n"
                   f"Total realised PnL: ₹{sum(t['pnl'] for t in self.state['trades']):+,.2f}\n"
                   f"Equity (cash only): ₹{self.state['capital']:,.2f}")
        self._last_daily_summary = today
        return summary

    def should_send_daily_summary(self) -> bool:
        now = datetime.now(timezone.utc).date().isoformat()
        return self._last_daily_summary != now

    def reset_daily_flag(self):
        self.state['last_daily_summary'] = self._last_daily_summary
        self._save_state()