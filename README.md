# Pitchme Platform

Search talent, run projects, and work in the PitchMe platform from your agent.

The plugin is `plugins/pitchme-platform`. It connects to `https://mcp.platform.pitchme.co/mcp`. Sign in on the PitchMe consent screen as yourself. The agent stays in the account and group you choose, and only with the permissions that group already has.

How to install it and what the agent can do are in the PitchMe docs: [Use the MCP server](https://pitchme.co/docs/sdk/use-the-mcp-server/).

- [Add it in Cursor](https://pitchme.co/docs/sdk/use-the-mcp-server/#add-it-in-cursor)
- [Add it in Claude](https://pitchme.co/docs/sdk/use-the-mcp-server/#add-it-in-claude)
- [Add it in ChatGPT](https://pitchme.co/docs/sdk/use-the-mcp-server/#add-it-in-chatgpt)
- [Add it in Codex](https://pitchme.co/docs/sdk/use-the-mcp-server/#add-it-in-codex)
- [What the agent can do](https://pitchme.co/docs/sdk/use-the-mcp-server/#what-the-agent-can-do)

Current plugin version: **1.0.0**.

Run the **Release** workflow and set `bump` to `patch`, `minor`, `major`, or `x.y.z`. The workflow writes that version into every plugin manifest and both marketplace files, then opens a pull request. A push leaves the version unchanged and does not submit a catalog.

## Cursor

Install **Pitchme Platform** from this repository. The manifest asks for **Platform MCP URL** and defaults it to production. The steps are in [Add it in Cursor](https://pitchme.co/docs/sdk/use-the-mcp-server/#add-it-in-cursor).

## Codex

This repository is the marketplace in `.agents/plugins/marketplace.json`. Codex reads `plugins/pitchme-platform/mcp.json`, which points at production. The steps are in [Add it in Codex](https://pitchme.co/docs/sdk/use-the-mcp-server/#add-it-in-codex).

## ChatGPT

The same card is the OpenAI plugin package. `plugins/pitchme-platform/mcp.json` uses Streamable HTTP and OAuth dynamic client registration. There is no client secret in the package.

Three skills ship with the card:

- `get-started` shows who is signed in.
- `find-candidates-for-a-role` goes from a brief to an estimate, a search, and a shortlist.
- `reveal-contacts-safely` checks the Sonar balance and waits for an explicit yes before each reveal.

Every push and every pull request builds `dist/pitchme-platform-<version>.zip` and uploads it as a GitHub Actions artifact. Download that ZIP from the workflow run. The workflow does not submit it to OpenAI. A person uploads it in the Plugins portal and presses Publish.

`python3 scripts/release.py package` builds the same ZIP locally. The checks are in [docs/testing.md](docs/testing.md). The references are in [docs/technical-references.md](docs/technical-references.md).
