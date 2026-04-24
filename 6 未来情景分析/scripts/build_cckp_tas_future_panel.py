from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from config_future_scenario_projection import CCKP_PROVINCE_TO_CN, FUTURE_PROVINCE_EXCLUDE


SECTION_DIR = Path(__file__).resolve().parents[1]
DATA_RAW_DIR = SECTION_DIR / "data_raw" / "cckp_tas_timeseries"
DATA_PROCESSED_DIR = SECTION_DIR / "data_processed"
LOG_DIR = SECTION_DIR / "logs"

FUTURE_URL = (
    "https://cckpapi.worldbank.org/cckp/v1/"
    "cmip6-x0.25_timeseries_tas_timeseries_annual_2015-2100_"
    "median,p10,p90_ssp119,ssp126,ssp245,ssp370,ssp585_ensemble_all_mean/"
    "CHN.@?_format=json"
)
HISTORICAL_URL = (
    "https://cckpapi.worldbank.org/cckp/v1/"
    "cmip6-x0.25_timeseries_tas_timeseries_annual_1950-2014_"
    "median,p10,p90_historical_ensemble_all_mean/"
    "CHN.@?_format=json"
)

FUTURE_RAW_PATH = DATA_RAW_DIR / "tas_timeseries_CHNprov_2015-2100_median_p10_p90.json"
HISTORICAL_RAW_PATH = DATA_RAW_DIR / "tas_timeseries_CHNprov_1950-2014_median_p10_p90_historical.json"
GEOCODE_MAP_PATH = DATA_PROCESSED_DIR / "cckp_tas_china_geocode_map.csv"

HISTORICAL_PANEL_PATH = DATA_PROCESSED_DIR / "cckp_tas_timeseries_historical_panel.csv"
COMBINED_PANEL_PATH = DATA_PROCESSED_DIR / "cckp_tas_timeseries_combined_panel.csv"
REFERENCE_PATH = DATA_PROCESSED_DIR / "cckp_tas_reference_1991_2020.csv"
TA_FUTURE_PATH = DATA_PROCESSED_DIR / "TA_future_panel.csv"
PROVINCE_TAS_SSP_PATH = DATA_PROCESSED_DIR / "ssp_province_mean_tas_panel.csv"

USER_AGENT = "Code_health/cckp-tas-future-panel-builder"
TIMEOUT = 180

REFERENCE_START_YEAR = 1991
REFERENCE_SPLIT_YEAR = 2014
REFERENCE_END_YEAR = 2020
DEFAULT_OUTPUT_START_YEAR = 2024
DEFAULT_OUTPUT_END_YEAR = 2100
TA_COL = "TA（°C）"
PROVINCE_TAS_COL = "省平均气温"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download historical CCKP tas, stitch with future SSP tas, and build TA_future_panel.csv."
    )
    parser.add_argument("--force-download", action="store_true", help="Redownload raw JSON files even if they exist.")
    parser.add_argument("--start-year", type=int, default=DEFAULT_OUTPUT_START_YEAR, help="First future year to export.")
    parser.add_argument("--end-year", type=int, default=DEFAULT_OUTPUT_END_YEAR, help="Last future year to export.")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="HTTP timeout in seconds.")
    return parser.parse_args()


