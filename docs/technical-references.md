# Technical references

Checked on 2026-11-04.

| Document | URL | What we use |
| --- | --- | --- |
| Agent Plugins specification | https://agent-plugins.org/specification | Plugin identity, `plugin.json`, and `mcp.json`. |
| Agent Plugin schema | https://agent-plugins.org/schemas/1.0.0/plugin.schema.json | Root `plugin.json`. |
| Agent Plugins MCP schema | https://agent-plugins.org/schemas/1.0.0/mcp.schema.json | `type` must be `streamable-http` for this remote server. The published schema does not list `extensions` on a server entry. OpenAI's packaging page requires `extensions["com.openai"].auth` there, so the package keeps that block. |
| Build an agent plugin | https://agent-plugins.org/plugin-authors/build-an-agent-plugin | Folder layout for skills and `mcp.json`. |
| OpenAI plugin packaging | https://developers.openai.com/plugins/build/plugins | ZIP contents, `extensions.com.openai`, and OAuth dynamic client registration. |
| OpenAI MCP server development | https://developers.openai.com/plugins/build/mcp-server | Remote Streamable HTTP server. The server already exists in `platform-mcp-server`. |
| OpenAI authentication | https://developers.openai.com/plugins/build/auth | Public client, dynamic registration, no client secret in the package. |
| OpenAI plugin guidelines | https://developers.openai.com/plugins/plugin-guidelines | Tool annotations. Justification text is no longer required. A generic executor is rejected. |
| Upload and submit | https://developers.openai.com/plugins/deploy/submission | A person uploads the ZIP. Domain verification and the tool scan happen in the portal. |
| MCP protocol | https://modelcontextprotocol.io/specification/2025-11-25 | Tools, annotations, and Streamable HTTP. |
| Agent Skills | https://agentskills.io/specification | `SKILL.md` frontmatter: `name` and `description`. |
| Cursor plugins | https://cursor.com/docs/plugins | The Cursor card stays in `.cursor-plugin` and `mcp.cursor.json`. It is not in the OpenAI ZIP. |
| MCP Inspector | https://modelcontextprotocol.io/docs/tools/inspector | Manual check of the staging server. |

When two documents disagree, the MCP protocol comes first, then the current OpenAI requirements, then the Agent Plugins specification.
