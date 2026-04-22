from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from cckp_rx1day_common import (
    OUTDIR,
    configure_logger,
    ensure_runtime_directories,
    iter_download_files,
    normalize_token,
    parse_output_filename,
    read_json_file,
)
from config_cckp_rx1day import DATA_PROCESSED_DIR


PROVINCE_TOKENS = [
    "province",
    "provincename",
    "subnational",
    "subnation",
    "region",
    "area",
    "location",
    "admin1",
    "name",
    "省",
    "省份",
    "地区",
]
VALUE_TOKENS = [
    "rx1day",
    "value",
    "mean",
    "avg",
    "average",
    "annual",
    "climatology",
    "indicator",
    "result",
    "statistic",
    "data",
    "值",
    "均值",
]
VALUE_BLOCKLIST = [
    "scenario",
    "percentile",
    "period",
    "model",
    "statistic",
    "unit",
    "year",
    "from",
    "to",
    "lat",
    "lon",
    "longitude",
    "latitude",
    "code",
    "id",
]
KNOWN_PROVINCES = {
    normalize_token(name)
    for name in [
        "Beijing",
        "Tianjin",
        "Hebei",
        "Shanxi",
        "Inner Mongolia",
        "Liaoning",
        "Jilin",
        "Heilongjiang",
        "Shanghai",
        "Jiangsu",
        "Zhejiang",
        "Anhui",
        "Fujian",
        "Jiangxi",
        "Shandong",
        "Henan",
        "Hubei",
        "Hunan",
        "Guangdong",
        "Guangxi",
        "Hainan",
        "Chongqing",
        "Sichuan",
        "Guizhou",
        "Yunnan",
        "Tibet",
        "Shaanxi",
        "Gansu",
        "Qinghai",
        "Ningxia",
        "Xinjiang",
        "Hong Kong",
        "Macao",
        "Macau",
        "Taiwan",
        "北京",
        "天津",
        "河北",
        "山西",
        "内蒙古",
        "辽宁",
        "吉林",
        "黑龙江",
        "上海",
        "江苏",
        "浙江",
        "安徽",
        "福建",
        "江西",
        "山东",
        "河南",
        "湖北",
        "湖南",
        "广东",
        "广西",
        "海南",
        "重庆",
        "四川",
        "贵州",
        "云南",
        "西藏",
        "陕西",
        "甘肃",
        "青海",
        "宁夏",
        "新疆",
        "香港",
        "澳门",
        "台湾",
    ]
}


def make_unique_columns(columns: list[object]) -> list[str]:
    counts: dict[str, int] = {}
    output: list[str] = []
    for idx, column in enumerate(columns):
        name = str(column).strip()
        if not name or name.lower() == "nan":
            name = f"unnamed_{idx}"
        base = name
        counts.setdefault(base, 0)
        counts[base] += 1
        if counts[base] > 1:
            name = f"{base}_{counts[base]}"
        output.append(name)
    return output


def coerce_numeric(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.replace(",", "", regex=False).str.strip()
    extracted = text.str.extract(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = make_unique_columns(list(cleaned.columns))
    cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if cleaned.empty:
        return cleaned
    cleaned = cleaned.reset_index(drop=True)
    return cleaned


def detect_header_rows(raw: pd.DataFrame) -> list[int]:
    candidates: list[tuple[float, int]] = []
    max_rows = min(20, len(raw))
    for idx in range(max_rows):
        values = [str(item).strip() for item in raw.iloc[idx].tolist() if str(item).strip() and str(item).strip().lower() != "nan"]
        if len(values) < 2:
            continue
        score = float(len(values))
        joined = " ".join(values)
        normalized = normalize_token(joined)
        if any(token in normalized for token in PROVINCE_TOKENS):
            score += 8
        if any(token in normalized for token in VALUE_TOKENS):
            score += 8
        candidates.append((score, idx))

    ranked = [idx for _, idx in sorted(candidates, reverse=True)]
    ordered: list[int] = []
    for idx in ranked + [0]:
        if idx not in ordered:
            ordered.append(idx)
    return ordered[:3]


def score_province_column(series: pd.Series, column_name: str) -> float:
    values = series.astype(str).str.strip()
    values = values[(values != "") & (values.str.lower() != "nan")]
    if values.empty:
        return float("-inf")

    normalized_name = normalize_token(column_name)
    score = 0.0
    if any(token in normalized_name for token in PROVINCE_TOKENS):
        score += 8.0

    numeric_ratio = coerce_numeric(values).notna().mean()
    score -= float(numeric_ratio) * 6.0

    known_ratio = values.map(lambda item: normalize_token(item) in KNOWN_PROVINCES).mean()
    score += float(known_ratio) * 12.0

    unique_count = values.nunique(dropna=True)
    if 5 <= unique_count <= 60:
        score += 2.0
    score += min(unique_count, 40) / 10.0
    return score


def score_value_column(series: pd.Series, column_name: str) -> float:
    normalized_name = normalize_token(column_name)
    penalty = 4.0 if any(token in normalized_name for token in VALUE_BLOCKLIST) else 0.0

    numeric = coerce_numeric(series)
    numeric_ratio = numeric.notna().mean()
    if numeric_ratio == 0:
        return float("-inf")

    score = float(numeric_ratio) * 12.0 - penalty
    if any(token in normalized_name for token in VALUE_TOKENS):
        score += 6.0
    if "rx1day" in normalized_name:
        score += 10.0
    if numeric.nunique(dropna=True) > 1:
        score += 1.0
    return score


def pick_columns(df: pd.DataFrame) -> tuple[str | None, str | None, float]:
    province_candidates: list[tuple[float, str]] = []
    value_candidates: list[tuple[float, str]] = []

    for column in df.columns:
        province_candidates.append((score_province_column(df[column], column), column))
        value_candidates.append((score_value_column(df[column], column), column))

    province_candidates.sort(reverse=True)
    value_candidates.sort(reverse=True)

    if not province_candidates or not value_candidates:
        return None, None, float("-inf")

    province_col = province_candidates[0][1]
    value_col = next((col for score, col in value_candidates if col != province_col and math.isfinite(score)), None)
    if value_col is None:
        return None, None, float("-inf")

    total_score = province_candidates[0][0] + next(score for score, col in value_candidates if col == value_col)
    return province_col, value_col, total_score


def finalize_table(df: pd.DataFrame, province_col: str, value_col: str) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "province": df[province_col].astype(str).str.strip(),
            "rx1day": coerce_numeric(df[value_col]),
        }
    )
    out = out[(out["province"] != "") & (out["province"].str.lower() != "nan")]
    out = out[out["rx1day"].notna()]
    out = out[~out["province"].map(lambda value: normalize_token(value) in {"china", "country", "allsubnationalsofchina"})]
    return out.reset_index(drop=True)


