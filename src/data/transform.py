"""Bygger processed-dataset (parquet) från raw-data. Fas 2.

Körs som:  python -m src.data.transform

Skriver till data/processed/ (PARQUET - hela kedjan läser processed via
src/data/datasets.py, aldrig råa filer; omkörning av download + transform
återskapar parquet automatiskt när ny månadsdata hämtats):
  target_monthly.parquet          region_code, region_name, region_type, ar, manad,
                                  date, areal_ha                  (NaN = saknas/'..')
  prices_quarterly.parquet        landsdel, sortiment, ar, kvartal, kvartal_label,
                                  preliminar, avrakningspris_kr_m3fub
  weather_stations.parquet        parameter, station_id, station_namn, lat, lon,
                                  date, value, quality            (långt format)
  weather_national_monthly.parquet
  volume_factors.parquet      landsdel, period, volym_milj_m3sk, areal_1000_ha,
                              faktor_m3sk_per_ha (slutavverkning, 5-årsmedel)
                              månadsaggregerat för hela landet: medel över
                              rapporterande stationer + antal stationer
                              (temp °C; nederbörd mm/månad; snö m, andel
                              snödagar, antal dygn) - kompositionseffekten
                              (stationsomfälle varierar) dokumenteras via n-kolumnerna
  DATA_DICTIONARY.md          kolumnbeskrivningar

Regional (län/landsdel) väderaggregering väntar till fas 3/4 tills
station->län-mappningen via koordinater är beslutad och dokumenterad.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR  # noqa: E402
from src.data.felling_volume import felling_to_factors  # noqa: E402
from src.data.skogsstyrelsen import target_to_dataframe  # noqa: E402
from src.data.smhi import parse_smhi_csv  # noqa: E402
from src.data.timber_prices import prices_to_dataframe  # noqa: E402

RAW_SS = RAW_DATA_DIR / "skogsstyrelsen"
RAW_SMHI = RAW_DATA_DIR / "smhi"

WEATHER_PARAMS = {
    22: ("temp_mean_c", "Lufttemperatur, medel per månad"),
    23: ("precip_sum_mm", "Nederbördsmängd, summa per månad"),
    8: ("snow_daily_m", "Snödjup per dygn"),
}

DATA_DICTIONARY = """# Data dictionary (processed)

## target_monthly.parquet
| Kolumn | Beskrivning |
| ------ | ----------- |
| region_code | Länkod enligt Skogsstyrelsen ('01'–'25'); tom för landsdel/rike |
| region_name | Läsbar regionsnamn ('Hela landet', 'Götaland', 'Jönköpings län', …) |
| region_type | rike / landsdel / län |
| ar, manad | År resp. månad (1–12) |
| date | Månadsstart (Timestamp) |
| areal_ha | Anmäld + ansökt avverkningsareal (hektar). NaN = saknas/'..' i källan |

Källa: Skogsstyrelsen PX-Web tabell 05_Areal_anm_ans_per_manad (2007M01–).
TERMINOLOGI: anmäld areal är en PROXY - inte 'faktisk avverkning'.

## prices_quarterly.parquet
| Kolumn | Beskrivning |
| ------ | ----------- |
| landsdel | Norra Norrland / Södra Norrland / Svealand / Götaland / Hela landet |
| sortiment | Tallsågtimmer, Gransågtimmer, Sågtimmer, Massaved av barrträd/lövträd/totalt |
| ar, kvartal, kvartal_label | Kvartalsupplösning |
| preliminar | True om källan märkt kvartalet 'Prel.' |
| avrakningspris_kr_m3fub | Volymvägt genomsnittligt avräkningspris (kr/m3f ub) |

Källa: JO0303_3ny (2019K1–, ny metod; metodbryt 2025K2 - äldre serier ej jämförbara).

## weather_stations.parquet
Långformat per station: parameter (22/23/8), station_id/namn, lat/lon,
date (månadsstart resp. dygn), value (°C / mm / m), quality (SMHI-flagga).
Källa: SMHI MetObs version/1.0, corrected-archive. Stationer utan länskod -
regional mappning sker via koordinater (fas 3/4).

## weather_national_monthly.parquet
Månadsaggregerat, hela landet: temp_mean_c/n_temp_stations,
precip_sum_mm/n_precip_stations, snow_mean_m/andel_snodagar/n_snow_days/
n_snow_stations. Medel över rapporterande stationer - se n-kolumnerna för
täckning (stationsomfallet påverkar nivån; hanteras i fas 3).

## volume_factors.parquet
| Kolumn | Beskrivning |
| ------ | ----------- |
| landsdel | Norra/Södra Norrland, Svealand, Götaland, Hela landet |
| period | 5-årsmedelvärde (senaste publicerade period) |
| volym_milj_m3sk, areal_1000_ha | Underlagsdata (slutavverkning, alla ägargrupper) |
| faktor_m3sk_per_ha | Publicerad genomsnittlig avverkad volym per ha - används för indikativ volym = anmäld areal × faktor |

Källa: JO0312_06 (Riksskogstaxeringen-baserad). OBS: gäller SLUTAVVERKNING
(avverkningsanmälan omfattar inte gallring/röjning). Län ärver sin landsdels faktor.

