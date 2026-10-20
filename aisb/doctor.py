# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""`aisb doctor <target>`: one command per tool. Local, reversible fixes are applied inside the project
(with --fix); anything that lives outside the project (caches, app state, IDE commands) is PRINTED with exact paths
and steps for you to do yourself - aisb never touches global state."""
from __future__ import annotations

import os
import shutil

from .common import dump_json, load_json, read_text
from .manifest import Manifest
from .ssot import SSOT
from .targets import TARGETS, resolve


def _paths(host, posix, mac, win):
    if host.is_windows:
        return [os.path.expandvars(p) for p in win]
    if host.is_mac:
        return [os.path.expanduser(p) for p in mac]
    return [os.path.expanduser(p) for p in posix]


def _size(path):
    total = 0
    try:
        for base, _d, files in os.walk(path):
            for fn in files:
                try:
                    total += os.path.getsize(os.path.join(base, fn))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _fmt(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.0f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n


# Per-tool playbooks. Each step: (kind, text) where kind is 'local' (aisb can do it with --fix) or 'manual'.
def playbook(tid, host, root):
    steps = []
    ign = TARGETS[tid].get("ignore") or {}
    if ign.get("file") or ign.get("style") in ("claude-deny", "vscode-settings", "zed-settings"):
        steps.append(("local", "context", "Optimize project context: write %s so huge folders (node_modules, dist, build, caches) are not indexed/read. Run: aisb context %s"
                      % (ign.get("file") or "the exclusion settings", tid)))
    steps.append(("local", "mcp", "Disable heavy MCP servers for this project while debugging: aisb doctor %s --disable-mcp <name,...>  (re-enable with aisb add mcp ... or edit .ai-sandbox/mcp/servers.json)" % tid))
    steps.append(("local", "logs", "Rotate the sandbox audit logs if they are large (.ai-sandbox/logs)."))
    steps.append(("local", "configs", "Validate every generated config file for this tool (JSON parse, hook paths exist)."))
    if tid == "antigravity":
        steps += [
            ("manual", "fresh-chat", "Start a fresh conversation: Ctrl+N (Windows/Linux) or Cmd+N (macOS). Very long multi-turn histories make the model time out."),
            ("manual", "model", "Switch models temporarily: pick a Flash variant (e.g. Gemini Flash) in the model selector under the prompt box, send one short message to force a reset, then switch back to the Pro/Opus model."),
            ("manual", "reset-onboarding", "Reset the language-server/onboarding state: Command Palette (Ctrl+Shift+P / Cmd+Shift+P) -> 'Antigravity: Reset Onboarding'. Also useful: 'Developer: Reload Window', 'MCP: Restart All Servers'."),
            ("manual", "antivirus", "Windows: make sure your antivirus has not quarantined the Antigravity language server (prompts hang on 'Working...'). Typical path: %LOCALAPPDATA%\\Programs\\Antigravity IDE\\resources\\app\\extensions\\antigravity\\bin\\language_server_windows_x64.exe - add an exclusion or restore it."),
            ("manual", "cache", "Clear the app cache/logs yourself if problems persist (these are OUTSIDE the project; aisb will not delete them):"),
            ("manual", "terminal-policy", "Keep 'Terminal Command Auto Execution' on Request Review or Proceed in Sandbox (Settings > Agent). 'Always Proceed' bypasses review."),
        ]
    elif tid == "cursor":
        steps += [
            ("manual", "fresh-chat", "Start a new chat (Cmd/Ctrl+N in the Agent pane) when a long conversation degrades or stalls."),
            ("manual", "indexing", "Re-index after large changes: Cursor Settings > Indexing & Docs > Resync Index. .cursorignore keeps node_modules etc. out."),
            ("manual", "run-mode", "Check Agent run mode: prefer Auto-review or Allowlist; never 'Run Everything' with project hooks disabled."),
            ("manual", "cache", "If the app itself misbehaves, clear its cache/logs yourself (OUTSIDE the project):"),
        ]
    elif tid == "claude":
        steps += [
            ("manual", "doctor", "Run `claude doctor` for the merged settings view and `claude --debug` to see hook stderr."),
            ("manual", "compact", "Long sessions: use /compact or start a new session; check /hooks and /permissions show the project rules."),
            ("manual", "trust", "If project hooks never fire: the folder is not trusted or ~/.claude/settings.json sets disableAllHooks."),
        ]
    elif tid == "gemini":
        steps += [
            ("manual", "memory", "Run /memory show to confirm GEMINI.md imports loaded; /hooks panel to see hook status; /permissions to trust the folder."),
            ("manual", "fresh-chat", "Start a new session (/clear) when the context is saturated."),
        ]
    elif tid == "copilot":
        steps += [
            ("manual", "session", "Copilot CLI: /permissions show; VS Code: Chat > Settings > verify 'Use hooks', 'Use AGENTS.md', 'Use Agent Skills' are on."),
            ("manual", "fresh-chat", "Start a new chat when the agent loops or times out; long histories degrade tool calls."),
        ]
    elif tid == "windsurf":
        steps += [
            ("manual", "fresh-chat", "Start a new Cascade conversation; Cascade keeps a per-conversation memory that grows."),
            ("manual", "mcp", "Devin/Windsurf keep MCP servers in a GLOBAL mcp_config.json (max 100 tools). Disable unused servers there yourself."),
        ]
    elif tid == "vscode":
        steps += [("manual", "reload", "Developer: Reload Window; check Workspace Trust (Restricted Mode disables workspace settings, tasks and terminal env).")]
    else:
        steps += [("manual", "fresh-chat", "Start a fresh conversation; check the tool's documentation for its rules/ignore file support: %s" % TARGETS[tid].get("docs", ""))]
    return steps


def cache_locations(tid, host):
    """Known app cache/log/state directories (printed only; never modified)."""
    if tid == "antigravity":
        return _paths(host,
                      ["~/.gemini/antigravity", "~/.gemini/antigravity-ide", "~/.gemini/antigravity-cli", "~/.config/Antigravity", "~/.config/Antigravity/logs"],
                      ["~/.gemini/antigravity", "~/.gemini/antigravity-ide", "~/Library/Application Support/Antigravity", "~/Library/Logs/Antigravity"],
                      ["%USERPROFILE%\\.gemini\\antigravity", "%USERPROFILE%\\.gemini\\antigravity-ide", "%APPDATA%\\Antigravity", "%LOCALAPPDATA%\\Programs\\Antigravity IDE"])
    if tid == "cursor":
        return _paths(host, ["~/.config/Cursor", "~/.cursor"], ["~/Library/Application Support/Cursor", "~/Library/Logs/Cursor", "~/.cursor"],
                      ["%APPDATA%\\Cursor", "%LOCALAPPDATA%\\Programs\\cursor", "%USERPROFILE%\\.cursor"])
    if tid == "claude":
        return _paths(host, ["~/.claude", "~/.claude.json"], ["~/.claude", "~/.claude.json"], ["%USERPROFILE%\\.claude", "%USERPROFILE%\\.claude.json"])
    if tid == "gemini":
        return _paths(host, ["~/.gemini"], ["~/.gemini"], ["%USERPROFILE%\\.gemini"])
    if tid == "copilot":
        return _paths(host, ["~/.copilot"], ["~/.copilot"], ["%USERPROFILE%\\.copilot"])
    if tid == "windsurf":
        return _paths(host, ["~/.codeium", "~/.config/devin", "~/.config/Windsurf"], ["~/.codeium", "~/Library/Application Support/Windsurf", "~/Library/Application Support/devin"],
                      ["%USERPROFILE%\\.codeium", "%APPDATA%\\Windsurf", "%APPDATA%\\devin"])
    if tid == "vscode":
        return _paths(host, ["~/.config/Code", "~/.vscode"], ["~/Library/Application Support/Code", "~/.vscode"], ["%APPDATA%\\Code", "%USERPROFILE%\\.vscode"])
    return []


def cmd_doctor(root, host, log, args):
    tid = resolve(args.target)
    if not tid:
        log.fail("unknown target %s (run `aisb targets`)" % args.target)
        return 2
    P = log.plain
    m = Manifest(root)
    T = TARGETS[tid]["title"]
    P("aisb doctor %s  -  %s" % (tid, T))
    P("=" * 72)
    installed = m.exists and tid in (m.data.get("tools") or [])
    if not m.exists:
        log.warn("the sandbox is not installed in %s (run `aisb init`); only generic advice follows" % root)
    elif not installed:
        log.warn("%s is not among this project's targets (%s); run `aisb sync --tools %s,%s`" % (tid, ",".join(m.data.get("tools", [])), ",".join(m.data.get("tools", [])), tid))
    steps = playbook(tid, host, root)
    fixes_applied = 0
    P("")
    P("LOCAL (inside this project - aisb can do these%s)" % ("" if args.fix else "; pass --fix to apply"))
    for kind, key, text in steps:
        if kind != "local":
            continue
        P("  [ ] " + text)
        if not args.fix:
            continue
        if key == "context":
            from types import SimpleNamespace
            from .context import cmd_context
            cmd_context(root, host, log, SimpleNamespace(target=tid, groups=None, add=[], dry_run=False))
            fixes_applied += 1
        elif key == "logs":
            fixes_applied += _rotate_logs(root, log)
        elif key == "configs":
            fixes_applied += _validate_configs(root, tid, log)
    if args.disable_mcp:
        s = SSOT(root)
        servers = s.mcp_all()
        changed = []
        for name in [n.strip() for n in args.disable_mcp.split(",") if n.strip()]:
            if name in servers:
                servers[name]["enabled"] = False
                changed.append(name)
            else:
                log.warn("no MCP server named %s in .ai-sandbox/mcp/servers.json" % name)
        if changed:
            s.save_mcp(servers)
            log.done("mcp        disabled %s (run `aisb sync` to update the tool configs; re-enable by editing servers.json)" % ", ".join(changed))
            fixes_applied += 1
    P("")
    P("MANUAL (outside this project - aisb never touches these; do them yourself if needed)")
    for kind, key, text in steps:
        if kind != "manual":
            continue
        P("  - " + text)
        if key == "cache":
            for p in cache_locations(tid, host):
                exists = os.path.exists(p)
                P("        %s%s" % (p, "  (%s)" % _fmt(_size(p)) if exists and os.path.isdir(p) else ("" if exists else "  (not present)")))
    # project-side facts for this tool
    P("")
    P("PROJECT FACTS")
    t = TARGETS[tid]
    ign = t.get("ignore") or {}
    if ign.get("file"):
        P("  ignore file     %s %s" % (ign["file"], "present" if os.path.exists(os.path.join(root, ign["file"])) else "MISSING (aisb context %s)" % tid))
    hooks = t.get("hooks") or {}
    if hooks.get("file"):
        P("  hooks file      %s %s" % (hooks["file"], "present" if os.path.exists(os.path.join(root, *hooks["file"].split("/"))) else "missing"))
    mcp = t.get("mcp") or {}
    if mcp.get("file"):
        P("  mcp file        %s %s" % (mcp["file"], "present" if os.path.exists(os.path.join(root, *mcp["file"].split("/"))) else "none (no MCP servers added)"))
    elif mcp.get("sidecar"):
        P("  mcp             global-only for this tool; sidecar %s" % mcp["sidecar"])
    s = SSOT(root) if m.exists else None
    if s:
        servers = s.mcp_all()
        if servers:
            P("  mcp servers     " + ", ".join("%s%s" % (n, "" if v.get("enabled", True) else " (disabled)") for n, v in servers.items()))
    if t.get("trust"):
        P("  trust note      %s" % t["trust"])
    P("  docs            %s" % t.get("docs", ""))
    if args.fix:
        log.done("doctor     %d local fix(es) applied; run `aisb sync` if MCP servers changed" % fixes_applied)
    return 0


def _rotate_logs(root, log):
    d = os.path.join(root, ".ai-sandbox", "logs")
    n = 0
    for fn in ("audit.log", "audit.jsonl", "aisb.log"):
        p = os.path.join(d, fn)
        if os.path.isfile(p) and os.path.getsize(p) > 5 * 1024 * 1024:
            for i in (3, 2, 1):
                src = p if i == 1 else p + ".%d" % (i - 1)
                dst = p + ".%d" % i
                if os.path.exists(src):
                    if os.path.exists(dst):
                        os.remove(dst)
                    os.replace(src, dst)
            open(p, "a").close()
            log.done("logs       rotated %s" % fn)
            n += 1
    if not n:
        log.info("logs       nothing to rotate (all under 5 MB)")
    return n


def _validate_configs(root, tid, log):
    t = TARGETS[tid]
    files = []
    for key in ("hooks", "mcp"):
        f = (t.get(key) or {}).get("file")
        if f:
            files.append(f)
    extra = {"claude": [".claude/settings.json", ".claude/settings.local.json", ".mcp.json"], "gemini": [".gemini/settings.json"],
             "cursor": [".cursor/hooks.json", ".cursor/mcp.json"], "vscode": [".vscode/settings.json", ".vscode/tasks.json", ".vscode/mcp.json"],
             "copilot": [".github/hooks/ai-sandbox.json", ".github/mcp.json"], "antigravity": [".agents/hooks.json", ".agents/mcp_config.json"],
             "windsurf": [".devin/hooks.json", ".windsurf/hooks.json"]}.get(tid, [])
    bad = 0
    for rel in sorted(set(files + extra)):
        p = os.path.join(root, *rel.split("/"))
        if not os.path.isfile(p):
            continue
        data = load_json(p, None)
        if data is None:
            log.fail("config     %s is not valid JSON" % rel)
            bad += 1
            continue
        # hook commands must point at existing files when they are paths
        text = read_text(p)
        for token in (".ai-sandbox/hooks/sandbox_guard.py", ".ai-sandbox/bin/aisb-bin/aisb", ".venv/bin/python", ".venv/Scripts/python.exe"):
            if token in text and not os.path.exists(os.path.join(root, *token.split("/"))):
                if token.startswith(".venv") and (m_rt(root) == "binary"):
                    continue
                log.warn("config     %s references %s which does not exist (run `aisb sync`)" % (rel, token))
    if not bad:
        log.ok("config     %s configuration files parse" % tid)
    return 1
    _ = dump_json, shutil


def m_rt(root):
    return (Manifest(root).data.get("runtime") or {}).get("mode")
