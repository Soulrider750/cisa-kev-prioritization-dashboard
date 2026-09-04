# CISA KEV Prioritization Dashboard

A learning-focused Python project that will retrieve, validate, analyze, and visualize the Cybersecurity and Infrastructure Security Agency's Known Exploited Vulnerabilities catalog.


## Project objective


The finished project will transform CISA KEV data into a reproducible, auditable dashboard containing catalog trends and transparent vulnerability review signals.


The dashboard will not claim to calculate an organization's actual risk. Asset ownership, exposure, business impact, compensating controls, and local threat intelligence are required for an organization-specific prioritization.

## Current stage

Stage 7 implements the complete command-line workflow:

- secure local or live CISA ingestion;
- strict validation and normalization;
- deterministic analysis;
- auditable snapshot, JSON, and CSV exports;
- responsive self-contained HTML reporting;
- configurable analysis and display options;
- concise success and failure messages; and
- offline end-to-end command-line tests.


## Quick start

Requires Python 3.11 or later. The application uses only Python's standard
library.

### Run the offline demonstration

The included fixture is synthetic and is intended only for repeatable testing:

```bash
python -m kev_dashboard \
  --input tests/fixtures/kev_sample.json \
  --as-of 2026-09-03 \
  --output-dir build/sample
```
Open `build/sample/index.html` in a browser.

## Build from current CISA data

```bash
python -m kev_dashboard \
  --output-dir build/live
```
The live command retrieves CISA's official KEV JSON feed, validates it, records its SHA-256 digest, exports normalized data, and generates a self-contained HTML dashboard.

## Command option

```bash
python -m kev_dashboard --help
```
important options include:
- `--input`: use a local catalog snapshot;
- `--source-url`: use an approved CISA HTTPS location;
- `-output-dir`: choose the build destinaton;
- `--as-of`: control the analysis date;
- `--top-vendors`: control the vendor chart size;
- `--queue-limit`: control visible queue rows;and
- `--timeout`: control the retrieval timeout.


## Official data source

Live data comes from CISA's public Known Exploited Vulnerabilities JSON feed:

https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

The project preserves the downloaded bytes, retrieval timestamp, source URL, and SHA-256 hash so generated results can be traced to a specific snapshot.




## Data notice

The records under `tests/fixtures` are fictional and exist only for software testing. They are not current threat intelligence and do not represent real vulnerabilities, vendors, or products.
