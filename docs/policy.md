# The policy: what is enforced and how to change it

The guard reads `.ai-sandbox/policy.json` (portable, commit it) merged with `.ai-sandbox/policy.local.json`
(this machine: the sandbox env var names and extra home prefixes). Lists concatenate. Edit `policy.json`,
run `aisb verify` (the guard self-test and protocol tests run against your policy) — no sync needed, hooks
read it on every call.

## Top-level keys

| Key | Default | Meaning |
|---|---|---|
| `on_internal_error` | `deny` | if the guard crashes, the tool call is denied (fail closed) |
| `on_unparsable_input` | `deny` | non-JSON stdin → deny |
| `ask_fallback` | `deny` | what "ask" becomes for tools without an ask channel (Gemini, Windsurf, generic) |
| `unknown_outside_read` | `ask` | reading a file outside the workspace that is not a known system location |
| `mcp_tools` | `allow` | `ask` to prompt on every MCP tool call (always logged) |
| `log_prompts` | `false` | store prompt text in the audit log (length only by default) |
| `protected_env_vars` | sandbox vars | names the AI may not set/unset/override in commands |
| `protected_paths` | sandbox files | `{"path": ".claude/settings.json", "mode": "deny|ask"}` — writes denied/asked |
| `system_read_prefixes_posix` / `_nt` | `/usr`, `/etc`, `C:\Windows` … | read-only locations outside the workspace that are fine to read |
| `home_prefixes` | `[]` + machine | extra directories treated as "home" (denied) |
| `forbidden_executables` | 80 names | executables denied outright (`sudo`, `brew`, `apt`, `winget`, `setx`, `crontab`, `nvm` …) |
| `deny_patterns` / `ask_patterns` | 38 / 17 rules | regexes over the whole command, see below |

## Pattern rules

```json
{"id": "cargo-install", "pattern": "\\bcargo\\s+install\\b", "unless": "\\s--root[= ]+\\.\\.?[/\\\\]",
 "unless_env_inside_root": ["CARGO_HOME"],
 "reason": "cargo install writes to ~/.cargo/bin unless --root ./<dir> or CARGO_HOME inside the workspace."}
```

- `pattern` is a case-insensitive regex applied to the full command (all segments).
- `unless` exempts when it matches.
- `unless_env_inside_root` exempts when **all** listed env vars point inside the workspace in the guard's
  own environment — i.e. the sandbox env is active in that process. This is how `cargo install`, `go install`,
  `uv tool install`, `pipx`, `git config --global`, `aws`, `kubectl`, `gh` … become safe automatically.
- `reason` is what the model sees.

Adding a project rule:

```json
"deny_patterns": [
  {"id": "no-prod-deploy", "pattern": "\\b(kubectl|helm)\\b.*\\b(prod|production)\\b", "reason": "Never touch production from an agent."},
  ...
]
```

Adding an ask rule for something you want to approve each time:

```json
"ask_patterns": [{"id": "db-migrate", "pattern": "\\b(alembic|prisma|knex)\\s+migrate\\b", "reason": "Migrations need a human."}]
```

## Built-in intents the regexes do not need to cover

The engine already understands: `cd`/`pushd` targets, write-all commands (`rm`, `mkdir`, `tee`, `chmod`,
`Remove-Item`, `tar`, `sed -i` …), write-last commands (`cp`, `mv`, `rsync`, `copy`, `robocopy` …), output
flags (`-o`, `--output`, `--target`, `--prefix`, `--cache-dir`, `-DestinationPath` …), `-C`/`--chdir`,
docker `-v`/`--mount` sources, `git clone/checkout/restore/rm/mv/clean/worktree`, `python -m venv <dir>`,
redirections (`> file`, `2>&1`, `&>`), env assignments (`HOME=… cmd`), wrappers (`env`, `nohup`, `xargs`,
`timeout` …), inline shells (`bash -c`, `sh -c`, `cmd /c`, `powershell -Command`) and inline interpreters
(`python -c`, `node -e`) which are scanned for outside paths.

## Self-protection

Writes to `.ai-sandbox/**` (except `cache/`; `home/` asks), `.claude/settings*.json`, `.cursor/hooks.json`,
`.gemini/settings.json`, `.gemini/.env`, `.github/hooks/**`, `.vscode/settings.json`, `.vscode/tasks.json`
are denied for the AI; `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `.gitignore` ask. You edit them yourself,
or through `aisb add/sync`, which runs with your permissions, not the agent's.

## Verifying a change

```bash
aisb verify                      # guard self-test (176 cases) + protocol tests use the live policy
./.ai-sandbox/bin/aisb guard --tool claude --event pre <<< '{"tool_name":"Bash","tool_input":{"command":"helm upgrade prod"}}'
aisb log --denied -n 20
```
