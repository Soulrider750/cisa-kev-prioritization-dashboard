# Backup and recovery

Validation scope reviewed: 2026-09-15. Manual off-host backup and isolated data/private-serving recovery have been verified; full-server recovery remains outside that acceptance.

## Purpose and scope

The dashboard uses one Ubuntu host, a persistent Docker data volume, a static web origin, and an outbound Cloudflare Tunnel. A source-code repository alone is not a complete recovery copy: deployed images, host configuration, credentials, and the generated data have separate recovery requirements.

A manual backup and isolated data-restore procedure has been exercised successfully. This establishes recovery of the archived dashboard data and private web serving using retained local Docker images. It does not establish a clean-server rebuild, public tunnel recovery, or a guaranteed recovery time.

## Backup contents and protection

The backup includes the complete dashboard volume, including historical releases, lock files, permissions, ownership, and the active-release symbolic link. It also includes deployment configuration and refresh units, an export of the exact deployed Docker images, a separate credential archive, inventories, manifests, and recovery notes.

Image and volume data are captured separately: an image export does not substitute for a backup of an external Docker volume. [Docker image-save documentation](https://docs.docker.com/reference/cli/docker/image/save/), [Docker volume-backup documentation](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes)

The Ubuntu staging and transfer directories restrict access through ownership and file permissions. Their archives are not individually encrypted. The off-host copy travels over authenticated SSH directly into an encrypted APFS disk image on a separate Mac, without a plaintext Mac staging copy. Keep the vault unmounted when not in use. Credentials, archives, detailed host inventories, and private evidence are excluded from the public repository.

Encryption protects the vault at rest; it does not protect an unlocked vault from a compromised operator account. SHA-256 manifests detect content changes against the expected manifest but are not digital signatures. SSH host-key checks and a separately retained expected manifest digest support transfer verification.

## Manual capture workflow

1. Confirm the exact deployed configuration, image identities, healthy public-serving containers, data-volume identity, available space, and an active/enabled refresh timer. Do not begin during another deployment or maintenance operation.
2. Export the exact already deployed images without pulling, rebuilding, or changing image references.
3. Pause the refresh timer and wait within a bounded period for an active refresh to finish. Leave the web origin and tunnel running.
4. Capture the data through a read-only volume mount while coordinating with the application's existing locks. Independently compare the archive with a complete file inventory and hashes.
5. Restore the timer's expected active/enabled state and verify it. Treat a failure to restore scheduling as an operational problem, even if an archive was created.
6. Transfer the complete backup directly to the encrypted off-host vault. Verify file counts, lengths, and hashes against the exact manifest.
7. Eject and reopen the vault, then read and verify the stored files again. Retain source evidence until the restore rehearsal succeeds and retention is explicitly reviewed.

A persistent timer may request a missed scheduled activation after it resumes. The backup procedure itself does not request a manual refresh. [Ubuntu systemd timer documentation](https://manpages.ubuntu.com/manpages/resolute/man5/systemd.timer.5.html)

## Isolated restore workflow

The accepted rehearsal returned selected files from the verified, reopened Mac backup to a new private Ubuntu input directory. It did not substitute the original Ubuntu staging files for the off-host copy.

The Ubuntu verifier checked the exact manifest, audited the archived configuration without installing it, and restored the data into a newly created scratch volume. Independent read-only checks verified every restored file hash, ownership, modes, symbolic links, metadata, and build validity. A private web container served that scratch data, and HTTP checks compared the served content with the archive, checked security headers, and rejected protected deployment paths. A final inventory verified that serving had not changed the restored data.

The test used the retained, previously verified deployed images. Test containers had no external network and no published host ports. Production data was not mounted into the test, no tunnel credential was used, no manual refresh occurred, and the production timer remained unchanged. Test containers were stopped and scratch resources were retained for review.

## Evidence and acceptance

The completed backup has a successful Ubuntu capture receipt, an off-host copy verification, and a readback after the vault was reopened. The restore has a separate successful receipt and phase audits proving isolated data restoration and private HTTP serving. Earlier receipts are immutable historical records: a capture receipt saying restoration was not yet tested is not rewritten after a later rehearsal passes.

Recovery closeout subsequently verified all eight original backup files and 29 evidence files after the encrypted vault was reopened. Closeout did not perform cleanup or a production upgrade.

Private closeout evidence records the exact run identifiers, manifest digest, restored release, helper versions, phase results, and retained resources. Public documentation summarizes the tested controls without publishing credentials or host-specific inventories. Record counts and retrieval timestamps belong to dated evidence, not permanent claims about the current live dashboard.

## Recovery limitations

The following remain explicitly outside the completed rehearsal:

- Importing the exported image archive into a clean Docker installation.
- Rebuilding a replacement Ubuntu host, Docker installation, systemd integration, or public tunnel.
- Validating Cloudflare account recovery, tunnel credential usability, DNS configuration restoration, or credential rotation.
- End-to-end application rollback after a production image upgrade.
- Automated recurring backups, backup-failure alerting, and automatic retention/deletion.
- A measured recovery-time objective or an agreed recovery-point objective.

The verified snapshot can restore only data captured by that backup. Later generated releases are outside that snapshot. The original host plus one separate Mac copy is a useful baseline, not protection against every shared physical or account compromise.

## Operating and retention policy

Backups remain manual. Before a production upgrade, confirm that the recovery copy is readable, the old deployed images and configuration remain available, and the backup's age is acceptable for the proposed change. If configuration, images, credentials, or data materially changed after the snapshot, assess whether a new capture is required; do not blindly rerun a baseline-specific helper.

After any future deployment, review and adapt the backup helper to the new deployment contract before taking and rehearsing a new backup. Preserve the previous verified recovery point until the replacement has passed off-host readback and the agreed restore check. Recurring frequency, retention periods, responsible operator, and acceptable data loss must be explicitly chosen before describing backup coverage as automated or continuous.

Cleanup is a separate, reviewed operation against exact resource identities. Never use broad Docker pruning, volume-deleting Compose teardown, or wildcard filesystem deletion as a recovery step. Do not delete a production volume or overwrite live data merely to test a backup.
