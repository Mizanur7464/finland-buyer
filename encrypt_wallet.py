"""
Helper script to encrypt a wallet private key
"""
from wallet_manager import WalletManager
import getpass

def main():
    """Encrypt a wallet private key"""
    print("Wallet Encryption Tool")
    print("=" * 50)
    
    # Get password
    password = getpass.getpass("Enter encryption password (or press Enter for default): ")
    if not password:
        password = None
        print("Using default password (change in production!)")
    
    wallet_manager = WalletManager(password)
    
    # Get private key
    print("\nEnter your Solana private key (base58 format):")
    private_key = input().strip()
    
    if not private_key:
        print("Error: Private key cannot be empty")
        return
    
    # Encrypt
    try:
        encrypted_key = wallet_manager.encrypt_private_key(private_key)
        print("\n" + "=" * 50)
        print("Encrypted Private Key:")
        print("=" * 50)
        print(encrypted_key)
        print("=" * 50)
        print("\nAdd this to your .env file as PRIVATE_KEY_ENCRYPTED")
        print("Keep your password secure!")
    except Exception as e:
        print(f"Error encrypting key: {e}")

if __name__ == "__main__":
    main()

