# EDA-fynd (fas 3)

*Auto-genererad av scripts/03_eda.py - figurer i outputs/figures/.*

## Target: anmäld avverkningsareal (Hela landet)

- Observationer: 236 månader (2007-01–2026-08).
- Årlig nivå (hela år 2007–2025): median 261,216 ha/år; variationsbredd 221,103–300,578 ha. (2026 är ofullständigt.)
- Linjär trend: +4 ha/månad (+53 ha/år).
- Saknade värden: 5 interiära NaN i hela matrisen; sista observerade månad 2026-08 (tabellen innehåller framtidsrader med NaN).
- Tydlig årscykel: topp okt (29,531), sep (28,636), nov (27,508) ha/mån - anmälan görs typiskt inför höst-/vinteravverkning; lägst mar (16,428), feb (16,294), apr (15,107) ha/mån. Topplistor ändrar narrativet 'vår är högsäsong': i anmälardata är hösten högsäsong; STL-säsongstyrka 0.38.
- Extrema observationer (|avvikelse| > 2,5 MAD från rullande median): 0 st.
  (Ingen månad överskrider tröskeln - landsserien är förvånansvänt jämn.)
  Tolkning: nationell nivå drivs av säsongsrytm och skadeår snarare än punktanomalier. Inga värden tas bort - de är verkliga fenomen och ingår i backtestingen.
- Datagap: Gotlands län saknar 5 månader (2010-03–2010-07). Hanteras som 0 ha i modellmatrisen (liten region, inga anmälningar är plausibelt) och dokumenteras i limitations.

## Regional variation

- Störst volym: Västerbottens län (629,862 ha totalt), Jämtlands län (575,401 ha totalt), Norrbottens län (480,072 ha totalt).
- Störst volym andel av landet: 33% kommer från topp-3 län.
- Mest stabila (lägsta CV): Västra Götalands län (0.33), Uppsala län (0.34), Jämtlands län (0.35); mest volatila: Gotlands län (0.57), Södermanlands län (0.59), Västmanlands län (0.97). Hög CV i små län drivs av enstaka stora avverkningar (t.ex. Västmanland: median 366 ha/mån men max 5 626) - sannolikt enskilda stora markägare/avverkningsuppdrag.
- Korrelation mellan råa länserier: median 0.34 - mätt men dämpat av lokalt brus; gemensam säsong är den dominerande gemensamma faktorn. Multivariat experiment B testar om TimesFM utnyttjar korsserie-information bättre än univariat prognos.

## Väder (nationellt) och virkespriser

- Stationstäckning 2007–: median 183 temp-, 386 nederbörds- och 242 snöststationer per månad.
- Prisserierna är kvartalsvisa med metodbryt 2025K2; används endast som senast-kända värden vid forecast-origin (experiment E).
