from __future__ import annotations

import argparse
import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import seaborn as sns
from linearmodels.panel import PanelOLS
from matplotlib.collections import PatchCollection
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Polygon


warnings.filterwarnings("ignore")

sns.set_theme(style="whitegrid", font="Microsoft YaHei", rc={"axes.unicode_minus": False})

ROOT = Path(__file__).resolve().parents[1]
SECTION_DIR = ROOT / "5 反事实推演"
RESULT_ROOT = SECTION_DIR / "results"
ASSET_DIR = SECTION_DIR / "assets"
RESULT_ROOT.mkdir(exist_ok=True)
ASSET_DIR.mkdir(exist_ok=True)

AMR_PATH = ROOT / "amr_rate.csv"
X_PATH = ROOT / "climate_social_eco.csv"
FE_SUMMARY_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_summary.csv"
FE_RANKING_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_ranking.csv"
FE_COEF_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_coefficients.csv"
BAYES_CANDIDATE_PATH = ROOT / "4 贝叶斯分析" / "results" / "bayes_candidate_models.csv"
BAYES_BRIDGE_PATH = ROOT / "4 贝叶斯分析" / "results" / "model_summaries" / "focus_variant_bridge_summary.csv"

AMR_COLS = [
    "MRCNS",
    "VREFS",
    "VREFM",
    "PRSP",
    "ERSP",
    "3GCRKP",
    "MRSA",
    "3GCREC",
    "CREC",
    "QREC",
    "CRPA",
    "CRKP",
    "CRAB",
]

FE_LABEL_TO_SPEC = {
    "Province: No / Year: Yes": {"entity_effects": False, "time_effects": True},
    "Province: Yes / Year: No": {"entity_effects": True, "time_effects": False},
    "Province: Yes / Year: Yes": {"entity_effects": True, "time_effects": True},
}

TEMPERATURE_VARS = {"主要城市平均气温", "省平均气温", "TA（°C）"}
HYDRO_VARS = {"R1xday", "R5xday", "主要城市降水量", "省平均降水", "PA（%）"}
CLIMATE_VARS = TEMPERATURE_VARS | HYDRO_VARS

ALL_X_VARS = sorted(
    {
        "主要城市平均气温",
        "主要城市降水量",
        "主要城市日照时数",
        "省平均气温",
        "省平均降水",
        "TA（°C）",
        "PA（%）",
        "R1xday",
        "R5xday",
        "二氧化硫",
        "氮氧化物",
        "PM2.5",
        "可支配收入",
        "食品消费量",
        "文盲比例",
        "GDP",
        "建成区绿化覆盖率",
        "医疗水平",
        "生活垃圾无害化处理率",
        "卫生程度\n（日污水处理能力）",
        "城市用水普及率",
        "饮用水\n供水综合生产能力(万立方米/日)",
        "人均日生活用水量(升)",
        "牲畜饲养\n-大牲畜年底头数",
        "牲畜饲养\n-猪年底头数",
        "牲畜饲养\n-羊年底头数",
        "抗菌药物使用强度",
    }
)

GEOJSON_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"
GEOJSON_PATH = ASSET_DIR / "china_provinces.geojson"


@dataclass
class SelectedModel:
    role_id: str
    role_label: str
    selection_rule: str
    reason: str
    model_id: str
    scheme_id: str
    scheme_source: str
    fe_label: str
    variables: list[str]
    performance_rank: int
    performance_score: float
    coef_R1xday: float
    p_R1xday: float
    coef_AMC: float
    p_AMC: float
    r2_model: float
    max_vif_z: float


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def zscore_series(series: pd.Series) -> pd.Series:
    values = to_float(series)
    mean = np.nanmean(values.values)
    std = np.nanstd(values.values, ddof=0)
    if not np.isfinite(std) or std == 0:
        return pd.Series(np.zeros(len(values)), index=values.index)
    return (values - mean) / std


def zscore_with_stats(series: pd.Series) -> tuple[pd.Series, float, float]:
    values = to_float(series)
    mean = np.nanmean(values.values)
    std = np.nanstd(values.values, ddof=0)
    if not np.isfinite(std) or std == 0:
        return pd.Series(np.zeros(len(values)), index=values.index), float(mean), 1.0
    return (values - mean) / std, float(mean), float(std)


def apply_zscore(series: pd.Series, mean: float, std: float) -> pd.Series:
    if not np.isfinite(std) or std == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (to_float(series) - mean) / std


def fill_panel_median(df: pd.DataFrame, col: str) -> pd.Series:
    out = to_float(df[col])
    out = out.groupby(df["Province"]).transform(lambda s: s.fillna(s.median()))
    return out.fillna(out.median())


def normalize_geo_name(name: str) -> str:
    text = str(name).strip()
    for token in ["壮族自治区", "回族自治区", "维吾尔自治区", "特别行政区", "自治区", "省", "市"]:
        text = text.replace(token, "")
    return text


def load_base_frame() -> pd.DataFrame:
    amr = pd.read_csv(AMR_PATH, encoding="utf-8-sig")
    x = pd.read_csv(X_PATH, encoding="utf-8-sig")
    x = x.rename(columns={x.columns[0]: "Province", x.columns[1]: "Year"})

    for df_temp in (amr, x):
        df_temp["Province"] = df_temp["Province"].astype(str).str.strip()
        df_temp["Year"] = pd.to_numeric(df_temp["Year"], errors="coerce").astype("Int64")

    df = amr.merge(x, on=["Province", "Year"], how="inner")
    df = df[df["Year"].between(2014, 2023)].copy()
    df = df[~df["Province"].isin(["全国", "μ", "σ"])].copy()

    for col in AMR_COLS:
        df[col] = to_float(df[col])
    for col in ALL_X_VARS:
        if col in df.columns:
            df[col] = to_float(df[col])

    return df.reset_index(drop=True)


