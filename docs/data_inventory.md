# Data inventory

**Fas:** 1 – Data discovery (genomförd 2026-09-17)
**Verifiering:** Alla uppgifter nedan är verifierade direkt mot källornas API:er av
`scripts/01_data_discovery.py` (rapport: `outputs/results/data_discovery_report.json`).

## Sammanfattande tabell

| Dataset | Källa | Frekvens | Historik | Geografi | Variabler | Problem |
| ------- | ----- | -------- | -------- | -------- | --------- | ------- |
| **Areal anmälan om avverkning och ansökan om tillstånd (target)** | Skogsstyrelsen PX-Web, tabell `05_Areal_anm_ans_per_manad` | Månad | 2007M01–2026M08 (19+ år; uppdaterad 2026-09-14) | 21 län + Hela landet + 4 landsdelar | anmäld/ansökt areal (hektar) | Är proxy för faktisk avverkning; sista månaderna preliminära; ".." för saknade/framtida värden; ingen uppdelning anmälan/ansökan i tabellen |
| **Avräkningspriser leveransvirke** | Skogsstyrelsen PX-Web, tabell `JO0303_3ny` | Kvartal | 2019K1–2026K2 | 4 landsdelar + Hela landet | 6 sortiment (tall/gran sågtimmer, barr/löv massaved m.fl.), kr/m³fub | Kvartal vs månads-target kräver alignment; metodbryt 2025K2; äldre serier ej jämförbara; landsdel (inte län) |
| **Lager av virkesråvara** | Skogsstyrelsen PX-Web, tabell `JO0306_2` | Kvartal | 2013K1– | Virkesbalansområden | lager (1 000 m³fub) per sortiment | Annan geografi (virkesbalansområde ≠ landsdel ≠ län); används ej initialt, möjlig covariate |
| **Väder: temperatur/nederbörd (månad)** | SMHI MetObs, param 22/23 | Månad | till 1985+ per station (varierar) | Stationer (lat/lon) → aggregeras | °C resp. mm | Ingen länskod på stationer → koordinatbaserad mappning krävs; stationsdensitet varierar över tid |
| **Väder: snödjup (dygn)** | SMHI MetObs, param 8 | Dygn (→ aggregeras till månad) | långa historiker per station | Stationer (lat/lon) | meter | Samma mappningsfråga; behöver måndsaggregering (t.ex. månadsmedel, antal snödagar) |
| **Väder: dygnstemp/dygnsnederbörd/vind** | SMHI MetObs, param 2/5/4 | Dygn/timme (→ månad) | långa historiker | Stationer (lat/lon) | °C, mm, m/s | Samma mappningsfråga; endast behövliga parametrar används |
| **Modell: TimesFM 3.0** | google-research/timesfm, checkpoint `google/timesfm-3.0-pytorch` | – | – | – | – | **Vikterna är icke-kommersiella** (kod: Apache-2.0); MLX-backend passar Apple Silicon |

## 1. Target: Skogsstyrelsens avverkningsstatistik

### Tabell: `05. Areal anmälan om avverkning och ansökan om tillstånd till avverkning efter Region, År och Månad`

- **API:** `https://pxweb.skogsstyrelsen.se/api/v1/sv/Skogsstyrelsens statistikdatabas/Avverkningsanmalan/05_Areal_anm_ans_per_manad.px`
- **Innehåll:** anmäld areal (avverkningsanmälan) + ansökt areal (tillståndspliktiga ändamål) per region och månad. Statistiken startade 2007 i samband med att avverkningsanmälningssystemet infördes.
- **Regioner (26):** 21 län (`01`–`25`, moderna län; `02` saknas då Älvsborg uppgick i Västra Götaland 1998), `00` Hela landet samt 4 landsdelar (Norra Norrland, Södra Norrland, Svealand, Götaland).
- **Period:** 2007M01–2026M08 (tabelluppdatering 2026-09-14; ~1 månads publiceringsfördröjning).
- **Enhet:** hektar. Provvärde 2007M01, Hela landet: 22 916 (kontrolleras mot statistikrapport i fas 2).
- **Saknade värden:** `".."` för framtida/ej publicerade månader.
- **Terminologi:** targeten kallas **inte** "faktisk avverkning" i projektet; korrekta termer är avverkningsanmälan/anmäld areal/avverkningsaktivitet (proxy).

### API-quirk (viktigt, dokumenterat för reproducerbarhet)

PX-Web-instansen returnerar **HTTP 404 i stället för 400** för POST:ar med variabelkoder
som inte matchar — inklusive koder med icke-ASCII-tecken (`År`, `Månad`), som
verifierat spårar ur server-side encoding. **Verifierad work-around:** en POST som
endast innehåller `Region`-koden (ASCII) returnerar hela tabellen (alla år × månader ×
regioner, ~6 240 celler) i ett anrop. Används av nedladdningsskriptet i fas 2.

### Övriga relevanta tabeller i menyn `Avverkningsanmalan` (ej initialt använda)

`07` hyggesstorlek, `08` grot-uttag, `09` ackumulerad areal (2018M01–), `12` per kommun,
`13` föryngringsmetod. Kan utnyttjas i error analysis/förbättringar senare.

## 2. Virkespriser (Skogsstyrelsen)

