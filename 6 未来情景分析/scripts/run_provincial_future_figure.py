from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import TwoSlopeNorm

from config_future_scenario_projection import (
    BASELINE_MODE_LABELS,
    DEFAULT_BASELINE_MODES,
    DEFAULT_OUTCOME,
    FUTURE_END_YEAR,
    FUTURE_START_YEAR,
    RX1DAY_MAIN_STATISTIC,
    RX1DAY_SCENARIOS,
    SCENARIO_LABELS,
    resolve_results_output_dir,
)
from future_scenario_common import configure_logger


SECTION_DIR = Path(__file__).resolve().parents[1]
REGION_MAPPING_PATH = SECTION_DIR / "data_processed" / "province_to_region_7zones.csv"


sns.set_theme(style="white", font="Microsoft YaHei", rc={"axes.unicode_minus": False})


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
        description="Render a province-scale future scenario figure with national trend and province-year heatmaps."
    )
    parser.add_argument("--outcome", default=DEFAULT_OUTCOME, help="Outcome folder under results.")
    parser.add_argument(
        "--baseline-modes",
        nargs="+",
        choices=sorted(BASELINE_MODE_LABELS),
        default=DEFAULT_BASELINE_MODES,
        help="Baseline modes to render.",
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


def prepare_provincial_panel(
    projection_panel: pd.DataFrame,
    region_mapping: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    keep_statistics = {RX1DAY_MAIN_STATISTIC, "p10", "p90"}
    plot_df = projection_panel[
        projection_panel["role_id"].eq("main_model")
        & projection_panel["scenario_id"].isin(RX1DAY_SCENARIOS)
        & projection_panel["statistic"].isin(keep_statistics)
        & projection_panel["Year"].between(start_year, end_year)
    ].copy()

    plot_df = plot_df.merge(
        region_mapping.rename(columns={"province": "Province"}),
        on="Province",
        how="left",
        validate="many_to_one",
    )
    missing = plot_df.loc[plot_df["region"].isna(), "Province"].dropna().unique().tolist()
    if missing:
        raise ValueError(f"Missing region mapping for provinces: {missing}")
    return plot_df.sort_values(["region_order", "Province", "scenario_id", "statistic", "Year"]).reset_index(drop=True)


def build_province_order(plot_df: pd.DataFrame, end_year: int) -> pd.DataFrame:
    order_df = (
        plot_df[plot_df["statistic"].eq(RX1DAY_MAIN_STATISTIC) & plot_df["Year"].eq(end_year)]
        .groupby(["Province", "region", "region_en", "region_order"], dropna=False)
        .agg(
            delta_mean_2050=("delta_vs_baseline", "mean"),
            delta_max_2050=("delta_vs_baseline", "max"),
            delta_min_2050=("delta_vs_baseline", "min"),
            scenario_pred_mean_2050=("scenario_pred", "mean"),
        )
        .reset_index()
        .sort_values(
            ["region_order", "delta_mean_2050", "scenario_pred_mean_2050", "Province"],
            ascending=[True, False, False, True],
        )
        .reset_index(drop=True)
    )
    order_df["province_order"] = np.arange(len(order_df))
    return order_df


def build_region_guides(province_order_df: pd.DataFrame) -> tuple[list[float], list[tuple[float, str]]]:
    boundaries: list[float] = []
    centers: list[tuple[float, str]] = []

    start_idx = 0
    regions = province_order_df["region"].tolist()
    for idx in range(1, len(regions) + 1):
        if idx == len(regions) or regions[idx] != regions[start_idx]:
            boundaries.append(idx - 0.5)
            centers.append(((start_idx + idx - 1) / 2.0, regions[start_idx]))
            start_idx = idx

    return boundaries[:-1], centers


def summarize_national_delta(plot_df: pd.DataFrame) -> pd.DataFrame:
    return (
        plot_df.groupby(["scenario_id", "statistic", "Year"], dropna=False)
        .agg(delta_mean=("delta_vs_baseline", "mean"))
        .reset_index()
        .sort_values(["scenario_id", "statistic", "Year"])
        .reset_index(drop=True)
    )


def plot_provincial_panel(
    plot_df: pd.DataFrame,
    province_order_df: pd.DataFrame,
    output_path: Path,
    baseline_label: str,
    start_year: int,
    end_year: int,
) -> Path:
    years = list(range(start_year, end_year + 1))
    provinces = province_order_df["Province"].tolist()
    region_boundaries, region_centers = build_region_guides(province_order_df)
    national = summarize_national_delta(plot_df)
    median_df = plot_df[plot_df["statistic"].eq(RX1DAY_MAIN_STATISTIC)].copy()

    abs_limit = float(median_df["delta_vs_baseline"].abs().max())
    abs_limit = max(abs_limit, 1e-6)
    norm = TwoSlopeNorm(vmin=-abs_limit, vcenter=0.0, vmax=abs_limit)
    cmap = mpl.colormaps["RdBu_r"]

    fig = plt.figure(figsize=(21, 14.5), facecolor="white")
    outer_grid = fig.add_gridspec(2, 1, height_ratios=[1.15, 6.6], hspace=0.16)
    ax_top = fig.add_subplot(outer_grid[0, 0])
    heatmap_grid = outer_grid[1, 0].subgridspec(
        1,
        7,
        width_ratios=[0.42, 1, 1, 1, 1, 1, 0.09],
        wspace=0.07,
    )
    region_ax = fig.add_subplot(heatmap_grid[0, 0])
    heat_axes = [fig.add_subplot(heatmap_grid[0, idx]) for idx in range(1, 6)]
    colorbar_ax = fig.add_subplot(heatmap_grid[0, 6])

    for scenario_id in RX1DAY_SCENARIOS:
        color = SCENARIO_PALETTE[scenario_id]
        median_line = national[
            national["scenario_id"].eq(scenario_id) & national["statistic"].eq(RX1DAY_MAIN_STATISTIC)
        ].sort_values("Year")
        p10_line = national[national["scenario_id"].eq(scenario_id) & national["statistic"].eq("p10")].sort_values(
            "Year"
        )
        p90_line = national[national["scenario_id"].eq(scenario_id) & national["statistic"].eq("p90")].sort_values(
            "Year"
        )
        if not p10_line.empty and not p90_line.empty:
            ax_top.fill_between(
                p10_line["Year"],
                p10_line["delta_mean"],
                p90_line["delta_mean"],
                color=color,
                alpha=0.12,
                linewidth=0,
            )
        ax_top.plot(
            median_line["Year"],
            median_line["delta_mean"],
            color=color,
            linewidth=2.3,
            label=SCENARIO_LABELS[scenario_id],
        )

    ax_top.axhline(0, color="#475569", linestyle="--", linewidth=1.1, alpha=0.9)
    ax_top.set_xlim(start_year, end_year)
    ax_top.set_ylabel("Mean \u0394AMR vs baseline\n(percentage points)")
    ax_top.set_xlabel("")
    ax_top.legend(loc="upper left", ncol=5, frameon=False, bbox_to_anchor=(0, 1.15))
    ax_top.spines["top"].set_visible(False)
    ax_top.spines["right"].set_visible(False)
    ax_top.grid(axis="y", color="#e2e8f0", linewidth=0.9)

    year_tick_values = [start_year, end_year]
    for milestone in (2030, 2040):
        if start_year < milestone < end_year:
            year_tick_values.append(milestone)
    year_tick_values = sorted(set(year_tick_values))
    year_tick_positions = [years.index(year) for year in year_tick_values]
    ax_top.set_xticks(year_tick_values)

    region_ax.set_xlim(0, 1)
    region_ax.set_ylim(len(provinces) - 0.5, -0.5)
    region_ax.axis("off")
    region_ax.text(
        0.5,
        1.01,
        "Region",
        transform=region_ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="#475569",
        fontweight="bold",
    )
    for center_y, region_name in region_centers:
        region_ax.text(
            0.5,
            center_y,
            region_name,
            va="center",
            ha="center",
            fontsize=10.5,
            fontweight="bold",
            color=REGION_PALETTE.get(region_name, "#334155"),
        )
    for boundary in region_boundaries:
        region_ax.axhline(boundary, color="#e2e8f0", linewidth=1.2)
    region_ax.axvline(0.98, color="#e2e8f0", linewidth=1.0)

    for ax, scenario_id in zip(heat_axes, RX1DAY_SCENARIOS):
        scenario_df = median_df[median_df["scenario_id"].eq(scenario_id)].copy()
        matrix = (
            scenario_df.pivot_table(index="Province", columns="Year", values="delta_vs_baseline", aggfunc="mean")
            .reindex(index=provinces, columns=years)
        )

        im = ax.imshow(matrix.values, aspect="auto", cmap=cmap, norm=norm, interpolation="nearest")

        for boundary in region_boundaries:
            ax.axhline(boundary, color="white", linewidth=1.4)
        for tick_pos in year_tick_positions:
            ax.axvline(tick_pos - 0.5, color="white", linewidth=0.6, alpha=0.5)

        ax.set_title(SCENARIO_LABELS[scenario_id], fontsize=12, fontweight="bold", color=SCENARIO_PALETTE[scenario_id])
        panel_tick_values = year_tick_values if ax is heat_axes[0] else [year for year in year_tick_values if year != start_year]
        panel_tick_positions = [years.index(year) for year in panel_tick_values]
        ax.set_xticks(panel_tick_positions)
        ax.set_xticklabels(panel_tick_values, rotation=0, fontsize=9)
        ax.set_xlabel("Year")
        ax.tick_params(axis="both", length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

        if ax is heat_axes[0]:
            ax.set_yticks(np.arange(len(provinces)))
            ax.set_yticklabels(provinces, fontsize=9)
            ax.tick_params(axis="y", pad=4)
        else:
            ax.set_yticks([])

    colorbar = fig.colorbar(im, cax=colorbar_ax)
    colorbar.set_label("\u0394AMR vs baseline (percentage points)")

    fig.suptitle(
        f"\u7701\u7ea7\u5c3a\u5ea6\u672a\u6765\u60c5\u666f\u6a21\u62df | {baseline_label}",
        x=0.06,
        y=0.98,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.06,
        0.947,
        "Top: mean provincial effect with p10-p90 uncertainty ribbons. Bottom: province-year heatmaps ordered by macro-region and 2050 average delta.",
        ha="left",
        va="center",
        fontsize=10.5,
        color="#475569",
    )

    fig.subplots_adjust(left=0.06, right=0.95, top=0.88, bottom=0.08)
    fig.savefig(output_path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> int:
    args = parse_args()
    logger, log_path = configure_logger("run_provincial_future_figure")
    logger.info("Log file: %s", log_path)

    region_mapping = load_region_mapping()
    outcome_dir = resolve_results_output_dir(args.outcome)
    compare_dir = outcome_dir / "baseline_mode_compare"
    compare_dir.mkdir(parents=True, exist_ok=True)

    mode_outputs: dict[str, dict[str, str]] = {}

    for baseline_mode in args.baseline_modes:
        baseline_label = BASELINE_MODE_LABELS[baseline_mode]
        mode_dir = outcome_dir / baseline_mode
        projection_path = mode_dir / "projection_outputs" / "future_scenario_projection_panel.csv"
        if not projection_path.exists():
            raise FileNotFoundError(f"Projection panel not found for baseline mode {baseline_mode}: {projection_path}")

        projection_panel = pd.read_csv(projection_path, encoding="utf-8-sig")
        plot_df = prepare_provincial_panel(
            projection_panel=projection_panel,
            region_mapping=region_mapping,
            start_year=args.start_year,
            end_year=args.end_year,
        )
        province_order_df = build_province_order(plot_df=plot_df, end_year=args.end_year)

        provincial_output_dir = mode_dir / "provincial_outputs"
        provincial_figure_dir = mode_dir / "provincial_figures"
        provincial_output_dir.mkdir(parents=True, exist_ok=True)
        provincial_figure_dir.mkdir(parents=True, exist_ok=True)

        order_path = provincial_output_dir / f"province_order_{args.end_year}.csv"
        province_order_df.to_csv(order_path, index=False, encoding="utf-8-sig")

        figure_path = plot_provincial_panel(
            plot_df=plot_df,
            province_order_df=province_order_df,
            output_path=provincial_figure_dir / "provincial_future_scenario_panel.png",
            baseline_label=baseline_label,
            start_year=args.start_year,
            end_year=args.end_year,
        )

        mode_outputs[baseline_mode] = {
            "projection_path": str(projection_path),
            "province_order_path": str(order_path),
            "provincial_future_scenario_panel": str(figure_path),
        }
        logger.info("Provincial figure completed for %s", baseline_mode)

    metadata = {
        "outcome": args.outcome,
        "baseline_modes": args.baseline_modes,
        "start_year": args.start_year,
        "end_year": args.end_year,
        "mapping_path": str(REGION_MAPPING_PATH),
        "mode_outputs": mode_outputs,
        "log_path": str(log_path),
    }
    metadata_path = compare_dir / "provincial_run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Provincial metadata: %s", metadata_path)
    print(f"[done] metadata={metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
