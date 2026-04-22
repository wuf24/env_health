from __future__ import annotations

from collections import defaultdict

import pandas as pd

from cckp_rx1day_common import (
    AREA_CODE,
    OUTDIR,
    build_output_stem,
    combination_key,
    configure_logger,
    ensure_runtime_directories,
    expected_combinations,
    iter_download_files,
    parse_output_filename,
    validate_downloaded_file,
)
from config_cckp_rx1day import LOG_DIR


def main() -> int:
    ensure_runtime_directories()
    logger, log_path = configure_logger("check_cckp_files")
    logger.info("Scanning directory: %s", OUTDIR)
    logger.info("Log file: %s", log_path)

    found: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    unexpected_files: list[str] = []

    for path in iter_download_files(OUTDIR):
        metadata = parse_output_filename(path)
        if metadata is None:
            unexpected_files.append(path.name)
            continue

        valid, detail = validate_downloaded_file(path)
        key = combination_key(
            metadata["scenario"],
            metadata["percentile"],
            metadata["period"],
        )
        found[key].append(
            {
                "file_name": path.name,
                "extension": metadata["extension"].lower(),
                "valid": valid,
                "detail": detail,
            }
        )

    rows: list[dict[str, object]] = []
    missing: list[str] = []
    duplicates: list[str] = []
    invalid: list[str] = []

    for combo in expected_combinations():
        key = combination_key(combo["scenario"], combo["percentile"], combo["period"])
        files = found.get(key, [])
        valid_files = [item for item in files if item["valid"]]

        if not files:
            status = "missing"
            missing.append(build_output_stem(combo["scenario"], combo["percentile"], combo["period"], area_code=AREA_CODE))
        elif len(files) > 1:
            status = "duplicate"
            duplicates.append(", ".join(item["file_name"] for item in files))
        elif not valid_files:
            status = "invalid"
            invalid.append(files[0]["file_name"])
        else:
            status = "ok"

        rows.append(
            {
                "scenario": combo["scenario"],
                "percentile": combo["percentile"],
                "period": combo["period"],
                "status": status,
                "file_count": len(files),
                "extensions": ",".join(sorted({str(item["extension"]) for item in files})),
                "files": " | ".join(item["file_name"] for item in files),
                "validation": " | ".join(f"{item['file_name']}:{item['detail']}" for item in files),
            }
        )

    status_df = pd.DataFrame(rows).sort_values(["scenario", "percentile", "period"]).reset_index(drop=True)
    summary_path = LOG_DIR / "cckp_rx1day_download_status.csv"
    status_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    logger.info("Status summary saved to: %s", summary_path)
    logger.info("Total expected combinations: %s", len(status_df))
    logger.info("OK combinations: %s", int((status_df["status"] == "ok").sum()))
    logger.info("Missing combinations: %s", int((status_df["status"] == "missing").sum()))
    logger.info("Duplicate combinations: %s", int((status_df["status"] == "duplicate").sum()))
    logger.info("Invalid combinations: %s", int((status_df["status"] == "invalid").sum()))

    if missing:
        logger.warning("Missing files:")
        for item in missing:
            logger.warning("  %s", item)

    if duplicates:
        logger.warning("Duplicate files:")
        for item in duplicates:
            logger.warning("  %s", item)

    if invalid:
        logger.warning("Invalid files:")
        for item in invalid:
            logger.warning("  %s", item)

    if unexpected_files:
        logger.warning("Unexpected files:")
        for item in unexpected_files:
            logger.warning("  %s", item)

    has_issue = bool(missing or duplicates or invalid or unexpected_files)
    return 1 if has_issue else 0


if __name__ == "__main__":
    raise SystemExit(main())
