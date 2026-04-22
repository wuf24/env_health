from __future__ import annotations

from pathlib import Path

import pandas as pd

from cckp_rx1day_timeseries_common import (
    OUTDIR,
    YEAR_KEY_RE,
    configure_logger,
    ensure_runtime_directories,
    iter_download_files,
    parse_output_filename,
    read_json_file,
)
from config_cckp_rx1day_timeseries import DATA_PROCESSED_DIR


def clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")
    return cleaned.reset_index(drop=True)


def year_columns(columns: list[object]) -> list[str]:
    return [str(column) for column in columns if YEAR_KEY_RE.match(str(column))]


def reshape_timeseries_frame(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    frame = clean_frame(df)
    frame.columns = [str(column).strip() for column in frame.columns]
    years = year_columns(list(frame.columns))
    if not years:
        raise ValueError(f"{source_file} does not contain yearly columns like 2015-07")

    province_name_col = "name" if "name" in frame.columns else None
    province_code_col = "code" if "code" in frame.columns else None
    if province_name_col is None and province_code_col is None:
        raise ValueError(f"{source_file} does not contain province columns")

    id_vars = [column for column in [province_code_col, province_name_col] if column is not None]
    long_df = frame.melt(id_vars=id_vars, value_vars=years, var_name="time_key", value_name="rx1day")
    long_df["year"] = long_df["time_key"].astype(str).str.slice(0, 4).astype(int)
    long_df["rx1day"] = pd.to_numeric(long_df["rx1day"], errors="coerce")
    long_df = long_df[long_df["rx1day"].notna()].copy()

    if province_name_col is not None:
        long_df["province"] = long_df[province_name_col].astype(str).str.strip()
    else:
        long_df["province"] = long_df[province_code_col].astype(str).str.strip()

    if province_code_col is None:
        long_df["province_code"] = ""
    else:
        long_df["province_code"] = long_df[province_code_col].astype(str).str.strip()

    return long_df[["province", "province_code", "year", "time_key", "rx1day"]].reset_index(drop=True)


def load_xlsx_table(path: Path, logger) -> pd.DataFrame:
    workbook = pd.ExcelFile(path)
    sheet_name = workbook.sheet_names[0]
    frame = pd.read_excel(path, sheet_name=sheet_name, header=0)
    logger.info("%s | sheet=%s | columns=%s", path.name, sheet_name, list(frame.columns))
    return reshape_timeseries_frame(frame, path.name)


def build_province_lookup(logger) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for path in iter_download_files(OUTDIR):
        if path.suffix.lower() != ".xlsx":
            continue
        try:
            workbook = pd.ExcelFile(path)
            frame = pd.read_excel(path, sheet_name=workbook.sheet_names[0], header=0, usecols=[0, 1])
            frame.columns = [str(column).strip() for column in frame.columns]
            if "code" in frame.columns and "name" in frame.columns:
                for _, row in frame.dropna().iterrows():
                    lookup[str(row["code"]).strip()] = str(row["name"]).strip()
        except Exception as exc:
            logger.warning("Province lookup skipped for %s | %s", path.name, exc)
    return lookup


def unwrap_json_data(data: object) -> dict[str, dict[str, float]]:
    if isinstance(data, dict) and data:
        sample = next(iter(data.values()))
        if isinstance(sample, dict) and any(YEAR_KEY_RE.match(str(key)) for key in sample.keys()):
            return data
        nested = next((value for value in data.values() if isinstance(value, dict)), None)
        if isinstance(nested, dict):
            nested_sample = next(iter(nested.values()), None)
            if isinstance(nested_sample, dict) and any(YEAR_KEY_RE.match(str(key)) for key in nested_sample.keys()):
                return nested
    raise ValueError("JSON data is not in province -> year mapping format")


def load_json_table(path: Path, province_lookup: dict[str, str], logger) -> pd.DataFrame:
    payload = read_json_file(path)
    if not isinstance(payload, dict):
        raise ValueError("JSON root is not an object")
    data = unwrap_json_data(payload.get("data"))
    rows: list[dict[str, object]] = []
    sample_keys = list(data.keys())[:5]
    logger.info("%s | province_code_sample=%s", path.name, sample_keys)
    for province_code, yearly_map in data.items():
        province_name = province_lookup.get(str(province_code).strip(), str(province_code).strip())
        for time_key, value in yearly_map.items():
            if not YEAR_KEY_RE.match(str(time_key)):
                continue
            rows.append(
                {
                    "province": province_name,
                    "province_code": str(province_code).strip(),
                    "year": int(str(time_key)[:4]),
                    "time_key": str(time_key),
                    "rx1day": pd.to_numeric(value, errors="coerce"),
                }
            )
    output = pd.DataFrame(rows)
    output = output[output["rx1day"].notna()].reset_index(drop=True)
    return output


def main() -> int:
    ensure_runtime_directories()
    logger, log_path = configure_logger("merge_cckp_rx1day_timeseries")
    logger.info("Source directory: %s", OUTDIR)
    logger.info("Log file: %s", log_path)

    province_lookup = build_province_lookup(logger)
    logger.info("Province lookup size from xlsx files: %s", len(province_lookup))

    rows: list[pd.DataFrame] = []
    failures: list[str] = []

    for path in iter_download_files(OUTDIR):
        metadata = parse_output_filename(path)
        if metadata is None:
            logger.warning("Skipping unexpected file name: %s", path.name)
            continue

        try:
            if path.suffix.lower() == ".xlsx":
                table = load_xlsx_table(path, logger)
            elif path.suffix.lower() == ".json":
                table = load_json_table(path, province_lookup, logger)
            else:
                raise ValueError(f"Unsupported file type: {path.suffix}")

            table["scenario"] = metadata["scenario"]
            table["statistic"] = metadata["statistic"]
            table["source_file"] = path.name
            rows.append(
                table[["province", "province_code", "year", "time_key", "scenario", "statistic", "rx1day", "source_file"]]
            )
        except Exception as exc:
            failures.append(f"{path.name}: {exc}")
            logger.error("Failed to merge %s | %s", path.name, exc)

    if not rows:
        logger.error("No timeseries files were merged. Download files first and rerun merge.")
        return 1

    panel = pd.concat(rows, ignore_index=True)
    panel = panel.sort_values(["scenario", "statistic", "province", "year"]).reset_index(drop=True)

    output_path = DATA_PROCESSED_DIR / "cckp_rx1day_timeseries_panel.csv"
    panel.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info("Merged rows: %s", len(panel))
    logger.info("Output path: %s", output_path)

    if failures:
        logger.warning("Files with merge failures:")
        for item in failures:
            logger.warning("  %s", item)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
