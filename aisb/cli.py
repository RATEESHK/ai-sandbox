# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""aisb command line."""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import traceback

from . import REPO_URL, __author__, __license_name__, __version__
from .common import Log
from .host import Host
from .manifest import Manifest
from .targets import ALL_TOOLS, DEFAULT_TOOLS, TARGETS, parse_tool_list, resolve

EPILOG = """commands:
  init | install     create or refresh the sandbox in this folder (idempotent; ends with verify)
  sync               regenerate every tool file from .ai-sandbox/ (after editing rules, policy, skills ...)
  verify             prove isolation: venv, guard self-test, hook protocols, drift, env, user-level configs
  status | log       summary / audit trail (log: -n N, --follow, --denied, --json)
  uninstall          remove exactly what aisb created, restore what it merged into
  add                add a component to the SSOT: mcp | skill | rule | agent | command | hook
  remove             remove a component or an applied bundle
  list               list components, applied bundles and targets
  apply              import a bundle / plugin / skill pack / profile (local path, zip, github:owner/repo, profile:name)
  pack               export this project's agentic setup as a shareable bundle (.aisb.zip)
  context            write the ignore file(s) that keep an AI tool's context lean:  aisb context cursor|antigravity|all
  doctor             troubleshoot one tool (local fixes applied, global steps printed):  aisb doctor antigravity
  runtime            project-local runtimes:  aisb runtime python [--version 3.12]
  clean              delete fetched bundle sources / caches / logs (--src --cache --logs --all)
  targets            supported tools and what is generated for each
  guard              (internal) the hook entry point used by the tools
"""


