"""Entry point for running the package with python -m kev_dashboard."""

from . import __version__


def main() -> None:
    """Display the current build status."""

    print(f"CISA KEV Dashboard build v{__version__}")
    print("Stage 2 complete: data models and validation are working.")


if __name__ == "__main__":
    main()