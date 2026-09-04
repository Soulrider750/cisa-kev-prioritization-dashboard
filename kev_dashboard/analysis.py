"""Deterministic metrics and review signals for CISA KEV data."""

from __future__ import annotations

from collections import Counter
from datetime import date
from statistics import mean, median
from typing import Any

from .models import Catalog, Vulnerability


REMEDIATION_BUCKETS = (
    ("0-7 days", 7),
    ("8-14 days", 14),
    ("15-21 days", 21),
    ("22-30 days", 30),
    ("31-60 days", 60),
    ("More than 60 days", None),
)

DUE_STATUS_ORDER = {
    "Catalog due date passed": 0,
    "Catalog due within 7 days": 1,
    "Catalog due within 30 days": 2,
    "Routine review": 3,
}

PRIMARY_REVIEW_SIGNALS = (
    "Forensic triage indicated",
    "Known ransomware use",
    "Catalog due date passed",
    "Catalog due within 7 days",
    "Catalog due within 30 days",
    "Routine review",
)


def _percentage(count: int, total: int) -> float:
    """Return a percentage rounded to one decimal place."""

    return round(count / total * 100, 1)


def _remediation_bucket(remediation_days: int) -> str:
    """Place a remediation window into a fixed reporting bucket."""

    for label, upper_limit in REMEDIATION_BUCKETS:
        if upper_limit is None or remediation_days <= upper_limit:
            return label

    raise AssertionError("unreachable remediation bucket")


def _due_status(
    vulnerability: Vulnerability,
    as_of: date,
) -> tuple[str, int]:
    """Describe the catalog due date relative to an analysis date."""

    days_until_due = (
        vulnerability.due_date - as_of
    ).days

    if days_until_due < 0:
        status = "Catalog due date passed"
    elif days_until_due <= 7:
        status = "Catalog due within 7 days"
    elif days_until_due <= 30:
        status = "Catalog due within 30 days"
    else:
        status = "Routine review"

    return status, days_until_due


def _review_reasons(
    vulnerability: Vulnerability,
    due_status: str,
) -> list[str]:
    """Return every fact contributing to the review decision."""

    reasons: list[str] = []

    if vulnerability.forensic_triage == "Yes":
        reasons.append("Forensic triage indicated")

    if vulnerability.ransomware_use == "Known":
        reasons.append("Known ransomware use")

    reasons.append(due_status)

    return reasons


def _primary_review_signal(
    vulnerability: Vulnerability,
    due_status: str,
) -> str:
    """Choose one mutually exclusive signal for summary reporting."""

    if vulnerability.forensic_triage == "Yes":
        return "Forensic triage indicated"

    if vulnerability.ransomware_use == "Known":
        return "Known ransomware use"

    return due_status


def _review_sort_key(
    row: dict[str, Any],
) -> tuple[int, int, int, str, str]:
    """Return the documented ordering used by the review queue."""

    forensic_order = (
        0 if row["forensic_triage"] == "Yes" else 1
    )
    ransomware_order = (
        0 if row["ransomware_use"] == "Known" else 1
    )
    due_order = DUE_STATUS_ORDER[row["due_status"]]

    return (
        forensic_order,
        ransomware_order,
        due_order,
        row["due_date"],
        row["cve_id"],
    )


