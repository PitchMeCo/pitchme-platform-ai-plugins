#!/usr/bin/env bash
# Bump the shared plugin semver in every manifest, both marketplace files,
# README, and CHANGELOG.
# Usage:
#   ./scripts/bump-version.sh patch
#   ./scripts/bump-version.sh minor
#   ./scripts/bump-version.sh major
#   ./scripts/bump-version.sh 1.2.3

set -euo pipefail

usage() {
  echo "Usage: $0 patch|minor|major|<x.y.z>" >&2
  exit 2
}

[[ $# -eq 1 ]] || usage

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
SOURCE_JSON="plugins/pitchme-platform/plugin.json"
README="README.md"
CHANGELOG="CHANGELOG.md"

is_semver() {
  [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

read_current() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$SOURCE_JSON"
}

bump_part() {
  local kind="$1" major minor patch
  IFS=. read -r major minor patch <<<"$2"
  case "$kind" in
    major)
      major=$((major + 1))
      minor=0
      patch=0
      ;;
    minor)
      minor=$((minor + 1))
      patch=0
      ;;
    patch)
      patch=$((patch + 1))
      ;;
    *)
      usage
      ;;
  esac
  printf '%s.%s.%s\n' "$major" "$minor" "$patch"
}

CURRENT="$(read_current)"
is_semver "$CURRENT" || {
  echo "Could not parse current version from $SOURCE_JSON (got ${CURRENT:-empty})" >&2
  exit 1
}
KIND="$1"
if is_semver "$KIND"; then
  NEW="$KIND"
else
  NEW="$(bump_part "$KIND" "$CURRENT")"
fi

if [[ "$NEW" == "$CURRENT" ]]; then
  echo "Version is already $CURRENT" >&2
  exit 1
fi

./scripts/check_versions.py

replace_in_file() {
  local file="$1" search="$2" replace="$3"
  local tmp found=0 line
  tmp="$(mktemp)"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == *"$search"* ]]; then
      found=1
      line="${line//"$search"/$replace}"
    fi
    printf '%s\n' "$line"
  done <"$file" >"$tmp"
  if [[ "$found" -eq 0 ]]; then
    rm -f "$tmp"
    echo "No replacement for '${search}' in $file" >&2
    exit 1
  fi
  mv "$tmp" "$file"
}

while IFS= read -r file; do
  replace_in_file "$file" "\"version\": \"$CURRENT\"" "\"version\": \"$NEW\""
done < <(find plugins -name plugin.json -type f | sort)

for file in .agents/plugins/marketplace.json .cursor-plugin/marketplace.json; do
  replace_in_file "$file" "\"version\": \"$CURRENT\"" "\"version\": \"$NEW\""
  replace_in_file "$file" "\"ref\": \"$CURRENT\"" "\"ref\": \"$NEW\""
done

replace_in_file "$README" "Current plugin version: **${CURRENT}**." "Current plugin version: **${NEW}**."

DATE="$(date +%F)"
changelog_tmp="$(mktemp)"
{
  printf '%s\n' "# Changelog" "" "## ${NEW} — ${DATE}" "" "-" ""
  if [[ -f "$CHANGELOG" ]]; then
    skip_heading=1
    skip_blank=1
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ "$skip_heading" -eq 1 && "$line" == "# Changelog" ]]; then
        skip_heading=0
        continue
      fi
      skip_heading=0
      if [[ "$skip_blank" -eq 1 && -z "$line" ]]; then
        skip_blank=0
        continue
      fi
      skip_blank=0
      printf '%s\n' "$line"
    done <"$CHANGELOG"
  fi
} >"$changelog_tmp"
mv "$changelog_tmp" "$CHANGELOG"

./scripts/check_versions.py
echo "Bumped ${CURRENT} -> ${NEW}"
