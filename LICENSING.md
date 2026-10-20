# How ai-sandbox is licensed

ai-sandbox is **dual-licensed**. You may use it under either of these, at your choice:

1. **Open source — the [GNU Affero General Public License v3.0 or later](LICENSE)** (`AGPL-3.0-or-later`), with the additional attribution terms in
   [`NOTICE`](NOTICE). Free of charge for anyone and any purpose, including commercial use, as long as you follow
   the license; or
2. **A [commercial license](COMMERCIAL-LICENSE.md)** from the copyright holder, for organisations that cannot or
   do not want to comply with the AGPL's conditions (typically: shipping a modified version closed).

SPDX expression: `AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial`. The files `aisb` installs into your projects (guard hook, launchers) carry it as a header.

## What you can do under the open-source license, free of charge

| You want to… | Allowed? | What the license asks of you |
|---|---|---|
| Use it on your projects, at work, for clients, inside your company, in CI | yes | nothing beyond keeping the notices in the files |
| Commit the files it installs (`.ai-sandbox/`, hook scripts) into your repository and share that repository with your team or publicly | yes | the files keep their headers (they already do); keep `LICENSE` and `NOTICE` with full copies |
| Modify it for yourself or inside your company | yes | nothing — private changes never have to be published as long as you do not distribute them or (AGPL only) let others use the modified version over a network |
| Redistribute it unmodified (mirror, package, bundle it in a template, course, image or installer) | yes | ship `LICENSE` and `NOTICE` with it and make the source available (section 6) |
| Publish a fork, a modified version or a derived tool | yes | license it `AGPL-3.0-or-later`, publish the complete source, mark it as modified, keep the attribution, and do not call it ai-sandbox / aisb (`NOTICE`) |
| Run a **modified** version as a service that other people use over a network (hosted IDE, CI service, platform) | yes | offer those users the complete source of your modified version under the same license (AGPL section 13) |
| Ship a modified version inside a proprietary product, or distribute / host a modified version without publishing its source | **no** — not under the AGPL | get a [commercial license](COMMERCIAL-LICENSE.md): pay, or contribute instead |
| Combine it into one program with proprietary code and distribute that | **no** — not under the AGPL | commercial license |

## Attribution — the additional terms in `NOTICE`

Section 7 of the GNU GPL v3 lets a licensor add a small number of terms to the license. ai-sandbox adds three,
stated verbatim in [`NOTICE`](NOTICE): the author attribution must be preserved (7(b)), modified versions must
be marked as modified (7(c)), and the project's names may not be used to name or endorse derived versions
(7(d), 7(e)). In practice:

- keep the `NOTICE` file and the two header lines in the source files;
- if you redistribute a build, keep the "ai-sandbox, created by Rateesh Koganti (https://github.com/RATEESHK/ai-sandbox)" line in the output of `aisb --version` (or your
  equivalent);
- if you modify it, say so, change the version string, and give your version another name.

These terms are compatible with the GPL and AGPL (section 7 explicitly permits them) and travel with the
code into anything built on it.

## For companies

Using ai-sandbox at work is free, with no notification, registration or permission required — the license
already grants it. A **commercial license** is only needed when you want to do something the AGPL does
not allow (the two "no" rows above), or when procurement wants a signed agreement, warranty or indemnity.
It can be paid for with **money or with maintenance**: an organisation that contributes code, maintains a
target, provides CI or support, or sponsors the project gets the commercial license without a fee. Details and
the request procedure: [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

## Why this license

- **Adoption.** `AGPL-3.0-or-later` is OSI-approved and known to every corporate legal team; nobody has to ask before
  using the tool, and package indexes, SBOM tools and GitHub recognise it.
- **Acknowledgement.** Every copy, fork and derived product carries the author attribution (`NOTICE`,
  file headers, `aisb --version`), and modified versions must say that they are modified.
- **Contributions flow back.** Anyone who improves and redistributes it must publish the improvements under the
  same license. Forks are allowed, but they stay open and keep the attribution.
- **Sustainability.** Organisations that want to go beyond the AGPL pay for a commercial license or
  maintain the project instead; the CLA keeps dual licensing possible.

What this license deliberately does **not** do: it does not require anyone to inform the author or ask
permission (no open-source license can — see the Open Source Definition, points 5–7), it does not forbid forks,
and it puts no obligation on companies that only use the tool internally. The `ADOPTERS.md` request and the
commercial license are the levers for those cases.

## Switching

`python scripts/set_license.py agpl|gpl|apache|noncommercial|strict` regenerates every license-related file and
source header. A later, more restrictive license applies to future versions only; copies already received under
`AGPL-3.0-or-later` keep that license forever.

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
