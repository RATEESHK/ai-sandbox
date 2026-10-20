#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-ai-sandbox-Commercial
# ai-sandbox - Copyright (c) 2026 Rateesh Koganti - https://github.com/RATEESHK/ai-sandbox - see LICENSE and NOTICE
"""Switch the project's license and keep every reference, generated document and source header consistent.

    python scripts/set_license.py agpl           # default: AGPL-3.0-or-later + attribution terms, OR a commercial license
    python scripts/set_license.py gpl            # GPL-3.0-or-later (same model, no network clause)
    python scripts/set_license.py apache         # Apache-2.0: maximum adoption, attribution via NOTICE, no copyleft lever
    python scripts/set_license.py noncommercial  # PolyForm Noncommercial 1.0.0: free for noncommercial use only
    python scripts/set_license.py strict         # PolyForm Strict 1.0.0: noncommercial use, no forks, no redistribution
    python scripts/set_license.py --check        # verify that everything matches the variant recorded in LICENSING.md

What it (re)generates, from the verbatim texts in licenses/:
    LICENSE                 the license text (verbatim for the open-source variants so GitHub detects it;
                            PolyForm variants carry their Required Notice and the additional permissions on top)
    NOTICE                  attribution notice + the additional terms that travel with every copy
    LICENSING.md            plain-English explanation of the whole scheme
    COMMERCIAL-LICENSE.md   the commercial offer (pay, or contribute instead of paying)
    README.md, docs/faq.md, GOVERNANCE.md     the sections between <!-- license-* --> markers
    CITATION.cff, pyproject.toml, aisb/__init__.py   license identifier / classifier / __license__
    source headers          the two SPDX/attribution comment lines in every .py / .sh / .cmd / .ps1 file
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNER_NAME = "Rateesh Koganti"
YEAR = "2026"
COMMERCIAL_REF = "LicenseRef-ai-sandbox-Commercial"

VARIANTS = {
    "agpl": {
        "family": "copyleft", "network": True,
        "spdx": "AGPL-3.0-or-later", "expr": "AGPL-3.0-or-later OR " + COMMERCIAL_REF,
        "title": "GNU Affero General Public License v3.0 or later", "short": "AGPL-3.0-or-later",
        "name": "GNU AGPL v3.0 or later, or a commercial license",
        "text": "licenses/AGPL-3.0.txt", "url": "https://www.gnu.org/licenses/agpl-3.0.html",
        "classifier": "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "cff": "AGPL-3.0-or-later",
        "badge": ("AGPL--3.0--or--later%20%7C%20commercial", "License: AGPL-3.0-or-later or commercial"),
    },
    "gpl": {
        "family": "copyleft", "network": False,
        "spdx": "GPL-3.0-or-later", "expr": "GPL-3.0-or-later OR " + COMMERCIAL_REF,
        "title": "GNU General Public License v3.0 or later", "short": "GPL-3.0-or-later",
        "name": "GNU GPL v3.0 or later, or a commercial license",
        "text": "licenses/GPL-3.0.txt", "url": "https://www.gnu.org/licenses/gpl-3.0.html",
        "classifier": "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "cff": "GPL-3.0-or-later",
        "badge": ("GPL--3.0--or--later%20%7C%20commercial", "License: GPL-3.0-or-later or commercial"),
    },
    "apache": {
        "family": "permissive", "network": False,
        "spdx": "Apache-2.0", "expr": "Apache-2.0",
        "title": "Apache License 2.0", "short": "Apache-2.0",
        "name": "Apache License 2.0",
        "text": "licenses/Apache-2.0.txt", "url": "https://www.apache.org/licenses/LICENSE-2.0",
        "classifier": "License :: OSI Approved :: Apache Software License",
        "cff": "Apache-2.0",
        "badge": ("Apache--2.0", "License: Apache-2.0"),
    },
    "noncommercial": {
        "family": "polyform", "network": False,
        "spdx": "PolyForm-Noncommercial-1.0.0", "expr": "PolyForm-Noncommercial-1.0.0 OR " + COMMERCIAL_REF,
        "title": "PolyForm Noncommercial License 1.0.0", "short": "PolyForm Noncommercial 1.0.0",
        "name": "PolyForm Noncommercial 1.0.0, or a commercial license",
        "text": "licenses/PolyForm-Noncommercial-1.0.0.md", "url": "https://polyformproject.org/licenses/noncommercial/1.0.0",
        "classifier": "License :: Other/Proprietary License",
        "cff": "PolyForm-Noncommercial-1.0.0",
        "badge": ("PolyForm%20Noncommercial%201.0.0", "License: PolyForm Noncommercial 1.0.0"),
    },
    "strict": {
        "family": "polyform", "network": False,
        "spdx": "LicenseRef-PolyForm-Strict-1.0.0", "expr": "LicenseRef-PolyForm-Strict-1.0.0 OR " + COMMERCIAL_REF,
        "title": "PolyForm Strict License 1.0.0", "short": "PolyForm Strict 1.0.0",
        "name": "PolyForm Strict 1.0.0, or a commercial license",
        "text": "licenses/PolyForm-Strict-1.0.0.md", "url": "https://polyformproject.org/licenses/strict/1.0.0",
        "classifier": "License :: Other/Proprietary License",
        "cff": "LicenseRef-PolyForm-Strict-1.0.0",
        "badge": ("PolyForm%20Strict%201.0.0", "License: PolyForm Strict 1.0.0"),
    },
}

# source files that carry the two-line SPDX / attribution header
HEADER_GLOBS = ["aisb/*.py", "scripts/*.py", "tests/*.py", "install.sh", "install.cmd", "install.ps1"]


# ----------------------------------------------------------------------------------------------- helpers
def read(rel):
    with io.open(os.path.join(ROOT, rel), "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(rel, text, changed):
    p = os.path.join(ROOT, rel)
    old = read(rel) if os.path.isfile(p) else None
    if old == text:
        return
    with io.open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    changed.append(rel)


def replace_marked(text, marker, body, inline=False):
    """Replace the content between <!-- marker --> and <!-- /marker -->; the markers stay."""
    begin, end = "<!-- %s -->" % marker, "<!-- /%s -->" % marker
    if begin not in text or end not in text:
        raise SystemExit("marker %s missing" % marker)
    sep = " " if inline else "\n"
    new = begin + sep + body.strip("\n") + sep + end
    return re.sub(re.escape(begin) + r".*?" + re.escape(end), lambda _m: new, text, count=1, flags=re.DOTALL)


def repo_url():
    return re.search(r"https://github\.com/[\w.\-]+/[\w.\-]+", read("pyproject.toml")).group(0)


# ----------------------------------------------------------------------------------------------- texts
def attribution(url):
    return "ai-sandbox, created by %s (%s)" % (OWNER_NAME, url)


def gen_license(v, url):
    text = read(v["text"])
    if v["family"] != "polyform":
        return text  # verbatim, so GitHub / licensee / SPDX tools detect it
    extra = {
        "strict": """Additional permissions granted by the licensor (extra licenses on top of the PolyForm Strict terms
below; they do not remove any restriction):

