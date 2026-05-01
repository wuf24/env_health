from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize, TwoSlopeNorm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from scipy.stats import pearsonr


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "public_dashboards" / "sys-08952-paper-analysis"
ASSET_DIR = OUTPUT_DIR / "assets"
DATA_DIR = OUTPUT_DIR / "data"
OUTPUT_HTML = OUTPUT_DIR / "index.html"
OUTPUT_PAYLOAD = DATA_DIR / "sys08952_paper_payload.json"

TARGET_SCHEME_ID = "SYS_08952"
TARGET_MODEL_ID = "SYS_08952 | Province: No / Year: Yes"
TARGET_ROLE_ID = "main_model"

DECISION_PAYLOAD = (
    ROOT
    / "public_dashboards"
    / "variable-group-deep-dive"
    / "data"
    / "decision_payload.json"
)
AMR_PATH = ROOT / "amr_rate.csv"
X_PATH = ROOT / "climate_social_eco.csv"
LANCET_TABLE_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_lancet_tables.csv"
BAYES_DIR = ROOT / "4 贝叶斯分析" / "results" / "model_summaries"
EXTENDED_BAYES_DIR = ROOT / "4 贝叶斯分析" / "results" / "sys08952_extended_interactions"
COUNTERFACTUAL_DIR = ROOT / "5 反事实推演" / "results" / "AMR_AGG"
CHINA_GEOJSON_PATH = ROOT / "5 反事实推演" / "assets" / "china_provinces.geojson"
FUTURE_DIR = ROOT / "6 未来情景分析" / "results"
REGION_MAP_PATH = ROOT / "6 未来情景分析" / "data_processed" / "province_to_region_7zones.csv"

