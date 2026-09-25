# Slutgranskning (fas 14)

- [x] **Inga leakage-problem:** evaluatorn historik slutar exakt vid origin
      (tests/test_evaluation.py), features vid t använder aldrig y>t
      (tests/test_features.py), priser följer 2-månaders publiceringsregeln,
      väder-covariater ≤ origin. Samma origins/serier/metrics för alla modeller.
- [x] **Inga orättvisa jämförelser:** alla modeller kör samma 48 origins × 26
      serier; multivariat rapporteras i jämförbara universum (topp/län-slices).
- [x] **Reproducerbarhet:** idempotent nedladdning med manifest (URL, UTC-tid,
      sha256, biblioteksversioner); transform deterministisk; seeds i config
      (XGBoost); TimesFM är deterministisk inference.
- [x] **Korrekta metrics:** enhetstester på kända värden; MASE-skalning enbart
      från träningsdelen; alla metrics omberäknas ur predictions-filen.
- [x] **Korrekt terminologi:** "anmäld areal/proxy" konsekvent — aldrig
      "faktisk avverkning".
- [x] **Data-provenance:** manifest + data_inventory med verifierade URL:er.
- [x] **TimesFM-licens:** icke-kommersiella vikter tydligt angivna i README,
      LICENSE-not, limitations och appens disclaimers.
- [x] **Testsvit:** 26 tester gröna.
- [x] **Professionell presentation:** README med figur, huvudtabell, fynd,
      business-tolkning och begränsningar.
