"""Indikativa volymerfaktorer: m³sk/ha (slutavverkning) per landsdel. Fas 12-tillägg.

Källa: Skogsstyrelsen JO0312_06 - bruttoavverkad volym, avverkad areal och
genomsnittlig avverkad volym per landsdel, ägarkategori och huggningsart
(5-årsmedelvärden, Riksskogstaxeringen-baserad statistik).

Faktorval: SLUTAVVERKNING, alla ägargrupper, senaste period med data.
Motivering: avverkningsanmälan gäller föryngringsavverkning (slutavverkning);
gallring/röjning kräver ingen anmälan och ska därför inte in i faktorn.
"""

from __future__ import annotations

import pandas as pd

from src.config import REGION_NAMES

CONTENT_VOLYM = "Avverkad volym (milj. m³sk)"
CONTENT_AREAL = "Avverkad areal (1000 ha)"
CONTENT_FAKTOR = "Avverkad volym per ha (m³sk/ha)"
HUGGNINGSART = "Slutavverkning"
AGARKATEGORI = "Alla ägargrupper"


def felling_to_factors(payload: dict, metadata: dict) -> pd.DataFrame:
    """PX-Web-svar för JO0312_06 -> DataFrame [landsdel, period, faktor_m3sk_per_ha, ...].

    Faktorn är den publicerade genomsnittliga avverkningsvolymen (m³sk/ha) för
    slutavverkning, alla ägargrupper, senaste period med data. Volym/areal
    medföljer som underlag.
    """
    dims = [c["code"] for c in payload["columns"] if c["type"] in ("d", "t")]
    lookup = {v["code"]: dict(zip(v["values"], v["valueTexts"])) for v in metadata["variables"]}
    content_dim = "Tabellinnehåll"
    year_dim = next(d for d in dims if d.startswith("År"))

    recs: dict[tuple[str, str], dict[str, float | str]] = {}
    for row in payload["data"]:
        labels = {d: lookup[d].get(k, k) for d, k in zip(dims, row["key"])}
        if labels["Huggningsart"] != HUGGNINGSART or labels["Ägarkategori"] != AGARKATEGORI:
            continue
        value = row["values"][0]
        if value == "..":
            continue
        key = (labels[year_dim], labels["Landsdel"])
        recs.setdefault(key, {})[labels[content_dim]] = float(value)

    if not recs:
        raise ValueError("ingen slutavverkningsdata i tabellen")
    latest = max(y for y, _ in recs)

    rows = []
    for (year_text, landsdel), content in sorted(recs.items()):
        if year_text != latest:
            continue
        if CONTENT_FAKTOR in content:
            faktor = content[CONTENT_FAKTOR]
        elif CONTENT_VOLYM in content and CONTENT_AREAL in content and content[CONTENT_AREAL] > 0:
            faktor = content[CONTENT_VOLYM] * 1e6 / (content[CONTENT_AREAL] * 1e3)
        else:
            continue
        rows.append(
            {
                "landsdel": landsdel,
                "period": f"{year_text} (5-årsmedel)",
                "volym_milj_m3sk": content.get(CONTENT_VOLYM),
                "areal_1000_ha": content.get(CONTENT_AREAL),
                "faktor_m3sk_per_ha": round(faktor, 1),
            }
        )
    return pd.DataFrame(rows)


def factor_for_region(
    region_name: str, factors: pd.DataFrame, landsdel_by_lan: dict[str, list[str]]
) -> tuple[float, str]:
    """Faktor (m³sk/ha) + vilken landsdel som används för en given region.

    Landsdelar och 'Hela landet' har egna rader; ett län ärver sin landsdels
    faktor (landsdel_by_lan använder länskoder enligt src/config.REGION_NAMES).
    """
    by_name = factors.set_index("landsdel")["faktor_m3sk_per_ha"]
    if region_name in by_name.index:
        return float(by_name[region_name]), region_name
    code = {name: code for code, name in REGION_NAMES.items()}.get(region_name)
    if code is not None:
        for landsdel, lan_codes in landsdel_by_lan.items():
            if code in lan_codes:
                return float(by_name[landsdel]), landsdel
    raise KeyError(f"ingen landsdel matchar regionen {region_name!r}")
