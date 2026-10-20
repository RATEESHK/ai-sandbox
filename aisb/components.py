# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""`aisb add|remove|list`: manage SSOT components (MCP servers, skills, rules, agents, commands, hooks)."""
from __future__ import annotations

import os
import re
import shutil

from .common import dump_json, parse_frontmatter, read_text, render_frontmatter, slugify, write_text
from .ssot import SSOT, valid_component_name
from .targets import DEFAULT_TOOLS, TARGETS, parse_tool_list

RULE_TEMPLATE = """---
description: {description}
{globs_line}---
# {title}

<!-- Write the instruction here. Keep it short and imperative; it is sent to every AI tool on every session
     (or when a matching file is touched, if globs are set). Run `aisb sync` after editing. -->
"""

AGENT_TEMPLATE = """---
name: {name}
description: {description}
tools: Read, Grep, Glob, Bash
model: inherit
---
You are the **{name}** sub-agent for this project.

<!-- Describe the job, the inputs it expects, the exact steps, and the output format. Keep it read-only unless the
     user explicitly wants it to edit files. Run `aisb sync` after editing. -->
"""

COMMAND_TEMPLATE = """---
description: {description}
argument-hint: "[what the user passes after /{name}]"
---
<!-- Slash command /{name}. $ARGUMENTS is replaced with what the user typed after the command.
     Claude Code, Gemini CLI (/{name}), Cursor, Copilot prompt files and Windsurf workflows all receive this text. -->

Task: {description}

Arguments: $ARGUMENTS
"""


def _ssot(root):
    return SSOT(root)


def _check_name(name, log):
    if not name:
        log.fail("a name is required")
        return False
    if not valid_component_name(name):
        log.fail("invalid name %r (use lowercase letters, digits, '-', '_' or '.')" % name)
        return False
    return True


def _guard_check(root, host, command, log):
    """Run the project's own guard on a command before registering it (hooks, MCP stdio commands)."""
    import json
    import subprocess
    from .manifest import Manifest
    m = Manifest(root)
    rt = m.data.get("runtime", {}) or {}
    if rt.get("mode") == "binary" and os.path.isfile(rt.get("exe") or ""):
        cmd = [rt["exe"], "guard"]
    else:
        py = m.data.get("hook_python") or host.python
        guard = os.path.join(root, ".ai-sandbox", "hooks", "sandbox_guard.py")
        if not (py and os.path.isfile(py) and os.path.isfile(guard)):
            return True
        cmd = [py, guard]
    payload = json.dumps({"cwd": root, "tool_name": "Bash", "tool_input": {"command": command}})
    try:
        r = subprocess.run(cmd + ["--tool", "generic", "--event", "pre"], input=payload, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, timeout=30, cwd=root)
    except Exception as exc:  # noqa: BLE001
        log.warn("could not run the guard to check the command: %s" % exc)
        return True
    if r.returncode == 2:
        log.fail("the sandbox guard rejects this command: %s" % r.stderr.strip()[:300])
        return False
    return True


