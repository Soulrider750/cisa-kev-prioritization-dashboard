# Methodology and limitations

## Purpose

This project analyzes the Cybersecurity and Infrastructure Security Agency's
Known Exploited Vulnerabilities catalog and creates a transparent first-pass
review queue.

The queue is a workflow aid. It is not an organization-specific risk score,
severity score, or claim that one vulnerability is safe to ignore.

## Analysis date

Every analysis uses an explicit `as_of` date. When no date is provided, the
catalog's release date is used.

This makes results reproducible and allows saved catalog snapshots to be
analyzed historically without depending on the computer's current date.

## Metrics

The project calculates:

- the total number of catalog entries;
- unique vendors based on CISA's published vendor names;
- entries grouped by vendor and year added;
- known and unknown ransomware-campaign use;
- forensic-triage values;
- the number of calendar days between `dateAdded` and `dueDate`; and
- fixed remediation-window buckets.

`Unknown` ransomware use is not interpreted as `No`. It means the source does
not confirm known ransomware-campaign use.

Vendor counts reflect CISA's catalog naming and contents. They do not measure
vendor market share, product quality, or an organization's exposure.

## Review ordering

Records are ordered using the following transparent sequence:

1. forensic triage indicated;
2. known ransomware use;
3. catalog due-date status;
4. due date; and
5. CVE identifier.

Each record receives one primary review signal for summary reporting. The
record also retains every applicable review reason so that useful context is
not discarded.

## Limitations

Every KEV entry already represents a vulnerability that met CISA's inclusion
criteria. The project does not know:

- whether an organization owns the affected product;
- whether a vulnerable version is installed;
- whether the asset is publicly exposed;
- the asset's business or mission importance;
- whether compensating controls exist;
- whether remediation has already occurred; or
- what local threat intelligence is available.

A passed catalog due date does not prove that a particular organization is
noncompliant or remains vulnerable. Organization-specific prioritization
requires asset and environmental context beyond the public catalog.

Current federal remediation guidance should be interpreted using CISA's BOD
26-04 and its implementation guidance:

https://www.cisa.gov/news-events/directives/bod-26-04-prioritizing-security-updates-based-risk

## Reproducibility and exported evidence

Each build preserves the exact source JSON bytes used for analysis. It also
records:

- the source location;
- retrieval timestamp;
- catalog version;
- catalog release timestamp;
- analysis date;
- record count; and
- SHA-256 snapshot digest.

The SHA-256 digest allows a reviewer to confirm that a saved snapshot has not
changed after analysis.

Summary JSON excludes vulnerability-level rows to keep the aggregate report
compact. Complete normalized records are exported separately as CSV.

Text beginning with spreadsheet formula characters is neutralized in CSV
output. This reduces the risk that externally supplied text will be interpreted
as a formula when a report is opened in spreadsheet software.