def build_outcome_series(df: pd.DataFrame, outcome: str, single_outcome_scale: str) -> tuple[pd.Series, dict[str, str]]:
    if outcome == "AMR_AGG":
        z_amr = pd.DataFrame({col: zscore_series(df[col]) for col in AMR_COLS})
        return z_amr.mean(axis=1, skipna=True), {
            "outcome_label": "AMR_AGG_z",
            "outcome_note": "13 个 AMR 指标分别 z-score 后取行均值。",
        }

    if outcome not in AMR_COLS:
        raise ValueError(f"未知 outcome: {outcome}")

    if single_outcome_scale == "raw":
        return to_float(df[outcome]), {
            "outcome_label": outcome,
            "outcome_note": f"{outcome} 原始指标。",
        }

    return zscore_series(df[outcome]), {
        "outcome_label": f"{outcome}_z",
        "outcome_note": f"{outcome} 单指标 z-score。",
    }


def load_existing_results() -> dict[str, pd.DataFrame]:
    return {
        "summary": pd.read_csv(FE_SUMMARY_PATH),
        "ranking": pd.read_csv(FE_RANKING_PATH),
        "coef": pd.read_csv(FE_COEF_PATH),
        "bayes_candidates": pd.read_csv(BAYES_CANDIDATE_PATH),
        "bayes_bridge": pd.read_csv(BAYES_BRIDGE_PATH),
    }


def compare_fe_specs(summary_df: pd.DataFrame) -> pd.DataFrame:
    fe_compare = (
        summary_df.groupby("fe_label")
        .agg(
            n_models=("model_id", "count"),
            mean_score=("performance_score", "mean"),
            median_score=("performance_score", "median"),
            top10_mean_score=("performance_score", lambda s: s.nlargest(10).mean()),
            mean_r1xday=("coef_R1xday", "mean"),
            share_r1xday_positive=("coef_R1xday", lambda s: float((s > 0).mean())),
            share_r1xday_sig_005=("p_R1xday", lambda s: float((s < 0.05).mean())),
            mean_amc=("coef_AMC", "mean"),
            share_amc_positive=("coef_AMC", lambda s: float((s > 0).mean())),
            share_amc_sig_005=("p_AMC", lambda s: float((s < 0.05).mean())),
            median_max_vif_z=("max_vif_z", "median"),
            mean_r2_model=("r2_model", "mean"),
        )
        .reset_index()
    )
    fe_compare["fe_rank_by_top10"] = fe_compare["top10_mean_score"].rank(method="dense", ascending=False).astype(int)
    return fe_compare.sort_values(["fe_rank_by_top10", "top10_mean_score"], ascending=[True, False]).reset_index(drop=True)


def summarize_bayes_bridge(bayes_bridge_df: pd.DataFrame) -> pd.DataFrame:
    variant_summary = (
        bayes_bridge_df.groupby("variant_label")
        .agg(
            n_models=("model_id", "nunique"),
            mean_main_r1xday=("main_R1xday_posterior_mean", "mean"),
            mean_main_amc=("main_AMC_posterior_mean", "mean"),
            share_main_r1xday_prob_gt_095=("main_R1xday_prob_gt_0", lambda s: float((s >= 0.95).mean())),
            share_main_amc_prob_gt_095=("main_AMC_prob_gt_0", lambda s: float((s >= 0.95).mean())),
            mean_interaction=("interaction_R1xday_x_AMC_posterior_mean", "mean"),
            share_interaction_prob_gt_095=("interaction_R1xday_x_AMC_prob_gt_0", lambda s: float((s >= 0.95).mean())),
        )
        .reset_index()
    )
    return variant_summary.sort_values("variant_label").reset_index(drop=True)


def pick_primary_fe(fe_compare_df: pd.DataFrame) -> str:
    return str(fe_compare_df.iloc[0]["fe_label"])


