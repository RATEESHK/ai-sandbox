#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Build distributables.

    python scripts/build.py pyz        -> dist/aisb.pyz                      (any Python 3.8+)
    python scripts/build.py binary     -> dist/aisb-bin/                     (PyInstaller onedir; run on each OS)
    python scripts/build.py release    -> dist/release/{aisb.pyz, aisb-<os>-<arch>.tar.gz|zip, SHA256SUMS, install.*}

The release step packages whatever exists in dist/ for THIS machine; CI runs it on every OS and merges SHA256SUMS.
"""
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipapp
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
sys.path.insert(0, ROOT)
from aisb import __version__  # noqa: E402


def platform_tag():
    arch = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(arch, arch)
    os_name = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}[platform.system()]
    return os_name, arch


def build_pyz():
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "aisb.pyz")
    stage = os.path.join(DIST, "_pyz")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    shutil.copytree(os.path.join(ROOT, "aisb"), os.path.join(stage, "aisb"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    with open(os.path.join(stage, "__main__.py"), "w", encoding="utf-8") as fh:
        fh.write("import sys\nfrom aisb.cli import main\nsys.exit(main())\n")
    zipapp.create_archive(stage, out, interpreter="/usr/bin/env python3", compressed=True)
    shutil.rmtree(stage)
    print("built", out, os.path.getsize(out), "bytes")
    return out


def build_binary():
    try:
        __import__("PyInstaller")
    except ImportError:
        print("PyInstaller is not installed in this interpreter. Use a scratch venv:  python -m venv .build && .build/bin/pip install pyinstaller", file=sys.stderr)
        return 1
    entry = os.path.join(HERE, "aisb_entry.py")
    sep = os.pathsep
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "aisb", "--contents-directory", "_internal",
           "--add-data", os.path.join(ROOT, "aisb") + sep + "aisb", "--distpath", DIST, "--workpath", os.path.join(DIST, "_build"),
           "--specpath", os.path.join(DIST, "_build"), entry]
    print(" ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)
    out = os.path.join(DIST, "aisb-bin")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.rename(os.path.join(DIST, "aisb"), out)
    with open(os.path.join(out, "VERSION"), "w", encoding="utf-8") as fh:
        fh.write(__version__ + "\n")
    shutil.rmtree(os.path.join(DIST, "_build"), ignore_errors=True)
    exe = os.path.join(out, "aisb.exe" if platform.system() == "Windows" else "aisb")
    r = subprocess.run([exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print("smoke:", r.stdout.strip())
    r = subprocess.run([exe, "guard", "--selftest"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print("guard selftest via binary:", r.stdout.strip().splitlines()[-1])
    return 0


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def package_release():
    rel = os.path.join(DIST, "release")
    os.makedirs(rel, exist_ok=True)
    produced = []
    pyz = os.path.join(DIST, "aisb.pyz")
    if os.path.isfile(pyz):
        shutil.copy2(pyz, os.path.join(rel, "aisb.pyz"))
        produced.append("aisb.pyz")
    bin_dir = os.path.join(DIST, "aisb-bin")
    if os.path.isdir(bin_dir):
        os_name, arch = platform_tag()
        extras = [("install.sh", os.path.join(ROOT, "install.sh")), ("install.cmd", os.path.join(ROOT, "install.cmd")),
                  ("install.ps1", os.path.join(ROOT, "install.ps1")), ("LICENSE", os.path.join(ROOT, "LICENSE")),
                  ("README.txt", None)]
        readme = ("ai-sandbox standalone build %s (%s-%s). No Python needed.\n\n"
                  "1. Extract this archive anywhere (e.g. next to your projects).\n"
                  "2. Open a terminal IN YOUR PROJECT FOLDER and run:\n"
                  "     Windows cmd:   C:\\path\\to\\aisb-%s-%s\\install.cmd\n"
                  "     PowerShell:    powershell -NoProfile -ExecutionPolicy Bypass -File C:\\path\\to\\install.ps1\n"
                  "     macOS/Linux:   sh /path/to/aisb-%s-%s/install.sh\n"
                  "   The build is copied into <project>/.ai-sandbox/bin/aisb-bin/ and used from there.\n"
                  "3. Afterwards use ./.ai-sandbox/bin/aisb (or aisb.cmd) inside the project.\n" % (__version__, os_name, arch, os_name, arch, os_name, arch))
        if os_name == "windows":
            name = "aisb-%s-%s.zip" % (os_name, arch)
            with zipfile.ZipFile(os.path.join(rel, name), "w", zipfile.ZIP_DEFLATED) as z:
                for base, _dirs, files in os.walk(bin_dir):
                    for fn in files:
                        full = os.path.join(base, fn)
                        z.write(full, "aisb-bin/" + os.path.relpath(full, bin_dir).replace("\\", "/"))
                for arc, src in extras:
                    if src and os.path.isfile(src):
                        z.write(src, arc)
                z.writestr("README.txt", readme)
        else:
            name = "aisb-%s-%s.tar.gz" % (os_name, arch)
            with tarfile.open(os.path.join(rel, name), "w:gz") as t:
                t.add(bin_dir, arcname="aisb-bin")
                for arc, src in extras:
                    if src and os.path.isfile(src):
                        t.add(src, arcname=arc)
                import io
                data = readme.encode("utf-8")
                info = tarfile.TarInfo("README.txt")
                info.size = len(data)
                t.addfile(info, io.BytesIO(data))
        produced.append(name)
    for fn in ("install.sh", "install.cmd", "install.ps1"):
        shutil.copy2(os.path.join(ROOT, fn), os.path.join(rel, fn))
        produced.append(fn)
    with open(os.path.join(rel, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as fh:
        for fn in sorted(os.listdir(rel)):
            if fn != "SHA256SUMS":
                fh.write("%s  %s\n" % (_sha(os.path.join(rel, fn)), fn))
    print("release assets in", rel, ":", ", ".join(sorted(os.listdir(rel))))
    return 0


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "pyz"
    if what == "pyz":
        build_pyz()
        return 0
    if what == "binary":
        return build_binary()
    if what == "release":
        return package_release()
    if what == "all":
        build_pyz()
        rc = build_binary()
        return rc or package_release()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
