# Governance

ai-sandbox follows a **single-maintainer, open-to-contribution** model, in the spirit of how SQLite is run: one
person controls the canonical code and the releases; outside changes go through that person as pull requests.
What others may do with the code outside this repository is decided by the license (`LICENSING.md`), not by
this file.

## Roles

- **Maintainer** (copyright holder, Rateesh Koganti): sole committer to `main`, cuts the signed releases, decides
  scope, grants commercial licenses, owns the names "ai-sandbox" and "aisb".
- **Contributors**: anyone who submits an issue or a pull request. Contributions are welcome and credited in the
  git history, the release notes and `CHANGELOG.md`. Signing the CLA (`CLA.md`) gives the maintainer the right
  to include a contribution under every license the project is offered under.
- **Adopters**: people and organisations who use the tool and say so in `ADOPTERS.md`. Their targets and
  workflows are maintained first.

## How changes get in

1. Open an issue first for anything bigger than a fix (new target, new command, policy change).
2. Fork on GitHub and open a pull request; sign the CLA when the bot asks.
3. CI must pass on Linux, macOS and Windows; the guard self-test must stay green; vendor doc URLs must be cited
   for tool-format changes.
4. The maintainer reviews and merges, or declines with a reason. There is no committer team to join.

## Forks, modified versions, names

<!-- license-governance -->
The license (`LICENSE` + `NOTICE`) allows forks, modified versions and proprietary derivatives as long as the
license and the attribution notice travel with them and modified files are marked. Please do not call a modified
version "ai-sandbox" or "aisb" ([TRADEMARKS.md](TRADEMARKS.md)). The canonical distribution is this repository and its signed
releases (`SHA256SUMS`).
<!-- /license-governance -->

The license is the legal instrument; this file is the human explanation.

## Why this model

The tool runs as a **security hook** inside developers' projects. A single, verifiable, maintainer-controlled
distribution is a feature: users should be able to trust that `aisb-linux-x64.tar.gz` with the published
checksum is exactly what was reviewed and tested here, not a repackaged variant. Modified versions therefore
have to be marked as modified and may not carry the project's name.

## Changing the license

`python scripts/set_license.py agpl|gpl|apache|noncommercial|strict` switches the license for future versions
and regenerates every license-related file and source header. Relaxing is always possible; a stricter license
only ever applies to future versions, because copies already received keep the terms they were received under.
The CLA gives the maintainer the rights needed for either direction.
