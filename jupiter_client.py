"""
Jupiter aggregator client for DEX swaps
"""
import aiohttp
import asyncio
import socket
from typing import Dict, Optional
from solders.pubkey import Pubkey
from config import Config

# Try to import httpx as fallback
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Try to import requests as fallback (better DNS handling on Windows)
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

class JupiterClient:
    """Client for Jupiter aggregator API"""
    
    BASE_URL = "https://quote-api.jup.ag/v6"
    SWAP_URL = "https://quote-api.jup.ag/v6/swap"
    
    # Hardcoded IP addresses for quote-api.jup.ag (fallback if DNS fails)
    # These are Cloudflare IPs that host the domain
    JUPITER_API_IPS = [
        "104.21.0.0",  # Cloudflare IP range
        "172.67.0.0",  # Cloudflare IP range
    ]
    
    # Known token addresses (SOL on testnet/mainnet)
    SOL_MINT_MAINNET = "So11111111111111111111111111111111111111112"
    SOL_MINT_TESTNET = "So11111111111111111111111111111111111111112"  # Same on testnet
    
    def __init__(self):
        self.config = Config
        self._resolved_ip = None  # Cache resolved IP address
    
    def _resolve_dns(self, hostname: str) -> Optional[str]:
        """
        Manually resolve DNS using nslookup (workaround for Windows DNS issues)
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            IP address or None if failed
        """
        try:
            # First try: Use socket.getaddrinfo
            result = socket.getaddrinfo(hostname, 443, socket.AF_INET, socket.SOCK_STREAM)
            if result:
                ip_address = result[0][4][0]
                print(f"✓ DNS resolved (socket): {hostname} -> {ip_address}")
                return ip_address
        except Exception:
            pass
        
        # Fallback 1: Try using dig command (Linux servers - most reliable)
        try:
            import subprocess
            import os
            # Use dig if available (Linux)
            if os.path.exists('/usr/bin/dig') or os.path.exists('/bin/dig'):
                result = subprocess.run(
                    ['dig', '+short', hostname, '@8.8.8.8'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    ip = result.stdout.strip().split('\n')[0].strip()
                    # Validate IP
                    if ip and ip.count('.') == 3:
                        try:
                            socket.inet_aton(ip)
                            print(f"✓ DNS resolved (dig): {hostname} -> {ip}")
                            return ip
                        except:
                            pass
        except Exception as e:
            print(f"⚠️ dig command failed: {e}")
        
        # Fallback 2: Try using DNS over HTTPS (Google)
        try:
            import json
            import urllib.request
            # Use Google's DNS over HTTPS
            doh_url = f"https://dns.google/resolve?name={hostname}&type=A"
            req = urllib.request.Request(doh_url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
                # Google DoH uses 'Answer' field
                if 'Answer' in data and len(data['Answer']) > 0:
                    for answer in data['Answer']:
                        if answer.get('type') == 1:  # A record
                            ip_address = answer.get('data', '').strip()
                            if ip_address:
                                try:
                                    socket.inet_aton(ip_address)
                                    print(f"✓ DNS resolved (Google DoH): {hostname} -> {ip_address}")
                                    return ip_address
                                except:
                                    continue
        except Exception as e:
            print(f"⚠️ Google DoH failed: {e}")
        
        # Fallback 2: Try Cloudflare DoH
        try:
            import json
            import urllib.request
            doh_url = f"https://cloudflare-dns.com/dns-query?name={hostname}&type=A"
            req = urllib.request.Request(doh_url, headers={'Accept': 'application/dns-json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
                if 'Answer' in data and len(data['Answer']) > 0:
                    for answer in data['Answer']:
                        if answer.get('type') == 1:  # A record
                            ip_address = answer.get('data', '').strip()
                            if ip_address:
                                try:
                                    socket.inet_aton(ip_address)
                                    print(f"✓ DNS resolved (Cloudflare DoH): {hostname} -> {ip_address}")
                                    return ip_address
                                except:
                                    continue
        except Exception as e:
            print(f"⚠️ Cloudflare DoH failed: {e}")
        
        # Fallback 3: Use requests library (better DNS handling on Windows)
        if REQUESTS_AVAILABLE:
            try:
                import requests
                # requests library uses system DNS which might work better
                response = requests.get(f"https://{hostname}", timeout=5, allow_redirects=False)
                # Extract IP from connection
                if hasattr(response.raw, '_connection') and hasattr(response.raw._connection, 'sock'):
                    sock = response.raw._connection.sock
                    if sock:
                        peer = sock.getpeername()
                        if peer:
                            ip_address = peer[0]
                            print(f"✓ DNS resolved (requests): {hostname} -> {ip_address}")
                            return ip_address
            except Exception as e:
                print(f"⚠️ requests DNS resolution failed: {e}")
        
        # Final fallback: Use hardcoded IP for quote-api.jup.ag
        if hostname == 'quote-api.jup.ag':
            # Try to resolve using dig command (Linux)
            try:
                import subprocess
                result = subprocess.run(
                    ['dig', '+short', hostname, '@8.8.8.8'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    ip = result.stdout.strip().split('\n')[0]
                    if ip and ip.count('.') == 3:
                        try:
                            socket.inet_aton(ip)
                            print(f"✓ DNS resolved (dig): {hostname} -> {ip}")
                            return ip
                        except:
                            pass
            except:
                pass
            
            # Last resort: Try common Cloudflare IPs
            print(f"⚠️ Trying hardcoded IP addresses for {hostname}...")
            # Note: We can't use hardcoded IPs directly due to SSL certificate validation
            # But we can try to get the actual IP from a DNS lookup service
        
        # Final fallback: Return None (will use httpx or other fallback)
        print(f"❌ All DNS resolution methods failed for {hostname}")
        
        # Fallback 2: Use nslookup with type A explicitly
        try:
            import subprocess
            # Use nslookup with explicit A record query
            result = subprocess.run(
                ['nslookup', '-type=A', hostname, '8.8.8.8'],
                capture_output=True,
                text=True,
                timeout=10,
                shell=True
            )
            if result.returncode == 0:
                # Parse IP from nslookup output using regex
                import re
                ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
                all_ips = re.findall(ip_pattern, result.stdout)
                for ip in all_ips:
                    if ip != '8.8.8.8' and ip:
                        try:
                            socket.inet_aton(ip)
                            print(f"✓ DNS resolved (nslookup): {hostname} -> {ip}")
                            return ip
                        except:
                            continue
        except Exception as e:
            print(f"⚠️ nslookup DNS resolution failed: {e}")
        
        return None
    
    async def _get_quote_with_requests(self, url: str, params: Dict) -> Optional[Dict]:
        """
        Get quote using requests library (better DNS handling on Windows)
        """
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            import requests
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, params=params, timeout=15)
            )
            if response.status_code == 200:
                print(f"✓ Quote received via requests library")
                return response.json()
            else:
                print(f"❌ Jupiter quote error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"⚠️ requests library failed: {e}")
            return None
    
    async def _get_quote_with_fallback(self, url: str, params: Dict) -> Optional[Dict]:
        """
        Get quote using aiohttp with IP address fallback if DNS fails
        
        Args:
            url: Full URL to request
            params: Query parameters
            
        Returns:
            Response JSON or None if failed
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        # First try: Use aiohttp with hostname
        try:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=0,
                use_dns_cache=False,
                force_close=True,
                family=socket.AF_INET,
            )
            timeout = aiohttp.ClientTimeout(total=15, connect=10)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        print(f"❌ Jupiter quote error: {response.status} - {error_text}")
                        return None
        except Exception as e:
            error_str = str(e)
            if "getaddrinfo failed" in error_str or "Name resolution failed" in error_str or "11001" in error_str:
                # Fallback: Resolve DNS manually and use IP address
                print(f"⚠️ aiohttp DNS failed, trying manual DNS resolution...")
                ip_address = self._resolve_dns(hostname)
                
                if ip_address:
                    # Use IP address with Host header for SSL
                    url_with_ip = url.replace(hostname, ip_address)
                    headers = {'Host': hostname}  # Important for SSL certificate validation
                    
                    try:
                        connector = aiohttp.TCPConnector(
                            limit=100,
                            limit_per_host=30,
                            ttl_dns_cache=0,
                            use_dns_cache=False,
                            force_close=True,
                            family=socket.AF_INET,
                        )
                        timeout = aiohttp.ClientTimeout(total=15, connect=10)
                        
                        # Create SSL context that doesn't verify hostname (since we're using IP)
                        import ssl
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE
                        
                        # Update connector with SSL context
                        connector = aiohttp.TCPConnector(
                            limit=100,
                            limit_per_host=30,
                            ttl_dns_cache=0,
                            use_dns_cache=False,
                            force_close=True,
                            family=socket.AF_INET,
                            ssl=ssl_context
                        )
                        
                        async with aiohttp.ClientSession(
                            connector=connector,
                            timeout=timeout
                        ) as session:
                            async with session.get(
                                url_with_ip,
                                params=params,
                                headers=headers
                            ) as response:
                                if response.status == 200:
                                    print(f"✓ Successfully connected using IP address")
                                    return await response.json()
                                else:
                                    error_text = await response.text()
                                    print(f"❌ Jupiter quote error (IP): {response.status} - {error_text}")
                                    return None
                    except Exception as ip_error:
                        print(f"❌ IP address connection failed: {ip_error}")
                        # Final fallback: Try httpx
                        if HTTPX_AVAILABLE:
                            print(f"⚠️ Trying httpx as final fallback...")
                            try:
                                async with httpx.AsyncClient(timeout=15.0) as client:
                                    response = await client.get(url, params=params)
                                    if response.status_code == 200:
                                        print(f"✓ httpx fallback succeeded")
                                        return response.json()
                                    else:
                                        print(f"❌ httpx error: {response.status_code}")
                                        return None
                            except Exception as httpx_error:
                                print(f"❌ httpx fallback also failed: {httpx_error}")
                                return None
                        return None
                else:
                    print(f"❌ Could not resolve DNS for {hostname}")
                    return None
            else:
                raise  # Re-raise if it's a different error
        
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
            # Retry logic for network issues
            max_retries = 5  # Increased retries
            
            for attempt in range(max_retries):
                try:
                    params = {
                        "inputMint": input_mint,
                        "outputMint": output_mint,
                        "amount": str(amount),
                        "slippageBps": str(slippage_bps),
                    }
                    
                    url = f"{self.BASE_URL}/quote"
                    
                    # First try: Use requests library (better DNS on Windows)
                    if REQUESTS_AVAILABLE and attempt == 0:
                        quote = await self._get_quote_with_requests(url, params)
                        if quote:
                            return quote
                    
                    # Fallback: Use aiohttp with DNS resolution
                    quote = await self._get_quote_with_fallback(url, params)
                    
                    if quote:
                        return quote
                    else:
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            print(f"⚠️ Quote request failed (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        return None
                except (aiohttp.ClientConnectorError, aiohttp.ClientError) as e:
                    # Clean up connector on error (session is already closed by context manager)
                    try:
                        if 'connector' in locals():
                            await connector.close()
                    except:
                        pass
                    error_str = str(e)
                    if "getaddrinfo failed" in error_str or "Name resolution failed" in error_str:
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                            print(f"⚠️ DNS resolution failed (attempt {attempt+1}/{max_retries}): {e}")
                            print(f"   Retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"❌ DNS resolution failed after {max_retries} attempts")
                            print(f"   Error: {e}")
                            print(f"   Possible causes:")
                            print(f"   1. No internet connection")
                            print(f"   2. DNS server issue")
                            print(f"   3. Firewall blocking quote-api.jup.ag")
                            print(f"   4. Jupiter API temporarily down")
                            return None
                    elif attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"⚠️ Network error (attempt {attempt+1}/{max_retries}): {e}, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Error getting Jupiter quote after {max_retries} attempts: {e}")
                        return None
                except asyncio.TimeoutError as e:
                    # Clean up connector on timeout (session is already closed by context manager)
                    try:
                        if 'connector' in locals():
                            await connector.close()
                    except:
                        pass
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"⚠️ Timeout error (attempt {attempt+1}/{max_retries}): {e}, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Timeout getting Jupiter quote after {max_retries} attempts")
                        return None
                except RuntimeError as e:
                    # Handle "Session is closed" error
                    if "Session is closed" in str(e):
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            print(f"⚠️ Session closed error (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            print(f"❌ Session closed error after {max_retries} attempts")
                            return None
                    else:
                        raise  # Re-raise if it's a different RuntimeError
                        
        except Exception as e:
            print(f"❌ Unexpected error getting Jupiter quote: {e}")
            import traceback
            traceback.print_exc()
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
                "prioritizationFeeLamports": priority_fee_lamports
            }
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Try aiohttp first
                    connector = aiohttp.TCPConnector(
                        limit=100,
                        limit_per_host=30,
                        ttl_dns_cache=0,
                        use_dns_cache=False,
                        force_close=True,
                        family=socket.AF_INET,
                    )
                    timeout = aiohttp.ClientTimeout(total=15, connect=10)
                    
                    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                        async with session.post(self.SWAP_URL, json=swap_request) as response:
                            if response.status == 200:
                                swap_data = await response.json()
                                return swap_data
                            else:
                                error_text = await response.text()
                                print(f"❌ Jupiter swap error: {response.status} - {error_text}")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(1)
                                    continue
                                return None
                except Exception as e:
                    error_str = str(e)
                    if "getaddrinfo failed" in error_str and HTTPX_AVAILABLE:
                        # Fallback to httpx (better DNS handling)
                        print(f"⚠️ aiohttp DNS failed for swap, trying httpx fallback...")
                        try:
                            async with httpx.AsyncClient(timeout=15.0) as client:
                                response = await client.post(self.SWAP_URL, json=swap_request)
                                if response.status_code == 200:
                                    print(f"✓ httpx fallback succeeded for swap")
                                    return response.json()
                                else:
                                    print(f"❌ httpx swap error: {response.status_code}")
                                    if attempt < max_retries - 1:
                                        await asyncio.sleep(1)
                                        continue
                                    return None
                        except Exception as httpx_error:
                            print(f"❌ httpx fallback also failed: {httpx_error}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(1)
                                continue
                            return None
                    else:
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            print(f"⚠️ Network error getting swap (attempt {attempt+1}/{max_retries}): {e}, retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise
                except (aiohttp.ClientConnectorError, aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as e:
                    # Clean up connector on error (session is already closed by context manager)
                    try:
                        if 'connector' in locals():
                            await connector.close()
                    except:
                        pass
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"⚠️ Network error getting swap (attempt {attempt+1}/{max_retries}): {e}, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Error getting Jupiter swap after {max_retries} attempts: {e}")
                        return None
                        
        except Exception as e:
            print(f"❌ Unexpected error getting Jupiter swap: {e}")
            import traceback
            traceback.print_exc()
            return None

