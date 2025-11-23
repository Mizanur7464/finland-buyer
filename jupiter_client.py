"""
Jupiter aggregator client for DEX swaps
"""
import aiohttp
from typing import Dict, Optional
from solders.pubkey import Pubkey
from config import Config

class JupiterClient:
    """Client for Jupiter aggregator API"""
    
    BASE_URL = "https://quote-api.jup.ag/v6"
    SWAP_URL = "https://quote-api.jup.ag/v6/swap"
    
    # Known token addresses (SOL on testnet/mainnet)
    SOL_MINT_MAINNET = "So11111111111111111111111111111111111111112"
    SOL_MINT_TESTNET = "So11111111111111111111111111111111111111112"  # Same on testnet
    
    def __init__(self):
        self.config = Config
        
    def get_sol_mint(self) -> str:
        """Get SOL mint address based on network"""
        if self.config.NETWORK == "testnet":
            return self.SOL_MINT_TESTNET
        return self.SOL_MINT_MAINNET
    
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,  # Amount in smallest unit (lamports for SOL)
        slippage_bps: int = 100  # Slippage in basis points (100 = 1%)
    ) -> Optional[Dict]:
        """
        Get swap quote from Jupiter
        
        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest unit
            slippage_bps: Slippage in basis points
            
        Returns:
            Quote dictionary or None if failed
        """
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": amount,
                    "slippageBps": slippage_bps,
                    "onlyDirectRoutes": False,
                    "asLegacyTransaction": False
                }
                
                async with session.get(f"{self.BASE_URL}/quote", params=params) as response:
                    if response.status == 200:
                        quote = await response.json()
                        return quote
                    else:
                        error_text = await response.text()
                        print(f"❌ Jupiter quote error: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            print(f"❌ Error getting Jupiter quote: {e}")
            return None
    
    async def get_swap_transaction(
        self,
        quote: Dict,
        user_public_key: Pubkey,
        priority_fee_lamports: int = 0,
        dynamic_compute_unit_limit: bool = True
    ) -> Optional[Dict]:
        """
        Get swap transaction from Jupiter
        
        Args:
            quote: Quote dictionary from get_quote()
            user_public_key: User's public key
            priority_fee_lamports: Priority fee in lamports
            dynamic_compute_unit_limit: Use dynamic compute unit limit
            
        Returns:
            Swap transaction dictionary or None if failed
        """
        try:
            swap_request = {
                "quoteResponse": quote,
                "userPublicKey": str(user_public_key),
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": dynamic_compute_unit_limit,
                "prioritizationFeeLamports": priority_fee_lamports,
                "asLegacyTransaction": False
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.SWAP_URL, json=swap_request) as response:
                    if response.status == 200:
                        swap_data = await response.json()
                        return swap_data
                    else:
                        error_text = await response.text()
                        print(f"❌ Jupiter swap error: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            print(f"❌ Error getting Jupiter swap: {e}")
            return None

