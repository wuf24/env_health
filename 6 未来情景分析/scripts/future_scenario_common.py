from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing

from config_future_scenario_projection import (
    AMR_PATH,
    CCKP_PROVINCE_TO_CN,
    DEFAULT_MODEL_ROLES,
    ETS_DAMPED_TREND,
    ETS_TREND,
    EXTERNAL_ALIGNMENT_METHOD,
    EXTERNAL_ALIGNMENT_MIN_OVERLAP,
    FUTURE_PROVINCE_EXCLUDE,
    HISTORICAL_END_YEAR,
    HISTORICAL_PROVINCE_EXCLUDE,
    HISTORICAL_START_YEAR,
    LOG_DIR,
    MIN_SERIES_POINTS_FOR_TREND,
    PROVINCE_TAS_SSP_PATH,
    PROVINCE_TAS_VARIABLE_NAME,
    RX1DAY_TIMESERIES_PATH,
    RX1DAY_VARIABLE_NAME,
    SELECTED_MODELS_DIR,
    TA_FUTURE_PATH,
    TA_VARIABLE_NAME,
    X_PATH,
    ensure_directories,
)


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


@dataclass
class SelectedModel:
    role_id: str
    role_label: str
    model_id: str
    scheme_id: str
    scheme_source: str
    fe_label: str
    variables: list[str]


def configure_logger(script_name: str) -> tuple[logging.Logger, Path]:
    ensure_directories()
    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"{script_name}_{timestamp}.log"

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger, log_path


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


def fill_panel_median(df: pd.DataFrame, col: str) -> pd.Series:
    out = to_float(df[col])
    out = out.groupby(df["Province"]).transform(lambda s: s.fillna(s.median()))
    return out.fillna(out.median())


