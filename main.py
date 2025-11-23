"""
Main entry point for the copy trading bot
"""
import asyncio
import os
import signal
import sys

from config import Config
from copy_trader import CopyTrader

# Global instances
copy_trader: CopyTrader = None
telegram_monitor = None

# Try to import Telegram bot (optional)
try:
    from telegram_bot import TelegramMonitor
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    print("\nShutting down copy trading bot...")
    if copy_trader:
        asyncio.create_task(copy_trader.stop())
    sys.exit(0)

async def main():
    """Main function"""
    global copy_trader
    
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nRequired configuration in .env file:")
        print("  - MASTER_WALLET_ADDRESS: Wallet address to copy from")
        print("  - PRIVATE_KEY_ENCRYPTED: Your encrypted trading wallet private key")
        print("  - YELLOWSTONE_GRPC_URL: Yellow Stone Geyser gRPC endpoint")
        print("\nOptional configuration:")
        print("  - RPC_ENDPOINT: Solana RPC endpoint (default: testnet)")
        print("  - NETWORK: testnet or mainnet (default: testnet)")
        print("\nTo encrypt your wallet, run: python encrypt_wallet.py")
        print("See env.example for template (copy to .env and fill in values)")
        return
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize Telegram bot if available
    global telegram_monitor
    if TELEGRAM_AVAILABLE:
        try:
            telegram_monitor = TelegramMonitor()
            await telegram_monitor.initialize()
            # Set copy_trader reference after initialization
            if copy_trader:
                telegram_monitor.copy_trader = copy_trader
                telegram_monitor.trade_db = copy_trader.trade_db
            print("✅ Telegram monitoring enabled")
            # Keep Telegram bot running in background
            # The polling is already started in initialize()
        except Exception as e:
            print(f"⚠️ Telegram bot not configured: {e}")
            print("   Bot will continue without Telegram notifications")
            telegram_monitor = None
    
    # Initialize and start copy trader
    copy_trader = CopyTrader()
    
    # Update telegram_monitor with copy_trader reference
    if telegram_monitor:
        telegram_monitor.copy_trader = copy_trader
        telegram_monitor.trade_db = copy_trader.trade_db
    
    try:
        print("=" * 50)
        print("Solana Copy Trading Bot")
        print(f"Network: {Config.NETWORK}")
        print(f"Master Wallet: {Config.MASTER_WALLET_ADDRESS}")
        print(f"Max Latency: {Config.MAX_LATENCY_MS}ms")
        if telegram_monitor:
            print("📱 Telegram monitoring: Enabled")
        print("=" * 50)
        
        await copy_trader.start()
        
        # Update Telegram stats if available
        if telegram_monitor:
            stats = copy_trader.get_stats()
            stats["is_running"] = True
            await telegram_monitor.update_stats(stats)
        
        # Keep running
        last_stats_update = 0
        while copy_trader.is_running:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            # Get stats
            stats = copy_trader.get_stats()
            stats["is_running"] = copy_trader.is_running
            
            # Print stats periodically (every 30 seconds)
            import time
            current_time = time.time()
            if current_time - last_stats_update > 30:
                if stats["total_copies"] > 0:
                    print(f"\n📊 Stats: {stats['successful_copies']}/{stats['total_copies']} successful | "
                          f"Avg latency: {stats['avg_latency_ms']:.2f}ms")
                last_stats_update = current_time
            
            # Update Telegram stats periodically (every 30 seconds or when new trades)
            if telegram_monitor:
                if stats.get("total_copies", 0) > 0:
                    await telegram_monitor.update_stats(stats)
    
    except KeyboardInterrupt:
        print("\nReceived interrupt signal")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if copy_trader:
            await copy_trader.stop()
        if telegram_monitor:
            await telegram_monitor.stop()

if __name__ == "__main__":
    asyncio.run(main())

