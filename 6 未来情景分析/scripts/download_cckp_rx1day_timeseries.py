from __future__ import annotations

import argparse
import time
from pathlib import Path

import requests

from cckp_rx1day_timeseries_common import (
    build_output_path,
    build_url,
    configure_logger,
    ensure_runtime_directories,
    find_matching_files,
    validate_downloaded_file,
    validation_notes,
)
from config_cckp_rx1day_timeseries import (
    AREA_CODE,
    BASE_URL,
    OUTPUT_FORMAT,
    OUTDIR,
    REQUESTED_STATISTICS,
    RETRY_TIMES,
    SCENARIOS,
    SCENARIO_TOKEN,
    SLEEP_SECONDS,
    STATISTICS,
    STATISTIC_TOKEN,
    TIMEOUT,
    USER_AGENT,
    YEAR_RANGE_LABEL,
    YEAR_RANGE_TOKEN,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download CCKP China provincial yearly rx1day timeseries files.")
    parser.add_argument("--force", action="store_true", help="Redownload even if a valid local file already exists.")
    parser.add_argument("--dry-run", action="store_true", help="Print URLs and target files without downloading.")
    parser.add_argument(
        "--output-format",
        choices=["xlsx", "json"],
        default=OUTPUT_FORMAT,
        help="Preferred format. When set to xlsx, the script falls back to json automatically.",
    )
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="HTTP timeout in seconds.")
    parser.add_argument("--sleep-seconds", type=float, default=SLEEP_SECONDS, help="Pause between combinations.")
    parser.add_argument("--retry-times", type=int, default=RETRY_TIMES, help="Retry count per format.")
    parser.add_argument(
        "--statistics",
        nargs="+",
        choices=REQUESTED_STATISTICS,
        default=STATISTICS,
        help="Statistics to download. Default excludes currently unavailable items like mean.",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=SCENARIOS,
        default=SCENARIOS,
        help="Scenarios to download.",
    )
    return parser.parse_args()


def preferred_formats(output_format: str) -> list[str]:
    if output_format == "xlsx":
        return ["xlsx", "json"]
    return [output_format]


def selected_combinations(scenarios: list[str], statistics: list[str]) -> list[dict[str, str]]:
    return [{"scenario": scenario, "statistic": statistic} for scenario in scenarios for statistic in statistics]


def cleanup_matching_files(files: list[Path], logger) -> None:
    for path in files:
        if path.exists():
            logger.info("Removing existing file before redownload: %s", path.name)
            path.unlink()


def download_once(
    session: requests.Session,
    url: str,
    target_path: Path,
    timeout: int,
) -> tuple[bool, str]:
    temp_path = target_path.with_name(f"{target_path.stem}.part{target_path.suffix}")
    if temp_path.exists():
        temp_path.unlink()

    try:
        with session.get(url, timeout=timeout, stream=True) as response:
            response.raise_for_status()
            with temp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        handle.write(chunk)
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        return False, f"request failed: {exc}"

    is_valid, detail = validate_downloaded_file(temp_path, extension=target_path.suffix)
    if not is_valid:
        if temp_path.exists():
            temp_path.unlink()
        return False, detail

    temp_path.replace(target_path)
    return True, "ok"


def process_combination(
    session: requests.Session,
    combo: dict[str, str],
    args: argparse.Namespace,
    logger,
) -> str:
    scenario = combo["scenario"]
    statistic = combo["statistic"]
    combo_label = f"{scenario} | {statistic}"
    existing_files = find_matching_files(scenario, statistic, outdir=OUTDIR)

    valid_existing = [path for path in existing_files if validate_downloaded_file(path)[0]]
    if valid_existing and not args.force:
        logger.info("[SKIP] %s -> %s", combo_label, ", ".join(path.name for path in valid_existing))
        return "skipped"

    if existing_files and not valid_existing:
        logger.warning("[RETRY] %s has only invalid local files, removing and downloading again", combo_label)
        cleanup_matching_files(existing_files, logger)

    if args.force and existing_files:
        cleanup_matching_files(existing_files, logger)

    for output_format in preferred_formats(args.output_format):
        url = build_url(
            base_url=BASE_URL,
            statistic=statistic,
            scenario=scenario,
            output_format=output_format,
            year_range=YEAR_RANGE_LABEL,
            year_range_token=YEAR_RANGE_TOKEN,
            statistic_token=STATISTIC_TOKEN,
            scenario_token=SCENARIO_TOKEN,
        )
        target_path = build_output_path(
            scenario=scenario,
            statistic=statistic,
            extension=output_format,
            area_code=AREA_CODE,
            outdir=OUTDIR,
            year_range=YEAR_RANGE_LABEL,
        )

        if args.dry_run:
            logger.info("[DRY-RUN] %s -> %s", combo_label, url)
            logger.info("[DRY-RUN] target: %s", target_path)
            return "dry-run"

        for attempt in range(1, args.retry_times + 1):
            logger.info(
                "[TRY] %s | format=%s | attempt=%s/%s",
                combo_label,
                output_format,
                attempt,
                args.retry_times,
            )
            ok, detail = download_once(session=session, url=url, target_path=target_path, timeout=args.timeout)
            if ok:
                logger.info("[OK] %s -> %s", combo_label, target_path.name)
                return f"downloaded:{output_format}"

            logger.warning("[FAIL] %s | format=%s | %s", combo_label, output_format, detail)
            if attempt < args.retry_times:
                time.sleep(min(5, args.sleep_seconds * attempt))

        logger.warning("[FALLBACK] %s | preferred format %s exhausted", combo_label, output_format)

    logger.error("[GIVE-UP] %s", combo_label)
    return "failed"


def main() -> int:
    args = parse_args()
    ensure_runtime_directories()
    logger, log_path = configure_logger("download_cckp_rx1day_timeseries")
    logger.info("Output directory: %s", OUTDIR)
    logger.info("Log file: %s", log_path)
    logger.info("Preferred format order: %s", " -> ".join(preferred_formats(args.output_format)))
    logger.info("Scenarios: %s", ", ".join(args.scenarios))
    logger.info("Statistics: %s", ", ".join(args.statistics))
    for note in validation_notes():
        logger.info("%s", note)

    summary = {"downloaded": 0, "skipped": 0, "failed": 0, "dry-run": 0}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    try:
        combos = selected_combinations(args.scenarios, args.statistics)
        logger.info("Expected combinations: %s", len(combos))
        for combo in combos:
            status = process_combination(session=session, combo=combo, args=args, logger=logger)
            if status.startswith("downloaded"):
                summary["downloaded"] += 1
            elif status == "skipped":
                summary["skipped"] += 1
            elif status == "dry-run":
                summary["dry-run"] += 1
            else:
                summary["failed"] += 1

            if not args.dry_run:
                time.sleep(args.sleep_seconds)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1
    finally:
        session.close()

    logger.info("Summary: %s", summary)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