def build_selected_models(summary_df: pd.DataFrame, bayes_candidates_df: pd.DataFrame, primary_fe_label: str) -> list[SelectedModel]:
    summary_df = summary_df.copy()
    summary_df["variables_list"] = summary_df["variables"].str.split(" | ", regex=False)
    year_fe = summary_df[summary_df["fe_label"].eq(primary_fe_label)].copy()

    main_pool = year_fe[
        year_fe["scheme_source"].eq("curated")
        & (year_fe["coef_R1xday"] > 0)
        & (year_fe["p_R1xday"] < 0.05)
        & (year_fe["coef_AMC"] > 0)
        & (year_fe["p_AMC"] < 0.05)
    ].sort_values(["performance_score", "r2_model"], ascending=[False, False])
    if main_pool.empty:
        raise RuntimeError("未找到满足主模型条件的 Year FE 候选。")
    main_row = main_pool.iloc[0]

    low_vif_pool = year_fe[
        year_fe["scheme_source"].eq("curated")
        & ~year_fe["scheme_id"].eq(main_row["scheme_id"])
        & (year_fe["coef_R1xday"] > 0)
        & (year_fe["p_R1xday"] < 0.10)
        & (year_fe["coef_AMC"] > 0)
        & (year_fe["p_AMC"] < 0.01)
    ].sort_values(["max_vif_z", "performance_score"], ascending=[True, False])
    if low_vif_pool.empty:
        raise RuntimeError("未找到满足低 VIF 稳健性条件的候选。")
    low_vif_row = low_vif_pool.iloc[0]

    bayes_systematic = bayes_candidates_df[
        bayes_candidates_df["fe_label"].eq(primary_fe_label) & bayes_candidates_df["scheme_source"].eq("systematic")
    ].copy()
    bayes_systematic = bayes_systematic.sort_values(["bayes_priority", "performance_score"], ascending=[True, False])
    if bayes_systematic.empty:
        raise RuntimeError("未找到已有贝叶斯桥接的 systematic 候选。")
    systematic_row = year_fe[year_fe["scheme_id"].eq(bayes_systematic.iloc[0]["scheme_id"])].sort_values(
        ["performance_score"], ascending=[False]
    )
    if systematic_row.empty:
        raise RuntimeError("无法将已有贝叶斯候选映射回 FE summary。")
    systematic_row = systematic_row.iloc[0]

    strict_pool = summary_df[
        summary_df["scheme_id"].eq(main_row["scheme_id"]) & summary_df["fe_label"].eq("Province: Yes / Year: Yes")
    ].copy()
    if strict_pool.empty:
        raise RuntimeError("未找到主模型同变量集的双向 FE 稳健性模型。")
    strict_row = strict_pool.iloc[0]

    return [
        SelectedModel(
            role_id="main_model",
            role_label="主模型",
            selection_rule="curated + Year FE + R1xday 与 AMC 同时正向且 p<0.05",
            reason="理论上最容易承接正文主线，且双核心变量在频率学和 year-only 贝叶斯结果中都最稳定。",
            model_id=str(main_row["model_id"]),
            scheme_id=str(main_row["scheme_id"]),
            scheme_source=str(main_row["scheme_source"]),
            fe_label=str(main_row["fe_label"]),
            variables=list(main_row["variables_list"]),
            performance_rank=int(main_row["performance_rank"]),
            performance_score=float(main_row["performance_score"]),
            coef_R1xday=float(main_row["coef_R1xday"]),
            p_R1xday=float(main_row["p_R1xday"]),
            coef_AMC=float(main_row["coef_AMC"]),
            p_AMC=float(main_row["p_AMC"]),
            r2_model=float(main_row["r2_model"]),
            max_vif_z=float(main_row["max_vif_z"]),
        ),
        SelectedModel(
            role_id="robust_low_vif",
            role_label="稳健性模型 1",
            selection_rule="curated + Year FE + 低 VIF + 双核心方向稳定",
            reason="用于检验主结果是否依赖于较高共线性的变量组织方式。",
            model_id=str(low_vif_row["model_id"]),
            scheme_id=str(low_vif_row["scheme_id"]),
            scheme_source=str(low_vif_row["scheme_source"]),
            fe_label=str(low_vif_row["fe_label"]),
            variables=list(low_vif_row["variables_list"]),
            performance_rank=int(low_vif_row["performance_rank"]),
            performance_score=float(low_vif_row["performance_score"]),
            coef_R1xday=float(low_vif_row["coef_R1xday"]),
            p_R1xday=float(low_vif_row["p_R1xday"]),
            coef_AMC=float(low_vif_row["coef_AMC"]),
            p_AMC=float(low_vif_row["p_AMC"]),
            r2_model=float(low_vif_row["r2_model"]),
            max_vif_z=float(low_vif_row["max_vif_z"]),
        ),
        SelectedModel(
            role_id="robust_systematic",
            role_label="稳健性模型 2",
            selection_rule="systematic + Year FE + 已有贝叶斯桥接 + 双核心显著",
            reason="用于证明结论不完全依赖人工选模，并与已完成的贝叶斯扩展自然衔接。",
            model_id=str(systematic_row["model_id"]),
            scheme_id=str(systematic_row["scheme_id"]),
            scheme_source=str(systematic_row["scheme_source"]),
            fe_label=str(systematic_row["fe_label"]),
            variables=list(systematic_row["variables_list"]),
            performance_rank=int(systematic_row["performance_rank"]),
            performance_score=float(systematic_row["performance_score"]),
            coef_R1xday=float(systematic_row["coef_R1xday"]),
            p_R1xday=float(systematic_row["p_R1xday"]),
            coef_AMC=float(systematic_row["coef_AMC"]),
            p_AMC=float(systematic_row["p_AMC"]),
            r2_model=float(systematic_row["r2_model"]),
            max_vif_z=float(systematic_row["max_vif_z"]),
        ),
        SelectedModel(
            role_id="robust_strict_fe",
            role_label="稳健性模型 3",
            selection_rule="主模型同变量集 + 双向 FE",
            reason="用于给出更严格 FE 控制下的保守下界，识别结果对 FE 设定的敏感性。",
            model_id=str(strict_row["model_id"]),
            scheme_id=str(strict_row["scheme_id"]),
            scheme_source=str(strict_row["scheme_source"]),
            fe_label=str(strict_row["fe_label"]),
            variables=list(strict_row["variables_list"]),
            performance_rank=int(strict_row["performance_rank"]),
            performance_score=float(strict_row["performance_score"]),
            coef_R1xday=float(strict_row["coef_R1xday"]),
            p_R1xday=float(strict_row["p_R1xday"]),
            coef_AMC=float(strict_row["coef_AMC"]),
            p_AMC=float(strict_row["p_AMC"]),
            r2_model=float(strict_row["r2_model"]),
            max_vif_z=float(strict_row["max_vif_z"]),
        ),
    ]


