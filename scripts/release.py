#!/usr/bin/env python3
"""Version check, bump, and tag for the plugin repository.

    python3 scripts/release.py check
    python3 scripts/release.py bump patch|minor|major|x.y.z
    python3 scripts/release.py tag

check fails when the plugin manifests, marketplace version and ref fields, and
the README line disagree. bump writes the next version and opens a pull
request. tag pushes the git tag for a commit bump created.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
GITHUB_MERGE = re.compile(r"^Merge pull request #(\d+) from \S+$")
SQUASH = re.compile(r"^(?P<title>.+?) \(#(?P<num>\d+)\)$")
RELEASE_SUBJECT = re.compile(r"^Release (\d+\.\d+\.\d+)(?: \(#\d+\))?$")
MERGE_RELEASE = re.compile(r"^Merge pull request #\d+ from \S+/release/(\d+\.\d+\.\d+)$")
SKIP_SUBJECTS = {"Initial commit"}
RELEASE_TRAILER = "PitchMe-Release-Version: "
GIT_AUTHOR = [
    "-c",
    "user.name=github-actions[bot]",
    "-c",
    "user.email=41898282+github-actions[bot]@users.noreply.github.com",
]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True)


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def manifests() -> list[Path]:
    found = sorted(ROOT.joinpath("plugins").glob("*/plugin.json"))
    found += sorted(ROOT.joinpath("plugins").glob("*/.cursor-plugin/plugin.json"))
    found += sorted(ROOT.joinpath("plugins").glob("*/.codex-plugin/plugin.json"))
    if not found:
        raise SystemExit("no plugin manifests under plugins/")
    return found


def marketplaces() -> list[Path]:
    return [
        ROOT / ".agents/plugins/marketplace.json",
        ROOT / ".cursor-plugin/marketplace.json",
    ]


def read_version() -> str:
    found: list[tuple[str, str]] = []
    for path in manifests():
        data = json.loads(path.read_text(encoding="utf-8"))
        if "version" not in data:
            raise SystemExit(f"{path} has no version")
        found.append((str(path.relative_to(ROOT)), str(data["version"])))
    for path in marketplaces():
        data = json.loads(path.read_text(encoding="utf-8"))
        plugins = data.get("plugins") or []
        if not plugins:
            raise SystemExit(f"{path.relative_to(ROOT)} has no plugins")
        for plugin in plugins:
            name = str(plugin.get("name", "?"))
            if "version" not in plugin or "ref" not in plugin:
                raise SystemExit(f"{path.relative_to(ROOT)} plugin {name} needs version and ref")
            label = str(path.relative_to(ROOT))
            found.append((f"{label}:{name}:version", str(plugin["version"])))
            found.append((f"{label}:{name}:ref", str(plugin["ref"])))
    values = {value for _, value in found}
    if len(values) != 1:
        detail = "\n".join(f"{label} = {value}" for label, value in found)
        raise SystemExit(f"version fields disagree\n{detail}")
    version = values.pop()
    mark = f"Current plugin version: **{version}**."
    if mark not in (ROOT / "README.md").read_text(encoding="utf-8"):
        raise SystemExit(f"README.md is missing {mark}")
    return version


def title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("*", "Co-authored-by:")):
            continue
        return stripped
    return fallback


def bullet(subject: str, body: str, pull_url: str) -> str | None:
    subject = subject.strip()
    if not subject or subject in SKIP_SUBJECTS:
        return None
    merge = GITHUB_MERGE.match(subject)
    if merge is not None:
        title = title_from_body(body, subject)
        if RELEASE_SUBJECT.match(title):
            return None
        return f"* {title} in {pull_url}/{merge.group(1)}"
    squash = SQUASH.match(subject)
    if squash is not None:
        title = squash.group("title")
        if RELEASE_SUBJECT.match(title) or title in SKIP_SUBJECTS:
            return None
        return f"* {title} in {pull_url}/{squash.group('num')}"
    if RELEASE_SUBJECT.match(subject):
        return None
    return f"* {subject}"


def render_notes(text: str, pull_url: str) -> list[str]:
    seen: set[str] = set()
    notes: list[str] = []
    for chunk in text.split("---COMMIT---\n"):
        if not chunk.strip():
            continue
        lines = chunk.splitlines()
        line = bullet(lines[0] if lines else "", "\n".join(lines[1:]), pull_url.rstrip("/"))
        if line and line not in seen:
            seen.add(line)
            notes.append(line)
    return notes


def release_version(message: str) -> str | None:
    for line in message.splitlines():
        if line.startswith(RELEASE_TRAILER):
            version = line[len(RELEASE_TRAILER) :].strip()
            if not SEMVER.match(version):
                raise SystemExit(f"bad PitchMe-Release-Version {version}")
            return version
    subject = message.splitlines()[0].strip() if message.strip() else ""
    match = RELEASE_SUBJECT.match(subject) or MERGE_RELEASE.match(subject)
    if match:
        return match.group(1)
    return None


def self_test() -> None:
    sample = textwrap.dedent("""\
        ---COMMIT---
        Merge pull request #1 from PitchMeCo/feature/TECH-239-add-plugins
        Add the Pitchme Platform plugin.
        ---COMMIT---
        Release 1.0.0
        PitchMe-Release-Version: 1.0.0
        ---COMMIT---
        Add the Pitchme Platform plugin. (#1)
        ---COMMIT---
        Initial commit
        """)
    expected = [
        "* Add the Pitchme Platform plugin. in https://github.com/PitchMeCo/pitchme-platform-ai-plugins/pull/1",
    ]
    pull_url = "https://github.com/PitchMeCo/pitchme-platform-ai-plugins/pull"
    actual = render_notes(sample, pull_url)
    if actual != expected:
        raise SystemExit(f"changelog self-test failed: {actual}")
    samples = {
        "Release 1.2.3\nPitchMe-Release-Version: 1.2.3\n": "1.2.3",
        "Release 1.2.3 (#4)": "1.2.3",
        "Merge pull request #4 from PitchMeCo/release/1.2.3": "1.2.3",
        "Add the plugin.": None,
    }
    for message, want in samples.items():
        if release_version(message) != want:
            raise SystemExit(f"release parser failed for {message!r}")


def next_version(current: str, bump: str) -> str:
    if SEMVER.match(bump):
        return bump
    major, minor, patch = (int(part) for part in current.split("."))
    if bump == "patch":
        patch += 1
    elif bump == "minor":
        minor += 1
        patch = 0
    elif bump == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise SystemExit("bump must be patch, minor, major, or x.y.z")
    return f"{major}.{minor}.{patch}"


def replace_version(path: Path, old: str, new: str, refs: bool) -> None:
    text = path.read_text(encoding="utf-8")
    old_version = f'"version": "{old}"'
    if old_version not in text:
        raise SystemExit(f"no {old_version} in {path.relative_to(ROOT)}")
    text = text.replace(old_version, f'"version": "{new}"')
    if refs:
        old_ref = f'"ref": "{old}"'
        if old_ref not in text:
            raise SystemExit(f"no {old_ref} in {path.relative_to(ROOT)}")
        text = text.replace(old_ref, f'"ref": "{new}"')
    path.write_text(text, encoding="utf-8")


def log_range(previous: str) -> str:
    if git("tag", "--list", previous).strip():
        return f"{previous}..HEAD"
    if previous == "0.0.0":
        return "HEAD"
    mark = f"Current plugin version: **{previous}**."
    introduced = git("log", "-1", "--format=%H", "-S", mark, "--", "README.md").strip()
    if introduced:
        return f"{introduced}..HEAD"
    return "HEAD"


def write_changelog(version: str, notes: list[str]) -> None:
    path = ROOT / "CHANGELOG.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n"
    rest = existing[len("# Changelog") :].lstrip("\n") if existing.startswith("# Changelog") else existing
    body = "\n".join(notes) if notes else "No commits since the previous release."
    date = datetime.date.today().isoformat()
    text = f"# Changelog\n\n## {version} — {date}\n\n{body}\n"
    if rest.strip():
        text += "\n" + (rest if rest.endswith("\n") else rest + "\n")
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def bump_files(current: str, bump: str) -> str:
    new = next_version(current, bump)
    if new == current:
        raise SystemExit(f"version is already {current}")
    repo = os.environ.get("GITHUB_REPOSITORY", "PitchMeCo/pitchme-platform-ai-plugins")
    notes = render_notes(
        git("log", "--first-parent", "--format=---COMMIT---%n%s%n%b", log_range(current)),
        f"https://github.com/{repo}/pull",
    )
    if git("tag", "--list", current).strip():
        notes.extend(["", f"Full changelog: https://github.com/{repo}/compare/{current}...{new}"])
    for path in manifests():
        replace_version(path, current, new, refs=False)
    for path in marketplaces():
        replace_version(path, current, new, refs=True)
    readme = ROOT / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(
            f"Current plugin version: **{current}**.",
            f"Current plugin version: **{new}**.",
            1,
        ),
        encoding="utf-8",
    )
    write_changelog(new, notes)
    if read_version() != new:
        raise SystemExit("bump left the version fields disagreeing")
    return new


def open_pull_request(version: str) -> None:
    branch = f"release/{version}"
    run(["git", "checkout", "-B", branch])
    run(["git", "add", "plugins", ".cursor-plugin", ".agents", "README.md", "CHANGELOG.md"])
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode == 0:
        raise SystemExit("version bump did not change any release files")
    run([
        "git",
        *GIT_AUTHOR,
        "commit",
        "-m",
        f"Release {version}",
        "-m",
        f"{RELEASE_TRAILER}{version}",
    ])
    fetched = subprocess.run(["git", "fetch", "origin", f"refs/heads/{branch}:refs/remotes/origin/{branch}"])
    if fetched.returncode == 0:
        run([
            "git",
            "push",
            f"--force-with-lease=refs/heads/{branch}:refs/remotes/origin/{branch}",
            "origin",
            f"HEAD:refs/heads/{branch}",
        ])
    else:
        run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"])
    repo = os.environ.get("GITHUB_REPOSITORY", "PitchMeCo/pitchme-platform-ai-plugins")
    owner = repo.split("/", 1)[0]
    listed = subprocess.check_output(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--base",
            "main",
            "--head",
            f"{owner}:{branch}",
            "--state",
            "open",
            "--json",
            "number",
        ],
        text=True,
    )
    if json.loads(listed):
        print(f"pull request for {branch} is already open")
        return
    body = "\n".join([
        f"Automated release preparation for {version}.",
        "",
        f"Bumps every plugin manifest and both marketplace files to `{version}`.",
        "",
        f"{RELEASE_TRAILER}{version}",
        "",
        "After this pull request merges, the Release workflow tags that main commit when the message carries PitchMe-Release-Version. The workflow does not submit a catalog.",
    ])
    run([
        "gh",
        "pr",
        "create",
        "--repo",
        repo,
        "--base",
        "main",
        "--head",
        branch,
        "--title",
        f"Release {version}",
        "--body",
        body,
    ])


def declared_release() -> str | None:
    declared = release_version(git("log", "-1", "--format=%B"))
    if declared is not None:
        return declared
    parents = git("rev-list", "--parents", "-1", "HEAD").split()
    if len(parents) > 2:
        return release_version(git("log", "-1", "--format=%B", parents[2]))
    return None


def command_check() -> None:
    self_test()
    print(f"ok: version {read_version()}")


def command_bump(bump: str) -> None:
    self_test()
    current = read_version()
    version = bump_files(current, bump.strip())
    print(f"bumped {current} -> {version}")
    open_pull_request(version)


def command_tag() -> None:
    self_test()
    current = read_version()
    declared = declared_release()
    if not declared:
        print("this commit was not produced by the Release workflow; no tag")
        return
    if declared != current:
        raise SystemExit(f"commit version {declared} does not match plugin version {current}")
    remote = subprocess.run(
        ["git", "ls-remote", "origin", f"refs/tags/{declared}"],
        check=True,
        text=True,
        capture_output=True,
    )
    if remote.stdout.strip():
        print(f"tag {declared} already exists")
        return
    run(["git", *GIT_AUTHOR, "tag", "-a", declared, "-m", f"v{declared}"])
    run(["git", "push", "origin", f"refs/tags/{declared}"])
    print(f"pushed tag {declared}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "bump", "tag"))
    parser.add_argument("bump", nargs="?")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "check":
        command_check()
    elif args.command == "bump":
        bump = args.bump or os.environ.get("BUMP", "")
        if not bump:
            raise SystemExit("bump is required: patch, minor, major, or x.y.z")
        command_bump(bump)
    else:
        command_tag()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error) from error
