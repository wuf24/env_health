from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from config_future_scenario_projection import (
    BASELINE_MODE_LABELS,
    DEFAULT_BASELINE_MODES,
    DEFAULT_OUTCOME,
    FUTURE_END_YEAR,
    FUTURE_START_YEAR,
    RX1DAY_SCENARIOS,
    SCENARIO_LABELS,
    resolve_results_output_dir,
)
from future_scenario_common import configure_logger


SECTION_DIR = Path(__file__).resolve().parents[1]
REGION_MAPPING_PATH = SECTION_DIR / "data_processed" / "province_to_region_7zones.csv"


sns.set_theme(style="whitegrid", font="Microsoft YaHei", rc={"axes.unicode_minus": False})


SCENARIO_PALETTE = {
    "ssp119": "#1b9e77",
    "ssp126": "#4daf4a",
    "ssp245": "#377eb8",
    "ssp370": "#ff7f00",
    "ssp585": "#d7301f",
}

REGION_PALETTE = {
    "\u534e\u5317": "#334155",
    "\u4e1c\u5317": "#0f766e",
    "\u534e\u4e1c": "#1d4ed8",
    "\u534e\u4e2d": "#7c3aed",
    "\u534e\u5357": "#b45309",
    "\u897f\u5357": "#be123c",
    "\u897f\u5317": "#4b5563",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a dual-scenario comparison figure with national trajectories, a provincial rose chart, and a 2050 provincial dumbbell ranking."
    )
    parser.add_argument("--outcome", default=DEFAULT_OUTCOME, help="Outcome folder under results.")
    parser.add_argument(
        "--baseline-modes",
        nargs="+",
        choices=sorted(BASELINE_MODE_LABELS),
        default=DEFAULT_BASELINE_MODES,
        help="Baseline modes to render.",
    )
    parser.add_argument(
        "--scenario-pair",
        nargs=2,
        choices=RX1DAY_SCENARIOS,
        default=["ssp119", "ssp585"],
        metavar=("SCENARIO_A", "SCENARIO_B"),
        help="Two SSP scenarios to compare.",
    )
    parser.add_argument(
        "--value-mode",
        choices=["delta", "predicted"],
        default="delta",
        help="Metric shown in the dual-scenario figure. `delta` emphasizes SSP contrast by plotting values relative to baseline.",
    )
    parser.add_argument("--start-year", type=int, default=FUTURE_START_YEAR, help="First future year to include.")
    parser.add_argument("--end-year", type=int, default=FUTURE_END_YEAR, help="Last future year to include.")
    return parser.parse_args()


def load_region_mapping(path: Path = REGION_MAPPING_PATH) -> pd.DataFrame:
    mapping = pd.read_csv(path, encoding="utf-8-sig")
    required = {"province", "region", "region_en", "region_order"}
    missing = required.difference(mapping.columns)
    if missing:
        raise ValueError(f"Region mapping missing columns: {sorted(missing)}")

    mapping["province"] = mapping["province"].astype(str).str.strip()
    mapping["region"] = mapping["region"].astype(str).str.strip()
    mapping["region_en"] = mapping["region_en"].astype(str).str.strip()
    mapping["region_order"] = pd.to_numeric(mapping["region_order"], errors="raise").astype(int)
    return mapping.sort_values(["region_order", "province"]).reset_index(drop=True)


def load_projection_panel(outcome_dir: Path, baseline_mode: str) -> pd.DataFrame:
    projection_path = outcome_dir / baseline_mode / "projection_outputs" / "future_scenario_projection_panel.csv"
    if not projection_path.exists():
        raise FileNotFoundError(f"Projection panel not found for baseline mode {baseline_mode}: {projection_path}")
    return pd.read_csv(projection_path, encoding="utf-8-sig")


def get_value_meta(value_mode: str) -> dict[str, str]:
    if value_mode == "predicted":
        return {
            "column": "scenario_pred",
            "label": "Predicted AMR (%)",
            "title": "Predicted AMR",
            "unit_suffix": "%",
        }
    return {
        "column": "delta_vs_baseline",
        "label": "\u0394AMR vs baseline (percentage points)",
        "title": "\u0394AMR vs baseline",
        "unit_suffix": "pp",
    }


