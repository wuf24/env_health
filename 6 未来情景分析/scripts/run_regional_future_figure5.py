from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config_future_scenario_projection import (
    BASELINE_MODE_LABELS,
    DEFAULT_BASELINE_MODES,
    DEFAULT_OUTCOME,
    DEFAULT_SINGLE_OUTCOME_SCALE,
    LAST_OBSERVED_YEAR,
    RESULTS_DIR,
    RX1DAY_MAIN_STATISTIC,
    RX1DAY_SCENARIOS,
    SCENARIO_LABELS,
    resolve_results_output_dir,
)
from future_scenario_common import build_outcome_series, configure_logger, load_base_frame


SECTION_DIR = Path(__file__).resolve().parents[1]
REGION_MAPPING_PATH = SECTION_DIR / "data_processed" / "province_to_region_7zones.csv"


sns.set_theme(style="whitegrid", font="Microsoft YaHei", rc={"axes.unicode_minus": False})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate future scenario projections into Chinese macro-regions.")
    parser.add_argument("--outcome", default=DEFAULT_OUTCOME, help="Outcome folder under results.")
    parser.add_argument(
        "--single-outcome-scale",
        choices=["zscore", "raw"],
        default=DEFAULT_SINGLE_OUTCOME_SCALE,
        help="Outcome scale for rebuilding historical values.",
    )
    parser.add_argument(
        "--baseline-modes",
        nargs="+",
        choices=sorted(BASELINE_MODE_LABELS),
        default=DEFAULT_BASELINE_MODES,
        help="Baseline modes to aggregate and plot.",
    )
    parser.add_argument("--end-year", type=int, default=2050, help="End year used for summary plots.")
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


def build_regional_historical(
    outcome: str,
    single_outcome_scale: str,
    region_mapping: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str]]:
    base_df = load_base_frame()
    outcome_series, outcome_meta = build_outcome_series(base_df, outcome, single_outcome_scale)

    historical = base_df[["Province", "Year"]].copy()
    historical["outcome_actual"] = outcome_series.values
    historical = historical.merge(
        region_mapping.rename(columns={"province": "Province"}),
        on="Province",
        how="left",
        validate="many_to_one",
    )
    missing = historical[historical["region"].isna()]["Province"].dropna().unique().tolist()
    if missing:
        raise ValueError(f"Missing region mapping for provinces: {missing}")

    regional_historical = (
        historical.groupby(["region_order", "region", "region_en", "Year"], dropna=False)
        .agg(
            province_n=("Province", "nunique"),
            outcome_actual_mean=("outcome_actual", "mean"),
        )
        .reset_index()
        .sort_values(["region_order", "Year"])
        .reset_index(drop=True)
    )
    return regional_historical, outcome_meta


def aggregate_projection_to_region(
    projection_panel: pd.DataFrame,
    region_mapping: pd.DataFrame,
    end_year: int,
) -> dict[str, pd.DataFrame]:
    work = projection_panel.merge(
        region_mapping.rename(columns={"province": "Province"}),
        on="Province",
        how="left",
        validate="many_to_one",
    )
    missing = work[work["region"].isna()]["Province"].dropna().unique().tolist()
    if missing:
        raise ValueError(f"Missing region mapping for provinces: {missing}")

    regional_yearly = (
        work.groupby(
            [
                "baseline_mode",
                "baseline_mode_label",
                "region_order",
                "region",
                "region_en",
                "role_id",
                "role_label",
                "model_id",
                "scheme_id",
                "fe_label",
                "scenario_id",
                "scenario_label",
                "scenario_family",
                "statistic",
                "Year",
            ],
            dropna=False,
        )
        .agg(
            province_n=("Province", "nunique"),
            baseline_pred_mean=("baseline_pred", "mean"),
            scenario_adjustment_mean=("scenario_adjustment", "mean"),
            scenario_pred_mean=("scenario_pred", "mean"),
            delta_vs_baseline_mean=("delta_vs_baseline", "mean"),
            rx1day_baseline_mean=("rx1day_baseline", "mean"),
            rx1day_scenario_mean=("rx1day_scenario", "mean"),
        )
        .reset_index()
        .sort_values(["region_order", "role_id", "scenario_id", "statistic", "Year"])
        .reset_index(drop=True)
    )

    region_end = regional_yearly[regional_yearly["Year"].eq(end_year)].copy()
    region_end["baseline_pred_mean_at_end"] = region_end["baseline_pred_mean"]
    region_end["delta_vs_baseline_at_end"] = region_end["delta_vs_baseline_mean"]

    return {
        "regional_yearly": regional_yearly,
        f"region_summary_{end_year}": region_end,
    }


