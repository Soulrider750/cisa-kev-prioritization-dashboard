"""Static tests for the live dashboard container stack."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

from kev_dashboard import __version__ as DASHBOARD_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]

COMPOSE_PATH = PROJECT_ROOT / "compose.yaml"
WEB_DOCKERFILE_PATH = PROJECT_ROOT / "Dockerfile.web"
NGINX_CONFIG_PATH = PROJECT_ROOT / "deploy" / "nginx.conf"

DEPLOYMENT_ROOT = "/srv/kev-dashboard"
APPLICATION_IDENTITY = "10001:10001"
TUNNEL_IDENTITY = "65532:65532"

DATA_VOLUME = "dashboard-data"
REFRESH_NETWORK = "refresh-egress"
WEB_NETWORK = "web-internal"
TUNNEL_NETWORK = "tunnel-egress"
TUNNEL_TOKEN_SOURCE = (
    "/etc/kev-dashboard/cloudflared-token"
)
TUNNEL_TOKEN_TARGET = (
    "/run/secrets/cloudflared-token"
)

CLOUDFLARED_IMAGE = (
    "cloudflare/cloudflared:2026.8.3@sha256:"
    "51c9cefcb4569df44e1ad403ab1d3d8065aa8e84"
    "339bcfc6aee75502e1140339"
)

NGINX_BASE = (
    "nginxinc/nginx-unprivileged:"
    "1.30.4-alpine-slim@sha256:"
    "b1d850535f815f18e9dd12ca7e9f4d"
    "36de36a49e246ccd8ef64289b0d06bde49"
)


def _meaningful_lines(text: str) -> tuple[str, ...]:
    """Return nonempty, non-comment lines."""

    return tuple(
        line.rstrip()
        for line in text.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
    )


class ComposeContractTests(unittest.TestCase):
    """Verify the live deployment security contract."""

    def read_required(self, path: Path) -> str:
        """Read one required UTF-8 deployment file."""

        if not path.is_file():
            self.fail(
                "required deployment file is missing: "
                f"{path.relative_to(PROJECT_ROOT)}"
            )

        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            self.fail(
                f"{path.name} is not valid UTF-8: {error}"
            )

    def compose_text(self) -> str:
        return self.read_required(COMPOSE_PATH)

    def compose_lines(self) -> tuple[str, ...]:
        return _meaningful_lines(self.compose_text())

    def block(
        self,
        lines: tuple[str, ...],
        key: str,
        indentation: int,
    ) -> tuple[str, ...]:
        """Extract one indentation-delimited YAML block."""

        header = (" " * indentation) + key + ":"

        matches = [
            index
            for index, line in enumerate(lines)
            if line == header
        ]

        self.assertEqual(
            len(matches),
            1,
            f"expected exactly one {header!r} mapping",
        )

        start = matches[0]
        end = len(lines)

        for index in range(start + 1, len(lines)):
            line = lines[index]
            found_indentation = (
                len(line) - len(line.lstrip(" "))
            )

            if found_indentation <= indentation:
                end = index
                break

        return lines[start:end]

    def service_block(
        self,
        service_name: str,
    ) -> tuple[str, ...]:
        services = self.block(
            self.compose_lines(),
            "services",
            0,
        )

        return self.block(
            services,
            service_name,
            2,
        )

    def test_required_deployment_files_exist(self) -> None:
        missing = [
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in (
                COMPOSE_PATH,
                WEB_DOCKERFILE_PATH,
                NGINX_CONFIG_PATH,
            )
            if not path.is_file()
        ]

        self.assertEqual(
            missing,
            [],
            f"required deployment files are missing: {missing}",
        )

    def test_compose_uses_restricted_readable_yaml(
        self,
    ) -> None:
        text = self.compose_text()
        lines = self.compose_lines()

        self.assertNotIn(
            "\t",
            text,
            "Compose YAML must use spaces, not tabs",
        )

        self.assertIsNone(
            re.search(
                r"(?m)(^|\s)(?:&[\w-]+|\*[\w-]+|<<:)",
                text,
            ),
            "anchors, aliases, and merge keys are forbidden",
        )

        self.assertIsNone(
            re.search(r"(?m)^version:", text),
            "the obsolete Compose version field is forbidden",
        )

        top_level_keys = {
            match.group(1)
            for line in lines
            if (
                match := re.fullmatch(
                    r"([a-z][a-z0-9_-]*):(?:\s+.*)?",
                    line,
                )
            )
        }

        self.assertEqual(
            top_level_keys,
            {
                "name",
                "services",
                "networks",
                "volumes",
            },
        )

        self.assertIn("name: kev-dashboard", lines)

        services = self.block(lines, "services", 0)

        service_names = {
            match.group(1)
            for line in services
            if (
                match := re.fullmatch(
                    r"  ([a-z][a-z0-9_-]*):",
                    line,
                )
            )
        }

        self.assertEqual(
            service_names,
            {"refresh", "web", "tunnel"},
        )

    def test_volume_is_external_and_required(self) -> None:
        lines = self.compose_lines()
        volumes = self.block(lines, "volumes", 0)

        volume_names = {
            match.group(1)
            for line in volumes
            if (
                match := re.fullmatch(
                    r"  ([a-z][a-z0-9_-]*):",
                    line,
                )
            )
        }

        self.assertEqual(volume_names, {DATA_VOLUME})

        data_volume = self.block(
            volumes,
            DATA_VOLUME,
            2,
        )

        self.assertEqual(
            data_volume,
            (
                f"  {DATA_VOLUME}:",
                (
                    '    name: "${KEV_DASHBOARD_VOLUME:'
                    '?set KEV_DASHBOARD_VOLUME}"'
                ),
                "    external: true",
            ),
        )

    def test_services_mount_the_complete_volume(
        self,
    ) -> None:
        refresh_volumes = self.block(
            self.service_block("refresh"),
            "volumes",
            4,
        )

        self.assertEqual(
            refresh_volumes,
            (
                "    volumes:",
                "      - type: volume",
                f"        source: {DATA_VOLUME}",
                f"        target: {DEPLOYMENT_ROOT}",
                "        read_only: false",
            ),
        )

        web_volumes = self.block(
            self.service_block("web"),
            "volumes",
            4,
        )

        self.assertEqual(
            web_volumes,
            (
                "    volumes:",
                "      - type: volume",
                f"        source: {DATA_VOLUME}",
                f"        target: {DEPLOYMENT_ROOT}",
                "        read_only: true",
            ),
        )

        tunnel_volumes = self.block(
            self.service_block("tunnel"),
            "volumes",
            4,
        )

        self.assertEqual(
            tunnel_volumes,
            (
                "    volumes:",
                "      - type: bind",
                f"        source: {TUNNEL_TOKEN_SOURCE}",
                f"        target: {TUNNEL_TOKEN_TARGET}",
                "        read_only: true",
                "        bind:",
                "          create_host_path: false",
            ),
        )

    def test_services_have_fixed_runtime_hardening(
        self,
    ) -> None:
        expected_resources = {
            "refresh": (
                APPLICATION_IDENTITY,
                "128",
                "512m",
                "1.0",
            ),
            "web": (
                APPLICATION_IDENTITY,
                "64",
                "128m",
                "0.50",
            ),
            "tunnel": (
                TUNNEL_IDENTITY,
                "128",
                "256m",
                "0.50",
            ),
        }

        for service_name, resources in (
            expected_resources.items()
        ):
            with self.subTest(service=service_name):
                service = self.service_block(service_name)

                required_lines = (
                    f'    user: "{resources[0]}"',
                    "    read_only: true",
                    f"    pids_limit: {resources[1]}",
                    f"    mem_limit: {resources[2]}",
                    f"    cpus: {resources[3]}",
                )

                for required_line in required_lines:
                    self.assertIn(required_line, service)

                self.assertEqual(
                    self.block(service, "cap_drop", 4),
                    (
                        "    cap_drop:",
                        "      - ALL",
                    ),
                )

                self.assertEqual(
                    self.block(service, "security_opt", 4),
                    (
                        "    security_opt:",
                        "      - no-new-privileges:true",
                    ),
                )

                self.assertEqual(
                    self.block(service, "logging", 4),
                    (
                        "    logging:",
                        "      driver: local",
                        "      options:",
                        '        max-size: "10m"',
                        '        max-file: "3"',
                    ),
                )

                service_text = "\n".join(service)

                for forbidden_key in (
                    "privileged",
                    "cap_add",
                    "devices",
                    "device_cgroup_rules",
                    "pid",
                    "ipc",
                    "uts",
                    "cgroup",
                    "network_mode",
                ):
                    self.assertIsNone(
                        re.search(
                            rf"(?m)^    {forbidden_key}:",
                            service_text,
                        )
                    )

        refresh = self.service_block("refresh")
        self.assertNotIn("    tmpfs:", refresh)

        tunnel = self.service_block("tunnel")
        self.assertNotIn("    tmpfs:", tunnel)

        web = self.service_block("web")

        self.assertEqual(
            self.block(web, "tmpfs", 4),
            (
                "    tmpfs:",
                (
                    "      - /tmp:rw,noexec,nosuid,nodev,"
                    "size=16m,mode=0700,uid=10001,gid=10001"
                ),
            ),
        )

    def test_networks_are_split_without_host_ports(
        self,
    ) -> None:
        lines = self.compose_lines()
        text = self.compose_text()
        networks = self.block(lines, "networks", 0)

        network_names = {
            match.group(1)
            for line in networks
            if (
                match := re.fullmatch(
                    r"  ([a-z][a-z0-9_-]*):",
                    line,
                )
            )
        }

        self.assertEqual(
            network_names,
            {
                REFRESH_NETWORK,
                WEB_NETWORK,
                TUNNEL_NETWORK,
            },
        )

        self.assertEqual(
            self.block(networks, REFRESH_NETWORK, 2),
            (
                f"  {REFRESH_NETWORK}:",
                "    driver: bridge",
                "    internal: false",
            ),
        )

        self.assertEqual(
            self.block(networks, WEB_NETWORK, 2),
            (
                f"  {WEB_NETWORK}:",
                "    driver: bridge",
                "    internal: true",
            ),
        )

        self.assertEqual(
            self.block(networks, TUNNEL_NETWORK, 2),
            (
                f"  {TUNNEL_NETWORK}:",
                "    driver: bridge",
                "    internal: false",
            ),
        )

        self.assertEqual(
            self.block(
                self.service_block("refresh"),
                "networks",
                4,
            ),
            (
                "    networks:",
                f"      - {REFRESH_NETWORK}",
            ),
        )

        self.assertEqual(
            self.block(
                self.service_block("web"),
                "networks",
                4,
            ),
            (
                "    networks:",
                f"      - {WEB_NETWORK}",
            ),
        )

        self.assertEqual(
            self.block(
                self.service_block("tunnel"),
                "networks",
                4,
            ),
            (
                "    networks:",
                f"      {WEB_NETWORK}:",
                f"      {TUNNEL_NETWORK}:",
                "        gw_priority: 1",
            ),
        )

        self.assertIsNone(
            re.search(r"(?m)^\s+ports:", text),
            "host port publication is forbidden",
        )

        self.assertEqual(
            self.block(
                self.service_block("web"),
                "expose",
                4,
            ),
            (
                "    expose:",
                '      - "8080"',
            ),
        )

    def test_service_images_and_startup_are_controlled(
        self,
    ) -> None:
        refresh = self.service_block("refresh")

        self.assertIn(
            (
                '    image: "${KEV_DASHBOARD_REFRESH_IMAGE:'
                '?set KEV_DASHBOARD_REFRESH_IMAGE}"'
            ),
            refresh,
        )
        self.assertIn("    pull_policy: never", refresh)
        self.assertIn('    restart: "no"', refresh)
        self.assertNotIn("    build:", refresh)

        self.assertEqual(
            self.block(refresh, "profiles", 4),
            (
                "    profiles:",
                "      - operations",
            ),
        )

        web = self.service_block("web")

        self.assertIn(
            (
                '    image: "${KEV_DASHBOARD_WEB_IMAGE:'
                '?set KEV_DASHBOARD_WEB_IMAGE}"'
            ),
            web,
        )
        self.assertIn("    pull_policy: never", web)
        self.assertIn(
            "    restart: unless-stopped",
            web,
        )
        self.assertIn(
            "    stop_grace_period: 10s",
            web,
        )

        self.assertEqual(
            self.block(web, "build", 4),
            (
                "    build:",
                "      context: .",
                "      dockerfile: Dockerfile.web",
            ),
        )

        tunnel = self.service_block("tunnel")

        self.assertIn(
            f"    image: {CLOUDFLARED_IMAGE}",
            tunnel,
        )
        self.assertIn("    pull_policy: never", tunnel)
        self.assertIn(
            "    restart: unless-stopped",
            tunnel,
        )
        self.assertIn(
            "    stop_grace_period: 30s",
            tunnel,
        )
        self.assertNotIn("    build:", tunnel)
        self.assertNotIn("    profiles:", tunnel)

    def test_web_healthcheck_and_no_ambient_secrets(
        self,
    ) -> None:
        text = self.compose_text()
        web = self.service_block("web")

        self.assertEqual(
            self.block(web, "healthcheck", 4),
            (
                "    healthcheck:",
                "      test:",
                "        - CMD",
                "        - wget",
                "        - -q",
                "        - -O",
                "        - /dev/null",
                (
                    "        - http://127.0.0.1:"
                    "8080/index.html"
                ),
                "      interval: 30s",
                "      timeout: 5s",
                "      retries: 3",
                "      start_period: 10s",
            ),
        )

        for forbidden_key in (
            "environment",
            "env_file",
            "secrets",
            "configs",
        ):
            self.assertIsNone(
                re.search(
                    rf"(?m)^\s*{forbidden_key}:",
                    text,
                )
            )

        self.assertNotIn("/var/run/docker.sock", text)

        self.assertEqual(
            text.count(TUNNEL_TOKEN_SOURCE),
            1,
        )
        self.assertEqual(
            text.count(TUNNEL_TOKEN_TARGET),
            2,
        )

        interpolation_variables = set(
            re.findall(
                r"\$\{([A-Za-z_][A-Za-z0-9_]*)",
                text,
            )
        )

        self.assertEqual(
            interpolation_variables,
            {
                "KEV_DASHBOARD_REFRESH_IMAGE",
                "KEV_DASHBOARD_VOLUME",
                "KEV_DASHBOARD_WEB_IMAGE",
            },
        )

    def test_tunnel_command_health_and_dependency(
        self,
    ) -> None:
        text = self.compose_text()
        tunnel = self.service_block("tunnel")

        self.assertEqual(
            self.block(tunnel, "command", 4),
            (
                "    command:",
                "      - tunnel",
                "      - --metrics",
                "      - 127.0.0.1:2000",
                "      - --loglevel",
                "      - info",
                "      - run",
                "      - --token-file",
                f"      - {TUNNEL_TOKEN_TARGET}",
            ),
        )

        self.assertEqual(
            self.block(tunnel, "depends_on", 4),
            (
                "    depends_on:",
                "      web:",
                "        condition: service_healthy",
            ),
        )

        self.assertEqual(
            self.block(tunnel, "healthcheck", 4),
            (
                "    healthcheck:",
                "      test:",
                "        - CMD",
                "        - cloudflared",
                "        - tunnel",
                "        - --metrics",
                "        - 127.0.0.1:2000",
                "        - ready",
                "      interval: 30s",
                "      timeout: 5s",
                "      retries: 3",
                "      start_period: 20s",
            ),
        )

        self.assertIsNone(
            re.search(r"(?m)(?:^|\s)--token(?:\s|$)", text),
            "literal token arguments are forbidden",
        )

        for forbidden_text in (
            "TUNNEL_TOKEN=",
            "TUNNEL_TOKEN_FILE=",
            "CF_TUNNEL_TOKEN",
        ):
            self.assertNotIn(forbidden_text, text)

    def test_web_dockerfile_uses_pinned_base(
        self,
    ) -> None:
        text = self.read_required(
            WEB_DOCKERFILE_PATH
        )
        lines = _meaningful_lines(text)

        self.assertEqual(
            [
                line
                for line in lines
                if line.startswith("FROM ")
            ],
            [f"FROM {NGINX_BASE}"],
        )

        self.assertIn(
            (
                "COPY --chown=0:0 --chmod=0444 "
                "deploy/nginx.conf "
                "/etc/nginx/nginx.conf"
            ),
            lines,
        )

        self.assertEqual(
            [
                line
                for line in lines
                if line.startswith("USER ")
            ],
            [f"USER {APPLICATION_IDENTITY}"],
        )

        self.assertIn(
            'ENTRYPOINT ["/usr/sbin/nginx"]',
            lines,
        )
        self.assertIn(
            'CMD ["-g", "daemon off;"]',
            lines,
        )

        self.assertIn(
            "org.opencontainers.image.source",
            text,
        )
        self.assertIn(
            "org.opencontainers.image.licenses=\"MIT\"",
            text,
        )
        self.assertIn(
            (
                "org.opencontainers.image.version=\""
                f"{DASHBOARD_VERSION}\""
            ),
            text,
        )

        for forbidden_instruction in (
            "ADD",
            "ARG",
            "ENV",
            "EXPOSE",
            "VOLUME",
            "HEALTHCHECK",
            "RUN",
        ):
            self.assertFalse(
                any(
                    line.startswith(
                        forbidden_instruction + " "
                    )
                    for line in lines
                ),
                (
                    "Dockerfile.web must not use "
                    f"{forbidden_instruction}"
                ),
            )

    def test_nginx_serves_only_current_with_headers(
        self,
    ) -> None:
        text = self.read_required(NGINX_CONFIG_PATH)

        self.assertNotIn("\t", text)

        compact = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        required_fragments = (
            "pid /tmp/nginx.pid;",
            "error_log /dev/stderr",
            "access_log /dev/stdout",
            "include /etc/nginx/mime.types;",
            "default_type application/octet-stream;",
            "server_tokens off;",
            "open_file_cache off;",
            "listen 8080 default_server;",
            "server_name _;",
            f"root {DEPLOYMENT_ROOT}/current;",
            "index index.html;",
            "autoindex off;",
            "limit_except GET { deny all; }",
            "try_files $uri $uri/ =404;",
            "client_body_temp_path /tmp/client_temp;",
            "proxy_temp_path /tmp/proxy_temp;",
            "fastcgi_temp_path /tmp/fastcgi_temp;",
            "uwsgi_temp_path /tmp/uwsgi_temp;",
            "scgi_temp_path /tmp/scgi_temp;",
            "location ~ /\\. { return 404; }",
            "Cache-Control",
            "no-store",
            "Content-Security-Policy",
            "default-src 'none'",
            "frame-ancestors 'none'",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy",
            "Permissions-Policy",
            "Referrer-Policy",
            "no-referrer",
            "X-Content-Type-Options",
            "nosniff",
            "X-Frame-Options",
            "DENY",
        )

        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, compact)

        self.assertEqual(
            compact.count(
                f"root {DEPLOYMENT_ROOT}/current;"
            ),
            1,
        )

        self.assertEqual(
            len(re.findall(r"\blisten\s+", compact)),
            1,
        )

        forbidden_patterns = (
            r"(?m)^\s*user\s+",
            r"\blisten\s+80\s*;",
            r"\blisten\s+443\b",
            r"\bautoindex\s+on\s*;",
            r"\bproxy_pass\b",
            r"\balias\s+",
            r"\bssl_certificate\b",
            r"\bssl_certificate_key\b",
        )

        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(
                    re.search(
                        pattern,
                        text,
                        re.IGNORECASE,
                    )
                )


if __name__ == "__main__":
    unittest.main()