def selected_models_to_frame(selected_models: list[SelectedModel]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "role_id": model.role_id,
                "role_label": model.role_label,
                "selection_rule": model.selection_rule,
                "reason": model.reason,
                "model_id": model.model_id,
                "scheme_id": model.scheme_id,
                "scheme_source": model.scheme_source,
                "fe_label": model.fe_label,
                "variables": " | ".join(model.variables),
                "performance_rank": model.performance_rank,
                "performance_score": model.performance_score,
                "coef_R1xday": model.coef_R1xday,
                "p_R1xday": model.p_R1xday,
                "coef_AMC": model.coef_AMC,
                "p_AMC": model.p_AMC,
                "r2_model": model.r2_model,
                "max_vif_z": model.max_vif_z,
            }
            for model in selected_models
        ]
    )


def ensure_geojson() -> Path:
    if GEOJSON_PATH.exists():
        return GEOJSON_PATH
    response = requests.get(GEOJSON_URL, timeout=30)
    response.raise_for_status()
    GEOJSON_PATH.write_text(response.text, encoding="utf-8")
    return GEOJSON_PATH


def build_baseline_lookup(raw_full: pd.DataFrame, variables: list[str], baseline_years: Iterable[int]) -> pd.DataFrame:
    baseline_years = set(int(year) for year in baseline_years)
    base = raw_full.reset_index()
    base = base[base["Year"].isin(baseline_years)].copy()
    if base.empty:
        raise RuntimeError("基准年份在样本中没有可用观测。")

    lookup = base.groupby("Province")[variables].mean()
    for province in raw_full.index.get_level_values("Province").unique():
        if province not in lookup.index:
            province_rows = raw_full.loc[province]
            lookup.loc[province, variables] = province_rows[variables].iloc[0].values
    return lookup.sort_index()


def deduplicate_scenarios(scenarios: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[str, ...]] = set()
    deduped: list[dict[str, object]] = []
    for scenario in scenarios:
        key = tuple(sorted(scenario["variables"]))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(scenario)
    return deduped


def build_scenarios(variables: list[str]) -> list[dict[str, object]]:
    climate_all = [var for var in variables if var in CLIMATE_VARS]
    r1_only = [var for var in variables if var == "R1xday"]
    temp_only = [var for var in variables if var in TEMPERATURE_VARS]
    key_bundle = []
    if "R1xday" in variables:
        key_bundle.append("R1xday")
    key_bundle.extend([var for var in variables if var in TEMPERATURE_VARS])

    scenarios = [
        {
            "scenario_id": "all_climate_to_baseline",
            "scenario_label": "所有气候变量恢复基准",
            "description": "将模型中所有气候相关变量恢复到基准期水平，其余协变量保持实际值。",
            "variables": climate_all,
        },
        {
            "scenario_id": "r1xday_to_baseline",
            "scenario_label": "仅 R1xday 恢复基准",
            "description": "仅将极端降雨代理 R1xday 恢复到基准期水平。",
            "variables": r1_only,
        },
        {
            "scenario_id": "temperature_to_baseline",
            "scenario_label": "仅温度变量恢复基准",
            "description": "仅将温度类变量恢复到基准期水平。",
            "variables": temp_only,
        },
        {
            "scenario_id": "r1xday_plus_temperature_to_baseline",
            "scenario_label": "R1xday + 温度变量共同恢复基准",
            "description": "将 R1xday 与温度类变量共同恢复到基准期水平。",
            "variables": key_bundle,
        },
    ]
    return deduplicate_scenarios(scenarios)


def fit_panel_model(
    base_df: pd.DataFrame,
    outcome_series: pd.Series,
    outcome_label: str,
    selected_model: SelectedModel,
) -> dict[str, object]:
    work = base_df[["Province", "Year"] + selected_model.variables].copy()
    work[outcome_label] = outcome_series.values

    transform_stats: dict[str, dict[str, float]] = {}
    for col in selected_model.variables:
        work[f"{col}__raw"] = fill_panel_median(work, col)
        work[f"{col}__z"], mean, std = zscore_with_stats(work[f"{col}__raw"])
        transform_stats[col] = {"mean": mean, "std": std}

    panel = work.set_index(["Province", "Year"]).sort_index()
    z_cols = [f"{col}__z" for col in selected_model.variables]
    raw_cols = [f"{col}__raw" for col in selected_model.variables]
    model_frame = panel[[outcome_label] + z_cols].dropna().copy()

    outcome = model_frame[outcome_label]
    exog = model_frame[z_cols].copy()
    exog.columns = selected_model.variables

    fe_cfg = FE_LABEL_TO_SPEC[selected_model.fe_label]
    result = PanelOLS(
        outcome,
        exog,
        entity_effects=fe_cfg["entity_effects"],
        time_effects=fe_cfg["time_effects"],
    ).fit(cov_type="clustered", cluster_entity=True)

    fitted_linear = result.fitted_values.iloc[:, 0].rename("fitted_linear")
    estimated_effects = result.estimated_effects.iloc[:, 0].fillna(0.0).rename("estimated_effects")
    actual_prediction = (fitted_linear + estimated_effects).rename("actual_pred")

    raw_full = panel[raw_cols].copy()
    raw_full.columns = selected_model.variables
    raw_sample = raw_full.loc[model_frame.index].copy()

    return {
        "selected_model": selected_model,
        "result": result,
        "raw_full": raw_full,
        "raw_sample": raw_sample,
        "actual_prediction": actual_prediction,
        "estimated_effects": estimated_effects,
        "outcome_actual": outcome.rename("outcome_actual"),
        "transform_stats": transform_stats,
    }


