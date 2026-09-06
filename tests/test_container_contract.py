"""Tests for the production refresh-container contract."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import unittest


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

DOCKERFILE_PATH = (
    PROJECT_ROOT / "Dockerfile"
)

DOCKERIGNORE_PATH = (
    PROJECT_ROOT / ".dockerignore"
)

DEPLOYMENT_ROOT = "/srv/kev-dashboard"

CONTAINER_IDENTITY = "10001:10001"

IMAGE_SOURCE = (
    "https://github.com/Soulrider750/"
    "cisa-kev-prioritization-dashboard"
)


def _logical_instructions(
    dockerfile_text: str,
) -> tuple[tuple[str, str], ...]:
    """Join continuations and return Docker instructions."""

    instructions: list[
        tuple[str, str]
    ] = []

    continued_parts: list[str] = []

    for raw_line in dockerfile_text.splitlines():
        line = raw_line.strip()

        if (
            not line
            or (
                not continued_parts
                and line.startswith("#")
            )
        ):
            continue

        continued = line.endswith("\\")

        if continued:
            line = line[:-1].rstrip()

        continued_parts.append(line)

        if continued:
            continue

        logical_line = " ".join(
            continued_parts
        )

        continued_parts.clear()

        (
            keyword,
            separator,
            value,
        ) = logical_line.partition(" ")

        if not separator:
            raise AssertionError(
                "Docker instruction has no value: "
                f"{logical_line!r}"
            )

        instructions.append(
            (
                keyword.upper(),
                value.strip(),
            )
        )

    if continued_parts:
        raise AssertionError(
            "Dockerfile ends with an unfinished "
            "line continuation"
        )

    return tuple(instructions)


def _dockerignore_patterns(
    dockerignore_text: str,
) -> tuple[str, ...]:
    """Return effective non-comment patterns."""

    return tuple(
        line.strip()
        for line in dockerignore_text.splitlines()
        if (
            line.strip()
            and not line.lstrip().startswith("#")
        )
    )


def _normalise_copy_source(
    source: str,
) -> str:
    """Normalize one Docker COPY source."""

    source = source.rstrip("/")

    if source.startswith("./"):
        source = source[2:]

    return source or "."


class ContainerContractTests(unittest.TestCase):
    """Verify static refresh-container safeguards."""

    def read_required(
        self,
        path: Path,
    ) -> str:
        """Read one required UTF-8 text file."""

        if not path.is_file():
            self.fail(
                "required container file is missing: "
                f"{path.name}"
            )

        try:
            return path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError as error:
            self.fail(
                f"{path.name} is not valid UTF-8: "
                f"{error}"
            )

    def instructions(
        self,
    ) -> tuple[tuple[str, str], ...]:
        """Parse the required Dockerfile."""

        return _logical_instructions(
            self.read_required(
                DOCKERFILE_PATH
            )
        )

    def stage(
        self,
        alias: str,
    ) -> tuple[tuple[str, str], ...]:
        """Return instructions belonging to one stage."""

        instructions = self.instructions()

        matches: list[int] = []

        for index, (
            keyword,
            value,
        ) in enumerate(instructions):
            if keyword != "FROM":
                continue

            parts = value.rsplit(
                None,
                2,
            )

            if (
                len(parts) == 3
                and parts[-2].casefold() == "as"
                and parts[-1].casefold()
                == alias.casefold()
            ):
                matches.append(index)

        self.assertEqual(
            len(matches),
            1,
            (
                "Dockerfile must contain exactly "
                f"one {alias!r} stage"
            ),
        )

        starting_index = matches[0] + 1
        ending_index = len(instructions)

        for index in range(
            starting_index,
            len(instructions),
        ):
            if instructions[index][0] == "FROM":
                ending_index = index
                break

        return instructions[
            starting_index:ending_index
        ]

    def one_json_instruction(
        self,
        instructions: tuple[
            tuple[str, str],
            ...,
        ],
        keyword: str,
    ) -> object:
        """Decode one required JSON-form instruction."""

        values = [
            value
            for found_keyword, value
            in instructions
            if found_keyword == keyword
        ]

        self.assertEqual(
            len(values),
            1,
            (
                "runtime stage must contain exactly "
                f"one {keyword} instruction"
            ),
        )

        try:
            return json.loads(values[0])
        except json.JSONDecodeError as error:
            self.fail(
                f"{keyword} must use JSON form: "
                f"{error}"
            )

    def test_required_container_files_exist(
        self,
    ) -> None:
        self.assertTrue(
            DOCKERFILE_PATH.is_file(),
            "missing required container file: Dockerfile",
        )

        self.assertTrue(
            DOCKERIGNORE_PATH.is_file(),
            (
                "missing required container file: "
                ".dockerignore"
            ),
        )

    def test_build_and_runtime_images_are_digest_pinned(
        self,
    ) -> None:
        from_values = [
            value
            for keyword, value
            in self.instructions()
            if keyword == "FROM"
        ]

        self.assertEqual(
            len(from_values),
            2,
        )

        image_pattern = re.compile(
            (
                r"(?P<image>"
                r"python:3\.14\.\d+"
                r"-slim-bookworm"
                r"@sha256:"
                r"(?P<digest>[0-9a-f]{64})"
                r")\s+AS\s+"
                r"(?P<alias>builder|runtime)"
            ),
            re.IGNORECASE,
        )

        matches = [
            image_pattern.fullmatch(value)
            for value in from_values
        ]

        self.assertTrue(
            all(
                match is not None
                for match in matches
            ),
            (
                "both FROM instructions must use "
                "digest-pinned Python 3.14 slim "
                "Bookworm images"
            ),
        )

        confirmed_matches = [
            match
            for match in matches
            if match is not None
        ]

        self.assertEqual(
            [
                match.group(
                    "alias"
                ).casefold()
                for match in confirmed_matches
            ],
            [
                "builder",
                "runtime",
            ],
        )

        images = [
            match.group("image")
            for match in confirmed_matches
        ]

        self.assertEqual(
            len(set(images)),
            1,
            (
                "builder and runtime must use "
                "the same pinned image"
            ),
        )

        digest = confirmed_matches[
            0
        ].group("digest")

        self.assertGreater(
            len(set(digest)),
            1,
            "image digest must not be a placeholder",
        )

    def test_builder_copies_only_package_inputs(
        self,
    ) -> None:
        builder_stage = self.stage(
            "builder"
        )

        copy_values = [
            value
            for keyword, value
            in builder_stage
            if keyword == "COPY"
        ]

        self.assertTrue(copy_values)

        sources: set[str] = set()

        for value in copy_values:
            tokens = shlex.split(value)

            while (
                tokens
                and tokens[0].startswith("--")
            ):
                tokens.pop(0)

            self.assertGreaterEqual(
                len(tokens),
                2,
                (
                    "COPY must have a source "
                    "and destination"
                ),
            )

            sources.update(
                _normalise_copy_source(source)
                for source in tokens[:-1]
            )

        self.assertEqual(
            sources,
            {
                "pyproject.toml",
                "README.md",
                "LICENSE",
                "kev_dashboard",
            },
        )

    def test_runtime_installs_only_the_built_wheel(
        self,
    ) -> None:
        builder_stage = self.stage(
            "builder"
        )

        runtime_stage = self.stage(
            "runtime"
        )

        builder_runs = " ".join(
            value
            for keyword, value
            in builder_stage
            if keyword == "RUN"
        )

        self.assertRegex(
            builder_runs,
            (
                r"\bpython\s+-m\s+"
                r"pip\s+wheel\b"
            ),
        )

        self.assertIn(
            "--no-cache-dir",
            builder_runs,
        )

        self.assertIn(
            "--no-deps",
            builder_runs,
        )

        self.assertRegex(
            builder_runs,
            (
                r"--wheel-dir(?:=|\s+)"
                r"/wheels\b"
            ),
        )

        wheel_copies = [
            value
            for keyword, value
            in runtime_stage
            if (
                keyword == "COPY"
                and "--from=builder" in value
            )
        ]

        self.assertEqual(
            len(wheel_copies),
            1,
        )

        self.assertIn(
            "/wheels",
            wheel_copies[0],
        )

        self.assertIn(
            "/tmp/wheels",
            wheel_copies[0],
        )

        runtime_runs = " ".join(
            value
            for keyword, value
            in runtime_stage
            if keyword == "RUN"
        )

        self.assertRegex(
            runtime_runs,
            (
                r"\bpython\s+-m\s+"
                r"pip\s+install\b"
            ),
        )

        self.assertIn(
            "--no-cache-dir",
            runtime_runs,
        )

        self.assertIn(
            "--no-deps",
            runtime_runs,
        )

        self.assertIn(
            "/tmp/wheels/*.whl",
            runtime_runs,
        )

        runtime_copy_text = " ".join(
            value
            for keyword, value
            in runtime_stage
            if keyword == "COPY"
        )

        self.assertNotIn(
            "kev_dashboard",
            runtime_copy_text,
            (
                "runtime must receive the wheel, "
                "not the source tree"
            ),
        )

    def test_runtime_uses_fixed_identity_and_layout(
        self,
    ) -> None:
        runtime_stage = self.stage(
            "runtime"
        )

        users = [
            value
            for keyword, value
            in runtime_stage
            if keyword == "USER"
        ]

        self.assertEqual(
            users,
            [CONTAINER_IDENTITY],
        )

        runtime_text = " ".join(
            value
            for _, value in runtime_stage
        )

        for required_text in (
            "groupadd --gid 10001 kevdash",
            "useradd --no-log-init",
            "--uid 10001",
            "--gid 10001",
            "--home-dir /nonexistent",
            "--no-create-home",
            "--shell /usr/sbin/nologin",
        ):
            with self.subTest(
                required_text=required_text
            ):
                self.assertIn(
                    required_text,
                    runtime_text,
                )

        shell_commands = {
            command.strip()
            for keyword, value in runtime_stage
            if keyword == "RUN"
            for command in re.split(
                r"\s*&&\s*",
                value,
            )
        }

        expected_directories = {
            (
                "install -d -o 10001 -g 10001 "
                "-m 0750 /srv/kev-dashboard"
            ),
            (
                "install -d -o 10001 -g 10001 "
                "-m 0700 "
                "/srv/kev-dashboard/candidates"
            ),
            (
                "install -d -o 10001 -g 10001 "
                "-m 0750 "
                "/srv/kev-dashboard/releases"
            ),
        }

        self.assertEqual(
            expected_directories
            - shell_commands,
            set(),
            (
                "secure deployment directory "
                "setup is incomplete"
            ),
        )

        environment_text = " ".join(
            value
            for keyword, value
            in runtime_stage
            if keyword == "ENV"
        )

        for setting in (
            "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONUNBUFFERED=1",
            "TZ=Etc/UTC",
        ):
            with self.subTest(setting=setting):
                self.assertIn(
                    setting,
                    environment_text,
                )

    def test_runtime_is_one_shot_without_ingress(
        self,
    ) -> None:
        runtime_stage = self.stage(
            "runtime"
        )

        workdirs = [
            value
            for keyword, value
            in runtime_stage
            if keyword == "WORKDIR"
        ]

        self.assertEqual(
            workdirs,
            [DEPLOYMENT_ROOT],
        )

        self.assertEqual(
            self.one_json_instruction(
                runtime_stage,
                "ENTRYPOINT",
            ),
            [
                "kev-dashboard-refresh",
            ],
        )

        self.assertEqual(
            self.one_json_instruction(
                runtime_stage,
                "CMD",
            ),
            [
                "--deployment-root",
                DEPLOYMENT_ROOT,
            ],
        )

        keywords = {
            keyword
            for keyword, _ in runtime_stage
        }

        for forbidden_keyword in (
            "EXPOSE",
            "VOLUME",
            "HEALTHCHECK",
        ):
            with self.subTest(
                keyword=forbidden_keyword
            ):
                self.assertNotIn(
                    forbidden_keyword,
                    keywords,
                )

    def test_runtime_has_required_oci_labels(
        self,
    ) -> None:
        runtime_stage = self.stage(
            "runtime"
        )

        labels: dict[str, str] = {}

        for keyword, value in runtime_stage:
            if keyword != "LABEL":
                continue

            for item in shlex.split(value):
                (
                    name,
                    separator,
                    label_value,
                ) = item.partition("=")

                self.assertEqual(
                    separator,
                    "=",
                    (
                        "LABEL entries must use "
                        "key=value form"
                    ),
                )

                labels[name] = label_value

        self.assertEqual(
            labels.get(
                "org.opencontainers.image.title"
            ),
            "CISA KEV Prioritization Dashboard",
        )

        self.assertEqual(
            labels.get(
                "org.opencontainers.image.source"
            ),
            IMAGE_SOURCE,
        )

        self.assertEqual(
            labels.get(
                "org.opencontainers.image.licenses"
            ),
            "MIT",
        )

        self.assertTrue(
            labels.get(
                "org.opencontainers.image.description",
                "",
            ).strip(),
            (
                "OCI image description "
                "must not be empty"
            ),
        )

    def test_dockerignore_is_deny_by_default(
        self,
    ) -> None:
        patterns = _dockerignore_patterns(
            self.read_required(
                DOCKERIGNORE_PATH
            )
        )

        self.assertEqual(
            patterns,
            (
                "**",
                "!Dockerfile",
                "!Dockerfile.web",
                "!pyproject.toml",
                "!README.md",
                "!LICENSE",
                "!kev_dashboard/",
                "!kev_dashboard/*.py",
                "!kev_dashboard/**/*.py",
                "!deploy/",
                "!deploy/nginx.conf",
            ),
        )


if __name__ == "__main__":
    unittest.main()
