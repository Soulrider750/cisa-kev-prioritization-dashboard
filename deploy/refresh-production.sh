#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

readonly CONFIG_LINK='/opt/kev-dashboard/current'
readonly CONFIG_ROOT='/opt/kev-dashboard/releases'
readonly ENV_PATH='/etc/kev-dashboard/compose.env'
readonly DATA_VOLUME='kev-dashboard-production-data-v1'
readonly WORKER_REF='kev-dashboard-refresh:c9328fb'
readonly WORKER_ID='sha256:c385c267c85e67c40de4e1dedd8e0b789f7ef0debed917b72526580247c2a87e'

export PATH='/usr/sbin:/usr/bin:/sbin:/bin'
export HOME='/nonexistent'
export DOCKER_CONFIG='/run/kev-dashboard-refresh/docker'

unset \
    DOCKER_HOST \
    DOCKER_CONTEXT \
    DOCKER_API_VERSION \
    KEV_DASHBOARD_VOLUME \
    COMPOSE_FILE \
    COMPOSE_PROJECT_NAME \
    COMPOSE_PROFILES \
    COMPOSE_ENV_FILES \
    COMPOSE_DISABLE_ENV_FILE \
    COMPOSE_REMOVE_ORPHANS \
    COMPOSE_IGNORE_ORPHANS \
    COMPOSE_STATUS_STDOUT \
    COMPOSE_MENU

[[ "$(id -u)" == '0' ]] ||
    fail 'scheduled refresh must run as root'

command -v docker >/dev/null 2>&1 ||
    fail 'Docker CLI is unavailable'

[[ -S /var/run/docker.sock ]] ||
    fail 'Docker socket is unavailable'

[[ -L "$CONFIG_LINK" ]] ||
    fail 'production configuration link is missing'

CONFIG_RELEASE="$(readlink -f -- "$CONFIG_LINK")" ||
    fail 'could not resolve production configuration'
readonly CONFIG_RELEASE

case "$CONFIG_RELEASE" in
    "$CONFIG_ROOT"/*)
        ;;
    *)
        fail 'production configuration escapes release root'
        ;;
esac

[[ -d "$CONFIG_RELEASE" && ! -L "$CONFIG_RELEASE" ]] ||
    fail 'production configuration is not a real directory'

[[ -f "$CONFIG_RELEASE/compose.yaml" &&
   ! -L "$CONFIG_RELEASE/compose.yaml" ]] ||
    fail 'production Compose file is not a regular file'

[[ -f "$ENV_PATH" && ! -L "$ENV_PATH" ]] ||
    fail 'production Compose environment is not a regular file'

[[ "$(stat -c '%U:%G:%a:%F' "$ENV_PATH")" == \
    'root:docker:640:regular file' ]] ||
    fail 'production Compose environment metadata mismatch'

[[ "$(cat -- "$ENV_PATH")" == \
    "KEV_DASHBOARD_VOLUME=$DATA_VOLUME" ]] ||
    fail 'production Compose environment content mismatch'

mkdir -p -- "$DOCKER_CONFIG"
chmod 0700 "$DOCKER_CONFIG"

docker --context default info >/dev/null 2>&1 ||
    fail 'Docker default context is unavailable'

[[ "$(
    docker --context default image inspect \
        --format '{{.Id}}' \
        "$WORKER_REF"
)" == "$WORKER_ID" ]] ||
    fail 'trusted refresh image identity mismatch'

compose_prod() {
    COMPOSE_ANSI=never \
    COMPOSE_PROGRESS=plain \
        docker --context default compose \
        --ansi never \
        --progress plain \
        --project-name kev-dashboard \
        --project-directory "$CONFIG_RELEASE" \
        --env-file "$ENV_PATH" \
        --file "$CONFIG_RELEASE/compose.yaml" \
        "$@"
}

compose_prod --profile operations config --quiet

compose_prod --profile operations run \
    --rm \
    --no-deps \
    --pull never \
    --no-TTY \
    refresh
