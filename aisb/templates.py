# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Text templates: the policy, the shared skill/agent, the sandbox README and the in-project launchers."""
from __future__ import annotations

POLICY_MD = r"""# AI SANDBOX POLICY - mandatory for every AI assistant working in this folder

`<ROOT>` = the directory that contains `.ai-sandbox/`. Everything you do stays inside `<ROOT>`.
These rules are ENFORCED: a guard hook inspects every shell command and file operation before it
runs, writes it to `.ai-sandbox/logs/audit.log`, and blocks violations. A blocked call returns
`AI-SANDBOX DENY: <reason>` or `AI-SANDBOX ASK: <reason>`. Never retry a blocked action in another
form and never try to work around the guard: tell the user what was blocked and ask how to proceed.

## 1. Nothing global, ever
- No privilege escalation: `sudo`, `su`, `doas`, `runas`, `gsudo`.
- No system or user package managers: `brew`, `apt`, `apt-get`, `dnf`, `yum`, `pacman`, `winget`, `choco`, `scoop`, `msiexec`.
- No user-wide or global language installs: `pip install --user`, `npm -g`, `yarn global`, `pnpm -g`, `bun -g`,
  `pipx`, `uv tool install`, `cargo install`, `go install`, `gem install`, `dotnet tool -g`, `nvm`, `corepack`,
  `pyenv install`, `rustup`.
- No global configuration: `git config --global`, `npm config set`, `setx`, registry edits, scheduled tasks,
  services, shell start-up files (`~/.bashrc`, `$PROFILE`), `Set-ExecutionPolicy` (only `-Scope Process` is fine).
- Several of these are allowed automatically when the sandbox environment redirects the tool inside `<ROOT>`
  (for example `cargo install` with `CARGO_HOME` inside the workspace). If you are denied, the sandbox environment
  is not active in your process: say so to the user instead of fighting it.

## 2. Stay inside the workspace
- Read, write, execute and `cd` only inside `<ROOT>`. No `..` escapes, no `~`, `$HOME`, `%USERPROFILE%`,
  `%APPDATA%`, no other repositories, no `~/.ssh`, `~/.aws`, `~/.kube`, `~/.config`, `~/.docker`, `~/.gnupg`.
- Reading system locations (`/usr`, `/etc`, `C:\Windows`, `C:\Program Files`) is allowed; writing there is not.
- Temporary files go to `.ai-sandbox/cache/tmp/` (TMPDIR, TEMP and TMP already point there). Never `/tmp`, `%TEMP%`.
- Do not bind-mount, copy or symlink anything from outside `<ROOT>` into the workspace or into containers.

## 3. Python = the project virtual environment, only
- Interpreter: `./.venv/bin/python` (Linux, macOS, WSL) or `.\.venv\Scripts\python.exe` (Windows).
- Install: `<that interpreter> -m pip install <pkg>` or `-r requirements.txt`. Never bare `pip`/`pip3` with a system
  interpreter, never `--user`, `--break-system-packages`, `--isolated`, `--target` outside `<ROOT>`.
- If `.venv/` is missing: `aisb runtime python` (project-local interpreter, nothing global) or `python3 -m venv .venv`.
- `PIP_REQUIRE_VIRTUALENV=true`, `PYTHONNOUSERSITE=1` and a workspace-local pip cache are preset by the sandbox.
  Never unset, override or shadow sandbox environment variables; never use `env -i`.

## 4. Node and other ecosystems
- `npm ci` / `npm install <pkg>` (project-local); run tools with `npx <tool>` or `./node_modules/.bin/<tool>`.
- uv, poetry, pipenv, go, cargo, gradle, maven, dotnet, gem/bundler, composer, helm, terraform: use them normally;
  their caches, tool directories and user-level config files are redirected into `.ai-sandbox/cache/` and
  `.ai-sandbox/home/` by the sandbox environment.

## 5. Credentials and remote systems
- `aws`, `gcloud`, `az`, `kubectl`, `helm`, `terraform`, `docker login`, `gh` and `ssh` run with EMPTY, isolated
  configuration under `.ai-sandbox/home/`. They have no credentials unless the user deliberately adds some.
- Never copy real credentials into the workspace, never hard-code secrets, and ask before any action that touches a
  remote system, pushes with force, or publishes a package or image.

## 6. Transparency and self-protection
- Every tool call is logged with timestamp, tool, decision, rule and arguments (prompts are not logged by default).
- Do not create, edit, rename or delete: anything under `.ai-sandbox/` except `.ai-sandbox/cache/`,
  `.claude/settings*.json`, `.cursor/hooks.json`, `.gemini/settings.json`, `.gemini/.env`, `.github/hooks/**`,
  `.vscode/settings.json`, `.vscode/tasks.json`. The guard denies it; the user maintains them with `aisb sync`.
  Edits to `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `.gitignore` and `.ai-sandbox/home/` need the user's confirmation.
- Never download-and-execute (`curl ... | sh`, `iex (iwr ...)`), never decode-and-execute, never `eval` untrusted text.
- When unsure whether something is allowed, do the local, reversible thing, or ask the user.

## Quick reference
| Task | Command |
|---|---|
| Python dependencies | `./.venv/bin/python -m pip install -r requirements.txt` (Windows: `.\.venv\Scripts\python.exe -m pip ...`) |
| Run Python | `./.venv/bin/python script.py` |
| Node dependencies | `npm ci` or `npm install <pkg>` (never `-g`) |
| Check isolation | `./.ai-sandbox/bin/aisb verify` (Windows: `.ai-sandbox\bin\aisb.cmd verify`) |
| Audit log | `./.ai-sandbox/bin/aisb log -n 50` |
| Add an MCP server / skill / rule / agent (ask the user first) | `aisb add mcp|skill|rule|agent|command|hook ...` then `aisb sync` |

Machine-readable rules: `.ai-sandbox/policy.json` (+ `policy.local.json`). Shared skill: `local-env-manager`.
Shared sub-agent: `sandbox-auditor`.
"""

