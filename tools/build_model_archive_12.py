from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_summary.csv"
BAYES_CANDIDATES_PATH = ROOT / "4 贝叶斯分析" / "results" / "bayes_candidate_models.csv"
STRICT_TOP8_PATH = ROOT / "2 固定效应模型" / "results" / "strict_top8_archive" / "strict_top8_models.csv"
OUTPUT_DIR = ROOT / "2 固定效应模型" / "results" / "model_archive_12"

YEAR_FE_LABEL = "Province: No / Year: Yes"

SELECTED_YEAR_FE_ROLE_META = {
    "main_model": {
        "bayes_role": "curated_main_story",
        "role_label": "主模型",
        "selection_rule": "SYS_08952-prioritized + Year FE + story-first candidate",
        "reason": (
            "SYS_08952 is prioritized as the final paper's main model because it is a compact "
            "high-ranking Year FE specification with positive and significant R1xday, AMC, TA, and NOx signals."
        ),
    },
    "robust_low_vif": {
        "bayes_role": "curated_low_vif_reference",
        "role_label": "稳健性模型 1",
        "selection_rule": "hand-picked + Year FE + lower-collinearity reference",
        "reason": "Used to test whether the core story depends on a more collinear variable bundle.",
    },
    "robust_systematic": {
        "bayes_role": "systematic_amplification_1",
        "role_label": "稳健性模型 2",
        "selection_rule": "hand-picked + Year FE + systematic bridge candidate",
        "reason": "Used to show the result does not rely only on manually curated bundles.",
    },
    "robust_systematic_2": {
        "bayes_role": "systematic_amplification_2",
        "role_label": "稳健性模型 3",
        "selection_rule": "hand-picked + Year FE + adjacent systematic candidate",
        "reason": "Used as a neighboring high-performing Year FE specification for final comparison.",
    },
}

SUMMARY_ENRICH_COLS = [
    "model_id",
    "scheme_id",
    "scheme_source",
    "fe_label",
    "variables",
    "performance_rank",
    "performance_score",
    "coef_R1xday",
    "p_R1xday",
    "coef_AMC",
    "p_AMC",
    "temperature_proxy",
    "coef_temperature_proxy",
    "p_temperature_proxy",
    "pollution_proxy",
    "coef_pollution_proxy",
    "p_pollution_proxy",
    "r2_model",
    "max_vif_z",
]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def as_float(value: object) -> float:
    return float(value) if pd.notna(value) else float("nan")


def build_summary_lookup(summary_df: pd.DataFrame) -> pd.DataFrame:
    year_fe = summary_df[summary_df["fe_label"].eq(YEAR_FE_LABEL)].copy()
    if year_fe.empty:
        raise RuntimeError(f"Could not find required FE label: {YEAR_FE_LABEL}")
    return year_fe[SUMMARY_ENRICH_COLS].drop_duplicates("model_id")


def enrich_selected_row(
    row: pd.Series,
    *,
    role_id: str,
    group_rank: int,
) -> dict[str, object]:
    meta = SELECTED_YEAR_FE_ROLE_META[role_id]
    return {
        "archive_rank": 0,
        "archive_group": "selected_yearfe4",
        "archive_group_label": "手选 Year FE 4 模型",
        "group_rank": group_rank,
        "role_id": role_id,
        "role_label": str(meta["role_label"]),
        "selection_rule": str(meta["selection_rule"]),
        "reason": str(meta["reason"]),
        "model_id": str(row["model_id"]),
        "scheme_id": str(row["scheme_id"]),
        "scheme_source": str(row["scheme_source"]),
        "fe_label": str(row["fe_label"]),
        "variables": str(row["variables"]),
        "performance_rank": int(row["performance_rank"]),
        "performance_score": float(row["performance_score"]),
        "coef_R1xday": float(row["coef_R1xday"]),
        "p_R1xday": float(row["p_R1xday"]),
        "coef_AMC": float(row["coef_AMC"]),
        "p_AMC": float(row["p_AMC"]),
        "temperature_proxy": str(row.get("temperature_proxy", "")),
        "coef_temperature_proxy": as_float(row.get("coef_temperature_proxy")),
        "p_temperature_proxy": as_float(row.get("p_temperature_proxy")),
        "coef_TA": as_float(row.get("coef_temperature_proxy")),
        "p_TA": as_float(row.get("p_temperature_proxy")),
        "pollution_proxy": str(row.get("pollution_proxy", "")),
        "coef_pollution_proxy": as_float(row.get("coef_pollution_proxy")),
        "p_pollution_proxy": as_float(row.get("p_pollution_proxy")),
        "r2_model": float(row["r2_model"]),
        "max_vif_z": float(row["max_vif_z"]),
    }