# ======================================================================================
# add
# ======================================================================================
def cmd_add(root, host, log, args):
    kind = args.kind
    s = _ssot(root)
    tools = None
    if args.tools:
        res = parse_tool_list(args.tools)
        if isinstance(res, tuple):
            log.fail("unknown tools: %s" % ", ".join(res[1]))
            return 2
        tools = res
    if kind == "mcp":
        return add_mcp(root, host, log, s, args)
    if kind == "skill":
        return add_skill(root, host, log, s, args)
    if kind == "rule":
        if not _check_name(args.name, log):
            return 2
        path = s.P("rules", args.name + ".md")
        if os.path.exists(path) and not args.src and not args.text:
            log.fail("rule %s already exists (%s)" % (args.name, path))
            return 1
        if args.src:
            text = read_text(args.src)
            fm, body = parse_frontmatter(text)
        else:
            fm, body = {}, args.text
        fm = dict(fm)
        if args.description:
            fm["description"] = args.description
        if args.globs:
            fm["globs"] = [g.strip() for g in args.globs.split(",") if g.strip()]
        if tools:
            fm["tools"] = tools
        if body is None:
            content = RULE_TEMPLATE.format(description=fm.get("description") or args.name.replace("-", " "),
                                           globs_line=("globs: [%s]\n" % ", ".join(fm["globs"])) if fm.get("globs") else "",
                                           title=args.name.replace("-", " ").title())
            if tools:
                content = content.replace("---\n#", "tools: [%s]\n---\n#" % ", ".join(tools), 1)
        else:
            content = (render_frontmatter(fm) + "\n" if fm else "") + body.strip("\n") + "\n"
        write_text(path, content)
        log.done("rule       .ai-sandbox/rules/%s.md%s" % (args.name, "" if (args.src or args.text) else "  <- edit this file, then `aisb sync`"))
        return 0
    if kind == "agent":
        if not _check_name(args.name, log):
            return 2
        path = s.P("agents", args.name + ".md")
        if os.path.exists(path) and not args.src and not args.text:
            log.fail("agent %s already exists" % args.name)
            return 1
        if args.src:
            text = read_text(args.src)
            fm, body = parse_frontmatter(text)
            fm = dict(fm)
            fm["name"] = args.name
            if args.description:
                fm["description"] = args.description
            content = render_frontmatter(fm) + "\n" + body.strip("\n") + "\n"
        elif args.text:
            content = render_frontmatter({"name": args.name, "description": args.description or args.name, "tools": "Read, Grep, Glob, Bash", "model": "inherit"}) + "\n" + args.text.strip("\n") + "\n"
        else:
            content = AGENT_TEMPLATE.format(name=args.name, description=args.description or ("%s sub-agent" % args.name))
        write_text(path, content)
        log.done("agent      .ai-sandbox/agents/%s.md%s" % (args.name, "" if (args.src or args.text) else "  <- edit this file, then `aisb sync`"))
        return 0
    if kind == "command":
        if not _check_name(args.name, log):
            return 2
        path = s.P("commands", args.name + ".md")
        if os.path.exists(path) and not args.src and not args.text:
            log.fail("command %s already exists" % args.name)
            return 1
        if args.src:
            text = read_text(args.src)
            fm, body = parse_frontmatter(text)
            fm = dict(fm)
            if args.description:
                fm["description"] = args.description
            fm.setdefault("description", args.name)
            content = render_frontmatter(fm) + "\n" + body.strip("\n") + "\n"
        elif args.text:
            content = render_frontmatter({"description": args.description or args.name}) + "\n" + args.text.strip("\n") + "\n"
        else:
            content = COMMAND_TEMPLATE.format(name=args.name, description=args.description or args.name.replace("-", " "))
        write_text(path, content)
        log.done("command    .ai-sandbox/commands/%s.md  -> /%s in Claude Code, Gemini CLI, Cursor, Copilot, Windsurf%s"
                 % (args.name, args.name, "" if (args.src or args.text) else "  <- edit this file, then `aisb sync`"))
        return 0
    if kind == "hook":
        if not _check_name(args.name, log):
            return 2
        if not args.command:
            log.fail("--command is required for a hook, e.g. --command \"npx prettier --write .\"")
            return 2
        if not _guard_check(root, host, args.command, log):
            return 1
        data = {"event": args.event, "command": args.command, "timeout": args.timeout}
        if args.matcher:
            data["matcher"] = args.matcher
        if tools:
            data["tools"] = tools
        if args.description:
            data["description"] = args.description
        write_text(s.P("hooks.d", args.name + ".json"), dump_json(data))
        log.done("hook       .ai-sandbox/hooks.d/%s.json  (%s%s -> %s)" % (args.name, args.event, " matcher=%s" % args.matcher if args.matcher else "", args.command))
        return 0
    log.fail("unknown kind %s" % kind)
    return 2


