PYTHON ?= python3
AS_OF ?= 2026-09-03

.DEFAULT_GOAL := help

.PHONY: help test sample live verify

help:
	@printf "%s\n" \
		"make test    Run the unit-test suite" \
		"make sample  Build the deterministic synthetic dashboard" \
		"make live    Build from the current official CISA feed" \
		"make verify  Run the complete offline release verification"

test:
	$(PYTHON) -m unittest discover -s tests -v

sample:
	$(PYTHON) -m kev_dashboard --input tests/fixtures/kev_sample.json --as-of $(AS_OF) --output-dir build/sample

live:
	$(PYTHON) -m kev_dashboard --output-dir build/live

verify:
	$(PYTHON) tools/verify_project.py