"""Secure credential storage with encryption.

This module provides encrypted storage for sensitive credentials like API keys.
Credentials are encrypted using Fernet (AES-128-CBC) with a key derived from
a machine-specific identifier using PBKDF2-SHA256.

Security features:
- AES-128 encryption via Fernet
- Machine-bound encryption key (prevents credential theft across machines)
- PBKDF2-SHA256 key derivation with 100,000 iterations
- File permissions restricted to owner only (0o600)
- Automatic migration from plaintext credentials with secure deletion
"""

import base64
import hashlib
import json
import logging
import os
import platform
import secrets
import uuid
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

# Try to import cryptography, provide helpful error if not installed
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore


class CredentialDecryptionError(Exception):
    """Raised when credentials cannot be decrypted.

    This typically occurs when:
    - Credentials were created on a different machine
    - The machine identifier has changed
    - The credential file is corrupted
    """

    def __init__(self, message: str | None = None):
        default_msg = (
            "Failed to decrypt credentials. This may happen if credentials were "
            "created on a different machine. Please run 'codeshift login' to "
            "re-authenticate."
        )
        super().__init__(message or default_msg)


class CredentialStore:
    """Secure encrypted credential storage.

    Credentials are encrypted using a key derived from a machine-specific
    identifier, making them non-portable between machines for security.

    Example:
        store = CredentialStore()
        store.save({"api_key": "secret123", "email": "user@example.com"})
        creds = store.load()
    """

    # Default paths
    DEFAULT_CONFIG_DIR = Path.home() / ".config" / "codeshift"
    CREDENTIALS_FILE = "credentials.enc"
    LEGACY_CREDENTIALS_FILE = "credentials.json"
    SALT_FILE = ".salt"

    # PBKDF2 parameters
    PBKDF2_ITERATIONS = 100_000
    KEY_LENGTH = 32  # 256 bits for Fernet

    def __init__(self, config_dir: Path | None = None):
        """Initialize the credential store.

        Args:
            config_dir: Directory for storing credentials. Defaults to ~/.config/codeshift
        """
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.credentials_path = self.config_dir / self.CREDENTIALS_FILE
        self.legacy_path = self.config_dir / self.LEGACY_CREDENTIALS_FILE
        self.salt_path = self.config_dir / self.SALT_FILE

        # Check if cryptography is available
        if not CRYPTOGRAPHY_AVAILABLE:
            logger.warning(
                "cryptography package not installed. "
                "Credentials will be stored in plaintext. "
                "Install with: pip install cryptography"
            )

    def _get_machine_identifier(self) -> str:
        """Get a stable machine identifier for key derivation.

        Combines multiple system attributes to create a stable identifier
        that persists across reboots but changes between machines.

        Returns:
            A string identifier unique to this machine.
        """
        components = []

        # Platform info (stable)
        components.append(platform.node())
        components.append(platform.system())
        components.append(platform.machine())

        # Try to get hardware UUID (most stable)
        try:
            if platform.system() == "Darwin":
                # macOS: Use IOPlatformUUID
                import subprocess

                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.split("\n"):
                    if "IOPlatformUUID" in line:
                        uuid_str = line.split('"')[-2]
                        components.append(uuid_str)
                        break
            elif platform.system() == "Linux":
                # Linux: Try machine-id
                for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                    try:
                        with open(path) as f:
                            components.append(f.read().strip())
                            break
                    except (OSError, PermissionError):
                        continue
            elif platform.system() == "Windows":
                # Windows: Use MachineGuid from registry
                try:
                    import winreg

                    key = winreg.OpenKey(  # type: ignore[attr-defined]
                        winreg.HKEY_LOCAL_MACHINE,  # type: ignore[attr-defined]
                        r"SOFTWARE\Microsoft\Cryptography",
                    )
                    machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]  # type: ignore[attr-defined]
                    components.append(machine_guid)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Could not get hardware UUID: {e}")

        # Fallback to UUID based on hostname (less stable but better than nothing)
        if len(components) < 4:
            components.append(str(uuid.getnode()))

        # Create hash of all components
        combined = "|".join(components)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _get_or_create_salt(self) -> bytes:
        """Get or create a random salt for key derivation.

        The salt is stored alongside credentials and is required for decryption.

        Returns:
            32-byte random salt.
        """
        if self.salt_path.exists():
            try:
                return self.salt_path.read_bytes()
            except OSError as e:
                logger.warning(f"Could not read salt file: {e}")

        # Generate new salt
        salt = secrets.token_bytes(32)

        # Save salt with restricted permissions
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.salt_path.write_bytes(salt)
        os.chmod(self.salt_path, 0o600)

        return salt

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive an encryption key from the machine identifier.

        Uses PBKDF2-SHA256 with 100,000 iterations for key derivation.

        Args:
            salt: Random salt for key derivation.

        Returns:
            32-byte encryption key suitable for Fernet.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError(
                "cryptography package required for encryption. "
                "Install with: pip install cryptography"
            )

        machine_id = self._get_machine_identifier()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
            backend=default_backend(),
        )

        key = kdf.derive(machine_id.encode())
        return base64.urlsafe_b64encode(key)

    def _encrypt(self, data: dict) -> bytes:
        """Encrypt credential data.

        Args:
            data: Dictionary of credentials to encrypt.

        Returns:
            Encrypted bytes.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            # Fallback to plaintext (with warning logged in __init__)
            return json.dumps(data).encode()

        salt = self._get_or_create_salt()
        key = self._derive_key(salt)
        f = Fernet(key)

        plaintext = json.dumps(data).encode()
        return f.encrypt(plaintext)

    def _decrypt(self, ciphertext: bytes) -> dict:
        """Decrypt credential data.

        Args:
            ciphertext: Encrypted bytes.

        Returns:
            Dictionary of credentials.

        Raises:
            CredentialDecryptionError: If decryption fails.
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            # Assume plaintext if cryptography not available
            try:
                return cast(dict[Any, Any], json.loads(ciphertext.decode()))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise CredentialDecryptionError(f"Invalid credential format: {e}") from e

        try:
            salt = self._get_or_create_salt()
            key = self._derive_key(salt)
            f = Fernet(key)

            plaintext = f.decrypt(ciphertext)
            return cast(dict[Any, Any], json.loads(plaintext.decode()))
        except InvalidToken as e:
            raise CredentialDecryptionError(
                "Failed to decrypt credentials. The encryption key may have changed "
                "(different machine or hardware change). Please run 'codeshift login' "
                "to re-authenticate."
            ) from e
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise CredentialDecryptionError(f"Corrupted credential data: {e}") from e

    def save(self, credentials: dict[str, Any]) -> None:
        """Save credentials securely.

        Args:
            credentials: Dictionary containing credentials (api_key, email, etc.)
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Encrypt and save
        encrypted = self._encrypt(credentials)
        self.credentials_path.write_bytes(encrypted)

        # Set restrictive permissions (owner read/write only)
        os.chmod(self.credentials_path, 0o600)

        logger.debug("Credentials saved securely")

    def load(self) -> dict[str, Any] | None:
        """Load credentials from secure storage.

        Automatically migrates from plaintext storage if found.

        Returns:
            Dictionary of credentials, or None if not found.

        Raises:
            CredentialDecryptionError: If credentials exist but cannot be decrypted.
        """
        # Check for encrypted credentials first
        if self.credentials_path.exists():
            try:
                ciphertext = self.credentials_path.read_bytes()
                return self._decrypt(ciphertext)
            except OSError as e:
                logger.error(f"Could not read credentials file: {e}")
                return None

        # Check for legacy plaintext credentials and migrate
        if self.legacy_path.exists():
            logger.info("Migrating credentials from plaintext to encrypted storage")
            try:
                plaintext = self.legacy_path.read_text()
                credentials: dict[str, Any] = json.loads(plaintext)

                # Save encrypted
                self.save(credentials)

                # Securely delete legacy file
                self._secure_delete(self.legacy_path)

                return credentials
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Could not migrate legacy credentials: {e}")
                return None

        return None

    def delete(self) -> None:
        """Delete stored credentials securely."""
        # Delete encrypted credentials
        if self.credentials_path.exists():
            self._secure_delete(self.credentials_path)

        # Also delete legacy file if it exists
        if self.legacy_path.exists():
            self._secure_delete(self.legacy_path)

        # Delete salt file
        if self.salt_path.exists():
            self._secure_delete(self.salt_path)

        logger.debug("Credentials deleted")

    def _secure_delete(self, path: Path) -> None:
        """Securely delete a file by overwriting before unlinking.

        Args:
            path: Path to the file to delete.
        """
        try:
            if path.exists():
                # Overwrite with random data
                size = path.stat().st_size
                if size > 0:
                    with open(path, "wb") as f:
                        f.write(secrets.token_bytes(size))
                        f.flush()
                        os.fsync(f.fileno())

                # Then delete
                path.unlink()
        except OSError as e:
            logger.warning(f"Could not securely delete {path}: {e}")
            # Try regular delete as fallback
            try:
                path.unlink()
            except OSError:
                pass

    def exists(self) -> bool:
        """Check if credentials exist.

        Returns:
            True if credentials file exists (encrypted or legacy).
        """
        return self.credentials_path.exists() or self.legacy_path.exists()


# Default credential store instance
_default_store: CredentialStore | None = None


def get_credential_store() -> CredentialStore:
    """Get the default credential store instance."""
    global _default_store
    if _default_store is None:
        _default_store = CredentialStore()
    return _default_store