def build_selected_yearfe4(summary_df: pd.DataFrame, bayes_candidates_df: pd.DataFrame) -> list[dict[str, object]]:
    summary_lookup = build_summary_lookup(summary_df)
    summary_enrich = summary_lookup[
        [
            "model_id",
            "temperature_proxy",
            "coef_temperature_proxy",
            "p_temperature_proxy",
            "pollution_proxy",
            "coef_pollution_proxy",
            "p_pollution_proxy",
            "r2_model",
        ]
    ]
    candidate_pool = bayes_candidates_df[
        bayes_candidates_df["fe_label"].eq(YEAR_FE_LABEL)
    ].copy()
    candidate_pool = candidate_pool.merge(
        summary_enrich,
        on="model_id",
        how="left",
        validate="one_to_one",
    )
    if candidate_pool.empty:
        raise RuntimeError("No Year FE Bayesian candidate pool was found for the 12-model archive.")

    chosen_rows: list[tuple[str, pd.Series]] = []
    used_model_ids: set[str] = set()
    for role_id, meta in SELECTED_YEAR_FE_ROLE_META.items():
        bayes_role = str(meta["bayes_role"])
        pick = candidate_pool[candidate_pool["bayes_role"].eq(bayes_role)].copy()
        pick = pick.sort_values(["performance_rank", "performance_score"], ascending=[True, False])
        if pick.empty:
            continue
        row = pick.iloc[0]
        model_id = str(row["model_id"])
        if model_id in used_model_ids:
            continue
        chosen_rows.append((role_id, row))
        used_model_ids.add(model_id)

    if len(chosen_rows) < 4:
        fallback = candidate_pool[~candidate_pool["model_id"].isin(used_model_ids)].copy()
        fallback = fallback.sort_values(["performance_rank", "performance_score"], ascending=[True, False])
        remaining_role_ids = [role_id for role_id in SELECTED_YEAR_FE_ROLE_META if role_id not in {role for role, _ in chosen_rows}]
        for role_id, (_, row) in zip(remaining_role_ids, fallback.iterrows()):
            chosen_rows.append((role_id, row))
            used_model_ids.add(str(row["model_id"]))
            if len(chosen_rows) == 4:
                break

    if len(chosen_rows) < 4:
        raise RuntimeError("Failed to build four Year FE selected models for the archive.")

    rows = [
        enrich_selected_row(row, role_id=role_id, group_rank=index)
        for index, (role_id, row) in enumerate(chosen_rows, start=1)
    ]
    rows.sort(key=lambda item: (item["r2_model"], -item["performance_rank"]), reverse=True)
    for group_rank, row in enumerate(rows, start=1):
        row["group_rank"] = group_rank
    return rows


