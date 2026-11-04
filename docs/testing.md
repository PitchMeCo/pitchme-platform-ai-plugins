# Testing

## Package check

From the repository root:

```sh
python3 scripts/release.py check
python3 scripts/release.py package
```

`check` confirms one version across the manifests and marketplace files, then validates the plugin. `package` writes `dist/pitchme-platform-<version>.zip`.

The ZIP root is `plugin.json`. The archive contains `plugin.json`, `mcp.json`, `.codex-plugin/plugin.json`, `skills/`, and `assets/`. It does not contain the Cursor files, `.env`, `.app.json`, or `hooks/`.

GitHub Actions runs the same two commands on every push and every pull request. The ZIP is the artifact on that workflow run.

## MCP Inspector

The server is already deployed.

1. Open MCP Inspector.
2. Connect to staging: `https://mcp.platform.pitchme.build/mcp`.
3. Sign in on the PitchMe consent screen.
4. List the tools. `reveal_contacts` has `destructiveHint` true. The other named tools have `destructiveHint` false. `readOnlyHint` matches each tool. `openWorldHint` is true.
5. Call one read tool, such as `who_is_signed_in`.
6. Do not call `reveal_contacts` on real data. That call spends a Sonar credit.

Production is `https://mcp.platform.pitchme.co/mcp`. The domain-check route answers only on that host, and only when `OPENAI_APPS_CHALLENGE` is set.

## ChatGPT

Download `pitchme-platform-<version>.zip` from the GitHub Actions run for `feature/chatgpt-plugin`. In ChatGPT, use developer mode and a personal marketplace entry to install that ZIP. Ask who is signed in, then run each skill once. Do not publish the directory listing from this check.
