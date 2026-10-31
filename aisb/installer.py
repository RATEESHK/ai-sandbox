# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Installer / sync: creates the SSOT, the runtime pieces (.venv or standalone build), and fans everything out."""
from __future__ import annotations

import datetime as _dt
import json
import os
import pkgutil
import re
import shutil
import subprocess
import sys

from . import REPO_URL, __author__, __license_name__, __version__
from .common import dump_json, q_ps, read_text
from .envmodel import build_env
from .generators import Generators
from .manifest import Manifest, Writer
from .ssot import SSOT
from .targets import TARGETS
from .templates import (ACTIVATE_SH, AGENT_AUDITOR_BODY, LAUNCHER_CMD, LAUNCHER_PS1, LAUNCHER_SH, POLICY_MD,
                        SANDBOX_README, SKILL_LOCAL_ENV)


def guard_source():
    """The guard's source text (works from a source checkout, a zipapp and a PyInstaller build with data files)."""
    data = pkgutil.get_data("aisb", "guard.py")
    if data:
        return data.decode("utf-8")
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard.py")
    return read_text(here)


def default_policy():
    """DEFAULT_POLICY from the guard source, without importing side effects."""
    src = guard_source()
    m = re.search(r"\nDEFAULT_POLICY = \{.*?\n\}\n", src, re.DOTALL)
    ns = {}
    exec(("_CMD = r\"[^\\n;&|]*\"\n" + m.group(0)) if m else "DEFAULT_POLICY = {}", ns)  # noqa: S102
    return ns.get("DEFAULT_POLICY", {})