def prepare_dual_scenario_frame(
    projection_panel: pd.DataFrame,
    region_mapping: pd.DataFrame,
    scenario_pair: list[str],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    plot_df = projection_panel[
        projection_panel["role_id"].eq("main_model")
        & projection_panel["scenario_id"].isin(["baseline_ets", *scenario_pair])
        & projection_panel["Year"].between(start_year, end_year)
    ].copy()

    plot_df = plot_df.merge(
        region_mapping.rename(columns={"province": "Province"}),
        on="Province",
        how="left",
        validate="many_to_one",
    )
    return plot_df.sort_values(["region_order", "Province", "scenario_id", "statistic", "Year"]).reset_index(drop=True)


def build_national_trajectory(
    plot_df: pd.DataFrame,
    scenario_pair: list[str],
    value_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    meta = get_value_meta(value_mode)
    value_col = meta["column"]

    if value_mode == "predicted":
        baseline = (
            plot_df[plot_df["scenario_id"].eq("baseline_ets")]
            .groupby("Year", as_index=False)
            .agg(reference_mean=(value_col, "mean"))
            .sort_values("Year")
        )
    else:
        years = sorted(plot_df["Year"].unique().tolist())
        baseline = pd.DataFrame({"Year": years, "reference_mean": np.zeros(len(years), dtype=float)})

    scenarios = (
        plot_df[plot_df["scenario_id"].isin(scenario_pair)]
        .groupby(["scenario_id", "statistic", "Year"], as_index=False)
        .agg(value_mean=(value_col, "mean"))
        .sort_values(["scenario_id", "statistic", "Year"])
    )
    return baseline, scenarios


def build_pair_table(
    plot_df: pd.DataFrame,
    scenario_pair: list[str],
    end_year: int,
    value_mode: str,
) -> pd.DataFrame:
    meta = get_value_meta(value_mode)
    value_col = meta["column"]

    end_df = plot_df[
        plot_df["Year"].eq(end_year)
        & plot_df["statistic"].eq("median")
        & plot_df["scenario_id"].isin(scenario_pair)
    ].copy()

    pivot = (
        end_df.pivot_table(
            index=["Province", "region", "region_en", "region_order"],
            columns="scenario_id",
            values=value_col,
            aggfunc="mean",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    pivot["scenario_gap"] = pivot[scenario_pair[1]] - pivot[scenario_pair[0]]
    pivot["scenario_gap_abs"] = pivot["scenario_gap"].abs()
    pivot["scenario_midpoint"] = pivot[[scenario_pair[0], scenario_pair[1]]].mean(axis=1)
    return pivot


def build_rose_order(
    plot_df: pd.DataFrame,
    scenario_pair: list[str],
    end_year: int,
    value_mode: str,
) -> pd.DataFrame:
    pivot = build_pair_table(
        plot_df=plot_df,
        scenario_pair=scenario_pair,
        end_year=end_year,
        value_mode=value_mode,
    )
    pivot = pivot.sort_values(
        ["scenario_gap_abs", "scenario_gap", "scenario_midpoint", "region_order", "Province"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)
    pivot["rose_order"] = np.arange(len(pivot))
    return pivot


def build_dumbbell_order(
    plot_df: pd.DataFrame,
    scenario_pair: list[str],
    end_year: int,
    value_mode: str,
) -> pd.DataFrame:
    pivot = build_pair_table(
        plot_df=plot_df,
        scenario_pair=scenario_pair,
        end_year=end_year,
        value_mode=value_mode,
    )
    return pivot.sort_values(
        ["scenario_gap_abs", "scenario_gap", "scenario_midpoint", "region_order", "Province"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)


def add_region_separators(ax: plt.Axes, ordered_df: pd.DataFrame) -> None:
    start = 0
    regions = ordered_df["region"].tolist()
    for idx in range(1, len(regions) + 1):
        if idx == len(regions) or regions[idx] != regions[start]:
            if idx < len(regions):
                ax.axhline(idx - 0.5, color="#e2e8f0", linewidth=1.0, zorder=0)
            start = idx


def format_tick(value: float) -> str:
    text = f"{value:.1f}"
    if text.endswith(".0"):
        return text[:-2]
    return text


def plot_national_trajectory(
    ax: plt.Axes,
    baseline: pd.DataFrame,
    national: pd.DataFrame,
    scenario_pair: list[str],
    value_mode: str,
) -> None:
    meta = get_value_meta(value_mode)

    if value_mode == "delta":
        ax.axhline(0, color="#475569", linewidth=2.0, linestyle="--", label="Baseline", zorder=1)
    else:
        ax.plot(
            baseline["Year"],
            baseline["reference_mean"],
            color="#475569",
            linewidth=2.0,
            linestyle="--",
            label="Baseline",
            zorder=2,
        )

    median_wide = (
        national[national["statistic"].eq("median")]
        .pivot(index="Year", columns="scenario_id", values="value_mean")
        .sort_index()
    )
    ax.fill_between(
        median_wide.index,
        median_wide[scenario_pair[0]],
        median_wide[scenario_pair[1]],
        color="#94a3b8",
        alpha=0.14,
        zorder=0,
    )

    for idx, scenario_id in enumerate(scenario_pair):
        color = SCENARIO_PALETTE[scenario_id]
        alpha = 0.18 if idx == 0 else 0.13
        median = national[
            national["scenario_id"].eq(scenario_id) & national["statistic"].eq("median")
        ].sort_values("Year")
        p10 = national[
            national["scenario_id"].eq(scenario_id) & national["statistic"].eq("p10")
        ].sort_values("Year")
        p90 = national[
            national["scenario_id"].eq(scenario_id) & national["statistic"].eq("p90")
        ].sort_values("Year")

        if not p10.empty and not p90.empty:
            ax.fill_between(
                p10["Year"],
                p10["value_mean"],
                p90["value_mean"],
                color=color,
                alpha=alpha,
                linewidth=0,
                zorder=1,
            )
        ax.plot(
            median["Year"],
            median["value_mean"],
            color=color,
            linewidth=2.8,
            label=SCENARIO_LABELS[scenario_id],
            zorder=3,
        )
        ax.scatter(
            median["Year"].iloc[-1],
            median["value_mean"].iloc[-1],
            s=34,
            color=color,
            edgecolor="white",
            linewidth=0.6,
            zorder=4,
        )

    end_year = int(median_wide.index.max())
    end_a = float(median_wide.loc[end_year, scenario_pair[0]])
    end_b = float(median_wide.loc[end_year, scenario_pair[1]])
    gap_2050 = end_b - end_a
    ax.annotate(
        "",
        xy=(end_year, end_a),
        xytext=(end_year, end_b),
        arrowprops=dict(arrowstyle="<->", color="#64748b", linewidth=1.2, shrinkA=4, shrinkB=4),
        zorder=4,
    )
    ax.text(
        end_year - 0.35,
        (end_a + end_b) / 2.0,
        f"{gap_2050:+.2f} {meta['unit_suffix']}",
        ha="right",
        va="center",
        fontsize=9,
        color="#475569",
        bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none", alpha=0.9),
    )
    ax.text(
        0.99,
        1.02,
        f"2050 national gap = {gap_2050:+.2f} {meta['unit_suffix']}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        color="#475569",
    )

    all_values = national["value_mean"].to_numpy()
    y_min = float(np.nanmin(all_values))
    y_max = float(np.nanmax(all_values))
    span = max(y_max - y_min, 0.15 if value_mode == "delta" else 1.0)
    pad = span * 0.18
    if value_mode == "delta":
        y_min = min(y_min - pad, -0.02)
        y_max = y_max + pad
    else:
        y_min = y_min - pad
        y_max = y_max + pad

    ax.set_title("National trajectory", loc="left", fontsize=13, fontweight="bold")
    ax.set_ylabel(meta["label"])
    ax.set_xlim(baseline["Year"].min(), baseline["Year"].max() + 0.55)
    ax.set_ylim(y_min, y_max)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.9)


def plot_rose_chart(
    ax: plt.Axes,
    rose_df: pd.DataFrame,
    scenario_pair: list[str],
    end_year: int,
    value_mode: str,
) -> None:
    meta = get_value_meta(value_mode)
    n = len(rose_df)
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    width = (2 * np.pi / n) * 0.88

    scenario_a = rose_df[scenario_pair[0]].to_numpy()
    scenario_b = rose_df[scenario_pair[1]].to_numpy()

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    if value_mode == "delta":
        combined = np.concatenate([scenario_a, scenario_b])
        min_val = float(np.nanmin(combined))
        max_val = float(np.nanmax(combined))
        span = max(max_val - min_val, 0.5)
        pad = span * 0.16
        zero_ring = abs(min(min_val, 0.0)) + pad
        outer_limit = zero_ring + max(max_val, 0.0) + pad

        for idx, (values, scenario_id, alpha, width_scale) in enumerate(
            [
                (scenario_a, scenario_pair[0], 0.24, 1.0),
                (scenario_b, scenario_pair[1], 0.76, 0.66),
            ]
        ):
            bottoms = np.where(values >= 0, zero_ring, zero_ring + values)
            heights = np.abs(values)
            ax.bar(
                theta,
                heights,
                bottom=bottoms,
                width=width * width_scale,
                color=SCENARIO_PALETTE[scenario_id],
                alpha=alpha,
                edgecolor="white",
                linewidth=0.5 if idx == 0 else 0.4,
                zorder=2 + idx,
            )
            ax.bar(
                theta,
                heights,
                bottom=bottoms,
                width=width * width_scale,
                facecolor="none",
                edgecolor=SCENARIO_PALETTE[scenario_id],
                linewidth=0.95 if idx == 0 else 1.05,
                zorder=4 + idx,
            )

        ring_theta = np.linspace(0, 2 * np.pi, 361)
        ax.plot(ring_theta, np.full_like(ring_theta, zero_ring), color="#475569", linestyle="--", linewidth=1.0, alpha=0.9)

        neg_extent = abs(min(min_val, 0.0))
        pos_extent = max(max_val, 0.0)
        tick_values = []
        if neg_extent > 0.02:
            tick_values.append(-neg_extent)
        tick_values.append(0.0)
        if pos_extent > 0.02:
            tick_values.append(pos_extent / 2.0)
            tick_values.append(pos_extent)
        tick_values = sorted({round(item, 2) for item in tick_values})
        tick_positions = [zero_ring + item for item in tick_values]
        ax.set_ylim(0, outer_limit)
        ax.set_yticks(tick_positions)
        ax.set_yticklabels([format_tick(item) for item in tick_values], fontsize=8, color="#64748b")
        ax.set_rlabel_position(90)
        label_radius = outer_limit * 1.03
    else:
        outer_limit = max(float(np.nanmax(scenario_a)), float(np.nanmax(scenario_b))) * 1.26
        ax.set_ylim(0, outer_limit)
        ax.bar(
            theta,
            scenario_a,
            width=width,
            color=SCENARIO_PALETTE[scenario_pair[0]],
            alpha=0.32,
            edgecolor="white",
            linewidth=0.5,
            zorder=2,
        )
        ax.bar(
            theta,
            scenario_b,
            width=width * 0.62,
            color=SCENARIO_PALETTE[scenario_pair[1]],
            alpha=0.72,
            edgecolor="white",
            linewidth=0.4,
            zorder=3,
        )
        ax.bar(
            theta,
            scenario_a,
            width=width,
            facecolor="none",
            edgecolor=SCENARIO_PALETTE[scenario_pair[0]],
            linewidth=0.9,
            zorder=4,
        )
        ax.bar(
            theta,
            scenario_b,
            width=width * 0.62,
            facecolor="none",
            edgecolor=SCENARIO_PALETTE[scenario_pair[1]],
            linewidth=1.0,
            zorder=5,
        )
        yticks = np.linspace(0, outer_limit * 0.8, 4)[1:]
        ax.set_yticks(yticks)
        ax.set_yticklabels([format_tick(tick) for tick in yticks], fontsize=8, color="#64748b")
        ax.set_rlabel_position(90)
        label_radius = outer_limit * 1.04

    ax.set_title(f"Provincial rose chart in {end_year}", loc="left", fontsize=13, fontweight="bold", pad=18)
    ax.text(
        0.02,
        1.05,
        "Clockwise order follows the 2050 SSP gap from largest to smallest.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.6,
        color="#64748b",
    )
    ax.grid(color="#e2e8f0", linewidth=0.8)
    ax.spines["polar"].set_color("#cbd5e1")
    ax.spines["polar"].set_linewidth(1.0)
    ax.set_xticks([])

    for angle, (_, row) in zip(theta, rose_df.iterrows()):
        rotation = np.degrees(angle)
        if 90 < rotation < 270:
            text_rotation = rotation + 180
            ha = "right"
        else:
            text_rotation = rotation
            ha = "left"
        ax.text(
            angle,
            label_radius,
            row["Province"],
            rotation=text_rotation,
            rotation_mode="anchor",
            ha=ha,
            va="center",
            fontsize=7.2,
            color=REGION_PALETTE.get(row["region"], "#334155"),
        )

    legend_handles = [
        Patch(facecolor=SCENARIO_PALETTE[scenario_pair[0]], edgecolor="none", alpha=0.34 if value_mode == "delta" else 0.32, label=SCENARIO_LABELS[scenario_pair[0]]),
        Patch(facecolor=SCENARIO_PALETTE[scenario_pair[1]], edgecolor="none", alpha=0.74 if value_mode == "delta" else 0.72, label=SCENARIO_LABELS[scenario_pair[1]]),
    ]
    ax.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, -0.10), frameon=False, ncol=2)
    ax.text(
        0.5,
        -0.20,
        meta["title"],
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        color="#475569",
    )


def plot_dumbbell(
    ax: plt.Axes,
    dumbbell_df: pd.DataFrame,
    scenario_pair: list[str],
    end_year: int,
    value_mode: str,
) -> None:
    meta = get_value_meta(value_mode)
    y = np.arange(len(dumbbell_df))
    a_values = dumbbell_df[scenario_pair[0]].to_numpy()
    b_values = dumbbell_df[scenario_pair[1]].to_numpy()
    gap_values = b_values - a_values

    if value_mode == "delta":
        left_values = np.zeros_like(gap_values)
        right_values = gap_values
        connector_color = "#f1b8b0"
        xlabel = f"Gap relative to {SCENARIO_LABELS[scenario_pair[0]]} ({meta['unit_suffix']})"
        ax.axvline(0, color="#475569", linewidth=1.0, linestyle="--", alpha=0.9, zorder=0)
        ax.text(
            0.99,
            1.055,
            f"Rebased: {SCENARIO_LABELS[scenario_pair[0]]} = 0 in every province",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=8.8,
            color="#64748b",
        )
    else:
        left_values = a_values
        right_values = b_values
        connector_color = "#cbd5e1"
        xlabel = meta["label"]

    ax.hlines(y, left_values, right_values, color=connector_color, linewidth=2.6, zorder=1)
    ax.scatter(
        left_values,
        y,
        s=42,
        color=SCENARIO_PALETTE[scenario_pair[0]],
        alpha=0.90,
        zorder=3,
        label=SCENARIO_LABELS[scenario_pair[0]],
    )
    ax.scatter(
        right_values,
        y,
        s=42,
        color=SCENARIO_PALETTE[scenario_pair[1]],
        alpha=0.98,
        zorder=4,
        label=SCENARIO_LABELS[scenario_pair[1]],
    )

    ax.set_yticks(y)
    ax.set_yticklabels(dumbbell_df["Province"], fontsize=9)
    for tick_label, (_, row) in zip(ax.get_yticklabels(), dumbbell_df.iterrows()):
        tick_label.set_color(REGION_PALETTE.get(row["region"], "#334155"))

    add_region_separators(ax, dumbbell_df)
    ax.invert_yaxis()
    ax.set_title(f"Provincial dumbbell ranking in {end_year}", loc="left", fontsize=13, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", color="#e2e8f0", linewidth=0.9)

    gap_median = gap_values.mean() if value_mode == "delta" else dumbbell_df["scenario_gap"].median()
    gap_max = dumbbell_df["scenario_gap_abs"].max()
    ax.text(
        0.99,
        1.01,
        f"Mean gap = {gap_median:+.2f} {meta['unit_suffix']} | Max gap = {gap_max:.2f} {meta['unit_suffix']}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        color="#475569",
    )

    if value_mode == "delta":
        value_min = float(np.nanmin(np.concatenate([left_values, right_values, np.array([0.0])])))
        value_max = float(np.nanmax(np.concatenate([left_values, right_values, np.array([0.0])])))
    else:
        value_min = float(np.nanmin(np.concatenate([a_values, b_values])))
        value_max = float(np.nanmax(np.concatenate([a_values, b_values])))
    span = max(value_max - value_min, 0.2)
    pad = span * 0.18
    if value_mode == "delta":
        ax.set_xlim(min(-pad * 0.35, value_min - pad * 0.2), value_max + pad * 0.9)
    else:
        ax.set_xlim(value_min - pad * 0.6, value_max + pad)

    for idx, (_, row) in enumerate(dumbbell_df.head(6).iterrows()):
        text_x = (row["scenario_gap"] if value_mode == "delta" else max(row[scenario_pair[0]], row[scenario_pair[1]])) + pad * 0.05
        ax.text(
            text_x,
            idx,
            f"{row['scenario_gap']:+.2f}",
            va="center",
            ha="left",
            fontsize=8.5,
            color="#475569",
        )


def render_dual_scenario_figure(
    plot_df: pd.DataFrame,
    output_path: Path,
    baseline_label: str,
    scenario_pair: list[str],
    value_mode: str,
    start_year: int,
    end_year: int,
) -> Path:
    meta = get_value_meta(value_mode)
    baseline, national = build_national_trajectory(
        plot_df=plot_df,
        scenario_pair=scenario_pair,
        value_mode=value_mode,
    )
    rose_df = build_rose_order(
        plot_df=plot_df,
        scenario_pair=scenario_pair,
        end_year=end_year,
        value_mode=value_mode,
    )
    dumbbell_df = build_dumbbell_order(
        plot_df=plot_df,
        scenario_pair=scenario_pair,
        end_year=end_year,
        value_mode=value_mode,
    )

    fig = plt.figure(figsize=(18.8, 13.6), facecolor="white")
    outer = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.65], hspace=0.28)
    ax_top = fig.add_subplot(outer[0, 0])
    bottom = outer[1, 0].subgridspec(1, 2, width_ratios=[1.04, 1.28], wspace=0.22)
    ax_rose = fig.add_subplot(bottom[0, 0], projection="polar")
    ax_dumbbell = fig.add_subplot(bottom[0, 1])

    plot_national_trajectory(
        ax=ax_top,
        baseline=baseline,
        national=national,
        scenario_pair=scenario_pair,
        value_mode=value_mode,
    )
    plot_rose_chart(
        ax=ax_rose,
        rose_df=rose_df,
        scenario_pair=scenario_pair,
        end_year=end_year,
        value_mode=value_mode,
    )
    plot_dumbbell(
        ax=ax_dumbbell,
        dumbbell_df=dumbbell_df,
        scenario_pair=scenario_pair,
        end_year=end_year,
        value_mode=value_mode,
    )

    legend_handles = [
        Line2D([0], [0], color="#475569", linewidth=2.0, linestyle="--", label="Baseline"),
        Line2D([0], [0], color=SCENARIO_PALETTE[scenario_pair[0]], linewidth=2.8, label=SCENARIO_LABELS[scenario_pair[0]]),
        Line2D([0], [0], color=SCENARIO_PALETTE[scenario_pair[1]], linewidth=2.8, label=SCENARIO_LABELS[scenario_pair[1]]),
    ]
    fig.legend(handles=legend_handles, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.90))

    pair_title = f"{SCENARIO_LABELS[scenario_pair[0]]} vs {SCENARIO_LABELS[scenario_pair[1]]}"
    if value_mode == "delta":
        mode_note = (
            f"Top and rose panels show \u0394AMR relative to baseline. The dumbbell panel is re-centered to "
            f"{SCENARIO_LABELS[scenario_pair[0]]} = 0 so line length equals the provincial SSP gap."
        )
    else:
        mode_note = "All panels show predicted AMR."
    fig.suptitle(
        f"Dual-scenario comparison | {baseline_label}",
        x=0.06,
        y=0.985,
        ha="left",
        fontsize=20,
        fontweight="bold",
    )
    fig.text(
        0.06,
        0.95,
        f"Top: national trajectories. Bottom-left: provincial rose chart. Bottom-right: {end_year} provincial dumbbell ranking. Pair: {pair_title}. {mode_note}",
        ha="left",
        va="center",
        fontsize=11,
        color="#475569",
    )

    fig.subplots_adjust(left=0.06, right=0.97, top=0.88, bottom=0.06)
    fig.savefig(output_path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> int:
    args = parse_args()
    logger, log_path = configure_logger("run_dual_scenario_compare_figure")
    logger.info("Log file: %s", log_path)

    scenario_pair = list(args.scenario_pair)
    if scenario_pair[0] == scenario_pair[1]:
        raise ValueError("scenario-pair must contain two different SSP scenarios.")

    outcome_dir = resolve_results_output_dir(args.outcome)
    compare_dir = outcome_dir / "baseline_mode_compare"
    compare_dir.mkdir(parents=True, exist_ok=True)

    mode_outputs: dict[str, dict[str, str]] = {}
    scenario_tag = f"{scenario_pair[0]}_vs_{scenario_pair[1]}_{args.value_mode}"

    for baseline_mode in args.baseline_modes:
        baseline_label = BASELINE_MODE_LABELS[baseline_mode]
        projection_panel = load_projection_panel(outcome_dir=outcome_dir, baseline_mode=baseline_mode)
        plot_df = prepare_dual_scenario_frame(
            projection_panel=projection_panel,
            region_mapping=load_region_mapping(),
            scenario_pair=scenario_pair,
            start_year=args.start_year,
            end_year=args.end_year,
        )

        figure_dir = outcome_dir / baseline_mode / "dual_scenario_figures"
        output_dir = outcome_dir / baseline_mode / "dual_scenario_outputs"
        figure_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        comparison_table = build_dumbbell_order(
            plot_df=plot_df,
            scenario_pair=scenario_pair,
            end_year=args.end_year,
            value_mode=args.value_mode,
        )
        table_path = output_dir / f"dual_scenario_compare_{scenario_tag}_{args.end_year}.csv"
        comparison_table.to_csv(table_path, index=False, encoding="utf-8-sig")

        figure_path = render_dual_scenario_figure(
            plot_df=plot_df,
            output_path=figure_dir / f"dual_scenario_compare_{scenario_tag}.png",
            baseline_label=baseline_label,
            scenario_pair=scenario_pair,
            value_mode=args.value_mode,
            start_year=args.start_year,
            end_year=args.end_year,
        )

        mode_outputs[baseline_mode] = {
            "comparison_table": str(table_path),
            "dual_scenario_figure": str(figure_path),
        }
        logger.info("Dual-scenario figure completed for %s", baseline_mode)

    metadata = {
        "outcome": args.outcome,
        "baseline_modes": args.baseline_modes,
        "scenario_pair": scenario_pair,
        "value_mode": args.value_mode,
        "start_year": args.start_year,
        "end_year": args.end_year,
        "mapping_path": str(REGION_MAPPING_PATH),
        "mode_outputs": mode_outputs,
        "log_path": str(log_path),
    }
    metadata_path = compare_dir / f"dual_scenario_run_metadata_{scenario_tag}.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Dual-scenario metadata: %s", metadata_path)
    print(f"[done] metadata={metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
