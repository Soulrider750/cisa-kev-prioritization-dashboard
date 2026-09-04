# Publishing status

Status: READY FOR PUBLICATION

Last reviewed: 2026-09-04

The repository owner approved public publication on 2026-09-04. The private
release candidate must complete its final CI run before repository visibility
is changed.

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

## Current restrictions

- Keep the repository private until this readiness change passes CI.
- Do not create the `v0.8.0` tag or release before public verification.
- Do not enable GitHub Pages or another deployment.
- Do not publish `SOURCE_MAP_PRIVATE.md`.
- Keep synthetic records clearly labeled as fictional test data.
