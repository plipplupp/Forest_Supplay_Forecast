"""Fas 3 - Exploratory Data Analysis av target, regioner, väder och priser.

Kör:  python scripts/03_eda.py

Genererar figurer till outputs/figures/ och en samlad analys i
docs/eda_findings.md. All EDA bygger på processed-parquet via loaders.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

from src.config import PROJECT_ROOT  # noqa: E402
from src.data.datasets import (  # noqa: E402
    load_prices,
    load_target,
    load_weather_national,
)
from src.visualization.plots import COLORS, save_fig  # noqa: E402

FINDINGS: list[str] = []


def section(title: str) -> None:
    FINDINGS.append(f"\n## {title}\n")


def note(text: str) -> None:
    FINDINGS.append(text)
    print(text)


def pivot_target(target: pd.DataFrame) -> pd.DataFrame:
    """Wide-matrix: index = månadsdatum, kolumner = region_name."""
    return target.pivot(index="date", columns="region_name", values="areal_ha")


# ------------------------------------------------------------------ target
def eda_target(target: pd.DataFrame, wide: pd.DataFrame) -> None:
    section("Target: anmäld avverkningsareal (Hela landet)")
    nat = wide["Hela landet"].dropna()
    obs = nat.index

    note(f"- Observationer: {len(nat)} månader ({obs.min():%Y-%m}–{obs.max():%Y-%m}).")
    annual = nat.resample("YS").sum()
    complete = nat.resample("YS").size() == 12
    annual = annual[complete]
    note(f"- Årlig nivå (hela år 2007–2025): median {annual.median():,.0f} ha/år; "
         f"variationsbredd {annual.min():,.0f}–{annual.max():,.0f} ha. (2026 är ofullständigt.)")
    trend = np.polyfit(np.arange(len(nat)), nat.values, 1)[0]
    note(f"- Linjär trend: {trend:+,.0f} ha/månad ({trend*12:+,.0f} ha/år).")

    # Missing
    interior_nan = int(wide.loc[obs].isna().sum().sum())
    trailing = wide.index.max() - obs.max()
    note(f"- Saknade värden: {interior_nan} interiära NaN i hela matrisen; "
         f"sista observerade månad {obs.max():%Y-%m} (tabellen innehåller framtidsrader med NaN).")

    # Säsong
    by_month = nat.groupby(nat.index.month).mean()
    strength_note = ""
    try:
        stl = STL(nat, period=12, robust=True).fit()
        seas_strength = max(0.0, 1 - np.var(stl.resid) / np.var(stl.trend + stl.resid))
        strength_note = f"; STL-säsongstyrka {seas_strength:.2f}"
        fig, axes = plt.subplots(4, 1, figsize=(8, 7), sharex=True)
        stl.observed.plot(ax=axes[0], color=COLORS["main"])
        axes[0].set_ylabel("observerad (ha/månad)")
        stl.trend.plot(ax=axes[1], color=COLORS["main"])
        axes[1].set_ylabel("trend (ha/månad)")
        stl.seasonal.plot(ax=axes[2], color=COLORS["neutral"])
        axes[2].set_ylabel("säsong (ha/månad)")
        stl.resid.plot(ax=axes[3], color=COLORS["accent"], lw=0.7)
        axes[3].set_ylabel("rest (ha/månad)")
        fig.suptitle("STL-dekomposition: anmäld areal, Hela landet (ha/månad)", y=1.0)
        save_fig(fig, "fig_stl_national.png")
    except Exception as exc:  # noqa: BLE001
        strength_note = f" (STL misslyckades: {exc})"

    month_names = {1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "maj", 6: "jun",
                   7: "jul", 8: "aug", 9: "sep", 10: "okt", 11: "nov", 12: "dec"}
    ranked = by_month.sort_values(ascending=False)
    tops = ", ".join(f"{month_names[m]} ({v:,.0f})" for m, v in ranked.head(3).items())
    bottoms = ", ".join(f"{month_names[m]} ({v:,.0f})" for m, v in ranked.tail(3).items())
    note(f"- Tydlig årscykel: topp {tops} ha/mån - anmälan görs typiskt inför höst-/vinteravverkning; "
         f"lägst {bottoms} ha/mån. Topplistor ändrar narrativet 'vår är högsäsong': i anmälardata "
         f"är hösten högsäsong{strength_note}.")

    # Figurer
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(nat.index, nat.values, color=COLORS["main"], lw=0.9, label="månadsareal")
    roll_mean = nat.rolling(12).mean()
    roll_std = nat.rolling(12).std()
    ax.plot(roll_mean.index, roll_mean.values, color=COLORS["accent"], lw=1.6, label="12-mån rullande medel")
    ax.fill_between(
        roll_mean.index, (roll_mean - roll_std).values, (roll_mean + roll_std).values,
        color=COLORS["accent"], alpha=0.15, label="±1 std",
    )
    ax.set_title("Anmäld avverkningsareal per månad, Hela landet")
    ax.set_ylabel("ha/månad")
    ax.legend(loc="upper right", frameon=False)
    save_fig(fig, "fig_target_national.png")

    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    data = [nat[nat.index.month == m].values for m in range(1, 13)]
    bp = ax.boxplot(data, tick_labels=["jan", "feb", "mar", "apr", "maj", "jun",
                                       "jul", "aug", "sep", "okt", "nov", "dec"],
                    patch_artist=True)
    for box in bp["boxes"]:
        box.set(facecolor=COLORS["main"], alpha=0.55, edgecolor=COLORS["main"])
    ax.set_title("Säsongsmönster: månadsareal per månad i året, 2007–2026")
    ax.set_ylabel("ha/månad")
    save_fig(fig, "fig_seasonality.png")

    # Anomalier: avvikelse från 12-mån rullande median, skalenlig via MAD av resid
    med12 = nat.rolling(12, center=True, min_periods=6).median()
    resid = nat - med12
    mad = (resid - resid.median()).abs().median()
    z = (resid - resid.median()).abs() / (1.4826 * mad)
    anomalies = z[z > 2.5].sort_values(ascending=False)
    note(f"- Extrema observationer (|avvikelse| > 2,5 MAD från rullande median): {len(anomalies)} st.")
    for ts in anomalies.index[:8]:
        direction = "över" if resid[ts] > 0 else "under"
        note(f"  - {ts:%Y-%m}: {nat[ts]:,.0f} ha ({direction} medianen, z={z[ts]:.1f})")
    if len(anomalies) == 0:
        note("  (Ingen månad överskrider tröskeln - landsserien är förvånansvänt jämn.)")
    note("  Tolkning: nationell nivå drivs av säsongsrytm och skadeår snarare än punktanomalier. "
         "Inga värden tas bort - de är verkliga fenomen och ingår i backtestingen.")

    # Datagap och småregions-spikar
    gap_months = wide.loc[obs].isna().stack()
    gaps = gap_months[gap_months]
    if len(gaps):
        by_region = gaps.reset_index().groupby("region_name")["date"].apply(list)
        for region, months in by_region.items():
            first, last = months[0], months[-1]
            note(f"- Datagap: {region} saknar {len(months)} månader ({first:%Y-%m}–{last:%Y-%m}). "
                 "Hanteras som 0 ha i modellmatrisen (liten region, inga anmälningar är plausibelt) "
                 "och dokumenteras i limitations.")

    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(nat.index, nat.values, color=COLORS["main"], lw=0.9)
    ax.plot(med12.index, med12.values, color=COLORS["neutral"], lw=1.2, ls="--", label="12-mån median")
    ax.scatter(anomalies.index, nat[anomalies.index], color=COLORS["bad"], zorder=5, s=22,
               label="anomali (z>3)")
    ax.set_title("Extrema observationer relativt 12-mån rullande median (Hela landet)")
    ax.set_ylabel("ha/månad")
    ax.legend(loc="upper right", frameon=False)
    save_fig(fig, "fig_anomalies.png")


# ------------------------------------------------------------------ regioner
def eda_regions(target: pd.DataFrame, wide: pd.DataFrame) -> None:
    section("Regional variation")
    lan = target[target["region_type"] == "län"]
    tot = lan.groupby("region_name")["areal_ha"].sum().sort_values(ascending=False)
    cv = (lan.groupby("region_name")["areal_ha"].std()
          / lan.groupby("region_name")["areal_ha"].mean()).sort_values()
    note(f"- Störst volym: {', '.join(f'{n} ({v:,.0f} ha totalt)' for n, v in tot.head(3).items())}.")
    note(f"- Störst volym andel av landet: {tot.head(3).sum() / tot.sum():.0%} kommer från topp-3 län.")
    note(f"- Mest stabila (lägsta CV): {', '.join(f'{n} ({v:.2f})' for n, v in cv.head(3).items())}; "
         f"mest volatila: {', '.join(f'{n} ({v:.2f})' for n, v in cv.tail(3).items())}. "
         "Hög CV i små län drivs av enstaka stora avverkningar (t.ex. Västmanland: median 366 ha/mån "
         "men max 5 626) - sannolikt enskilda stora markägare/avverkningsuppdrag.")

    lan_wide = wide[[c for c in wide.columns
                     if c != "Hela landet" and c not in
                     ("Norra Norrland", "Södra Norrland", "Svealand", "Götaland")]]
    corr = lan_wide.corr()
    off_diag = corr.where(~np.eye(len(corr), dtype=bool))
    note(f"- Korrelation mellan råa länserier: median {off_diag.stack().median():.2f} - "
         "mätt men dämpat av lokalt brus; gemensam säsong är den dominerande gemensamma faktorn. "
         "Multivariat experiment B testar om TimesFM utnyttjar korsserie-information bättre än "
         "univariat prognos.")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    tot.plot(kind="barh", ax=axes[0], color=COLORS["main"])
    axes[0].invert_yaxis()
    axes[0].set_title("Total anmäld areal per län, 2007–2026")
    axes[0].set_xlabel("ha (summa över perioden)")
    cv.sort_values().plot(kind="barh", ax=axes[1], color=COLORS["accent"])
    axes[1].set_title("Variationskoefficient per län")
    axes[1].set_xlabel("std / medel (enhetslöst)")
    save_fig(fig, "fig_regional_profile.png")

    fig, ax = plt.subplots(figsize=(7.2, 6))
    im = ax.imshow(corr.values, vmin=0.4, vmax=1, cmap="Blues")
    ax.set_xticks(range(len(corr)), corr.columns, rotation=90, fontsize=6.5)
    ax.set_yticks(range(len(corr)), corr.index, fontsize=6.5)
    fig.colorbar(im, shrink=0.8)
    ax.set_title("Korrelation mellan läners månadserier")
    ax.grid(False)
    save_fig(fig, "fig_region_correlation.png")

    # Landsdelarnas andel över tid
    ld = target[target["region_type"] == "landsdel"].pivot(
        index="date", columns="region_name", values="areal_ha")
    share = ld.div(ld.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.stackplot(share.index, [share[c].values for c in share.columns], labels=share.columns,
                 colors=["#2C6E8F", "#7FB3C8", "#C46A2B", "#E3B58C"], alpha=0.9)
    ax.set_title("Landsdelarnas andel av anmäld areal över tid")
    ax.set_ylabel("andel")
    ax.set_ylim(0, 1)
    ax.legend(loc="lower left", frameon=False, ncols=4, fontsize=8)
    ax.margins(x=0)
    save_fig(fig, "fig_landsdel_shares.png")


# ------------------------------------------------------------------ väder & priser
def eda_weather_prices(wx: pd.DataFrame, prices: pd.DataFrame) -> None:
    section("Väder (nationellt) och virkespriser")
    wx = wx[wx["date"] >= "2006-01-01"]
    fig, axes = plt.subplots(3, 1, figsize=(9, 6), sharex=True)
    axes[0].plot(wx["date"], wx["temp_mean_c"], color=COLORS["main"], lw=0.8)
    axes[0].set_ylabel("temp (°C)")
    axes[1].plot(wx["date"], wx["precip_sum_mm"], color=COLORS["neutral"], lw=0.8)
    axes[1].set_ylabel("nederbörd (mm/mån)")
    axes[2].plot(wx["date"], wx["snow_mean_m"], color=COLORS["accent"], lw=0.8)
    axes[2].set_ylabel("snödjup (m)")
    axes[2].axvline(pd.Timestamp("2007-01-01"), color=COLORS["bad"], ls=":", lw=1)
    fig.suptitle("Nationellt väder (medel över stationer) - prognosfönstret börjar 2007")
    save_fig(fig, "fig_weather_national.png")
    n2007 = wx[wx["date"] >= "2007-01-01"]
    note(f"- Stationstäckning 2007–: median {n2007['n_temp_stations'].median():.0f} temp-, "
         f"{n2007['n_precip_stations'].median():.0f} nederbörds- och "
         f"{n2007['n_snow_stations'].median():.0f} snöststationer per månad.")

    hl = prices[prices["landsdel"] == "Hela landet"].copy()
    hl["qdate"] = pd.to_datetime(
        dict(year=hl["ar"], month=hl["kvartal"] * 3 - 2, day=1)
    ).dt.to_period("Q").dt.to_timestamp()
    piv = hl.pivot(index="qdate", columns="sortiment", values="avrakningspris_kr_m3fub")
    fig, ax = plt.subplots(figsize=(8, 3.4))
    for col in ["Tallsågtimmer", "Gransågtimmer", "Massaved av barrträd", "Massaved av lövträd"]:
        ax.plot(piv.index, piv[col], lw=1.4, label=col)
    ax.axvline(pd.Timestamp("2025-04-01"), color=COLORS["bad"], ls=":", lw=1)
    ax.text(pd.Timestamp("2025-07-01"), ax.get_ylim()[0] + 40, "ny metod 2025K2",
            color=COLORS["bad"], fontsize=7)
    ax.set_title("Avräkningspriser, Hela landet (kvartal)")
    ax.set_ylabel("kr/m³fub")
    ax.legend(frameon=False, fontsize=7.5, ncols=2)
    save_fig(fig, "fig_prices_quarterly.png")
    note("- Prisserierna är kvartalsvisa med metodbryt 2025K2; används endast som "
         "senast-kända värden vid forecast-origin (experiment E).")


def main() -> int:
    target = load_target()
    wide = pivot_target(target)
    wx = load_weather_national()
    prices = load_prices()

    FINDINGS.append("# EDA-fynd (fas 3)\n\n*Auto-genererad av scripts/03_eda.py - "
                    "figurer i outputs/figures/.*")

    eda_target(target, wide)
    eda_regions(target, wide)
    eda_weather_prices(wx, prices)

    out = PROJECT_ROOT / "docs" / "eda_findings.md"
    out.write_text("\n".join(FINDINGS) + "\n")
    print(f"\nFynd skrivna till {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
