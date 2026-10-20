# MCP servers, project-local

`aisb` keeps one list of [Model Context Protocol](https://modelcontextprotocol.io) servers in
`.ai-sandbox/mcp/servers.json` and writes it into every tool's own file on `aisb sync`. Servers start inside
the sandbox environment, so `npx`-based servers download into the project cache and see the isolated
credentials, and every MCP call goes through the guard (`mcp__*` / `mcp_*` matchers) and the audit log.

## Add a server

```bash
# local (stdio) servers
aisb add mcp filesystem --command "npx -y @modelcontextprotocol/server-filesystem ."
aisb add mcp playwright --command "npx -y @playwright/mcp@latest" --description "browser automation"
aisb add mcp sqlite --command "uvx" --args "mcp-server-sqlite,--db-path,./data/app.db"
aisb add mcp my-tool --command "./.venv/bin/python" --args "-m,my_mcp_server" --env "LOG_LEVEL=debug"

# remote (HTTP / SSE) servers
aisb add mcp github --url https://api.githubcopilot.com/mcp/ --header "Authorization: Bearer \${GITHUB_TOKEN}"
aisb add mcp linear --url https://mcp.linear.app/mcp
aisb add mcp legacy --url https://example.com/sse --transport sse

aisb list components          # mcp  filesystem(stdio), github(http) ...
aisb remove mcp legacy
```

Rules of thumb:

- The command is checked by the guard before it is saved (`curl … | sh` is rejected). `npx` servers should
  carry `-y` so they start unattended.
- Secrets: use `${ENV_VAR}` references, never literal tokens. `aisb` warns if a value looks like a secret;
  `aisb pack` replaces such values with `${VAR}` placeholders.
- Disable without deleting: set `"enabled": false` in `servers.json` (or `aisb doctor <tool> --disable-mcp a,b`),
  then `aisb sync`.
- Servers imported from bundles/plugins arrive **disabled** (`--enable-mcp` to override). Enable the ones you want.

## Where they land

| Tool | File | Shape |
|---|---|---|
| Claude Code | `.mcp.json` | `mcpServers`: `{type: stdio, command, args, env}` / `{type: http\|sse, url, headers}`; `.claude/settings.json` gets `enabledMcpjsonServers: [names]` so exactly these are pre-approved (`enableAllProjectMcpServers` stays false) |
| Cursor | `.cursor/mcp.json` | `mcpServers`: `{command, args, env}` / `{url, headers}` |
| VS Code (Copilot agent) | `.vscode/mcp.json` | `servers`: `{type: stdio, …}` / `{type: http, url, headers}` |
| Copilot CLI / coding agent | `.github/mcp.json` | `mcpServers`: `{type: local, command, args, env, tools: ["*"]}` / `{type: http, url, headers, tools}` |
| Gemini CLI | `.gemini/settings.json` | `mcpServers`: `{command, args, env, cwd}` / `{httpUrl}` or `{url}` (SSE) |
| Antigravity | `.agents/mcp_config.json` | `mcpServers`: `{command, args, env, cwd}` / `{serverUrl, headers}` |
| Roo Code · Kiro · Junie | `.roo/mcp.json` · `.kiro/settings/mcp.json` · `.junie/mcp/mcp.json` | `mcpServers` |
| Zed | `.zed/settings.json` | `context_servers` (stdio only) |
| Windsurf / Devin Desktop | **global only** → sidecar `.ai-sandbox/mcp/devin.mcp_config.json` to paste | `mcpServers` with `serverUrl` |
| Codex CLI | TOML → sidecar `.ai-sandbox/mcp/codex.mcp.toml` to merge into `.codex/config.toml` | `[mcp_servers.<name>]` |
| Cline | global only (`cline_mcp_settings.json`) | — |

## Public MCP servers worth knowing

Add any of these with `aisb add mcp` — they stay confined to the project. Check each project's README for
auth requirements; remote servers usually use OAuth or a `${TOKEN}` header.

| Server | Install | Notes |
|---|---|---|
| Filesystem (reference) | `npx -y @modelcontextprotocol/server-filesystem .` | scope it to `.` — the sandbox blocks paths outside anyway |
| Playwright | `npx -y @playwright/mcp@latest` | browsers land in `.ai-sandbox/cache/ms-playwright` |
| Chrome DevTools | `npx -y chrome-devtools-mcp@latest` | performance / accessibility audits |
| GitHub (remote) | `--url https://api.githubcopilot.com/mcp/` | token via `${GITHUB_TOKEN}` header |
| Linear · Notion · Slack · Asana · Atlassian … | remote `https://mcp.<vendor>.com/mcp` | included (disabled) by `aisb apply productivity@knowledge-work-plugins` |
| Context7 (docs) | `npx -y @upstash/context7-mcp` | library documentation lookup |
| SQLite / Postgres | `uvx mcp-server-sqlite --db-path ./x.db` · `npx -y @modelcontextprotocol/server-postgres <url>` | keep connection strings as `${VAR}` |

## Writing a custom MCP server inside the sandbox

1. Create it in the project (e.g. `tools/my_server/`), using the project `.venv` or `node_modules`.
2. `aisb add mcp my-server --command "./.venv/bin/python" --args "-m,my_server"` (Windows users on the same
   project: prefer `--command npx`/`uvx` style commands or a small launcher script so the path is portable).
3. `aisb sync` writes it to every tool; the guard logs each call (`aisb log --follow`).
4. Ship it: `aisb pack` includes `mcp/servers.json` with placeholders; teammates `aisb apply` and `--enable-mcp`.

## Controlling MCP calls

- `policy.json` → `"mcp_tools": "ask"` makes every MCP tool call prompt (default: allow + log).
- Claude Code: deny or allow specific MCP tools with permission rules (`mcp__server__tool`) in `.claude/settings.json`.
- Gemini: `mcpServers.<name>.includeTools` / `excludeTools`. Copilot: the `tools` list per server.