def add_mcp(root, host, log, s, args):
    name = args.name
    if not _check_name(name, log):
        return 2
    servers = s.mcp_all()
    if name in servers and not getattr(args, "force", False):
        log.info("mcp        %s exists; updating it" % name)
    entry = {"enabled": True}
    if args.url:
        entry["transport"] = args.transport or ("sse" if args.url.rstrip("/").endswith("/sse") else "http")
        entry["url"] = args.url
        if args.header:
            headers = {}
            for h in args.header:
                if ":" in h:
                    k, v = h.split(":", 1)
                    headers[k.strip()] = v.strip()
            entry["headers"] = headers
    elif args.command:
        entry["transport"] = "stdio"
        cmdline = args.command
        argv = []
        if args.args:
            argv = [a for a in re.split(r",\s*", args.args) if a != ""]
        # allow `--command "npx -y @scope/server ."` with embedded args
        parts = cmdline.split()
        if len(parts) > 1 and not argv:
            cmdline, argv = parts[0], parts[1:]
        entry["command"] = cmdline
        entry["args"] = argv
        if not _guard_check(root, host, " ".join([cmdline] + argv), log):
            return 1
        if cmdline in ("npx", "npx.cmd") and "-y" not in argv and "--yes" not in argv:
            log.info("mcp        tip: npx will prompt to install the package; add '-y' as the first arg for unattended starts")
    else:
        log.fail("give --url <http(s) url> for a remote server or --command <exe> [--args a,b,c] for a local (stdio) server")
        return 2
    if args.env:
        env = {}
        for kv in args.env:
            if "=" in kv:
                k, v = kv.split("=", 1)
                env[k.strip()] = v
        entry["env"] = env
        for k, v in env.items():
            if re.search(r"(token|secret|key|password|passwd)", k, re.IGNORECASE) and v and not v.startswith("${"):
                log.warn("mcp        %s looks like a secret; it is stored in .ai-sandbox/mcp/servers.json and fanned out to tool configs in this folder. Prefer a ${ENV_VAR} reference." % k)
    if args.description:
        entry["description"] = args.description
    if args.tools:
        entry["tools"] = [t.strip() for t in args.tools.split(",") if t.strip()]
    servers[name] = entry
    s.save_mcp(servers)
    where = []
    for tid in DEFAULT_TOOLS:
        mcp = TARGETS[tid].get("mcp") or {}
        if mcp.get("file"):
            where.append(mcp["file"])
        elif mcp.get("sidecar"):
            where.append(mcp["sidecar"] + " (paste into %s)" % TARGETS[tid]["title"])
    log.done("mcp        %s (%s) saved to .ai-sandbox/mcp/servers.json; sync writes: %s" % (name, entry["transport"], ", ".join(where)))
    return 0


def add_skill(root, host, log, s, args):
    """`aisb add skill <name> --from <dir>`  |  `aisb add skill <source>` where source is a dir with SKILL.md,
    a github:owner/repo[/subdir] reference or a URL (delegated to the bundle importer)."""
    src = args.src or args.name
    if not src:
        log.fail("usage: aisb add skill <name> --from <dir-with-SKILL.md>   |   aisb add skill github:owner/repo[/subdir]")
        return 2
    if src.startswith(("github:", "http://", "https://", "gh:")) or src.endswith(".zip"):
        from .bundles import apply_source
        return apply_source(root, host, log, src, name=None, only="skills", plugin=None, yes=True, sync=False)
    if not os.path.isdir(src):
        log.fail("%s is not a directory" % src)
        return 2
    sk = os.path.join(src, "SKILL.md")
    if not os.path.isfile(sk):
        log.fail("%s has no SKILL.md" % src)
        return 2
    fm, _ = parse_frontmatter(read_text(sk))
    name = args.name if (args.src and args.name) else (fm.get("name") or os.path.basename(os.path.abspath(src)))
    name = slugify(name)
    dst = s.P("skills", name)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
    log.done("skill      .ai-sandbox/skills/%s (from %s)" % (name, src))
    return 0


