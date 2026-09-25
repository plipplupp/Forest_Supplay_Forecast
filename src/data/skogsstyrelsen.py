"""Hämtning av data från Skogsstyrelsens statistikdatabas (PX-Web API v1). Fas 2.

Körs via src/data/download_data.py (python -m src.data.download_data).

Verifierade API-fakta (2026-09-17, se docs/data_inventory.md):

- API-root: https://pxweb.skogsstyrelsen.se/api/v1/sv (kräver User-Agent).
- Targettabell: Avverkningsanmalan/05_Areal_anm_ans_per_manad.px
  "Areal anmälan om avverkning och ansökan om tillstånd till avverkning
  efter Region, År och Månad", 2007M01–2026M08.
- API-QUIRK: POST:ar där variabelkodens NAMN innehåller icke-ASCII-tecken
  (t.ex. "År", "Månad") ger HTTP 404 (i stället för 400). Kodernas VÄRDEN är
  ASCII ("0"–"19" för år) - det är kodnamnet som spårar ur server-side.
  Work-around (verifierad): query som endast innehåller ASCII-kodade
  dimensioner; servern fyller i ALLA värden för övriga dimensioner. För
  targettabellen räcker därför Region (alla 26 värden) för hela tabellen.
- Saknade/framtida värden representeras som "..".
"""

from __future__ import annotations

import time
from urllib.parse import quote

import pandas as pd
import requests

from src.config import HTTP_HEADERS, PXWEB_BASE_URL, PXWEB_DATABASE

LANDSDEL_NAMES = ("Norra Norrland", "Södra Norrland", "Svealand", "Götaland")
RIKE_NAME = "Hela landet"

_MONTH_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


class PxWebError(RuntimeError):
    """API-anrop mot PX-Web misslyckades efter retries."""


class PxWebClient:
    """Minimal PX-Web API v1-klient med retry och den dokumenterade quirk-hänsynen."""

    def __init__(
        self,
        base_url: str = PXWEB_BASE_URL,
        database: str = PXWEB_DATABASE,
        timeout: float = 90.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.database = database
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(headers or HTTP_HEADERS)

    def table_url(self, table_path: str) -> str:
        return f"{self.base_url}/{quote(self.database)}/{quote(table_path)}"

    def _request(self, method: str, url: str, **kwargs: object) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if resp.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                return resp
            except requests.RequestException as exc:  # nätverk/timeout
                last_exc = exc
                time.sleep(2**attempt)
        raise PxWebError(f"{method} {url} misslyckades: {last_exc}") from last_exc

    def metadata(self, table_path: str) -> dict:
        resp = self._request("GET", self.table_url(table_path))
        if resp.status_code != 200:
            raise PxWebError(f"metadata {table_path}: HTTP {resp.status_code}")
        return resp.json()

    def fetch_whole_table(self, table_path: str) -> tuple[dict, dict]:
        """Hämtar en hel tabell (payload, metadata).

        Queryn innehåller endast dimensioner vars kodnamn är rena ASCII
        (se moduldokstringen). Servern fyller i alla värden för de övriga.
        """
        meta = self.metadata(table_path)
        resp = self._request(
            "POST",
            self.table_url(table_path),
            json=build_all_values_query(meta),
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            raise PxWebError(f"data {table_path}: HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json(), meta


def build_all_values_query(metadata: dict) -> dict:
    """PX-Web query som väljer ALLA värden för alla ASCII-kodade dimensioner.

    Work-around för serverns 404 på icke-ASCII-kodnamn ("År", "Månad"):
    dimensioner som utelämnas ur queryn returneras i sin helhet, så det
    räcker att explicit välja de ASCII-kodade dimensionerna.
    """
    query = []
    for var in metadata["variables"]:
        if var["code"].isascii():
            query.append(
                {
                    "code": var["code"],
                    "selection": {"filter": "item", "values": list(var["values"])},
                }
            )
    return {"query": query, "response": {"format": "json"}}


def _value_text_lookup(metadata: dict) -> dict[str, dict[str, str]]:
    """Per variabelkod: värde -> valueText (läsbar etikett)."""
    return {
        var["code"]: dict(zip(var["values"], var["valueTexts"]))
        for var in metadata["variables"]
    }


def parse_region_text(text: str) -> tuple[str, str, str]:
    """'07 Kronobergs län' -> ('07', 'Kronobergs län', 'län'); landsdel/rike har ingen länkod."""
    parts = text.split(" ", 1)
    if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 2:
        code, name = parts[0], parts[1]
    else:
        code, name = "", text
    if name == RIKE_NAME:
        region_type = "rike"
    elif name in LANDSDEL_NAMES:
        region_type = "landsdel"
    else:
        region_type = "län"
    return code, name, region_type


def _numeric(value: str) -> float:
    """PX-Web: '..' (och varianter) = saknat värde -> NaN."""
    if value is None or value.strip() in {"..", ".", ""}:
        return float("nan")
    return float(value)


def target_to_dataframe(payload: dict, metadata: dict) -> pd.DataFrame:
    """PX-Web-svar för tabell 05 -> tidy DataFrame (en rad per region×månad).

    Kolumner: region_code, region_name, region_type, ar, manad, date, areal_ha.
    """
    lookup = _value_text_lookup(metadata)
    dims = [c["code"] for c in payload["columns"] if c["type"] in ("d", "t")]
    contents = [c["code"] for c in payload["columns"] if c["type"] == "c"]
    if len(contents) != 1:
        raise ValueError(f"förväntade exakt en innehållskolumn, fick {contents}")

    records = []
    for row in payload["data"]:
        rec = {}
        for dim, key in zip(dims, row["key"]):
            rec[dim] = lookup[dim][key]
        rec["value"] = _numeric(row["values"][0])
        records.append(rec)

    df = pd.DataFrame.from_records(records)
    parsed = df["Region"].map(parse_region_text)
    df["region_code"] = parsed.map(lambda t: t[0])
    df["region_name"] = parsed.map(lambda t: t[1])
    df["region_type"] = parsed.map(lambda t: t[2])
    df["ar"] = df["År"].astype(int)
    df["manad"] = df["Månad"].str.lower().map(_MONTH_NUM)
    if df["manad"].isna().any():
        bad = sorted(df.loc[df["manad"].isna(), "Månad"].unique())
        raise ValueError(f"okända månadsetiketter: {bad}")
    df["date"] = pd.to_datetime(
        {"year": df["ar"], "month": df["manad"], "day": 1}
    )
    df = (
        df.rename(columns={"value": "areal_ha"})[
            ["region_code", "region_name", "region_type", "ar", "manad", "date", "areal_ha"]
        ]
        .sort_values(["region_code", "region_name", "date"], kind="stable")
        .reset_index(drop=True)
    )
    return df