OBS: weather_national_monthly.parquet sträcker sig längre bak i tiden än 2007
(äldsta snöstationer har data till 1700-talet). Före ~2007 vilar aggregeringen
på få stationer - använd endast data från och med targetens start (2007M01),
se n_*-kolumnerna.
"""


def build_target() -> pd.DataFrame:
    blob = json.loads((RAW_SS / "avverkningsanmalan_tabell05.json").read_text())
    df = target_to_dataframe(blob["payload"], blob["metadata"])
    out = PROCESSED_DATA_DIR / "target_monthly.parquet"
    df.to_parquet(out, index=False)
    print(f"target_monthly.parquet: {len(df):,} rader, "
          f"{df['region_name'].nunique()} regioner, {df['date'].min():%Y-%m}–{df['date'].max():%Y-%m}")
    return df


def build_prices() -> pd.DataFrame:
    blob = json.loads((RAW_SS / "avrakningspriser_JO0303_3ny.json").read_text())
    df = prices_to_dataframe(blob["payload"], blob["metadata"])
    out = PROCESSED_DATA_DIR / "prices_quarterly.parquet"
    df.to_parquet(out, index=False)
    print(f"prices_quarterly.parquet: {len(df):,} rader, "
          f"{df['ar'].min()}K{df.loc[df['ar'] == df['ar'].min(), 'kvartal'].min()}–"
          f"{df['kvartal_label'].max()}")
    return df


def build_weather_stations() -> pd.DataFrame:
    frames = []
    for pid, (col, desc) in WEATHER_PARAMS.items():
        param_dir = RAW_SMHI / f"param_{pid}"
        index = json.loads((param_dir / "stationsindex.json").read_text())
        meta = {s["id"]: s for s in index["stationer"]}
        parts = []
        for csv_path in sorted(param_dir.glob("*.csv")):
            sid = csv_path.stem
            s = meta[sid]
            df = parse_smhi_csv(csv_path.read_text(encoding="utf-8-sig"))
            df.insert(0, "station_id", sid)
            df.insert(1, "station_namn", s["namn"])
            df.insert(2, "lat", s["lat"])
            df.insert(3, "lon", s["lon"])
            parts.append(df)
        stations = pd.concat(parts, ignore_index=True)
        stations.insert(0, "parameter", pid)
        stations.insert(1, "parameter_beskrivning", desc)
        frames.append(stations)
        print(f"  param {pid} ({desc}): {len(meta)} stationer, {len(stations):,} rader")
    df = pd.concat(frames, ignore_index=True)
    out = PROCESSED_DATA_DIR / "weather_stations.parquet"
    df.to_parquet(out, index=False)
    print(f"weather_stations.parquet: {len(df):,} rader")
    return df


def build_weather_national(stations: pd.DataFrame) -> pd.DataFrame:
    """Månadsaggregerat för hela landet: medel över rapporterande stationer + täckning."""
    monthly = stations[stations["parameter"].isin([22, 23])].copy()
    monthly["month"] = monthly["date"].dt.to_period("M")

    out = None
    for pid, prefix in ((22, "temp"), (23, "precip")):
        sub = monthly[monthly["parameter"] == pid]
        agg = sub.groupby("month")["value"].agg(["mean", "size"]).reset_index()
        agg.columns = ["month", f"{prefix}_{'mean_c' if pid == 22 else 'sum_mm'}",
                       f"n_{prefix}_stations"]
        out = agg if out is None else out.merge(agg, on="month", how="outer")

    snow = stations[stations["parameter"] == 8].copy()
    snow["month"] = snow["date"].dt.to_period("M")
    sagg = snow.groupby("month").apply(
        lambda g: pd.Series(
            {
                "snow_mean_m": g["value"].mean(),
                "andel_snodagar": (g["value"] > 0).mean(),
                "n_snow_days": len(g),
                "n_snow_stations": g["station_id"].nunique(),
            }
        ),
        include_groups=False,
    ).reset_index()
    out = out.merge(sagg, on="month", how="outer")

    out["date"] = out["month"].dt.to_timestamp()
    out = out.drop(columns=["month"]).sort_values("date").reset_index(drop=True)
    out_path = PROCESSED_DATA_DIR / "weather_national_monthly.parquet"
    out.to_parquet(out_path, index=False)
    print(f"weather_national_monthly.parquet: {len(out):,} månader, "
          f"{out['date'].min():%Y-%m}–{out['date'].max():%Y-%m}")
    return out


def build_volume_factors() -> pd.DataFrame:
    blob = json.loads((RAW_SS / "avverkad_volym_JO0312_06.json").read_text())
    df = felling_to_factors(blob["payload"], blob["metadata"])
    out = PROCESSED_DATA_DIR / "volume_factors.parquet"
    df.to_parquet(out, index=False)
    print(f"volume_factors.parquet: {len(df)} landsdelar "
          f"(period {df['period'].iloc[0]})")
    return df


def main() -> int:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    build_target()
    build_prices()
    stations = build_weather_stations()
    build_weather_national(stations)
    build_volume_factors()
    (PROCESSED_DATA_DIR / "DATA_DICTIONARY.md").write_text(DATA_DICTIONARY)
    print("\nKlar - processed-data och data dictionary skrivna.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
