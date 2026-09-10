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
readonly -a REQUIRED_ENV_KEYS=(
    KEV_DASHBOARD_VOLUME
    KEV_DASHBOARD_REFRESH_IMAGE
    KEV_DASHBOARD_REFRESH_IMAGE_ID
    KEV_DASHBOARD_WEB_IMAGE
    KEV_DASHBOARD_WEB_IMAGE_ID
)

export PATH='/usr/sbin:/usr/bin:/sbin:/bin'
export HOME='/nonexistent'
export DOCKER_CONFIG='/run/kev-dashboard-refresh/docker'

unset \
    DOCKER_HOST \
    DOCKER_CONTEXT \
    DOCKER_API_VERSION \
    KEV_DASHBOARD_VOLUME \
    KEV_DASHBOARD_REFRESH_IMAGE \
    KEV_DASHBOARD_REFRESH_IMAGE_ID \
    KEV_DASHBOARD_WEB_IMAGE \
    KEV_DASHBOARD_WEB_IMAGE_ID \
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

command -v python3 >/dev/null 2>&1 ||
    fail 'Python 3 is unavailable'

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

[[ "$(stat -c '%U:%G:%a:%F:%h' "$ENV_PATH")" == \
    'root:docker:640:regular file:1' ]] ||
    fail 'production Compose environment metadata mismatch'

declare -A ENV_VALUES=()
ENV_LINE_NUMBER=0

while IFS= read -r ENV_LINE || [[ -n "$ENV_LINE" ]]; do
    ((ENV_LINE_NUMBER += 1))

    [[ "$ENV_LINE" =~ ^([A-Z][A-Z0-9_]*)=(.*)$ ]] ||
        fail "production Compose environment line $ENV_LINE_NUMBER is invalid"

    ENV_KEY="${BASH_REMATCH[1]}"
    ENV_VALUE="${BASH_REMATCH[2]}"

    case "$ENV_KEY" in
        KEV_DASHBOARD_VOLUME|\
        KEV_DASHBOARD_REFRESH_IMAGE|\
        KEV_DASHBOARD_REFRESH_IMAGE_ID|\
        KEV_DASHBOARD_WEB_IMAGE|\
        KEV_DASHBOARD_WEB_IMAGE_ID)
            ;;
        *)
            fail "production Compose environment has an unexpected key: $ENV_KEY"
            ;;
    esac

    [[ -z "${ENV_VALUES[$ENV_KEY]+present}" ]] ||
        fail "production Compose environment has a duplicate key: $ENV_KEY"

    [[ -n "$ENV_VALUE" ]] ||
        fail "production Compose environment has an empty value: $ENV_KEY"

    ENV_VALUES["$ENV_KEY"]="$ENV_VALUE"
done < "$ENV_PATH"

for ENV_KEY in "${REQUIRED_ENV_KEYS[@]}"; do
    [[ -n "${ENV_VALUES[$ENV_KEY]+present}" ]] ||
        fail "production Compose environment is missing a required key: $ENV_KEY"
done

readonly LOCKED_VOLUME="${ENV_VALUES[KEV_DASHBOARD_VOLUME]}"
readonly REFRESH_IMAGE="${ENV_VALUES[KEV_DASHBOARD_REFRESH_IMAGE]}"
readonly REFRESH_IMAGE_ID="${ENV_VALUES[KEV_DASHBOARD_REFRESH_IMAGE_ID]}"
readonly WEB_IMAGE="${ENV_VALUES[KEV_DASHBOARD_WEB_IMAGE]}"
readonly WEB_IMAGE_ID="${ENV_VALUES[KEV_DASHBOARD_WEB_IMAGE_ID]}"

[[ "$LOCKED_VOLUME" == "$DATA_VOLUME" ]] ||
    fail 'production data volume identity mismatch'

[[ "$REFRESH_IMAGE" =~ \
   ^kev-dashboard-refresh:[0-9]+\.[0-9]+\.[0-9]+([.-][a-z0-9][a-z0-9.-]*)?$ ]] ||
    fail 'production refresh image reference is invalid'

[[ "$WEB_IMAGE" =~ \
   ^kev-dashboard-web:[0-9]+\.[0-9]+\.[0-9]+([.-][a-z0-9][a-z0-9.-]*)?$ ]] ||
    fail 'production web image reference is invalid'

[[ "$REFRESH_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]] ||
    fail 'production refresh image ID is invalid'

[[ "$WEB_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]] ||
    fail 'production web image ID is invalid'

mkdir -p -- "$DOCKER_CONFIG"
chmod 0700 "$DOCKER_CONFIG"

docker --context default info >/dev/null 2>&1 ||
    fail 'Docker default context is unavailable'

verify_image_identity() {
    local image_role="$1"
    local image_reference="$2"
    local expected_id="$3"
    local actual_id

    actual_id="$(
        docker --context default image inspect \
            --format '{{.Id}}' \
            "$image_reference"
    )" || fail "trusted $image_role image is unavailable"

    [[ "$actual_id" == "$expected_id" ]] ||
        fail "trusted $image_role image identity mismatch"
}

verify_image_identity \
    refresh \
    "$REFRESH_IMAGE" \
    "$REFRESH_IMAGE_ID"

verify_image_identity \
    web \
    "$WEB_IMAGE" \
    "$WEB_IMAGE_ID"

compose_prod() {
    COMPOSE_ANSI=never \
    COMPOSE_PROGRESS=plain \
    COMPOSE_DISABLE_ENV_FILE=1 \
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

COMPOSE_MODEL_JSON="$(
    compose_prod --profile operations config --format json
)" || fail 'could not resolve the production Compose model'
readonly COMPOSE_MODEL_JSON

if ! KEV_COMPOSE_MODEL_JSON="$COMPOSE_MODEL_JSON" \
    python3 -I -B - \
        "$REFRESH_IMAGE" \
        "$WEB_IMAGE" \
        "$DATA_VOLUME" <<'PY'
import json
import os
import sys


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


try:
    model = json.loads(os.environ["KEV_COMPOSE_MODEL_JSON"])
except (KeyError, json.JSONDecodeError) as error:
    fail(f"could not parse the resolved Compose model: {error}")

if not isinstance(model, dict):
    fail("resolved Compose model is not a mapping")

expected_images = {
    "refresh": sys.argv[1],
    "web": sys.argv[2],
}

services = model.get("services")

if not isinstance(services, dict):
    fail("resolved Compose model has no services mapping")

for service_name, expected_image in expected_images.items():
    service = services.get(service_name)

    if not isinstance(service, dict):
        fail(f"resolved Compose model is missing {service_name!r}")

    if service.get("image") != expected_image:
        fail(f"resolved {service_name} image does not match the image lock")

volumes = model.get("volumes")

if not isinstance(volumes, dict):
    fail("resolved Compose model has no volumes mapping")

dashboard_data = volumes.get("dashboard-data")

if not isinstance(dashboard_data, dict):
    fail("resolved Compose model is missing the dashboard data volume")

if dashboard_data.get("name") != sys.argv[3]:
    fail("resolved dashboard data volume does not match the volume lock")
PY
then
    fail 'resolved production Compose model failed identity validation'
fi

compose_prod --profile operations run \
    --rm \
    --no-deps \
    --pull never \
    --no-TTY \
    refresh