def plot_regional_figure5_grid(
    regional_historical: pd.DataFrame,
    regional_yearly: pd.DataFrame,
    output_path: Path,
    baseline_label: str,
    y_label: str,
    end_year: int,
) -> Path:
    plot_df = regional_yearly[regional_yearly["role_id"].eq("main_model")].copy()
    hist = regional_historical.sort_values(["region_order", "Year"]).copy()
    regions = (
        hist[["region_order", "region"]]
        .drop_duplicates()
        .sort_values("region_order")
        .reset_index(drop=True)
    )

    palette = {
        "ssp119": "#1b9e77",
        "ssp126": "#4daf4a",
        "ssp245": "#377eb8",
        "ssp370": "#ff7f00",
        "ssp585": "#d7301f",
    }

    fig, axes = plt.subplots(4, 2, figsize=(15, 16), sharex=True, sharey=False)
    axes_flat = axes.flatten()

    for idx, row in regions.iterrows():
        region = row["region"]
        ax = axes_flat[idx]
        hist_sub = hist[hist["region"].eq(region)].sort_values("Year")
        plot_sub = plot_df[plot_df["region"].eq(region)].copy()

        ax.plot(
            hist_sub["Year"],
            hist_sub["outcome_actual_mean"],
            color="black",
            linewidth=2.3,
            label="Historical observed",
        )

        baseline = plot_sub[plot_sub["scenario_id"].eq("baseline_ets")].sort_values("Year")
        baseline_full = pd.concat(
            [
                hist_sub[["Year", "outcome_actual_mean"]].rename(columns={"outcome_actual_mean": "scenario_pred_mean"}),
                baseline[["Year", "scenario_pred_mean"]],
            ],
            ignore_index=True,
        )
        ax.plot(
            baseline_full["Year"],
            baseline_full["scenario_pred_mean"],
            color="#111111",
            linestyle="--",
            linewidth=1.8,
            label=baseline_label,
        )

        history_prefix = hist_sub[["Year", "outcome_actual_mean"]].rename(
            columns={"outcome_actual_mean": "scenario_pred_mean"}
        )
        for scenario_id in RX1DAY_SCENARIOS:
            median = plot_sub[
                plot_sub["scenario_id"].eq(scenario_id) & plot_sub["statistic"].eq(RX1DAY_MAIN_STATISTIC)
            ].sort_values("Year")
            if median.empty:
                continue

            p10 = plot_sub[
                plot_sub["scenario_id"].eq(scenario_id) & plot_sub["statistic"].eq("p10")
            ].sort_values("Year")
            p90 = plot_sub[
                plot_sub["scenario_id"].eq(scenario_id) & plot_sub["statistic"].eq("p90")
            ].sort_values("Year")

            median_full = pd.concat([history_prefix, median[["Year", "scenario_pred_mean"]]], ignore_index=True)
            if not p10.empty and not p90.empty:
                p10_full = pd.concat([history_prefix, p10[["Year", "scenario_pred_mean"]]], ignore_index=True)
                p90_full = pd.concat([history_prefix, p90[["Year", "scenario_pred_mean"]]], ignore_index=True)
                ax.fill_between(
                    p10_full["Year"],
                    p10_full["scenario_pred_mean"],
                    p90_full["scenario_pred_mean"],
                    color=palette[scenario_id],
                    alpha=0.12,
                )
            ax.plot(
                median_full["Year"],
                median_full["scenario_pred_mean"],
                color=palette[scenario_id],
                linewidth=1.9,
                label=SCENARIO_LABELS[scenario_id],
            )

        ax.axvline(LAST_OBSERVED_YEAR, color="#666666", linestyle=":", linewidth=1.0)
        ax.set_title(region)
        ax.set_xlim(hist["Year"].min(), end_year)
        ax.set_ylabel(y_label)

    for j in range(len(regions), len(axes_flat)):
        axes_flat[j].axis("off")

    handles, labels = axes_flat[0].get_legend_handles_labels()
    uniq: dict[str, object] = {}
    for handle, label in zip(handles, labels):
        if label not in uniq:
            uniq[label] = handle
    fig.legend(
        uniq.values(),
        uniq.keys(),
        loc="upper center",
        ncol=4,
        frameon=True,
        bbox_to_anchor=(0.5, 0.985),
    )
    fig.suptitle(f"Regional Figure 5 style trajectories: {baseline_label}", y=0.995, fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_regional_delta_heatmap(
    regional_yearly: pd.DataFrame,
    output_path: Path,
    baseline_label: str,
    end_year: int,
) -> Path:
    plot_df = regional_yearly[
        regional_yearly["role_id"].eq("main_model")
        & regional_yearly["Year"].eq(end_year)
        & regional_yearly["statistic"].eq(RX1DAY_MAIN_STATISTIC)
        & ~regional_yearly["scenario_id"].eq("baseline_ets")
    ].copy()

    heatmap_data = (
        plot_df.pivot_table(
            index=["region_order", "region"],
            columns="scenario_id",
            values="delta_vs_baseline_mean",
            aggfunc="mean",
        )
        .reindex(columns=RX1DAY_SCENARIOS)
        .sort_index(level=0)
    )
    heatmap_data.index = [region for _, region in heatmap_data.index]
    heatmap_data.columns = [SCENARIO_LABELS[item] for item in heatmap_data.columns]

    fig, ax = plt.subplots(figsize=(10.5, 6))
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt=".2f",
        cmap="RdYlBu_r",
        center=0,
        linewidths=0.5,
        cbar_kws={"label": f"Difference vs {baseline_label} in {end_year}"},
        ax=ax,
    )
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Region")
    ax.set_title(f"Regional {end_year} delta heatmap relative to {baseline_label}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> int:
    args = parse_args()
    logger, log_path = configure_logger("run_regional_future_figure5")
    logger.info("Log file: %s", log_path)

    region_mapping = load_region_mapping()
    regional_historical, outcome_meta = build_regional_historical(
        outcome=args.outcome,
        single_outcome_scale=args.single_outcome_scale,
        region_mapping=region_mapping,
    )
    y_label = "Aggregate antibiotic resistance (%)" if args.outcome == "AMR_AGG_RAW" else "Predicted AMR"

    outcome_dir = resolve_results_output_dir(args.outcome)
    compare_dir = outcome_dir / "baseline_mode_compare"
    compare_dir.mkdir(parents=True, exist_ok=True)

    compare_tables: list[pd.DataFrame] = []
    mode_outputs: dict[str, dict[str, str]] = {}

    for baseline_mode in args.baseline_modes:
        baseline_label = BASELINE_MODE_LABELS[baseline_mode]
        mode_dir = outcome_dir / baseline_mode
        projection_path = mode_dir / "projection_outputs" / "future_scenario_projection_panel.csv"
        if not projection_path.exists():
            raise FileNotFoundError(f"Projection panel not found for baseline mode {baseline_mode}: {projection_path}")

        projection_panel = pd.read_csv(projection_path, encoding="utf-8-sig")
        aggregated = aggregate_projection_to_region(
            projection_panel=projection_panel,
            region_mapping=region_mapping,
            end_year=args.end_year,
        )

        regional_output_dir = mode_dir / "regional_outputs"
        regional_figure_dir = mode_dir / "regional_figures"
        regional_output_dir.mkdir(parents=True, exist_ok=True)
        regional_figure_dir.mkdir(parents=True, exist_ok=True)

        historical_out = regional_historical.copy()
        historical_out["baseline_mode"] = baseline_mode
        historical_out["baseline_mode_label"] = baseline_label
        historical_path = regional_output_dir / "regional_historical.csv"
        historical_out.to_csv(historical_path, index=False, encoding="utf-8-sig")

        output_paths: dict[str, str] = {"regional_historical": str(historical_path)}
        for name, df in aggregated.items():
            out_path = regional_output_dir / f"{name}.csv"
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            output_paths[name] = str(out_path)

        region_grid = plot_regional_figure5_grid(
            regional_historical=regional_historical,
            regional_yearly=aggregated["regional_yearly"],
            output_path=regional_figure_dir / "regional_figure5_grid.png",
            baseline_label=baseline_label,
            y_label=y_label,
            end_year=args.end_year,
        )
        region_heatmap = plot_regional_delta_heatmap(
            regional_yearly=aggregated["regional_yearly"],
            output_path=regional_figure_dir / f"regional_delta_{args.end_year}_heatmap.png",
            baseline_label=baseline_label,
            end_year=args.end_year,
        )

        mode_outputs[baseline_mode] = {
            **output_paths,
            "regional_figure5_grid": str(region_grid),
            "regional_delta_heatmap": str(region_heatmap),
        }

        compare_tables.append(aggregated[f"region_summary_{args.end_year}"])
        logger.info("Regional outputs completed for %s", baseline_mode)

    compare_summary = pd.concat(compare_tables, ignore_index=True)
    compare_summary_path = compare_dir / f"regional_summary_{args.end_year}_compare.csv"
    compare_summary.to_csv(compare_summary_path, index=False, encoding="utf-8-sig")

    metadata = {
        "outcome": args.outcome,
        "mapping_path": str(REGION_MAPPING_PATH),
        "baseline_modes": args.baseline_modes,
        "end_year": args.end_year,
        "mode_outputs": mode_outputs,
        "compare_summary": str(compare_summary_path),
        "log_path": str(log_path),
        "region_count": int(region_mapping["region"].nunique()),
    }
    metadata_path = compare_dir / "regional_run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Regional compare summary: %s", compare_summary_path)
    print(f"[done] regional_compare={compare_summary_path}")
    print(f"[done] metadata={metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
