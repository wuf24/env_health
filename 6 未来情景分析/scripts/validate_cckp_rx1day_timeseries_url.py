from __future__ import annotations

import json

import requests

from cckp_rx1day_timeseries_common import build_url, configure_logger, ensure_runtime_directories
from config_cckp_rx1day_timeseries import (
    BASE_URL,
    REQUESTED_STATISTICS,
    SCENARIOS,
    YEAR_RANGE_LABEL,
    YEAR_RANGE_TOKEN,
    SCENARIO_TOKEN,
    STATISTIC_TOKEN,
    TIMEOUT,
    USER_AGENT,
)


def inspect_response(response: requests.Response) -> tuple[bool, str]:
    content_type = response.headers.get("content-type", "")
    if "spreadsheetml" in content_type:
        return True, "xlsx export available"

    try:
        payload = response.json()
    except Exception:
        preview = response.text[:120].replace("\n", " ")
        return False, f"unexpected response: {preview}"

    data = payload.get("data") if isinstance(payload, dict) else None
    if data:
        return True, f"json data available ({type(data).__name__})"

    if isinstance(payload, dict) and "error" in payload:
        return False, f"api error: {payload['error']}"
    return False, "json returned empty data"


def main() -> int:
    ensure_runtime_directories()
    logger, log_path = configure_logger("validate_cckp_rx1day_timeseries_url")
    logger.info("Log file: %s", log_path)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    failures = 0
    sample_scenario = "ssp245" if "ssp245" in SCENARIOS else SCENARIOS[0]

    try:
        for statistic in REQUESTED_STATISTICS:
            url_json = build_url(
                base_url=BASE_URL,
                statistic=statistic,
                scenario=sample_scenario,
                output_format="json",
                year_range=YEAR_RANGE_LABEL,
                year_range_token=YEAR_RANGE_TOKEN,
                statistic_token=STATISTIC_TOKEN,
                scenario_token=SCENARIO_TOKEN,
            )
            url_xlsx = build_url(
                base_url=BASE_URL,
                statistic=statistic,
                scenario=sample_scenario,
                output_format="xlsx",
                year_range=YEAR_RANGE_LABEL,
                year_range_token=YEAR_RANGE_TOKEN,
                statistic_token=STATISTIC_TOKEN,
                scenario_token=SCENARIO_TOKEN,
            )

            for fmt, url in (("json", url_json), ("xlsx", url_xlsx)):
                logger.info("[CHECK] statistic=%s | scenario=%s | format=%s", statistic, sample_scenario, fmt)
                response = session.get(url, timeout=TIMEOUT)
                ok, detail = inspect_response(response)
                logger.info("status=%s | content_type=%s | detail=%s", response.status_code, response.headers.get("content-type"), detail)
                logger.info("url=%s", url)
                if not ok:
                    failures += 1
    finally:
        session.close()

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
