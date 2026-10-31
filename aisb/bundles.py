# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Bundles: import (apply) and export (pack) agentic setups, project-locally.

`aisb apply` understands four shapes:
  1. aisb bundles        - a folder/zip with aisb-bundle.json + rules/ skills/ agents/ commands/ hooks.d/ mcp/servers.json
  2. Claude Code plugins - .claude-plugin/plugin.json (+ skills/ commands/ agents/ hooks/hooks.json .mcp.json)
  3. Claude marketplaces - .claude-plugin/marketplace.json listing plugins (pick with --plugin a,b | all)
  4. skill trees         - any repo with SKILL.md folders (ui-skills, claude-design-skills, vercel agent-skills, gstack ...)

Everything lands in .ai-sandbox/ (the SSOT); `aisb sync` fans it out to each tool. Nothing is installed globally.
Sources are fetched INTO the project (.ai-sandbox/bundles/_src/<name>) with git (preferred) or a zip download.
"""
from __future__ import annotations

import io
import json
import os
import pkgutil
import re
import shutil
import subprocess
import urllib.request
import zipfile

from .common import dump_json, load_json, now_iso, parse_frontmatter, read_text, render_frontmatter, slugify, write_text
from .ssot import SSOT, unique_name

KNOWN_MARKETPLACES = {
    "knowledge-work-plugins": "github:anthropics/knowledge-work-plugins",
    "anthropic-agent-skills": "github:anthropics/skills",
    "anthropic-skills": "github:anthropics/skills",
    "claude-code": "github:anthropics/claude-code",
    "ui-ux-pro-max-skill": "github:nextlevelbuilder/ui-ux-pro-max-skill",
    "impeccable": "github:pbakaus/impeccable",
    "designer-skills": "github:julianoczkowski/designer-skills",
    "claude-animation-skill": "github:buildwithhanif/claude-animation-skill",
}
LICENSE_PATTERNS = [
    ("MIT", r"\bMIT License\b|Permission is hereby granted, free of charge"),
    ("Apache-2.0", r"Apache License\s*,?\s*Version 2\.0"),
    ("BSD", r"Redistribution and use in source and binary forms"),
    ("GPL", r"GNU GENERAL PUBLIC LICENSE|GNU General Public License"),
    ("LGPL", r"GNU LESSER GENERAL PUBLIC LICENSE"),
    ("MPL-2.0", r"Mozilla Public License,? v(?:ersion)? 2\.0"),
    ("PolyForm-Noncommercial", r"PolyForm Noncommercial"),
    ("PolyForm-Strict", r"PolyForm Strict"),
    ("PolyForm-Internal-Use", r"PolyForm Internal Use"),
    ("CC-BY", r"Creative Commons Attribution"),
    ("Unlicense", r"This is free and unencumbered software"),
    ("Proprietary", r"All rights reserved\.?\s*Use is subject to|Commercial Terms of Service"),
]
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".ai-sandbox", "test", "tests", "evals"}


# ======================================================================================
# profiles (built-in recipes)
# ======================================================================================
def builtin_profiles():
    idx = pkgutil.get_data("aisb", "profiles/index.json")
    names = json.loads(idx.decode("utf-8")) if idx else []
    out = {}
    for n in names:
        data = pkgutil.get_data("aisb", "profiles/%s.json" % n)
        if data:
            out[n] = json.loads(data.decode("utf-8"))
    return out


# ======================================================================================
# source resolution + fetch (always inside the project)
# ======================================================================================
def parse_github(spec):
    """github:owner/repo[/sub/dir][@ref]  |  https://github.com/owner/repo[/tree/ref/sub]  |  owner/repo.git url  -> dict or None"""
    spec = spec.strip()
    m = re.match(r"^(?:github:|gh:)([\w.\-]+)/([\w.\-]+?)(?:\.git)?(?:/([^@]+?))?(?:@([\w.\-/]+))?/?$", spec)
    if m:
        return {"owner": m.group(1), "repo": m.group(2), "sub": (m.group(3) or "").strip("/"), "ref": m.group(4) or ""}
    m = re.match(r"^https?://github\.com/([\w.\-]+)/([\w.\-]+?)(?:\.git)?(?:/tree/([\w.\-]+)(?:/(.*))?)?/?$", spec)
    if m:
        return {"owner": m.group(1), "repo": m.group(2), "sub": (m.group(4) or "").strip("/"), "ref": m.group(3) or ""}
    m = re.match(r"^([\w.\-]+)/([\w.\-]+)$", spec)
    if m and not os.path.exists(spec):
        return {"owner": m.group(1), "repo": m.group(2), "sub": "", "ref": ""}
    return None