SKILL_LOCAL_ENV = r"""---
name: local-env-manager
description: Install, run and inspect Python, Node and other dependencies strictly inside this workspace (.venv, node_modules, .ai-sandbox caches) with zero global side effects. Use before any pip, npm, uv, poetry, cargo, go, dotnet or environment-setup task, and whenever a package or interpreter seems to be missing.
---
# Local environment manager

`<ROOT>` is the folder containing `.ai-sandbox/`. Every step below is checked by the sandbox guard;
a denial means the command took a global path. Fix the command, never bypass the guard.

## Python
1. Check the venv: `ls .venv/bin/python` (Windows: `dir .venv\Scripts\python.exe`).
   Missing: `./.ai-sandbox/bin/aisb runtime python` (downloads a project-local interpreter, nothing global)
   or `python3 -m venv .venv` (Windows: `python -m venv .venv` or `py -3 -m venv .venv`).
2. Install only through the venv interpreter:
   `./.venv/bin/python -m pip install <pkg>` / `-r requirements.txt` (Windows: `.\.venv\Scripts\python.exe -m pip ...`).
3. Run with the venv interpreter: `./.venv/bin/python -m pytest`, `./.venv/bin/python app.py`.
4. uv / poetry / pipenv: `uv venv`, `uv sync`, `uv pip install`, `poetry install`, `pipenv install` are fine
   (in-project environments are forced). Never `uv tool install`, `pipx`, `--system`, `--user`, `conda install`.
5. Record what you added (`requirements.txt`, `pyproject.toml`) so the environment is reproducible.

## Node
1. `npm ci` when a lockfile exists, otherwise `npm install <pkg>` (`--save-dev` for tooling). Never `-g`, `--global`.
2. Run tools with `npx <tool>` or `./node_modules/.bin/<tool>`. `npm config set` only with `--location=project`.
3. yarn / pnpm / bun: project-local commands only (`yarn add`, `pnpm add`, `bun add`). No `corepack enable`, no `nvm`.

## Other ecosystems
- go: `go build`, `go test`, `go run` as usual; module cache and `GOBIN` are already inside `<ROOT>`.
- cargo: `cargo build/test/run`; `cargo install <crate>` lands in the workspace-local `CARGO_HOME`.
- dotnet: `dotnet restore/build/test`; tools: `dotnet tool install --tool-path ./.ai-sandbox/home/dotnet-tools <tool>`.
- gem / bundler: `bundle install` (`BUNDLE_PATH` is local); composer: `composer install`.
- Temporary files: `.ai-sandbox/cache/tmp/`.

## Verify and report
- `./.ai-sandbox/bin/aisb verify` (Windows: `.ai-sandbox\bin\aisb.cmd verify`) must end with `RESULT: PASS`.
- `./.ai-sandbox/bin/aisb log -n 30` shows what you triggered. Mention every DENY/ASK line to the user.
"""

