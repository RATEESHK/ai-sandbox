# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Verify: prove the sandbox is installed, intact and effective on this machine."""
from __future__ import annotations

import json
import os
import re
import subprocess

from .common import parse_jsonc, read_text, sha256_file, sha256_text
from .manifest import Manifest

from . import __version__


class Verifier:
    def __init__(self, root, host, log):
        self.root, self.host, self.log = root, host, log
        self.m = Manifest(root)
        self.fails = 0
        self.warns = 0

    def P(self, *parts):
        return os.path.join(self.root, *parts)

    def ok(self, msg):
        self.log.ok(msg)

    def warn(self, msg):
        self.warns += 1
        self.log.warn(msg)

    def fail(self, msg):
        self.fails += 1
        self.log.fail(msg)

    def run(self, quick=False):
        L, h = self.log, self.host
        L.info("verify  %s  |  %s  |  root %s" % (__version__, h.label, self.root))
        if not os.path.isfile(self.m.path):
            self.fail("no .ai-sandbox/manifest.json: the sandbox is not installed here (run install)")
            return self.finish()
        if os.path.normcase(self.m.data.get("root", "")) != os.path.normcase(self.root):
            self.fail("manifest root %s != current root %s - the folder moved; run `aisb init` to regenerate paths"
                      % (self.m.data.get("root"), self.root))
        else:
            self.ok("manifest   root matches (%s files tracked, kit %s)" % (len(self.m.files), self.m.data.get("kit_version")))
        hook_py = self.m.data.get("hook_python") or ""
        rt = self.m.data.get("runtime", {}) or {}
        self.check_venv(hook_py)
        guard = self.P(".ai-sandbox", "hooks", "sandbox_guard.py")
        if not os.path.isfile(guard):
            self.fail("guard missing: .ai-sandbox/hooks/sandbox_guard.py")
            return self.finish()
        if rt.get("mode") == "binary":
            exe = rt.get("exe") or ""
            if os.path.isfile(exe):
                self.guard_cmd = [exe, "guard"]
                self.ok("runtime    standalone build %s (no Python needed)" % (rt.get("version") or ""))
            else:
                self.guard_cmd = None
                self.fail("runtime    standalone build missing at %s (re-run the installer)" % exe)
        else:
            self.guard_cmd = [hook_py, guard] if hook_py and os.path.isfile(hook_py) else None
            if self.guard_cmd is None:
                self.fail("runtime    hook interpreter missing: %s (run `aisb init`)" % hook_py)
        if self.guard_cmd:
            self.check_guard()
            if not quick:
                self.check_protocols()
                if rt.get("mode") != "binary" and hook_py:
                    self.check_pip_enforcement(hook_py)
        self.check_components()
        self.check_drift()
        self.check_json_files()
        self.check_env_active()
        self.check_os_sandbox()
        self.check_globals()
        self.check_logs()
        return self.finish()

    def finish(self):
        L = self.log
        L.info("-" * 72)
        quiet = L.quiet
        L.quiet = False  # the verdict is always shown
        if self.fails:
            L.fail("RESULT: FAIL (%d failed, %d warnings)" % (self.fails, self.warns))
            L.quiet = quiet
            return 1
        L.ok("RESULT: PASS (%d warnings)" % self.warns)
        L.quiet = quiet
        return 0

    # --- individual checks --------------------------------------------------------------
    def check_venv(self, hook_py):
        venv = self.P(".venv")
        if self.m.data.get("venv", {}).get("path") is None and self.m.data.get("options", {}).get("no_venv"):
            self.warn("venv       disabled (--no-venv); hooks use %s" % hook_py)
            return
        if self.m.data.get("venv", {}).get("path") is None and (self.m.data.get("runtime") or {}).get("mode") == "binary":
            self.log.info("venv       none (no Python on this machine). `aisb runtime python` adds a project-local one.")
            return
        py = self.P(".venv", self.host.venv_bin, self.host.venv_py)
        if not os.path.isfile(os.path.join(venv, "pyvenv.cfg")) or not os.path.exists(py):
            self.fail("venv       .venv missing or broken (%s). Run `aisb init`." % py)
            return
        try:
            r = subprocess.run([py, "-c", "import sys; print(sys.prefix != sys.base_prefix); print(sys.version.split()[0])"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
            lines = (r.stdout or "").strip().splitlines()
            if r.returncode == 0 and lines and lines[0] == "True":
                self.ok("venv       real virtual environment, python %s" % (lines[1] if len(lines) > 1 else "?"))
            else:
                self.fail("venv       interpreter does not report a virtual environment: %s" % (r.stdout or "").strip()[-200:])
        except Exception as exc:  # noqa: BLE001
            self.fail("venv       interpreter failed to run: %s" % exc)
        r = subprocess.run([py, "-m", "pip", "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        if r.returncode == 0:
            self.ok("venv       pip available: %s" % (r.stdout or "").strip()[:80])
        else:
            self.warn("venv       pip not available inside .venv (created without ensurepip?)")

    def check_guard(self):
        r = subprocess.run(self.guard_cmd + ["--selftest"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
        last = (r.stdout or "").strip().splitlines()[-1:] or [""]
        if r.returncode == 0:
            self.ok("guard      self-test %s" % last[0])
        else:
            self.fail("guard      self-test failed: %s" % (r.stdout or "").strip()[-600:])

    def _hook(self, tool, event, payload, env=None):
        e = dict(os.environ)
        e.pop("AI_SANDBOX_ROOT", None)
        if env:
            e.update(env)
        r = subprocess.run(self.guard_cmd + ["--tool", tool, "--event", event], input=json.dumps(payload) if not isinstance(payload, str) else payload,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60, env=e, cwd=self.root)
        out = r.stdout.strip()
        j = None
        if out.startswith("{"):
            try:
                j = json.loads(out.splitlines()[0])
            except Exception:  # noqa: BLE001
                j = None
        return r.returncode, j, out, r.stderr.strip()

    def check_protocols(self):
        root = self.root
        home = os.path.expanduser("~")
        checks = [
            ("claude deny npm -g", "claude", "pre", {"session_id": "t", "cwd": root, "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "npm install -g typescript"}},
             lambda c, j, o, e: c == 0 and j and j["hookSpecificOutput"]["permissionDecision"] == "deny"),
            ("claude deny Write ../", "claude", "pre", {"cwd": root, "tool_name": "Write", "tool_input": {"file_path": "../escape.txt", "content": "x"}},
             lambda c, j, o, e: j and j["hookSpecificOutput"]["permissionDecision"] == "deny"),
            ("claude deny Read ~/.ssh", "claude", "pre", {"cwd": root, "tool_name": "Read", "tool_input": {"file_path": os.path.join(home, ".ssh", "id_rsa")}},
             lambda c, j, o, e: j and j["hookSpecificOutput"]["permissionDecision"] == "deny"),
            ("claude deny self-protection", "claude", "pre", {"cwd": root, "tool_name": "Edit", "tool_input": {"file_path": os.path.join(root, ".claude", "settings.local.json")}},
             lambda c, j, o, e: j and j["hookSpecificOutput"]["permissionDecision"] == "deny"),
            ("claude allow git status", "claude", "pre", {"cwd": root, "tool_name": "Bash", "tool_input": {"command": "git status"}},
             lambda c, j, o, e: c == 0 and o == ""),
            ("claude allow venv pip", "claude", "pre", {"cwd": root, "tool_name": "Bash", "tool_input": {"command": "./.venv/bin/python -m pip install requests" if not self.host.is_windows else ".\\.venv\\Scripts\\python.exe -m pip install requests"}},
             lambda c, j, o, e: c == 0 and o == ""),
            ("claude post logs", "claude", "post", {"cwd": root, "tool_name": "Bash", "tool_input": {"command": "git status"}, "tool_response": {"stdout": "ok"}},
             lambda c, j, o, e: c == 0),
            ("gemini deny sudo", "gemini", "pre", {"session_id": "t", "cwd": root, "hook_event_name": "BeforeTool", "tool_name": "run_shell_command", "tool_input": {"command": "sudo ls"}},
             lambda c, j, o, e: c == 0 and j and j.get("decision") == "deny"),
            ("gemini allow write inside", "gemini", "pre", {"cwd": root, "tool_name": "write_file", "tool_input": {"file_path": os.path.join(root, "x.txt"), "content": ""}},
             lambda c, j, o, e: c == 0 and o == ""),
            ("cursor deny pip --user", "cursor", "pre", {"conversation_id": "t", "hook_event_name": "beforeShellExecution", "command": "pip install --user x", "cwd": root, "workspace_roots": [root]},
             lambda c, j, o, e: c == 0 and j and j.get("permission") == "deny"),
            ("cursor deny read outside", "cursor", "pre", {"hook_event_name": "beforeReadFile", "file_path": os.path.join(home, ".zshrc"), "workspace_roots": [root]},
             lambda c, j, o, e: j and j.get("permission") == "deny"),
            ("cursor allow answers JSON", "cursor", "pre", {"hook_event_name": "beforeShellExecution", "command": "npm test", "cwd": root, "workspace_roots": [root]},
             lambda c, j, o, e: c == 0 and j and j.get("permission") == "allow"),
            ("cursor post answers JSON", "cursor", "post", {"hook_event_name": "afterFileEdit", "file_path": os.path.join(root, "x.py"), "edits": [], "workspace_roots": [root]},
             lambda c, j, o, e: c == 0 and j == {}),
            ("cursor prompt continue", "cursor", "prompt", {"hook_event_name": "beforeSubmitPrompt", "prompt": "hello", "workspace_roots": [root]},
             lambda c, j, o, e: j and j.get("continue") is True),
            ("cursor session env", "cursor", "session-start", {"hook_event_name": "sessionStart", "workspace_roots": [root]},
             lambda c, j, o, e: j and "PIP_REQUIRE_VIRTUALENV" in (j.get("env") or {})),
            ("copilot deny brew (string args)", "copilot", "pre", {"timestamp": 1, "cwd": root, "toolName": "bash", "toolArgs": json.dumps({"command": "brew install x"})},
             lambda c, j, o, e: c == 0 and j and j.get("permissionDecision") == "deny" and j["hookSpecificOutput"]["permissionDecision"] == "deny"),
            ("copilot allow ls (object args)", "copilot", "pre", {"cwd": root, "toolName": "bash", "toolArgs": {"command": "ls -la"}},
             lambda c, j, o, e: c == 0 and o == ""),
            ("windsurf deny cd ..", "windsurf", "pre", {"agent_action_name": "run_command", "tool_info": {"command_line": "cd ..", "cwd": root}},
             lambda c, j, o, e: c == 2),
            ("generic unparsable -> deny", "generic", "pre", "not json at all",
             lambda c, j, o, e: c == 2),
        ]
        for name, tool, event, payload, check in checks:
            try:
                c, j, o, e = self._hook(tool, event, payload)
                if check(c, j, o, e):
                    self.ok("protocol   %s" % name)
                else:
                    self.fail("protocol   %s -> exit=%s stdout=%s stderr=%s" % (name, c, o[:200], e[:200]))
            except Exception as exc:  # noqa: BLE001
                self.fail("protocol   %s crashed: %s" % (name, exc))
        # Claude SessionStart writes the env preamble
        tmp = self.P(".ai-sandbox", "cache", "tmp", "claude-env-test.sh")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
            c, j, o, e = self._hook("claude", "session-start",
                                    {"cwd": root, "hook_event_name": "SessionStart", "source": "startup"}, env={"CLAUDE_ENV_FILE": tmp})
            txt = read_text(tmp) if os.path.exists(tmp) else ""
            need_venv = os.path.isdir(self.P(".venv"))
            if j and "additionalContext" in j.get("hookSpecificOutput", {}) and "export PIP_REQUIRE_VIRTUALENV=" in txt \
                    and "_ais_prepend" in txt and ("export VIRTUAL_ENV=" in txt or not need_venv):
                self.ok("protocol   claude SessionStart context + CLAUDE_ENV_FILE preamble")
            else:
                self.fail("protocol   claude SessionStart: context=%s envfile=%s" % (bool(j), txt[:120]))
        except Exception as exc:  # noqa: BLE001
            self.fail("protocol   claude SessionStart crashed: %s" % exc)
        finally:
            try:
                os.remove(tmp)
            except Exception:  # noqa: BLE001
                pass

    def check_pip_enforcement(self, hook_py):
        """With the sandbox env, the SYSTEM interpreter's pip must refuse to install (exit 3, before any network)."""
        sys_py = self.host.python
        env = dict(os.environ)
        env.update({"PIP_REQUIRE_VIRTUALENV": "true", "PIP_NO_INPUT": "1"})
        try:
            r = subprocess.run([sys_py, "-m", "pip", "install", "--no-index", "ai-sandbox-nonexistent-package"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120, env=env, cwd=self.root)
        except Exception as exc:  # noqa: BLE001
            self.warn("pip guard  could not run the system pip test: %s" % exc)
            return
        out = (r.stdout or "")
        if "activated virtualenv" in out.lower() or r.returncode == 3:
            self.ok("pip guard  system pip refuses installs under PIP_REQUIRE_VIRTUALENV (exit %s)" % r.returncode)
        elif "No module named pip" in out:
            self.warn("pip guard  system interpreter has no pip at all (fine: nothing to leak)")
        else:
            self.fail("pip guard  system pip did NOT refuse: exit=%s %s" % (r.returncode, out.strip()[-200:]))
        _ = hook_py

    def check_components(self):
        from .ssot import SSOT
        sm = SSOT(self.root).summary()
        self.ok("ssot       rules=%d skills=%d agents=%d commands=%d hooks=%d mcp=%d bundles=%d" % (
            len(sm["rules"]), len(sm["skills"]), len(sm["agents"]), len(sm["commands"]), len(sm["hooks"]), len(sm["mcp"]), len(sm["bundles"])))
        hd = self.P(".ai-sandbox", "hooks.d")
        if os.path.isdir(hd):
            for fn in os.listdir(hd):
                if fn.endswith(".json"):
                    try:
                        d = parse_jsonc(read_text(os.path.join(hd, fn)))
                        if not d.get("command"):
                            self.warn("hooks.d    %s has no command" % fn)
                    except Exception as exc:  # noqa: BLE001
                        self.fail("hooks.d    %s is not valid JSON: %s" % (fn, exc))

    def check_drift(self):
        drifted = 0
        for rel, entry in sorted(self.m.files.items()):
            path = self.P(*rel.split("/"))
            if not os.path.exists(path):
                if entry.get("created") or entry.get("mode") == "generated":
                    self.warn("missing    %s (tracked file deleted; run `aisb sync`)" % rel)
                continue
            if entry.get("mode") in ("generated", "merged") and entry.get("sha256"):
                if entry.get("binary"):
                    cur = sha256_file(path)
                else:
                    try:
                        cur = sha256_text(read_text(path).replace("\r\n", "\n"))
                    except UnicodeDecodeError:
                        cur = sha256_file(path)
                if cur != entry["sha256"]:
                    if entry.get("user_edited") or rel in (".ai-sandbox/policy.json", ".ai-sandbox/policy.local.json",
                                                            ".ai-sandbox/rules/sandbox-policy.md", ".ai-sandbox/mcp/servers.json") \
                            or rel.startswith((".ai-sandbox/skills/", ".ai-sandbox/agents/")):
                        self.log.info("edited     %s (SSOT file you changed; copies refresh on `aisb sync`)" % rel)
                        continue
                    drifted += 1
                    if rel.startswith((".ai-sandbox/hooks/", ".ai-sandbox/bin/")):
                        self.fail("drift      %s was modified after install (sandbox code!) - run `aisb sync --force`" % rel)
                    else:
                        self.warn("drift      %s differs from what install generated (local edit or external tool)" % rel)
        if not drifted:
            self.ok("drift      all %d tracked files match the manifest" % len(self.m.files))
        # policy copies in sync with SSOT
        ssot = self.P(".ai-sandbox", "rules", "sandbox-policy.md")
        if os.path.isfile(ssot):
            body = read_text(ssot).strip()
            for rel in (".cursor/rules/sandbox-policy.mdc", ".windsurf/rules/sandbox-policy.md", "AGENTS.md"):
                p = self.P(*rel.split("/"))
                if os.path.isfile(p) and body not in read_text(p):
                    self.warn("ssot       %s no longer contains the policy text from rules/sandbox-policy.md (run `aisb sync`)" % rel)

    def check_json_files(self):
        bad = 0
        for rel in sorted(self.m.files):
            if rel.endswith(".json"):
                p = self.P(*rel.split("/"))
                if os.path.exists(p):
                    try:
                        parse_jsonc(read_text(p))
                    except Exception as exc:  # noqa: BLE001
                        bad += 1
                        self.fail("json       %s is not valid JSON: %s" % (rel, exc))
        if not bad:
            self.ok("json       every generated/merged JSON file parses")

    def check_env_active(self):
        env_file = self.P(".ai-sandbox", "sandbox.env")
        if not os.path.isfile(env_file):
            self.fail("env        sandbox.env missing")
            return
        wanted = {}
        for ln in read_text(env_file).splitlines():
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)='(.*)'", ln)
            if m:
                wanted[m.group(1)] = m.group(2).replace("'\\''", "'")
        self.ok("env        sandbox.env defines %d variables" % len(wanted))
        present = sum(1 for k, v in wanted.items() if os.environ.get(k) == v)
        if present == len(wanted):
            self.ok("env        this terminal has the sandbox environment active (%d/%d)" % (present, len(wanted)))
        elif present:
            self.warn("env        this terminal has only %d/%d sandbox variables (stale activation? re-source activate.*)" % (present, len(wanted)))
        else:
            self.log.info("env        this terminal is NOT activated (expected if you run from a plain shell; AI tools get the env from their own config)")
        for k, v in wanted.items():
            if v.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", v):
                try:
                    if os.path.commonpath([os.path.realpath(v), os.path.realpath(self.root)]) != os.path.realpath(self.root):
                        self.fail("env        %s points outside the workspace: %s" % (k, v))
                except ValueError:
                    self.fail("env        %s points to another drive: %s" % (k, v))

    def check_os_sandbox(self):
        h = self.host
        if h.is_mac:
            self.ok("os-sandbox macOS seatbelt available (Claude Code sandbox can be enabled)")
        elif h.is_linux:
            if h.has["bwrap"] and h.has["socat"]:
                self.ok("os-sandbox bubblewrap + socat present%s" % (" (WSL2)" if h.is_wsl else ""))
            else:
                self.warn("os-sandbox bubblewrap/socat missing: Claude Code's kernel sandbox is OFF; hooks + permissions enforce instead")
        else:
            self.log.info("os-sandbox native Windows: no kernel sandbox for AI tools; hooks + permissions enforce (WSL2 would add bubblewrap)")

    def check_globals(self):
        """Read-only report: user-level files these tools will merge with the project configuration."""
        home = self.host.home
        appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
        candidates = [
            ("Claude Code user settings", os.path.join(home, ".claude", "settings.json")),
            ("Claude Code user CLAUDE.md", os.path.join(home, ".claude", "CLAUDE.md")),
            ("Gemini CLI user settings", os.path.join(home, ".gemini", "settings.json")),
            ("Gemini CLI user GEMINI.md", os.path.join(home, ".gemini", "GEMINI.md")),
            ("Cursor user hooks", os.path.join(home, ".cursor", "hooks.json")),
            ("Copilot CLI user settings", os.path.join(home, ".copilot", "settings.json")),
            ("Copilot CLI user hooks", os.path.join(home, ".copilot", "hooks")),
            ("VS Code user settings", os.path.join(appdata, "Code", "User", "settings.json") if self.host.is_windows
             else (os.path.join(home, "Library", "Application Support", "Code", "User", "settings.json") if self.host.is_mac
                   else os.path.join(home, ".config", "Code", "User", "settings.json"))),
            ("npm user config", os.path.join(home, ".npmrc")),
            ("pip user config", os.path.join(appdata, "pip", "pip.ini") if self.host.is_windows else os.path.join(home, ".config", "pip", "pip.conf")),
            ("git global config", os.path.join(home, ".gitconfig")),
            ("conda rc", os.path.join(home, ".condarc")),
        ]
        found = [(n, p) for n, p in candidates if os.path.exists(p)]
        if found:
            self.log.info("globals    user-level configs present on this machine (NOT modified; tools merge them with the project):")
            for n, p in found:
                self.log.info("           - %-26s %s" % (n, p))
        else:
            self.ok("globals    no user-level tool configs found")
        # Claude user settings that could neutralise the project hooks
        cs = os.path.join(home, ".claude", "settings.json")
        if os.path.isfile(cs):
            try:
                d = parse_jsonc(read_text(cs))
                if d.get("disableAllHooks"):
                    self.fail("globals    ~/.claude/settings.json sets disableAllHooks=true - the project hooks would never run")
                if d.get("permissions", {}).get("defaultMode") in ("bypassPermissions", "dontAsk", "auto"):
                    self.warn("globals    ~/.claude/settings.json defaultMode=%s (project sets 'default'; project wins)" % d["permissions"]["defaultMode"])
            except Exception:  # noqa: BLE001
                pass
        managed = ["/Library/Application Support/ClaudeCode/managed-settings.json", "/etc/claude-code/managed-settings.json",
                   "C:\\Program Files\\ClaudeCode\\managed-settings.json"]
        for p in managed:
            if os.path.exists(p):
                self.warn("globals    managed Claude settings exist (%s) - they override project settings" % p)

    def check_logs(self):
        log = self.P(".ai-sandbox", "logs", "audit.log")
        try:
            os.makedirs(os.path.dirname(log), exist_ok=True)
            with open(log, "a", encoding="utf-8"):
                pass
            n = sum(1 for _ in open(log, "r", encoding="utf-8", errors="ignore"))
            self.ok("audit      log writable, %d entries so far" % n)
        except Exception as exc:  # noqa: BLE001
            self.fail("audit      log not writable: %s" % exc)
