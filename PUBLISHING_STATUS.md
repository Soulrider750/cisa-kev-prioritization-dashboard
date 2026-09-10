# Publishing status

Status: PUBLISHED

Current public release: v0.9.0

Release candidate: v0.9.1

Deployment status: LIVE

v0.9.0 production promotion: BLOCKED pending a corrective patch release

Repository published: 2026-09-04

v0.9.0 published: 2026-09-09

v0.9.0 release verified: 2026-09-09

Live deployment verified: 2026-09-09

Last reviewed: 2026-09-10

The repository was first published on 2026-09-04 after the initial release
passed local verification and GitHub CI across Python 3.11 through 3.14.
Version 0.9.0 records the completed live-deployment milestone. Its exact
candidate passed the offline release gate, GitHub CI, CodeQL analysis, and an
isolated Ubuntu verification that left the production deployment unchanged.
The annotated tag and public GitHub Release both resolve to the final reviewed
publication commit, and both generated source archives were retrieved
successfully.

A post-publication, read-only production inventory found that the v0.9.0
Compose image selection and the scheduled refresh wrapper's trusted image
identity came from different constants. The live deployment was not changed
and continues operating with its previously verified image set. Direct
production promotion of v0.9.0 is blocked; the correction is recorded under
`Unreleased` and will be delivered as a patch release without moving the
existing v0.9.0 tag.

## v0.9.1 candidate status

Version 0.9.1 contains the corrective image-lock change merged through pull
request #10. The underlying fix passed GitHub CI, the complete offline
verifier, real Compose configuration validation, and 31 isolated wrapper
behavior checks before version preparation.

The wrapper behavior checks used simulated Docker responses, root identity,
and file metadata. They establish controlled wrapper behavior, not successful
production execution.

The exact versioned candidate and its container images still require their
own release verification. Publication and production promotion remain pending
separate approval. The existing production deployment and published v0.9.0
tag are unchanged.

## v0.9.0 completed release gates.

- [x] All unit tests pass.
- [x] The complete offline verifier passes.
- [x] The synthetic dashboard has been visually reviewed.
- [x] A current live build has been reviewed separately.
- [x] Generated files, caches, and virtual environments are not tracked.
- [x] No credentials, tokens, personal paths, or private source maps are present.
- [x] All third-party material is properly attributed.
- [x] Commit names and email addresses are acceptable for public display.
- [x] The repository owner has explicitly approved publication.
- [x] The exact v0.9.0 candidate passed isolated Ubuntu verification.
- [x] Candidate testing left the production deployment unchanged.
- [x] The v0.9.0 tag and GitHub Release resolve to the publication commit.
- [x] The public v0.9.0 source archives were retrieved successfully.

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
