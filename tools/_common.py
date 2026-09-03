from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = PROJECT_ROOT / ".tmp"
TOOLS_DIR = PROJECT_ROOT / "tools"
WORKFLOWS_DIR = PROJECT_ROOT / "workflows"


def project_path(*parts: str) -> Path:
    """Return an absolute path inside the project root."""
    return PROJECT_ROOT.joinpath(*parts)


def ensure_tmp_dir() -> Path:
    """Create and return the disposable workspace directory."""
    TMP_DIR.mkdir(exist_ok=True)
    return TMP_DIR


def load_env_file(path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs from .env without overwriting existing env vars."""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

