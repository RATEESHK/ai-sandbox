# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Project-local Python runtime: downloads a pinned python-build-standalone build into .ai-sandbox/runtime/python
and creates .venv from it. Nothing is installed globally; the download is verified against a pinned SHA256."""
from __future__ import annotations

import hashlib
import json
import os
import pkgutil
import platform
import shutil
import subprocess
import tarfile
import urllib.request


def load_lock():
    data = pkgutil.get_data("aisb", "runtime_lock.json")
    return json.loads(data.decode("utf-8"))


def platform_key(host):
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(host.arch.lower(), host.arch.lower())
    if host.is_windows:
        return "windows-" + arch
    if host.is_mac:
        return "macos-" + arch
    if host.is_linux:
        musl = False
        try:
            libc = platform.libc_ver()[0]
            musl = libc == "" and os.path.exists("/lib/ld-musl-x86_64.so.1") or os.path.exists("/lib/ld-musl-aarch64.so.1")
        except Exception:  # noqa: BLE001
            pass
        return ("linux-musl-" if musl else "linux-") + arch
    return None


def _download(url, dest, log, expected_sha):
    log.info("runtime    downloading %s" % url)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "aisb"})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if total and done % (4 << 20) < (1 << 16):
                log.debug("runtime    %d%%" % (100 * done // total))
    digest = h.hexdigest()
    if digest != expected_sha:
        os.remove(tmp)
        raise RuntimeError("SHA256 mismatch for %s: expected %s got %s (download refused)" % (os.path.basename(dest), expected_sha, digest))
    os.replace(tmp, dest)
    return digest


def _safe_extract(tar, dest):
    base = os.path.realpath(dest)
    for member in tar.getmembers():
        target = os.path.realpath(os.path.join(dest, member.name))
        if not target.startswith(base + os.sep) and target != base:
            raise RuntimeError("unsafe path in archive: %s" % member.name)
        if member.issym() or member.islnk():
            link = os.path.realpath(os.path.join(os.path.dirname(target), member.linkname))
            if not link.startswith(base):
                raise RuntimeError("unsafe link in archive: %s -> %s" % (member.name, member.linkname))
    tar.extractall(dest)  # noqa: S202 (members validated above)


def install_python(root, host, log, version=None, force=False):
    """Returns the path of the project-local interpreter."""
    lock = load_lock()
    version = version or lock["default_version"]
    if version not in lock["versions"]:
        raise RuntimeError("unknown Python version %s; available: %s" % (version, ", ".join(sorted(lock["versions"]))))
    key = platform_key(host)
    entry = lock["versions"][version]["platforms"].get(key or "")
    if not entry:
        raise RuntimeError("no pinned runtime for platform %s" % key)
    runtime_dir = os.path.join(root, ".ai-sandbox", "runtime")
    py_dir = os.path.join(runtime_dir, "python")
    exe = os.path.join(py_dir, "python.exe") if host.is_windows else os.path.join(py_dir, "bin", "python3")
    stamp = os.path.join(runtime_dir, "python.json")
    if os.path.isfile(exe) and os.path.isfile(stamp) and not force:
        try:
            meta = json.load(open(stamp, "r", encoding="utf-8"))
            if meta.get("asset") == entry["asset"]:
                log.ok("runtime    project-local Python already installed (%s)" % meta.get("version"))
                return exe
        except Exception:  # noqa: BLE001
            pass
    os.makedirs(runtime_dir, exist_ok=True)
    cache_dir = os.path.join(root, ".ai-sandbox", "cache", "runtime")
    os.makedirs(cache_dir, exist_ok=True)
    archive = os.path.join(cache_dir, entry["asset"])
    url = lock["asset_url_prefix"] + "/" + entry["asset"]
    if os.path.isfile(archive):
        h = hashlib.sha256()
        with open(archive, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        if h.hexdigest() != entry["sha256"]:
            os.remove(archive)
    if not os.path.isfile(archive):
        _download(url, archive, log, entry["sha256"])
    log.ok("runtime    SHA256 verified: %s" % entry["sha256"][:16])
    if os.path.isdir(py_dir):
        shutil.rmtree(py_dir, ignore_errors=True)
    with tarfile.open(archive, "r:gz") as tar:
        _safe_extract(tar, runtime_dir)  # archive contains a top-level "python/" directory
    if not os.path.isfile(exe):
        raise RuntimeError("archive extracted but %s is missing" % exe)
    r = subprocess.run([exe, "-c", "import sys; print(sys.version.split()[0])"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("runtime does not start: %s" % (r.stdout or "").strip()[-300:])
    with open(stamp, "w", encoding="utf-8") as fh:
        json.dump({"asset": entry["asset"], "sha256": entry["sha256"], "version": r.stdout.strip(), "source": lock["source"],
                   "tag": lock["tag"], "url": url}, fh, indent=2)
    log.done("runtime    project-local Python %s at %s" % (r.stdout.strip(), exe))
    return exe
