"""Usage tracking with debit/credit model for LLM migrations.

This module implements a debit/credit pattern for tracking usage:
1. record_pending_usage() - "Debit" before LLM call starts
2. confirm_usage() - "Credit" confirmation after success
3. cancel_pending_usage() - "Credit" cancellation on failure

This ensures usage is never lost even if the server crashes mid-operation.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class UsageStatus(str, Enum):
    """Status of a usage record."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass
class PendingUsageRecord:
    """Represents a pending usage record before confirmation."""

    request_id: str
    user_id: str
    event_type: str
    library: str
    estimated_cost: float
    created_at: float = field(default_factory=time.time)
    status: UsageStatus = UsageStatus.PENDING
    actual_cost: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    cancellation_reason: Optional[str] = None

    def is_stale(self, max_age_seconds: float) -> bool:
        """Check if this record has exceeded the maximum age."""
        return time.time() - self.created_at > max_age_seconds


class UsageTracker:
    """Thread-safe usage tracker with debit/credit model.

    This tracker ensures usage is recorded before LLM calls begin,
    preventing lost usage tracking due to crashes or failures.
    The pattern is:
    1. record_pending_usage() - Record "debit" before starting work
    2. confirm_usage() - Mark as "credited" after successful completion
    3. cancel_pending_usage() - Mark as "cancelled" if work failed

    Stale pending records (older than max_age_seconds) are periodically
    cleaned up and can be reviewed for reconciliation.
    """

    # Default max age for pending records (15 minutes)
    DEFAULT_MAX_AGE_SECONDS = 900

    def __init__(self) -> None:
        """Initialize the usage tracker with thread-safe data structures."""
        self._lock = threading.Lock()
        self._pending_records: Dict[str, PendingUsageRecord] = {}
        self._confirmed_records: Dict[str, PendingUsageRecord] = {}
        self._cancelled_records: Dict[str, PendingUsageRecord] = {}
        # Track cumulative confirmed usage per user
        self._user_confirmed_usage: Dict[str, float] = {}

    def record_pending_usage(
        self,
        user_id: str,
        request_id: str,
        event_type: str,
        library: str,
        estimated_cost: float,
    ) -> bool:
        """Record a pending usage entry before the LLM call starts.

        This is the "debit" side of the transaction - recording that
        usage is about to occur. If the operation completes successfully,
        confirm_usage() should be called. If it fails, cancel_pending_usage()
        should be called.

        Args:
            user_id: The user initiating the operation.
            request_id: Unique identifier for this request.
            event_type: Type of event (e.g., "tier2_migration", "tier3_migration").
            library: The library being migrated.
            estimated_cost: Estimated cost units for this operation.

        Returns:
            True if the pending usage was recorded successfully.
        """
        with self._lock:
            if request_id in self._pending_records:
                logger.warning(
                    "Attempted to record duplicate pending usage for request_id=%s",
                    request_id,
                )
                return False

            record = PendingUsageRecord(
                request_id=request_id,
                user_id=user_id,
                event_type=event_type,
                library=library,
                estimated_cost=estimated_cost,
            )
            self._pending_records[request_id] = record

            logger.info(
                "Recorded pending usage: request_id=%s, user_id=%s, "
                "event_type=%s, library=%s, estimated_cost=%s",
                request_id,
                user_id,
                event_type,
                library,
                estimated_cost,
            )
            return True

    def confirm_usage(
        self,
        request_id: str,
        actual_cost: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Confirm a pending usage entry after successful completion.

        This is the "credit" confirmation - the operation completed
        successfully and the usage should be finalized.

        Args:
            request_id: The request ID to confirm.
            actual_cost: The actual cost units consumed.
            metadata: Additional metadata about the completed operation.

        Returns:
            True if the usage was confirmed successfully.
        """
        with self._lock:
            record = self._pending_records.get(request_id)
            if record is None:
                logger.warning(
                    "Attempted to confirm non-existent pending usage: request_id=%s",
                    request_id,
                )
                return False

            record.status = UsageStatus.CONFIRMED
            record.actual_cost = actual_cost
            if metadata:
                record.metadata.update(metadata)

            # Move from pending to confirmed
            del self._pending_records[request_id]
            self._confirmed_records[request_id] = record

            # Update cumulative usage
            self._user_confirmed_usage[record.user_id] = (
                self._user_confirmed_usage.get(record.user_id, 0.0) + actual_cost
            )

            logger.info(
                "Confirmed usage: request_id=%s, user_id=%s, actual_cost=%s",
                request_id,
                record.user_id,
                actual_cost,
            )
            return True

    def cancel_pending_usage(self, request_id: str, reason: str) -> bool:
        """Cancel a pending usage entry due to failure.

        This is the "credit" cancellation - the operation failed and
        the pending usage should be cancelled, not charged.

        Args:
            request_id: The request ID to cancel.
            reason: The reason for cancellation.

        Returns:
            True if the usage was cancelled successfully.
        """
        with self._lock:
            record = self._pending_records.get(request_id)
            if record is None:
                logger.warning(
                    "Attempted to cancel non-existent pending usage: request_id=%s",
                    request_id,
                )
                return False

            record.status = UsageStatus.CANCELLED
            record.cancellation_reason = reason

            # Move from pending to cancelled
            del self._pending_records[request_id]
            self._cancelled_records[request_id] = record

            logger.info(
                "Cancelled pending usage: request_id=%s, user_id=%s, reason=%s",
                request_id,
                record.user_id,
                reason,
            )
            return True

    def cleanup_stale_pending_usage(
        self,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    ) -> int:
        """Clean up stale pending usage records.

        Records that have been pending for longer than max_age_seconds
        are considered stale and are moved to cancelled state. These
        can be reviewed for reconciliation if needed.

        Args:
            max_age_seconds: Maximum age in seconds for pending records.

        Returns:
            Number of stale records cleaned up.
        """
        with self._lock:
            stale_request_ids = [
                request_id
                for request_id, record in self._pending_records.items()
                if record.is_stale(max_age_seconds)
            ]

            for request_id in stale_request_ids:
                record = self._pending_records[request_id]
                record.status = UsageStatus.CANCELLED
                record.cancellation_reason = (
                    f"Stale: exceeded max age of {max_age_seconds} seconds"
                )

                del self._pending_records[request_id]
                self._cancelled_records[request_id] = record

                logger.warning(
                    "Cleaned up stale pending usage: request_id=%s, user_id=%s, "
                    "age=%.1f seconds",
                    request_id,
                    record.user_id,
                    time.time() - record.created_at,
                )

            if stale_request_ids:
                logger.info(
                    "Cleaned up %d stale pending usage records",
                    len(stale_request_ids),
                )

            return len(stale_request_ids)

    def get_pending_count(self, user_id: Optional[str] = None) -> int:
        """Get the count of pending usage records.

        Args:
            user_id: Optional filter by user ID.

        Returns:
            Number of pending records.
        """
        with self._lock:
            if user_id is None:
                return len(self._pending_records)
            return sum(
                1 for record in self._pending_records.values() if record.user_id == user_id
            )

    def get_user_confirmed_usage(self, user_id: str) -> float:
        """Get the cumulative confirmed usage for a user.

        Args:
            user_id: The user to check.

        Returns:
            Cumulative confirmed usage cost.
        """
        with self._lock:
            return self._user_confirmed_usage.get(user_id, 0.0)

    def get_pending_record(self, request_id: str) -> Optional[PendingUsageRecord]:
        """Get a pending usage record by request ID.

        Args:
            request_id: The request ID to look up.

        Returns:
            The pending record if found, None otherwise.
        """
        with self._lock:
            return self._pending_records.get(request_id)


def generate_request_id() -> str:
    """Generate a unique request ID for usage tracking.

    Returns:
        A unique request ID string (UUID format).
    """
    return str(uuid.uuid4())


# Singleton instance
_usage_tracker_instance: Optional[UsageTracker] = None
_singleton_lock = threading.Lock()


def get_usage_tracker() -> UsageTracker:
    """Get the singleton UsageTracker instance.

    This function is thread-safe and ensures only one UsageTracker
    instance exists across the application.

    Returns:
        The singleton UsageTracker instance.
    """
    global _usage_tracker_instance

    if _usage_tracker_instance is None:
        with _singleton_lock:
            # Double-check locking pattern
            if _usage_tracker_instance is None:
                _usage_tracker_instance = UsageTracker()

    return _usage_tracker_instance


async def run_cleanup_task(
    interval_seconds: float = 300.0,
    max_age_seconds: float = UsageTracker.DEFAULT_MAX_AGE_SECONDS,
) -> None:
    """Run a background cleanup task for stale pending usage records.

    This coroutine runs indefinitely, periodically cleaning up stale
    pending usage records. It should be started as a background task
    during application startup.

    Args:
        interval_seconds: How often to run cleanup (default: 5 minutes).
        max_age_seconds: Maximum age for pending records (default: 15 minutes).
    """
    tracker = get_usage_tracker()
    logger.info(
        "Starting usage cleanup task: interval=%ds, max_age=%ds",
        interval_seconds,
        max_age_seconds,
    )

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            cleaned = tracker.cleanup_stale_pending_usage(max_age_seconds)
            if cleaned > 0:
                logger.info("Cleanup task removed %d stale records", cleaned)
        except asyncio.CancelledError:
            logger.info("Usage cleanup task cancelled")
            break
        except Exception as e:
            logger.exception("Error in usage cleanup task: %s", e)
            # Continue running despite errors
            await asyncio.sleep(interval_seconds)
