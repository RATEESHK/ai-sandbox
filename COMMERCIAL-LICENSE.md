# Commercial license

ai-sandbox is free and open source under the GNU Affero General Public License v3.0 or later (`LICENSING.md` explains the whole scheme). **You only
need a commercial license if you want to do something the AGPL does not allow** — most teams never do.

## Do you need one?

| Situation | AGPL (free) | Commercial license |
|---|---|---|
| Using ai-sandbox at your company, on client projects, in CI, on any number of machines | free | — |
| Committing the installed files into private or public repositories | free | — |
| Private modifications used only inside your organisation | free (nothing to publish) | — |
| Publishing a fork or a modified version under the AGPL, with source, marked as modified | free | — |
| Bundling it **unmodified** in a product, template, course, image or installer, with `LICENSE` + `NOTICE` and the source available | free | — |
| Offering a **modified** version as part of a hosted service and giving its users the modified source | free | — |
| Offering a **modified** version as part of a hosted service **without** offering its users the source | — | needed |
| Bundling a **modified** version in a product without releasing its source under the AGPL | — | needed |
| Combining it into one program with proprietary code and distributing that | — | needed |
| A signed agreement, warranty, indemnity or support commitment for procurement | — | available |

## Two ways to get a commercial license: pay, or contribute

The copyright holder grants commercial licenses in exchange for **either**:

1. **A license fee** — yearly, per organisation, sized to the organisation (team / company / enterprise), or per
   product for OEM and bundling deals; **or**
2. **A contribution plan** — the fee is waived for organisations that help maintain the project in a way agreed
   in writing, for example: maintaining one or more targets in `aisb/targets.py` and their CI jobs, contributing
   features or fixes upstream, writing and maintaining docs or profiles, providing CI runners or code-signing
   infrastructure, security review, user support, or sponsorship. The maintainer decides which contributions
   qualify and reviews the plan once a year.

Commercial licensees agree to tell the maintainer where ai-sandbox is used (product, service or internal
platform) and are listed in `ADOPTERS.md` unless they opt out.

## How to request one

Open an issue titled **"Commercial license request"** on the repository, or contact the copyright holder via the
URL in `NOTICE`. Say:

1. who you are (company / individual),
2. what you want to do (product component, modified version, redistribution, hosting, internal use),
3. the number of developers, seats or products, if relevant,
4. whether you want to pay or to contribute, and what you could contribute.

Licenses are granted in writing by the copyright holder, Rateesh Koganti, who retains all rights to license,
sublicense and relicense ai-sandbox. Contributions are accepted under `CLA.md`, which keeps that possible.

## Third-party content

ai-sandbox itself contains no third-party code. Skill packs, plugins and bundles that `aisb apply` fetches at
your request are **not** part of ai-sandbox; they keep their own licenses (shown at import time and recorded in
`.ai-sandbox/bundles/bundles.lock.json`). Check them before redistributing a bundle you built with `aisb pack`.

*This file is a summary written by the project author, not legal advice. The license text in `LICENSE` and the
terms in `NOTICE` are the binding documents; a commercial license is a separate written agreement.*
