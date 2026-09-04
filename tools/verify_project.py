"""Run the repository's complete offline release verification."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib


ROOT = Path(__file__).resolve().parents[1]

FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "kev_sample.json"
)

REQUIRED_PATHS = (
    Path(".gitignore"),
    Path(".github/workflows/tests.yml"),
    Path("LICENSE"),
    Path("Makefile"),
    Path("PUBLISHING_STATUS.md"),
    Path("README.md"),
    Path("RELEASE_WORKFLOW.md"),
    Path("SECURITY.md"),
    Path("docs/METHODOLOGY.md"),
    Path("pyproject.toml"),
    Path("tests/fixtures/kev_sample.json"),
    Path("tools/verify_project.py"),
)

EXPECTED_OUTPUTS = {
    "index.html",
    "data/kev_snapshot.json",
    "data/metadata.json",
    "data/summary.json",
    "data/vulnerabilities.csv",
    "data/vendor_summary.csv",
    "data/year_summary.csv",
    "data/ransomware_summary.csv",
    "data/forensic_triage_summary.csv",
    "data/remediation_window_summary.csv",
    "data/review_signal_summary.csv",
}


def run_command(
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    """Run one local command and capture its output."""

    return subprocess.run(
        arguments,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def record_failure(
    failures: list[str],
    message: str,
) -> None:
    """Record and display one failed check."""

    failures.append(message)
    print(f"FAIL: {message}")


def print_process_output(
    result: subprocess.CompletedProcess[str],
) -> None:
    """Display captured output for a failed process."""

    for output in (
        result.stdout,
        result.stderr,
    ):
        if output.strip():
            print(output.rstrip())


def check_required_files(
    failures: list[str],
) -> None:
    """Confirm that the release-supporting files exist."""

    starting_count = len(failures)

    for relative_path in REQUIRED_PATHS:
        if not (ROOT / relative_path).is_file():
            record_failure(
                failures,
                f"missing required file: {relative_path}",
            )

    if len(failures) == starting_count:
        print("PASS: required release files exist")


def check_project_metadata(
    failures: list[str],
) -> None:
    """Validate pyproject metadata and package version access."""

    starting_count = len(failures)
    pyproject_path = ROOT / "pyproject.toml"

    try:
        with pyproject_path.open("rb") as file:
            configuration = tomllib.load(file)
    except (
        OSError,
        tomllib.TOMLDecodeError,
    ) as error:
        record_failure(
            failures,
            f"could not parse pyproject.toml: {error}",
        )
        return

    project = configuration.get("project")

    if not isinstance(project, dict):
        record_failure(
            failures,
            "pyproject.toml is missing [project]",
        )
        return

    expected_values = {
        "name": "cisa-kev-prioritization-dashboard",
        "requires-python": ">=3.11",
        "license": "MIT",
        "license-files": ["LICENSE"],
        "dependencies": [],
    }

    for field, expected_value in expected_values.items():
        actual_value = project.get(field)

        if actual_value != expected_value:
            record_failure(
                failures,
                (
                    f"project.{field} should be "
                    f"{expected_value!r}, found {actual_value!r}"
                ),
            )

    dynamic_fields = project.get("dynamic", [])

    if (
        not isinstance(dynamic_fields, list)
        or "version" not in dynamic_fields
    ):
        record_failure(
            failures,
            "project.version must be dynamic",
        )

    scripts = project.get("scripts", {})

    if scripts.get("kev-dashboard") != (
        "kev_dashboard.cli:main"
    ):
        record_failure(
            failures,
            "kev-dashboard console script is incorrect",
        )

    try:
        version_attribute = configuration[
            "tool"
        ]["setuptools"]["dynamic"]["version"]["attr"]
    except (
        KeyError,
        TypeError,
    ):
        version_attribute = None

    if version_attribute != "kev_dashboard.__version__":
        record_failure(
            failures,
            "setuptools dynamic version source is incorrect",
        )

    version_result = run_command(
        sys.executable,
        "-c",
        (
            "import kev_dashboard; "
            "print(kev_dashboard.__version__)"
        ),
    )

    if version_result.returncode != 0:
        record_failure(
            failures,
            "the package version could not be imported",
        )
        print_process_output(version_result)
    else:
        package_version = version_result.stdout.strip()

        if re.fullmatch(
            r"\d+\.\d+\.\d+",
            package_version,
        ) is None:
            record_failure(
                failures,
                (
                    "package version is not a three-part "
                    f"version: {package_version!r}"
                ),
            )

    if len(failures) == starting_count:
        print("PASS: project metadata is consistent")


def check_repository_hygiene(
    failures: list[str],
) -> None:
    """Check tracked files and documentation gates."""

    starting_count = len(failures)

    tracked_result = run_command(
        "git",
        "ls-files",
        "-z",
    )

    if tracked_result.returncode != 0:
        record_failure(
            failures,
            "git could not list tracked files",
        )
        print_process_output(tracked_result)
        return

    tracked_files = {
        Path(item)
        for item in tracked_result.stdout.split("\0")
        if item
    }

    forbidden_files: set[Path] = set()

    for path in tracked_files:
        if not path.parts:
            continue

        if path.parts[0] in {
            "build",
            ".venv",
        }:
            forbidden_files.add(path)

        if "__pycache__" in path.parts:
            forbidden_files.add(path)

        if path.suffix in {
            ".pyc",
            ".pyo",
        }:
            forbidden_files.add(path)

        if path.name in {
            ".DS_Store",
            "SOURCE_MAP_PRIVATE.md",
        }:
            forbidden_files.add(path)

    for path in sorted(
        forbidden_files,
        key=lambda item: item.as_posix(),
    ):
        record_failure(
            failures,
            f"generated or private file is tracked: {path}",
        )

    ignore_result = run_command(
        "git",
        "check-ignore",
        "--no-index",
        "--quiet",
        ".github/workflows/tests.yml",
    )

    if ignore_result.returncode == 0:
        record_failure(
            failures,
            "the GitHub Actions workflow is ignored",
        )
    elif ignore_result.returncode != 1:
        record_failure(
            failures,
            "could not determine workflow ignore status",
        )
        print_process_output(ignore_result)

    readme_text = (
        ROOT / "README.md"
    ).read_text(
        encoding="utf-8"
    ).casefold()

    required_readme_terms = (
        "synthetic",
        "make verify",
        "security.md",
        "docs/methodology.md",
    )

    for term in required_readme_terms:
        if term not in readme_text:
            record_failure(
                failures,
                f"README is missing required text: {term}",
            )

    publishing_text = (
        ROOT / "PUBLISHING_STATUS.md"
    ).read_text(
        encoding="utf-8"
    ).casefold()

    if "status: not published" not in publishing_text:
        record_failure(
            failures,
            "publishing status must remain NOT PUBLISHED",
        )

    if len(failures) == starting_count:
        print("PASS: repository hygiene checks passed")


def check_unit_tests(
    failures: list[str],
) -> None:
    """Run the complete unit-test suite."""

    result = run_command(
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v",
    )

    if result.returncode != 0:
        record_failure(
            failures,
            "unit-test suite failed",
        )
        print_process_output(result)
        return

    combined_output = (
        result.stdout
        + result.stderr
    )

    count_match = re.search(
        r"Ran\s+(\d+)\s+tests?",
        combined_output,
    )

    if count_match is None:
        print("PASS: unit-test suite passed")
    else:
        print(
            "PASS: unit-test suite passed "
            f"({count_match.group(1)} tests)"
        )


def check_offline_sample_build(
    failures: list[str],
) -> None:
    """Build and inspect the fixture without using the network."""

    starting_count = len(failures)

    try:
        fixture_document = json.loads(
            FIXTURE.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        record_failure(
            failures,
            f"could not read the fixture: {error}",
        )
        return

    expected_count = fixture_document.get("count")

    if not isinstance(expected_count, int):
        record_failure(
            failures,
            "fixture count is not an integer",
        )
        return

    with TemporaryDirectory(
        prefix="kev-dashboard-verify-"
    ) as temporary_directory:
        output_directory = (
            Path(temporary_directory)
            / "sample"
        )

        result = run_command(
            sys.executable,
            "-m",
            "kev_dashboard",
            "--input",
            str(FIXTURE),
            "--as-of",
            "2026-09-03",
            "--output-dir",
            str(output_directory),
        )

        if result.returncode != 0:
            record_failure(
                failures,
                "offline sample build failed",
            )
            print_process_output(result)
            return

        found_outputs = {
            path.relative_to(
                output_directory
            ).as_posix()
            for path in output_directory.rglob("*")
            if path.is_file()
        }

        missing_outputs = (
            EXPECTED_OUTPUTS
            - found_outputs
        )

        unexpected_outputs = (
            found_outputs
            - EXPECTED_OUTPUTS
        )

        for path in sorted(missing_outputs):
            record_failure(
                failures,
                f"sample output is missing: {path}",
            )

        for path in sorted(unexpected_outputs):
            record_failure(
                failures,
                f"unexpected sample output: {path}",
            )

        if missing_outputs:
            return

        snapshot_path = (
            output_directory
            / "data"
            / "kev_snapshot.json"
        )

        metadata_path = (
            output_directory
            / "data"
            / "metadata.json"
        )

        summary_path = (
            output_directory
            / "data"
            / "summary.json"
        )

        report_path = (
            output_directory
            / "index.html"
        )

        fixture_bytes = FIXTURE.read_bytes()
        snapshot_bytes = snapshot_path.read_bytes()

        if snapshot_bytes != fixture_bytes:
            record_failure(
                failures,
                "saved snapshot differs from the fixture",
            )

        try:
            metadata = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )

            summary = json.loads(
                summary_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            record_failure(
                failures,
                f"generated JSON is invalid: {error}",
            )
            return

        expected_digest = sha256(
            snapshot_bytes
        ).hexdigest()

        if metadata.get(
            "snapshot_sha256"
        ) != expected_digest:
            record_failure(
                failures,
                "snapshot digest is incorrect",
            )

        if metadata.get(
            "record_count"
        ) != expected_count:
            record_failure(
                failures,
                "exported record count is incorrect",
            )

        if metadata.get(
            "as_of"
        ) != "2026-09-03":
            record_failure(
                failures,
                "exported analysis date is incorrect",
            )

        if "vulnerabilities" in summary:
            record_failure(
                failures,
                (
                    "summary.json should not contain "
                    "vulnerability-level rows"
                ),
            )

        report_text = report_path.read_text(
            encoding="utf-8"
        )

        if (
            "<html" not in report_text.casefold()
            or "CISA KEV" not in report_text
        ):
            record_failure(
                failures,
                "generated HTML report is incomplete",
            )

        expected_message = (
            f"Validated {expected_count:,} KEV records."
        )

        if expected_message not in result.stdout:
            record_failure(
                failures,
                "CLI success message is incorrect",
            )

    if len(failures) == starting_count:
        print(
            "PASS: deterministic offline sample build passed"
        )


def main() -> int:
    """Run every release verification check."""

    print("Running offline release verification...\n")

    failures: list[str] = []

    check_required_files(failures)
    check_project_metadata(failures)
    check_repository_hygiene(failures)
    check_unit_tests(failures)
    check_offline_sample_build(failures)

    if failures:
        print(
            f"\nFAILED: {len(failures)} "
            "release check(s) did not pass."
        )
        return 1

    print(
        "\nPASS: all offline release checks passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
