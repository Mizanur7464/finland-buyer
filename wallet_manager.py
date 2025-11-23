"""
Encrypted wallet management for secure private key storage
"""
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from solders.keypair import Keypair
from solders.pubkey import Pubkey
import base58
import os

class WalletManager:
    """Manages encrypted wallet operations"""
    
    def __init__(self, password: str = None):
        """
        Initialize wallet manager
        
        Args:
            password: Password for encryption (if None, uses default from env)
        """
        self.password = password or os.getenv("WALLET_PASSWORD", "default_password_change_me")
        self.cipher = self._create_cipher()
    
    def _create_cipher(self) -> Fernet:
        """Create Fernet cipher from password"""
        password_bytes = self.password.encode()
        salt = b'solana_bot_salt'  # In production, use random salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        return Fernet(key)
    
    def encrypt_private_key(self, private_key: str) -> str:
        """
        Encrypt a private key
        
        Args:
            private_key: Base58 encoded private key string
            
        Returns:
            Encrypted private key string
        """
        private_key_bytes = private_key.encode()
        encrypted = self.cipher.encrypt(private_key_bytes)
        return encrypted.decode()
    
    def decrypt_private_key(self, encrypted_key: str) -> str:
        """
        Decrypt a private key
        
        Args:
            encrypted_key: Encrypted private key string
            
        Returns:
            Decrypted private key string (base58)
        """
        encrypted_bytes = encrypted_key.encode()
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted.decode()
    
    def load_keypair(self, encrypted_key: str) -> Keypair:
        """
        Load Keypair from encrypted private key
        
        Args:
            encrypted_key: Encrypted private key string
            
        Returns:
            Solana Keypair object
        """
        private_key_str = self.decrypt_private_key(encrypted_key)
        private_key_bytes = base58.b58decode(private_key_str)
        return Keypair.from_bytes(private_key_bytes)
    
    def generate_new_keypair(self) -> tuple[str, str]:
        """
        Generate a new keypair and return both encrypted and unencrypted versions
        
        Returns:
            Tuple of (encrypted_private_key, public_key_address)
        """
        keypair = Keypair()
        private_key_bytes = bytes(keypair)
        private_key_str = base58.b58encode(private_key_bytes).decode()
        encrypted_key = self.encrypt_private_key(private_key_str)
        public_key = str(keypair.pubkey())
        
        return encrypted_key, public_key

