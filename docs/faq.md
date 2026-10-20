# FAQ

**Does it work without Python?** Yes. `install.sh` (POSIX sh) and `install.cmd` (cmd.exe) download the
standalone build for your OS/CPU from the releases, verify its SHA-256 and run it from
`.ai-sandbox/bin/aisb-bin/`. No bash, no PowerShell, no admin rights, no PATH changes. See `docs/install.md`.

**Does it install anything globally, ever?** No. Not Python, not Node, not a package manager, not a shell
rc entry, not a registry key. The `.venv`, the standalone build, the optional project-local Python, all
caches, all tool configs live inside the project folder. `aisb uninstall` removes them.

**Which tools?** Claude Code, Gemini CLI, Cursor, GitHub Copilot (CLI, VS Code agent, coding agent),
VS Code, Google Antigravity (App/IDE/CLI), Windsurf / Devin Desktop by default; Codex, Cline, Roo Code,
Kiro, JetBrains Junie, Amazon Q, Continue, Zed, Aider via `--tools all` (rules + MCP where a project file exists).
`aisb targets` prints the live table.

**How do I isolate each project?** Run `aisb init` in each project. Every project gets its own `.venv`,
caches, credentials firewall, rules, skills, agents, MCP servers and audit log; the hooks of one project
never see another (they resolve paths against their own root).

**Can I share my setup?** `aisb pack` → `name.aisb.zip`; others run `aisb apply name.aisb.zip` (or push the
unpacked folder to GitHub and `aisb apply github:you/name`). See `docs/bundles.md`.

**How do I add a custom MCP server? A public one?** `aisb add mcp <name> --command ...` or `--url ...`,
then it is written into every tool's file. Public servers list and per-tool quirks: `docs/mcp.md`.

**Voice mode and dictation?** `aisb apply profile:voice` adds dictation and voice-mode instructions as rules
(every tool receives them) and enables Claude Code's voice dictation for the project. None of the tools has
a native "dictation instructions" setting, so rules are the portable way.

**Why does `aisb context` not run automatically?** Because some teams want `node_modules` or data
folders in the agent's context. You decide, per tool, when you run it.

**Does the guard replace the tools' own permission systems?** No, it adds to them. Tool-native rules are
layer 2, the guard is layer 3, environment redirection is layer 4, Claude Code's kernel sandbox is layer 5.
Each works without the others.

**Is the audit log sensitive?** It contains the exact commands the agent ran. It is git-ignored; treat it
like a shell history.

<!-- license-faq -->
**Why AGPL + a commercial license, and not MIT (or "the SQLite license")?** SQLite's code is actually public domain — anyone may copy, modify and sell it; what makes SQLite feel "closed" is governance (one team, no outside commits, a trademark, paid warranty-of-title licenses for corporate legal departments). ai-sandbox copies the governance (`GOVERNANCE.md`) and uses the AGPL-3.0-or-later so that every company's legal team already knows the terms and everyone can use it, at work too, for free. What the AGPL adds over MIT: forks and modified distributions must stay open and keep the author attribution (`NOTICE`), and whoever wants to ship it closed buys a commercial license — or contributes instead of paying (`COMMERCIAL-LICENSE.md`). Everything is explained in `LICENSING.md`; switching is one command (`scripts/set_license.py agpl|gpl|apache|noncommercial|strict`).
<!-- /license-faq -->

**What about tool updates that change file formats?** The registry (`aisb/targets.py`) carries the
vendor doc URL and a confidence note per fact; `aisb verify` checks the files aisb generated. Open a
"Tool format change" issue with the new doc URL — that is the most valuable contribution.
