#!/usr/bin/env python3
"""Fail when plugin versions disagree.

Every plugins/*/plugin.json, plugins/*/.cursor-plugin/plugin.json, and
plugins/*/.codex-plugin/plugin.json carries the same version. Both
marketplace files repeat that version as version and ref on each plugin.
README states it as "Current plugin version: **x.y.z**."
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README_MARK = "Current plugin version: **{version}**."


def versions_in(path: Path) -> list[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    found: list[tuple[str, str]] = []
    if isinstance(data, dict) and "version" in data and "plugins" not in data:
        found.append((f"{path}:version", str(data["version"])))
    for plugin in data.get("plugins", []) if isinstance(data, dict) else []:
        name = plugin.get("name", "?")
        if "version" in plugin:
            found.append((f"{path}:{name}:version", str(plugin["version"])))
        if "ref" in plugin:
            found.append((f"{path}:{name}:ref", str(plugin["ref"])))
    return found


def collect() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    plugin_jsons = sorted(ROOT.joinpath("plugins").glob("*/plugin.json"))
    plugin_jsons += sorted(ROOT.joinpath("plugins").glob("*/.cursor-plugin/plugin.json"))
    plugin_jsons += sorted(ROOT.joinpath("plugins").glob("*/.codex-plugin/plugin.json"))
    if not plugin_jsons:
        raise SystemExit("no plugin manifests under plugins/")
    for path in plugin_jsons:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "version" not in data:
            raise SystemExit(f"{path} has no version")
        found.append((str(path.relative_to(ROOT)), str(data["version"])))
    for relative in (
        ".agents/plugins/marketplace.json",
        ".cursor-plugin/marketplace.json",
    ):
        path = ROOT / relative
        entries = versions_in(path)
        if not any(label.endswith(":version") for label, _ in entries):
            raise SystemExit(f"{relative} has no plugin version")
        if not any(label.endswith(":ref") for label, _ in entries):
            raise SystemExit(f"{relative} has no plugin ref")
        found.extend(entries)
    return found


def main() -> int:
    found = collect()
    values = {value for _, value in found}
    if len(values) != 1:
        for label, value in found:
            print(f"{label} = {value}", file=sys.stderr)
        raise SystemExit("version fields disagree")
    version = values.pop()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    mark = README_MARK.format(version=version)
    if mark not in readme:
        raise SystemExit(f"README.md is missing {mark}")
    print(f"ok: version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
