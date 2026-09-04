"""Validated domain models for the CISA KEV catalog."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any


CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,19}$")
CWE_PATTERN = re.compile(r"^CWE-\d+$")

REQUIRED_TEXT_FIELDS = (
    "cveID",
    "vendorProject",
    "product",
    "vulnerabilityName",
    "dateAdded",
    "shortDescription",
    "requiredAction",
    "dueDate",
    "knownRansomwareCampaignUse",
)

RANSOMWARE_VALUES = {
    "known": "Known",
    "unknown": "Unknown",
}

FORENSIC_TRIAGE_VALUES = {
    "yes": "Yes",
    "no": "No",
}


class CatalogValidationError(ValueError):
    """Raised when KEV data does not satisfy the expected structure."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)

        preview = "; ".join(errors[:10])
        if len(errors) > 10:
            remaining = len(errors) - 10
            preview += f"; and {remaining} more error(s)"

        super().__init__(f"Catalog validation failed: {preview}")


@dataclass(frozen=True, slots=True)
class Vulnerability:
    """A normalized vulnerability from the CISA KEV catalog."""

    cve_id: str
    vendor: str
    product: str
    name: str
    date_added: date
    due_date: date
    ransomware_use: str
    forensic_triage: str | None
    description: str
    required_action: str
    notes: str
    cwes: tuple[str, ...]

    @property
    def remediation_days(self) -> int:
        """Return the number of calendar days in CISA's response window."""

        return (self.due_date - self.date_added).days


@dataclass(frozen=True, slots=True)
class Catalog:
    """A validated KEV catalog and its source information."""

    catalog_version: str
    released_at: datetime
    source: str
    vulnerabilities: tuple[Vulnerability, ...]

    @property
    def released_date(self) -> date:
        """Return only the calendar date portion of the release timestamp."""

        return self.released_at.date()


def _required_text(
    record: Mapping[str, Any],
    field: str,
    location: str,
    errors: list[str],
) -> str:
    """Read and clean a required nonempty string."""

    value = record.get(field)

    if not isinstance(value, str) or not value.strip():
        errors.append(f"{location}: {field} must be a non-empty string")
        return ""

    return value.strip()


def _parse_date(
    value: str,
    field: str,
    location: str,
    errors: list[str],
) -> date | None:
    """Convert a YYYY-MM-DD string into a date object."""

    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{location}: {field} must use YYYY-MM-DD format")
        return None


def _parse_release_timestamp(
    value: str,
    errors: list[str],
) -> datetime | None:
    """Convert CISA's ISO 8601 release timestamp into a datetime."""

    normalized = value.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        errors.append("catalog: dateReleased must be a valid ISO 8601 timestamp")
        return None


def _parse_cwes(
    record: Mapping[str, Any],
    location: str,
    errors: list[str],
) -> tuple[str, ...]:
    """Validate and normalize an optional CWE array."""

    raw_cwes = record.get("cwes", [])

    if raw_cwes is None:
        return ()

    if not isinstance(raw_cwes, list):
        errors.append(f"{location}: cwes must be an array")
        return ()

    normalized_cwes: list[str] = []

    for cwe_index, raw_cwe in enumerate(raw_cwes):
        if not isinstance(raw_cwe, str):
            errors.append(
                f"{location}: cwes[{cwe_index}] must be a string"
            )
            continue

        cwe = raw_cwe.strip().upper()

        if not CWE_PATTERN.fullmatch(cwe):
            errors.append(
                f"{location}: cwes[{cwe_index}] must match CWE-NNNN"
            )
            continue

        normalized_cwes.append(cwe)

    return tuple(normalized_cwes)


def _parse_forensic_triage(
    record: Mapping[str, Any],
    location: str,
    errors: list[str],
) -> str | None:
    """Normalize the optional forensic-triage value."""

    raw_value = record.get("forensicTriage")

    if raw_value is None:
        return None

    if not isinstance(raw_value, str):
        errors.append(
            f"{location}: forensicTriage must be Yes or No when present"
        )
        return None

    cleaned_value = raw_value.strip()

    if not cleaned_value:
        return None

    normalized = FORENSIC_TRIAGE_VALUES.get(cleaned_value.casefold())

    if normalized is None:
        errors.append(
            f"{location}: forensicTriage must be Yes or No when present"
        )

    return normalized


