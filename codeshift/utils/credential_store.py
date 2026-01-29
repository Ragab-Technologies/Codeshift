"""Encrypted credential storage for Codeshift CLI."""

import base64
import getpass
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Config directory for storing credentials
CONFIG_DIR = Path.home() / ".config" / "codeshift"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
ENCRYPTED_CREDENTIALS_FILE = CONFIG_DIR / "credentials.enc"


class CredentialDecryptionError(Exception):
    """Raised when credentials cannot be decrypted."""

    pass


class CredentialStore:
    """Encrypted credential storage using Fernet encryption."""

    def __init__(self) -> None:
        """Initialize the credential store."""
        self._cipher = self._create_cipher()

    def _get_machine_id(self) -> str:
        """Generate a unique machine identifier using MAC address and username.

        Returns:
            A string combining MAC address and username for machine identification.
        """
        # Get MAC address
        mac = uuid.getnode()
        mac_str = hex(mac)

        # Get username
        username = getpass.getuser()

        # Combine them
        return f"{mac_str}-{username}"

    def _create_cipher(self) -> Fernet:
        """Create a Fernet cipher using PBKDF2 key derivation.

        Returns:
            A Fernet cipher instance for encryption/decryption.
        """
        machine_id = self._get_machine_id()

        # Use a fixed salt based on the application name
        # This ensures the same key is derived on the same machine
        salt = b"codeshift-credential-store-v1"

        # Derive a key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # OWASP recommended minimum for PBKDF2-SHA256
        )

        key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
        return Fernet(key)

    def save_credentials(self, credentials: dict[str, Any]) -> None:
        """Save credentials to encrypted storage.

        Args:
            credentials: Dictionary containing credential data to store.
        """
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Convert to JSON and encrypt
        json_data = json.dumps(credentials)
        encrypted_data = self._cipher.encrypt(json_data.encode())

        # Write encrypted data
        ENCRYPTED_CREDENTIALS_FILE.write_bytes(encrypted_data)
        os.chmod(ENCRYPTED_CREDENTIALS_FILE, 0o600)

        # Remove legacy plaintext file if it exists
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()

    def load_credentials(self) -> dict[str, Any] | None:
        """Load credentials from encrypted storage.

        Returns:
            Dictionary containing credential data, or None if not found.

        Raises:
            CredentialDecryptionError: If credentials exist but cannot be decrypted.
        """
        # First try to migrate legacy credentials if they exist
        self._migrate_legacy_credentials()

        if not ENCRYPTED_CREDENTIALS_FILE.exists():
            return None

        try:
            encrypted_data = ENCRYPTED_CREDENTIALS_FILE.read_bytes()
            decrypted_data = self._cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except InvalidToken as e:
            raise CredentialDecryptionError(
                "Failed to decrypt credentials. This may happen if credentials were "
                "created on a different machine or user account. Please run 'codeshift login' again."
            ) from e
        except (OSError, json.JSONDecodeError) as e:
            raise CredentialDecryptionError(
                f"Failed to read credentials: {e}"
            ) from e

    def clear_credentials(self) -> None:
        """Clear all stored credentials."""
        if ENCRYPTED_CREDENTIALS_FILE.exists():
            ENCRYPTED_CREDENTIALS_FILE.unlink()

        # Also remove legacy file if present
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()

    def _migrate_legacy_credentials(self) -> None:
        """Migrate plaintext credentials to encrypted storage.

        If legacy plaintext credentials exist, read them, encrypt them,
        and remove the plaintext file.
        """
        if not CREDENTIALS_FILE.exists():
            return

        # Don't migrate if encrypted file already exists
        if ENCRYPTED_CREDENTIALS_FILE.exists():
            # Just remove the legacy file
            CREDENTIALS_FILE.unlink()
            return

        try:
            # Read plaintext credentials
            plaintext_data = CREDENTIALS_FILE.read_text()
            credentials = json.loads(plaintext_data)

            # Save as encrypted
            self.save_credentials(credentials)

            # The save_credentials method will remove the legacy file
        except (OSError, json.JSONDecodeError):
            # If we can't read the legacy file, just remove it
            CREDENTIALS_FILE.unlink()


# Singleton instance
_credential_store: CredentialStore | None = None


def get_credential_store() -> CredentialStore:
    """Get the singleton CredentialStore instance.

    Returns:
        The shared CredentialStore instance.
    """
    global _credential_store
    if _credential_store is None:
        _credential_store = CredentialStore()
    return _credential_store
