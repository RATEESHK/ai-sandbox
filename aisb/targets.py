# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Declarative registry of supported AI tools ("targets").

Each entry says where a tool reads project-level rules, skills, agents, commands, MCP servers, hooks and
ignore files, so one SSOT can be fanned out, and so `aisb context <target>` / `aisb doctor <target>` know
what to do.  Facts here were checked against vendor documentation in October 2026; items marked
`"confidence": "medium"` are best-effort (file exists but the vendor's documentation is thin).
"""
from __future__ import annotations

DEFAULT_TOOLS = ["claude", "gemini", "cursor", "copilot", "vscode", "windsurf", "antigravity"]

# ignore patterns by group; `aisb context` writes the selected groups
IGNORE_GROUPS = {
    "deps": ["node_modules/", ".venv/", "venv/", ".tox/", ".nox/", "vendor/", "bower_components/", "jspm_packages/",
             ".pnpm-store/", ".yarn/cache/", ".yarn/unplugged/", "Pods/", ".bundle/", "packages/*/node_modules/"],
    "build": ["dist/", "build/", "out/", "target/", "bin/", "obj/", ".next/", ".nuxt/", ".svelte-kit/", ".output/",
              ".turbo/", ".parcel-cache/", ".angular/", "storybook-static/", "public/build/", "*.egg-info/",
              "__pycache__/", "*.pyc", "*.pyo", "*.class", "*.o", "*.so", "*.dll", "*.dylib", "*.exe", "*.wasm"],
    "caches": [".cache/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/", ".gradle/", ".dart_tool/", ".eslintcache",
               ".stylelintcache", "coverage/", ".nyc_output/", "htmlcov/", "*.log", "logs/", "tmp/", "temp/",
               ".ai-sandbox/cache/", ".ai-sandbox/home/", ".ai-sandbox/logs/", ".ai-sandbox/backup/",
               ".ai-sandbox/runtime/", ".ai-sandbox/bin/aisb-bin/", ".ai-sandbox/bundles/_src/"],
    "secrets": [".env", ".env.*", "!.env.example", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore",
                "id_rsa", "id_ed25519", "*.tfstate", "*.tfstate.backup", "secrets.*", "credentials.*",
                ".netrc", ".npmrc", ".pypirc"],
    "lockfiles": ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock", "poetry.lock",
                  "uv.lock", "Pipfile.lock", "Cargo.lock", "composer.lock", "Gemfile.lock", "go.sum",
                  "packages.lock.json", "flake.lock"],
    "media": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg", "*.ico", "*.bmp", "*.tiff", "*.psd",
              "*.mp3", "*.wav", "*.flac", "*.mp4", "*.mov", "*.avi", "*.mkv", "*.webm", "*.pdf", "*.zip", "*.tar",
              "*.gz", "*.7z", "*.rar", "*.iso", "*.dmg", "*.bin", "*.ttf", "*.otf", "*.woff", "*.woff2"],
    "data": ["*.csv", "*.tsv", "*.parquet", "*.sqlite", "*.db", "*.h5", "*.hdf5", "*.npy", "*.npz", "*.pkl",
             "*.onnx", "*.pt", "*.pth", "*.safetensors", "*.ckpt", "data/", "datasets/", "models/"],
    "minified": ["*.min.js", "*.min.css", "*.map", "*.bundle.js", "*.chunk.js"],
    "vcs": [".git/", ".svn/", ".hg/", ".idea/", ".vs/", "*.iml"],
}
IGNORE_DEFAULT_GROUPS = ["deps", "build", "caches", "secrets", "minified", "vcs"]

TARGETS = {
    "claude": {
        "title": "Claude Code", "vendor": "Anthropic", "kind": "cli", "aliases": ["claude-code", "claudecode", "cc"],
        "rules": {"style": "claude"},                         # CLAUDE.md import + .claude/rules/*.md (paths: globs)
        "skills_dirs": [".claude/skills"],
        "agents": {"dir": ".claude/agents", "style": "claude"},
        "commands": {"dir": ".claude/commands", "style": "md", "ext": ".md"},
        "mcp": {"file": ".mcp.json", "style": "claude"},
        "hooks": {"style": "claude", "file": ".claude/settings.local.json"},
        "ignore": {"file": None, "style": "claude-deny",
                   "note": "Claude Code has no ignore file; exclusions are permissions.deny Read(...) rules in .claude/settings.json"},
        "trust": "Project settings, hooks and .mcp.json load after you accept the one-time 'trust this folder' dialog.",
        "docs": "https://code.claude.com/docs/en/settings",
        "confidence": "high",
    },
    "gemini": {
        "title": "Gemini CLI", "vendor": "Google", "kind": "cli", "aliases": ["gemini-cli", "geminicli"],
        "rules": {"style": "gemini"},                         # GEMINI.md imports
        "skills_dirs": [".agents/skills"],
        "agents": {"dir": ".gemini/agents", "style": "gemini"},
        "commands": {"dir": ".gemini/commands", "style": "toml", "ext": ".toml"},
        "mcp": {"file": ".gemini/settings.json", "style": "gemini"},
        "hooks": {"style": "gemini", "file": ".gemini/settings.json"},
        "ignore": {"file": ".geminiignore", "style": "gitignore",
                   "note": ".geminiignore uses .gitignore syntax; .gitignore is also respected (context.fileFiltering)"},
        "trust": "Untrusted folders ignore .gemini/settings.json, .gemini/.env, hooks and commands; accept the trust dialog or run /permissions.",
        "docs": "https://geminicli.com/docs/reference/configuration/",
        "confidence": "high",
    },
    "cursor": {
        "title": "Cursor", "vendor": "Anysphere", "kind": "ide", "aliases": ["cursor-ide"],
        "rules": {"style": "cursor", "dir": ".cursor/rules", "ext": ".mdc"},
        "skills_dirs": [".claude/skills", ".agents/skills"],
        "agents": {"dir": ".cursor/agents", "style": "cursor"},
        "commands": {"dir": ".cursor/commands", "style": "md", "ext": ".md", "confidence": "medium"},
        "mcp": {"file": ".cursor/mcp.json", "style": "cursor"},
        "hooks": {"style": "cursor", "file": ".cursor/hooks.json"},
        "ignore": {"file": ".cursorignore", "style": "gitignore",
                   "note": ".cursorignore blocks Agent/Tab/@-mentions reads (best effort; terminal/MCP cannot be blocked); .gitignore respected by default"},
        "trust": "Project hooks and MCP run only in a trusted workspace (Workspace Trust prompt on open).",
        "docs": "https://cursor.com/docs/context/rules",
        "confidence": "high",
    },
    "copilot": {
        "title": "GitHub Copilot (CLI, VS Code agent, coding agent)", "vendor": "GitHub", "kind": "cli",
        "aliases": ["github-copilot", "copilot-cli", "gh-copilot"],
        "rules": {"style": "copilot", "dir": ".github/instructions", "ext": ".instructions.md"},
        "skills_dirs": [".claude/skills", ".agents/skills"],
        "agents": {"dir": ".github/agents", "style": "copilot", "ext": ".agent.md"},
        "commands": {"dir": ".github/prompts", "style": "prompt-md", "ext": ".prompt.md", "confidence": "medium"},
        "mcp": {"file": ".github/mcp.json", "style": "copilot",
                "note": "Copilot CLI/coding agent read .github/mcp.json (and .mcp.json); VS Code Copilot reads .vscode/mcp.json (written by the vscode target)"},
        "hooks": {"style": "copilot", "file": ".github/hooks/ai-sandbox.json"},
        "ignore": {"file": None, "style": "none",
                   "note": "Copilot content exclusion is configured by repository/organization administrators (GitHub settings), not by a project file"},
        "trust": "Copilot CLI asks to trust the folder on first start (stored in ~/.copilot/config.json).",
        "docs": "https://docs.github.com/en/copilot/reference/hooks-reference",
        "confidence": "high",
    },
    "vscode": {
        "title": "VS Code (editor settings, terminal env, tasks)", "vendor": "Microsoft", "kind": "ide",
        "aliases": ["code", "visual-studio-code"],
        "rules": {"style": "none"}, "skills_dirs": [], "agents": None, "commands": None,
        "mcp": {"file": ".vscode/mcp.json", "style": "vscode"},
        "hooks": None,
        "ignore": {"file": None, "style": "vscode-settings",
                   "note": "files.exclude / search.exclude / files.watcherExclude in .vscode/settings.json"},
        "trust": "Restricted Mode (untrusted workspace) ignores workspace settings, tasks and the terminal env.",
        "docs": "https://code.visualstudio.com/docs/editing/workspaces/workspace-trust",
        "confidence": "high",
    },
    "windsurf": {
        "title": "Windsurf / Devin Desktop (Cascade)", "vendor": "Cognition", "kind": "ide", "aliases": ["devin", "cascade", "codeium", "devin-desktop"],
        "rules": {"style": "windsurf", "dir": ".devin/rules", "ext": ".md", "legacy_dir": ".windsurf/rules"},
        "skills_dirs": [],
        "agents": None,
        "commands": {"dir": ".devin/workflows", "style": "workflow-md", "ext": ".md", "legacy_dir": ".windsurf/workflows"},
        "mcp": {"file": None, "style": "windsurf", "sidecar": ".ai-sandbox/mcp/devin.mcp_config.json",
                "note": "Devin Desktop/Windsurf read MCP servers only from the global mcp_config.json (~/.config/devin or ~/.codeium/windsurf); aisb writes a sidecar you can paste"},
        "hooks": {"style": "windsurf", "file": ".devin/hooks.json", "legacy_file": ".windsurf/hooks.json"},
        "ignore": {"file": ".devinignore", "style": "gitignore", "extra": {".codeiumignore": "legacy name, still read by older Windsurf builds"},
                   "note": ".devinignore (legacy .windsurfignore/.codeiumignore still read); .gitignore respected"},
        "trust": "Workspace rules are limited to 12,000 characters per file. Windsurf was renamed Devin Desktop in 2026; both layouts are written.",
        "docs": "https://docs.devin.ai/desktop/cascade/memories",
        "confidence": "high",
    },
    "antigravity": {
        "title": "Google Antigravity (App, IDE, CLI)", "vendor": "Google", "kind": "ide", "aliases": ["ag", "agy", "antigravity-ide"],
        "rules": {"style": "antigravity", "dir": ".agents/rules", "ext": ".md"},
        "skills_dirs": [".agents/skills"],
        "agents": {"dir": ".agents/agents", "style": "antigravity"},
        "commands": None,  # workflows were retired in Oct 2026 in favour of skills
        "mcp": {"file": ".agents/mcp_config.json", "style": "antigravity"},
        "hooks": {"style": "antigravity", "file": ".agents/hooks.json"},
        "ignore": {"file": ".antigravityignore", "style": "gitignore",
                   "note": "Antigravity's documented exclusion is Strict Mode + .gitignore; .antigravityignore is widely used but not in the official docs",
                   "confidence": "medium"},
        "trust": "Keep 'Terminal Command Auto Execution' on Request Review (or Proceed in Sandbox); never 'Always Proceed'.",
        "docs": "https://www.antigravity.google/docs/rules",
        "confidence": "high",
    },
    # ---- optional extras: rules + ignore only ------------------------------------------------
    "cline": {"title": "Cline", "vendor": "Cline Bot", "kind": "extension", "aliases": [],
              "rules": {"style": "dir-md", "dir": ".clinerules", "ext": ".md"}, "skills_dirs": [], "agents": None, "commands": None,
              "mcp": {"file": None, "style": "none", "note": "Cline stores MCP servers globally (cline_mcp_settings.json)"},
              "hooks": None, "ignore": {"file": ".clineignore", "style": "gitignore"}, "trust": "", "docs": "https://docs.cline.bot/features/cline-rules", "confidence": "high"},
    "roo": {"title": "Roo Code", "vendor": "Roo Code", "kind": "extension", "aliases": ["roo-code", "roocode"],
            "rules": {"style": "dir-md", "dir": ".roo/rules", "ext": ".md"}, "skills_dirs": [], "agents": None, "commands": None,
            "mcp": {"file": ".roo/mcp.json", "style": "mcpservers"}, "hooks": None,
            "ignore": {"file": ".rooignore", "style": "gitignore"}, "trust": "", "docs": "https://roocodeinc.github.io/Roo-Code/features/custom-instructions/", "confidence": "high"},
    "kiro": {"title": "Kiro", "vendor": "AWS", "kind": "ide", "aliases": [],
             "rules": {"style": "kiro", "dir": ".kiro/steering", "ext": ".md"}, "skills_dirs": [], "agents": None, "commands": None,
             "mcp": {"file": ".kiro/settings/mcp.json", "style": "mcpservers"}, "hooks": None,
             "ignore": {"file": ".kiroignore", "style": "gitignore", "note": ".kiroignore (nested files allowed)"}, "trust": "", "docs": "https://kiro.dev/docs/kiroignore/", "confidence": "high"},
    "junie": {"title": "JetBrains Junie", "vendor": "JetBrains", "kind": "ide", "aliases": ["jetbrains"],
              "rules": {"style": "block-md", "file": ".junie/guidelines.md"}, "skills_dirs": [], "agents": None, "commands": None,
              "mcp": {"file": ".junie/mcp/mcp.json", "style": "mcpservers"}, "hooks": None,
              "ignore": {"file": ".aiignore", "style": "gitignore", "note": "JetBrains AI Assistant/Junie honour .aiignore"}, "trust": "", "docs": "https://junie.jetbrains.com/docs/guidelines-and-memory.html", "confidence": "medium"},
    "amazonq": {"title": "Amazon Q Developer", "vendor": "AWS", "kind": "extension", "aliases": ["amazon-q", "q"],
                "rules": {"style": "dir-md", "dir": ".amazonq/rules", "ext": ".md"}, "skills_dirs": [], "agents": None, "commands": None,
                "mcp": {"file": None, "style": "none"}, "hooks": None, "ignore": {"file": None, "style": "none"}, "trust": "",
                "docs": "https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/context-project-rules.html", "confidence": "high"},
    "continue": {"title": "Continue", "vendor": "Continue", "kind": "extension", "aliases": [],
                 "rules": {"style": "continue", "dir": ".continue/rules", "ext": ".md"}, "skills_dirs": [], "agents": None, "commands": None,
                 "mcp": {"file": None, "style": "none", "note": "Continue uses .continue/mcpServers/*.yaml"}, "hooks": None,
                 "ignore": {"file": ".continueignore", "style": "gitignore"}, "trust": "", "docs": "https://docs.continue.dev/customize/deep-dives/rules", "confidence": "high"},
    "zed": {"title": "Zed", "vendor": "Zed Industries", "kind": "ide", "aliases": [],
            "rules": {"style": "block-md", "file": ".rules"}, "skills_dirs": [], "agents": None, "commands": None,
            "mcp": {"file": ".zed/settings.json", "style": "zed", "confidence": "medium"}, "hooks": None,
            "ignore": {"file": None, "style": "zed-settings", "note": "Zed uses private_files / file_scan_exclusions in .zed/settings.json"}, "trust": "", "docs": "https://zed.dev/docs/ai/rules", "confidence": "high"},
    "codex": {"title": "OpenAI Codex CLI", "vendor": "OpenAI", "kind": "cli", "aliases": ["codex-cli"],
              "rules": {"style": "agents-md-only"}, "skills_dirs": [".codex/skills"], "agents": {"dir": ".codex/agents", "style": "claude", "confidence": "medium"}, "commands": None,
              "mcp": {"file": ".codex/config.toml", "style": "codex-toml"}, "hooks": None,
              "ignore": {"file": None, "style": "none"}, "trust": "Project .codex/config.toml loads only after the project is trusted.", "docs": "https://developers.openai.com/codex", "confidence": "medium"},
    "aider": {"title": "Aider", "vendor": "Aider", "kind": "cli", "aliases": [],
              "rules": {"style": "block-md", "file": "CONVENTIONS.md"}, "skills_dirs": [], "agents": None, "commands": None,
              "mcp": {"file": None, "style": "none"}, "hooks": None,
              "ignore": {"file": ".aiderignore", "style": "gitignore"}, "trust": "", "docs": "https://aider.chat/docs/usage/conventions.html", "confidence": "high"},
}

EXTRA_TOOLS = [t for t in TARGETS if t not in DEFAULT_TOOLS]
ALL_TOOLS = list(TARGETS.keys())


def resolve(name):
    """Map a user-typed target name/alias to a target id, or None."""
    n = (name or "").strip().lower()
    if n in TARGETS:
        return n
    for tid, t in TARGETS.items():
        if n in [a.lower() for a in t.get("aliases", [])] or n == t["title"].lower():
            return tid
    return None


def parse_tool_list(spec):
    if spec is None:
        return list(DEFAULT_TOOLS)
    spec = spec.strip()
    if spec in ("all", "*"):
        return list(ALL_TOOLS)
    out, unknown = [], []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        tid = resolve(part)
        if tid:
            if tid not in out:
                out.append(tid)
        else:
            unknown.append(part)
    return out if not unknown else (out, unknown)
