"""
Yellow Stone Geyser gRPC client for monitoring Solana transactions
"""
import asyncio
from typing import Callable, Optional
import grpc
from grpc import aio
from config import Config

# Import generated proto stubs
try:
    import geyser_pb2
    import geyser_pb2_grpc
    PROTO_AVAILABLE = True
except ImportError:
    PROTO_AVAILABLE = False
    print("⚠️ Proto files not found. Run: python -m grpc_tools.protoc --proto_path=proto --python_out=. --grpc_python_out=. proto/*.proto")

class YellowstoneGeyserClient:
    """Client for Yellow Stone Geyser gRPC service"""
    
    def __init__(self, grpc_url: str = None, token: str = None):
        """
        Initialize Yellow Stone Geyser client
        
        Args:
            grpc_url: gRPC endpoint URL (e.g., grpcs://smart-holy-pool.solana-testnet.quiknode.pro:10000)
            token: Authentication token for QuickNode (optional if set in config)
        """
        self.grpc_url = grpc_url or Config.YELLOWSTONE_GRPC_URL
        self.token = token or Config.YELLOWSTONE_GRPC_TOKEN
        self.channel = None
        self.stub = None
        self.is_connected = False
        self.metadata = []
        
        # Add token to metadata for authentication
        # QuickNode uses 'x-token' header for authentication
        if self.token:
            # QuickNode token authentication format
            self.metadata = [('x-token', self.token)]
    
    async def connect(self):
        """Establish gRPC connection"""
        try:
            # Parse URL (format: grpc://host:port or grpcs://host:port)
            if self.grpc_url.startswith("grpcs://"):
                # Use secure channel (QuickNode uses HTTPS/gRPC over SSL)
                credentials = grpc.ssl_channel_credentials()
                endpoint = self.grpc_url.replace("grpcs://", "").replace("https://", "")
                # Remove trailing slash if present
                endpoint = endpoint.rstrip('/')
                # Add keepalive options for better connection stability
                options = [
                    ('grpc.keepalive_time_ms', 30000),
                    ('grpc.keepalive_timeout_ms', 5000),
                    ('grpc.keepalive_permit_without_calls', True),
                    ('grpc.http2.max_pings_without_data', 0),
                ]
                self.channel = grpc.aio.secure_channel(endpoint, credentials, options=options)
                print(f"Connecting to Yellow Stone Geyser (secure) at {endpoint}...")
            elif self.grpc_url.startswith("grpc://"):
                # Use insecure channel
                endpoint = self.grpc_url.replace("grpc://", "")
                self.channel = grpc.aio.insecure_channel(endpoint)
                print(f"Connecting to Yellow Stone Geyser (insecure) at {endpoint}...")
            else:
                # If no protocol specified, assume secure (QuickNode default)
                credentials = grpc.ssl_channel_credentials()
                endpoint = self.grpc_url
                if "://" not in endpoint:
                    endpoint = endpoint if ":" in endpoint else f"{endpoint}:10000"
                self.channel = grpc.aio.secure_channel(endpoint, credentials)
                print(f"Connecting to Yellow Stone Geyser (assumed secure) at {endpoint}...")
            
            # Initialize stub from proto
            if PROTO_AVAILABLE:
                self.stub = geyser_pb2_grpc.GeyserStub(self.channel)
                print(f"✓ gRPC stub initialized")
            else:
                self.stub = None
                print(f"⚠️ Proto stubs not available - using fallback mode")
            
            self.is_connected = True
            print(f"✓ Connected to Yellow Stone Geyser at {self.grpc_url}")
            if self.token:
                print(f"✓ Authentication token configured")
        except Exception as e:
            print(f"✗ Error connecting to gRPC: {e}")
            raise
    
    async def subscribe_to_account(self, account_address: str, callback: Callable):
        """
        Subscribe to account changes for a specific wallet
        
        Args:
            account_address: Solana wallet address to monitor
            callback: Async function to call when transaction detected
        """
        if not self.is_connected:
            await self.connect()
        
        print(f"Subscribing to account: {account_address}")
        
        # Try to use proto-based subscription if stub is available
        if self.stub and PROTO_AVAILABLE:
            try:
                # Create subscription request for account monitoring
                filter_accounts = geyser_pb2.SubscribeRequestFilterAccounts()
                filter_accounts.account.append(account_address)
                
                # Create subscription request
                request = geyser_pb2.SubscribeRequest()
                # Accounts is a map, so assign directly
                request.accounts[account_address].CopyFrom(filter_accounts)
                # Use CommitmentLevel enum - CONFIRMED = 1
                request.commitment = geyser_pb2.CONFIRMED
                
                print(f"✓ Starting gRPC subscription...")
                
                # Create async iterator for request (stream-stream requires iterator)
                async def request_iterator():
                    yield request
                    # Keep connection alive - don't spam pings initially
                    # Let the connection establish first
                    await asyncio.sleep(60)  # Wait before first ping
                    ping_id = 1
                    while True:
                        await asyncio.sleep(30)  # Send ping every 30 seconds to keep connection alive
                        ping_request = geyser_pb2.SubscribeRequest()
                        ping_request.ping.id = ping_id
                        ping_id += 1
                        yield ping_request
                
                # Test connection with Ping first (skip if timeout)
                ping_test_passed = False
                try:
                    print(f"✓ Testing connection with Ping...")
                    ping_request = geyser_pb2.PingRequest(count=1)
                    ping_response = await asyncio.wait_for(
                        self.stub.Ping(ping_request, metadata=self.metadata),
                        timeout=3.0  # Shorter timeout
                    )
                    print(f"✓ Connection test successful (Pong received)")
                    ping_test_passed = True
                except asyncio.TimeoutError:
                    print(f"⚠️ Ping test timeout - continuing with subscription anyway")
                except Exception as ping_error:
                    print(f"⚠️ Connection test failed: {ping_error}")
                    print(f"   Continuing with subscription - server might be slow")
                
                # Subscribe and listen for updates
                print(f"✓ Starting subscription (this may take a few seconds)...")
                
                # Add timeout and retry logic
                try:
                    # Use longer timeout for initial connection
                    subscription_stream = self.stub.Subscribe(request_iterator(), metadata=self.metadata)
                    async for update in subscription_stream:
                        # Process different update types
                            if update.HasField('account'):
                                await callback({
                                    "type": "account",
                                    "account": update.account,
                                    "slot": update.account.slot,
                                    "update": update
                                })
                            elif update.HasField('transaction'):
                                await callback({
                                    "type": "transaction",
                                    "transaction": update.transaction,
                                    "slot": update.transaction.slot,
                                    "update": update
                                })
                            elif update.HasField('slot'):
                                # Slot updates
                                pass
                            elif update.HasField('ping'):
                                # Respond to ping
                                print(f"✓ Ping received from server")
                                pass
                            elif update.HasField('pong'):
                                # Pong received
                                print(f"✓ Pong received (connection alive)")
                                pass
                        
                except grpc.aio.AioRpcError as grpc_error:
                    error_code = grpc_error.code()
                    error_details = grpc_error.details()
                    
                    print(f"⚠️ gRPC subscription error: {error_code}")
                    print(f"   Details: {error_details}")
                    
                    # Handle specific error codes
                    if error_code == grpc.StatusCode.UNAVAILABLE:
                        print(f"⚠️ Server unavailable - possible causes:")
                        print(f"   1. QuickNode server temporarily down")
                        print(f"   2. Network connectivity issue")
                        print(f"   3. Authentication token issue")
                        print(f"   4. Firewall blocking connection")
                        print(f"\n   Retrying in 5 seconds...")
                        await asyncio.sleep(5)
                        # Retry once
                        try:
                            async for update in self.stub.Subscribe(request_iterator(), metadata=self.metadata):
                                if update.HasField('account'):
                                    await callback({
                                        "type": "account",
                                        "account": update.account,
                                        "slot": update.account.slot,
                                        "update": update
                                    })
                                elif update.HasField('transaction'):
                                    await callback({
                                        "type": "transaction",
                                        "transaction": update.transaction,
                                        "slot": update.transaction.slot,
                                        "update": update
                                    })
                        except Exception as retry_error:
                            print(f"⚠️ Retry failed: {retry_error}")
                            await self._subscribe_fallback(account_address, callback)
                    else:
                        print(f"⚠️ Falling back to placeholder mode")
                        await self._subscribe_fallback(account_address, callback)
                        
            except Exception as e:
                print(f"⚠️ gRPC subscription error: {e}")
                import traceback
                traceback.print_exc()
                print("⚠️ Falling back to placeholder mode")
                await self._subscribe_fallback(account_address, callback)
        else:
            # Fallback: Use WebSocket polling via RPC
            print("⚠️ Using fallback WebSocket subscription (proto files needed for full functionality)")
            await self._subscribe_fallback(account_address, callback)
    
    async def _subscribe_fallback(self, account_address: str, callback: Callable):
        """Fallback subscription using RPC polling - ACTUALLY WORKS"""
        import asyncio
        from solders.pubkey import Pubkey
        from solana.rpc.async_api import AsyncClient
        
        print(f"🔄 Switching to RPC-based transaction monitoring...")
        print(f"   Master wallet: {account_address}")
        print(f"   This will check for new transactions every 5 seconds")
        print(f"   ⚠️ Slower than gRPC but will actually work!")
        
        rpc_client = AsyncClient(Config.RPC_ENDPOINT)
        pubkey = Pubkey.from_string(account_address)
        
        last_signature = None
        check_count = 0
        
        try:
            # Get initial signature to establish baseline
            initial_sigs = await rpc_client.get_signatures_for_address(
                pubkey,
                limit=1,
                commitment="confirmed"
            )
            if initial_sigs.value and len(initial_sigs.value) > 0:
                last_signature = initial_sigs.value[0].signature
                print(f"✓ Initial transaction found: {last_signature}")
                print(f"✓ Now monitoring for NEW transactions...")
            else:
                print(f"✓ No previous transactions found. Monitoring for first transaction...")
                print(f"   Master wallet: {account_address}")
                print(f"   Will detect ANY new transaction from this wallet")
            
            while self.is_connected:
                try:
                    check_count += 1
                    if check_count % 12 == 0:  # Every minute
                        print(f"⏳ Still monitoring... (checked {check_count} times)")
                    
                    # Get recent transactions
                    signatures = await rpc_client.get_signatures_for_address(
                        pubkey,
                        limit=5,  # Check last 5 to catch any missed
                        commitment="confirmed"
                    )
                    
                    if signatures.value and len(signatures.value) > 0:
                        current_sig = signatures.value[0].signature
                        
                        # Check if this is a new transaction
                        # If last_signature is None, this is the first transaction
                        # If current_sig != last_signature, this is a new transaction
                        is_new_transaction = False
                        
                        if not last_signature:
                            # First transaction ever detected
                            is_new_transaction = True
                            print(f"\n🚨 FIRST TRANSACTION DETECTED!")
                        elif current_sig != last_signature:
                            # New transaction detected
                            is_new_transaction = True
                            print(f"\n🚨 NEW TRANSACTION DETECTED!")
                        
                        if is_new_transaction:
                            print(f"   Signature: {current_sig}")
                            print(f"   Previous: {last_signature if last_signature else 'None (first)'}")
                            
                            # Get full transaction details
                            try:
                                tx_info = await rpc_client.get_transaction(
                                    current_sig,
                                    commitment="confirmed",
                                    max_supported_transaction_version=0
                                )
                                
                                if tx_info.value:
                                    print(f"✓ Transaction details retrieved")
                                    
                                    # Call the callback with transaction data
                                    await callback({
                                        "type": "transaction",
                                        "transaction": tx_info.value,
                                        "signature": str(current_sig),
                                        "account": account_address,
                                        "update": tx_info.value
                                    })
                                else:
                                    print(f"⚠️ Transaction info is None for signature: {current_sig}")
                            except Exception as tx_error:
                                print(f"⚠️ Error fetching transaction details: {tx_error}")
                                import traceback
                                traceback.print_exc()
                        
                        # Update last signature to the most recent one
                        last_signature = current_sig
                    
                    # Wait 5 seconds before next check
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    print(f"⚠️ Polling error: {e}")
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            print(f"✓ Monitoring stopped")
        except Exception as e:
            print(f"✗ Fatal error in polling: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                await rpc_client.close()
            except:
                pass
    
    async def subscribe_to_transactions(self, wallet_address: str, callback: Callable):
        """
        Subscribe to transactions for a specific wallet
        
        Args:
            wallet_address: Master wallet address to monitor
            callback: Async function to call when transaction detected
        """
        await self.subscribe_to_account(wallet_address, callback)
    
    async def get_latest_block(self) -> Optional[dict]:
        """Get latest block information"""
        if not self.is_connected:
            await self.connect()
        
        # Placeholder - implement based on actual gRPC service
        return None
    
    async def close(self):
        """Close gRPC connection"""
        if self.channel:
            await self.channel.close()
            self.is_connected = False

