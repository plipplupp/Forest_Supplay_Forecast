"""Enhetliga läsare för processed-data (parquet). Fas 2.

ALL downstream-kod (EDA, features, modeller, utvärdering, Streamlit-app) läser
processed-data via dessa funktioner - aldrig direkt från filvägar. När ny
månadsdata hämtats räcker det att köra om download + transform; parquet
återskapas automatiskt och alla konsumenter får den färska datan.
"""

from __future__ import annotations

import pandas as pd

from src.config import PROCESSED_DATA_DIR


def _read(name: str) -> pd.DataFrame:
    path = PROCESSED_DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} saknas - kör 'python -m src.data.download_data' och "
            "'python -m src.data.transform' först"
        )
    return pd.read_parquet(path)


def load_target() -> pd.DataFrame:
    """Månadsvis anmäld avverkningsareal per region (region_code/name/type, ar, manad, date, areal_ha)."""
    return _read("target_monthly.parquet")


def load_prices() -> pd.DataFrame:
    """Kvartalsvisa virkespriser per landsdel/sortiment (med preliminar-flagga)."""
    return _read("prices_quarterly.parquet")


def load_weather_stations() -> pd.DataFrame:
    """Långformat per SMHI-station (parameter 22/23/8)."""
    return _read("weather_stations.parquet")


def load_weather_national() -> pd.DataFrame:
    """Månadsaggregerat väder för hela landet med täckningskolumner."""
    return _read("weather_national_monthly.parquet")

def load_target_wide(fill_gaps: bool = True) -> pd.DataFrame:
    """Wide-modellmatris: index = månadsstarter (kontinuerligt), kolumner = region.

    Gotlands datagap 2010M03-2010M07 fylls med 0 (dokumenterat i methodology/
    limitations). Framtida månader (efter senaste observationen) innehåller NaN.
    """
    df = load_target()
    wide = df.pivot(index="date", columns="region_name", values="areal_ha")
    last_obs = wide["Hela landet"].last_valid_index()
    wide = wide.loc[:last_obs]
    # kontinuerlig månadsindex
    full_idx = pd.date_range(wide.index.min(), wide.index.max(), freq="MS")
    wide = wide.reindex(full_idx)
    if fill_gaps:
        wide = wide.fillna(0.0)
    wide.index.name = "date"
    return wide


def load_volume_factors() -> pd.DataFrame:
    """Indikativa volymfaktorer (m³sk/ha, slutavverkning) per landsdel."""
    return _read("volume_factors.parquet")
