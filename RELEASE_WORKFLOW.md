# Release workflow

This checklist defines the review required before a version is committed,
tagged, or published. No command in this repository automatically publishes
the project.

Current release review: v0.9.0 complete

Latest published release: v0.9.0

Release published: 2026-09-09

## 1. Technical verification

- [x] Run `python3 --version` and confirm Python 3.11 or later.
- [x] Run `make test`.
- [x] Run `make verify`.
- [x] Run `git diff --check`.
- [x] Confirm `git ls-files build` produces no output.
- [x] Confirm no virtual environment, cache, or compiled Python files are tracked.
- [x] Review every failure instead of bypassing the verifier.

## 2. Visual verification

- [x] Run `make sample`.
- [x] Open `build/sample/index.html`.
- [x] Inspect the report at desktop width.
- [x] Inspect the report at narrow mobile width.
- [x] Confirm headings, charts, tables, links, and expandable data are readable.
- [x] Confirm the report loads without external scripts, fonts, or stylesheets.

## 3. Live-data verification

- [x] Run `make live` separately from the offline gate.
- [x] Confirm the source is the approved CISA HTTPS feed.
- [x] Confirm the downloaded record count agrees with the generated metadata.
- [x] Confirm the snapshot SHA-256 value is present.
- [x] Avoid writing current catalog counts into permanent documentation.

Live-data results change over time and must not be used as deterministic test
expectations.

## 4. Privacy and content review

- [x] Search tracked files for credentials, tokens, private keys, and passwords.
- [x] Search for personal filesystem paths and unintended email addresses.
- [x] Confirm all fixture records remain obviously synthetic.
- [x] Confirm no raw coursework, private source map, or third-party submission is included.
- [x] Confirm claims in the README match implemented and tested behavior.
- [x] Confirm CISA is identified as the data source without implying endorsement.

## 5. Git identity review

- [x] Review the configured Git author name.
- [x] Review the configured Git author email.
- [x] Review author information in every existing commit.
- [x] Decide whether any existing history must be rewritten before publication.
- [x] Make a recoverable backup before any approved history rewrite.

Changing the current Git configuration affects future commits only. It does
not alter author information already stored in repository history.

## 6. Publication decision

- [x] Review the complete staged diff.
- [x] Update `PUBLISHING_STATUS.md`.
- [x] Obtain explicit approval from the repository owner.
- [x] Create or connect a remote only after approval.
- [x] Push only the reviewed commit history.
- [x] Verify the public repository immediately after publication.

## 7. Live deployment verification

- [x] Build deployment artifacts only from a clean, reviewed commit.
- [x] Transfer committed source with an integrity-checked Git bundle.
- [x] Verify pinned container identities before production use.
- [x] Confirm the refresh, web, and tunnel services retain their tested runtime
  restrictions.
- [x] Confirm the web origin is reachable only through its private container
  network and has no host-published port.
- [x] Keep the tunnel credential outside Git, Compose environment values,
  process arguments, and captured evidence.
- [x] Validate a candidate release before atomically changing `current`.
- [x] Confirm failed refreshes preserve the last-known-good release.
- [x] Verify the public hostname, HTTPS redirect, security headers, and cache
  policy independently.
- [x] Run one controlled manual refresh before enabling the timer.
- [x] Observe one successful timer-initiated refresh before closing deployment.
- [x] Confirm the public metadata agrees with the activated production release.
- [x] Configure tunnel health notifications.

Production evidence contains host-specific details and remains private. Public
documentation records the controls and verification outcome, not credentials,
raw host inventories, temporary paths, or changing catalog counts.

## 8. v0.9.0 release record

- [x] Merge the exact release candidate through protected pull request #7.
- [x] Confirm the merged commit passes main-branch offline verification and
  CodeQL analysis.
- [x] Complete isolated Ubuntu verification without changing production.
- [x] Preserve host-specific evidence outside the public repository.
- [x] Create the annotated `v0.9.0` tag from the final publication commit.
- [x] Publish the GitHub Release from that exact tag.
- [x] Verify the public tag, release metadata, and downloadable source
  archives before closing the release record.