1. Project embedding. When you run the software for a permitted purpose it places unmodified copies of some
   of its own files inside your project (for example `.ai-sandbox/bin/aisb.pyz`,
   `.ai-sandbox/hooks/sandbox_guard.py`, `.ai-sandbox/bin/aisb-bin/`). You may keep those unmodified files in
   that project, commit them to version control, and share that repository with the people who work on the
   project with you, for the same permitted purpose. This is not a license to publish, package, sell or
   otherwise distribute the software on its own.
2. Contributions. You may make changes to the software solely in order to submit them to the licensor as
   contributions (for example as a pull request to the canonical repository) under the Contributor License
   Agreement in CLA.md. Changes that are not submitted, or not accepted, stay covered by the restrictions below.
3. Names and marks. Nothing here grants any right to the names "ai-sandbox" and "aisb" or any logo; they
   identify the licensor's canonical distribution only.

Everything else - commercial use (use at or for a company, in a product, or in paid work), distributing the
software or any part of it, publishing or running modified versions, forks, repackaging, hosting it as a
service - requires a separate written license from the licensor: see COMMERCIAL-LICENSE.md.""",
        "noncommercial": """Names and marks: nothing here grants any right to the names "ai-sandbox" and "aisb" or any logo; they
identify the licensor's canonical distribution only. Commercial use requires a separate written license from
the licensor: see COMMERCIAL-LICENSE.md.""",
    }[v["key"]]
    header = ("Required Notice: Copyright (c) %s %s (%s)\nSPDX-License-Identifier: %s\n\n"
              "ai-sandbox is licensed under the %s (text below).\n%s\n\n---\n\n" % (YEAR, OWNER_NAME, url, v["spdx"], v["title"], extra))
    return header + text


def gen_notice(v, url):
    head = ("ai-sandbox (aisb) - project-local sandbox for AI coding agents\n"
            "Copyright (c) %s %s\n%s\n\n" % (YEAR, OWNER_NAME, url))
    if v["family"] == "copyleft":
        gnu = "GNU Affero General Public License" if v["network"] else "GNU General Public License"
        return head + """This program is free software: you can redistribute it and/or modify it under the terms of the
%(gnu)s as published by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version, subject to the additional terms below (SPDX: %(spdx)s).
It is also available under a commercial license from the copyright holder: see COMMERCIAL-LICENSE.md.
SPDX-License-Identifier: %(expr)s

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the %(gnu)s
in the file LICENSE for more details.

ADDITIONAL TERMS under section 7 of the %(gnu)s version 3

