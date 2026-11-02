# Pitchme Platform

Search talent, run projects, and work in the PitchMe platform from your agent.

The plugin is `plugins/pitchme-platform`. It connects to `https://mcp.platform.pitchme.co/mcp`. Sign in on the PitchMe consent screen as yourself.

Current plugin version: **0.0.0**.

Run the **Release** workflow and set `bump` to `patch`, `minor`, `major`, or `x.y.z`. The workflow writes that version into every plugin manifest and both marketplace files, then opens a pull request. A push leaves the version unchanged and does not submit a catalog.

## Cursor

Install **Pitchme Platform** from this repository. The manifest asks for **Platform MCP URL** and defaults it to production.

To point one install somewhere else:

- Staging: `https://mcp.platform.pitchme.build/mcp`
- A local tunnel: `https://<name>.tunnel.pitchme.run/mcp`

## Codex

This repository is the marketplace in `.agents/plugins/marketplace.json`. Codex reads `plugins/pitchme-platform/mcp.json`, which points at production.
