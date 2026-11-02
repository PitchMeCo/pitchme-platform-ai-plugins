#!/usr/bin/env bash
# Bump the plugin version, push release/<version>, and open a GitHub pull request.
# CircleCI runs this when the prepare_release pipeline parameter is true.
# Usage: ./scripts/prepare-release.sh patch|minor|major|<x.y.z>

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OWNER="${GITHUB_OWNER:-PitchMeCo}"
REPO="${GITHUB_REPO:-pitchme-platform-ai-plugins}"
BASE_BRANCH="${RELEASE_BASE_BRANCH:-main}"
API="https://api.github.com/repos/${OWNER}/${REPO}"
PR_BODY_FILE="$(mktemp)"
trap 'rm -f "$PR_BODY_FILE"' EXIT

die() {
  printf 'prepare-release: %s\n' "$*" >&2
  exit 1
}

[[ "${CIRCLECI:-}" == "true" ]] || die "run this from the CircleCI prepare_release pipeline"
[[ $# -eq 1 ]] || die "usage: $0 patch|minor|major|<x.y.z>"
BUMP="$1"
case "$BUMP" in
  patch|minor|major) ;;
  *.*.*)
    [[ "$BUMP" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must be x.y.z"
    ;;
  *) die "bump must be patch, minor, major, or x.y.z" ;;
esac
[[ -n "${GITHUB_REPO_TOKEN:-}" ]] || die "GITHUB_REPO_TOKEN is required (CircleCI context pitchme-platform-ai-plugins)"

git fetch origin "$BASE_BRANCH" --tags
git checkout -B "$BASE_BRANCH" "origin/${BASE_BRANCH}"
if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
  git fetch --unshallow origin || true
fi

PREVIOUS="$(
  python3 -c 'import json; print(json.load(open("plugins/pitchme-platform/plugin.json", encoding="utf-8"))["version"])'
)"
if git rev-parse -q --verify "refs/tags/${PREVIOUS}^{}" >/dev/null 2>&1 \
  || git rev-parse -q --verify "refs/tags/${PREVIOUS}" >/dev/null 2>&1; then
  log_range="${PREVIOUS}..HEAD"
elif [[ "$PREVIOUS" == "0.0.0" ]]; then
  # 0.0.0 is the seed written by this repository, not a published release.
  log_range="HEAD"
elif introduced="$(
  git log -1 --format=%H -S "Current plugin version: **${PREVIOUS}**." -- README.md
)" && [[ -n "$introduced" ]]; then
  log_range="${introduced}..HEAD"
else
  log_range="HEAD"
fi

./scripts/bump-version.sh "$BUMP"
NOTES="$(
  git log --first-parent --format='---COMMIT---%n%s%n%b' "$log_range" \
    | python3 scripts/render_changelog_notes.py \
      --pull-request-url "https://github.com/${OWNER}/${REPO}/pull"
)"
if git rev-parse -q --verify "refs/tags/${PREVIOUS}" >/dev/null 2>&1; then
  NEW="$(
    python3 -c 'import json; print(json.load(open("plugins/pitchme-platform/plugin.json", encoding="utf-8"))["version"])'
  )"
  NOTES="${NOTES}"$'\n\n'"Full changelog: https://github.com/${OWNER}/${REPO}/compare/${PREVIOUS}...${NEW}"
fi
NOTES="$NOTES" python3 - <<'PY'
import os
from pathlib import Path

path = Path("CHANGELOG.md")
lines = path.read_text(encoding="utf-8").splitlines()
notes = [line for line in os.environ["NOTES"].splitlines()]
while notes and notes[-1] == "":
    notes.pop()
if not notes:
    notes = ["No commits since the previous release."]
for index, line in enumerate(lines):
    if line == "-":
        lines[index : index + 1] = notes
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        break
else:
    raise SystemExit("changelog stub '-' was not found")
PY

./scripts/check.sh

VERSION="$(
  python3 -c 'import json; print(json.load(open("plugins/pitchme-platform/plugin.json"))["version"])'
)"
BRANCH="release/${VERSION}"

git checkout -B "$BRANCH"
git add plugins .cursor-plugin .agents README.md CHANGELOG.md
git diff --cached --quiet && die "version bump did not change any release files"

GIT_AUTHOR_NAME="PitchMe CircleCI" \
GIT_AUTHOR_EMAIL="pitchme-circleci@users.noreply.github.com" \
GIT_COMMITTER_NAME="PitchMe CircleCI" \
GIT_COMMITTER_EMAIL="pitchme-circleci@users.noreply.github.com" \
  git commit -m "Release ${VERSION}" -m "PitchMe-Release-Version: ${VERSION}"

PUSH_URL="https://x-access-token:${GITHUB_REPO_TOKEN}@github.com/${OWNER}/${REPO}.git"
if git fetch origin "refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}"; then
  git push --force-with-lease="refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}" \
    "$PUSH_URL" "HEAD:refs/heads/${BRANCH}"
else
  git push "$PUSH_URL" "HEAD:refs/heads/${BRANCH}"
fi

AUTH_HEADER="Authorization: Bearer ${GITHUB_REPO_TOKEN}"
EXISTING="$(
  curl -fsS \
    -H "$AUTH_HEADER" \
    -H "Accept: application/vnd.github+json" \
    --get \
    --data-urlencode "head=${OWNER}:${BRANCH}" \
    --data-urlencode "state=open" \
    "${API}/pulls"
)"
COUNT="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' <<<"$EXISTING")"
if [[ "$COUNT" != "0" ]]; then
  echo "Pull request for ${BRANCH} already exists; branch updated."
  exit 0
fi

BODY="$(
  printf '%s\n' \
    "Automated release preparation for ${VERSION}." \
    "" \
    "Bumps every plugin manifest and both marketplace files to \`${VERSION}\`." \
    "" \
    "After this pull request merges, CircleCI tags that main commit \`${VERSION}\` when the commit message carries PitchMe-Release-Version. The pipeline does not submit a catalog."
)"
python3 - "$VERSION" "$BRANCH" "$BASE_BRANCH" "$BODY" <<'PY' >"$PR_BODY_FILE"
import json
import sys
print(json.dumps({
    "title": f"Release {sys.argv[1]}",
    "head": sys.argv[2],
    "base": sys.argv[3],
    "body": sys.argv[4],
}))
PY

curl -fsS \
  -H "$AUTH_HEADER" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -X POST \
  "${API}/pulls" \
  --data-binary @"$PR_BODY_FILE"
echo
echo "Opened pull request for ${BRANCH} into ${BASE_BRANCH}."
