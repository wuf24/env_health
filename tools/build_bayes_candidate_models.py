from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_FE_LABEL = "Province: No / Year: Yes"
CURATED_TARGETS = [
    ("方案A_平衡主线组", "curated_main_story"),
    ("方案F_低VIF主线组", "curated_low_vif_reference"),
]
SYSTEMATIC_TARGETS = [
    ("SYS_09556", "systematic_amplification_1"),
    ("SYS_09557", "systematic_amplification_2"),
    ("SYS_01678", "systematic_confirmatory_1"),
    ("SYS_00553", "systematic_confirmatory_2"),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_tables(results_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranking = pd.read_csv(results_dir / "exhaustive_model_ranking.csv")
    catalog = pd.read_csv(results_dir / "exhaustive_scheme_catalog.csv")
    return ranking, catalog


def pick_curated_models(ranking: pd.DataFrame) -> list[dict[str, object]]:
    picked: list[dict[str, object]] = []
    for scheme_id, role in CURATED_TARGETS:
        rows = ranking[
            (ranking["scheme_id"] == scheme_id)
            & (ranking["fe_label"] == DEFAULT_FE_LABEL)
        ].sort_values("performance_rank")
        if rows.empty:
            continue
        row = rows.iloc[0].to_dict()
        row["bayes_role"] = role
        row["why_selected"] = {
            "curated_main_story": "人工主线中最适合承接论文叙事，当前 R1xday 与 AMC 同时为正，且 R1xday 达到 0.05 显著。",
            "curated_low_vif_reference": "人工主线中共线性最低，适合与方案A做稳健性对照。",
        }[role]
        picked.append(row)
    return picked


def pick_systematic_models(ranking: pd.DataFrame) -> list[dict[str, object]]:
    subset = ranking[
        (ranking["scheme_source"] == "systematic")
        & (ranking["fe_label"] == DEFAULT_FE_LABEL)
        & (ranking["core_sig_count_p_lt_0_05"] >= 2)
    ].sort_values(["performance_rank", "max_vif_z"])

    picked: list[dict[str, object]] = []
    for scheme_id, role in SYSTEMATIC_TARGETS:
        rows = subset[subset["scheme_id"] == scheme_id]
        if rows.empty:
            continue
        record = rows.iloc[0].to_dict()
        record["bayes_role"] = role
        record["why_selected"] = {
            "systematic_amplification_1": "Year FE 下双核心同时显著、排名靠前，适合直接测试贝叶斯 amplification 版本。",
            "systematic_amplification_2": "与 SYS_09556 结构接近且双核心仍显著，适合做相邻高分规格的 amplification 对照。",
            "systematic_confirmatory_1": "系统穷举里双核心同时显著、排名靠前，适合证明结论不完全依赖人工选模。",
            "systematic_confirmatory_2": "系统穷举里保留双核心显著，同时更换关键代理变量，适合做 proxy 替换后的确认。",
        }[role]
        picked.append(record)

    if picked:
        return picked

    for idx, (_, row) in enumerate(subset.head(2).iterrows(), start=1):
        record = row.to_dict()
        record["bayes_role"] = f"systematic_confirmatory_{idx}"
        record["why_selected"] = "系统穷举里双核心同时显著、排名靠前，适合证明结论不完全依赖人工选模。"
        picked.append(record)
    return picked


def attach_catalog_fields(
    picked_rows: list[dict[str, object]],
    catalog: pd.DataFrame,
) -> pd.DataFrame:
    if not picked_rows:
        return pd.DataFrame()

    picked = pd.DataFrame(picked_rows)
    merged = picked.merge(
        catalog[["scheme_id", "scheme_note", "n_vars", "variables", "family_selection"]],
        on="scheme_id",
        how="left",
    )
    merged["recommended_bayes_spec"] = (
        "Screen a Bayesian grid aligned to FE: year-only / province-only / province+year, each with additive and amplification versions"
    )
    merged["optional_appendix_spec"] = (
        "Use Mundlak within-between or spatial CAR/BYM2 only as second-round diagnostics after the main grid"
    )
    merged["paper_alignment"] = (
        "Borrow the paper's Bayesian/hierarchical logic while first mirroring the project's three FE scenarios before stricter decomposition."
    )
    merged.insert(0, "bayes_priority", range(1, len(merged) + 1))

    keep_cols = [
        "bayes_priority",
        "bayes_role",
        "model_id",
        "scheme_id",
        "scheme_source",
        "fe_label",
        "performance_rank",
        "performance_score",
        "coef_R1xday",
        "p_R1xday",
        "coef_AMC",
        "p_AMC",
        "max_vif_z",
        "n_vars",
        "variables",
        "family_selection",
        "scheme_note",
        "why_selected",
        "recommended_bayes_spec",
        "optional_appendix_spec",
        "paper_alignment",
    ]
    return merged[keep_cols]


def build_candidates(results_dir: Path) -> pd.DataFrame:
    ranking, catalog = load_tables(results_dir)
    picked_rows = []
    picked_rows.extend(pick_curated_models(ranking))
    picked_rows.extend(pick_systematic_models(ranking))
    return attach_catalog_fields(picked_rows, catalog)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a short list of selected model combinations for Bayesian auxiliary analysis.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=repo_root() / "2 固定效应模型" / "results",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "4 贝叶斯分析" / "results" / "bayes_candidate_models.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates = build_candidates(results_dir=args.results_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(candidates)} candidate models to {args.output}")


if __name__ == "__main__":
    main()
