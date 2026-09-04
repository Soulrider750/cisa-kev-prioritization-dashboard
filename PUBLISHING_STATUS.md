# Publishing status

Status: PUBLISHED

Published: 2026-09-04

Last reviewed: 2026-09-04

The repository was published on 2026-09-04 after the release candidate passed
local verification and GitHub CI across Python 3.11 through 3.14.

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

## Continuing safeguards

- Do not publish `SOURCE_MAP_PRIVATE.md`.
- Keep synthetic records clearly labeled as fictional test data.
- Review every generated artifact before sharing it.
- Treat deployment or GitHub Pages as a separate reviewed change.
- Run the offline verification gate before every release.
