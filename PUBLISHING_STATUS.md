# Publishing status

Status: PUBLISHED

Deployment status: LIVE

Published: 2026-09-04

Live deployment verified: 2026-09-09

Last reviewed: 2026-09-09

The repository was published on 2026-09-04 after the release candidate passed
local verification and GitHub CI across Python 3.11 through 3.14. The public
dashboard subsequently passed container, private-origin, tunnel, HTTPS,
publication, and naturally scheduled refresh verification.

## Required gates

- [x] All unit tests pass.
- [x] The complete offline verifier passes.
- [x] The synthetic dashboard has been visually reviewed.
- [x] A current live build has been reviewed separately.
- [x] Generated files, caches, and virtual environments are not tracked.
- [x] No credentials, tokens, personal paths, or private source maps are present.
- [x] All third-party material is properly attributed.
- [x] Commit names and email addresses are acceptable for public display.
- [x] The repository owner has explicitly approved publication.

## Live deployment gates

- [x] The live dashboard is available over HTTPS at the documented hostname.
- [x] HTTP requests redirect to HTTPS without changing the requested path.
- [x] Edge caching is bypassed for the live hostname.
- [x] The origin is reached through an outbound-only Cloudflare Tunnel.
- [x] No dashboard service publishes a port on the Ubuntu host.
- [x] Long-running containers use fixed non-root identities, read-only root
  filesystems, dropped capabilities, resource limits, and health checks.
- [x] The web origin mounts production dashboard data read-only.
- [x] Refresh publication is serialized, validated, and last-known-good.
- [x] A systemd timer initiated a successful production refresh without manual
  intervention on 2026-09-09.
- [x] Public metadata agreed with the activated production release.
- [x] Tunnel health notifications are configured.
- [x] The tunnel credential is absent from Git, Compose environment values,
  process arguments, and public evidence.

## Continuing safeguards

- Do not publish `SOURCE_MAP_PRIVATE.md`.
- Keep synthetic records clearly labeled as fictional test data.
- Review every generated artifact before sharing it.
- Keep host inventories, private operational evidence, and credentials out of
  the public repository.
- Keep changing catalog counts and snapshot digests out of permanent project
  claims.
- Treat every future deployment, credential, image, network, or scheduling
  change as a separately reviewed change.
- Revoke and replace a tunnel credential immediately if exposure is suspected.
- Run the offline verification gate before every release.
