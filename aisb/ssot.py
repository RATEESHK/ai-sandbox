# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""The single source of truth under .ai-sandbox/: rules, skills, agents, commands, hooks.d, mcp servers, bundles lock.

Everything an AI tool needs lives here once; `aisb sync` fans it out to each tool's expected location."""
from __future__ import annotations

import json
import os
import re

from .common import dump_json, load_json, parse_frontmatter, read_text, slugify

COMPONENT_DIRS = {
    "rule": "rules",
    "skill": "skills",
    "agent": "agents",
    "command": "commands",
    "hook": "hooks.d",
}
HOOK_EVENTS = ("pre-tool", "post-tool", "session-start", "session-end", "prompt", "stop")


class Rule:
    def __init__(self, name, path, fm, body):
        self.name, self.path, self.fm, self.body = name, path, fm, body
        self.description = str(fm.get("description", "")).strip()
        self.globs = fm.get("globs") or fm.get("paths") or []
        if isinstance(self.globs, str):
            self.globs = [g.strip() for g in self.globs.split(",") if g.strip()]
        self.always = bool(fm.get("always", not self.globs))
        self.tools = fm.get("tools") or []
        if isinstance(self.tools, str):
            self.tools = [t.strip() for t in self.tools.split(",") if t.strip()]
        try:
            self.order = int(fm.get("order", 100 if name != "sandbox-policy" else 0))
        except (TypeError, ValueError):
            self.order = 100

    def applies_to(self, target_id):
        return not self.tools or target_id in self.tools


class Skill:
    def __init__(self, name, path, fm):
        self.name, self.path, self.fm = name, path, fm
        self.description = str(fm.get("description", "")).strip()


class Agent:
    def __init__(self, name, path, fm, body):
        self.name, self.path, self.fm, self.body = name, path, fm, body
        self.description = str(fm.get("description", "")).strip()
        tools = fm.get("tools") or []
        self.tools = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else list(tools)
        self.model = fm.get("model")


class Command:
    def __init__(self, name, path, fm, body):
        self.name, self.path, self.fm, self.body = name, path, fm, body   # name may be "ns/cmd"
        self.description = str(fm.get("description", "")).strip()
        self.argument_hint = str(fm.get("argument-hint", "")).strip()

    @property
    def ns(self):
        return self.name.split("/")[0] if "/" in self.name else ""

    @property
    def base(self):
        return self.name.split("/")[-1]

    @property
    def flat(self):
        """Single-level name for tools without namespaces: ns-cmd."""
        return self.name.replace("/", "-")

    @property
    def slash(self):
        """How the user invokes it in Claude Code / Gemini CLI."""
        return "/" + self.name.replace("/", ":")


class Hook:
    def __init__(self, name, path, data):
        self.name, self.path, self.data = name, path, data
        self.event = data.get("event", "pre-tool")
        self.matcher = data.get("matcher") or ""
        self.command = data.get("command", "")
        self.timeout = int(data.get("timeout", 30))
        tools = data.get("tools") or []
        self.tools = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else list(tools)

    def applies_to(self, target_id):
        return not self.tools or target_id in self.tools


class SSOT:
    def __init__(self, root):
        self.root = root
        self.dir = os.path.join(root, ".ai-sandbox")

    # ---- paths -------------------------------------------------------------------------
    def P(self, *parts):
        return os.path.join(self.dir, *parts)

    @property
    def lock_path(self):
        return self.P("bundles", "bundles.lock.json")

    # ---- loaders -----------------------------------------------------------------------
    def rules(self):
        out = []
        d = self.P("rules")
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.endswith(".md") and not fn.startswith("."):
                    text = read_text(os.path.join(d, fn))
                    fm, body = parse_frontmatter(text)
                    out.append(Rule(fn[:-3], os.path.join(d, fn), fm, body))
        out.sort(key=lambda r: (r.order, r.name))
        return out

    def skills(self):
        out = []
        d = self.P("skills")
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                sk = os.path.join(d, name, "SKILL.md")
                if os.path.isfile(sk):
                    fm, _ = parse_frontmatter(read_text(sk))
                    out.append(Skill(name, os.path.join(d, name), fm))
        return out

    def agents(self):
        out = []
        d = self.P("agents")
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.endswith(".md"):
                    fm, body = parse_frontmatter(read_text(os.path.join(d, fn)))
                    out.append(Agent(fn[:-3], os.path.join(d, fn), fm, body))
        return out

    def commands(self):
        out = []
        d = self.P("commands")
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                full = os.path.join(d, fn)
                if fn.endswith(".md") and os.path.isfile(full):
                    fm, body = parse_frontmatter(read_text(full))
                    out.append(Command(fn[:-3], full, fm, body))
                elif os.path.isdir(full) and not fn.startswith("."):
                    for fn2 in sorted(os.listdir(full)):
                        if fn2.endswith(".md"):
                            fm, body = parse_frontmatter(read_text(os.path.join(full, fn2)))
                            out.append(Command("%s/%s" % (fn, fn2[:-3]), os.path.join(full, fn2), fm, body))
        return out

    def hooks(self):
        out = []
        d = self.P("hooks.d")
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.endswith(".json"):
                    data = load_json(os.path.join(d, fn), {})
                    if isinstance(data, dict) and data.get("command"):
                        out.append(Hook(fn[:-5], os.path.join(d, fn), data))
        return out

    def mcp_servers(self):
        data = load_json(self.P("mcp", "servers.json"), {}) or {}
        servers = data.get("servers", {}) if isinstance(data, dict) else {}
        return {k: v for k, v in servers.items() if isinstance(v, dict) and v.get("enabled", True)}

    def mcp_all(self):
        data = load_json(self.P("mcp", "servers.json"), {}) or {}
        return data.get("servers", {}) if isinstance(data, dict) else {}

    def save_mcp(self, servers):
        os.makedirs(self.P("mcp"), exist_ok=True)
        with open(self.P("mcp", "servers.json"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dump_json({"_doc": "MCP servers for this project. Fan-out to every tool with `aisb sync`. "
                                        "stdio: command/args/env/cwd; remote: transport=http|sse, url, headers.",
                                "servers": servers}))

    # ---- lock (provenance of imported components) ----------------------------------------
    def lock(self):
        data = load_json(self.lock_path, {}) or {}
        data.setdefault("bundles", {})
        return data

    def save_lock(self, data):
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        with open(self.lock_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")

    # ---- summary -----------------------------------------------------------------------
    def summary(self):
        return {
            "rules": [r.name for r in self.rules()],
            "skills": [s.name for s in self.skills()],
            "agents": [a.name for a in self.agents()],
            "commands": [c.name for c in self.commands()],
            "hooks": [h.name for h in self.hooks()],
            "mcp": sorted(self.mcp_all().keys()),
            "bundles": sorted(self.lock().get("bundles", {}).keys()),
        }


def unique_name(base, existing):
    base = slugify(base)
    if base not in existing:
        return base
    i = 2
    while "%s-%d" % (base, i) in existing:
        i += 1
    return "%s-%d" % (base, i)


def valid_component_name(name):
    return bool(re.match(r"^[a-z0-9][a-z0-9._\-]{0,63}$", name))