def build_parser():
    p = argparse.ArgumentParser(prog="aisb", description="ai-sandbox: project-local, OS-aware sandbox for AI coding agents.",
                                epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version",
                   version="aisb %s - ai-sandbox, created by %s - %s - %s - see LICENSE and NOTICE"
                   % (__version__, __author__, __license_name__, REPO_URL))
    p.add_argument("--root", default=None, help="project folder (default: current directory)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    for name in ("init", "install", "sync"):
        s = sub.add_parser(name, help=argparse.SUPPRESS)
        s.add_argument("--tools", default=None, help="comma list from: %s | all  (default: %s)" % (",".join(ALL_TOOLS), ",".join(DEFAULT_TOOLS)))
        s.add_argument("--no-venv", action="store_true", help="do not create .venv; hooks use the interpreter running aisb")
        s.add_argument("--python", default=None, help="interpreter used to create .venv")
        s.add_argument("--no-credential-firewall", action="store_true", help="do not redirect aws/gcloud/az/kube/docker/gh/git-global/XDG into the sandbox")
        s.add_argument("--isolate-tool-homes", action="store_true", help="also point CLAUDE_CONFIG_DIR / GEMINI_CLI_HOME / COPILOT_HOME into the sandbox")
        s.add_argument("--no-os-sandbox", action="store_true", help="do not enable Claude Code's kernel sandbox even if available")
        s.add_argument("--cursor-windows-shell", choices=("cmd", "powershell"), default=None, help="shell Cursor uses for hooks on Windows (default cmd)")
        s.add_argument("--profile", default=None, help="apply a built-in profile after init (e.g. design, motion-design, boris-workflow)")
        s.add_argument("--force", action="store_true", help="regenerate files even if you modified them (backups are kept)")
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--yes", "-y", action="store_true", help="accepted for compatibility; init is non-interactive")
        s.add_argument("--skip-verify", action="store_true")
    s = sub.add_parser("verify", help=argparse.SUPPRESS)
    s.add_argument("--quick", action="store_true", help="skip protocol smoke tests")
    s = sub.add_parser("uninstall", help=argparse.SUPPRESS)
    s.add_argument("--purge-venv", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--yes", "-y", action="store_true")
    sub.add_parser("status", help=argparse.SUPPRESS)
    s = sub.add_parser("log", help=argparse.SUPPRESS)
    s.add_argument("-n", type=int, default=50)
    s.add_argument("--follow", "-f", action="store_true")
    s.add_argument("--json", action="store_true", help="show audit.jsonl instead of audit.log")
    s.add_argument("--denied", action="store_true", help="only DENY/ASK lines")
    s = sub.add_parser("guard", help=argparse.SUPPRESS, add_help=False)
    s.add_argument("rest", nargs=argparse.REMAINDER)
    # components
    s = sub.add_parser("add", help=argparse.SUPPRESS)
    s.add_argument("kind", choices=("mcp", "skill", "rule", "agent", "command", "hook"))
    s.add_argument("name", nargs="?", help="component name (or source for skill: path | github:owner/repo[/sub] | url)")
    s.add_argument("--command", default=None, help="mcp (stdio) / hook: command to run")
    s.add_argument("--args", default=None, help="mcp: arguments, comma-separated (use quotes for spaces)")
    s.add_argument("--url", default=None, help="mcp: remote server URL (http/sse)")
    s.add_argument("--transport", choices=("stdio", "http", "sse"), default=None)
    s.add_argument("--env", action="append", default=[], help="mcp: KEY=VALUE (repeatable; values never leave the project)")
    s.add_argument("--header", action="append", default=[], help="mcp: Header: value (repeatable)")
    s.add_argument("--from", dest="src", default=None, help="skill/agent/rule/command: file or directory to import")
    s.add_argument("--text", default=None, help="rule/agent/command: body text (otherwise a template is written for you to edit)")
    s.add_argument("--description", default=None)
    s.add_argument("--globs", default=None, help="rule: comma-separated globs (file-scoped rule)")
    s.add_argument("--event", choices=("pre-tool", "post-tool", "session-start", "session-end", "prompt", "stop"), default="post-tool", help="hook event")
    s.add_argument("--matcher", default=None, help="hook: tool-name regex (pre/post-tool)")
    s.add_argument("--timeout", type=int, default=30)
    s.add_argument("--tools", default=None, help="limit fan-out to these tools (comma list)")
    s.add_argument("--no-sync", action="store_true", help="do not run sync afterwards")
    s = sub.add_parser("remove", help=argparse.SUPPRESS)
    s.add_argument("kind", choices=("mcp", "skill", "rule", "agent", "command", "hook", "bundle"))
    s.add_argument("name")
    s.add_argument("--no-sync", action="store_true")
    s = sub.add_parser("list", help=argparse.SUPPRESS)
    s.add_argument("what", nargs="?", default="all", choices=("all", "components", "bundles", "targets", "profiles"))
    s = sub.add_parser("apply", help=argparse.SUPPRESS)
    s.add_argument("source", help="path/dir/zip, github:owner/repo[/subdir][@ref], https://... .git/.zip, profile:<name>, name@marketplace")
    s.add_argument("--name", default=None, help="bundle name (default: derived from the source)")
    s.add_argument("--only", default=None, help="comma list of component kinds to import (skills,commands,agents,rules,hooks,mcp)")
    s.add_argument("--plugin", default=None, help="for marketplaces: import only this plugin (repeatable via comma list)")
    s.add_argument("--yes", "-y", action="store_true", help="accept hooks defined by the bundle (they run commands)")
    s.add_argument("--enable-mcp", action="store_true", help="enable MCP servers defined by the bundle (default: imported disabled)")
    s.add_argument("--no-sync", action="store_true")
    s = sub.add_parser("pack", help=argparse.SUPPRESS)
    s.add_argument("--out", default=None, help="output file (default: <folder-name>.aisb.zip)")
    s.add_argument("--name", default=None)
    s.add_argument("--description", default="")
    s.add_argument("--include-policy", action="store_true", help="also include policy.json")
    s = sub.add_parser("context", help=argparse.SUPPRESS)
    s.add_argument("target", help="tool name or 'all'")
    s.add_argument("--groups", default=None, help="comma list of pattern groups (deps,build,caches,secrets,lockfiles,media,data,minified,vcs)")
    s.add_argument("--add", action="append", default=[], help="extra pattern (repeatable)")
    s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("doctor", help=argparse.SUPPRESS)
    s.add_argument("target", help="tool name")
    s.add_argument("--fix", action="store_true", help="apply the local fixes (ignore file, log rotation, config checks)")
    s.add_argument("--disable-mcp", default=None, help="comma list of MCP server names to disable in the project config")
    s = sub.add_parser("runtime", help=argparse.SUPPRESS)
    s.add_argument("what", choices=("python",))
    s.add_argument("--version", dest="py_version", default=None, help="3.12 or 3.13 (default 3.13)")
    s.add_argument("--force", action="store_true")
    sub.add_parser("targets", help=argparse.SUPPRESS)
    s = sub.add_parser("clean", help=argparse.SUPPRESS)
    s.add_argument("--src", action="store_true", help="delete fetched bundle sources (.ai-sandbox/bundles/_src; re-fetched on next apply)")
    s.add_argument("--cache", action="store_true", help="delete .ai-sandbox/cache (pip/npm/uv/... caches, tmp)")
    s.add_argument("--logs", action="store_true", help="delete the audit logs")
    s.add_argument("--all", action="store_true")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # `aisb guard ...` must stay cheap and tolerant: dispatch before argparse
    if argv and argv[0] == "guard":
        from . import guard
        return guard.main(argv[1:])
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 2
    root = os.path.realpath(os.path.abspath(args.root or os.getcwd()))
    if os.path.isdir(root):
        os.chdir(root)
    host = Host(getattr(args, "python", None))
    dry = getattr(args, "dry_run", False)
    log = Log(root, dry_run=dry, verbose=args.verbose, quiet=args.quiet)
    try:
        return dispatch(args, root, host, log)
    except BrokenPipeError:
        try:
            sys.stdout = open(os.devnull, "w")
        except Exception:  # noqa: BLE001
            pass
        return 0
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1
    except KeyboardInterrupt:
        return 130
    except Exception:  # noqa: BLE001
        log.fail("unexpected error:\n" + traceback.format_exc())
        return 1


def _tools_from(args, root, log):
    spec = getattr(args, "tools", None)
    res = parse_tool_list(spec)
    if isinstance(res, tuple):
        out, unknown = res
        log.fail("unknown tools: %s (choose from %s or 'all')" % (", ".join(unknown), ", ".join(ALL_TOOLS)))
        return None
    return res


def dispatch(args, root, host, log):
    cmd = args.cmd
    if cmd in ("init", "install", "sync"):
        from .installer import Installer, print_next_steps
        from .verifier import Verifier
        tools = _tools_from(args, root, log)
        if tools is None:
            return 2
        opts = {"tools": tools, "no_venv": args.no_venv, "no_credential_firewall": args.no_credential_firewall,
                "isolate_tool_homes": args.isolate_tool_homes, "no_os_sandbox": args.no_os_sandbox,
                "cursor_windows_shell": args.cursor_windows_shell or "cmd", "force": args.force, "dry_run": args.dry_run}
        m = Manifest(root)
        if cmd == "sync":
            if not m.exists:
                log.fail("sync: not installed here yet (run `aisb init`)")
                return 1
        if m.exists:
            saved = m.data.get("options", {})
            for k in ("no_venv", "no_credential_firewall", "isolate_tool_homes", "no_os_sandbox"):
                if saved.get(k) and not getattr(args, k, None):
                    opts[k] = saved[k]
            if args.cursor_windows_shell is None and saved.get("cursor_windows_shell"):
                opts["cursor_windows_shell"] = saved["cursor_windows_shell"]
            if args.tools is None and m.data.get("tools"):
                opts["tools"] = m.data["tools"]
        if host.frozen and not opts["no_venv"] and cmd != "sync":
            # standalone build: a venv can only be created from a project-local runtime (none yet) -> handled in installer
            pass
        inst = Installer(root, host, opts, log)
        rc = inst.run(sync_only=(cmd == "sync"))
        if rc:
            return rc
        if cmd != "sync" and args.profile:
            from .bundles import apply_source
            rc = apply_source(root, host, log, "profile:" + args.profile, yes=True, sync=False)
            if rc:
                return rc
            inst = Installer(root, host, opts, log)
            inst.run(sync_only=True)
        if cmd != "sync" and not args.skip_verify and not args.dry_run:
            log.info("")
            rc = Verifier(root, host, log).run()
            log.info("")
            print_next_steps(root, host, opts, log)
        return rc
    if cmd == "verify":
        from .verifier import Verifier
        return Verifier(root, host, log).run(quick=args.quick)
    if cmd == "uninstall":
        from .uninstaller import Uninstaller
        return Uninstaller(root, host, log, purge_venv=args.purge_venv, dry_run=args.dry_run).run()
    if cmd == "status":
        return cmd_status(root, host, log)
    if cmd == "log":
        return cmd_log(root, args)
    if cmd == "targets":
        return cmd_targets(log)
    if cmd == "list":
        from .components import cmd_list
        return cmd_list(root, host, log, args.what)
    if cmd in ("add", "remove"):
        from .components import cmd_add, cmd_remove
        if not Manifest(root).exists:
            log.fail("%s: the sandbox is not installed here (run `aisb init` first)" % cmd)
            return 1
        rc = cmd_add(root, host, log, args) if cmd == "add" else cmd_remove(root, host, log, args)
        if rc == 0 and not args.no_sync:
            rc = _resync(root, host, log)
        return rc
    if cmd == "apply":
        from .bundles import apply_source
        if not Manifest(root).exists:
            log.fail("apply: the sandbox is not installed here (run `aisb init` first)")
            return 1
        rc = apply_source(root, host, log, args.source, name=args.name, only=args.only, plugin=args.plugin, yes=args.yes, sync=False, enable_mcp=args.enable_mcp)
        if rc == 0 and not args.no_sync:
            rc = _resync(root, host, log)
        return rc
    if cmd == "pack":
        from .bundles import pack
        return pack(root, host, log, out=args.out, name=args.name, description=args.description, include_policy=args.include_policy)
    if cmd == "context":
        from .context import cmd_context
        return cmd_context(root, host, log, args)
    if cmd == "doctor":
        from .doctor import cmd_doctor
        return cmd_doctor(root, host, log, args)
    if cmd == "clean":
        import shutil
        if not (args.src or args.cache or args.logs or args.all):
            log.fail("clean: choose --src, --cache, --logs or --all")
            return 2
        targets = []
        if args.src or args.all:
            targets.append(os.path.join(root, ".ai-sandbox", "bundles", "_src"))
        if args.cache or args.all:
            targets.append(os.path.join(root, ".ai-sandbox", "cache"))
        if args.logs or args.all:
            targets.append(os.path.join(root, ".ai-sandbox", "logs"))
        for t in targets:
            if os.path.isdir(t):
                shutil.rmtree(t, ignore_errors=True)
                log.done("removed    %s" % os.path.relpath(t, root))
        for sub_dir in ("cache/pip", "cache/npm", "cache/tmp", "cache/uv", "cache/pycache", "logs"):
            os.makedirs(os.path.join(root, ".ai-sandbox", *sub_dir.split("/")), exist_ok=True)
        return 0
    if cmd == "runtime":
        from .runtime import install_python
        from .installer import Installer
        exe = install_python(root, host, log, version=args.py_version, force=args.force)
        m = Manifest(root)
        if m.exists:
            opts = dict(m.data.get("options", {}))
            opts.setdefault("tools", m.data.get("tools", DEFAULT_TOOLS))
            opts["no_venv"] = False
            inst = Installer(root, host, opts, log)
            created = False
            if not os.path.exists(inst.venv_python):
                inst._create_venv(exe)  # noqa: SLF001
                m2 = Manifest(root)
                m2.data["venv"] = inst.m.data.get("venv", {})
                m2.save()
                created = True
            inst = Installer(root, host, opts, log)
            inst.run(sync_only=True)
            if created:
                log.done("runtime    .venv created from the project-local Python; hooks now use it")
            else:
                log.info("runtime    .venv already existed and was kept; use it or delete it and re-run to rebuild from the project-local Python")
        return 0
    log.fail("unknown command %s" % cmd)
    return 2


def _resync(root, host, log):
    from .installer import Installer
    m = Manifest(root)
    opts = dict(m.data.get("options", {}))
    opts.setdefault("tools", m.data.get("tools", DEFAULT_TOOLS))
    opts.setdefault("cursor_windows_shell", "cmd")
    opts["terse"] = True
    quiet = log.quiet
    log.quiet = True
    rc = Installer(root, host, opts, log).run(sync_only=True)
    log.quiet = quiet
    if rc == 0:
        log.done("synced     every tool configuration from .ai-sandbox/")
    return rc


# ======================================================================================
# status / log / targets
# ======================================================================================
def cmd_status(root, host, log):
    m = Manifest(root)
    if not m.exists:
        log.fail("not installed in %s" % root)
        return 1
    P = log.plain
    P("aisb %s  root=%s" % (m.data.get("kit_version"), root))
    P("host       %s   installed %s   updated %s" % (host.label, m.data.get("created"), m.data.get("updated")))
    rt = m.data.get("runtime", {}) or {}
    P("runtime    %s (%s)" % (rt.get("mode", "?"), rt.get("exe") or ""))
    P("venv       %s" % (m.data.get("venv", {}).get("python") or "none"))
    P("tools      %s" % ", ".join(m.data.get("tools", [])))
    P("files      %d tracked (%d generated, %d merged, %d blocks)" % (
        len(m.files), sum(1 for e in m.files.values() if e.get("mode") == "generated"),
        sum(1 for e in m.files.values() if e.get("mode") == "merged"), sum(1 for e in m.files.values() if e.get("mode") == "block")))
    from .ssot import SSOT
    sm = SSOT(root).summary()
    P("ssot       rules=%s" % ", ".join(sm["rules"]))
    P("           skills=%s" % ", ".join(sm["skills"]))
    P("           agents=%s  commands=%s  hooks=%s" % (", ".join(sm["agents"]), ", ".join(sm["commands"]) or "-", ", ".join(sm["hooks"]) or "-"))
    P("           mcp=%s  bundles=%s" % (", ".join(sm["mcp"]) or "-", ", ".join(sm["bundles"]) or "-"))
    log_path = os.path.join(root, ".ai-sandbox", "logs", "audit.jsonl")
    if os.path.isfile(log_path):
        counts, last = {}, None
        with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
            for ln in fh:
                try:
                    rec = json.loads(ln)
                except Exception:  # noqa: BLE001
                    continue
                key = (rec.get("source"), rec.get("decision"))
                counts[key] = counts.get(key, 0) + 1
                last = rec
        if counts:
            P("audit      " + ", ".join("%s/%s=%d" % (k[0], k[1], v) for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))))
            if last:
                P("last       %s %s %s %s" % (last.get("ts"), last.get("source"), last.get("decision"), (last.get("summary") or "")[:80]))
        else:
            P("audit      no events yet")
    return 0


