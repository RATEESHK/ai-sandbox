# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Manifest (what we created / merged) and the tracked Writer that records every file it touches."""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import stat

from . import __version__
from .common import MARK_MD, deep_merge, dump_json, now_iso, parse_jsonc, read_text, remove_owned, sha256_text


class Manifest:
    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, ".ai-sandbox", "manifest.json")
        self.data = {"kit_version": __version__, "root": root, "created": now_iso(), "files": {}, "dirs": [],
                     "venv": {}, "options": {}, "tools": [], "hook_python": "", "runtime": {}, "components": {}}
        if os.path.isfile(self.path):
            try:
                self.data.update(json.loads(read_text(self.path)))
            except Exception:  # noqa: BLE001
                pass

    @property
    def files(self):
        return self.data.setdefault("files", {})

    @property
    def exists(self):
        return os.path.isfile(self.path)

    def save(self):
        self.data["updated"] = now_iso()
        self.data["kit_version"] = __version__
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=True)
            fh.write("\n")


class Writer:
    """Every write goes through here so uninstall can undo exactly what install did."""

    def __init__(self, root, manifest, log, force=False, dry_run=False):
        self.root = root
        self.m = manifest
        self.log = log
        self.force = force
        self.dry = dry_run

    # ---- helpers ---------------------------------------------------------------------
    def P(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def rel(self, path):
        return os.path.relpath(path, self.root).replace("\\", "/")

    def ensure_dir(self, rel):
        path = self.P(rel)
        if os.path.isdir(path):
            return
        if self.dry:
            self.log.info("[dry-run] would create directory %s" % rel)
            return
        parts = rel.split("/")
        for i in range(1, len(parts) + 1):
            sub = "/".join(parts[:i])
            p = self.P(sub)
            if not os.path.isdir(p):
                os.makedirs(p, exist_ok=True)
                if sub not in self.m.data["dirs"]:
                    self.m.data["dirs"].append(sub)

    def _backup(self, rel, suffix=""):
        src = self.P(rel)
        if not os.path.exists(src):
            return None
        dst_rel = ".ai-sandbox/backup/" + rel + suffix
        dst = self.P(dst_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return dst_rel

    def _write(self, rel, content, executable=False, crlf=False):
        path = self.P(rel)
        parent_rel = "/".join(rel.split("/")[:-1])
        if parent_rel:
            self.ensure_dir(parent_rel)
        data = content.replace("\r\n", "\n")
        if crlf:
            data = data.replace("\n", "\r\n")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(data)
        if executable and os.name != "nt":
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # ---- generated files ---------------------------------------------------------------
    def put(self, rel, content, executable=False, crlf=False, label=None, user_editable=False):
        """Write a file we own entirely. Pre-existing foreign files are backed up; local edits are respected."""
        label = label or rel
        path = self.P(rel)
        entry = self.m.files.get(rel)
        new_sha = sha256_text(content.replace("\r\n", "\n"))
        if os.path.exists(path):
            cur_sha = sha256_text(read_text(path).replace("\r\n", "\n"))
            if entry and cur_sha == entry.get("sha256") and cur_sha == new_sha:
                self.log.debug("unchanged  %s" % label)
                return
            if entry and cur_sha != entry.get("sha256"):
                if user_editable and not self.force:
                    self.log.info("kept       %s (your edits; SSOT files are never overwritten without --force)" % label)
                    entry["user_edited"] = True
                    return
                if not self.force:
                    self.log.warn("kept your local edits in %s (generated file modified; use --force to regenerate)" % label)
                    entry["drift"] = True
                    return
                if not self.dry:
                    b = self._backup(rel, ".modified-" + _dt.datetime.now().strftime("%Y%m%d%H%M%S"))
                    self.log.warn("overwrote modified %s (your version saved to %s)" % (label, b))
            elif not entry:
                if self.dry:
                    self.log.info("[dry-run] would back up and replace pre-existing %s" % label)
                else:
                    b = self._backup(rel)
                    self.log.warn("pre-existing %s backed up to %s and replaced (restored on uninstall)" % (label, b))
                    entry = {"created": False, "backup": b}
        else:
            entry = entry or {"created": True}
            if entry.get("created") is None:
                entry["created"] = True
        if self.dry:
            self.log.info("[dry-run] would write %s" % label)
            return
        self._write(rel, content, executable=executable, crlf=crlf)
        entry = entry or {"created": True}
        entry.update({"mode": "generated", "sha256": new_sha, "drift": False})
        self.m.files[rel] = entry
        self.log.done("wrote      %s" % label)

    def put_bytes(self, rel, data, label=None):
        """Binary file we own (bundled assets). No merge semantics."""
        label = label or rel
        path = self.P(rel)
        import hashlib
        new_sha = hashlib.sha256(data).hexdigest()
        entry = self.m.files.get(rel) or {"created": not os.path.exists(path)}
        if os.path.exists(path) and entry.get("sha256") == new_sha:
            return
        if self.dry:
            self.log.info("[dry-run] would write %s" % label)
            return
        parent_rel = "/".join(rel.split("/")[:-1])
        if parent_rel:
            self.ensure_dir(parent_rel)
        with open(path, "wb") as fh:
            fh.write(data)
        entry.update({"mode": "generated", "sha256": new_sha, "binary": True})
        self.m.files[rel] = entry
        self.log.done("wrote      %s" % label)

    def copy_file(self, src_rel, dst_rel):
        self.put(dst_rel, read_text(self.P(src_rel)), label="%s  (copy of %s)" % (dst_rel, src_rel))

    # ---- JSON merge --------------------------------------------------------------------
    def merge_json(self, rel, ours, label=None):
        label = label or rel
        path = self.P(rel)
        entry = self.m.files.get(rel) or {}
        if not os.path.exists(path):
            if self.dry:
                self.log.info("[dry-run] would create %s" % label)
                return
            merged, owned, overwritten = deep_merge({}, json.loads(json.dumps(ours)))
            text = dump_json(merged)
            self._write(rel, text)
            self.m.files[rel] = {"mode": "merged", "created": True, "sha256": sha256_text(text), "owned": owned,
                                 "overwritten": {}}
            self.log.done("wrote      %s" % label)
            return
        try:
            text = read_text(path)
            existing = parse_jsonc(text) if text.strip() else {}
            if not isinstance(existing, dict):
                raise ValueError("top level is not an object")
        except Exception as exc:  # noqa: BLE001
            side = rel + ".ai-sandbox.json"
            self.log.warn("%s could not be parsed (%s). Left untouched; our settings are in %s - merge them by hand."
                          % (label, exc, side))
            if not self.dry:
                self._write(side, dump_json(ours))
                self.m.files[side] = {"mode": "generated", "created": True, "sha256": sha256_text(dump_json(ours))}
            return
        if self.dry:
            self.log.info("[dry-run] would merge our keys into existing %s" % label)
            return
        if not entry:
            b = self._backup(rel)
            entry = {"mode": "merged", "created": False, "backup": b, "owned": [], "overwritten": {}}
            self.log.info("merging into your existing %s (original backed up to %s)" % (label, b))
            if "//" in text or "/*" in text:
                self.log.warn("%s contained comments; JSON is rewritten without them (original kept in backup)" % label)
        else:
            existing = remove_owned(existing, entry.get("owned", []), entry.get("overwritten", {}))
        merged, owned, overwritten = deep_merge(existing, json.loads(json.dumps(ours)))
        prev_over = entry.get("overwritten", {})
        prev_over.update({k: v for k, v in overwritten.items() if k not in prev_over})
        out = dump_json(merged)
        entry.update({"mode": "merged", "sha256": sha256_text(out), "owned": owned, "overwritten": prev_over})
        self.m.files[rel] = entry
        if out == text:
            self.log.debug("unchanged  %s" % label)
            return
        self._write(rel, out)
        self.log.done("merged     %s" % label)

    # ---- marked blocks in text files ---------------------------------------------------
    def put_block(self, rel, body, markers=MARK_MD, label=None, crlf=False):
        label = label or rel
        begin, end = markers
        block = "%s\n%s\n%s\n" % (begin, body.strip("\n"), end)
        path = self.P(rel)
        entry = self.m.files.get(rel) or {}
        if not os.path.exists(path):
            if self.dry:
                self.log.info("[dry-run] would create %s" % label)
                return
            self._write(rel, block, crlf=crlf)
            self.m.files[rel] = {"mode": "block", "created": True, "sha256": sha256_text(block), "markers": [begin, end]}
            self.log.done("wrote      %s" % label)
            return
        text = read_text(path)
        if self.dry:
            self.log.info("[dry-run] would add/refresh the ai-sandbox block in %s" % label)
            return
        if begin in text and end in text:
            pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
            new_text = pattern.sub(lambda _m: block, text, count=1)
            action = "refreshed"
        else:
            if not entry:
                entry = {"created": False, "backup": self._backup(rel)}
            sep = "" if text.endswith("\n") else "\n"
            new_text = text + sep + "\n" + block
            action = "appended block to"
        if new_text == text:
            self.log.debug("unchanged  %s" % label)
            return
        self._write(rel, new_text, crlf=crlf)
        entry.update({"mode": "block", "sha256": sha256_text(new_text), "markers": [begin, end]})
        self.m.files[rel] = entry
        self.log.done("%-10s %s" % (action, label))

    def forget(self, rel):
        """Stop tracking a file (used when a component is removed and its generated copies deleted)."""
        path = self.P(rel)
        entry = self.m.files.pop(rel, None)
        if entry and os.path.exists(path) and entry.get("mode") == "generated" and not self.dry:
            try:
                os.remove(path)
                self.log.debug("removed    %s" % rel)
            except OSError:
                pass
            # prune now-empty parent directories (but never the project root or .ai-sandbox itself)
            parent = os.path.dirname(path)
            while parent and len(parent) > len(self.root) and os.path.isdir(parent) and not os.listdir(parent):
                try:
                    os.rmdir(parent)
                except OSError:
                    break
                parent = os.path.dirname(parent)
