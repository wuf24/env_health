from __future__ import annotations

import json
import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config_cckp_rx1day import (
    AREA_CODE,
    LOG_DIR,
    OUTDIR,
    PERIODS,
    PERCENTILES,
    SCENARIOS,
    ensure_directories,
)


FILENAME_RE = re.compile(
    r"^rx1day_(?P<area>.+?)_(?P<scenario>ssp\d+)_(?P<percentile>median|p10|p90)_(?P<period>\d{4}-\d{4})\.(?P<extension>xlsx|json)$",
    re.IGNORECASE,
)


def area_label_from_code(area_code: str = AREA_CODE) -> str:
    parts = str(area_code).split(".")
    if len(parts) == 2 and parts[1] in {"Q", "@"}:
        return f"{parts[0].upper()}prov"
    safe = re.sub(r"[^0-9A-Za-z]+", "_", str(area_code)).strip("_")
    return safe or "area"


def build_output_stem(scenario: str, percentile: str, period: str, area_code: str = AREA_CODE) -> str:
    return f"rx1day_{area_label_from_code(area_code)}_{scenario}_{percentile}_{period}"


def build_output_path(
    scenario: str,
    percentile: str,
    period: str,
    extension: str,
    outdir: Path = OUTDIR,
    area_code: str = AREA_CODE,
) -> Path:
    return outdir / f"{build_output_stem(scenario, percentile, period, area_code=area_code)}.{extension}"


def parse_output_filename(path: Path) -> dict[str, str] | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    return match.groupdict()


def expected_combinations() -> list[dict[str, str]]:
    combos: list[dict[str, str]] = []
    for scenario in SCENARIOS:
        for percentile in PERCENTILES:
            for period in PERIODS:
                combos.append(
                    {
                        "scenario": scenario,
                        "percentile": percentile,
                        "period": period,
                    }
                )
    return combos


def combination_key(scenario: str, percentile: str, period: str) -> tuple[str, str, str]:
    return scenario, percentile, period


def normalize_base_url(base_url: str) -> str:
    cleaned = str(base_url).strip()
    if not cleaned or cleaned in {"<PASTE_CCKP_URL_HERE>", "PASTE_CCKP_URL_HERE"}:
        raise ValueError(
            "BASE_URL is empty. Paste the exact CCKP URL copied from the webpage into "
            "'6 未来情景分析/scripts/config_cckp_rx1day.py' before running the downloader."
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
    period: str,
    percentile: str,
    scenario: str,
    output_format: str,
    period_token: str,
    percentile_token: str,
    scenario_token: str,
) -> str:
    url = normalize_base_url(base_url)
    replacements = {
        "period": (period_token, period),
        "percentile": (percentile_token, percentile),
        "scenario": (scenario_token, scenario),
    }
    for label, (token, _) in replacements.items():
        if token not in url:
            raise ValueError(
                f"BASE_URL does not contain the configured {label} token '{token}'. "
                "Update the token values in config_cckp_rx1day.py to match the copied URL."
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


def normalize_token(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", "", text)
    return text.replace("_", "").replace("-", "").replace(".", "")


def find_matching_files(scenario: str, percentile: str, period: str, outdir: Path = OUTDIR) -> list[Path]:
    stem = build_output_stem(scenario, percentile, period)
    return sorted(path for path in outdir.glob(f"{stem}.*") if path.is_file())


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
        from openpyxl import load_workbook

        workbook = load_workbook(path, read_only=True, data_only=True)
        workbook.close()
    except Exception as exc:  # pragma: no cover - defensive validation
        return False, f"openpyxl failed to read workbook: {exc}"
    return True, "ok"


def validate_json_file(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "file does not exist"
    if path.stat().st_size == 0:
        return False, "file is empty"
    try:
        read_json_file(path)
    except Exception as exc:  # pragma: no cover - defensive validation
        return False, f"json parse failed: {exc}"
    return True, "ok"


def validate_downloaded_file(path: Path, extension: str | None = None) -> tuple[bool, str]:
    extension = (extension or path.suffix).lower().lstrip(".")
    if extension == "xlsx":
        return validate_xlsx_file(path)
    if extension == "json":
        return validate_json_file(path)
    return False, f"unsupported extension: {extension}"


def iter_download_files(outdir: Path = OUTDIR) -> Iterable[Path]:
    for path in sorted(outdir.glob("rx1day_*.*")):
        if path.is_file():
            yield path
