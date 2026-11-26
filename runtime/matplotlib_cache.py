"""Select a shared persistent Matplotlib cache before importing Matplotlib."""
from __future__ import annotations

import os
from pathlib import Path
import sys


def configure_matplotlib_cache() -> str:
    """Preserve explicit overrides, including isolated test cache directories."""
    configured = os.environ.get("MPLCONFIGDIR")
    if configured:
        return configured

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        directory = base / "PhaseEQ" / "Cache" / "matplotlib"
    elif sys.platform == "darwin":
        directory = Path.home() / "Library" / "Caches" / "PhaseEQ" / "matplotlib"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        directory = base / "phaseeq" / "matplotlib"

    # Matplotlib owns directory creation, writability checks and cache updates.
    os.environ["MPLCONFIGDIR"] = str(directory)
    return str(directory)
