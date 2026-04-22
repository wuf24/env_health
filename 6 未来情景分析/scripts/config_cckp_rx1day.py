from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SECTION_DIR = ROOT / "6 未来情景分析"
DATA_RAW_DIR = SECTION_DIR / "data_raw"
OUTDIR = DATA_RAW_DIR / "cckp_rx1day"
DATA_PROCESSED_DIR = SECTION_DIR / "data_processed"
LOG_DIR = SECTION_DIR / "logs"
DOCS_DIR = SECTION_DIR / "docs"

# Paste the exact CCKP URL copied from the webpage here.
# The downloader only replaces period / percentile / scenario based on this template.
BASE_URL = "https://cckpapi.worldbank.org/api/v1/cmip6-x0.25_climatology_rx1day_climatology_annual_2020-2039_median,p10,p90_ssp119,ssp126,ssp245,ssp370,ssp585_ensemble_all_mean/CHN.@?_format=json"

AREA_CODE = "CHN.@"
SCENARIOS = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
PERCENTILES = ["median", "p10", "p90"]
PERIODS = ["2020-2039", "2040-2059", "2060-2079", "2080-2099"]

OUTPUT_FORMAT = "xlsx"
TIMEOUT = 120
SLEEP_SECONDS = 1.0
RETRY_TIMES = 3
USER_AGENT = "Code_health/cckp-rx1day-downloader"

# These tokens are replaced inside BASE_URL.
PERIOD_TOKEN = "2020-2039"
PERCENTILE_TOKEN = "median,p10,p90"
SCENARIO_TOKEN = "ssp119,ssp126,ssp245,ssp370,ssp585"


def ensure_directories() -> None:
    for path in (SECTION_DIR, DATA_RAW_DIR, OUTDIR, DATA_PROCESSED_DIR, LOG_DIR, DOCS_DIR):
        path.mkdir(parents=True, exist_ok=True)
