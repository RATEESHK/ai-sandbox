# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Shared helpers: time, hashing, tolerant JSON, deep merge with ownership tracking, quoting, logging."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import sys

MARK_MD = ("<!-- ai-sandbox:begin -->", "<!-- ai-sandbox:end -->")
MARK_HASH = ("# >>> ai-sandbox >>>", "# <<< ai-sandbox <<<")


def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return fh.read()


def write_text(path, text, newline="\n"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace("\r\n", "\n").replace("\n", newline))


def parse_jsonc(text):
    """Tolerant JSON: strips // and /* */ comments outside strings and trailing commas (VS Code style)."""
    out, i, n, in_str, esc = [], 0, len(text), False, False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    cleaned = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    if not cleaned.strip():
        return {}
    return json.loads(cleaned)


def load_json(path, default=None):
    try:
        return parse_jsonc(read_text(path))
    except Exception:  # noqa: BLE001
        return default


def dump_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def deep_merge(theirs, ours, path=(), owned=None, overwritten=None):
    """Merge `ours` into `theirs` in place. Dict containers are shared, leaves are owned by us,
    lists are unioned (our items appended and owned individually)."""
    if owned is None:
        owned = []
    if overwritten is None:
        overwritten = {}
    for k, v in ours.items():
        p = path + (k,)
        if isinstance(v, dict) and (k not in theirs or isinstance(theirs[k], dict)):
            if k not in theirs:
                theirs[k] = {}
            deep_merge(theirs[k], v, p, owned, overwritten)
        elif k in theirs and isinstance(theirs[k], list) and isinstance(v, list):
            for item in v:
                if item not in theirs[k]:
                    theirs[k].append(item)
                owned.append({"path": list(p), "item": item})
        else:
            if k in theirs and theirs[k] != v:
                overwritten[".".join(str(x) for x in p)] = theirs[k]
            theirs[k] = v
            owned.append({"path": list(p)})
    return theirs, owned, overwritten


def remove_owned(obj, owned, overwritten):
    """Undo deep_merge: delete owned leaves / list items, restore overwritten values, prune empty dicts."""
    for entry in owned:
        path = entry["path"]
        cur = obj
        ok = True
        for key in path[:-1]:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if not ok or not isinstance(cur, dict) or path[-1] not in cur:
            continue
        leaf = path[-1]
        if "item" in entry:
            if isinstance(cur[leaf], list) and entry["item"] in cur[leaf]:
                cur[leaf].remove(entry["item"])
                if not cur[leaf]:
                    del cur[leaf]
        else:
            dotted = ".".join(str(x) for x in path)
            if dotted in overwritten:
                cur[leaf] = overwritten[dotted]
            else:
                del cur[leaf]
    prune_empty(obj)
    return obj


def prune_empty(d):
    if not isinstance(d, dict):
        return
    for k in list(d.keys()):
        if isinstance(d[k], dict):
            prune_empty(d[k])
            if not d[k]:
                del d[k]


def q_sh(s):
    """POSIX single-quote."""
    return "'" + str(s).replace("'", "'\"'\"'") + "'"


def q_ps(s):
    """PowerShell single-quote."""
    return "'" + str(s).replace("'", "''") + "'"


def q_dq(s):
    """Double-quote for cmd.exe / sh / bash (paths only)."""
    return '"' + str(s) + '"'


def msys_path(p):
    """C:\\Users\\x -> /c/Users/x (PATH entries inside Git Bash)."""
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", p)
    if not m:
        return p.replace("\\", "/")
    return "/%s/%s" % (m.group(1).lower(), m.group(2).replace("\\", "/"))


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return s or "item"


def parse_frontmatter(text):
    """Return (dict, body). Minimal YAML: `key: value`, `key: [a, b]`, `key:` + `- item` lists. No nesting."""
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", text, re.DOTALL)
    if not m:
        return {}, text
    fm = {}
    key = None
    for ln in m.group(1).splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if re.match(r"^\s+-\s", ln) and key:
            fm.setdefault(key, [])
            if isinstance(fm[key], list):
                fm[key].append(ln.split("-", 1)[1].strip().strip("'\""))
            continue
        mm = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", ln)
        if not mm:
            continue
        key, val = mm.group(1), mm.group(2).strip()
        if val == "":
            fm[key] = []
        elif val.startswith("[") and val.endswith("]"):
            fm[key] = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
        elif val.lower() in ("true", "false"):
            fm[key] = val.lower() == "true"
        else:
            fm[key] = val.strip("'\"")
    return fm, text[m.end():]


def _yaml_scalar(sv):
    """Quote a scalar when plain YAML would misread it (globs with *, leading specials, colons, commas in lists)."""
    if sv == "" or sv != sv.strip() or sv[0] in "*&!%@`|>'\"{}[]#?-" or any(c in sv for c in ":#{}[],") \
            or sv.lower() in ("true", "false", "null", "yes", "no", "on", "off") or "*" in sv:
        return '"' + sv.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return sv


def render_frontmatter(d):
    lines = ["---"]
    for k, v in d.items():
        if isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif isinstance(v, list):
            lines.append("%s: [%s]" % (k, ", ".join(_yaml_scalar(str(x)) for x in v)))
        elif v is None:
            continue
        else:
            lines.append("%s: %s" % (k, _yaml_scalar(str(v))))
    lines.append("---")
    return "\n".join(lines) + "\n"


class Log:
    LEVELS = ("INFO", "DONE", "WARN", "FAIL", "PASS")

    def __init__(self, root, dry_run=False, verbose=False, quiet=False):
        self.root = root
        self.dry = dry_run
        self.verbose = verbose
        self.quiet = quiet
        self.path = os.path.join(root, ".ai-sandbox", "logs", "aisb.log")
        self.file_enabled = True
        self.lines = []
        self.counts = {k: 0 for k in self.LEVELS}

    def _emit(self, level, msg, force=False):
        self.counts[level] = self.counts.get(level, 0) + 1
        line = "[%s] %s" % (level, msg)
        self.lines.append("%s %s" % (now_iso(), line))
        if force or not self.quiet or level in ("WARN", "FAIL"):
            try:
                print(line)
            except UnicodeEncodeError:
                print(line.encode("ascii", "replace").decode("ascii"))
            sys.stdout.flush()
        if not self.dry and self.file_enabled:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(self.lines[-1] + "\n")
            except Exception:  # noqa: BLE001
                pass

    def info(self, msg, force=False):
        self._emit("INFO", msg, force)

    def done(self, msg):
        self._emit("DONE", msg)

    def warn(self, msg):
        self._emit("WARN", msg)

    def fail(self, msg):
        self._emit("FAIL", msg)

    def ok(self, msg, force=False):
        self._emit("PASS", msg, force)

    def debug(self, msg):
        if self.verbose:
            self._emit("INFO", msg)

    def plain(self, msg):
        """Unlogged, always printed (reports, next steps)."""
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode("ascii", "replace").decode("ascii"))
