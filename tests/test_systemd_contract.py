"""Static tests for scheduled production refresh operations."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

COMPOSE_PATH = PROJECT_ROOT / "compose.yaml"
REFRESH_SCRIPT = (
    PROJECT_ROOT / "deploy" / "refresh-production.sh"
)
SERVICE_UNIT = (
    PROJECT_ROOT
    / "deploy"
    / "systemd"
    / "kev-dashboard-refresh.service"
)
TIMER_UNIT = (
    PROJECT_ROOT
    / "deploy"
    / "systemd"
    / "kev-dashboard-refresh.timer"
)


class SystemdContractTests(unittest.TestCase):
    """Verify the host scheduler and fixed refresh command."""

    def read_required(self, path: Path) -> str:
        if not path.is_file():
            self.fail(
                "required operations file is missing: "
                f"{path.relative_to(PROJECT_ROOT)}"
            )

        return path.read_text(encoding="utf-8")

    def test_required_operations_files_exist(self) -> None:
        missing = [
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (
                REFRESH_SCRIPT,
                SERVICE_UNIT,
                TIMER_UNIT,
            )
            if not path.is_file()
        ]

        self.assertEqual(missing, [])

    def test_refresh_script_is_fail_closed(self) -> None:
        text = self.read_required(REFRESH_SCRIPT)

        self.assertTrue(
            text.startswith("#!/usr/bin/env bash\n")
        )
        self.assertIn("set -Eeuo pipefail", text)
        self.assertIn("umask 077", text)

        required_fragments = (
            "readonly CONFIG_LINK='/opt/kev-dashboard/current'",
            "readonly CONFIG_ROOT='/opt/kev-dashboard/releases'",
            "readonly ENV_PATH='/etc/kev-dashboard/compose.env'",
            (
                "readonly DATA_VOLUME="
                "'kev-dashboard-production-data-v1'"
            ),
            "KEV_DASHBOARD_REFRESH_IMAGE",
            "KEV_DASHBOARD_REFRESH_IMAGE_ID",
            "KEV_DASHBOARD_WEB_IMAGE",
            "KEV_DASHBOARD_WEB_IMAGE_ID",
            "docker --context default compose",
            "--project-name kev-dashboard",
            "--profile operations config --quiet",
            "--profile operations config --format json",
            "--profile operations run",
            "--rm",
            "--no-deps",
            "--pull never",
            "--no-TTY",
            "refresh",
            "production Compose environment has an unexpected key",
            "production Compose environment has a duplicate key",
            "production Compose environment is missing a required key",
            "production refresh image reference is invalid",
            "production web image reference is invalid",
            "production refresh image ID is invalid",
            "production web image ID is invalid",
            'fail "trusted $image_role image identity mismatch"',
            "python3 -I -B -",
            "resolved production Compose model failed identity validation",
        )

        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

        for variable in (
            "DOCKER_HOST",
            "DOCKER_CONTEXT",
            "DOCKER_API_VERSION",
            "KEV_DASHBOARD_VOLUME",
            "KEV_DASHBOARD_REFRESH_IMAGE",
            "KEV_DASHBOARD_REFRESH_IMAGE_ID",
            "KEV_DASHBOARD_WEB_IMAGE",
            "KEV_DASHBOARD_WEB_IMAGE_ID",
            "COMPOSE_FILE",
            "COMPOSE_PROJECT_NAME",
            "COMPOSE_PROFILES",
            "COMPOSE_ENV_FILES",
            "COMPOSE_REMOVE_ORPHANS",
        ):
            self.assertRegex(
                text,
                rf"(?m)^\s*{variable}(?:\s|\\|$)",
            )

        for forbidden in (
            "docker compose up",
            "docker compose down",
            "docker volume rm",
            "docker system prune",
            "--build",
            "--pull always",
            "eval ",
            "kev-dashboard-refresh:c9328fb",
            (
                "sha256:"
                "c385c267c85e67c40de4e1dedd8e0b789f7ef0de"
                "bed917b72526580247c2a87e"
            ),
        ):
            self.assertNotIn(forbidden, text)

        self.assertNotRegex(
            text,
            (
                r'''(?m)^\s*(?:source|\.)\s+'''
                r'''(?:--\s+)?["']?\$ENV_PATH'''
            ),
            "the root-run wrapper must parse, not source, the env file",
        )

    def test_refresh_script_has_valid_bash_syntax(self) -> None:
        result = subprocess.run(
            ("bash", "-n", str(REFRESH_SCRIPT)),
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stderr,
        )

    def test_refresh_script_embedded_python_is_valid(self) -> None:
        text = self.read_required(REFRESH_SCRIPT)
        snippets = re.findall(
            r"(?ms)<<'PY'\n(.*?)^PY$",
            text,
        )

        self.assertEqual(len(snippets), 1)
        compile(
            snippets[0],
            str(REFRESH_SCRIPT),
            "exec",
        )

    def test_image_lock_contract_is_shared_with_compose(
        self,
    ) -> None:
        compose = self.read_required(COMPOSE_PATH)
        script = self.read_required(REFRESH_SCRIPT)

        image_variables = (
            (
                "KEV_DASHBOARD_REFRESH_IMAGE",
                "KEV_DASHBOARD_REFRESH_IMAGE_ID",
            ),
            (
                "KEV_DASHBOARD_WEB_IMAGE",
                "KEV_DASHBOARD_WEB_IMAGE_ID",
            ),
        )

        for image_variable, identity_variable in image_variables:
            with self.subTest(image_variable=image_variable):
                self.assertIn(
                    (
                        "${"
                        f"{image_variable}:?set {image_variable}"
                        "}"
                    ),
                    compose,
                )
                self.assertIn(image_variable, script)
                self.assertIn(identity_variable, script)
                self.assertNotIn(
                    "${" + identity_variable,
                    compose,
                )

    def test_service_is_oneshot_and_hardened(self) -> None:
        text = self.read_required(SERVICE_UNIT)

        required_lines = {
            "Wants=network-online.target",
            "Requires=docker.service",
            "After=network-online.target docker.service",
            "Type=oneshot",
            (
                "ExecStart=/opt/kev-dashboard/current/"
                "deploy/refresh-production.sh"
            ),
            "TimeoutStartSec=10min",
            "UMask=0077",
            "RuntimeDirectory=kev-dashboard-refresh",
            "NoNewPrivileges=yes",
            "PrivateTmp=yes",
            "PrivateDevices=yes",
            "ProtectSystem=strict",
            "ProtectHome=yes",
            "ProtectHostname=yes",
            "ProtectClock=yes",
            "ProtectKernelTunables=yes",
            "ProtectKernelModules=yes",
            "ProtectKernelLogs=yes",
            "ProtectControlGroups=yes",
            "RestrictAddressFamilies=AF_UNIX",
            "RestrictRealtime=yes",
            "RestrictSUIDSGID=yes",
            "LockPersonality=yes",
            "MemoryDenyWriteExecute=yes",
            "CapabilityBoundingSet=",
            "AmbientCapabilities=",
            "SystemCallArchitectures=native",
        }

        lines = {
            line.strip()
            for line in text.splitlines()
            if line.strip()
            and not line.lstrip().startswith("#")
        }

        self.assertTrue(
            required_lines.issubset(lines),
            required_lines - lines,
        )

        self.assertNotIn("[Install]", lines)
        self.assertNotRegex(text, r"(?m)^User=")

    def test_timer_is_persistent_and_bounded(self) -> None:
        text = self.read_required(TIMER_UNIT)

        calendars = re.findall(
            r"(?m)^OnCalendar=(.+)$",
            text,
        )

        self.assertEqual(
            calendars,
            [
                "*-*-* 10:17:00 UTC",
                "*-*-* 22:17:00 UTC",
            ],
        )

        required_lines = {
            "RandomizedDelaySec=15m",
            "AccuracySec=1m",
            "Persistent=true",
            "Unit=kev-dashboard-refresh.service",
            "WantedBy=timers.target",
        }

        lines = {
            line.strip()
            for line in text.splitlines()
            if line.strip()
            and not line.lstrip().startswith("#")
        }

        self.assertTrue(
            required_lines.issubset(lines),
            required_lines - lines,
        )


if __name__ == "__main__":
    unittest.main()
