"""Hämtning av väderobservationer från SMHI MetObs-API (version/1.0). Fas 2.

Verifierade API-fakta (2026-09-17, se docs/data_inventory.md):

- Bas: https://opendata-download-metobs.smhi.se/api/version/1.0
  (gamla /api/version/1 är avvecklad).
- Flöde: parameter/{id}.json -> station/{sid}.json ->
  period/{period}.json -> period/{period}/data.csv.
- Perioder: "corrected-archive" (kvalitetskontrollerade historiska data,
  utom de senaste ~3 månaderna) och "latest-months" (ogranskade, senaste
  ~4 månaderna). corrected-archive används här; preliminära månader i
  slutet hanteras separat om de behövs.
- CSV: semikolonseparator, BOM, svensk rubrikrad. Två tabellformat:
  månadsdata har rubrikrad "Från Datum Tid (UTC);Till Datum Tid (UTC);
  Representativ månad;<värde>;Kvalitet;..." (datum från Representativ-
  kolumnen), dygnsdata har "Datum;Tid (UTC);<värde>;Kvalitet;...".
- Stationer har lat/lon men ingen länskod (mappning till län/landsdel
  görs i fas 3/4 via koordinater).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

import pandas as pd
import requests

from src.config import HTTP_HEADERS, SMHI_METOBS_BASE_URL


class SmhiError(RuntimeError):
    """API-anrop mot SMHI misslyckades efter retries."""


def _epoch_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


class SmhiClient:
    """Minimal SMHI MetObs-klient med retry."""

    def __init__(
        self,
        base_url: str = SMHI_METOBS_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(headers or HTTP_HEADERS)

    def _request(self, url: str) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(2**attempt)
        raise SmhiError(f"GET {url} misslyckades: {last_exc}") from last_exc

    def parameter_meta(self, pid: int) -> dict:
        resp = self._request(f"{self.base_url}/parameter/{pid}.json")
        if resp.status_code != 200:
            raise SmhiError(f"parameter {pid}: HTTP {resp.status_code}")
        return resp.json()

    def station_data_url(self, pid: int, sid: str, period: str = "corrected-archive") -> str:
        return f"{self.base_url}/parameter/{pid}/station/{sid}/period/{period}/data.csv"

    def download_station_csv(self, pid: int, sid: str, period: str = "corrected-archive") -> str:
        resp = self._request(self.station_data_url(pid, sid, period))
        if resp.status_code != 200:
            raise SmhiError(f"station {pid}/{sid}/{period}: HTTP {resp.status_code}")
        return resp.text


def stations_covering(meta: dict, start: date, end: date) -> list[dict]:
    """Stationer som mäter genom hela fönstret [start, end] (SMHI 'from'/'to' är epoch-ms)."""
    ms_start, ms_end = _epoch_ms(start), _epoch_ms(end)
    return [
        s
        for s in meta.get("station", [])
        if (s.get("from") or 0) < ms_start and (s.get("to") or 0) > ms_end
    ]


def parse_smhi_csv(text: str) -> pd.DataFrame:
    """SMHI-CSV -> DataFrame [date, value, quality].

    Hittar värdetabellen via rubrikraden som inleds med 'Från Datum';
    datum tas från kolumnen vars namn innehåller 'Representativ' (månad,
    t.ex. '2026-05', eller dygn), värdet är nästföljande kolumn och
    kvalitetsflaggan den därefter.
    """
    lines = text.splitlines()
    header_idx = next(
        (
            i
            for i, ln in enumerate(lines)
            if ln.strip().startswith("Från Datum") or ln.strip().startswith("Datum;")
        ),
        None,
    )
    if header_idx is None:
        raise ValueError("hittade ingen rubrikrad ('Från Datum'/'Datum;') i SMHI-CSV")
    header = [h.strip() for h in lines[header_idx].split(";")]

    if any("Representativ" in h for h in header):  # månadsformat
        date_idx = next(i for i, h in enumerate(header) if "Representativ" in h)
        value_idx, quality_idx = date_idx + 1, date_idx + 2
    else:  # dygnsformat: Datum;Tid (UTC);<värde>;Kvalitet
        date_idx = next(i for i, h in enumerate(header) if h == "Datum")
        value_idx, quality_idx = date_idx + 2, date_idx + 3

    rows = []
    for ln in lines[header_idx + 1 :]:
        parts = ln.split(";")
        if len(parts) <= value_idx:
            continue
        rep = parts[date_idx].strip()
        if not rep:
            continue
        quality = parts[quality_idx].strip() if len(parts) > quality_idx else ""
        rows.append((rep, parts[value_idx].strip(), quality))

    df = pd.DataFrame(rows, columns=["representative", "value", "quality"])
    # Månadsformat ('2026-05') -> första dagen i månaden; dygnsformat parseas direkt.
    parsed = pd.to_datetime(df["representative"], format="%Y-%m", errors="coerce")
    daily = pd.to_datetime(df["representative"], format="%Y-%m-%d", errors="coerce")
    df["date"] = parsed.fillna(daily)
    if df["date"].isna().any():
        bad = sorted(df.loc[df["date"].isna(), "representative"].unique())
        raise ValueError(f"okända datumformat i SMHI-CSV: {bad[:5]}")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df[["date", "value", "quality"]].reset_index(drop=True)
