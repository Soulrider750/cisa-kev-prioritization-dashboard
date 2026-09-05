"""Tests for live dashboard deployment policy."""

from datetime import datetime, timedelta, timezone
import unittest

from kev_dashboard.deployment_policy import (
    DEFAULT_FUTURE_TOLERANCE,
    DeploymentPolicyError,
    DeploymentPolicyResult,
    evaluate_deployment_policy,
)
from kev_dashboard.fetch import DEFAULT_FEED_URL


class DeploymentPolicyTests(unittest.TestCase):
    """Verify the rules governing public candidates."""

    def setUp(self) -> None:
        self.now = datetime(
            2026,
            9,
            5,
            3,
            36,
            25,
            tzinfo=timezone.utc,
        )

        self.max_age = timedelta(
            hours=1
        )

    def evaluate(
        self,
        *,
        source: str = DEFAULT_FEED_URL,
        retrieved_at: datetime | None = None,
        now: datetime | None = None,
        max_age: timedelta | None = None,
        future_tolerance: timedelta = (
            DEFAULT_FUTURE_TOLERANCE
        ),
    ) -> DeploymentPolicyResult:
        return evaluate_deployment_policy(
            source=source,
            retrieved_at=(
                retrieved_at
                if retrieved_at is not None
                else (
                    self.now
                    - timedelta(minutes=10)
                )
            ),
            now=(
                now
                if now is not None
                else self.now
            ),
            max_age=(
                max_age
                if max_age is not None
                else self.max_age
            ),
            future_tolerance=future_tolerance,
        )

    def test_recent_official_candidate_returns_result(
        self,
    ) -> None:
        eastern = timezone(
            -timedelta(hours=4)
        )

        result = self.evaluate(
            retrieved_at=datetime(
                2026,
                9,
                4,
                23,
                30,
                tzinfo=eastern,
            )
        )

        self.assertEqual(
            result.source,
            DEFAULT_FEED_URL,
        )

        self.assertEqual(
            result.retrieved_at,
            datetime(
                2026,
                9,
                5,
                3,
                30,
                tzinfo=timezone.utc,
            ),
        )

        self.assertIs(
            result.retrieved_at.tzinfo,
            timezone.utc,
        )

        self.assertEqual(
            result.evaluated_at,
            self.now,
        )

        self.assertEqual(
            result.age,
            timedelta(
                minutes=6,
                seconds=25,
            ),
        )

        self.assertEqual(
            result.max_age,
            self.max_age,
        )

    def test_other_cisa_url_is_not_approved(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            DeploymentPolicyError,
            (
                "deployment source must be the "
                "official CISA KEV feed"
            ),
        ):
            self.evaluate(
                source=(
                    "https://www.cisa.gov/"
                    "other-feed.json"
                )
            )

    def test_naive_retrieval_time_is_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            DeploymentPolicyError,
            "retrieved_at must be timezone-aware",
        ):
            self.evaluate(
                retrieved_at=datetime(
                    2026,
                    9,
                    5,
                    3,
                    30,
                )
            )

    def test_naive_evaluation_time_is_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            DeploymentPolicyError,
            "now must be timezone-aware",
        ):
            self.evaluate(
                now=datetime(
                    2026,
                    9,
                    5,
                    3,
                    36,
                    25,
                )
            )

    def test_zero_maximum_age_is_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            DeploymentPolicyError,
            "max_age must be greater than zero",
        ):
            self.evaluate(
                max_age=timedelta(),
            )

    def test_negative_future_tolerance_is_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            DeploymentPolicyError,
            (
                "future_tolerance must not be "
                "negative"
            ),
        ):
            self.evaluate(
                future_tolerance=timedelta(
                    seconds=-1
                )
            )

    def test_stale_candidate_is_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            DeploymentPolicyError,
            (
                "candidate retrieval timestamp "
                "exceeds maximum age"
            ),
        ):
            self.evaluate(
                retrieved_at=(
                    self.now
                    - self.max_age
                    - timedelta(seconds=1)
                )
            )

    def test_candidate_at_maximum_age_is_accepted(
        self,
    ) -> None:
        result = self.evaluate(
            retrieved_at=(
                self.now - self.max_age
            )
        )

        self.assertEqual(
            result.age,
            self.max_age,
        )

    def test_timestamp_beyond_future_tolerance_is_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            DeploymentPolicyError,
            (
                "candidate retrieval timestamp "
                "is too far in the future"
            ),
        ):
            self.evaluate(
                retrieved_at=(
                    self.now
                    + DEFAULT_FUTURE_TOLERANCE
                    + timedelta(seconds=1)
                )
            )

    def test_timestamp_at_future_tolerance_is_accepted(
        self,
    ) -> None:
        result = self.evaluate(
            retrieved_at=(
                self.now
                + DEFAULT_FUTURE_TOLERANCE
            )
        )

        self.assertEqual(
            result.age,
            timedelta(),
        )


if __name__ == "__main__":
    unittest.main()
