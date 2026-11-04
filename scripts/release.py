#!/usr/bin/env python3
"""Version check, package, bump, and tag for the plugin repository.

    python3 scripts/release.py check
    python3 scripts/release.py package
    python3 scripts/release.py bump patch|minor|major|x.y.z
    python3 scripts/release.py tag

check fails when the plugin manifests, marketplace version and ref fields, and
the README line disagree, or when the OpenAI package is invalid. package writes
dist/pitchme-platform-<version>.zip. bump writes the next version and opens a
pull request. tag pushes the git tag for a commit bump created and attaches
the ZIP to the GitHub Release.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SECRET = re.compile(
    r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:sk|rk)-[A-Za-z0-9]{20,}"
)
PRODUCTION_MCP_URL = "https://mcp.platform.pitchme.co/mcp"
ZIP_PATHS = ("plugin.json", "mcp.json", ".codex-plugin/plugin.json")
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
    package_self_test()


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


def fail(message: str) -> None:
    raise SystemExit(message)


def plugin_dir() -> Path:
    return ROOT / "plugins" / "pitchme-platform"


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"{path} is not valid JSON: {error}")
    if not isinstance(data, dict):
        fail(f"{path} must be a JSON object")
    return data


def walk_strings(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(walk_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(walk_strings(item))
    return found


def skill_frontmatter(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"{path} is missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"{path} frontmatter does not close")
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        fields[key.strip()] = raw.strip()
    if "name" not in fields or "description" not in fields:
        fail(f"{path} frontmatter needs name and description")
    if not fields["description"]:
        fail(f"{path} description is empty")
    if fields["name"] != path.parent.name:
        fail(f"{path} skill name does not match {path.parent.name}")


def validate_plugin(plugin: Path) -> None:
    if not plugin.is_dir():
        fail(f"missing plugin directory {plugin}")
    for path in plugin.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(plugin)
        if path.name in {".env", ".app.json"} or "hooks" in relative.parts:
            fail(f"{relative.as_posix()} is not allowed in the plugin")
        if "assets" in relative.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if SECRET.search(text):
            fail(f"{relative.as_posix()} contains a secret-looking string")
        if path.suffix == ".json":
            load_json(path)
    manifest = load_json(plugin / "plugin.json")
    mcp = load_json(plugin / "mcp.json")
    codex = load_json(plugin / ".codex-plugin" / "plugin.json")
    if "apps" in manifest:
        fail("apps is not allowed in plugin.json")
    versions = [str(manifest.get("version", "")), str(codex.get("version", ""))]
    if len(set(versions)) != 1 or not SEMVER.match(versions[0]):
        fail(f"plugin versions disagree: {versions[0]} {versions[1]}")
    servers = mcp.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        fail("mcp.json needs mcpServers")
    for name, server in servers.items():
        if not isinstance(server, dict) or server.get("type") != "streamable-http":
            fail(f"mcp.json server {name} type is not streamable-http")
        if server.get("url") != PRODUCTION_MCP_URL:
            fail(f"mcp.json server {name} url is not production")
        auth = (
            server.get("extensions", {})
            .get("com.openai", {})
            .get("auth", {})
        )
        client = auth.get("client", {}) if isinstance(auth, dict) else {}
        if auth.get("type") != "oauth" or client.get("mode") != "dcr":
            fail("mcp.json must declare oauth dynamic client registration")
        if "clientSecret" in json.dumps(server) or "client_secret" in json.dumps(server):
            fail("mcp.json must not contain a client secret")
    documents = {
        "plugin.json": manifest,
        "mcp.json": mcp,
        ".codex-plugin/plugin.json": codex,
    }
    for label, data in documents.items():
        for ref in walk_strings(data):
            if not ref.startswith("./"):
                continue
            if not (plugin / ref[2:]).is_file():
                fail(f"{label} references missing file {ref}")
    skills = sorted(plugin.glob("skills/*/SKILL.md"))
    if not skills:
        fail("plugin has no skills")
    for skill in skills:
        skill_frontmatter(skill)
    onboarding = (
        manifest.get("extensions", {}).get("com.openai", {}).get("onboardingSkill")
    )
    if onboarding != "./skills/get-started/SKILL.md":
        fail("onboardingSkill must be ./skills/get-started/SKILL.md")


def zip_members(plugin: Path) -> list[Path]:
    members = [plugin / relative for relative in ZIP_PATHS]
    for folder in ("skills", "assets"):
        members.extend(sorted(path for path in (plugin / folder).rglob("*") if path.is_file()))
    return members


def write_package(plugin: Path, dest: Path) -> Path:
    validate_plugin(plugin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in zip_members(plugin):
            archive.write(path, path.relative_to(plugin).as_posix())
    with zipfile.ZipFile(dest) as archive:
        names = set(archive.namelist())
    expected = {path.relative_to(plugin).as_posix() for path in zip_members(plugin)}
    if names != expected or "plugin.json" not in names:
        fail(f"zip contents do not match the OpenAI package: {sorted(names)}")
    if any(name.startswith(".cursor-plugin/") or name == "mcp.cursor.json" for name in names):
        fail("zip contains the Cursor card")
    return dest


def sample_plugin(root: Path) -> Path:
    plugin = root / "pitchme-platform"
    (plugin / "skills" / "get-started").mkdir(parents=True)
    (plugin / "assets").mkdir()
    (plugin / ".codex-plugin").mkdir()
    (plugin / "assets" / "logo.png").write_text("png", encoding="utf-8")
    (plugin / "assets" / "logo.svg").write_text("<svg/>", encoding="utf-8")
    (plugin / "plugin.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "mcpServers": "./mcp.json",
                "extensions": {
                    "com.openai": {
                        "onboardingSkill": "./skills/get-started/SKILL.md",
                        "interface": {
                            "logo": "./assets/logo.png",
                            "composerIcon": "./assets/logo.png",
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (plugin / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "Pitchme Platform": {
                        "type": "streamable-http",
                        "url": PRODUCTION_MCP_URL,
                        "extensions": {"com.openai": {"auth": {"type": "oauth", "client": {"mode": "dcr"}}}},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (plugin / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "mcpServers": "./mcp.json",
                "interface": {"logo": "./assets/logo.svg"},
            }
        ),
        encoding="utf-8",
    )
    (plugin / "skills" / "get-started" / "SKILL.md").write_text(
        "---\nname: get-started\ndescription: Start.\n---\n\nStart.\n",
        encoding="utf-8",
    )
    return plugin


def expect_invalid(plugin: Path, needle: str) -> None:
    try:
        validate_plugin(plugin)
    except SystemExit as error:
        if needle not in str(error):
            fail(f"expected {needle!r} in {error}")
        return
    fail(f"expected failure containing {needle!r}")


def package_self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plugin = sample_plugin(root)
        dest = root / "out.zip"
        write_package(plugin, dest)
        with zipfile.ZipFile(dest) as archive:
            if "plugin.json" not in archive.namelist():
                fail("sample zip is missing plugin.json at the archive root")
            if any("/" not in name and name.startswith("plugins") for name in archive.namelist()):
                fail("sample zip wrapped the plugin in a parent directory")
        cases = [
            ("plugin.json", "{", "not valid JSON"),
            ("mcp.json", json.dumps({"mcpServers": {"Pitchme Platform": {"type": "http", "url": PRODUCTION_MCP_URL}}}), "streamable-http"),
            ("skills/get-started/SKILL.md", "---\nname: get-started\n---\n\nStart.\n", "name and description"),
            ("skills/get-started/SKILL.md", "---\nname: get-started\ndescription: Start.\n---\n\nsk-" + ("a" * 20) + "\n", "secret-looking"),
        ]
        for relative, text, needle in cases:
            trial = root / "trial"
            if trial.exists():
                shutil.rmtree(trial)
            shutil.copytree(plugin, trial)
            (trial / relative).write_text(text, encoding="utf-8")
            expect_invalid(trial, needle)
        trial = root / "missing-logo"
        shutil.copytree(plugin, trial)
        data = json.loads((trial / "plugin.json").read_text(encoding="utf-8"))
        data["extensions"]["com.openai"]["interface"]["logo"] = "./assets/missing.png"
        (trial / "plugin.json").write_text(json.dumps(data), encoding="utf-8")
        expect_invalid(trial, "missing file")
        for relative, needle in (
            (".env", ".env is not allowed"),
            (".app.json", ".app.json is not allowed"),
            ("hooks/hooks.json", "hooks/hooks.json is not allowed"),
        ):
            trial = root / relative.replace("/", "-")
            shutil.copytree(plugin, trial)
            target = trial / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x", encoding="utf-8")
            expect_invalid(trial, needle)
        trial = root / "version"
        shutil.copytree(plugin, trial)
        codex = json.loads((trial / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        codex["version"] = "9.9.9"
        (trial / ".codex-plugin" / "plugin.json").write_text(json.dumps(codex), encoding="utf-8")
        expect_invalid(trial, "versions disagree")


def publish_release(version: str) -> None:
    zip_path = ROOT / "dist" / f"pitchme-platform-{version}.zip"
    if not zip_path.is_file():
        write_package(plugin_dir(), zip_path)
    viewed = subprocess.run(
        ["gh", "release", "view", version],
        capture_output=True,
        text=True,
    )
    if viewed.returncode == 0:
        print(f"release {version} already exists")
        return
    run(
        [
            "gh",
            "release",
            "create",
            version,
            str(zip_path),
            "--title",
            f"v{version}",
            "--notes",
            f"Plugin package {version}.",
        ]
    )
    print(f"published release {version}")


def command_check() -> None:
    self_test()
    version = read_version()
    validate_plugin(plugin_dir())
    print(f"ok: version {version}")


def command_package() -> None:
    self_test()
    version = read_version()
    dest = write_package(plugin_dir(), ROOT / "dist" / f"pitchme-platform-{version}.zip")
    print(f"wrote {dest}")


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
    else:
        run(["git", *GIT_AUTHOR, "tag", "-a", declared, "-m", f"v{declared}"])
        run(["git", "push", "origin", f"refs/tags/{declared}"])
        print(f"pushed tag {declared}")
    publish_release(declared)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "package", "bump", "tag"))
    parser.add_argument("bump", nargs="?")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "check":
        command_check()
    elif args.command == "package":
        command_package()
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
