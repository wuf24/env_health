from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config_future_scenario_projection import (
    ACTIVE_SCENARIOS,
    BASELINE_MODE_DESCRIPTIONS,
    BASELINE_MODE_LABELS,
    CCKP_PROVINCE_TO_CN,
    CONTROLLED_FUTURE_VARIABLES,
    DEFAULT_BASELINE_MODES,
    DEFAULT_MODEL_ROLES,
    DEFAULT_MODEL_SOURCE_OUTCOME,
    DEFAULT_OUTCOME,
    DEFAULT_SINGLE_OUTCOME_SCALE,
    FUTURE_END_YEAR,
    FUTURE_START_YEAR,
    LAST_OBSERVED_YEAR,
    MORTALITY_MODULE,
    RESULTS_DIR,
    RX1DAY_MAIN_STATISTIC,
    RX1DAY_SCENARIOS,
    RX1DAY_STATISTICS,
    RX1DAY_VARIABLE_NAME,
    SCENARIO_LABELS,
    ensure_directories,
    resolve_results_output_dir,
)
from future_scenario_common import (
    align_future_rx1day_to_history,
    build_baseline_covariate_forecasts,
    build_outcome_series,
    build_x_driven_baseline_outcome,
    configure_logger,
    fit_panel_association_model,
    forecast_panel_value,
    load_base_frame,
    load_future_rx1day_panel,
    load_selected_models,
)


sns.set_theme(style="whitegrid", font="Microsoft YaHei", rc={"axes.unicode_minus": False})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 Lancet 风格运行未来情景预测框架。")
    parser.add_argument("--outcome", default=DEFAULT_OUTCOME, help="默认先跑 AMR_AGG。")
    parser.add_argument(
        "--model-source-outcome",
        default=DEFAULT_MODEL_SOURCE_OUTCOME,
        help="从 5 反事实推演 的哪个 outcome 目录读取已筛好的 selected_models。",
    )
    parser.add_argument(
        "--single-outcome-scale",
        choices=["zscore", "raw"],
        default=DEFAULT_SINGLE_OUTCOME_SCALE,
        help="当 outcome 为单一 AMR 指标时，使用 zscore 或 raw。",
    )
    parser.add_argument("--start-year", type=int, default=FUTURE_START_YEAR, help="未来投影起始年份。")
    parser.add_argument("--end-year", type=int, default=FUTURE_END_YEAR, help="未来投影结束年份。")
    parser.add_argument(
        "--roles",
        nargs="+",
        default=DEFAULT_MODEL_ROLES,
        help="读取 5 反事实推演 中已选好的哪些模型角色。",
    )
    parser.add_argument(
        "--baseline-modes",
        nargs="+",
        choices=sorted(BASELINE_MODE_LABELS),
        default=DEFAULT_BASELINE_MODES,
        help="Run one or both baseline constructions.",
    )
    return parser.parse_args()


def build_scenario_dict(baseline_mode: str) -> dict[str, dict[str, object]]:
    scenario_lookup: dict[str, dict[str, object]] = {}
    for item in ACTIVE_SCENARIOS:
        scenario = dict(item)
        if scenario["scenario_id"] == "baseline_ets":
            if baseline_mode == "x_driven":
                scenario["scenario_label"] = "Baseline (X-driven)"
                scenario["description"] = BASELINE_MODE_DESCRIPTIONS["x_driven"]
            else:
                scenario["scenario_label"] = "Baseline (ETS)"
                scenario["description"] = BASELINE_MODE_DESCRIPTIONS["lancet_ets"]
        scenario_lookup[str(scenario["scenario_id"])] = scenario
    return scenario_lookup


def build_baseline_outcome_future(
    baseline_mode: str,
    fit_bundle: dict[str, object],
    baseline_covariate_forecasts: dict[str, pd.Series],
    future_years: list[int],
    logger,
) -> tuple[pd.Series, pd.DataFrame]:
    if baseline_mode == "lancet_ets":
        outcome_history = fit_bundle["history_outcome"].reset_index()
        baseline_outcome_df, method_df = forecast_panel_value(
            df=outcome_history.rename(columns={"outcome_actual": "value"}),
            value_col="value",
            future_years=future_years,
            logger=logger,
        )
        baseline_future = baseline_outcome_df.set_index(["Province", "Year"])["value"].sort_index()
        method_df = method_df.copy()
        method_df["baseline_mode"] = baseline_mode
        return baseline_future, method_df

    if baseline_mode == "x_driven":
        return build_x_driven_baseline_outcome(
            fit_bundle=fit_bundle,
            baseline_covariate_forecasts=baseline_covariate_forecasts,
            future_years=future_years,
            logger=logger,
        )

    raise ValueError(f"Unknown baseline mode: {baseline_mode}")


