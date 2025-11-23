"""
Slippage, fees, and tips calculation and management
"""
from config import Config
from typing import Dict, Optional
import asyncio

class SlippageManager:
    """Manages slippage, transaction fees, and tips"""
    
    def __init__(self):
        self.slippage_tolerance = Config.SLIPPAGE_TOLERANCE
        self.fee_buffer = Config.FEE_BUFFER
        self.tips_amount = Config.TIPS_AMOUNT
    
    def calculate_slippage_adjusted_amount(
        self, 
        base_amount: float, 
        slippage_percent: Optional[float] = None
    ) -> float:
        """
        Calculate amount adjusted for slippage
        
        Args:
            base_amount: Base amount to trade
            slippage_percent: Custom slippage percentage (uses config if None)
            
        Returns:
            Adjusted amount accounting for slippage
        """
        slippage = slippage_percent or self.slippage_tolerance
        # For buys: increase amount to account for slippage
        # For sells: decrease amount to account for slippage
        return base_amount * (1 + slippage / 100)
    
    def calculate_total_fees(self, transaction_size: int = 1232) -> float:
        """
        Calculate total transaction fees
        
        Args:
            transaction_size: Size of transaction in bytes (default Solana tx size)
            
        Returns:
            Total fees in SOL
        """
        # Base fee: 5000 lamports per signature
        # Transaction size fee: varies
        # Priority fee: tips
        base_fee = 0.000005  # 5000 lamports
        size_fee = (transaction_size / 1000) * 0.000001  # Approximate
        priority_fee = self.tips_amount
        
        total = base_fee + size_fee + priority_fee + self.fee_buffer
        return total
    
    def calculate_trade_amount_with_fees(
        self, 
        trade_amount: float, 
        is_buy: bool = True
    ) -> Dict[str, float]:
        """
        Calculate final trade amount accounting for fees and slippage
        
        Args:
            trade_amount: Base trade amount
            is_buy: True for buy, False for sell
            
        Returns:
            Dictionary with calculated amounts
        """
        # Calculate slippage adjustment
        slippage_adjusted = self.calculate_slippage_adjusted_amount(trade_amount)
        
        # Calculate fees
        fees = self.calculate_total_fees()
        
        if is_buy:
            # For buys: need to account for fees in the total cost
            total_cost = slippage_adjusted + fees
            final_amount = trade_amount
        else:
            # For sells: fees reduce the amount received
            total_cost = fees
            final_amount = slippage_adjusted - fees
        
        return {
            "base_amount": trade_amount,
            "slippage_adjusted": slippage_adjusted,
            "fees": fees,
            "total_cost": total_cost,
            "final_amount": max(0, final_amount),  # Ensure non-negative
            "tips": self.tips_amount
        }
    
    def validate_trade(
        self, 
        trade_amount: float, 
        available_balance: float, 
        is_buy: bool = True
    ) -> tuple[bool, str]:
        """
        Validate if trade can be executed with current balance
        
        Args:
            trade_amount: Amount to trade
            available_balance: Available balance in wallet
            is_buy: True for buy, False for sell
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        calculation = self.calculate_trade_amount_with_fees(trade_amount, is_buy)
        
        if is_buy:
            required = calculation["total_cost"]
            if available_balance < required:
                return False, f"Insufficient balance. Need {required} SOL, have {available_balance} SOL"
        else:
            if available_balance < trade_amount:
                return False, f"Insufficient balance. Need {trade_amount} SOL, have {available_balance} SOL"
        
        return True, ""

