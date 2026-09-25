"""Phase 1 - Data discovery: verifierar alla datakallor direkt mot deras API:er.

Kors:  python scripts/01_data_discovery.py

Skriptet ar lasbart (endast GET/META + en liten POST-sond) och skriver en
samlad rapport till outputs/results/data_discovery_report.json samt en
sammanfattning till stdout. Ingen data laddas ner i bulk - det gor
src/data/download_data.py i Phase 2.

Verifierar:
1. Skogsstyrelsen PX-Web: targettabell (05), pristabell (JO0303_3ny),
   lagertabell (JO0306_2): metadata, regioner, period, och att dataval
   fungerar (inkl. work-around for icke-ASCII-koder).
2. SMHI MetObs (version/latest): parameterlista, stationsantal och
   tacking for prognosperioden, provhamtning av en stations CSV.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    HTTP_HEADERS,
    PXWEB_BASE_URL,
    PXWEB_DATABASE,
    PXWEB_TABLE_INVENTORY,
    PXWEB_TABLE_PRICES,
    PXWEB_TABLE_TARGET,
    RESULTS_DIR,
    SMHI_METOBS_BASE_URL,
)

TIMEOUT = 60
# Epoch-ms for 2007-01-01 resp. 2026-01-01 (tackningskoll for SMHI-stationer)
MS_2007 = 1167609600000
MS_2026 = 1767225600000


def pxweb_table_path(table: str) -> str:
    return f"{PXWEB_BASE_URL}/{PXWEB_DATABASE}/{table}"


def check_pxweb(report: dict) -> None:
    print("=" * 70)
    print("SKOGSSTYRELSEN PX-WEB")
    print("=" * 70)
    sec = report["skogsstyrelsen"] = {}

    r = requests.get(f"{PXWEB_BASE_URL}/", headers=HTTP_HEADERS, timeout=TIMEOUT)
    dbs = [d["dbid"] for d in r.json()]
    sec["databaser"] = dbs
    print(f"API-root OK ({r.status_code}); databaser: {dbs}")

    # --- target-tabellen
    r = requests.get(pxweb_table_path(PXWEB_TABLE_TARGET), headers=HTTP_HEADERS, timeout=TIMEOUT)
    meta = r.json()
    vars_ = {v["code"]: v for v in meta["variables"]}
    regions = list(zip(vars_["Region"]["values"], vars_["Region"]["valueTexts"]))
    sec["target"] = {
        "title": meta["title"],
        "regioner": len(regions),
        "lan": len(regions) - 5,  # 21 lan + Hela landet + 4 landsdelar
        "ar": vars_["Ar" if "Ar" in vars_ else "År"]["values"],
        "updated": str(meta.get("updated")),
    }
    print(f"\nTarget: {meta['title']}")
    print(f"  regioner: {len(regions)} (21 lan + Hela landet + 4 landsdelar)")
    print(f"  forsta/sista region: {regions[0][1]!r} / {regions[-1][1]!r}")

    # --- datasond: POST med ENBART Region-koden returnerar hela tabellen
    #     (work-around: koder med A/O-diacritikar ger 404 pa denna PX-Web)
    region_value = vars_["Region"]["values"][0]  # "0" = Hela landet
    probe = {
        "query": [
            {
                "code": "Region",
                "selection": {"filter": "item", "values": [region_value]},
            }
        ],
        "response": {"format": "json"},
    }
    r = requests.post(
        pxweb_table_path(PXWEB_TABLE_TARGET),
        headers={**HTTP_HEADERS, "Content-Type": "application/json"},
        data=json.dumps(probe),
        timeout=TIMEOUT,
    )
    data = r.json()["data"]
    first, last = data[0], data[-1]
    sec["target"]["sond"] = {
        "status": r.status_code,
        "n_rader": len(data),
        "forsta": {"key": first["key"], "value": first["values"][0]},
        "sista": {"key": last["key"], "value": last["values"][0]},
        "not_isanlighet": "'..' ar saknat/framtida varde",
    }
    print(f"  datasond: POST OK ({r.status_code}), {len(data)} rader for Hela landet")
    print(f"  forsta raden {first['key']} = {first['values'][0]}")
    print(f"  sista raden {last['key']} = {last['values'][0]}  ('..' = saknar/framtida)")

    # --- pris- och lagertabellerna
    for key, table in (("priser", PXWEB_TABLE_PRICES), ("lager", PXWEB_TABLE_INVENTORY)):
        r = requests.get(pxweb_table_path(table), headers=HTTP_HEADERS, timeout=TIMEOUT)
        m = r.json()
        dims = {v["code"]: len(v["values"]) for v in m["variables"]}
        sec[key] = {"title": m["title"], "dimensioner": dims}
        print(f"\n{key}: {m['title']}")
        print(f"  dimensioner: {dims}")


def check_smhi(report: dict) -> None:
    print("\n" + "=" * 70)
    print("SMHI METOBS (version/latest)")
    print("=" * 70)
    sec = report["smhi"] = {}

    params_to_check = {
        "22": "Lufttemperatur, medel per manad",
        "23": "Nederbordsmangd, summa per manad",
        "2": "Lufttemperatur, medel per dygn",
        "5": "Nederbordsmangd, summa per dygn",
        "8": "Snodjup per dygn",
    }
    sec["parametrar"] = {}
    first_station_csv = None

    for pid, label in params_to_check.items():
        r = requests.get(
            f"{SMHI_METOBS_BASE_URL}/parameter/{pid}.json", headers=HTTP_HEADERS, timeout=TIMEOUT
        )
        meta = r.json()
        stations = meta.get("station", [])
        covering = [
            s for s in stations
            if (s.get("from") or 0) < MS_2007 and (s.get("to") or 0) > MS_2026
        ]
        sec["parametrar"][pid] = {
            "label": label,
            "unit": meta.get("unit"),
            "antal_stationer": len(stations),
            "tacker_2007_2026": len(covering),
        }
        print(f"param {pid} ({label}): {len(stations)} stationer, "
              f"{len(covering)} tacker 2007-2026")

        if pid == "22" and covering and first_station_csv is None:
            first_station_csv = (covering[0]["key"], covering[0]["name"])

    # --- provhamtning: en stations CSV (corrected-archive)
    sid, name = first_station_csv
    r = requests.get(
        f"{SMHI_METOBS_BASE_URL}/parameter/22/station/{sid}.json",
        headers=HTTP_HEADERS, timeout=TIMEOUT,
    )
    periods = [p["key"] for p in r.json().get("period", [])]
    r = requests.get(
        f"{SMHI_METOBS_BASE_URL}/parameter/22/station/{sid}/period/corrected-archive/data.csv",
        headers=HTTP_HEADERS, timeout=TIMEOUT,
    )
    lines = r.text.strip().splitlines()
    sec["provhamtning"] = {
        "station": f"{sid} ({name})",
        "perioder": periods,
        "csv_status": r.status_code,
        "csv_rader": len(lines),
        "forsta_datarad": next((ln for ln in lines if ";" in ln and "Tidsutsnitt" not in ln), ""),
        "sista_datarad": lines[-1],
    }
    print(f"\nprovhamtning param 22, station {sid} ({name}): "
          f"CSV {r.status_code}, {len(lines)} rader")
    print(f"  sista datarad: {lines[-1]}")


def main() -> None:
    report: dict = {
        "genererad": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "syfte": "Verifiering av datakallor for forest-supply-forecast (Phase 1)",
    }
    check_pxweb(report)
    check_smhi(report)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "data_discovery_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print("\n" + "=" * 70)
    print(f"Rapport sparad: {out}")
    print("ALLA KALLOR VERIFIERADE.")


if __name__ == "__main__":
    main()