AGENT_AUDITOR_BODY = r"""You are the sandbox auditor for this workspace (root = the folder containing `.ai-sandbox/`).
You are READ-ONLY: you may run `./.ai-sandbox/bin/aisb verify|status|log ...`
(Windows: `.ai-sandbox\bin\aisb.cmd ...`) and read files. You never edit, install, delete or configure anything.

Procedure:
1. Run `verify`. Report the `RESULT:` line and every FAIL/WARN with a one-line explanation.
2. Read `.ai-sandbox/logs/audit.jsonl` (JSON per line). Count events per source and tool. List every `deny` and
   `ask` with timestamp, rule id and the exact command or path. Flag anything that looks like an attempt to leave the
   workspace or weaken the guard (rules: env-tamper, sandbox-self-protection, pipe-to-shell, parent-traversal,
   home-directory, forbidden-executable).
3. Confirm isolation facts: `.venv/` exists and is a real virtual environment; `PIP_REQUIRE_VIRTUALENV` and the cache
   variables appear in `.ai-sandbox/sandbox.env`; the generated files under `.vscode/`, `.claude/`, `.gemini/`,
   `.cursor/`, `.github/hooks/` contain no paths outside the workspace other than the system interpreter.
4. Finish with a verdict (CLEAN or ATTENTION), the three most important findings, and the exact next command for
   the user if something needs fixing (`aisb sync`, `aisb init`, or a policy.json change).
Quote log lines; do not speculate.
"""

GEMINI_CMD_AUDIT = """description = "ai-sandbox: run verify and summarise the audit log"
prompt = \"\"\"
Act as the sandbox-auditor (read-only). Verification output:
!{%(verify)s}

Latest audit log entries:
!{%(log)s}

Report: the RESULT line, every DENY/ASK with rule id and the exact command or path, whether anything tried to leave
the workspace or weaken the guard, and the single next command for the user if something needs fixing.
\"\"\"
"""

GEMINI_CMD_LOG = """description = "ai-sandbox: show the last audit log entries"
prompt = \"\"\"
Here are the latest sandbox audit entries (newest last):
!{%(log)s}

Explain in plain language what was run, what was blocked and why.
\"\"\"
"""

SANDBOX_README = r"""# .ai-sandbox - project-local AI sandbox (single source of truth)

| Path | Purpose | Edit? |
|---|---|---|
| `rules/*.md` | Instructions every AI tool receives. `sandbox-policy.md` is the mandatory one; add more with `aisb add rule` | yes, then `aisb sync` |
| `policy.json` / `policy.local.json` | Machine-enforced rules (regex patterns, forbidden executables, protected paths, env var names) | yes (`policy.json` is committable; `.local` is per machine) |
| `hooks/sandbox_guard.py` | The enforcement + audit hook (Claude Code, Gemini CLI, Cursor, Copilot, Windsurf protocols) | no (update aisb) |
| `skills/`, `agents/`, `commands/`, `hooks.d/`, `mcp/servers.json` | Shared components; fanned out to every tool's expected location on `aisb sync` | yes / via `aisb add` |
| `bundles/` | Imported plugins, skill packs and bundles (`aisb apply`), with `bundles.lock.json` | via `aisb apply/remove` |
| `sandbox.env` | Generated environment for this machine (absolute paths) | no (regenerated) |
| `bin/` | `aisb` / `aisb.cmd` / `aisb.ps1` launchers, `activate.{sh,ps1,cmd}`, `aisb.pyz` (or `aisb-bin/` when installed without Python) | no |
| `config/`, `home/` | Isolated pip/npm/git/kube/aws/gcloud/docker/XDG configuration the tools see instead of your real ones | only on purpose |
| `cache/` | pip, npm, uv, go, cargo, playwright, HF ... caches + `tmp/` | safe to delete |
| `runtime/` | Optional project-local Python (`aisb runtime python`) | no |
| `logs/audit.log` + `audit.jsonl` | Every tool call: timestamp, source, tool, decision, rule, command/path | read only |
| `manifest.json`, `backup/` | What aisb created/merged + originals of files it merged into (used by `aisb uninstall`) | no |

Commands (from the project root; `aisb` is a shell function after activation, otherwise `./.ai-sandbox/bin/aisb`):

    aisb verify | sync | status | log [-n 50] [--follow] [--denied] | uninstall [--purge-venv]
    aisb add mcp|skill|rule|agent|command|hook ...     aisb apply <bundle|github:owner/repo|profile:name>
    aisb context <target|all>      aisb doctor <target>      aisb pack      aisb runtime python

Activate the sandbox environment in a terminal before starting any AI tool from it:

    source ./.ai-sandbox/bin/activate.sh        (bash/zsh)      . .\.ai-sandbox\bin\activate.ps1   (PowerShell)
    call .ai-sandbox\bin\activate.cmd           (cmd)
"""

