# CISA KEV Prioritization Dashboard

A learning-focused Python project that will retrieve, validate, analyze, and visualize the Cybersecurity and Infrastructure Security Agency's Known Exploited Vulnerabilities catalog.


## Project objective


The finished project will transform CISA KEV data into a reproducible, auditable dashboard containing catalog trends and transparent vulnerability review signals.


The dashboard will not claim to calculate an organization's actual risk. Asset ownership, exposure, business impact, compensating controls, and local threat intelligence are required for an organization-specific prioritization.


## Current stage

Stage 5 implements:

- validated catalog and vulnerability models;
- secure local and live JSON ingestion;
- deterministic catalog analysis;
- exact source-snapshot preservation;
- SHA-256 provenance metadata;
- aggregate summary JSON;
- normalized vulnerability CSV output;
- vendor, year, ransomware, forensic-triage, remediation-window, and review
  summary CSV files;
- spreadsheet-formula neutralization; and
- atomic output replacement.

The project currently generates machine-readable evidence. The HTML dashboard
and final command-line workflow have not been implemented yet.

See `docs/METHODOLOGY.md` for definitions, limitations, and reproducibility
details.


## Official data source

Live data comes from CISA's public Known Exploited Vulnerabilities JSON feed:

https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

The project preserves the downloaded bytes, retrieval timestamp, source URL, and SHA-256 hash so generated results can be traced to a specific snapshot.




## Data notice

The records under `tests/fixtures` are fictional and exist only for software testing. They are not current threat intelligence and do not represent real vulnerabilities, vendors, or products.
