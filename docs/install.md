# Installing

Everything below is project-local. `aisb` never writes outside the folder you run it in, never needs
administrator rights, and never installs a package manager, Python, Node or a shell for you.

## A. You have Python 3.8+ (most machines)

```bash
# macOS / Linux / WSL / Git Bash
git clone https://github.com/RATEESHK/ai-sandbox ~/ai-sandbox     # once
cd ~/code/my-project
sh ~/ai-sandbox/install.sh                 # = aisb init

# Windows (cmd)
git clone https://github.com/RATEESHK/ai-sandbox %USERPROFILE%\ai-sandbox
cd C:\code\my-project
%USERPROFILE%\ai-sandbox\install.cmd

# Windows (PowerShell) - Bypass is process-scoped, nothing on the machine changes
powershell -NoProfile -ExecutionPolicy Bypass -File $HOME\ai-sandbox\install.ps1
```

No clone? Download `install.sh` / `install.cmd` from the [latest release](https://github.com/RATEESHK/ai-sandbox/releases/latest)
and run it from your project: it fetches `aisb.pyz` (single file, verified against `SHA256SUMS`) and runs it.
Prefer to look before you run: `curl -fsSLO https://github.com/RATEESHK/ai-sandbox/releases/latest/download/install.sh && less install.sh && sh install.sh`.

With `uv`: `uvx --from git+https://github.com/RATEESHK/ai-sandbox aisb init` (runs from uv's cache).

Afterwards the project is self-sufficient: `./.ai-sandbox/bin/aisb` (or `aisb.cmd` / `aisb.ps1`) runs the
copy stored in `.ai-sandbox/bin/aisb.pyz`. `source ./.ai-sandbox/bin/activate.sh` makes `aisb` a shell function.

## B. No Python at all

The same bootstraps detect the situation and download the **standalone build** (`aisb-<os>-<arch>.tar.gz`
or `.zip`, built by GitHub Actions with PyInstaller) for Windows x64/arm64, macOS x64/arm64, Linux x64/arm64:

- Windows: `install.cmd` needs only `cmd.exe`, a downloader (`curl.exe` ships with Windows 10 1803+; falls back
  to `certutil`, `bitsadmin`, then PowerShell if present), `certutil` for SHA-256 and `tar.exe` (1803+) to unpack.
- macOS / Linux: `install.sh` needs POSIX `sh`, `curl` or `wget`, `tar`, and `sha256sum`/`shasum`/`openssl`.

The build is copied into `<project>/.ai-sandbox/bin/aisb-bin/` (git-ignored, ~20 MB) and all hooks point
at it (`aisb guard …`). Hook latency is ~100 ms. Delete the folder to remove it.

Offline / air-gapped: download the archive on another machine, unpack it next to your projects and run its
`install.cmd` / `install.sh` **from the project folder** — no network needed.

Want Python in that project anyway (to run the project's own code)? `aisb runtime python [--version 3.12]`
downloads a pinned [python-build-standalone](https://github.com/astral-sh/python-build-standalone) CPython
into `.ai-sandbox/runtime/python/` (SHA-256 verified against the lock file shipped with aisb), creates `.venv`
from it and re-points the hooks at the venv.

## C. What `init` does

1. Detects OS, WSL, Git Bash, admin rights, available tools (git, uv, bubblewrap/socat, …).
2. Creates `.venv` with `python -m venv` (falls back to `uv venv`, then `venv --without-pip` with a warning).
   Never `pip --user`, never a system package.
3. Writes the SSOT (`.ai-sandbox/`), the isolated config/home/cache tree, `sandbox.env` and the launchers.
4. Generates every tool's files (see `aisb targets`), merging into files you already have.
5. Runs `aisb verify` and prints the next steps.

Flags: `--tools claude,gemini,cursor,copilot,vscode,windsurf,antigravity` (default) or `all`; `--profile <name>`;
`--no-venv`; `--python <path>`; `--no-credential-firewall`; `--isolate-tool-homes`; `--no-os-sandbox`;
`--cursor-windows-shell cmd|powershell`; `--force`; `--dry-run`; `--skip-verify`.

## D. Per-tool activation

| Tool | What to do once |
|---|---|
| Claude Code | start `claude` in the project; accept the trust dialog. `claude doctor` shows merged settings; `/hooks` lists the guard. |
| Gemini CLI | start `gemini` in the project; accept the trust dialog (or `/permissions`). `/memory show`, `/hooks panel`. |
| Cursor | open the folder; trust the workspace. Hooks reload on save of `.cursor/hooks.json`. |
| VS Code + Copilot | open the folder; trust it (Restricted Mode ignores workspace settings). Settings enable AGENTS.md, CLAUDE.md, skills, hooks. |
| Copilot CLI | start `copilot` from an **activated** terminal in the project (it inherits the env). |
| Antigravity | open the folder; keep "Terminal Command Auto Execution" on Request Review / Proceed in Sandbox. |
| Windsurf / Devin | open the folder. MCP servers must be pasted into the global `mcp_config.json` (sidecar in `.ai-sandbox/mcp/`). |

## E. Teams and CI

Commit `.ai-sandbox/` (minus the git-ignored machine parts), `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
`.claude/settings.json`, `.cursor/`, `.github/`, `.vscode/`, `.agents/`, `.devin/`. A teammate clones and runs
`install.*` once: `aisb init` regenerates the machine-specific files (`settings.local.json`, `.gemini/.env`,
`sandbox.env`, `.agents/hooks.json`) with their absolute paths.

In CI, `sh install.sh verify --quick` proves the sandbox is intact before an agent job runs.

## F. Uninstall

```bash
aisb uninstall                 # keeps .venv
aisb uninstall --purge-venv    # removes it too
aisb uninstall --dry-run       # show what would happen
```

Generated files are deleted, merged JSON files get only our keys removed (originals restored byte for byte
when nothing else changed), marked blocks are stripped, empty directories removed. Anything you modified
after install is kept and reported; its original goes to `.ai-sandbox-backup-<timestamp>/`.

## G. Upgrading

Pull the repo (or download the new release) and run `install.*` / `aisb init` again in each project. The
manifest and the SSOT survive; generated files are refreshed; your edits to rules/skills/policy are kept.
