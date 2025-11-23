"""
Configuration management for the copy trading bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Wallet Configuration
    MASTER_WALLET_ADDRESS = os.getenv("MASTER_WALLET_ADDRESS", "")
    PRIVATE_KEY_ENCRYPTED = os.getenv("PRIVATE_KEY_ENCRYPTED", "")
    
    # gRPC Configuration
    YELLOWSTONE_GRPC_URL = os.getenv("YELLOWSTONE_GRPC_URL", "")
    YELLOWSTONE_GRPC_TOKEN = os.getenv("YELLOWSTONE_GRPC_TOKEN", "")  # Token for authentication
    
    # Solana RPC Configuration
    RPC_ENDPOINT = os.getenv("RPC_ENDPOINT", "https://api.testnet.solana.com")
    NETWORK = os.getenv("NETWORK", "testnet")
    
    # Trading Configuration
    SLIPPAGE_TOLERANCE = float(os.getenv("SLIPPAGE_TOLERANCE", "1.0"))
    FEE_BUFFER = float(os.getenv("FEE_BUFFER", "0.001"))
    TIPS_AMOUNT = float(os.getenv("TIPS_AMOUNT", "0.0001"))
    
    # Lot Size Configuration
    # Options: "fixed", "percentage", "multiplier"
    # "fixed": Always trade fixed amount (use LOT_SIZE_VALUE as SOL amount)
    # "percentage": Trade percentage of master wallet amount (use LOT_SIZE_VALUE as percentage, e.g., 10 for 10%)
    # "multiplier": Multiply master wallet amount (use LOT_SIZE_VALUE as multiplier, e.g., 2 for 2x)
    LOT_SIZE_MODE = os.getenv("LOT_SIZE_MODE", "percentage")  # Default: percentage
    LOT_SIZE_VALUE = float(os.getenv("LOT_SIZE_VALUE", "10.0"))  # Default: 10% of master wallet
    
    # Performance Configuration
    MAX_LATENCY_MS = 150  # Maximum allowed latency in milliseconds
    MAX_COPIES_PER_DAY = 200
    
    # DEX Configuration
    DEX_PLATFORMS = ["pumpkin", "radium"]  # Supported DEX platforms
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            cls.MASTER_WALLET_ADDRESS,
            cls.PRIVATE_KEY_ENCRYPTED,
            cls.YELLOWSTONE_GRPC_URL,
        ]
        if not all(required):
            raise ValueError("Missing required configuration. Check .env file")
        
        # Validate Yellowstone gRPC URL format
        if cls.YELLOWSTONE_GRPC_URL:
            if not (cls.YELLOWSTONE_GRPC_URL.startswith("grpc://") or 
                    cls.YELLOWSTONE_GRPC_URL.startswith("grpcs://")):
                raise ValueError("YELLOWSTONE_GRPC_URL must start with grpc:// or grpcs://")
        
        # Token is required for QuickNode
        if cls.YELLOWSTONE_GRPC_URL and not cls.YELLOWSTONE_GRPC_TOKEN:
            raise ValueError("YELLOWSTONE_GRPC_TOKEN is required for QuickNode Yellowstone Geyser")

