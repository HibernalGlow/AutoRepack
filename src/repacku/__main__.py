"""Bootstrap entry: delegate to Typer CLI in repacku.cli"""

from .cli import run


def main():
    return run()


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())