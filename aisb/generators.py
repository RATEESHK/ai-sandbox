# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Per-target file generation from the SSOT (rules, skills, agents, commands, hooks.d, MCP servers) plus the
sandbox core for each tool (settings, permissions, guard hooks, env)."""
from __future__ import annotations

import os

from .common import MARK_HASH, MARK_MD, dump_json, read_text, render_frontmatter
from .targets import TARGETS
from .templates import GEMINI_CMD_AUDIT, GEMINI_CMD_LOG


def _toml_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_multiline(s):
    return '"""\n' + str(s).replace('"""', '\\"""').rstrip("\n") + '\n"""'


class Generators:
    """Stateless helpers bound to an Installer (uses its writer, host, env, SSOT and hook-command builders)."""

    def __init__(self, inst):
        self.i = inst
        self.w = inst.w
        self.h = inst.host
        self.ssot = inst.ssot
        self.log = inst.log

    # ======================================================================================
    # Cross-tool pieces
    # ======================================================================================
    def universal(self):
        """AGENTS.md (full rules), .agents/skills (the cross-tool skills location read by Cursor, Copilot/VS Code,
        Gemini CLI, Antigravity and Codex), .gitignore block.  Claude Code gets its own copy under .claude/skills."""
        w = self.w
        rules = [r for r in self.ssot.rules() if r.always]
        body = "\n\n".join(("# [%s]\n" % r.name if r.name != "sandbox-policy" else "") + r.body.strip("\n") for r in rules)
        w.put_block("AGENTS.md", body, MARK_MD,
                    label="AGENTS.md  (read by Codex, Cursor, Copilot, Windsurf, Antigravity, Zed, Jules, Amp, Kiro, Roo, Cline ...)")
        self._fan_out_skills([".agents/skills"])
        self._gitignore()

    def _gitignore(self):
        body = "\n".join([
            ".venv/", ".ai-sandbox/cache/", ".ai-sandbox/logs/", ".ai-sandbox/home/", ".ai-sandbox/backup/",
            ".ai-sandbox/runtime/", ".ai-sandbox/bin/aisb-bin/", ".ai-sandbox/bundles/_src/",
            ".ai-sandbox/manifest.json", ".ai-sandbox/sandbox.env", ".ai-sandbox/policy.local.json",
            ".ai-sandbox/bin/activate.cmd", ".ai-sandbox/bin/activate.ps1",
            ".claude/settings.local.json", ".gemini/.env", ".github/copilot/settings.local.json", ".agents/hooks.json", ".envrc",
        ])
        self.w.put_block(".gitignore", body, MARK_HASH)

    def _fan_out_skills(self, dirs):
        for sk in self.ssot.skills():
            for d in dirs:
                self._copy_tree(sk.path, "%s/%s" % (d, sk.name))

    def _copy_tree(self, src_dir, dst_rel):
        """Copy a component directory (text files) under tracking. Binary files are copied as bytes."""
        for base, _dirs, files in os.walk(src_dir):
            for fn in files:
                src = os.path.join(base, fn)
                rel = os.path.relpath(src, src_dir).replace("\\", "/")
                dst = dst_rel + "/" + rel
                try:
                    self.w.put(dst, read_text(src), label=dst)
                except UnicodeDecodeError:
                    with open(src, "rb") as fh:
                        self.w.put_bytes(dst, fh.read(), label=dst)

    # ---- rules -------------------------------------------------------------------------
    def rules_for(self, tid):
        return [r for r in self.ssot.rules() if r.applies_to(tid)]

    def _rule_block(self, r, style):
        """Render one rule for a target style."""
        if style == "cursor":
            fm = {"description": r.description or ("Project rule: %s" % r.name)}
            if r.globs:
                fm["globs"] = ", ".join(r.globs)
                fm["alwaysApply"] = False
            else:
                fm["alwaysApply"] = bool(r.always)
            return render_frontmatter(fm) + "\n" + r.body.strip("\n") + "\n"
        if style == "copilot":
            fm = {"applyTo": ", ".join(r.globs) if r.globs else "**"}
            if r.description:
                fm["description"] = r.description
            return render_frontmatter(fm) + "\n" + r.body.strip("\n") + "\n"
        if style == "windsurf":
            fm = {"trigger": "glob", "globs": ", ".join(r.globs)} if r.globs else {"trigger": "always_on"}
            return render_frontmatter(fm) + "\n" + r.body.strip("\n") + "\n"
        if style == "antigravity":
            fm = {"trigger": "glob", "globs": ", ".join(r.globs)} if r.globs else {"trigger": "always_on"}
            return render_frontmatter(fm) + "\n" + r.body.strip("\n") + "\n"
        if style == "kiro":
            fm = {"inclusion": "fileMatch", "fileMatchPattern": ", ".join(r.globs)} if r.globs else {"inclusion": "always"}
            return render_frontmatter(fm) + "\n" + r.body.strip("\n") + "\n"
        if style == "continue":
            fm = {"name": r.name, "alwaysApply": not r.globs}
            if r.globs:
                fm["globs"] = r.globs
            if r.description:
                fm["description"] = r.description
            return render_frontmatter(fm) + "\n" + r.body.strip("\n") + "\n"
        if style == "claude-rules":
            fm = {"paths": r.globs} if r.globs else {}
            return (render_frontmatter(fm) + "\n" if fm else "") + r.body.strip("\n") + "\n"
        return r.body.strip("\n") + "\n"

    # ======================================================================================
    # Claude Code
    # ======================================================================================
    def claude(self):
        w, h, i = self.w, self.h, self.i
        w.ensure_dir(".claude/skills")
        w.ensure_dir(".claude/agents")
        self._fan_out_skills([".claude/skills"])
        self._agents_claude(".claude/agents")
        self._commands(".claude/commands", "md", ".md")
        # rules: CLAUDE.md imports every always-on rule; path-scoped rules go to .claude/rules/
        imports = []
        for r in self.rules_for("claude"):
            if r.globs:
                w.put(".claude/rules/%s.md" % r.name, self._rule_block(r, "claude-rules"))
            else:
                imports.append("@.ai-sandbox/rules/%s.md" % r.name)
        w.put_block("CLAUDE.md", "\n".join(imports), MARK_MD,
                    label="CLAUDE.md  (imports the policy and project rules; Claude Code reads it every session)")
        bash_deny = [
            "Bash(sudo *)", "Bash(su *)", "Bash(doas *)", "Bash(runas *)",
            "Bash(npm * -g*)", "Bash(npm * --global*)", "Bash(yarn global *)", "Bash(pnpm * -g*)", "Bash(bun * -g*)",
            "Bash(pip install * --user*)", "Bash(pip3 install * --user*)", "Bash(pipx *)", "Bash(uv tool install *)",
            "Bash(brew *)", "Bash(apt *)", "Bash(apt-get *)", "Bash(dnf *)", "Bash(yum *)", "Bash(pacman *)",
            "Bash(winget *)", "Bash(choco *)", "Bash(scoop *)", "Bash(setx *)", "Bash(reg *)",
            "Bash(git config --global *)", "Bash(git config --system *)", "Bash(crontab *)", "Bash(systemctl *)",
            "Bash(launchctl *)", "Bash(nvm *)", "Bash(corepack *)",
        ]
        home_dirs = [".ssh", ".aws", ".kube", ".gnupg", ".docker", ".azure", ".config/gcloud", ".config/gh", ".claude",
                     ".gemini", ".copilot", ".cursor", ".npm", ".cargo", ".local/share"]
        read_deny = ["Read(~/%s/**)" % d for d in home_dirs] + ["Read(~/.gitconfig)", "Read(~/.npmrc)", "Read(~/.netrc)",
                                                                 "Read(~/.bashrc)", "Read(~/.zshrc)", "Read(~/.profile)", "Read(~/.pypirc)"]
        edit_deny = ["Edit(~/%s/**)" % d for d in home_dirs] + ["Edit(~/.gitconfig)", "Edit(~/.npmrc)", "Edit(~/.netrc)",
                                                                 "Edit(~/.bashrc)", "Edit(~/.zshrc)", "Edit(~/.profile)",
                                                                 "Edit(//etc/**)", "Edit(//usr/**)", "Edit(//opt/**)", "Edit(//Library/**)", "Edit(//System/**)"]
        portable_env = {e.name: e.value for e in i.env if e.kind == "flag"}
        portable_env.update({"CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR": "1", "DISABLE_AUTOUPDATER": "1",
                             "DISABLE_TELEMETRY": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
        shared = {
            "permissions": {
                "defaultMode": "default",
                "disableBypassPermissionsMode": "disable",
                "blockReadsOutsideWorkingDirectories": True,
                "additionalDirectories": [],
                "deny": bash_deny + read_deny + edit_deny,
            },
            "env": portable_env,
            "enableAllProjectMcpServers": False,
            "autoMemoryEnabled": False,
        }
        servers = self.ssot.mcp_servers()
        if servers:
            shared["enabledMcpjsonServers"] = sorted(servers.keys())
        w.merge_json(".claude/settings.json", shared, label=".claude/settings.json  (portable: permissions, deny rules, flags)")
        # machine-specific: hooks (exec form), absolute-path env, Claude's own OS sandbox
        matcher = "Bash|PowerShell|Monitor|Write|Edit|MultiEdit|NotebookEdit|Read|Glob|Grep"

        def hook(ev):
            cmd, args = i.hook_exec("claude", ev)
            return {"type": "command", "command": cmd, "args": args, "timeout": 20}
        hooks = {
            "SessionStart": [{"hooks": [hook("session-start")]}],
            "SessionEnd": [{"hooks": [hook("session-end")]}],
            "UserPromptSubmit": [{"hooks": [hook("prompt")]}],
            "PreToolUse": [{"matcher": matcher, "hooks": [hook("pre")]}, {"matcher": "mcp__.*", "hooks": [hook("pre")]}],
            "PostToolUse": [{"matcher": matcher, "hooks": [hook("post")]}],
        }
        self._user_hooks_into(hooks, "claude")
        local = {"env": {e.name: e.value for e in i.env if e.kind != "flag"}, "hooks": hooks}
        if h.os_sandbox_capable and not i.opts.get("no_os_sandbox"):
            local["sandbox"] = {
                "enabled": True, "autoAllowBashIfSandboxed": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                "filesystem": {
                    "denyRead": ["~/.ssh", "~/.aws", "~/.kube", "~/.gnupg", "~/.docker", "~/.azure", "~/.config/gcloud",
                                 "~/.config/gh", "~/.gitconfig", "~/.npmrc", "~/.netrc", "~/.pypirc"],
                    "denyWrite": ["./.ai-sandbox/hooks", "./.ai-sandbox/policy.json", "./.ai-sandbox/policy.local.json",
                                  "./.ai-sandbox/bin", "./.cursor/hooks.json", "./.gemini/settings.json", "./.github/hooks",
                                  "./.vscode/settings.json"],
                },
                "network": {
                    "allowedDomains": ["pypi.org", "files.pythonhosted.org", "registry.npmjs.org", "registry.yarnpkg.com",
                                       "github.com", "api.github.com", "codeload.github.com", "objects.githubusercontent.com",
                                       "raw.githubusercontent.com", "proxy.golang.org", "sum.golang.org", "storage.googleapis.com",
                                       "crates.io", "static.crates.io", "index.crates.io", "rubygems.org", "repo.maven.apache.org",
                                       "plugins.gradle.org", "api.nuget.org", "registry.terraform.io", "releases.hashicorp.com",
                                       "huggingface.co", "cdn-lfs.huggingface.co", "download.pytorch.org", "playwright.azureedge.net",
                                       "cdn.playwright.dev", "localhost", "127.0.0.1"],
                    "allowLocalBinding": True,
                },
            }
            self.log.info("Claude Code OS sandbox enabled (%s). Add registries you need to sandbox.network.allowedDomains in .claude/settings.local.json."
                          % ("seatbelt" if h.is_mac else "bubblewrap+socat"))
        elif not i.opts.get("no_os_sandbox") and not i.opts.get("terse"):
            if h.is_windows:
                self.log.info("Claude Code OS sandbox: not available on native Windows (hooks + permissions enforce instead; WSL2 has it)")
            else:
                self.log.warn("Claude Code OS sandbox not enabled: install `bubblewrap` and `socat` yourself (e.g. apt/dnf), then run `aisb sync`")
        w.merge_json(".claude/settings.local.json", local, label=".claude/settings.local.json  (this machine: hooks, path env, OS sandbox)")
        if servers:
            w.merge_json(".mcp.json", {"mcpServers": self._mcp_render(servers, "claude")}, label=".mcp.json  (Claude Code project MCP servers)")

    def _agents_claude(self, dst_dir):
        for a in self.ssot.agents():
            fm = {"name": a.name, "description": a.description}
            if a.tools:
                fm["tools"] = ", ".join(a.tools)
            if a.model:
                fm["model"] = a.model
            for k in ("permissionMode", "skills", "maxTurns", "color"):
                if a.fm.get(k) is not None:
                    fm[k] = a.fm[k]
            self.w.put("%s/%s.md" % (dst_dir, a.name), render_frontmatter(fm) + "\n" + a.body.strip("\n") + "\n")

    def _commands(self, dst_dir, style, ext):
        for c in self.ssot.commands():
            # Claude Code and Gemini CLI support namespaces via sub-directories (/ns:cmd); others get ns-cmd
            rel = "%s/%s%s" % (dst_dir, c.name if style in ("md", "toml") and dst_dir.startswith((".claude", ".gemini")) else c.flat, ext)
            if style == "md":
                fm = {"description": c.description or c.name}
                if c.argument_hint:
                    fm["argument-hint"] = c.argument_hint
                for k in ("allowed-tools", "model"):
                    if c.fm.get(k):
                        fm[k] = c.fm[k]
                self.w.put(rel, render_frontmatter(fm) + "\n" + c.body.strip("\n") + "\n")
            elif style == "toml":
                body = c.body.replace("$ARGUMENTS", "{{args}}")
                self.w.put(rel, "description = %s\nprompt = %s\n" % (_toml_str(c.description or c.name), _toml_multiline(body)))
            elif style == "prompt-md":
                fm = {"description": c.description or c.name}
                self.w.put(rel, render_frontmatter(fm) + "\n" + c.body.strip("\n") + "\n")
            elif style == "workflow-md":
                fm = {"description": c.description or c.name}
                self.w.put(rel, render_frontmatter(fm) + "\n" + c.body.strip("\n") + "\n")

    # ---- user hooks (hooks.d) -----------------------------------------------------------------
    _CLAUDE_EVENTS = {"pre-tool": "PreToolUse", "post-tool": "PostToolUse", "session-start": "SessionStart",
                      "session-end": "SessionEnd", "prompt": "UserPromptSubmit", "stop": "Stop"}
    _GEMINI_EVENTS = {"pre-tool": "BeforeTool", "post-tool": "AfterTool", "session-start": "SessionStart",
                      "session-end": "SessionEnd", "prompt": "BeforeAgent", "stop": "AfterAgent"}
    _CURSOR_EVENTS = {"pre-tool": "preToolUse", "post-tool": "postToolUse", "session-start": "sessionStart",
                      "session-end": "sessionEnd", "prompt": "beforeSubmitPrompt", "stop": "stop"}
    _COPILOT_EVENTS = {"pre-tool": "preToolUse", "post-tool": "postToolUse", "session-start": "sessionStart",
                       "session-end": "sessionEnd", "prompt": "userPromptSubmitted", "stop": "agentStop"}
    _WINDSURF_EVENTS = {"pre-tool": "pre_run_command", "post-tool": "post_run_command", "prompt": "pre_user_prompt",
                        "stop": "post_cascade_response"}

    def _user_hooks_into(self, hooks, tid):
        for hk in self.ssot.hooks():
            if not hk.applies_to(tid):
                continue
            if tid == "claude":
                ev = self._CLAUDE_EVENTS.get(hk.event)
                if not ev:
                    continue
                entry = {"hooks": [{"type": "command", "command": hk.command, "timeout": hk.timeout}]}
                if hk.matcher and ev in ("PreToolUse", "PostToolUse"):
                    entry["matcher"] = hk.matcher
                hooks.setdefault(ev, []).append(entry)
            elif tid == "gemini":
                ev = self._GEMINI_EVENTS.get(hk.event)
                if not ev:
                    continue
                entry = {"hooks": [{"type": "command", "name": "user-" + hk.name, "command": hk.command, "timeout": hk.timeout * 1000}]}
                if hk.matcher and ev in ("BeforeTool", "AfterTool"):
                    entry["matcher"] = hk.matcher
                hooks.setdefault(ev, []).append(entry)
            elif tid == "cursor":
                ev = self._CURSOR_EVENTS.get(hk.event)
                if not ev:
                    continue
                entry = {"command": hk.command, "timeout": hk.timeout}
                if hk.matcher and ev in ("preToolUse", "postToolUse"):
                    entry["matcher"] = hk.matcher
                hooks.setdefault(ev, []).append(entry)
            elif tid == "copilot":
                ev = self._COPILOT_EVENTS.get(hk.event)
                if not ev:
                    continue
                entry = {"type": "command", "command": hk.command, "timeoutSec": hk.timeout}
                if hk.matcher and ev in ("preToolUse", "postToolUse"):
                    entry["matcher"] = hk.matcher
                hooks.setdefault(ev, []).append(entry)
            elif tid == "windsurf":
                ev = self._WINDSURF_EVENTS.get(hk.event)
                if not ev:
                    continue
                hooks.setdefault(ev, []).append({"command": hk.command, "show_output": False})

    # ---- MCP rendering ------------------------------------------------------------------------
    @staticmethod
    def _mcp_render(servers, style):
        """Render SSOT servers into a tool's schema. Only the fields each tool understands are emitted."""
        out = {}
        for name, s in servers.items():
            transport = (s.get("transport") or ("stdio" if s.get("command") else "http")).lower()
            if transport == "stdio":
                entry = {"command": s.get("command", "")}
                if s.get("args"):
                    entry["args"] = list(s["args"])
                if s.get("env"):
                    entry["env"] = dict(s["env"])
                if s.get("cwd") and style in ("gemini", "windsurf", "antigravity"):
                    entry["cwd"] = s["cwd"]
                if style in ("vscode", "claude"):
                    entry = dict({"type": "stdio"}, **entry)
                elif style == "copilot":
                    entry = dict({"type": "local"}, **entry)
                    if s.get("tools"):
                        entry["tools"] = list(s["tools"])
                    else:
                        entry["tools"] = ["*"]
            else:
                url = s.get("url", "")
                if style in ("claude", "vscode", "copilot"):
                    entry = {"type": "sse" if transport == "sse" else "http", "url": url}
                    if style == "copilot":
                        entry["tools"] = list(s.get("tools") or ["*"])
                elif style == "gemini":
                    entry = {"url": url} if transport == "sse" else {"httpUrl": url}
                elif style in ("windsurf", "antigravity"):
                    entry = {"serverUrl": url}
                else:  # cursor, roo, kiro, generic
                    entry = {"url": url}
                if s.get("headers"):
                    entry["headers"] = dict(s["headers"])
            if s.get("timeout") and style in ("gemini",):
                entry["timeout"] = s["timeout"]
            out[name] = entry
        return out

    # ======================================================================================
    # Gemini CLI
    # ======================================================================================
    def gemini(self):
        w, h, i = self.w, self.h, self.i
        w.ensure_dir(".gemini/agents")
        w.ensure_dir(".gemini/commands")
        for a in self.ssot.agents():
            fm = {"name": a.name, "description": a.description, "kind": "local"}
            if a.model:
                fm["model"] = a.model
            w.put(".gemini/agents/%s.md" % a.name, render_frontmatter(fm) + "\n" + a.body.strip("\n") + "\n")
        self._commands(".gemini/commands", "toml", ".toml")
        imports = ["@./.ai-sandbox/rules/%s.md" % r.name for r in self.rules_for("gemini") if r.always]
        w.put_block("GEMINI.md", "\n".join(imports), MARK_MD, label="GEMINI.md  (imports the policy and project rules)")
        pre = i.hook_shell("gemini", "%s", flavor="ps" if h.is_windows else "sh", env_root="GEMINI_PROJECT_DIR")
        verify_cmd = i.manager_shell("verify", flavor="ps" if h.is_windows else "sh")
        log_cmd = i.manager_shell("log -n 60", flavor="ps" if h.is_windows else "sh")

        def hk(event, name):
            return {"type": "command", "name": "ai-sandbox-" + name, "command": pre % event, "timeout": 20000,
                    "description": "ai-sandbox firewall + audit log"}
        tool_matcher = "run_shell_command|write_file|replace|read_file|read_many_files|list_directory|glob|grep_search|search_file_content|web_fetch|mcp_.*"
        hooks = {
            "SessionStart": [{"hooks": [hk("session-start", "session-start")]}],
            "SessionEnd": [{"hooks": [hk("session-end", "session-end")]}],
            "BeforeTool": [{"matcher": tool_matcher, "hooks": [hk("pre", "guard")]}],
            "AfterTool": [{"matcher": tool_matcher, "hooks": [hk("post", "audit")]}],
        }
        self._user_hooks_into(hooks, "gemini")
        settings = {
            "general": {"enableAutoUpdate": False, "enableAutoUpdateNotification": False},
            "context": {"fileName": "GEMINI.md", "loadMemoryFromIncludeDirectories": False,
                        "fileFiltering": {"respectGitIgnore": True, "respectGeminiIgnore": True}},
            "security": {"folderTrust": {"enabled": True}},
            "privacy": {"usageStatisticsEnabled": False},
            "telemetry": {"enabled": False},
            "tools": {"exclude": ["run_shell_command(sudo)", "run_shell_command(su )", "run_shell_command(npm install -g)",
                                  "run_shell_command(npm i -g)", "run_shell_command(pip install --user)",
                                  "run_shell_command(brew)", "run_shell_command(apt)", "run_shell_command(apt-get)",
                                  "run_shell_command(winget)", "run_shell_command(choco)", "run_shell_command(scoop)",
                                  "run_shell_command(setx)", "run_shell_command(reg )", "run_shell_command(git config --global)"]},
            "hooksConfig": {"enabled": True},
            "hooks": hooks,
        }
        servers = self.ssot.mcp_servers()
        if servers:
            settings["mcpServers"] = self._mcp_render(servers, "gemini")
        w.merge_json(".gemini/settings.json", settings, label=".gemini/settings.json  (hooks, trust, no auto-update, telemetry off, MCP)")
        env_lines = ["# ai-sandbox: loaded by Gemini CLI for THIS trusted folder (machine-specific, git-ignored)."]
        env_lines += ["%s='%s'" % (e.name, e.value.replace("'", "'\\''")) for e in i.env]
        w.put(".gemini/.env", "\n".join(env_lines) + "\n")
        w.put(".gemini/commands/sandbox/audit.toml", GEMINI_CMD_AUDIT % {"verify": verify_cmd, "log": log_cmd})
        w.put(".gemini/commands/sandbox/log.toml", GEMINI_CMD_LOG % {"log": log_cmd})

    # ======================================================================================
    # Cursor
    # ======================================================================================
    def cursor(self):
        w, h, i = self.w, self.h, self.i
        w.ensure_dir(".cursor/rules")
        for r in self.rules_for("cursor"):
            w.put(".cursor/rules/%s.mdc" % r.name, self._rule_block(r, "cursor"))
        for a in self.ssot.agents():
            fm = {"name": a.name, "description": a.description, "model": a.model or "inherit", "readonly": bool(a.fm.get("readonly", False))}
            w.put(".cursor/agents/%s.md" % a.name, render_frontmatter(fm) + "\n" + a.body.strip("\n") + "\n")
        self._commands(".cursor/commands", "md", ".md")
        shell = i.opts.get("cursor_windows_shell", "cmd")
        flavor = "ps" if (h.is_windows and shell == "powershell") else "sh"
        cmd = lambda ev: i.hook_shell("cursor", ev, flavor=flavor, relative=True)  # noqa: E731
        hooks = {
            "sessionStart": [{"command": cmd("session-start"), "timeout": 20}],
            "sessionEnd": [{"command": cmd("session-end"), "timeout": 10}],
            "beforeSubmitPrompt": [{"command": cmd("prompt"), "timeout": 10}],
            "beforeShellExecution": [{"command": cmd("pre"), "timeout": 20, "failClosed": True}],
            "beforeMCPExecution": [{"command": cmd("pre"), "timeout": 20, "failClosed": True}],
            "beforeReadFile": [{"command": cmd("pre"), "timeout": 20}],
            "afterShellExecution": [{"command": cmd("post"), "timeout": 20}],
            "afterFileEdit": [{"command": cmd("post"), "timeout": 20}],
        }
        self._user_hooks_into(hooks, "cursor")
        w.merge_json(".cursor/hooks.json", {"version": 1, "hooks": hooks}, label=".cursor/hooks.json  (relative commands; portable)")
        servers = self.ssot.mcp_servers()
        if servers:
            w.merge_json(".cursor/mcp.json", {"mcpServers": self._mcp_render(servers, "cursor")}, label=".cursor/mcp.json")

    # ======================================================================================
    # GitHub Copilot (VS Code agent, CLI, coding agent)
    # ======================================================================================
    def copilot(self):
        w, i = self.w, self.i
        w.ensure_dir(".github/hooks")
        pointer = ("# AI sandbox (mandatory)\n\n"
                   "The full, binding sandbox policy is in `AGENTS.md` at the repository root (identical to "
                   "`.ai-sandbox/rules/sandbox-policy.md`). Follow it exactly. Headlines: nothing global (no sudo, no "
                   "system/user package managers, no `-g`/`--user` installs, no global config); stay inside the workspace "
                   "(no `..`, `~`, `%USERPROFILE%`, `~/.ssh`, `~/.aws`); Python only through `./.venv` "
                   "(`.\\.venv\\Scripts\\python.exe` on Windows); isolated empty credentials for cloud/cluster CLIs; "
                   "every tool call is logged and may be blocked by the guard hook - report `AI-SANDBOX DENY/ASK` to the user, "
                   "never work around it.")
        w.put_block(".github/copilot-instructions.md", pointer, MARK_MD, label=".github/copilot-instructions.md  (pointer; AGENTS.md carries the full text)")
        for r in self.rules_for("copilot"):
            if r.name != "sandbox-policy":
                w.put(".github/instructions/%s.instructions.md" % r.name, self._rule_block(r, "copilot"))
        for a in self.ssot.agents():
            fm = {"name": a.name, "description": a.description}
            if a.tools:
                fm["tools"] = a.tools
            w.put(".github/agents/%s.agent.md" % a.name, render_frontmatter(fm) + "\n" + a.body.strip("\n") + "\n")
        self._commands(".github/prompts", "prompt-md", ".prompt.md")

        def hk(ev, timeout=20):
            return {"type": "command", "bash": i.hook_shell("copilot", ev, flavor="sh", relative=True, layout="posix"),
                    "powershell": i.hook_shell("copilot", ev, flavor="ps", relative=True), "timeoutSec": timeout}
        hooks = {"sessionStart": [hk("session-start")], "sessionEnd": [hk("session-end", 10)],
                 "userPromptSubmitted": [hk("prompt", 10)], "preToolUse": [hk("pre")], "postToolUse": [hk("post")]}
        self._user_hooks_into(hooks, "copilot")
        w.put(".github/hooks/ai-sandbox.json", dump_json({"version": 1, "hooks": hooks}))
        servers = self.ssot.mcp_servers()
        if servers:
            w.merge_json(".github/mcp.json", {"mcpServers": self._mcp_render(servers, "copilot")}, label=".github/mcp.json  (Copilot CLI / coding agent MCP servers)")

    # ======================================================================================
    # VS Code
    # ======================================================================================
    def vscode(self):
        w, i = self.w, self.i

        def env_block(sep, venv_bin):
            wf = "${workspaceFolder}"
            out = {}
            for e in i.env:
                if e.kind == "flag":
                    out[e.name] = e.value
                elif e.kind == "mixed":
                    out[e.name] = e.value.replace(i.root, wf).replace(os.sep, sep)
                else:
                    rel = os.path.relpath(e.value, i.root).replace("\\", "/")
                    out[e.name] = wf + sep + rel.replace("/", sep)
            out["VIRTUAL_ENV"] = wf + sep + ".venv"
            ps = ";" if sep == "\\" else ":"
            out["PATH"] = ps.join([wf + sep + ".venv" + sep + venv_bin, wf + sep + "node_modules" + sep + ".bin",
                                   wf + sep + ".ai-sandbox" + sep + "bin", "${env:PATH}"])
            return out
        auto = {"sudo": False, "su": False, "brew": False, "apt": False, "apt-get": False, "winget": False, "choco": False,
                "scoop": False, "setx": False, "reg": False, "pipx": False, "nvm": False, "corepack": False,
                "/\\s(-g|--global)\\b/": False, "/\\s--user\\b/": False, "/git\\s+config\\s+--(global|system)/": False,
                "/\\|\\s*(ba|z|)sh\\b/": False, "/iex\\b/i": False}
        settings = {
            "python.defaultInterpreterPath": "${workspaceFolder}/.venv",
            "python.terminal.activateEnvironment": True,
            "python.terminal.activateEnvInCurrentTerminal": True,
            "terminal.integrated.cwd": "${workspaceFolder}",
            "terminal.integrated.env.linux": env_block("/", "bin"),
            "terminal.integrated.env.osx": env_block("/", "bin"),
            "terminal.integrated.env.windows": env_block("\\", "Scripts"),
            "chat.useAgentsMdFile": True,
            "chat.useClaudeMdFile": True,
            "chat.useAgentSkills": True,
            "chat.useHooks": True,
            "chat.tools.global.autoApprove": False,
            "chat.tools.terminal.blockDetectedFileWrites": "outsideWorkspace",
            "chat.tools.terminal.autoApprove": auto,
            "github.copilot.chat.codeGeneration.useInstructionFiles": True,
            "telemetry.telemetryLevel": "off",
            "extensions.ignoreRecommendations": True,
            "task.allowAutomaticTasks": "off",
            "files.watcherExclude": {"**/.ai-sandbox/cache/**": True, "**/.ai-sandbox/home/**": True, "**/.ai-sandbox/runtime/**": True, "**/.venv/**": True},
            "search.exclude": {"**/.ai-sandbox/cache": True, "**/.ai-sandbox/home": True, "**/.ai-sandbox/logs": True,
                               "**/.ai-sandbox/runtime": True, "**/.venv": True},
        }
        w.merge_json(".vscode/settings.json", settings, label=".vscode/settings.json  (portable ${workspaceFolder} paths)")
        launcher_posix, launcher_win = "${workspaceFolder}/.ai-sandbox/bin/aisb", "${workspaceFolder}\\.ai-sandbox\\bin\\aisb.cmd"

        def task(label, args, background=False):
            t = {"label": "Sandbox: " + label, "type": "shell", "command": launcher_posix, "args": args,
                 "windows": {"command": launcher_win, "args": args},
                 "options": {"cwd": "${workspaceFolder}"}, "problemMatcher": [], "presentation": {"reveal": "always", "panel": "dedicated"}}
            if background:
                t["isBackground"] = True
            return t
        tasks = {"version": "2.0.0", "tasks": [
            task("Verify isolation", ["verify"]), task("Status", ["status"]),
            task("Audit log (last 50)", ["log", "-n", "50"]), task("Audit log (follow)", ["log", "--follow"], True),
            task("Sync configs from SSOT", ["sync"]), task("Uninstall (keeps .venv)", ["uninstall", "--yes"]),
        ]}
        w.merge_json(".vscode/tasks.json", tasks, label=".vscode/tasks.json  (audited local tasks)")
        servers = self.ssot.mcp_servers()
        if servers:
            w.merge_json(".vscode/mcp.json", {"servers": self._mcp_render(servers, "vscode")}, label=".vscode/mcp.json  (VS Code / Copilot MCP servers)")

    # ======================================================================================
    # Windsurf / Devin
    # ======================================================================================
    def windsurf(self):
        w, i = self.w, self.i
        for base in (".devin", ".windsurf"):
            w.ensure_dir(base + "/rules")
            for r in self.rules_for("windsurf"):
                w.put("%s/rules/%s.md" % (base, r.name), self._rule_block(r, "windsurf"))
            self._commands(base + "/workflows", "workflow-md", ".md")

        def hk(ev):
            return {"command": i.hook_shell("windsurf", ev, flavor="sh", relative=True, layout="posix"),
                    "powershell": i.hook_shell("windsurf", ev, flavor="ps", relative=True), "show_output": False}
        hooks = {"pre_run_command": [hk("pre")], "pre_write_code": [hk("pre")], "pre_read_code": [hk("pre")],
                 "pre_mcp_tool_use": [hk("pre")], "post_run_command": [hk("post")], "post_write_code": [hk("post")]}
        self._user_hooks_into(hooks, "windsurf")
        w.merge_json(".devin/hooks.json", {"hooks": hooks}, label=".devin/hooks.json  (Devin Desktop; .windsurf/hooks.json kept for older builds)")
        w.merge_json(".windsurf/hooks.json", {"hooks": hooks}, label=".windsurf/hooks.json")
        servers = self.ssot.mcp_servers()
        if servers:
            w.put(".ai-sandbox/mcp/devin.mcp_config.json", dump_json({"mcpServers": self._mcp_render(servers, "windsurf")}),
                  label=".ai-sandbox/mcp/devin.mcp_config.json  (paste into Devin Desktop/Windsurf MCP settings; no project-level MCP file)")

    # ======================================================================================
    # Google Antigravity
    # ======================================================================================
    def antigravity(self):
        w, i = self.w, self.i
        w.ensure_dir(".agents/rules")
        for r in self.rules_for("antigravity"):
            w.put(".agents/rules/%s.md" % r.name, self._rule_block(r, "antigravity"))
        for a in self.ssot.agents():
            fm = {"name": a.name, "description": a.description, "model": "inherit", "commandExecutionPolicy": "off" if a.fm.get("readonly") else "auto"}
            if a.tools:
                fm["tools"] = a.tools
            w.put(".agents/agents/%s.md" % a.name, render_frontmatter(fm) + "\n" + a.body.strip("\n") + "\n")

        def hk(ev):  # absolute paths: Antigravity does not document the hook working directory
            return {"type": "command", "command": i.hook_shell("antigravity", ev, flavor="ps" if self.h.is_windows else "sh"), "timeout": 20}
        block = {
            "enabled": True,
            "SessionStart": [hk("session-start")],
            "PreToolUse": [{"matcher": "", "hooks": [hk("pre")]}],
            "PostToolUse": [{"matcher": "", "hooks": [hk("post")]}],
            "Stop": [hk("stop")],
        }
        for hk_user in self.ssot.hooks():
            if not hk_user.applies_to("antigravity"):
                continue
            ev = {"pre-tool": "PreToolUse", "post-tool": "PostToolUse", "session-start": "SessionStart", "stop": "Stop"}.get(hk_user.event)
            if not ev:
                continue
            entry = {"type": "command", "command": hk_user.command, "timeout": hk_user.timeout}
            if ev in ("PreToolUse", "PostToolUse"):
                block.setdefault(ev, []).append({"matcher": hk_user.matcher or "", "hooks": [entry]})
            else:
                block.setdefault(ev, []).append(entry)
        w.merge_json(".agents/hooks.json", {"ai-sandbox": block}, label=".agents/hooks.json  (Antigravity hooks)")
        servers = self.ssot.mcp_servers()
        if servers:
            w.merge_json(".agents/mcp_config.json", {"mcpServers": self._mcp_render(servers, "antigravity")}, label=".agents/mcp_config.json  (Antigravity project MCP servers)")

    # ======================================================================================
    # Extras: rules only (plus MCP where a project file exists)
    # ======================================================================================
    def extra(self, tid):
        t = TARGETS[tid]
        w = self.w
        rules = self.rules_for(tid)
        st = t["rules"]
        if st["style"] == "dir-md":
            w.ensure_dir(st["dir"])
            for r in rules:
                w.put("%s/%s%s" % (st["dir"], r.name, st["ext"]), r.body.strip("\n") + "\n")
        elif st["style"] in ("kiro", "continue"):
            w.ensure_dir(st["dir"])
            for r in rules:
                w.put("%s/%s%s" % (st["dir"], r.name, st["ext"]), self._rule_block(r, st["style"]))
        elif st["style"] == "block-md":
            body = "\n\n".join(("# [%s]\n" % r.name if r.name != "sandbox-policy" else "") + r.body.strip("\n") for r in rules if r.always)
            w.put_block(st["file"], body, MARK_MD)
        servers = self.ssot.mcp_servers()
        mcp = t.get("mcp") or {}
        if servers and mcp.get("file") and mcp.get("style") == "mcpservers":
            w.merge_json(mcp["file"], {"mcpServers": self._mcp_render(servers, "cursor")}, label=mcp["file"])
        elif servers and mcp.get("style") == "zed":
            ctx = {}
            for name, s in servers.items():
                if s.get("command"):
                    ctx[name] = {"source": "custom", "command": s["command"], "args": list(s.get("args", [])), "env": dict(s.get("env", {}))}
            if ctx:
                w.merge_json(".zed/settings.json", {"context_servers": ctx}, label=".zed/settings.json  (context_servers)")
        elif servers and mcp.get("style") == "codex-toml":
            lines = ["# ai-sandbox: MCP servers (merge into .codex/config.toml; generated, do not edit)"]
            for name, s in servers.items():
                lines.append("[mcp_servers.%s]" % name)
                if s.get("command"):
                    lines.append("command = %s" % _toml_str(s["command"]))
                    if s.get("args"):
                        lines.append("args = [%s]" % ", ".join(_toml_str(a) for a in s["args"]))
                    if s.get("env"):
                        lines.append("env = { %s }" % ", ".join("%s = %s" % (k, _toml_str(v)) for k, v in s["env"].items()))
                else:
                    lines.append("url = %s" % _toml_str(s.get("url", "")))
                lines.append("")
            w.put(".ai-sandbox/mcp/codex.mcp.toml", "\n".join(lines) + "\n", label=".ai-sandbox/mcp/codex.mcp.toml  (merge into .codex/config.toml)")
        if tid == "codex":
            self._fan_out_skills([".codex/skills"])
