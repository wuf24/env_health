from __future__ import annotations

import time
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from statsmodels.stats.outliers_influence import variance_inflation_factor


warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "2 固定效应模型"
RESULT_DIR = MODEL_DIR / "results"
RESULT_DIR.mkdir(exist_ok=True)

AMR_PATH = ROOT / "amr_rate.csv"
X_PATH = ROOT / "climate_social_eco.csv"

AMR_COLS = [
    "MRCNS", "VREFS", "VREFM", "PRSP", "ERSP", "3GCRKP",
    "MRSA", "3GCREC", "CREC", "QREC", "CRPA", "CRKP", "CRAB",
]

CORE_VARS = ["R1xday", "抗菌药物使用强度"]
MIN_VARS = 7
MAX_VARS = 15
TOP_N_HORIZONTAL = 200

FE_SPECS = {
    "NoYes_YearFE": {
        "entity_effects": False,
        "time_effects": True,
        "province_fe": "No",
        "year_fe": "Yes",
        "label": "Province: No / Year: Yes",
    },
    "YesNo_EntityFE": {
        "entity_effects": True,
        "time_effects": False,
        "province_fe": "Yes",
        "year_fe": "No",
        "label": "Province: Yes / Year: No",
    },
    "YesYes_TwoWayFE": {
        "entity_effects": True,
        "time_effects": True,
        "province_fe": "Yes",
        "year_fe": "Yes",
        "label": "Province: Yes / Year: Yes",
    },
}

CURATED_SCHEMES = {
    "方案A_平衡主线组": {
        "note": "保留的人工主线组合：R1xday 与 AMC 都较稳，VIF 仍在可接受范围内。",
        "vars": ["省平均气温", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "人均日生活用水量(升)", "牲畜饲养\n-猪年底头数"],
    },
    "方案D_城市气候组": {
        "note": "保留的人工组合：强调城市气候与绿化视角。",
        "vars": ["主要城市平均气温", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "建成区绿化覆盖率", "牲畜饲养\n-猪年底头数"],
    },
    "方案F_低VIF主线组": {
        "note": "保留的人工组合：当前低共线性主线参考版本。",
        "vars": ["TA（°C）", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "人均日生活用水量(升)", "牲畜饲养\n-猪年底头数", "主要城市日照时数"],
    },
    "方案C_污染替代组": {
        "note": "保留的人工组合：污染与社会经济代理的替代规格。",
        "vars": ["省平均气温", "R1xday", "氮氧化物", "抗菌药物使用强度", "可支配收入", "建成区绿化覆盖率", "人均日生活用水量(升)", "牲畜饲养\n-猪年底头数"],
    },
}

FAMILY_SPECS = [
    {
        "family": "temperature_proxy",
        "label": "温度代理",
        "required": True,
        "choices": ["主要城市平均气温", "省平均气温", "TA（°C）"],
    },
    {
        "family": "hydro_proxy",
        "label": "背景降水/湿度代理",
        "required": False,
        "choices": ["主要城市降水量", "省平均降水", "PA（%）", "R5xday"],
    },
    {
        "family": "pollution_proxy",
        "label": "空气污染代理",
        "required": True,
        "choices": ["二氧化硫", "氮氧化物", "PM2.5"],
    },
    {
        "family": "development_proxy",
        "label": "发展/医疗代理",
        "required": True,
        "choices": ["可支配收入", "GDP", "医疗水平"],
    },
    {
        "family": "social_env_proxy",
        "label": "社会环境代理",
        "required": False,
        "choices": ["主要城市日照时数", "食品消费量", "文盲比例", "建成区绿化覆盖率"],
    },
    {
        "family": "water_sanitation_proxy",
        "label": "供水/卫生代理",
        "required": True,
        "choices": [
            "生活垃圾无害化处理率",
            "卫生程度\n（日污水处理能力）",
            "城市用水普及率",
            "饮用水\n供水综合生产能力(万立方米/日)",
            "人均日生活用水量(升)",
        ],
    },
    {
        "family": "livestock_proxy",
        "label": "畜牧代理",
        "required": True,
        "choices": [
            "牲畜饲养\n-大牲畜年底头数",
            "牲畜饲养\n-猪年底头数",
            "牲畜饲养\n-羊年底头数",
        ],
    },
]

