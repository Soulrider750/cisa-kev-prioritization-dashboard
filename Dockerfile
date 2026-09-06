# syntax=docker/dockerfile:1

FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS builder

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY kev_dashboard/ ./kev_dashboard/

RUN python -m pip wheel \
    --no-cache-dir \
    --no-deps \
    --wheel-dir /wheels \
    .

FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS runtime

LABEL org.opencontainers.image.title="CISA KEV Prioritization Dashboard" \
    org.opencontainers.image.description="One-shot production worker for securely refreshing the live CISA KEV dashboard" \
    org.opencontainers.image.source="https://github.com/Soulrider750/cisa-kev-prioritization-dashboard" \
    org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Etc/UTC

COPY --from=builder /wheels/ /tmp/wheels/

RUN python -m pip install \
    --no-cache-dir \
    --no-deps \
    /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels

RUN groupadd --gid 10001 kevdash \
    && useradd --no-log-init \
        --uid 10001 \
        --gid 10001 \
        --home-dir /nonexistent \
        --no-create-home \
        --shell /usr/sbin/nologin \
        kevdash \
    && install -d -o 10001 -g 10001 -m 0750 /srv/kev-dashboard \
    && install -d -o 10001 -g 10001 -m 0700 /srv/kev-dashboard/candidates \
    && install -d -o 10001 -g 10001 -m 0750 /srv/kev-dashboard/releases

USER 10001:10001

WORKDIR /srv/kev-dashboard

ENTRYPOINT ["kev-dashboard-refresh"]
CMD ["--deployment-root", "/srv/kev-dashboard"]
