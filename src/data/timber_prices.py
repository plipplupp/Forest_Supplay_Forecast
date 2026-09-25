"""Virkespriser (Skogsstyrelsen JO0303_3ny) - hämtning och reshape. Fas 2.

Verifierade fakta (se docs/data_inventory.md):

- Tabell JO0303_3ny: avräkningspriser, volymvägda genomsnitt (kr/m3f ub)
  för leveransvirke, kvartal 2019K1-, per landsdel och sortiment.
  Alla kodnamn är ASCII -> hela tabellen hämtas med explicit selections.
- Sista kvartalet kan vara märkt "Prel." i valueTexts - fångas som flagga.
- Metodbryt 2025K2; äldre priser (JO0303_3.px m.fl.) används inte.
"""

from __future__ import annotations

import re

import pandas as pd

from src.data.skogsstyrelsen import _numeric

_QUARTER_RE = re.compile(r"^(\d{4})K([1-4])(?:\s+(?P<prel>Prel\.))?$")


def parse_quarter_label(text: str) -> tuple[int, int, bool]:
    """'2019K1' -> (2019, 1, False); '2026K2 Prel.' -> (2026, 2, True)."""
    m = _QUARTER_RE.match(text.strip())
    if not m:
        raise ValueError(f"okänd kvartaletikett: {text!r}")
    return int(m.group(1)), int(m.group(2)), m.group("prel") is not None


def prices_to_dataframe(payload: dict, metadata: dict) -> pd.DataFrame:
    """PX-Web-svar för JO0303_3ny -> tidy DataFrame.

    Kolumner: landsdel, sortiment, ar, kvartal, kvartal_label, preliminar,
    avrakningspris_kr_m3fub.
    """
    lookup = {
        var["code"]: dict(zip(var["values"], var["valueTexts"]))
        for var in metadata["variables"]
    }
    dims = [c["code"] for c in payload["columns"] if c["type"] in ("d", "t")]
    contents = [c["code"] for c in payload["columns"] if c["type"] == "c"]
    if len(contents) != 1:
        raise ValueError(f"förväntade exakt en innehållskolumn, fick {contents}")

    records = []
    for row in payload["data"]:
        rec = {dim: lookup[dim][key] for dim, key in zip(dims, row["key"])}
        rec["value"] = _numeric(row["values"][0])
        records.append(rec)
    df = pd.DataFrame.from_records(records)

    parsed = df["Kvartal"].map(parse_quarter_label)
    df["ar"] = parsed.map(lambda t: t[0])
    df["kvartal"] = parsed.map(lambda t: t[1])
    df["preliminar"] = parsed.map(lambda t: t[2])

    df = df.rename(
        columns={
            "Landsdel": "landsdel",
            "Sortiment": "sortiment",
            "Kvartal": "kvartal_label",
            "value": "avrakningspris_kr_m3fub",
        }
    )
    return df[
        [
            "landsdel",
            "sortiment",
            "ar",
            "kvartal",
            "kvartal_label",
            "preliminar",
            "avrakningspris_kr_m3fub",
        ]
    ].sort_values(["sortiment", "landsdel", "ar", "kvartal"], kind="stable").reset_index(drop=True)
