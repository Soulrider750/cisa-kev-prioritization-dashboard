# CISA KEV Prioritization Dashboard

A learning-focused Python project that will retrieve, validate, analyze, and visualize the Cybersecurity and Infrastructure Security Agency's Known Exploited Vulnerabilities catalog.


## Project objective


The finished project will transform CISA KEV data into a reproducable, auditable dashboard containing catalog trends and transparent vulnerability review signals.


The dashboard will not claim to calculate an organization's actual risk. Asset ownership, exposure, business impact, compensating controls, and local threat intelligence are required for an organization-specific prioritization.


## Current stage

Stage 1 establishes:


- the Python package structure;
- an offline synthetic KEV fixture;
- the initial automated tests; and
- the command used to run the roject.


No live CISA data is used during this stage.


## Data notice

The records under `tests/fixtures` are fictional and exist only for software testing. They are not current threat intelligence and do not represent real vulnerabilities, vendors, or products.