def cmd_log(root, args):
    path = os.path.join(root, ".ai-sandbox", "logs", "audit.jsonl" if args.json else "audit.log")
    if not os.path.isfile(path):
        print("no audit log yet at %s" % path)
        return 0
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    shown = lines[-args.n:] if args.n > 0 else lines
    if args.denied:
        shown = [ln for ln in shown if (" DENY " in ln or " ASK " in ln) or ('"decision": "deny"' in ln or '"decision": "ask"' in ln)]
    sys.stdout.write("".join(shown))
    sys.stdout.flush()
    if not args.follow:
        return 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            fh.seek(0, io.SEEK_END)
            while True:
                ln = fh.readline()
                if ln:
                    sys.stdout.write(ln)
                    sys.stdout.flush()
                else:
                    time.sleep(0.5)
    except KeyboardInterrupt:
        return 0


def cmd_targets(log):
    P = log.plain
    P("%-12s %-46s %-9s %s" % ("target", "title", "default", "rules / mcp / hooks / ignore"))
    for tid, t in TARGETS.items():
        rules = t["rules"].get("dir") or t["rules"].get("file") or t["rules"]["style"]
        mcp = (t.get("mcp") or {}).get("file") or ((t.get("mcp") or {}).get("sidecar") and "sidecar") or "-"
        hooks = (t.get("hooks") or {}).get("file") or "-"
        ign = (t.get("ignore") or {}).get("file") or (t.get("ignore") or {}).get("style") or "-"
        P("%-12s %-46s %-9s %s | %s | %s | %s" % (tid, t["title"][:46], "yes" if tid in DEFAULT_TOOLS else "", rules, mcp, hooks, ign))
    P("")
    P("aliases: " + ", ".join("%s=%s" % (a, tid) for tid, t in TARGETS.items() for a in t.get("aliases", [])[:2]))
    _ = resolve
    return 0
