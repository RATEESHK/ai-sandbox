# Reusable prompts

## A. Bootstrap prompt — paste into any AI coding tool

```text
Set up this folder as a closed, audited AI sandbox with ai-sandbox (aisb). Mandatory rules for this task:

1. Work only inside the current folder. Do not install anything globally; do not use sudo/brew/apt/winget/choco;
   do not touch files under my home directory; do not change global git/npm/pip configuration.
2. Detect the operating system and shell first, then run the matching bootstrap FROM THIS FOLDER:
     Linux / macOS / WSL / Git Bash:   sh <AISB_DIR>/install.sh
     Windows cmd:                      <AISB_DIR>\install.cmd
     Windows PowerShell:               powershell -NoProfile -ExecutionPolicy Bypass -File <AISB_DIR>\install.ps1
   (<AISB_DIR> is the ai-sandbox checkout or the unpacked release). The bootstrap uses an existing Python 3.8+ or
   downloads the standalone build into ./.ai-sandbox/bin/aisb-bin/. It never installs Python. If it says no Python
   and no network, stop and tell me.
3. Do not pass --force, --no-credential-firewall or --no-os-sandbox unless I say so.
4. When init finishes, run `./.ai-sandbox/bin/aisb verify` (Windows: `.ai-sandbox\bin\aisb.cmd verify`). It must end
   with "RESULT: PASS". Paste the full output. If anything FAILs, explain and stop.
5. Show `git status --short` (or a file listing) so I see every file created or merged, and the ai-sandbox block
   appended to .gitignore.
6. From now on follow .ai-sandbox/rules/sandbox-policy.md (loaded automatically): use ./.venv/bin/python
   (Windows .\.venv\Scripts\python.exe), never -g/--user installs, never paths outside this folder, and report any
   "AI-SANDBOX DENY/ASK" message to me instead of working around it.
7. Do not run `aisb context`, `aisb apply` or `aisb add` unless I ask; when I do, tell me exactly which files changed.
8. Finish with the activate command for my shell and the reminder to start each AI tool from this folder and accept
   its "trust this folder" prompt.
```

## B. The policy text (for tools that cannot read project files)

The binding text is `.ai-sandbox/rules/sandbox-policy.md` in any sandboxed project, or
[`aisb/templates.py`](../aisb/templates.py) (`POLICY_MD`) in this repository. Paste it into a hosted agent's
instructions field when the agent cannot read the project.

## C. Rebuilding from this repository

This repository *is* the specification: `aisb/targets.py` (where each tool reads what), `aisb/guard.py`
(the engine and its 176-case self-test), `aisb/generators.py` (file shapes per tool), `tests/` (behaviour).
A capable model given `docs/architecture.md`, `docs/policy.md`, `docs/targets.md` and the tests can
re-implement a compatible tool; start from the acceptance tests in `tests/test_e2e.py`.