The licensor adds the following terms to this program and to every covered work based on it. They are
permitted by section 7, paragraphs (b), (c), (d) and (e), and may not be removed:

1. Attribution (section 7(b)). You must preserve the author attribution
       "%(attr)s"
   in this NOTICE file, in the source-file headers in which it appears, and in the Appropriate Legal Notices
   displayed by any covered work that displays such notices (for this program: the output of `aisb --version`).
   You may add your own attributions next to it; you may not remove, hide or alter it.

2. Modified versions (section 7(c)). A modified version must be marked in reasonable ways as different from
   the original: at least a different version string, and a prominent notice stating that the work was
   modified, by whom and when. Do not misrepresent the origin of the material.

3. Names (sections 7(d) and 7(e)). The names "ai-sandbox" and "aisb", the licensor's name and any project logo
   may not be used for publicity, to name a modified version or a derived product, or to suggest that the
   licensor endorses it, without the licensor's written permission. No trademark rights are granted.

These terms are compatible with the GNU GPL version 3 (section 7 permits them). A work that combines this
program with other GPL-3.0 or %(spdx_short)s code keeps these terms for the parts that come from this program.
""" % {"gnu": gnu, "spdx": v["spdx"], "expr": v["expr"],
       "attr": attribution(url), "spdx_short": v["spdx"]}
    if v["family"] == "permissive":
        return head + """Licensed under the Apache License, Version 2.0 (the "License"); you may not use this software except in
compliance with the License. You may obtain a copy of the License in the file LICENSE or at
    http://www.apache.org/licenses/LICENSE-2.0
SPDX-License-Identifier: Apache-2.0

This product includes software developed by %(owner)s: %(attr)s.

Section 4(d) of the License: when you redistribute this software, with or without modifications, you must
include a readable copy of this NOTICE file (the attribution notices it contains) within the distribution.
The names "ai-sandbox" and "aisb" and any project logo identify the original project (section 6: no trademark
license is granted); please do not use them for modified versions.
""" % {"owner": OWNER_NAME, "attr": attribution(url)}
    # polyform
    return head + """Required Notice: Copyright (c) %(year)s %(owner)s (%(url)s)
SPDX-License-Identifier: %(expr)s

ai-sandbox is licensed under the %(title)s (file LICENSE, which also states the licensor's additional
permissions), or under a commercial license from the copyright holder (COMMERCIAL-LICENSE.md). Anyone who
receives a copy of any part of this software must also receive the license terms or their URL and this
Required Notice. The names "ai-sandbox" and "aisb" and any project logo identify the licensor's canonical
distribution only; no trademark rights are granted. Author attribution: %(attr)s.
""" % {"year": YEAR, "owner": OWNER_NAME, "url": url, "expr": v["expr"], "title": v["title"], "attr": attribution(url)}


COMMON_TAIL = """## Contributions and the CLA

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
"""


def gen_licensing(v, url):
    f = v["family"]
    if f == "copyleft":
        gnu_short = "AGPL" if v["network"] else "GPL"
        hosted = ("| Run a **modified** version as a service that other people use over a network (hosted IDE, CI service, platform) | yes | offer those users the complete source of your modified version under the same license (AGPL section 13) |"
                  if v["network"] else
                  "| Run a **modified** version as a service that other people use over a network | yes | nothing: the GPL has no network clause (the AGPL variant adds one) |")
        return """# How ai-sandbox is licensed

ai-sandbox is **dual-licensed**. You may use it under either of these, at your choice:

1. **Open source — the [%(title)s](LICENSE)** (`%(spdx)s`), with the additional attribution terms in
   [`NOTICE`](NOTICE). Free of charge for anyone and any purpose, including commercial use, as long as you follow
   the license; or
2. **A [commercial license](COMMERCIAL-LICENSE.md)** from the copyright holder, for organisations that cannot or
   do not want to comply with the %(gnu_short)s's conditions (typically: shipping a modified version closed).

SPDX expression: `%(expr)s`. The files `aisb` installs into your projects (guard hook, launchers) carry it as a header.

## What you can do under the open-source license, free of charge

| You want to… | Allowed? | What the license asks of you |
|---|---|---|
| Use it on your projects, at work, for clients, inside your company, in CI | yes | nothing beyond keeping the notices in the files |
| Commit the files it installs (`.ai-sandbox/`, hook scripts) into your repository and share that repository with your team or publicly | yes | the files keep their headers (they already do); keep `LICENSE` and `NOTICE` with full copies |
| Modify it for yourself or inside your company | yes | nothing — private changes never have to be published as long as you do not distribute them%(private_note)s |
| Redistribute it unmodified (mirror, package, bundle it in a template, course, image or installer) | yes | ship `LICENSE` and `NOTICE` with it and make the source available (section 6) |
| Publish a fork, a modified version or a derived tool | yes | license it `%(spdx)s`, publish the complete source, mark it as modified, keep the attribution, and do not call it ai-sandbox / aisb (`NOTICE`) |
%(hosted)s
| Ship a modified version inside a proprietary product, or distribute / host a modified version without publishing its source | **no** — not under the %(gnu_short)s | get a [commercial license](COMMERCIAL-LICENSE.md): pay, or contribute instead |
| Combine it into one program with proprietary code and distribute that | **no** — not under the %(gnu_short)s | commercial license |

