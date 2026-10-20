# Contributing to ai-sandbox

Thanks for helping make AI coding agents safer to run. Everything here is optimised for one thing:
**an agent can never touch anything outside the project, and the human can always see what ran.**

## Ways to contribute

- **Add or fix a target** (`aisb/targets.py` + `aisb/generators.py`): a new AI tool, a renamed config
  path, a new hook event. Please link the vendor documentation page you verified it against.
- **Improve the guard** (`aisb/guard.py`): new global-install patterns, a path-escape case, a tool
  payload shape. Add a case to `selftest()` for every change; the suite must stay green on POSIX *and*
  Windows path semantics.
- **Profiles** (`aisb/profiles/*.json`): recipes that bring a complete agentic setup into a project.
  Only reference sources whose license allows redistribution, and say which.
- **Docs**: `README.md`, `docs/*.md`. Short, exact, no marketing.

## Ground rules

1. **Nothing global, ever.** No code path may write outside the project folder, require admin rights,
   or install anything system- or user-wide. Reviewers will reject it.
2. **Fail closed.** If the guard cannot decide, it denies. If a download cannot be verified, it refuses.
3. **Stdlib only, Python 3.8+ grammar.** The whole tool must run as a zipapp and freeze with PyInstaller.
   CI checks `ast.parse(..., feature_version=(3, 8))`.
4. **Every generated file is tracked** in the manifest so `aisb uninstall` can undo it.
5. **Verify facts.** Tool config formats change monthly. Cite the doc URL in the PR description.

## Workflow

```bash
git clone https://github.com/RATEESHK/ai-sandbox && cd ai-sandbox
python -m unittest discover -s tests -v       # ~15 s, no network
python -m aisb --help                          # run from the checkout
python scripts/build.py pyz                    # dist/aisb.pyz
```

- Branch from `main`, keep PRs focused, add tests for behaviour changes.
- Run `python -m pyflakes aisb` (CI does) and the test suite on at least one OS.
- Sign the CLA when the bot asks (comment `I have read the CLA Document and I hereby sign the CLA`).
  See `CLA.md` for why: the project is offered under more than one license (`LICENSING.md`), so the owner needs
  the right to include your contribution under all of them. `GOVERNANCE.md` explains the single-maintainer model.
- Use conventional, descriptive commit messages (`guard: deny uv tool upgrade`, `targets: antigravity hooks`).

## Reporting a tool-format change

Open an issue with the **"Tool format change"** template: tool, version, the doc URL, old vs new
path/schema, and (if you can) a sample payload. These are the most valuable issues we get.

## Security

Please do not file sandbox-escape findings as public issues — see `SECURITY.md`.
