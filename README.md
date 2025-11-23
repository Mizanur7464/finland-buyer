# Solana Copy Trading Bot (Python gRPC)

High-performance copy trading bot for Solana DEX (Pumpkin/Radium) with sub-150ms latency.

## Features

- **Fast Copy Trading**: <150ms latency using Python gRPC
- **Yellow Stone Geyser Integration**: Real-time transaction monitoring
- **Same Block Execution**: Copy trades on the same block using node and VPs
- **Encrypted Wallet**: Secure wallet storage with encryption
- **Monitoring Dashboard**: Web-based dashboard for tracking trades
- **Slippage & Fees Management**: Automatic calculation and handling
- **Testnet Support**: Start on testnet before mainnet

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
   - Copy `env.example` to `.env`
   - Fill in the required values:
     - `MASTER_WALLET_ADDRESS`: Wallet address to copy from (get from buyer)
     - `PRIVATE_KEY_ENCRYPTED`: Your encrypted trading wallet key (run `python encrypt_wallet.py`)
     - `YELLOWSTONE_GRPC_URL`: Yellow Stone Geyser gRPC endpoint (get from buyer)
   - Optional: Adjust slippage, fees, and network settings

3. Run the bot:
```bash
python main.py
```

4. Access dashboard:
```
http://localhost:8000
```

## Architecture

- `main.py`: Main bot entry point
- `grpc_client.py`: Yellow Stone Geyser gRPC client
- `wallet_manager.py`: Encrypted wallet management
- `copy_trader.py`: Core copy trading logic
- `slippage_manager.py`: Slippage, fees, and tips calculation
- `dashboard/`: Web dashboard for monitoring

