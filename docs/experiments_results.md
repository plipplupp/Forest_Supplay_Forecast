# Benchmark-resultat (fas 10)

*Auto-genererad av scripts/10_benchmark.py. MASE = medel över 26 serier (lägre = bättre; 1.0 = i nivå med säsongs-naiv skalning).*

## Huvudtabell (MASE per horizon)

| modell                |    1 |    3 |    6 |
|:----------------------|-----:|-----:|-----:|
| Naive                 | 0.84 | 1.1  | 1.21 |
| Seasonal Naive        | 0.91 | 0.93 | 0.93 |
| TimesFM A (univariat) | 0.63 | 0.77 | 0.82 |
| TimesFM C (+kalender) | 0.62 | 0.76 | 0.81 |
| TimesFM D (+väder)    | 0.64 | 0.77 | 0.82 |
| TimesFM E (+priser)   | 0.64 | 0.77 | 0.82 |
| XGBoost (bas)         | 0.75 | 0.92 | 0.95 |
| XGBoost + väder       | 0.76 | 0.92 | 0.95 |
| XGBoost + väder+pris  | 0.75 | 0.89 | 0.92 |

**Bäst per horizon:** h=1: TimesFM C (+kalender) (MASE 0.62), h=3: TimesFM C (+kalender) (MASE 0.76), h=6: TimesFM C (+kalender) (MASE 0.81)

Se outputs/results/ för detaljer: metrics_per_region.csv, benchmark_slice_top.csv (riket+landsdelar), benchmark_slice_lan.csv (21 län), per_origin_variation_riker.csv.

![Benchmark](../outputs/figures/fig_benchmark_mase.png)

## Marginalnytta av covariater (TimesFM-familjen, MASE)

| modell                |     1 |     3 |     6 |
|:----------------------|------:|------:|------:|
| TimesFM A (univariat) | 0.632 | 0.767 | 0.816 |
| TimesFM C (+kalender) | 0.624 | 0.764 | 0.814 |
| TimesFM D (+väder)    | 0.636 | 0.77  | 0.819 |
| TimesFM E (+priser)   | 0.639 | 0.771 | 0.823 |

## XGBoost-familjen (MASE)

| modell               |     1 |     3 |     6 |
|:---------------------|------:|------:|------:|
| XGBoost (bas)        | 0.754 | 0.922 | 0.954 |
| XGBoost + väder      | 0.761 | 0.916 | 0.954 |
| XGBoost + väder+pris | 0.751 | 0.89  | 0.917 |

## A vs B - hjälper multivariat information?

På toppserierna (riket + 4 landsdelar), MASE:

| modell                       |     1 |     3 |     6 |
|:-----------------------------|------:|------:|------:|
| Naive                        | 0.981 | 1.281 | 1.462 |
| Seasonal Naive               | 0.876 | 0.892 | 0.898 |
| TimesFM A (univariat)        | 0.658 | 0.883 | 0.911 |
| TimesFM B (multivariat topp) | 0.643 | 0.877 | 0.907 |
| TimesFM C (+kalender)        | 0.65  | 0.888 | 0.922 |
| TimesFM D (+väder)           | 0.666 | 0.899 | 0.925 |
| TimesFM E (+priser)          | 0.672 | 0.905 | 0.927 |
| XGBoost (bas)                | 0.775 | 1.021 | 1.008 |
| XGBoost + väder              | 0.814 | 0.997 | 0.991 |
| XGBoost + väder+pris         | 0.797 | 0.976 | 0.971 |

På 21 län, MASE:

| modell                      |     1 |     3 |     6 |
|:----------------------------|------:|------:|------:|
| Naive                       | 0.811 | 1.062 | 1.144 |
| Seasonal Naive              | 0.92  | 0.935 | 0.941 |
| TimesFM A (univariat)       | 0.626 | 0.739 | 0.793 |
| TimesFM B (multivariat län) | 0.613 | 0.722 | 0.774 |
| TimesFM C (+kalender)       | 0.617 | 0.735 | 0.789 |
| TimesFM D (+väder)          | 0.629 | 0.739 | 0.794 |
| TimesFM E (+priser)         | 0.631 | 0.74  | 0.798 |
| XGBoost (bas)               | 0.749 | 0.899 | 0.941 |
| XGBoost + väder             | 0.748 | 0.896 | 0.946 |
| XGBoost + väder+pris        | 0.74  | 0.87  | 0.904 |

## Per-origin-variation (riket, summa abs. fel per origin)

Visar prognosfördelningens bakkant - vissa origins är systematiskt svåra:

| model          |   horizon |   mean |    std |     max |
|:---------------|----------:|-------:|-------:|--------:|
| naive          |         1 | 3913.6 | 2720.9 |  9923   |
| naive          |         3 | 4580.3 | 3569.2 | 12724   |
| naive          |         6 | 5490.8 | 3635.5 | 14944   |
| seasonal_naive |         1 | 3041.4 | 2173.3 |  7218   |
| seasonal_naive |         3 | 3095   | 2202.3 |  7218   |
| seasonal_naive |         6 | 3084.8 | 2221.3 |  7218   |
| timesfm_univ   |         1 | 2383.4 | 2033.9 |  9794.4 |
| timesfm_univ   |         3 | 3456.6 | 2089.6 |  8550.5 |
| timesfm_univ   |         6 | 3494.7 | 2065.1 |  7475   |
| xgb_base       |         1 | 2782.6 | 2188.8 |  7812.4 |
| xgb_base       |         3 | 4439.9 | 2939.7 | 10583.1 |
| xgb_base       |         6 | 3911.3 | 2681.4 |  9507.7 |
