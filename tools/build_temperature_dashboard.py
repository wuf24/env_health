from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "6 未来情景分析"
RESULTS_DIR = PROJECT_DIR / "results"
OUT_FILE = PROJECT_DIR / "temperature_dashboard.html"
FIGURE_DIR = RESULTS_DIR / "temperature_dashboard_figures"
X_PATH = ROOT / "climate_social_eco.csv"
PROVINCE_REGION_PATH = PROJECT_DIR / "data_processed" / "province_to_region_7zones.csv"

TA_COL = "TA（°C）"
PROVINCE_TAS_COL = "省平均气温"
PROVINCE_TAS_ALIGNED_COL = f"{PROVINCE_TAS_COL}_aligned"
TEMPERATURE_VARS = {TA_COL, PROVINCE_TAS_COL}
HISTORICAL_START_YEAR = 2014
HISTORICAL_END_YEAR = 2023
FUTURE_END_YEAR = 2050
EXCLUDE_PROVINCES = {"全国", "μ", "σ"}
SCENARIO_ORDER = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585", "amc_reduce_50"]
MODE_ORDER = ["lancet_ets", "x_driven"]

SCENARIO_META = [
    {"id": "ssp119", "label": "SSP1-1.9", "color": "#4C78A8"},
    {"id": "ssp126", "label": "SSP1-2.6", "color": "#4F8A5B"},
    {"id": "ssp245", "label": "SSP2-4.5", "color": "#C4932E"},
    {"id": "ssp370", "label": "SSP3-7.0", "color": "#C96C32"},
    {"id": "ssp585", "label": "SSP5-8.5", "color": "#B54A3A"},
    {"id": "amc_reduce_50", "label": "AMC -50% by 2050", "color": "#7C5AC7"},
]

MODE_META = [
    {"id": "lancet_ets", "label": "Lancet ETS", "note": "AMR 自身 ETS baseline + 温度情景增量。"},
    {"id": "x_driven", "label": "X-driven", "note": "协变量 baseline + 温度情景增量。"},
]

PAPER_BG = "#F6F1E8"
PANEL_BG = "#FFFDF8"
FIGURE_BG = "#FCFAF5"
FIGURE_PANEL = "#FFFDF8"
INK = "#22303C"
MUTED = "#5F6C79"
BORDER = "#CFC5B6"
GRID = "#D9D2C4"
OBSERVED_LINE = "#243447"
NEGATIVE_BAR = "#7AA6C2"
POSITIVE_BAR = "#C26C32"
RIBBON_ALPHA = 0.14

DESIGN_RULES = [
    {
        "title": "把温度路径和不确定性拆开表达",
        "description": "所有时间序列都保留中位线，并把 p10-p90 画成半透明 ribbon，避免只画单一路径造成“精确到单值”的误读。",
    },
    {
        "title": "把图题、坐标、图注都写成可单独阅读",
        "description": "每张图都补足变量名、单位、年份范围和图注，保证脱离正文截图后仍能看懂其统计对象和口径。",
    },
    {
        "title": "颜色从强调装饰改成强调顺序和可读性",
        "description": "SSP 采用由冷到暖的顺序色板，正负效应使用两组稳定对照色，同时避免彩虹色和低对比深色底。",
    },
    {
        "title": "零基线和误差线要比背景更重要",
        "description": "对增量图统一强调 zero baseline；2050 柱状图给出 p10-p90 whiskers，让读者先看到方向，再看到范围。",
    },
]

LITERATURE_REFERENCES = [
    {
        "short": "Cleveland & McGill (1984)",
        "title": "Graphical Perception: Theory, Experimentation, and Application to the Development of Graphical Methods",
        "url": "https://doi.org/10.1080/01621459.1984.10478080",
        "note": "支持优先使用位置、长度和对齐等更容易被准确解读的编码方式。",
    },
    {
        "short": "Heer & Bostock (2010)",
        "title": "Crowdsourcing Graphical Perception: Using Mechanical Turk to Assess Visualization Design",
        "url": "https://doi.org/10.1145/1753326.1753357",
        "note": "延续 graphical perception 证据，说明线型、网格和编码细节会显著影响读图准确性。",
    },
    {
        "short": "Spiegelhalter et al. (2011)",
        "title": "Visualizing Uncertainty About the Future",
        "url": "https://doi.org/10.1126/science.1191181",
        "note": "直接指导未来情景的不确定性表达，所以这里新增 ribbon、误差线和更清楚的图注。",
    },
    {
        "short": "Crameri et al. (2020)",
        "title": "The Misuse of Colour in Science Communication",
        "url": "https://doi.org/10.1038/s41467-020-19160-7",
        "note": "支持使用感知均匀、色弱友好的浅色图板，并避免 rainbow / red-green 误导。",
    },
    {
        "short": "McMahon et al. (2021)",
        "title": "Communicating Future Climate Projections of Precipitation Change",
        "url": "https://doi.org/10.1007/s10584-021-03118-9",
        "note": "提醒未来情景图如果只给 summary mean 容易低估 projection range，因此温度页保留情景范围信息。",
    },
    {
        "short": "Harold et al. (2024)",
        "title": "Improving Figures for Climate Change Communications: Insights from Interviews with International Policymakers and Practitioners",
        "url": "https://doi.org/10.1007/s10584-024-03704-7",
        "note": "支持去杂讯、标题直陈 key message，并让 caption 可以单独承担解释作用。",
    },
]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def fill_panel_median(df: pd.DataFrame, col: str) -> pd.Series:
    out = to_float(df[col])
    out = out.groupby(df["Province"]).transform(lambda s: s.fillna(s.median()))
    return out.fillna(out.median())


def load_base_frame() -> pd.DataFrame:
    df = read_csv(X_PATH)
    df = df.rename(columns={df.columns[0]: "Province", df.columns[1]: "Year"})
    df["Province"] = df["Province"].astype(str).str.strip()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df = df[df["Year"].between(HISTORICAL_START_YEAR, HISTORICAL_END_YEAR)].copy()
    df = df[~df["Province"].isin(EXCLUDE_PROVINCES)].copy()
    df["Year"] = df["Year"].astype(int)
    return df.reset_index(drop=True)


def build_input_metric(
    metric_id: str,
    label: str,
    unit: str,
    note: str,
    history_series: pd.DataFrame,
    future_df: pd.DataFrame,
    value_col: str,
) -> dict[str, object]:
    future_df = future_df.copy()
    future_df["Year"] = pd.to_numeric(future_df["Year"], errors="coerce").astype(int)
    future_df[value_col] = to_float(future_df[value_col])
    grouped = (
        future_df.groupby(["scenario", "statistic", "Year"], dropna=False)[value_col]
        .mean()
        .reset_index(name="value")
    )

    series: dict[str, dict[str, list[dict[str, float]]]] = {}
    for scenario, scenario_df in grouped.groupby("scenario", dropna=False):
        stat_map: dict[str, list[dict[str, float]]] = {}
        for statistic, stat_df in scenario_df.groupby("statistic", dropna=False):
            stat_map[str(statistic)] = [
                {"year": int(row["Year"]), "value": float(row["value"])}
                for _, row in stat_df.sort_values("Year").iterrows()
            ]
        series[str(scenario)] = stat_map

    summary_rows: list[dict[str, object]] = []
    for scenario in SCENARIO_ORDER:
        summary_row = {"scenario_id": scenario}
        for statistic in ("median", "p10", "p90"):
            subset = grouped[
                grouped["scenario"].eq(scenario)
                & grouped["statistic"].eq(statistic)
                & grouped["Year"].eq(FUTURE_END_YEAR)
            ]
            summary_row[statistic] = float(subset.iloc[0]["value"]) if not subset.empty else np.nan
        summary_rows.append(summary_row)

    return {
        "id": metric_id,
        "label": label,
        "unit": unit,
        "note": note,
        "history": [
            {"year": int(row["Year"]), "value": float(row["value"])}
            for _, row in history_series.sort_values("Year").iterrows()
        ],
        "series": series,
        "summary2050": summary_rows,
    }


def temperature_role_order(role_ids: list[str]) -> list[str]:
    if "main_model" in role_ids:
        return ["main_model"] + [role_id for role_id in role_ids if role_id != "main_model"]
    return role_ids


def build_role_meta(base_df: pd.DataFrame) -> tuple[list[str], list[dict[str, object]]]:
    models = read_csv(RESULTS_DIR / "model_screening" / "selected_models_snapshot.csv")
    coefficients = read_csv(RESULTS_DIR / "model_screening" / "future_projection_coefficients.csv")

    roles: list[dict[str, object]] = []
    for _, row in models.iterrows():
        variables = [part.strip().replace("\n", " ") for part in str(row["variables"]).split("|") if part.strip()]
        temp_proxy = next((item for item in variables if item in TEMPERATURE_VARS), None)
        if not temp_proxy:
            continue

        coef_rows = coefficients[coefficients["role_id"].eq(str(row["role_id"]))].copy()
        if temp_proxy == TA_COL:
            coef_row = coef_rows[coef_rows["predictor"].astype(str).str.contains("TA", regex=False)].head(1)
        else:
            coef_row = coef_rows[coef_rows["predictor"].astype(str).str.contains("省平均气温", regex=False)].head(1)
        if coef_row.empty:
            continue

        filled = fill_panel_median(base_df[["Province", temp_proxy]].copy(), temp_proxy)
        temp_std = float(np.nanstd(filled.to_numpy(), ddof=0))
        if not np.isfinite(temp_std) or temp_std == 0:
            temp_std = 1.0

        temp_coef = float(coef_row.iloc[0]["coef"])
        roles.append(
            {
                "id": str(row["role_id"]),
                "label": str(row["role_label"]),
                "scheme_id": str(row["scheme_id"]),
                "scheme_source": str(row["scheme_source"]),
                "fe_label": str(row["fe_label"]),
                "temp_proxy": temp_proxy,
                "temp_metric_id": "ta" if temp_proxy == TA_COL else "province_tas",
                "temp_coef": temp_coef,
                "temp_std": temp_std,
                "temp_coef_per_degree": temp_coef / temp_std,
            }
        )

    role_order = temperature_role_order([item["id"] for item in roles])
    role_map = {item["id"]: item for item in roles}
    ordered_roles = [role_map[role_id] for role_id in role_order if role_id in role_map]
    return role_order, ordered_roles


def build_contribution_data(
    roles: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    region_df = read_csv(PROVINCE_REGION_PATH)
    region_lookup = {
        str(row["province"]): {
            "region": str(row.get("region", "")),
            "region_en": str(row.get("region_en", "")),
            "region_order": int(row.get("region_order", 99)) if pd.notna(row.get("region_order")) else 99,
        }
        for _, row in region_df.iterrows()
    }

    yearly_rows: list[dict[str, object]] = []
    province_rows: list[dict[str, object]] = []

    for mode in MODE_ORDER:
        projection_path = RESULTS_DIR / mode / "projection_outputs" / "future_scenario_projection_panel.csv"
        projection_df = read_csv(projection_path)
        projection_df["Year"] = pd.to_numeric(projection_df["Year"], errors="coerce").astype(int)
        projection_df["temperature_baseline"] = to_float(projection_df["temperature_baseline"])
        projection_df["temperature_scenario"] = to_float(projection_df["temperature_scenario"])
        projection_df["temperature_delta"] = to_float(projection_df["temperature_delta"])
        projection_df["delta_vs_baseline"] = to_float(projection_df["delta_vs_baseline"])

        for role in roles:
            role_df = projection_df[projection_df["role_id"].eq(role["id"])].copy()
            if role_df.empty:
                continue
            role_df["temp_contribution"] = float(role["temp_coef_per_degree"]) * role_df["temperature_delta"]

            grouped = (
                role_df.groupby(["scenario_id", "statistic", "Year"], dropna=False)
                .agg(
                    baseline_pred_mean=("baseline_pred", "mean"),
                    scenario_pred_mean=("scenario_pred", "mean"),
                    temp_baseline_mean=("temperature_baseline", "mean"),
                    temp_scenario_mean=("temperature_scenario", "mean"),
                    temp_delta_mean=("temperature_delta", "mean"),
                    temp_contribution_mean=("temp_contribution", "mean"),
                    total_delta_mean=("delta_vs_baseline", "mean"),
                )
                .reset_index()
            )
            for _, row in grouped.iterrows():
                yearly_rows.append(
                    {
                        "baseline_mode": mode,
                        "role_id": role["id"],
                        "scenario_id": str(row["scenario_id"]),
                        "statistic": str(row["statistic"]),
                        "year": int(row["Year"]),
                        "baseline_pred_mean": float(row["baseline_pred_mean"]),
                        "scenario_pred_mean": float(row["scenario_pred_mean"]),
                        "temp_baseline_mean": float(row["temp_baseline_mean"]),
                        "temp_scenario_mean": float(row["temp_scenario_mean"]),
                        "temp_delta_mean": float(row["temp_delta_mean"]),
                        "temp_contribution_mean": float(row["temp_contribution_mean"]),
                        "total_delta_mean": float(row["total_delta_mean"]),
                    }
                )

            province_2050 = role_df[
                role_df["Year"].eq(FUTURE_END_YEAR) & role_df["statistic"].eq("median")
            ].copy()
            for _, row in province_2050.iterrows():
                province_meta = region_lookup.get(str(row["Province"]), {})
                province_rows.append(
                    {
                        "baseline_mode": mode,
                        "role_id": role["id"],
                        "scenario_id": str(row["scenario_id"]),
                        "Province": str(row["Province"]),
                        "region": str(province_meta.get("region", "")),
                        "region_en": str(province_meta.get("region_en", "")),
                        "region_order": int(province_meta.get("region_order", 99)),
                        "baseline_pred": float(row["baseline_pred"]),
                        "scenario_pred": float(row["scenario_pred"]),
                        "temp_baseline": float(row["temperature_baseline"]),
                        "temp_scenario": float(row["temperature_scenario"]),
                        "temp_delta": float(row["temperature_delta"]),
                        "temp_contribution": float(row["temp_contribution"]),
                        "total_delta": float(row["delta_vs_baseline"]),
                    }
                )

    return yearly_rows, province_rows


def build_files() -> list[dict[str, str]]:
    return [
        {
            "label": "Local output page",
            "path": rel(OUT_FILE),
            "note": "温度专页本身；和 index.html 并行。",
        },
        {
            "label": "Temperature dashboard figures",
            "path": rel(FIGURE_DIR),
            "note": "温度页预先绘制好的 PNG 图件目录，HTML 直接引用这里的图片。",
        },
        {
            "label": "TA future panel",
            "path": rel(PROJECT_DIR / "data_processed" / "TA_future_panel.csv"),
            "note": "从 CCKP tas + 1991-2020 reference 构建的 TA 面板。",
        },
        {
            "label": "SSP province mean tas panel",
            "path": rel(PROJECT_DIR / "data_processed" / "ssp_province_mean_tas_panel.csv"),
            "note": "从 data_raw 再处理得到的 SSP 省平均气温绝对温度面板。",
        },
        {
            "label": "TA common input",
            "path": rel(RESULTS_DIR / "common_inputs" / "ta_future_panel.csv"),
            "note": "未来投影实际读取的 TA 输入。",
        },
        {
            "label": "Aligned province tas input",
            "path": rel(RESULTS_DIR / "common_inputs" / "province_tas_future_aligned.csv"),
            "note": "省平均气温对齐历史口径后的实际输入。",
        },
        {
            "label": "Province tas bias correction",
            "path": rel(RESULTS_DIR / "common_inputs" / "province_tas_bias_correction.csv"),
            "note": "省平均气温历史-外部路径 bias correction 结果。",
        },
        {
            "label": "Projection coefficients",
            "path": rel(RESULTS_DIR / "model_screening" / "future_projection_coefficients.csv"),
            "note": "温度系数来自这里。",
        },
        {
            "label": "Lancet ETS projection panel",
            "path": rel(RESULTS_DIR / "lancet_ets" / "projection_outputs" / "future_scenario_projection_panel.csv"),
            "note": "包含 temperature_baseline / temperature_scenario / temperature_delta。",
        },
        {
            "label": "X-driven projection panel",
            "path": rel(RESULTS_DIR / "x_driven" / "projection_outputs" / "future_scenario_projection_panel.csv"),
            "note": "温度贡献在另一种 baseline 下的并行结果。",
        },
    ]


def configure_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Atkinson Hyperlegible", "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "axes.titlesize": 13.5,
            "axes.labelsize": 11.5,
            "legend.fontsize": 9.5,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "figure.facecolor": FIGURE_BG,
            "axes.facecolor": FIGURE_PANEL,
            "savefig.facecolor": FIGURE_BG,
            "savefig.bbox": "tight",
        }
    )