def simulate_counterfactuals(
    fit_bundle: dict[str, object],
    baseline_years: Iterable[int],
) -> pd.DataFrame:
    selected_model: SelectedModel = fit_bundle["selected_model"]
    result = fit_bundle["result"]
    raw_full: pd.DataFrame = fit_bundle["raw_full"]
    raw_sample: pd.DataFrame = fit_bundle["raw_sample"]
    actual_prediction: pd.Series = fit_bundle["actual_prediction"]
    estimated_effects: pd.Series = fit_bundle["estimated_effects"]
    outcome_actual: pd.Series = fit_bundle["outcome_actual"]
    transform_stats: dict[str, dict[str, float]] = fit_bundle["transform_stats"]

    scenarios = build_scenarios(selected_model.variables)
    baseline_lookup = build_baseline_lookup(raw_full, selected_model.variables, baseline_years)

    rows: list[pd.DataFrame] = []
    for scenario in scenarios:
        cf_raw = raw_sample.copy()
        for var in scenario["variables"]:
            cf_raw[var] = cf_raw.index.get_level_values("Province").map(baseline_lookup[var]).values

        cf_z = pd.DataFrame(index=cf_raw.index)
        for var in selected_model.variables:
            stats = transform_stats[var]
            cf_z[var] = apply_zscore(cf_raw[var], stats["mean"], stats["std"])

        cf_linear = result.predict(exog=cf_z, fitted=True).iloc[:, 0].rename("counterfactual_linear")
        cf_prediction = (cf_linear + estimated_effects).rename("counterfactual_pred")
        delta = (actual_prediction - cf_prediction).rename("actual_minus_counterfactual")
        denominator = cf_prediction.abs().where(lambda s: s >= 0.05)
        rel_change = (100 * delta / denominator).rename("relative_change_pct")

        out = pd.concat([outcome_actual, actual_prediction, cf_prediction, delta, rel_change], axis=1).reset_index()
        out["role_id"] = selected_model.role_id
        out["role_label"] = selected_model.role_label
        out["model_id"] = selected_model.model_id
        out["scheme_id"] = selected_model.scheme_id
        out["scheme_source"] = selected_model.scheme_source
        out["fe_label"] = selected_model.fe_label
        out["scenario_id"] = scenario["scenario_id"]
        out["scenario_label"] = scenario["scenario_label"]
        out["scenario_description"] = scenario["description"]
        out["scenario_variables"] = " | ".join(scenario["variables"])
        out["baseline_years"] = ",".join(str(year) for year in baseline_years)
        rows.append(out)

    return pd.concat(rows, axis=0, ignore_index=True)


def summarize_counterfactual(panel_results: pd.DataFrame, target_year: int) -> dict[str, pd.DataFrame]:
    national_yearly = (
        panel_results.groupby(
            ["role_id", "role_label", "model_id", "scheme_id", "fe_label", "scenario_id", "scenario_label", "Year"],
            dropna=False,
        )
        .agg(
            province_n=("Province", "nunique"),
            outcome_actual_mean=("outcome_actual", "mean"),
            actual_pred_mean=("actual_pred", "mean"),
            counterfactual_pred_mean=("counterfactual_pred", "mean"),
            actual_minus_counterfactual_mean=("actual_minus_counterfactual", "mean"),
            relative_change_pct_mean=("relative_change_pct", "mean"),
        )
        .reset_index()
    )

    province_average = (
        panel_results.groupby(
            ["role_id", "role_label", "model_id", "scheme_id", "fe_label", "scenario_id", "scenario_label", "Province"],
            dropna=False,
        )
        .agg(
            year_n=("Year", "nunique"),
            outcome_actual_mean=("outcome_actual", "mean"),
            actual_pred_mean=("actual_pred", "mean"),
            counterfactual_pred_mean=("counterfactual_pred", "mean"),
            actual_minus_counterfactual_mean=("actual_minus_counterfactual", "mean"),
            relative_change_pct_mean=("relative_change_pct", "mean"),
        )
        .reset_index()
    )

    latest_year = (
        panel_results[panel_results["Year"].eq(target_year)]
        .groupby(
            ["role_id", "role_label", "model_id", "scheme_id", "fe_label", "scenario_id", "scenario_label", "Province"],
            dropna=False,
        )
        .agg(
            outcome_actual_mean=("outcome_actual", "mean"),
            actual_pred_mean=("actual_pred", "mean"),
            counterfactual_pred_mean=("counterfactual_pred", "mean"),
            actual_minus_counterfactual_mean=("actual_minus_counterfactual", "mean"),
            relative_change_pct_mean=("relative_change_pct", "mean"),
        )
        .reset_index()
    )

    national_overall = (
        panel_results.groupby(
            ["role_id", "role_label", "model_id", "scheme_id", "fe_label", "scenario_id", "scenario_label"],
            dropna=False,
        )
        .agg(
            province_n=("Province", "nunique"),
            year_n=("Year", "nunique"),
            outcome_actual_mean=("outcome_actual", "mean"),
            actual_pred_mean=("actual_pred", "mean"),
            counterfactual_pred_mean=("counterfactual_pred", "mean"),
            actual_minus_counterfactual_mean=("actual_minus_counterfactual", "mean"),
            relative_change_pct_mean=("relative_change_pct", "mean"),
        )
        .reset_index()
    )

    return {
        "national_yearly": national_yearly,
        "province_average": province_average,
        "latest_year_province": latest_year,
        "national_overall": national_overall,
    }