def ensure_directories() -> None:
    for path in (DATA_RAW_DIR, DATA_PROCESSED_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def configure_logger() -> tuple[logging.Logger, Path]:
    ensure_directories()
    logger = logging.getLogger("build_cckp_tas_future_panel")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"build_cckp_tas_future_panel_{timestamp}.log"
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger, log_path


def download_json(url: str, target_path: Path, timeout: int, force: bool, logger: logging.Logger) -> dict:
    if target_path.exists() and not force:
        logger.info("Using existing file: %s", target_path.name)
        return json.loads(target_path.read_text(encoding="utf-8"))

    logger.info("Downloading %s", url)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved %s", target_path)
    return payload


def load_geocode_map() -> dict[str, str]:
    if not GEOCODE_MAP_PATH.exists():
        raise FileNotFoundError(f"Missing geocode map: {GEOCODE_MAP_PATH}")
    df = pd.read_csv(GEOCODE_MAP_PATH, encoding="utf-8-sig")
    return dict(zip(df["province_code"], df["province"]))


def flatten_historical(payload: dict, code_to_province: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for statistic, geo_map in payload["data"].items():
        for province_code, time_map in geo_map.items():
            province = code_to_province.get(province_code, province_code)
            for time_key, value in time_map.items():
                rows.append(
                    {
                        "province": province,
                        "province_code": province_code,
                        "year": int(str(time_key).split("-")[0]),
                        "time_key": str(time_key),
                        "scenario": "historical",
                        "statistic": statistic,
                        "tas": float(value),
                        "source_file": HISTORICAL_RAW_PATH.name,
                        "data_stage": "historical",
                    }
                )
    df = pd.DataFrame(rows)
    return df.sort_values(["province", "statistic", "year"]).reset_index(drop=True)


def flatten_future(payload: dict, code_to_province: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for statistic, scenario_map in payload["data"].items():
        for scenario, geo_map in scenario_map.items():
            for province_code, time_map in geo_map.items():
                province = code_to_province.get(province_code, province_code)
                for time_key, value in time_map.items():
                    rows.append(
                        {
                            "province": province,
                            "province_code": province_code,
                            "year": int(str(time_key).split("-")[0]),
                            "time_key": str(time_key),
                            "scenario": scenario,
                            "statistic": statistic,
                            "tas": float(value),
                            "source_file": FUTURE_RAW_PATH.name,
                            "data_stage": "future",
                        }
                    )
    df = pd.DataFrame(rows)
    return df.sort_values(["province", "scenario", "statistic", "year"]).reset_index(drop=True)


def harmonize_provinces(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Province"] = out["province"].map(CCKP_PROVINCE_TO_CN)
    out = out[out["Province"].notna()].copy()
    out = out[~out["Province"].isin(FUTURE_PROVINCE_EXCLUDE)].copy()
    return out.reset_index(drop=True)


def build_reference_table(historical_df: pd.DataFrame, future_df: pd.DataFrame) -> pd.DataFrame:
    hist_ref = historical_df[
        historical_df["year"].between(REFERENCE_START_YEAR, REFERENCE_SPLIT_YEAR, inclusive="both")
    ].copy()
    fut_ref = future_df[
        future_df["year"].between(REFERENCE_SPLIT_YEAR + 1, REFERENCE_END_YEAR, inclusive="both")
    ].copy()

    hist_group = (
        hist_ref.groupby(["Province", "province", "province_code", "statistic"], dropna=False)
        .agg(hist_reference_n=("year", "nunique"), hist_tas_sum=("tas", "sum"))
        .reset_index()
    )
    future_group = (
        fut_ref.groupby(["Province", "province", "province_code", "scenario", "statistic"], dropna=False)
        .agg(future_reference_n=("year", "nunique"), future_tas_sum=("tas", "sum"))
        .reset_index()
    )

    reference = future_group.merge(
        hist_group,
        on=["Province", "province", "province_code", "statistic"],
        how="left",
        validate="many_to_one",
    )
    reference["hist_reference_n"] = reference["hist_reference_n"].fillna(0).astype(int)
    reference["future_reference_n"] = reference["future_reference_n"].fillna(0).astype(int)
    reference["reference_n"] = reference["hist_reference_n"] + reference["future_reference_n"]
    reference["tas_ref_1991_2020"] = (
        reference["hist_tas_sum"].fillna(0.0) + reference["future_tas_sum"].fillna(0.0)
    ) / reference["reference_n"]
    reference["reference_period"] = "1991-2020"
    reference["reference_method"] = "cmip6_same_stat_same_scenario_mean_1991_2020"
    reference["reference_hist_years"] = "1991-2014"
    reference["reference_future_years"] = "2015-2020"

    return reference.sort_values(["Province", "scenario", "statistic"]).reset_index(drop=True)


def build_combined_panel(historical_df: pd.DataFrame, future_df: pd.DataFrame) -> pd.DataFrame:
    frames = [historical_df.copy(), future_df.copy()]
    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values(["Province", "scenario", "statistic", "year"]).reset_index(drop=True)


def build_ta_future_panel(reference_df: pd.DataFrame, future_df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    future_subset = future_df[future_df["year"].between(start_year, end_year, inclusive="both")].copy()
    out = future_subset.merge(
        reference_df[
            [
                "Province",
                "province",
                "province_code",
                "scenario",
                "statistic",
                "tas_ref_1991_2020",
                "reference_n",
                "reference_period",
                "reference_method",
                "reference_hist_years",
                "reference_future_years",
            ]
        ],
        on=["Province", "province", "province_code", "scenario", "statistic"],
        how="left",
        validate="many_to_one",
    )
    out[TA_COL] = out["tas"] - out["tas_ref_1991_2020"]
    out["ta_future"] = out[TA_COL]
    out["baseline_method"] = "cmip6_self_reference"
    out["source_historical_file"] = HISTORICAL_RAW_PATH.name
    out["source_future_file"] = FUTURE_RAW_PATH.name
    return out.sort_values(["Province", "scenario", "statistic", "year"]).reset_index(drop=True)


def build_province_tas_ssp_panel(reference_df: pd.DataFrame, future_df: pd.DataFrame) -> pd.DataFrame:
    out = future_df.merge(
        reference_df[
            [
                "Province",
                "province",
                "province_code",
                "scenario",
                "statistic",
                "tas_ref_1991_2020",
                "reference_n",
                "reference_period",
                "reference_method",
                "reference_hist_years",
                "reference_future_years",
            ]
        ],
        on=["Province", "province", "province_code", "scenario", "statistic"],
        how="left",
        validate="many_to_one",
    )
    out[PROVINCE_TAS_COL] = out["tas"]
    out["province_tas_ssp"] = out[PROVINCE_TAS_COL]
    out["baseline_method"] = "cmip6_absolute_tas"
    out["source_historical_file"] = HISTORICAL_RAW_PATH.name
    out["source_future_file"] = FUTURE_RAW_PATH.name
    return out.sort_values(["Province", "scenario", "statistic", "year"]).reset_index(drop=True)


def validate_reference(reference_df: pd.DataFrame) -> None:
    missing = reference_df["tas_ref_1991_2020"].isna().sum()
    if missing:
        raise ValueError(f"Reference table contains {missing} missing tas_ref_1991_2020 values")
    bad_counts = reference_df.loc[reference_df["reference_n"] != 30]
    if not bad_counts.empty:
        preview = bad_counts[["Province", "scenario", "statistic", "reference_n"]].head(10).to_dict("records")
        raise ValueError(f"Reference years are incomplete for some province/scenario/statistic groups: {preview}")


def validate_ta_future_panel(df: pd.DataFrame, start_year: int, end_year: int) -> None:
    if df.empty:
        raise ValueError("TA_future_panel is empty")
    if df["year"].min() != start_year or df["year"].max() != end_year:
        raise ValueError(
            f"TA_future_panel year range mismatch: got {df['year'].min()}-{df['year'].max()}, expected {start_year}-{end_year}"
        )
    if df["Province"].isna().any():
        raise ValueError("TA_future_panel contains missing Province values")
    if df[TA_COL].isna().any():
        raise ValueError("TA_future_panel contains missing TA values")


def validate_province_tas_ssp_panel(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("ssp_province_mean_tas_panel is empty")
    if df["Province"].isna().any():
        raise ValueError("ssp_province_mean_tas_panel contains missing Province values")
    if df[PROVINCE_TAS_COL].isna().any():
        raise ValueError("ssp_province_mean_tas_panel contains missing province tas values")
    if df["year"].min() != 2015 or df["year"].max() != 2100:
        raise ValueError(
            "ssp_province_mean_tas_panel year range mismatch: "
            f"got {df['year'].min()}-{df['year'].max()}, expected 2015-2100"
        )


def save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def main() -> int:
    args = parse_args()
    if args.start_year < REFERENCE_END_YEAR + 1:
        raise ValueError("start-year should be 2021 or later; 2024 is the default future projection start year")
    if args.end_year < args.start_year:
        raise ValueError("end-year must be greater than or equal to start-year")

    logger, log_path = configure_logger()
    logger.info("Log file: %s", log_path)

    code_to_province = load_geocode_map()
    logger.info("Loaded %s province-code mappings", len(code_to_province))

    historical_payload = download_json(
        url=HISTORICAL_URL,
        target_path=HISTORICAL_RAW_PATH,
        timeout=args.timeout,
        force=args.force_download,
        logger=logger,
    )
    future_payload = download_json(
        url=FUTURE_URL,
        target_path=FUTURE_RAW_PATH,
        timeout=args.timeout,
        force=args.force_download,
        logger=logger,
    )

    historical_panel = harmonize_provinces(flatten_historical(historical_payload, code_to_province))
    future_panel = harmonize_provinces(flatten_future(future_payload, code_to_province))
    combined_panel = build_combined_panel(historical_panel, future_panel)
    reference_df = build_reference_table(historical_panel, future_panel)
    ta_future_panel = build_ta_future_panel(reference_df, future_panel, args.start_year, args.end_year)
    province_tas_ssp_panel = build_province_tas_ssp_panel(reference_df, future_panel)

    validate_reference(reference_df)
    validate_ta_future_panel(ta_future_panel, args.start_year, args.end_year)
    validate_province_tas_ssp_panel(province_tas_ssp_panel)

    save_csv(historical_panel, HISTORICAL_PANEL_PATH)
    save_csv(combined_panel, COMBINED_PANEL_PATH)
    save_csv(reference_df, REFERENCE_PATH)
    save_csv(ta_future_panel, TA_FUTURE_PATH)
    save_csv(province_tas_ssp_panel, PROVINCE_TAS_SSP_PATH)

    logger.info("Historical panel rows: %s", len(historical_panel))
    logger.info("Future panel rows: %s", len(future_panel))
    logger.info("Combined panel rows: %s", len(combined_panel))
    logger.info("Reference rows: %s", len(reference_df))
    logger.info("TA future rows: %s", len(ta_future_panel))
    logger.info("Province SSP tas rows: %s", len(province_tas_ssp_panel))
    logger.info("TA future provinces: %s", ta_future_panel["Province"].nunique())
    logger.info("TA future scenarios: %s", ", ".join(sorted(ta_future_panel["scenario"].unique())))
    logger.info("TA future statistics: %s", ", ".join(sorted(ta_future_panel["statistic"].unique())))
    logger.info(
        "Province SSP tas year range: %s-%s",
        province_tas_ssp_panel["year"].min(),
        province_tas_ssp_panel["year"].max(),
    )
    logger.info("Wrote %s", HISTORICAL_PANEL_PATH)
    logger.info("Wrote %s", COMBINED_PANEL_PATH)
    logger.info("Wrote %s", REFERENCE_PATH)
    logger.info("Wrote %s", TA_FUTURE_PATH)
    logger.info("Wrote %s", PROVINCE_TAS_SSP_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
