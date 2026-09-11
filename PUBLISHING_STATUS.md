# Publishing status

This publication-source checkpoint records completed acceptance and owner
approval before external tag, release, and archive verification. Historical
publication dates below are not a claim that v0.9.1 has already been published.

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
production promotion of v0.9.0 remains blocked. The correction is recorded in
the v0.9.1 changelog entry; the existing v0.9.0 tag will not be moved.

## v0.9.1 candidate status

Version 0.9.1 contains the corrective image-lock change merged through pull
request #10. Before version preparation, the underlying fix passed the
complete offline verifier, GitHub CI, real Compose configuration validation,
and 31 isolated wrapper behavior checks. Those behavior checks used simulated
Docker responses, root identity, and file metadata.

The exact versioned candidate,
`850d759335bc164d70c57a494748008d505dec66`, subsequently passed the complete
offline verifier with 187 tests, pull-request CI, and Ubuntu acceptance of
its Linux/amd64 worker and web images.

Isolated Ubuntu runtime acceptance used a root-run refresh wrapper adapted
for the test deployment and a dedicated scratch volume. One live refresh
completed successfully. Four rejection cases verified rejection of
incorrect lock-file permissions or image identities, including preservation
of the complete last-known-good scratch release after a rejected attempt.
Private HTTP checks verified the expected dashboard content, security
headers, and blocked deployment paths.

An initial web-runtime verification failure came from the verifier rejecting
Docker's legacy representation of the expected named-volume mount. A
verifier-only correction checked the resolved mount type, exact volume name,
destination, and read-only access, while allowing only its matching legacy
encoding. The original failure evidence was retained. Recovery acceptance
passed without changing the application or candidate images and without
performing an additional live refresh.

Pull request #11 merged the candidate as
`2f7f029050c343ec1c69fa3ed60582ce8011c338`. The candidate and merge commits
have identical Git trees. The merged commit also passed local offline
verification and main-branch Offline verification and CodeQL workflows.

Host-specific evidence remains private. Candidate acceptance did not mount
production data or change the production deployment. It did not establish
v0.9.1 systemd timer acceptance or validate an installed production upgrade.

Final publication preparation changes only README, changelog, publishing
status, and release-workflow documentation. Application and deployment code
remain unchanged. README is a worker build input and package metadata, so
candidate-image acceptance remains attributed to the original candidate
commit, not to images rebuilt from the final publication source. Any such
images require separate verification before production use.

The repository owner approved finalization and publication of v0.9.1, subject
to successful final source verification and GitHub CI. Tag creation, GitHub
Release publication, and public archive verification remain pending at this
publication-source checkpoint. Production promotion requires separate
approval. The existing deployment and published v0.9.0 tag remain unchanged.

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
