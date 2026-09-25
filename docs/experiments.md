# Experimentmatris och genomförande

Samma rolling-origin-protokoll för alla modeller: 48 origins (2022M09–2026M08),
26 serier, horizons 1/3/6. Alla råa prognoser sparas i outputs/predictions/.

| Experiment | Target | Regional | Calendar | Weather | Prices | Modell | Fas | Status |
| ---------- | ------ | -------- | -------- | ------- | ------ | ------ | --- | ------ |
| Naive | ✓ | (alla 26 serier) | – | – | – | naive | 5 | ✅ klar |
| Seasonal Naive | ✓ | (alla 26) | – | – | – | seasonal_naive | 5 | ✅ klar |
| XGBoost bas | ✓ | (alla 26) | ✓ | – | – | xgb_base | 6 | ✅ klar |
| XGBoost + väder | ✓ | (alla 26) | ✓ | ✓ | – | xgb_wx | 6/9 | ✅ klar |
| XGBoost + väder+pris | ✓ | (alla 26) | ✓ | ✓ | ✓ | xgb_full | 6/9 | ✅ klar |
| A – TimesFM univariat | ✓ | (alla 26) | – | – | – | timesfm_univ | 7 | ✅ klar |
| B – multivariat topp | ✓ | ✓ (riket + 4 landsdelar) | – | – | – | timesfm_multi_top | 8 | ✅ klar |
| B – multivariat län | ✓ | ✓ (21 län) | – | – | – | timesfm_multi_lan | 8 | ✅ klar |
| C – +kalender | ✓ | (alla 26) | ✓ | – | – | timesfm_cal | 9 | ✅ klar |
| D – +väder | ✓ | (alla 26) | ✓ | ✓ | – | timesfm_wx | 9 | ✅ klar |
| E – +priser | ✓ | (alla 26) | ✓ | ✓ | ✓ | timesfm_full | 9 | ✅ klar |

Resultat och slutsatser: [experiments_results.md](experiments_results.md).

## Designval

- XGBoost har calendar-features i basen (spec §10) - dess väder/pris-varianter
  testar därför marginalnyttan av just de källorna.
- Experiment B körs i två upplagg (toppserier respektive 21 län) för att
  ge jämförbara universum mot de univariata körningarna.
- Priser används som "senast kända kvartalspris" med 2 månaders
  publiceringsfördröjning (se src/features/features.py och tests).
