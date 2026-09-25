# Checkpoint-sammanställning (alla 5)

## Checkpoint 1 — Data Discovery
**"Här är exakt vilken data vi har."**
- Target: Skogsstyrelsen PX-Web tabell 05, månatlig anmäld areal 2007M01–2026M08,
  21 län + 4 landsdelar + riket. Priser: JO0303_3ny (kvartal, landsdel). Väder: SMHI
  MetObs (nya API:t version/1.0), ~900 stationer med full täckning. Lager + äldre
  priser dokumenterade men ej använda. TimesFM 3.0 verifierad (aug 2026, icke-kommersiella vikter).
- Dokumenterade API-kvasar: PX-Web 404 på icke-ASCII-kodnamn (work-around: endast
  ASCII-dimensioner i queryn); SMHI gamla version/1 avvecklad; två CSV-format.
- Detaljer: [data_inventory.md](data_inventory.md), beviskörning i
  `outputs/results/data_discovery_report.json`.

## Checkpoint 2 — EDA + forecastdesign
**"Target, regioner, horizons och varför."**
- Säsongens topp är aug–nov (inte vår) — anmälan görs inför höst/vinteravverkning.
  STL-säsongstyrka 0,38. Flad trend (~0). Inga nationella punktanomalier > 2,5 MAD.
- Gotland har datagap 2010M03–07 → 0-fill dokumenterat. Västmanland extremvolatilt
  (enskilda stora avverkningar). Korrelation mellan län ~0,34 (säsongsdrivet).
- Design: 26 serier, horizons 1/3/6, 48 månatliga origins 2022M09–2026M08,
  hela historiken som context, MASE-skalning per origin på träningsdelen.
- Detaljer: [eda_findings.md](eda_findings.md), [methodology.md](methodology.md).

## Checkpoint 3 — Baselines + TimesFM 3
**"Här är första riktiga benchmarken."**
- Naive MASE 0,84/1,10/1,21; Seasonal Naive 0,91/0,93/0,93 (h=1/3/6).
- XGBoost bas 0,75/0,92/0,95.
- TimesFM univariat (zero-shot): **0,63/0,77/0,82 — vinner alla horizons.**

## Checkpoint 4 — Multivariat + covariates
**"Vad bidrar extra informationen faktiskt med?"**
- Multivariat (B): hjälper måttligt på län (0,61/0,72/0,77), tie på toppserier.
- Calendar (C): marginell förbättring (0,62/0,76/0,81).
- Väder (D) och priser (E): ingen nytta — marginellt sämre än A. Samma mönster
  för XGBoost (pris +marginalt vid h≥3, väder inget).
- Slutsats: marginalnyttan sitter i modellernas inbyggda säsongskapacitet, inte
  i externa källor — på denna data.

## Checkpoint 5 — Produktifiering
- Streamlit-app (region × modell × horizon; historik, prognos, P10–P90,
  MAE mot baseline, förändring mot senaste och fjolårsmånad).
  Kör: `streamlit run app/streamlit_app.py`.
- README som professionellt case; limitations; reproducerbar kedja
  (idempotent download med sha256-manifest → parquet → loaders → modeller → app).
