from __future__ import annotations

import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "public_dashboards" / "variable-group-deep-dive"
OUTPUT_HTML = OUTPUT_DIR / "index.html"
DATA_DIR = OUTPUT_DIR / "data"

SELECTED_MODELS_PATH = ROOT / "2 固定效应模型" / "results" / "model_archive_12" / "selected_models.csv"
FE_SUMMARY_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_summary.csv"
FE_COEF_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_coefficients.csv"
FE_VIF_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_vif.csv"

BAYES_PRIMARY_DIR = ROOT / "4 贝叶斯分析" / "results" / "model_summaries"
BAYES_BACKUP_DIR = (
    ROOT
    / "4 贝叶斯分析"
    / "results"
    / "backups"
    / "model_summaries_pre_strict_top8_20260423-010048"
)
BAYES_BRIDGE_NAME = "focus_variant_bridge_summary.csv"
BAYES_DIAGNOSTIC_NAME = "combined_diagnostics.csv"

COUNTERFACTUAL_PATH = ROOT / "5 反事实推演" / "results" / "AMR_AGG" / "counterfactual_outputs" / "national_overall.csv"
COUNTERFACTUAL_NOTES_PATH = ROOT / "5 反事实推演" / "results" / "AMR_AGG" / "selection_and_writeup_notes.md"

FUTURE_2050_PATH = ROOT / "6 未来情景分析" / "results" / "baseline_mode_compare" / "scenario_summary_2050_compare.csv"
FUTURE_COMPARE_NOTE_PATH = ROOT / "6 未来情景分析" / "results" / "baseline_mode_compare" / "baseline_mode_comparison.md"


COUNTERFACTUAL_SCENARIO_ORDER = [
    "all_climate_to_baseline",
    "r1xday_plus_temperature_to_baseline",
    "r1xday_to_baseline",
    "temperature_to_baseline",
]

FUTURE_SCENARIO_ORDER = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
FUTURE_MODE_ORDER = ["x_driven", "lancet_ets"]

CORE_PREDICTORS = {"R1xday", "抗菌药物使用强度"}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return (
        str(value)
        .replace("\r\n", "\n")
        .replace("\u00a0", " ")
        .replace("\n-", " - ")
        .replace("\n", " ")
        .replace("  ", " ")
        .strip()
    )


def split_variables(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [item.strip() for item in text.split("|") if item and item.strip()]


def as_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def as_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    return int(value)


def rank_desc(series: pd.Series) -> pd.Series:
    return series.rank(method="min", ascending=False).astype(int)


def rank_asc(series: pd.Series) -> pd.Series:
    return series.rank(method="min", ascending=True).astype(int)


def normalize(series: pd.Series, *, inverse: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    if values.isna().all():
        out = pd.Series(0.0, index=values.index)
    else:
        low = float(values.min())
        high = float(values.max())
        if math.isclose(low, high):
            out = pd.Series(1.0, index=values.index)
        else:
            out = (values - low) / (high - low)
    return 1.0 - out if inverse else out


def mitigation_fraction(best_case: float | None, worst_case: float | None) -> float | None:
    if best_case is None or worst_case is None:
        return None
    if abs(worst_case) < 1e-9:
        return None
    return (worst_case - best_case) / abs(worst_case)


def monotonicity_score(values: list[float | None]) -> float:
    usable = [value for value in values if value is not None]
    if len(usable) < 2:
        return 0.0
    checks = []
    for left, right in zip(usable[:-1], usable[1:]):
        checks.append(1.0 if right >= left else 0.0)
    return float(sum(checks) / len(checks)) if checks else 0.0


def merge_with_backup(
    primary_path: Path,
    backup_path: Path,
    selected_model_ids: set[str],
    dedupe_keys: list[str],
) -> tuple[pd.DataFrame, dict[str, str]]:
    primary = read_csv(primary_path) if primary_path.exists() else pd.DataFrame()
    backup = read_csv(backup_path) if backup_path.exists() else pd.DataFrame()

    source_map: dict[str, str] = {}
    if not primary.empty and "model_id" in primary.columns:
        for model_id in primary["model_id"].dropna().astype(str).unique():
            source_map[model_id] = "current_focus"

    missing = selected_model_ids - set(source_map)
    extra = pd.DataFrame()
    if missing and not backup.empty and "model_id" in backup.columns:
        extra = backup[backup["model_id"].astype(str).isin(missing)].copy()
        for model_id in extra["model_id"].dropna().astype(str).unique():
            source_map[model_id] = "backup_focus"

    frames = [frame for frame in (primary, extra) if not frame.empty]
    if not frames:
        return pd.DataFrame(), source_map
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(dedupe_keys, keep="first").reset_index(drop=True)
    return merged, source_map


def build_bayes_diagnostic_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "model_id",
                "variant_id",
                "variant_label",
                "max_rhat",
                "min_ess_bulk",
                "min_ess_tail",
                "share_rhat_gt_1_01",
            ]
        )
    out = (
        df.groupby(["model_id", "variant_id", "variant_label"], dropna=False)
        .agg(
            max_rhat=("r_hat", "max"),
            min_ess_bulk=("ess_bulk", "min"),
            min_ess_tail=("ess_tail", "min"),
            share_rhat_gt_1_01=("r_hat", lambda s: float((pd.to_numeric(s, errors="coerce") > 1.01).mean())),
        )
        .reset_index()
    )
    return out


def pick_bridge_variant(model_variants: list[dict[str, Any]], variant_id: str) -> dict[str, Any] | None:
    for item in model_variants:
        if item["variant_id"] == variant_id:
            return item
    return None


