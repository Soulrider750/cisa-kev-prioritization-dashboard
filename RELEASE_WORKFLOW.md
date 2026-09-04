# Release workflow

This checklist defines the review required before a version is committed,
tagged, or published. No command in this repository automatically publishes
the project.

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