class Installer:
    def __init__(self, root, host, opts, log):
        self.root = root
        self.host = host
        self.opts = opts
        self.log = log
        self.m = Manifest(root)
        self.w = Writer(root, self.m, log, force=opts.get("force", False), dry_run=opts.get("dry_run", False))
        self.ssot = SSOT(root)
        self.tools = opts["tools"]
        self.env = build_env(root, host, opts)
        self.venv_python = os.path.join(root, ".venv", host.venv_bin, host.venv_py)
        self.runtime_python = self._runtime_python()
        self.guard = os.path.join(root, ".ai-sandbox", "hooks", "sandbox_guard.py")
        self.bin_dir = os.path.join(root, ".ai-sandbox", "bin")
        self.frozen_dst = os.path.join(self.bin_dir, "aisb-bin")
        self.frozen_exe = os.path.join(self.frozen_dst, "aisb.exe" if host.is_windows else "aisb")
        self.gen = Generators(self)
        # how hooks run: "binary" (standalone build) or "python" (interpreter + guard file)
        self.runtime_mode = "binary" if host.frozen else "python"
        self.hook_python = None if host.frozen else (self.venv_python if not opts.get("no_venv") else host.python)

    # ---- runtime helpers -----------------------------------------------------------------
    def _runtime_python(self):
        p = os.path.join(self.root, ".ai-sandbox", "runtime", "python")
        for cand in (os.path.join(p, "python.exe"), os.path.join(p, "bin", "python3"), os.path.join(p, "bin", "python")):
            if os.path.isfile(cand):
                return cand
        return None

    def P(self, *parts):
        return os.path.join(self.root, *parts)

    def policy_text(self):
        p = self.P(".ai-sandbox", "rules", "sandbox-policy.md")
        return read_text(p) if os.path.isfile(p) else POLICY_MD

    # ---- hook command builders -----------------------------------------------------------
    def hook_exec(self, tool, event):
        """Exec form (no shell): (command, args)."""
        if self.runtime_mode == "binary":
            return self.frozen_exe, ["guard", "--tool", tool, "--event", event]
        return self.hook_python, [self.guard, "--tool", tool, "--event", event]

    def hook_shell(self, tool, event, flavor="sh", relative=False, layout="host", env_root=None):
        """Shell-string form for tools that only take a command string.
        flavor: sh | ps.  relative: use project-relative paths (portable file).  layout: 'host' or 'posix' venv layout.
        env_root: name of an env var the tool exposes for the project dir (e.g. GEMINI_PROJECT_DIR)."""
        if self.runtime_mode == "binary":
            if relative:
                exe = ".ai-sandbox/bin/aisb-bin/aisb" + (".exe" if (self.host.is_windows and flavor == "ps") else "")
                if flavor == "ps":
                    exe = exe.replace("/", "\\")
                    return "& %s guard --tool %s --event %s" % (exe, tool, event)
                return "%s guard --tool %s --event %s" % (exe, tool, event)
            if env_root:
                if flavor == "ps":
                    return '& "$env:%s\\.ai-sandbox\\bin\\aisb-bin\\aisb.exe" guard --tool %s --event %s' % (env_root, tool, event)
                return '"$%s/.ai-sandbox/bin/aisb-bin/aisb" guard --tool %s --event %s' % (env_root, tool, event)
            if flavor == "ps":
                return "& %s guard --tool %s --event %s" % (q_ps(self.frozen_exe), tool, event)
            return '"%s" guard --tool %s --event %s' % (self.frozen_exe, tool, event)
        # ---- python mode
        guard_rel = ".ai-sandbox/hooks/sandbox_guard.py"
        if self.opts.get("no_venv"):
            py_abs = self.hook_python
            if relative:
                if flavor == "ps":
                    return "& %s %s --tool %s --event %s" % (q_ps(py_abs), guard_rel.replace("/", "\\"), tool, event)
                return '"%s" %s --tool %s --event %s' % (py_abs, guard_rel, tool, event)
            if env_root:
                if flavor == "ps":
                    return '& %s "$env:%s\\.ai-sandbox\\hooks\\sandbox_guard.py" --tool %s --event %s' % (q_ps(py_abs), env_root, tool, event)
                return '%s "$%s/.ai-sandbox/hooks/sandbox_guard.py" --tool %s --event %s' % ('"%s"' % py_abs, env_root, tool, event)
            if flavor == "ps":
                return "& %s %s --tool %s --event %s" % (q_ps(py_abs), q_ps(self.guard), tool, event)
            return '"%s" "%s" --tool %s --event %s' % (py_abs, self.guard, tool, event)
        venv_rel_posix = ".venv/bin/python"
        venv_rel_host = ".venv/%s/%s" % (self.host.venv_bin, self.host.venv_py)
        if relative:
            if flavor == "ps":
                return "& .venv\\Scripts\\python.exe .ai-sandbox\\hooks\\sandbox_guard.py --tool %s --event %s" % (tool, event)
            py = venv_rel_posix if layout == "posix" else venv_rel_host
            return "%s %s --tool %s --event %s" % (py, guard_rel, tool, event)
        if env_root:
            if flavor == "ps":
                return '& "$env:%s\\.venv\\Scripts\\python.exe" "$env:%s\\.ai-sandbox\\hooks\\sandbox_guard.py" --tool %s --event %s' % (env_root, env_root, tool, event)
            return '"$%s/.venv/bin/python" "$%s/.ai-sandbox/hooks/sandbox_guard.py" --tool %s --event %s' % (env_root, env_root, tool, event)
        if flavor == "ps":
            return "& %s %s --tool %s --event %s" % (q_ps(self.venv_python), q_ps(self.guard), tool, event)
        return '"%s" "%s" --tool %s --event %s' % (self.venv_python, self.guard, tool, event)

    def manager_shell(self, args, flavor="sh"):
        """Project-relative command that runs the aisb launcher (used inside Gemini custom commands)."""
        if flavor == "ps":
            return "& .ai-sandbox\\bin\\aisb.cmd %s" % args
        return "./.ai-sandbox/bin/aisb %s" % args

    # ======================================================================================
    # Phases
    # ======================================================================================
    def run(self, sync_only=False):
        h, L = self.host, self.log
        L.info("%s %s  |  %s  |  runtime: %s%s" % ("aisb", __version__, h.label, h.mode,
                                                  "" if h.frozen else " (python %s)" % h.python_version))
        L.info("target: %s" % self.root)
        if h.is_admin and not self.opts.get("terse"):
            L.warn("running as %s. The sandbox is user-level; elevated rights are unnecessary and discouraged."
                   % ("Administrator" if h.is_windows else "root"))
        if not os.path.isdir(self.root):
            L.fail("target folder does not exist: %s" % self.root)
            return 1
        if self.m.data.get("root") and os.path.normcase(self.m.data["root"]) != os.path.normcase(self.root):
            L.warn("this folder was last installed at %s; regenerating all absolute paths for %s" % (self.m.data["root"], self.root))
        self.m.data["root"] = self.root
        self.m.data["options"] = {k: v for k, v in self.opts.items() if k not in ("dry_run", "force")}
        self.m.data["tools"] = list(self.tools)
        self.m.data["host"] = {"system": h.system, "release": h.release, "arch": h.arch, "wsl": h.is_wsl,
                               "hostname": h.hostname, "user": h.user, "mode": h.mode}
        self.phase_dirs()
        if not sync_only:
            self.phase_runtime()
        self.m.data["hook_python"] = self.hook_python or ""
        self.m.data["runtime"] = {"mode": self.runtime_mode, "exe": self.frozen_exe if self.runtime_mode == "binary" else self.hook_python}
        self.phase_ssot()
        self.phase_seed_configs()
        self.phase_env_files()
        self.gen.universal()
        for tool in self.tools:
            fn = getattr(self.gen, tool, None)
            if fn is not None:
                fn()
            else:
                self.gen.extra(tool)
        if not self.opts.get("dry_run"):
            self.m.save()
            L.done("manifest   .ai-sandbox/manifest.json (%d files tracked)" % len(self.m.files))
        return 0

    def phase_dirs(self):
        dirs = ["rules", "hooks", "skills", "agents", "commands", "hooks.d", "mcp", "bundles", "bin", "config", "logs", "backup",
                "cache/pip", "cache/npm", "cache/tmp", "cache/uv", "cache/pycache",
                "home/git", "home/kube", "home/aws", "home/gcloud", "home/azure", "home/docker", "home/gh",
                "home/terraform", "home/helm/config", "home/helm/data", "home/gnupg", "home/xdg/config",
                "home/xdg/data", "home/xdg/state", "home/xdg/cache", "home/python-user", "home/go/bin"]
        for d in dirs:
            self.w.ensure_dir(".ai-sandbox/" + d)
        if not self.opts.get("dry_run") and os.name != "nt":
            try:
                os.chmod(self.P(".ai-sandbox", "home", "gnupg"), 0o700)
            except Exception:  # noqa: BLE001
                pass

    # ---- runtime: .venv (python mode) or the standalone build (binary mode) -----------------
    def phase_runtime(self):
        L = self.log
        if self.host.frozen:
            self._install_frozen_copy()
            if self.runtime_python and not os.path.exists(self.venv_python) and not self.opts.get("no_venv"):
                self._create_venv(self.runtime_python)
            elif not os.path.exists(self.venv_python):
                L.info("venv       no Python on this machine: skipped. `aisb runtime python` installs a project-local one later.")
                self.m.data["venv"] = {"path": None, "created_by_sandbox": False}
            return
        if self.opts.get("no_venv"):
            L.info("venv       skipped (--no-venv); hooks will use %s" % self.host.python)
            self.m.data["venv"] = {"path": None, "created_by_sandbox": False}
            return
        venv_dir = self.P(".venv")
        cfg = os.path.join(venv_dir, "pyvenv.cfg")
        if os.path.isfile(cfg) and os.path.exists(self.venv_python):
            L.ok("venv       .venv already present (%s)" % self.venv_python)
            self.m.data.setdefault("venv", {}).update({"path": ".venv", "python": self.venv_python})
            self.m.data["venv"].setdefault("created_by_sandbox", False)
            return
        if os.path.isdir(venv_dir) and not os.path.isfile(cfg):
            L.fail(".venv exists but is not a virtual environment (no pyvenv.cfg). Move it away or use --no-venv.")
            raise SystemExit(2)
        self._create_venv(self.runtime_python or self.host.python)

    def _create_venv(self, base_python):
        L = self.log
        venv_dir = self.P(".venv")
        if self.opts.get("dry_run"):
            L.info("[dry-run] would create .venv with %s" % base_python)
            return
        L.info("venv       creating .venv with %s ..." % base_python)
        attempts = [("venv+pip", [base_python, "-m", "venv", "--prompt", "sandbox", venv_dir])]
        if self.host.has["uv"]:
            attempts.append(("uv venv", [shutil.which("uv"), "venv", "--python", base_python, venv_dir]))
        attempts.append(("venv --without-pip", [base_python, "-m", "venv", "--without-pip", "--prompt", "sandbox", venv_dir]))
        created = None
        for name, cmd in attempts:
            try:
                r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
            except Exception as exc:  # noqa: BLE001
                L.warn("venv       %s failed to start: %s" % (name, exc))
                continue
            if r.returncode == 0 and os.path.exists(self.venv_python):
                created = name
                break
            L.warn("venv       %s failed (exit %s): %s" % (name, r.returncode, (r.stdout or "").strip()[-400:]))
            shutil.rmtree(venv_dir, ignore_errors=True)
        if not created:
            L.fail("could not create .venv. Debian/Ubuntu: install `python3-venv` yourself once; or run `aisb runtime python` "
                   "for a project-local interpreter; or re-run with --no-venv.")
            raise SystemExit(2)
        self.m.data["venv"] = {"path": ".venv", "created_by_sandbox": True, "python": self.venv_python, "method": created,
                               "base": base_python}
        if created == "venv --without-pip":
            L.warn("venv       created WITHOUT pip (ensurepip unavailable). Use `aisb runtime python` or install python3-venv.")
        else:
            L.done("venv       .venv created (%s)" % created)

    def _install_frozen_copy(self):
        """Copy the running standalone build into the project so hooks keep working if the download folder is deleted."""
        L = self.log
        src = self.host.frozen_dir
        if os.path.normcase(os.path.realpath(src)) == os.path.normcase(os.path.realpath(self.frozen_dst)):
            L.ok("runtime    standalone build already in place (%s)" % self.frozen_dst)
            return
        if self.opts.get("dry_run"):
            L.info("[dry-run] would copy the standalone build into %s" % self.frozen_dst)
            return
        marker = os.path.join(self.frozen_dst, "VERSION")
        if os.path.isfile(marker) and read_text(marker).strip() == __version__ and os.path.exists(self.frozen_exe):
            L.ok("runtime    standalone build %s already in place" % __version__)
            return
        if os.path.isdir(self.frozen_dst):
            shutil.rmtree(self.frozen_dst, ignore_errors=True)
        shutil.copytree(src, self.frozen_dst)
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(__version__ + "\n")
        L.done("runtime    standalone build copied to .ai-sandbox/bin/aisb-bin/ (no Python needed)")
        self.m.data["runtime"] = {"mode": "binary", "exe": self.frozen_exe, "version": __version__}

    # ---- SSOT ------------------------------------------------------------------------------
    def phase_ssot(self):
        w = self.w
        w.put(".ai-sandbox/hooks/sandbox_guard.py", guard_source(), executable=True)
        w.put(".ai-sandbox/rules/sandbox-policy.md", POLICY_MD, user_editable=True)
        w.put(".ai-sandbox/skills/local-env-manager/SKILL.md", SKILL_LOCAL_ENV, user_editable=True)
        w.put(".ai-sandbox/agents/sandbox-auditor.md", self._auditor_md(), user_editable=True)
        w.put(".ai-sandbox/README.md", SANDBOX_README)
        w.put(".ai-sandbox/VERSION", __version__ + "\n")
        w.put(".ai-sandbox/policy.json", dump_json(default_policy()), user_editable=True)
        local = {
            "_doc": "Generated per machine by `aisb init`; lists here are ADDED to policy.json. Safe to edit; regenerated on sync.",
            "protected_env_vars": [e.name for e in self.env],
            "home_prefixes": self.extra_home_prefixes(),
        }
        w.put(".ai-sandbox/policy.local.json", dump_json(local), user_editable=True)
        if not os.path.isfile(self.ssot.P("mcp", "servers.json")):
            w.put(".ai-sandbox/mcp/servers.json", dump_json({"_doc": "MCP servers for this project (aisb add mcp ...). Fanned out to every tool on `aisb sync`.", "servers": {}}),
                  user_editable=True)
        if not os.path.isfile(self.ssot.P("hooks.d", "README.md")):
            w.put(".ai-sandbox/hooks.d/README.md", "# hooks.d\n\nOne JSON file per user hook, created with `aisb add hook`:\n\n"
                  "```json\n{\"event\": \"post-tool\", \"matcher\": \"Write|Edit\", \"command\": \"npx prettier --write .\", \"timeout\": 30, \"tools\": [\"claude\", \"cursor\"]}\n```\n\n"
                  "Events: pre-tool, post-tool, session-start, session-end, prompt, stop. `tools` limits fan-out (default: all).\n")
        # the manager itself (single-file zipapp) + launchers, so the project is self-sufficient
        self._install_pyz()
        w.put(".ai-sandbox/bin/aisb", LAUNCHER_SH, executable=True)
        w.put(".ai-sandbox/bin/aisb.cmd", LAUNCHER_CMD, crlf=True)
        w.put(".ai-sandbox/bin/aisb.ps1", LAUNCHER_PS1)

    def _install_pyz(self):
        """Write .ai-sandbox/bin/aisb.pyz from the running package (zipapp or source checkout)."""
        import zipfile
        import io
        buf = io.BytesIO()
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        if self.host.zipapp:
            # running from a .pyz: copy it verbatim
            pyz = os.path.abspath(__file__).split(".pyz")[0] + ".pyz"
            with open(pyz, "rb") as fh:
                data = fh.read()
            self.w.put_bytes(".ai-sandbox/bin/aisb.pyz", data, label=".ai-sandbox/bin/aisb.pyz  (single-file aisb)")
            return
        if self.host.frozen:
            # PyInstaller build: the package sources are bundled as data under _internal/aisb; rebuild a pyz from them
            src_root = os.path.join(sys._MEIPASS, "aisb") if hasattr(sys, "_MEIPASS") else pkg_dir  # noqa: SLF001
        else:
            src_root = pkg_dir
        # deterministic archive (fixed timestamps, sorted entries) so re-running sync does not look like drift
        entries = [("__main__.py", b"import sys\nfrom aisb.cli import main\nsys.exit(main())\n")]
        for base, dirs, files in os.walk(src_root):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for fn in sorted(files):
                if fn.endswith((".py", ".json", ".md", ".txt")):
                    full = os.path.join(base, fn)
                    arc = "aisb/" + os.path.relpath(full, src_root).replace("\\", "/")
                    with open(full, "rb") as fh:
                        entries.append((arc, fh.read()))
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for arc, data in entries:
                info = zipfile.ZipInfo(arc, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, data)
        data = b"#!/usr/bin/env python3\n" + buf.getvalue()
        self.w.put_bytes(".ai-sandbox/bin/aisb.pyz", data, label=".ai-sandbox/bin/aisb.pyz  (single-file aisb)")

    def _auditor_md(self):
        return ("---\nname: sandbox-auditor\ndescription: Read-only auditor for the AI sandbox - reviews .ai-sandbox/logs/audit.log, "
                "explains DENY/ASK events, confirms nothing was installed or written outside the workspace, checks generated configs for drift. "
                "Never modifies files.\ntools: Read, Grep, Glob, Bash\nmodel: inherit\n---\n" + AGENT_AUDITOR_BODY)

    def extra_home_prefixes(self):
        out = []
        h = self.host
        if h.is_wsl:
            for drive in "cdefgh":
                base = "/mnt/%s/Users" % drive
                if os.path.isdir(base):
                    for name in os.listdir(base):
                        if name.lower() not in ("public", "default", "default user", "all users"):
                            out.append(os.path.join(base, name))
        if h.is_windows:
            for var in ("APPDATA", "LOCALAPPDATA", "USERPROFILE"):
                if os.environ.get(var):
                    out.append(os.environ[var])
        return out

    # ---- isolated configs the tools see instead of yours ---------------------------------------
    def phase_seed_configs(self):
        w = self.w
        seeds = {
            ".ai-sandbox/config/pip.conf": "[global]\nrequire-virtualenv = true\ncache-dir = %s\ndisable-pip-version-check = true\n"
                                           % self.P(".ai-sandbox", "cache", "pip"),
            ".ai-sandbox/config/npmrc": "# ai-sandbox: npm user config (NPM_CONFIG_USERCONFIG). Project .npmrc still applies.\nfund=false\nupdate-notifier=false\ncache=%s\n"
                                        % self.P(".ai-sandbox", "cache", "npm").replace("\\", "/"),
            ".ai-sandbox/config/npmrc-global": "# ai-sandbox: npm global config (NPM_CONFIG_GLOBALCONFIG), intentionally empty\n",
            ".ai-sandbox/home/kube/config": "apiVersion: v1\nkind: Config\nclusters: []\ncontexts: []\nusers: []\ncurrent-context: \"\"\npreferences: {}\n",
            ".ai-sandbox/home/aws/config": "# ai-sandbox: intentionally empty AWS config\n",
            ".ai-sandbox/home/aws/credentials": "# ai-sandbox: intentionally empty AWS credentials\n",
            ".ai-sandbox/home/docker/config.json": "{}\n",
            ".ai-sandbox/home/terraform/terraformrc": 'plugin_cache_dir = "%s"\ndisable_checkpoint = true\n'
                                                      % self.P(".ai-sandbox", "cache", "terraform-plugins").replace("\\", "/"),
        }
        for rel, content in seeds.items():
            if rel.startswith(".ai-sandbox/home/") and os.path.exists(self.P(*rel.split("/"))) and rel not in self.m.files:
                continue
            w.put(rel, content)
        gitconfig_rel = ".ai-sandbox/home/git/gitconfig"
        if not os.path.exists(self.P(*gitconfig_rel.split("/"))):
            name = email = ""
            if self.host.has["git"]:
                for key in ("user.name", "user.email"):
                    try:
                        r = subprocess.run(["git", "config", "--global", "--get", key], stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL, text=True, timeout=10)
                        if r.returncode == 0:
                            if key == "user.name":
                                name = r.stdout.strip()
                            else:
                                email = r.stdout.strip()
                    except Exception:  # noqa: BLE001
                        pass
            body = "# ai-sandbox: git global config seen by tools (GIT_CONFIG_GLOBAL). Only identity was copied from your real config.\n"
            if name or email:
                body += "[user]\n" + ("\tname = %s\n" % name if name else "") + ("\temail = %s\n" % email if email else "")
            body += "[init]\n\tdefaultBranch = main\n[core]\n\tautocrlf = %s\n" % ("true" if self.host.is_windows else "input")
            w.put(gitconfig_rel, body)
            if name or email:
                self.log.info("git identity (%s <%s>) copied into the sandbox gitconfig" % (name, email))

    # ---- env + activate scripts -----------------------------------------------------------------
    def phase_env_files(self):
        w, h = self.w, self.host
        lines = ["# ai-sandbox environment for THIS machine (generated by `aisb init`; regenerated by `aisb sync`).",
                 "# Root: %s   OS: %s" % (self.root, h.label),
                 "# Format: KEY='value' (single quotes, literal). Sourced by activate.sh, copied to .gemini/.env and to Claude Code env.", ""]
        tier_names = {1: "tier 1 - language tooling confined to the workspace",
                      2: "tier 2 - credential firewall (empty, isolated config for cloud/cluster/git tools)",
                      3: "tier 3 - AI tool homes inside the workspace (opt-in)"}
        last = None
        if any("'" in e.value for e in self.env):
            self.log.warn("your path contains an apostrophe; dotenv-style readers may mis-parse sandbox.env - prefer a path without it")
        for e in self.env:
            if e.tier != last:
                lines += ["", "# ---- %s" % tier_names[e.tier]]
                last = e.tier
            lines.append("%s='%s'" % (e.name, e.value.replace("'", "'\\''")))
        w.put(".ai-sandbox/sandbox.env", "\n".join(lines) + "\n")
        excluded = " ".join(e.name for e in self.env if not e.shell) or "AI_SANDBOX_NOTHING_EXCLUDED"
        w.put(".ai-sandbox/bin/activate.sh", ACTIVATE_SH.replace("@@VENV_BIN@@", h.venv_bin).replace("@@VENV_PY@@", h.venv_py)
              .replace("@@SHELL_EXCLUDED@@", excluded))
        w.put(".ai-sandbox/bin/activate.ps1", self.activate_ps1())
        w.put(".ai-sandbox/bin/activate.cmd", self.activate_cmd(), crlf=True)
        if h.has["direnv"]:
            w.put(".envrc", "# ai-sandbox (direnv detected). Run `direnv allow` once.\ndotenv .ai-sandbox/sandbox.env\nPATH_add .venv/%s\nPATH_add node_modules/.bin\nPATH_add .ai-sandbox/bin\nexport VIRTUAL_ENV=$PWD/.venv\n" % h.venv_bin)

    def activate_ps1(self):
        h = self.host
        out = ["# ai-sandbox: activate in the CURRENT PowerShell session:   . .\\.ai-sandbox\\bin\\activate.ps1",
               "# Only this session's environment changes. Undo with: aisb_deactivate",
               "$script:aisRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\\..')).Path",
               "$env:AI_SANDBOX_ROOT = $script:aisRoot",
               "if (-not $env:AI_SANDBOX_OLD_PATH) { $env:AI_SANDBOX_OLD_PATH = $env:PATH }"]
        for e in self.env:
            line = "$env:%s = %s" % (e.name, q_ps(e.value))
            out.append(line if e.shell else "if ($env:AI_SANDBOX_STRICT -eq '1') { %s }" % line)
        out += ["$env:VIRTUAL_ENV = Join-Path $script:aisRoot '.venv'",
                "foreach ($p in @((Join-Path $script:aisRoot '.venv\\%s'), (Join-Path $script:aisRoot 'node_modules\\.bin'), (Join-Path $script:aisRoot '.ai-sandbox\\bin'))) {" % h.venv_bin,
                "  if (($env:PATH -split [IO.Path]::PathSeparator) -notcontains $p) { $env:PATH = $p + [IO.Path]::PathSeparator + $env:PATH }",
                "}",
                "function global:aisb { & (Join-Path $env:AI_SANDBOX_ROOT '.ai-sandbox\\bin\\aisb.ps1') @args }",
                "function global:sandbox { aisb @args }",
                "function global:aisb_deactivate {",
                "  if ($env:AI_SANDBOX_OLD_PATH) { $env:PATH = $env:AI_SANDBOX_OLD_PATH }",
                "  foreach ($v in @(%s)) { Remove-Item -ErrorAction SilentlyContinue ('Env:' + $v) }" % ", ".join("'%s'" % e.name for e in self.env),
                "  Remove-Item -ErrorAction SilentlyContinue Env:VIRTUAL_ENV, Env:AI_SANDBOX_OLD_PATH, Env:AI_SANDBOX_ROOT",
                "  Remove-Item -ErrorAction SilentlyContinue Function:global:aisb, Function:global:sandbox, Function:global:aisb_deactivate",
                "  Write-Host '[ai-sandbox] deactivated'",
                "}",
                "Write-Host ('[ai-sandbox] active: ' + $script:aisRoot)"]
        return "\n".join(out) + "\n"

    def activate_cmd(self):
        h = self.host
        out = ["@echo off",
               "rem ai-sandbox: activate in the CURRENT cmd.exe window:   call .ai-sandbox\\bin\\activate.cmd",
               "rem Only this window's environment changes. Close the window to undo.",
               'set "AI_SANDBOX_ROOT=%s"' % self.root]
        for e in self.env:
            line = 'set "%s=%s"' % (e.name, e.value)
            out.append(line if e.shell else 'if "%%AI_SANDBOX_STRICT%%"=="1" %s' % line)
        out += ['set "VIRTUAL_ENV=%AI_SANDBOX_ROOT%\\.venv"',
                'set "PATH=%%AI_SANDBOX_ROOT%%\\.venv\\%s;%%AI_SANDBOX_ROOT%%\\node_modules\\.bin;%%AI_SANDBOX_ROOT%%\\.ai-sandbox\\bin;%%PATH%%"' % h.venv_bin,
                'doskey aisb="%AI_SANDBOX_ROOT%\\.ai-sandbox\\bin\\aisb.cmd" $*',
                'doskey sandbox="%AI_SANDBOX_ROOT%\\.ai-sandbox\\bin\\aisb.cmd" $*',
                "echo [ai-sandbox] active: %AI_SANDBOX_ROOT%"]
        return "\n".join(out) + "\n"


