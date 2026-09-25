# Data dictionary (processed)

## target_monthly.parquet
| Kolumn | Beskrivning |
| ------ | ----------- |
| region_code | Länkod enligt Skogsstyrelsen ('01'–'25'); tom för landsdel/rike |
| region_name | Läsbar regionsnamn ('Hela landet', 'Götaland', 'Jönköpings län', …) |
| region_type | rike / landsdel / län |
| ar, manad | År resp. månad (1–12) |
| date | Månadsstart (Timestamp) |
| areal_ha | Anmäld + ansökt avverkningsareal (hektar). NaN = saknas/'..' i källan |

Källa: Skogsstyrelsen PX-Web tabell 05_Areal_anm_ans_per_manad (2007M01–).
TERMINOLOGI: anmäld areal är en PROXY - inte 'faktisk avverkning'.

## prices_quarterly.parquet
| Kolumn | Beskrivning |
| ------ | ----------- |
| landsdel | Norra Norrland / Södra Norrland / Svealand / Götaland / Hela landet |
| sortiment | Tallsågtimmer, Gransågtimmer, Sågtimmer, Massaved av barrträd/lövträd/totalt |
| ar, kvartal, kvartal_label | Kvartalsupplösning |
| preliminar | True om källan märkt kvartalet 'Prel.' |
| avrakningspris_kr_m3fub | Volymvägt genomsnittligt avräkningspris (kr/m3f ub) |

Källa: JO0303_3ny (2019K1–, ny metod; metodbryt 2025K2 - äldre serier ej jämförbara).

## weather_stations.parquet
Långformat per station: parameter (22/23/8), station_id/namn, lat/lon,
date (månadsstart resp. dygn), value (°C / mm / m), quality (SMHI-flagga).
Källa: SMHI MetObs version/1.0, corrected-archive. Stationer utan länskod -
regional mappning sker via koordinater (fas 3/4).

## weather_national_monthly.parquet
Måndsaggregerat, hela landet: temp_mean_c/n_temp_stations,
precip_sum_mm/n_precip_stations, snow_mean_m/andel_snodagar/n_snow_days/
n_snow_stations. Medel över rapporterande stationer - se n-kolumnerna för
täckning (stationsomfallet påverkar nivån; hanteras i fas 3).

OBS: weather_national_monthly.parquet sträcker sig längre bak i tiden än 2007
(äldsta snöstationer har data till 1700-talet). Före ~2007 vilar aggregeringen
på få stationer - använd endast data från och med targetens start (2007M01),
se n_*-kolumnerna.
