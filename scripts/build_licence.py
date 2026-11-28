#!/usr/bin/env python3
"""Write LICENSE: the ELI End User Licence Agreement, ELI Creation Station's Product Schedule and the
tier supplements, as ELI Legal's and ELI VR's LICENSE carry them.

    python3 scripts/build_licence.py            from ELI v3 beside this checkout (or ELI_V3_SRC)

The agreement and the tier supplements are ELI v3's (COMMERCIAL_EULA.md, docs/eula/*.md), word for
word; the schedule is this repository's docs/eula/CREATION.md. Run it again when either changes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE = "=" * 79

HEADER = """ELI Creation Station

PROPRIETARY COMMERCIAL SOFTWARE — NOT OPEN SOURCE

Its source code may be published for anyone to read. Reading it grants no licence: not to
install, run, copy, modify or build it, nor to use anything built from it.

ELI Creation Station is licensed, not sold. The only licence to install, run, copy or modify it is
the one granted by the ELI End User Licence Agreement together with the ELI Creation Station Product
Schedule, both set out in full below: for a licence to ELI Creation Station you have purchased, an
ELI v3 licence that includes it, or its seven-day trial. Having a copy of the software or its source
code, from a download, an installer, a repository or anyone else, does not by itself give you a
licence to use it. The Licensor is named in the agreement.

Third-party components and models keep their own licences, which this notice does not change. See
THIRD_PARTY_NOTICES.md and docs/MODELS.md.

Licensing and purchasing: ShadowESC95 <jaybridgeman0095@gmail.com>

These are the same terms ELI v3 ships (ELI v3 {commit}), reproduced so that ELI Creation Station
carries its own. Where the agreement names a file (the tier supplements in docs/eula/,
THIRD_PARTY_NOTICES.md, models/MODEL_LICENSES.md), it means the one that accompanies the ELI
Product concerned; the tier supplements are in the appendix below.
"""


def main() -> int:
    core = Path(os.environ.get("ELI_V3_SRC") or ROOT.parent / "ELI_v3.0")
    eula = core / "COMMERCIAL_EULA.md"
    if not eula.is_file():
        print(f"no ELI v3 at {core} (set ELI_V3_SRC)", file=sys.stderr)
        return 1
    try:
        commit = subprocess.run(["git", "-C", str(core), "rev-parse", "--short=10", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unknown"
    schedule = (ROOT / "docs" / "eula" / "CREATION.md").read_text(encoding="utf-8")
    schedule = "\n".join(line for line in schedule.splitlines() if "Copy it there as" not in line
                         and "id `creation` is added" not in line and "Made from ELI v3's" not in line)
    tiers = [core / "docs" / "eula" / f"{name}.md" for name in ("PERSONAL", "PRO", "ENTERPRISE", "TRIAL")]
    parts = [HEADER.format(commit=commit), RULE, "", eula.read_text(encoding="utf-8").strip(), "", RULE, "",
             schedule.strip(), "", RULE, "", "# Appendix: Tier Supplements", ""]
    parts += [t.read_text(encoding="utf-8").strip() + "\n" for t in tiers if t.is_file()]
    (ROOT / "LICENSE").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote LICENSE from ELI v3 {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
