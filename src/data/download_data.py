"""Reproducerbar nedladdning av all raw-data. Fas 2.

Körs som:  python -m src.data.download_data [--only target|prices|weather] [--force]

Laddar till data/raw/:
  skogsstyrelsen/avverkningsanmalan_tabell05.json   (target, hela tabellen)
  skogsstyrelsen/avrakningspriser_JO0303_3ny.json   (virkespriser)
  smhi/param_22/*.csv + param_23/*.csv + param_8/*.csv + stationsindex per param

Alla filer loggas i data/raw/download_manifest.json med URL, tidpunkt (UTC),
sha256 och storlek, plus miljöinformation (python/pandas/numpy-version) -
det ger full provenance och gör körningen idempotent (befintliga filer
hopplas över utan --force).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import (  # noqa: E402
    PXWEB_TABLE_FELLING,
    PXWEB_TABLE_PRICES,
    PXWEB_TABLE_TARGET,
    RAW_DATA_DIR,
    SMHI_PARAM_PRECIP_MONTHLY,
    SMHI_PARAM_SNOW_DAILY,
    SMHI_PARAM_TEMP_MONTHLY,
)
from src.data.skogsstyrelsen import PxWebClient  # noqa: E402
from src.data.smhi import SmhiClient, SmhiError, stations_covering  # noqa: E402

MANIFEST_PATH = RAW_DATA_DIR / "download_manifest.json"
# Väderfönstret: targeten börjar 2007M01; stationer ska mäta genom hela fönstret.
WEATHER_START = date(2007, 1, 1)
WEATHER_END = datetime.now(timezone.utc).date()
SMHI_PARAMS = {
    SMHI_PARAM_TEMP_MONTHLY: "monthly",
    SMHI_PARAM_PRECIP_MONTHLY: "monthly",
    SMHI_PARAM_SNOW_DAILY: "daily",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {"genererad": None, "miljo": _env_info(), "filer": {}}


def _env_info() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }


def save_manifest(manifest: dict) -> None:
    manifest["genererad"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest["miljo"] = _env_info()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def record_file(manifest: dict, path: Path, url: str, downloaded_at: str) -> None:
    manifest["filer"][str(path.relative_to(RAW_DATA_DIR))] = {
        "url": url,
        "hamtat": downloaded_at,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fetch_json_if_needed(
    manifest: dict, dest: Path, url: str, force: bool, fetch: callable
) -> bool:
    """Idempotent nedladdning; returnerar True om filen hämtades nu."""
    if dest.exists() and not force:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = fetch()
    dest.write_text(content, encoding="utf-8")
    record_file(manifest, dest, url, _now())
    print(f"  hämtad: {dest.relative_to(RAW_DATA_DIR.parent.parent)} "
          f"({dest.stat().st_size / 1024:.0f} kB)")
    return True


def download_felling(manifest: dict, force: bool) -> None:
    print("Skogsstyrelsen: avverkad volym/areal per landsdel (JO0312_06, 5-arsmedel)")
    client = PxWebClient()

    def fetch() -> str:
        payload, meta = client.fetch_whole_table(PXWEB_TABLE_FELLING)
        return json.dumps({"payload": payload, "metadata": meta}, ensure_ascii=False)

    url = client.table_url(PXWEB_TABLE_FELLING)
    _fetch_json_if_needed(
        manifest, RAW_DATA_DIR / "skogsstyrelsen" / "avverkad_volym_JO0312_06.json",
        url, force, fetch,
    )


def download_target(manifest: dict, force: bool) -> None:
    print("Skogsstyrelsen: targettabell 05 (hela tabellen via ASCII-work-around)")
    client = PxWebClient()

    def fetch() -> str:
        payload, meta = client.fetch_whole_table(PXWEB_TABLE_TARGET)
        return json.dumps({"payload": payload, "metadata": meta}, ensure_ascii=False)

    url = client.table_url(PXWEB_TABLE_TARGET)
    _fetch_json_if_needed(
        manifest, RAW_DATA_DIR / "skogsstyrelsen" / "avverkningsanmalan_tabell05.json",
        url, force, fetch,
    )


def download_prices(manifest: dict, force: bool) -> None:
    print("Skogsstyrelsen: avräkningspriser JO0303_3ny")
    client = PxWebClient()

    def fetch() -> str:
        payload, meta = client.fetch_whole_table(PXWEB_TABLE_PRICES)
        return json.dumps({"payload": payload, "metadata": meta}, ensure_ascii=False)

    url = client.table_url(PXWEB_TABLE_PRICES)
    _fetch_json_if_needed(
        manifest, RAW_DATA_DIR / "skogsstyrelsen" / "avrakningspriser_JO0303_3ny.json",
        url, force, fetch,
    )


def _download_station(smhi: SmhiClient, pid: int, sid: str, dest: Path) -> str:
    text = smhi.download_station_csv(pid, sid)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return sid


def download_weather(manifest: dict, force: bool, workers: int = 6) -> None:
    for pid, freq in SMHI_PARAMS.items():
        print(f"SMHI: parameter {pid} ({freq})")
        smhi = SmhiClient()
        meta = smhi.parameter_meta(pid)
        stations = stations_covering(meta, WEATHER_START, WEATHER_END)
        print(f"  {len(stations)} stationer täcker {WEATHER_START}–{WEATHER_END}")

        param_dir = RAW_DATA_DIR / "smhi" / f"param_{pid}"
        index = {
            "parameter": pid,
            "frekvens": freq,
            "fönster": [str(WEATHER_START), str(WEATHER_END)],
            "stationer": [
                {
                    "id": s["key"],
                    "namn": s["name"],
                    "lat": s.get("latitude"),
                    "lon": s.get("longitude"),
                    "from": s.get("from"),
                    "to": s.get("to"),
                    "aktiv": s.get("active"),
                }
                for s in stations
            ],
        }
        index_path = param_dir / "stationsindex.json"
        param_dir.mkdir(parents=True, exist_ok=True)
        if force or not index_path.exists():
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2))
            record_file(
                manifest, index_path,
                f"{smhi.base_url}/parameter/{pid}.json", _now(),
            )

        pending = []
        for s in stations:
            dest = param_dir / f"{s['key']}.csv"
            if dest.exists() and not force:
                continue
            pending.append((s["key"], dest))

        print(f"  {len(pending)} CSV-filer att hämta ({workers} trådar)")
        fel: list[str] = []
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_download_station, smhi, pid, sid, dest): sid
                for sid, dest in pending
            }
            for fut in as_completed(futures):
                sid = futures[fut]
                try:
                    fut.result()
                    record_file(
                        manifest, param_dir / f"{sid}.csv",
                        smhi.station_data_url(pid, sid), _now(),
                    )
                except Exception as exc:  # noqa: BLE001 - samla och rapportera i slutet
                    fel.append(f"{sid}: {exc}")
                done += 1
                if done % 50 == 0:
                    print(f"    {done}/{len(pending)}")
        if fel:
            print(f"  VARNING: {len(fel)} stationer misslyckades:")
            for line in fel[:10]:
                print(f"    {line}")
            raise SmhiError(f"{len(fel)} stationer misslyckades för parameter {pid}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["target", "prices", "weather", "felling"], default=None)
    parser.add_argument("--force", action="store_true", help="hämta om även befintliga filer")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)

    manifest = load_manifest()
    wanted = [args.only] if args.only else ["target", "prices", "weather", "felling"]

    if "target" in wanted:
        download_target(manifest, args.force)
    if "prices" in wanted:
        download_prices(manifest, args.force)
    if "felling" in wanted:
        download_felling(manifest, args.force)
    if "weather" in wanted:
        download_weather(manifest, args.force, workers=args.workers)

    save_manifest(manifest)
    n = len(manifest["filer"])
    print(f"\nKlar. Manifest: {MANIFEST_PATH} ({n} filer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