def parse_catalog(
    payload: Mapping[str, Any],
    *,
    source: str,
) -> Catalog:
    """Validate and normalize a decoded CISA KEV JSON document."""

    if not isinstance(payload, Mapping):
        raise CatalogValidationError(
            ["top-level JSON value must be an object"]
        )

    errors: list[str] = []

    catalog_version = _required_text(
        payload,
        "catalogVersion",
        "catalog",
        errors,
    )

    released_text = _required_text(
        payload,
        "dateReleased",
        "catalog",
        errors,
    )

    released_at = (
        _parse_release_timestamp(released_text, errors)
        if released_text
        else None
    )

    declared_count = payload.get("count")

    if isinstance(declared_count, bool) or not isinstance(
        declared_count,
        int,
    ):
        errors.append("catalog: count must be an integer")

    records = payload.get("vulnerabilities")

    if not isinstance(records, list):
        errors.append("catalog: vulnerabilities must be an array")
        raise CatalogValidationError(errors)

    if not records:
        errors.append("catalog: vulnerabilities must not be empty")

    if isinstance(declared_count, int) and not isinstance(
        declared_count,
        bool,
    ):
        if declared_count != len(records):
            errors.append(
                "catalog: count declares "
                f"{declared_count} records but vulnerabilities "
                f"contains {len(records)}"
            )

    vulnerabilities: list[Vulnerability] = []
    seen_cves: set[str] = set()

    for index, record in enumerate(records):
        location = f"record {index}"

        if not isinstance(record, Mapping):
            errors.append(f"{location}: must be an object")
            continue

        record_errors: list[str] = []

        values = {
            field: _required_text(
                record,
                field,
                location,
                record_errors,
            )
            for field in REQUIRED_TEXT_FIELDS
        }

        cve_id = values["cveID"].upper()

        if cve_id and not CVE_PATTERN.fullmatch(cve_id):
            record_errors.append(
                f"{location}: cveID must match CVE-YYYY-NNNN"
            )
        elif cve_id in seen_cves:
            record_errors.append(
                f"{location}: duplicate cveID {cve_id}"
            )
        elif cve_id:
            seen_cves.add(cve_id)

        date_added = (
            _parse_date(
                values["dateAdded"],
                "dateAdded",
                location,
                record_errors,
            )
            if values["dateAdded"]
            else None
        )

        due_date = (
            _parse_date(
                values["dueDate"],
                "dueDate",
                location,
                record_errors,
            )
            if values["dueDate"]
            else None
        )

        if (
            date_added is not None
            and due_date is not None
            and due_date < date_added
        ):
            record_errors.append(
                f"{location}: dueDate cannot precede dateAdded"
            )

        ransomware_use = RANSOMWARE_VALUES.get(
            values["knownRansomwareCampaignUse"].casefold()
        )

        if (
            values["knownRansomwareCampaignUse"]
            and ransomware_use is None
        ):
            record_errors.append(
                f"{location}: knownRansomwareCampaignUse "
                "must be Known or Unknown"
            )

        forensic_triage = _parse_forensic_triage(
            record,
            location,
            record_errors,
        )

        raw_notes = record.get("notes", "")

        if raw_notes is None:
            notes = ""
        elif isinstance(raw_notes, str):
            notes = raw_notes.strip()
        else:
            record_errors.append(
                f"{location}: notes must be a string when present"
            )
            notes = ""

        cwes = _parse_cwes(
            record,
            location,
            record_errors,
        )

        errors.extend(record_errors)

        if record_errors:
            continue

        if (
            date_added is None
            or due_date is None
            or ransomware_use is None
        ):
            continue

        vulnerabilities.append(
            Vulnerability(
                cve_id=cve_id,
                vendor=values["vendorProject"],
                product=values["product"],
                name=values["vulnerabilityName"],
                date_added=date_added,
                due_date=due_date,
                ransomware_use=ransomware_use,
                forensic_triage=forensic_triage,
                description=values["shortDescription"],
                required_action=values["requiredAction"],
                notes=notes,
                cwes=cwes,
            )
        )

    if errors:
        raise CatalogValidationError(errors)

    if released_at is None:
        raise CatalogValidationError(
            ["catalog: dateReleased could not be parsed"]
        )

    return Catalog(
        catalog_version=catalog_version,
        released_at=released_at,
        source=source,
        vulnerabilities=tuple(vulnerabilities),
    )