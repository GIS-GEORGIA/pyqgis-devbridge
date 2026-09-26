#!/usr/bin/env bash
# One-shot bootstrap for Linux/macOS: installs the devbridge CLI, links the
# DevBridge plugin into your QGIS profile (and enables it), then prepares a
# plugin from your QGIS profile for debugging.
#
#   scripts/install.sh                          # pick the plugin interactively
#   scripts/install.sh --plugin selection_tools
#   scripts/install.sh --project-dir ~/src/my_plugin
#   scripts/install.sh --lang ka --force
#   scripts/install.sh --skip-setup             # only CLI + DevBridge plugin
#
# Options: --plugin NAME  --project-dir DIR  --profile NAME  --lang en|ka
#          --copy  --force  --skip-bridge  --skip-setup
set -euo pipefail

PLUGIN="" PROJECT_DIR="" PROFILE="" LANG_CODE="${DEVBRIDGE_LANG:-en}"
COPY=0 FORCE=0 SKIP_BRIDGE=0 SKIP_SETUP=0

while [ $# -gt 0 ]; do
    case "$1" in
        --plugin)       PLUGIN="$2"; shift 2 ;;
        --project-dir)  PROJECT_DIR="$2"; shift 2 ;;
        --profile)      PROFILE="$2"; shift 2 ;;
        --lang)         LANG_CODE="$2"; shift 2 ;;
        --copy)         COPY=1; shift ;;
        --force)        FORCE=1; shift ;;
        --skip-bridge)  SKIP_BRIDGE=1; shift ;;
        --skip-setup)   SKIP_SETUP=1; shift ;;
        -h|--help)      sed -n '2,13p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
    esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

command -v python3 >/dev/null || { echo "python3 not found on PATH" >&2; exit 1; }
[ -d .bootstrap-venv ] || python3 -m venv .bootstrap-venv
.bootstrap-venv/bin/python -m pip install -q --upgrade pip
.bootstrap-venv/bin/python -m pip install -q -e .
DEVBRIDGE=.bootstrap-venv/bin/devbridge

if [ "$SKIP_BRIDGE" -eq 0 ]; then
    args=(--lang "$LANG_CODE" install-plugin)
    [ -n "$PROFILE" ] && args+=(--profile "$PROFILE")
    [ "$COPY" -eq 1 ] && args+=(--copy)
    [ "$FORCE" -eq 1 ] && args+=(--force)
    "$DEVBRIDGE" "${args[@]}" || echo "Warning: DevBridge plugin install reported a problem (see above)." >&2
fi

if [ "$SKIP_SETUP" -eq 0 ]; then
    args=(--lang "$LANG_CODE" setup)
    if [ -n "$PROJECT_DIR" ]; then args+=(--project-dir "$PROJECT_DIR")
    elif [ -n "$PLUGIN" ]; then args+=(--plugin "$PLUGIN"); fi
    [ -n "$PROFILE" ] && args+=(--profile "$PROFILE")
    "$DEVBRIDGE" "${args[@]}"
fi

echo
echo "Done. Restart QGIS, then: Plugins > DevBridge > Start debug bridge,"
echo "and in VS Code: Run and Debug > 'PyQGIS: Attach to running QGIS'."