# ======================================================================================
# remove
# ======================================================================================
def cmd_remove(root, host, log, args):
    s = _ssot(root)
    kind, name = args.kind, args.name
    if kind == "bundle":
        from .bundles import remove_bundle
        return remove_bundle(root, host, log, name)
    if kind == "mcp":
        servers = s.mcp_all()
        if name not in servers:
            log.fail("no MCP server named %s" % name)
            return 1
        del servers[name]
        s.save_mcp(servers)
        log.done("mcp        removed %s" % name)
        return 0
    paths = {"skill": s.P("skills", name), "rule": s.P("rules", name + ".md"), "agent": s.P("agents", name + ".md"),
             "command": s.P("commands", name + ".md"), "hook": s.P("hooks.d", name + ".json")}
    path = paths[kind]
    if not os.path.exists(path):
        log.fail("no %s named %s" % (kind, name))
        return 1
    if kind == "rule" and name == "sandbox-policy":
        log.fail("sandbox-policy is the mandatory policy; edit it instead of removing it")
        return 1
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
    # delete generated copies tracked in the manifest
    from .manifest import Manifest, Writer
    m = Manifest(root)
    w = Writer(root, m, log)
    pattern = {"skill": "/skills/%s/" % name, "rule": "/%s" % name, "agent": "/%s" % name, "command": "/%s" % name, "hook": None}[kind]
    if pattern:
        for rel in list(m.files.keys()):
            if rel.startswith(".ai-sandbox/"):
                continue
            base = os.path.basename(rel)
            stem = base.split(".")[0]
            if (kind == "skill" and pattern in rel) or (kind in ("rule", "agent", "command") and stem == name and "/" + {
                    "rule": "rules", "agent": "agents", "command": "commands"}[kind] in rel) or \
               (kind == "rule" and rel == ".claude/rules/%s.md" % name) or (kind == "command" and rel.endswith("/%s.md" % name) and "/workflows/" in rel):
                w.forget(rel)
    m.save()
    log.done("%-10s removed %s" % (kind, name))
    return 0


# ======================================================================================
# list
# ======================================================================================
def cmd_list(root, host, log, what):
    s = _ssot(root)
    P = log.plain
    if what in ("all", "components"):
        P("rules      " + ", ".join("%s%s" % (r.name, "[%s]" % ",".join(r.globs) if r.globs else "") for r in s.rules()))
        P("skills     " + ", ".join(sk.name for sk in s.skills()))
        P("agents     " + ", ".join(a.name for a in s.agents()))
        P("commands   " + (", ".join("/" + c.name for c in s.commands()) or "-"))
        P("hooks      " + (", ".join("%s(%s)" % (h.name, h.event) for h in s.hooks()) or "-"))
        servers = s.mcp_all()
        P("mcp        " + (", ".join("%s(%s%s)" % (n, v.get("transport", "stdio"), "" if v.get("enabled", True) else ",disabled") for n, v in servers.items()) or "-"))
    if what in ("all", "bundles"):
        lock = s.lock()
        if lock.get("bundles"):
            P("bundles")
            for n, b in sorted(lock["bundles"].items()):
                P("  %-24s %s  (%s)  license=%s  %s" % (n, b.get("source", ""), b.get("ref") or b.get("sha", "")[:7] or "", b.get("license", "?"),
                                                      ", ".join("%s=%d" % (k, len(v)) for k, v in sorted(b.get("components", {}).items()) if v)))
        else:
            P("bundles    -")
    if what in ("all", "profiles"):
        from .bundles import builtin_profiles
        P("profiles   " + ", ".join(sorted(builtin_profiles().keys())))
    if what == "targets":
        from .cli import cmd_targets
        cmd_targets(log)
    _ = host
    return 0
