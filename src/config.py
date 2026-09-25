"""Central konfiguration för Forest Supply Forecast.

Alla sökvägar, datakällor och referensdata samlas här så att övriga moduler
kan importera från ett enda ställe. Ingenting här ska hårdkodas utöver det som
verifierats i data discovery (se docs/data_inventory.md).
"""

from pathlib import Path

# ---------------------------------------------------------------- sökvägar
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
PREDICTIONS_DIR = OUTPUTS_DIR / "predictions"
RESULTS_DIR = OUTPUTS_DIR / "results"

# ---------------------------------------------------------------- API:er
# Verifierade 2026-09-17 (se docs/data_inventory.md för detaljer och baskrav).

# Skogsstyrelsens statistikdatabas (PX-Web, API v1)
PXWEB_BASE_URL = "https://pxweb.skogsstyrelsen.se/api/v1/sv"
PXWEB_DATABASE = "Skogsstyrelsens statistikdatabas"
PXWEB_TABLE_TARGET = "Avverkningsanmalan/05_Areal_anm_ans_per_manad.px"
PXWEB_TABLE_PRICES = "Rundvirkespriser/JO0303_3ny.px"
PXWEB_TABLE_INVENTORY = "Lager av virkesravara/JO0306_2.px"
PXWEB_TABLE_FELLING = "Avverkning/JO0312_06.px"

# SMHI Meteorologiska observationer (ny API: version/latest == "1.0").
# OBS: gamla "/api/version/1" är avvecklad och svarar 404.
SMHI_METOBS_BASE_URL = "https://opendata-download-metobs.smhi.se/api/version/1.0"

# SMHI-parameter-id (verifierade):
#   22 = Lufttemperatur, medel per månad
#   23 = Nederbördsmängd, summa per månad
#    2 = Lufttemperatur, medel per dygn
#    5 = Nederbördsmängd, summa per dygn (kl 06)
#    8 = Snödjup, per dygn (kl 06)
#    4 = Vindhastighet, medel 10 min per timme
SMHI_PARAM_TEMP_MONTHLY = 22
SMHI_PARAM_PRECIP_MONTHLY = 23
SMHI_PARAM_TEMP_DAILY = 2
SMHI_PARAM_PRECIP_DAILY = 5
SMHI_PARAM_SNOW_DAILY = 8
SMHI_PARAM_WIND_HOURLY = 4

HTTP_HEADERS = {
    "User-Agent": "forest-supply-forecast/0.1 (open-data research project)",
}

# ---------------------------------------------------------------- övrigt
RANDOM_SEED = 42

# Regioner i Skogsstyrelsens targettabell (värden "0"–"25").
# Värdesträngarna läses dynamiskt från tabellmetadata vid hämtning;
# här sparas de läsbara namnen (prefix i tabellens valueTexts, t.ex. "07 Kronobergs län").
REGION_NAMES = {
    "00": "Hela landet",
    "01": "Stockholms län",
    "03": "Uppsala län",
    "04": "Södermanlands län",
    "05": "Östergötlands län",
    "06": "Jönköpings län",
    "07": "Kronobergs län",
    "08": "Kalmar län",
    "09": "Gotlands län",
    "10": "Blekinge län",
    "12": "Skåne län",
    "13": "Hallands län",
    "14": "Västra Götalands län",
    "17": "Värmlands län",
    "18": "Örebro län",
    "19": "Västmanlands län",
    "20": "Dalarnas län",
    "21": "Gävleborgs län",
    "22": "Västernorrlands län",
    "23": "Jämtlands län",
    "24": "Västerbottens län",
    "25": "Norrbottens län",
}

# Landsdelar (finns även som egna rader i targettabellen) enligt SCB:s
# standardindelning. Används för att aggregera SMHI-stationer till landsdel.
# OBS: att kopplingen län→landsdel stämmer mot Skogsstyrelsens egen gruppering
# ska verifieras i fas 2 genom att jämföra tabellens landsdelsrader mot
# summerade länserier.
LANDSDEL_BY_LAN = {
    "Norra Norrland": ["25", "24", "22", "23"],
    "Södra Norrland": ["21", "20"],
    "Svealand": ["01", "03", "04", "18", "19"],
    "Götaland": ["05", "06", "07", "08", "09", "10", "12", "13", "14", "17"],
}