- **Aktuell tabell:** `JO0303_3ny.px` — Avräkningspriser, volymvägda genomsnitt (kr/m³f ub) för leveransvirke, **kvartal 2019K1–**, per **landsdel** (Norra Norrland, Södra Norrland, Svealand, Götaland, Hela landet) och **sortiment** (Tallsågtimmer, Gransågtimmer, Sågtimmer, Massaved av barrträd, Massaved av lövträd, Massaved totalt).
- **Metodbryt:** ny metod från **2025K2**; 2019K1–serien är beräknad med ny metod (källa: Skogsaktuellt/verksamhetsrapporter). Äldre tabeller (`JO0303_3.px`, kvartal 1999K1–2021K4, annan regionsindelning) är **inte** direkt jämförbara och används inte initialt.
- **Geografisk kompatibilitet:** landsdel-nivån **matchar** targettabellens landsdelar — bra för landsdel- eller nationella experiment. Län-nivå finns inte i priser.
- **Alignment:** kvartal vs månad. Kandidatstrategi (fas 9): senast publicerade kvartalspris vid forecast-origin (aldrig framtida pris); alternativt interpolation dokumenteras separat.

## 3. Lager av virkesråvara (valfri kandidat-covariate)

`JO0306_2.px` — Lager per virkesbalansområde och sortiment, kvartal 2013K1–.
Intressant för supply chain-berättelsen men **annan geografi** (virkesbalansområden).
Hanteras som separat beslut i fas 4; ingår ej i grundexperimenten.

## 4. Väder (SMHI MetObs)

### API (fornylat 2026)

- **Bas:** `https://opendata-download-metobs.smhi.se/api/version/1.0` (gamla `version/1` är **avvecklad**; dokumentation via `opendata.smhi.se/metobs/`).
- **Flöde:** `parameter/{id}.json` → `station/{sid}.json` → `period/corrected-archive.json` → `.../data.csv`.
- **Perioder:** `corrected-archive` = kvalitetskontrollerade historiska data (utom de senaste ~3 månaderna); `latest-months` = ogranskade data de senaste 4 månaderna. Datakvalitetsnot: slutet av serien är preliminärt — hanteras i ingestion (kvalitetsflagga).
- **Format:** CSV med semikolonseparator, BOM, svensk rubrikrad; nyckelkolumnen **"Representativ månad"**; kvalitetsflagga i kolumnen `Kvalitet` (t.ex. `Y`).

### Parametrar och stationstäckning (verifierat)

| SMHI-param | Beskrivning | Stationer totalt | Täcker 2007–2026 |
| ---------- | ----------- | ---------------: | ---------------: |
| 22 | Lufttemperatur, medel per månad | 975 | **205** |
| 23 | Nederbördsmängd, summa per månad | 2 169 | **480** |
| 2 | Lufttemperatur, medel per dygn | 941 | 206 |
| 5 | Nederbördsmängd, summa per dygn | 2 182 | 482 |
| 8 | Snödjup per dygn (kl 06) | 1 897 | **371** |

### Geografisk mappning (öppet problem, lösas i fas 2)

Stationerna har **lat/lon men ingen länskod**. Plan: mappa station → län via koordinater
(närmaste länscentrum som enkel, dokumenterad baslinje; alternativt polygon-overlay med
öppna länsgränser). Väder aggregeras sedan till län/landsdel/nivå som targeten.
**Leakage-regel:** väder för månad t+1 … t+h används aldrig som om det vore känt vid
forecast-origin; endast laggat väder (eller väderprognos-scenario, tydligt separerat).

## 5. TimesFM 3.0 (modellkälla)

- **Status:** släppt augusti 2026 av Google Research; 330M parametrar; zero-shot; **native multivariat prognos** och covariate-stöd (`past_only_covariates`, `past_future_covariates`).
- **API:** univariat `predict_batch([ts], horizon=h)`; multivariat 2D-array `(num_variates, context_len)`; kvantiler via `return_quantiles=True` → 9 kvantiler (0.1–0.9) — stödjer P10/P50/P90 (spec §18).
- **Gränser:** context trunceras vid `global_context` = 15 360 (irrelevant för vår data, ~250 punkter); horizon ≥ 128 staplas över patchar (våra horizons 1/3/6 mån är trivialt små).
- **Installation:** `pip install "timesfm[mlx]"` (Apple Silicon — rekommenderas här) eller `"timesfm[torch]"`; checkpoint `google/timesfm-3.0-pytorch`. Version/JS-API dokumenteras igen vid installation (fas 7) enligt spec §11.
- **Licens:** kod Apache-2.0; **TimesFM 3.0-vikterna: icke-kommersiell, icke-produktion** (ändring mot ≤2.5 som var Apache-2.0). Ok för detta portfolio-/forskningsprojekt, men måste nämnas: Södra kan inte sätta dessa vikter i produktion utan licensöverenskommelse. Dokumenteras i limitations.

## 6. Beslut som föreslås (avvägs i Checkpoint 2)

1. **Geografisk nivå för huvudanalysen:** förslag — landsdel + Hela landet som huvudnivå (pris-kompatibelt, robustare serier) och 21 län som regional detalj i experiment B (multivariat regional information).
2. **Väderaggregering:** medel över stationer per landsdel med komplettering; dokumentera stationsantal per månad (kvalitetsmått).
3. **Priser:** endast JO0303_3ny (2019K1–); kvartalsalignment via senast kända värde vid origin.
4. **Horizons 1/3/6:** fullt genomförbara — ~205 månader historik per serie; rolling-origin med t.ex. 36–60 testmånader ger tillräckligt många origins.