def load_base_frame() -> pd.DataFrame:
    amr = pd.read_csv(AMR_PATH, encoding="utf-8-sig")
    x = pd.read_csv(X_PATH, encoding="utf-8-sig")
    x = x.rename(columns={x.columns[0]: "Province", x.columns[1]: "Year"})

    for df_temp in (amr, x):
        df_temp["Province"] = df_temp["Province"].astype(str).str.strip()
        df_temp["Year"] = pd.to_numeric(df_temp["Year"], errors="coerce").astype("Int64")

    df = amr.merge(x, on=["Province", "Year"], how="inner")
    df = df[df["Year"].between(HISTORICAL_START_YEAR, HISTORICAL_END_YEAR)].copy()
    df = df[~df["Province"].isin(HISTORICAL_PROVINCE_EXCLUDE)].copy()

    for col in AMR_COLS:
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

    if outcome == "AMR_AGG_RAW":
        raw_amr = pd.DataFrame({col: to_float(df[col]) for col in AMR_COLS})
        return raw_amr.mean(axis=1, skipna=True), {
            "outcome_label": "AMR_AGG_raw_mean",
            "outcome_note": "13 个 AMR 指标原始百分比直接取行均值，近似 aggregate antibiotic resistance。",
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


def load_selected_models(outcome: str, roles: Iterable[str] | None = None) -> list[SelectedModel]:
    roles = list(roles or DEFAULT_MODEL_ROLES)
    path = SELECTED_MODELS_DIR / outcome / "model_screening" / "selected_models.csv"
    if not path.exists():
        raise FileNotFoundError(f"找不到 selected_models.csv: {path}")

    df = pd.read_csv(path)
    if roles:
        df = df[df["role_id"].isin(roles)].copy()
    if df.empty:
        raise RuntimeError(
            f"selected_models.csv 中没有匹配的 role_id: {roles}" if roles else "selected_models.csv 为空。"
        )

    return [
        SelectedModel(
            role_id=str(row["role_id"]),
            role_label=str(row["role_label"]),
            model_id=str(row["model_id"]),
            scheme_id=str(row["scheme_id"]),
            scheme_source=str(row["scheme_source"]),
            fe_label=str(row["fe_label"]),
            variables=str(row["variables"]).split(" | "),
        )
        for _, row in df.iterrows()
    ]


def fit_panel_association_model(
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

    raw_panel = panel[raw_cols].copy()
    raw_panel.columns = selected_model.variables
    history_outcome = panel[[outcome_label]].copy()

    return {
        "selected_model": selected_model,
        "result": result,
        "transform_stats": transform_stats,
        "raw_panel": raw_panel,
        "history_outcome": history_outcome.rename(columns={outcome_label: "outcome_actual"}),
    }


def fit_ets_series(series: pd.Series, future_years: list[int]) -> tuple[pd.Series, pd.Series, str]:
    clean = to_float(series).dropna().sort_index()
    clean = clean[~clean.index.duplicated(keep="last")]

    if clean.empty:
        historical = pd.Series(dtype=float)
        future = pd.Series(np.nan, index=future_years, dtype=float)
        return historical, future, "empty"

    if len(clean) == 1:
        level = float(clean.iloc[-1])
        historical = pd.Series(level, index=clean.index, dtype=float)
        future = pd.Series(level, index=future_years, dtype=float)
        return historical, future, "flat_single_point"

    years = clean.index.astype(int)
    ts_index = pd.to_datetime([f"{year}-12-31" for year in years])
    ts = pd.Series(clean.values, index=ts_index, dtype=float)

    candidates: list[tuple[str, object]] = []
    if len(clean) >= MIN_SERIES_POINTS_FOR_TREND:
        candidates.append(
            (
                "ets_add_damped",
                lambda s: ExponentialSmoothing(
                    s,
                    trend=ETS_TREND,
                    damped_trend=ETS_DAMPED_TREND,
                    seasonal=None,
                    initialization_method="estimated",
                ).fit(optimized=True, use_brute=False),
            )
        )
        candidates.append(
            (
                "ets_add",
                lambda s: ExponentialSmoothing(
                    s,
                    trend=ETS_TREND,
                    damped_trend=False,
                    seasonal=None,
                    initialization_method="estimated",
                ).fit(optimized=True, use_brute=False),
            )
        )
    candidates.append(
        (
            "ses",
            lambda s: SimpleExpSmoothing(s, initialization_method="estimated").fit(optimized=True),
        )
    )

    for method_name, builder in candidates:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fitted = builder(ts)
                historical = pd.Series(np.asarray(fitted.fittedvalues), index=years, dtype=float)
                future = pd.Series(np.asarray(fitted.forecast(len(future_years))), index=future_years, dtype=float)
            return historical, future, method_name
        except Exception:
            continue

    level = float(clean.iloc[-1])
    historical = pd.Series(level, index=clean.index, dtype=float)
    future = pd.Series(level, index=future_years, dtype=float)
    return historical, future, "flat_fallback"


def forecast_panel_value(
    df: pd.DataFrame,
    value_col: str,
    future_years: list[int],
    logger: logging.Logger | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = df[["Province", "Year", value_col]].copy()
    work["Year"] = pd.to_numeric(work["Year"], errors="coerce").astype(int)
    work[value_col] = to_float(work[value_col])

    forecast_rows: list[dict[str, object]] = []
    method_rows: list[dict[str, object]] = []

    for province, sub in work.groupby("Province"):
        series = sub.sort_values("Year").set_index("Year")[value_col]
        _, future, method_name = fit_ets_series(series, future_years)
        for year, value in future.items():
            forecast_rows.append({"Province": province, "Year": int(year), value_col: float(value)})
        method_rows.append({"Province": province, "variable": value_col, "ets_method": method_name})

    forecast_df = pd.DataFrame(forecast_rows)
    method_df = pd.DataFrame(method_rows)

    if logger is not None:
        logger.info("Forecasted %s for %s provinces", value_col, forecast_df["Province"].nunique())

    return forecast_df, method_df


def build_baseline_covariate_forecasts(
    base_df: pd.DataFrame,
    variables: Iterable[str],
    future_years: list[int],
    logger: logging.Logger | None = None,
) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    forecasts: dict[str, pd.Series] = {}
    method_tables: list[pd.DataFrame] = []

    for var in sorted(set(variables)):
        work = base_df[["Province", "Year", var]].copy()
        work[var] = fill_panel_median(work, var)
        forecast_df, method_df = forecast_panel_value(work, var, future_years, logger=logger)
        series = forecast_df.set_index(["Province", "Year"])[var].sort_index()
        forecasts[var] = series
        method_tables.append(method_df)

    methods = pd.concat(method_tables, ignore_index=True) if method_tables else pd.DataFrame()
    return forecasts, methods


def build_x_driven_baseline_outcome(
    fit_bundle: dict[str, object],
    baseline_covariate_forecasts: dict[str, pd.Series],
    future_years: list[int],
    logger: logging.Logger | None = None,
) -> tuple[pd.Series, pd.DataFrame]:
    selected_model: SelectedModel = fit_bundle["selected_model"]
    result = fit_bundle["result"]
    transform_stats: dict[str, dict[str, float]] = fit_bundle["transform_stats"]
    raw_panel: pd.DataFrame = fit_bundle["raw_panel"]
    history_outcome: pd.DataFrame = fit_bundle["history_outcome"]

    if not baseline_covariate_forecasts:
        raise ValueError("baseline_covariate_forecasts is empty")

    template_index = next(iter(baseline_covariate_forecasts.values())).index
    future_index = pd.MultiIndex.from_tuples(template_index.tolist(), names=["Province", "Year"])

    history_component = pd.Series(0.0, index=raw_panel.index, dtype=float)
    future_component = pd.Series(0.0, index=future_index, dtype=float)

    for variable in selected_model.variables:
        stats = transform_stats[variable]
        std = float(stats["std"])
        mean = float(stats["mean"])
        beta = float(result.params.get(variable, 0.0))

        raw_hist = to_float(raw_panel[variable]).reindex(raw_panel.index)
        raw_future = to_float(baseline_covariate_forecasts[variable].reindex(future_index))

        if std == 0:
            z_hist = pd.Series(0.0, index=raw_hist.index, dtype=float)
            z_future = pd.Series(0.0, index=raw_future.index, dtype=float)
        else:
            z_hist = (raw_hist - mean) / std
            z_future = (raw_future - mean) / std

        history_component = history_component.add(beta * z_hist, fill_value=0.0)
        future_component = future_component.add(beta * z_future, fill_value=0.0)

    history_actual = to_float(history_outcome["outcome_actual"]).reindex(history_component.index)
    remainder = history_actual - history_component

    fe_cfg = FE_LABEL_TO_SPEC[selected_model.fe_label]
    overall_level = float(remainder.mean())

    entity_effect = pd.Series(0.0, index=pd.Index(raw_panel.index.get_level_values("Province").unique(), name="Province"))
    if fe_cfg["entity_effects"]:
        entity_effect = remainder.groupby(level="Province").mean() - overall_level

    remainder_after_entity = remainder - overall_level
    if fe_cfg["entity_effects"]:
        entity_lookup = raw_panel.index.get_level_values("Province").map(entity_effect).astype(float)
        remainder_after_entity = remainder_after_entity - entity_lookup

    time_effect_hist = pd.Series(0.0, index=pd.Index(sorted(raw_panel.index.get_level_values("Year").unique()), name="Year"))
    time_effect_future = pd.Series(0.0, index=pd.Index(future_years, name="Year"))
    time_effect_method = "none"
    if fe_cfg["time_effects"]:
        time_effect_hist = remainder_after_entity.groupby(level="Year").mean().sort_index()
        _, time_effect_future, time_effect_method = fit_ets_series(time_effect_hist, future_years)

    baseline_future = pd.Series(overall_level, index=future_index, dtype=float)
    if fe_cfg["entity_effects"]:
        future_entity = future_index.get_level_values("Province").map(entity_effect).astype(float)
        baseline_future = baseline_future.add(pd.Series(future_entity, index=future_index), fill_value=0.0)
    if fe_cfg["time_effects"]:
        future_time = future_index.get_level_values("Year").map(time_effect_future).astype(float)
        baseline_future = baseline_future.add(pd.Series(future_time, index=future_index), fill_value=0.0)

    baseline_future = baseline_future.add(future_component, fill_value=0.0)

    method_rows = [
        {
            "role_id": selected_model.role_id,
            "role_label": selected_model.role_label,
            "model_id": selected_model.model_id,
            "scheme_id": selected_model.scheme_id,
            "baseline_mode": "x_driven",
            "component": "overall_level",
            "method": "historical_mean_remainder",
            "value": overall_level,
        },
        {
            "role_id": selected_model.role_id,
            "role_label": selected_model.role_label,
            "model_id": selected_model.model_id,
            "scheme_id": selected_model.scheme_id,
            "baseline_mode": "x_driven",
            "component": "time_effect",
            "method": time_effect_method,
            "value": float(time_effect_hist.mean()) if not time_effect_hist.empty else 0.0,
        },
    ]
    method_df = pd.DataFrame(method_rows)

    if logger is not None:
        logger.info(
            "Built x-driven baseline for %s using %s variables; time-effect method=%s",
            selected_model.role_id,
            len(selected_model.variables),
            time_effect_method,
        )

    return baseline_future.sort_index(), method_df


def load_future_rx1day_panel() -> pd.DataFrame:
    if not RX1DAY_TIMESERIES_PATH.exists():
        raise FileNotFoundError(f"找不到逐年 rx1day 面板文件: {RX1DAY_TIMESERIES_PATH}")

    df = pd.read_csv(RX1DAY_TIMESERIES_PATH, encoding="utf-8-sig")
    df["Province"] = df["province"].map(CCKP_PROVINCE_TO_CN)
    df["Year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["rx1day"] = to_float(df["rx1day"])

    df = df[df["Province"].notna()].copy()
    df = df[~df["Province"].isin(FUTURE_PROVINCE_EXCLUDE)].copy()
    df = df[df["Year"].notna()].copy()
    df["Year"] = df["Year"].astype(int)

    return df[["Province", "Year", "scenario", "statistic", "rx1day"]].reset_index(drop=True)


def load_future_ta_panel() -> pd.DataFrame:
    if not TA_FUTURE_PATH.exists():
        raise FileNotFoundError(f"找不到 TA future 面板文件: {TA_FUTURE_PATH}")

    df = pd.read_csv(TA_FUTURE_PATH, encoding="utf-8-sig")
    df["Province"] = df["Province"].astype(str).str.strip()
    df["Year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df[TA_VARIABLE_NAME] = to_float(df[TA_VARIABLE_NAME])

    df = df[df["Province"].notna()].copy()
    df = df[~df["Province"].isin(FUTURE_PROVINCE_EXCLUDE)].copy()
    df = df[df["Year"].notna()].copy()
    df["Year"] = df["Year"].astype(int)

    return df[["Province", "Year", "scenario", "statistic", TA_VARIABLE_NAME]].reset_index(drop=True)


def load_future_province_tas_panel() -> pd.DataFrame:
    if not PROVINCE_TAS_SSP_PATH.exists():
        raise FileNotFoundError(f"找不到 SSP 省平均气温面板文件: {PROVINCE_TAS_SSP_PATH}")

    df = pd.read_csv(PROVINCE_TAS_SSP_PATH, encoding="utf-8-sig")
    df["Province"] = df["Province"].astype(str).str.strip()
    df["Year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df[PROVINCE_TAS_VARIABLE_NAME] = to_float(df[PROVINCE_TAS_VARIABLE_NAME])

    df = df[df["Province"].notna()].copy()
    df = df[~df["Province"].isin(FUTURE_PROVINCE_EXCLUDE)].copy()
    df = df[df["Year"].notna()].copy()
    df["Year"] = df["Year"].astype(int)

    return df[["Province", "Year", "scenario", "statistic", PROVINCE_TAS_VARIABLE_NAME]].reset_index(drop=True)


def align_external_series_to_history(
    future_df: pd.DataFrame,
    historical_df: pd.DataFrame,
    historical_value_col: str,
    external_value_col: str,
    aligned_value_col: str,
    series_label: str,
    logger: logging.Logger | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if EXTERNAL_ALIGNMENT_METHOD != "mean_bias":
        future_df = future_df.copy()
        future_df[aligned_value_col] = future_df[external_value_col]
        return future_df, pd.DataFrame()

    history = historical_df[["Province", "Year", historical_value_col]].copy()
    history = history.rename(columns={historical_value_col: "history_value"})

    overlap = future_df.merge(history, on=["Province", "Year"], how="inner")
    if overlap.empty:
        future_df = future_df.copy()
        future_df[aligned_value_col] = future_df[external_value_col]
        return future_df, pd.DataFrame()

    bias = (
        overlap.assign(additive_bias=overlap["history_value"] - overlap[external_value_col])
        .groupby(["Province", "scenario", "statistic"], dropna=False)
        .agg(
            overlap_n=("Year", "nunique"),
            history_value_mean=("history_value", "mean"),
            external_value_mean=(external_value_col, "mean"),
            additive_bias=("additive_bias", "mean"),
        )
        .reset_index()
    )
    bias.loc[bias["overlap_n"] < EXTERNAL_ALIGNMENT_MIN_OVERLAP, "additive_bias"] = 0.0

    adjusted = future_df.merge(
        bias[["Province", "scenario", "statistic", "additive_bias", "overlap_n"]],
        on=["Province", "scenario", "statistic"],
        how="left",
    )
    adjusted["additive_bias"] = adjusted["additive_bias"].fillna(0.0)
    adjusted["overlap_n"] = adjusted["overlap_n"].fillna(0).astype(int)
    adjusted[aligned_value_col] = adjusted[external_value_col] + adjusted["additive_bias"]

    if logger is not None:
        logger.info(
            "Aligned external %s by province/scenario/statistic with mean-bias correction; overlap groups=%s",
            series_label,
            len(bias),
        )

    return adjusted, bias.sort_values(["Province", "scenario", "statistic"]).reset_index(drop=True)


def align_future_rx1day_to_history(
    future_df: pd.DataFrame,
    historical_df: pd.DataFrame,
    logger: logging.Logger | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return align_external_series_to_history(
        future_df=future_df,
        historical_df=historical_df,
        historical_value_col=RX1DAY_VARIABLE_NAME,
        external_value_col="rx1day",
        aligned_value_col="rx1day_aligned",
        series_label="rx1day",
        logger=logger,
    )


def align_future_province_tas_to_history(
    future_df: pd.DataFrame,
    historical_df: pd.DataFrame,
    logger: logging.Logger | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return align_external_series_to_history(
        future_df=future_df,
        historical_df=historical_df,
        historical_value_col=PROVINCE_TAS_VARIABLE_NAME,
        external_value_col=PROVINCE_TAS_VARIABLE_NAME,
        aligned_value_col=f"{PROVINCE_TAS_VARIABLE_NAME}_aligned",
        series_label=PROVINCE_TAS_VARIABLE_NAME,
        logger=logger,
    )
