#!/usr/bin/env bash
# Version agreement, changelog renderer, and shellcheck.
# Usage: ./scripts/check.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/check_versions.py
python3 scripts/render_changelog_notes.py --self-test

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "shellcheck is required" >&2
  exit 1
fi
shellcheck scripts/bump-version.sh scripts/prepare-release.sh scripts/publish-release.sh scripts/check.sh
echo "ok: shellcheck"
