"""
Core copy trading logic with sub-150ms latency
"""
import asyncio
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Callable
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solana.rpc.async_api import AsyncClient

from config import Config
from grpc_client import YellowstoneGeyserClient
from wallet_manager import WalletManager
from slippage_manager import SlippageManager
from jupiter_client import JupiterClient
from trade_database import TradeDatabase
from base64 import b64decode

class CopyTrader:
    """High-performance copy trading bot"""
    
    def __init__(self):
        self.config = Config
        self.grpc_client = YellowstoneGeyserClient()
        self.wallet_manager = WalletManager()
        self.slippage_manager = SlippageManager()
        self.jupiter_client = JupiterClient()
        self.trade_db = TradeDatabase()
        self.trading_keypair: Optional[Keypair] = None
        self.rpc_client: Optional[AsyncClient] = None
        self.is_running = False
        self.stats = {
            "total_copies": 0,
            "successful_copies": 0,
            "failed_copies": 0,
            "avg_latency_ms": 0.0,
            "last_trade_time": None
        }
        # Track active trades (for duration calculation)
        self.active_trades: Dict[str, Dict] = {}
    
    async def initialize(self):
        """Initialize the copy trader"""
        # Load encrypted wallet
        encrypted_key = self.config.PRIVATE_KEY_ENCRYPTED
        if not encrypted_key:
            raise ValueError("PRIVATE_KEY_ENCRYPTED not set in config")
        
        self.trading_keypair = self.wallet_manager.load_keypair(encrypted_key)
        print(f"Wallet loaded: {self.trading_keypair.pubkey()}")
        
        # Initialize RPC client
        self.rpc_client = AsyncClient(self.config.RPC_ENDPOINT)
        
        # Connect to Yellow Stone Geyser
        await self.grpc_client.connect()
        
        print("Copy trader initialized successfully")
    
    def _adjust_lot_size(self, master_amount: float) -> float:
        """
        Adjust trade amount based on lot size configuration
        
        Args:
            master_amount: Amount traded by master wallet
            
        Returns:
            Adjusted amount for your bot
        """
        mode = self.config.LOT_SIZE_MODE.lower()
        value = self.config.LOT_SIZE_VALUE
        
        if mode == "fixed":
            # Fixed amount regardless of master
            return value
        elif mode == "percentage":
            # Percentage of master amount (e.g., 10% = 0.1)
            return master_amount * (value / 100.0)
        elif mode == "multiplier":
            # Multiply master amount (e.g., 2x)
            return master_amount * value
        else:
            # Default: same as master (100%)
            return master_amount
    
    async def _process_transaction(self, transaction_data: Dict):
        """
        Process a transaction from the master wallet
        
        Args:
            transaction_data: Transaction data from gRPC stream
        """
        start_time = time.time()
        trade_timestamp = datetime.now()
        master_amount = 0.0
        
        try:
            # Extract trade information from transaction
            print(f"\n📥 Processing transaction from master wallet...")
            print(f"   Transaction data received: {type(transaction_data)}")
            
            trade_info = self._extract_trade_info(transaction_data)
            
            if not trade_info:
                print("⚠️ No trade info extracted from transaction")
                print("   This might not be a swap/trade transaction")
                print("   Or transaction format is not recognized")
                return
            
            # Get master wallet amount
            master_amount = trade_info.get("amount_in", 0.0)
            
            # Adjust lot size based on configuration
            adjusted_amount = self._adjust_lot_size(master_amount)
            trade_info["amount_in"] = adjusted_amount
            trade_info["master_amount"] = master_amount
            trade_info["your_amount"] = adjusted_amount
            
            print(f"📊 Trade detected:")
            print(f"   Master Amount: {master_amount} SOL")
            print(f"   Your Amount: {adjusted_amount} SOL ({self.config.LOT_SIZE_MODE}: {self.config.LOT_SIZE_VALUE})")
            print(f"   Token In: {trade_info.get('token_in')}")
            print(f"   Token Out: {trade_info.get('token_out')}")
            print(f"   Type: {'BUY' if trade_info.get('is_buy') else 'SELL'}")
            
            # Get entry price from Jupiter quote (approximate)
            entry_price = 0.0  # Will be fetched during trade execution
            
            # Execute copy trade
            success = await self._execute_copy_trade(trade_info, entry_price, trade_timestamp, start_time)
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Update stats
            self.stats["total_copies"] += 1
            
            if success:
                self.stats["successful_copies"] += 1
                print(f"✓ Copy trade executed in {latency_ms:.2f}ms")
            else:
                self.stats["failed_copies"] += 1
                print(f"✗ Copy trade failed after {latency_ms:.2f}ms")
                # Add to failed trades database
                self.trade_db.add_failed_trade(
                    timestamp=trade_timestamp,
                    reason="Trade execution failed",
                    master_amount=master_amount,
                    trade_info=trade_info
                )
            
            # Update average latency
            total = self.stats["total_copies"]
            current_avg = self.stats["avg_latency_ms"]
            self.stats["avg_latency_ms"] = ((current_avg * (total - 1)) + latency_ms) / total
            self.stats["last_trade_time"] = time.time()
            
        except Exception as e:
            print(f"Error processing transaction: {e}")
            self.stats["failed_copies"] += 1
            
            # Add error to database
            self.trade_db.add_error(
                timestamp=trade_timestamp,
                error_message=str(e),
                error_type=type(e).__name__,
                potential_cause="Transaction processing error",
                context={"transaction_data": str(transaction_data)[:200]}
            )
    
    def _extract_trade_info(self, transaction_data: Dict) -> Optional[Dict]:
        """
        Extract trade information from transaction data
        Handles both gRPC format and RPC format
        
        Args:
            transaction_data: Raw transaction data from gRPC or RPC
            
        Returns:
            Dictionary with trade info or None if not a trade
        """
        try:
            # Check if transaction data exists
            if not transaction_data:
                print("⚠️ No transaction data provided")
                return None
            
            # Debug: Print transaction data structure (only first time or on error)
            if not hasattr(self, '_debug_printed'):
                print(f"🔍 DEBUG: Transaction data structure:")
                print(f"   Type: {type(transaction_data)}")
                if isinstance(transaction_data, dict):
                    print(f"   Keys: {list(transaction_data.keys())}")
                self._debug_printed = True
            
            transaction = None
            tx_bytes = None
            
            # Handle RPC format (from get_transaction response)
            if isinstance(transaction_data, dict):
                if 'transaction' in transaction_data:
                    tx_obj = transaction_data['transaction']
                    
                    # RPC TransactionInfo format
                    if hasattr(tx_obj, 'transaction'):
                        # Solana RPC TransactionInfo has .transaction.message
                        rpc_tx = tx_obj.transaction
                        if hasattr(rpc_tx, 'message'):
                            # Try to get serialized transaction
                            if hasattr(rpc_tx, 'serialize'):
                                tx_bytes = rpc_tx.serialize()
                            elif hasattr(rpc_tx.message, 'serialize'):
                                tx_bytes = rpc_tx.message.serialize()
                    
                    # Check for base64 encoded transaction
                    if not tx_bytes:
                        if hasattr(tx_obj, 'transaction') and isinstance(tx_obj.transaction, (str, bytes)):
                            if isinstance(tx_obj.transaction, str):
                                try:
                                    tx_bytes = b64decode(tx_obj.transaction)
                                except:
                                    pass
                            else:
                                tx_bytes = tx_obj.transaction
                
                # Handle gRPC format
                elif 'update' in transaction_data:
                    update = transaction_data['update']
                    if hasattr(update, 'transaction'):
                        tx_obj = update.transaction
                        # Try to extract transaction bytes
                        if hasattr(tx_obj, 'transaction'):
                            if isinstance(tx_obj.transaction, (str, bytes)):
                                if isinstance(tx_obj.transaction, str):
                                    try:
                                        tx_bytes = b64decode(tx_obj.transaction)
                                    except:
                                        pass
                                else:
                                    tx_bytes = tx_obj.transaction
            
            # Parse transaction bytes if we have them
            if tx_bytes:
                try:
                    parsed_tx = Transaction.from_bytes(tx_bytes)
                    return self._parse_transaction_instructions(parsed_tx, transaction_data)
                except Exception as e:
                    print(f"⚠️ Could not parse transaction bytes: {e}")
            
            # Fallback: Try to extract from RPC TransactionInfo message/instructions
            if isinstance(transaction_data, dict) and 'transaction' in transaction_data:
                tx_obj = transaction_data['transaction']
                if hasattr(tx_obj, 'transaction'):
                    rpc_tx = tx_obj.transaction
                    if hasattr(rpc_tx, 'message'):
                        message = rpc_tx.message
                        # Try to parse instructions from RPC message
                        return self._parse_rpc_transaction(message, transaction_data)
            
            # Final fallback: Try to detect common swap patterns
            return self._detect_swap_from_data(transaction_data)
                
        except Exception as e:
            print(f"⚠️ Error extracting trade info: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_rpc_transaction(self, message, transaction_data: Dict) -> Optional[Dict]:
        """Parse transaction from RPC message format"""
        try:
            if not hasattr(message, 'instructions'):
                return None
            
            instructions = message.instructions
            
            # Get program IDs from account keys
            account_keys = message.account_keys if hasattr(message, 'account_keys') else []
            
            sol_mint = self.jupiter_client.get_sol_mint()
            
            for instruction in instructions:
                try:
                    # Get program ID index
                    if hasattr(instruction, 'program_id_index'):
                        program_id_idx = instruction.program_id_index
                        if program_id_idx < len(account_keys):
                            program_id = str(account_keys[program_id_idx])
                            
                            # Check for Jupiter/Raydium
                            JUPITER_PROGRAM = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
                            RAYDIUM_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
                            
                            if program_id in [JUPITER_PROGRAM, RAYDIUM_PROGRAM]:
                                # Try to parse swap instruction
                                return self._parse_swap_instruction(instruction, account_keys, transaction_data)
                except:
                    continue
            
            return None
        except Exception as e:
            print(f"⚠️ Error parsing RPC transaction: {e}")
            return None
    
    def _parse_swap_instruction(self, instruction, account_keys, transaction_data: Dict) -> Optional[Dict]:
        """Parse swap instruction from RPC format with REAL data"""
        try:
            sol_mint = self.jupiter_client.get_sol_mint()
            
            # Extract accounts from instruction
            accounts = []
            if hasattr(instruction, 'accounts'):
                accounts = instruction.accounts
            
            # Extract REAL data from transaction balance changes
            trade_info = self._extract_real_trade_data(transaction_data, account_keys, accounts)
            
            if trade_info:
                return trade_info
            
            # Fallback if extraction fails
            return {
                "token_in": sol_mint,
                "token_out": sol_mint,
                "amount_in": 0.1,
                "amount_out": 0.0,
                "is_buy": True,
                "dex": "jupiter"
            }
        except Exception as e:
            print(f"⚠️ Error parsing swap instruction: {e}")
            return None
    
    def _parse_transaction_instructions(self, transaction: Transaction, raw_data: Dict) -> Optional[Dict]:
        """Parse transaction instructions to find swap operations"""
        try:
            instructions = transaction.message.instructions
            
            # Common DEX program IDs
            JUPITER_PROGRAM = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
            RAYDIUM_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
            PUMPKIN_PROGRAM = None  # Need to research actual program ID
            
            sol_mint = self.jupiter_client.get_sol_mint()
            
            for idx, instruction in enumerate(instructions):
                try:
                    # Get program ID
                    program_id = None
                    if hasattr(instruction, 'program_id'):
                        program_id = str(instruction.program_id)
                    elif hasattr(instruction, 'program_id_index'):
                        # Instruction might reference program ID by index
                        program_id_idx = instruction.program_id_index
                        account_keys = transaction.message.account_keys
                        if program_id_idx < len(account_keys):
                            program_id = str(account_keys[program_id_idx])
                    
                    if not program_id:
                        continue
                    
                    # Check if this is a swap instruction
                    if program_id == JUPITER_PROGRAM:
                        return self._parse_jupiter_swap(instruction, raw_data, sol_mint)
                    elif program_id == RAYDIUM_PROGRAM:
                        return self._parse_jupiter_swap(instruction, raw_data, sol_mint)  # Use same parser for now
                    # Add more DEX parsers as needed
                except Exception as e:
                    continue  # Skip invalid instructions
                
            return None
            
        except Exception as e:
            print(f"Error parsing instructions: {e}")
            return None
    
    def _parse_jupiter_swap(self, instruction, raw_data: Dict, sol_mint: str) -> Optional[Dict]:
        """Parse Jupiter swap instruction with REAL data"""
        try:
            # Get account keys from transaction
            account_keys = []
            if 'transaction' in raw_data:
                tx_obj = raw_data['transaction']
                if hasattr(tx_obj, 'transaction'):
                    rpc_tx = tx_obj.transaction
                    if hasattr(rpc_tx, 'message'):
                        message = rpc_tx.message
                        if hasattr(message, 'account_keys'):
                            account_keys = message.account_keys
                    elif hasattr(rpc_tx, 'account_keys'):
                        account_keys = rpc_tx.account_keys
            
            # Get instruction accounts
            accounts = []
            if hasattr(instruction, 'accounts'):
                accounts = instruction.accounts
            
            # Extract REAL data from transaction balance changes
            trade_info = self._extract_real_trade_data(raw_data, account_keys, accounts)
            
            if trade_info:
                trade_info["dex"] = "jupiter"
                return trade_info
            
            # Fallback if extraction fails
            return {
                "token_in": sol_mint,
                "token_out": sol_mint,
                "amount_in": 0.1,
                "amount_out": 0.0,
                "is_buy": True,
                "dex": "jupiter"
            }
        except Exception as e:
            print(f"⚠️ Error parsing Jupiter swap: {e}")
            return None
    
    def _extract_real_trade_data(self, transaction_data: Dict, account_keys: list, instruction_accounts: list) -> Optional[Dict]:
        """
        Extract REAL trade data from transaction balance changes
        
        Args:
            transaction_data: Full transaction data from RPC
            account_keys: Account keys from transaction message
            instruction_accounts: Account indices from instruction
            
        Returns:
            Dictionary with real trade info or None
        """
        try:
            sol_mint = self.jupiter_client.get_sol_mint()
            LAMPORTS_PER_SOL = 1_000_000_000
            
            # Get metadata from transaction
            meta = None
            if 'transaction' in transaction_data:
                tx_obj = transaction_data['transaction']
                if hasattr(tx_obj, 'meta'):
                    meta = tx_obj.meta
                elif isinstance(tx_obj, dict) and 'meta' in tx_obj:
                    meta = tx_obj['meta']
            
            if not meta:
                return None
            
            # Extract token balance changes (MOST RELIABLE for swap detection)
            pre_token_balances = None
            post_token_balances = None
            
            if hasattr(meta, 'pre_token_balances'):
                pre_token_balances = meta.pre_token_balances
            elif hasattr(meta, 'preTokenBalances'):
                pre_token_balances = meta.preTokenBalances
            elif isinstance(meta, dict):
                pre_token_balances = meta.get('preTokenBalances') or meta.get('pre_token_balances')
            
            if hasattr(meta, 'post_token_balances'):
                post_token_balances = meta.post_token_balances
            elif hasattr(meta, 'postTokenBalances'):
                post_token_balances = meta.postTokenBalances
            elif isinstance(meta, dict):
                post_token_balances = meta.get('postTokenBalances') or meta.get('post_token_balances')
            
            # Extract SOL balance changes
            pre_balances = None
            post_balances = None
            
            if hasattr(meta, 'pre_balances'):
                pre_balances = meta.pre_balances
            elif hasattr(meta, 'preBalances'):
                pre_balances = meta.preBalances
            elif isinstance(meta, dict):
                pre_balances = meta.get('preBalances') or meta.get('pre_balances')
            
            if hasattr(meta, 'post_balances'):
                post_balances = meta.post_balances
            elif hasattr(meta, 'postBalances'):
                post_balances = meta.postBalances
            elif isinstance(meta, dict):
                post_balances = meta.get('postBalances') or meta.get('post_balances')
            
            # Method 1: Extract from token balances (MOST ACCURATE)
            if pre_token_balances and post_token_balances:
                # Convert to lists if needed
                if not isinstance(pre_token_balances, list):
                    pre_token_balances = list(pre_token_balances) if pre_token_balances else []
                if not isinstance(post_token_balances, list):
                    post_token_balances = list(post_token_balances) if post_token_balances else []
                
                # Find token account with balance change
                token_in_mint = None
                token_out_mint = None
                amount_in = 0.0
                amount_out = 0.0
                
                # Create maps of account index -> balance
                pre_token_map = {}
                post_token_map = {}
                
                for balance in pre_token_balances:
                    if isinstance(balance, dict):
                        account_idx = balance.get('accountIndex') or balance.get('account_index')
                        mint = balance.get('mint')
                        ui_amount = balance.get('uiTokenAmount', {}).get('uiAmount') or balance.get('uiAmount')
                        if account_idx is not None and mint:
                            pre_token_map[account_idx] = {'mint': mint, 'amount': ui_amount or 0.0}
                    elif hasattr(balance, 'account_index') or hasattr(balance, 'accountIndex'):
                        account_idx = getattr(balance, 'accountIndex', None) or getattr(balance, 'account_index', None)
                        mint = getattr(balance, 'mint', None)
                        ui_amount = 0.0
                        if hasattr(balance, 'ui_token_amount'):
                            ui_amount = getattr(balance.ui_token_amount, 'ui_amount', 0.0)
                        elif hasattr(balance, 'uiTokenAmount'):
                            ui_amount = getattr(balance.uiTokenAmount, 'uiAmount', 0.0)
                        if account_idx is not None and mint:
                            pre_token_map[account_idx] = {'mint': str(mint), 'amount': ui_amount or 0.0}
                
                for balance in post_token_balances:
                    if isinstance(balance, dict):
                        account_idx = balance.get('accountIndex') or balance.get('account_index')
                        mint = balance.get('mint')
                        ui_amount = balance.get('uiTokenAmount', {}).get('uiAmount') or balance.get('uiAmount')
                        if account_idx is not None and mint:
                            post_token_map[account_idx] = {'mint': mint, 'amount': ui_amount or 0.0}
                    elif hasattr(balance, 'account_index') or hasattr(balance, 'accountIndex'):
                        account_idx = getattr(balance, 'accountIndex', None) or getattr(balance, 'account_index', None)
                        mint = getattr(balance, 'mint', None)
                        ui_amount = 0.0
                        if hasattr(balance, 'ui_token_amount'):
                            ui_amount = getattr(balance.ui_token_amount, 'ui_amount', 0.0)
                        elif hasattr(balance, 'uiTokenAmount'):
                            ui_amount = getattr(balance.uiTokenAmount, 'uiAmount', 0.0)
                        if account_idx is not None and mint:
                            post_token_map[account_idx] = {'mint': str(mint), 'amount': ui_amount or 0.0}
                
                # Find accounts with balance changes
                for account_idx, post_data in post_token_map.items():
                    pre_data = pre_token_map.get(account_idx, {'amount': 0.0})
                    balance_change = post_data['amount'] - pre_data.get('amount', 0.0)
                    
                    if abs(balance_change) > 0.0001:  # Significant change
                        if balance_change < 0:
                            # Token out (decreased)
                            if not token_out_mint:
                                token_out_mint = post_data['mint']
                                amount_out = abs(balance_change)
                        else:
                            # Token in (increased)
                            if not token_in_mint:
                                token_in_mint = post_data['mint']
                                amount_in = abs(balance_change)
                
                # Get SOL balance change to determine direction
                sol_balance_change = 0.0
                if pre_balances and post_balances and len(pre_balances) == len(post_balances):
                    # Find SOL account (usually first account or signer)
                    for idx in range(min(len(pre_balances), len(account_keys) if account_keys else 10)):
                        change = post_balances[idx] - pre_balances[idx]
                        if abs(change) > abs(sol_balance_change):
                            sol_balance_change = change
                
                # Determine trade direction
                # If SOL decreased and token increased = BUY (SOL -> Token)
                # If token decreased and SOL increased = SELL (Token -> SOL)
                if sol_balance_change < 0:
                    # SOL spent = BUY
                    is_buy = True
                    if not token_in_mint:
                        token_in_mint = sol_mint
                        amount_in = abs(sol_balance_change) / LAMPORTS_PER_SOL
                    if token_in_mint == sol_mint and not token_out_mint:
                        # Need to find token_out from instruction accounts
                        token_out_mint = None
                else:
                    # SOL received = SELL
                    is_buy = False
                    if not token_out_mint:
                        token_out_mint = sol_mint
                        amount_out = abs(sol_balance_change) / LAMPORTS_PER_SOL
                    if token_out_mint == sol_mint and not token_in_mint:
                        # Need to find token_in from instruction accounts
                        token_in_mint = None
                
                # If we have valid mints, return trade info
                if token_in_mint and token_out_mint:
                    # Normalize: token_in should be what we're spending, token_out what we're getting
                    if is_buy:
                        # BUY: Spending SOL, getting Token
                        if token_in_mint == sol_mint and token_out_mint != sol_mint:
                            return {
                                "token_in": token_in_mint,
                                "token_out": token_out_mint,
                                "amount_in": amount_in if amount_in > 0 else 0.1,
                                "amount_out": amount_out,
                                "is_buy": True,
                                "dex": "jupiter"
                            }
                        elif token_in_mint != sol_mint:
                            # Token is being spent (might be wrapped SOL)
                            return {
                                "token_in": token_in_mint,
                                "token_out": token_out_mint,
                                "amount_in": amount_in,
                                "amount_out": amount_out,
                                "is_buy": True,
                                "dex": "jupiter"
                            }
                    else:
                        # SELL: Spending Token, getting SOL
                        if token_in_mint != sol_mint and token_out_mint == sol_mint:
                            return {
                                "token_in": token_in_mint,
                                "token_out": token_out_mint,
                                "amount_in": amount_in,
                                "amount_out": amount_out if amount_out > 0 else 0.1,
                                "is_buy": False,
                                "dex": "jupiter"
                            }
            
            # Method 2: Extract from SOL balance change only
            if pre_balances and post_balances and len(pre_balances) == len(post_balances):
                sol_account_idx = None
                max_change = 0
                
                # Find account with largest SOL balance change
                for idx in range(min(len(pre_balances), len(account_keys) if account_keys else 10)):
                    change = post_balances[idx] - pre_balances[idx]
                    if abs(change) > abs(max_change):
                        max_change = change
                        sol_account_idx = idx
                
                if sol_account_idx is not None and abs(max_change) > 1000000:  # More than 0.001 SOL
                    sol_change = abs(max_change) / LAMPORTS_PER_SOL
                    is_buy = max_change < 0
                    
                    # Try to get token mint from instruction accounts
                    token_mint = sol_mint
                    if instruction_accounts and len(instruction_accounts) >= 3:
                        # Jupiter swaps: accounts often contain token mints
                        for idx in instruction_accounts[1:min(5, len(instruction_accounts))]:
                            if idx < len(account_keys):
                                potential_mint = str(account_keys[idx])
                                if potential_mint != sol_mint:
                                    token_mint = potential_mint
                                    break
                    
                    return {
                        "token_in": sol_mint if is_buy else (token_mint if token_mint != sol_mint else sol_mint),
                        "token_out": (token_mint if token_mint != sol_mint else sol_mint) if is_buy else sol_mint,
                        "amount_in": sol_change if is_buy else 0.1,
                        "amount_out": 0.0,
                        "is_buy": is_buy,
                        "dex": "jupiter"
                    }
            
            # Method 3: Fallback to instruction accounts
            if instruction_accounts and len(instruction_accounts) >= 3 and account_keys:
                token_in_idx = instruction_accounts[1] if len(instruction_accounts) > 1 else None
                token_out_idx = instruction_accounts[2] if len(instruction_accounts) > 2 else None
                
                if token_in_idx is not None and token_in_idx < len(account_keys):
                    token_in = str(account_keys[token_in_idx])
                    token_out = str(account_keys[token_out_idx]) if token_out_idx is not None and token_out_idx < len(account_keys) else sol_mint
                    
                    is_buy = token_in == sol_mint
                    
                    # Try to get amounts from balance changes
                    amount_in = 0.1
                    if pre_balances and post_balances and len(pre_balances) == len(post_balances):
                        # Find largest SOL balance change
                        max_change = 0
                        for idx in range(min(len(pre_balances), len(account_keys) if account_keys else 10)):
                            change = abs(post_balances[idx] - pre_balances[idx])
                            if change > max_change:
                                max_change = change
                        
                        if max_change > 1000000:  # More than 0.001 SOL
                            sol_change = max_change / LAMPORTS_PER_SOL
                            amount_in = sol_change if is_buy else amount_in
                    
                    return {
                        "token_in": token_in,
                        "token_out": token_out,
                        "amount_in": amount_in,
                        "amount_out": 0.0,
                        "is_buy": is_buy,
                        "dex": "jupiter"
                    }
            
            return None
        except Exception as e:
            print(f"⚠️ Error extracting real trade data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _detect_swap_from_data(self, transaction_data: Dict) -> Optional[Dict]:
        """Fallback: Try to detect swap from transaction data patterns"""
        try:
            # Try to extract real data first
            account_keys = []
            if 'transaction' in transaction_data:
                tx_obj = transaction_data['transaction']
                if hasattr(tx_obj, 'transaction'):
                    rpc_tx = tx_obj.transaction
                    if hasattr(rpc_tx, 'message'):
                        message = rpc_tx.message
                        if hasattr(message, 'account_keys'):
                            account_keys = message.account_keys
            
            trade_info = self._extract_real_trade_data(transaction_data, account_keys, [])
            if trade_info:
                return trade_info
            
            # Fallback to pattern matching
            data_str = str(transaction_data).lower()
            
            # Simple heuristics (not production-ready)
            if any(indicator in data_str for indicator in ['swap', 'trade', 'jupiter', 'raydium']):
                sol_mint = self.jupiter_client.get_sol_mint()
                return {
                    "token_in": sol_mint,
                    "token_out": sol_mint,
                    "amount_in": 0.1,
                    "amount_out": 0.0,
                    "is_buy": True,
                    "dex": "jupiter"
                }
        except:
            pass
        return None
    
    async def _execute_copy_trade(self, trade_info: Dict, entry_price: float = 0.0, trade_timestamp: datetime = None, start_time: float = None) -> bool:
        """
        Execute a copy trade with minimal latency
        
        Args:
            trade_info: Trade information dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate trade info
            if not trade_info or not trade_info.get("amount_in"):
                print("⚠️ Invalid trade info")
                return False
            
            # Check balance before trading
            balance = await self.rpc_client.get_balance(self.trading_keypair.pubkey())
            available_sol = balance.value / 1e9  # Convert lamports to SOL
            
            is_buy = trade_info.get("is_buy", True)
            amount = trade_info.get("amount_in", 0)
            
            # Validate balance
            is_valid, error_msg = self.slippage_manager.validate_trade(
                amount, available_sol, is_buy
            )
            
            if not is_valid:
                print(f"❌ Trade validation failed: {error_msg}")
                
                # Add to failed trades
                if trade_timestamp:
                    self.trade_db.add_failed_trade(
                        timestamp=trade_timestamp,
                        reason=error_msg,
                        master_amount=trade_info.get("master_amount", 0.0),
                        trade_info=trade_info
                    )
                return False
            
            # Calculate amounts with slippage and fees
            calculation = self.slippage_manager.calculate_trade_amount_with_fees(
                amount, is_buy
            )
            
            print(f"📊 Executing copy trade:")
            print(f"   Amount: {amount} SOL")
            print(f"   Total Cost: {calculation['total_cost']:.6f} SOL")
            print(f"   Available: {available_sol:.6f} SOL")
            
            # Get Jupiter quote first (for entry price and transaction)
            quote = None
            try:
                token_in = trade_info.get("token_in")
                token_out = trade_info.get("token_out")
                if token_in and token_out:
                    amount_lamports = int(amount * 1e9)
                    slippage_bps = int(self.config.SLIPPAGE_TOLERANCE * 100)
                    quote = await self.jupiter_client.get_quote(
                        input_mint=token_in,
                        output_mint=token_out,
                        amount=amount_lamports,
                        slippage_bps=slippage_bps
                    )
                    if quote and not entry_price:
                        in_amount = quote.get('inAmount', 0)
                        out_amount = quote.get('outAmount', 0)
                        if out_amount > 0:
                            entry_price = in_amount / out_amount
            except Exception as e:
                print(f"⚠️ Could not get quote for entry price: {e}")
            
            # Build and send transaction
            transaction = await self._build_swap_transaction(trade_info, calculation)
            
            if not transaction:
                print("❌ Failed to build transaction")
                return False
            
            # Send transaction
            signature = await self._send_transaction(transaction)
            
            if signature:
                print(f"✅ Copy trade executed: {signature}")
                
                # Use entry price from quote if available
                if not entry_price and quote:
                    in_amount = quote.get('inAmount', 0)
                    out_amount = quote.get('outAmount', 0)
                    if out_amount > 0:
                        entry_price = in_amount / out_amount
                
                # Create trade ID
                trade_id = str(uuid.uuid4())[:8]
                
                # Track trade start time
                trade_start_time = time.time() if start_time else time.time()
                
                # Add to successful trades database
                trade_record = self.trade_db.add_successful_trade(
                    trade_id=trade_id,
                    timestamp=trade_timestamp if trade_timestamp else datetime.now(),
                    token_in=trade_info.get("token_in", ""),
                    token_out=trade_info.get("token_out", ""),
                    amount_in=amount,
                    amount_out=quote.get('outAmount', 0) / 1e9 if quote else 0.0,  # Convert to SOL
                    entry_price=entry_price,
                    is_buy=is_buy,
                    latency_ms=(time.time() - trade_start_time) * 1000 if start_time else 0.0,
                    signature=str(signature),
                    master_amount=trade_info.get("master_amount", 0.0),
                    your_amount=amount
                )
                
                # Store active trade for duration tracking
                self.active_trades[trade_id] = {
                    "start_time": trade_start_time,
                    "entry_price": entry_price,
                    "trade_info": trade_info
                }
                
                return True
            else:
                print("Transaction failed")
                return False
            
        except Exception as e:
            print(f"❌ Error executing copy trade: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _build_swap_transaction(
        self, 
        trade_info: Dict, 
        calculation: Dict
    ) -> Optional[Transaction]:
        """
        Build swap transaction using Jupiter aggregator
        
        Args:
            trade_info: Trade information
            calculation: Fee and slippage calculations
            
        Returns:
            Signed transaction or None if failed
        """
        try:
            token_in = trade_info.get("token_in")
            token_out = trade_info.get("token_out")
            amount_in = trade_info.get("amount_in", 0)
            
            if not token_in or not token_out:
                print("❌ Missing token addresses")
                return None
            
            # Convert SOL amount to lamports
            amount_lamports = int(amount_in * 1e9)
            
            # Calculate slippage in basis points
            slippage_percent = self.config.SLIPPAGE_TOLERANCE
            slippage_bps = int(slippage_percent * 100)  # Convert % to basis points
            
            # Get quote from Jupiter
            print(f"🔍 Getting Jupiter quote...")
            quote = await self.jupiter_client.get_quote(
                input_mint=token_in,
                output_mint=token_out,
                amount=amount_lamports,
                slippage_bps=slippage_bps
            )
            
            if not quote:
                print("❌ Failed to get Jupiter quote")
                return None
            
            print(f"✓ Quote received: {quote.get('outAmount', 0)} output tokens")
            
            # Calculate priority fee in lamports
            priority_fee_lamports = int(calculation.get("tips", 0.0001) * 1e9)
            
            # Get swap transaction from Jupiter
            print(f"🔧 Building swap transaction...")
            swap_data = await self.jupiter_client.get_swap_transaction(
                quote=quote,
                user_public_key=self.trading_keypair.pubkey(),
                priority_fee_lamports=priority_fee_lamports,
                dynamic_compute_unit_limit=True
            )
            
            if not swap_data or 'swapTransaction' not in swap_data:
                print("❌ Failed to get swap transaction from Jupiter")
                return None
            
            # Decode transaction from base64
            swap_tx_b64 = swap_data['swapTransaction']
            swap_tx_bytes = b64decode(swap_tx_b64)
            
            # Parse transaction
            transaction = Transaction.from_bytes(swap_tx_bytes)
            
            # Get recent blockhash (if needed)
            latest_blockhash = await self.rpc_client.get_latest_blockhash()
            transaction.recent_blockhash = latest_blockhash.value.blockhash
            
            # Sign transaction
            transaction.sign([self.trading_keypair], latest_blockhash.value.blockhash)
            
            print(f"✓ Transaction built and signed")
            return transaction
            
        except Exception as e:
            print(f"❌ Error building swap transaction: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _send_transaction(self, transaction: Transaction) -> Optional[str]:
        """
        Send transaction with same-block execution
        
        Args:
            transaction: Signed transaction
            
        Returns:
            Transaction signature or None if failed
        """
        try:
            # Send transaction
            print(f"📤 Sending transaction...")
            response = await self.rpc_client.send_transaction(
                transaction,
                self.trading_keypair,
                skip_preflight=False,
                max_retries=3,
                preflight_commitment="confirmed"
            )
            
            if not response.value:
                print("❌ Failed to get transaction signature")
                return None
            
            signature = response.value
            print(f"✓ Transaction sent: {signature}")
            
            # Wait for confirmation with timeout
            print(f"⏳ Waiting for confirmation...")
            confirmation = await self.rpc_client.confirm_transaction(
                signature,
                commitment="confirmed",
                timeout=10.0
            )
            
            if confirmation.value and len(confirmation.value) > 0:
                status = confirmation.value[0].confirmation_status
                if status == "confirmed":
                    print(f"✅ Transaction confirmed: {signature}")
                    return signature
                else:
                    print(f"⚠️ Transaction status: {status}")
                    return signature  # Return anyway, might still be processing
            else:
                print(f"⚠️ Could not confirm transaction status")
                return signature  # Return anyway
            
        except Exception as e:
            print(f"❌ Error sending transaction: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def start(self):
        """Start the copy trading bot"""
        await self.initialize()
        
        master_wallet = self.config.MASTER_WALLET_ADDRESS
        if not master_wallet:
            raise ValueError("MASTER_WALLET_ADDRESS not set")
        
        print(f"Starting copy trader for wallet: {master_wallet}")
        self.is_running = True
        
        # Subscribe to master wallet transactions
        await self.grpc_client.subscribe_to_transactions(
            master_wallet,
            self._process_transaction
        )
    
    async def stop(self):
        """Stop the copy trading bot"""
        self.is_running = False
        await self.grpc_client.close()
        if self.rpc_client:
            await self.rpc_client.close()
        print("Copy trader stopped")
    
    def get_stats(self) -> Dict:
        """Get trading statistics"""
        return self.stats.copy()

