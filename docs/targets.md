# Supported tools (targets)

Generated from `aisb/targets.py` by `scripts/gen_targets_doc.py`. Facts verified against vendor
documentation in October 2026; `confidence: medium` marks items the vendor documents thinly.
Default targets: `claude`, `gemini`, `cursor`, `copilot`, `vscode`, `windsurf`, `antigravity`. Use `--tools all` for the rest.

| id | tool | rules | skills | agents | commands | MCP (project) | hooks | ignore | confidence |
|---|---|---|---|---|---|---|---|---|---|
| `claude` | Claude Code | claude | .claude/skills | .claude/agents | .claude/commands | .mcp.json | .claude/settings.local.json | claude-deny | high |
| `gemini` | Gemini CLI | gemini | .agents/skills | .gemini/agents | .gemini/commands | .gemini/settings.json | .gemini/settings.json | .geminiignore | high |
| `cursor` | Cursor | .cursor/rules | .claude/skills, .agents/skills | .cursor/agents | .cursor/commands | .cursor/mcp.json | .cursor/hooks.json | .cursorignore | high |
| `copilot` | GitHub Copilot (CLI, VS Code agent, coding agent) | .github/instructions | .claude/skills, .agents/skills | .github/agents | .github/prompts | .github/mcp.json | .github/hooks/ai-sandbox.json | none | high |
| `vscode` | VS Code (editor settings, terminal env, tasks) | none | — | — | — | .vscode/mcp.json | — | vscode-settings | high |
| `windsurf` | Windsurf / Devin Desktop (Cascade) | .devin/rules | — | — | .devin/workflows | sidecar `.ai-sandbox/mcp/devin.mcp_config.json` | .devin/hooks.json | .devinignore | high |
| `antigravity` | Google Antigravity (App, IDE, CLI) | .agents/rules | .agents/skills | .agents/agents | — | .agents/mcp_config.json | .agents/hooks.json | .antigravityignore | high |
| `cline` | Cline | .clinerules | — | — | — | — | — | .clineignore | high |
| `roo` | Roo Code | .roo/rules | — | — | — | .roo/mcp.json | — | .rooignore | high |
| `kiro` | Kiro | .kiro/steering | — | — | — | .kiro/settings/mcp.json | — | .kiroignore | high |
| `junie` | JetBrains Junie | .junie/guidelines.md | — | — | — | .junie/mcp/mcp.json | — | .aiignore | medium |
| `amazonq` | Amazon Q Developer | .amazonq/rules | — | — | — | — | — | none | high |
| `continue` | Continue | .continue/rules | — | — | — | — | — | .continueignore | high |
| `zed` | Zed | .rules | — | — | — | .zed/settings.json | — | zed-settings | high |
| `codex` | OpenAI Codex CLI | agents-md-only | .codex/skills | .codex/agents | — | .codex/config.toml | — | none | medium |
| `aider` | Aider | CONVENTIONS.md | — | — | — | — | — | .aiderignore | high |

## Notes per tool

- **claude** (Claude Code) — docs: <https://code.claude.com/docs/en/settings>
  - ignore: Claude Code has no ignore file; exclusions are permissions.deny Read(...) rules in .claude/settings.json
  - trust: Project settings, hooks and .mcp.json load after you accept the one-time 'trust this folder' dialog.
- **gemini** (Gemini CLI) — docs: <https://geminicli.com/docs/reference/configuration/>
  - ignore: .geminiignore uses .gitignore syntax; .gitignore is also respected (context.fileFiltering)
  - trust: Untrusted folders ignore .gemini/settings.json, .gemini/.env, hooks and commands; accept the trust dialog or run /permissions.
- **cursor** (Cursor) — docs: <https://cursor.com/docs/context/rules>
  - ignore: .cursorignore blocks Agent/Tab/@-mentions reads (best effort; terminal/MCP cannot be blocked); .gitignore respected by default
  - trust: Project hooks and MCP run only in a trusted workspace (Workspace Trust prompt on open).
- **copilot** (GitHub Copilot (CLI, VS Code agent, coding agent)) — docs: <https://docs.github.com/en/copilot/reference/hooks-reference>
  - mcp: Copilot CLI/coding agent read .github/mcp.json (and .mcp.json); VS Code Copilot reads .vscode/mcp.json (written by the vscode target)
  - ignore: Copilot content exclusion is configured by repository/organization administrators (GitHub settings), not by a project file
  - trust: Copilot CLI asks to trust the folder on first start (stored in ~/.copilot/config.json).
- **vscode** (VS Code (editor settings, terminal env, tasks)) — docs: <https://code.visualstudio.com/docs/editing/workspaces/workspace-trust>
  - ignore: files.exclude / search.exclude / files.watcherExclude in .vscode/settings.json
  - trust: Restricted Mode (untrusted workspace) ignores workspace settings, tasks and the terminal env.
