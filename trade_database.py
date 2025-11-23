"""
Trade database for storing all trade data, PnL, latency, duration, and history
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque

class TradeDatabase:
    """Database for storing and querying trade data"""
    
    def __init__(self, db_file: str = "trades.json"):
        self.db_file = db_file
        self.trades: List[Dict] = []
        self.errors: List[Dict] = []
        self.failed_trades: List[Dict] = []
        
        # Load existing data
        self._load_data()
        
        # Latency tracking (for time-based averages)
        self.latency_history = deque(maxlen=10000)  # Store last 10000 latencies with timestamps
        
    def _load_data(self):
        """Load data from JSON file"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get("trades", [])
                    self.errors = data.get("errors", [])
                    self.failed_trades = data.get("failed_trades", [])
                    
                    # Load latency history
                    latency_data = data.get("latency_history", [])
                    self.latency_history = deque(latency_data, maxlen=10000)
            except Exception as e:
                print(f"⚠️ Error loading trade database: {e}")
                self.trades = []
                self.errors = []
                self.failed_trades = []
    
    def _save_data(self):
        """Save data to JSON file"""
        try:
            data = {
                "trades": self.trades,
                "errors": self.errors,
                "failed_trades": self.failed_trades,
                "latency_history": list(self.latency_history)
            }
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Error saving trade database: {e}")
    
    def add_successful_trade(
        self,
        trade_id: str,
        timestamp: datetime,
        token_in: str,
        token_out: str,
        amount_in: float,
        amount_out: float,
        entry_price: float,
        exit_price: Optional[float] = None,
        is_buy: bool = True,
        latency_ms: float = 0.0,
        duration_seconds: Optional[float] = None,
        signature: Optional[str] = None,
        master_amount: Optional[float] = None,
        your_amount: Optional[float] = None
    ):
        """Add a successful trade"""
        trade = {
            "trade_id": trade_id,
            "timestamp": timestamp.isoformat(),
            "token_in": token_in,
            "token_out": token_out,
            "amount_in": amount_in,
            "amount_out": amount_out,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "is_buy": is_buy,
            "latency_ms": latency_ms,
            "duration_seconds": duration_seconds,
            "signature": signature,
            "master_amount": master_amount,
            "your_amount": your_amount,
            "status": "successful",
            "pnl": None,  # Will be calculated when exit
            "pnl_percentage": None
        }
        
        self.trades.append(trade)
        
        # Add to latency history
        self.latency_history.append({
            "timestamp": timestamp.isoformat(),
            "latency_ms": latency_ms
        })
        
        self._save_data()
        return trade
    
    def update_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_timestamp: datetime,
        duration_seconds: float
    ):
        """Update trade with exit information and calculate PnL"""
        for trade in self.trades:
            if trade.get("trade_id") == trade_id:
                trade["exit_price"] = exit_price
                trade["exit_timestamp"] = exit_timestamp.isoformat()
                trade["duration_seconds"] = duration_seconds
                
                # Calculate PnL
                if trade.get("entry_price") and exit_price:
                    if trade.get("is_buy", True):
                        # Buy: Profit if exit > entry
                        pnl = (exit_price - trade["entry_price"]) * trade.get("amount_in", 0)
                    else:
                        # Sell: Profit if entry > exit
                        pnl = (trade["entry_price"] - exit_price) * trade.get("amount_in", 0)
                    
                    trade["pnl"] = pnl
                    if trade["entry_price"] > 0:
                        trade["pnl_percentage"] = (pnl / (trade["entry_price"] * trade.get("amount_in", 1))) * 100
                
                self._save_data()
                return trade
        return None
    
    def add_failed_trade(
        self,
        timestamp: datetime,
        reason: str,
        master_amount: Optional[float] = None,
        trade_info: Optional[Dict] = None
    ):
        """Add a failed/non-executed trade"""
        failed = {
            "timestamp": timestamp.isoformat(),
            "reason": reason,
            "master_amount": master_amount,
            "trade_info": trade_info,
            "status": "failed"
        }
        
        self.failed_trades.append(failed)
        self._save_data()
        return failed
    
    def add_error(
        self,
        timestamp: datetime,
        error_message: str,
        error_type: str,
        potential_cause: str,
        context: Optional[Dict] = None
    ):
        """Add an error with potential cause"""
        error = {
            "timestamp": timestamp.isoformat(),
            "error_message": error_message,
            "error_type": error_type,
            "potential_cause": potential_cause,
            "context": context
        }
        
        self.errors.append(error)
        self._save_data()
        return error
    
    def get_successful_trades(self, limit: int = 20) -> List[Dict]:
        """Get list of successful trades"""
        return self.trades[-limit:] if len(self.trades) > limit else self.trades
    
    def get_failed_trades(self, limit: int = 20) -> List[Dict]:
        """Get list of failed trades"""
        return self.failed_trades[-limit:] if len(self.failed_trades) > limit else self.failed_trades
    
    def get_errors(self, limit: int = 20) -> List[Dict]:
        """Get list of errors"""
        return self.errors[-limit:] if len(self.errors) > limit else self.errors
    
    def get_pnl_by_period(self, period: str = "day") -> Dict:
        """
        Get PnL by time period
        
        Args:
            period: "hour", "day", "week"
        
        Returns:
            Dictionary with PnL data
        """
        now = datetime.now()
        
        if period == "hour":
            cutoff = now - timedelta(hours=24)
            group_by = lambda dt: dt.strftime("%Y-%m-%d %H:00")
        elif period == "day":
            cutoff = now - timedelta(days=7)
            group_by = lambda dt: dt.strftime("%Y-%m-%d")
        elif period == "week":
            cutoff = now - timedelta(weeks=4)
            group_by = lambda dt: dt.strftime("%Y-W%W")
        else:
            cutoff = datetime.min
            group_by = lambda dt: "total"
        
        # Filter trades by period
        period_trades = [
            trade for trade in self.trades
            if datetime.fromisoformat(trade["timestamp"]) >= cutoff
        ]
        
        # Group by period
        pnl_by_period = {}
        for trade in period_trades:
            trade_time = datetime.fromisoformat(trade["timestamp"])
            period_key = group_by(trade_time)
            
            if period_key not in pnl_by_period:
                pnl_by_period[period_key] = {
                    "trades": 0,
                    "profit": 0.0,
                    "loss": 0.0,
                    "net_pnl": 0.0
                }
            
            pnl_by_period[period_key]["trades"] += 1
            
            pnl = trade.get("pnl", 0.0)
            if pnl:
                if pnl > 0:
                    pnl_by_period[period_key]["profit"] += pnl
                else:
                    pnl_by_period[period_key]["loss"] += abs(pnl)
                
                pnl_by_period[period_key]["net_pnl"] += pnl
        
        return pnl_by_period
    
    def get_latency_averages(self) -> Dict:
        """Get latency averages by time period"""
        now = datetime.now()
        
        averages = {
            "1min": 0.0,
            "15min": 0.0,
            "1hour": 0.0,
            "4hours": 0.0,
            "24hours": 0.0,
            "all_time": 0.0
        }
        
        if not self.latency_history:
            return averages
        
        # Get latencies for each period
        latencies_1min = []
        latencies_15min = []
        latencies_1hour = []
        latencies_4hours = []
        latencies_24hours = []
        all_latencies = []
        
        for entry in self.latency_history:
            entry_time = datetime.fromisoformat(entry["timestamp"])
            latency = entry["latency_ms"]
            all_latencies.append(latency)
            
            if entry_time >= now - timedelta(minutes=1):
                latencies_1min.append(latency)
            if entry_time >= now - timedelta(minutes=15):
                latencies_15min.append(latency)
            if entry_time >= now - timedelta(hours=1):
                latencies_1hour.append(latency)
            if entry_time >= now - timedelta(hours=4):
                latencies_4hours.append(latency)
            if entry_time >= now - timedelta(hours=24):
                latencies_24hours.append(latency)
        
        # Calculate averages
        if latencies_1min:
            averages["1min"] = sum(latencies_1min) / len(latencies_1min)
        if latencies_15min:
            averages["15min"] = sum(latencies_15min) / len(latencies_15min)
        if latencies_1hour:
            averages["1hour"] = sum(latencies_1hour) / len(latencies_1hour)
        if latencies_4hours:
            averages["4hours"] = sum(latencies_4hours) / len(latencies_4hours)
        if latencies_24hours:
            averages["24hours"] = sum(latencies_24hours) / len(latencies_24hours)
        if all_latencies:
            averages["all_time"] = sum(all_latencies) / len(all_latencies)
        
        return averages
    
    def get_trade_duration_stats(self) -> Dict:
        """Get trade duration statistics"""
        if not self.trades:
            return {
                "average_duration": 0.0,
                "shortest_duration": 0.0,
                "longest_duration": 0.0,
                "durations": []
            }
        
        durations = [
            trade.get("duration_seconds", 0.0)
            for trade in self.trades
            if trade.get("duration_seconds") is not None
        ]
        
        if not durations:
            return {
                "average_duration": 0.0,
                "shortest_duration": 0.0,
                "longest_duration": 0.0,
                "durations": []
            }
        
        return {
            "average_duration": sum(durations) / len(durations),
            "shortest_duration": min(durations),
            "longest_duration": max(durations),
            "durations": durations[-10:]  # Last 10 durations
        }
    
    def get_total_pnl(self) -> Dict:
        """Get total PnL statistics"""
        if not self.trades:
            return {
                "total_trades": 0,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "net_pnl": 0.0,
                "roi": 0.0
            }
        
        total_profit = 0.0
        total_loss = 0.0
        
        for trade in self.trades:
            pnl = trade.get("pnl", 0.0)
            if pnl:
                if pnl > 0:
                    total_profit += pnl
                else:
                    total_loss += abs(pnl)
        
        net_pnl = total_profit - total_loss
        
        # Calculate ROI (simplified - would need initial capital tracking)
        roi = 0.0
        if self.trades:
            # Simple ROI calculation
            total_invested = sum(trade.get("amount_in", 0.0) for trade in self.trades)
            if total_invested > 0:
                roi = (net_pnl / total_invested) * 100
        
        return {
            "total_trades": len(self.trades),
            "total_profit": total_profit,
            "total_loss": total_loss,
            "net_pnl": net_pnl,
            "roi": roi
        }

