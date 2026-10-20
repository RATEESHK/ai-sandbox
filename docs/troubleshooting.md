# Troubleshooting

`aisb doctor <tool>` prints the per-tool checklist; `--fix` applies the local parts. This page is the
long form. The rule throughout: **aisb only touches the project folder.** App caches, user settings and
IDE state are yours — the exact paths are printed so you can act, but nothing outside the project is
ever deleted or modified by aisb.

## Any tool

| Symptom | Cause / fix |
|---|---|
| Hooks never fire | The tool was started in a parent/sub folder, or the folder is not trusted. Open the project **root**, accept the trust dialog, restart the tool. `aisb verify` must show `RESULT: PASS`. |
| `aisb verify` → `root moved` | The folder was moved or renamed. `aisb init` regenerates all absolute paths. |
| `drift … sandbox code!` | `.ai-sandbox/hooks` or `bin` changed after install. `aisb sync --force` (backup kept) — and ask yourself what changed it. |
| `.venv` creation fails (Debian/Ubuntu) | Install `python3-venv` yourself once, or run `aisb runtime python` for a project-local interpreter. |
| Private registry unreachable from the agent | Add `index-url` / `registry=` to `.ai-sandbox/config/pip.conf` / `npmrc` (the agent cannot see your `~/.pip`, `~/.npmrc`). |
| `git push` asks for credentials inside the agent | Credential firewall (HTTPS helpers live in your real gitconfig). Use SSH remotes, or `aisb init --no-credential-firewall`. |
| The agent keeps retrying a denied command | Working as intended; the policy tells it to report `AI-SANDBOX DENY` to you. If the rule is wrong for your project, change `policy.json` (see `docs/policy.md`). |
| Long sessions time out / degrade | Start a fresh chat; keep the context lean with `aisb context <tool>`; disable heavy MCP servers (`aisb doctor <tool> --disable-mcp a,b`). |

## Google Antigravity

```text
aisb doctor antigravity --fix
```

1. **Optimize project context** — `.antigravityignore` is written (`node_modules`, `dist`, `build`, caches,
   secrets …). Officially, Antigravity's exclusion is *Strict Mode* + `.gitignore`, so keep the same folders
   in `.gitignore` too.
2. **Start a fresh chat** — `Ctrl+N` (Windows/Linux) / `Cmd+N` (macOS). Long multi-turn histories make the
   model time out.
3. **Switch models temporarily** — pick a Flash variant in the model selector under the prompt box, send a
   short message to force a reset, switch back to Pro/Opus.
4. **Reset language-server / onboarding state** — Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) →
   `Antigravity: Reset Onboarding`. Also `Developer: Reload Window`, `MCP: Restart All Servers`.
5. **Antivirus (Windows)** — if prompts hang on "Working…", check that the language server was not quarantined:
   `%LOCALAPPDATA%\Programs\Antigravity IDE\resources\app\extensions\antigravity\bin\language_server_windows_x64.exe`.
   Restore it / add an exclusion.
6. **Clear cache and logs** (yours, outside the project): `~/.gemini/antigravity`, `~/.gemini/antigravity-ide`,
   `~/.gemini/antigravity-cli`, `%APPDATA%\Antigravity` / `~/Library/Application Support/Antigravity` /
   `~/.config/Antigravity`. Disable heavy MCP servers first: `aisb doctor antigravity --disable-mcp <names>`.
7. **Terminal policy** — keep *Request Review* or *Proceed in Sandbox*; never *Always Proceed*.

Project files aisb manages for Antigravity: `.agents/rules/*.md` (+ `AGENTS.md`), `.agents/skills/`,
`.agents/agents/`, `.agents/hooks.json` (absolute paths, git-ignored), `.agents/mcp_config.json`.

## Cursor

`aisb doctor cursor` — `.cursorignore` (`aisb context cursor`), new chat when a conversation stalls,
*Resync Index* after big changes, keep the Agent run mode on Auto-review/Allowlist. Hooks: `.cursor/hooks.json`
reloads on save; run from a trusted workspace. On Windows, if hook commands fail, `aisb init --cursor-windows-shell powershell`.

## Claude Code

`claude doctor` (merged settings), `claude --debug` (hook stderr), `/hooks`, `/permissions`. If hooks never
run: `~/.claude/settings.json` may set `disableAllHooks` (verify flags it) or the folder is untrusted.
Kernel sandbox refusing commands: add the registry to `sandbox.network.allowedDomains` in
`.claude/settings.local.json`, or `aisb init --no-os-sandbox`. Linux needs `bubblewrap` + `socat`
(install them yourself).

## Gemini CLI

`/memory show` (GEMINI.md imports), `/hooks panel`, `/permissions` (trust). Untrusted folders ignore
`.gemini/settings.json`, `.gemini/.env`, hooks and commands.

## GitHub Copilot

Copilot CLI inherits the environment of the terminal you start it from — activate first. VS Code: Chat
settings must have *Use hooks*, *Use AGENTS.md*, *Use Agent Skills* on (aisb sets them in
`.vscode/settings.json`); Restricted Mode disables everything. Content exclusion is an org-level feature,
not a project file.

## Windsurf / Devin Desktop

MCP servers are global-only: paste `.ai-sandbox/mcp/devin.mcp_config.json` into the app's MCP settings.
Rules are limited to 12,000 characters per file (split long rules). Both `.devin/` and `.windsurf/` layouts
are written; Devin prefers `.devin/`.

## Standalone build (no Python)

- "no Python 3.8+ found and no standalone build" → re-run `install.sh` / `install.cmd` from the project; it
  downloads `aisb-<os>-<arch>` into `.ai-sandbox/bin/aisb-bin/`.
- Windows SmartScreen / antivirus flags `aisb.exe` → PyInstaller false positives are common; verify the
  `SHA256SUMS` match the GitHub release and add an exclusion, or use the Python path instead.
- Want a venv for the project's own code → `aisb runtime python`.
