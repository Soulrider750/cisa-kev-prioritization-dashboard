# CISA KEV Prioritization Dashboard

A learning-focused Python project that will retrieve, validate, analyze, and visualize the Cybersecurity and Infrastructure Security Agency's Known Exploited Vulnerabilities catalog.


## Project objective


The finished project will transform CISA KEV data into a reproducible, auditable dashboard containing catalog trends and transparent vulnerability review signals.


The dashboard will not claim to calculate an organization's actual risk. Asset ownership, exposure, business impact, compensating controls, and local threat intelligence are required for an organization-specific prioritization.


## Current stage

Stage 4 implements:

- validated catalog and vulnerability models;
- secure local and live data ingestion;
- vendor and yearly catalog summaries;
- ransomware and forensic-triage distributions;
- remediation-window statistics;
- reproducible `as_of` date analysis; and
- a transparent, deterministic review queue.

Analysis is deliberately separated from file, network, and presentation code.
The output is currently available as Python dictionaries. CSV, JSON, and HTML report generation have not been implemented yet.

see `docs/METHODOLOGY.md` for definitions and interpretation limits.


## Official data source

Live data comes from CISA's public Known Exploited Vulnerabilities JSON feed:

https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

The project preserves the downloaded bytes, retrieval timestamp, source URL, and SHA-256 hash so generated results can be traced to a specific snapshot.




## Data notice

The records under `tests/fixtures` are fictional and exist only for software testing. They are not current threat intelligence and do not represent real vulnerabilities, vendors, or products.
