# CISA KEV Prioritization Dashboard

A learning-focused Python project that will retrieve, validate, analyze, and visualize the Cybersecurity and Infrastructure Security Agency's Known Exploited Vulnerabilities catalog.


## Project objective


The finished project will transform CISA KEV data into a reproducible, auditable dashboard containing catalog trends and transparent vulnerability review signals.


The dashboard will not claim to calculate an organization's actual risk. Asset ownership, exposure, business impact, compensating controls, and local threat intelligence are required for an organization-specific prioritization.


## Current stage

Stage 2 implements:

- immutable catalog and vulnerability models;
- normalization of external JSON field names;
- CVE, date, category, count, and duplicate validation;
- optional forensic-triage and CWE handling; and
- derived remediation-window calculations.

The application currently only operates on the synthetic offline fixture.
Live CISA retrieval and dashboard generation have not been implemented yet.




## Data notice

The records under `tests/fixtures` are fictional and exist only for software testing. They are not current threat intelligence and do not represent real vulnerabilities, vendors, or products.