def apply_scenario_overrides(baseline_path: pd.Series, override: dict[str, object] | None) -> pd.Series:
    if not override:
        return baseline_path.copy()

    mode = str(override.get("mode", "")).lower().strip()
    value = override.get("value")
    if value is None:
        return baseline_path.copy()

    if mode == "scale":
        return baseline_path * float(value)
    if mode == "delta":
        return baseline_path + float(value)
    if mode == "set":
        return pd.Series(float(value), index=baseline_path.index, dtype=float)
    if mode == "cap":
        return baseline_path.clip(upper=float(value))

    return baseline_path.copy()


def build_external_rx1day_lookup(future_rx1day_aligned: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    lookup: dict[tuple[str, str], pd.Series] = {}
    for (scenario, statistic), sub in future_rx1day_aligned.groupby(["scenario", "statistic"], dropna=False):
        series = sub.set_index(["Province", "Year"])["rx1day_aligned"].sort_index()
        lookup[(str(scenario), str(statistic))] = series
    return lookup


def simulate_future_scenarios(
    fit_bundle: dict[str, object],
    baseline_outcome_future: pd.Series,
    baseline_covariate_forecasts: dict[str, pd.Series],
    scenario_lookup: dict[str, dict[str, object]],
    external_rx1day_lookup: dict[tuple[str, str], pd.Series],
) -> pd.DataFrame:
    selected_model = fit_bundle["selected_model"]
    result = fit_bundle["result"]
    transform_stats: dict[str, dict[str, float]] = fit_bundle["transform_stats"]

    rows: list[pd.DataFrame] = []
    base_index = baseline_outcome_future.index

    for scenario_id, scenario_meta in scenario_lookup.items():
        statistics = ["baseline"] if scenario_id == "baseline_ets" else list(RX1DAY_STATISTICS)
        for statistic in statistics:
            delta_total = pd.Series(0.0, index=base_index, dtype=float)
            rx1day_baseline = None
            rx1day_scenario = None

            for variable in selected_model.variables:
                baseline_path = baseline_covariate_forecasts[variable].reindex(base_index)
                scenario_path = baseline_path.copy()

                if variable == RX1DAY_VARIABLE_NAME and scenario_meta.get("rx1day_source_scenario"):
                    external_key = (str(scenario_meta["rx1day_source_scenario"]), str(statistic))
                    external_path = external_rx1day_lookup[external_key].reindex(base_index)
                    scenario_path = external_path.fillna(baseline_path)

                if variable in CONTROLLED_FUTURE_VARIABLES:
                    override = scenario_meta.get("adjustments", {}).get(variable)
                    scenario_path = apply_scenario_overrides(scenario_path, override)

                std = float(transform_stats[variable]["std"])
                if std == 0:
                    delta_z = pd.Series(0.0, index=base_index, dtype=float)
                else:
                    delta_z = (scenario_path - baseline_path) / std

                beta = float(result.params.get(variable, 0.0))
                delta_total = delta_total.add(beta * delta_z, fill_value=0.0)

                if variable == RX1DAY_VARIABLE_NAME:
                    rx1day_baseline = baseline_path
                    rx1day_scenario = scenario_path

            scenario_pred = baseline_outcome_future.add(delta_total, fill_value=0.0)
            out = pd.DataFrame(index=base_index).reset_index()
            out["role_id"] = selected_model.role_id
            out["role_label"] = selected_model.role_label
            out["model_id"] = selected_model.model_id
            out["scheme_id"] = selected_model.scheme_id
            out["scheme_source"] = selected_model.scheme_source
            out["fe_label"] = selected_model.fe_label
            out["scenario_id"] = scenario_id
            out["scenario_label"] = scenario_meta["scenario_label"]
            out["scenario_family"] = scenario_meta["scenario_family"]
            out["scenario_description"] = scenario_meta["description"]
            out["statistic"] = statistic
            out["baseline_pred"] = baseline_outcome_future.reindex(base_index).values
            out["scenario_adjustment"] = delta_total.reindex(base_index).values
            out["scenario_pred"] = scenario_pred.reindex(base_index).values
            out["delta_vs_baseline"] = out["scenario_pred"] - out["baseline_pred"]
            if rx1day_baseline is not None:
                out["rx1day_baseline"] = rx1day_baseline.reindex(base_index).values
                out["rx1day_scenario"] = rx1day_scenario.reindex(base_index).values
                out["rx1day_delta"] = out["rx1day_scenario"] - out["rx1day_baseline"]
            else:
                out["rx1day_baseline"] = pd.NA
                out["rx1day_scenario"] = pd.NA
                out["rx1day_delta"] = pd.NA
            rows.append(out)

    projection_panel = pd.concat(rows, ignore_index=True)
    projection_panel = projection_panel.sort_values(["role_id", "scenario_id", "statistic", "Province", "Year"])
    return projection_panel.reset_index(drop=True)


def summarize_future_projection(
    historical_observed: pd.DataFrame,
    projection_panel: pd.DataFrame,
    end_year: int,
) -> dict[str, pd.DataFrame]:
    baseline_mode = str(projection_panel["baseline_mode"].iloc[0])
    baseline_mode_label = str(projection_panel["baseline_mode_label"].iloc[0])

    historical_national = (
        historical_observed.groupby("Year", dropna=False)
        .agg(
            province_n=("Province", "nunique"),
            outcome_actual_mean=("outcome_actual", "mean"),
        )
        .reset_index()
    )
    historical_national["baseline_mode"] = baseline_mode
    historical_national["baseline_mode_label"] = baseline_mode_label

    national_yearly = (
        projection_panel.groupby(
            [
                "baseline_mode",
                "baseline_mode_label",
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
    )

    national_end = national_yearly[national_yearly["Year"].eq(end_year)].copy()
    national_end["baseline_pred_mean_at_end"] = national_end["baseline_pred_mean"]
    national_end["delta_vs_baseline_at_end"] = national_end["delta_vs_baseline_mean"]

    last_historical_mean = float(historical_national.sort_values("Year")["outcome_actual_mean"].iloc[-1])
    national_end["delta_vs_last_observed"] = national_end["scenario_pred_mean"] - last_historical_mean

    province_end = projection_panel[projection_panel["Year"].eq(end_year)].copy()

    return {
        "historical_national": historical_national,
        "national_yearly": national_yearly,
        f"scenario_summary_{end_year}": national_end,
        f"province_projection_{end_year}": province_end,
    }


def plot_national_yearly_main_model(
    historical_national: pd.DataFrame,
    national_yearly: pd.DataFrame,
    output_path: Path,
    end_year: int,
    y_label: str,
    last_observed_year: int,
    baseline_label: str,
) -> Path:
    plot_df = national_yearly[national_yearly["role_id"].eq("main_model")].copy()

    fig, ax = plt.subplots(figsize=(12, 6.5))
    hist = historical_national.sort_values("Year")
    ax.plot(hist["Year"], hist["outcome_actual_mean"], color="black", linewidth=2.5, label="Historical observed")

    baseline = plot_df[plot_df["scenario_id"].eq("baseline_ets")].sort_values("Year")
    ax.plot(
        baseline["Year"],
        baseline["scenario_pred_mean"],
        color="#111111",
        linestyle="--",
        linewidth=2.0,
        label=baseline_label,
    )

    palette = {
        "ssp119": "#1b9e77",
        "ssp126": "#4daf4a",
        "ssp245": "#377eb8",
        "ssp370": "#ff7f00",
        "ssp585": "#d7301f",
    }

    for scenario_id in RX1DAY_SCENARIOS:
        median = plot_df[
            plot_df["scenario_id"].eq(scenario_id) & plot_df["statistic"].eq(RX1DAY_MAIN_STATISTIC)
        ].sort_values("Year")
        if median.empty:
            continue

        p10 = plot_df[
            plot_df["scenario_id"].eq(scenario_id) & plot_df["statistic"].eq("p10")
        ].sort_values("Year")
        p90 = plot_df[
            plot_df["scenario_id"].eq(scenario_id) & plot_df["statistic"].eq("p90")
        ].sort_values("Year")

        color = palette[scenario_id]
        history_prefix = hist[["Year", "outcome_actual_mean"]].rename(columns={"outcome_actual_mean": "scenario_pred_mean"})
        median_full = pd.concat([history_prefix, median[["Year", "scenario_pred_mean"]]], ignore_index=True)
        if not p10.empty and not p90.empty:
            p10_full = pd.concat([history_prefix, p10[["Year", "scenario_pred_mean"]]], ignore_index=True)
            p90_full = pd.concat([history_prefix, p90[["Year", "scenario_pred_mean"]]], ignore_index=True)
            ax.fill_between(
                p10_full["Year"],
                p10_full["scenario_pred_mean"],
                p90_full["scenario_pred_mean"],
                color=color,
                alpha=0.15,
            )
        ax.plot(
            median_full["Year"],
            median_full["scenario_pred_mean"],
            color=color,
            linewidth=2.0,
            label=SCENARIO_LABELS[scenario_id],
        )

    ax.axvline(last_observed_year, color="#666666", linestyle=":", linewidth=1.2)
    ax.set_xlim(hist["Year"].min(), end_year)
    ax.set_xlabel("Year")
    ax.set_ylabel(y_label)
    ax.set_title("Main model: national AMR trajectory with historical observations and future scenarios")
    ax.legend(ncol=2, frameon=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_scenario_delta_bar(
    national_yearly: pd.DataFrame,
    output_path: Path,
    end_year: int,
    baseline_label: str,
) -> Path:
    plot_df = national_yearly[
        national_yearly["role_id"].eq("main_model")
        & national_yearly["Year"].eq(end_year)
        & national_yearly["statistic"].eq(RX1DAY_MAIN_STATISTIC)
        & ~national_yearly["scenario_id"].eq("baseline_ets")
    ].copy()

    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(
        data=plot_df,
        x="scenario_label",
        y="delta_vs_baseline_mean",
        hue="scenario_label",
        dodge=False,
        legend=False,
        ax=ax,
        palette="RdYlBu_r",
    )
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xlabel("Scenario")
    ax.set_ylabel(f"Difference vs {baseline_label} in {end_year}")
    ax.set_title(f"Main model: {end_year} deltas relative to {baseline_label}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_figure5_style_main(
    historical_national: pd.DataFrame,
    national_yearly: pd.DataFrame,
    output_path: Path,
    end_year: int,
    y_label: str,
    last_observed_year: int,
    baseline_label: str,
) -> Path:
    plot_df = national_yearly[national_yearly["role_id"].eq("main_model")].copy()
    hist = historical_national.sort_values("Year")

    palette = {
        "baseline_ets": "#111111",
        "ssp119": "#1b9e77",
        "ssp126": "#4daf4a",
        "ssp245": "#377eb8",
        "ssp370": "#ff7f00",
        "ssp585": "#d7301f",
    }

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), gridspec_kw={"height_ratios": [3.2, 1.4]})
    ax_top, ax_bottom = axes

    ax_top.plot(hist["Year"], hist["outcome_actual_mean"], color="black", linewidth=2.6, label="Actual")

    baseline = plot_df[plot_df["scenario_id"].eq("baseline_ets")].sort_values("Year")
    baseline_full = pd.concat(
        [
            hist[["Year", "outcome_actual_mean"]].rename(columns={"outcome_actual_mean": "scenario_pred_mean"}),
            baseline[["Year", "scenario_pred_mean"]],
        ],
        ignore_index=True,
    )
    ax_top.plot(
        baseline_full["Year"],
        baseline_full["scenario_pred_mean"],
        color=palette["baseline_ets"],
        linestyle="--",
        linewidth=2.0,
        label=baseline_label,
    )

    for scenario_id in RX1DAY_SCENARIOS:
        median = plot_df[
            plot_df["scenario_id"].eq(scenario_id) & plot_df["statistic"].eq(RX1DAY_MAIN_STATISTIC)
        ].sort_values("Year")
        if median.empty:
            continue
        p10 = plot_df[
            plot_df["scenario_id"].eq(scenario_id) & plot_df["statistic"].eq("p10")
        ].sort_values("Year")
        p90 = plot_df[
            plot_df["scenario_id"].eq(scenario_id) & plot_df["statistic"].eq("p90")
        ].sort_values("Year")

        history_prefix = hist[["Year", "outcome_actual_mean"]].rename(columns={"outcome_actual_mean": "scenario_pred_mean"})
        median_full = pd.concat([history_prefix, median[["Year", "scenario_pred_mean"]]], ignore_index=True)
        p10_full = pd.concat([history_prefix, p10[["Year", "scenario_pred_mean"]]], ignore_index=True)
        p90_full = pd.concat([history_prefix, p90[["Year", "scenario_pred_mean"]]], ignore_index=True)

        ax_top.fill_between(
            p10_full["Year"],
            p10_full["scenario_pred_mean"],
            p90_full["scenario_pred_mean"],
            color=palette[scenario_id],
            alpha=0.12,
        )
        ax_top.plot(
            median_full["Year"],
            median_full["scenario_pred_mean"],
            color=palette[scenario_id],
            linewidth=2.0,
            label=SCENARIO_LABELS[scenario_id],
        )

    ax_top.axvline(last_observed_year, color="#666666", linestyle=":", linewidth=1.2)
    ax_top.set_xlim(hist["Year"].min(), end_year)
    ax_top.set_ylabel(y_label)
    ax_top.set_title("Figure 5 style: national antibiotic resistance under future R1xday scenarios")
    ax_top.legend(ncol=3, frameon=True, fontsize=9)

    end_plot = plot_df[
        plot_df["Year"].eq(end_year)
        & plot_df["statistic"].eq(RX1DAY_MAIN_STATISTIC)
        & ~plot_df["scenario_id"].eq("baseline_ets")
    ].copy()
    end_plot = end_plot.sort_values("delta_vs_baseline_mean", ascending=False)
    sns.barplot(
        data=end_plot,
        x="scenario_label",
        y="delta_vs_baseline_mean",
        hue="scenario_label",
        dodge=False,
        legend=False,
        ax=ax_bottom,
        palette="RdYlBu_r",
    )
    ax_bottom.axhline(0, color="black", linewidth=1)
    ax_bottom.set_xlabel("Future scenario")
    ax_bottom.set_ylabel(f"Difference vs {baseline_label} in {end_year}")
    ax_bottom.set_title(f"{end_year} comparison against {baseline_label}")

    fig.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return output_path


def write_projection_notes(
    output_dir: Path,
    outcome_label: str,
    model_source_outcome: str,
    roles: list[str],
    start_year: int,
    end_year: int,
    baseline_mode: str,
    baseline_label: str,
    baseline_description: str,
) -> Path:
    if baseline_mode == "lancet_ets":
        baseline_formula = [
            "```text",
            "Y_it = alpha_i + lambda_t + sum_k beta_k Z_itk + epsilon_it",
            "Y^base_it = ETS(Y_i, historical series)",
            "Delta^scenario_it = sum_k beta_k * (Z^scenario_itk - Z^base_itk)",
            "Y^scenario_it = Y^base_it + Delta^scenario_it",
            "```",
        ]
        interpretation = [
            "- This version is closest to Lancet 2023: future baseline comes from ETS on AMR itself.",
            "- Future R1xday scenarios are layered on top of ETS(AMR) as increments.",
            "- The curve shape is therefore more strongly influenced by historical AMR inertia.",
        ]
    else:
        baseline_formula = [
            "```text",
            "Y_it = alpha_i + lambda_t + sum_k beta_k Z_itk + epsilon_it",
            "Y^base_it = alpha_i* + lambda_t* + sum_k beta_k Z^base_itk",
            "Y^scenario_it = alpha_i* + lambda_t* + sum_k beta_k Z^scenario_itk",
            "If only R1xday is controlled:",
            "Y^scenario_it = Y^base_it + beta_R * (R1xday^scenario_it - R1xday^base_it)",
            "```",
        ]
        interpretation = [
            "- This is a simplified X-driven / Nature-like baseline: future baseline is driven by future covariate paths.",
            "- R1xday^base_it and other baseline covariates first follow their own ETS extensions, then are plugged back into the historical panel model.",
            "- The future trajectory is therefore more responsive to covariate path divergence.",
        ]

    lines = [
        f"# {outcome_label} future projection notes",
        "",
        f"## Version: {baseline_label}",
        "",
        f"- baseline_mode: `{baseline_mode}`",
        f"- meaning: {baseline_description}",
        f"- model source: `5 ?????/results/{model_source_outcome}/model_screening/selected_models.csv`",
        f"- projection window: `{start_year}-{end_year}`",
        f"- roles: `{', '.join(roles)}`",
        "- external scenario variable: `R1xday`",
        "- climate scenarios: annual CCKP `rx1day` for `ssp119 / ssp126 / ssp245 / ssp370 / ssp585`",
        "- uncertainty paths: `median / p10 / p90`",
        "- national result rule: project province-level AMR first, then take arithmetic mean across provinces without weighting.",
        "",
        "## Workflow",
        "",
        "1. Reuse the selected historical province-year models from `5 ?????`.",
        "2. Re-estimate the historical panel coefficients and keep the historical scaling of covariates.",
        "3. Only let `R1xday` vary by future scenario; all other covariates follow baseline paths.",
        "4. Project AMR province by province, then average across provinces to obtain national trajectories and Figure-5-style outputs.",
        "",
        "## Formula",
        "",
        *baseline_formula,
        "",
        "## Interpretation",
        "",
        *interpretation,
        "",
        "## Mortality extension",
        "",
        "- The current repository still stops at antibiotic resistance rather than attributable deaths.",
        "- If infection deaths and RR are added later, the Lancet-style PAF formula can be appended:",
        "",
        "```text",
        "PAF = p (RR - 1) / [1 + p (RR - 1)]",
        "```",
    ]

    output_path = output_dir / "projection_notes.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def write_baseline_comparison_notes(
    output_dir: Path,
    outcome_label: str,
    generated_modes: list[str],
    start_year: int,
    end_year: int,
) -> Path:
    lines = [
        f"# {outcome_label} baseline comparison",
        "",
        "## Generated versions",
        "",
        *[f"- `{mode}`: {BASELINE_MODE_LABELS[mode]}." for mode in generated_modes],
        "",
        "## Core difference",
        "",
        "- `lancet_ets`: future baseline comes from ETS on AMR itself, then future R1xday deltas are added.",
        "- `x_driven`: future baseline comes from future covariate paths plugged back into the historical panel model.",
        "",
        "## When to look at which version",
        "",
        "- Use `lancet_ets` when you want the closest implementation of the Lancet phrase 'baseline scenario continued at current rates, as estimated by ETS models'.",
        "- Use `x_driven` when you want future R1xday paths to play a larger role in shaping future AMR trajectories.",
        "",
        "## Current scope",
        "",
        f"- projection window: `{start_year}-{end_year}`",
        "- only `R1xday` is varied by future scenario at this stage",
        "- national results remain arithmetic means across province-level AMR projections",
        "- the x-driven version is still a simplified Nature-like baseline rather than the full spatiotemporal Bayesian model",
    ]
    output_path = output_dir / "baseline_mode_comparison.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def maybe_run_mortality_scaffold(logger, projection_output_dir: Path) -> Path | None:
    if not MORTALITY_MODULE.get("enabled"):
        return None

    lines = [
        "# Mortality Module Placeholder",
        "",
        "The mortality module is not executed yet because province-level infection deaths and RR inputs are still missing.",
        f"- enabled={MORTALITY_MODULE.get('enabled')}",
        f"- infection_deaths_path={MORTALITY_MODULE.get('infection_deaths_path')}",
        f"- relative_risk={MORTALITY_MODULE.get('relative_risk')}",
    ]
    output_path = projection_output_dir / "mortality_module_placeholder.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Mortality scaffold note written to %s", output_path)
    return output_path


