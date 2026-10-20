# Changelog

All notable changes to ai-sandbox are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [1.1.0] - 2026-10-21

### Added
- `aisb` command line with `init/sync/verify/status/log/uninstall`, `add/remove/list`, `apply/pack`,
  `context`, `doctor`, `runtime`, `targets`.
- Multi-protocol guard hook: Claude Code, Gemini CLI, Cursor, GitHub Copilot (CLI + VS Code), Windsurf /
  Devin Desktop, Google Antigravity (`.agents/hooks.json`), generic exit-code runners.
- Targets registry (`aisb/targets.py`) with verified rules / skills / agents / commands / MCP / hooks /
  ignore locations for 15 tools.
- Bundles: import Claude Code plugins & marketplaces, skill-tree repos and `.aisb.zip` bundles into the
  project SSOT; `aisb pack` exports a project's agentic setup with secrets scrubbed.
- Built-in profiles: `design`, `motion-design`, `boris-workflow`, `voice`, `knowledge-work`, `gstack`.
- Project-local Python runtime (`aisb runtime python`) from pinned python-build-standalone builds with
  SHA256 verification.
- Standalone builds (PyInstaller onedir) and bootstraps that work with only `cmd.exe` or POSIX `sh`.
- Dual license: GNU AGPL-3.0-or-later with attribution terms (`NOTICE`, GPL section 7) **or** a commercial
  license whose fee can be replaced by contributing to / maintaining the project (`COMMERCIAL-LICENSE.md`,
  `LICENSING.md`). `scripts/set_license.py agpl|gpl|apache|noncommercial|strict` regenerates every
  license-related file and the SPDX headers of all source files. Governance document, CLA workflow, `ADOPTERS.md`;
  `aisb --version` prints the attribution.

### Changed
- Renamed the manager from `sandbox_manager.py` to the `aisb` package; `.ai-sandbox/bin/aisb{,.cmd,.ps1}`
  launchers replace `sandbox.sh/.ps1/.cmd`.

## [1.0.0] - 2026-10-19

- Initial single-file kit (`sandbox_manager.py` + guard) for Claude Code, Gemini CLI, Cursor, Copilot,
  VS Code and Windsurf.