def fetch_github(root, host, log, gh, name):
    """Clone (depth 1) or download a zip of owner/repo into .ai-sandbox/bundles/_src/<name>. Returns (dir, sha)."""
    dst = os.path.join(root, ".ai-sandbox", "bundles", "_src", name)
    if os.path.isdir(dst):
        shutil.rmtree(dst, onerror=_force_rm)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    url = "https://github.com/%s/%s.git" % (gh["owner"], gh["repo"])
    sha = ""
    if host.has["git"]:
        cmd = ["git", "clone", "--depth", "1", "--quiet"]
        if gh.get("ref"):
            cmd += ["--branch", gh["ref"]]
        cmd += [url, dst]
        log.info("fetch      git clone --depth 1 %s%s" % (url, " @" + gh["ref"] if gh.get("ref") else ""))
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600, env=env)
        if r.returncode != 0:
            log.warn("fetch      git clone failed (%s); trying zip download" % (r.stdout or "").strip()[-200:])
            shutil.rmtree(dst, ignore_errors=True)
        else:
            try:
                r2 = subprocess.run(["git", "-C", dst, "rev-parse", "HEAD"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30)
                sha = r2.stdout.strip()
            except Exception:  # noqa: BLE001
                pass
            shutil.rmtree(os.path.join(dst, ".git"), onerror=_force_rm)
            return dst, sha
    ref = gh.get("ref") or "HEAD"
    zurl = "https://codeload.github.com/%s/%s/zip/%s" % (gh["owner"], gh["repo"], ref if ref == "HEAD" else "refs/heads/" + ref)
    log.info("fetch      downloading %s" % zurl)
    req = urllib.request.Request(zurl, headers={"User-Agent": "aisb"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        data = resp.read()
    _extract_zip(io.BytesIO(data), dst, strip_top=True)
    return dst, ""


def _extract_zip(fobj, dst, strip_top=False):
    os.makedirs(dst, exist_ok=True)
    with zipfile.ZipFile(fobj) as z:
        names = z.namelist()
        top = ""
        if strip_top and names:
            first = names[0].split("/")[0]
            if all(n.split("/")[0] == first for n in names):
                top = first + "/"
        base = os.path.realpath(dst)
        for info in z.infolist():
            name = info.filename
            if top and name.startswith(top):
                name = name[len(top):]
            if not name or name.endswith("/"):
                continue
            target = os.path.realpath(os.path.join(dst, name))
            if not target.startswith(base + os.sep):
                raise RuntimeError("unsafe path in zip: %s" % info.filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def _force_rm(func, path, _exc):
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:  # noqa: BLE001
        pass


# ======================================================================================
# layout detection
# ======================================================================================
def detect_license(d):
    names = sorted(os.listdir(d), key=lambda f: (0 if f.upper().startswith(("LICENSE", "LICENCE", "COPYING")) else 1, f)) if os.path.isdir(d) else []
    for fn in names:
        if fn.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")) and os.path.isfile(os.path.join(d, fn)):
            try:
                text = read_text(os.path.join(d, fn))[:6000]
            except Exception:  # noqa: BLE001
                continue
            for name, pat in LICENSE_PATTERNS:
                if re.search(pat, text, re.IGNORECASE):
                    return name
            return "custom (see %s)" % fn
    # README mention
    for fn in ("README.md", "readme.md", "README"):
        p = os.path.join(d, fn)
        if os.path.isfile(p):
            text = read_text(p)
            m = re.search(r"##?\s*License[^\n]*\n+\s*([^\n]+)", text, re.IGNORECASE)
            if m:
                for name, pat in LICENSE_PATTERNS:
                    if re.search(pat, m.group(1), re.IGNORECASE) or name.lower() in m.group(1).lower():
                        return name + " (README only, no LICENSE file)"
    return "none"


def find_skill_dirs(d, max_depth=4):
    out = []
    base_depth = d.rstrip(os.sep).count(os.sep)
    for base, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        if base.count(os.sep) - base_depth > max_depth:
            dirs[:] = []
            continue
        if "SKILL.md" in files:
            out.append(base)
            dirs[:] = []  # a skill owns its subtree
    return sorted(out)


def detect_layout(d):
    if os.path.isfile(os.path.join(d, "aisb-bundle.json")):
        return "aisb"
    if os.path.isfile(os.path.join(d, ".claude-plugin", "marketplace.json")):
        return "marketplace"
    if os.path.isfile(os.path.join(d, ".claude-plugin", "plugin.json")):
        return "plugin"
    if os.path.isfile(os.path.join(d, "SKILL.md")):
        return "skill"
    if any(os.path.isdir(os.path.join(d, x)) for x in ("skills", "commands", "agents")) or os.path.isfile(os.path.join(d, ".mcp.json")):
        return "plugin"
    if find_skill_dirs(d):
        return "skill-tree"
    return "unknown"


# ======================================================================================
# importer
# ======================================================================================
class Importer:
    def __init__(self, root, host, log, bundle_name, only=None, yes=False, enable_mcp=False):
        self.root, self.host, self.log = root, host, log
        self.name = bundle_name
        self.ssot = SSOT(root)
        self.only = set(x.strip() for x in only.split(",")) if only else None
        self.yes = yes
        self.enable_mcp = enable_mcp
        self.added = {"skills": [], "commands": [], "agents": [], "rules": [], "hooks": [], "mcp": []}
        self.existing_skills = set(s.name for s in self.ssot.skills())
        self.existing_cmds = set(c.name for c in self.ssot.commands())
        self.existing_agents = set(a.name for a in self.ssot.agents())
        self.existing_rules = set(r.name for r in self.ssot.rules())

    def want(self, kind):
        return self.only is None or kind in self.only

    # ---- skills ------------------------------------------------------------------------------
    def import_skill_dir(self, src, prefer_name=None):
        if not self.want("skills"):
            return
        fm, _ = parse_frontmatter(read_text(os.path.join(src, "SKILL.md")))
        name = slugify(prefer_name or fm.get("name") or os.path.basename(src))
        if name in self.existing_skills:
            if name in self.added["skills"]:
                return
            name = unique_name("%s-%s" % (self.name, name), self.existing_skills | set(self.added["skills"]))
        dst = self.ssot.P("skills", name)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".DS_Store"))
        # make sure the frontmatter name matches the folder (tools require it)
        sk = os.path.join(dst, "SKILL.md")
        text = read_text(sk)
        fm2, body = parse_frontmatter(text)
        if not fm2 or fm2.get("name") != name or not fm2.get("description"):
            fm2 = dict(fm2)
            fm2["name"] = name
            fm2.setdefault("description", "Imported skill %s from bundle %s" % (name, self.name))
            write_text(sk, render_frontmatter(fm2) + body if body.startswith("\n") else render_frontmatter(fm2) + "\n" + body)
        self.added["skills"].append(name)
        self.existing_skills.add(name)

    # ---- commands -------------------------------------------------------------------------------
    def import_command_file(self, src, ns=None):
        if not self.want("commands"):
            return
        base = os.path.basename(src)
        stem = slugify(base[:-3])
        fm, body = parse_frontmatter(read_text(src))
        fm = dict(fm)
        fm.setdefault("description", stem.replace("-", " "))
        rel_name = ("%s/%s" % (ns, stem)) if ns else stem
        if rel_name in self.existing_cmds and rel_name not in self.added["commands"]:
            rel_name = "%s/%s" % (ns or self.name, stem)
        dst = self.ssot.P("commands", *rel_name.split("/")) + ".md"
        write_text(dst, render_frontmatter(fm) + "\n" + body.strip("\n") + "\n")
        self.added["commands"].append(rel_name)
        self.existing_cmds.add(rel_name)

    # ---- agents ---------------------------------------------------------------------------------
    def import_agent_file(self, src):
        if not self.want("agents"):
            return
        fm, body = parse_frontmatter(read_text(src))
        fm = dict(fm)
        name = slugify(fm.get("name") or os.path.basename(src)[:-3])
        if name in self.existing_agents and name not in self.added["agents"]:
            name = unique_name("%s-%s" % (self.name, name), self.existing_agents)
        fm["name"] = name
        fm.setdefault("description", "Imported agent %s" % name)
        write_text(self.ssot.P("agents", name + ".md"), render_frontmatter(fm) + "\n" + body.strip("\n") + "\n")
        self.added["agents"].append(name)
        self.existing_agents.add(name)

    # ---- rules ----------------------------------------------------------------------------------
    def import_rule_file(self, src, name=None):
        if not self.want("rules"):
            return
        text = read_text(src)
        fm, body = parse_frontmatter(text)
        name = slugify(name or fm.get("name") or os.path.basename(src).rsplit(".", 1)[0])
        if name == "sandbox-policy":
            name = self.name + "-policy"
        if name in self.existing_rules and name not in self.added["rules"]:
            name = unique_name("%s-%s" % (self.name, name), self.existing_rules)
        fm = {k: v for k, v in fm.items() if k in ("description", "globs", "paths", "always", "tools")}
        write_text(self.ssot.P("rules", name + ".md"), (render_frontmatter(fm) + "\n" if fm else "") + body.strip("\n") + "\n")
        self.added["rules"].append(name)
        self.existing_rules.add(name)

    # ---- hooks (Claude hooks.json format) ---------------------------------------------------------
    _EV = {"PreToolUse": "pre-tool", "PostToolUse": "post-tool", "SessionStart": "session-start", "SessionEnd": "session-end",
           "UserPromptSubmit": "prompt", "Stop": "stop"}

    def import_hooks_json(self, path):
        if not self.want("hooks"):
            return
        data = load_json(path, {}) or {}
        hooks = data.get("hooks", data)
        if not isinstance(hooks, dict):
            return
        n = 0
        for ev, entries in hooks.items():
            mapped = self._EV.get(ev)
            if not mapped or not isinstance(entries, list):
                continue
            for entry in entries:
                for h in (entry.get("hooks") or []) if isinstance(entry, dict) else []:
                    if h.get("type", "command") != "command" or not h.get("command"):
                        continue
                    cmd = h["command"]
                    if "${CLAUDE_PLUGIN_ROOT}" in cmd:
                        cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PROJECT_DIR}/.ai-sandbox/bundles/_src/" + self.name)
                    if not self.yes:
                        self.log.warn("hook       bundle %s defines a %s hook: %s  (not imported; re-run with --yes to accept hooks)" % (self.name, ev, cmd[:120]))
                        continue
                    name = unique_name("%s-%s" % (self.name, mapped), set(x.name for x in self.ssot.hooks()) | set(self.added["hooks"]))
                    rec = {"event": mapped, "command": cmd, "timeout": int(h.get("timeout", 30)), "source": self.name}
                    if entry.get("matcher") and mapped in ("pre-tool", "post-tool"):
                        rec["matcher"] = entry["matcher"]
                    write_text(self.ssot.P("hooks.d", name + ".json"), dump_json(rec))
                    self.added["hooks"].append(name)
                    n += 1
        if n:
            self.log.info("hook       %d hook(s) imported from %s (they run with the tool's permissions; review .ai-sandbox/hooks.d)" % (n, os.path.relpath(path, self.root)))

    # ---- MCP (.mcp.json, Claude/Cursor shape) ------------------------------------------------------
    def import_mcp_json(self, path):
        if not self.want("mcp"):
            return
        data = load_json(path, {}) or {}
        servers = data.get("mcpServers") or data.get("servers") or {}
        if not isinstance(servers, dict) or not servers:
            return
        current = self.ssot.mcp_all()
        for name, s in servers.items():
            if not isinstance(s, dict):
                continue
            key = slugify(name)
            if key in current and key not in self.added["mcp"]:
                key = unique_name("%s-%s" % (self.name, key), set(current))
            entry = {"enabled": True, "source": self.name}
            if s.get("command"):
                entry.update({"transport": "stdio", "command": s["command"], "args": list(s.get("args") or []), "env": dict(s.get("env") or {})})
            elif s.get("url") or s.get("httpUrl") or s.get("serverUrl"):
                entry.update({"transport": "sse" if s.get("type") == "sse" else "http", "url": s.get("url") or s.get("httpUrl") or s.get("serverUrl")})
                if s.get("headers"):
                    entry["headers"] = dict(s["headers"])
            else:
                continue
            if not self.enable_mcp:
                entry["enabled"] = False
                self.log.info("mcp        %s: server %s imported DISABLED (enable it in .ai-sandbox/mcp/servers.json, or apply with --enable-mcp)" % (self.name, key))
            current[key] = entry
            self.added["mcp"].append(key)
        self.ssot.save_mcp(current)

    # ---- layouts -----------------------------------------------------------------------------------
    def import_plugin(self, d, ns=None):
        """A Claude Code plugin directory (or our own layout without a manifest). ns: command namespace (marketplaces)."""
        meta = load_json(os.path.join(d, ".claude-plugin", "plugin.json"), {}) or {}
        declared = meta.get("skills") if isinstance(meta.get("skills"), list) else []
        skill_dirs = []
        for rel in declared:
            p = os.path.normpath(os.path.join(d, rel))
            if os.path.isfile(os.path.join(p, "SKILL.md")):
                skill_dirs.append(p)
            elif os.path.isdir(p):
                skill_dirs += find_skill_dirs(p)
        if os.path.isdir(os.path.join(d, "skills")):
            skill_dirs += find_skill_dirs(os.path.join(d, "skills"))
        if not skill_dirs:  # marketplaces with "source": "./" often keep skills at the repository root
            skill_dirs = find_skill_dirs(d)
        seen = set()
        for sd in skill_dirs:
            if os.path.normpath(sd) in seen:
                continue
            seen.add(os.path.normpath(sd))
            self.import_skill_dir(sd)
        cdir = os.path.join(d, "commands")
        if os.path.isdir(cdir):
            for base, dirs, files in os.walk(cdir):
                dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
                for fn in sorted(files):
                    if fn.endswith(".md"):
                        self.import_command_file(os.path.join(base, fn), ns=ns)
        adir = os.path.join(d, "agents")
        if os.path.isdir(adir):
            for fn in sorted(os.listdir(adir)):
                if fn.endswith(".md"):
                    self.import_agent_file(os.path.join(adir, fn))
        rdir = os.path.join(d, "rules")
        if os.path.isdir(rdir):
            for fn in sorted(os.listdir(rdir)):
                if fn.endswith(".md"):
                    self.import_rule_file(os.path.join(rdir, fn))
        hj = os.path.join(d, "hooks", "hooks.json")
        if os.path.isfile(hj):
            self.import_hooks_json(hj)
        if isinstance(meta.get("hooks"), dict):
            tmp = os.path.join(d, ".claude-plugin", "_inline_hooks.json")
            write_text(tmp, dump_json({"hooks": meta["hooks"]}))
            self.import_hooks_json(tmp)
        mj = os.path.join(d, ".mcp.json")
        if os.path.isfile(mj):
            self.import_mcp_json(mj)
        if isinstance(meta.get("mcpServers"), dict):
            tmp = os.path.join(d, ".claude-plugin", "_inline_mcp.json")
            write_text(tmp, dump_json({"mcpServers": meta["mcpServers"]}))
            self.import_mcp_json(tmp)

    def import_marketplace(self, d, plugins):
        mp = load_json(os.path.join(d, ".claude-plugin", "marketplace.json"), {}) or {}
        entries = mp.get("plugins") or []
        names = [e.get("name") for e in entries if isinstance(e, dict)]
        if not plugins and len(entries) == 1:
            plugins = ["all"]
        if not plugins:
            self.log.info("marketplace %s lists %d plugins: %s" % (mp.get("name", self.name), len(entries), ", ".join(n for n in names if n)[:1500]))
            self.log.fail("pick plugins with --plugin a,b (or --plugin all)")
            return 2
        wanted = None if plugins == ["all"] else set(plugins)
        root_dir = d
        pr = (mp.get("metadata") or {}).get("pluginRoot")
        if pr:
            root_dir = os.path.normpath(os.path.join(d, pr))
        missing = set(wanted or []) - set(names)
        if missing:
            self.log.warn("not in marketplace: %s" % ", ".join(sorted(missing)))
        for e in entries:
            if not isinstance(e, dict) or (wanted is not None and e.get("name") not in wanted):
                continue
            src = e.get("source")
            if isinstance(src, str):
                pdir = os.path.normpath(os.path.join(root_dir, src))
                if os.path.isdir(pdir):
                    self.log.info("plugin     %s (%s)" % (e.get("name"), src))
                    self.import_plugin(pdir, ns=slugify(e.get("name") or src))
                else:
                    self.log.warn("plugin     %s: directory %s not found" % (e.get("name"), src))
            elif isinstance(src, dict) and src.get("source") in ("github", "url", "git-subdir"):
                if src.get("source") == "github":
                    spec = "github:" + src.get("repo", "")
                else:
                    spec = src.get("url", "")
                gh = parse_github(spec)
                if not gh:
                    self.log.warn("plugin     %s: unsupported remote source %s" % (e.get("name"), src))
                    continue
                if src.get("ref"):
                    gh["ref"] = src["ref"]
                sub = src.get("path") or ""
                try:
                    fdir, _sha = fetch_github(self.root, self.host, self.log, gh, "%s--%s" % (self.name, slugify(e.get("name") or gh["repo"])))
                except Exception as exc:  # noqa: BLE001
                    self.log.warn("plugin     %s: fetch failed: %s" % (e.get("name"), exc))
                    continue
                pdir = os.path.join(fdir, sub) if sub else fdir
                lic = detect_license(pdir) if detect_license(pdir) != "none" else detect_license(fdir)
                self.log.info("plugin     %s (remote %s, license: %s)" % (e.get("name"), spec, lic))
                self.import_plugin(pdir, ns=slugify(e.get("name") or gh["repo"]))
            else:
                self.log.warn("plugin     %s: unsupported source %r (npm/archive/command sources are not imported)" % (e.get("name"), src))
        return 0

    def import_skill_tree(self, d):
        for sd in find_skill_dirs(d):
            if os.path.normpath(sd) == os.path.normpath(d):
                self.import_skill_dir(sd, prefer_name=self.name)
            else:
                self.import_skill_dir(sd)
        for sub in ("commands", "agents"):
            p = os.path.join(d, sub)
            if os.path.isdir(p):
                for fn in sorted(os.listdir(p)):
                    if fn.endswith(".md"):
                        (self.import_command_file if sub == "commands" else self.import_agent_file)(os.path.join(p, fn))

    def import_aisb_bundle(self, d):
        meta = load_json(os.path.join(d, "aisb-bundle.json"), {}) or {}
        for sd in find_skill_dirs(os.path.join(d, "skills")) if os.path.isdir(os.path.join(d, "skills")) else []:
            self.import_skill_dir(sd)
        for sub, fn_import in (("rules", self.import_rule_file), ("agents", self.import_agent_file)):
            p = os.path.join(d, sub)
            if os.path.isdir(p):
                for fn in sorted(os.listdir(p)):
                    if fn.endswith(".md"):
                        fn_import(os.path.join(p, fn))
        cdir = os.path.join(d, "commands")
        if os.path.isdir(cdir):
            for base, dirs, files in os.walk(cdir):
                for fn in sorted(files):
                    if fn.endswith(".md"):
                        rel = os.path.relpath(base, cdir).replace("\\", "/")
                        self.import_command_file(os.path.join(base, fn), ns=None if rel == "." else rel)
        hd = os.path.join(d, "hooks.d")
        if os.path.isdir(hd) and self.want("hooks"):
            for fn in sorted(os.listdir(hd)):
                if fn.endswith(".json"):
                    data = load_json(os.path.join(hd, fn), None)
                    if isinstance(data, dict) and data.get("command"):
                        if not self.yes:
                            self.log.warn("hook       %s defines hook %s: %s (skipped; --yes to accept)" % (self.name, fn, data["command"][:100]))
                            continue
                        name = unique_name("%s-%s" % (self.name, fn[:-5]), set(x.name for x in self.ssot.hooks()))
                        data["source"] = self.name
                        write_text(self.ssot.P("hooks.d", name + ".json"), dump_json(data))
                        self.added["hooks"].append(name)
        mj = os.path.join(d, "mcp", "servers.json")
        if os.path.isfile(mj):
            data = load_json(mj, {}) or {}
            tmp = os.path.join(d, "mcp", "_servers_as_mcpjson.json")
            write_text(tmp, dump_json({"mcpServers": data.get("servers", {})}))
            self.import_mcp_json(tmp)
            os.remove(tmp)
        return meta

    def summary(self):
        return {k: v for k, v in self.added.items()}


# ======================================================================================
# apply / remove / pack
# ======================================================================================
def _confirm_license(log, lic, name):
    if lic == "none":
        log.warn("license    %s has NO license file. You can use it locally, but you may not have the right to redistribute it (e.g. inside a bundle you ship)." % name)
    elif lic.startswith("Proprietary"):
        log.warn("license    %s is proprietary (%s). Check its terms before use." % (name, lic))
    else:
        log.info("license    %s: %s" % (name, lic))


def apply_source(root, host, log, source, name=None, only=None, plugin=None, yes=False, sync=False, enable_mcp=False, _depth=0):
    """Returns exit code."""
    if _depth > 2:
        log.fail("apply: too many nested sources")
        return 1
    ssot = SSOT(root)
    lock = ssot.lock()
    plugins = [p.strip() for p in plugin.split(",")] if plugin else None
    # ---- profile
    if source.startswith("profile:"):
        pname = source.split(":", 1)[1]
        profiles = builtin_profiles()
        prof = profiles.get(pname)
        if not prof:
            log.fail("unknown profile %s (available: %s)" % (pname, ", ".join(sorted(profiles))))
            return 2
        log.info("profile    %s - %s" % (pname, prof.get("description", "")))
        rc = 0
        for src in prof.get("sources", []):
            spec = src["source"] if isinstance(src, dict) else src
            if isinstance(src, dict) and src.get("note"):
                log.info("           %s" % src["note"])
            rc |= apply_source(root, host, log, spec, name=(src.get("name") if isinstance(src, dict) else None),
                               only=(src.get("only") if isinstance(src, dict) else None) or only,
                               plugin=",".join(src.get("plugins", [])) if isinstance(src, dict) and src.get("plugins") else plugin,
                               yes=yes, sync=False, enable_mcp=enable_mcp, _depth=_depth + 1)
        prev = ssot.lock().get("bundles", {}).get("profile-" + pname)
        if prev:
            _remove_components(root, log, "profile-" + pname, prev.get("components", {}))
        imp = Importer(root, host, log, slugify("profile-" + pname), only=only, yes=True, enable_mcp=True)
        for rname, text in (prof.get("rules") or {}).items():
            tmp = os.path.join(root, ".ai-sandbox", "cache", "tmp", "rule-%s.md" % rname)
            write_text(tmp, text)
            imp.import_rule_file(tmp, name=rname)
            os.remove(tmp)
        for cname, text in (prof.get("commands") or {}).items():
            tmp = os.path.join(root, ".ai-sandbox", "cache", "tmp", "%s.md" % cname)
            write_text(tmp, text)
            imp.import_command_file(tmp)
            os.remove(tmp)
        for aname, text in (prof.get("agents") or {}).items():
            tmp = os.path.join(root, ".ai-sandbox", "cache", "tmp", "%s.md" % aname)
            write_text(tmp, text)
            imp.import_agent_file(tmp)
            os.remove(tmp)
        if prof.get("mcp"):
            tmp = os.path.join(root, ".ai-sandbox", "cache", "tmp", "mcp-%s.json" % pname)
            write_text(tmp, dump_json({"mcpServers": prof["mcp"]}))
            imp.import_mcp_json(tmp)
            os.remove(tmp)
        if prof.get("claude_settings_local"):
            from .manifest import Manifest, Writer
            m = Manifest(root)
            Writer(root, m, log).merge_json(".claude/settings.local.json", prof["claude_settings_local"], label=".claude/settings.local.json  (profile %s)" % pname)
            m.save()
        lock = ssot.lock()
        lock["bundles"]["profile-" + pname] = {"source": source, "applied": now_iso(), "license": "mixed (see each source)", "components": imp.summary()}
        ssot.save_lock(lock)
        for note in prof.get("notes", []):
            log.info("note       " + note)
        log.done("profile    %s applied%s" % (pname, "" if rc == 0 else " with errors"))
        return rc
    # ---- name@marketplace
    m = re.match(r"^([\w.\-]+)@([\w.\-]+)$", source)
    if m and not os.path.exists(source):
        plug, mk = m.group(1), m.group(2)
        if mk not in KNOWN_MARKETPLACES:
            log.fail("unknown marketplace %s. Known: %s. Or use github:owner/repo --plugin %s" % (mk, ", ".join(KNOWN_MARKETPLACES), plug))
            return 2
        return apply_source(root, host, log, KNOWN_MARKETPLACES[mk], name=name or mk, only=only, plugin=plug, yes=yes, sync=sync, enable_mcp=enable_mcp, _depth=_depth + 1)
    # ---- resolve to a directory
    gh = parse_github(source)
    src_dir, sha, cleanup = None, "", False
    if gh:
        bname = slugify(name or gh["repo"] + ("-" + gh["sub"].replace("/", "-") if gh["sub"] else ""))
        try:
            fdir, sha = fetch_github(root, host, log, gh, bname)
        except Exception as exc:  # noqa: BLE001
            log.fail("fetch      %s: %s" % (source, exc))
            return 1
        src_dir = os.path.join(fdir, gh["sub"]) if gh["sub"] else fdir
        if not os.path.isdir(src_dir):
            log.fail("subdirectory %s not found in %s/%s" % (gh["sub"], gh["owner"], gh["repo"]))
            return 1
        lic = detect_license(src_dir)
        if lic == "none" and gh["sub"]:
            lic = detect_license(fdir)
    elif source.startswith(("http://", "https://")):
        bname = slugify(name or os.path.basename(source.rstrip("/")).rsplit(".", 1)[0] or "bundle")
        dst = os.path.join(root, ".ai-sandbox", "bundles", "_src", bname)
        if source.endswith(".zip"):
            log.info("fetch      downloading %s" % source)
            req = urllib.request.Request(source, headers={"User-Agent": "aisb"})
            with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
                data = resp.read()
            if os.path.isdir(dst):
                shutil.rmtree(dst, onerror=_force_rm)
            _extract_zip(io.BytesIO(data), dst, strip_top=True)
            src_dir = dst
        elif source.endswith(".git") and host.has["git"]:
            if os.path.isdir(dst):
                shutil.rmtree(dst, onerror=_force_rm)
            r = subprocess.run(["git", "clone", "--depth", "1", "--quiet", source, dst], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
            if r.returncode != 0:
                log.fail("git clone failed: %s" % (r.stdout or "").strip()[-200:])
                return 1
            shutil.rmtree(os.path.join(dst, ".git"), onerror=_force_rm)
            src_dir = dst
        else:
            log.fail("unsupported URL (use a github.com URL, a .git URL or a .zip URL)")
            return 2
        lic = detect_license(src_dir)
    else:
        p = os.path.abspath(source)
        if os.path.isfile(p) and p.endswith(".zip"):
            bname = slugify(name or os.path.basename(p)[:-4].replace(".aisb", ""))
            dst = os.path.join(root, ".ai-sandbox", "bundles", "_src", bname)
            if os.path.isdir(dst):
                shutil.rmtree(dst, onerror=_force_rm)
            with open(p, "rb") as fh:
                _extract_zip(io.BytesIO(fh.read()), dst, strip_top=not os.path.basename(p).endswith(".aisb.zip"))
            src_dir = dst
        elif os.path.isdir(p):
            bname = slugify(name or os.path.basename(p.rstrip(os.sep)))
            src_dir = p
        else:
            log.fail("source not found: %s" % source)
            return 2
        lic = detect_license(src_dir)
    layout = detect_layout(src_dir)
    if bname in lock.get("bundles", {}):
        log.info("apply      %s was applied before; replacing its components" % bname)
        _remove_components(root, log, bname, lock["bundles"][bname].get("components", {}))
    _confirm_license(log, lic, bname)
    log.info("apply      %s  layout=%s  -> .ai-sandbox/" % (bname, layout))
    imp = Importer(root, host, log, bname, only=only, yes=yes, enable_mcp=enable_mcp)
    rc = 0
    if layout == "aisb":
        meta = imp.import_aisb_bundle(src_dir)
        if meta.get("notes"):
            for n in meta["notes"]:
                log.info("note       " + str(n))
    elif layout == "marketplace":
        rc = imp.import_marketplace(src_dir, plugins) or 0
    elif layout == "plugin":
        imp.import_plugin(src_dir)
    elif layout == "skill":
        imp.import_skill_dir(src_dir, prefer_name=bname if not parse_frontmatter(read_text(os.path.join(src_dir, "SKILL.md")))[0].get("name") else None)
    elif layout == "skill-tree":
        imp.import_skill_tree(src_dir)
        if os.path.isfile(os.path.join(src_dir, "setup")) or os.path.isfile(os.path.join(src_dir, "setup.ps1")):
            log.warn("this repository ships its own installer (setup); only the skill documents were imported. Helper binaries/scripts it expects "
                     "under ~/.claude are NOT installed (that would be global). Skills referencing them may need adaptation.")
    else:
        log.fail("could not recognise the layout of %s (no aisb-bundle.json, .claude-plugin/, SKILL.md, skills/ or commands/)" % bname)
        rc = 2
    if rc:
        return rc
    summ = imp.summary()
    total = sum(len(v) for v in summ.values())
    lock = ssot.lock()
    lock["bundles"][bname] = {"source": source, "sha": sha, "license": lic, "layout": layout, "applied": now_iso(), "components": summ}
    ssot.save_lock(lock)
    log.done("apply      %s: %s" % (bname, ", ".join("%s=%d" % (k, len(v)) for k, v in summ.items() if v) or "nothing new"))
    if total and layout in ("skill-tree", "plugin", "marketplace"):
        log.info("           skills: %s" % ", ".join(summ["skills"][:30]) + (" ..." if len(summ["skills"]) > 30 else ""))
    _ = cleanup
    return 0


def remove_bundle(root, host, log, name):
    ssot = SSOT(root)
    lock = ssot.lock()
    b = lock["bundles"].get(name)
    if not b:
        log.fail("no applied bundle named %s (aisb list bundles)" % name)
        return 1
    comps = b.get("components", {})
    _remove_components(root, log, name, comps)
    src = os.path.join(root, ".ai-sandbox", "bundles", "_src", name)
    if os.path.isdir(src):
        shutil.rmtree(src, onerror=_force_rm)
    for d in os.listdir(os.path.join(root, ".ai-sandbox", "bundles", "_src")) if os.path.isdir(os.path.join(root, ".ai-sandbox", "bundles", "_src")) else []:
        if d.startswith(name + "--"):
            shutil.rmtree(os.path.join(root, ".ai-sandbox", "bundles", "_src", d), onerror=_force_rm)
    lock = ssot.lock()
    del lock["bundles"][name]
    ssot.save_lock(lock)
    log.done("removed    bundle %s (%s)" % (name, ", ".join("%s=%d" % (k, len(v)) for k, v in comps.items() if v)))
    _ = host
    return 0


def _remove_components(root, log, name, comps):
    ssot = SSOT(root)
    from .manifest import Manifest, Writer
    m = Manifest(root)
    w = Writer(root, m, log)
    for sk in comps.get("skills", []):
        p = ssot.P("skills", sk)
        if os.path.isdir(p):
            shutil.rmtree(p)
        for rel in list(m.files):
            if "/skills/%s/" % sk in rel:
                w.forget(rel)
    for c in comps.get("commands", []):
        p = ssot.P("commands", *c.split("/")) + ".md"
        if os.path.isfile(p):
            os.remove(p)
        for rel in list(m.files):
            if rel.endswith("/%s.md" % c) or rel.endswith("/%s.toml" % c) or rel.endswith("/%s.prompt.md" % c) or rel.endswith("/%s.md" % c.replace("/", "-")):
                w.forget(rel)
    for a in comps.get("agents", []):
        p = ssot.P("agents", a + ".md")
        if os.path.isfile(p):
            os.remove(p)
        for rel in list(m.files):
            if "/agents/" in rel and (rel.endswith("/%s.md" % a) or rel.endswith("/%s.agent.md" % a)):
                w.forget(rel)
    for r in comps.get("rules", []):
        p = ssot.P("rules", r + ".md")
        if os.path.isfile(p):
            os.remove(p)
        for rel in list(m.files):
            if "/rules/" in rel and rel.split("/")[-1].split(".")[0] == r or rel.endswith("/instructions/%s.instructions.md" % r):
                w.forget(rel)
    for h in comps.get("hooks", []):
        p = ssot.P("hooks.d", h + ".json")
        if os.path.isfile(p):
            os.remove(p)
    if comps.get("mcp"):
        servers = ssot.mcp_all()
        for sname in comps["mcp"]:
            servers.pop(sname, None)
        ssot.save_mcp(servers)
    m.save()
    _ = name


def pack(root, host, log, out=None, name=None, description="", include_policy=False):
    ssot = SSOT(root)
    name = slugify(name or os.path.basename(root.rstrip(os.sep)))
    out = out or os.path.join(root, "%s.aisb.zip" % name)
    comps = ssot.summary()
    comps["rules"] = [r for r in comps["rules"] if r != "sandbox-policy"]
    comps["skills"] = [x for x in comps["skills"] if x != "local-env-manager"]
    comps["agents"] = [x for x in comps["agents"] if x != "sandbox-auditor"]
    meta = {"name": name, "description": description, "version": "1", "created": now_iso(), "kit": "aisb", "format": 1,
            "components": comps, "notes": ["Apply with: aisb apply %s.aisb.zip" % name,
                                           "Third-party skills keep their own licenses (see .ai-sandbox/bundles/bundles.lock.json in the source project)."]}
    lock = ssot.lock()
    if lock.get("bundles"):
        meta["provenance"] = {k: {kk: vv for kk, vv in v.items() if kk in ("source", "sha", "license")} for k, v in lock["bundles"].items()}
    n = 0
    base_components = {("rules", "sandbox-policy.md"), ("agents", "sandbox-auditor.md")}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("aisb-bundle.json", dump_json(meta))
        for sub in ("rules", "skills", "agents", "commands", "hooks.d"):
            base = ssot.P(sub)
            if not os.path.isdir(base):
                continue
            for b, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git") and not (sub == "skills" and b == base and d == "local-env-manager")]
                for fn in files:
                    if fn == "README.md" and sub == "hooks.d":
                        continue
                    if b == base and (sub, fn) in base_components:
                        continue  # every sandboxed project already has these
                    full = os.path.join(b, fn)
                    z.write(full, os.path.relpath(full, ssot.dir).replace("\\", "/"))
                    n += 1
        mj = ssot.P("mcp", "servers.json")
        if os.path.isfile(mj):
            data = load_json(mj, {}) or {}
            servers = data.get("servers", {})
            scrubbed = {}
            for k, v in servers.items():
                vv = dict(v)
                if vv.get("env"):
                    vv["env"] = {ek: ("${%s}" % ek if re.search(r"(token|secret|key|password)", ek, re.IGNORECASE) and not str(ev).startswith("${") else ev) for ek, ev in vv["env"].items()}
                if vv.get("headers"):
                    vv["headers"] = {hk: ("${%s}" % hk.upper().replace("-", "_") if re.search(r"(authorization|token|key)", hk, re.IGNORECASE) else hv) for hk, hv in vv["headers"].items()}
                scrubbed[k] = vv
            z.writestr("mcp/servers.json", dump_json({"servers": scrubbed}))
            n += 1
        if include_policy and os.path.isfile(ssot.P("policy.json")):
            z.write(ssot.P("policy.json"), "policy.json")
            n += 1
        readme = ("# %s\n\n%s\n\nAn ai-sandbox bundle. Apply into any project with:\n\n    aisb apply %s\n\n"
                  "Contents: %s\n" % (name, description or "", os.path.basename(out), ", ".join("%s=%d" % (k, len(v)) for k, v in comps.items() if v)))
        z.writestr("README.md", readme)
    log.done("pack       %s (%d files; secrets in MCP env/headers replaced by ${VAR} placeholders)" % (out, n))
    log.info("           share it, or push the extracted folder to GitHub and let others run: aisb apply github:you/%s" % name)
    _ = host
    return 0