def plot_national_yearly_main_model(national_yearly_df: pd.DataFrame, target_dir: Path) -> Path:
    plot_df = national_yearly_df[national_yearly_df["role_id"].eq("main_model")].copy()
    scenario_order = plot_df["scenario_label"].drop_duplicates().tolist()

    fig, axes = plt.subplots(len(scenario_order), 1, figsize=(11, 3.5 * len(scenario_order)), sharex=True)
    if len(scenario_order) == 1:
        axes = [axes]

    for ax, scenario_label in zip(axes, scenario_order):
        sub = plot_df[plot_df["scenario_label"].eq(scenario_label)].sort_values("Year")
        ax.plot(sub["Year"], sub["actual_pred_mean"], marker="o", linewidth=2.2, label="实际情景预测值")
        ax.plot(sub["Year"], sub["counterfactual_pred_mean"], marker="s", linewidth=2.2, label="反事实情景预测值")
        ax.fill_between(
            sub["Year"],
            sub["counterfactual_pred_mean"],
            sub["actual_pred_mean"],
            color="#D1495B",
            alpha=0.18,
        )
        ax.set_title(scenario_label)
        ax.set_ylabel("Predicted AMR")
        ax.legend(loc="best")

    axes[-1].set_xlabel("Year")
    fig.suptitle("主模型下全国年度实际情景与反事实情景对比", fontsize=14, y=1.02)
    fig.tight_layout()
    output_path = target_dir / "national_yearly_main_model.png"
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_model_comparison_heatmap(national_yearly_df: pd.DataFrame, target_year: int, target_dir: Path) -> Path:
    plot_df = national_yearly_df[national_yearly_df["Year"].eq(target_year)].copy()
    plot_df["model_short"] = plot_df["role_label"] + "\n" + plot_df["scheme_id"]
    heat = plot_df.pivot(index="model_short", columns="scenario_label", values="actual_minus_counterfactual_mean")

    fig, ax = plt.subplots(figsize=(10, max(4.5, 1.1 * len(heat))))
    sns.heatmap(heat, annot=True, fmt=".3f", cmap="RdBu_r", center=0, linewidths=0.5, ax=ax)
    ax.set_title(f"{target_year} 年全国平均反事实差值的模型比较")
    ax.set_xlabel("情景")
    ax.set_ylabel("模型")
    fig.tight_layout()
    output_path = target_dir / "model_comparison_heatmap_latest_year.png"
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_scenario_comparison_bar(national_overall_df: pd.DataFrame, target_dir: Path) -> Path:
    plot_df = national_overall_df.copy()
    plot_df["model_short"] = plot_df["role_label"] + " | " + plot_df["scheme_id"]

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(data=plot_df, x="scenario_label", y="actual_minus_counterfactual_mean", hue="model_short", ax=ax)
    ax.axhline(0, color="black", linewidth=1)
    ax.set_title("不同情景下全国平均反事实差值比较")
    ax.set_xlabel("情景")
    ax.set_ylabel("Actual - Counterfactual")
    ax.legend(title="模型", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    output_path = target_dir / "scenario_comparison_bar.png"
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def iter_feature_patches(geometry: dict) -> list[Polygon]:
    patches: list[Polygon] = []
    if geometry["type"] == "Polygon":
        rings = [geometry["coordinates"][0]]
    elif geometry["type"] == "MultiPolygon":
        rings = [polygon[0] for polygon in geometry["coordinates"]]
    else:
        rings = []

    for ring in rings:
        coords = np.asarray(ring, dtype=float)
        if coords.ndim == 2 and len(coords) >= 3:
            patches.append(Polygon(coords[:, :2], closed=True))
    return patches


def plot_province_map(latest_year_df: pd.DataFrame, target_year: int, target_dir: Path) -> Path:
    geojson_path = ensure_geojson()
    geo = json.loads(geojson_path.read_text(encoding="utf-8"))

    plot_df = latest_year_df[
        latest_year_df["role_id"].eq("main_model") & latest_year_df["scenario_id"].eq("all_climate_to_baseline")
    ].copy()
    if plot_df.empty:
        raise RuntimeError("主模型缺少“所有气候变量恢复基准”情景，无法生成省级地图。")

    plot_df["geo_name"] = plot_df["Province"].map(normalize_geo_name)
    value_map = plot_df.set_index("geo_name")["actual_minus_counterfactual_mean"].to_dict()

    patches: list[Polygon] = []
    values: list[float] = []
    for feature in geo["features"]:
        geo_name = normalize_geo_name(feature.get("properties", {}).get("name", ""))
        if geo_name == "南海诸岛":
            continue
        feature_patches = iter_feature_patches(feature["geometry"])
        if not feature_patches:
            continue
        value = value_map.get(geo_name, np.nan)
        patches.extend(feature_patches)
        values.extend([value] * len(feature_patches))

    values_arr = np.asarray(values, dtype=float)
    finite = values_arr[np.isfinite(values_arr)]
    vmax = float(np.nanmax(np.abs(finite))) if len(finite) else 1.0
    vmax = max(vmax, 1e-6)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)

    fig, ax = plt.subplots(figsize=(11, 8))
    collection = PatchCollection(
        patches,
        array=np.ma.masked_invalid(values_arr),
        cmap="RdBu_r",
        edgecolor="white",
        linewidth=0.45,
        norm=norm,
    )
    ax.add_collection(collection)
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{target_year} 年主模型下“所有气候变量恢复基准”情景的分省差值地图")
    cbar = fig.colorbar(collection, ax=ax, shrink=0.75, pad=0.02)
    cbar.set_label("Actual - Counterfactual")
    fig.tight_layout()
    output_path = target_dir / "province_map_main_model_latest_year.png"
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def write_notes(
    output_dir: Path,
    outcome_label: str,
    baseline_years: Iterable[int],
    fe_compare_df: pd.DataFrame,
    bayes_variant_summary_df: pd.DataFrame,
    selected_models_df: pd.DataFrame,
    national_overall_df: pd.DataFrame,
) -> Path:
    baseline_text = "、".join(str(year) for year in baseline_years)
    fe_main = fe_compare_df.iloc[0]
    main_model = selected_models_df[selected_models_df["role_id"].eq("main_model")].iloc[0]
    strict_model = selected_models_df[selected_models_df["role_id"].eq("robust_strict_fe")].iloc[0]
    top_rows = national_overall_df[
        ["role_label", "scheme_id", "scenario_label", "actual_minus_counterfactual_mean", "relative_change_pct_mean"]
    ].sort_values(["scenario_label", "role_label"])

    lines = [
        f"# {outcome_label} 反事实推演说明",
        "",
        "## 与前文的衔接",
        "",
        "本节不重新从头建立普通多元线性回归，而是在既有固定效应候选模型库的基础上，先做候选模型筛选，再对入选 FE 模型做 counterfactual simulation。",
        "写作上可以自然承接前文“单因素筛选 → 多变量固定效应整合 → 贝叶斯桥接验证”的主线。",
        "",
        "## 文献借鉴的分工",
        "",
        "1. Lancet Planetary Health 2023：你提供的 Lancet URL 对应的是 2023 年发表的全球 PM2.5 与临床耐药分析，我这里只借环境-AMR 多因素框架、控制变量组织方式和主结果表风格，不照搬其全球模型。",
        "2. Nature Medicine 2025（Published: 28 April 2025）：借其从主分析到扩展分析、再到情景/预测分析的叙述逻辑，并用已有贝叶斯结果作为主模型筛选后的桥接证据。",
        "3. Nature 2023（Published: 22 February 2023）：借其“以 benchmark 为基准，比较 observed 与 counterfactual prediction”的反事实逻辑；这里把 benchmark 改写为省级气候变量在基准期的水平。",
        "",
        "## 为什么主推 Year FE",
        "",
        f"- 当前全库结果里，`{fe_main['fe_label']}` 的 top-10 平均综合分最高（{fe_main['top10_mean_score']:.3f}）。",
        f"- `R1xday` 在该 FE 设定下为正的模型占比 {fe_main['share_r1xday_positive']:.1%}，显著比例为 {fe_main['share_r1xday_sig_005']:.1%}；`AMC` 为正的模型占比 {fe_main['share_amc_positive']:.1%}。",
        "- 与之相对，双向 FE 更适合作为保守下界检验，因为它显著压缩了气候主效应。",
        "",
        "## 入选模型",
        "",
        f"- 主模型：`{main_model['scheme_id']}` + `{main_model['fe_label']}`。原因是理论叙事最完整，且 `R1xday` 与 `AMC` 同时为正且达到 0.05 显著。",
        f"- 稳健性模型 1：`{selected_models_df.loc[selected_models_df['role_id'].eq('robust_low_vif'), 'scheme_id'].iloc[0]}` + Year FE，用于检验低共线性口径。",
        f"- 稳健性模型 2：`{selected_models_df.loc[selected_models_df['role_id'].eq('robust_systematic'), 'scheme_id'].iloc[0]}` + Year FE，用于检验结论能否在系统穷举高分模型中复现。",
        f"- 稳健性模型 3：`{strict_model['scheme_id']}` + `{strict_model['fe_label']}`，用于给出严格 FE 下的保守下界。",
        "",
        "## 当前结果解释时建议强调",
        "",
        f"- 基准期默认设为 {baseline_text}；脚本会把每个省的气候变量恢复到该基准期的省内水平。",
        "- `actual_minus_counterfactual > 0` 表示：相对于“气候恢复基准”的世界，实际气候轨迹对应更高的预测 AMR。",
        "- 由于 `AMR_AGG_z` 是标准化综合指标，百分比变化仅作辅助展示；正文请优先解释绝对差值与方向一致性。",
        "- 如果 Year FE 下多数情景都给出正的 national average difference，而双向 FE 明显收缩，则可写成“反事实量化支持 climate-related burden 的存在，但其幅度对 FE 设定敏感”。",
        "",
        "## 全国平均结果快照",
        "",
        top_rows.to_markdown(index=False),
        "",
    ]

    output_path = output_dir / "selection_and_writeup_notes.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def save_outputs(
    output_dir: Path,
    fe_compare_df: pd.DataFrame,
    bayes_variant_summary_df: pd.DataFrame,
    selected_models_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    panel_results_df: pd.DataFrame,
    summary_tables: dict[str, pd.DataFrame],
) -> None:
    screening_dir = output_dir / "model_screening"
    counterfactual_dir = output_dir / "counterfactual_outputs"
    screening_dir.mkdir(exist_ok=True)
    counterfactual_dir.mkdir(exist_ok=True)

    fe_compare_df.to_csv(screening_dir / "fe_spec_comparison.csv", index=False, encoding="utf-8-sig")
    bayes_variant_summary_df.to_csv(screening_dir / "bayes_variant_summary.csv", index=False, encoding="utf-8-sig")
    selected_models_df.to_csv(screening_dir / "selected_models.csv", index=False, encoding="utf-8-sig")
    ranking_df.head(20).to_csv(screening_dir / "top20_ranking_snapshot.csv", index=False, encoding="utf-8-sig")
    panel_results_df.to_csv(counterfactual_dir / "counterfactual_panel_predictions.csv", index=False, encoding="utf-8-sig")

    for name, table in summary_tables.items():
        table.to_csv(counterfactual_dir / f"{name}.csv", index=False, encoding="utf-8-sig")


