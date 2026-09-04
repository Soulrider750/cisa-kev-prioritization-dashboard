# Release workflow

This checklist defines the review required before a version is committed,
tagged, or published. No command in this repository automatically publishes
the project.

## 1. Technical verification

- [ ] Run `python3 --version` and confirm Python 3.11 or later.
- [ ] Run `make test`.
- [ ] Run `make verify`.
- [ ] Run `git diff --check`.
- [ ] Confirm `git ls-files build` produces no output.
- [ ] Confirm no virtual environment, cache, or compiled Python files are tracked.
- [ ] Review every failure instead of bypassing the verifier.

## 2. Visual verification

- [ ] Run `make sample`.
- [ ] Open `build/sample/index.html`.
- [ ] Inspect the report at desktop width.
- [ ] Inspect the report at narrow mobile width.
- [ ] Confirm headings, charts, tables, links, and expandable data are readable.
- [ ] Confirm the report loads without external scripts, fonts, or stylesheets.

## 3. Live-data verification

- [ ] Run `make live` separately from the offline gate.
- [ ] Confirm the source is the approved CISA HTTPS feed.
- [ ] Confirm the downloaded record count agrees with the generated metadata.
- [ ] Confirm the snapshot SHA-256 value is present.
- [ ] Avoid writing current catalog counts into permanent documentation.

Live-data results change over time and must not be used as deterministic test
expectations.

## 4. Privacy and content review

- [ ] Search tracked files for credentials, tokens, private keys, and passwords.
- [ ] Search for personal filesystem paths and unintended email addresses.
- [ ] Confirm all fixture records remain obviously synthetic.
- [ ] Confirm no raw coursework, private source map, or third-party submission is included.
- [ ] Confirm claims in the README match implemented and tested behavior.
- [ ] Confirm CISA is identified as the data source without implying endorsement.

## 5. Git identity review

- [ ] Review the configured Git author name.
- [ ] Review the configured Git author email.
- [ ] Review author information in every existing commit.
- [ ] Decide whether any existing history must be rewritten before publication.
- [ ] Make a recoverable backup before any approved history rewrite.

Changing the current Git configuration affects future commits only. It does
not alter author information already stored in repository history.

## 6. Publication decision

- [ ] Review the complete staged diff.
- [ ] Update `PUBLISHING_STATUS.md`.
- [ ] Obtain explicit approval from the repository owner.
- [ ] Create or connect a remote only after approval.
- [ ] Push only the reviewed commit history.
- [ ] Verify the public repository immediately after publication.
