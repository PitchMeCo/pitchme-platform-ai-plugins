#!/usr/bin/env python3
"""Changelog bullets from first-parent history.

Merge commits contribute the pull request title. Other commits contribute
their subject. Release commits and the initial commit are omitted.
"""

from __future__ import annotations

import argparse
import re
import sys

GITHUB_MERGE = re.compile(r"^Merge pull request #(\d+) from \S+$")
SQUASH = re.compile(r"^(?P<title>.+?) \(#(?P<num>\d+)\)$")
RELEASE = re.compile(r"^Release \d+\.\d+\.\d+$")
SKIP_SUBJECTS = {"Initial commit"}


def title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("*", "Co-authored-by:")):
            continue
        return stripped
    return fallback


def bullet(subject: str, body: str, pull_request_url: str) -> str | None:
    subject = subject.strip()
    if not subject or subject in SKIP_SUBJECTS:
        return None
    merge = GITHUB_MERGE.match(subject)
    if merge is not None:
        title = title_from_body(body, subject)
        if RELEASE.match(title):
            return None
        return f"* {title} in {pull_request_url}/{merge.group(1)}"
    squash = SQUASH.match(subject)
    if squash is not None:
        title = squash.group("title")
        if RELEASE.match(title) or title in SKIP_SUBJECTS:
            return None
        return f"* {title} in {pull_request_url}/{squash.group('num')}"
    if RELEASE.match(subject):
        return None
    return f"* {subject}"


def render(text: str, pull_request_url: str) -> list[str]:
    seen: set[str] = set()
    notes: list[str] = []
    for chunk in text.split("---COMMIT---\n"):
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        subject = lines[0] if lines else ""
        body = "\n".join(lines[1:])
        line = bullet(subject, body, pull_request_url.rstrip("/"))
        if line and line not in seen:
            seen.add(line)
            notes.append(line)
    return notes


def self_test() -> None:
    sample = """---COMMIT---
Merge pull request #1 from PitchMeCo/feature/TECH-239-add-plugins
Add the Pitchme Platform plugin.

The catalog manifests now live in this public repository.
---COMMIT---
Release 1.0.0
PitchMe-Release-Version: 1.0.0
---COMMIT---
Add the Pitchme Platform plugin. (#1)
---COMMIT---
Initial commit
"""
    expected = [
        "* Add the Pitchme Platform plugin. in https://github.com/PitchMeCo/pitchme-platform-ai-plugins/pull/1",
    ]
    actual = render(sample, "https://github.com/PitchMeCo/pitchme-platform-ai-plugins/pull")
    if actual != expected:
        raise SystemExit(f"changelog notes self-test failed:\n{actual}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pull-request-url", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.pull_request_url:
        print("pull request url is required", file=sys.stderr)
        return 1
    notes = render(sys.stdin.read(), args.pull_request_url)
    sys.stdout.write(("\n".join(notes) + "\n") if notes else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
