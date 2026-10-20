# Bundles and profiles — shipping an agentic setup

A **bundle** is a folder (or `.aisb.zip`) that carries rules, skills, agents, commands, hooks and MCP
servers. A **profile** is a recipe: a list of sources to import plus inline components. Both land in the
project's `.ai-sandbox/` and are fanned out to every tool by `aisb sync`. Nothing is installed globally.

```bash
aisb apply <source> [--name X] [--only skills,commands] [--plugin a,b|all] [--yes] [--enable-mcp]
aisb list bundles
aisb remove bundle <name>
aisb pack [--name X] [--out file.aisb.zip] [--description "..."] [--include-policy]
```

## Sources `aisb apply` understands

| Source | Example |
|---|---|
| Built-in profile | `profile:design`, `profile:motion-design`, `profile:boris-workflow`, `profile:voice`, `profile:knowledge-work`, `profile:gstack` |
| Local directory or zip | `./team-setup`, `../shared/design-studio.aisb.zip` |
| GitHub | `github:owner/repo`, `github:owner/repo/sub/dir`, `github:owner/repo@branch`, `https://github.com/owner/repo/tree/main/skills/x` |
| Any git / zip URL | `https://example.com/setup.git`, `https://example.com/setup.zip` |
| Plugin from a known marketplace | `sales@knowledge-work-plugins`, `ui-ux-pro-max@ui-ux-pro-max-skill` |

Fetching happens **into the project** (`.ai-sandbox/bundles/_src/<name>`, git-ignored) with `git clone --depth 1`
or a zip download — never into `~/.claude` or any global location.

## Layouts recognised

1. **aisb bundle** – `aisb-bundle.json` + `rules/ skills/ agents/ commands/ hooks.d/ mcp/servers.json` (what `aisb pack` produces).
2. **Claude Code plugin** – `.claude-plugin/plugin.json` and/or `skills/`, `commands/`, `agents/`, `hooks/hooks.json`, `.mcp.json`.
3. **Claude Code marketplace** – `.claude-plugin/marketplace.json`. Single-plugin marketplaces import directly; otherwise
   pick with `--plugin a,b` or `--plugin all`. Remote plugin sources (`github`, `url`, `git-subdir`) are fetched; `npm`/`archive`/`command` sources are skipped with a note.
4. **Skill tree** – any repository with `SKILL.md` folders (ui-skills, Vercel agent-skills, designer-skills, gstack …) plus optional root `commands/` and `agents/`.
5. **Single skill** – a folder whose root is a `SKILL.md`.

What happens on import:

- Skills keep their names; a name clash becomes `<bundle>-<skill>`. The folder name is forced to match the frontmatter `name` (tools require it).
- Plugin commands from marketplaces are namespaced (`/plugin:command`, as Claude Code does); direct imports are not.
- Hooks are imported **only with `--yes`** (they run commands). `${CLAUDE_PLUGIN_ROOT}` is rewritten to the bundle's source folder.
- MCP servers are imported **disabled** unless `--enable-mcp`.
- The license is detected (`LICENSE*`, `COPYING`, README "License" section) and shown; "none" is a warning — you may use it locally but perhaps not redistribute it.
- Everything is recorded in `.ai-sandbox/bundles/bundles.lock.json`; re-applying a bundle replaces its previous components (safe update); `aisb remove bundle` removes exactly them.

## Built-in profiles

| Profile | Contents |
|---|---|
| `design` | ui-skills (ibelick, MIT), claude-design-skills (MIT: skills + `/design-review` commands + agent), Anthropic `frontend-design` (Apache-2.0), designer-skills (Apache-2.0), Vercel agent-skills (MIT), UI/UX Pro Max (MIT), Impeccable (Apache-2.0); MCP: Playwright, Chrome DevTools; rule `design-workflow` |
| `motion-design` | Remotion skills, HyperFrames skills, claude-animation plugin; MCP: Playwright; rule `motion-studio-setup` (the project-local equivalent of the popular "motion design studio" course: no `brew`, no `-g`, ffmpeg via `ffmpeg-static` or `imageio-ffmpeg`); command `/motion-reel` |
| `boris-workflow` | Original material inspired by how Boris Cherny works with Claude Code: `working-agreement` rule (plan, verify, keep CLAUDE.md honest), agents `readonly-reviewer`, `build-validator`, `code-simplifier`, command `/commit-push-pr` |
| `voice` | rules `dictation` (how to interpret spoken input) and `voice-mode` (how to answer when the user talks); Claude Code `voice` settings enabled in `.claude/settings.local.json` |
| `knowledge-work` | Anthropic knowledge-work-plugins marketplace (Apache-2.0): `productivity`, `engineering`, `design` by default |
| `gstack` | gstack skill documents only (MIT). gstack's own `./setup` is global by design and is not run |

Profiles live in `aisb/profiles/*.json`. Contribute one with sources whose licenses allow redistribution.

## Writing your own bundle

Option A — just work in a sandboxed project and run `aisb pack`:

```bash
aisb add rule working-agreement --text "..."
aisb add skill ./my-skill
aisb add command release-notes --from ./release-notes.md
aisb add mcp docs --command "npx -y @upstash/context7-mcp"
aisb pack --name team-setup --description "How we ship"
# -> team-setup.aisb.zip ; share it, or unzip it into a repo and let people `aisb apply github:you/team-setup`
```

The archive contains `aisb-bundle.json` (name, version, components, provenance of imported third-party
content), the component folders, and `mcp/servers.json` with secrets replaced by `${VAR}` placeholders.
`--include-policy` also ships your `policy.json` (custom deny/ask rules).

Option B — write the folder by hand (or make it a Claude Code plugin; both import the same way):

```text
team-setup/
├── aisb-bundle.json      {"name": "team-setup", "version": "1", "description": "...", "notes": ["..."]}
├── rules/working-agreement.md
├── skills/release-notes/SKILL.md
├── agents/readonly-reviewer.md
├── commands/release/notes.md          -> /release:notes
├── hooks.d/format.json                {"event":"post-tool","matcher":"Write|Edit","command":"npx prettier --write .","timeout":30}
├── mcp/servers.json                   {"servers": {"docs": {"transport":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}}}
└── LICENSE
```

## Importing the well-known setups

| Setup | Command | Notes |
|---|---|---|
| How Boris uses Claude Code (prose site) | `aisb apply profile:boris-workflow` | our own distilled starter; adapt `rules/working-agreement.md` to your build/test commands |
| garrytan/gstack | `aisb apply profile:gstack` | 57 skill documents; the Bun-based helper binaries and `~/.claude` hooks that `./setup` installs are global and intentionally skipped |
| anthropics/knowledge-work-plugins | `aisb apply sales@knowledge-work-plugins` or `aisb apply github:anthropics/knowledge-work-plugins --plugin sales,legal` | MCP connectors imported disabled; enable the ones you use |
| ui-skills.com | `aisb apply github:ibelick/ui-skills` | the `npx ui-skills` CLI only prints skills; aisb copies them into the project |
| claude-design-skills | `aisb apply github:Gustavosilveira23/claude-design-skills` | skills + `/design-review` commands + agent; its README's `~/.claude` copy steps are replaced by project-local copies |
| The "motion design studio" course | `aisb apply profile:motion-design` | `brew install …`, `pip install …`, `npx skills add … -g`, `claude plugin install` become project-local equivalents |
