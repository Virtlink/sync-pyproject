#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#    "tomlkit>=0.14.0",
#    "typer>=0.25.1",
#    "pytest>=8.0.0",
# ]
# ///
"""Run the syncpyproject test suite with pytest.
Any command-line arguments are forwarded to pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def main(argv: list[str]) -> int:
    # Make the main script importable as `syncpyproject` regardless of the
    # current working directory the script is invoked from.
    sys.path.insert(0, str(HERE))

    args = argv or ["-s", str(HERE / "tests")]
    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
