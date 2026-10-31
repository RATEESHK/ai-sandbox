# Commercial use, support and sponsorship

ai-sandbox is open source under the Apache License 2.0. **No commercial license exists or is needed**: companies
may use, modify, redistribute and sell it, in open or proprietary products, as long as they keep `LICENSE`,
include the attribution in `NOTICE` (section 4(d)) and mark modified files (`LICENSING.md`).

## Open core: what stays commercial

The local CLI and guard are Apache-2.0 and stay that way. Team and enterprise components built later
(central policy server, signed policy distribution, audit-log export to SIEM / OpenTelemetry, SSO, org
dashboard, compliance evidence reports) are **not** part of this repository and are offered under a separate
commercial license by the maintainer.

## What the maintainer offers organisations

- **Support and maintenance agreements** — a named target (tool) kept working, response times, upgrades.
- **A signed agreement, warranty or indemnity** for procurement, where the Apache License's "AS IS" terms are not enough.
- **Sponsorship** — it funds the time that keeps 15+ tool formats verified against vendor docs.
- **Contribution plans** — organisations that maintain a target, provide CI runners or security review, or
  contribute features get their needs prioritised.

Open an issue titled **"Commercial support request"** on the repository or contact the maintainer via the URL in
`NOTICE`. Organisations that use ai-sandbox are asked (not required) to add themselves to `ADOPTERS.md`.

Contributions are accepted under `CLA.md`; the copyright holder, Rateesh Koganti, retains the right to offer the
project under other licenses in the future.

## Third-party content

ai-sandbox itself contains no third-party code. Skill packs, plugins and bundles that `aisb apply` fetches at
your request are **not** part of ai-sandbox; they keep their own licenses (shown at import time and recorded in
`.ai-sandbox/bundles/bundles.lock.json`). Check them before redistributing a bundle you built with `aisb pack`.

*This file is a summary written by the project author, not legal advice. The license text in `LICENSE` and the
terms in `NOTICE` are the binding documents; a commercial license is a separate written agreement.*
