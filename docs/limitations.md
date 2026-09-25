# Begränsningar

1. **Avverkningsanmälan ≠ faktisk avverkning.** Targeten är en administrativ
   proxy: en anmälan ska lämnas in före avverkning och vissa ändamål kräver
   tillstånd i stället. Volymen av "anmäld areal" avviker systematiskt från
   avverkad/levererad volym och tolkas bäst som *aktivitetsindikation*.
2. **Public data ≠ company data.** Projektet säger ingenting om Södras interna
   prognosprecision, leveransgeografi eller medlemsstruktur. Resultaten är
   relevanta som metoddemonstration, inte som facit för Södras verksamhet.
3. **Väder-leakage.** Observerat framtida väder används aldrig: alla
   väder-covariater vid origin t är observerade ≤ t (testat i tests/). Ändå är
   covariat-experimenten inte en test av *prognos-väder* - med väderprognoser
   i realtid skulle experiment D kunna se annorlunda ut.
4. **Prisdata.** Kvartalsfrekvens mot månads-target; metodbryt 2025K2 gör äldre
   serier ojämförbara (endast 2019K1– används); publiceringsfördröjning hanteras
   konservativt (2 månader). Priser bidrog inte med marginalnytta i testen.
5. **Väder endast nationellt aggregerat.** Station→län-mappning via koordinater
   är medvetet utelämnad (osäker antagandekedja); regional väderskillnad fångas
   därför inte. En regionalisering är ett naturligt nästa steg.
6. **Limited history.** ~19 år månadsdata (~230 punkter/serie) är litet i
   foundation model-sammanhang. Å andra sidan visar resultatet att TimesFM:s
   pretraining ändå överförs - men regimer som aldrig setts (extrema stormskador,
   strukturella marknadsförändringar) hanteras osäkert av alla modeller.
7. **Foundation model ≠ automatiskt bättre.** TimesFM 3 vann här, men på
   regimskifte-origins slog Seasonal Naive (t.ex. origin 2025-06). En modell som
   vinner i medel kan förlora där det gör som mest ont.
8. **TimesFM 3.0-licens.** Kod: Apache-2.0; vikterna: icke-kommersiell,
   icke-produktion (ändring mot ≤2.5). Portfolio/forskning är ok; produktion i
   ett företag kräver licensöverenskommelse eller alternativ modell.
9. **Osäkra prognosintervall på längre horizons.** P10–P90-täckningen är ~79 %
   vid h=1 men ~60 % vid h=6 (nominal 80 %) - intervallen behöver kalibreras
   (t.ex. konform prediktion) innan beslutsanvändning.
10. **Gotlands datagap** 2010M03–2010M07 fylls med 0 ha (liten region, plausibelt
    men ovisst) - påverkan på resultatet är försumbar men antagandet är explicit.
11a. **Indikativ volym är en grov omvandling.** Volymvyn multiplicerar anmäld
    areal med landsdelens genomsnittliga slutavverkningsvolym (m³sk/ha, 5-årsmedel,
    JO0312_06). Den ignorerar variation i trädslag, ägarkategori, jordmån och
    avverkningstyp, liksom att all anmäld areal inte realiseras. Siffrorna ska
    läsas som storleksordningsindikation, inte volymsprognos.
11. **Preliminära observationer.** De senaste månaderna i Skogsstyrelsens
    statistik (och SMHI:s väderdata, ~3 månaders rättningsprocess) kan komma att
    revideras; backtestet använder den historik som var publicerad vid hämtningen,
    inte den som fanns vid respektive historisk prognostidpunkt (revisionsbias
    ingår alltså inte i utvärderingen).
