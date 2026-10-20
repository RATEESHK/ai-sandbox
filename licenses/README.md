# License texts

Verbatim copies of the licenses this project can be offered under. `scripts/set_license.py <variant>` turns one
of them into the top-level `LICENSE` and regenerates `NOTICE`, `LICENSING.md`, `COMMERCIAL-LICENSE.md`, the
license sections of `README.md`, `docs/faq.md` and `GOVERNANCE.md`, the identifiers in `CITATION.cff`,
`pyproject.toml` and `aisb/__init__.py`, and the SPDX header of every source file.

| Variant | File | Source | Open source? | What it gives the author |
|---|---|---|---|---|
| `agpl` (default) | `AGPL-3.0.txt` | github.com/github/choosealicense.com (`_licenses/agpl-3.0.txt`, the text GitHub's detector matches) | yes (OSI) | attribution terms (GPL §7), forks must stay open, commercial license for closed use |
| `gpl` | `GPL-3.0.txt` | same source, `_licenses/gpl-3.0.txt` | yes (OSI) | same, without the network-service clause |
| `apache` | `Apache-2.0.txt` | same source, `_licenses/apache-2.0.txt` | yes (OSI) | attribution via `NOTICE` only |
| `noncommercial` | `PolyForm-Noncommercial-1.0.0.md` | github.com/polyformproject/polyform-licenses, branch 1.0.0 | no | commercial use needs permission |
| `strict` | `PolyForm-Strict-1.0.0.md` | same source | no | commercial use, forks and redistribution need permission |

For the open-source variants `LICENSE` is the verbatim text (so GitHub, SPDX and SBOM tools detect it) and the
attribution terms live in `NOTICE`; for the PolyForm variants `LICENSE` carries the Required Notice and the
licensor's additional permissions above the text, as those licenses expect.
