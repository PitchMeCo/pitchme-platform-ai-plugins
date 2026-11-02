# Pitchme Platform

Search talent, run projects, and work in the PitchMe platform from your agent.

The plugin is `plugins/pitchme-platform`. It connects to `https://mcp.platform.pitchme.co/mcp`. Sign in on the PitchMe consent screen as yourself.

## Cursor

Install **Pitchme Platform** from this repository. The manifest asks for **Platform MCP URL** and defaults it to production.

To point one install somewhere else:

- Staging: `https://mcp.platform.pitchme.build/mcp`
- A local tunnel: `https://<name>.tunnel.pitchme.run/mcp`

## Codex

This repository is the marketplace in `.agents/plugins/marketplace.json`. Codex reads `plugins/pitchme-platform/mcp.json`, which points at production.
