#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
# ai-sandbox bootstrap for macOS / Linux / WSL / Git Bash / BSD  -  POSIX sh only (no bash, no Python required).
#
#   cd your-project
#   sh /path/to/install.sh                 # same as: aisb init
#   sh /path/to/install.sh verify          # any aisb command
#
# What it does, in order:
#   1. If a Python >= 3.8 exists:  run aisb from this checkout (./aisb/) or from a downloaded aisb.pyz.
#   2. Otherwise: download the standalone build for this OS/CPU from GitHub Releases, verify SHA256SUMS,
#      unpack it into ./.ai-sandbox/bin/aisb-bin/ and run it.  Nothing is installed outside this folder.
# Override:  AISB_REPO=owner/repo  AISB_VERSION=v1.2.3 (default latest)  AISB_BASE_URL=<custom asset base url>
set -u
AISB_REPO="${AISB_REPO:-RATEESHK/ai-sandbox}"
AISB_VERSION="${AISB_VERSION:-latest}"
if [ -n "${AISB_BASE_URL:-}" ]; then base="$AISB_BASE_URL"
elif [ "$AISB_VERSION" = "latest" ]; then base="https://github.com/$AISB_REPO/releases/latest/download"
else base="https://github.com/$AISB_REPO/releases/download/$AISB_VERSION"; fi

here="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
proj="$(pwd)"
[ $# -eq 0 ] && set -- init
case "$1" in -h|--help|help) sed -n '2,12p' "$0"; exit 0;; esac

if [ "$here" = "$proj" ] && [ -d "$here/aisb" ] && [ ! -f "$here/.ai-sandbox/policy.json" ]; then
  echo "install.sh: you are inside the ai-sandbox repository itself. Run it from the project you want to sandbox:" >&2
  echo "    cd /path/to/your/project && sh $here/install.sh" >&2
  exit 1
fi

py_ok() { "$@" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; }
find_python() {
  for cand in "$proj/.venv/bin/python" "$proj/.ai-sandbox/runtime/python/bin/python3"; do
    [ -x "$cand" ] && py_ok "$cand" && { echo "$cand"; return 0; }
  done
  for name in python3 python; do
    command -v "$name" >/dev/null 2>&1 || continue
    if [ "$(uname -s 2>/dev/null)" = "Darwin" ] && [ "$(command -v "$name")" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then
      continue   # Xcode stub: would open an installer dialog
    fi
    py_ok "$name" && { command -v "$name"; return 0; }
  done
  if command -v py >/dev/null 2>&1 && py_ok py -3; then echo "py -3"; return 0; fi
  return 1
}

fetch() {  # fetch URL DEST
  if command -v curl >/dev/null 2>&1; then curl -fsSL --retry 3 -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then wget -q -O "$2" "$1"
  else echo "install.sh: neither curl nor wget is available; download $1 yourself into $2" >&2; return 1; fi
}
sha256() {  # sha256 FILE -> hex
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then openssl dgst -sha256 "$1" | awk '{print $NF}'
  else echo ""; fi
}
verify() {  # verify FILE NAME SUMSFILE
  want="$(grep " $2\$" "$3" 2>/dev/null | awk '{print $1}' | head -n 1)"
  got="$(sha256 "$1")"
  if [ -z "$want" ]; then echo "install.sh: $2 is not listed in SHA256SUMS - refusing" >&2; return 1; fi
  if [ -z "$got" ]; then echo "install.sh: no sha256 tool (sha256sum/shasum/openssl) - cannot verify $2" >&2; return 1; fi
  [ "$want" = "$got" ] || { echo "install.sh: SHA256 mismatch for $2 (expected $want, got $got) - refusing" >&2; return 1; }
}

# ---- 1. Python path --------------------------------------------------------------------------
if py="$(find_python)"; then
  if [ -d "$here/aisb" ] && [ -f "$here/aisb/cli.py" ]; then
    PYTHONPATH="$here${PYTHONPATH:+:$PYTHONPATH}" exec $py -m aisb "$@"
  fi
  if [ -f "$proj/.ai-sandbox/bin/aisb.pyz" ]; then exec $py "$proj/.ai-sandbox/bin/aisb.pyz" "$@"; fi
  if [ -f "$here/aisb.pyz" ]; then exec $py "$here/aisb.pyz" "$@"; fi
  tmp="$proj/.ai-sandbox-bootstrap"; mkdir -p "$tmp"
  echo "install.sh: downloading aisb.pyz from $base ..."
  fetch "$base/SHA256SUMS" "$tmp/SHA256SUMS" && fetch "$base/aisb.pyz" "$tmp/aisb.pyz" && verify "$tmp/aisb.pyz" "aisb.pyz" "$tmp/SHA256SUMS" || { rm -rf "$tmp"; exit 1; }
  $py "$tmp/aisb.pyz" "$@"; rc=$?
  rm -rf "$tmp"
  exit $rc
fi

# ---- 2. No Python: standalone build ---------------------------------------------------------
os="$(uname -s 2>/dev/null)"; arch="$(uname -m 2>/dev/null)"
case "$os" in Linux*) os=linux;; Darwin*) os=macos;; MINGW*|MSYS*|CYGWIN*) os=windows;; *) echo "install.sh: unsupported OS $os" >&2; exit 1;; esac
case "$arch" in x86_64|amd64) arch=x64;; arm64|aarch64) arch=arm64;; *) echo "install.sh: unsupported CPU $arch" >&2; exit 1;; esac
if [ "$os" = "windows" ]; then asset="aisb-windows-$arch.zip"; else asset="aisb-$os-$arch.tar.gz"; fi
dest="$proj/.ai-sandbox/bin/aisb-bin"
if [ -x "$dest/aisb" ] || [ -x "$dest/aisb.exe" ]; then
  exe="$dest/aisb"; [ -x "$exe" ] || exe="$dest/aisb.exe"
  exec "$exe" "$@"
fi
echo "install.sh: no Python 3.8+ found; downloading the standalone build $asset from $base ..."
tmp="$proj/.ai-sandbox-bootstrap"; mkdir -p "$tmp"
fetch "$base/SHA256SUMS" "$tmp/SHA256SUMS" && fetch "$base/$asset" "$tmp/$asset" && verify "$tmp/$asset" "$asset" "$tmp/SHA256SUMS" || { rm -rf "$tmp"; exit 1; }
mkdir -p "$dest"
if [ "$os" = "windows" ]; then
  (cd "$tmp" && unzip -q -o "$asset" -d "$tmp/unpacked") || { echo "install.sh: unzip failed" >&2; rm -rf "$tmp"; exit 1; }
else
  mkdir -p "$tmp/unpacked" && tar -xzf "$tmp/$asset" -C "$tmp/unpacked" || { echo "install.sh: tar failed" >&2; rm -rf "$tmp"; exit 1; }
fi
src="$tmp/unpacked/aisb-bin"; [ -d "$src" ] || src="$tmp/unpacked"
rm -rf "$dest" && mv "$src" "$dest" && rm -rf "$tmp"
exe="$dest/aisb"; [ -x "$exe" ] || exe="$dest/aisb.exe"
chmod +x "$exe" 2>/dev/null
echo "install.sh: standalone aisb ready at $dest (project-local; delete the folder to remove it)"
exec "$exe" "$@"