- **windsurf** (Windsurf / Devin Desktop (Cascade)) — docs: <https://docs.devin.ai/desktop/cascade/memories>
  - mcp: Devin Desktop/Windsurf read MCP servers only from the global mcp_config.json (~/.config/devin or ~/.codeium/windsurf); aisb writes a sidecar you can paste
  - ignore: .devinignore (legacy .windsurfignore/.codeiumignore still read); .gitignore respected
  - trust: Workspace rules are limited to 12,000 characters per file. Windsurf was renamed Devin Desktop in 2026; both layouts are written.
- **antigravity** (Google Antigravity (App, IDE, CLI)) — docs: <https://www.antigravity.google/docs/rules>
  - ignore: Antigravity's documented exclusion is Strict Mode + .gitignore; .antigravityignore is widely used but not in the official docs
  - trust: Keep 'Terminal Command Auto Execution' on Request Review (or Proceed in Sandbox); never 'Always Proceed'.
- **cline** (Cline) — docs: <https://docs.cline.bot/features/cline-rules>
  - mcp: Cline stores MCP servers globally (cline_mcp_settings.json)
- **roo** (Roo Code) — docs: <https://roocodeinc.github.io/Roo-Code/features/custom-instructions/>
- **kiro** (Kiro) — docs: <https://kiro.dev/docs/kiroignore/>
  - ignore: .kiroignore (nested files allowed)
- **junie** (JetBrains Junie) — docs: <https://junie.jetbrains.com/docs/guidelines-and-memory.html>
  - ignore: JetBrains AI Assistant/Junie honour .aiignore
- **amazonq** (Amazon Q Developer) — docs: <https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/context-project-rules.html>
- **continue** (Continue) — docs: <https://docs.continue.dev/customize/deep-dives/rules>
  - mcp: Continue uses .continue/mcpServers/*.yaml
- **zed** (Zed) — docs: <https://zed.dev/docs/ai/rules>
  - ignore: Zed uses private_files / file_scan_exclusions in .zed/settings.json
- **codex** (OpenAI Codex CLI) — docs: <https://developers.openai.com/codex>
  - trust: Project .codex/config.toml loads only after the project is trusted.
- **aider** (Aider) — docs: <https://aider.chat/docs/usage/conventions.html>

## Ignore-file pattern groups (`aisb context`)

Default groups: deps, build, caches, secrets, minified, vcs.

- **deps**: `node_modules/`, `.venv/`, `venv/`, `.tox/`, `.nox/`, `vendor/`, `bower_components/`, `jspm_packages/`, `.pnpm-store/`, `.yarn/cache/`, `.yarn/unplugged/`, `Pods/`, `.bundle/`, `packages/*/node_modules/`
- **build**: `dist/`, `build/`, `out/`, `target/`, `bin/`, `obj/`, `.next/`, `.nuxt/`, `.svelte-kit/`, `.output/`, `.turbo/`, `.parcel-cache/`, `.angular/`, `storybook-static/`, `public/build/`, `*.egg-info/`, `__pycache__/`, `*.pyc`, `*.pyo`, `*.class`, `*.o`, `*.so`, `*.dll`, `*.dylib`, `*.exe`, `*.wasm`
- **caches**: `.cache/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.gradle/`, `.dart_tool/`, `.eslintcache`, `.stylelintcache`, `coverage/`, `.nyc_output/`, `htmlcov/`, `*.log`, `logs/`, `tmp/`, `temp/`, `.ai-sandbox/cache/`, `.ai-sandbox/home/`, `.ai-sandbox/logs/`, `.ai-sandbox/backup/`, `.ai-sandbox/runtime/`, `.ai-sandbox/bin/aisb-bin/`, `.ai-sandbox/bundles/_src/`
- **secrets**: `.env`, `.env.*`, `!.env.example`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `id_rsa`, `id_ed25519`, `*.tfstate`, `*.tfstate.backup`, `secrets.*`, `credentials.*`, `.netrc`, `.npmrc`, `.pypirc`
- **lockfiles**: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `bun.lock`, `poetry.lock`, `uv.lock`, `Pipfile.lock`, `Cargo.lock`, `composer.lock`, `Gemfile.lock`, `go.sum`, `packages.lock.json`, `flake.lock`
- **media**: `*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.webp`, `*.svg`, `*.ico`, `*.bmp`, `*.tiff`, `*.psd`, `*.mp3`, `*.wav`, `*.flac`, `*.mp4`, `*.mov`, `*.avi`, `*.mkv`, `*.webm`, `*.pdf`, `*.zip`, `*.tar`, `*.gz`, `*.7z`, `*.rar`, `*.iso`, `*.dmg`, `*.bin`, `*.ttf`, `*.otf`, `*.woff`, `*.woff2`
- **data**: `*.csv`, `*.tsv`, `*.parquet`, `*.sqlite`, `*.db`, `*.h5`, `*.hdf5`, `*.npy`, `*.npz`, `*.pkl`, `*.onnx`, `*.pt`, `*.pth`, `*.safetensors`, `*.ckpt`, `data/`, `datasets/`, `models/`
- **minified**: `*.min.js`, `*.min.css`, `*.map`, `*.bundle.js`, `*.chunk.js`
- **vcs**: `.git/`, `.svn/`, `.hg/`, `.idea/`, `.vs/`, `*.iml`