def print_next_steps(root, host, opts, log):
    sh = "source ./.ai-sandbox/bin/activate.sh"
    ps = ". .\\.ai-sandbox\\bin\\activate.ps1"
    cmd = "call .ai-sandbox\\bin\\activate.cmd"
    P = log.plain
    P("NEXT STEPS")
    P("  1. Activate the sandbox in every terminal you start an AI tool from:")
    if host.is_windows:
        P("       PowerShell: %s      cmd: %s      Git Bash: %s" % (ps, cmd, sh))
    else:
        P("       %s" % sh)
    P("  2. Start the tool from that terminal inside %s and accept its one-time 'trust this folder' prompt" % root)
    P("     (Claude Code, Gemini CLI, VS Code, Cursor and Copilot only load project settings/hooks from trusted folders).")
    P("  3. Prove it: `aisb verify` must end with RESULT: PASS.   Watch it: `aisb log --follow`.")
    P("  4. Add things: `aisb add mcp|skill|rule|agent|command|hook ...`, `aisb apply profile:design`, then `aisb sync`.")
    P("  5. Keep the AI's context lean: `aisb context <tool>`  |  troubleshoot a tool: `aisb doctor <tool>`.")
    if opts.get("isolate_tool_homes"):
        P("  ! --isolate-tool-homes: Claude/Gemini/Copilot keep their login inside .ai-sandbox/home (git-ignored); log in again once.")
    P("")
    P("ai-sandbox %s, created by %s - %s - %s" % (__version__, __author__, __license_name__, REPO_URL))
    P("Using it? Add yourself to ADOPTERS.md in that repository; it is what keeps the tool formats maintained.")
    _ = TARGETS, _dt, json
