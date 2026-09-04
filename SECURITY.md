# Security policy

## Supported versions

The current `main` branch and the latest tagged release are the supported
versions of this learning project. Earlier snapshots may not receive fixes.

## Reporting a vulnerability

Do not disclose sensitive vulnerability details, credentials, tokens, or
private data in a public issue.

If GitHub private vulnerability reporting is enabled for this repository, use
the repository's **Security** tab and select **Report a vulnerability**.

If private reporting is unavailable, use a private contact method listed on
the repository owner's GitHub profile. Do not post sensitive evidence publicly.

## Relevant security issues

Examples of relevant reports include:

- bypasses of the approved CISA source restrictions;
- unsafe redirect or URL handling;
- catalog validation bypasses;
- HTML injection in generated reports;
- spreadsheet-formula injection in CSV exports;
- corruption of saved snapshot or digest evidence; and
- unintended disclosure of local files or sensitive information.

## Responsible use

This project analyzes public CISA KEV catalog data. It does not contain exploit
code and should not be used to test systems without authorization.

Local and downloaded JSON must be treated as untrusted input. Generated
snapshots may reproduce text from the source catalog and should be reviewed
before being shared.

## Project limitations

This project is not affiliated with or endorsed by CISA. Its review queue is
not an organization-specific risk score and does not prove that an asset is
vulnerable, exposed, remediated, or compliant.

Security reports and maintenance are handled on a best-effort basis. No
specific response or remediation time is guaranteed.