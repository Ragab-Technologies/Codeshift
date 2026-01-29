"""Quota management with thread-safe reservation system to prevent race conditions."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional


# Tier limits for monthly LLM migrations
TIER_LIMITS: Dict[str, int] = {
    "free": 0,
    "pro": 100,
    "unlimited": 999999,
}

# Reservation timeout in seconds (5 minutes)
RESERVATION_TIMEOUT_SECONDS = 300


@dataclass
class QuotaReservation:
    """Represents a reserved quota slot for an in-progress migration."""

    reservation_id: str
    user_id: str
    tier: str
    amount: int
    created_at: float = field(default_factory=time.time)
    confirmed: bool = False

    def is_stale(self, timeout_seconds: float = RESERVATION_TIMEOUT_SECONDS) -> bool:
        """Check if this reservation has exceeded the timeout."""
        return time.time() - self.created_at > timeout_seconds


class QuotaManager:
    """Thread-safe quota manager with reservation pattern to prevent race conditions.

    This manager ensures that concurrent migration requests don't exceed quota limits
    by using a reservation system:
    1. reserve_quota() - Atomically reserves quota before starting migration
    2. confirm_usage() - Confirms the reservation after successful migration
    3. release_quota() - Releases reservation if migration fails/cancelled

    The reservation pattern prevents the "check-then-act" race condition where
    multiple concurrent requests might each see available quota and proceed,
    exceeding the limit.
    """

    def __init__(self) -> None:
        """Initialize the quota manager with thread-safe data structures."""
        self._lock = threading.Lock()
        self._reservations: Dict[str, QuotaReservation] = {}
        # Track confirmed usage per user per billing period
        # In production, this would be backed by a database
        self._confirmed_usage: Dict[str, int] = {}

    def reserve_quota(
        self,
        user_id: str,
        tier: str,
        current_usage: int,
        amount: int = 1,
    ) -> Optional[str]:
        """Atomically reserve quota for a migration operation.

        Args:
            user_id: The user requesting the migration.
            tier: The user's subscription tier.
            current_usage: The user's current confirmed usage count.
            amount: Number of quota units to reserve.

        Returns:
            Reservation ID if successful, None if quota would be exceeded.
        """
        with self._lock:
            limit = TIER_LIMITS.get(tier, 0)

            # Calculate total pending reservations for this user
            pending_reserved = sum(
                r.amount
                for r in self._reservations.values()
                if r.user_id == user_id and not r.confirmed and not r.is_stale()
            )

            # Check if reservation would exceed limit
            total_committed = current_usage + pending_reserved + amount
            if total_committed > limit:
                return None

            # Create and store the reservation
            reservation_id = str(uuid.uuid4())
            reservation = QuotaReservation(
                reservation_id=reservation_id,
                user_id=user_id,
                tier=tier,
                amount=amount,
            )
            self._reservations[reservation_id] = reservation

            return reservation_id

    def release_quota(self, reservation_id: str) -> bool:
        """Release a quota reservation (e.g., when migration fails or is cancelled).

        Args:
            reservation_id: The ID of the reservation to release.

        Returns:
            True if the reservation was found and released, False otherwise.
        """
        with self._lock:
            if reservation_id in self._reservations:
                del self._reservations[reservation_id]
                return True
            return False

    def confirm_usage(self, reservation_id: str) -> bool:
        """Confirm a reservation after successful migration.

        This marks the reservation as confirmed, meaning the quota has been
        permanently consumed. The reservation is then cleaned up.

        Args:
            reservation_id: The ID of the reservation to confirm.

        Returns:
            True if the reservation was found and confirmed, False otherwise.
        """
        with self._lock:
            reservation = self._reservations.get(reservation_id)
            if reservation is None:
                return False

            # Mark as confirmed and update confirmed usage
            reservation.confirmed = True
            user_id = reservation.user_id
            self._confirmed_usage[user_id] = (
                self._confirmed_usage.get(user_id, 0) + reservation.amount
            )

            # Remove the reservation since it's now confirmed
            del self._reservations[reservation_id]
            return True

    def cleanup_stale_reservations(self, timeout_seconds: float = RESERVATION_TIMEOUT_SECONDS) -> int:
        """Clean up reservations that have exceeded the timeout.

        This should be called periodically to prevent quota from being held
        indefinitely by failed or abandoned migration requests.

        Args:
            timeout_seconds: Age threshold for considering a reservation stale.

        Returns:
            Number of reservations cleaned up.
        """
        with self._lock:
            stale_ids = [
                rid
                for rid, reservation in self._reservations.items()
                if reservation.is_stale(timeout_seconds)
            ]

            for rid in stale_ids:
                del self._reservations[rid]

            return len(stale_ids)

    def get_available_quota(self, user_id: str, tier: str, current_usage: int) -> int:
        """Get the available quota for a user, accounting for pending reservations.

        Args:
            user_id: The user to check quota for.
            tier: The user's subscription tier.
            current_usage: The user's current confirmed usage count.

        Returns:
            Number of quota units available.
        """
        with self._lock:
            limit = TIER_LIMITS.get(tier, 0)

            pending_reserved = sum(
                r.amount
                for r in self._reservations.values()
                if r.user_id == user_id and not r.confirmed and not r.is_stale()
            )

            return max(0, limit - current_usage - pending_reserved)

    def get_pending_reservations_count(self, user_id: str) -> int:
        """Get the count of pending reservations for a user.

        Args:
            user_id: The user to check.

        Returns:
            Number of pending (non-confirmed, non-stale) reservations.
        """
        with self._lock:
            return sum(
                1
                for r in self._reservations.values()
                if r.user_id == user_id and not r.confirmed and not r.is_stale()
            )


# Singleton instance
_quota_manager_instance: Optional[QuotaManager] = None
_singleton_lock = threading.Lock()


def get_quota_manager() -> QuotaManager:
    """Get the singleton QuotaManager instance.

    This function is thread-safe and ensures only one QuotaManager
    instance exists across the application.

    Returns:
        The singleton QuotaManager instance.
    """
    global _quota_manager_instance

    if _quota_manager_instance is None:
        with _singleton_lock:
            # Double-check locking pattern
            if _quota_manager_instance is None:
                _quota_manager_instance = QuotaManager()

    return _quota_manager_instance
