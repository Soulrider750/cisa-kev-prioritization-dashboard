"""Publication policy for live dashboard candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from .fetch import DEFAULT_FEED_URL


APPROVED_DEPLOYMENT_SOURCE = DEFAULT_FEED_URL

DEFAULT_FUTURE_TOLERANCE = timedelta(
    minutes=5
)


class DeploymentPolicyError(ValueError):
    """Raised when a candidate is ineligible for publication."""


@dataclass(frozen=True, slots=True)
class DeploymentPolicyResult:
    """Evidence that a candidate satisfied deployment policy."""

    source: str
    retrieved_at: datetime
    evaluated_at: datetime
    age: timedelta
    max_age: timedelta


def _as_utc(
    value: datetime,
    field: str,
) -> datetime:
    """Validate an aware datetime and normalize it to UTC."""

    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise DeploymentPolicyError(
            f"{field} must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    )


def evaluate_deployment_policy(
    *,
    source: str,
    retrieved_at: datetime,
    now: datetime,
    max_age: timedelta,
    future_tolerance: timedelta = (
        DEFAULT_FUTURE_TOLERANCE
    ),
) -> DeploymentPolicyResult:
    """Evaluate whether a candidate is eligible for publication."""

    if source != APPROVED_DEPLOYMENT_SOURCE:
        raise DeploymentPolicyError(
            "deployment source must be the "
            "official CISA KEV feed"
        )

    retrieved_at_utc = _as_utc(
        retrieved_at,
        "retrieved_at",
    )

    now_utc = _as_utc(
        now,
        "now",
    )

    if (
        not isinstance(max_age, timedelta)
        or max_age <= timedelta()
    ):
        raise DeploymentPolicyError(
            "max_age must be greater than zero"
        )

    if (
        not isinstance(
            future_tolerance,
            timedelta,
        )
        or future_tolerance < timedelta()
    ):
        raise DeploymentPolicyError(
            "future_tolerance must not be "
            "negative"
        )

    future_offset = (
        retrieved_at_utc - now_utc
    )

    if future_offset > future_tolerance:
        raise DeploymentPolicyError(
            "candidate retrieval timestamp "
            "is too far in the future"
        )

    age = max(
        now_utc - retrieved_at_utc,
        timedelta(),
    )

    if age > max_age:
        raise DeploymentPolicyError(
            "candidate retrieval timestamp "
            "exceeds maximum age"
        )

    return DeploymentPolicyResult(
        source=source,
        retrieved_at=retrieved_at_utc,
        evaluated_at=now_utc,
        age=age,
        max_age=max_age,
    )
