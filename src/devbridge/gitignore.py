"""Keep the folders `devbridge setup` generates (a venv that can be
gigabytes, `__pycache__/`, the PyCharm notes folder) out of git, without
ever touching anything else already in `.gitignore` - same "add only what's
missing" philosophy as vscode_config.py's merge.

Only acts on an actual git checkout (a `.gitignore` already exists, or
`.git/` is right there): a scaffolded plugin sitting loose in a QGIS
profile that was never `git init`-ed gets no surprise file.
"""
from __future__ import annotations

from pathlib import Path

MANAGED_ENTRIES = (".venv/", "__pycache__/", ".pycharm-debug/")


def _wanted_entries(venv_name: str) -> list[str]:
    venv_entry = f"{venv_name.rstrip('/')}/"
    return [venv_entry if e == ".venv/" else e for e in MANAGED_ENTRIES]


def ensure_ignored(project_dir: Path, venv_name: str = ".venv") -> Path | None:
    """Appends whichever managed entries are missing from `.gitignore`.
    Returns the path written to, or None if nothing needed doing (no repo
    here, or every entry was already covered) - so the caller only logs
    when something actually changed."""
    project_dir = Path(project_dir)
    path = project_dir / ".gitignore"
    if not path.exists() and not (project_dir / ".git").is_dir():
        return None

    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing = {ln.strip().rstrip("/") for ln in existing_lines}
    missing = [e for e in _wanted_entries(venv_name) if e.rstrip("/") not in existing]
    if not missing:
        return None

    lines = list(existing_lines)
    if lines and lines[-1].strip():
        lines.append("")
    lines.append("# devbridge")
    lines.extend(missing)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
