# Changelog

This file records notable changes to the CISA KEV Prioritization Dashboard.
Live catalog counts and snapshot digests are intentionally excluded because
they change whenever CISA updates the source feed.

## Unreleased

### Added

- A separate search page for every entry in the validated KEV snapshot, with
  combined text, CVE, vendor, product, ransomware-use, CWE, and date-added
  filters, result counts, pagination, and expandable catalog details.
- Clickable HTTP and HTTPS references in each entry's Notes. Links open in a
  new tab while the surrounding Notes text remains visible.
- A full-catalog CSV download link on the search page, labeled to distinguish
  it from the filtered results.

### Changed

- Added dashboard navigation to the search page and a working CSV download
  link. Build validation, release verification, package data, and Docker build
  inputs now include the search assets.
- Permitted same-origin scripts and catalog requests in the NGINX Content
  Security Policy for search. The dashboard document retains its stricter
  policy.

The project owner reviewed this work locally on October 29, 2026. It has not
been published or deployed; the public and production version remains v0.9.1.

## [0.9.1] - 2026-09-11

Corrective patch for deployment image selection. Publishing this source
release does not upgrade an existing live deployment.

### Fixed

- Bound the production Compose image references to a protected per-host image
  lock, verified both local image IDs, and checked the fully resolved Compose
  model before a scheduled refresh can run.
- Added Bash and embedded-Python syntax regression checks for the root-run
  production refresh wrapper.

## [0.9.0] - 2026-09-09

### Added

- A reusable build pipeline and a dedicated one-shot live-refresh command.
- Strict candidate validation, deployment policy checks, serialized
  publication, atomic activation, and last-known-good release preservation.
- A non-root refresh-worker image and a read-only NGINX web-origin image with
  pinned base-image digests and fixed runtime identities.
- A hardened Docker Compose stack with separate refresh, private web, and
  tunnel networks and no host-published dashboard port.
- An outbound Cloudflare Tunnel service and systemd units for persistent,
  twice-daily refresh scheduling.
- Static contract tests for the container, Compose, systemd, publication, and
  live-refresh security boundaries.
- Public operations documentation, an engineering case study, and a verified
  live-dashboard overview image.

### Changed

- Dashboard generation now flows through one reusable pipeline shared by the
  local CLI and the production refresh command.
- Generated reports display source retrieval timing and retain complete source
  provenance and SHA-256 evidence.
- The release verifier now covers the committed deployment and public
  documentation assets in addition to the deterministic offline build.

### Security

- Candidate identifiers, deployment paths, symbolic links, lock files,
  permissions, and release collisions are rejected fail closed.
- Failed fetch, build, validation, locking, or publication operations preserve
  the currently active validated release.
- Long-running containers use read-only root filesystems, dropped Linux
  capabilities, `no-new-privileges`, resource limits, and non-root identities.
- The tunnel credential stays outside Git, Compose environment values, process
  arguments, and public operational evidence.

## [0.8.0] - 2026-09-04

- Initial public release of the dependency-free Python dashboard, synthetic
  offline demonstration, auditable JSON and CSV exports, self-contained HTML
  report, and Python 3.11 through 3.14 verification workflow.

[0.9.1]: https://github.com/Soulrider750/cisa-kev-prioritization-dashboard/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/Soulrider750/cisa-kev-prioritization-dashboard/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/Soulrider750/cisa-kev-prioritization-dashboard/releases/tag/v0.8.0
