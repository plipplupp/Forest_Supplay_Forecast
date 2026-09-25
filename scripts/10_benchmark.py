"""Fas 10 - Sammanställer full benchmark av alla modeller/experiment.

Kör:  python scripts/10_benchmark.py

Läser alla predictions-parquet, beräknar metrics (MAE/RMSE/MASE/sMAPE per
modell x region x horizon), aggregerar och skriver:
  outputs/results/metrics_per_region.csv       (detaljnivå)
  outputs/results/benchmark_hovedtabell.csv    (medel över serier per horizon)
  outputs/results/benchmark_slice_*.csv        (jämförbara universum A vs B)
  outputs/figures/fig_benchmark_mase.png
  docs/experiments_results.md                  (resultatrapport)
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import PREDICTIONS_DIR, PROJECT_ROOT, RESULTS_DIR  # noqa: E402
from src.evaluation.metrics import compute_metrics  # noqa: E402
from src.visualization.plots import COLORS, save_fig  # noqa: E402

MODEL_FILES = [
    "naive", "seasonal_naive", "xgb_base", "xgb_wx", "xgb_full",
    "timesfm_univ", "timesfm_multi_top", "timesfm_multi_lan",
    "timesfm_cal", "timesfm_wx", "timesfm_full",
]
PRETTY = {
    "naive": "Naive", "seasonal_naive": "Seasonal Naive",
    "xgb_base": "XGBoost (bas)", "xgb_wx": "XGBoost + väder", "xgb_full": "XGBoost + väder+pris",
    "timesfm_univ": "TimesFM A (univariat)", "timesfm_multi_top": "TimesFM B (multivariat topp)",
    "timesfm_multi_lan": "TimesFM B (multivariat län)", "timesfm_cal": "TimesFM C (+kalender)",
    "timesfm_wx": "TimesFM D (+väder)", "timesfm_full": "TimesFM E (+priser)",
}
LANDSDELAR = ("Norra Norrland", "Södra Norrland", "Svealand", "Götaland")


def load_all() -> pd.DataFrame:
    frames = []
    for f in MODEL_FILES:
        p = PREDICTIONS_DIR / f"{f}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    preds = load_all()
    print(f"{preds['model'].nunique()} modeller, {len(preds):,} prognosrader")

    metrics = compute_metrics(preds)
    metrics["modell"] = metrics["model"].map(PRETTY)
    metrics.to_csv(RESULTS_DIR / "metrics_per_region.csv", index=False)

    # Huvudtabell: modeller som täcker alla 26 serier
    models26 = ["naive", "seasonal_naive", "xgb_base", "xgb_wx", "xgb_full",
                "timesfm_univ", "timesfm_cal", "timesfm_wx", "timesfm_full"]
    main_m = metrics[metrics["model"].isin(models26)]
    hoved = (
        main_m.groupby(["modell", "horizon"])[["MAE", "RMSE", "MASE", "sMAPE"]]
        .mean().round(2).reset_index()
    )
    hoved.to_csv(RESULTS_DIR / "benchmark_hovedtabell.csv", index=False)

    # Jämförbara universum: toppserier (riket + landsdelar) och 21 län
    top_slice = metrics[metrics["region_name"].isin(("Hela landet",) + LANDSDELAR)
                        & metrics["model"].isin(models26 + ["timesfm_multi_top"])]
    (top_slice.groupby(["modell", "horizon"])[["MAE", "MASE", "sMAPE"]]
     .mean().round(2).reset_index()
     .to_csv(RESULTS_DIR / "benchmark_slice_top.csv", index=False))
    lan_slice = metrics[~metrics["region_name"].isin(("Hela landet",) + LANDSDELAR)
                        & metrics["model"].isin(models26 + ["timesfm_multi_lan"])]
    (lan_slice.groupby(["modell", "horizon"])[["MAE", "MASE", "sMAPE"]]
     .mean().round(2).reset_index()
     .to_csv(RESULTS_DIR / "benchmark_slice_lan.csv", index=False))

    # Per-origin variation för nyckelmodeller
    key = preds[preds["model"].isin(["naive", "seasonal_naive", "xgb_base", "timesfm_univ"])]
    key = key[key["region_name"] == "Hela landet"]
    per_origin = (
        key.assign(abs_err=(key["actual"] - key["prediction"]).abs())
        .groupby(["model", "horizon", "origin"])["abs_err"].sum().reset_index()
    )
    pov = (
        per_origin.groupby(["model", "horizon"])["abs_err"]
        .agg(["mean", "std", "max"]).round(1).reset_index()
    )
    pov.to_csv(RESULTS_DIR / "per_origin_variation_riker.csv", index=False)

    # Figur: MASE per modell x horizon
    fig, ax = plt.subplots(figsize=(9, 4))
    horizons = [1, 3, 6]
    models_plot = ["naive", "seasonal_naive", "xgb_base", "xgb_full",
                   "timesfm_univ", "timesfm_cal", "timesfm_wx", "timesfm_full"]
    colors_seq = plt.cm.Blues(np.linspace(0.35, 0.9, 5))
    color_map = {"naive": COLORS["neutral"], "seasonal_naive": "#B0B7BC",
                 "xgb_base": colors_seq[2], "xgb_full": colors_seq[4],
                 "timesfm_univ": COLORS["accent"], "timesfm_cal": "#D98B52",
                 "timesfm_wx": "#E3A876", "timesfm_full": "#EBC29E"}
    width = 0.11
    x = np.arange(len(horizons))
    for j, mdl in enumerate(models_plot):
        vals = [main_m[(main_m["model"] == mdl) & (main_m["horizon"] == h)]["MASE"].mean()
                for h in horizons]
        ax.bar(x + (j - len(models_plot) / 2) * width, vals, width,
               label=PRETTY[mdl], color=color_map[mdl])
    ax.set_xticks(x, ["1 månad", "3 månader", "6 månader"])
    ax.set_ylabel("MASE (lägre = bättre)")
    ax.set_title("Benchmark: MASE per modell och horizon (medel över 26 serier)")
    ax.legend(frameon=False, fontsize=7, ncols=3, loc="upper left")
    save_fig(fig, "fig_benchmark_mase.png")

    # Resultatrapport
    best = hoved.loc[hoved.groupby("horizon")["MASE"].idxmin()]
    lines = ["# Benchmark-resultat (fas 10)",
             "",
             "*Auto-genererad av scripts/10_benchmark.py. MASE = medel över 26 serier "
             "(lägre = bättre; 1.0 = i nivå med säsongs-naiv skalning).*",
             "",
             "## Huvudtabell (MASE per horizon)",
             "",
             hoved.pivot(index="modell", columns="horizon", values="MASE")
             .reindex(columns=[1, 3, 6]).to_markdown(),
             "",
             "**Bäst per horizon:** "
             + ", ".join(f"h={int(r.horizon)}: {r.modell} (MASE {r.MASE:.2f})"
                          for r in best.itertuples()),
             "",
             "Se outputs/results/ för detaljer: metrics_per_region.csv, "
             "benchmark_slice_top.csv (riket+landsdelar), benchmark_slice_lan.csv (21 län), "
             "per_origin_variation_riker.csv.",
             "",
             "![Benchmark](../outputs/figures/fig_benchmark_mase.png)",
             "",
             "## Marginalnytta av covariater (TimesFM-familjen, MASE)",
             "",
             main_m[main_m["model"].str.startswith("timesfm") & (main_m["model"] != "timesfm_multi_lan")]
             .groupby(["modell", "horizon"])["MASE"].mean().unstack()
             .reindex(columns=[1, 3, 6]).round(3).to_markdown(),
             "",
             "## XGBoost-familjen (MASE)",
             "",
             main_m[main_m["model"].str.startswith("xgb")]
             .groupby(["modell", "horizon"])["MASE"].mean().unstack()
             .reindex(columns=[1, 3, 6]).round(3).to_markdown(),
             "",
             "## A vs B - hjälper multivariat information?",
             "",
             "På toppserierna (riket + 4 landsdelar), MASE:",
             "",
             top_slice.groupby(["modell", "horizon"])["MASE"].mean().unstack()
             .reindex(columns=[1, 3, 6]).round(3).to_markdown(),
             "",
             "På 21 län, MASE:",
             "",
             lan_slice.groupby(["modell", "horizon"])["MASE"].mean().unstack()
             .reindex(columns=[1, 3, 6]).round(3).to_markdown(),
             "",
             "## Per-origin-variation (riket, summa abs. fel per origin)",
             "",
             "Visar prognosfördelningens bakkant - vissa origins är systematiskt svåra:",
             "",
             pov.to_markdown(index=False),
             "",
         ]
    (PROJECT_ROOT / "docs" / "experiments_results.md").write_text("\n".join(lines))
    print("\nHuvudtabell (MASE):")
    print(hoved.pivot(index="modell", columns="horizon", values="MASE")
          .reindex(columns=[1, 3, 6]).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
