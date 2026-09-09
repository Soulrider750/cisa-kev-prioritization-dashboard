# Live deployment operations

This document describes the public, security-relevant operating model for the
live CISA KEV Prioritization Dashboard. It intentionally excludes credentials,
private host inventories, temporary deployment paths, and raw production
evidence.

## Service scope

The public dashboard is available at
[kev.cloudsoulrider750.net](https://kev.cloudsoulrider750.net/). It presents a
static report derived from CISA's public Known Exploited Vulnerabilities JSON
feed. The deployment is an independent learning and portfolio project; it is
not affiliated with or endorsed by CISA and does not provide an availability
service-level agreement.

The site is intentionally public and does not contain user accounts, sessions,
forms, or organization-specific asset data. It remains a triage and workflow
aid rather than an organizational risk score.

## Architecture and trust boundaries

```text
approved CISA HTTPS feed
          |
          v
one-shot refresh container ---- refresh egress network
          |
          v
external dashboard data volume
          |
          +---- read-only ----> NGINX container
                                      |
                               private web network
                                      |
                                      v
                              cloudflared container
                                      |
                               tunnel egress network
                                      |
                                      v
                         Cloudflare edge and public HTTPS
```

The refresh worker is the only service allowed to write dashboard data. The
NGINX origin mounts that data read-only and serves only the active `current`
release. The tunnel does not mount dashboard data. NGINX and the tunnel share a
private internal network, while refresh and tunnel egress use separate bridge
networks.

No dashboard container publishes a port on the Ubuntu host. `cloudflared`
establishes outbound connections to Cloudflare and proxies the public hostname
to the internal NGINX service. Visitor TLS terminates at Cloudflare, while the
tunnel protects traffic between Cloudflare and the private connector.

The committed contract is defined by `compose.yaml`, `Dockerfile`,
`Dockerfile.web`, `deploy/nginx.conf`, and the systemd units under
`deploy/systemd`.

## Refresh and publication lifecycle

The refresh service is a one-shot operation:

1. Acquire the refresh lock so overlapping executions cannot proceed.
2. Retrieve the catalog only from the approved CISA HTTPS source.
3. Validate and normalize the complete catalog.
4. Create a private candidate directory.
5. Generate the snapshot, metadata, summaries, CSV exports, and HTML report.
6. Validate the complete candidate build and deployment policy.
7. Acquire the publication lock and move the candidate into a versioned
   release directory.
8. Atomically switch `current` to the validated release.
9. Emit one structured success event for operational evidence.

Fetch, build, validation, policy, lock, or activation failures return a
nonzero status and do not replace the active release. Candidate cleanup is
attempted without changing the last-known-good dashboard.

## Schedule

The systemd timer has two daily base times:

- 10:17 UTC
- 22:17 UTC

Each activation receives up to fifteen minutes of randomized delay. The timer
is persistent, so a missed activation is requested after the host and timer
become available again. The live retrieval timestamp may advance even when
CISA has not changed the catalog; in that case, the catalog version and source
snapshot digest can legitimately remain the same.

## Runtime security controls

The committed container contract requires:

- immutable, digest-pinned upstream base images;
- fixed non-root runtime identities;
- read-only container root filesystems;
- all Linux capabilities dropped;
- `no-new-privileges` enabled;
- bounded memory, CPU, and process counts;
- bounded local container logs;
- health checks for the web origin and tunnel connector;
- separate internal and egress networks;
- an external production data volume;
- read-only data access for the web origin; and
- no host-published dashboard ports.

The tunnel credential is stored outside the repository and mounted read-only as
a file. It must never be placed in source control, Compose environment values,
process arguments, terminal transcripts, issue reports, or public evidence.

NGINX disables directory indexing, refuses hidden paths, serves only generated
static files, and adds restrictive browser security headers. Cloudflare forces
the public hostname to HTTPS and bypasses edge caching so the active release is
served without a stale dashboard copy.

## Provenance and public verification

Every successful build preserves the retrieved CISA snapshot and publishes
metadata containing:

- the approved source URL;
- catalog version and release date;
- analysis date and retrieval timestamp;
- record count; and
- SHA-256 digest of the source snapshot.

These values are intentionally dynamic and must not be copied into permanent
README claims. Users can inspect the current metadata at
<https://kev.cloudsoulrider750.net/data/metadata.json>.

A minimal external availability check is:

```bash
curl --fail --silent --show-error \
  --proto '=https' \
  --tlsv1.2 \
  https://kev.cloudsoulrider750.net/data/metadata.json
```

## Operator checks

The timer and last refresh result can be inspected without changing state:

```bash
systemctl list-timers kev-dashboard-refresh.timer --all --no-pager

systemctl show kev-dashboard-refresh.service \
  --property=ActiveState \
  --property=Result \
  --property=ExecMainStatus

journalctl \
  --unit kev-dashboard-refresh.service \
  --since '24 hours ago' \
  --no-pager \
  --output cat
```

A completed one-shot service normally returns to `inactive` with
`Result=success` and `ExecMainStatus=0`. Its structured event must report
`event=kev_dashboard.refresh`, `status=success`, and
`code=refresh_succeeded`.

Cloudflare tunnel health notifications provide separate coverage for connector
availability. A healthy connector alone does not prove that the internal web
origin or publication pipeline is healthy, so tunnel, timer, release, and
public HTTP checks remain distinct.

## Change and recovery boundaries

Deployment changes follow the same fail-closed sequence as the original
installation: verify source and image identities, validate the Compose model,
stage a versioned configuration, confirm private health, activate it, test the
public hostname, and only then accept the change.

If a refresh fails, inspect its structured event and journal output before
another attempt. Do not manually replace the dashboard data `current` link or
delete the active release. If unsafe content becomes publicly reachable,
disable the Cloudflare published route first so public access stops without
altering production data. If the tunnel credential may have been exposed,
rotate it through Cloudflare and replace the protected host file.

Broad cleanup commands such as Docker system or volume pruning, Compose
teardown with volume deletion, and wildcard deletion are outside the recovery
procedure. The production data volume must not be deleted during diagnosis.

## Current limitations and future work

The deployment currently uses one Ubuntu host, one production data volume, and
one connector container. Host failure therefore remains a service-availability
risk. Tunnel alerts are configured, but a separate external alert for refresh
failure is future work.

Automated release retention and a tested backup-and-restore procedure are not
yet implemented. Until those controls are designed and rehearsed against a
scratch volume, release cleanup and recovery remain deliberate manual review
activities rather than automated claims.

## References

- [CISA Known Exploited Vulnerabilities Catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- [CISA KEV JSON feed](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json)
- [Cloudflare Tunnel documentation](https://developers.cloudflare.com/tunnel/)
- [Docker Compose file reference](https://docs.docker.com/reference/compose-file/)
- [systemd timer documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)
