# Changelog

This file records notable changes to the CISA KEV Prioritization Dashboard.
Live catalog counts and snapshot digests are intentionally excluded because
they change whenever CISA updates the source feed.

## [Unreleased]

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

[Unreleased]: https://github.com/Soulrider750/cisa-kev-prioritization-dashboard/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/Soulrider750/cisa-kev-prioritization-dashboard/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/Soulrider750/cisa-kev-prioritization-dashboard/releases/tag/v0.8.0
