from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SECTION_DIR = ROOT / "6 未来情景分析"
DATA_RAW_DIR = SECTION_DIR / "data_raw"
OUTDIR = DATA_RAW_DIR / "cckp_rx1day_timeseries"
DATA_PROCESSED_DIR = SECTION_DIR / "data_processed"
LOG_DIR = SECTION_DIR / "logs"
DOCS_DIR = SECTION_DIR / "docs"

# Paste the exact CCKP timeseries URL copied from the webpage here when needed.
BASE_URL = (
    "https://cckpapi.worldbank.org/api/v1/"
    "cmip6-x0.25_timeseries_rx1day_timeseries_annual_2015-2100_"
    "mean,median,p10,p90_ssp119,ssp126,ssp245,ssp370,ssp585_ensemble_all_mean/"
    "CHN.@?_format=json"
)

AREA_CODE = "CHN.@"
SCENARIOS = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]

# Validated on 2026-04-19:
# - median / p10 / p90 return usable data in both json and xlsx.
# - mean currently returns empty data / export errors for this endpoint.
REQUESTED_STATISTICS = ["mean", "median", "p10", "p90"]
STATISTICS = ["median", "p10", "p90"]
UNAVAILABLE_STATISTICS = ["mean"]

YEAR_RANGE_LABEL = "2015-2100"
OUTPUT_FORMAT = "xlsx"
TIMEOUT = 120
SLEEP_SECONDS = 1.0
RETRY_TIMES = 3
USER_AGENT = "Code_health/cckp-rx1day-timeseries-downloader"

YEAR_RANGE_TOKEN = "2015-2100"
STATISTIC_TOKEN = "mean,median,p10,p90"
SCENARIO_TOKEN = "ssp119,ssp126,ssp245,ssp370,ssp585"


def ensure_directories() -> None:
    for path in (SECTION_DIR, DATA_RAW_DIR, OUTDIR, DATA_PROCESSED_DIR, LOG_DIR, DOCS_DIR):
        path.mkdir(parents=True, exist_ok=True)