def ensure_figure_dir() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)


def style_axis(ax: plt.Axes, grid_axis: str = "both", zero_axis: str | None = None) -> None:
    ax.set_facecolor(FIGURE_PANEL)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BORDER)
        ax.spines[side].set_linewidth(0.9)
    ax.tick_params(colors=INK, labelcolor=INK)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linestyle=(0, (3, 3)), linewidth=0.75, alpha=0.92)
        ax.set_axisbelow(True)
    if zero_axis == "h":
        ax.axhline(0, color="#5B6673", linewidth=1.15, zorder=2)
    elif zero_axis == "v":
        ax.axvline(0, color="#5B6673", linewidth=1.15, zorder=2)


def apply_publication_title(ax: plt.Axes, title: str, subtitle: str | None = None) -> None:
    ax.set_title(title, loc="left", pad=16, fontsize=13.6, fontweight="bold", color=INK)
    if subtitle:
        ax.text(
            0.0,
            1.01,
            subtitle,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9.7,
            color=MUTED,
        )


def style_legend(legend) -> None:
    if legend is None:
        return
    frame = legend.get_frame()
    frame.set_facecolor("#FFFDFA")
    frame.set_edgecolor(BORDER)
    frame.set_linewidth(0.8)
    frame.set_alpha(0.98)
    for text in legend.get_texts():
        text.set_color(INK)


def finish_figure(fig: plt.Figure, output_path: Path, note: str | None = None) -> None:
    note_space = 0.05 if note else 0.0
    fig.tight_layout(rect=(0, note_space, 1, 0.985))
    if note:
        fig.text(0.012, 0.016, note, ha="left", va="bottom", fontsize=8.9, color=MUTED)
    fig.savefig(output_path, dpi=240)
    plt.close(fig)


def points_to_frame(points: list[dict[str, float]]) -> pd.DataFrame:
    if not points:
        return pd.DataFrame(columns=["year", "value"])
    frame = pd.DataFrame(points)
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype(int)
    frame["value"] = to_float(frame["value"])
    return frame.sort_values("year").reset_index(drop=True)


def merge_stat_series(
    stat_map: dict[str, list[dict[str, float]]],
    history_points: list[dict[str, float]] | None = None,
    anchored: bool = False,
) -> pd.DataFrame:
    merged: pd.DataFrame | None = None
    for statistic in ("median", "p10", "p90"):
        points = list(stat_map.get(statistic, []))
        if history_points is not None:
            points = shifted_points(history_points, points, anchored=anchored)
        frame = points_to_frame(points).rename(columns={"value": statistic})
        merged = frame if merged is None else merged.merge(frame, on="year", how="outer")
    if merged is None:
        return pd.DataFrame(columns=["year", "median", "p10", "p90"])
    for column in ("median", "p10", "p90"):
        if column not in merged.columns:
            merged[column] = np.nan
    return merged.sort_values("year").reset_index(drop=True)


def yearly_stat_frame(yearly_df: pd.DataFrame, scenario_id: str, value_col: str) -> pd.DataFrame:
    subset = yearly_df[
        yearly_df["scenario_id"].eq(scenario_id) & yearly_df["statistic"].isin(["median", "p10", "p90"])
    ].copy()
    if subset.empty:
        return pd.DataFrame(columns=["year", "median", "p10", "p90"])
    subset["year"] = pd.to_numeric(subset["year"], errors="coerce").astype(int)
    subset[value_col] = to_float(subset[value_col])
    pivot = (
        subset.pivot_table(index="year", columns="statistic", values=value_col, aggfunc="mean")
        .reset_index()
        .rename_axis(None, axis=1)
        .sort_values("year")
    )
    for column in ("median", "p10", "p90"):
        if column not in pivot.columns:
            pivot[column] = np.nan
    return pivot[["year", "median", "p10", "p90"]].reset_index(drop=True)


def shifted_points(
    history_points: list[dict[str, float]],
    future_points: list[dict[str, float]],
    anchored: bool,
) -> list[dict[str, float]]:
    if not anchored or not history_points or not future_points:
        return future_points
    shift = float(history_points[-1]["value"]) - float(future_points[0]["value"])
    return [{"year": int(item["year"]), "value": float(item["value"]) + shift} for item in future_points]


def save_input_metric_figure(
    metric: dict[str, object],
    anchored: bool,
    output_path: Path,
) -> None:
    scenario_colors = {item["id"]: item["color"] for item in SCENARIO_META}
    history = list(metric["history"])
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    style_axis(ax, grid_axis="both")
    ax.plot(
        [int(item["year"]) for item in history],
        [float(item["value"]) for item in history],
        color=OBSERVED_LINE,
        linewidth=2.35,
        linestyle="--",
        label="Historical observed",
        zorder=4,
    )

    for meta in SCENARIO_META:
        stat_frame = merge_stat_series(((metric.get("series") or {}).get(meta["id"], {}) or {}), history, anchored)
        if stat_frame.empty:
            continue
        if stat_frame["p10"].notna().any() and stat_frame["p90"].notna().any():
            ax.fill_between(
                stat_frame["year"],
                stat_frame["p10"],
                stat_frame["p90"],
                color=scenario_colors[meta["id"]],
                alpha=RIBBON_ALPHA,
                linewidth=0,
                zorder=1,
            )
        ax.plot(
            stat_frame["year"],
            stat_frame["median"],
            color=scenario_colors[meta["id"]],
            linewidth=2.0,
            label=meta["label"],
            zorder=3,
        )

    display_suffix = "2023 anchored (display only)" if anchored else "raw SSP / aligned series"
    apply_publication_title(
        ax,
        title=f"{metric['label']} national mean trajectory",
        subtitle=f"Historical mean, 2014-2023 + SSP trajectories, 2024-2050 | {display_suffix}",
    )
    ax.set_xlabel("Year")
    ax.set_ylabel(f"{metric['label']} ({metric['unit']})")
    legend = ax.legend(
        ncol=3,
        frameon=True,
        loc="upper left",
        bbox_to_anchor=(0.0, 1.0),
        handlelength=2.4,
        columnspacing=1.3,
    )
    style_legend(legend)
    finish_figure(
        fig,
        output_path,
        note="Dashed black line shows the 2014-2023 historical mean; colored ribbons show p10-p90 across scenario statistics.",
    )


