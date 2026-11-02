#!/usr/bin/env bash
# Push the git tag for a release the prepare_release pipeline created.
# A push that is not that release commit exits 0 and does not tag.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OWNER="${GITHUB_OWNER:-PitchMeCo}"
REPO="${GITHUB_REPO:-pitchme-platform-ai-plugins}"
BASE_BRANCH="${RELEASE_BASE_BRANCH:-main}"

die() {
  printf 'publish-release: %s\n' "$*" >&2
  exit 1
}

release_version_from_message() {
  local message="$1" line version subject
  while IFS= read -r line; do
    case "$line" in
      "PitchMe-Release-Version: "*)
        version="${line#PitchMe-Release-Version: }"
        [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
        printf '%s\n' "$version"
        return 0
        ;;
    esac
  done <<<"$message"
  subject="${message%%$'\n'*}"
  case "$subject" in
    "Release "[0-9]*)
      version="${subject#Release }"
      version="${version%% (*}"
      ;;
    "Merge pull request #"*"/release/"*)
      version="${subject##*/release/}"
      ;;
    *)
      return 1
      ;;
  esac
  [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  printf '%s\n' "$version"
}

[[ "${CIRCLECI:-}" == "true" ]] || die "run this from CircleCI on ${BASE_BRANCH}"
[[ "${CIRCLE_BRANCH:-}" == "$BASE_BRANCH" ]] || die "only tag ${BASE_BRANCH}"

if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
  git fetch --deepen=50 origin
fi

PLUGIN_VERSION="$(
  python3 -c 'import json; print(json.load(open("plugins/pitchme-platform/plugin.json", encoding="utf-8"))["version"])'
)"
[[ "$PLUGIN_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "plugin version must be x.y.z"

DECLARED=""
if ! DECLARED="$(release_version_from_message "$(git log -1 --format=%B)")"; then
  DECLARED=""
  if git rev-parse --verify --quiet HEAD^2 >/dev/null; then
    DECLARED="$(release_version_from_message "$(git log -1 --format=%B HEAD^2)")" || DECLARED=""
  fi
fi

if [[ -z "$DECLARED" ]]; then
  echo "This commit was not produced by the prepare_release pipeline; no tag pushed."
  exit 0
fi
[[ "$DECLARED" == "$PLUGIN_VERSION" ]] || die "pipeline version ${DECLARED} does not match plugin version ${PLUGIN_VERSION}"

existing="$(git ls-remote origin "refs/tags/${DECLARED}^{}" | awk 'NR == 1 { print $1 }')"
if [[ -z "$existing" ]]; then
  existing="$(git ls-remote origin "refs/tags/${DECLARED}" | awk 'NR == 1 { print $1 }')"
fi
if [[ -n "$existing" ]]; then
  echo "Tag ${DECLARED} already exists; leaving it in place."
  exit 0
fi

[[ -n "${GITHUB_REPO_TOKEN:-}" ]] || die "GITHUB_REPO_TOKEN is required to push tag ${DECLARED} (CircleCI context pitchme-platform-ai-plugins)"

HEAD="$(git rev-parse HEAD)"
GIT_COMMITTER_NAME="PitchMe CircleCI" \
GIT_COMMITTER_EMAIL="pitchme-circleci@users.noreply.github.com" \
  git tag -a "$DECLARED" -m "v${DECLARED}" "$HEAD"

PUSH_URL="https://x-access-token:${GITHUB_REPO_TOKEN}@github.com/${OWNER}/${REPO}.git"
git push "$PUSH_URL" "refs/tags/${DECLARED}"
echo "Pushed tag ${DECLARED} at ${HEAD}."
