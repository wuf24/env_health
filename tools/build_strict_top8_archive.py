from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from build_results_dashboard import ROOT, build_payload


RESULT_DIR = ROOT / "2 固定效应模型" / "results"
ARCHIVE_DIR = RESULT_DIR / "strict_top8_archive"
ARCHIVE_CSV = ARCHIVE_DIR / "strict_top8_models.csv"
ARCHIVE_JSON = ARCHIVE_DIR / "strict_top8_models.json"
ARCHIVE_MD = ARCHIVE_DIR / "strict_top8_models.md"


def build_archive() -> pd.DataFrame:
    payload = build_payload()
    rows = [row for row in payload["ranking"] if row.get("strict_preset_pass")]
    rows = sorted(rows, key=lambda row: int(row["performance_rank"]))[:8]

    archived_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        role_id = "main_model" if index == 1 else f"strict_top_{index:02d}"
        role_label = "严筛主模型" if index == 1 else f"严筛模型 {index}"
        archived_rows.append(
            {
                "archive_rank": index,
                "role_id": role_id,
                "role_label": role_label,
                "selection_rule": "R1xday / AMC / TA 显著 + PM2.5 + 其他系数不为负",
                "reason": (
                    "作为严筛主模型进入后续分析。"
                    if index == 1
                    else f"作为严筛并列候选 #{index}，用于稳健性与异质性比较。"
                ),
                "model_id": row["model_id"],
                "scheme_id": row["scheme_id"],
                "scheme_source": row["scheme_source"],
                "fe_label": row["fe_label"],
                "variables": " | ".join(row.get("variables_list") or []),
                "performance_rank": row["performance_rank"],
                "performance_score": row["performance_score"],
                "coef_R1xday": row["coef_R1xday"],
                "p_R1xday": row["p_R1xday"],
                "coef_AMC": row["coef_AMC"],
                "p_AMC": row["p_AMC"],
                "coef_TA": row.get("coef_TA"),
                "p_TA": row.get("p_TA"),
                "temperature_proxy": row.get("temperature_proxy"),
                "pollution_proxy": row.get("pollution_proxy"),
                "r2_model": row.get("r2_model"),
                "max_vif_z": row.get("max_vif_z"),
                "other_coefficients_nonnegative": row.get("other_coefficients_nonnegative"),
                "negative_other_predictors": " | ".join(row.get("negative_other_predictors") or []),
                "strict_preset_pass": row.get("strict_preset_pass"),
                "scheme_note": row.get("scheme_note"),
            }
        )

    return pd.DataFrame(archived_rows)


def write_markdown(df: pd.DataFrame) -> None:
    lines = [
        "# Strict Top 8 Archive",
        "",
        "筛选规则：`R1xday`、`AMC`、`TA` 显著，污染代理为 `PM2.5`，且除三者外其他变量系数均不为负。",
        "",
        f"- archived models: {len(df)}",
        f"- source: `{ARCHIVE_CSV.relative_to(ROOT).as_posix()}`",
        "",
    ]
    if not df.empty:
        view = df[
            [
                "archive_rank",
                "role_label",
                "model_id",
                "performance_rank",
                "performance_score",
                "coef_R1xday",
                "p_R1xday",
                "coef_AMC",
                "p_AMC",
                "coef_TA",
                "p_TA",
                "r2_model",
            ]
        ].copy()
        lines.append(view.to_markdown(index=False))
        lines.append("")
    ARCHIVE_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_df = build_archive()
    archive_df.to_csv(ARCHIVE_CSV, index=False, encoding="utf-8-sig")
    ARCHIVE_JSON.write_text(
        json.dumps(archive_df.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(archive_df)
    print(f"Wrote {len(archive_df)} strict models to {ARCHIVE_CSV}")


if __name__ == "__main__":
    main()