def enrich_baseline_method_snapshot(
    baseline_mode: str,
    baseline_method_df: pd.DataFrame,
    fit_bundle: dict[str, object],
) -> pd.DataFrame:
    selected_model = fit_bundle["selected_model"]
    out = baseline_method_df.copy()
    if out.empty:
        out = pd.DataFrame([{}])

    out["baseline_mode"] = baseline_mode
    out["baseline_mode_label"] = BASELINE_MODE_LABELS[baseline_mode]
    out["role_id"] = selected_model.role_id
    out["role_label"] = selected_model.role_label
    out["model_id"] = selected_model.model_id
    out["scheme_id"] = selected_model.scheme_id
    if "component" not in out.columns:
        out["component"] = "baseline_outcome"
    if "method" not in out.columns:
        out["method"] = out["ets_method"] if "ets_method" in out.columns else pd.NA
    return out


def main() -> int:
    args = parse_args()
    ensure_directories()
    logger, log_path = configure_logger("run_future_scenario_projection")
    logger.info("Log file: %s", log_path)

    if args.start_year > args.end_year:
        raise ValueError("start-year cannot be greater than end-year")

    requested_modes = list(dict.fromkeys(args.baseline_modes))
    future_years = list(range(args.start_year, args.end_year + 1))
    y_label = "Aggregate antibiotic resistance (%)" if args.outcome == "AMR_AGG_RAW" else "Predicted AMR"

    base_df = load_base_frame()
    outcome_series, outcome_meta = build_outcome_series(base_df, args.outcome, args.single_outcome_scale)
    selected_models = load_selected_models(args.model_source_outcome, roles=args.roles)

    union_vars = sorted({var for model in selected_models for var in model.variables})
    logger.info("Selected model roles: %s", [model.role_id for model in selected_models])
    logger.info("Union variables: %s", union_vars)
    logger.info("Baseline modes: %s", requested_modes)

    historical_outcome_df = base_df[["Province", "Year"]].copy()
    historical_outcome_df["outcome_actual"] = outcome_series.values

    baseline_covariate_forecasts, covariate_ets_methods = build_baseline_covariate_forecasts(
        base_df=base_df,
        variables=union_vars,
        future_years=future_years,
        logger=logger,
    )

    future_rx1day_raw = load_future_rx1day_panel()
    future_rx1day_aligned, rx1day_bias_table = align_future_rx1day_to_history(
        future_df=future_rx1day_raw,
        historical_df=base_df,
        logger=logger,
    )
    future_rx1day_aligned = future_rx1day_aligned[
        future_rx1day_aligned["Year"].between(args.start_year, args.end_year)
    ].copy()
    external_rx1day_lookup = build_external_rx1day_lookup(future_rx1day_aligned)

    fit_records: list[dict[str, object]] = []
    coefficient_rows: list[pd.DataFrame] = []
    for selected_model in selected_models:
        fit_bundle = fit_panel_association_model(base_df, outcome_series, outcome_meta["outcome_label"], selected_model)
        beta_df = fit_bundle["result"].params.rename("coef").reset_index().rename(columns={"index": "predictor"})
        beta_df["role_id"] = selected_model.role_id
        beta_df["role_label"] = selected_model.role_label
        beta_df["scheme_id"] = selected_model.scheme_id
        coefficient_rows.append(beta_df)
        fit_records.append({"selected_model": selected_model, "fit_bundle": fit_bundle})

    outcome_dir = resolve_results_output_dir(args.outcome)
    common_input_dir = outcome_dir / "common_inputs"
    common_model_dir = outcome_dir / "model_screening"
    compare_dir = outcome_dir / "baseline_mode_compare"
    for path in (outcome_dir, common_input_dir, common_model_dir, compare_dir):
        path.mkdir(parents=True, exist_ok=True)

    coefficient_df = pd.concat(coefficient_rows, ignore_index=True)
    coefficient_path = common_model_dir / "future_projection_coefficients.csv"
    coefficient_df.to_csv(coefficient_path, index=False, encoding="utf-8-sig")

    selected_models_snapshot = pd.DataFrame(
        [
            {
                "role_id": model.role_id,
                "role_label": model.role_label,
                "model_id": model.model_id,
                "scheme_id": model.scheme_id,
                "scheme_source": model.scheme_source,
                "fe_label": model.fe_label,
                "variables": " | ".join(model.variables),
            }
            for model in selected_models
        ]
    )
    selected_models_path = common_model_dir / "selected_models_snapshot.csv"
    selected_models_snapshot.to_csv(selected_models_path, index=False, encoding="utf-8-sig")

    covariate_ets_path = common_model_dir / "covariate_ets_methods_snapshot.csv"
    covariate_ets_methods.to_csv(covariate_ets_path, index=False, encoding="utf-8-sig")

    rx1day_future_aligned_path = common_input_dir / "rx1day_future_aligned.csv"
    future_rx1day_aligned.to_csv(rx1day_future_aligned_path, index=False, encoding="utf-8-sig")

    rx1day_bias_path = None
    if not rx1day_bias_table.empty:
        rx1day_bias_path = common_input_dir / "rx1day_bias_correction.csv"
        rx1day_bias_table.to_csv(rx1day_bias_path, index=False, encoding="utf-8-sig")

    compare_national_yearly: list[pd.DataFrame] = []
    compare_end_summary: list[pd.DataFrame] = []
    mode_output_lookup: dict[str, dict[str, str | None]] = {}

    for baseline_mode in requested_modes:
        baseline_label = BASELINE_MODE_LABELS[baseline_mode]
        baseline_description = BASELINE_MODE_DESCRIPTIONS[baseline_mode]
        scenario_lookup = build_scenario_dict(baseline_mode)

        logger.info("Running baseline mode: %s", baseline_mode)
        projection_rows: list[pd.DataFrame] = []
        baseline_method_tables: list[pd.DataFrame] = []

        for record in fit_records:
            fit_bundle = record["fit_bundle"]
            baseline_outcome_future, baseline_method_df = build_baseline_outcome_future(
                baseline_mode=baseline_mode,
                fit_bundle=fit_bundle,
                baseline_covariate_forecasts=baseline_covariate_forecasts,
                future_years=future_years,
                logger=logger,
            )
            baseline_method_tables.append(
                enrich_baseline_method_snapshot(
                    baseline_mode=baseline_mode,
                    baseline_method_df=baseline_method_df,
                    fit_bundle=fit_bundle,
                )
            )

            mode_projection = simulate_future_scenarios(
                fit_bundle=fit_bundle,
                baseline_outcome_future=baseline_outcome_future,
                baseline_covariate_forecasts=baseline_covariate_forecasts,
                scenario_lookup=scenario_lookup,
                external_rx1day_lookup=external_rx1day_lookup,
            )
            mode_projection["baseline_mode"] = baseline_mode
            mode_projection["baseline_mode_label"] = baseline_label
            projection_rows.append(mode_projection)

        projection_panel = pd.concat(projection_rows, ignore_index=True)
        summaries = summarize_future_projection(historical_outcome_df, projection_panel, end_year=args.end_year)

        mode_dir = outcome_dir / baseline_mode
        projection_output_dir = mode_dir / "projection_outputs"
        figure_dir = mode_dir / "figures"
        mode_model_dir = mode_dir / "model_screening"
        for path in (mode_dir, projection_output_dir, figure_dir, mode_model_dir):
            path.mkdir(parents=True, exist_ok=True)

        projection_panel_path = projection_output_dir / "future_scenario_projection_panel.csv"
        projection_panel.to_csv(projection_panel_path, index=False, encoding="utf-8-sig")

        for name, df in summaries.items():
            df.to_csv(projection_output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")

        baseline_method_snapshot = pd.concat(baseline_method_tables, ignore_index=True)
        baseline_method_path = mode_model_dir / "baseline_method_snapshot.csv"
        baseline_method_snapshot.to_csv(baseline_method_path, index=False, encoding="utf-8-sig")

        national_plot = plot_national_yearly_main_model(
            historical_national=summaries["historical_national"],
            national_yearly=summaries["national_yearly"],
            output_path=figure_dir / "national_yearly_main_model.png",
            end_year=args.end_year,
            y_label=y_label,
            last_observed_year=LAST_OBSERVED_YEAR,
            baseline_label=baseline_label,
        )
        delta_plot = plot_scenario_delta_bar(
            national_yearly=summaries["national_yearly"],
            output_path=figure_dir / f"scenario_delta_{args.end_year}_main_model.png",
            end_year=args.end_year,
            baseline_label=baseline_label,
        )
        figure5_plot = plot_figure5_style_main(
            historical_national=summaries["historical_national"],
            national_yearly=summaries["national_yearly"],
            output_path=figure_dir / "figure5_style_main.png",
            end_year=args.end_year,
            y_label=y_label,
            last_observed_year=LAST_OBSERVED_YEAR,
            baseline_label=baseline_label,
        )
        notes_path = write_projection_notes(
            output_dir=mode_dir,
            outcome_label=outcome_meta["outcome_label"],
            model_source_outcome=args.model_source_outcome,
            roles=args.roles,
            start_year=args.start_year,
            end_year=args.end_year,
            baseline_mode=baseline_mode,
            baseline_label=baseline_label,
            baseline_description=baseline_description,
        )
        mortality_note_path = maybe_run_mortality_scaffold(logger, projection_output_dir)

        mode_metadata = {
            "outcome": args.outcome,
            "outcome_label": outcome_meta["outcome_label"],
            "baseline_mode": baseline_mode,
            "baseline_mode_label": baseline_label,
            "baseline_mode_description": baseline_description,
            "start_year": args.start_year,
            "end_year": args.end_year,
            "selected_roles": args.roles,
            "model_source_outcome": args.model_source_outcome,
            "scenario_ids": list(scenario_lookup.keys()),
            "rx1day_scenarios": RX1DAY_SCENARIOS,
            "rx1day_statistics": RX1DAY_STATISTICS,
            "controlled_future_variables": CONTROLLED_FUTURE_VARIABLES,
            "province_map_size": len(CCKP_PROVINCE_TO_CN),
            "outputs": {
                "projection_panel": str(projection_panel_path),
                "baseline_method_snapshot": str(baseline_method_path),
                "notes": str(notes_path),
                "national_plot": str(national_plot),
                "delta_plot": str(delta_plot),
                "figure5_style_main": str(figure5_plot),
                "mortality_note": str(mortality_note_path) if mortality_note_path else None,
            },
            "common_outputs": {
                "coefficient_path": str(coefficient_path),
                "selected_models_snapshot": str(selected_models_path),
                "covariate_ets_methods_snapshot": str(covariate_ets_path),
                "rx1day_future_aligned": str(rx1day_future_aligned_path),
                "rx1day_bias_correction": str(rx1day_bias_path) if rx1day_bias_path else None,
            },
        }
        mode_metadata_path = mode_dir / "run_metadata.json"
        mode_metadata_path.write_text(json.dumps(mode_metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        compare_national_yearly.append(summaries["national_yearly"])
        compare_end_summary.append(summaries[f"scenario_summary_{args.end_year}"])
        mode_output_lookup[baseline_mode] = {
            "mode_dir": str(mode_dir),
            "projection_panel": str(projection_panel_path),
            "notes": str(notes_path),
            "metadata": str(mode_metadata_path),
            "figure5_style_main": str(figure5_plot),
        }

        logger.info("Completed baseline mode %s with %s rows", baseline_mode, len(projection_panel))

    national_yearly_compare = pd.concat(compare_national_yearly, ignore_index=True)
    national_yearly_compare_path = compare_dir / "national_yearly_compare.csv"
    national_yearly_compare.to_csv(national_yearly_compare_path, index=False, encoding="utf-8-sig")

    end_summary_compare = pd.concat(compare_end_summary, ignore_index=True)
    end_summary_compare_path = compare_dir / f"scenario_summary_{args.end_year}_compare.csv"
    end_summary_compare.to_csv(end_summary_compare_path, index=False, encoding="utf-8-sig")

    main_model_end_compare = end_summary_compare[
        end_summary_compare["role_id"].eq("main_model") & end_summary_compare["statistic"].eq(RX1DAY_MAIN_STATISTIC)
    ].copy()
    main_model_end_compare_path = compare_dir / f"main_model_{args.end_year}_compare.csv"
    main_model_end_compare.to_csv(main_model_end_compare_path, index=False, encoding="utf-8-sig")

    comparison_note_path = write_baseline_comparison_notes(
        output_dir=compare_dir,
        outcome_label=outcome_meta["outcome_label"],
        generated_modes=requested_modes,
        start_year=args.start_year,
        end_year=args.end_year,
    )

    metadata = {
        "outcome": args.outcome,
        "outcome_label": outcome_meta["outcome_label"],
        "outcome_note": outcome_meta["outcome_note"],
        "start_year": args.start_year,
        "end_year": args.end_year,
        "selected_roles": args.roles,
        "model_source_outcome": args.model_source_outcome,
        "baseline_modes": requested_modes,
        "common_outputs": {
            "coefficient_path": str(coefficient_path),
            "selected_models_snapshot": str(selected_models_path),
            "covariate_ets_methods_snapshot": str(covariate_ets_path),
            "rx1day_future_aligned": str(rx1day_future_aligned_path),
            "rx1day_bias_correction": str(rx1day_bias_path) if rx1day_bias_path else None,
        },
        "compare_outputs": {
            "national_yearly_compare": str(national_yearly_compare_path),
            "end_summary_compare": str(end_summary_compare_path),
            "main_model_end_compare": str(main_model_end_compare_path),
            "comparison_note": str(comparison_note_path),
        },
        "mode_outputs": mode_output_lookup,
    }
    metadata_path = outcome_dir / "run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Top-level metadata: %s", metadata_path)
    print(f"[done] metadata={metadata_path}")
    print(f"[done] compare_note={comparison_note_path}")
    for mode in requested_modes:
        print(f"[done] {mode}={mode_output_lookup[mode]['projection_panel']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