AMR_COLUMNS = [
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

VARIABLE_LABELS = {
    "R1xday": "R1xday",
    "抗菌药物使用强度": "AMC",
    "TA（°C）": "TA",
    "氮氧化物": "NOx",
    "医疗水平": "Medical",
    "人均日生活用水量(升)": "Water use",
    "牲畜饲养 - 猪年底头数": "Pigs",
    "文盲比例": "Illiteracy",
}
VARIABLE_GROUPS = {
    "R1xday": "气候：极端降雨",
    "抗菌药物使用强度": "抗菌药物压力",
    "TA（°C）": "气候：温度",
    "氮氧化物": "污染环境",
    "医疗水平": "医疗系统/检测代理",
    "人均日生活用水量(升)": "供水与生活条件",
    "牲畜饲养 - 猪年底头数": "畜牧暴露",
    "文盲比例": "社会经济结构",
}

BAYES_VARIANT_ORDER = [
    "year_only_additive",
    "year_only_amplification",
    "province_only_additive",
    "province_only_amplification",
    "province_year_additive",
    "province_year_amplification",
]
BAYES_VARIANT_LABELS = {
    "year_only_additive": "Year-only 主效应",
    "year_only_amplification": "Year-only 放大效应",
    "province_only_additive": "Province-only 主效应",
    "province_only_amplification": "Province-only 放大效应",
    "province_year_additive": "Province + Year 主效应",
    "province_year_amplification": "Province + Year 放大效应",
}
EXTENDED_BAYES_VARIANT_ORDER = [
    "year_only_ta_amc_amplification",
    "year_only_climate_amc_triple",
]
EXTENDED_BAYES_VARIANT_LABELS = {
    "year_only_ta_amc_amplification": "Year-only TA × AMC",
    "year_only_climate_amc_triple": "Year-only 层级三重交互",
}
SCENARIO_ORDER = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
SCENARIO_LABELS = {
    "ssp119": "SSP1-1.9",
    "ssp126": "SSP1-2.6",
    "ssp245": "SSP2-4.5",
    "ssp370": "SSP3-7.0",
    "ssp585": "SSP5-8.5",
}
COUNTERFACTUAL_ORDER = [
    "all_climate_to_baseline",
    "temperature_to_baseline",
    "r1xday_to_baseline",
]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return (
        str(value)
        .replace("\r\n", "\n")
        .replace("\n-", " - ")
        .replace("\n", " ")
        .replace("  ", " ")
        .strip()
    )


def normalize_name(value: Any) -> str:
    return "".join(clean_text(value).lower().split())


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def fmt(value: Any, digits: int = 3, *, signed: bool = False) -> str:
    numeric = as_float(value)
    if numeric is None:
        return "—"
    prefix = "+" if signed and numeric > 0 else ""
    return f"{prefix}{numeric:.{digits}f}"


def fmt_pct(value: Any, digits: int = 1) -> str:
    numeric = as_float(value)
    if numeric is None:
        return "—"
    return f"{numeric:.{digits}f}%"


def fmt_prob(value: Any) -> str:
    numeric = as_float(value)
    if numeric is None:
        return "—"
    return f"{100 * numeric:.1f}%"


def fmt_p(value: Any) -> str:
    numeric = as_float(value)
    if numeric is None:
        return "—"
    if numeric < 0.0001:
        return "<0.0001"
    return f"{numeric:.4f}"


def fmt_interval(low: Any, high: Any, digits: int = 3) -> str:
    low_num = as_float(low)
    high_num = as_float(high)
    if low_num is None or high_num is None:
        return "—"
    return f"[{low_num:.{digits}f}, {high_num:.{digits}f}]"


def stars(p_value: Any) -> str:
    p = as_float(p_value)
    if p is None:
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def p_to_star(p_value: Any) -> str:
    return stars(p_value)


def sign_class(value: Any) -> str:
    numeric = as_float(value)
    if numeric is None:
        return ""
    return "pos" if numeric >= 0 else "neg"


def signed_log1p(value: Any) -> float | None:
    numeric = as_float(value)
    if numeric is None:
        return None
    return math.copysign(math.log1p(abs(numeric)), numeric)


def province_key(value: Any) -> str:
    name = clean_text(value)
    if not name:
        return "南海诸岛"
    replacements = [
        ("特别行政区", ""),
        ("维吾尔自治区", ""),
        ("壮族自治区", ""),
        ("回族自治区", ""),
        ("自治区", ""),
        ("省", ""),
        ("市", ""),
    ]
    for old, new in replacements:
        name = name.replace(old, new)
    return name.strip()


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_target_model() -> dict[str, Any]:
    payload = json.loads(DECISION_PAYLOAD.read_text(encoding="utf-8"))
    for model in payload["models"]:
        if model["scheme_id"] == TARGET_SCHEME_ID and model["model_id"] == TARGET_MODEL_ID:
            return model
    raise KeyError(f"{TARGET_MODEL_ID} not found in {DECISION_PAYLOAD}")


def resolve_variables(raw_variables: list[str], columns: list[str]) -> list[str]:
    lookup = {normalize_name(column): column for column in columns}
    resolved: list[str] = []
    for item in raw_variables:
        key = normalize_name(item)
        if key not in lookup:
            raise KeyError(f"Cannot resolve variable `{item}` against analysis frame.")
        resolved.append(lookup[key])
    return resolved


def load_panel(raw_variables: list[str]) -> tuple[pd.DataFrame, list[str]]:
    amr = read_csv(AMR_PATH)
    x = read_csv(X_PATH).rename(columns={"省份": "Province", "YEAR": "Year"})
    for col in AMR_COLUMNS:
        amr[col] = pd.to_numeric(amr[col], errors="coerce")
        std = amr[col].std(ddof=0)
        if pd.isna(std) or std == 0:
            raise ValueError(f"Cannot standardize AMR column {col}.")
        amr[f"{col}_z"] = (amr[col] - amr[col].mean()) / std
    amr["AMR_AGG_z"] = amr[[f"{col}_z" for col in AMR_COLUMNS]].mean(axis=1)
    panel = amr.merge(x, on=["Province", "Year"], how="inner")
    panel = panel.sort_values(["Province", "Year"]).reset_index(drop=True)
    resolved = resolve_variables(raw_variables, list(panel.columns))
    for col in resolved:
        panel[col] = pd.to_numeric(panel[col], errors="coerce")
    return panel, resolved


def run_univariate(panel: pd.DataFrame, variables: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variable in variables:
        tmp = panel[["AMR_AGG_z", variable]].dropna().copy()
        x = tmp[variable].astype(float)
        y = tmp["AMR_AGG_z"].astype(float)
        x_sd = x.std(ddof=0)
        if len(tmp) < 3 or x_sd == 0:
            continue
        x_z = (x - x.mean()) / x_sd
        model = sm.OLS(y, sm.add_constant(x_z)).fit()
        r, r_p = pearsonr(x_z, y)
        ci_low, ci_high = model.conf_int().iloc[1].tolist()
        p_value = float(model.pvalues.iloc[1])
        rows.append(
            {
                "source_variable": variable,
                "variable": clean_text(variable),
                "short_label": VARIABLE_LABELS.get(clean_text(variable), clean_text(variable)),
                "group": VARIABLE_GROUPS.get(clean_text(variable), "控制变量"),
                "n": int(len(tmp)),
                "std_beta": float(model.params.iloc[1]),
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                "p_value": p_value,
                "pearson_r": float(r),
                "pearson_p": float(r_p),
                "direction": "positive" if model.params.iloc[1] >= 0 else "negative",
                "significant": bool(p_value < 0.05),
            }
        )
    return rows


def add_gdp_group(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    if "GDP" not in out.columns:
        out["Group"] = "All"
        return out

    def year_quantile_group(values: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(values, errors="coerce")
        ranked = numeric.rank(method="first")
        try:
            return pd.qcut(ranked, 4, labels=["L", "LM", "UM", "H"])
        except ValueError:
            return pd.Series(["All"] * len(values), index=values.index)

    out["Group"] = out.groupby("Year")["GDP"].transform(year_quantile_group).astype(str)
    return out


def diag_kde(x: pd.Series, **_: Any) -> None:
    ax = plt.gca()
    values = pd.to_numeric(pd.Series(x), errors="coerce").dropna().to_numpy()
    if len(values) >= 10 and np.nanstd(values) > 0:
        sns.kdeplot(x=values, fill=True, alpha=0.22, linewidth=1.2, ax=ax)
    else:
        ax.hist(values, bins=10, alpha=0.28)


def lower_scatter_group_reg(x: pd.Series, y: pd.Series, color: str | None = None, **_: Any) -> None:
    ax = plt.gca()
    x_values = pd.to_numeric(pd.Series(x), errors="coerce").to_numpy()
    y_values = pd.to_numeric(pd.Series(y), errors="coerce").to_numpy()
    mask = np.isfinite(x_values) & np.isfinite(y_values)
    ax.scatter(x_values[mask], y_values[mask], s=12, alpha=0.26, color=color, edgecolor="none")
    if mask.sum() >= 10 and np.nanstd(x_values[mask]) > 0 and np.nanstd(y_values[mask]) > 0:
        slope, intercept = np.polyfit(x_values[mask], y_values[mask], 1)
        xs = np.linspace(np.nanmin(x_values[mask]), np.nanmax(x_values[mask]), 60)
        ax.plot(xs, slope * xs + intercept, color=color, linewidth=1.3)


def upper_group_corr_text(data: pd.DataFrame, x: str, y: str, group_col: str) -> None:
    ax = plt.gca()
    ax.axis("off")
    xx = pd.to_numeric(data[x], errors="coerce").to_numpy()
    yy = pd.to_numeric(data[y], errors="coerce").to_numpy()
    mask = np.isfinite(xx) & np.isfinite(yy)
    if mask.sum() >= 10 and np.nanstd(xx[mask]) > 0 and np.nanstd(yy[mask]) > 0:
        r, p_value = pearsonr(xx[mask], yy[mask])
        ax.text(0.04, 0.84, f"Corr: {r:.3f}{p_to_star(p_value)}", transform=ax.transAxes, fontsize=8.5, color="#17252c")
    y_pos = 0.64
    for group, color in [("H", "tab:blue"), ("UM", "tab:orange"), ("LM", "tab:green"), ("L", "tab:red")]:
        sub = data[data[group_col].eq(group)]
        sx = pd.to_numeric(sub[x], errors="coerce").to_numpy()
        sy = pd.to_numeric(sub[y], errors="coerce").to_numpy()
        group_mask = np.isfinite(sx) & np.isfinite(sy)
        if group_mask.sum() >= 8 and np.nanstd(sx[group_mask]) > 0 and np.nanstd(sy[group_mask]) > 0:
            rr, pp = pearsonr(sx[group_mask], sy[group_mask])
            ax.text(0.04, y_pos, f"{group}: {rr:.3f}{p_to_star(pp)}", transform=ax.transAxes, fontsize=7.8, color=color)
        y_pos -= 0.14


def plot_univariate(panel: pd.DataFrame, rows: list[dict[str, Any]]) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 4, figsize=(16, 8), constrained_layout=True)
    axes = axes.ravel()
    for ax, row in zip(axes, rows):
        variable = row["source_variable"]
        tmp = panel[["AMR_AGG_z", variable]].dropna().copy()
        x = tmp[variable].astype(float)
        y = tmp["AMR_AGG_z"].astype(float)
        x_z = (x - x.mean()) / x.std(ddof=0)
        ax.scatter(x_z, y, s=18, alpha=0.38, color="#2563eb", edgecolor="none")
        xs = np.linspace(x_z.min(), x_z.max(), 100)
        ax.plot(xs, sm.OLS(y, sm.add_constant(x_z)).fit().predict(sm.add_constant(xs)), color="#0f766e", lw=2)
        ax.axhline(0, color="#94a3b8", lw=0.8, ls="--")
        ax.axvline(0, color="#94a3b8", lw=0.8, ls="--")
        ax.set_title(
            f"{row['short_label']}  β={fmt(row['std_beta'], 2, signed=True)}{stars(row['p_value'])}",
            fontsize=11,
            loc="left",
        )
        ax.set_xlabel("X standardized")
        ax.set_ylabel("AMR_AGG_z")
        ax.grid(True, color="#e2e8f0", lw=0.6)
    for ax in axes[len(rows) :]:
        ax.axis("off")
    fig.suptitle("SYS_08952 variables: univariate associations with AMR_AGG_z", fontsize=15, fontweight="bold")
    fig.savefig(ASSET_DIR / "univariate_scatter_grid.png", dpi=180)
    plt.close(fig)

    sorted_rows = sorted(rows, key=lambda item: item["std_beta"])
    fig, ax = plt.subplots(figsize=(9, 5.2), constrained_layout=True)
    y_pos = np.arange(len(sorted_rows))
    betas = [row["std_beta"] for row in sorted_rows]
    low = [row["std_beta"] - row["ci_low"] for row in sorted_rows]
    high = [row["ci_high"] - row["std_beta"] for row in sorted_rows]
    colors = ["#0f766e" if beta >= 0 else "#be123c" for beta in betas]
    ax.barh(y_pos, betas, color=colors, alpha=0.18)
    ax.errorbar(betas, y_pos, xerr=[low, high], fmt="o", color="#17252c", ecolor="#64748b", capsize=3)
    ax.axvline(0, color="#334155", lw=1)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([row["short_label"] for row in sorted_rows])
    ax.set_xlabel("Standardized univariate coefficient")
    ax.set_title("Univariate coefficient forest plot", loc="left", fontweight="bold")
    ax.grid(axis="x", color="#e2e8f0", lw=0.7)
    fig.savefig(ASSET_DIR / "univariate_forest.png", dpi=180)
    plt.close(fig)

    pair_panel = add_gdp_group(panel)
    source_vars = [row["source_variable"] for row in rows]
    rename_map = {row["source_variable"]: row["short_label"] for row in rows}
    plot_cols = source_vars + ["AMR_AGG_z"]
    d = pair_panel[plot_cols + ["Group"]].rename(columns={**rename_map, "AMR_AGG_z": "AMR_AGG_z"}).dropna(subset=[rename_map.get(col, col) for col in source_vars] + ["AMR_AGG_z"])
    vars_list = [rename_map.get(col, col) for col in source_vars] + ["AMR_AGG_z"]
    if len(d) >= 60:
        sns.set_theme(style="white", font="Microsoft YaHei")
        grid = sns.PairGrid(d, vars=vars_list, hue="Group", hue_order=["H", "UM", "LM", "L"], corner=False, diag_sharey=False, height=1.0)
        grid.map_diag(diag_kde)
        grid.map_lower(lower_scatter_group_reg)
        for i in range(len(vars_list)):
            for j in range(len(vars_list)):
                ax = grid.axes[i, j]
                if j <= i:
                    continue
                plt.sca(ax)
                upper_group_corr_text(d, vars_list[j], vars_list[i], "Group")
        grid.add_legend(title="GDP group")
        grid.fig.set_size_inches(16.5, 15.6)
        grid.fig.suptitle("SYS_08952 variables and AMR_AGG_z: raw-scale pairwise correlations", y=1.01, fontsize=18)
        for ax in grid.axes.flat:
            if ax is not None:
                ax.tick_params(labelsize=8)
                ax.xaxis.label.set_size(10)
                ax.yaxis.label.set_size(10)
        grid.fig.tight_layout()
        grid.fig.savefig(ASSET_DIR / "univariate_pairgrid_sys08952.png", dpi=220, bbox_inches="tight")
        plt.close(grid.fig)


def load_lancet_table() -> list[dict[str, Any]]:
    df = read_csv(LANCET_TABLE_PATH)
    rows = df[df["model_id"] == TARGET_MODEL_ID].to_dict(orient="records")
    out: list[dict[str, Any]] = []
    for row in rows:
        predictor = clean_text(row.get("Predictor"))
        if not predictor or predictor == TARGET_MODEL_ID:
            continue
        if predictor in {"R-squared (Overall)", "R² (within)"}:
            continue
        if predictor == "R-squared":
            predictor = "R-squared (model)"
        out.append(
            {
                "predictor": predictor,
                "coefficient": clean_text(row.get("Coefficient")),
                "ci": clean_text(row.get("95% CI")),
                "p_value": clean_text(row.get("p value")),
            }
        )
    return out


def load_bayes_rows_from(base_dir: Path, variant_order: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for variant_id in variant_order:
        path = base_dir / f"SYS_08952__ProvinceNo-YearYes__{variant_id}_posterior_summary.csv"
        if not path.exists():
            out[variant_id] = []
            continue
        rows = []
        for row in read_csv(path).to_dict(orient="records"):
            rows.append(
                {
                    **row,
                    "variable": clean_text(row.get("variable")),
                    "posterior_mean": as_float(row.get("posterior_mean")),
                    "crI_2_5": as_float(row.get("crI_2_5")),
                    "crI_97_5": as_float(row.get("crI_97_5")),
                    "prob_gt_0": as_float(row.get("prob_gt_0")),
                }
            )
        out[variant_id] = rows
    return out


def load_bayes_rows() -> dict[str, list[dict[str, Any]]]:
    return load_bayes_rows_from(BAYES_DIR, BAYES_VARIANT_ORDER)


def load_extended_bayes_rows() -> dict[str, list[dict[str, Any]]]:
    return load_bayes_rows_from(EXTENDED_BAYES_DIR, EXTENDED_BAYES_VARIANT_ORDER)


def load_bayes_diagnostics_from(base_dir: Path) -> dict[str, dict[str, Any]]:
    path = base_dir / "combined_diagnostics.csv"
    if not path.exists():
        return {}
    df = read_csv(path)
    df = df[(df["scheme_id"] == TARGET_SCHEME_ID) & (df["model_id"] == TARGET_MODEL_ID)]
    out: dict[str, dict[str, Any]] = {}
    for variant_id, group in df.groupby("variant_id"):
        r_hat = pd.to_numeric(group["r_hat"], errors="coerce")
        ess_bulk = pd.to_numeric(group["ess_bulk"], errors="coerce")
        ess_tail = pd.to_numeric(group["ess_tail"], errors="coerce")
        out[str(variant_id)] = {
            "max_rhat": float(r_hat.max()),
            "min_ess_bulk": float(ess_bulk.min()),
            "min_ess_tail": float(ess_tail.min()),
            "share_rhat_gt_1_01": float((r_hat > 1.01).mean()),
        }
    return out


def load_bayes_diagnostics() -> dict[str, dict[str, Any]]:
    return load_bayes_diagnostics_from(BAYES_DIR)


def load_extended_bayes_diagnostics() -> dict[str, dict[str, Any]]:
    return load_bayes_diagnostics_from(EXTENDED_BAYES_DIR)


def bayes_row(
    bayes_rows: dict[str, list[dict[str, Any]]],
    variant_id: str,
    variable: str,
    effect_scope: str | None = None,
) -> dict[str, Any] | None:
    for row in bayes_rows.get(variant_id, []):
        if row.get("variable") != variable:
            continue
        if effect_scope is not None and row.get("effect_scope") != effect_scope:
            continue
        return row
    return None


def crosses_zero(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    low = as_float(row.get("crI_2_5"))
    high = as_float(row.get("crI_97_5"))
    return low is not None and high is not None and low <= 0 <= high


def load_counterfactual() -> dict[str, Any]:
    base = COUNTERFACTUAL_DIR / "counterfactual_outputs"
    frames = {
        "overall": read_csv(base / "national_overall.csv"),
        "yearly": read_csv(base / "national_yearly.csv"),
        "province_average": read_csv(base / "province_average.csv"),
        "latest_year": read_csv(base / "latest_year_province.csv"),
    }
    filters = {"scheme_id": TARGET_SCHEME_ID, "role_id": TARGET_ROLE_ID}
    filtered: dict[str, pd.DataFrame] = {}
    for name, df in frames.items():
        mask = pd.Series(True, index=df.index)
        for key, value in filters.items():
            mask &= df[key].astype(str).eq(value)
        filtered[name] = df[mask].copy()
    overall = filtered["overall"]
    yearly = filtered["yearly"]
    province_avg = filtered["province_average"]
    latest = filtered["latest_year"]
    region_map = read_csv(REGION_MAP_PATH)
    province_region_col = "Province"
    region_col = "region"
    if "province" in region_map.columns and "Province" not in region_map.columns:
        region_map = region_map.rename(columns={"province": "Province"})
    if "region_zh" in region_map.columns:
        region_col = "region_zh"
    elif "Region" in region_map.columns:
        region_col = "Region"
    region = province_avg.merge(region_map[[province_region_col, region_col]], on="Province", how="left")
    region_summary = (
        region.groupby(["scenario_id", "scenario_label", region_col], dropna=False)
        .agg(
            province_n=("Province", "nunique"),
            actual_minus_counterfactual_mean=("actual_minus_counterfactual_mean", "mean"),
            relative_change_pct_mean=("relative_change_pct_mean", "mean"),
        )
        .reset_index()
        .rename(columns={region_col: "region"})
    )
    return {
        "overall": overall,
        "yearly": yearly,
        "province_average": province_avg,
        "latest_year": latest,
        "region_summary": region_summary,
    }


def load_future_scale_stats(variables: list[str]) -> dict[str, float]:
    amr = read_csv(AMR_PATH)
    x = read_csv(X_PATH)
    x = x.rename(columns={x.columns[0]: "Province", x.columns[1]: "Year"})
    for df in (amr, x):
        df["Province"] = df["Province"].astype(str).str.strip()
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    base = amr[["Province", "Year"]].merge(x, on=["Province", "Year"], how="inner")
    base = base[base["Year"].between(2014, 2023)].copy()
    base = base[~base["Province"].isin({"全国", "μ", "σ"})].copy()

    stats: dict[str, float] = {}
    for variable in variables:
        if variable not in base.columns:
            continue
        raw = pd.to_numeric(base[variable], errors="coerce")
        filled = raw.groupby(base["Province"]).transform(lambda item: item.fillna(item.median()))
        filled = filled.fillna(raw.median())
        std = float(np.nanstd(filled.values, ddof=0))
        stats[variable] = std if math.isfinite(std) and std != 0 else 1.0
    return stats


def load_future() -> dict[str, Any]:
    lancet_dir = FUTURE_DIR / "lancet_ets"
    national = read_csv(lancet_dir / "projection_outputs" / "scenario_summary_2050.csv")
    yearly = read_csv(lancet_dir / "projection_outputs" / "national_yearly.csv")
    regional = read_csv(lancet_dir / "regional_outputs" / "region_summary_2050.csv")
    province = read_csv(lancet_dir / "projection_outputs" / "province_projection_2050.csv")
    coef = read_csv(FUTURE_DIR / "model_screening" / "future_projection_coefficients.csv")
    coef = coef[(coef["scheme_id"] == TARGET_SCHEME_ID) & (coef["role_id"] == TARGET_ROLE_ID)]
    coef_map = {clean_text(row["predictor"]): float(row["coef"]) for row in coef.to_dict(orient="records")}
    r1_coef = coef_map["R1xday"]
    ta_coef = coef_map["TA（°C）"]
    scale_stats = load_future_scale_stats(list(coef_map))
    r1_scale = scale_stats.get("R1xday", 1.0)
    ta_scale = scale_stats.get("TA（°C）", 1.0)

    def filter_main(df: pd.DataFrame) -> pd.DataFrame:
        return df[
            (df["scheme_id"] == TARGET_SCHEME_ID)
            & (df["role_id"] == TARGET_ROLE_ID)
            & (df["baseline_mode"] == "lancet_ets")
        ].copy()

    def numeric_delta(
        out: pd.DataFrame,
        mean_col: str,
        raw_col: str,
        scenario_col: str | None = None,
        baseline_col: str | None = None,
    ) -> pd.Series:
        if mean_col in out.columns:
            return pd.to_numeric(out[mean_col], errors="coerce")
        if raw_col in out.columns:
            return pd.to_numeric(out[raw_col], errors="coerce")
        if scenario_col and baseline_col and scenario_col in out.columns and baseline_col in out.columns:
            return pd.to_numeric(out[scenario_col], errors="coerce") - pd.to_numeric(out[baseline_col], errors="coerce")
        return pd.Series(0.0, index=out.index, dtype=float)

    def add_decomposition(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        r1_delta = numeric_delta(
            out,
            "rx1day_delta_mean",
            "rx1day_delta",
            "rx1day_scenario_mean",
            "rx1day_baseline_mean",
        )
        ta_delta = numeric_delta(out, "temperature_delta_mean", "temperature_delta")
        out["r1xday_delta_standardized"] = r1_delta / r1_scale
        out["ta_delta_standardized"] = ta_delta / ta_scale
        out["r1xday_contribution"] = r1_coef * out["r1xday_delta_standardized"]
        out["ta_contribution"] = ta_coef * out["ta_delta_standardized"]
        out["joint_climate_contribution"] = numeric_delta(out, "delta_vs_baseline_mean", "delta_vs_baseline")
        out["decomp_residual"] = out["joint_climate_contribution"] - out["r1xday_contribution"] - out["ta_contribution"]
        return out

    national = add_decomposition(filter_main(national))
    yearly = add_decomposition(filter_main(yearly))
    regional = add_decomposition(filter_main(regional))
    province = add_decomposition(filter_main(province))
    return {
        "coef_map": coef_map,
        "scale_stats": scale_stats,
        "national": national,
        "yearly": yearly,
        "regional": regional,
        "province": province,
    }


def df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.replace({np.nan: None}).to_json(orient="records", force_ascii=False))


def geojson_polygons(geometry: dict[str, Any]) -> list[list[list[float]]]:
    if geometry.get("type") == "Polygon":
        return [geometry.get("coordinates", [])]
    if geometry.get("type") == "MultiPolygon":
        return [polygon for polygon in geometry.get("coordinates", [])]
    return []


def map_norm(values: list[float]) -> Normalize | TwoSlopeNorm:
    if not values:
        return Normalize(vmin=-1, vmax=1)
    vmin = min(values)
    vmax = max(values)
    if math.isclose(vmin, vmax):
        return Normalize(vmin=vmin - 1, vmax=vmax + 1)
    if vmin < 0 < vmax:
        return TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
    return Normalize(vmin=vmin, vmax=vmax)


def draw_china_map(
    ax: plt.Axes,
    value_map: dict[str, float],
    title: str,
    *,
    cmap_name: str = "RdBu_r",
    transform: str | None = None,
    cbar_label: str = "",
) -> ScalarMappable:
    geo = json.loads(CHINA_GEOJSON_PATH.read_text(encoding="utf-8"))
    cmap = plt.get_cmap(cmap_name)
    transformed: dict[str, float] = {}
    for key, value in value_map.items():
        numeric = as_float(value)
        if numeric is None:
            continue
        transformed_value = signed_log1p(numeric) if transform == "signed_log1p" else numeric
        if transformed_value is not None:
            transformed[key] = transformed_value
    norm = map_norm(list(transformed.values()))
    missing_color = "#d1d5db"
    edge_color = "#ffffff"

    for feature in geo.get("features", []):
        raw_name = clean_text(feature.get("properties", {}).get("name"))
        name_key = province_key(raw_name)
        value = transformed.get(name_key)
        face = missing_color if value is None else cmap(norm(value))
        for polygon in geojson_polygons(feature.get("geometry", {})):
            if not polygon:
                continue
            exterior = polygon[0]
            xs = [point[0] for point in exterior]
            ys = [point[1] for point in exterior]
            ax.fill(xs, ys, facecolor=face, edgecolor=edge_color, linewidth=0.35)

    ax.set_xlim(73, 135)
    ax.set_ylim(3, 54)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    ax.text(
        0.01,
        0.02,
        "灰色：无港澳台、南沙群岛/南海诸岛观测值",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#475569",
        bbox={"facecolor": "white", "edgecolor": "#d8e1e6", "boxstyle": "round,pad=0.25", "alpha": 0.88},
    )
    return sm


def plot_counterfactual_figures(cf: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    colors = {
        "all_climate_to_baseline": "#17252c",
        "temperature_to_baseline": "#0f766e",
        "r1xday_to_baseline": "#2563eb",
    }

    yearly = cf["yearly"].copy()
    overall = cf["overall"].copy()
    fig, axes = plt.subplots(1, 2, figsize=(13.4, 4.8), constrained_layout=True)
    for scenario_id in COUNTERFACTUAL_ORDER:
        sub = yearly[yearly["scenario_id"].eq(scenario_id)].sort_values("Year")
        if sub.empty:
            continue
        label = "R1xday + TA" if scenario_id == "all_climate_to_baseline" else str(sub["scenario_label"].iloc[0])
        axes[0].plot(
            sub["Year"],
            sub["actual_minus_counterfactual_mean"],
            marker="o",
            linewidth=2.1,
            color=colors.get(scenario_id, "#64748b"),
            label=label,
        )
    axes[0].axhline(0, color="#334155", linewidth=0.9)
    axes[0].set_title("Annual actual - counterfactual", loc="left", fontweight="bold")
    axes[0].set_ylabel("AMR_AGG_z delta")
    axes[0].grid(True, color="#e2e8f0", linewidth=0.7)
    axes[0].legend(frameon=False, fontsize=9)

    overall["order"] = overall["scenario_id"].map({sid: idx for idx, sid in enumerate(COUNTERFACTUAL_ORDER)})
    overall = overall.sort_values("order")
    labels = ["R1xday + TA" if sid == "all_climate_to_baseline" else str(label) for sid, label in zip(overall["scenario_id"], overall["scenario_label"])]
    axes[1].bar(
        np.arange(len(overall)),
        overall["actual_minus_counterfactual_mean"].astype(float),
        color=[colors.get(item, "#64748b") for item in overall["scenario_id"]],
        alpha=0.86,
    )
    axes[1].axhline(0, color="#334155", linewidth=0.9)
    axes[1].set_xticks(np.arange(len(overall)))
    axes[1].set_xticklabels(labels, rotation=18, ha="right")
    axes[1].set_title("National mean by rollback scenario", loc="left", fontweight="bold")
    axes[1].set_ylabel("AMR_AGG_z delta")
    axes[1].grid(axis="y", color="#e2e8f0", linewidth=0.7)
    fig.savefig(ASSET_DIR / "counterfactual_sys08952_national.png", dpi=190)
    plt.close(fig)

    latest = cf["latest_year"]
    latest = latest[latest["scenario_id"].eq("all_climate_to_baseline")]
    value_map = {
        province_key(row["Province"]): float(row["actual_minus_counterfactual_mean"])
        for row in latest.to_dict(orient="records")
    }
    fig, ax = plt.subplots(figsize=(8.8, 7.5), constrained_layout=True)
    sm = draw_china_map(
        ax,
        value_map,
        "Province delta map: R1xday + TA rollback",
        transform="signed_log1p",
        cmap_name="RdBu_r",
        cbar_label="signed log1p(delta)",
    )
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.045, pad=0.04)
    cbar.set_label("signed log1p(Actual - Counterfactual)")
    raw_ticks = [latest["actual_minus_counterfactual_mean"].min(), 0, latest["actual_minus_counterfactual_mean"].median(), latest["actual_minus_counterfactual_mean"].max()]
    tick_positions = [signed_log1p(item) for item in raw_ticks]
    cbar.set_ticks([item for item in tick_positions if item is not None])
    cbar.set_ticklabels([fmt(item, 2, signed=True) for item in raw_ticks])
    fig.savefig(ASSET_DIR / "counterfactual_china_map_sys08952_signedlog.png", dpi=190)
    plt.close(fig)


def plot_future_decomposition(future: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    rows = future["national"]
    rows = rows[(rows["statistic"] == "median") & (rows["scenario_id"].isin(SCENARIO_ORDER))]
    rows = rows.set_index("scenario_id").loc[SCENARIO_ORDER].reset_index()
    fig, ax = plt.subplots(figsize=(10.2, 4.9), constrained_layout=True)
    x = np.arange(len(rows))
    r1 = rows["r1xday_contribution"].astype(float).to_numpy()
    ta = rows["ta_contribution"].astype(float).to_numpy()
    joint = rows["joint_climate_contribution"].astype(float).to_numpy()
    width = 0.24
    ax.bar(x - width, r1, width=width, label="R1xday only", color="#2563eb", alpha=0.82)
    ax.bar(x, ta, width=width, label="TA only", color="#0f766e", alpha=0.82)
    ax.bar(x + width, joint, width=width, label="R1xday + TA", color="#17252c", alpha=0.82)
    ax.axhline(0, color="#334155", lw=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS[item] for item in rows["scenario_id"]])
    ax.set_ylabel("2050 delta vs Lancet ETS baseline")
    ax.set_title("Lancet ETS 2050 climate components", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.grid(axis="y", color="#e2e8f0", lw=0.7)
    fig.savefig(ASSET_DIR / "future_lancet_decomposition.png", dpi=180)
    plt.close(fig)

    yearly = future["yearly"]
    yearly = yearly[(yearly["statistic"] == "median") & (yearly["scenario_id"] == "ssp585")].sort_values("Year")
    fig, ax = plt.subplots(figsize=(9.8, 4.8), constrained_layout=True)
    ax.plot(yearly["Year"], yearly["r1xday_contribution"], label="R1xday only", color="#2563eb", linewidth=2.2)
    ax.plot(yearly["Year"], yearly["ta_contribution"], label="TA only", color="#0f766e", linewidth=2.2)
    ax.plot(yearly["Year"], yearly["joint_climate_contribution"], label="R1xday + TA", color="#17252c", linewidth=2.4)
    ax.axhline(0, color="#334155", linewidth=0.9)
    ax.set_title("SSP5-8.5 component trajectories", loc="left", fontweight="bold")
    ax.set_ylabel("Delta vs Lancet ETS baseline")
    ax.grid(True, color="#e2e8f0", linewidth=0.7)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    fig.savefig(ASSET_DIR / "future_component_trajectories_ssp585.png", dpi=180)
    plt.close(fig)

    province = future["province"]
    province = province[(province["statistic"] == "median") & (province["scenario_id"] == "ssp585")].copy()
    maps = [
        ("R1xday only", "r1xday_contribution", "#2563eb"),
        ("TA only", "ta_contribution", "#0f766e"),
        ("R1xday + TA", "joint_climate_contribution", "#17252c"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(17.2, 6.5), constrained_layout=True)
    for ax, (title, col, _) in zip(axes, maps):
        value_map = {province_key(row["Province"]): float(row[col]) for row in province.to_dict(orient="records")}
        sm = draw_china_map(ax, value_map, title, cmap_name="RdBu_r", cbar_label=col)
        cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.048, pad=0.04)
        cbar.set_label("2050 contribution")
    fig.savefig(ASSET_DIR / "future_component_maps_ssp585.png", dpi=180)
    plt.close(fig)


def univariate_table(rows: list[dict[str, Any]]) -> str:
    body = []
    for row in sorted(rows, key=lambda item: abs(item["std_beta"]), reverse=True):
        body.append(
            f"""
            <tr>
              <td><strong>{escape(row['variable'])}</strong><span>{escape(row['group'])}</span></td>
              <td class="{sign_class(row['std_beta'])}">{fmt(row['std_beta'], 3, signed=True)}{stars(row['p_value'])}</td>
              <td>{fmt_interval(row['ci_low'], row['ci_high'], 3)}</td>
              <td>{fmt_p(row['p_value'])}</td>
              <td>{fmt(row['pearson_r'], 3, signed=True)}</td>
              <td>{escape(univariate_reading(row))}</td>
            </tr>
            """
        )
    return "\n".join(body)


def univariate_reading(row: dict[str, Any]) -> str:
    direction = "正向" if row["std_beta"] >= 0 else "负向"
    if row["p_value"] < 0.05:
        return f"单因素层面呈{direction}且达到统计显著；进入多变量模型后还需看混杂调整。"
    if row["p_value"] < 0.10:
        return f"单因素层面呈{direction}、接近显著；适合作为候选信号而非强结论。"
    return f"单因素层面呈{direction}但证据不足；主要作为背景探索结果。"


def lancet_table_html(rows: list[dict[str, Any]]) -> str:
    body = []
    for row in rows:
        predictor = row["predictor"]
        if predictor in {"Province", "Year", "R-squared (model)", "Total number of observations"}:
            body.append(
                f"""
                <tr class="meta-row">
                  <td>{escape(predictor)}</td>
                  <td>{escape(row['coefficient'])}</td>
                  <td></td>
                  <td></td>
                </tr>
                """
            )
            continue
        coefficient = row["coefficient"]
        p_value = row["p_value"]
        if stars(p_value) and not coefficient.endswith(stars(p_value)):
            coefficient = f"{coefficient}{stars(p_value)}"
        body.append(
            f"""
            <tr>
              <td><strong>{escape(predictor)}</strong></td>
              <td class="{sign_class(coefficient.replace('*', ''))}">{escape(coefficient)}</td>
              <td>{escape(row['ci'])}</td>
              <td>{escape(p_value)}</td>
            </tr>
            """
        )
    return "\n".join(body)


def bayes_cell(row: dict[str, Any] | None) -> str:
    if row is None:
        return "<span class=\"muted\">该规格未包含</span>"
    return (
        f"<strong class=\"{sign_class(row['posterior_mean'])}\">{fmt(row['posterior_mean'], 3, signed=True)}</strong>"
        f"<span>95% CrI {fmt_interval(row['crI_2_5'], row['crI_97_5'], 3)}</span>"
        f"<span>P(β&gt;0) {fmt_prob(row['prob_gt_0'])}</span>"
    )


def bayes_variant_table(bayes_rows: dict[str, list[dict[str, Any]]], diagnostics: dict[str, dict[str, Any]]) -> str:
    body = []
    for variant_id in BAYES_VARIANT_ORDER:
        r1 = bayes_row(bayes_rows, variant_id, "R1xday", "main")
        amc = bayes_row(bayes_rows, variant_id, "抗菌药物使用强度", "main")
        ta = bayes_row(bayes_rows, variant_id, "TA（°C）", "main")
        inter = bayes_row(bayes_rows, variant_id, "R1xday × 抗菌药物使用强度", "interaction")
        diag = diagnostics.get(variant_id, {})
        body.append(
            f"""
            <tr>
              <td><strong>{escape(BAYES_VARIANT_LABELS[variant_id])}</strong><span>{escape(variant_id)}</span></td>
              <td>{bayes_cell(r1)}</td>
              <td>{bayes_cell(amc)}</td>
              <td>{bayes_cell(ta)}</td>
              <td>{bayes_cell(inter)}</td>
              <td>{escape(bayes_judgement(variant_id, r1, amc, ta, inter))}</td>
              <td>R-hat max {fmt(diag.get('max_rhat'), 2)}<span>ESS bulk min {fmt(diag.get('min_ess_bulk'), 0)}</span></td>
            </tr>
            """
        )
    return "\n".join(body)


def support_label(row: dict[str, Any] | None) -> str:
    if not row:
        return "未估计"
    low = as_float(row.get("crI_2_5"))
    high = as_float(row.get("crI_97_5"))
    mean = as_float(row.get("posterior_mean"))
    if low is not None and high is not None and low > 0:
        return "正向且 CrI 不跨 0"
    if low is not None and high is not None and high < 0:
        return "负向且 CrI 不跨 0"
    if mean is not None and mean > 0:
        return "正向但 CrI 跨 0"
    if mean is not None and mean < 0:
        return "负向但 CrI 跨 0"
    return "CrI 跨 0"


def extended_bayes_interaction_table(
    extended_rows: dict[str, list[dict[str, Any]]],
    extended_diagnostics: dict[str, dict[str, Any]],
) -> str:
    rows = []
    specs = [
        (
            "year_only_ta_amc_amplification",
            bayes_row(extended_rows, "year_only_ta_amc_amplification", "TA（°C） × 抗菌药物使用强度", "interaction"),
            None,
            None,
            "只检验温度是否放大 AMC；结果不支持 TA × AMC 放大。",
        ),
        (
            "year_only_climate_amc_triple",
            bayes_row(extended_rows, "year_only_climate_amc_triple", "TA（°C） × 抗菌药物使用强度", "interaction"),
            bayes_row(extended_rows, "year_only_climate_amc_triple", "R1xday × TA（°C）", "interaction"),
            bayes_row(extended_rows, "year_only_climate_amc_triple", "R1xday × TA（°C） × 抗菌药物使用强度", "interaction"),
            "三重项 CrI 跨 0，不能写三者共同放大；但 R1xday × TA 二阶项为正且不跨 0。",
        ),
    ]
    for variant_id, ta_amc, r1_ta, triple, judgement in specs:
        diag = extended_diagnostics.get(variant_id, {})
        rows.append(
            f"""
            <tr>
              <td><strong>{escape(EXTENDED_BAYES_VARIANT_LABELS[variant_id])}</strong><span>{escape(variant_id)}</span></td>
              <td>{bayes_cell(ta_amc)}<span>{escape(support_label(ta_amc))}</span></td>
              <td>{bayes_cell(r1_ta)}<span>{escape(support_label(r1_ta))}</span></td>
              <td>{bayes_cell(triple)}<span>{escape(support_label(triple))}</span></td>
              <td>{escape(judgement)}</td>
              <td>R-hat max {fmt(diag.get('max_rhat'), 2)}<span>ESS bulk min {fmt(diag.get('min_ess_bulk'), 0)}</span></td>
            </tr>
            """
        )
    return "\n".join(rows)


def bayes_judgement(
    variant_id: str,
    r1: dict[str, Any] | None,
    amc: dict[str, Any] | None,
    ta: dict[str, Any] | None,
    inter: dict[str, Any] | None,
) -> str:
    if variant_id == "year_only_additive":
        return "与正文主模型最一致；R1xday、AMC 与 TA 的 95% CrI 均高于 0，是主效应的核心 Bayes 支持。"
    if variant_id == "year_only_amplification":
        if crosses_zero(inter):
            return "R1xday、AMC、TA 主效应仍以正向为主；交互项均值为正但 CrI 跨 0，因此只能写方向性放大。"
        return "主效应与交互项都支持放大效应。"
    if variant_id.startswith("province_year"):
        return "双重固定效应后效应明显收缩，说明核心信号依赖 Year FE 主识别口径，适合放在 SI 作为保守检验。"
    return "吸收省际长期差异后主效应减弱，提示省际结构差异是主叙事的一部分。"


def counterfactual_overall_table(cf: dict[str, Any]) -> str:
    rows = cf["overall"].copy()
    rows["order"] = rows["scenario_id"].map({sid: idx for idx, sid in enumerate(COUNTERFACTUAL_ORDER)})
    rows = rows.sort_values("order")
    body = []
    for row in rows.to_dict(orient="records"):
        label = "R1xday + TA 共同恢复基准" if row["scenario_id"] == "all_climate_to_baseline" else row["scenario_label"]
        body.append(
            f"""
            <tr>
              <td><strong>{escape(label)}</strong><span>{escape(row['scenario_id'])}</span></td>
              <td class="{sign_class(row['actual_minus_counterfactual_mean'])}">{fmt(row['actual_minus_counterfactual_mean'], 3, signed=True)}</td>
              <td>{fmt_pct(row['relative_change_pct_mean'])}</td>
              <td>{escape(counterfactual_reading(row['scenario_id']))}</td>
            </tr>
            """
        )
    return "\n".join(body)


def counterfactual_reading(scenario_id: str) -> str:
    if scenario_id == "all_climate_to_baseline":
        return "综合气候归因结果；本模型气候变量只有 R1xday 与 TA，因此这就是二者共同影响。"
    if scenario_id == "temperature_to_baseline":
        return "温度通道贡献最大，是反事实结果的主体。"
    if scenario_id == "r1xday_to_baseline":
        return "极端降雨贡献较小，但方向与 FE 和 Bayes 主效应一致。"
    return "气候变量回拨情景。"


def counterfactual_extreme_table(df: pd.DataFrame, scenario_id: str, n: int = 8) -> str:
    rows = df[df["scenario_id"] == scenario_id].sort_values("actual_minus_counterfactual_mean", ascending=False)
    top = rows.head(n)
    bottom = rows.tail(n).sort_values("actual_minus_counterfactual_mean")
    parts = []
    for label, sub in [("贡献最高", top), ("贡献最低", bottom)]:
        parts.append(f"<h4>{escape(label)}</h4><div class=\"table-wrap small\"><table><thead><tr><th>省份</th><th>差值</th><th>相对变化</th></tr></thead><tbody>")
        for row in sub.to_dict(orient="records"):
            parts.append(
                f"<tr><td>{escape(row['Province'])}</td><td class=\"{sign_class(row['actual_minus_counterfactual_mean'])}\">{fmt(row['actual_minus_counterfactual_mean'], 3, signed=True)}</td><td>{fmt_pct(row['relative_change_pct_mean'])}</td></tr>"
            )
        parts.append("</tbody></table></div>")
    return "\n".join(parts)


def counterfactual_region_table(cf: dict[str, Any]) -> str:
    df = cf["region_summary"]
    df = df[df["scenario_id"] == "all_climate_to_baseline"].sort_values("actual_minus_counterfactual_mean", ascending=False)
    return "\n".join(
        f"""
        <tr>
          <td>{escape(str(row['region']))}</td>
          <td>{int(row['province_n'])}</td>
          <td class="{sign_class(row['actual_minus_counterfactual_mean'])}">{fmt(row['actual_minus_counterfactual_mean'], 3, signed=True)}</td>
          <td>{fmt_pct(row['relative_change_pct_mean'])}</td>
        </tr>
        """
        for row in df.to_dict(orient="records")
    )


def future_national_table(future: dict[str, Any]) -> str:
    df = future["national"]
    med = df[(df["statistic"] == "median") & (df["scenario_id"].isin(SCENARIO_ORDER))].copy()
    p10 = df[(df["statistic"] == "p10") & (df["scenario_id"].isin(SCENARIO_ORDER))].set_index("scenario_id")
    p90 = df[(df["statistic"] == "p90") & (df["scenario_id"].isin(SCENARIO_ORDER))].set_index("scenario_id")
    med = med.set_index("scenario_id").loc[SCENARIO_ORDER].reset_index()
    body = []
    for row in med.to_dict(orient="records"):
        scenario_id = row["scenario_id"]
        low = p10.loc[scenario_id, "joint_climate_contribution"] if scenario_id in p10.index else None
        high = p90.loc[scenario_id, "joint_climate_contribution"] if scenario_id in p90.index else None
        body.append(
            f"""
            <tr>
              <td><strong>{escape(SCENARIO_LABELS[scenario_id])}</strong><span>{escape(row['scenario_label'])}</span></td>
              <td>{fmt(row['baseline_pred_mean'], 2)}</td>
              <td class="{sign_class(row['r1xday_contribution'])}">{fmt(row['r1xday_contribution'], 3, signed=True)}</td>
              <td class="{sign_class(row['ta_contribution'])}">{fmt(row['ta_contribution'], 3, signed=True)}</td>
              <td class="{sign_class(row['joint_climate_contribution'])}">{fmt(row['joint_climate_contribution'], 3, signed=True)}</td>
              <td>{fmt_interval(low, high, 3)}</td>
              <td>{fmt(row['scenario_pred_mean'], 2)}</td>
            </tr>
            """
        )
    return "\n".join(body)


def future_region_table(future: dict[str, Any], scenario_id: str = "ssp585") -> str:
    df = future["regional"]
    df = df[(df["statistic"] == "median") & (df["scenario_id"] == scenario_id)].sort_values("joint_climate_contribution", ascending=False)
    return "\n".join(
        f"""
        <tr>
          <td><strong>{escape(row['region'])}</strong><span>{escape(row.get('region_en', ''))}</span></td>
          <td>{int(row['province_n'])}</td>
          <td class="{sign_class(row['r1xday_contribution'])}">{fmt(row['r1xday_contribution'], 3, signed=True)}</td>
          <td class="{sign_class(row['ta_contribution'])}">{fmt(row['ta_contribution'], 3, signed=True)}</td>
          <td class="{sign_class(row['joint_climate_contribution'])}">{fmt(row['joint_climate_contribution'], 3, signed=True)}</td>
          <td>{fmt(row['scenario_pred_mean'], 2)}</td>
        </tr>
        """
        for row in df.to_dict(orient="records")
    )


def future_province_table(future: dict[str, Any], scenario_id: str = "ssp585") -> str:
    df = future["province"]
    df = df[(df["statistic"] == "median") & (df["scenario_id"] == scenario_id)].sort_values("joint_climate_contribution", ascending=False)
    return "\n".join(
        f"""
        <tr>
          <td><strong>{escape(row['Province'])}</strong></td>
          <td>{fmt(row['baseline_pred'], 2)}</td>
          <td class="{sign_class(row['r1xday_contribution'])}">{fmt(row['r1xday_contribution'], 3, signed=True)}</td>
          <td class="{sign_class(row['ta_contribution'])}">{fmt(row['ta_contribution'], 3, signed=True)}</td>
          <td class="{sign_class(row['joint_climate_contribution'])}">{fmt(row['joint_climate_contribution'], 3, signed=True)}</td>
          <td>{fmt(row['scenario_pred'], 2)}</td>
        </tr>
        """
        for row in df.to_dict(orient="records")
    )


def future_extreme_cards(future: dict[str, Any], scenario_id: str = "ssp585") -> str:
    df = future["province"]
    df = df[(df["statistic"] == "median") & (df["scenario_id"] == scenario_id)].sort_values("joint_climate_contribution", ascending=False)
    top = df.head(6)
    bottom = df.tail(6).sort_values("joint_climate_contribution")
    parts = []
    for title, rows in [("SSP5-8.5 增量最高省份", top), ("SSP5-8.5 增量最低省份", bottom)]:
        parts.append(f"<article class=\"mini-card\"><h3>{escape(title)}</h3><table><tbody>")
        for row in rows.to_dict(orient="records"):
            parts.append(
                f"<tr><td>{escape(row['Province'])}</td><td class=\"{sign_class(row['joint_climate_contribution'])}\">{fmt(row['joint_climate_contribution'], 3, signed=True)}</td><td><span>R1 {fmt(row['r1xday_contribution'], 2, signed=True)} / TA {fmt(row['ta_contribution'], 2, signed=True)}</span></td></tr>"
            )
        parts.append("</tbody></table></article>")
    return "\n".join(parts)


def future_component_summary(future: dict[str, Any]) -> str:
    df = future["national"]
    med = df[(df["statistic"] == "median") & (df["scenario_id"].isin(SCENARIO_ORDER))].set_index("scenario_id").loc[SCENARIO_ORDER].reset_index()
    ssp585 = med[med["scenario_id"] == "ssp585"].iloc[0]
    r1_best = med.sort_values("r1xday_contribution", ascending=False).iloc[0]
    ta_best = med.sort_values("ta_contribution", ascending=False).iloc[0]
    joint_best = med.sort_values("joint_climate_contribution", ascending=False).iloc[0]
    joint_low = med.sort_values("joint_climate_contribution", ascending=True).iloc[0]
    return f"""
      <div class="grid three" style="margin-top:12px;">
        <article class="mini-card">
          <span>R1xday 单独分析</span>
          <strong class="value {sign_class(ssp585['r1xday_contribution'])}">{fmt(ssp585['r1xday_contribution'], 3, signed=True)}</strong>
          <p>SSP5-8.5 下 R1xday 单独贡献为 {fmt(ssp585['r1xday_contribution'], 3, signed=True)}；五个 SSP 中最大为 {escape(SCENARIO_LABELS[r1_best['scenario_id']])}（{fmt(r1_best['r1xday_contribution'], 3, signed=True)}）。</p>
        </article>
        <article class="mini-card">
          <span>TA 单独分析</span>
          <strong class="value {sign_class(ssp585['ta_contribution'])}">{fmt(ssp585['ta_contribution'], 3, signed=True)}</strong>
          <p>SSP5-8.5 下 TA 单独贡献为 {fmt(ssp585['ta_contribution'], 3, signed=True)}；五个 SSP 中最大为 {escape(SCENARIO_LABELS[ta_best['scenario_id']])}（{fmt(ta_best['ta_contribution'], 3, signed=True)}）。</p>
        </article>
        <article class="mini-card">
          <span>R1xday + TA 共同作用</span>
          <strong class="value {sign_class(ssp585['joint_climate_contribution'])}">{fmt(ssp585['joint_climate_contribution'], 3, signed=True)}</strong>
          <p>共同作用最高为 {escape(SCENARIO_LABELS[joint_best['scenario_id']])}（{fmt(joint_best['joint_climate_contribution'], 3, signed=True)}），最低为 {escape(SCENARIO_LABELS[joint_low['scenario_id']])}（{fmt(joint_low['joint_climate_contribution'], 3, signed=True)}）。</p>
        </article>
      </div>
    """


def hero_values(model: dict[str, Any], cf: dict[str, Any], future: dict[str, Any], bayes_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    cf_all = cf["overall"][cf["overall"]["scenario_id"] == "all_climate_to_baseline"].iloc[0]
    ssp585 = future["national"][
        (future["national"]["scenario_id"] == "ssp585") & (future["national"]["statistic"] == "median")
    ].iloc[0]
    r1 = bayes_row(bayes_rows, "year_only_additive", "R1xday", "main")
    amc = bayes_row(bayes_rows, "year_only_additive", "抗菌药物使用强度", "main")
    ta = bayes_row(bayes_rows, "year_only_additive", "TA（°C）", "main")
    return {
        "r2": model["fe"]["r2_model"],
        "cf_all": cf_all["actual_minus_counterfactual_mean"],
        "ssp585_delta": ssp585["joint_climate_contribution"],
        "bayes_r1": r1["posterior_mean"] if r1 else None,
        "bayes_amc": amc["posterior_mean"] if amc else None,
        "bayes_ta": ta["posterior_mean"] if ta else None,
    }


def build_html(
    model: dict[str, Any],
    univariate_rows: list[dict[str, Any]],
    lancet_rows: list[dict[str, Any]],
    bayes_rows: dict[str, list[dict[str, Any]]],
    diagnostics: dict[str, dict[str, Any]],
    extended_bayes_rows: dict[str, list[dict[str, Any]]],
    extended_diagnostics: dict[str, dict[str, Any]],
    cf: dict[str, Any],
    future: dict[str, Any],
) -> str:
    values = hero_values(model, cf, future, bayes_rows)
    fe = model["fe"]
    year_r1 = bayes_row(bayes_rows, "year_only_additive", "R1xday", "main")
    year_amc = bayes_row(bayes_rows, "year_only_additive", "抗菌药物使用强度", "main")
    year_ta = bayes_row(bayes_rows, "year_only_additive", "TA（°C）", "main")
    inter = bayes_row(bayes_rows, "year_only_amplification", "R1xday × 抗菌药物使用强度", "interaction")
    cf_all = cf["overall"][cf["overall"]["scenario_id"] == "all_climate_to_baseline"].iloc[0]
    cf_temp = cf["overall"][cf["overall"]["scenario_id"] == "temperature_to_baseline"].iloc[0]
    cf_r1 = cf["overall"][cf["overall"]["scenario_id"] == "r1xday_to_baseline"].iloc[0]
    f585 = future["national"][(future["national"]["scenario_id"] == "ssp585") & (future["national"]["statistic"] == "median")].iloc[0]
    f119 = future["national"][(future["national"]["scenario_id"] == "ssp119") & (future["national"]["statistic"] == "median")].iloc[0]
    build_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SYS_08952 完整论文分析</title>
  <style>
    :root {{
      --bg: #f7f9fb;
      --surface: #ffffff;
      --soft: #eef4f6;
      --ink: #17252c;
      --muted: #62737c;
      --line: #d8e1e6;
      --teal: #0f766e;
      --blue: #2563eb;
      --rose: #be123c;
      --amber: #b45309;
      --shadow: 0 14px 34px rgba(21, 32, 39, 0.09);
      --serif: Georgia, "Times New Roman", serif;
      --sans: "Segoe UI", "Microsoft YaHei UI", Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: linear-gradient(180deg, #edf3f5 0%, #f7f9fb 34%, #eef4f6 100%);
      font-family: var(--sans);
    }}
    a {{ color: inherit; }}
    .page {{ width: min(1240px, calc(100vw - 28px)); margin: 0 auto; padding: 16px 0 44px; }}
    .topbar {{
      display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; font-size: 14px;
    }}
    .topbar a {{ text-decoration: none; color: var(--muted); border: 1px solid var(--line); background: rgba(255,255,255,.78); padding: 9px 12px; border-radius: 8px; }}
    .topbar a:hover {{ color: var(--teal); border-color: rgba(15,118,110,.42); }}
    .hero {{
      border-radius: 8px; background: linear-gradient(135deg, #16343a 0%, #0f766e 60%, #204564 100%);
      color: #f9fcfb; padding: clamp(24px, 4vw, 44px); box-shadow: var(--shadow);
    }}
    .eyebrow {{ margin: 0 0 10px; font-size: 12px; line-height: 1.4; letter-spacing: .10em; text-transform: uppercase; color: var(--teal); font-weight: 800; }}
    .hero .eyebrow {{ color: rgba(249,252,251,.78); }}
    h1,h2,h3,h4 {{ margin: 0; letter-spacing: 0; }}
    h1 {{ max-width: 1040px; font-family: var(--serif); font-size: clamp(34px, 5vw, 58px); line-height: 1.06; }}
    h2 {{ font-family: var(--serif); font-size: clamp(25px, 3vw, 37px); line-height: 1.14; }}
    h3 {{ font-size: 18px; line-height: 1.28; }}
    h4 {{ font-size: 15px; margin: 10px 0 8px; }}
    p {{ margin: 10px 0 0; color: var(--muted); line-height: 1.85; font-size: 15px; }}
    .hero p {{ max-width: 1040px; color: rgba(249,252,251,.9); font-size: 17px; }}
    .hero-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-top: 24px; }}
    .metric {{ min-height: 126px; border: 1px solid rgba(255,255,255,.22); background: rgba(255,255,255,.10); border-radius: 8px; padding: 14px; }}
    .metric span {{ display:block; min-height: 30px; color: rgba(249,252,251,.75); font-size: 12px; line-height: 1.45; }}
    .metric strong {{ display:block; margin: 8px 0 6px; color: #fff; font-size: clamp(22px, 2.5vw, 34px); line-height: 1; overflow-wrap:anywhere; }}
    .metric em {{ display:block; font-style:normal; color: rgba(249,252,251,.82); font-size:12px; line-height:1.45; }}
    .nav {{ position: sticky; top: 0; z-index: 4; display:flex; flex-wrap:wrap; gap:8px; margin:14px 0; padding:10px; border:1px solid var(--line); border-radius:8px; background:rgba(247,249,251,.94); backdrop-filter:blur(12px); }}
    .nav a {{ text-decoration:none; padding:8px 10px; border-radius:8px; color:var(--muted); font-weight:800; font-size:13px; }}
    .nav a:hover {{ color:var(--teal); background:#e7f3f1; }}
    section.block {{ margin-top:14px; border:1px solid var(--line); background:var(--surface); border-radius:8px; box-shadow:0 10px 28px rgba(21,32,39,.06); padding:clamp(20px,3vw,30px); }}
    .section-head {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:18px; align-items:start; margin-bottom:18px; }}
    .grid {{ display:grid; gap:12px; }}
    .two {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .four {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    .mini-card {{ border:1px solid var(--line); border-radius:8px; padding:16px; background:#fbfdfe; }}
    .mini-card strong.value {{ display:block; font-size:23px; line-height:1.1; margin-top:7px; }}
    .mini-card span,.muted {{ color: var(--muted); }}
    .callout {{ border-left:4px solid var(--teal); background:#f1f7f6; padding:14px 16px; border-radius:8px; color:#284247; line-height:1.85; }}
    .warn {{ border-left-color: var(--amber); background:#fff7ed; }}
    .formula-block {{ margin-top:10px; padding:12px; border-radius:8px; background:#edf4f6; border:1px solid #d9e5e8; font-family:Consolas, "SFMono-Regular", monospace; color:#203a44; line-height:1.7; overflow:auto; }}
    .tag-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
    .tag {{ display:inline-flex; align-items:center; min-height:30px; border:1px solid #cddae0; background:#f6fafb; color:#284247; border-radius:8px; padding:5px 9px; font-size:13px; }}
    .table-wrap {{ width:100%; overflow:auto; border:1px solid var(--line); border-radius:8px; background:#fff; }}
    .table-wrap.small {{ max-height: 360px; }}
    table {{ width:100%; min-width:760px; border-collapse:collapse; font-size:14px; }}
    .mini-card table {{ min-width: 0; }}
    th {{ text-align:left; padding:11px 12px; background:#edf4f6; color:#34484f; border-bottom:1px solid var(--line); white-space:nowrap; }}
    td {{ padding:12px; border-bottom:1px solid #edf1f3; vertical-align:top; line-height:1.55; }}
    tr:last-child td {{ border-bottom:0; }}
    td span {{ display:block; color:var(--muted); font-size:12px; margin-top:3px; }}
    .meta-row td {{ background:#f8fafb; color:#34484f; font-weight:800; }}
    .pos {{ color: var(--teal); font-weight: 800; }}
    .neg {{ color: var(--rose); font-weight: 800; }}
    figure {{ margin:0; border:1px solid var(--line); border-radius:8px; background:#fff; overflow:hidden; }}
    figure img {{ display:block; width:100%; height:auto; background:#f5f8fa; }}
    figcaption {{ padding:10px 12px; color:var(--muted); font-size:13px; line-height:1.55; border-top:1px solid var(--line); }}
    .figure-grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:14px; }}
    .figure-grid.single {{ grid-template-columns: 1fr; }}
    .note-list {{ margin:12px 0 0; padding-left:20px; color:var(--muted); line-height:1.8; }}
    .writing {{ display:grid; gap:12px; }}
    .writing article {{ border:1px solid var(--line); border-radius:8px; padding:16px; background:#fbfdfe; }}
    code {{ font-family: Consolas, "SFMono-Regular", monospace; color:#203a44; background:#edf4f6; border:1px solid #d9e5e8; padding:1px 6px; border-radius:6px; }}
    @media (max-width: 1050px) {{
      .hero-grid,.two,.three,.four,.figure-grid,.section-head {{ grid-template-columns: 1fr; }}
      .nav {{ position: static; }}
    }}
    @media (max-width: 560px) {{
      .page {{ width: calc(100vw - 14px); padding-top: 8px; }}
      .topbar {{ flex-direction: column; align-items: stretch; }}
      .hero, section.block {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <div class="topbar">
      <a href="../index.html">返回发布入口</a>
      <div class="tag-row">
        <a href="../variable-group-deep-dive/index.html">模型决策页</a>
        <a href="../counterfactual-amr-agg/index.html">反事实原页</a>
        <a href="../future-scenario-analysis/index.html">未来情景原页</a>
      </div>
    </div>

    <header class="hero">
      <div class="eyebrow">Final Full Analysis · generated {escape(build_time)}</div>
      <h1>SYS_08952 完整论文分析页</h1>
      <p>
        本页只服务最终论文写作：先做 SYS_08952 变量组的单因素探索，再呈现固定效应 Lancet 风格主表，
        随后把 Bayesian SI、反事实推演和 Lancet ETS 未来情景分解补成可解释、可追溯、可写入论文的完整证据链。
      </p>
      <div class="hero-grid">
        <div class="metric"><span>主模型</span><strong>SYS_08952</strong><em>Province: No / Year: Yes</em></div>
        <div class="metric"><span>固定效应 R²</span><strong>{fmt(values['r2'], 3)}</strong><em>只保留 model R-squared</em></div>
        <div class="metric"><span>Bayes 主效应</span><strong>{fmt(values['bayes_r1'], 3, signed=True)}</strong><em>R1xday year-only posterior mean</em></div>
        <div class="metric"><span>反事实共同气候贡献</span><strong>{fmt(values['cf_all'], 3, signed=True)}</strong><em>R1xday + TA 恢复基准</em></div>
        <div class="metric"><span>2050 SSP5-8.5</span><strong>{fmt(values['ssp585_delta'], 3, signed=True)}</strong><em>Lancet ETS baseline delta</em></div>
      </div>
    </header>

    <nav class="nav">
      <a href="#univariate">单因素</a>
      <a href="#fe">固定效应</a>
      <a href="#bayes">Bayes SI</a>
      <a href="#counterfactual">反事实</a>
      <a href="#future">未来情景</a>
      <a href="#writing">论文陈述</a>
      <a href="#limits">边界</a>
    </nav>

    <section class="block" id="univariate">
      <div class="section-head">
        <div>
          <div class="eyebrow">1. Univariate Screening</div>
          <h2>先看 8952 变量组与 AMR_AGG_z 的单因素关系</h2>
          <p>单因素分析只回答“每个变量单独看时与综合耐药性指标是否同向变化”。它不控制其他变量，因此是探索和可视化，不是最终主结论。</p>
        </div>
      </div>
      <div class="callout">
        <strong>读图规则：</strong>主图改成与 <code>1 单因素分析/figs</code> 一致的相关矩阵风格：
        下三角为原始量纲散点与分组趋势线，对角线为分布，上三角为总体 Pearson 相关和按 GDP 四分位分组的相关。
        标准化不会改变 Pearson 相关系数，但会抹掉变量原始尺度，所以旧的标准化散点图确实不如相关矩阵直观。
      </div>
      <div class="figure-grid single">
        <figure><img src="assets/univariate_pairgrid_sys08952.png" alt="SYS_08952 单因素相关矩阵" loading="lazy" /><figcaption>SYS_08952 八个解释变量与 AMR_AGG_z 的原始尺度相关矩阵。H/UM/LM/L 按同一年内 GDP 四分位划分，用于观察社会经济分层后的相关性是否一致。</figcaption></figure>
      </div>
      <div class="figure-grid">
        <figure><img src="assets/univariate_scatter_grid.png" alt="SYS_08952 标准化单因素散点图" loading="lazy" /><figcaption>标准化散点图保留作为辅助图：它适合读标准化 β，但视觉上不如原始尺度相关矩阵直观。</figcaption></figure>
        <figure><img src="assets/univariate_forest.png" alt="SYS_08952 单因素森林图" loading="lazy" /><figcaption>标准化单因素 β 的森林图，方便横向比较哪个变量的单因素关联更强。</figcaption></figure>
      </div>
      <div class="table-wrap" style="margin-top:14px;">
        <table>
          <thead><tr><th>变量</th><th>标准化 β</th><th>95% CI</th><th>p 值</th><th>Pearson r</th><th>解释</th></tr></thead>
          <tbody>{univariate_table(univariate_rows)}</tbody>
        </table>
      </div>
      <ul class="note-list">
        <li>单因素结果用于筛选和描述，不应替代固定效应模型，因为它没有同时调整其他气候、污染和社会经济变量。</li>
        <li>如果单因素与多变量方向不一致，论文中应优先以固定效应模型为主，并把单因素作为探索性补充。</li>
      </ul>
    </section>

    <section class="block" id="fe">
      <div class="section-head">
        <div>
          <div class="eyebrow">2. Fixed Effects Main Table</div>
          <h2>固定效应主模型：Lancet 风格结果表</h2>
          <p>这里使用 SYS_08952 的 Year FE 主规格。按你的要求，R² 只保留 <strong>model R-squared</strong>，不再展示其他容易混淆的 R² 口径。</p>
        </div>
      </div>
      <div class="grid three">
        <article class="mini-card"><span>R1xday</span><strong class="value pos">{fmt(fe.get('coef_R1xday'), 3, signed=True)}*</strong><p>p={fmt_p(fe.get('p_R1xday'))}，极端单日降雨为正。</p></article>
        <article class="mini-card"><span>AMC</span><strong class="value pos">{fmt(fe.get('coef_AMC'), 3, signed=True)}**</strong><p>p={fmt_p(fe.get('p_AMC'))}，抗菌药物压力为正。</p></article>
        <article class="mini-card"><span>TA</span><strong class="value pos">{fmt(fe.get('coef_temperature_proxy'), 3, signed=True)}*</strong><p>p={fmt_p(fe.get('p_temperature_proxy'))}，温度通道为正。</p></article>
      </div>
      <div class="table-wrap" style="margin-top:14px;">
        <table>
          <thead><tr><th>Predictor</th><th>Coefficient</th><th>95% CI</th><th>p value</th></tr></thead>
          <tbody>{lancet_table_html(lancet_rows)}</tbody>
        </table>
      </div>
      <ul class="note-list">
        <li>R1xday、AMC、TA、氮氧化物、医疗水平均为正且达到常用显著性阈值，构成“极端降雨 + 温度 + 抗菌药物压力 + 环境压力”的主叙事。</li>
        <li>Year FE 控制每一年全国共同冲击；没有 Province FE，因此模型仍保留省际结构差异，这一点要在论文方法和局限中说清楚。</li>
      </ul>
    </section>

    <section class="block" id="bayes">
      <div class="section-head">
        <div>
          <div class="eyebrow">3. Bayesian Analysis for SI</div>
          <h2>Bayes 分析到底在做什么，以及如何判断稳不稳</h2>
          <p>Bayes 分析建议放 SI。它不是另建一个主模型替代固定效应，而是把同一组变量放进概率模型，检查主效应方向、可信区间、交互项和 MCMC 收敛诊断。</p>
        </div>
      </div>
      <div class="grid four">
        <article class="mini-card"><span>第一步</span><strong class="value">定义后验</strong><p>把每个系数看作一个有不确定性的分布，而不是单一估计值。</p></article>
        <article class="mini-card"><span>第二步</span><strong class="value">看方向</strong><p>P(β&gt;0) 越接近 100%，说明正向证据越强。</p></article>
        <article class="mini-card"><span>第三步</span><strong class="value">看 CrI</strong><p>95% CrI 不跨 0，可作为较稳健的方向证据。</p></article>
        <article class="mini-card"><span>第四步</span><strong class="value">看诊断</strong><p>R-hat 接近 1 且 ESS 充足，说明采样结果可信。</p></article>
      </div>
      <div class="grid four" style="margin-top:12px;">
        <article class="mini-card"><span>Year-only R1xday</span><strong class="value pos">{fmt(year_r1.get('posterior_mean') if year_r1 else None, 3, signed=True)}</strong><p>95% CrI {fmt_interval(year_r1.get('crI_2_5') if year_r1 else None, year_r1.get('crI_97_5') if year_r1 else None)}；P(β&gt;0) {fmt_prob(year_r1.get('prob_gt_0') if year_r1 else None)}。</p></article>
        <article class="mini-card"><span>Year-only AMC</span><strong class="value pos">{fmt(year_amc.get('posterior_mean') if year_amc else None, 3, signed=True)}</strong><p>95% CrI {fmt_interval(year_amc.get('crI_2_5') if year_amc else None, year_amc.get('crI_97_5') if year_amc else None)}；P(β&gt;0) {fmt_prob(year_amc.get('prob_gt_0') if year_amc else None)}。</p></article>
        <article class="mini-card"><span>Year-only TA</span><strong class="value pos">{fmt(year_ta.get('posterior_mean') if year_ta else None, 3, signed=True)}</strong><p>95% CrI {fmt_interval(year_ta.get('crI_2_5') if year_ta else None, year_ta.get('crI_97_5') if year_ta else None)}；P(β&gt;0) {fmt_prob(year_ta.get('prob_gt_0') if year_ta else None)}。</p></article>
        <article class="mini-card"><span>R1xday × AMC</span><strong class="value pos">{fmt(inter.get('posterior_mean') if inter else None, 3, signed=True)}</strong><p>95% CrI {fmt_interval(inter.get('crI_2_5') if inter else None, inter.get('crI_97_5') if inter else None)}；跨 0，所以不是强确定性结论。</p></article>
      </div>
      <div class="table-wrap" style="margin-top:14px;">
        <table>
          <thead><tr><th>Bayes 规格</th><th>R1xday</th><th>AMC</th><th>TA</th><th>交互项</th><th>判断依据</th><th>诊断</th></tr></thead>
          <tbody>{bayes_variant_table(bayes_rows, diagnostics)}</tbody>
        </table>
      </div>
      <h3 style="margin-top:18px;">新增交互探索：TA × AMC 与 R1xday × TA × AMC</h3>
      <div class="callout">
        <strong>为什么单列：</strong>这两项是后加的机制探索，不改变正文主模型。三重交互按层级原则同时放入三个二阶项，
        因此三重项解释为“极端降雨和温度是否会共同改变 AMC 与 AMR 的关联”。
      </div>
      <div class="table-wrap" style="margin-top:14px;">
        <table>
          <thead><tr><th>新增规格</th><th>TA × AMC</th><th>R1xday × TA</th><th>R1xday × TA × AMC</th><th>判断</th><th>诊断</th></tr></thead>
          <tbody>{extended_bayes_interaction_table(extended_bayes_rows, extended_diagnostics)}</tbody>
        </table>
      </div>
      <div class="callout warn" style="margin-top:14px;">
        <strong>SI 推荐写法：</strong>Bayesian year-only models support positive R1xday, AMC, and TA main effects, because their posterior means are positive and their 95% credible intervals are above zero.
        The R1xday × AMC amplification term is positive on average, but its credible interval crosses zero, so it should be described as suggestive rather than confirmatory.
        Additional TA × AMC and R1xday × TA × AMC tests did not show robust amplification through AMC.
      </div>
      <ul class="note-list">
        <li>正向/负向：后验均值大于 0 表示正向，小于 0 表示负向；P(β&gt;0) 是方向概率。</li>
        <li>稳健：Year-only 下 R1xday、AMC 和 TA 主效应均为正；加入 Province 或 Province+Year 后主效应收缩，说明省际结构差异是主模型信号的重要来源。</li>
        <li>诊断：SYS_08952 的 Bayes 诊断 R-hat 基本为 1.00–1.01，未见 diagnostic flag，可放 SI 支撑模型收敛。</li>
      </ul>
    </section>

    <section class="block" id="counterfactual">
      <div class="section-head">
        <div>
          <div class="eyebrow">4. Counterfactual Simulation</div>
          <h2>反事实推演：如果 R1xday 和 TA 回到基准期，AMR 会低多少</h2>
          <p>反事实不是重新回归，而是固定 SYS_08952 系数，把气候变量替换成基准期水平，再比较实际预测值与反事实预测值。</p>
        </div>
      </div>
      <div class="callout">
        <strong>核心公式：</strong><code>Actual - Counterfactual &gt; 0</code> 表示当前气候轨迹对应更高的预测 AMR。
        对 SYS_08952 来说，“所有气候变量恢复基准”就是 <code>R1xday + TA</code> 共同恢复基准。
      </div>
      <div class="grid two" style="margin-top:12px;">
        <article class="mini-card">
          <h3>固定效应预测方程</h3>
          <div class="formula-block">ŷ_it = Σ_k β̂_k · X_kit^(z) + γ̂_t</div>
          <p>这里 <code>i</code> 是省份，<code>t</code> 是年份；SYS_08952 是 Year FE，所以保留年份固定效应 <code>γ_t</code>，解释变量进入模型前按历史样本标准化。</p>
        </article>
        <article class="mini-card">
          <h3>反事实替换方程</h3>
          <div class="formula-block">ŷ_it^cf(s) = Σ_(k∉S_s) β̂_k · X_kit,actual^(z) + Σ_(k∈S_s) β̂_k · X_ki,2014^(z) + γ̂_t</div>
          <p><code>S_s</code> 是情景中被回拨的气候变量集合。R1xday-only 只替换 R1xday；TA-only 只替换 TA；joint 情景同时替换 R1xday 和 TA。</p>
        </article>
        <article class="mini-card">
          <h3>归因差值</h3>
          <div class="formula-block">Δ_it^(s) = ŷ_it^actual - ŷ_it^cf(s)</div>
          <p><code>Δ &gt; 0</code> 表示实际气候轨迹相对于基准气候世界提高了预测 AMR；<code>Δ &lt; 0</code> 表示实际气候轨迹相对于基准情景降低了预测 AMR。</p>
        </article>
        <article class="mini-card">
          <h3>汇总方式</h3>
          <div class="formula-block">全国年度平均: Δ̄_t = (1/N_t) Σ_i Δ_it<br/>分省长期平均: Δ̄_i = (1/T_i) Σ_t Δ_it</div>
          <p>网页中的全国曲线、全国平均、地区表和省级地图，都是先在省份-年份层面得到 <code>Δ_it</code>，再按相应维度汇总。</p>
        </article>
      </div>
      <div class="grid three" style="margin-top:12px;">
        <article class="mini-card"><span>R1xday + TA</span><strong class="value pos">{fmt(cf_all['actual_minus_counterfactual_mean'], 3, signed=True)}</strong><p>相对变化 {fmt_pct(cf_all['relative_change_pct_mean'])}，总体气候贡献。</p></article>
        <article class="mini-card"><span>仅 TA</span><strong class="value pos">{fmt(cf_temp['actual_minus_counterfactual_mean'], 3, signed=True)}</strong><p>相对变化 {fmt_pct(cf_temp['relative_change_pct_mean'])}，温度通道占主体。</p></article>
        <article class="mini-card"><span>仅 R1xday</span><strong class="value pos">{fmt(cf_r1['actual_minus_counterfactual_mean'], 3, signed=True)}</strong><p>相对变化 {fmt_pct(cf_r1['relative_change_pct_mean'])}，方向一致但量级较小。</p></article>
      </div>
      <div class="table-wrap" style="margin-top:14px;">
        <table>
          <thead><tr><th>反事实情景</th><th>Actual - Counterfactual</th><th>相对变化</th><th>解释</th></tr></thead>
          <tbody>{counterfactual_overall_table(cf)}</tbody>
        </table>
      </div>
      <div class="figure-grid">
        <figure><img src="assets/counterfactual_sys08952_national.png" alt="SYS_08952 反事实全国结果" loading="lazy" /><figcaption>只保留已选定 SYS_08952 主模型：左图为年度 <code>Actual - Counterfactual</code>，右图为三个回拨情景的全国平均差值。</figcaption></figure>
        <figure><img src="assets/counterfactual_china_map_sys08952_signedlog.png" alt="SYS_08952 反事实完整中国地图" loading="lazy" /><figcaption>省级差值地图使用 signed log1p 色阶：因为最新年省级差值存在一个负值且正值跨度约 6 倍，signed log1p 能保留正负方向并压缩极端值。港澳台、南沙群岛/南海诸岛无观测值，灰色显示。</figcaption></figure>
      </div>
      <div class="grid two" style="margin-top:14px;">
        <article class="mini-card">
          <h3>长期平均省级异质性：R1xday + TA</h3>
          {counterfactual_extreme_table(cf['province_average'], 'all_climate_to_baseline')}
        </article>
        <article class="mini-card">
          <h3>地区平均：R1xday + TA</h3>
          <div class="table-wrap small"><table><thead><tr><th>地区</th><th>省份数</th><th>差值</th><th>相对变化</th></tr></thead><tbody>{counterfactual_region_table(cf)}</tbody></table></div>
        </article>
      </div>
      <ul class="note-list">
        <li>正文建议优先报告绝对差值，而不是百分比，因为 <code>AMR_AGG_z</code> 是标准化综合指标，百分比更适合作辅助说明。</li>
        <li>结果显示温度通道是主要贡献，R1xday 是较小但方向一致的补充通道；这与固定效应和 Bayes 主效应可形成连贯叙事。</li>
      </ul>
    </section>

    <section class="block" id="future">
      <div class="section-head">
        <div>
          <div class="eyebrow">5. Future Scenario · Lancet ETS Outcome Baseline</div>
          <h2>未来情景模拟：只采用 outcome ETS / Lancet ETS 这组作为主分析</h2>
          <p>Lancet ETS 的含义是：先用 AMR 自身历史序列生成未来 baseline，再把不同 SSP 下的 R1xday 和 TA 气候增量叠加到 baseline 上。</p>
        </div>
      </div>
      <div class="callout">
        <strong>分解公式：</strong><code>Δ scenario = β_R1xday × (ΔR1xday / historical SD) + β_TA × (ΔTA / historical SD)</code>。
        当前未来情景模块使用标准化投影系数：R1xday β={fmt(future['coef_map'].get('R1xday'), 3)}，
        TA β={fmt(future['coef_map'].get('TA（°C）'), 3)}；历史 SD 分别为
        R1xday {fmt(future['scale_stats'].get('R1xday'), 3)}、TA {fmt(future['scale_stats'].get('TA（°C）'), 3)}。
      </div>
      {future_component_summary(future)}
      <div class="grid three" style="margin-top:12px;">
        <article class="mini-card"><span>2050 baseline</span><strong class="value">{fmt(f585['baseline_pred_mean'], 2)}</strong><p>Lancet ETS 主模型全国 baseline。</p></article>
        <article class="mini-card"><span>SSP5-8.5 joint delta</span><strong class="value pos">{fmt(f585['joint_climate_contribution'], 3, signed=True)}</strong><p>R1xday {fmt(f585['r1xday_contribution'], 3, signed=True)} + TA {fmt(f585['ta_contribution'], 3, signed=True)}。</p></article>
        <article class="mini-card"><span>SSP1-1.9 joint delta</span><strong class="value neg">{fmt(f119['joint_climate_contribution'], 3, signed=True)}</strong><p>低排放路径下气候增量为负，表示低于 baseline。</p></article>
      </div>
      <div class="figure-grid">
        <figure><img src="assets/future_lancet_decomposition.png" alt="Lancet ETS 未来情景贡献分解" loading="lazy" /><figcaption>2050 各 SSP 下 R1xday 单独贡献、TA 单独贡献和二者共同贡献分开展示。</figcaption></figure>
        <figure><img src="assets/future_component_trajectories_ssp585.png" alt="SSP5-8.5 未来情景分通道轨迹" loading="lazy" /><figcaption>SSP5-8.5 下，R1xday、TA、共同作用三条轨迹随时间的变化。</figcaption></figure>
      </div>
      <div class="figure-grid single">
        <figure><img src="assets/future_component_maps_ssp585.png" alt="SSP5-8.5 分通道完整中国地图" loading="lazy" /><figcaption>SSP5-8.5 省级分通道地图：左为 R1xday，中为 TA，右为共同作用。港澳台、南沙群岛/南海诸岛无观测值，以灰色保留在完整中国地图中。</figcaption></figure>
      </div>
      <div class="table-wrap" style="margin-top:14px;">
        <table>
          <thead><tr><th>情景</th><th>Baseline</th><th>R1xday 单独贡献</th><th>TA 单独贡献</th><th>共同贡献</th><th>不确定性 p10-p90</th><th>Scenario pred</th></tr></thead>
          <tbody>{future_national_table(future)}</tbody>
        </table>
      </div>
      <div class="figure-grid">
        <figure><img src="../future-scenario-analysis/results/lancet_ets/regional_figures/regional_figure5_grid.png" alt="Lancet ETS 地区未来轨迹" loading="lazy" /><figcaption>七大区未来情景轨迹。地区结果帮助说明全国平均背后的空间分布。</figcaption></figure>
        <figure><img src="../future-scenario-analysis/results/lancet_ets/regional_figures/regional_delta_2050_heatmap.png" alt="Lancet ETS 地区 2050 热图" loading="lazy" /><figcaption>2050 地区情景增量热图，展示不同地区对 SSP5-8.5 的响应强弱。</figcaption></figure>
      </div>
      <h3 style="margin-top:14px;">地区层面：SSP5-8.5 的 R1xday、TA 和共同影响</h3>
      <div class="table-wrap" style="margin-top:8px;">
        <table>
          <thead><tr><th>地区</th><th>省份数</th><th>R1xday</th><th>TA</th><th>共同影响</th><th>2050 pred</th></tr></thead>
          <tbody>{future_region_table(future, 'ssp585')}</tbody>
        </table>
      </div>
      <div class="figure-grid">
        <figure><img src="../future-scenario-analysis/results/lancet_ets/provincial_figures/provincial_future_scenario_panel.png" alt="Lancet ETS 省级未来情景" loading="lazy" /><figcaption>省级未来情景面板：展示 31 个省在不同 SSP 下的 2050 差异。</figcaption></figure>
        <figure><img src="../future-scenario-analysis/results/lancet_ets/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585_delta.png" alt="SSP1-1.9 与 SSP5-8.5 省级比较" loading="lazy" /><figcaption>低排放与高排放的省级差异，有助于写“气候缓解”叙事。</figcaption></figure>
      </div>
      <div class="grid two" style="margin-top:14px;">{future_extreme_cards(future, 'ssp585')}</div>
      <h3 style="margin-top:14px;">省级完整表：SSP5-8.5</h3>
      <div class="table-wrap small" style="margin-top:8px;">
        <table>
          <thead><tr><th>省份</th><th>Baseline</th><th>R1xday</th><th>TA</th><th>共同影响</th><th>2050 pred</th></tr></thead>
          <tbody>{future_province_table(future, 'ssp585')}</tbody>
        </table>
      </div>
      <ul class="note-list">
        <li>未来情景主文建议使用 Lancet ETS/outcome ETS baseline，因为它更贴近“先外推结果变量自身历史趋势，再叠加气候增量”的文献写法。</li>
        <li>SSP5-8.5 相对 baseline 增加 {fmt(f585['joint_climate_contribution'], 3, signed=True)}；SSP1-1.9 为 {fmt(f119['joint_climate_contribution'], 3, signed=True)}。两者差距说明低排放路径具有潜在缓解意义。</li>
        <li>R1xday 和 TA 的“单独贡献”已经按历史标准差换算到模型实际使用的标准化尺度；两项相加等于共同气候贡献，残差仅为四舍五入误差。</li>
        <li>R1xday 与 TA 的贡献方向可能在不同 SSP 下相互抵消，所以共同影响不应机械理解为单调随排放等级上升。</li>
      </ul>
    </section>

    <section class="block" id="writing">
      <div class="section-head">
        <div>
          <div class="eyebrow">6. Paper Narrative</div>
          <h2>可以直接转成正文和 SI 的论文陈述逻辑</h2>
        </div>
      </div>
      <div class="writing">
        <article><h3>正文主结果</h3><p>在 Year FE 主规格 SYS_08952 中，R1xday、AMC、TA 和氮氧化物均呈正向关联，其中 R1xday β={fmt(fe.get('coef_R1xday'),3,signed=True)}，AMC β={fmt(fe.get('coef_AMC'),3,signed=True)}，TA β={fmt(fe.get('coef_temperature_proxy'),3,signed=True)}。这说明在控制年份共同冲击后，极端降雨、温度和抗菌药物压力与综合 AMR 水平具有同向变化。</p></article>
        <article><h3>SI Bayes 段</h3><p>Bayesian models were used as a probabilistic bridge to examine whether the main effects remained positive under alternative random/fixed-effect structures. The year-only additive model reproduced positive R1xday, AMC, and TA effects, whereas the R1xday × AMC interaction was positive on average but crossed zero. Additional TA × AMC and R1xday × TA × AMC tests also crossed zero, while R1xday × TA was positive in the hierarchical model. Therefore, AMC-related amplification should be interpreted as exploratory rather than confirmatory.</p></article>
        <article><h3>反事实段</h3><p>Counterfactual rollback of R1xday and TA to baseline levels lowered the national AMR signal by {fmt(cf_all['actual_minus_counterfactual_mean'],3)} on average. The temperature-only rollback contributed {fmt(cf_temp['actual_minus_counterfactual_mean'],3)}, while the R1xday-only rollback contributed {fmt(cf_r1['actual_minus_counterfactual_mean'],3)}, indicating that temperature dominated the modeled climate burden while R1xday provided a smaller but directionally consistent pathway.</p></article>
        <article><h3>未来情景段</h3><p>Under the Lancet ETS baseline, the 2050 national baseline was {fmt(f585['baseline_pred_mean'],2)}. SSP5-8.5 increased the projected AMR level by {fmt(f585['joint_climate_contribution'],3,signed=True)}, while SSP1-1.9 decreased it by {fmt(f119['joint_climate_contribution'],3,signed=True)} relative to baseline. This supports reporting high-emission climate pathways as an additional future AMR burden.</p></article>
      </div>
    </section>

    <section class="block" id="limits">
      <div class="section-head">
        <div>
          <div class="eyebrow">7. Interpretation Boundaries</div>
          <h2>最后论文里必须说清楚的边界</h2>
        </div>
      </div>
      <div class="grid two">
        <article class="mini-card"><span>单因素不是最终结论</span><strong class="value">探索性</strong><p>单因素图帮助理解变量方向，但不控制混杂，最终判断以后续固定效应和推演为准。</p></article>
        <article class="mini-card"><span>Year FE 的识别含义</span><strong class="value">控制年份共同冲击</strong><p>没有 Province FE，说明省际结构差异仍参与解释，论文不宜写成严格省内因果效应。</p></article>
        <article class="mini-card"><span>Bayes 交互项</span><strong class="value">谨慎解释</strong><p>R1xday × AMC、TA × AMC 和三重交互均 CrI 跨 0；R1xday × TA 可作为气候协同的探索性发现。</p></article>
        <article class="mini-card"><span>未来情景</span><strong class="value">选择 Lancet ETS</strong><p>主文采用 outcome ETS/Lancet ETS；X-driven 可作为补充敏感性说明，不混入本页主线。</p></article>
      </div>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    ensure_dirs()
    model = load_target_model()
    panel, variables = load_panel(model["variables"])
    univariate_rows = run_univariate(panel, variables)
    plot_univariate(panel, univariate_rows)
    lancet_rows = load_lancet_table()
    bayes_rows = load_bayes_rows()
    diagnostics = load_bayes_diagnostics()
    extended_bayes_rows = load_extended_bayes_rows()
    extended_diagnostics = load_extended_bayes_diagnostics()
    cf = load_counterfactual()
    future = load_future()
    plot_counterfactual_figures(cf)
    plot_future_decomposition(future)

    write_csv(DATA_DIR / "univariate_summary.csv", univariate_rows)
    write_csv(DATA_DIR / "counterfactual_main_model_overall.csv", df_records(cf["overall"]))
    write_csv(DATA_DIR / "counterfactual_main_model_region.csv", df_records(cf["region_summary"]))
    write_csv(
        DATA_DIR / "future_lancet_2050_decomposition.csv",
        df_records(
            future["national"][
                (future["national"]["statistic"] == "median")
                & (future["national"]["scenario_id"].isin(SCENARIO_ORDER))
            ]
        ),
    )
    write_json(
        OUTPUT_PAYLOAD,
        {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model_id": TARGET_MODEL_ID,
            "univariate": univariate_rows,
            "lancet_table": lancet_rows,
            "bayes_diagnostics": diagnostics,
            "extended_bayes": extended_bayes_rows,
            "extended_bayes_diagnostics": extended_diagnostics,
            "counterfactual_overall": df_records(cf["overall"]),
            "future_coefficients": future["coef_map"],
            "future_scale_stats": future["scale_stats"],
            "future_lancet_national": df_records(future["national"]),
        },
    )
    OUTPUT_HTML.write_text(
        build_html(
            model,
            univariate_rows,
            lancet_rows,
            bayes_rows,
            diagnostics,
            extended_bayes_rows,
            extended_diagnostics,
            cf,
            future,
        ),
        encoding="utf-8",
    )
    print(f"Wrote SYS_08952 full paper analysis to {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
