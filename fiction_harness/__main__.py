"""Diagnostic-only entrypoint for the archived fiction harness."""

from .archive_quarantine import main


if __name__ == "__main__":
    raise SystemExit(main())
