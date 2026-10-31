# How ai-sandbox is licensed

ai-sandbox is open source under the **[Apache License 2.0](LICENSE)** (`Apache-2.0`). There is nothing else to
buy or to ask for: everyone — individuals and companies — may use, modify, redistribute and sell it, in open or
proprietary products, as long as they follow the license.

## What the license asks of you

| You want to… | Allowed? | What the license asks of you |
|---|---|---|
| Use it anywhere, including at work and in proprietary products | yes | nothing |
| Commit the installed files into your repositories and share them | yes | the files keep their headers (they already do) |
| Redistribute it, modified or not, in source or binary form | yes | include `LICENSE`; include the attribution in [`NOTICE`](NOTICE) (section 4(d)); state in modified files that you changed them; keep the copyright and license notices |
| Publish a fork or a derived tool | yes | same as above, under **its own name** (section 6 grants no trademark rights; see [TRADEMARKS.md](TRADEMARKS.md)) |
| Make a closed-source product out of it | yes | same as above — Apache-2.0 has no copyleft |

## Attribution

Section 4(d) of the Apache License requires every redistribution to carry the contents of [`NOTICE`](NOTICE),
which names the author: "ai-sandbox, created by Rateesh Koganti (https://github.com/RATEESHK/ai-sandbox)". The source files carry a two-line header pointing to it, and
`aisb --version` prints it.

## For companies

No commercial license exists or is needed. Companies that want support, maintenance of a particular target,
a signed agreement for procurement, or simply to keep the project alive can sponsor it or contribute to it:
see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

## Why this license

Apache-2.0 maximises adoption: it is the license most corporate policies allow without review, it carries a
patent grant, and it is compatible with almost everything. The trade-off is that it gives the author no lever
over proprietary forks beyond attribution. The maintainer can switch to a copyleft dual-license model at any
time for future versions (`python scripts/set_license.py agpl`); copies already received under Apache-2.0 keep it.

## Contributions and the CLA

Pull requests are welcome (`CONTRIBUTING.md`). The CLA bot asks you to sign `CLA.md` on your first pull request.
It is there for one reason: the project is offered under more than one license, so the copyright holder needs
the right to include your contribution under all of them. You keep your copyright, you are credited in the git
history, release notes and `CHANGELOG.md`, and you can use your own contribution anywhere else.

## Third-party content

ai-sandbox itself contains no third-party code. Skill packs, plugins and bundles that `aisb apply` fetches at
your request are **not** part of ai-sandbox; they keep their own licenses, which `aisb` shows at import time and
records in `.ai-sandbox/bundles/bundles.lock.json`. Check them before redistributing a bundle you built with
`aisb pack`.

## Please tell us

Nothing in the license requires it, but if you or your company use ai-sandbox, add a line to `ADOPTERS.md`
(pull request) or open a "We use ai-sandbox" issue. It is the acknowledgement the author asks for in return for
the free license, and it decides which tools and workflows get maintained first.

*This file is an explanation written by the project author, not legal advice. The license text in `LICENSE`
(and the terms in `NOTICE`) are the binding documents.*