def analyze_catalog(
    catalog: Catalog,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Calculate reproducible statistics and review signals."""

    effective_date = as_of or catalog.released_date
    vulnerabilities = catalog.vulnerabilities
    total = len(vulnerabilities)

    vendor_counts = Counter(
        vulnerability.vendor
        for vulnerability in vulnerabilities
    )

    year_counts = Counter(
        vulnerability.date_added.year
        for vulnerability in vulnerabilities
    )

    ransomware_counts = Counter(
        vulnerability.ransomware_use
        for vulnerability in vulnerabilities
    )

    forensic_counts = Counter(
        vulnerability.forensic_triage or "Not supplied"
        for vulnerability in vulnerabilities
    )

    remediation_days = [
        vulnerability.remediation_days
        for vulnerability in vulnerabilities
    ]

    remediation_counts = Counter(
        _remediation_bucket(days)
        for days in remediation_days
    )

    review_signal_counts: Counter[str] = Counter()
    vulnerability_rows: list[dict[str, Any]] = []

    for vulnerability in vulnerabilities:
        due_status, days_until_due = _due_status(
            vulnerability,
            effective_date,
        )

        primary_signal = _primary_review_signal(
            vulnerability,
            due_status,
        )

        review_reasons = _review_reasons(
            vulnerability,
            due_status,
        )

        review_signal_counts[primary_signal] += 1

        vulnerability_rows.append(
            {
                "cve_id": vulnerability.cve_id,
                "vendor": vulnerability.vendor,
                "product": vulnerability.product,
                "vulnerability_name": vulnerability.name,
                "date_added": vulnerability.date_added.isoformat(),
                "due_date": vulnerability.due_date.isoformat(),
                "remediation_days": (
                    vulnerability.remediation_days
                ),
                "days_until_due": days_until_due,
                "ransomware_use": (
                    vulnerability.ransomware_use
                ),
                "forensic_triage": (
                    vulnerability.forensic_triage
                    or "Not supplied"
                ),
                "due_status": due_status,
                "primary_review_signal": primary_signal,
                "review_reasons": review_reasons,
                "short_description": (
                    vulnerability.description
                ),
                "required_action": (
                    vulnerability.required_action
                ),
                "notes": vulnerability.notes,
                "cwes": list(vulnerability.cwes),
            }
        )

    vulnerability_rows.sort(key=_review_sort_key)

    known_ransomware = ransomware_counts.get(
        "Known",
        0,
    )

    forensic_triage = forensic_counts.get(
        "Yes",
        0,
    )

    return {
        "metadata": {
            "source": catalog.source,
            "catalog_version": catalog.catalog_version,
            "date_released": (
                catalog.released_at.isoformat()
            ),
            "as_of": effective_date.isoformat(),
        },
        "headline": {
            "total_vulnerabilities": total,
            "unique_vendors": len(vendor_counts),
            "known_ransomware": known_ransomware,
            "known_ransomware_percent": _percentage(
                known_ransomware,
                total,
            ),
            "forensic_triage": forensic_triage,
            "forensic_triage_percent": _percentage(
                forensic_triage,
                total,
            ),
            "median_remediation_days": float(
                median(remediation_days)
            ),
        },
        "remediation_window_statistics": {
            "minimum_days": min(remediation_days),
            "maximum_days": max(remediation_days),
            "mean_days": round(
                mean(remediation_days),
                1,
            ),
            "median_days": float(
                median(remediation_days)
            ),
        },
        "vendors": [
            {
                "vendor": vendor,
                "count": count,
                "percent": _percentage(count, total),
            }
            for vendor, count in sorted(
                vendor_counts.items(),
                key=lambda item: (
                    -item[1],
                    item[0].casefold(),
                ),
            )
        ],
        "years": [
            {
                "year": year,
                "count": year_counts[year],
            }
            for year in sorted(year_counts)
        ],
        "ransomware": [
            {
                "status": status,
                "count": ransomware_counts.get(status, 0),
                "percent": _percentage(
                    ransomware_counts.get(status, 0),
                    total,
                ),
            }
            for status in ("Known", "Unknown")
        ],
        "forensic_triage": [
            {
                "status": status,
                "count": forensic_counts.get(status, 0),
                "percent": _percentage(
                    forensic_counts.get(status, 0),
                    total,
                ),
            }
            for status in (
                "Yes",
                "No",
                "Not supplied",
            )
        ],
        "remediation_buckets": [
            {
                "window": label,
                "count": remediation_counts.get(label, 0),
            }
            for label, _ in REMEDIATION_BUCKETS
        ],
        "review_signals": [
            {
                "signal": signal,
                "count": review_signal_counts.get(
                    signal,
                    0,
                ),
            }
            for signal in PRIMARY_REVIEW_SIGNALS
        ],
        "vulnerabilities": vulnerability_rows,
    }