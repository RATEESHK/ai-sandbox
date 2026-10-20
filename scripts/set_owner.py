#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Rewrite the RATEESHK placeholder (and optionally the repo name) everywhere.

    python scripts/set_owner.py <github-user-or-org> [repo-name]
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "dist", "build", "__pycache__", ".venv", ".ai-sandbox", "licenses"}
TEXT_EXT = {".md", ".py", ".toml", ".cff", ".yml", ".yaml", ".sh", ".cmd", ".ps1", ".json", ".txt", ".cfg", ".ini", ""}


def candidate_files():
    """Every text file in the repository (the placeholder may sit in docs, workflows, source headers, NOTICE...)."""
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in TEXT_EXT:
                yield os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    owner = sys.argv[1]
    repo = sys.argv[2] if len(sys.argv) > 2 else "ai-sandbox"
    n = 0
    for rel in candidate_files():
        p = os.path.join(ROOT, rel)
        try:
            with open(p, "r", encoding="utf-8", newline="") as fh:
                s = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        t = s.replace("RATEESHK/ai-sandbox", "%s/%s" % (owner, repo)).replace("RATEESHK", owner)
        if repo != "ai-sandbox":
            t = re.sub(r"github\.com/%s/ai-sandbox" % re.escape(owner), "github.com/%s/%s" % (owner, repo), t)
        if t != s:
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(t)
            n += 1
            print("updated", rel)
    print("%d file(s) updated for %s/%s" % (n, owner, repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
