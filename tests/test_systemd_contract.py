"""Static tests for scheduled production refresh operations."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

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
            "readonly WORKER_REF='kev-dashboard-refresh:c9328fb'",
            (
                "readonly WORKER_ID='sha256:"
                "c385c267c85e67c40de4e1dedd8e0b789f7ef0de"
                "bed917b72526580247c2a87e'"
            ),
            "docker --context default compose",
            "--project-name kev-dashboard",
            "--profile operations config --quiet",
            "--profile operations run",
            "--rm",
            "--no-deps",
            "--pull never",
            "--no-TTY",
            "refresh",
        )

        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

        for variable in (
            "DOCKER_HOST",
            "DOCKER_CONTEXT",
            "DOCKER_API_VERSION",
            "KEV_DASHBOARD_VOLUME",
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
        ):
            self.assertNotIn(forbidden, text)

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
