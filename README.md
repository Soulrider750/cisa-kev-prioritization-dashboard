# CISA KEV Prioritization Dashboard

A learning-focused Python project that will retrieve, validate, analyze, and visualize the Cybersecurity and Infrastructure Security Agency's Known Exploited Vulnerabilities catalog.


## Project objective


The finished project will transform CISA KEV data into a reproducible, auditable dashboard containing catalog trends and transparent vulnerability review signals.


The dashboard will not claim to calculate an organization's actual risk. Asset ownership, exposure, business impact, compensating controls, and local threat intelligence are required for an organization-specific prioritization.


## Current stage

Stage 6 implements the complete offline reporting pipeline:

- validated KEV data models;
- secure local and live JSON ingestion;
- deterministic metrics and review signals;
- exact source-snapshot preservation;
- JSON and CSV evidence exports;
- a responsive self-contained HTML dashboard;
- accessible inline SVG charts and text-equivalent data tables;
- an operational review queue;
- HTML escaping and spreadsheet-formula protection; and
- atomic output replacement.

The pipeline can currently be run through its Python functions. The final
command-line interface has not yet connected all stages into one command.

See `docs/METHODOLOGY.md` for definitions, accessibility decisions, and
interpretation limits.


## Official data source

Live data comes from CISA's public Known Exploited Vulnerabilities JSON feed:

https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

The project preserves the downloaded bytes, retrieval timestamp, source URL, and SHA-256 hash so generated results can be traced to a specific snapshot.




## Data notice

The records under `tests/fixtures` are fictional and exist only for software testing. They are not current threat intelligence and do not represent real vulnerabilities, vendors, or products.
