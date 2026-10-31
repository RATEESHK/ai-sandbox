# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Host detection: OS, WSL, Git Bash, admin, available tools, how this program is running (source / zipapp / frozen)."""
from __future__ import annotations

import getpass
import os
import platform
import shutil
import socket
import sys


def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None


class Host:
    def __init__(self, python=None):
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        self.is_mac = self.system == "Darwin"
        self.is_linux = self.system == "Linux"
        self.release = platform.release()
        self.arch = platform.machine()
        self.is_wsl = False
        if self.is_linux:
            try:
                with open("/proc/version", "r", encoding="utf-8", errors="ignore") as fh:
                    self.is_wsl = "microsoft" in fh.read().lower()
            except Exception:  # noqa: BLE001
                self.is_wsl = "microsoft" in self.release.lower()
        self.in_git_bash = self.is_windows and bool(os.environ.get("MSYSTEM"))
        self.frozen = bool(getattr(sys, "frozen", False))
        self.zipapp = (not self.frozen) and (".pyz" in os.path.abspath(__file__))
        self.exe = os.path.realpath(sys.executable)
        self.frozen_dir = os.path.dirname(self.exe) if self.frozen else None
        self.python = None if self.frozen else os.path.abspath(python or self._base_python())
        self.python_version = "%d.%d.%d" % sys.version_info[:3]
        self.home = os.path.expanduser("~")
        self.user = _safe(getpass.getuser) or "user"
        self.hostname = _safe(socket.gethostname) or "host"
        self.has = {name: bool(shutil.which(name)) for name in
                    ("git", "node", "npm", "npx", "uv", "direnv", "bwrap", "socat", "sandbox-exec", "pwsh", "bash",
                     "docker", "claude", "gemini", "cursor", "code", "copilot", "codex", "windsurf", "antigravity",
                     "curl", "wget", "tar")}
        self.is_admin = self._admin()
        self.venv_bin = "Scripts" if self.is_windows else "bin"
        self.venv_py = "python.exe" if self.is_windows else "python"
        self.os_sandbox_capable = self.is_mac or (self.is_linux and self.has["bwrap"] and self.has["socat"])
        self.label = "%s %s (%s)%s%s" % (self.system, self.release, self.arch,
                                          " [WSL]" if self.is_wsl else "", " [Git Bash]" if self.in_git_bash else "")
        self.mode = "binary" if self.frozen else ("zipapp" if self.zipapp else "source")

    @staticmethod
    def _base_python():
        """The interpreter outside any venv (so re-running from the project .venv still works)."""
        if sys.prefix == sys.base_prefix:
            return sys.executable
        base = getattr(sys, "_base_executable", None)
        if base and os.path.isfile(base) and os.path.realpath(base) != os.path.realpath(sys.executable):
            return base
        cfg = os.path.join(sys.prefix, "pyvenv.cfg")
        try:
            with open(cfg, "r", encoding="utf-8") as fh:
                for ln in fh:
                    if ln.lower().startswith("home"):
                        home = ln.split("=", 1)[1].strip()
                        for name in ("python3", "python", "python.exe", "python3.exe"):
                            cand = os.path.join(home, name)
                            if os.path.isfile(cand):
                                return cand
        except Exception:  # noqa: BLE001
            pass
        return sys.executable

    def _admin(self):
        try:
            if self.is_windows:
                import ctypes  # noqa: WPS433
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            return os.geteuid() == 0
        except Exception:  # noqa: BLE001
            return False

    @property
    def platform_tag(self):
        arch = self.arch.lower()
        arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(arch, arch)
        os_name = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(self.system, self.system.lower())
        return "%s-%s" % (os_name, arch)
