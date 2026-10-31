# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Uninstall: remove exactly what aisb created, strip our keys/blocks from merged files, restore originals."""
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import stat

from .common import MARK_MD, dump_json, parse_jsonc, read_text, remove_owned, sha256_file, sha256_text
from .manifest import Manifest

class Uninstaller:
    def __init__(self, root, host, log, purge_venv=False, purge_cache=True, dry_run=False):
        self.root, self.host, self.log = root, host, log
        self.m = Manifest(root)
        self.purge_venv = purge_venv
        self.dry = dry_run
        self.leftovers = []

    def P(self, *parts):
        return os.path.join(self.root, *parts)

    def run(self):
        L = self.log
        if not os.path.isfile(self.m.path):
            L.fail("nothing to uninstall: no .ai-sandbox/manifest.json in %s" % self.root)
            return 1
        L.info("uninstall  %s  |  %d tracked files" % (self.root, len(self.m.files)))
        # files first (outside .ai-sandbox), then the sandbox dir, then empty dirs
        order = sorted(self.m.files.items(), key=lambda kv: (kv[0].startswith(".ai-sandbox/"), kv[0]))
        for rel, entry in order:
            if rel.startswith(".ai-sandbox/"):
                continue
            self.remove_entry(rel, entry)
        if self.purge_venv:
            self.rm_tree(".venv", "removed    .venv (--purge-venv)")
        elif os.path.isdir(self.P(".venv")):
            created = self.m.data.get("venv", {}).get("created_by_sandbox")
            L.info("kept       .venv (%s; pass --purge-venv to delete it)" % ("created by the sandbox" if created else "pre-existing"))
        # move backups out before deleting .ai-sandbox if anything could not be restored
        if self.leftovers:
            keep = self.P(".ai-sandbox-backup-" + _dt.datetime.now().strftime("%Y%m%d%H%M%S"))
            if not self.dry:
                shutil.move(self.P(".ai-sandbox", "backup"), keep)
            L.warn("some files were modified after install and were left in place; originals kept in %s" % keep)
        self.log.file_enabled = False  # nothing may be written under .ai-sandbox from here on
        self.rm_tree(".ai-sandbox", "removed    .ai-sandbox/")
        for d in reversed(self.m.data.get("dirs", [])):
            p = self.P(*d.split("/"))
            if os.path.isdir(p) and not os.listdir(p) and not d.startswith(".ai-sandbox"):
                if not self.dry:
                    os.rmdir(p)
                L.done("removed    empty dir %s" % d)
        L.done("uninstall complete. Nothing outside %s was ever touched." % self.root)
        return 0

    def rm_tree(self, rel, msg):
        p = self.P(rel)
        if os.path.isdir(p):
            if not self.dry:
                shutil.rmtree(p, onerror=_force_rm)
            self.log.done(msg)

    def remove_entry(self, rel, entry):
        L = self.log
        path = self.P(*rel.split("/"))
        if not os.path.exists(path):
            return
        mode = entry.get("mode")
        try:
            text = None if entry.get("binary") else read_text(path)
        except Exception:  # noqa: BLE001
            text = None
        cur = sha256_text(text.replace("\r\n", "\n")) if (text is not None and not entry.get("binary")) else sha256_file(path)
        unchanged = cur == entry.get("sha256")
        backup = entry.get("backup")
        backup_path = self.P(*backup.split("/")) if backup else None
        if mode == "generated":
            if unchanged:
                self._delete(path, rel)
                if backup_path and os.path.exists(backup_path):
                    self._restore(backup_path, path, rel)
            else:
                L.warn("kept       %s (you modified it after install)" % rel)
                self.leftovers.append(rel)
        elif mode == "merged":
            if entry.get("created") and unchanged:
                self._delete(path, rel)
            else:
                self._strip_owned(path, rel, entry, text, backup_path)
        elif mode == "block":
            begin, end = entry.get("markers", MARK_MD)
            if text is None:
                return
            new = re.sub(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", "", text, count=1, flags=re.DOTALL)
            new = re.sub(r"\n{3,}$", "\n\n", new).rstrip("\n") + ("\n" if new.strip() else "")
            if entry.get("created") and not new.strip():
                self._delete(path, rel)
            else:
                if not self.dry:
                    with open(path, "w", encoding="utf-8", newline="") as fh:
                        fh.write(new)
                L.done("removed    ai-sandbox block from %s" % rel)

    def _strip_owned(self, path, rel, entry, text, backup_path=None):
        """Remove our keys; if what remains equals the pre-install original, put the original bytes back."""
        try:
            data = parse_jsonc(text)
            data = remove_owned(data, entry.get("owned", []), entry.get("overwritten", {}))
            if not data and entry.get("created"):
                self._delete(path, rel)
                return
            if backup_path and os.path.exists(backup_path):
                try:
                    if parse_jsonc(read_text(backup_path)) == data:
                        self._restore(backup_path, path, rel)
                        return
                except Exception:  # noqa: BLE001
                    pass
            if not self.dry:
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(dump_json(data))
            self.log.done("removed    our keys from %s (your other settings kept)" % rel)
        except Exception as exc:  # noqa: BLE001
            self.log.warn("kept       %s (could not parse to remove our keys: %s)" % (rel, exc))
            self.leftovers.append(rel)

    def _delete(self, path, rel):
        if not self.dry:
            os.remove(path)
        self.log.done("removed    %s" % rel)

    def _restore(self, backup_path, path, rel):
        if not self.dry:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.copy2(backup_path, path)
        self.log.done("restored   %s (pre-install original)" % rel)


def _force_rm(func, path, _exc):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:  # noqa: BLE001
        pass