ACTIVATE_SH = r"""# ai-sandbox: activate the sandbox environment in the CURRENT shell (bash or zsh).
#   source ./.ai-sandbox/bin/activate.sh
# Only this shell's environment changes; nothing is written anywhere. Undo with: aisb_deactivate
if [ -n "${BASH_SOURCE:-}" ]; then _ais_src="${BASH_SOURCE[0]}"; elif [ -n "${ZSH_VERSION:-}" ]; then _ais_src="${(%):-%x}"; else _ais_src="$0"; fi
AI_SANDBOX_ROOT="$(cd "$(dirname "$_ais_src")/../.." && pwd)"
export AI_SANDBOX_ROOT
if [ -z "${AI_SANDBOX_OLD_PATH:-}" ]; then export AI_SANDBOX_OLD_PATH="$PATH"; export AI_SANDBOX_OLD_PS1="${PS1:-}"; fi
set -a
. "$AI_SANDBOX_ROOT/.ai-sandbox/sandbox.env"
set +a
if [ "${AI_SANDBOX_STRICT:-0}" != "1" ]; then unset @@SHELL_EXCLUDED@@; fi
export VIRTUAL_ENV="$AI_SANDBOX_ROOT/.venv"
for _ais_dir in "$AI_SANDBOX_ROOT/.ai-sandbox/bin" "$AI_SANDBOX_ROOT/node_modules/.bin" "$AI_SANDBOX_ROOT/.venv/@@VENV_BIN@@"; do
  case ":$PATH:" in *":$_ais_dir:"*) ;; *) PATH="$_ais_dir:$PATH" ;; esac
done
export PATH
unset _ais_dir _ais_src
aisb() { "$AI_SANDBOX_ROOT/.ai-sandbox/bin/aisb" "$@"; }
sandbox() { aisb "$@"; }
aisb_deactivate() {
  [ -n "${AI_SANDBOX_OLD_PATH:-}" ] && export PATH="$AI_SANDBOX_OLD_PATH"
  [ -n "${AI_SANDBOX_OLD_PS1+x}" ] && PS1="$AI_SANDBOX_OLD_PS1"
  for _v in $(sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' "$AI_SANDBOX_ROOT/.ai-sandbox/sandbox.env"); do unset "$_v"; done
  unset VIRTUAL_ENV AI_SANDBOX_OLD_PATH AI_SANDBOX_OLD_PS1 AI_SANDBOX_ROOT _v
  unset -f aisb sandbox aisb_deactivate
  echo "[ai-sandbox] deactivated"
}
sandbox_deactivate() { aisb_deactivate; }
case "${PS1:-}" in "(sandbox) "*) ;; *) PS1="(sandbox) ${PS1:-}" ;; esac
echo "[ai-sandbox] active: $AI_SANDBOX_ROOT  (python: $AI_SANDBOX_ROOT/.venv/@@VENV_BIN@@/@@VENV_PY@@)$( [ "${AI_SANDBOX_STRICT:-0}" = "1" ] && echo '  [strict: credential firewall in this shell too]' )"
"""

# In-project launcher: finds the sandbox's own runtime WITHOUT installing anything.
LAUNCHER_SH = r"""#!/bin/sh
# ai-sandbox launcher (POSIX sh: dash, bash, zsh, busybox, Git Bash).  Usage: ./.ai-sandbox/bin/aisb <command> ...
# Runtime order: 1) aisb-bin/ (standalone build, no Python needed)  2) project .venv  3) .ai-sandbox/runtime/python
#                4) python3 / python / py -3 on PATH.  Nothing is installed by this script.
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
if [ -x "$here/aisb-bin/aisb" ]; then exec "$here/aisb-bin/aisb" "$@"; fi
if [ -x "$here/aisb-bin/aisb.exe" ]; then exec "$here/aisb-bin/aisb.exe" "$@"; fi
pyz="$here/aisb.pyz"
[ -f "$pyz" ] || { echo "aisb: $pyz is missing - re-run the installer" >&2; exit 1; }
ok() { "$@" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; }
for cand in "$root/.venv/bin/python" "$root/.venv/Scripts/python.exe" "$root/.ai-sandbox/runtime/python/bin/python3" "$root/.ai-sandbox/runtime/python/python.exe"; do
  if [ -x "$cand" ] && ok "$cand"; then exec "$cand" "$pyz" "$@"; fi
done
for name in python3 python; do
  if command -v "$name" >/dev/null 2>&1; then
    if [ "$(uname -s 2>/dev/null)" = "Darwin" ] && [ "$(command -v "$name")" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then continue; fi
    if ok "$name"; then exec "$name" "$pyz" "$@"; fi
  fi
done
if command -v py >/dev/null 2>&1 && ok py -3; then exec py -3 "$pyz" "$@"; fi
echo "aisb: no Python 3.8+ found and no standalone build in $here/aisb-bin. Run the installer again (it can fetch a standalone build) or install Python 3.8+ yourself." >&2
exit 1
"""

