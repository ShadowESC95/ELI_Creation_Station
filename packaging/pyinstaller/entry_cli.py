# Adapted from ELI_Legal: packaging/pyinstaller/entry_cli.py @ 3b05ccd88f. Edited for ELI Creation Station; scripts/sync_reused.py --check says when the original changes.
"""Frozen entry point with a console: the command line and the server.
With no arguments it opens the desktop application, like ``python -m eli_creation``."""

import sys

from eli_creation.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["gui"]))
