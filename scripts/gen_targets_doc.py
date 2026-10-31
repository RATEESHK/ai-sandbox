#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Generate docs/targets.md from aisb/targets.py (run after changing the registry)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aisb.targets import DEFAULT_TOOLS, IGNORE_DEFAULT_GROUPS, IGNORE_GROUPS, TARGETS  # noqa: E402


def cell(x):
    return str(x).replace("|", "\\|") if x else "—"


def main():
    out = ["# Supported tools (targets)", "",
           "Generated from `aisb/targets.py` by `scripts/gen_targets_doc.py`. Facts verified against vendor",
           "documentation in October 2026; `confidence: medium` marks items the vendor documents thinly.",
           "Default targets: " + ", ".join("`%s`" % t for t in DEFAULT_TOOLS) + ". Use `--tools all` for the rest.", "",
           "| id | tool | rules | skills | agents | commands | MCP (project) | hooks | ignore | confidence |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for tid, t in TARGETS.items():
        r = t["rules"]
        rules = r.get("dir") or r.get("file") or r["style"]
        skills = ", ".join(t.get("skills_dirs") or []) or ("`.claude/skills`, `.agents/skills`" if tid in ("claude", "cursor", "copilot", "gemini", "antigravity") else "—")
        agents = (t.get("agents") or {}).get("dir")
        cmds = (t.get("commands") or {}).get("dir")
        mcp = t.get("mcp") or {}
        mcp_s = mcp.get("file") or (("sidecar `%s`" % mcp["sidecar"]) if mcp.get("sidecar") else None)
        hooks = (t.get("hooks") or {}).get("file")
        ign = t.get("ignore") or {}
        ign_s = ign.get("file") or ign.get("style")
        out.append("| `%s` | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            tid, cell(t["title"]), cell(rules), cell(skills), cell(agents), cell(cmds), cell(mcp_s), cell(hooks), cell(ign_s), t.get("confidence", "")))
    out += ["", "## Notes per tool", ""]
    for tid, t in TARGETS.items():
        notes = []
        for key in ("mcp", "ignore"):
            n = (t.get(key) or {}).get("note")
            if n:
                notes.append("%s: %s" % (key, n))
        if t.get("trust"):
            notes.append("trust: " + t["trust"])
        out.append("- **%s** (%s) — docs: <%s>%s" % (tid, t["title"], t.get("docs", ""), ("\n  - " + "\n  - ".join(notes)) if notes else ""))
    out += ["", "## Ignore-file pattern groups (`aisb context`)", "", "Default groups: " + ", ".join(IGNORE_DEFAULT_GROUPS) + ".", ""]
    for g, pats in IGNORE_GROUPS.items():
        out.append("- **%s**: `%s`" % (g, "`, `".join(pats)))
    with open(os.path.join(ROOT, "docs", "targets.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    print("wrote docs/targets.md")


if __name__ == "__main__":
    main()
