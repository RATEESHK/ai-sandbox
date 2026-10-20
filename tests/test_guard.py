# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Guard engine tests (pure, no files): both path flavours plus the wire protocols."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from aisb import guard  # noqa: E402


class SelfTest(unittest.TestCase):
    def test_selftest_passes(self):
        self.assertEqual(guard.selftest(verbose=False), 0)


class Protocols(unittest.TestCase):
    """Run the guard as a subprocess against a throwaway sandbox root and check each tool's answer shape."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="aisb-guard-")
        os.makedirs(os.path.join(cls.tmp, ".ai-sandbox", "logs"))
        with open(os.path.join(cls.tmp, ".ai-sandbox", "policy.json"), "w") as fh:
            json.dump(guard.DEFAULT_POLICY, fh)
        with open(os.path.join(cls.tmp, ".ai-sandbox", "sandbox.env"), "w") as fh:
            fh.write("PIP_REQUIRE_VIRTUALENV='true'\n")
        cls.guard = os.path.join(ROOT, "aisb", "guard.py")

    def run_guard(self, tool, event, payload):
        env = dict(os.environ, AI_SANDBOX_ROOT=self.tmp)
        r = subprocess.run([sys.executable, self.guard, "--tool", tool, "--event", event], input=json.dumps(payload) if not isinstance(payload, str) else payload,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=self.tmp)
        out = r.stdout.strip()
        return r.returncode, (json.loads(out.splitlines()[0]) if out.startswith("{") else None), out, r.stderr

    def test_claude_deny(self):
        c, j, _o, _e = self.run_guard("claude", "pre", {"cwd": self.tmp, "tool_name": "Bash", "tool_input": {"command": "npm install -g x"}})
        self.assertEqual(c, 0)
        self.assertEqual(j["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_claude_allow_is_silent(self):
        c, j, o, _e = self.run_guard("claude", "pre", {"cwd": self.tmp, "tool_name": "Bash", "tool_input": {"command": "git status"}})
        self.assertEqual((c, j, o), (0, None, ""))

    def test_gemini(self):
        c, j, _o, _e = self.run_guard("gemini", "pre", {"cwd": self.tmp, "tool_name": "run_shell_command", "tool_input": {"command": "sudo ls"}})
        self.assertEqual((c, j["decision"]), (0, "deny"))

    def test_cursor(self):
        c, j, _o, _e = self.run_guard("cursor", "pre", {"hook_event_name": "beforeShellExecution", "command": "pip install --user x", "cwd": self.tmp, "workspace_roots": [self.tmp]})
        self.assertEqual((c, j["permission"]), (0, "deny"))
        c, j, _o, _e = self.run_guard("cursor", "pre", {"hook_event_name": "beforeShellExecution", "command": "npm test", "cwd": self.tmp, "workspace_roots": [self.tmp]})
        self.assertEqual((c, j["permission"]), (0, "allow"))
        c, j, _o, _e = self.run_guard("cursor", "prompt", {"hook_event_name": "beforeSubmitPrompt", "prompt": "hi", "workspace_roots": [self.tmp]})
        self.assertTrue(j["continue"])

    def test_copilot_string_args(self):
        c, j, _o, _e = self.run_guard("copilot", "pre", {"cwd": self.tmp, "toolName": "bash", "toolArgs": json.dumps({"command": "brew install x"})})
        self.assertEqual((c, j["permissionDecision"]), (0, "deny"))

    def test_antigravity(self):
        c, j, _o, _e = self.run_guard("antigravity", "pre", {"workspacePaths": [self.tmp], "toolCall": {"name": "run_command", "args": {"CommandLine": "cd ..", "Cwd": self.tmp}}})
        self.assertEqual((c, j["decision"]), (0, "deny"))
        c, j, _o, _e = self.run_guard("antigravity", "pre", {"workspacePaths": [self.tmp], "toolCall": {"name": "run_command", "args": {"CommandLine": "npm test", "Cwd": self.tmp}}})
        self.assertEqual((c, j["decision"]), (0, "allow"))

    def test_windsurf_exit_2(self):
        c, _j, _o, e = self.run_guard("windsurf", "pre", {"agent_action_name": "run_command", "tool_info": {"command_line": "cd ..", "cwd": self.tmp}})
        self.assertEqual(c, 2)
        self.assertIn("AI-SANDBOX DENY", e)

    def test_unparsable_denies(self):
        c, _j, _o, _e = self.run_guard("generic", "pre", "not json")
        self.assertEqual(c, 2)

    def test_audit_written(self):
        log = os.path.join(self.tmp, ".ai-sandbox", "logs", "audit.jsonl")
        self.assertTrue(os.path.isfile(log))
        with open(log) as fh:
            recs = [json.loads(ln) for ln in fh if ln.strip()]
        self.assertTrue(any(r.get("decision") == "deny" for r in recs))
        self.assertTrue(all("ts" in r and "source" in r for r in recs))


if __name__ == "__main__":
    unittest.main()
