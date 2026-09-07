"""Helpers for protecting locally stored authentication data."""

import os
from pathlib import Path


def _is_posix() -> bool:
    return os.name == "posix"


def ensure_private_directory(path: Path) -> None:
    """Create a directory and restrict it to the current user on POSIX."""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if _is_posix():
        path.chmod(0o700)


def restrict_private_file(path: Path) -> None:
    """Restrict an existing file to the current user on POSIX."""
    if _is_posix():
        path.chmod(0o600)
