"""Token encryption service using Fernet symmetric encryption.

This module provides secure encryption and decryption of Spotify access tokens
before storing them in the database.
"""

import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TokenEncryption:
    """Handles encryption and decryption of tokens using Fernet symmetric encryption."""
    
    def __init__(self):
        """Initialize the encryption service with the encryption key from environment."""
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        
        # Ensure the key is properly encoded
        if isinstance(key, str):
            key = key.encode()
        
        try:
            self.cipher = Fernet(key)
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")
    
    def encrypt(self, token: str) -> str:
        """
        Encrypt a token.
        
        Args:
            token: The plaintext token to encrypt
            
        Returns:
            The encrypted token as a string
            
        Raises:
            ValueError: If token is empty or None
        """
        if not token:
            raise ValueError("Token cannot be empty or None")
        
        encrypted_bytes = self.cipher.encrypt(token.encode())
        return encrypted_bytes.decode()
    
    def decrypt(self, encrypted_token: str) -> str:
        """
        Decrypt a token.
        
        Args:
            encrypted_token: The encrypted token to decrypt
            
        Returns:
            The decrypted plaintext token
            
        Raises:
            ValueError: If encrypted_token is empty or None
            cryptography.fernet.InvalidToken: If the token is invalid or corrupted
        """
        if not encrypted_token:
            raise ValueError("Encrypted token cannot be empty or None")
        
        decrypted_bytes = self.cipher.decrypt(encrypted_token.encode())
        return decrypted_bytes.decode()


# Singleton instance for use across the application
_encryptor = None


def get_encryptor() -> TokenEncryption:
    """
    Get the singleton TokenEncryption instance.
    
    Returns:
        TokenEncryption: The encryption service instance
    """
    global _encryptor
    if _encryptor is None:
        _encryptor = TokenEncryption()
    return _encryptor
