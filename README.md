# CISA KEV Prioritization Dashboard

A dependency-free Python application that retrieves, validates, analyzes, and visualizes the Cybersecurity and Infrastructure Security Agency's Known Exploited Vulnerabilities catalog.

**Project status:** Stage 8 release engineering is being completed locally. The repository has not been approved for public publication.

## Purpose

The project transforms CISA KEV data into a reproducible dashboard containing catalog trends and a transparent vulnerability review queue.

It demonstrates:

- defensive input validation;
- restricted HTTPS data retrieval;
- deterministic analysis;
- source provenance and SHA-256 integrity evidence;
- safe CSV and HTML generation;
- accessible, self-contained reporting;
- automated testing across supported Python versions; and
- an offline release-verification workflow.

The dashboard does not calculate an organization's actual risk. Asset ownership, vulnerable versions, exposure, business impact, compensating controls, remediation status, and local threat intelligence are required for organization-specific prioritization.

## Requirements

- Python 3.11 or later
- No third-party runtime packages

## Quick start

### Build the deterministic offline demonstration

The included fixture is synthetic and exists only for repeatable testing:

```bash
python3 -m kev_dashboard \
  --input tests/fixtures/kev_sample.json \
  --as-of 2026-09-03 \
  --output-dir build/sample
```

Open `build/sample/index.html` in a browser.

### Build from current CISA data

```bash
python3 -m kev_dashboard \
  --output-dir build/live
```

The live command retrieves CISA's approved KEV JSON feed, validates the catalog, preserves the original snapshot, records its SHA-256 digest, exports normalized data, and generates a self-contained HTML dashboard.

Live results change as CISA updates the catalog.

## Command-line options

Display the complete help page:

```bash
python3 -m kev_dashboard --help
```

Important options include:

- `--input`: use a local catalog snapshot;
- `--source-url`: use an approved CISA HTTPS location;
- `--output-dir`: choose the build destination;
- `--as-of`: choose the reproducible analysis date;
- `--top-vendors`: control the vendor chart size;
- `--queue-limit`: control the visible review-queue rows;
- `--timeout`: control the live retrieval timeout; and
- `--version`: display the application version.

## Generated output

A successful build contains:

```text
index.html
data/
├── kev_snapshot.json
├── metadata.json
├── summary.json
├── vulnerabilities.csv
├── vendor_summary.csv
├── year_summary.csv
├── ransomware_summary.csv
├── forensic_triage_summary.csv
├── remediation_window_summary.csv
└── review_signal_summary.csv
```

Generated output is excluded from Git because it can be reproduced from the source snapshot and application code.

## Testing

Run the unit-test suite:

```bash
make test
```

Build the synthetic demonstration:

```bash
make sample
```

Run the complete offline release gate:

```bash
make verify
```

The verifier checks project metadata, repository hygiene, documentation, all unit tests, the complete command-line pipeline, expected artifacts, snapshot preservation, record counts, and SHA-256 evidence.

The offline verification process never contacts the live CISA feed.

## Methodology and limitations

The review queue uses transparent, deterministic ordering rather than an opaque risk score. See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for the complete methodology, review signals, export behavior, and limitations.

Every KEV entry already represents a vulnerability that met CISA's inclusion criteria. Placement in this dashboard does not prove that a particular organization owns the product, runs an affected version, is exposed, or has failed to remediate it.

## Official data source

Live data comes from CISA's public Known Exploited Vulnerabilities JSON feed:

https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

This independent learning project is not affiliated with or endorsed by CISA.

## Synthetic-data notice

Every record under `tests/fixtures` is fictional and exists only for software testing. These records are not current threat intelligence and do not represent real vulnerabilities, vendors, or products.

## Security

Review [SECURITY.md](SECURITY.md) before reporting a security concern or processing untrusted catalog data.

## Publication status

The repository remains unpublished until every gate in [PUBLISHING_STATUS.md](PUBLISHING_STATUS.md) and [RELEASE_WORKFLOW.md](RELEASE_WORKFLOW.md) has been reviewed.

## License

Application source code is available under the [MIT License](LICENSE). CISA catalog data remains subject to its original source terms and attribution.