def extract_frames_from_json(payload: object, path: str = "root") -> list[tuple[str, pd.DataFrame]]:
    frames: list[tuple[str, pd.DataFrame]] = []
    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload):
            frames.append((path, pd.json_normalize(payload, sep="__")))
        elif payload and all(not isinstance(item, (dict, list)) for item in payload):
            frames.append((path, pd.DataFrame({"value": payload})))
        else:
            for idx, item in enumerate(payload):
                frames.extend(extract_frames_from_json(item, f"{path}[{idx}]"))
    elif isinstance(payload, dict):
        if payload and all(not isinstance(item, (dict, list)) for item in payload.values()):
            frames.append((path, pd.DataFrame([payload])))
        for key, value in payload.items():
            frames.extend(extract_frames_from_json(value, f"{path}.{key}"))
    return frames


def load_excel_candidates(path: Path, logger) -> list[tuple[str, pd.DataFrame]]:
    candidates: list[tuple[str, pd.DataFrame]] = []
    workbook = pd.ExcelFile(path)
    for sheet_name in workbook.sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
        for header_row in detect_header_rows(raw):
            frame = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
            frame = clean_frame(frame)
            if frame.empty:
                continue
            candidate_name = f"sheet={sheet_name},header_row={header_row}"
            logger.info("%s | %s | columns=%s", path.name, candidate_name, list(frame.columns))
            candidates.append((candidate_name, frame))
    return candidates


def load_json_candidates(path: Path, logger) -> list[tuple[str, pd.DataFrame]]:
    payload = read_json_file(path)
    candidates: list[tuple[str, pd.DataFrame]] = []
    for candidate_name, frame in extract_frames_from_json(payload):
        frame = clean_frame(frame)
        if frame.empty:
            continue
        logger.info("%s | %s | columns=%s", path.name, candidate_name, list(frame.columns))
        candidates.append((candidate_name, frame))
    return candidates


def choose_best_table(path: Path, logger) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        candidates = load_excel_candidates(path, logger)
    elif path.suffix.lower() == ".json":
        candidates = load_json_candidates(path, logger)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    best_score = float("-inf")
    best_table: pd.DataFrame | None = None
    best_note = ""

    for candidate_name, frame in candidates:
        province_col, value_col, score = pick_columns(frame)
        if province_col is None or value_col is None:
            continue

        final = finalize_table(frame, province_col, value_col)
        if final.empty:
            continue

        logger.info(
            "%s | selected candidate=%s | province_col=%s | value_col=%s | rows=%s | score=%.2f",
            path.name,
            candidate_name,
            province_col,
            value_col,
            len(final),
            score,
        )
        if score > best_score:
            best_score = score
            best_table = final
            best_note = candidate_name

    if best_table is None:
        raise ValueError(
            f"Could not identify province/value columns in {path.name}. "
            "Check the merge log for printed column names and adjust the token lists if needed."
        )

    logger.info("%s | final candidate=%s | final_rows=%s", path.name, best_note, len(best_table))
    return best_table


def main() -> int:
    ensure_runtime_directories()
    logger, log_path = configure_logger("merge_cckp_rx1day")
    logger.info("Source directory: %s", OUTDIR)
    logger.info("Log file: %s", log_path)

    rows: list[pd.DataFrame] = []
    failures: list[str] = []

    for path in iter_download_files(OUTDIR):
        metadata = parse_output_filename(path)
        if metadata is None:
            logger.warning("Skipping unexpected file name: %s", path.name)
            continue

        try:
            table = choose_best_table(path, logger)
            table["scenario"] = metadata["scenario"]
            table["percentile"] = metadata["percentile"]
            table["period"] = metadata["period"]
            table["source_file"] = path.name
            rows.append(table[["province", "scenario", "percentile", "period", "rx1day", "source_file"]])
        except Exception as exc:
            failures.append(f"{path.name}: {exc}")
            logger.error("Failed to merge %s | %s", path.name, exc)

    if not rows:
        logger.error("No files were merged. Fill BASE_URL, download files, and rerun merge.")
        return 1

    panel = pd.concat(rows, ignore_index=True)
    panel = panel.sort_values(["scenario", "percentile", "period", "province", "source_file"]).reset_index(drop=True)

    output_path = DATA_PROCESSED_DIR / "cckp_rx1day_panel.csv"
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
