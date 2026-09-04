# CISA KEV Prioritization Dashboard

A learning-focused Python project that will retrieve, validate, analyze, and visualize the Cybersecurity and Infrastructure Security Agency's Known Exploited Vulnerabilities catalog.


## Project objective


The finished project will transform CISA KEV data into a reproducible, auditable dashboard containing catalog trends and transparent vulnerability review signals.


The dashboard will not claim to calculate an organization's actual risk. Asset ownership, exposure, business impact, compensating controls, and local threat intelligence are required for an organization-specific prioritization.


## Current stage

Stage 3 implements:

- immutable catalog and vulnerability models;
- strict KEV validation and normalization;
- bounded local JSON loading;
- approved-host HTTPS retrieval;
- redirect-destination validation;
- network timeout and response-time controls; and
- source timestamps and SHA-256 snapshot fingerprints.

Automated tests use only synthetic local data. Live CISA retrieval is performed separately so changing catalog contents or temporary network failures cannot make the test site unreliable.

Dashboard analysis and report generation have not been implemented yet.


## Official data source

Live data comes from CISA's public Known Exploited Vulnerabilities JSON feed:

https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json

The project preserves the downloaded bytes, retrieval timestamp, source URL, and SHA-256 hash so generated results can be traced to a specific snapshot.




## Data notice

The records under `tests/fixtures` are fictional and exist only for software testing. They are not current threat intelligence and do not represent real vulnerabilities, vendors, or products.
