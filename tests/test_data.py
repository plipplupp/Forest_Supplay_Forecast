"""Tester för datamodulerna (fas 2): reshape, datumindex, sortering, missing values.

Ren enhetstestning på syntetiska PX-Web/SMHI-svar - inga nätverksanrop.
E2E-verifiering mot riktiga API:er görs av scripts/01_data_discovery.py och
python -m src.data.download_data.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from src.data.download_data import sha256_file
from src.data.skogsstyrelsen import (
    build_all_values_query,
    parse_region_text,
    target_to_dataframe,
    _numeric,
)
from src.data.smhi import parse_smhi_csv, stations_covering
from src.data.timber_prices import parse_quarter_label, prices_to_dataframe

# ---------------------------------------------------------------- fixtures
TARGET_META = {
    "variables": [
        {
            "code": "Region",
            "values": ["0", "1"],
            "valueTexts": ["00 Hela landet", "01 Stockholms län"],
        },
        {"code": "År", "values": ["0"], "valueTexts": ["2007"]},
        {
            "code": "Månad",
            "values": [str(i) for i in range(12)],
            "valueTexts": ["jan", "feb", "mar", "apr", "maj", "jun",
                           "jul", "aug", "sep", "okt", "nov", "dec"],
        },
    ]
}


def _target_payload() -> dict:
    """Hela landet: 12 månader 2007 (alt. värde/'..'), Stockholm: 1 månad."""
    data = []
    for m in range(12):
        value = str(20_000 + m) if m % 2 == 0 else ".."
        data.append({"key": ["0", "0", str(m)], "values": [value]})
    data.append({"key": ["1", "0", "0"], "values": ["1000"]})
    return {
        "columns": [
            {"code": "Region", "type": "d"},
            {"code": "År", "type": "d"},
            {"code": "Månad", "type": "d"},
            {"code": "areal", "type": "c"},
        ],
        "data": data,
    }


PRICE_META = {
    "variables": [
        {"code": "Landsdel", "values": ["0", "4"],
         "valueTexts": ["Norra Norrland", "Hela landet"]},
        {"code": "Sortiment", "values": ["0"], "valueTexts": ["Tallsågtimmer"]},
        {"code": "Kvartal", "values": ["0", "29"],
         "valueTexts": ["2019K1", "2026K2 Prel."]},
    ]
}


def _price_payload() -> dict:
    return {
        "columns": [
            {"code": "Landsdel", "type": "d"},
            {"code": "Sortiment", "type": "d"},
            {"code": "Kvartal", "type": "t"},  # tidsdimension!
            {"code": "pris", "type": "c"},
        ],
        "data": [
            {"key": ["0", "0", "0"], "values": ["472"]},
            {"key": ["4", "0", "29"], "values": ["918"]},
        ],
    }


SMHI_MONTHLY_CSV = (
    "﻿Stationsnamn;Stationsnummer\n"
    "Abisko Aut;188790\n"
    "\n"
    "Från Datum Tid (UTC);Till Datum Tid (UTC);Representativ månad;Lufttemperatur;Kvalitet;;Tidsutsnitt:\n"
    "2026-04-01 00:00:01;2026-05-01 00:00:00;2026-04;1.3;Y;;Kvalitetskontrollerade historiska data\n"
    "2026-05-01 00:00:01;2026-06-01 00:00:00;2026-05;5.2;Y\n"
    "2026-06-01 00:00:01;2026-07-01 00:00:00;2026-06;;Y\n"
)

SMHI_DAILY_CSV = (
    "﻿Stationsnamn;Stationsnummer\n"
    "Tåsan;102460\n"
    "\n"
    "Datum;Tid (UTC);Snödjup;Kvalitet;;Tidsutsnitt:\n"
    "1997-12-02;06:00:00;0.48;G;;Kvalitetskontrollerade historiska data\n"
    "1997-12-16;06:00:00;;G\n"
)

# ---------------------------------------------------------------- PX-Web
def test_build_all_values_query_hoppar_over_icke_ascii_koder():
    query = build_all_values_query(TARGET_META)
    # "År" och "Månad" har icke-ASCII-kodnamn -> endast Region väljs explicit
    assert [q["code"] for q in query["query"]] == ["Region"]
    assert query["query"][0]["selection"]["values"] == ["0", "1"]


def test_numeric_hanterar_saknade_varden():
    assert _numeric("22916") == 22916.0
    assert np.isnan(_numeric(".."))
    assert np.isnan(_numeric(""))
    assert np.isnan(_numeric(" . "))


def test_parse_region_text():
    assert parse_region_text("00 Hela landet") == ("00", "Hela landet", "rike")
    assert parse_region_text("07 Kronobergs län") == ("07", "Kronobergs län", "län")
    assert parse_region_text("Götaland") == ("", "Götaland", "landsdel")
    assert parse_region_text("Norra Norrland") == ("", "Norra Norrland", "landsdel")


def test_target_reshape_varde_och_missing():
    df = target_to_dataframe(_target_payload(), TARGET_META)
    riket = df[df["region_code"] == "00"].sort_values("date")
    assert len(df) == 13
    assert riket["areal_ha"].iloc[0] == 20000.0
    assert riket["areal_ha"].isna().sum() == 6  # varannan månad = ".."
    assert riket["region_type"].eq("rike").all()


def test_target_datumindex_och_sortering():
    df = target_to_dataframe(_target_payload(), TARGET_META)
    # sorterad per region + datum
    assert df[["region_code", "date"]].apply(tuple, axis=1).is_monotonic_increasing
    # kontinuerlig månadsindex per region (inga dubletter/gap)
    for _, g in df.groupby("region_code"):
        periods = g["date"].dt.to_period("M").sort_values()
        assert periods.is_unique
        ordinals = periods.astype("int64")  # periodordinal: 1 steg = 1 månad
        assert (ordinals.diff().dropna() == 1).all()


def test_target_ar_och_manad_paras_korrekt():
    df = target_to_dataframe(_target_payload(), TARGET_META)
    assert (df["ar"] == 2007).all()
    assert set(df["manad"].unique()) == set(range(1, 13))
    assert (df["date"] == pd.to_datetime("2007-01-01")).sum() == 2


# ---------------------------------------------------------------- priser
def test_parse_quarter_label():
    assert parse_quarter_label("2019K1") == (2019, 1, False)
    assert parse_quarter_label("2026K2 Prel.") == (2026, 2, True)
    with pytest.raises(ValueError):
        parse_quarter_label("2026Q1")


def test_prices_reshape_hanterar_tidsdimension():
    df = prices_to_dataframe(_price_payload(), PRICE_META)
    assert len(df) == 2
    assert list(df.columns) == [
        "landsdel", "sortiment", "ar", "kvartal", "kvartal_label",
        "preliminar", "avrakningspris_kr_m3fub",
    ]
    row = df[df["kvartal_label"] == "2026K2 Prel."]
    assert bool(row["preliminar"].iloc[0])
    assert row["kvartal"].iloc[0] == 2
    assert df["avrakningspris_kr_m3fub"].max() == 918.0


# ---------------------------------------------------------------- SMHI
def test_smhi_manadsformat():
    df = parse_smhi_csv(SMHI_MONTHLY_CSV)
    assert len(df) == 3
    assert df["date"].iloc[0] == pd.Timestamp("2026-04-01")
    assert df["value"].iloc[1] == 5.2
    assert (df["quality"] == "Y").all()


def test_smhi_dygnsformat():
    df = parse_smhi_csv(SMHI_DAILY_CSV)
    assert len(df) == 2
    assert df["date"].iloc[0] == pd.Timestamp("1997-12-02")
    assert df["value"].iloc[0] == 0.48


def test_smhi_saknat_varde_blir_nan():
    assert np.isnan(parse_smhi_csv(SMHI_MONTHLY_CSV)["value"].iloc[2])
    assert np.isnan(parse_smhi_csv(SMHI_DAILY_CSV)["value"].iloc[1])


def test_smhi_ogiltig_csv_kastar():
    with pytest.raises(ValueError):
        parse_smhi_csv("inget här är en värdetabell")


def test_stations_covering_filtrerar_pa_fonster():
    meta = {
        "station": [
            {"key": "a", "from": 946684800000, "to": 1798761600000},   # 2000 -> 2027: OK
            {"key": "b", "from": 1207006800000, "to": 1798761600000},  # 2008: för sent
            {"key": "c", "from": 946684800000, "to": 1577836800000},   # slutat 2020: för tidigt
        ]
    }
    import datetime as dt
    ids = {s["key"] for s in stations_covering(
        meta, dt.date(2007, 1, 1), dt.date(2026, 1, 1))}
    assert ids == {"a"}


# ---------------------------------------------------------------- manifest
def test_sha256_file(tmp_path):
    f = tmp_path / "x.txt"
    f.write_bytes(b"hej")
    assert sha256_file(f) == hashlib.sha256(b"hej").hexdigest()


# ---------------------------------------------------------------- volymer
def _felling_payload() -> tuple[dict, dict]:
    meta = {
        "variables": [
            {"code": "Tabellinnehåll", "values": ["v", "a", "g"],
             "valueTexts": ["Avverkad volym (milj. m³sk)", "Avverkad areal (1000 ha)",
                            "Avverkad volym per ha (m³sk/ha)"]},
            {"code": "Huggningsart", "values": ["0", "5"],
             "valueTexts": ["Slutavverkning", "Alla huggningsarter"]},
            {"code": "Landsdel", "values": ["3", "4"],
             "valueTexts": ["Götaland", "Hela landet"]},
            {"code": "Ägarkategori", "values": ["3"],
             "valueTexts": ["Alla ägargrupper"]},
            {"code": "År (5-årsmedelvärde)", "values": ["0", "1"],
             "valueTexts": ["2021", "2022"]},
        ]
    }
    data = [
        # Götaland 2022: publicerad faktor vinner over volym/areal-berakning
        {"key": ["g", "0", "3", "3", "1"], "values": ["362.5"]},
        {"key": ["v", "0", "3", "3", "1"], "values": ["36.3"]},
        {"key": ["a", "0", "3", "3", "1"], "values": ["100.0"]},
        # riket 2022: saknar publicerad faktor -> beraknas ur volym/areal
        {"key": ["v", "0", "4", "3", "1"], "values": ["52.9"]},
        {"key": ["a", "0", "4", "3", "1"], "values": ["200.0"]},
        # gammal period - ska ignoreras
        {"key": ["g", "0", "3", "3", "0"], "values": ["350.0"]},
        # Alla huggningsarter - ska ignoreras
        {"key": ["v", "5", "3", "3", "1"], "values": ["999"]},
    ]
    payload = {
        "columns": [
            {"code": "Tabellinnehåll", "type": "d"},
            {"code": "Huggningsart", "type": "d"},
            {"code": "Landsdel", "type": "d"},
            {"code": "Ägarkategori", "type": "d"},
            {"code": "År (5-årsmedelvärde)", "type": "t"},
            {"code": "innehåll", "type": "c"},
        ],
        "data": data,
    }
    return payload, meta


def test_felling_factors_vaeljer_senaste_period_och_slutavverkning():
    from src.data.felling_volume import felling_to_factors

    df = felling_to_factors(*_felling_payload())
    assert set(df["landsdel"]) == {"Götaland", "Hela landet"}
    assert (df["period"] == "2022 (5-årsmedel)").all()
    got = float(df.loc[df["landsdel"] == "Götaland", "faktor_m3sk_per_ha"].iloc[0])
    assert got == 362.5  # publicerad faktor vinner; 2021 och alla-huggningsarter saknas
    riket = float(df.loc[df["landsdel"] == "Hela landet", "faktor_m3sk_per_ha"].iloc[0])
    assert riket == 264.5  # beraknad: 52.9 milj m3sk / 200 tusen ha


def test_factor_for_region_lan_erv_landsdel():
    from src.data.felling_volume import factor_for_region

    factors = pd.DataFrame(
        {"landsdel": ["Götaland", "Hela landet"],
         "faktor_m3sk_per_ha": [362.5, 264.6]}
    )
    landsdel_by_lan = {"Götaland": ["08", "09"], "Svealand": ["01"]}
    assert factor_for_region("Götaland", factors, landsdel_by_lan) == (362.5, "Götaland")
    assert factor_for_region("Hela landet", factors, landsdel_by_lan) == (264.6, "Hela landet")
    assert factor_for_region("Kalmar län", factors, landsdel_by_lan) == (362.5, "Götaland")
    with pytest.raises(KeyError):
        factor_for_region("Okänd region", factors, landsdel_by_lan)
