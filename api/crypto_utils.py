"""
Encryption/decryption utilities for sensitive fields like API keys.
Uses Fernet (AES-128-CBC + HMAC-SHA256) for authenticated symmetric encryption.

Generate a new key:
    python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
"""
import os
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    raw = os.environ.get('API_KEY_ENCRYPTION_KEY')
    if not raw:
        raise ValueError("API_KEY_ENCRYPTION_KEY environment variable is not set")
    return Fernet(raw.encode())


def encrypt_api_key(plaintext: str) -> str:
    """
    Encrypt an API key. Returns a URL-safe base64 ciphertext string for DB storage.
    Raises ValueError if the env var is missing or plaintext is empty.
    """
    if not plaintext or not plaintext.strip():
        raise ValueError("Cannot encrypt an empty API key")
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """
    Decrypt an API key. Returns the original plaintext.
    Raises ValueError if the env var is missing, the token is invalid,
    or the ciphertext has been tampered with.
    """
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError(
            "Failed to decrypt API key — ciphertext may be corrupted "
            "or encrypted with a different key"
        )