def build_score_frame(
    selected_df: pd.DataFrame,
    bayes_variant_lookup: dict[str, list[dict[str, Any]]],
    bayes_source_map: dict[str, str],
    counterfactual_lookup: dict[str, list[dict[str, Any]]],
    future_lookup: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in selected_df.to_dict(orient="records"):
        model_id = str(row["model_id"])
        variants = bayes_variant_lookup.get(model_id, [])
        year_add = pick_bridge_variant(variants, "year_only_additive") or {}
        year_amp = pick_bridge_variant(variants, "year_only_amplification") or {}
        prov_amp = pick_bridge_variant(variants, "province_only_amplification") or {}

        cf_records = {item["scenario_id"]: item for item in counterfactual_lookup.get(model_id, [])}
        future_modes = future_lookup.get(model_id, {})
        xd = future_modes.get("x_driven", {})
        le = future_modes.get("lancet_ets", {})

        x585 = as_float(((xd.get("ssp585") or {}).get("median")))
        x126 = as_float(((xd.get("ssp126") or {}).get("median")))
        l585 = as_float(((le.get("ssp585") or {}).get("median")))
        l126 = as_float(((le.get("ssp126") or {}).get("median")))

        monotonic_x = monotonicity_score([as_float(((xd.get(s) or {}).get("median"))) for s in FUTURE_SCENARIO_ORDER])
        monotonic_l = monotonicity_score([as_float(((le.get(s) or {}).get("median"))) for s in FUTURE_SCENARIO_ORDER])

        rows.append(
            {
                "model_id": model_id,
                "scheme_id": str(row["scheme_id"]),
                "role_id": str(row["role_id"]),
                "archive_group": str(row["archive_group"]),
                "scheme_source": str(row["scheme_source"]),
                "r2_model": float(row["r2_model"]),
                "performance_rank": int(row["performance_rank"]),
                "max_vif_z": float(row["max_vif_z"]),
                "n_vars": len(split_variables(row["variables"])),
                "bayes_year_r1_prob": as_float(year_add.get("main_R1xday_prob_gt_0")),
                "bayes_year_amc_prob": as_float(year_add.get("main_AMC_prob_gt_0")),
                "bayes_year_amp_inter_prob": as_float(year_amp.get("interaction_R1xday_x_AMC_prob_gt_0")),
                "bayes_prov_amp_inter_prob": as_float(prov_amp.get("interaction_R1xday_x_AMC_prob_gt_0")),
                "bayes_max_rhat": as_float(max((item.get("diagnostics") or {}).get("max_rhat") or float("nan") for item in variants)) if variants else None,
                "bayes_min_ess_bulk": as_float(min((item.get("diagnostics") or {}).get("min_ess_bulk") or float("inf") for item in variants)) if variants else None,
                "counterfactual_all": as_float((cf_records.get("all_climate_to_baseline") or {}).get("actual_minus_counterfactual_mean")),
                "counterfactual_r1": as_float((cf_records.get("r1xday_to_baseline") or {}).get("actual_minus_counterfactual_mean")),
                "counterfactual_temp": as_float((cf_records.get("temperature_to_baseline") or {}).get("actual_minus_counterfactual_mean")),
                "counterfactual_r1temp": as_float((cf_records.get("r1xday_plus_temperature_to_baseline") or {}).get("actual_minus_counterfactual_mean")),
                "future_xdriven_585": x585,
                "future_xdriven_126": x126,
                "future_lancet_585": l585,
                "future_lancet_126": l126,
                "future_monotonic_x": monotonic_x,
                "future_monotonic_l": monotonic_l,
                "bridge_continuity": 1.0 if bayes_source_map.get(model_id) == "current_focus" else 0.78,
                "shortlist_bonus": 1.0 if str(row["archive_group"]) == "selected_yearfe4" else 0.45,
                "curated_bonus": 1.0 if str(row["scheme_source"]) == "curated" else 0.72,
            }
        )

    score_df = pd.DataFrame(rows)
    score_df["fit_score"] = 0.75 * normalize(score_df["r2_model"]) + 0.25 * normalize(
        score_df["performance_rank"], inverse=True
    )

    year_main = (
        score_df["bayes_year_r1_prob"].fillna(0)
        + score_df["bayes_year_amc_prob"].fillna(0)
    ) / 2
    interaction = (
        0.6 * score_df["bayes_prov_amp_inter_prob"].fillna(0)
        + 0.4 * score_df["bayes_year_amp_inter_prob"].fillna(0)
    )
    diagnostics = (
        0.5 * normalize(score_df["bayes_max_rhat"].fillna(score_df["bayes_max_rhat"].max()), inverse=True)
        + 0.5 * normalize(score_df["bayes_min_ess_bulk"].fillna(score_df["bayes_min_ess_bulk"].min()))
    )
    score_df["bayes_score"] = 0.5 * year_main + 0.25 * interaction + 0.25 * diagnostics

    score_df["counterfactual_score"] = (
        0.45 * normalize(score_df["counterfactual_all"].fillna(score_df["counterfactual_all"].min()))
        + 0.20 * normalize(score_df["counterfactual_r1"].fillna(score_df["counterfactual_r1"].min()))
        + 0.15 * normalize(score_df["counterfactual_temp"].fillna(score_df["counterfactual_temp"].min()))
        + 0.20 * normalize(score_df["counterfactual_r1temp"].fillna(score_df["counterfactual_r1temp"].min()))
    )

    future_x585 = pd.to_numeric(score_df["future_xdriven_585"], errors="coerce")
    future_x126 = pd.to_numeric(score_df["future_xdriven_126"], errors="coerce")
    future_l585 = pd.to_numeric(score_df["future_lancet_585"], errors="coerce")
    future_l126 = pd.to_numeric(score_df["future_lancet_126"], errors="coerce")
    mitigation_x = future_x585 - future_x126
    mitigation_l = future_l585 - future_l126
    score_df["future_score"] = (
        0.30 * normalize(future_x585.fillna(future_x585.min()))
        + 0.20 * normalize(mitigation_x.fillna(mitigation_x.min()))
        + 0.20 * normalize(future_l585.fillna(future_l585.min()))
        + 0.10 * normalize(mitigation_l.fillna(mitigation_l.min()))
        + 0.10 * score_df["future_monotonic_x"].fillna(0)
        + 0.10 * score_df["future_monotonic_l"].fillna(0)
    )

    clarity = (
        0.35 * normalize(score_df["max_vif_z"], inverse=True)
        + 0.20 * normalize(score_df["n_vars"], inverse=True)
        + 0.20 * score_df["curated_bonus"]
        + 0.25 * score_df["bridge_continuity"]
    )
    score_df["story_score"] = (
        0.35 * score_df["shortlist_bonus"]
        + 0.20 * clarity
        + 0.15 * year_main
        + 0.15 * normalize(score_df["counterfactual_all"].fillna(score_df["counterfactual_all"].min()))
        + 0.15 * score_df["bridge_continuity"]
    )
    score_df["evidence_score"] = (
        0.35 * score_df["fit_score"]
        + 0.25 * score_df["bayes_score"]
        + 0.20 * score_df["counterfactual_score"]
        + 0.20 * score_df["future_score"]
    )
    score_df["paper_balance_score"] = 0.60 * score_df["evidence_score"] + 0.40 * score_df["story_score"]

    score_df["r2_rank"] = rank_desc(score_df["r2_model"])
    score_df["paper_rank"] = rank_desc(score_df["paper_balance_score"])
    score_df["evidence_rank"] = rank_desc(score_df["evidence_score"])
    score_df["story_rank"] = rank_desc(score_df["story_score"])
    score_df["interaction_rank"] = rank_desc(
        (score_df["bayes_prov_amp_inter_prob"].fillna(0) + score_df["bayes_year_amp_inter_prob"].fillna(0)) / 2
    )
    return score_df


def build_strengths(model: dict[str, Any], overview: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    if model["flags"].get("paper_leader"):
        strengths.append("当前最适合作为论文主模型的平衡解：统计证据、故事完整性和写作连续性最均衡。")
    if model["flags"].get("highest_r2"):
        strengths.append("12 个候选里 R² 最高，适合作为纯拟合最强的参考上限。")
    if model["scores"]["evidence_rank"] <= 2:
        strengths.append("证据总分位居前列，说明 FE、Bayes、反事实和未来情景几条线的方向较一致。")
    if model["bayes"].get("year_only_main_prob_text"):
        strengths.append(model["bayes"]["year_only_main_prob_text"])
    if model["counterfactual"].get("headline_text"):
        strengths.append(model["counterfactual"]["headline_text"])
    if model["future"].get("headline_text"):
        strengths.append(model["future"]["headline_text"])
    if not strengths:
        strengths.append("这组模型没有明显短板，适合作为补充稳健性或备选主规格。")
    return strengths[:5]


def build_caveats(model: dict[str, Any]) -> list[str]:
    caveats: list[str] = []
    if model["fe"]["max_vif_z"] is not None and model["fe"]["max_vif_z"] > 2.5:
        caveats.append("共线性压力偏高，正文写作时需要强调这是一组故事导向的主线规格。")
    if model["bayes"]["diagnostics_overall"]["max_rhat"] is not None and model["bayes"]["diagnostics_overall"]["max_rhat"] > 1.01:
        caveats.append("贝叶斯链收敛边界略紧，最好在附录里补一句诊断说明。")
    if model["bayes"]["source"] == "backup_focus":
        caveats.append("贝叶斯桥接结果来自备份焦点汇总，而不是当前主汇总；正文引用时需注明来源一致性。")
    if model["future"]["x_driven"]["monotonicity"] < 0.75:
        caveats.append("未来情景路径并非完全单调，说明 rx1day 情景差异仍受基线与偏差校正方式影响。")
    if model["archive_group"] == "strict_screened8":
        caveats.append("这是一组严筛强相关规格，统计表现强，但变量组合的叙事可解释性略弱于手选 Year FE 组。")
    if not caveats:
        caveats.append("目前没有特别突出的硬伤，更像是主规格或第一备选之间的细节权衡。")
    return caveats[:4]


def build_english_story(model: dict[str, Any]) -> list[str]:
    cf_all = model["counterfactual"]["scenario_map"].get("all_climate_to_baseline")
    x585 = model["future"]["x_driven"]["scenarios"].get("ssp585")
    x126 = model["future"]["x_driven"]["scenarios"].get("ssp126")
    mitigation = mitigation_fraction(
        as_float((x126 or {}).get("median")),
        as_float((x585 or {}).get("median")),
    )

    lines = [
        (
            f"In the selected Year FE specification ({model['scheme_id']}), "
            f"R1xday remains positive (beta={model['fe']['coef_R1xday']:+.3f}, p={model['fe']['p_R1xday']:.4f}) "
            f"alongside AMC (beta={model['fe']['coef_AMC']:+.3f}, p={model['fe']['p_AMC']:.4f})."
        )
    ]

    year_add = model["bayes"]["variant_map"].get("year_only_additive")
    if year_add:
        lines.append(
            (
                "Bayesian year-only inference keeps the two core effects positive "
                f"(P(beta_R1xday>0)={year_add['main_R1xday_prob_gt_0']:.3f}; "
                f"P(beta_AMC>0)={year_add['main_AMC_prob_gt_0']:.3f})."
            )
        )

    if cf_all:
        lines.append(
            (
                "Counterfactual rollback of all climate variables to the baseline period lowers the national AMR signal by "
                f"{cf_all['actual_minus_counterfactual_mean']:+.3f} on average "
                f"({cf_all['relative_change_pct_mean']:+.1f}% relative change)."
            )
        )

    if x585 and x126:
        mitigation_text = f"{100 * mitigation:.1f}%" if mitigation is not None else "n/a"
        lines.append(
            (
                "By 2050 under the x-driven baseline, the climate-driven increment reaches "
                f"{x585['median']:+.3f} under SSP5-8.5 versus {x126['median']:+.3f} under SSP1-2.6, "
                f"implying a mitigation of {mitigation_text}."
            )
        )

    lines.append(
        "This specification is therefore useful not only for fit comparison, but also for writing a coherent causal and scenario-based narrative."
    )
    return lines


def build_payload() -> dict[str, Any]:
    selected = read_csv(SELECTED_MODELS_PATH).sort_values(["r2_model", "performance_rank"], ascending=[False, True])
    selected_model_ids = set(selected["model_id"].astype(str))

    fe_summary = read_csv(FE_SUMMARY_PATH)
    coefficients = read_csv(FE_COEF_PATH)
    vifs = read_csv(FE_VIF_PATH)
    counterfactual = read_csv(COUNTERFACTUAL_PATH)
    future_2050 = read_csv(FUTURE_2050_PATH)

    bridge_df, bridge_source_map = merge_with_backup(
        BAYES_PRIMARY_DIR / BAYES_BRIDGE_NAME,
        BAYES_BACKUP_DIR / BAYES_BRIDGE_NAME,
        selected_model_ids,
        ["model_id", "variant_id"],
    )
    diagnostics_df, _ = merge_with_backup(
        BAYES_PRIMARY_DIR / BAYES_DIAGNOSTIC_NAME,
        BAYES_BACKUP_DIR / BAYES_DIAGNOSTIC_NAME,
        selected_model_ids,
        ["model_id", "variant_id", "parameter"],
    )
    diagnostic_summary = build_bayes_diagnostic_summary(diagnostics_df)

    coefficients = coefficients[coefficients["model_id"].astype(str).isin(selected_model_ids)].copy()
    vifs = vifs[vifs["model_id"].astype(str).isin(selected_model_ids)].copy()
    counterfactual = counterfactual[counterfactual["model_id"].astype(str).isin(selected_model_ids)].copy()
    future_2050 = future_2050[future_2050["model_id"].astype(str).isin(selected_model_ids)].copy()

    coefficient_lookup: dict[str, list[dict[str, Any]]] = {}
    for model_id, group in coefficients.groupby("model_id", dropna=False):
        rows = []
        for row in group.to_dict(orient="records"):
            rows.append(
                {
                    "predictor": clean_text(row["predictor"]),
                    "coef": as_float(row["coef"]),
                    "p_value": as_float(row["p_value"]),
                    "ci_low": as_float(row["ci_low"]),
                    "ci_high": as_float(row["ci_high"]),
                    "is_core": clean_text(row["predictor"]) in CORE_PREDICTORS,
                }
            )
        coefficient_lookup[str(model_id)] = rows

    vif_lookup: dict[str, list[dict[str, Any]]] = {}
    for model_id, group in vifs.groupby("model_id", dropna=False):
        rows = []
        for row in group.sort_values("vif_z", ascending=False).to_dict(orient="records"):
            rows.append(
                {
                    "predictor": clean_text(row["predictor"]),
                    "vif_raw": as_float(row["vif_raw"]),
                    "vif_z": as_float(row["vif_z"]),
                    "abs_diff": as_float(row["abs_diff"]),
                }
            )
        vif_lookup[str(model_id)] = rows

    diagnostic_lookup = {
        (str(row["model_id"]), str(row["variant_id"])): {
            "max_rhat": as_float(row["max_rhat"]),
            "min_ess_bulk": as_float(row["min_ess_bulk"]),
            "min_ess_tail": as_float(row["min_ess_tail"]),
            "share_rhat_gt_1_01": as_float(row["share_rhat_gt_1_01"]),
        }
        for row in diagnostic_summary.to_dict(orient="records")
    }

    bayes_lookup: dict[str, list[dict[str, Any]]] = {}
    for model_id, group in bridge_df.groupby("model_id", dropna=False):
        items: list[dict[str, Any]] = []
        for row in group.sort_values("variant_id").to_dict(orient="records"):
            item = {
                "variant_id": clean_text(row["variant_id"]),
                "variant_label": clean_text(row["variant_label"]),
                "main_R1xday_posterior_mean": as_float(row["main_R1xday_posterior_mean"]),
                "main_R1xday_prob_gt_0": as_float(row["main_R1xday_prob_gt_0"]),
                "main_AMC_posterior_mean": as_float(row["main_AMC_posterior_mean"]),
                "main_AMC_prob_gt_0": as_float(row["main_AMC_prob_gt_0"]),
                "interaction_R1xday_x_AMC_posterior_mean": as_float(row["interaction_R1xday_x_AMC_posterior_mean"]),
                "interaction_R1xday_x_AMC_prob_gt_0": as_float(row["interaction_R1xday_x_AMC_prob_gt_0"]),
                "diagnostics": diagnostic_lookup.get((str(model_id), clean_text(row["variant_id"])), {}),
            }
            items.append(item)
        bayes_lookup[str(model_id)] = items

    counterfactual_lookup: dict[str, list[dict[str, Any]]] = {}
    for model_id, group in counterfactual.groupby("model_id", dropna=False):
        items: list[dict[str, Any]] = []
        for row in group.to_dict(orient="records"):
            items.append(
                {
                    "scenario_id": clean_text(row["scenario_id"]),
                    "scenario_label": clean_text(row["scenario_label"]),
                    "actual_minus_counterfactual_mean": as_float(row["actual_minus_counterfactual_mean"]),
                    "relative_change_pct_mean": as_float(row["relative_change_pct_mean"]),
                }
            )
        items.sort(key=lambda item: COUNTERFACTUAL_SCENARIO_ORDER.index(item["scenario_id"]) if item["scenario_id"] in COUNTERFACTUAL_SCENARIO_ORDER else 99)
        counterfactual_lookup[str(model_id)] = items

    future_lookup: dict[str, dict[str, Any]] = {}
    for model_id, group in future_2050.groupby("model_id", dropna=False):
        model_modes: dict[str, Any] = {}
        for mode, mode_group in group.groupby("baseline_mode", dropna=False):
            scenarios: dict[str, Any] = {}
            for scenario_id, scenario_group in mode_group.groupby("scenario_id", dropna=False):
                entry: dict[str, Any] = {
                    "scenario_id": clean_text(scenario_id),
                    "scenario_label": clean_text(scenario_group.iloc[0]["scenario_label"]),
                    "median": None,
                    "p10": None,
                    "p90": None,
                }
                for row in scenario_group.to_dict(orient="records"):
                    statistic = clean_text(row["statistic"])
                    key = "median" if statistic in {"median", "baseline"} else statistic
                    if key in entry:
                        entry[key] = as_float(row["delta_vs_baseline_at_end"])
                scenarios[clean_text(scenario_id)] = entry
            model_modes[clean_text(mode)] = {
                "baseline_mode": clean_text(mode),
                "baseline_mode_label": clean_text(mode_group.iloc[0]["baseline_mode_label"]),
                "scenarios": scenarios,
                "monotonicity": monotonicity_score([as_float((scenarios.get(s) or {}).get("median")) for s in FUTURE_SCENARIO_ORDER]),
            }
        future_lookup[str(model_id)] = model_modes

    score_df = build_score_frame(selected, bayes_lookup, bridge_source_map, counterfactual_lookup, future_lookup)
    score_lookup = {str(row["model_id"]): row for row in score_df.to_dict(orient="records")}

    paper_pool = score_df[score_df["archive_group"].eq("selected_yearfe4")].copy()
    paper_pool = paper_pool.sort_values("paper_balance_score", ascending=False).reset_index(drop=True)
    paper_top_score = float(paper_pool.iloc[0]["paper_balance_score"])
    paper_near_tie = paper_pool[paper_pool["paper_balance_score"] >= paper_top_score - 0.01].copy()
    paper_leader = (
        paper_near_tie.sort_values(["bridge_continuity", "r2_model"], ascending=[False, False]).iloc[0]["model_id"]
    )
    r2_leader = score_df.sort_values("r2_model", ascending=False).iloc[0]["model_id"]
    strict_leader = (
        score_df[score_df["archive_group"].eq("strict_screened8")]
        .sort_values("evidence_score", ascending=False)
        .iloc[0]["model_id"]
    )
    amplification_leader = (
        paper_pool[paper_pool["model_id"].ne(paper_leader)]
        .sort_values(["paper_balance_score", "bayes_prov_amp_inter_prob", "r2_model"], ascending=[False, False, False])
        .iloc[0]["model_id"]
    )

    shortlist_sorted = paper_pool.sort_values(
        ["paper_balance_score", "bridge_continuity", "r2_model"], ascending=[False, False, False]
    ).reset_index(drop=True)
    shortlist_ids = [paper_leader] + [
        str(model_id) for model_id in shortlist_sorted["model_id"] if str(model_id) != str(paper_leader)
    ]
    shortlist_rank_map = {model_id: index for index, model_id in enumerate(shortlist_ids, start=1)}
    strict_order = (
        score_df[score_df["archive_group"].eq("strict_screened8")]
        .sort_values(["evidence_score", "r2_model"], ascending=[False, False])
        .reset_index(drop=True)
    )
    strict_rank_map = {str(model_id): index for index, model_id in enumerate(strict_order["model_id"], start=1)}

    comparison_rows: list[dict[str, Any]] = []
    model_records: list[dict[str, Any]] = []

    for row in selected.to_dict(orient="records"):
        model_id = str(row["model_id"])
        score_row = score_lookup[model_id]
        variables = split_variables(row["variables"])
        coef_rows = coefficient_lookup.get(model_id, [])
        vif_rows = vif_lookup.get(model_id, [])
        bayes_variants = bayes_lookup.get(model_id, [])
        year_add = pick_bridge_variant(bayes_variants, "year_only_additive")
        year_amp = pick_bridge_variant(bayes_variants, "year_only_amplification")
        prov_amp = pick_bridge_variant(bayes_variants, "province_only_amplification")
        cf_items = counterfactual_lookup.get(model_id, [])
        cf_map = {item["scenario_id"]: item for item in cf_items}

        bayes_diag_overall = {
            "max_rhat": as_float(max((item.get("diagnostics") or {}).get("max_rhat") or float("nan") for item in bayes_variants)) if bayes_variants else None,
            "min_ess_bulk": as_float(min((item.get("diagnostics") or {}).get("min_ess_bulk") or float("inf") for item in bayes_variants)) if bayes_variants else None,
        }

        x_mode = future_lookup.get(model_id, {}).get("x_driven", {"scenarios": {}, "monotonicity": 0.0, "baseline_mode_label": "X-driven baseline"})
        l_mode = future_lookup.get(model_id, {}).get("lancet_ets", {"scenarios": {}, "monotonicity": 0.0, "baseline_mode_label": "Lancet-like ETS baseline"})

        x585 = as_float((x_mode["scenarios"].get("ssp585") or {}).get("median"))
        x126 = as_float((x_mode["scenarios"].get("ssp126") or {}).get("median"))
        l585 = as_float((l_mode["scenarios"].get("ssp585") or {}).get("median"))
        l126 = as_float((l_mode["scenarios"].get("ssp126") or {}).get("median"))
        x_mitigation = mitigation_fraction(x126, x585)
        l_mitigation = mitigation_fraction(l126, l585)

        year_prob_text = None
        if year_add:
            year_prob_text = (
                "Bayes year-only 主效应稳定："
                f"P(beta_R1xday>0)={year_add['main_R1xday_prob_gt_0']:.3f}，"
                f"P(beta_AMC>0)={year_add['main_AMC_prob_gt_0']:.3f}。"
            )

        cf_headline = None
        if cf_map.get("all_climate_to_baseline"):
            cf_all = cf_map["all_climate_to_baseline"]
            cf_headline = (
                "把全部气候变量回拨到基准期后，全国平均 AMR 指标下降 "
                f"{cf_all['actual_minus_counterfactual_mean']:+.3f}"
                f"（{cf_all['relative_change_pct_mean']:+.1f}%）。"
            )

        future_headline = None
        if x585 is not None and x126 is not None:
            mitigation_text = f"{100 * x_mitigation:.1f}%" if x_mitigation is not None else "n/a"
            future_headline = (
                "2050 年 x-driven 基线下，SSP5-8.5 的气候增量为 "
                f"{x585:+.3f}，SSP1-2.6 为 {x126:+.3f}，"
                f"相对可缓解 {mitigation_text}。"
            )

        variant_map = {item["variant_id"]: item for item in bayes_variants}

        model_record: dict[str, Any] = {
            "model_id": model_id,
            "scheme_id": str(row["scheme_id"]),
            "scheme_source": str(row["scheme_source"]),
            "role_id": str(row["role_id"]),
            "role_label": str(row["role_label"]),
            "archive_group": str(row["archive_group"]),
            "archive_group_label": str(row["archive_group_label"]),
            "group_rank": int(row["group_rank"]),
            "variables": variables,
            "flags": {
                "paper_leader": model_id == paper_leader,
                "highest_r2": model_id == r2_leader,
                "strict_evidence_leader": model_id == strict_leader,
                "amplification_alt": model_id == amplification_leader,
            },
            "scores": {
                "fit_score": as_float(score_row["fit_score"]),
                "bayes_score": as_float(score_row["bayes_score"]),
                "counterfactual_score": as_float(score_row["counterfactual_score"]),
                "future_score": as_float(score_row["future_score"]),
                "story_score": as_float(score_row["story_score"]),
                "evidence_score": as_float(score_row["evidence_score"]),
                "paper_balance_score": as_float(score_row["paper_balance_score"]),
                "paper_rank": int(score_row["paper_rank"]),
                "evidence_rank": int(score_row["evidence_rank"]),
                "story_rank": int(score_row["story_rank"]),
                "r2_rank": int(score_row["r2_rank"]),
                "shortlist_rank": shortlist_rank_map.get(model_id),
                "strict_group_rank": strict_rank_map.get(model_id),
            },
            "fe": {
                "fe_label": str(row["fe_label"]),
                "r2_model": as_float(row["r2_model"]),
                "performance_rank": as_int(row["performance_rank"]),
                "performance_score": as_float(row["performance_score"]),
                "coef_R1xday": as_float(row["coef_R1xday"]),
                "p_R1xday": as_float(row["p_R1xday"]),
                "coef_AMC": as_float(row["coef_AMC"]),
                "p_AMC": as_float(row["p_AMC"]),
                "temperature_proxy": clean_text(row["temperature_proxy"]),
                "coef_temperature_proxy": as_float(row["coef_temperature_proxy"]),
                "p_temperature_proxy": as_float(row["p_temperature_proxy"]),
                "pollution_proxy": clean_text(row["pollution_proxy"]),
                "coef_pollution_proxy": as_float(row["coef_pollution_proxy"]),
                "p_pollution_proxy": as_float(row["p_pollution_proxy"]),
                "max_vif_z": as_float(row["max_vif_z"]),
                "coefficients": coef_rows,
                "vif_rows": vif_rows,
            },
            "bayes": {
                "source": bridge_source_map.get(model_id, "missing"),
                "variant_map": variant_map,
                "variants": bayes_variants,
                "diagnostics_overall": bayes_diag_overall,
                "year_only_main_prob_text": year_prob_text,
            },
            "counterfactual": {
                "scenarios": cf_items,
                "scenario_map": cf_map,
                "headline_text": cf_headline,
            },
            "future": {
                "x_driven": {
                    "label": x_mode["baseline_mode_label"],
                    "scenarios": x_mode["scenarios"],
                    "monotonicity": x_mode["monotonicity"],
                    "mitigation_pct": x_mitigation,
                },
                "lancet_ets": {
                    "label": l_mode["baseline_mode_label"],
                    "scenarios": l_mode["scenarios"],
                    "monotonicity": l_mode["monotonicity"],
                    "mitigation_pct": l_mitigation,
                },
                "headline_text": future_headline,
            },
        }

        model_record["strengths"] = build_strengths(model_record, {})
        model_record["caveats"] = build_caveats(model_record)
        model_record["english_story"] = build_english_story(model_record)

        model_records.append(model_record)
        comparison_rows.append(
            {
                "model_id": model_id,
                "scheme_id": model_record["scheme_id"],
                "role_label": model_record["role_label"],
                "group_label": model_record["archive_group_label"],
                "r2_rank": model_record["scores"]["r2_rank"],
                "paper_rank": model_record["scores"]["paper_rank"],
                "evidence_rank": model_record["scores"]["evidence_rank"],
                "paper_balance_score": model_record["scores"]["paper_balance_score"],
                "evidence_score": model_record["scores"]["evidence_score"],
                "story_score": model_record["scores"]["story_score"],
                "r2_model": model_record["fe"]["r2_model"],
                "counterfactual_all": as_float((cf_map.get("all_climate_to_baseline") or {}).get("actual_minus_counterfactual_mean")),
                "future_xdriven_585": x585,
                "future_xdriven_126": x126,
                "bayes_year_r1_prob": as_float((year_add or {}).get("main_R1xday_prob_gt_0")),
                "bayes_year_amc_prob": as_float((year_add or {}).get("main_AMC_prob_gt_0")),
                "bayes_amp_prob": as_float((prov_amp or {}).get("interaction_R1xday_x_AMC_prob_gt_0")),
                "flag_text": (
                    "Paper-ready"
                    if model_id == paper_leader
                    else "Best R²"
                    if model_id == r2_leader
                    else "Strict evidence"
                    if model_id == strict_leader
                    else "Amplification alt"
                    if model_id == amplification_leader
                    else ""
                ),
            }
        )

    comparison_rows.sort(key=lambda item: (item["r2_rank"], item["paper_rank"]))

    overview = {
        "paper_leader": paper_leader,
        "r2_leader": r2_leader,
        "strict_leader": strict_leader,
        "amplification_leader": amplification_leader,
        "selected_count": int(selected.shape[0]),
        "yearfe_count": int(selected["archive_group"].eq("selected_yearfe4").sum()),
        "strict_count": int(selected["archive_group"].eq("strict_screened8").sum()),
        "build_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "counterfactual_note_excerpt": COUNTERFACTUAL_NOTES_PATH.read_text(encoding="utf-8").splitlines()[:10]
        if COUNTERFACTUAL_NOTES_PATH.exists()
        else [],
        "future_note_excerpt": FUTURE_COMPARE_NOTE_PATH.read_text(encoding="utf-8").splitlines()[:10]
        if FUTURE_COMPARE_NOTE_PATH.exists()
        else [],
    }

    return {
        "overview": overview,
        "models": model_records,
        "comparison_rows": comparison_rows,
    }


def render_html(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    build_time = clean_text(payload["overview"]["build_time"])
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Final Model Decision</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Fira+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root{
      --bg:#f4f2eb;
      --panel:#fffdf8;
      --panel-strong:#f0ece2;
      --ink:#151515;
      --muted:#66645f;
      --line:#ddd6c9;
      --accent:#c14d35;
      --accent-soft:#f2d4cb;
      --teal:#145d56;
      --teal-soft:#cfe7e0;
      --gold:#a87412;
      --gold-soft:#f0dfb9;
      --shadow:0 18px 48px rgba(21,21,21,.08);
      --radius:22px;
      --mono:"Fira Code", monospace;
      --sans:"Fira Sans", sans-serif;
    }
    *{box-sizing:border-box}
    html{scroll-behavior:smooth}
    body{
      margin:0;
      font-family:var(--sans);
      color:var(--ink);
      background:
        radial-gradient(circle at top left, rgba(193,77,53,.14), transparent 28%),
        radial-gradient(circle at top right, rgba(20,93,86,.12), transparent 24%),
        linear-gradient(180deg, #f7f5ef 0%, var(--bg) 100%);
    }
    a{color:inherit}
    .page{max-width:1500px;margin:0 auto;padding:24px 20px 56px}
    .hero{
      display:grid;
      grid-template-columns:1.2fr .8fr;
      gap:18px;
      margin-bottom:18px;
    }
    .hero-card,.panel,.selector-panel{
      background:rgba(255,253,248,.92);
      border:1px solid rgba(221,214,201,.92);
      border-radius:var(--radius);
      box-shadow:var(--shadow);
      backdrop-filter: blur(10px);
    }
    .hero-copy{
      padding:28px 30px;
      min-height:260px;
      display:flex;
      flex-direction:column;
      justify-content:space-between;
    }
    .eyebrow{
      display:inline-flex;
      align-items:center;
      gap:8px;
      padding:8px 12px;
      border-radius:999px;
      background:var(--panel-strong);
      color:var(--muted);
      font-size:12px;
      letter-spacing:.08em;
      text-transform:uppercase;
      font-weight:700;
    }
    h1{
      margin:14px 0 10px;
      font-size:clamp(2rem,4vw,4.4rem);
      line-height:.96;
      letter-spacing:-.05em;
      font-weight:800;
      max-width:10ch;
    }
    .hero-copy p{
      margin:0;
      max-width:78ch;
      color:var(--muted);
      font-size:15px;
      line-height:1.65;
    }
    .hero-metrics{
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:12px;
      margin-top:22px;
    }
    .hero-metrics .mini{
      padding:14px 16px;
      border-radius:18px;
      background:var(--panel-strong);
    }
    .mini strong{
      display:block;
      font-size:28px;
      line-height:1;
      margin-bottom:6px;
    }
    .mini span{
      color:var(--muted);
      font-size:13px;
      line-height:1.4;
    }
    .hero-side{
      padding:24px;
      display:grid;
      gap:12px;
    }
    .rec-card{
      padding:16px 18px;
      border-radius:18px;
      border:1px solid transparent;
      background:var(--panel-strong);
      cursor:pointer;
      transition:transform .18s ease, border-color .18s ease, background .18s ease;
    }
    .rec-card:hover{transform:translateY(-2px);border-color:var(--ink)}
    .rec-card.primary{background:linear-gradient(135deg, rgba(193,77,53,.16), rgba(255,253,248,.92))}
    .rec-card strong{display:block;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
    .rec-card h3{margin:0 0 6px;font-size:24px;line-height:1.02}
    .rec-card p{margin:0;color:var(--muted);font-size:13px;line-height:1.45}
    .workspace{
      display:grid;
      grid-template-columns:340px minmax(0,1fr);
      gap:18px;
      align-items:start;
    }
    .selector-panel{
      padding:18px;
      position:sticky;
      top:16px;
    }
    .selector-panel h2,.detail-hero h2{margin:10px 0 8px;font-size:28px;line-height:1.02}
    .selector-panel p{margin:0 0 16px;color:var(--muted);font-size:14px;line-height:1.55}
    .selector-list{display:grid;gap:10px}
    .selector-btn{
      border:1px solid var(--line);
      background:var(--panel);
      border-radius:18px;
      padding:14px 14px 12px;
      text-align:left;
      cursor:pointer;
      transition:all .18s ease;
    }
    .selector-btn:hover,.selector-btn.active{border-color:var(--ink);transform:translateY(-1px)}
    .selector-btn.active{background:linear-gradient(135deg, rgba(193,77,53,.13), rgba(255,253,248,.96))}
    .selector-row{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
    .selector-rank{
      font-family:var(--mono);
      font-size:12px;
      color:var(--muted);
    }
    .selector-name{font-size:16px;font-weight:700;line-height:1.2}
    .selector-meta{margin-top:6px;color:var(--muted);font-size:12px;line-height:1.45}
    .pill{
      display:inline-flex;
      align-items:center;
      padding:5px 10px;
      border-radius:999px;
      font-size:11px;
      line-height:1;
      font-weight:700;
      letter-spacing:.04em;
      text-transform:uppercase;
      font-family:var(--mono);
    }
    .pill.red{background:var(--accent-soft);color:#7f2819}
    .pill.teal{background:var(--teal-soft);color:#0b4e46}
    .pill.gold{background:var(--gold-soft);color:#77540f}
    .pill.ink{background:#ece8df;color:#2e2d29}
    .detail-stack{display:grid;gap:18px}
    .panel{padding:22px}
    .detail-hero{
      display:grid;
      grid-template-columns:1fr auto;
      gap:16px;
      align-items:start;
    }
    .detail-hero p{margin:0;color:var(--muted);font-size:15px;line-height:1.6}
    .hero-badges{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
    .hero-subgrid{
      display:grid;
      grid-template-columns:repeat(5,1fr);
      gap:12px;
      margin-top:18px;
    }
    .stat-card{
      padding:14px 16px;
      border-radius:18px;
      background:var(--panel-strong);
    }
    .stat-card small{
      display:block;
      color:var(--muted);
      font-size:12px;
      margin-bottom:8px;
      text-transform:uppercase;
      letter-spacing:.06em;
    }
    .stat-card strong{display:block;font-size:24px;line-height:1.05}
    .stat-card span{display:block;margin-top:6px;color:var(--muted);font-size:12px;line-height:1.45}
    .score-grid,.two-col{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:18px;
    }
    .score-card{
      padding:16px;
      border-radius:18px;
      background:var(--panel-strong);
    }
    .score-bar{
      height:10px;
      border-radius:999px;
      background:#ddd7cd;
      overflow:hidden;
      margin:10px 0 8px;
    }
    .score-bar span{
      display:block;
      height:100%;
      border-radius:999px;
      background:linear-gradient(90deg, var(--teal), var(--accent));
    }
    .score-row{display:flex;justify-content:space-between;gap:8px;font-family:var(--mono);font-size:12px;color:var(--muted)}
    .section-head{
      display:flex;
      justify-content:space-between;
      gap:16px;
      align-items:flex-end;
      margin-bottom:18px;
    }
    .section-head h3{margin:0;font-size:28px;line-height:1.02}
    .section-head p{margin:0;color:var(--muted);max-width:78ch;font-size:14px;line-height:1.6}
    .bullet-list{
      display:grid;
      gap:10px;
      padding:0;
      margin:0;
      list-style:none;
    }
    .bullet-list li{
      padding:14px 16px;
      border-radius:16px;
      background:var(--panel-strong);
      line-height:1.6;
      color:var(--ink);
    }
    .variant-grid,.scenario-grid,.future-grid{
      display:grid;
      gap:12px;
    }
    .variant-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
    .scenario-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
    .future-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
    .variant-card,.scenario-card,.future-card{
      padding:16px;
      border-radius:18px;
      border:1px solid var(--line);
      background:var(--panel);
    }
    .variant-card h4,.scenario-card h4,.future-card h4{
      margin:0 0 10px;
      font-size:18px;
      line-height:1.15;
    }
    .subtle{color:var(--muted);font-size:12px;line-height:1.5}
    .prob-item{margin-top:10px}
    .prob-label{display:flex;justify-content:space-between;gap:10px;font-family:var(--mono);font-size:12px}
    .prob-track{height:8px;border-radius:999px;background:#dfd9ce;overflow:hidden;margin-top:6px}
    .prob-track span{display:block;height:100%;background:linear-gradient(90deg, var(--gold), var(--accent));border-radius:999px}
    table{
      width:100%;
      border-collapse:collapse;
      border-radius:18px;
      overflow:hidden;
      border:1px solid var(--line);
      background:var(--panel);
    }
    th,td{
      padding:12px 12px;
      border-bottom:1px solid var(--line);
      font-size:13px;
      text-align:left;
      vertical-align:top;
    }
    th{
      background:#f0ebe1;
      font-size:11px;
      letter-spacing:.06em;
      text-transform:uppercase;
      color:var(--muted);
    }
    tr.active-row{background:rgba(193,77,53,.08)}
    .bar-rows{display:grid;gap:10px}
    .bar-row{display:grid;grid-template-columns:180px 1fr 84px;gap:12px;align-items:center}
    .bar-label{font-size:12px;color:var(--muted);line-height:1.35}
    .bar-track{height:12px;border-radius:999px;background:#dfd9ce;position:relative;overflow:hidden}
    .bar-track span{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg, var(--teal), var(--accent));border-radius:999px}
    .bar-value{font-family:var(--mono);font-size:12px;text-align:right}
    .chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
    .chip{
      padding:7px 10px;
      border-radius:999px;
      background:var(--panel-strong);
      font-size:12px;
      line-height:1.1;
      border:1px solid var(--line);
    }
    .footer{
      margin-top:18px;
      padding:18px 22px;
      border-radius:22px;
      background:#161616;
      color:#f8f6f0;
    }
    .footer a{color:#f8f6f0}
    .footer-links{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
    .footer-links a{
      padding:8px 12px;
      border-radius:999px;
      background:rgba(255,255,255,.08);
      text-decoration:none;
      font-size:12px;
      font-family:var(--mono);
    }
    .mono{font-family:var(--mono)}
    @media (max-width: 1180px){
      .hero,.workspace,.future-grid,.variant-grid,.scenario-grid,.hero-subgrid,.score-grid,.two-col{grid-template-columns:1fr}
      .selector-panel{position:static}
      h1{max-width:none}
      .bar-row{grid-template-columns:1fr}
    }
    @media (prefers-reduced-motion: reduce){
      *,*::before,*::after{animation:none !important;transition:none !important;scroll-behavior:auto !important}
    }
  </style>
</head>
<body>
  <div class="page">
    <header class="hero">
      <section class="hero-card hero-copy">
        <div>
          <span class="eyebrow">Final Model Decision</span>
          <h1>Climate Change Amplifies AMR</h1>
          <p>这不是原来的 4×3 FE 浏览页，而是论文收口阶段的最终模型决策台。页面把 12 个候选模型固定为 <span class="mono">8 个严筛强相关模型 + 4 个手选 Year FE 模型</span>，并把固定效应、贝叶斯桥接、反事实推演、2050 未来情景和写作建议统一放在同一个选择器下，帮助你尽可能稳地选出最后用于正文阐述的主模型。</p>
        </div>
        <div class="hero-metrics" id="heroMetrics"></div>
      </section>
      <aside class="hero-card hero-side" id="recommendationCards"></aside>
    </header>

    <div class="workspace">
      <aside class="selector-panel">
        <span class="eyebrow">Model Pool</span>
        <h2>按 R² 排序的 12 组候选</h2>
        <p>左侧始终按照 <span class="mono">r2_model</span> 排名，方便你先看纯拟合上限，再回到右侧判断哪一个更适合写成论文主故事。</p>
        <div class="selector-list" id="selectorList"></div>
      </aside>

      <main class="detail-stack">
        <section class="panel" id="detailHero"></section>
        <section class="panel" id="writeupPanel"></section>
        <section class="panel" id="scorePanel"></section>
        <section class="panel two-col">
          <div id="fePanel"></div>
          <div id="bayesPanel"></div>
        </section>
        <section class="panel" id="counterfactualPanel"></section>
        <section class="panel" id="futurePanel"></section>
        <section class="panel" id="comparisonPanel"></section>
      </main>
    </div>

    <footer class="footer">
      <div class="eyebrow" style="background:rgba(255,255,255,.08);color:#eae6dd">Source Snapshot</div>
      <p style="margin:14px 0 0;color:#ddd6c8;line-height:1.6">生成时间 __BUILD_TIME__。当前入口聚焦最终选模决策，不替代原有 FE、Bayes、Counterfactual 或 Future dashboards；它只是把这几条证据线重新收拢成一个论文主模型选择页。</p>
      <div class="footer-links">
        <a href="./data/decision_payload.json">decision_payload.json</a>
        <a href="./data/selected_models.csv">selected_models.csv</a>
        <a href="./data/bayes_bridge_merged.csv">bayes_bridge_merged.csv</a>
        <a href="./data/counterfactual_national_overall.csv">counterfactual_national_overall.csv</a>
        <a href="./data/future_2050_compare.csv">future_2050_compare.csv</a>
      </div>
    </footer>
  </div>

  <script>
    const payload = __PAYLOAD__;
    const models = payload.models;
    const comparisonRows = payload.comparison_rows;
    const state = { modelId: payload.overview.paper_leader };

    const fmtNum = (value, digits = 3) => (value === null || Number.isNaN(value)) ? "—" : Number(value).toFixed(digits);
    const fmtSigned = (value, digits = 3) => (value === null || Number.isNaN(value)) ? "—" : `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(digits)}`;
    const fmtPct = (value, digits = 1) => (value === null || Number.isNaN(value)) ? "—" : `${Number(value).toFixed(digits)}%`;
    const fmtScore = (value) => (value === null || Number.isNaN(value)) ? "—" : `${Math.round(Number(value) * 100)}`;
    const pill = (label, tone) => `<span class="pill ${tone}">${label}</span>`;

    function getModel(modelId) {
      return models.find((item) => item.model_id === modelId);
    }

    function scenarioLabel(model, scenarioId) {
      const item = model.counterfactual.scenario_map[scenarioId];
      return item ? item.scenario_label : scenarioId;
    }

    function barRows(items) {
      const usable = items.filter((item) => item.value !== null && !Number.isNaN(item.value));
      const max = usable.length ? Math.max(...usable.map((item) => Math.abs(item.value))) : 0;
      return `
        <div class="bar-rows">
          ${items.map((item) => {
            const width = max > 0 && item.value !== null && !Number.isNaN(item.value) ? `${Math.max(6, Math.abs(item.value) / max * 100)}%` : "0%";
            return `
              <div class="bar-row">
                <div class="bar-label">${item.label}</div>
                <div class="bar-track"><span style="width:${width}"></span></div>
                <div class="bar-value">${item.formatted}</div>
              </div>
            `;
          }).join("")}
        </div>
      `;
    }

    function bayesVariantCard(variant) {
      const interText = variant.interaction_R1xday_x_AMC_prob_gt_0 === null || Number.isNaN(variant.interaction_R1xday_x_AMC_prob_gt_0)
        ? "—"
        : variant.interaction_R1xday_x_AMC_prob_gt_0.toFixed(3);
      const diag = variant.diagnostics || {};
      return `
        <article class="variant-card">
          <h4>${variant.variant_label}</h4>
          <div class="subtle">max R-hat ${fmtNum(diag.max_rhat, 3)} · min bulk ESS ${fmtNum(diag.min_ess_bulk, 0)}</div>
          <div class="prob-item">
            <div class="prob-label"><span>R1xday posterior mean</span><strong>${fmtSigned(variant.main_R1xday_posterior_mean, 3)}</strong></div>
            <div class="prob-track"><span style="width:${(variant.main_R1xday_prob_gt_0 || 0) * 100}%"></span></div>
            <div class="subtle">P(beta&gt;0) = ${fmtNum(variant.main_R1xday_prob_gt_0, 3)}</div>
          </div>
          <div class="prob-item">
            <div class="prob-label"><span>AMC posterior mean</span><strong>${fmtSigned(variant.main_AMC_posterior_mean, 3)}</strong></div>
            <div class="prob-track"><span style="width:${(variant.main_AMC_prob_gt_0 || 0) * 100}%"></span></div>
            <div class="subtle">P(beta&gt;0) = ${fmtNum(variant.main_AMC_prob_gt_0, 3)}</div>
          </div>
          <div class="prob-item">
            <div class="prob-label"><span>Amplification interaction</span><strong>${fmtSigned(variant.interaction_R1xday_x_AMC_posterior_mean, 3)}</strong></div>
            <div class="prob-track"><span style="width:${(variant.interaction_R1xday_x_AMC_prob_gt_0 || 0) * 100}%"></span></div>
            <div class="subtle">P(beta&gt;0) = ${interText}</div>
          </div>
        </article>
      `;
    }

    function renderHeroMetrics() {
      const paper = getModel(payload.overview.paper_leader);
      document.getElementById("heroMetrics").innerHTML = `
        <div class="mini"><strong>${payload.overview.selected_count}</strong><span>候选模型总数</span></div>
        <div class="mini"><strong>${payload.overview.yearfe_count}+${payload.overview.strict_count}</strong><span>手选 Year FE + 严筛强相关</span></div>
        <div class="mini"><strong>${paper ? paper.scheme_id : "—"}</strong><span>当前推荐主模型</span></div>
      `;
    }

    function renderRecommendationCards() {
      const cards = [
        { key: payload.overview.paper_leader, title: "Paper-Ready Primary", desc: "优先推荐写进正文的平衡解。", primary: true },
        { key: payload.overview.r2_leader, title: "Highest R²", desc: "纯拟合上限，适合作为性能标杆。", tone: "gold" },
        { key: payload.overview.strict_leader, title: "Strict Evidence Leader", desc: "严筛组里证据总分最强的模型。", tone: "teal" },
        { key: payload.overview.amplification_leader, title: "Amplification Alternative", desc: "交互放大链最值得保留的替代方案。", tone: "red" },
      ];
      document.getElementById("recommendationCards").innerHTML = cards.map((card) => {
        const model = getModel(card.key);
        if (!model) return "";
        const rankText = card.title === "Paper-Ready Primary"
          ? `手选 Year FE 组内第 #${model.scores.shortlist_rank}`
          : card.title === "Strict Evidence Leader"
          ? `严筛组证据排名 #${model.scores.strict_group_rank}`
          : `R² 排名 #${model.scores.r2_rank}`;
        return `
          <button class="rec-card ${card.primary ? "primary" : ""}" data-model="${model.model_id}">
            <strong>${card.title}</strong>
            <h3>${model.scheme_id}</h3>
            <p>${card.desc} ${rankText}。</p>
          </button>
        `;
      }).join("");
      document.querySelectorAll(".rec-card").forEach((node) => {
        node.addEventListener("click", () => {
          state.modelId = node.dataset.model;
          renderAll();
        });
      });
    }

    function renderSelector() {
      const list = document.getElementById("selectorList");
      list.innerHTML = comparisonRows.map((row) => `
        <button class="selector-btn ${row.model_id === state.modelId ? "active" : ""}" data-model="${row.model_id}">
          <div class="selector-row">
            <div>
              <div class="selector-rank">R² #${row.r2_rank} · Paper #${row.paper_rank}</div>
              <div class="selector-name">${row.scheme_id}</div>
            </div>
            <div>${row.flag_text ? pill(row.flag_text, row.flag_text === "Paper-ready" ? "red" : row.flag_text === "Strict evidence" ? "teal" : "gold") : ""}</div>
          </div>
          <div class="selector-meta">${row.group_label} · ${row.role_label}<br/>R² ${fmtNum(row.r2_model, 3)} · All-climate CF ${fmtSigned(row.counterfactual_all, 3)} · SSP5-8.5 ${fmtSigned(row.future_xdriven_585, 3)}</div>
        </button>
      `).join("");
      list.querySelectorAll(".selector-btn").forEach((node) => {
        node.addEventListener("click", () => {
          state.modelId = node.dataset.model;
          renderAll();
        });
      });
    }

    function renderDetailHero(model) {
      const badges = [];
      if (model.flags.paper_leader) badges.push(pill("Paper-ready primary", "red"));
      if (model.flags.highest_r2) badges.push(pill("Highest R²", "gold"));
      if (model.flags.strict_evidence_leader) badges.push(pill("Strict evidence leader", "teal"));
      if (model.flags.amplification_alt) badges.push(pill("Amplification alt", "ink"));
      badges.push(pill(model.archive_group_label, model.archive_group === "selected_yearfe4" ? "red" : "teal"));
      badges.push(pill(model.bayes.source === "current_focus" ? "Current Bayes bridge" : "Backup Bayes bridge", "ink"));
      document.getElementById("detailHero").innerHTML = `
        <div class="detail-hero">
          <div>
            <div class="hero-badges">${badges.join("")}</div>
            <h2>${model.scheme_id}</h2>
            <p>当前选中的是 <span class="mono">${model.model_id}</span>。它的角色是 <strong>${model.role_label}</strong>，所在组为 <strong>${model.archive_group_label}</strong>。这部分不是只看 FE，而是把 FE、Bayes、Counterfactual、2050 Scenario 和写作可用性合并成一张完整的选模档案。</p>
            <div class="chips">${model.variables.map((item) => `<span class="chip">${item}</span>`).join("")}</div>
          </div>
          <div style="min-width:240px">
            <div class="pill red">${model.archive_group === "selected_yearfe4" ? `Hand-picked #${model.scores.shortlist_rank}` : `Evidence #${model.scores.strict_group_rank || model.scores.evidence_rank}`}</div>
          </div>
        </div>
        <div class="hero-subgrid">
          <div class="stat-card"><small>R²</small><strong>${fmtNum(model.fe.r2_model, 3)}</strong><span>12 组中排名 #${model.scores.r2_rank}</span></div>
          <div class="stat-card"><small>Fit Rank</small><strong>#${model.fe.performance_rank}</strong><span>全模型库 performance_rank</span></div>
          <div class="stat-card"><small>Bayes</small><strong>${fmtScore(model.scores.bayes_score)}</strong><span>Year-only 与 amplification 共同记分</span></div>
          <div class="stat-card"><small>Counterfactual</small><strong>${fmtScore(model.scores.counterfactual_score)}</strong><span>基准期回拨后的全国平均降幅</span></div>
          <div class="stat-card"><small>Future</small><strong>${fmtScore(model.scores.future_score)}</strong><span>2050 SSP 分歧与高排放敏感度</span></div>
        </div>
      `;
    }

    function renderWriteup(model) {
      document.getElementById("writeupPanel").innerHTML = `
        <div class="section-head">
          <div>
            <span class="eyebrow">Abstract Builder</span>
            <h3>可直接拿去写摘要的故事骨架</h3>
            <p>这部分不是最终文稿，而是把当前模型已经给出的 FE、Bayes、Counterfactual、Future 证据拼成英文摘要的可写句式。</p>
          </div>
        </div>
        <div class="two-col">
          <div>
            <h4 style="margin:0 0 12px;font-size:20px">English Scaffold</h4>
            <ul class="bullet-list">${model.english_story.map((item) => `<li>${item}</li>`).join("")}</ul>
          </div>
          <div>
            <h4 style="margin:0 0 12px;font-size:20px">Why Pick / Why Pause</h4>
            <div style="display:grid;gap:14px">
              <div>
                <div class="pill teal">Strengths</div>
                <ul class="bullet-list" style="margin-top:10px">${model.strengths.map((item) => `<li>${item}</li>`).join("")}</ul>
              </div>
              <div>
                <div class="pill gold">Caveats</div>
                <ul class="bullet-list" style="margin-top:10px">${model.caveats.map((item) => `<li>${item}</li>`).join("")}</ul>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    function renderScores(model) {
      const scores = [
        ["Fit", model.scores.fit_score, "R² 与 performance rank 的综合分。"],
        ["Bayesian", model.scores.bayes_score, "核心系数后验概率、交互项支持与诊断稳定性。"],
        ["Counterfactual", model.scores.counterfactual_score, "把气候变量回拨到基准期后，全国平均会下降多少。"],
        ["Future", model.scores.future_score, "2050 SSP5-8.5 的高排放增量与 SSP1-2.6 的可缓解幅度。"],
        ["Story", model.scores.story_score, "是否更适合写成正文主模型，而不只是技术上最强。"],
        ["Paper Balance", model.scores.paper_balance_score, "最终平衡分，用来挑正文主模型。"],
      ];
      document.getElementById("scorePanel").innerHTML = `
        <div class="section-head">
          <div>
            <span class="eyebrow">Decision Scoring</span>
            <h3>不是只按 R² 选，而是按论文主模型适配度选</h3>
            <p>左侧排序仍按 R²，但最终主模型更看重平衡：既要有足够高的拟合和清晰的气候信号，也要能在 Bayes、反事实和未来情景里形成闭环。</p>
          </div>
        </div>
        <div class="score-grid">
          ${scores.map(([title, value, desc]) => `
            <article class="score-card">
              <div class="score-row"><strong>${title}</strong><span>#${title === "Paper Balance" ? (model.archive_group === "selected_yearfe4" ? model.scores.shortlist_rank : model.scores.paper_rank) : title === "Story" ? model.scores.story_rank : title === "Fit" ? model.scores.r2_rank : title === "Bayesian" ? model.scores.evidence_rank : model.scores.paper_rank}</span></div>
              <div class="score-bar"><span style="width:${Math.round((value || 0) * 100)}%"></span></div>
              <div style="font-size:28px;font-weight:800">${fmtScore(value)}</div>
              <div class="subtle" style="margin-top:6px">${desc}</div>
            </article>
          `).join("")}
        </div>
      `;
    }

    function renderFE(model) {
      const coefTable = `
        <table>
          <thead><tr><th>Predictor</th><th>Coef</th><th>p</th><th>95% CI</th></tr></thead>
          <tbody>
            ${model.fe.coefficients.map((row) => `
              <tr>
                <td>${row.is_core ? `<strong>${row.predictor}</strong>` : row.predictor}</td>
                <td>${fmtSigned(row.coef, 3)}</td>
                <td>${fmtNum(row.p_value, 4)}</td>
                <td>${fmtSigned(row.ci_low, 3)} to ${fmtSigned(row.ci_high, 3)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
      const vifTable = `
        <table>
          <thead><tr><th>Predictor</th><th>VIF raw</th><th>VIF z</th><th>|raw-z|</th></tr></thead>
          <tbody>
            ${model.fe.vif_rows.map((row) => `
              <tr>
                <td>${row.predictor}</td>
                <td>${fmtNum(row.vif_raw, 2)}</td>
                <td>${fmtNum(row.vif_z, 2)}</td>
                <td>${fmtNum(row.abs_diff, 2)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
      document.getElementById("fePanel").innerHTML = `
        <div class="section-head">
          <div>
            <span class="eyebrow">FE Line</span>
            <h3>固定效应主线</h3>
            <p>先确认这组模型在传统 FE 口径下是否站得住。这里看的是核心气候变量、AMC、温度代理、污染代理和共线性压力。</p>
          </div>
        </div>
        <ul class="bullet-list" style="margin-bottom:14px">
          <li>R1xday = <strong>${fmtSigned(model.fe.coef_R1xday, 3)}</strong> (p=${fmtNum(model.fe.p_R1xday, 4)})；AMC = <strong>${fmtSigned(model.fe.coef_AMC, 3)}</strong> (p=${fmtNum(model.fe.p_AMC, 4)})。</li>
          <li>温度代理是 <span class="mono">${model.fe.temperature_proxy || "—"}</span>，系数 ${fmtSigned(model.fe.coef_temperature_proxy, 3)}；污染代理是 <span class="mono">${model.fe.pollution_proxy || "—"}</span>，系数 ${fmtSigned(model.fe.coef_pollution_proxy, 3)}。</li>
          <li>最大 VIF z = <strong>${fmtNum(model.fe.max_vif_z, 2)}</strong>；如果明显高于 2.5，正文就要把它写成“主叙事规格”，而不是唯一技术最优规格。</li>
        </ul>
        <div class="score-grid">
          <div>${coefTable}</div>
          <div>${vifTable}</div>
        </div>
      `;
    }

    function renderBayes(model) {
      document.getElementById("bayesPanel").innerHTML = `
        <div class="section-head">
          <div>
            <span class="eyebrow">Bayesian Line</span>
            <h3>贝叶斯桥接与放大效应</h3>
            <p>这里不是简单重复 FE，而是看 year-only / province-only / province+year 三条层级线，判断主效应是否稳定，以及 <span class="mono">R1xday × AMC</span> 的放大证据能否成立。</p>
          </div>
        </div>
        <ul class="bullet-list" style="margin-bottom:14px">
          <li>Bayes 汇总来源：<strong>${model.bayes.source === "current_focus" ? "当前 focus summary" : "backup focus summary"}</strong>。</li>
          <li>整体诊断：max R-hat = <strong>${fmtNum(model.bayes.diagnostics_overall.max_rhat, 3)}</strong>，min bulk ESS = <strong>${fmtNum(model.bayes.diagnostics_overall.min_ess_bulk, 0)}</strong>。</li>
        </ul>
        <div class="variant-grid">
          ${model.bayes.variants.map(bayesVariantCard).join("")}
        </div>
      `;
    }

    function renderCounterfactual(model) {
      const items = model.counterfactual.scenarios.map((item) => ({
        label: item.scenario_label,
        value: item.actual_minus_counterfactual_mean,
        formatted: `${fmtSigned(item.actual_minus_counterfactual_mean, 3)} · ${fmtSigned(item.relative_change_pct_mean, 1)}%`,
      }));
      document.getElementById("counterfactualPanel").innerHTML = `
        <div class="section-head">
          <div>
            <span class="eyebrow">Counterfactual</span>
            <h3>反事实推演</h3>
            <p>同一个模型在不同回拨情景下，现实气候到底把全国 AMR 平均值抬高了多少。这里尤其看 “all climate” 是否稳、R1xday 通道是否单独成立，以及温度回拨是否只是敏感性结果。</p>
          </div>
        </div>
        <div class="scenario-grid">
          ${model.counterfactual.scenarios.map((item) => `
            <article class="scenario-card">
              <h4>${item.scenario_label}</h4>
              <div style="font-size:30px;font-weight:800">${fmtSigned(item.actual_minus_counterfactual_mean, 3)}</div>
              <div class="subtle" style="margin-top:6px">relative change ${fmtSigned(item.relative_change_pct_mean, 1)}%</div>
            </article>
          `).join("")}
        </div>
        <div style="margin-top:16px">
          ${barRows(items)}
        </div>
      `;
    }

    function renderFutureMode(mode) {
      const scenarioItems = ["ssp119","ssp126","ssp245","ssp370","ssp585"].map((key) => {
        const item = mode.scenarios[key];
        return {
          label: item ? item.scenario_label : key,
          value: item ? item.median : null,
          formatted: item ? `${fmtSigned(item.median, 3)} · [${fmtSigned(item.p10, 3)}, ${fmtSigned(item.p90, 3)}]` : "—",
        };
      });
      return `
        <article class="future-card">
          <h4>${mode.label}</h4>
          <div class="subtle">Monotonicity ${fmtNum(mode.monotonicity, 2)} · SSP1-2.6 mitigation ${fmtPct(mode.mitigation_pct !== null && mode.mitigation_pct !== undefined ? mode.mitigation_pct * 100 : null, 1)}</div>
          <div style="margin-top:14px">${barRows(scenarioItems)}</div>
        </article>
      `;
    }

    function renderFuture(model) {
      document.getElementById("futurePanel").innerHTML = `
        <div class="section-head">
          <div>
            <span class="eyebrow">2050 Scenarios</span>
            <h3>未来情景与 SSP 分歧</h3>
            <p>这里看的不是总 AMR 水平，而是“气候驱动增量”本身。重点观察 2050 年 SSP5-8.5 的高排放风险是否明显更高，以及 SSP1-2.6 能减轻多少。</p>
          </div>
        </div>
        <ul class="bullet-list" style="margin-bottom:14px">
          <li>${model.future.headline_text || "当前模型未来情景增量较弱，更适合做稳健性补充而不是未来风险主叙事。"}</li>
          <li>如果两个 baseline mode 都给出同方向结论，说明未来情景判断不只是某一种 baseline 构造方法的产物。</li>
        </ul>
        <div class="future-grid">
          ${renderFutureMode(model.future.x_driven)}
          ${renderFutureMode(model.future.lancet_ets)}
        </div>
      `;
    }

    function renderComparison(model) {
      document.getElementById("comparisonPanel").innerHTML = `
        <div class="section-head">
          <div>
            <span class="eyebrow">Comparison Matrix</span>
            <h3>12 组候选一览</h3>
            <p>表格继续保持按 R² 排名，但把 Paper score、Evidence score、Bayes 年度主效应、反事实 all-climate 和 2050 SSP5-8.5 增量一起放进来，方便你做最后取舍。</p>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>R² Rank</th>
              <th>Model</th>
              <th>Group</th>
              <th>Paper</th>
              <th>Evidence</th>
              <th>R²</th>
              <th>Bayes Year R1</th>
              <th>Bayes Year AMC</th>
              <th>All-Climate CF</th>
              <th>2050 SSP5-8.5</th>
              <th>Flag</th>
            </tr>
          </thead>
          <tbody>
            ${comparisonRows.map((row) => `
              <tr class="${row.model_id === model.model_id ? "active-row" : ""}">
                <td>#${row.r2_rank}</td>
                <td><strong>${row.scheme_id}</strong><br/><span class="subtle">${row.role_label}</span></td>
                <td>${row.group_label}</td>
                <td>#${row.paper_rank} · ${fmtScore(row.paper_balance_score)}</td>
                <td>#${row.evidence_rank} · ${fmtScore(row.evidence_score)}</td>
                <td>${fmtNum(row.r2_model, 3)}</td>
                <td>${fmtNum(row.bayes_year_r1_prob, 3)}</td>
                <td>${fmtNum(row.bayes_year_amc_prob, 3)}</td>
                <td>${fmtSigned(row.counterfactual_all, 3)}</td>
                <td>${fmtSigned(row.future_xdriven_585, 3)}</td>
                <td>${row.flag_text || "—"}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function renderAll() {
      const model = getModel(state.modelId);
      renderHeroMetrics();
      renderRecommendationCards();
      renderSelector();
      renderDetailHero(model);
      renderWriteup(model);
      renderScores(model);
      renderFE(model);
      renderBayes(model);
      renderCounterfactual(model);
      renderFuture(model);
      renderComparison(model);
    }

    renderAll();
  </script>
</body>
</html>
""".replace("__PAYLOAD__", payload_json).replace("__BUILD_TIME__", build_time)


def main() -> None:
    payload = build_payload()

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    write_json(DATA_DIR / "decision_payload.json", payload)
    shutil.copy2(SELECTED_MODELS_PATH, DATA_DIR / "selected_models.csv")

    bridge_df, _ = merge_with_backup(
        BAYES_PRIMARY_DIR / BAYES_BRIDGE_NAME,
        BAYES_BACKUP_DIR / BAYES_BRIDGE_NAME,
        {model["model_id"] for model in payload["models"]},
        ["model_id", "variant_id"],
    )
    bridge_df.to_csv(DATA_DIR / "bayes_bridge_merged.csv", index=False, encoding="utf-8-sig")
    read_csv(COUNTERFACTUAL_PATH).to_csv(DATA_DIR / "counterfactual_national_overall.csv", index=False, encoding="utf-8-sig")
    read_csv(FUTURE_2050_PATH).to_csv(DATA_DIR / "future_2050_compare.csv", index=False, encoding="utf-8-sig")

    OUTPUT_HTML.write_text(render_html(payload), encoding="utf-8")
    print(f"Wrote final model decision dashboard to {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