def build_strict_screened8(summary_df: pd.DataFrame, strict_df: pd.DataFrame) -> list[dict[str, object]]:
    summary_lookup = build_summary_lookup(summary_df)
    strict_df = strict_df.merge(
        summary_lookup[
            [
                "model_id",
                "temperature_proxy",
                "coef_temperature_proxy",
                "p_temperature_proxy",
                "pollution_proxy",
                "coef_pollution_proxy",
                "p_pollution_proxy",
            ]
        ],
        on="model_id",
        how="left",
        validate="one_to_one",
    )
    strict_df = strict_df.sort_values(["r2_model", "performance_rank"], ascending=[False, True]).reset_index(drop=True)

    rows: list[dict[str, object]] = []
    for index, row in enumerate(strict_df.to_dict(orient="records"), start=1):
        role_id = str(row["role_id"])
        if role_id == "main_model":
            role_id = "strict_main_model"
        rows.append(
            {
                "archive_rank": 0,
                "archive_group": "strict_screened8",
                "archive_group_label": "严筛强相关 8 模型",
                "group_rank": index,
                "role_id": role_id,
                "role_label": str(row["role_label"]),
                "selection_rule": str(row["selection_rule"]),
                "reason": str(row["reason"]),
                "model_id": str(row["model_id"]),
                "scheme_id": str(row["scheme_id"]),
                "scheme_source": str(row["scheme_source"]),
                "fe_label": str(row["fe_label"]),
                "variables": str(row["variables"]),
                "performance_rank": int(row["performance_rank"]),
                "performance_score": float(row["performance_score"]),
                "coef_R1xday": float(row["coef_R1xday"]),
                "p_R1xday": float(row["p_R1xday"]),
                "coef_AMC": float(row["coef_AMC"]),
                "p_AMC": float(row["p_AMC"]),
                "temperature_proxy": str(row.get("temperature_proxy", "")),
                "coef_temperature_proxy": as_float(row.get("coef_temperature_proxy")),
                "p_temperature_proxy": as_float(row.get("p_temperature_proxy")),
                "coef_TA": as_float(row.get("coef_TA")),
                "p_TA": as_float(row.get("p_TA")),
                "pollution_proxy": str(row.get("pollution_proxy", "")),
                "coef_pollution_proxy": as_float(row.get("coef_pollution_proxy")),
                "p_pollution_proxy": as_float(row.get("p_pollution_proxy")),
                "r2_model": float(row["r2_model"]),
                "max_vif_z": float(row["max_vif_z"]),
            }
        )
    return rows


def build_markdown(df: pd.DataFrame) -> str:
    overview = [
        "# 12-Model Archive",
        "",
        "- archived models: 12",
        f"- selected Year FE models: {int((df['archive_group'] == 'selected_yearfe4').sum())}",
        f"- strict screened models: {int((df['archive_group'] == 'strict_screened8').sum())}",
        f"- fixed FE for hand-picked models: {YEAR_FE_LABEL}",
        "- ordering: ranked by r2_model (descending) for final comparison.",
        "",
    ]
    table_cols = [
        "archive_rank",
        "archive_group_label",
        "role_label",
        "scheme_id",
        "fe_label",
        "performance_rank",
        "coef_R1xday",
        "p_R1xday",
        "coef_AMC",
        "p_AMC",
        "temperature_proxy",
        "coef_temperature_proxy",
        "p_temperature_proxy",
        "r2_model",
        "max_vif_z",
    ]
    return "\n".join(overview) + df[table_cols].to_markdown(index=False)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_df = read_csv(SUMMARY_PATH)
    bayes_candidates_df = read_csv(BAYES_CANDIDATES_PATH)
    strict_df = read_csv(STRICT_TOP8_PATH)

    selected_rows = build_selected_yearfe4(summary_df, bayes_candidates_df)
    strict_rows = build_strict_screened8(summary_df, strict_df)

    archive_df = pd.DataFrame([*selected_rows, *strict_rows])
    archive_df = archive_df.sort_values(["r2_model", "performance_rank"], ascending=[False, True]).reset_index(drop=True)
    archive_df["archive_rank"] = archive_df.index + 1

    csv_path = OUTPUT_DIR / "selected_models.csv"
    json_path = OUTPUT_DIR / "selected_models.json"
    md_path = OUTPUT_DIR / "selected_models.md"

    archive_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(
        json.dumps(archive_df.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(build_markdown(archive_df), encoding="utf-8")

    print(f"Wrote 12-model archive to {csv_path}")


if __name__ == "__main__":
    main()
