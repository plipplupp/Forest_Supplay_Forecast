"""Fas 11 - Error analysis: när lyckas/misslyckas modellerna?

Kör:  python scripts/11_error_analysis.py

Frågor (spec §16-17): säsongsbias, värsta origins, över/underprognoser,
regioner med dålig precision, konkreta exempel där respektive modell vinner.
Skriver outputs/figures/fig_error_*.png och docs/error_analysis.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import PREDICTIONS_DIR, PROJECT_ROOT  # noqa: E402
from src.data.datasets import load_target_wide  # noqa: E402
from src.visualization.plots import COLORS, save_fig  # noqa: E402

KEY_MODELS = ["naive", "seasonal_naive", "xgb_base", "timesfm_univ"]
PRETTY = {"naive": "Naive", "seasonal_naive": "Seasonal Naive",
          "xgb_base": "XGBoost", "timesfm_univ": "TimesFM"}
LAN_SLICE = ("Hela landet", "Norra Norrland", "Södra Norrland", "Svealand", "Götaland")


def load() -> pd.DataFrame:
    frames = [pd.read_parquet(PREDICTIONS_DIR / f"{m}.parquet") for m in KEY_MODELS]
    df = pd.concat(frames, ignore_index=True)
    df["abs_err"] = (df["actual"] - df["prediction"]).abs()
    df["signed_err"] = df["prediction"] - df["actual"]
    df["month"] = pd.to_datetime(df["timestamp"]).dt.month
    return df


def error_by_season(df: pd.DataFrame) -> None:
    nat = df[df["region_name"] == "Hela landet"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
    for ax, h in zip(axes, (1, 3, 6)):
        sub = nat[nat["horizon"] == h]
        for mdl in KEY_MODELS:
            g = sub[sub["model"] == mdl].groupby("month")["signed_err"].mean()
            ax.plot(g.index, g.values, marker="o", ms=3,
                    color={"naive": COLORS["neutral"], "seasonal_naive": "#B0B7BC",
                           "xgb_base": COLORS["main"], "timesfm_univ": COLORS["accent"]}[mdl],
                    lw=1.4, label=PRETTY[mdl])
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title(f"h = {h} mån")
        ax.set_xticks(range(1, 13), ["j", "f", "m", "a", "m", "j", "j", "a", "s", "o", "n", "d"])
    axes[0].set_ylabel("Medel signerat fel (prognos − utfall), ha")
    axes[0].legend(frameon=False, fontsize=7.5)
    fig.suptitle("Säsongsbias, Hela landet: över- (>0) / underprognos (<0) per prognosmånad")
    save_fig(fig, "fig_error_seasonal_bias.png")

    lines = ["### Säsongsbias (Hela landet)", ""]
    for mdl in KEY_MODELS:
        sub = nat[(nat["model"] == mdl) & (nat["horizon"] == 3)]
        worst = sub.groupby("month")["signed_err"].mean().abs().idxmax()
        bias = sub["signed_err"].mean()
        lines.append(f"- **{PRETTY[mdl]}**: total bias {bias:+,.0f} ha/mån; störst säsongsbias "
                     f"i månad {int(worst)} ({sub[sub['month']==worst]['signed_err'].mean():+,.0f} ha).")
    lines += ["",
              "Mönstret: fel koncentreras till övergångsmånaderna (framför allt sommaren "
              "augusti-september när anmälan rusar) - modeller som hänger med i nivåskift "
              "men missar säsongens *timing* tar stryk där.",
              ""]
    return lines


def worst_origins(df: pd.DataFrame) -> list[str]:
    nat = df[(df["region_name"] == "Hela landet") & (df["horizon"] == 3)]
    piv = nat.pivot_table(index="origin", columns="model", values="abs_err", aggfunc="mean")
    piv["timesfm_rank"] = piv["timesfm_univ"].rank()
    hard = piv.sort_values("timesfm_univ", ascending=False).head(5)
    lines = ["### Svåraste origins (h=3, Hela landet)", ""]
    for origin, row in hard.iterrows():
        lines.append(f"- **{pd.Timestamp(origin):%Y-%m}**: TimesFM MAE {row['timesfm_univ']:,.0f} ha, "
                     f"SNaive {row['seasonal_naive']:,.0f}, XGB {row['xgb_base']:,.0f} - "
                     f"prognosmånaderna {pd.Timestamp(origin) + pd.offsets.MonthBegin(1):%Y-%m}–"
                     f"{pd.Timestamp(origin) + pd.offsets.MonthBegin(3):%Y-%m}.")
    lines += ["", "![Värsta origins](../outputs/figures/fig_error_worst_origins.png)", ""]

    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.bar(pd.to_datetime(piv.index).strftime("%Y-%m"), piv["timesfm_univ"],
           color=COLORS["accent"], alpha=0.85, label="TimesFM")
    ax.plot(pd.to_datetime(piv.index).strftime("%Y-%m"), piv["seasonal_naive"],
            color=COLORS["neutral"], marker="o", ms=3, lw=1.2, label="Seasonal Naive")
    ax.set_ylabel("MAE (ha)")
    ax.set_title("MAE per forecasting origin (Hela landet, h=3)")
    ax.tick_params(axis="x", rotation=60, labelsize=6.5)
    ax.legend(frameon=False)
    save_fig(fig, "fig_error_worst_origins.png")
    return lines


def who_wins_where(df: pd.DataFrame) -> list[str]:
    # vinstmatris per region x horizon (h=3)
    sub = df[df["horizon"] == 3]
    agg = sub.groupby(["region_name", "model"])["abs_err"].mean().unstack()
    winners = agg.idxmin(axis=1).value_counts()
    lines = ["### Vem vinner var (h = 3)?", ""]
    for mdl, n in winners.items():
        lines.append(f"- {PRETTY.get(mdl, mdl)}: bäst i {n} av {len(agg)} serier.")
    worst_timesfm = agg["timesfm_univ"].sort_values(ascending=False).head(3)
    lines.append("")
    lines.append("Svåraste serier för TimesFM (h=3): "
                 + ", ".join(f"{r} (MAE {v:,.0f})" for r, v in worst_timesfm.items())
                 + " - volatila småserier och övergångsregioner.")
    lines.append("")
    return lines


def example_cases(df: pd.DataFrame, wide: pd.DataFrame) -> list[str]:
    """Tre konkreta fall: TimesFM vinner, XGB vinner, SNaive vinner."""
    h3 = df[df["horizon"] == 3]
    piv = h3.pivot_table(index=["region_name", "origin"], columns="model",
                         values="abs_err", aggfunc="sum")
    cases = {
        "TimesFM klart bättre": (piv["timesfm_univ"] - piv["xgb_base"]).idxmax(),
        "XGBoost klart bättre": (piv["xgb_base"] - piv["timesfm_univ"]).idxmax(),
        "Seasonal Naive bäst": (piv["seasonal_naive"] - piv["timesfm_univ"]).min(),  # noqa
    }
    # korrigera tredje fallet: hitta origin där snaive slår båda modellerna mest
    d = piv["seasonal_naive"] - piv[["xgb_base", "timesfm_univ"]].min(axis=1)
    cases["Seasonal Naive bäst"] = d.idxmin()

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
    lines = ["### Tre konkreta fall (h = 3, prognoser mot utfall)", ""]
    for ax, (title, (region, origin)) in zip(axes, cases.items()):
        origin = pd.Timestamp(origin)
        t_pos = int((wide.index <= origin).sum())
        hist = wide[region].iloc[max(0, t_pos - 24): t_pos]
        model_row = h3[(h3["region_name"] == region) & (h3["origin"] == origin)]
        ax.plot(hist.index, hist.values, color=COLORS["main"], lw=1.2, label="historik")
        actual = wide[region].iloc[t_pos: t_pos + 3]
        ax.plot(actual.index, actual.values, color="black", lw=1.8, label="utfall")
        for mdl, color, ls in (("timesfm_univ", COLORS["accent"], "-"),
                               ("xgb_base", "#7FB3C8", "--"),
                               ("seasonal_naive", COLORS["neutral"], ":")):
            r = model_row[model_row["model"] == mdl].sort_values("timestamp")
            if len(r):
                # linje från sista historikpunkten till prognospunkten + markör,
                # annars ritar matplotlib ingenting för en ensam punkt
                xs = [hist.index[-1], *pd.to_datetime(r["timestamp"])]
                ys = [hist.values[-1], *r["prediction"].values]
                ax.plot(xs, ys, color=color, ls=ls, lw=1.8, marker="o", ms=3.5,
                        label=PRETTY.get(mdl, mdl))
        # zooma in sista året + prognosperioden så att prognoslinjerna syns tydligt
        ax.set_xlim(hist.index[-12], pd.Timestamp(origin) + pd.DateOffset(months=3))
        ax.set_title(f"{title}\n{region}, origin {origin:%Y-%m}", fontsize=8.5)
        ax.set_ylabel("ha/månad")
        ax.tick_params(axis="x", rotation=45, labelsize=6.5)
        ax.legend(frameon=False, fontsize=6.5)
        errs = model_row.groupby("model")["abs_err"].sum().sort_values()
        lines.append(f"- **{title}** ({region}, origin {origin:%Y-%m}): "
                     + ", ".join(f"{PRETTY.get(m, m)} MAE {v:,.0f}" for m, v in errs.items()))
    fig.suptitle("Konkreta prognosfall: historik (blå), utfall (svart), prognoser", y=1.02)
    save_fig(fig, "fig_error_examples.png")
    lines += ["", "![Konkreta fall](../outputs/figures/fig_error_examples.png)", ""]
    return lines


def uncertainty(df_timesfm: pd.DataFrame) -> list[str]:
    sub = df_timesfm[(df_timesfm["region_name"] == "Hela landet")].copy()
    sub["in_interval"] = ((sub["actual"] >= sub[["p10", "p50"]].min(axis=1)) &
                          (sub["actual"] <= sub[["p90", "p50"]].max(axis=1)))
    cov = sub.groupby("horizon")["in_interval"].mean()
    width = sub.groupby("horizon").apply(
        lambda g: (g["p90"] - g["p10"]).mean(), include_groups=False)
    lines = ["### Prognosintervall (P10–P90, Hela landet)", ""]
    for h in cov.index:
        lines.append(f"- h={int(h)}: {cov[h]:.0%} av utfallen inom intervallet "
                     f"(medelbredd {width[h]:,.0f} ha). Nominal 80% - täckningen "
                     f"{'är' if cov[h] >= 0.78 else 'avviker från'} rimlig.")
    lines.append("")
    lines.append("Intervallen är prognosfördelningar, inte garantier - och kalibreringen "
                 "kan skifta över tid (kolla per origin innan beslut).")
    lines.append("")
    return lines


def main() -> int:
    df = load()
    wide = load_target_wide()
    lines = ["# Error analysis (fas 11)",
             "", "*Auto-genererad av scripts/11_error_analysis.py.*", ""]

    lines += error_by_season(df)
    lines += worst_origins(df)
    lines += who_wins_where(df)
    lines += example_cases(df, wide)
    lines += uncertainty(pd.read_parquet(PREDICTIONS_DIR / "timesfm_univ.parquet"))

    out = PROJECT_ROOT / "docs" / "error_analysis.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines[:24]))
    print(f"\nFull analys: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
