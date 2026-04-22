from __future__ import annotations

import json
import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config_cckp_rx1day_timeseries import (
    AREA_CODE,
    LOG_DIR,
    OUTDIR,
    SCENARIOS,
    STATISTICS,
    UNAVAILABLE_STATISTICS,
    YEAR_RANGE_LABEL,
    ensure_directories,
)


FILENAME_RE = re.compile(
    r"^rx1day_timeseries_(?P<area>.+?)_(?P<scenario>ssp\d+)_(?P<statistic>mean|median|p10|p90)_(?P<year_range>\d{4}-\d{4})\.(?P<extension>xlsx|json)$",
    re.IGNORECASE,
)
YEAR_KEY_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")


def area_label_from_code(area_code: str = AREA_CODE) -> str:
    parts = str(area_code).split(".")
    if len(parts) == 2 and parts[1] in {"Q", "@"}:
        return f"{parts[0].upper()}prov"
    safe = re.sub(r"[^0-9A-Za-z]+", "_", str(area_code)).strip("_")
    return safe or "area"


def build_output_stem(scenario: str, statistic: str, year_range: str = YEAR_RANGE_LABEL, area_code: str = AREA_CODE) -> str:
    return f"rx1day_timeseries_{area_label_from_code(area_code)}_{scenario}_{statistic}_{year_range}"


def build_output_path(
    scenario: str,
    statistic: str,
    extension: str,
    outdir: Path = OUTDIR,
    area_code: str = AREA_CODE,
    year_range: str = YEAR_RANGE_LABEL,
) -> Path:
    return outdir / f"{build_output_stem(scenario, statistic, year_range=year_range, area_code=area_code)}.{extension}"


def parse_output_filename(path: Path) -> dict[str, str] | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    return match.groupdict()


def expected_combinations() -> list[dict[str, str]]:
    return [{"scenario": scenario, "statistic": statistic} for scenario in SCENARIOS for statistic in STATISTICS]


def combination_key(scenario: str, statistic: str) -> tuple[str, str]:
    return scenario, statistic


def normalize_base_url(base_url: str) -> str:
    cleaned = str(base_url).strip()
    if not cleaned or cleaned in {"<PASTE_CCKP_URL_HERE>", "PASTE_CCKP_URL_HERE"}:
        raise ValueError(
            "BASE_URL is empty. Paste the exact CCKP timeseries URL into "
            "'6 未来情景分析/scripts/config_cckp_rx1day_timeseries.py' before running the downloader."
        )
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError("BASE_URL must start with http:// or https:// .")
    return cleaned


def set_query_format(url: str, output_format: str) -> str:
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    replaced = False
    updated: list[tuple[str, str]] = []
    for key, value in query:
        if key == "_format":
            updated.append((key, output_format))
            replaced = True
        else:
            updated.append((key, value))
    if not replaced:
        updated.append(("_format", output_format))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(updated), parts.fragment))


def build_url(
    base_url: str,
    statistic: str,
    scenario: str,
    output_format: str,
    year_range: str,
    year_range_token: str,
    statistic_token: str,
    scenario_token: str,
) -> str:
    url = normalize_base_url(base_url)
    replacements = {
        "year_range": (year_range_token, year_range),
        "statistic": (statistic_token, statistic),
        "scenario": (scenario_token, scenario),
    }
    for label, (token, _) in replacements.items():
        if token not in url:
            raise ValueError(
                f"BASE_URL does not contain the configured {label} token '{token}'. "
                "Update config_cckp_rx1day_timeseries.py to match the copied URL."
            )
    for token, value in (item for item in replacements.values()):
        url = url.replace(token, value, 1)
    return set_query_format(url, output_format)


def ensure_runtime_directories() -> None:
    ensure_directories()


def configure_logger(prefix: str) -> tuple[logging.Logger, Path]:
    ensure_runtime_directories()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"{prefix}_{timestamp}.log"
    logger = logging.getLogger(f"{prefix}_{timestamp}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger, log_path


def find_matching_files(scenario: str, statistic: str, outdir: Path = OUTDIR) -> list[Path]:
    stem = build_output_stem(scenario, statistic)
    return sorted(
        path
        for path in outdir.glob(f"{stem}.*")
        if path.is_file() and parse_output_filename(path) is not None
    )


def read_json_file(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_xlsx_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "file does not exist"
    if path.stat().st_size == 0:
        return False, "file is empty"
    if not zipfile.is_zipfile(path):
        return False, "xlsx is not a valid zip container"
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            if "xl/workbook.xml" not in names:
                return False, "xlsx is missing xl/workbook.xml"
    except Exception as exc:  # pragma: no cover - defensive validation
        return False, f"zip validation failed: {exc}"
    return True, "ok"


def validate_json_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "file does not exist"
    if path.stat().st_size == 0:
        return False, "file is empty"

    try:
        payload = read_json_file(path)
    except Exception as exc:  # pragma: no cover - defensive validation
        return False, f"json parse failed: {exc}"

    data = payload.get("data") if isinstance(payload, dict) else None
    if not data:
        return False, "json data is empty"
    if not isinstance(data, dict):
        return False, "json data is not a dict"
    sample = next(iter(data.values()), None)
    if not isinstance(sample, dict):
        return False, "json payload is not province -> annual mapping"
    if not any(YEAR_KEY_RE.match(str(key)) for key in sample.keys()):
        return False, "json payload does not contain annual year keys"
    return True, "ok"


def validate_downloaded_file(path: Path, extension: str | None = None) -> tuple[bool, str]:
    extension = (extension or path.suffix).lower().lstrip(".")
    if extension == "xlsx":
        return validate_xlsx_file(path)
    if extension == "json":
        return validate_json_file(path)
    return False, f"unsupported extension: {extension}"


def iter_download_files(outdir: Path = OUTDIR) -> Iterable[Path]:
    for path in sorted(outdir.glob("rx1day_timeseries_*.*")):
        if path.is_file():
            yield path


def validation_notes() -> list[str]:
    notes = []
    if UNAVAILABLE_STATISTICS:
        notes.append(
            "Unavailable statistics currently excluded from downloads: "
            + ", ".join(UNAVAILABLE_STATISTICS)
        )
    return notes