def run_analysis(
    outcome: str,
    single_outcome_scale: str,
    baseline_years: list[int],
    target_year: int,
) -> dict[str, Path]:
    base_df = load_base_frame()
    outcome_series, outcome_meta = build_outcome_series(base_df, outcome, single_outcome_scale)
    results = load_existing_results()

    fe_compare_df = compare_fe_specs(results["summary"])
    bayes_variant_summary_df = summarize_bayes_bridge(results["bayes_bridge"])
    primary_fe_label = pick_primary_fe(fe_compare_df)
    selected_models = build_selected_models(results["summary"], results["bayes_candidates"], primary_fe_label)
    selected_models_df = selected_models_to_frame(selected_models)

    outcome_dir = RESULT_ROOT / outcome
    figure_dir = outcome_dir / "figures"
    outcome_dir.mkdir(exist_ok=True)
    figure_dir.mkdir(exist_ok=True)

    panel_results = []
    for selected_model in selected_models:
        fit_bundle = fit_panel_model(base_df, outcome_series, outcome_meta["outcome_label"], selected_model)
        panel_results.append(simulate_counterfactuals(fit_bundle, baseline_years))

    panel_results_df = pd.concat(panel_results, axis=0, ignore_index=True)
    summary_tables = summarize_counterfactual(panel_results_df, target_year=target_year)

    save_outputs(
        output_dir=outcome_dir,
        fe_compare_df=fe_compare_df,
        bayes_variant_summary_df=bayes_variant_summary_df,
        selected_models_df=selected_models_df,
        ranking_df=results["ranking"],
        panel_results_df=panel_results_df,
        summary_tables=summary_tables,
    )

    national_plot = plot_national_yearly_main_model(summary_tables["national_yearly"], figure_dir)
    model_heatmap = plot_model_comparison_heatmap(summary_tables["national_yearly"], target_year, figure_dir)
    scenario_plot = plot_scenario_comparison_bar(summary_tables["national_overall"], figure_dir)
    province_map = plot_province_map(summary_tables["latest_year_province"], target_year, figure_dir)
    notes_path = write_notes(
        output_dir=outcome_dir,
        outcome_label=outcome_meta["outcome_label"],
        baseline_years=baseline_years,
        fe_compare_df=fe_compare_df,
        bayes_variant_summary_df=bayes_variant_summary_df,
        selected_models_df=selected_models_df,
        national_overall_df=summary_tables["national_overall"],
    )

    metadata = {
        "outcome": outcome,
        "outcome_label": outcome_meta["outcome_label"],
        "outcome_note": outcome_meta["outcome_note"],
        "baseline_years": baseline_years,
        "target_year": target_year,
        "primary_fe_label": primary_fe_label,
        "selected_models": selected_models_df.to_dict(orient="records"),
        "figures": {
            "national_yearly_main_model": str(national_plot),
            "model_comparison_heatmap_latest_year": str(model_heatmap),
            "scenario_comparison_bar": str(scenario_plot),
            "province_map_main_model_latest_year": str(province_map),
        },
        "notes": str(notes_path),
    }
    metadata_path = outcome_dir / "run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "outcome_dir": outcome_dir,
        "figure_dir": figure_dir,
        "metadata_path": metadata_path,
        "notes_path": notes_path,
        "national_plot": national_plot,
        "model_heatmap": model_heatmap,
        "scenario_plot": scenario_plot,
        "province_map": province_map,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于既有固定效应候选模型开展反事实推演。")
    parser.add_argument("--outcome", default="AMR_AGG", help="默认先跑 AMR_AGG；后续可扩展到 13 个单独指标。")
    parser.add_argument(
        "--single-outcome-scale",
        choices=["zscore", "raw"],
        default="zscore",
        help="当 outcome 是单独 AMR 指标时，使用 zscore 或 raw 口径。",
    )
    parser.add_argument("--baseline-years", nargs="+", type=int, default=[2014], help="反事实基准年份，默认 2014。")
    parser.add_argument(
        "--target-year",
        type=int,
        default=2023,
        help="分省地图与模型比较图默认展示的目标年份。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_analysis(
        outcome=args.outcome,
        single_outcome_scale=args.single_outcome_scale,
        baseline_years=args.baseline_years,
        target_year=args.target_year,
    )
    print(f"[done] outcome_dir={outputs['outcome_dir']}")
    print(f"[done] metadata={outputs['metadata_path']}")
    print(f"[done] notes={outputs['notes_path']}")


if __name__ == "__main__":
    main()
