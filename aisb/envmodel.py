# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Environment model: every variable the sandbox sets, in tiers, with absolute paths for this machine."""
from __future__ import annotations

import os


class EnvVar:
    def __init__(self, name, value, tier, note, kind="path"):
        self.name, self.value, self.tier, self.note, self.kind = name, value, tier, note, kind
        # tier 2 (credential firewall) is applied inside the AI tools' own environments; it reaches your
        # interactive shell only when you export AI_SANDBOX_STRICT=1 before activating (see README)
        self.shell = tier != 2


def build_env(root, host, opts):
    """Return the ordered list of sandbox environment variables for this machine."""
    j = lambda *p: os.path.join(root, *p)  # noqa: E731
    cache = lambda *p: j(".ai-sandbox", "cache", *p)  # noqa: E731
    home = lambda *p: j(".ai-sandbox", "home", *p)  # noqa: E731
    cfg = lambda *p: j(".ai-sandbox", "config", *p)  # noqa: E731
    E = []  # noqa: N806

    # --- tier 1: language tooling stays inside the workspace -------------------------
    E += [
        EnvVar("PIP_REQUIRE_VIRTUALENV", "true", 1, "pip refuses to install outside a virtual environment", "flag"),
        EnvVar("PIP_CONFIG_FILE", cfg("pip.conf"), 1, "pip ignores your user/global pip.conf; uses the sandbox one"),
        EnvVar("PIP_CACHE_DIR", cache("pip"), 1, "pip download cache"),
        EnvVar("PIP_DISABLE_PIP_VERSION_CHECK", "1", 1, "no 'new pip available' network nag", "flag"),
        EnvVar("PYTHONNOUSERSITE", "1", 1, "Python never imports ~/.local site-packages", "flag"),
        EnvVar("PYTHONUSERBASE", home("python-user"), 1, "if anything still targets the user base, it lands here"),
        EnvVar("PYTHONPYCACHEPREFIX", cache("pycache"), 1, "__pycache__ kept out of the source tree"),
        EnvVar("UV_CACHE_DIR", cache("uv"), 1, "uv cache"),
        EnvVar("UV_PROJECT_ENVIRONMENT", j(".venv"), 1, "uv uses the project .venv"),
        EnvVar("UV_TOOL_DIR", home("uv-tools"), 1, "uv tool install lands inside the workspace"),
        EnvVar("UV_TOOL_BIN_DIR", home("uv-tools", "bin"), 1, "uv tool binaries inside the workspace"),
        EnvVar("UV_PYTHON_INSTALL_DIR", home("uv-python"), 1, "uv-managed interpreters inside the workspace"),
        EnvVar("POETRY_VIRTUALENVS_IN_PROJECT", "true", 1, "poetry creates .venv in the project", "flag"),
        EnvVar("POETRY_CACHE_DIR", cache("pypoetry"), 1, "poetry cache"),
        EnvVar("POETRY_CONFIG_DIR", home("pypoetry"), 1, "poetry config never touches ~/.config/pypoetry"),
        EnvVar("PIPENV_VENV_IN_PROJECT", "1", 1, "pipenv creates .venv in the project", "flag"),
        EnvVar("PIPENV_CACHE_DIR", cache("pipenv"), 1, "pipenv cache"),
        EnvVar("PIPX_HOME", home("pipx"), 1, "pipx (if ever used) stays inside"),
        EnvVar("PIPX_BIN_DIR", home("pipx", "bin"), 1, "pipx binaries inside"),
        EnvVar("PRE_COMMIT_HOME", cache("pre-commit"), 1, "pre-commit hook environments"),
        EnvVar("MYPY_CACHE_DIR", cache("mypy"), 1, "mypy cache"),
        EnvVar("RUFF_CACHE_DIR", cache("ruff"), 1, "ruff cache"),
        EnvVar("npm_config_cache", cache("npm"), 1, "npm cache (npx cache included)"),
        EnvVar("NPM_CONFIG_USERCONFIG", cfg("npmrc"), 1, "npm user config = sandbox file, not ~/.npmrc"),
        EnvVar("NPM_CONFIG_GLOBALCONFIG", cfg("npmrc-global"), 1, "npm global config = sandbox file"),
        EnvVar("npm_config_update_notifier", "false", 1, "no npm update nag", "flag"),
        EnvVar("npm_config_fund", "false", 1, "no funding banner", "flag"),
        EnvVar("npm_config_store_dir", cache("pnpm-store"), 1, "pnpm content-addressable store"),
        EnvVar("PNPM_HOME", home("pnpm"), 1, "pnpm global dir (should stay unused)"),
        EnvVar("YARN_CACHE_FOLDER", cache("yarn"), 1, "yarn classic cache"),
        EnvVar("YARN_GLOBAL_FOLDER", cache("yarn-berry"), 1, "yarn berry global folder"),
        EnvVar("YARN_ENABLE_GLOBAL_CACHE", "false", 1, "yarn berry keeps cache per project", "flag"),
        EnvVar("BUN_INSTALL", home("bun"), 1, "bun global dir inside"),
        EnvVar("BUN_INSTALL_CACHE_DIR", cache("bun"), 1, "bun cache"),
        EnvVar("DENO_DIR", cache("deno"), 1, "deno cache"),
        EnvVar("COREPACK_HOME", cache("corepack"), 1, "corepack cache"),
        EnvVar("CARGO_HOME", cache("cargo"), 1, "cargo registry/git cache and `cargo install` root"),
        EnvVar("GOPATH", cache("go"), 1, "go path"),
        EnvVar("GOMODCACHE", cache("go", "pkg", "mod"), 1, "go module cache"),
        EnvVar("GOCACHE", cache("go-build"), 1, "go build cache"),
        EnvVar("GOBIN", home("go", "bin"), 1, "`go install` target inside the workspace"),
        EnvVar("GOFLAGS", "-modcacherw", 1, "module cache stays deletable", "flag"),
        EnvVar("GRADLE_USER_HOME", cache("gradle"), 1, "gradle home"),
        EnvVar("MAVEN_OPTS", "-Dmaven.repo.local=" + cache("maven"), 1, "maven local repository", "mixed"),
        EnvVar("NUGET_PACKAGES", cache("nuget"), 1, "nuget packages"),
        EnvVar("DOTNET_CLI_HOME", home("dotnet"), 1, "dotnet tools/first-run state inside"),
        EnvVar("DOTNET_CLI_TELEMETRY_OPTOUT", "1", 1, "dotnet telemetry off", "flag"),
        EnvVar("DOTNET_NOLOGO", "1", 1, "dotnet banner off", "flag"),
        EnvVar("GEM_HOME", cache("gems"), 1, "ruby gems inside"),
        EnvVar("BUNDLE_PATH", cache("bundle"), 1, "bundler install path"),
        EnvVar("BUNDLE_USER_HOME", home("bundle"), 1, "bundler user home"),
        EnvVar("COMPOSER_HOME", home("composer"), 1, "composer home"),
        EnvVar("COMPOSER_CACHE_DIR", cache("composer"), 1, "composer cache"),
        EnvVar("TF_PLUGIN_CACHE_DIR", cache("terraform-plugins"), 1, "terraform provider cache"),
        EnvVar("CHECKPOINT_DISABLE", "1", 1, "terraform/hashicorp version checks off", "flag"),
        EnvVar("PLAYWRIGHT_BROWSERS_PATH", cache("ms-playwright"), 1, "playwright browsers inside"),
        EnvVar("PUPPETEER_CACHE_DIR", cache("puppeteer"), 1, "puppeteer browsers inside"),
        EnvVar("CYPRESS_CACHE_FOLDER", cache("cypress"), 1, "cypress binaries inside"),
        EnvVar("HF_HOME", cache("huggingface"), 1, "Hugging Face models/datasets inside"),
        EnvVar("TORCH_HOME", cache("torch"), 1, "torch hub inside"),
        EnvVar("KERAS_HOME", cache("keras"), 1, "keras inside"),
        EnvVar("CURL_HOME", home("curl"), 1, "curl reads .curlrc from here, not ~"),
        EnvVar("DO_NOT_TRACK", "1", 1, "generic telemetry opt-out", "flag"),
        EnvVar("HOMEBREW_NO_ANALYTICS", "1", 1, "(brew is blocked anyway)", "flag"),
        EnvVar("NEXT_TELEMETRY_DISABLED", "1", 1, "next.js telemetry off", "flag"),
        EnvVar("GATSBY_TELEMETRY_DISABLED", "1", 1, "gatsby telemetry off", "flag"),
        EnvVar("TMPDIR", cache("tmp"), 1, "temporary files (POSIX)"),
        EnvVar("TEMP", cache("tmp"), 1, "temporary files (Windows)"),
        EnvVar("TMP", cache("tmp"), 1, "temporary files (Windows)"),
    ]
    # --- tier 2: credential firewall ----------------------------------------------------
    if not opts.get("no_credential_firewall"):
        E += [
            EnvVar("GIT_CONFIG_GLOBAL", home("git", "gitconfig"), 2, "git global config = sandbox file (your identity is copied in)"),
            EnvVar("GIT_CONFIG_NOSYSTEM", "1", 2, "git ignores the system gitconfig", "flag"),
            EnvVar("KUBECONFIG", home("kube", "config"), 2, "kubectl/helm see an EMPTY kubeconfig"),
            EnvVar("AWS_CONFIG_FILE", home("aws", "config"), 2, "aws CLI sees an EMPTY config"),
            EnvVar("AWS_SHARED_CREDENTIALS_FILE", home("aws", "credentials"), 2, "aws CLI sees EMPTY credentials"),
            EnvVar("CLOUDSDK_CONFIG", home("gcloud"), 2, "gcloud config dir (empty)"),
            EnvVar("AZURE_CONFIG_DIR", home("azure"), 2, "az config dir (empty)"),
            EnvVar("DOCKER_CONFIG", home("docker"), 2, "docker registry auth (empty)"),
            EnvVar("GH_CONFIG_DIR", home("gh"), 2, "GitHub CLI token dir (empty)"),
            EnvVar("TF_CLI_CONFIG_FILE", home("terraform", "terraformrc"), 2, "terraform CLI config (no credentials)"),
            EnvVar("HELM_CONFIG_HOME", home("helm", "config"), 2, "helm repos/registry config (empty)"),
            EnvVar("HELM_CACHE_HOME", cache("helm"), 2, "helm cache"),
            EnvVar("HELM_DATA_HOME", home("helm", "data"), 2, "helm plugins"),
            EnvVar("GNUPGHOME", home("gnupg"), 2, "gpg keyring (empty)"),
            EnvVar("XDG_CONFIG_HOME", home("xdg", "config"), 2, "XDG config (~/.config) for tools that honour it"),
            EnvVar("XDG_DATA_HOME", home("xdg", "data"), 2, "XDG data"),
            EnvVar("XDG_STATE_HOME", home("xdg", "state"), 2, "XDG state"),
            EnvVar("XDG_CACHE_HOME", home("xdg", "cache"), 2, "XDG cache"),
        ]
    # --- tier 3: AI tool homes (opt-in; needs re-login per project) ---------------------
    if opts.get("isolate_tool_homes"):
        E += [
            EnvVar("CLAUDE_CONFIG_DIR", home("claude"), 3, "Claude Code user config/credentials inside the workspace"),
            EnvVar("GEMINI_CLI_HOME", home("gemini"), 3, "Gemini CLI user config/credentials inside the workspace"),
            EnvVar("COPILOT_HOME", home("copilot"), 3, "Copilot CLI user config/credentials inside the workspace"),
        ]
    return E