FAMILY_CHOICE_MAP = {spec["family"]: list(spec["choices"]) for spec in FAMILY_SPECS}
PREFERRED_POLLUTION_PROXY = "PM2.5"


def to_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)


def zscore_series(s: pd.Series) -> pd.Series:
    s = to_float(s)
    mu = np.nanmean(s.values)
    sd = np.nanstd(s.values, ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - mu) / sd


def fill_panel_median(df: pd.DataFrame, col: str) -> pd.Series:
    out = to_float(df[col])
    out = out.groupby(df["Province"]).transform(lambda s: s.fillna(s.median()))
    out = out.fillna(out.median())
    return out


def compute_vif(x: pd.DataFrame) -> pd.DataFrame:
    vals = x.values.astype(float)
    return pd.DataFrame(
        {
            "predictor": x.columns,
            "VIF": [variance_inflation_factor(vals, i) for i in range(len(x.columns))],
        }
    )


def p_to_text(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 1e-4:
        return "<0.0001"
    return f"{p:.4f}".rstrip("0").rstrip(".")


def p_to_stars(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def fmt_coef(x: float, digits: int = 4, stars: str = "") -> str:
    if not np.isfinite(x):
        return ""
    return f"{x:.{digits}f}".rstrip("0").rstrip(".") + stars


def fmt_ci(lo: float, hi: float, digits: int = 4) -> str:
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return ""
    return f"({lo:.{digits}f}, {hi:.{digits}f})"


def minmax01(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    if np.isclose(s.max(), s.min()):
        return pd.Series(np.ones(len(s)), index=s.index)
    return (s - s.min()) / (s.max() - s.min())


def split_variables(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    return [item.strip() for item in text.split(" | ") if item and item.strip()]


def pick_family_choice(variables: list[str] | str, family: str) -> str | None:
    values = split_variables(variables) if isinstance(variables, str) else list(variables)
    for choice in FAMILY_CHOICE_MAP.get(family, []):
        if choice in values:
            return choice
    return None


def enrich_summary_for_screening(summary_df: pd.DataFrame, coef_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = summary_df.copy()
    summary_df = summary_df.drop(
        columns=[
            "temperature_proxy",
            "pollution_proxy",
            "coef_temperature_proxy",
            "p_temperature_proxy",
            "coef_pollution_proxy",
            "p_pollution_proxy",
            "core_joint_pass",
            "temperature_positive",
            "temperature_gate_pass",
            "pollution_preferred",
            "screening_stage",
        ],
        errors="ignore",
    )
    summary_df["variables_list"] = summary_df["variables"].map(split_variables)
    summary_df["temperature_proxy"] = summary_df["variables_list"].map(
        lambda values: pick_family_choice(values, "temperature_proxy")
    )
    summary_df["pollution_proxy"] = summary_df["variables_list"].map(
        lambda values: pick_family_choice(values, "pollution_proxy")
    )

    coef_lookup = coef_df[["model_id", "predictor", "coef", "p_value"]].drop_duplicates(
        subset=["model_id", "predictor"]
    )
    temp_lookup = coef_lookup.rename(
        columns={
            "predictor": "temperature_proxy",
            "coef": "coef_temperature_proxy",
            "p_value": "p_temperature_proxy",
        }
    )
    pollution_lookup = coef_lookup.rename(
        columns={
            "predictor": "pollution_proxy",
            "coef": "coef_pollution_proxy",
            "p_value": "p_pollution_proxy",
        }
    )

    summary_df = summary_df.merge(
        temp_lookup[["model_id", "temperature_proxy", "coef_temperature_proxy", "p_temperature_proxy"]],
        on=["model_id", "temperature_proxy"],
        how="left",
    )
    summary_df = summary_df.merge(
        pollution_lookup[["model_id", "pollution_proxy", "coef_pollution_proxy", "p_pollution_proxy"]],
        on=["model_id", "pollution_proxy"],
        how="left",
    )

    summary_df["core_joint_pass"] = (
        (summary_df["coef_R1xday"] > 0)
        & (summary_df["p_R1xday"] < 0.05)
        & (summary_df["coef_AMC"] > 0)
        & (summary_df["p_AMC"] < 0.05)
    )
    summary_df["temperature_positive"] = summary_df["coef_temperature_proxy"] > 0
    summary_df["temperature_gate_pass"] = summary_df["core_joint_pass"] & summary_df["temperature_positive"]
    summary_df["pollution_preferred"] = summary_df["pollution_proxy"].eq(PREFERRED_POLLUTION_PROXY)
    summary_df["screening_stage"] = np.select(
        [
            summary_df["temperature_gate_pass"],
            summary_df["core_joint_pass"],
        ],
        [
            "核心变量通过 + 温度为正",
            "仅核心变量通过",
        ],
        default="未通过核心门槛",
    )
    summary_df = summary_df.drop(columns=["variables_list"])
    return summary_df


def load_analysis_frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    amr = pd.read_csv(AMR_PATH, encoding="utf-8-sig")
    x = pd.read_csv(X_PATH, encoding="utf-8-sig")
    x = x.rename(columns={x.columns[0]: "Province", x.columns[1]: "Year"})

    for df_temp in [amr, x]:
        df_temp["Province"] = df_temp["Province"].astype(str).str.strip()
        df_temp["Year"] = pd.to_numeric(df_temp["Year"], errors="coerce").astype("Int64")

    df = amr.merge(x, on=["Province", "Year"], how="inner")
    df = df[df["Year"].between(2014, 2023)].dropna(subset=["Province", "Year"]).copy()

    for c in AMR_COLS:
        df[c] = to_float(df[c])

    z_amr = pd.DataFrame({c: zscore_series(df[c]) for c in AMR_COLS})
    df["AMR_AGG_z"] = z_amr.mean(axis=1, skipna=True)

    all_vars = sorted(
        set(CORE_VARS).union(*[set(f["choices"]) for f in FAMILY_SPECS]).union(
            *[set(spec["vars"]) for spec in CURATED_SCHEMES.values()]
        )
    )
    for col in all_vars:
        df[f"{col}__raw"] = fill_panel_median(df, col)
        df[f"{col}__z"] = zscore_series(df[f"{col}__raw"])

    panel = df.set_index(["Province", "Year"]).sort_index()
    return df, panel


def build_scheme_catalog() -> pd.DataFrame:
    rows: list[dict] = []
    seen_signatures: set[tuple[str, ...]] = set()

    for name, spec in CURATED_SCHEMES.items():
        sig = tuple(sorted(spec["vars"]))
        seen_signatures.add(sig)
        rows.append(
            {
                "scheme_id": name,
                "scheme_source": "curated",
                "scheme_note": spec["note"],
                "n_vars": len(spec["vars"]),
                "variables": " | ".join(spec["vars"]),
                "family_selection": "manual_curated",
            }
        )

    required = [fam for fam in FAMILY_SPECS if fam["required"]]
    optional = [fam for fam in FAMILY_SPECS if not fam["required"]]

    sys_idx = 1
    for req_choice in product(*[fam["choices"] for fam in required]):
        for opt_choice in product(*([[None] + fam["choices"] for fam in optional])):
            selected = list(CORE_VARS) + list(req_choice) + [x for x in opt_choice if x is not None]
            selected = list(dict.fromkeys(selected))
            if not (MIN_VARS <= len(selected) <= MAX_VARS):
                continue
            sig = tuple(sorted(selected))
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            family_tokens = []
            for fam, value in zip(required, req_choice):
                family_tokens.append(f"{fam['family']}={value}")
            for fam, value in zip(optional, opt_choice):
                family_tokens.append(f"{fam['family']}={value if value is not None else 'skip'}")

            rows.append(
                {
                    "scheme_id": f"SYS_{sys_idx:05d}",
                    "scheme_source": "systematic",
                    "scheme_note": "全变量池在科学约束下的系统穷举：保留核心变量，且每个高相关代理家族最多取 1 个。",
                    "n_vars": len(selected),
                    "variables": " | ".join(selected),
                    "family_selection": " ; ".join(family_tokens),
                }
            )
            sys_idx += 1

    catalog = pd.DataFrame(rows)
    return catalog.sort_values(["scheme_source", "scheme_id"]).reset_index(drop=True)


def build_lancet_rows(
    res,
    x_cols: list[str],
    scheme_row: dict,
    fe_name: str,
    fe_cfg: dict,
    model_id: str,
) -> list[dict]:
    ci = res.conf_int()
    ci_lo = ci.iloc[:, 0]
    ci_hi = ci.iloc[:, 1]

    rows = []
    title = f"{scheme_row['scheme_id']} | {fe_cfg['label']}"
    rows.append(
        {
            "model_id": model_id,
            "scheme_id": scheme_row["scheme_id"],
            "scheme_source": scheme_row["scheme_source"],
            "fe_spec": fe_name,
            "Predictor": title,
            "Coefficient": "",
            "95% CI": "",
            "p value": "",
        }
    )

    for xname in x_cols:
        p = float(res.pvalues.get(xname, np.nan))
        lo = float(ci_lo.loc[xname]) if xname in ci_lo.index else np.nan
        hi = float(ci_hi.loc[xname]) if xname in ci_hi.index else np.nan
        rows.append(
            {
                "model_id": model_id,
                "scheme_id": scheme_row["scheme_id"],
                "scheme_source": scheme_row["scheme_source"],
                "fe_spec": fe_name,
                "Predictor": xname,
                "Coefficient": fmt_coef(float(res.params.get(xname, np.nan)), 4, p_to_stars(p)),
                "95% CI": fmt_ci(lo, hi, 4),
                "p value": p_to_text(p),
            }
        )

    rows.extend(
        [
            {"model_id": model_id, "scheme_id": scheme_row["scheme_id"], "scheme_source": scheme_row["scheme_source"], "fe_spec": fe_name, "Predictor": "Province", "Coefficient": fe_cfg["province_fe"], "95% CI": "", "p value": ""},
            {"model_id": model_id, "scheme_id": scheme_row["scheme_id"], "scheme_source": scheme_row["scheme_source"], "fe_spec": fe_name, "Predictor": "Year", "Coefficient": fe_cfg["year_fe"], "95% CI": "", "p value": ""},
            {"model_id": model_id, "scheme_id": scheme_row["scheme_id"], "scheme_source": scheme_row["scheme_source"], "fe_spec": fe_name, "Predictor": "R-squared", "Coefficient": fmt_coef(float(res.rsquared), 3), "95% CI": "", "p value": ""},
            {"model_id": model_id, "scheme_id": scheme_row["scheme_id"], "scheme_source": scheme_row["scheme_source"], "fe_spec": fe_name, "Predictor": "R-squared (Overall)", "Coefficient": fmt_coef(float(res.rsquared_overall), 3), "95% CI": "", "p value": ""},
            {"model_id": model_id, "scheme_id": scheme_row["scheme_id"], "scheme_source": scheme_row["scheme_source"], "fe_spec": fe_name, "Predictor": "R² (within)", "Coefficient": fmt_coef(float(res.rsquared_within), 3), "95% CI": "", "p value": ""},
            {"model_id": model_id, "scheme_id": scheme_row["scheme_id"], "scheme_source": scheme_row["scheme_source"], "fe_spec": fe_name, "Predictor": "Total number of observations", "Coefficient": str(int(res.nobs)), "95% CI": "", "p value": ""},
            {"model_id": model_id, "scheme_id": scheme_row["scheme_id"], "scheme_source": scheme_row["scheme_source"], "fe_spec": fe_name, "Predictor": "", "Coefficient": "", "95% CI": "", "p value": ""},
        ]
    )
    return rows


def fit_model_space(catalog: pd.DataFrame, panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict] = []
    coef_rows: list[dict] = []
    vif_rows: list[dict] = []
    lancet_rows: list[dict] = []

    t0 = time.time()
    total_model_runs = len(catalog) * len(FE_SPECS)

    for idx, (_, scheme) in enumerate(catalog.iterrows(), start=1):
        cols = scheme["variables"].split(" | ")
        raw_x = pd.DataFrame({c: panel[f"{c}__raw"] for c in cols}, index=panel.index)
        z_x = pd.DataFrame({c: panel[f"{c}__z"] for c in cols}, index=panel.index)

        vif_raw = compute_vif(raw_x).rename(columns={"VIF": "vif_raw"})
        vif_z = compute_vif(z_x).rename(columns={"VIF": "vif_z"})
        vif_table = vif_raw.merge(vif_z, on="predictor", how="inner")
        vif_table["abs_diff"] = (vif_table["vif_raw"] - vif_table["vif_z"]).abs()

        tmp = pd.concat([panel["AMR_AGG_z"], z_x], axis=1).dropna()
        y = tmp["AMR_AGG_z"]
        x_model = tmp[cols]

        for fe_name, fe_cfg in FE_SPECS.items():
            model_id = f"{scheme['scheme_id']} | {fe_cfg['label']}"
            res = PanelOLS(
                y,
                x_model,
                entity_effects=fe_cfg["entity_effects"],
                time_effects=fe_cfg["time_effects"],
            ).fit(cov_type="clustered", cluster_entity=True)

            summary_rows.append(
                {
                    "model_id": model_id,
                    "scheme_id": scheme["scheme_id"],
                    "scheme_source": scheme["scheme_source"],
                    "scheme_note": scheme["scheme_note"],
                    "family_selection": scheme["family_selection"],
                    "fe_spec": fe_name,
                    "fe_label": fe_cfg["label"],
                    "province_fe": fe_cfg["province_fe"],
                    "year_fe": fe_cfg["year_fe"],
                    "n_vars": len(cols),
                    "variables": scheme["variables"],
                    "nobs": int(res.nobs),
                    "r2_model": float(res.rsquared),
                    "r2_overall": float(res.rsquared_overall),
                    "r2_within": float(res.rsquared_within),
                    "max_vif_raw": float(vif_table["vif_raw"].max()),
                    "median_vif_raw": float(vif_table["vif_raw"].median()),
                    "max_vif_z": float(vif_table["vif_z"].max()),
                    "median_vif_z": float(vif_table["vif_z"].median()),
                    "max_abs_vif_diff": float(vif_table["abs_diff"].max()),
                    "coef_R1xday": float(res.params["R1xday"]),
                    "p_R1xday": float(res.pvalues["R1xday"]),
                    "coef_AMC": float(res.params["抗菌药物使用强度"]),
                    "p_AMC": float(res.pvalues["抗菌药物使用强度"]),
                    "sig_predictors_p_lt_0_05": ", ".join([c for c in cols if float(res.pvalues[c]) < 0.05]),
                }
            )

            conf = res.conf_int()
            for predictor in cols:
                coef_rows.append(
                    {
                        "model_id": model_id,
                        "scheme_id": scheme["scheme_id"],
                        "scheme_source": scheme["scheme_source"],
                        "fe_spec": fe_name,
                        "predictor": predictor,
                        "coef": float(res.params[predictor]),
                        "p_value": float(res.pvalues[predictor]),
                        "ci_low": float(conf.loc[predictor].iloc[0]),
                        "ci_high": float(conf.loc[predictor].iloc[1]),
                    }
                )

            vif_out = vif_table.copy()
            vif_out["model_id"] = model_id
            vif_out["scheme_id"] = scheme["scheme_id"]
            vif_out["scheme_source"] = scheme["scheme_source"]
            vif_out["fe_spec"] = fe_name
            vif_rows.extend(vif_out.to_dict(orient="records"))
            lancet_rows.extend(build_lancet_rows(res, cols, scheme.to_dict(), fe_name, fe_cfg, model_id))

        if idx % 250 == 0 or idx == len(catalog):
            elapsed = time.time() - t0
            done = idx * len(FE_SPECS)
            rate = done / elapsed if elapsed > 0 else np.nan
            print(f"[progress] schemes={idx}/{len(catalog)} fits={done}/{total_model_runs} elapsed={elapsed:.1f}s rate={rate:.2f} fits/s")

    return (
        pd.DataFrame(summary_rows),
        pd.DataFrame(coef_rows),
        pd.DataFrame(vif_rows),
        pd.DataFrame(lancet_rows),
    )


def build_ranking(summary_df: pd.DataFrame) -> pd.DataFrame:
    summary_df = summary_df.copy()
    summary_df["r1xday_support_raw"] = np.sign(summary_df["coef_R1xday"]) * (
        -np.log10(summary_df["p_R1xday"].clip(lower=1e-12))
    )
    summary_df["amc_support_raw"] = np.sign(summary_df["coef_AMC"]) * (
        -np.log10(summary_df["p_AMC"].clip(lower=1e-12))
    )
    summary_df["core_positive_count"] = (
        (summary_df["coef_R1xday"] > 0).astype(int) + (summary_df["coef_AMC"] > 0).astype(int)
    )
    summary_df["core_sig_count_p_lt_0_05"] = (
        (summary_df["p_R1xday"] < 0.05).astype(int) + (summary_df["p_AMC"] < 0.05).astype(int)
    )
    summary_df["core_signal_score"] = summary_df["core_joint_pass"].astype(float)
    summary_df["temperature_score"] = summary_df["temperature_positive"].astype(float)
    summary_df["temperature_gate_score"] = summary_df["temperature_gate_pass"].astype(float)
    summary_df["fit_score"] = minmax01(summary_df["r2_model"])
    summary_df["r2_overall_score"] = minmax01(summary_df["r2_overall"])
    summary_df["r2_within_score"] = minmax01(summary_df["r2_within"])
    summary_df["pollution_score"] = summary_df["pollution_preferred"].astype(float)
    summary_df["vif_score"] = 1 - minmax01(np.log1p(summary_df["max_vif_z"]))
    summary_df["performance_score_raw"] = (
        100.0 * summary_df["core_signal_score"]
        + 10.0 * summary_df["temperature_gate_score"]
        + summary_df["fit_score"]
        + 1e-7 * summary_df["pollution_score"]
        + 1e-8 * summary_df["r2_overall_score"]
        + 1e-9 * summary_df["r2_within_score"]
        + 1e-10 * summary_df["vif_score"]
    )
    summary_df["performance_score"] = (
        summary_df["performance_score_raw"] / summary_df["performance_score_raw"].max()
    )

    ranking_df = (
        summary_df[
            [
                "model_id",
                "scheme_id",
                "scheme_source",
                "fe_label",
                "screening_stage",
                "performance_score",
                "core_signal_score",
                "temperature_score",
                "temperature_gate_score",
                "fit_score",
                "pollution_score",
                "vif_score",
                "core_joint_pass",
                "core_positive_count",
                "core_sig_count_p_lt_0_05",
                "temperature_positive",
                "temperature_gate_pass",
                "temperature_proxy",
                "coef_temperature_proxy",
                "p_temperature_proxy",
                "pollution_proxy",
                "coef_pollution_proxy",
                "p_pollution_proxy",
                "pollution_preferred",
                "coef_R1xday",
                "p_R1xday",
                "coef_AMC",
                "p_AMC",
                "r2_model",
                "r2_overall",
                "r2_within",
                "max_vif_z",
                "sig_predictors_p_lt_0_05",
            ]
        ]
        .sort_values(
            [
                "core_joint_pass",
                "temperature_gate_pass",
                "r2_model",
                "pollution_preferred",
                "r2_overall",
                "r2_within",
                "vif_score",
                "model_id",
            ],
            ascending=[False, False, False, False, False, False, False, True],
        )
        .reset_index(drop=True)
    )
    ranking_df.insert(0, "performance_rank", np.arange(1, len(ranking_df) + 1))
    summary_df = summary_df.drop(columns=["performance_rank"], errors="ignore")
    summary_df["performance_rank"] = summary_df["model_id"].map(
        ranking_df.set_index("model_id")["performance_rank"]
    )
    return summary_df, ranking_df


def build_horizontal_top(summary_df: pd.DataFrame, ranking_df: pd.DataFrame) -> pd.DataFrame:
    top_ids = ranking_df["model_id"].head(TOP_N_HORIZONTAL).tolist()
    metric_cols = [
        "core_joint_pass",
        "temperature_positive",
        "temperature_gate_pass",
        "pollution_preferred",
        "r2_model",
        "r2_overall",
        "r2_within",
        "coef_R1xday",
        "p_R1xday",
        "coef_AMC",
        "p_AMC",
        "max_vif_raw",
        "max_vif_z",
        "performance_score",
        "performance_rank",
    ]
    return (
        summary_df.loc[summary_df["model_id"].isin(top_ids), ["model_id"] + metric_cols]
        .set_index("model_id")
        .T.reset_index()
        .rename(columns={"index": "metric"})
    )


def save_outputs(
    catalog_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    coef_df: pd.DataFrame,
    vif_df: pd.DataFrame,
    lancet_df: pd.DataFrame,
    horizontal_top_df: pd.DataFrame,
) -> None:
    outputs = {
        "catalog_csv": RESULT_DIR / "exhaustive_scheme_catalog.csv",
        "catalog_xlsx": RESULT_DIR / "exhaustive_scheme_catalog.xlsx",
        "summary_csv": RESULT_DIR / "exhaustive_model_summary.csv",
        "summary_xlsx": RESULT_DIR / "exhaustive_model_summary.xlsx",
        "ranking_csv": RESULT_DIR / "exhaustive_model_ranking.csv",
        "ranking_xlsx": RESULT_DIR / "exhaustive_model_ranking.xlsx",
        "coef_csv": RESULT_DIR / "exhaustive_model_coefficients.csv",
        "vif_csv": RESULT_DIR / "exhaustive_model_vif.csv",
        "lancet_csv": RESULT_DIR / "exhaustive_model_lancet_tables.csv",
        "horizontal_csv": RESULT_DIR / "exhaustive_model_horizontal_compare_top200.csv",
        "horizontal_xlsx": RESULT_DIR / "exhaustive_model_horizontal_compare_top200.xlsx",
    }

    catalog_df.to_csv(outputs["catalog_csv"], index=False, encoding="utf-8-sig")
    catalog_df.to_excel(outputs["catalog_xlsx"], index=False)
    summary_df.to_csv(outputs["summary_csv"], index=False, encoding="utf-8-sig")
    summary_df.to_excel(outputs["summary_xlsx"], index=False)
    ranking_df.to_csv(outputs["ranking_csv"], index=False, encoding="utf-8-sig")
    ranking_df.to_excel(outputs["ranking_xlsx"], index=False)
    coef_df.to_csv(outputs["coef_csv"], index=False, encoding="utf-8-sig")
    vif_df.to_csv(outputs["vif_csv"], index=False, encoding="utf-8-sig")
    lancet_df.to_csv(outputs["lancet_csv"], index=False, encoding="utf-8-sig")
    horizontal_top_df.to_csv(outputs["horizontal_csv"], index=False, encoding="utf-8-sig")
    horizontal_top_df.to_excel(outputs["horizontal_xlsx"], index=False)

    for key, path in outputs.items():
        print(f"Saved {key}: {path}")


def main() -> None:
    t0 = time.time()
    _, panel = load_analysis_frame()
    catalog_df = build_scheme_catalog()
    print(f"[info] scheme_count={len(catalog_df)} curated={(catalog_df['scheme_source'] == 'curated').sum()} systematic={(catalog_df['scheme_source'] == 'systematic').sum()}")
    print(f"[info] scientific_rules: keep core vars {CORE_VARS}, one proxy per conceptual family, and preserve curated schemes.")

    summary_df, coef_df, vif_df, lancet_df = fit_model_space(catalog_df, panel)
    summary_df = enrich_summary_for_screening(summary_df, coef_df)
    summary_df, ranking_df = build_ranking(summary_df)
    horizontal_top_df = build_horizontal_top(summary_df, ranking_df)
    save_outputs(catalog_df, summary_df, ranking_df, coef_df, vif_df, lancet_df, horizontal_top_df)

    elapsed = time.time() - t0
    print(f"[done] total_models={len(summary_df)} total_seconds={elapsed:.1f}")


if __name__ == "__main__":
    main()
