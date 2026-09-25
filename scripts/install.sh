#!/usr/bin/env bash
# One-shot bootstrap for Linux/macOS: clones nothing (run from inside the
# repo), just installs the CLI and runs setup against $1 (default: cwd).
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"
LANG_CODE="${DEVBRIDGE_LANG:-en}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

python3 -m venv .bootstrap-venv
source .bootstrap-venv/bin/activate
pip install -q --upgrade pip
pip install -q -e .

devbridge setup --project-dir "$PROJECT_DIR" --lang "$LANG_CODE"