LAUNCHER_CMD = r"""@echo off
rem ai-sandbox launcher (cmd.exe).  Usage: .ai-sandbox\bin\aisb.cmd <command> ...
rem Runtime order: aisb-bin\aisb.exe (no Python needed) > .venv > .ai-sandbox\runtime\python > py -3 / python on PATH.
setlocal
set "HERE=%~dp0"
set "ROOT=%HERE%..\.."
if exist "%HERE%aisb-bin\aisb.exe" ( "%HERE%aisb-bin\aisb.exe" %* & exit /b %ERRORLEVEL% )
if not exist "%HERE%aisb.pyz" ( echo aisb: %HERE%aisb.pyz is missing - re-run the installer 1>&2 & exit /b 1 )
set "PY="
set "PYARGS="
if exist "%ROOT%\.venv\Scripts\python.exe" ( set "PY=%ROOT%\.venv\Scripts\python.exe" & call :check && goto :run )
if exist "%ROOT%\.ai-sandbox\runtime\python\python.exe" ( set "PY=%ROOT%\.ai-sandbox\runtime\python\python.exe" & call :check && goto :run )
where py >nul 2>nul && ( set "PY=py" & set "PYARGS=-3" & call :check && goto :run )
where python >nul 2>nul && ( set "PY=python" & set "PYARGS=" & call :check && goto :run )
echo aisb: no Python 3.8+ found and no standalone build in %HERE%aisb-bin. Re-run install.cmd (it can fetch a standalone build). 1>&2
exit /b 1
:check
"%PY%" %PYARGS% -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if errorlevel 1 ( set "PY=" & set "PYARGS=" & exit /b 1 )
exit /b 0
:run
"%PY%" %PYARGS% "%HERE%aisb.pyz" %*
exit /b %ERRORLEVEL%
"""

LAUNCHER_PS1 = r"""#requires -Version 5.1
# ai-sandbox launcher (PowerShell).  Usage: .\.ai-sandbox\bin\aisb.ps1 <command> ...
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $here '..\..')).Path
$bin = Join-Path $here 'aisb-bin\aisb.exe'
if (-not (Test-Path $bin)) { $bin = Join-Path $here 'aisb-bin\aisb' }
if (Test-Path $bin) { & $bin @args; exit $LASTEXITCODE }
$pyz = Join-Path $here 'aisb.pyz'
if (-not (Test-Path $pyz)) { Write-Error "aisb: $pyz is missing - re-run the installer"; exit 1 }
function Test-Py([string]$exe, [string[]]$pre) {
  try { & $exe @pre -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}
$cands = @(
  @{ exe = (Join-Path $root '.venv\Scripts\python.exe'); pre = @() },
  @{ exe = (Join-Path $root '.venv\bin\python'); pre = @() },
  @{ exe = (Join-Path $root '.ai-sandbox\runtime\python\python.exe'); pre = @() },
  @{ exe = (Join-Path $root '.ai-sandbox\runtime\python\bin\python3'); pre = @() },
  @{ exe = 'py'; pre = @('-3') }, @{ exe = 'python'; pre = @() }, @{ exe = 'python3'; pre = @() })
foreach ($c in $cands) {
  if (($c.exe -like '*\*' -or $c.exe -like '*/*') -and -not (Test-Path $c.exe)) { continue }
  if (-not ($c.exe -like '*\*' -or $c.exe -like '*/*') -and -not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
  if (Test-Py $c.exe $c.pre) { & $c.exe @($c.pre) $pyz @args; exit $LASTEXITCODE }
}
Write-Host 'aisb: no Python 3.8+ found and no standalone build in .ai-sandbox\bin\aisb-bin. Re-run install.ps1/install.cmd.' -ForegroundColor Red
exit 1
"""
