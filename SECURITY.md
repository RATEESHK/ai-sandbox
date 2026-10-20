# Security policy

ai-sandbox is a safety tool. A bug that lets an AI agent escape the workspace, install something
globally, read credentials, or silently disable the guard is a **security issue**.

## Reporting

Use GitHub's private vulnerability reporting ("Security" tab → "Report a vulnerability") on this
repository, or contact the maintainer via the URL in `NOTICE`.
Please include: OS, tool (Claude Code / Cursor / ...), the exact command or payload, and what happened.
Do not open a public issue for escapes.

You will get an acknowledgement within 7 days. Fixes ship as a patch release with a `SHA256SUMS`
update; credit is given in the release notes unless you prefer otherwise.

## Scope and known limits (not bugs)

- Command inspection is static analysis of the command string and tool arguments. A program the agent
  writes and then runs is opaque to the guard; Claude Code's own kernel sandbox (enabled by aisb where
  available) is the hard barrier. Native Windows has no kernel sandbox.
- Hooks only run when the tool loads them: the project folder must be opened as the root and trusted.
- Tools decide what reaches their hooks; vendor changes can silently reduce coverage. `aisb verify`
  checks the file formats aisb knows about, not the live tool.
- Exclusion/ignore files are best-effort by the tools' own documentation (terminal and MCP access cannot be
  blocked by `.cursorignore`, for example).

## Supported versions

Only the latest release receives fixes.
