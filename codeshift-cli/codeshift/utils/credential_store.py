"""Secure credential storage with encryption for Codeshift CLI."""

import getpass
import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Config directory for storing credentials
CONFIG_DIR = Path.home() / ".config" / "codeshift"
ENCRYPTED_CREDENTIALS_FILE = CONFIG_DIR / "credentials.enc"
LEGACY_CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


class CredentialDecryptionError(Exception):
    """Raised when credentials cannot be decrypted."""

    pass


class CredentialStore:
    """Handles encrypted credential storage.

    Uses Fernet symmetric encryption with a machine-specific key derived from
    the MAC address and username. This prevents credentials from being portable
    to other machines.
    """

    def __init__(self) -> None:
        """Initialize the credential store."""
        self._encryption_key: bytes | None = None

    def _get_machine_identifier(self) -> str:
        """Generate a machine-specific identifier.

        Combines the MAC address and username to create an identifier that is
        unique to this machine and user combination.
        """
        # Get MAC address (or a fallback UUID if unavailable)
        try:
            mac = uuid.getnode()
            # Check if we got a random fallback (indicated by the 8th bit being set)
            if (mac >> 40) % 2:
                # Fallback to a file-based identifier
                mac_str = self._get_or_create_machine_id()
            else:
                mac_str = format(mac, "012x")
        except Exception:
            mac_str = self._get_or_create_machine_id()

        # Get username
        try:
            username = getpass.getuser()
        except Exception:
            username = "unknown"

        return f"{mac_str}:{username}"

    def _get_or_create_machine_id(self) -> str:
        """Get or create a persistent machine ID file as fallback."""
        machine_id_file = CONFIG_DIR / ".machine_id"
        if machine_id_file.exists():
            try:
                return machine_id_file.read_text().strip()
            except OSError:
                pass

        # Create a new machine ID
        machine_id = uuid.uuid4().hex
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            machine_id_file.write_text(machine_id)
            os.chmod(machine_id_file, 0o600)
        except OSError:
            pass

        return machine_id

    def _derive_key(self) -> bytes:
        """Derive the encryption key from the machine identifier.

        Uses SHA-256 to derive a 32-byte key suitable for Fernet.
        """
        if self._encryption_key is not None:
            return self._encryption_key

        machine_id = self._get_machine_identifier()
        # Add a static salt to prevent rainbow table attacks
        salt = b"codeshift-credential-store-v1"
        key_material = machine_id.encode() + salt

        # Use SHA-256 and encode to base64 for Fernet (requires 32 bytes, base64 encoded)
        digest = hashlib.sha256(key_material).digest()
        import base64

        self._encryption_key = base64.urlsafe_b64encode(digest)
        return self._encryption_key

    def _get_fernet(self) -> Fernet:
        """Get a Fernet instance with the derived key."""
        return Fernet(self._derive_key())

    def save_credentials(self, credentials: dict[str, Any]) -> None:
        """Save credentials to disk with encryption.

        Args:
            credentials: Dictionary of credentials to save.
        """
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Serialize to JSON
        plaintext = json.dumps(credentials, indent=2).encode()

        # Encrypt
        fernet = self._get_fernet()
        ciphertext = fernet.encrypt(plaintext)

        # Write to file with restrictive permissions
        ENCRYPTED_CREDENTIALS_FILE.write_bytes(ciphertext)
        os.chmod(ENCRYPTED_CREDENTIALS_FILE, 0o600)

        logger.debug("Credentials saved to encrypted storage")

    def load_credentials(self) -> dict[str, Any] | None:
        """Load credentials from encrypted storage.

        Returns:
            Dictionary of credentials, or None if not found or decryption fails.

        Raises:
            CredentialDecryptionError: If decryption fails (file corrupted or
                credentials from different machine).
        """
        # First, check for and migrate legacy plaintext credentials
        if self._migrate_legacy_credentials():
            logger.info("Migrated legacy plaintext credentials to encrypted format")

        if not ENCRYPTED_CREDENTIALS_FILE.exists():
            return None

        try:
            ciphertext = ENCRYPTED_CREDENTIALS_FILE.read_bytes()
            fernet = self._get_fernet()
            plaintext = fernet.decrypt(ciphertext)
            return json.loads(plaintext.decode())
        except InvalidToken:
            raise CredentialDecryptionError(
                "Failed to decrypt credentials. This may happen if:\n"
                "  1. The credential file was moved from another machine\n"
                "  2. The credential file is corrupted\n"
                "  3. System identifiers have changed\n\n"
                "Please run 'codeshift logout' and 'codeshift login' again."
            )
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load credentials: {e}")
            return None

    def clear_credentials(self) -> None:
        """Delete stored credentials."""
        if ENCRYPTED_CREDENTIALS_FILE.exists():
            try:
                ENCRYPTED_CREDENTIALS_FILE.unlink()
                logger.debug("Encrypted credentials deleted")
            except OSError as e:
                logger.warning(f"Failed to delete credentials: {e}")

        # Also clean up legacy file if it exists
        if LEGACY_CREDENTIALS_FILE.exists():
            try:
                LEGACY_CREDENTIALS_FILE.unlink()
                logger.debug("Legacy credentials deleted")
            except OSError as e:
                logger.warning(f"Failed to delete legacy credentials: {e}")

    def _migrate_legacy_credentials(self) -> bool:
        """Migrate legacy plaintext credentials to encrypted format.

        Returns:
            True if migration was performed, False otherwise.
        """
        if not LEGACY_CREDENTIALS_FILE.exists():
            return False

        # Don't migrate if encrypted file already exists
        if ENCRYPTED_CREDENTIALS_FILE.exists():
            # Just delete the legacy file
            try:
                LEGACY_CREDENTIALS_FILE.unlink()
            except OSError:
                pass
            return False

        try:
            # Read legacy credentials
            legacy_data = json.loads(LEGACY_CREDENTIALS_FILE.read_text())

            # Save to encrypted storage
            self.save_credentials(legacy_data)

            # Delete legacy file
            LEGACY_CREDENTIALS_FILE.unlink()

            return True
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to migrate legacy credentials: {e}")
            return False


# Global instance for convenience
_credential_store: CredentialStore | None = None


def get_credential_store() -> CredentialStore:
    """Get the global credential store instance."""
    global _credential_store
    if _credential_store is None:
        _credential_store = CredentialStore()
    return _credential_store