def save_contribution_figure(
    yearly_df: pd.DataFrame,
    mode_label: str,
    role_label: str,
    output_path: Path,
) -> None:
    scenario_colors = {item["id"]: item["color"] for item in SCENARIO_META}
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    style_axis(ax, grid_axis="both", zero_axis="h")
    if yearly_df.empty:
        ax.text(0.5, 0.5, "No contribution data", ha="center", va="center", fontsize=14)
        ax.axis("off")
        finish_figure(fig, output_path)
        return
    for meta in SCENARIO_META:
        sub = yearly_stat_frame(yearly_df, meta["id"], "temp_contribution_mean")
        if sub.empty:
            continue
        if sub["p10"].notna().any() and sub["p90"].notna().any():
            ax.fill_between(
                sub["year"],
                sub["p10"],
                sub["p90"],
                color=scenario_colors[meta["id"]],
                alpha=RIBBON_ALPHA,
                linewidth=0,
                zorder=1,
            )
        ax.plot(
            sub["year"],
            sub["median"],
            color=scenario_colors[meta["id"]],
            linewidth=2.05,
            label=meta["label"],
            zorder=3,
        )
    apply_publication_title(
        ax,
        title="National temperature-only contribution",
        subtitle=f"{role_label} | {mode_label} | annual national mean, 2024-2050",
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("Temperature-only ΔAMR (percentage points)")
    legend = ax.legend(
        ncol=3,
        frameon=True,
        loc="upper left",
        bbox_to_anchor=(0.0, 1.0),
        handlelength=2.3,
        columnspacing=1.3,
    )
    style_legend(legend)
    finish_figure(
        fig,
        output_path,
        note="Lines show median temperature-only ΔAMR by future scenario; shaded ribbons show p10-p90 for SSP scenarios, while AMC intervention is a single median path.",
    )


def save_vertical_bar_figure(
    rows: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    x_label: str,
    y_label: str,
    output_path: Path,
    color_lookup: dict[str, str] | None = None,
    color_key: str | None = None,
    lower_col: str | None = None,
    upper_col: str | None = None,
    note: str | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(9.8, 5.8))
    rows = rows.copy()
    style_axis(ax, grid_axis="y", zero_axis="h")
    if rows.empty:
        ax.text(0.5, 0.5, "No figure data", ha="center", va="center", fontsize=14)
        ax.axis("off")
        finish_figure(fig, output_path)
        return
    colors = None
    if color_lookup and color_key:
        colors = [color_lookup.get(str(value), POSITIVE_BAR) for value in rows[color_key]]
    if colors is None:
        colors = [POSITIVE_BAR if value >= 0 else NEGATIVE_BAR for value in rows[y_col].astype(float)]
    x_values = np.arange(len(rows))
    heights = rows[y_col].astype(float).to_numpy()
    bars = ax.bar(
        x_values,
        heights,
        color=colors,
        edgecolor="#FFFDF8",
        linewidth=0.8,
        width=0.78,
        zorder=3,
    )
    if lower_col and upper_col and lower_col in rows.columns and upper_col in rows.columns:
        lower_values = rows[lower_col].astype(float).to_numpy()
        upper_values = rows[upper_col].astype(float).to_numpy()
        lower = np.nan_to_num(np.clip(heights - lower_values, a_min=0, a_max=None), nan=0.0)
        upper = np.nan_to_num(np.clip(upper_values - heights, a_min=0, a_max=None), nan=0.0)
        ax.errorbar(
            x_values,
            heights,
            yerr=np.vstack([lower, upper]),
            fmt="none",
            ecolor=INK,
            elinewidth=1.0,
            capsize=3.8,
            capthick=1.0,
            zorder=4,
        )
    apply_publication_title(ax, title=title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_xticks(x_values, rows[x_col].astype(str))
    max_abs = max(np.max(np.abs(heights)), 0.001)
    for bar, value in zip(bars, heights):
        offset = 0.05 * max_abs
        va = "bottom" if value >= 0 else "top"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + (offset if value >= 0 else -offset),
            f"{value:+.3f}",
            ha="center",
            va=va,
            fontsize=9,
            color=INK,
        )
    finish_figure(
        fig,
        output_path,
        note=note
        or "Bars show the median 2050 effect; whiskers show the p10-p90 range across scenario statistics, not a frequentist confidence interval.",
    )


def save_horizontal_bar_figure(
    rows: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str,
    x_label: str,
    y_label: str,
    output_path: Path,
    color_mode: str = "signed",
    subtitle: str | None = None,
    note: str | None = None,
) -> None:
    if rows.empty:
        fig, ax = plt.subplots(figsize=(10.2, 4.8))
        ax.text(0.5, 0.5, "No figure data", ha="center", va="center", fontsize=14)
        ax.axis("off")
        finish_figure(fig, output_path)
        return
    values = rows[value_col].astype(float)
    labels = rows[label_col].astype(str)
    if color_mode == "scenario_gap":
        colors = [NEGATIVE_BAR if value <= 0 else POSITIVE_BAR for value in values]
    else:
        colors = [NEGATIVE_BAR if value <= 0 else POSITIVE_BAR for value in values]

    fig_height = max(4.8, 0.38 * len(rows) + 1.4)
    fig, ax = plt.subplots(figsize=(10.2, fig_height))
    style_axis(ax, grid_axis="x", zero_axis="v")
    positions = np.arange(len(rows))
    bars = ax.barh(
        positions,
        values,
        color=colors,
        edgecolor="#FFFDF8",
        linewidth=0.8,
        zorder=3,
    )
    max_abs = max(values.abs().max(), 0.001)
    min_bound = min(float(values.min()), 0.0)
    max_bound = max(float(values.max()), 0.0)
    ax.set_xlim(min_bound - 0.24 * max_abs, max_bound + 0.24 * max_abs)
    apply_publication_title(ax, title=title, subtitle=subtitle)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_yticks(positions, labels)
    for bar, value in zip(bars, values):
        offset = 0.03 * max_abs
        x_pos = value + (offset if value >= 0 else -offset)
        ha = "left" if value >= 0 else "right"
        ax.text(
            x_pos,
            bar.get_y() + bar.get_height() / 2,
            f"{value:+.3f}",
            va="center",
            ha=ha,
            fontsize=9,
            color=INK,
        )
    ax.invert_yaxis()
    finish_figure(
        fig,
        output_path,
        note=note or "Horizontal bars are ordered from the strongest positive contribution to the weakest or negative contribution.",
    )


def aggregate_region_table(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows.copy()
    grouped = (
        rows.groupby(["region", "region_en", "region_order"], dropna=False)
        .agg(
            province_n=("Province", "nunique"),
            baseline_pred_mean=("baseline_pred", "mean"),
            scenario_pred_mean=("scenario_pred", "mean"),
            temp_baseline_mean=("temp_baseline", "mean"),
            temp_scenario_mean=("temp_scenario", "mean"),
            temp_delta_mean=("temp_delta", "mean"),
            temp_contribution_mean=("temp_contribution", "mean"),
            total_delta_mean=("total_delta", "mean"),
        )
        .reset_index()
        .sort_values(["region_order", "temp_contribution_mean"], ascending=[True, False])
    )
    return grouped.reset_index(drop=True)


def build_province_focus(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows.copy()
    ranked = rows.sort_values("temp_contribution", ascending=False).copy()
    focus = pd.concat([ranked.head(8), ranked.tail(4)], ignore_index=True)
    focus = focus.drop_duplicates(subset=["Province"], keep="first")
    focus = focus.sort_values("temp_contribution", ascending=False)
    return focus.reset_index(drop=True)


def build_region_gap_table(
    province_df: pd.DataFrame,
    mode: str,
    role_id: str,
    low_scenario: str,
    high_scenario: str,
) -> pd.DataFrame:
    low_rows = aggregate_region_table(
        province_df[
            province_df["baseline_mode"].eq(mode)
            & province_df["role_id"].eq(role_id)
            & province_df["scenario_id"].eq(low_scenario)
        ].copy()
    )
    high_rows = aggregate_region_table(
        province_df[
            province_df["baseline_mode"].eq(mode)
            & province_df["role_id"].eq(role_id)
            & province_df["scenario_id"].eq(high_scenario)
        ].copy()
    )
    if low_rows.empty or high_rows.empty:
        return pd.DataFrame()
    merged = high_rows.merge(
        low_rows,
        on="region",
        suffixes=("_high", "_low"),
        how="inner",
    )
    merged["temp_contribution_gap"] = merged["temp_contribution_mean_high"] - merged["temp_contribution_mean_low"]
    merged["temp_delta_gap"] = merged["temp_delta_mean_high"] - merged["temp_delta_mean_low"]
    merged["total_delta_gap"] = merged["total_delta_mean_high"] - merged["total_delta_mean_low"]
    merged["region_en"] = merged["region_en_high"].fillna(merged["region_en_low"])
    merged["region_order"] = merged["region_order_high"].fillna(merged["region_order_low"])
    return merged.sort_values("temp_contribution_gap", ascending=False).reset_index(drop=True)


def build_province_gap_table(
    province_df: pd.DataFrame,
    mode: str,
    role_id: str,
    low_scenario: str,
    high_scenario: str,
) -> pd.DataFrame:
    low_rows = province_df[
        province_df["baseline_mode"].eq(mode)
        & province_df["role_id"].eq(role_id)
        & province_df["scenario_id"].eq(low_scenario)
    ].copy()
    high_rows = province_df[
        province_df["baseline_mode"].eq(mode)
        & province_df["role_id"].eq(role_id)
        & province_df["scenario_id"].eq(high_scenario)
    ].copy()
    if low_rows.empty or high_rows.empty:
        return pd.DataFrame()
    merged = high_rows.merge(low_rows, on="Province", suffixes=("_high", "_low"), how="inner")
    merged["temp_contribution_gap"] = merged["temp_contribution_high"] - merged["temp_contribution_low"]
    merged["temp_delta_gap"] = merged["temp_delta_high"] - merged["temp_delta_low"]
    merged["total_delta_gap"] = merged["total_delta_high"] - merged["total_delta_low"]
    merged["region"] = merged["region_high"].fillna(merged["region_low"])
    return merged.sort_values("temp_contribution_gap", ascending=False).reset_index(drop=True)


def build_standard_metric_tag(role: dict[str, object]) -> str:
    proxy = str(role.get("temp_proxy", "")).strip()
    role_id = str(role.get("id", "")).strip()
    if proxy == TA_COL:
        return f"temperature_ta_{role_id}"
    if proxy == PROVINCE_TAS_COL:
        return f"temperature_province_tas_{role_id}"
    return f"temperature_{role_id}"


def collect_standard_result_figures(role: dict[str, object], mode: str) -> dict[str, str]:
    metric_tag = build_standard_metric_tag(role)
    mode_dir = RESULTS_DIR / mode
    expected = {
        "regional_grid": mode_dir / "regional_figures" / f"regional_figure5_grid_{metric_tag}.png",
        "regional_heatmap": mode_dir / "regional_figures" / f"regional_delta_2050_heatmap_{metric_tag}.png",
        "provincial_panel": mode_dir / "provincial_figures" / f"provincial_future_scenario_panel_{metric_tag}.png",
        "dual_predicted": mode_dir / "dual_scenario_figures" / f"dual_scenario_compare_{metric_tag}_ssp119_vs_ssp585.png",
        "dual_delta": mode_dir / "dual_scenario_figures" / f"dual_scenario_compare_{metric_tag}_ssp119_vs_ssp585_delta.png",
    }
    return {
        key: rel(path)
        for key, path in expected.items()
        if path.exists()
    }


def build_figure_manifest(data: dict[str, object]) -> dict[str, object]:
    configure_matplotlib()
    ensure_figure_dir()

    scenario_color_map = {item["id"]: item["color"] for item in SCENARIO_META}
    scenario_label_map = {item["id"]: item["label"] for item in SCENARIO_META}
    mode_label_map = {item["id"]: item["label"] for item in MODE_META}
    role_label_map = {item["id"]: item["label"] for item in data["roles"]}
    role_yearly_df = pd.DataFrame(data["role_yearly"])
    province_df = pd.DataFrame(data["province_2050"])
    end_year = int(data["summary"]["end_year"])
    low_scenario = str(data["compare_pair"]["low"])
    high_scenario = str(data["compare_pair"]["high"])

    manifest: dict[str, object] = {
        "input": {},
        "national_delta": {},
        "contribution": {},
        "spatial_region": {},
        "spatial_province": {},
        "compare_region": {},
        "compare_province": {},
        "standard_results": {},
    }

    for metric in data["input_metrics"]:
        metric_id = str(metric["id"])
        manifest["input"][metric_id] = {}
        for display_mode, anchored in (("raw", False), ("anchored", True)):
            output_path = FIGURE_DIR / f"input__{metric_id}__{display_mode}.png"
            save_input_metric_figure(metric, anchored=anchored, output_path=output_path)
            manifest["input"][metric_id][display_mode] = rel(output_path)

    for mode in MODE_ORDER:
        manifest["national_delta"][mode] = {}
        manifest["contribution"][mode] = {}
        manifest["spatial_region"][mode] = {}
        manifest["spatial_province"][mode] = {}
        manifest["compare_region"][mode] = {}
        manifest["compare_province"][mode] = {}
        manifest["standard_results"][mode] = {}

        for role_id in data["role_order"]:
            role_meta = next((item for item in data["roles"] if item["id"] == role_id), None)
            manifest["standard_results"][mode][role_id] = (
                collect_standard_result_figures(role_meta, mode) if role_meta else {}
            )
            role_yearly = role_yearly_df[
                role_yearly_df["baseline_mode"].eq(mode) & role_yearly_df["role_id"].eq(role_id)
            ].copy()
            role_yearly["year"] = pd.to_numeric(role_yearly["year"], errors="coerce").astype(int)

            contribution_path = FIGURE_DIR / f"contribution__{mode}__{role_id}.png"
            save_contribution_figure(
                yearly_df=role_yearly,
                mode_label=mode_label_map.get(mode, mode),
                role_label=role_label_map.get(role_id, role_id),
                output_path=contribution_path,
            )
            manifest["contribution"][mode][role_id] = rel(contribution_path)

            delta_rows = role_yearly[
                role_yearly["year"].eq(end_year)
                & role_yearly["scenario_id"].isin(SCENARIO_ORDER)
            ].copy()
            delta_rows = (
                delta_rows.pivot_table(
                    index="scenario_id",
                    columns="statistic",
                    values="temp_contribution_mean",
                    aggfunc="mean",
                )
                .reset_index()
                .rename_axis(None, axis=1)
            )
            delta_rows["scenario_order"] = delta_rows["scenario_id"].map({sid: idx for idx, sid in enumerate(SCENARIO_ORDER)})
            delta_rows = delta_rows.sort_values("scenario_order")
            delta_rows["scenario_label"] = delta_rows["scenario_id"].map(scenario_label_map)
            for column in ("median", "p10", "p90"):
                if column not in delta_rows.columns:
                    delta_rows[column] = np.nan

            national_delta_path = FIGURE_DIR / f"national_delta__{mode}__{role_id}.png"
            save_vertical_bar_figure(
                rows=delta_rows,
                x_col="scenario_label",
                y_col="median",
                title="2050 scenario deltas from the temperature channel",
                x_label="Future scenario",
                y_label="Temperature-only ΔAMR in 2050 (percentage points)",
                output_path=national_delta_path,
                color_lookup=scenario_color_map,
                color_key="scenario_id",
                lower_col="p10",
                upper_col="p90",
                note=f"{role_label_map.get(role_id, role_id)} | {mode_label_map.get(mode, mode)} | whiskers show p10-p90 for SSP scenarios; AMC intervention has a single median path.",
            )
            manifest["national_delta"][mode][role_id] = rel(national_delta_path)

            manifest["spatial_region"][mode][role_id] = {}
            manifest["spatial_province"][mode][role_id] = {}
            for scenario_id in SCENARIO_ORDER:
                scenario_rows = province_df[
                    province_df["baseline_mode"].eq(mode)
                    & province_df["role_id"].eq(role_id)
                    & province_df["scenario_id"].eq(scenario_id)
                ].copy()
                if scenario_rows.empty:
                    continue

                region_rows = aggregate_region_table(scenario_rows).sort_values("temp_contribution_mean", ascending=False)
                spatial_region_path = FIGURE_DIR / f"spatial_region__{mode}__{role_id}__{scenario_id}.png"
                save_horizontal_bar_figure(
                    rows=region_rows,
                    label_col="region",
                    value_col="temp_contribution_mean",
                    title="Regional temperature-channel pattern",
                    x_label="Temperature-only ΔAMR (percentage points)",
                    y_label="Region",
                    output_path=spatial_region_path,
                    subtitle=f"{role_label_map.get(role_id, role_id)} | {mode_label_map.get(mode, mode)} | {scenario_label_map.get(scenario_id, scenario_id)} | 2050",
                    note="Each bar is the mean province-level temperature-only contribution within a region in 2050.",
                )
                manifest["spatial_region"][mode][role_id][scenario_id] = rel(spatial_region_path)

                province_focus = build_province_focus(scenario_rows)
                spatial_province_path = FIGURE_DIR / f"spatial_province__{mode}__{role_id}__{scenario_id}.png"
                save_horizontal_bar_figure(
                    rows=province_focus,
                    label_col="Province",
                    value_col="temp_contribution",
                    title="Provincial temperature-channel hotspots",
                    x_label="Temperature-only ΔAMR (percentage points)",
                    y_label="Province",
                    output_path=spatial_province_path,
                    subtitle=f"{role_label_map.get(role_id, role_id)} | {mode_label_map.get(mode, mode)} | {scenario_label_map.get(scenario_id, scenario_id)} | 2050",
                    note="Top bars mark the strongest warming-sensitive provinces; the tail keeps the weakest or negative contributors for contrast.",
                )
                manifest["spatial_province"][mode][role_id][scenario_id] = rel(spatial_province_path)

            region_gap_rows = build_region_gap_table(province_df, mode, role_id, low_scenario, high_scenario)
            compare_region_path = FIGURE_DIR / f"compare_region__{mode}__{role_id}.png"
            save_horizontal_bar_figure(
                rows=region_gap_rows,
                label_col="region",
                value_col="temp_contribution_gap",
                title="Regional gap between the low and high SSP pathways",
                x_label=f"Temperature-only ΔAMR gap ({high_scenario.upper()} - {low_scenario.upper()})",
                y_label="Region",
                output_path=compare_region_path,
                color_mode="scenario_gap",
                subtitle=f"{role_label_map.get(role_id, role_id)} | {mode_label_map.get(mode, mode)} | {scenario_label_map.get(high_scenario, high_scenario)} - {scenario_label_map.get(low_scenario, low_scenario)}",
                note="Positive bars mean the high-emissions pathway produces a larger temperature-only contribution than the low-emissions pathway.",
            )
            manifest["compare_region"][mode][role_id] = rel(compare_region_path)

            province_gap_rows = build_province_gap_table(province_df, mode, role_id, low_scenario, high_scenario).head(12)
            compare_province_path = FIGURE_DIR / f"compare_province__{mode}__{role_id}.png"
            save_horizontal_bar_figure(
                rows=province_gap_rows,
                label_col="Province",
                value_col="temp_contribution_gap",
                title="Provincial gap between the low and high SSP pathways",
                x_label=f"Temperature-only ΔAMR gap ({high_scenario.upper()} - {low_scenario.upper()})",
                y_label="Province",
                output_path=compare_province_path,
                color_mode="scenario_gap",
                subtitle=f"{role_label_map.get(role_id, role_id)} | {mode_label_map.get(mode, mode)} | {scenario_label_map.get(high_scenario, high_scenario)} - {scenario_label_map.get(low_scenario, low_scenario)}",
                note="Only the largest province-level gaps are shown here so the page keeps the cross-scenario contrast readable.",
            )
            manifest["compare_province"][mode][role_id] = rel(compare_province_path)

    return manifest


def build_data() -> dict[str, object]:
    base_df = load_base_frame()
    role_order, roles = build_role_meta(base_df)
    yearly_rows, province_rows = build_contribution_data(roles)

    ta_input = read_csv(RESULTS_DIR / "common_inputs" / "ta_future_panel.csv")
    ta_input["Year"] = pd.to_numeric(ta_input["Year"], errors="coerce").astype(int)
    prov_input = read_csv(RESULTS_DIR / "common_inputs" / "province_tas_future_aligned.csv")
    prov_input["Year"] = pd.to_numeric(prov_input["Year"], errors="coerce").astype(int)

    history_ta = base_df.groupby("Year", dropna=False)[TA_COL].mean().reset_index(name="value")
    history_prov = base_df.groupby("Year", dropna=False)[PROVINCE_TAS_COL].mean().reset_index(name="value")

    input_metrics = [
        build_input_metric(
            metric_id="ta",
            label="Temperature anomaly (TA)",
            unit="°C",
            note="直接使用 TA anomaly 的未来面板；参考期为 1991-2020。",
            history_series=history_ta,
            future_df=ta_input,
            value_col=TA_COL,
        ),
        build_input_metric(
            metric_id="province_tas",
            label="SSP province mean temperature",
            unit="°C",
            note="使用对齐后的绝对温度路径；这里讲的是省平均气温，不是 anomaly。",
            history_series=history_prov,
            future_df=prov_input,
            value_col=PROVINCE_TAS_ALIGNED_COL if PROVINCE_TAS_ALIGNED_COL in prov_input.columns else PROVINCE_TAS_COL,
        ),
    ]

    bias_df = read_csv(RESULTS_DIR / "common_inputs" / "province_tas_bias_correction.csv")
    bias_df["additive_bias"] = to_float(bias_df["additive_bias"])
    bias_summary = (
        bias_df.groupby(["scenario", "statistic"], dropna=False)["additive_bias"]
        .agg(["mean", "min", "max"])
        .reset_index()
        .rename(columns={"scenario": "scenario_id", "mean": "mean_bias", "min": "min_bias", "max": "max_bias"})
    )
    bias_summary["scenario_id"] = pd.Categorical(bias_summary["scenario_id"], categories=SCENARIO_ORDER, ordered=True)
    bias_summary["statistic"] = pd.Categorical(bias_summary["statistic"], categories=["median", "p10", "p90"], ordered=True)
    bias_summary = bias_summary.sort_values(["scenario_id", "statistic"]).reset_index(drop=True)

    ta_role_count = sum(1 for role in roles if role["temp_proxy"] == TA_COL)
    province_role_count = sum(1 for role in roles if role["temp_proxy"] == PROVINCE_TAS_COL)

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "history_start": HISTORICAL_START_YEAR,
            "history_end": HISTORICAL_END_YEAR,
            "start_year": HISTORICAL_END_YEAR + 1,
            "end_year": FUTURE_END_YEAR,
            "scenario_count": len(SCENARIO_ORDER),
            "province_count": int(base_df["Province"].nunique()),
            "role_count": len(roles),
            "ta_role_count": ta_role_count,
            "province_tas_role_count": province_role_count,
            "bias_mean": float(bias_df["additive_bias"].mean()),
            "bias_min": float(bias_df["additive_bias"].min()),
            "bias_max": float(bias_df["additive_bias"].max()),
        },
        "scenario_meta": SCENARIO_META,
        "mode_meta": MODE_META,
        "role_order": role_order,
        "roles": roles,
        "input_metrics": input_metrics,
        "bias_summary": bias_summary.to_dict(orient="records"),
        "role_yearly": yearly_rows,
        "province_2050": province_rows,
        "files": build_files(),
        "design_rules": DESIGN_RULES,
        "references": LITERATURE_REFERENCES,
        "default_mode": "lancet_ets",
        "default_role": (
            "strict_main_model"
            if "strict_main_model" in role_order
            else ("main_model" if "main_model" in role_order else role_order[0])
        ),
        "default_scenario": "ssp585",
        "compare_pair": {"low": "ssp119", "high": "ssp585"},
    }
    data["figures"] = build_figure_manifest(data)
    return data


def build_styles() -> str:
    return """
      @import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Crimson+Pro:wght@400;500;600;700&display=swap');
      :root {
        --bg: #f6f1e8;
        --panel: rgba(255, 253, 248, 0.97);
        --panel-soft: #f8f3eb;
        --ink: #22303c;
        --muted: #5f6c79;
        --line: #d9d1c4;
        --line-strong: #c9bead;
        --hot: #c96c32;
        --cool: #4c78a8;
        --good: #4f8a5b;
        --gold: #c4932e;
        --danger: #b54a3a;
        --shadow: 0 18px 36px rgba(102, 81, 51, 0.08);
        --radius-xl: 28px;
        --radius-lg: 20px;
        --radius-md: 14px;
        --serif: "Crimson Pro", "Noto Serif SC", "Source Han Serif SC", Georgia, serif;
        --sans: "Atkinson Hyperlegible", "Noto Sans SC", "Microsoft YaHei", sans-serif;
      }
      * { box-sizing: border-box; }
      html { scroll-behavior: smooth; }
      body {
        margin: 0;
        color: var(--ink);
        font-family: var(--sans);
        background:
          radial-gradient(circle at top left, rgba(76, 120, 168, 0.08), transparent 28%),
          radial-gradient(circle at top right, rgba(201, 108, 50, 0.09), transparent 30%),
          linear-gradient(180deg, #faf6ef 0%, #f3ede3 52%, #efe7db 100%);
      }
      body::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        opacity: 0.22;
        background-image:
          linear-gradient(rgba(141, 124, 101, 0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(141, 124, 101, 0.03) 1px, transparent 1px);
        background-size: 24px 24px, 24px 24px;
      }
      a { color: inherit; }
      .page {
        width: min(1480px, calc(100vw - 28px));
        margin: 18px auto 42px;
        display: grid;
        gap: 18px;
      }
      .hero, .section {
        background: var(--panel);
        border: 1px solid var(--line);
        box-shadow: var(--shadow);
        border-radius: var(--radius-xl);
      }
      .hero {
        padding: 34px;
        display: grid;
        gap: 24px;
        background:
          linear-gradient(135deg, rgba(255, 253, 248, 0.98), rgba(247, 241, 231, 0.98)),
          radial-gradient(circle at right top, rgba(196, 147, 46, 0.10), transparent 24%),
          radial-gradient(circle at left bottom, rgba(76, 120, 168, 0.10), transparent 30%);
      }
      .hero-grid, .section-head, .grid-2, .grid-3, .grid-4, .controls, .files-grid {
        display: grid;
        gap: 16px;
      }
      .hero-grid { grid-template-columns: 1.45fr 1fr; }
      .section-head { grid-template-columns: 1.15fr 1fr; align-items: end; }
      .grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .controls { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .controls-single { grid-template-columns: minmax(280px, 420px); }
      .files-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .eyebrow {
        margin-bottom: 12px;
        font-size: 12px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: rgba(95, 108, 121, 0.84);
      }
      h1, h2, h3, p { margin: 0; }
      h1 {
        font-family: var(--serif);
        font-size: clamp(40px, 5vw, 72px);
        line-height: 0.98;
        letter-spacing: -0.035em;
        max-width: 11ch;
      }
      h2 {
        font-family: var(--serif);
        font-size: clamp(28px, 3vw, 40px);
        line-height: 1.08;
        letter-spacing: -0.02em;
      }
      h3 {
        font-family: var(--serif);
        font-size: 22px;
        line-height: 1.16;
      }
      p, li {
        color: var(--muted);
        font-size: 15px;
        line-height: 1.75;
      }
      .hero-links, .legend {
        display: flex;
        flex-wrap: wrap;
        gap: 10px 14px;
      }
      .pill-link {
        display: inline-flex;
        align-items: center;
        padding: 10px 14px;
        border-radius: 999px;
        text-decoration: none;
        background: rgba(255, 251, 244, 0.92);
        border: 1px solid var(--line);
        color: var(--ink);
        font-size: 13px;
      }
      .pill-link:hover, .nav a:hover, .file-link:hover, .reference-link:hover {
        border-color: var(--line-strong);
        box-shadow: 0 8px 18px rgba(102, 81, 51, 0.08);
      }
      .hero-note, .card, .chart-card, .table-card {
        border-radius: 20px;
        border: 1px solid var(--line);
        background: linear-gradient(180deg, rgba(255, 253, 248, 0.98), rgba(250, 246, 239, 0.98));
        padding: 18px;
      }
      .hero-note, .card, .chart-card, .table-card, .section {
        display: grid;
        gap: 14px;
      }
      .section { padding: 28px; gap: 20px; }
      .hero-metrics {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
      }
      .metric {
        padding: 18px;
        border-radius: 18px;
        background: rgba(255, 252, 246, 0.95);
        border: 1px solid var(--line);
        display: grid;
        gap: 8px;
      }
      .metric .k, .mini-label {
        font-size: 12px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: rgba(95, 108, 121, 0.78);
      }
      .metric .v, .value-md {
        font-size: clamp(24px, 3vw, 38px);
        line-height: 1;
        color: var(--ink);
        font-weight: 700;
      }
      .metric .h, .subtle, .mode-note, .table-caption {
        color: var(--muted);
        font-size: 13px;
      }
      .nav {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 10px;
      }
      .nav a {
        text-decoration: none;
        padding: 13px 14px;
        border-radius: 16px;
        background: rgba(255, 251, 244, 0.92);
        border: 1px solid var(--line);
        color: var(--ink);
        font-weight: 700;
        font-size: 14px;
      }
      .chart-box {
        width: 100%;
        min-height: 320px;
        border-radius: 18px;
        background: #fffdfa;
        border: 1px solid var(--line);
        overflow: hidden;
      }
      .figure-link {
        display: block;
        width: 100%;
        height: 100%;
        text-decoration: none;
      }
      .figure-image {
        display: block;
        width: 100%;
        height: auto;
        background: #fffdfa;
      }
      .figure-caption {
        font-size: 12.5px;
        line-height: 1.72;
        color: var(--muted);
      }
      .chart-wrap { display: grid; gap: 10px; padding: 14px; }
      .legend-item {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: var(--muted);
        font-size: 12px;
      }
      .legend-swatch {
        width: 12px;
        height: 12px;
        border-radius: 999px;
      }
      label {
        display: grid;
        gap: 8px;
        font-size: 13px;
        color: var(--muted);
      }
      select {
        width: 100%;
        padding: 12px 14px;
        border-radius: 14px;
        border: 1px solid var(--line-strong);
        background: #fffdfa;
        color: var(--ink);
        font: inherit;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        color: var(--ink);
      }
      th, td {
        padding: 11px 10px;
        border-bottom: 1px solid var(--line);
        text-align: left;
        vertical-align: top;
      }
      th {
        color: var(--ink);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: #f7f1e7;
      }
      tbody tr:nth-child(even) { background: rgba(95, 108, 121, 0.035); }
      .delta-pos { color: var(--hot); }
      .delta-neg { color: var(--cool); }
      .delta-flat { color: var(--muted); }
      .empty-state {
        padding: 20px;
        border-radius: 16px;
        background: #f8f3eb;
        border: 1px dashed var(--line-strong);
        color: var(--muted);
        font-size: 14px;
      }
      .file-link {
        display: grid;
        gap: 6px;
        padding: 16px;
        border-radius: 16px;
        text-decoration: none;
        color: inherit;
        background: rgba(255, 252, 246, 0.95);
        border: 1px solid var(--line);
      }
      .file-link strong { color: var(--ink); font-size: 14px; }
      .file-link span { font-size: 12px; color: var(--muted); overflow-wrap: anywhere; }
      .logic-grid, .story-grid {
        display: grid;
        gap: 16px;
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .story-card {
        padding: 18px;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: linear-gradient(180deg, rgba(255, 253, 248, 0.98), rgba(246, 239, 228, 0.98));
        display: grid;
        gap: 10px;
      }
      .story-card strong {
        color: var(--ink);
        font-size: 15px;
      }
      .story-card ol {
        margin: 0;
        padding-left: 18px;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.75;
      }
      .narrative {
        padding: 18px 20px;
        border-radius: 18px;
        border: 1px solid rgba(196, 147, 46, 0.35);
        background: linear-gradient(135deg, rgba(255, 248, 233, 0.96), rgba(247, 241, 231, 0.98));
      }
      .narrative strong { color: var(--ink); }
      .bar-list {
        display: grid;
        gap: 12px;
      }
      .bar-row {
        display: grid;
        grid-template-columns: 190px 1fr 90px;
        gap: 12px;
        align-items: center;
      }
      .bar-label {
        display: grid;
        gap: 2px;
      }
      .bar-label strong {
        color: #ffffff;
        font-size: 14px;
      }
      .bar-sub {
        font-size: 12px;
        color: rgba(229, 238, 251, 0.56);
      }
      .bar-track {
        position: relative;
        height: 14px;
        border-radius: 999px;
        background: rgba(95, 108, 121, 0.12);
        overflow: hidden;
      }
      .bar-axis {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 1px;
        background: rgba(34, 48, 60, 0.32);
      }
      .bar-fill {
        position: absolute;
        top: 0;
        bottom: 0;
        border-radius: 999px;
      }
      .bar-value {
        text-align: right;
        font-size: 13px;
        font-weight: 700;
        color: var(--ink);
      }
      .table-note {
        color: var(--muted);
        font-size: 12px;
        line-height: 1.65;
      }
      .accent-line {
        height: 1px;
        background: linear-gradient(90deg, rgba(76, 120, 168, 0.36), rgba(201, 108, 50, 0.36), transparent);
      }
      .reference-grid {
        display: grid;
        gap: 14px;
      }
      .reference-item {
        display: grid;
        gap: 8px;
        padding: 16px 18px;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: linear-gradient(180deg, rgba(255, 253, 248, 0.98), rgba(248, 242, 232, 0.98));
      }
      .reference-item strong {
        color: var(--ink);
        font-size: 15px;
      }
      .reference-note {
        font-size: 13px;
        color: var(--muted);
      }
      .reference-link {
        color: var(--cool);
        font-size: 12px;
        text-decoration: none;
        overflow-wrap: anywhere;
      }
      @media (max-width: 1180px) {
        .hero-grid, .section-head, .grid-2, .grid-3, .grid-4, .controls, .files-grid, .logic-grid, .story-grid { grid-template-columns: 1fr; }
        .hero-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .bar-row { grid-template-columns: 1fr; }
      }
      @media (max-width: 720px) {
        .page { width: min(100vw - 16px, 100%); }
        .hero, .section { padding: 18px; }
        .hero-metrics { grid-template-columns: 1fr; }
        h1 { max-width: none; }
      }
    """


def build_script() -> str:
    return """
      const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
      const SCENARIO_MAP = Object.fromEntries(DATA.scenario_meta.map(item => [item.id, item]));
      const MODE_MAP = Object.fromEntries(DATA.mode_meta.map(item => [item.id, item]));
      const ROLE_MAP = Object.fromEntries(DATA.roles.map(item => [item.id, item]));
      const INPUT_MAP = Object.fromEntries(DATA.input_metrics.map(item => [item.id, item]));
      const FIGURE_MAP = DATA.figures || {};
      const ROLE_YEARLY_INDEX = {};
      const PROVINCE_INDEX = {};

      DATA.role_yearly.forEach(row => {
        const key = `${row.baseline_mode}__${row.role_id}`;
        if (!ROLE_YEARLY_INDEX[key]) ROLE_YEARLY_INDEX[key] = [];
        ROLE_YEARLY_INDEX[key].push(row);
      });
      DATA.province_2050.forEach(row => {
        const key = `${row.baseline_mode}__${row.role_id}__${row.scenario_id}`;
        if (!PROVINCE_INDEX[key]) PROVINCE_INDEX[key] = [];
        PROVINCE_INDEX[key].push(row);
      });

      const state = {
        mode: DATA.default_mode,
        role: DATA.default_role,
        scenario: DATA.default_scenario,
        inputDisplay: "raw",
      };

      function fmt(value, digits = 2) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) return "NA";
        return Number(value).toLocaleString("zh-CN", {
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        });
      }

      function fmtSigned(value, digits = 2) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) return "NA";
        const num = Number(value);
        return `${num > 0 ? "+" : ""}${fmt(num, digits)}`;
      }

      function deltaClass(value) {
        const num = Number(value);
        if (!Number.isFinite(num) || Math.abs(num) < 1e-12) return "delta-flat";
        return num > 0 ? "delta-pos" : "delta-neg";
      }

      function sharePercent(part, whole) {
        const numerator = Number(part);
        const denominator = Number(whole);
        if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || Math.abs(denominator) < 1e-12) return null;
        return (numerator / denominator) * 100;
      }

      function scenarioLabel(id) {
        return SCENARIO_MAP[id] ? SCENARIO_MAP[id].label : id;
      }

      function metricUnit(metricId) {
        return INPUT_MAP[metricId] ? INPUT_MAP[metricId].unit : "";
      }

      function inputPoints(metric, scenarioId, statistic = "median") {
        const points = (((metric.series || {})[scenarioId] || {})[statistic] || []).map(item => ({
          year: Number(item.year),
          value: Number(item.value),
        }));
        if (state.inputDisplay !== "anchored" || !points.length || !(metric.history || []).length) {
          return points;
        }
        const lastHistory = [...metric.history].sort((a, b) => Number(a.year) - Number(b.year)).slice(-1)[0];
        const firstFuture = points[0];
        const shift = Number(lastHistory?.value) - Number(firstFuture?.value);
        if (!Number.isFinite(shift)) {
          return points;
        }
        return points.map(point => ({
          year: point.year,
          value: point.value + shift,
        }));
      }

      function roleRows(mode, roleId) {
        return ROLE_YEARLY_INDEX[`${mode}__${roleId}`] || [];
      }

      function roleEndRow(mode, roleId, scenarioId, statistic) {
        return roleRows(mode, roleId).find(
          row =>
            row.scenario_id === scenarioId &&
            row.statistic === statistic &&
            Number(row.year) === Number(DATA.summary.end_year)
        );
      }

      function provinceRows(mode, roleId, scenarioId) {
        return PROVINCE_INDEX[`${mode}__${roleId}__${scenarioId}`] || [];
      }

      function otherMode(mode) {
        const other = DATA.mode_meta.find(item => item.id !== mode);
        return other ? other.id : mode;
      }

      function baselineRow(mode = state.mode, roleId = state.role) {
        return roleEndRow(mode, roleId, "baseline_ets", "baseline");
      }

      function scenarioRows2050(mode = state.mode, roleId = state.role, statistic = "median") {
        return DATA.scenario_meta
          .map(item => ({ meta: item, row: roleEndRow(mode, roleId, item.id, statistic) }))
          .filter(item => item.row);
      }

      function aggregateRegionRows(rows) {
        const grouped = new Map();
        rows.forEach(row => {
          const key = row.region || "未分区";
          if (!grouped.has(key)) {
            grouped.set(key, {
              region: key,
              region_en: row.region_en || "",
              region_order: Number(row.region_order || 99),
              province_n: 0,
              baseline_pred_mean: 0,
              scenario_pred_mean: 0,
              temp_baseline_mean: 0,
              temp_scenario_mean: 0,
              temp_delta_mean: 0,
              temp_contribution_mean: 0,
              total_delta_mean: 0,
            });
          }
          const item = grouped.get(key);
          item.province_n += 1;
          item.baseline_pred_mean += Number(row.baseline_pred) || 0;
          item.scenario_pred_mean += Number(row.scenario_pred) || 0;
          item.temp_baseline_mean += Number(row.temp_baseline) || 0;
          item.temp_scenario_mean += Number(row.temp_scenario) || 0;
          item.temp_delta_mean += Number(row.temp_delta) || 0;
          item.temp_contribution_mean += Number(row.temp_contribution) || 0;
          item.total_delta_mean += Number(row.total_delta) || 0;
        });
        return [...grouped.values()]
          .map(item => ({
            ...item,
            baseline_pred_mean: item.baseline_pred_mean / item.province_n,
            scenario_pred_mean: item.scenario_pred_mean / item.province_n,
            temp_baseline_mean: item.temp_baseline_mean / item.province_n,
            temp_scenario_mean: item.temp_scenario_mean / item.province_n,
            temp_delta_mean: item.temp_delta_mean / item.province_n,
            temp_contribution_mean: item.temp_contribution_mean / item.province_n,
            total_delta_mean: item.total_delta_mean / item.province_n,
          }))
          .sort((a, b) => Number(a.region_order) - Number(b.region_order) || Number(b.temp_contribution_mean) - Number(a.temp_contribution_mean));
      }

      function regionRows(mode = state.mode, roleId = state.role, scenarioId = state.scenario) {
        return aggregateRegionRows(provinceRows(mode, roleId, scenarioId));
      }

      function provinceGapRows(mode = state.mode, roleId = state.role) {
        const lowId = DATA.compare_pair.low;
        const highId = DATA.compare_pair.high;
        const lowRows = new Map(provinceRows(mode, roleId, lowId).map(row => [row.Province, row]));
        const highRows = new Map(provinceRows(mode, roleId, highId).map(row => [row.Province, row]));
        return [...highRows.keys()]
          .filter(key => lowRows.has(key))
          .map(key => {
            const low = lowRows.get(key);
            const high = highRows.get(key);
            return {
              Province: key,
              region: high.region || low.region || "",
              region_en: high.region_en || low.region_en || "",
              region_order: Number(high.region_order || low.region_order || 99),
              low_temp_delta: Number(low.temp_delta) || 0,
              high_temp_delta: Number(high.temp_delta) || 0,
              temp_delta_gap: (Number(high.temp_delta) || 0) - (Number(low.temp_delta) || 0),
              low_temp_contribution: Number(low.temp_contribution) || 0,
              high_temp_contribution: Number(high.temp_contribution) || 0,
              temp_contribution_gap: (Number(high.temp_contribution) || 0) - (Number(low.temp_contribution) || 0),
              low_total_delta: Number(low.total_delta) || 0,
              high_total_delta: Number(high.total_delta) || 0,
              total_delta_gap: (Number(high.total_delta) || 0) - (Number(low.total_delta) || 0),
            };
          })
          .sort((a, b) => Number(b.temp_contribution_gap) - Number(a.temp_contribution_gap));
      }

      function regionGapRows(mode = state.mode, roleId = state.role) {
        const lowId = DATA.compare_pair.low;
        const highId = DATA.compare_pair.high;
        const lowRows = new Map(regionRows(mode, roleId, lowId).map(row => [row.region, row]));
        const highRows = new Map(regionRows(mode, roleId, highId).map(row => [row.region, row]));
        return [...highRows.keys()]
          .filter(key => lowRows.has(key))
          .map(key => {
            const low = lowRows.get(key);
            const high = highRows.get(key);
            return {
              region: key,
              region_en: high.region_en || low.region_en || "",
              region_order: Number(high.region_order || low.region_order || 99),
              province_n: Number(high.province_n || low.province_n || 0),
              low_temp_delta: Number(low.temp_delta_mean) || 0,
              high_temp_delta: Number(high.temp_delta_mean) || 0,
              temp_delta_gap: (Number(high.temp_delta_mean) || 0) - (Number(low.temp_delta_mean) || 0),
              low_temp_contribution: Number(low.temp_contribution_mean) || 0,
              high_temp_contribution: Number(high.temp_contribution_mean) || 0,
              temp_contribution_gap: (Number(high.temp_contribution_mean) || 0) - (Number(low.temp_contribution_mean) || 0),
              low_total_delta: Number(low.total_delta_mean) || 0,
              high_total_delta: Number(high.total_delta_mean) || 0,
              total_delta_gap: (Number(high.total_delta_mean) || 0) - (Number(low.total_delta_mean) || 0),
            };
          })
          .sort((a, b) => Number(b.temp_contribution_gap) - Number(a.temp_contribution_gap));
      }

      function createLegend(items) {
        return `
          <div class="legend">
            ${items.map(item => `
              <span class="legend-item">
                <span class="legend-swatch" style="background:${item.color}"></span>
                ${item.label}
              </span>
            `).join("")}
          </div>
        `;
      }

      function renderFigureImage(targetId, path, alt) {
        const host = document.getElementById(targetId);
        if (!host) return;
        if (!path) {
          host.innerHTML = `<div class="chart-wrap"><div class="empty-state">暂无图件。</div></div>`;
          return;
        }
        host.innerHTML = `
          <a class="figure-link" href="${path}" target="_blank" rel="noopener">
            <img class="figure-image" src="${path}" alt="${alt}" loading="lazy" />
          </a>
        `;
      }

      function standardFigurePath(key) {
        return (((FIGURE_MAP.standard_results || {})[state.mode] || {})[state.role] || {})[key] || "";
      }

      function barListHtml(rows, options = {}) {
        if (!rows.length) {
          return `<div class="empty-state">暂无可展示的条带结果。</div>`;
        }
        const valueOf = options.value || (row => row.value);
        const labelOf = options.label || (row => row.label);
        const subOf = options.sub || (() => "");
        const valueTextOf = options.valueText || (row => fmtSigned(valueOf(row), 3));
        const colorOf = options.color || ((row, value) => {
          if (!Number.isFinite(value) || Math.abs(value) < 1e-12) return "rgba(160, 156, 148, 0.45)";
          return value > 0
            ? "linear-gradient(90deg, rgba(194,108,50,0.88), rgba(217,147,82,0.78))"
            : "linear-gradient(90deg, rgba(76,120,168,0.90), rgba(123,159,195,0.80))";
        });

        const values = rows.map(row => Number(valueOf(row))).filter(Number.isFinite);
        const maxAbs = Math.max(...values.map(value => Math.abs(value)), 0.001);
        const hasPos = values.some(value => value > 0);
        const hasNeg = values.some(value => value < 0);
        const bipolar = hasPos && hasNeg;
        const axisLeft = bipolar ? 50 : hasNeg ? 100 : 0;

        return `
          <div class="bar-list">
            ${rows.map(row => {
              const value = Number(valueOf(row));
              const width = Math.max((Math.abs(value) / maxAbs) * (bipolar ? 50 : 100), Math.abs(value) < 1e-12 ? 0 : 2);
              const left = bipolar ? (value >= 0 ? 50 : 50 - width) : (hasNeg ? 100 - width : 0);
              return `
                <div class="bar-row">
                  <div class="bar-label">
                    <strong>${labelOf(row)}</strong>
                    <span class="bar-sub">${subOf(row) || ""}</span>
                  </div>
                  <div class="bar-track">
                    <span class="bar-axis" style="left:${axisLeft}%"></span>
                    <span class="bar-fill" style="left:${left}%;width:${width}%;background:${colorOf(row, value)}"></span>
                  </div>
                  <div class="bar-value">${valueTextOf(row)}</div>
                </div>
              `;
            }).join("")}
          </div>
        `;
      }

      function renderLineChart(targetId, series, subtitle) {
        const host = document.getElementById(targetId);
        const allPoints = series.flatMap(item => item.points || []);
        if (!host) return;
        if (!allPoints.length) {
          host.innerHTML = `<div class="chart-wrap"><div class="empty-state">没有可用数据。</div></div>`;
          return;
        }

        const width = 980;
        const height = 300;
        const pad = { left: 56, right: 18, top: 20, bottom: 40 };
        const years = Array.from(new Set(allPoints.map(item => Number(item.year)))).sort((a, b) => a - b);
        const values = allPoints.map(item => Number(item.value)).filter(Number.isFinite);
        let minY = Math.min(...values);
        let maxY = Math.max(...values);
        if (Math.abs(maxY - minY) < 1e-9) {
          minY -= 1;
          maxY += 1;
        }
        const yPad = (maxY - minY) * 0.12;
        minY -= yPad;
        maxY += yPad;

        const x = year => {
          if (years.length === 1) return pad.left + (width - pad.left - pad.right) / 2;
          const ratio = (Number(year) - years[0]) / (years[years.length - 1] - years[0]);
          return pad.left + ratio * (width - pad.left - pad.right);
        };
        const y = value => {
          const ratio = (Number(value) - minY) / (maxY - minY);
          return height - pad.bottom - ratio * (height - pad.top - pad.bottom);
        };

        const yTicks = Array.from({ length: 5 }, (_, index) => minY + ((maxY - minY) * index) / 4);
        const xTicks = years.filter((year, index) => index === 0 || index === years.length - 1 || year % 5 === 0);
        const grid = yTicks.map(value => `
          <g>
            <line x1="${pad.left}" x2="${width - pad.right}" y1="${y(value)}" y2="${y(value)}" stroke="rgba(148,163,184,0.16)" stroke-dasharray="4 6" />
            <text x="${pad.left - 10}" y="${y(value) + 4}" fill="rgba(229,238,251,0.54)" font-size="11" text-anchor="end">${fmt(value, 2)}</text>
          </g>
        `).join("");
        const ticks = xTicks.map(year => `
          <g>
            <line x1="${x(year)}" x2="${x(year)}" y1="${height - pad.bottom}" y2="${height - pad.bottom + 6}" stroke="rgba(148,163,184,0.28)" />
            <text x="${x(year)}" y="${height - 12}" fill="rgba(229,238,251,0.58)" font-size="11" text-anchor="middle">${year}</text>
          </g>
        `).join("");
        const lines = series.map(item => {
          const points = (item.points || []).filter(point => Number.isFinite(Number(point.value)));
          if (!points.length) return "";
          const polyline = points.map(point => `${x(point.year)},${y(point.value)}`).join(" ");
          const last = points[points.length - 1];
          return `
            <g>
              <polyline fill="none" stroke="${item.color}" stroke-width="${item.dash ? 2.3 : 3.1}" stroke-linecap="round" stroke-linejoin="round" points="${polyline}" ${item.dash ? `stroke-dasharray="${item.dash}"` : ""} />
              <circle cx="${x(last.year)}" cy="${y(last.value)}" r="4" fill="${item.color}" />
            </g>
          `;
        }).join("");

        host.innerHTML = `
          <div class="chart-wrap">
            <div class="subtle">${subtitle}</div>
            <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}">
              ${grid}
              <line x1="${pad.left}" x2="${width - pad.right}" y1="${height - pad.bottom}" y2="${height - pad.bottom}" stroke="rgba(148,163,184,0.32)" />
              <line x1="${pad.left}" x2="${pad.left}" y1="${pad.top}" y2="${height - pad.bottom}" stroke="rgba(148,163,184,0.32)" />
              ${ticks}
              ${lines}
            </svg>
            ${createLegend(series.map(item => ({ label: item.label, color: item.color })))}
          </div>
        `;
      }

      function provinceTableHtml(rows, columns) {
        if (!rows.length) {
          return `<div class="empty-state">当前筛选下没有省级结果。</div>`;
        }
        return `
          <table>
            <thead>
              <tr>${columns.map(col => `<th>${col.label}</th>`).join("")}</tr>
            </thead>
            <tbody>
              ${rows.map(row => `
                <tr>
                  ${columns.map(col => `<td class="${col.className ? col.className(row[col.key]) : ""}">${col.render ? col.render(row[col.key], row) : row[col.key]}</td>`).join("")}
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
      }

      function renderHero() {
        document.getElementById("generatedAt").textContent = `Generated at ${DATA.generated_at}`;
        const summary = DATA.summary;
        document.getElementById("heroMetrics").innerHTML = [
          {
            key: "Input Window",
            value: `${summary.history_start}-${summary.end_year}`,
            hint: `历史 ${summary.history_start}-${summary.history_end}，未来 ${summary.start_year}-${summary.end_year}。`,
          },
          {
            key: "Temperature Roles",
            value: summary.role_count,
            hint: `${summary.ta_role_count} 个 TA 模型，${summary.province_tas_role_count} 个省平均气温模型。`,
          },
          {
            key: "Scenarios",
            value: `${summary.scenario_count} × 3`,
            hint: "5 个 SSP，每个都保留 median / p10 / p90。",
          },
          {
            key: "Bias Mean",
            value: fmtSigned(summary.bias_mean, 3),
            hint: "省平均气温 alignment 的整体均值偏差。",
          },
        ].map(item => `
          <article class="metric">
            <div class="k">${item.key}</div>
            <div class="v">${item.value}</div>
            <div class="h">${item.hint}</div>
          </article>
        `).join("");
      }

      function renderInputCharts() {
        const displayNote = state.inputDisplay === "anchored"
          ? "当前展示的是 2023 锚定版本：先把图预绘制到本地 PNG，再在页面里引用；锚定只用于显示衔接，不改投影输入。"
          : "当前展示的是原始 SSP / aligned 序列：图先预绘制到本地 PNG，再在页面里引用；2023-2024 可能出现可见断点。";
        const noteEl = document.getElementById("inputDisplayNote");
        if (noteEl) noteEl.textContent = displayNote;
        renderFigureImage(
          "taInputChart",
          (((FIGURE_MAP.input || {}).ta || {})[state.inputDisplay]) || "",
          `TA national mean trajectory (${state.inputDisplay})`
        );
        renderFigureImage(
          "provinceInputChart",
          (((FIGURE_MAP.input || {}).province_tas || {})[state.inputDisplay]) || "",
          `Province mean temperature trajectory (${state.inputDisplay})`
        );
      }

      function renderInputSummary() {
        document.getElementById("inputSummary").innerHTML = DATA.input_metrics.map(metric => `
          <article class="card">
            <div class="mini-label">${metric.label}</div>
            <div class="table-caption">${metric.note}</div>
            <table>
              <thead>
                <tr><th>Scenario</th><th>Median</th><th>p10</th><th>p90</th></tr>
              </thead>
              <tbody>
                ${metric.summary2050.map(row => `
                  <tr>
                    <td><strong>${scenarioLabel(row.scenario_id)}</strong></td>
                    <td>${fmt(row.median, 2)} ${metric.unit}</td>
                    <td>${fmt(row.p10, 2)} ${metric.unit}</td>
                    <td>${fmt(row.p90, 2)} ${metric.unit}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </article>
        `).join("");
      }

      function renderBiasSummary() {
        const summary = DATA.summary;
        document.getElementById("biasCards").innerHTML = [
          { key: "Mean", value: fmtSigned(summary.bias_mean, 3) + " °C" },
          { key: "Min", value: fmtSigned(summary.bias_min, 3) + " °C" },
          { key: "Max", value: fmtSigned(summary.bias_max, 3) + " °C" },
        ].map(item => `
          <article class="card">
            <div class="mini-label">${item.key}</div>
            <div class="value-md">${item.value}</div>
          </article>
        `).join("");
        document.getElementById("biasTable").innerHTML = `
          <table>
            <thead>
              <tr><th>Scenario</th><th>Statistic</th><th>Mean bias</th><th>Min</th><th>Max</th></tr>
            </thead>
            <tbody>
              ${DATA.bias_summary.map(row => `
                <tr>
                  <td><strong>${scenarioLabel(row.scenario_id)}</strong></td>
                  <td>${row.statistic}</td>
                  <td>${fmtSigned(row.mean_bias, 3)}</td>
                  <td>${fmtSigned(row.min_bias, 3)}</td>
                  <td>${fmtSigned(row.max_bias, 3)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
      }

      function initControls() {
        document.getElementById("modeSelect").innerHTML = DATA.mode_meta.map(item => `<option value="${item.id}">${item.label}</option>`).join("");
        document.getElementById("roleSelect").innerHTML = DATA.role_order.map(roleId => `<option value="${roleId}">${ROLE_MAP[roleId].label} · ${ROLE_MAP[roleId].temp_proxy}</option>`).join("");
        document.getElementById("scenarioSelect").innerHTML = DATA.scenario_meta.map(item => `<option value="${item.id}">${item.label}</option>`).join("");
        const inputDisplaySelect = document.getElementById("inputDisplaySelect");
        if (inputDisplaySelect) {
          inputDisplaySelect.innerHTML = [
            { value: "raw", label: "Raw SSP" },
            { value: "anchored", label: "2023 Anchored" },
          ].map(item => `<option value="${item.value}">${item.label}</option>`).join("");
          inputDisplaySelect.value = state.inputDisplay;
        }
        document.getElementById("modeSelect").value = state.mode;
        document.getElementById("roleSelect").value = state.role;
        document.getElementById("scenarioSelect").value = state.scenario;
        document.getElementById("modeSelect").addEventListener("change", event => { state.mode = event.target.value; updateRoleSection(); });
        document.getElementById("roleSelect").addEventListener("change", event => { state.role = event.target.value; updateRoleSection(); });
        document.getElementById("scenarioSelect").addEventListener("change", event => { state.scenario = event.target.value; updateRoleSection(); });
        if (inputDisplaySelect) {
          inputDisplaySelect.addEventListener("change", event => {
            state.inputDisplay = event.target.value;
            renderInputCharts();
          });
        }
      }

      function renderBaselineLogic() {
        const role = ROLE_MAP[state.role];
        const currentBaseline = baselineRow(state.mode, state.role);
        const otherBaseline = baselineRow(otherMode(state.mode), state.role);
        const currentScenario = roleEndRow(state.mode, state.role, state.scenario, "median");
        const otherScenario = roleEndRow(otherMode(state.mode), state.role, state.scenario, "median");
        const baselineGap = Number(currentBaseline?.baseline_pred_mean || 0) - Number(otherBaseline?.baseline_pred_mean || 0);
        const scenarioGap = Number(currentScenario?.scenario_pred_mean || 0) - Number(otherScenario?.scenario_pred_mean || 0);
        const tempContributionGap = Number(currentScenario?.temp_contribution_mean || 0) - Number(otherScenario?.temp_contribution_mean || 0);

        document.getElementById("baselineCompareCards").innerHTML = [
          {
            key: `${MODE_MAP[state.mode].label} 2050 baseline`,
            value: fmt(Number(currentBaseline?.baseline_pred_mean), 2),
            hint: "当前 baseline mode 下的全国 AMR baseline。",
          },
          {
            key: `${MODE_MAP[otherMode(state.mode)].label} 2050 baseline`,
            value: fmt(Number(otherBaseline?.baseline_pred_mean), 2),
            hint: "相同 temperature role 在另一种 baseline 口径下的全国 baseline。",
          },
          {
            key: "Baseline gap",
            value: fmtSigned(baselineGap, 2),
            hint: "同一 role 下两种 baseline 的 absolute level 差。",
          },
          {
            key: "Temp-only gap across modes",
            value: fmtSigned(tempContributionGap, 3),
            hint: `同一 ${scenarioLabel(state.scenario)} 下，温度通道单独贡献在两种 mode 之间的差。`,
          },
        ].map(item => `
          <article class="card">
            <div class="mini-label">${item.key}</div>
            <div class="value-md">${item.value}</div>
            <div class="subtle">${item.hint}</div>
          </article>
        `).join("");

        document.getElementById("baselineNarrative").innerHTML = `
          <strong>怎么理解 temperature 页里的 baseline logic？</strong>
          <p>
            当前选中的 <strong>${role.label}</strong> 到 ${DATA.summary.end_year} 年在 <strong>${MODE_MAP[state.mode].label}</strong> 下的全国 AMR baseline
            约为 <strong>${fmt(Number(currentBaseline?.baseline_pred_mean), 2)}</strong>，而在
            <strong>${MODE_MAP[otherMode(state.mode)].label}</strong> 下约为
            <strong>${fmt(Number(otherBaseline?.baseline_pred_mean), 2)}</strong>，两者相差
            <strong>${fmtSigned(baselineGap, 2)}</strong>。
          </p>
          <p>
            但温度情景本身走的是同一条 SSP 温度路径，所以到 <strong>${scenarioLabel(state.scenario)}</strong>、
            <strong>${DATA.summary.end_year}</strong> 年，温度通道单独贡献在两种 baseline mode 之间的差只有
            <strong>${fmtSigned(tempContributionGap, 3)}</strong>，几乎不变。也就是说，这里的 baseline 选择主要决定
            <strong>AMR 的 baseline 水平</strong>，而不是温度情景增量本身；两种 mode 的 scenario 预测值差
            <strong>${fmtSigned(scenarioGap, 2)}</strong>，更多是在平移 absolute level。
          </p>
        `;
      }

      function renderNationalResults() {
        const role = ROLE_MAP[state.role];
        const currentBaseline = baselineRow(state.mode, state.role);
        const currentScenario = roleEndRow(state.mode, state.role, state.scenario, "median");
        const rows = scenarioRows2050(state.mode, state.role);
        const lowScenario = rows.find(item => item.meta.id === DATA.compare_pair.low);
        const highScenario = rows.find(item => item.meta.id === DATA.compare_pair.high);
        const spread = (Number(highScenario?.row?.temp_contribution_mean) || 0) - (Number(lowScenario?.row?.temp_contribution_mean) || 0);
        const share = sharePercent(currentScenario?.temp_contribution_mean, currentScenario?.total_delta_mean);
        const hottest = rows.slice().sort((a, b) => Number(b.row.temp_contribution_mean) - Number(a.row.temp_contribution_mean))[0];

        document.getElementById("nationalCards").innerHTML = [
          {
            key: "2050 baseline AMR",
            value: fmt(Number(currentBaseline?.baseline_pred_mean), 2),
            hint: `${MODE_MAP[state.mode].label} 下的全国 baseline。`,
          },
          {
            key: `${scenarioLabel(state.scenario)} 2050`,
            value: fmt(Number(currentScenario?.scenario_pred_mean), 2),
            hint: `全国 scenario prediction；相对 baseline ${fmtSigned(Number(currentScenario?.total_delta_mean), 3)}。`,
          },
          {
            key: "Temp-only contribution",
            value: fmtSigned(Number(currentScenario?.temp_contribution_mean), 3),
            hint: `来自 ${role.temp_proxy} 的温度通道单独贡献。`,
          },
          {
            key: `${scenarioLabel(DATA.compare_pair.high)} - ${scenarioLabel(DATA.compare_pair.low)}`,
            value: fmtSigned(spread, 3),
            hint: "2050 情景分叉带来的温度通道增量差。",
          },
        ].map(item => `
          <article class="card">
            <div class="mini-label">${item.key}</div>
            <div class="value-md">${item.value}</div>
            <div class="subtle">${item.hint}</div>
          </article>
        `).join("");

        renderFigureImage(
          "nationalDeltaBars",
          (((FIGURE_MAP.national_delta || {})[state.mode] || {})[state.role]) || "",
          `${role.label} ${MODE_MAP[state.mode].label} 2050 scenario deltas`
        );

        document.getElementById("nationalRead").innerHTML = `
          <strong>全国结果怎么读？</strong>
          <p>
            先看当前 mode 下的全国 baseline，再看选中情景在 ${DATA.summary.end_year} 年把温度通道额外推高或压低了多少。
            现在在 <strong>${MODE_MAP[state.mode].label}</strong> + <strong>${role.label}</strong> + <strong>${scenarioLabel(state.scenario)}</strong> 下，
            全国平均温度从 baseline 的 <strong>${fmt(Number(currentScenario?.temp_baseline_mean), 3)} ${metricUnit(role.temp_metric_id)}</strong>
            走到 scenario 的 <strong>${fmt(Number(currentScenario?.temp_scenario_mean), 3)} ${metricUnit(role.temp_metric_id)}</strong>，
            对应 <strong>Δtemp = ${fmtSigned(Number(currentScenario?.temp_delta_mean), 3)} ${metricUnit(role.temp_metric_id)}</strong>。
          </p>
          <p>
            这部分温度变化折算成的温度通道单独贡献约为 <strong>${fmtSigned(Number(currentScenario?.temp_contribution_mean), 3)}</strong>，
            在总 ΔAMR 中的近似占比是 <strong>${share === null ? "NA" : fmtSigned(share, 1) + "%"}</strong>。
            当前 role 下温度通道增量最高的情景是 <strong>${hottest ? hottest.meta.label : "—"}</strong>。
          </p>
        `;
      }

      function renderSpatialOverview() {
        const role = ROLE_MAP[state.role];
        const regionRank = regionRows().slice().sort((a, b) => Number(b.temp_contribution_mean) - Number(a.temp_contribution_mean));
        const provinceRank = provinceRows(state.mode, state.role, state.scenario).slice().sort((a, b) => Number(b.temp_contribution) - Number(a.temp_contribution));
        const provinceFocus = [...provinceRank.slice(0, 8), ...provinceRank.slice(-4)]
          .filter((row, index, array) => array.findIndex(item => item.Province === row.Province) === index)
          .sort((a, b) => Number(b.temp_contribution) - Number(a.temp_contribution));
        const warmest = provinceRank.slice().sort((a, b) => Number(b.temp_delta) - Number(a.temp_delta))[0];
        const coolest = provinceRank.slice().sort((a, b) => Number(a.temp_delta) - Number(b.temp_delta))[0];

        renderFigureImage(
          "spatialRegionBars",
          ((((FIGURE_MAP.spatial_region || {})[state.mode] || {})[state.role] || {})[state.scenario]) || "",
          `${role.label} ${MODE_MAP[state.mode].label} ${scenarioLabel(state.scenario)} regional pattern`
        );

        renderFigureImage(
          "spatialProvinceBars",
          ((((FIGURE_MAP.spatial_province || {})[state.mode] || {})[state.role] || {})[state.scenario]) || "",
          `${role.label} ${MODE_MAP[state.mode].label} ${scenarioLabel(state.scenario)} provincial pattern`
        );

        document.getElementById("spatialNarrative").innerHTML = `
          <strong>地区与省级空间格局怎么读？</strong>
          <p>
            这里把地图问题压缩成条带排序。地区层面看的是七大区在 <strong>${scenarioLabel(state.scenario)}</strong>、
            <strong>${DATA.summary.end_year}</strong> 年的温度通道均值贡献；省级层面保留具体省份，用来判断全国均值到底是被哪些地方推着走。
          </p>
          <p>
            当前最强的地区是 <strong>${regionRank[0]?.region || "—"}</strong>，最强省份是
            <strong>${provinceRank[0]?.Province || "—"}</strong>；升温幅度最高的是
            <strong>${warmest?.Province || "—"}</strong>（${fmtSigned(Number(warmest?.temp_delta), 3)} ${metricUnit(role.temp_metric_id)}），
            最低的是 <strong>${coolest?.Province || "—"}</strong>（${fmtSigned(Number(coolest?.temp_delta), 3)} ${metricUnit(role.temp_metric_id)}）。
          </p>
        `;
      }

      function renderRegionalAnalysis() {
        const role = ROLE_MAP[state.role];
        const rows = regionRows().slice().sort((a, b) => Number(b.temp_contribution_mean) - Number(a.temp_contribution_mean));
        const gapRows = regionGapRows(state.mode, state.role);
        document.getElementById("regionalTable").innerHTML = `
          <table>
            <thead>
              <tr>
                <th>Region</th>
                <th>Province n</th>
                <th>Baseline temp</th>
                <th>Scenario temp</th>
                <th>Δtemp</th>
                <th>Temp-only ΔAMR</th>
                <th>Total ΔAMR</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(row => `
                <tr>
                  <td><strong>${row.region}</strong><br /><span class="subtle">${row.region_en || ""}</span></td>
                  <td>${row.province_n}</td>
                  <td>${fmt(Number(row.temp_baseline_mean), 3)} ${metricUnit(role.temp_metric_id)}</td>
                  <td>${fmt(Number(row.temp_scenario_mean), 3)} ${metricUnit(role.temp_metric_id)}</td>
                  <td class="${deltaClass(row.temp_delta_mean)}">${fmtSigned(Number(row.temp_delta_mean), 3)}</td>
                  <td class="${deltaClass(row.temp_contribution_mean)}">${fmtSigned(Number(row.temp_contribution_mean), 3)}</td>
                  <td class="${deltaClass(row.total_delta_mean)}">${fmtSigned(Number(row.total_delta_mean), 3)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
        document.getElementById("regionalRead").innerHTML = `
          <strong>分地区分析</strong>
          <p>
            七大区结果最适合回答“全国平均是被哪个地带推着走”。当前筛选下，
            <strong>${rows[0]?.region || "—"}</strong> 的温度通道贡献最高，为
            <strong>${fmtSigned(Number(rows[0]?.temp_contribution_mean), 3)}</strong>；最低的是
            <strong>${rows[rows.length - 1]?.region || "—"}</strong>，为
            <strong>${fmtSigned(Number(rows[rows.length - 1]?.temp_contribution_mean), 3)}</strong>。
          </p>
          <p>
            如果换成看双情景差值，敏感度最高的地区是 <strong>${gapRows[0]?.region || "—"}</strong>，
            到 ${DATA.summary.end_year} 年 <strong>${scenarioLabel(DATA.compare_pair.high)}</strong> 相比
            <strong>${scenarioLabel(DATA.compare_pair.low)}</strong> 的温度通道差值约为
            <strong>${fmtSigned(Number(gapRows[0]?.temp_contribution_gap), 3)}</strong>。
          </p>
        `;
        renderFigureImage(
          "regionalFigureGrid",
          standardFigurePath("regional_grid"),
          `${role.label} ${MODE_MAP[state.mode].label} regional trajectory grid`
        );
        renderFigureImage(
          "regionalHeatmapFigure",
          standardFigurePath("regional_heatmap"),
          `${role.label} ${MODE_MAP[state.mode].label} regional 2050 heatmap`
        );
      }

      function renderDualCompare() {
        const role = ROLE_MAP[state.role];
        const regionGaps = regionGapRows(state.mode, state.role);
        const provinceGaps = provinceGapRows(state.mode, state.role);
        const topProvinceGaps = provinceGaps.slice(0, 12);

        renderFigureImage(
          "compareRegionBars",
          (((FIGURE_MAP.compare_region || {})[state.mode] || {})[state.role]) || "",
          `${role.label} ${MODE_MAP[state.mode].label} regional scenario-gap`
        );

        renderFigureImage(
          "compareProvinceBars",
          (((FIGURE_MAP.compare_province || {})[state.mode] || {})[state.role]) || "",
          `${role.label} ${MODE_MAP[state.mode].label} provincial scenario-gap`
        );

        document.getElementById("compareRegionTable").innerHTML = `
          <table>
            <thead>
              <tr>
                <th>Region</th>
                <th>${scenarioLabel(DATA.compare_pair.low)}</th>
                <th>${scenarioLabel(DATA.compare_pair.high)}</th>
                <th>Δtemp gap</th>
                <th>Temp-only gap</th>
                <th>Total ΔAMR gap</th>
              </tr>
            </thead>
            <tbody>
              ${regionGaps.map(row => `
                <tr>
                  <td><strong>${row.region}</strong><br /><span class="subtle">${row.region_en || ""}</span></td>
                  <td>${fmtSigned(Number(row.low_temp_contribution), 3)}</td>
                  <td>${fmtSigned(Number(row.high_temp_contribution), 3)}</td>
                  <td class="${deltaClass(row.temp_delta_gap)}">${fmtSigned(Number(row.temp_delta_gap), 3)}</td>
                  <td class="${deltaClass(row.temp_contribution_gap)}">${fmtSigned(Number(row.temp_contribution_gap), 3)}</td>
                  <td class="${deltaClass(row.total_delta_gap)}">${fmtSigned(Number(row.total_delta_gap), 3)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;

        document.getElementById("compareProvinceTable").innerHTML = `
          <table>
            <thead>
              <tr>
                <th>Province</th>
                <th>${scenarioLabel(DATA.compare_pair.low)}</th>
                <th>${scenarioLabel(DATA.compare_pair.high)}</th>
                <th>Δtemp gap</th>
                <th>Temp-only gap</th>
                <th>Total ΔAMR gap</th>
              </tr>
            </thead>
            <tbody>
              ${topProvinceGaps.map(row => `
                <tr>
                  <td><strong>${row.Province}</strong><br /><span class="subtle">${row.region}</span></td>
                  <td>${fmtSigned(Number(row.low_temp_contribution), 3)}</td>
                  <td>${fmtSigned(Number(row.high_temp_contribution), 3)}</td>
                  <td class="${deltaClass(row.temp_delta_gap)}">${fmtSigned(Number(row.temp_delta_gap), 3)} ${metricUnit(role.temp_metric_id)}</td>
                  <td class="${deltaClass(row.temp_contribution_gap)}">${fmtSigned(Number(row.temp_contribution_gap), 3)}</td>
                  <td class="${deltaClass(row.total_delta_gap)}">${fmtSigned(Number(row.total_delta_gap), 3)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
        renderFigureImage(
          "dualScenarioPredictedFigure",
          standardFigurePath("dual_predicted"),
          `${role.label} ${MODE_MAP[state.mode].label} dual-scenario predicted figure`
        );
        renderFigureImage(
          "dualScenarioDeltaFigure",
          standardFigurePath("dual_delta"),
          `${role.label} ${MODE_MAP[state.mode].label} dual-scenario delta figure`
        );
      }

      function renderRoleCards() {
        const role = ROLE_MAP[state.role];
        const row = roleEndRow(state.mode, state.role, state.scenario, "median");
        const p10 = roleEndRow(state.mode, state.role, state.scenario, "p10");
        const p90 = roleEndRow(state.mode, state.role, state.scenario, "p90");
        const share = row && Number(row.total_delta_mean) !== 0
          ? Number(row.temp_contribution_mean) / Number(row.total_delta_mean)
          : null;

        document.getElementById("modeNote").textContent = MODE_MAP[state.mode].note;
        document.getElementById("roleCards").innerHTML = [
          {
            key: "Temperature Proxy",
            value: role.temp_proxy,
            hint: `${role.scheme_id} · ${role.fe_label}`,
          },
          {
            key: "β_temp",
            value: fmtSigned(role.temp_coef, 3),
            hint: "每 1 std 温度变化对应的历史系数。",
          },
          {
            key: "std_temp",
            value: fmt(role.temp_std, 3),
            hint: `历史 ${role.temp_proxy} 标准差。`,
          },
          {
            key: `${scenarioLabel(state.scenario)} 2050`,
            value: row ? `${fmtSigned(row.temp_delta_mean, 3)} ${metricUnit(role.temp_metric_id)}` : "NA",
            hint: row
              ? `温度单独贡献 ${fmtSigned(row.temp_contribution_mean, 3)}；区间 ${p10 ? fmtSigned(p10.temp_contribution_mean, 3) : "NA"} 到 ${p90 ? fmtSigned(p90.temp_contribution_mean, 3) : "NA"}。`
              : "没有找到当前选择的 2050 温度行。",
          },
          {
            key: "Temp Share in Total Δ",
            value: share === null ? "NA" : `${fmtSigned(share * 100, 1)}%`,
            hint: "当前 mode + role + scenario 下，温度通道在 total ΔAMR 里的近似占比。",
          },
        ].map(item => `
          <article class="card">
            <div class="mini-label">${item.key}</div>
            <div class="value-md">${item.value}</div>
            <div class="subtle">${item.hint}</div>
          </article>
        `).join("");
      }

      function renderRoleComparisonTable() {
        const rows = DATA.role_order.map(roleId => {
          const role = ROLE_MAP[roleId];
          const row = roleEndRow(state.mode, roleId, state.scenario, "median");
          return { role, row };
        }).filter(item => item.row);
        rows.sort((a, b) => Number(b.row.temp_contribution_mean) - Number(a.row.temp_contribution_mean));
        document.getElementById("roleComparisonTable").innerHTML = `
          <table>
            <thead>
              <tr>
                <th>Role</th>
                <th>Temp proxy</th>
                <th>β_temp</th>
                <th>std_temp</th>
                <th>2050 Δtemp</th>
                <th>2050 temp-only ΔAMR</th>
                <th>2050 total ΔAMR</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(item => `
                <tr>
                  <td><strong>${item.role.label}</strong><br /><span class="subtle">${item.role.scheme_id}</span></td>
                  <td>${item.role.temp_proxy}</td>
                  <td>${fmtSigned(item.role.temp_coef, 3)}</td>
                  <td>${fmt(item.role.temp_std, 3)}</td>
                  <td class="${deltaClass(item.row.temp_delta_mean)}">${fmtSigned(item.row.temp_delta_mean, 3)} ${metricUnit(item.role.temp_metric_id)}</td>
                  <td class="${deltaClass(item.row.temp_contribution_mean)}">${fmtSigned(item.row.temp_contribution_mean, 3)}</td>
                  <td class="${deltaClass(item.row.total_delta_mean)}">${fmtSigned(item.row.total_delta_mean, 3)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
      }

      function renderContributionChart() {
        const role = ROLE_MAP[state.role];
        renderFigureImage(
          "contributionChart",
          (((FIGURE_MAP.contribution || {})[state.mode] || {})[state.role]) || "",
          `${role.label} ${MODE_MAP[state.mode].label} contribution trajectory`
        );
      }

      function renderScenarioBreakdownTable() {
        const role = ROLE_MAP[state.role];
        const rows = DATA.scenario_meta.map(item => {
          const median = roleEndRow(state.mode, state.role, item.id, "median");
          const p10 = roleEndRow(state.mode, state.role, item.id, "p10");
          const p90 = roleEndRow(state.mode, state.role, item.id, "p90");
          return { item, median, p10, p90 };
        }).filter(item => item.median);
        document.getElementById("scenarioBreakdownTable").innerHTML = `
          <table>
            <thead>
              <tr>
                <th>Scenario</th>
                <th>2050 baseline temp</th>
                <th>2050 scenario temp</th>
                <th>2050 Δtemp</th>
                <th>Temp-only ΔAMR</th>
                <th>Temp uncertainty</th>
                <th>Total ΔAMR</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map(({ item, median, p10, p90 }) => `
                <tr>
                  <td><strong>${item.label}</strong></td>
                  <td>${fmt(median.temp_baseline_mean, 3)} ${metricUnit(role.temp_metric_id)}</td>
                  <td>${fmt(median.temp_scenario_mean, 3)} ${metricUnit(role.temp_metric_id)}</td>
                  <td class="${deltaClass(median.temp_delta_mean)}">${fmtSigned(median.temp_delta_mean, 3)}</td>
                  <td class="${deltaClass(median.temp_contribution_mean)}">${fmtSigned(median.temp_contribution_mean, 3)}</td>
                  <td>${p10 && p90 ? `${fmtSigned(p10.temp_contribution_mean, 3)} to ${fmtSigned(p90.temp_contribution_mean, 3)}` : "NA"}</td>
                  <td class="${deltaClass(median.total_delta_mean)}">${fmtSigned(median.total_delta_mean, 3)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
      }

      function renderProvinceTables() {
        const role = ROLE_MAP[state.role];
        const rows = [...provinceRows(state.mode, state.role, state.scenario)];
        const byWarm = [...rows].sort((a, b) => Number(b.temp_delta) - Number(a.temp_delta));
        const byCool = [...rows].sort((a, b) => Number(a.temp_delta) - Number(b.temp_delta));
        const byPositive = [...rows].sort((a, b) => Number(b.temp_contribution) - Number(a.temp_contribution));
        const byNegative = [...rows].sort((a, b) => Number(a.temp_contribution) - Number(b.temp_contribution));
        const share = sharePercent(byPositive[0]?.temp_contribution, byPositive[0]?.total_delta);
        const tempColumns = [
          { label: "Province", key: "Province", render: (value, row) => `<strong>${value}</strong><br /><span class="subtle">${row.region}</span>` },
          { label: "Baseline", key: "temp_baseline", render: value => `${fmt(value, 3)} ${metricUnit(role.temp_metric_id)}` },
          { label: "Scenario", key: "temp_scenario", render: value => `${fmt(value, 3)} ${metricUnit(role.temp_metric_id)}` },
          { label: "Δtemp", key: "temp_delta", render: value => fmtSigned(value, 3), className: value => deltaClass(value) },
        ];
        const contributionColumns = [
          { label: "Province", key: "Province", render: (value, row) => `<strong>${value}</strong><br /><span class="subtle">${row.region}</span>` },
          { label: "Δtemp", key: "temp_delta", render: value => fmtSigned(value, 3), className: value => deltaClass(value) },
          { label: "Temp-only ΔAMR", key: "temp_contribution", render: value => fmtSigned(value, 3), className: value => deltaClass(value) },
          { label: "Total ΔAMR", key: "total_delta", render: value => fmtSigned(value, 3), className: value => deltaClass(value) },
        ];
        document.getElementById("warmingTable").innerHTML = provinceTableHtml(byWarm.slice(0, 8), tempColumns);
        document.getElementById("coolingTable").innerHTML = provinceTableHtml(byCool.slice(0, 8), tempColumns);
        document.getElementById("positiveContributionTable").innerHTML = provinceTableHtml(byPositive.slice(0, 8), contributionColumns);
        document.getElementById("negativeContributionTable").innerHTML = provinceTableHtml(byNegative.slice(0, 8), contributionColumns);
        document.getElementById("provinceNarrative").innerHTML = `
          <strong>省级尺度分析</strong>
          <p>
            省级层面最适合看两个问题：谁对当前情景最敏感，谁在温度通道里占总结果的比重最高。
            当前 <strong>${scenarioLabel(state.scenario)}</strong> 下，温度通道贡献最高的省份是
            <strong>${byPositive[0]?.Province || "—"}</strong>（${fmtSigned(Number(byPositive[0]?.temp_contribution), 3)}），
            最低的是 <strong>${byNegative[0]?.Province || "—"}</strong>（${fmtSigned(Number(byNegative[0]?.temp_contribution), 3)}）。
          </p>
          <p>
            如果只盯总 ΔAMR，很容易看不出到底是温度路径还是其他协变量在起作用。这里把省级的
            <strong>Δtemp</strong>、<strong>temp-only ΔAMR</strong> 和 <strong>total ΔAMR</strong> 放在同一行，
            方便直接判断温度通道的解释力。当前贡献最高省份里，温度通道占总 ΔAMR 的近似比重约为
            <strong>${share === null ? "NA" : fmtSigned(share, 1) + "%"}</strong>。
          </p>
        `;
        renderFigureImage(
          "provincialPanelFigure",
          standardFigurePath("provincial_panel"),
          `${role.label} ${MODE_MAP[state.mode].label} provincial future scenario panel`
        );
      }

      function renderFiles() {
        document.getElementById("fileGrid").innerHTML = DATA.files.map(item => `
          <a class="file-link" href="${item.path}">
            <strong>${item.label}</strong>
            <span>${item.note}</span>
            <span>${item.path}</span>
          </a>
        `).join("");
      }

      function updateRoleSection() {
        renderBaselineLogic();
        renderNationalResults();
        renderRoleCards();
        renderRoleComparisonTable();
        renderContributionChart();
        renderScenarioBreakdownTable();
        renderSpatialOverview();
        renderRegionalAnalysis();
        renderDualCompare();
        renderProvinceTables();
      }

      function boot() {
        renderHero();
        renderInputCharts();
        renderInputSummary();
        renderBiasSummary();
        initControls();
        renderFiles();
        updateRoleSection();
        window.addEventListener("resize", () => {
          renderInputCharts();
          renderContributionChart();
        });
      }

      boot();
    """


def render_design_rules(rules: list[dict[str, str]]) -> str:
    blocks: list[str] = []
    for item in rules:
        blocks.append(
            f"""
            <article class="reference-item">
              <div class="mini-label">Applied Rule</div>
              <strong>{html.escape(item["title"])}</strong>
              <p>{html.escape(item["description"])}</p>
            </article>"""
        )
    return "\n".join(blocks)


def render_reference_cards(refs: list[dict[str, str]]) -> str:
    blocks: list[str] = []
    for item in refs:
        blocks.append(
            f"""
            <article class="reference-item">
              <div class="mini-label">Literature</div>
              <strong>{html.escape(item["short"])}</strong>
              <p>{html.escape(item["title"])}</p>
              <p class="reference-note">{html.escape(item["note"])}</p>
              <a class="reference-link" href="{html.escape(item["url"])}" target="_blank" rel="noopener">{html.escape(item["url"])}</a>
            </article>"""
        )
    return "\n".join(blocks)


def build_html(data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    design_rules_html = render_design_rules(data["design_rules"])
    references_html = render_reference_cards(data["references"])
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>温度未来情景专页</title>
  <style>{build_styles()}</style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">Temperature-Only Future Dashboard</div>
          <h1>温度未来情景专页</h1>
          <p>这页只讲 TA 与 SSP 省平均气温，按温度输入、模型响应和省级差异单独展开。</p>
          <div class="hero-links">
            <a class="pill-link" href="index.html">原未来情景主页仍保留</a>
            <a class="pill-link" href="#inputs">看温度路径</a>
            <a class="pill-link" href="#baseline">看 baseline logic</a>
            <a class="pill-link" href="#national">看全国结果</a>
            <a class="pill-link" href="#models">看模型响应</a>
            <a class="pill-link" href="#compare">看双情景比较</a>
          </div>
          <div class="hero-metrics" id="heroMetrics"></div>
        </div>
        <div class="hero-note">
          <strong>口径说明</strong>
          <p>1. 输入层只看 `TA（°C）` 和 `省平均气温`。</p>
          <p>2. 模型层单独拆 `β_temp × Δtemp / std_temp`。</p>
          <p>3. 省平均气温先做历史口径 alignment；TA 保留 anomaly 定义。</p>
          <p>4. 本页图件全部先输出到本地 PNG，再由 HTML 引用；页面配色改成 light / paper 风格。</p>
          <p class="subtle" id="generatedAt"></p>
        </div>
      </div>
      <nav class="nav">
        <a href="#inputs">温度输入路径</a>
        <a href="#baseline">Baseline Logic</a>
        <a href="#national">全国结果</a>
        <a href="#models">温度模型矩阵</a>
        <a href="#contribution">温度贡献分解</a>
        <a href="#spatial">空间格局</a>
        <a href="#regional">分地区分析</a>
        <a href="#compare">双情景比较</a>
        <a href="#provinces">省级温度热点</a>
        <a href="#design-notes">图形规范与文献</a>
        <a href="#files">输入与文件</a>
      </nav>
    </section>

    <section class="section" id="inputs">
      <div class="section-head">
        <div>
          <div class="eyebrow">Input Paths</div>
          <h2>温度输入路径先单独讲清楚</h2>
        </div>
        <p>上半页先看温度本身的未来轨迹，再进入模型和贡献分解。</p>
      </div>
      <div class="controls controls-single">
        <label>Input display mode<select id="inputDisplaySelect"></select><span class="mode-note" id="inputDisplayNote"></span></label>
      </div>
      <div class="grid-2">
        <article class="chart-card">
          <div class="mini-label">Input A</div>
          <h3>TA national mean trajectory</h3>
          <div class="chart-box" id="taInputChart"></div>
          <p class="figure-caption">虚线为 2014-2023 历史均值，彩带为 `p10-p90` 范围；`2023 anchored` 只用于视觉衔接，不改预测输入。</p>
        </article>
        <article class="chart-card">
          <div class="mini-label">Input B</div>
          <h3>Province mean temperature trajectory</h3>
          <div class="chart-box" id="provinceInputChart"></div>
          <p class="figure-caption">这里展示的是对齐历史口径后的 SSP 省平均气温绝对温度路径，不是 anomaly。</p>
        </article>
      </div>
      <div class="grid-2">
        <article class="table-card">
          <div class="mini-label">2050 Ladder</div>
          <h3>温度输入 2050 national summary</h3>
          <div id="inputSummary"></div>
        </article>
        <article class="table-card">
          <div class="mini-label">Bias Alignment</div>
          <h3>省平均气温的口径校正</h3>
          <div class="grid-3" id="biasCards"></div>
          <div id="biasTable"></div>
        </article>
      </div>
    </section>

    <section class="section" id="baseline">
      <div class="section-head">
        <div>
          <div class="eyebrow">Baseline Logic</div>
          <h2>先把温度页里的 baseline 逻辑讲清楚</h2>
        </div>
        <p>这部分对应原来 r1xday 页里的方法入口，但这里强调的是温度通道如何接进两种 baseline mode，以及为什么温度增量在双 mode 下几乎平行。</p>
      </div>
      <div class="logic-grid">
        <article class="story-card">
          <div class="mini-label">Step 1</div>
          <strong>生成 baseline</strong>
          <p>`Lancet ETS` 先延续 AMR 自身；`X-driven` 先用协变量路径重建 baseline。温度页里，这一步决定的是 AMR absolute level。</p>
        </article>
        <article class="story-card">
          <div class="mini-label">Step 2</div>
          <strong>接入温度情景</strong>
          <p>把 `TA` 或 `省平均气温` 的未来 SSP 路径接进模型，再按 `β_temp / std_temp × Δtemp` 折算成温度通道单独贡献。</p>
        </article>
        <article class="story-card">
          <div class="mini-label">Step 3</div>
          <strong>先省级后全国</strong>
          <p>所有结果先在省级计算，再按省份平均聚合成全国与地区结果，所以后面的空间格局和全国均值是同一套底层数据。</p>
        </article>
      </div>
      <div class="grid-4" id="baselineCompareCards"></div>
      <div class="narrative" id="baselineNarrative"></div>
    </section>

    <section class="section" id="national">
      <div class="section-head">
        <div>
          <div class="eyebrow">National Results</div>
          <h2>全国结果先看 baseline，再看情景增量怎么拉开</h2>
        </div>
        <p>这一段把“2050 baseline 水平”“温度通道的情景增量”“全国结果怎么读”放在同一处，方便直接写结果段。</p>
      </div>
      <div class="grid-4" id="nationalCards"></div>
      <div class="grid-2">
        <article class="table-card">
          <div class="mini-label">Scenario Delta 2050</div>
          <h3>2050 情景增量柱状图</h3>
          <div class="table-note">柱带长度对应温度通道单独贡献，副标题同时给出 `Δtemp` 和 `total ΔAMR`，这样能直接看出温度通道在总结果里的位置。</div>
          <div class="accent-line"></div>
          <div id="nationalDeltaBars"></div>
          <p class="figure-caption">柱体是 2050 中位数，whisker 是 `p10-p90` 统计范围，用来表达情景分布宽度而不是频率学意义上的置信区间。</p>
        </article>
        <article class="table-card">
          <div class="mini-label">How To Read</div>
          <h3>全国结果怎么读</h3>
          <div class="narrative" id="nationalRead"></div>
        </article>
      </div>
    </section>

    <section class="section" id="models">
      <div class="section-head">
        <div>
          <div class="eyebrow">Model Matrix</div>
          <h2>哪些模型在用哪种温度代理</h2>
        </div>
        <p>这里单独切 role、baseline mode 和 scenario，只看温度变量的响应方式。</p>
      </div>
      <div class="controls">
        <label>Baseline mode<select id="modeSelect"></select><span class="mode-note" id="modeNote"></span></label>
        <label>Temperature role<select id="roleSelect"></select></label>
        <label>Scenario<select id="scenarioSelect"></select></label>
      </div>
      <div class="grid-4" id="roleCards"></div>
      <article class="table-card">
        <div class="mini-label">Role Comparison</div>
        <h3>当前 scenario 下的温度敏感模型排名</h3>
        <div id="roleComparisonTable"></div>
      </article>
    </section>

    <section class="section" id="contribution">
      <div class="section-head">
        <div>
          <div class="eyebrow">Contribution Decomposition</div>
          <h2>把温度这条通道单独拆出来</h2>
        </div>
        <p>这里的线和表都只看温度变量自己的贡献，和总气候效应分开呈现。</p>
      </div>
      <div class="grid-2">
        <article class="chart-card">
          <div class="mini-label">Temperature-Only</div>
          <h3>National temperature contribution by scenario</h3>
          <div class="chart-box" id="contributionChart"></div>
          <p class="figure-caption">所有线都只对应温度通道自身的 `ΔAMR`；零线帮助区分温度通道在不同情景下是抬升还是压低结果。</p>
        </article>
        <article class="table-card">
          <div class="mini-label">2050 Breakdown</div>
          <h3>当前 role 的情景分解表</h3>
          <div id="scenarioBreakdownTable"></div>
        </article>
      </div>
    </section>

    <section class="section" id="spatial">
      <div class="section-head">
        <div>
          <div class="eyebrow">Spatial Pattern</div>
          <h2>地区与省级空间格局先压缩成可读层级</h2>
        </div>
        <p>没有直接做地图，而是先用条带排序把空间结构压缩出来：地区看均值，省级看具体热点和尾部省份。</p>
      </div>
      <div class="grid-2">
        <article class="table-card">
          <div class="mini-label">Regional Pattern</div>
          <h3>七大区温度通道排序</h3>
          <div id="spatialRegionBars"></div>
          <p class="figure-caption">每根条带表示该地区内部各省的均值贡献，适合快速看全国平均主要由哪些地带拉动。</p>
        </article>
        <article class="table-card">
          <div class="mini-label">Provincial Pattern</div>
          <h3>省级温度通道热点与尾部</h3>
          <div id="spatialProvinceBars"></div>
          <p class="figure-caption">省级图同时保留高值热点和尾部省份，避免只看“前几名”时丢失空间对照。</p>
        </article>
      </div>
      <div class="narrative" id="spatialNarrative"></div>
    </section>

    <section class="section" id="regional">
      <div class="section-head">
        <div>
          <div class="eyebrow">Regional Analysis</div>
          <h2>分地区分析帮助判断全国平均是被哪些地带推着走</h2>
        </div>
        <p>这里固定看当前 baseline mode + role + scenario，把各地区的 baseline temp、scenario temp、温度贡献和总 ΔAMR 放在一张表里。</p>
      </div>
      <div class="grid-2">
        <article class="chart-card">
          <div class="mini-label">Standard Regional Figure</div>
          <h3>Figure 5 style regional trajectories</h3>
          <div class="chart-box" id="regionalFigureGrid"></div>
          <p class="figure-caption">这里接入模块原生的区域轨迹总图，保留历史观测、baseline path 和五条 SSP 温度轨迹，方便和 r1xday 页逐图对照。</p>
        </article>
        <article class="chart-card">
          <div class="mini-label">Standard Regional Heatmap</div>
          <h3>2050 regional delta heatmap</h3>
          <div class="chart-box" id="regionalHeatmapFigure"></div>
          <p class="figure-caption">热图直接展示 2050 各大区在五条 SSP 下相对 baseline 的 Δtemperature，用来补足条带排序之外的横向比较。</p>
        </article>
      </div>
      <div class="narrative" id="regionalRead"></div>
      <article class="table-card">
        <div class="mini-label">Region Table</div>
        <h3>七大区当前情景总表</h3>
        <div id="regionalTable"></div>
      </article>
    </section>

    <section class="section" id="compare">
      <div class="section-head">
        <div>
          <div class="eyebrow">Dual Scenario Compare</div>
          <h2>双情景比较看的是对未来路径分叉的敏感度</h2>
        </div>
        <p>这里固定比较 `SSP1-1.9` 和 `SSP5-8.5`。gap 越大，说明该地区或省份对未来温度路径分化越敏感。</p>
      </div>
      <div class="grid-2">
        <article class="chart-card">
          <div class="mini-label">Standard Dual Figure</div>
          <h3>Dual-scenario trajectory + rose + dumbbell</h3>
          <div class="chart-box" id="dualScenarioPredictedFigure"></div>
          <p class="figure-caption">这里接入模块原生的双情景总图，三联图同时看全国轨迹、各省玫瑰图和省级 dumbbell 排序。</p>
        </article>
        <article class="chart-card">
          <div class="mini-label">Standard Dual Delta</div>
          <h3>Dual-scenario gap re-centered to SSP1-1.9</h3>
          <div class="chart-box" id="dualScenarioDeltaFigure"></div>
          <p class="figure-caption">增量版把低排放路径重心放到零线，直接强调 `SSP5-8.5 - SSP1-1.9` 的温度分叉幅度。</p>
        </article>
      </div>
      <div class="grid-2">
        <article class="table-card">
          <div class="mini-label">Regional Gap</div>
          <h3>地区双情景差值排序</h3>
          <div id="compareRegionBars"></div>
          <p class="figure-caption">正值表示 `SSP5-8.5` 相比 `SSP1-1.9` 带来更大的温度通道贡献；数值越大，对未来路径分叉越敏感。</p>
        </article>
        <article class="table-card">
          <div class="mini-label">Provincial Gap</div>
          <h3>省级双情景差值排序</h3>
          <div id="compareProvinceBars"></div>
          <p class="figure-caption">这里只保留差值最大的省份，控制图面复杂度，同时把最强的 cross-scenario contrast 留在第一页可见范围。</p>
        </article>
      </div>
      <div class="grid-2">
        <article class="table-card">
          <div class="mini-label">Regional Gap Table</div>
          <h3>七大区双情景 gap 总表</h3>
          <div id="compareRegionTable"></div>
        </article>
        <article class="table-card">
          <div class="mini-label">Provincial Gap Table</div>
          <h3>省级双情景 gap 总表</h3>
          <div id="compareProvinceTable"></div>
        </article>
      </div>
    </section>

    <section class="section" id="provinces">
      <div class="section-head">
        <div>
          <div class="eyebrow">Provincial Hotspots</div>
          <h2>省级层面谁最热、谁最敏感</h2>
        </div>
        <p>这一段保留你现在已经认可的省级多表结构，并把它升级成可以直接读温度通道解释力的省级分析。</p>
      </div>
      <article class="chart-card">
        <div class="mini-label">Standard Provincial Panel</div>
        <h3>Province-year temperature panel</h3>
        <div class="chart-box" id="provincialPanelFigure"></div>
        <p class="figure-caption">这里接入模块原生的省级 panel：上方是全国均值轨迹，下方是按大区和省份排序的 province-year heatmap，和 r1xday 页保持同一阅读入口。</p>
      </article>
      <div class="narrative" id="provinceNarrative"></div>
      <div class="grid-2">
        <article class="table-card"><div class="mini-label">Warmest Shift</div><h3>升温幅度最高</h3><div id="warmingTable"></div></article>
        <article class="table-card"><div class="mini-label">Coolest Shift</div><h3>降温 / 相对最弱增温</h3><div id="coolingTable"></div></article>
        <article class="table-card"><div class="mini-label">Positive Contribution</div><h3>温度单独抬升 AMR 最多</h3><div id="positiveContributionTable"></div></article>
        <article class="table-card"><div class="mini-label">Negative Contribution</div><h3>温度单独拉低 AMR 最多</h3><div id="negativeContributionTable"></div></article>
      </div>
    </section>

    <section class="section" id="design-notes">
      <div class="section-head">
        <div>
          <div class="eyebrow">Figure Design Notes</div>
          <h2>把图改得更学术，这次具体参考了什么</h2>
        </div>
        <p>这一段不改结果，只公开本页的图形语法和文献依据，方便后续继续沿着同一套规范迭代。</p>
      </div>
      <div class="grid-2">
        <article class="table-card">
          <div class="mini-label">Applied Rules</div>
          <h3>本页已经落实的出图规则</h3>
          <div class="reference-grid">{design_rules_html}</div>
        </article>
        <article class="table-card">
          <div class="mini-label">Literature</div>
          <h3>图形与气候传播参考文献</h3>
          <div class="reference-grid">{references_html}</div>
        </article>
      </div>
    </section>

    <section class="section" id="files">
      <div class="section-head">
        <div>
          <div class="eyebrow">Files</div>
          <h2>这页直接依赖的温度文件</h2>
        </div>
        <p>只列温度相关输入、中间件和 projection 面板。</p>
      </div>
      <div class="files-grid" id="fileGrid"></div>
    </section>
  </div>
  <script id="dashboard-data" type="application/json">{payload}</script>
  <script>{build_script()}</script>
</body>
</html>"""


def main() -> int:
    data = build_data()
    html = build_html(data)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Wrote temperature dashboard to {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