## Attribution — the additional terms in `NOTICE`

Section 7 of the GNU GPL v3 lets a licensor add a small number of terms to the license. ai-sandbox adds three,
stated verbatim in [`NOTICE`](NOTICE): the author attribution must be preserved (7(b)), modified versions must
be marked as modified (7(c)), and the project's names may not be used to name or endorse derived versions
(7(d), 7(e)). In practice:

- keep the `NOTICE` file and the two header lines in the source files;
- if you redistribute a build, keep the "%(attr)s" line in the output of `aisb --version` (or your
  equivalent);
- if you modify it, say so, change the version string, and give your version another name.

These terms are compatible with the GPL and %(gnu_short)s (section 7 explicitly permits them) and travel with the
code into anything built on it.

## For companies

Using ai-sandbox at work is free, with no notification, registration or permission required — the license
already grants it. A **commercial license** is only needed when you want to do something the %(gnu_short)s does
not allow (the two "no" rows above), or when procurement wants a signed agreement, warranty or indemnity.
It can be paid for with **money or with maintenance**: an organisation that contributes code, maintains a
target, provides CI or support, or sponsors the project gets the commercial license without a fee. Details and
the request procedure: [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

## Why this license

- **Adoption.** `%(spdx)s` is OSI-approved and known to every corporate legal team; nobody has to ask before
  using the tool, and package indexes, SBOM tools and GitHub recognise it.
- **Acknowledgement.** Every copy, fork and derived product carries the author attribution (`NOTICE`,
  file headers, `aisb --version`), and modified versions must say that they are modified.
- **Contributions flow back.** Anyone who improves and redistributes it must publish the improvements under the
  same license. Forks are allowed, but they stay open and keep the attribution.
- **Sustainability.** Organisations that want to go beyond the %(gnu_short)s pay for a commercial license or
  maintain the project instead; the CLA keeps dual licensing possible.

What this license deliberately does **not** do: it does not require anyone to inform the author or ask
permission (no open-source license can — see the Open Source Definition, points 5–7), it does not forbid forks,
and it puts no obligation on companies that only use the tool internally. The `ADOPTERS.md` request and the
commercial license are the levers for those cases.

## Switching

`python scripts/set_license.py agpl|gpl|apache|noncommercial|strict` regenerates every license-related file and
source header. A later, more restrictive license applies to future versions only; copies already received under
`%(spdx)s` keep that license forever.

%(tail)s""" % {"title": v["title"], "spdx": v["spdx"], "expr": v["expr"], "gnu_short": gnu_short, "attr": attribution(url),
               "hosted": hosted, "tail": COMMON_TAIL,
               "private_note": " or (AGPL only) let others use the modified version over a network" if v["network"] else ""}
    if f == "permissive":
        return """# How ai-sandbox is licensed

ai-sandbox is open source under the **[Apache License 2.0](LICENSE)** (`Apache-2.0`). There is nothing else to
buy or to ask for: everyone — individuals and companies — may use, modify, redistribute and sell it, in open or
proprietary products, as long as they follow the license.

## What the license asks of you

| You want to… | Allowed? | What the license asks of you |
|---|---|---|
| Use it anywhere, including at work and in proprietary products | yes | nothing |
| Commit the installed files into your repositories and share them | yes | the files keep their headers (they already do) |
| Redistribute it, modified or not, in source or binary form | yes | include `LICENSE`; include the attribution in [`NOTICE`](NOTICE) (section 4(d)); state in modified files that you changed them; keep the copyright and license notices |
| Publish a fork or a derived tool | yes | same as above; please give it another name (section 6 grants no trademark rights) |
| Make a closed-source product out of it | yes | same as above — Apache-2.0 has no copyleft |

## Attribution

Section 4(d) of the Apache License requires every redistribution to carry the contents of [`NOTICE`](NOTICE),
which names the author: "%(attr)s". The source files carry a two-line header pointing to it, and
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

%(tail)s""" % {"attr": attribution(url), "tail": COMMON_TAIL}
    # polyform
    strict = v["key"] == "strict"
    return """# How ai-sandbox is licensed

ai-sandbox is **source-available**, not open source: it is published under the **[%(title)s](LICENSE)** for
noncommercial use, and under a **[commercial license](COMMERCIAL-LICENSE.md)** for everything else. SPDX
expression: `%(expr)s`.

## What you can do under the %(short)s, free of charge

| You want to… | Allowed? | Notes |
|---|---|---|
| Use it for personal projects, study, research, hobby work; use by charities, schools, public research bodies and government institutions | yes | regardless of funding (see the license's definition of noncommercial purposes) |
| Keep the files it installs inside your project repository and share that repository with the people you work with | yes | %(embed)s |
| Send a pull request | yes | %(contrib)s |
| Modify it, fork it, redistribute it for noncommercial purposes | %(modify)s | |
| Use it at a company, for clients, in paid work, inside a product or platform | **no** | commercial license |
| Publish a modified version, repackage it, host it as a service | %(publish)s | |

## Attribution

Every copy must carry the `Required Notice` line (it is in `LICENSE` and `NOTICE`), and the source files carry a
two-line header pointing to it; `aisb --version` prints "%(attr)s".

## For companies

Commercial use needs a written license from the copyright holder. It can be paid for with **money or with
maintenance**: an organisation that contributes code, maintains a target, provides CI or support, or sponsors
the project gets the commercial license without a fee. Commercial licensees also agree to tell the maintainer
where the software is used. Details: [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

## Why this license — and its cost

PolyForm gives the author full control: companies legally have to ask. The price is adoption: the license is not
OSI-approved, most corporate policies block it unreviewed, package indexes and GitHub do not recognise it, and
GitHub's terms still allow anyone to fork the public repository on GitHub. The open-source dual-license model
(`python scripts/set_license.py agpl`) trades the "must ask" rule for adoption, mandatory attribution and
contributions flowing back; this file is regenerated when you switch.

%(tail)s""" % {"title": v["title"], "short": v["short"], "expr": v["expr"], "attr": attribution(url), "tail": COMMON_TAIL,
               "embed": "additional permission 1 in `LICENSE`" if strict else "the license permits noncommercial distribution",
               "contrib": "additional permission 2 in `LICENSE`" if strict else "the license permits modification",
               "modify": "**no** (only to contribute)" if strict else "yes",
               "publish": "**no**" if strict else "noncommercial only"}


def gen_commercial(v, url):
    f = v["family"]
    pay_or_contribute = """## Two ways to get a commercial license: pay, or contribute

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

Licenses are granted in writing by the copyright holder, %(owner)s, who retains all rights to license,
sublicense and relicense ai-sandbox. Contributions are accepted under `CLA.md`, which keeps that possible.
""" % {"owner": OWNER_NAME}
    third = """## Third-party content

ai-sandbox itself contains no third-party code. Skill packs, plugins and bundles that `aisb apply` fetches at
your request are **not** part of ai-sandbox; they keep their own licenses (shown at import time and recorded in
`.ai-sandbox/bundles/bundles.lock.json`). Check them before redistributing a bundle you built with `aisb pack`.

*This file is a summary written by the project author, not legal advice. The license text in `LICENSE` and the
terms in `NOTICE` are the binding documents; a commercial license is a separate written agreement.*
"""
    if f == "copyleft":
        gnu_short = "AGPL" if v["network"] else "GPL"
        hosted = ("| Offering a **modified** version as part of a hosted service and giving its users the modified source | free | — |\n"
                  "| Offering a **modified** version as part of a hosted service **without** offering its users the source | — | needed |"
                  if v["network"] else
                  "| Offering a modified version as part of a hosted service (the GPL has no network clause) | free | — |")
        return """# Commercial license

ai-sandbox is free and open source under the %(title)s (`LICENSING.md` explains the whole scheme). **You only
need a commercial license if you want to do something the %(gnu_short)s does not allow** — most teams never do.

## Do you need one?

| Situation | %(gnu_short)s (free) | Commercial license |
|---|---|---|
| Using ai-sandbox at your company, on client projects, in CI, on any number of machines | free | — |
| Committing the installed files into private or public repositories | free | — |
| Private modifications used only inside your organisation | free (nothing to publish) | — |
| Publishing a fork or a modified version under the %(gnu_short)s, with source, marked as modified | free | — |
| Bundling it **unmodified** in a product, template, course, image or installer, with `LICENSE` + `NOTICE` and the source available | free | — |
%(hosted)s
| Bundling a **modified** version in a product without releasing its source under the %(gnu_short)s | — | needed |
| Combining it into one program with proprietary code and distributing that | — | needed |
| A signed agreement, warranty, indemnity or support commitment for procurement | — | available |

%(pay)s
%(third)s""" % {"title": v["title"], "gnu_short": gnu_short, "hosted": hosted, "pay": pay_or_contribute, "third": third}
    if f == "permissive":
        return """# Commercial use, support and sponsorship

ai-sandbox is open source under the Apache License 2.0. **No commercial license exists or is needed**: companies
may use, modify, redistribute and sell it, in open or proprietary products, as long as they keep `LICENSE`,
include the attribution in `NOTICE` (section 4(d)) and mark modified files (`LICENSING.md`).

## What the maintainer offers organisations

- **Support and maintenance agreements** — a named target (tool) kept working, response times, upgrades.
- **A signed agreement, warranty or indemnity** for procurement, where the Apache License's "AS IS" terms are not enough.
- **Sponsorship** — it funds the time that keeps 15+ tool formats verified against vendor docs.
- **Contribution plans** — organisations that maintain a target, provide CI runners or security review, or
  contribute features get their needs prioritised.

Open an issue titled **"Commercial support request"** on the repository or contact the maintainer via the URL in
`NOTICE`. Organisations that use ai-sandbox are asked (not required) to add themselves to `ADOPTERS.md`.

Contributions are accepted under `CLA.md`; the copyright holder, %(owner)s, retains the right to offer the
project under other licenses in the future.

%(third)s""" % {"owner": OWNER_NAME, "third": third}
    # polyform
    strict = v["key"] == "strict"
    rows = ("| Commercial use | using it at a company, for client work, in paid consulting, inside an internal platform |\n"
            "| Modifying beyond contributions | maintaining a patched version, building a derived tool |\n"
            "| Redistribution | publishing a fork, bundling it in a product, template, course, image or installer, mirroring releases |\n"
            "| Hosting | offering it, or a derived service, to third parties |"
            if strict else
            "| Commercial use | using it at a company, for client work, in paid consulting, inside an internal platform |\n"
            "| Commercial redistribution or hosting | bundling it in a product, offering it as a service, selling a derived tool |")
    return """# Commercial and extended licensing

ai-sandbox is published under the **%(title)s** (see `LICENSE`%(plus)s).

**Free, no questions asked:** %(free)s

**Needs a written license from the copyright holder:**

| Situation | Examples |
|---|---|
%(rows)s

This is deliberate: the maintainer keeps a single, verifiable distribution of a security tool and decides who
may build on it (see `GOVERNANCE.md`).

%(pay)s
%(third)s""" % {"title": v["title"], "rows": rows, "pay": pay_or_contribute, "third": third,
               "plus": ", plus a few additional permissions the copyright holder grants on top of it" if strict else "",
               "free": ("using the software, as published, for any **noncommercial** purpose — personal projects, study, "
                        "research, hobby work, and use by charities, schools, public research bodies and government institutions "
                        "regardless of funding. Keeping the files it installs inside your project repository and sharing that "
                        "repository with the people who work on it with you is covered. So is modifying it in order to send a "
                        "pull request." if strict else
                        "using, modifying and sharing the software for any **noncommercial** purpose — personal projects, study, "
                        "research, hobby work, and use by charities, schools, public research bodies and government institutions "
                        "regardless of funding.")}


def gen_readme_section(v):
    f = v["family"]
    if f == "copyleft":
        gnu_short = "AGPL" if v["network"] else "GPL"
        return """**Free and open source under the [%(title)s](LICENSE) — or a [commercial license](COMMERCIAL-LICENSE.md) if you want to ship it closed.**

- **Everyone** — individuals, companies, client work, CI — may use it free of charge, including at work. Keep `LICENSE` and `NOTICE` with any copy.
- **Forks and modified versions** are welcome; the %(gnu_short)s requires them to stay open (source under the same license), to be marked as modified, and to keep the author attribution in [`NOTICE`](NOTICE).
- **Companies** that want to bundle a modified version in a proprietary product or service without releasing the source get a commercial license — paid, **or free in exchange for contributing to or maintaining the project** ([COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)).
- Using it? Add yourself to [ADOPTERS.md](ADOPTERS.md) — it is how the project gets known and maintained.

Details: [LICENSING.md](LICENSING.md) · single-maintainer model: [GOVERNANCE.md](GOVERNANCE.md) · contributions: [CLA.md](CLA.md). Skill packs and plugins you import keep their own licenses, which `aisb` shows and records.""" % {"title": v["title"], "gnu_short": gnu_short}
    if f == "permissive":
        return """**Open source under the [Apache License 2.0](LICENSE).** Use it anywhere, including in commercial and proprietary products; keep `LICENSE` and the attribution in [`NOTICE`](NOTICE) with any copy, and mark modified files. No commercial license exists or is needed — support, sponsorship and contribution plans: [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md). Using it? Add yourself to [ADOPTERS.md](ADOPTERS.md).

Details: [LICENSING.md](LICENSING.md) · single-maintainer model: [GOVERNANCE.md](GOVERNANCE.md) · contributions: [CLA.md](CLA.md). Skill packs and plugins you import keep their own licenses, which `aisb` shows and records."""
    strict = v["key"] == "strict"
    return """**Source-available. Free for noncommercial use; the author keeps control of everything else.**
Free to **use**%(mod)s for any noncommercial purpose (personal, research, education, non-profits, public bodies). Companies%(forks)s need a written license from the copyright holder — paid, **or free in exchange for contributing to or maintaining the project** ([COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)). The license is the [%(title)s](LICENSE)%(plus)s. Using it? Add yourself to [ADOPTERS.md](ADOPTERS.md).

Details: [LICENSING.md](LICENSING.md) · single-maintainer model: [GOVERNANCE.md](GOVERNANCE.md) · contributions: [CLA.md](CLA.md). Skill packs and plugins you import keep their own licenses, which `aisb` shows and records.""" % {
        "title": v["title"], "mod": "" if strict else ", modify and share",
        "forks": " and anyone who wants to **modify, fork, redistribute, repackage, host or commercialise** it" if strict else " and anyone commercialising it",
        "plus": " with additional permissions for keeping the installed files inside your project repository and for sending contributions" if strict else ""}


def gen_faq(v):
    f = v["family"]
    sqlite = ("SQLite's code is actually public domain — anyone may copy, modify and sell it; what makes SQLite feel \"closed\" "
              "is governance (one team, no outside commits, a trademark, paid warranty-of-title licenses for corporate legal "
              "departments). ai-sandbox copies the governance (`GOVERNANCE.md`)")
    if f == "copyleft":
        gnu_short = "AGPL" if v["network"] else "GPL"
        return ("**Why %(gnu_short)s + a commercial license, and not MIT (or \"the SQLite license\")?** %(sqlite)s and uses the "
                "%(spdx)s so that every company's legal team already knows the terms and everyone can use it, at work too, for "
                "free. What the %(gnu_short)s adds over MIT: forks and modified distributions must stay open and keep the author "
                "attribution (`NOTICE`), and whoever wants to ship it closed buys a commercial license — or contributes instead of "
                "paying (`COMMERCIAL-LICENSE.md`). Everything is explained in `LICENSING.md`; switching is one command "
                "(`scripts/set_license.py agpl|gpl|apache|noncommercial|strict`)." % {"gnu_short": gnu_short, "sqlite": sqlite, "spdx": v["spdx"]})
    if f == "permissive":
        return ("**Why Apache-2.0 (and not \"the SQLite license\")?** %(sqlite)s and uses Apache-2.0 for maximum adoption: every "
                "company can use it without review, redistributions must carry the attribution in `NOTICE`, and there is a patent "
                "grant. See `LICENSING.md`; the maintainer can switch to a copyleft dual-license model for future versions with one "
                "command (`scripts/set_license.py agpl`)." % {"sqlite": sqlite})
    return ("**Why %(short)s and not MIT (or \"the SQLite license\")?** %(sqlite)s and goes further on the license: individuals, "
            "students, researchers, non-profits and public bodies use it for free; companies need a written license — paid or in "
            "exchange for maintaining the project (`COMMERCIAL-LICENSE.md`). The cost is adoption: PolyForm is not OSI-approved and "
            "GitHub's license detector does not recognise it (the sidebar says \"View license\"). Switching to the open-source "
            "dual-license model is one command (`scripts/set_license.py agpl`)." % {"short": v["short"], "sqlite": sqlite})


def gen_governance(v):
    f = v["family"]
    if f == "copyleft":
        return """The license (`LICENSE` + `NOTICE`) allows forks and modified versions, under conditions: they stay under the same
license with their source published, they are marked as modified, they keep the author attribution, and they are
not called "ai-sandbox" or "aisb". The canonical distribution is this repository and its signed releases
(`SHA256SUMS`). Shipping a modified version closed, or inside a proprietary product, needs a commercial license
(`COMMERCIAL-LICENSE.md`)."""
    if f == "permissive":
        return """The license (`LICENSE` + `NOTICE`) allows forks, modified versions and proprietary derivatives as long as the
license and the attribution notice travel with them and modified files are marked. Please do not call a modified
version "ai-sandbox" or "aisb". The canonical distribution is this repository and its signed releases (`SHA256SUMS`)."""
    return """What is not allowed without a written license (`COMMERCIAL-LICENSE.md`): commercial use; publishing modified
versions, forks meant to be used instead of the canonical release, repackaged builds, or hosted/managed versions
(%(strict)s); using the names "ai-sandbox" / "aisb" or the project's logo for anything other than the canonical
project. The canonical distribution is this repository and its signed releases (`SHA256SUMS`).""" % {
        "strict": "the Strict variant also forbids noncommercial ones" if v["key"] == "strict" else "for commercial purposes"}


# ----------------------------------------------------------------------------------------------- source headers
HEADER_RE = re.compile(r"^(?P<p>#|rem|::) SPDX-License-Identifier: [^\n]*\n(?P=p) ai-sandbox - Copyright [^\n]*\n", re.M)


def header_lines(v, url, prefix):
    return ("%s SPDX-License-Identifier: %s\n%s ai-sandbox - Copyright (c) %s %s - %s - see LICENSE and NOTICE\n"
            % (prefix, v["expr"], prefix, YEAR, OWNER_NAME, url))


def insertion_point(rel, text):
    lines = text.split("\n")
    i = 0
    ext = os.path.splitext(rel)[1].lower()
    if ext in (".py", ".sh"):
        while i < len(lines) and (lines[i].startswith("#!") or re.match(r"#.*coding[:=]", lines[i])):
            i += 1
    elif ext == ".cmd":
        if lines and lines[0].strip().lower() == "@echo off":
            i = 1
    elif ext == ".ps1":
        while i < len(lines) and lines[i].lower().startswith("#requires"):
            i += 1
    return sum(len(line) + 1 for line in lines[:i])


def stamp_headers(v, url, changed):
    prefix = {".cmd": "rem"}
    for pattern in HEADER_GLOBS:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            text = read(rel)
            hdr = header_lines(v, url, prefix.get(os.path.splitext(rel)[1].lower(), "#"))
            crlf = "\r\n" in text
            if crlf:
                text = text.replace("\r\n", "\n")
            if HEADER_RE.search(text):
                new = HEADER_RE.sub(lambda _m: hdr, text, count=1)
            else:
                at = insertion_point(rel, text)
                new = text[:at] + hdr + text[at:]
            if crlf:
                new = new.replace("\n", "\r\n")
            write(rel, new, changed)


# ----------------------------------------------------------------------------------------------- main
def apply(key, quiet=False):
    v = dict(VARIANTS[key], key=key)
    url = repo_url()
    changed = []
    write("LICENSE", gen_license(v, url), changed)
    write("NOTICE", gen_notice(v, url), changed)
    write("LICENSING.md", gen_licensing(v, url), changed)
    write("COMMERCIAL-LICENSE.md", gen_commercial(v, url), changed)
    # README: badge + section
    t = read("README.md")
    badge = "[![%s](https://img.shields.io/badge/license-%s-blue)](LICENSING.md)" % (v["badge"][1], v["badge"][0])
    t = replace_marked(t, "license-badge", badge, inline=True)
    t = replace_marked(t, "license-section", gen_readme_section(v))
    write("README.md", t, changed)
    write("docs/faq.md", replace_marked(read("docs/faq.md"), "license-faq", gen_faq(v)), changed)
    write("GOVERNANCE.md", replace_marked(read("GOVERNANCE.md"), "license-governance", gen_governance(v)), changed)
    # one-line fields
    write("CITATION.cff", re.sub(r"^license: .*$", "license: " + v["cff"], read("CITATION.cff"), count=1, flags=re.M), changed)
    write("pyproject.toml", re.sub(r'^(\s*)"License :: [^"]*",', lambda m: '%s"%s",' % (m.group(1), v["classifier"]),
                                   read("pyproject.toml"), count=1, flags=re.M), changed)
    init = read("aisb/__init__.py")
    init = re.sub(r'^__license__ = "[^"]*"', '__license__ = "%s"' % v["expr"], init, count=1, flags=re.M)
    init = re.sub(r'^__license_name__ = "[^"]*"', '__license_name__ = "%s"' % v["name"], init, count=1, flags=re.M)
    write("aisb/__init__.py", init, changed)
    stamp_headers(v, url, changed)
    if not quiet:
        for rel in changed:
            print("updated", rel)
        print("license set to %s (%s)" % (key, v["expr"]))
    return 0


def current_variant():
    init = read("aisb/__init__.py")
    m = re.search(r'^__license__ = "([^"]*)"', init, re.M)
    expr = m.group(1) if m else ""
    for key, v in VARIANTS.items():
        if v["expr"] == expr:
            return key
    return None


def check():
    """Regenerate for the current variant into memory and report files that differ (used by CI)."""
    key = current_variant()
    if not key:
        print("cannot determine the current variant from aisb/__init__.py")
        return 1
    snapshot = {}
    for pattern in HEADER_GLOBS + ["LICENSE", "NOTICE", "LICENSING.md", "COMMERCIAL-LICENSE.md", "README.md", "docs/faq.md",
                                   "GOVERNANCE.md", "CITATION.cff", "pyproject.toml", "aisb/__init__.py"]:
        for path in glob.glob(os.path.join(ROOT, pattern)):
            rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
            snapshot[rel] = read(rel)
    apply(key, quiet=True)
    drift = sorted(rel for rel, old in snapshot.items() if read(rel) != old)
    for rel, old in snapshot.items():  # restore whatever apply() touched
        if read(rel) != old:
            with io.open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as fh:
                fh.write(old)
    if drift:
        print("OUT OF DATE for variant %s: %s  (run: python scripts/set_license.py %s)" % (key, ", ".join(drift), key))
        return 1
    print("license files consistent (variant %s)" % key)
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--check":
        return check()
    if len(sys.argv) < 2 or sys.argv[1] not in VARIANTS:
        print(__doc__)
        return 2
    return apply(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
