# Metodik

## Forecasting-problemet

- **Target:** anmäld avverkningsareal (hektar/månad) per region — Skogsstyrelsen
  tabell 05 (avverkningsanmälan + ansökan om tillstånd). Det är en **proxy** för
  faktisk avverkning; terminologin i hela projektet speglar det.
- **Serier:** 26 månadsserier 2007M01– senaste observerade månad (dynamiskt):
  Hela landet, 4 landsdelar, 21 län.
  - Gotlands datagap 2010M03–2010M07 fylls med 0 ha i modellmatrisen
    (liten region; inga anmälningar plausibelt) — dokumenteras i limitations.
- **Geografisk prioritet:** landsdel + Hela landet är huvudnivå (pris-kompatibel,
  robust); 21 län ingår i multivariat experiment B och i per-region-rapportering.

## Horizons och evaluation-design

- **Horizons:** 1, 3 och 6 månader. 6 mån valdes som max eftersom avverkningsplanering
  (inköp, kapacitet) typiskt rör sig i halvårs perspektiv; längre horizons ger
  väsentligt färre utvärderbara origins och ökande säsongsförväxling.
- **Rolling-origin backtesting:** ett origin per månad, var 12:e månad från
  2022M09 (start testfönstret) fram till senaste observerade månaden. Vid varje
  origin prognostiserar modellen 6 månader (h = 1, 3, 6 läses ur samma prognos).
  h = 6 utvärderas bara där verkliga utfall finns (origin ≤ senaste månad − 6).
  Det ger ~60 origins × 26 serier ≈ 1 560 prognoser per modell och horizonskiva.
- **Context:** hela historiken fram till origin (~190–240 månader) — inget
  rullande fönster klipper bort tidiga regimer.
- **MASE-skalning:** per (serie, origin) beräknad som mean|y_t − y_{t−12}| på
  endast träningsdelen (historiken fram till origin); skalfaktorn sparas i
  predictions-filen så alla metrics kan återskapas i efterhand.

## Leakage-regler (hårda)

1. Ingen observation efter origin får användas av någon modell eller feature.
2. Observerat väder för framtiden används aldrig — endast väder ≤ origin.
3. Priser: senaste kvartalet vars slut är ≥ 2 månader före origin (publiceringsfördröjning
   är konservativt borträknad); kvartal märkta "Prel." används som övriga.
4. Future-known covariates (månad/kvartal för prognosmånaden) får gälla hela horizon.
5. Samma origins, samma context och samma metrics för ALLA modeller — ingen
   modell får tränas/prognosotas på annan data än de andra.

## Covariate-regler per experiment

| Experiment | Calendar | Weather | Prices | Regler |
| ---------- | -------- | ------- | ------ | ------ |
| C | ✓ | – | – | Månad/kvartal är kända i framtiden (past_future) |
| D | ✓ | ✓ | – | Nationellt väder (temp, nederbörd, snö) ≤ origin (past_only) |
| E | ✓ | ✓ | ✓ | + senast kända kvartalspris enligt regel 3 (past_only) |

Väder aggregeras nationellt (medel över stationer) — regional (län-)mappning via
koordinater är medvetet utelämnad för att undvika en osäker antagandekedja;
beskrivet i limitations. XGBoost har calendar-features redan i sin bas (enligt
spec §10); dess covariate-varianter lägger därför endast till väder/priser.

## Modeller

- **Naive:** y(t+1) = y(t), repeterad över horizon.
- **Seasonal Naive (m = 12):** de 12 senaste värdena repeteras cykliskt.
- **XGBoost:** direkt multi-horizon (en modell per (region, h)); features enligt
  spec §10: lag 1/2/3/6/12, rolling mean/std (3 och 12 mån), month, quarter av
  prognosmånaden. Fasta hyperparametrar (seed ur config) — ingen tuning på testdata.
- **TimesFM 3.0:** zero-shot foundation model; univariat (A), multivariat över
  21 län (B), + calendar (C), + väder (D), + priser (E). Kvantiler (P10/P50/P90)
  sparas där modellen ger dem.

## Utvärdering

MAE, RMSE, MASE, sMAPE per (modell, experiment, region, horizon), aggregerat
till landsdel/rike och totalt, plus per-origin-variation (std och värsta/bästa
origins). Alla metrics beräknas ur predictions-filen - aldrig i farten.
