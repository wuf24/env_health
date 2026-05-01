from __future__ import annotations

import argparse
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


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
CORE_VARIABLES = {"R1xday", "抗菌药物使用强度"}
INTERACTION_VARIABLE = "R1xday × 抗菌药物使用强度"
TA_AMC_INTERACTION_VARIABLE = "TA（°C） × 抗菌药物使用强度"
R1_TA_INTERACTION_VARIABLE = "R1xday × TA（°C）"
R1_TA_AMC_INTERACTION_VARIABLE = "R1xday × TA（°C） × 抗菌药物使用强度"
FOCUS_VARIABLES = CORE_VARIABLES | {
    INTERACTION_VARIABLE,
    TA_AMC_INTERACTION_VARIABLE,
    R1_TA_INTERACTION_VARIABLE,
    R1_TA_AMC_INTERACTION_VARIABLE,
}
CORE_ALIASES = {
    "R1xday": "R1xday",
    "抗菌药物使用强度": "AMC",
    INTERACTION_VARIABLE: "R1xday_x_AMC",
    TA_AMC_INTERACTION_VARIABLE: "TA_x_AMC",
    R1_TA_INTERACTION_VARIABLE: "R1xday_x_TA",
    R1_TA_AMC_INTERACTION_VARIABLE: "R1xday_x_TA_x_AMC",
}


@dataclass
class RunConfig:
    draws: int
    tune: int
    chains: int
    cores: int
    target_accept: float


@dataclass
class SelectionConfig:
    default_fe_label: str
    selected_scheme_ids: list[str]
    selected_model_ids: list[str]


@dataclass
class ModelGridConfig:
    variant_ids: list[str]
    interaction_pairs: list[tuple[str, str]]
    interaction_terms: list[tuple[str, ...]]


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    label: str
    include_year: bool
    include_province: bool
    use_mundlak: bool
    include_interaction: bool
    rationale: str


@dataclass
class TermBlock:
    name: str
    labels: list[str]
    cols: list[str]
    prior_sigma: float


VARIANT_LIBRARY: dict[str, VariantSpec] = {
    "year_only_additive": VariantSpec(
        variant_id="year_only_additive",
        label="Year-only additive",
        include_year=True,
        include_province=False,
        use_mundlak=False,
        include_interaction=False,
        rationale="Mirror Year FE only without an explicit amplification term.",
    ),
    "year_only_amplification": VariantSpec(
        variant_id="year_only_amplification",
        label="Year-only amplification",
        include_year=True,
        include_province=False,
        use_mundlak=False,
        include_interaction=True,
        rationale="Mirror Year FE only and directly test whether R1xday amplifies AMC.",
    ),
    "year_only_ta_amc_amplification": VariantSpec(
        variant_id="year_only_ta_amc_amplification",
        label="Year-only TA x AMC amplification",
        include_year=True,
        include_province=False,
        use_mundlak=False,
        include_interaction=True,
        rationale="Mirror Year FE only and test whether temperature amplifies AMC.",
    ),
    "year_only_climate_amc_triple": VariantSpec(
        variant_id="year_only_climate_amc_triple",
        label="Year-only R1xday x TA x AMC interaction",
        include_year=True,
        include_province=False,
        use_mundlak=False,
        include_interaction=True,
        rationale="Mirror Year FE only and test the hierarchical climate-by-AMC three-way interaction.",
    ),
    "province_only_additive": VariantSpec(
        variant_id="province_only_additive",
        label="Province-only additive",
        include_year=False,
        include_province=True,
        use_mundlak=False,
        include_interaction=False,
        rationale="Mirror Province FE only at the Bayesian hierarchy level.",
    ),
    "province_only_amplification": VariantSpec(
        variant_id="province_only_amplification",
        label="Province-only amplification",
        include_year=False,
        include_province=True,
        use_mundlak=False,
        include_interaction=True,
        rationale="Mirror Province FE only and directly test amplification.",
    ),
    "province_year_additive": VariantSpec(
        variant_id="province_year_additive",
        label="Province + year additive",
        include_year=True,
        include_province=True,
        use_mundlak=False,
        include_interaction=False,
        rationale="Bridge model closest to a two-way panel adjustment without decomposition.",
    ),
    "province_year_amplification": VariantSpec(
        variant_id="province_year_amplification",
        label="Province + year amplification",
        include_year=True,
        include_province=True,
        use_mundlak=False,
        include_interaction=True,
        rationale="Bridge model plus direct amplification interaction.",
    ),
    "mundlak_year_additive": VariantSpec(
        variant_id="mundlak_year_additive",
        label="Mundlak + year additive",
        include_year=True,
        include_province=True,
        use_mundlak=True,
        include_interaction=False,
        rationale="Diagnostic decomposition of province-internal and province-level signals.",
    ),
    "mundlak_year_amplification": VariantSpec(
        variant_id="mundlak_year_amplification",
        label="Mundlak + year amplification",
        include_year=True,
        include_province=True,
        use_mundlak=True,
        include_interaction=True,
        rationale="Diagnostic decomposition plus direct amplification interaction.",
    ),
}

DEFAULT_VARIANTS = [
    "year_only_additive",
    "year_only_amplification",
    "province_only_additive",
    "province_only_amplification",
    "province_year_additive",
    "province_year_amplification",
]

VARIANT_INTERACTION_TERMS: dict[str, list[tuple[str, ...]]] = {
    "year_only_ta_amc_amplification": [
        ("TA（°C）", "抗菌药物使用强度"),
    ],
    "year_only_climate_amc_triple": [
        ("R1xday", "抗菌药物使用强度"),
        ("TA（°C）", "抗菌药物使用强度"),
        ("R1xday", "TA（°C）"),
        ("R1xday", "TA（°C）", "抗菌药物使用强度"),
    ],
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_name(name: str) -> str:
    if pd.isna(name):
        return ""
    text = str(name)
    for token in ("\n", "\r", "\t", " "):
        text = text.replace(token, "")
    return text


def build_column_lookup(columns: Iterable[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for column in columns:
        lookup[normalize_name(column)] = column
    return lookup


def resolve_variables(raw_variables: str, lookup: dict[str, str]) -> list[str]:
    variables: list[str] = []
    for token in str(raw_variables).split("|"):
        cleaned = token.strip()
        if not cleaned:
            continue
        key = normalize_name(cleaned)
        if key not in lookup:
            raise KeyError(f"Variable `{cleaned}` not found in merged data columns.")
        variables.append(lookup[key])
    return variables


def compute_amr_agg_z(amr: pd.DataFrame) -> pd.DataFrame:
    result = amr.copy()
    z_cols = []
    for col in AMR_COLUMNS:
        std = result[col].std(ddof=0)
        if pd.isna(std) or std == 0:
            raise ValueError(f"Cannot standardize AMR column `{col}` because its std is zero.")
        z_col = f"{col}_z"
        result[z_col] = (result[col] - result[col].mean()) / std
        z_cols.append(z_col)
    result["AMR_AGG_z"] = result[z_cols].mean(axis=1)
    return result


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def apply_time_panel_imputation(
    df: pd.DataFrame,
    cols: list[str],
    group_col: str = "Province",
    time_col: str = "Year",
    base_year: int = 2014,
    base_year_fill_from: int = 2015,
) -> tuple[pd.DataFrame, dict[str, object]]:
    work = df.copy()
    work[time_col] = pd.to_numeric(work[time_col], errors="coerce")
    work = work.sort_values([group_col, time_col]).reset_index(drop=True)
    missing_report: list[dict[str, int | str]] = []
    logs: list[dict[str, object]] = []

    for col in cols:
        work[col] = to_float(work[col])

        def first_non_missing_after(g: pd.DataFrame) -> tuple[float, float]:
            future = g.loc[(g[time_col] > base_year) & g[col].notna(), [time_col, col]].sort_values(time_col)
            if future.empty:
                return np.nan, np.nan
            row = future.iloc[0]
            return float(row[time_col]), float(row[col])

        def process_group(g: pd.DataFrame) -> pd.Series:
            s = g[col].copy()
            years = pd.to_numeric(g[time_col], errors="coerce")
            province = str(g[group_col].iloc[0])

            mask_2014 = years.eq(base_year) & s.isna()
            if mask_2014.any():
                v2015 = g.loc[years.eq(base_year_fill_from), col].dropna()
                if not v2015.empty:
                    fill_year = float(base_year_fill_from)
                    fill_val = float(v2015.iloc[0])
                    rule = f"A1: {base_year}->{base_year_fill_from}"
                else:
                    fill_year, fill_val = first_non_missing_after(g)
                    rule = f"A2: {base_year}->first_future"

                if np.isfinite(fill_val):
                    for idx in s.index[mask_2014]:
                        logs.append(
                            {
                                group_col: province,
                                time_col: int(g.loc[idx, time_col]),
                                "column": col,
                                "before": None,
                                "after": float(fill_val),
                                "rule": rule,
                                "ref1_year": int(fill_year) if np.isfinite(fill_year) else None,
                                "ref1_value": float(fill_val),
                                "ref2_year": None,
                                "ref2_value": None,
                            }
                        )
                    s.loc[mask_2014] = fill_val

            prev_val = s.ffill()
            next_val = s.bfill()
            prev_year = years.where(s.notna()).ffill()
            next_year = years.where(s.notna()).bfill()

            mask_other = years.ne(base_year) & s.isna()
            if mask_other.any():
                for idx in s.index[mask_other]:
                    pv, nv = prev_val.loc[idx], next_val.loc[idx]
                    py, ny = prev_year.loc[idx], next_year.loc[idx]

                    if pd.isna(pv) and pd.isna(nv):
                        continue

                    if pd.notna(pv) and pd.notna(nv):
                        fill = float((pv + nv) / 2.0)
                        rule = "B1: mean(prev,next)"
                        ref1_year = int(py)
                        ref1_value = float(pv)
                        ref2_year = int(ny)
                        ref2_value = float(nv)
                    elif pd.notna(pv):
                        fill = float(pv)
                        rule = "B2: carry prev (edge)"
                        ref1_year = int(py)
                        ref1_value = float(pv)
                        ref2_year = None
                        ref2_value = None
                    else:
                        fill = float(nv)
                        rule = "B3: carry next (edge)"
                        ref1_year = int(ny)
                        ref1_value = float(nv)
                        ref2_year = None
                        ref2_value = None

                    logs.append(
                        {
                            group_col: province,
                            time_col: int(g.loc[idx, time_col]),
                            "column": col,
                            "before": None,
                            "after": fill,
                            "rule": rule,
                            "ref1_year": ref1_year,
                            "ref1_value": ref1_value,
                            "ref2_year": ref2_year,
                            "ref2_value": ref2_value,
                        }
                    )
                    s.loc[idx] = fill

            return s

        before_missing = int(work[col].isna().sum())
        filled_groups = [process_group(group) for _, group in work.groupby(group_col, sort=False)]
        work[col] = pd.concat(filled_groups).sort_index()
        after_missing = int(work[col].isna().sum())
        missing_report.append(
            {
                "column": col,
                "missing_before": before_missing,
                "missing_after": after_missing,
            }
        )

    remaining = {col: int(work[col].isna().sum()) for col in cols if int(work[col].isna().sum()) > 0}

    rule_counts: dict[str, int] = {}
    for item in logs:
        rule = str(item["rule"])
        rule_counts[rule] = rule_counts.get(rule, 0) + 1

    metadata = {
        "missing_value_strategy": {
            "label": "province_year_time_imputation",
            "steps": [
                "convert selected X columns to numeric with coercion",
                f"if {base_year} is missing, fill from {base_year_fill_from}; if {base_year_fill_from} is also missing, use the first future non-missing year within the same province",
                "for other missing years, use the mean of previous and next non-missing values within the same province",
                "if only one side exists at the boundary, carry the nearest available value",
            ],
            "applied_columns": cols,
            "column_report": missing_report,
            "remaining_missing_after_imputation": remaining,
            "rule_counts": rule_counts,
            "imputation_log": logs,
        }
    }
    return work, metadata


def load_analysis_frame(amr_path: Path, x_path: Path) -> pd.DataFrame:
    amr = pd.read_csv(amr_path)
    x = pd.read_csv(x_path)
    x = x.rename(columns={"省份": "Province", "YEAR": "Year"})
    amr = compute_amr_agg_z(amr)
    merged = amr.merge(x, on=["Province", "Year"], how="inner")
    merged = merged.sort_values(["Province", "Year"]).reset_index(drop=True)
    return merged


def prepare_model_frame(merged: pd.DataFrame, row: pd.Series) -> tuple[pd.DataFrame, list[str], dict[str, object]]:
    lookup = build_column_lookup(merged.columns)
    variables = resolve_variables(row["variables"], lookup)
    keep_cols = ["Province", "Year", "AMR_AGG_z", *variables]
    model_df = merged[keep_cols].copy()
    model_df["AMR_AGG_z"] = to_float(model_df["AMR_AGG_z"])
    outcome_missing_before = int(model_df["AMR_AGG_z"].isna().sum())
    model_df, frame_meta = apply_time_panel_imputation(model_df, variables)
    x_missing_after_imputation = {
        var: int(model_df[var].isna().sum()) for var in variables if int(model_df[var].isna().sum()) > 0
    }
    model_df = model_df.dropna(subset=["AMR_AGG_z", *variables]).copy()
    model_df = model_df.sort_values(["Province", "Year"]).reset_index(drop=True)
    if model_df.empty:
        raise ValueError(f"No rows remain after X imputation and AMR outcome filtering for {row['model_id']}.")
    frame_meta["outcome_handling"] = {
        "column": "AMR_AGG_z",
        "strategy": "do_not_impute_drop_missing_after_x_completion",
        "missing_before_drop": outcome_missing_before,
        "missing_after_drop": int(model_df["AMR_AGG_z"].isna().sum()),
        "n_obs_after_drop": int(len(model_df)),
    }
    frame_meta["post_imputation_filtering"] = {
        "dropna_subset": ["AMR_AGG_z", *variables],
        "remaining_x_missing_before_drop": x_missing_after_imputation,
    }
    return model_df, variables, frame_meta


def load_selection_config(path: Path) -> SelectionConfig:
    if not path.exists():
        return SelectionConfig(
            default_fe_label="Province: No / Year: Yes",
            selected_scheme_ids=[],
            selected_model_ids=[],
        )

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    selection = raw.get("selection", {})
    return SelectionConfig(
        default_fe_label=selection.get("default_fe_label", "Province: No / Year: Yes"),
        selected_scheme_ids=list(selection.get("selected_scheme_ids", [])),
        selected_model_ids=list(selection.get("selected_model_ids", [])),
    )


def load_model_grid_config(path: Path) -> ModelGridConfig:
    if not path.exists():
        interaction_pairs = [("R1xday", "抗菌药物使用强度")]
        return ModelGridConfig(
            variant_ids=DEFAULT_VARIANTS.copy(),
            interaction_pairs=interaction_pairs,
            interaction_terms=[tuple(pair) for pair in interaction_pairs],
        )

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    grid = raw.get("model_grid", raw.get("model", {}))
    variant_ids = list(grid.get("variant_ids", DEFAULT_VARIANTS))
    interaction_pairs: list[tuple[str, str]] = []
    for pair in grid.get("interaction_pairs", [["R1xday", "抗菌药物使用强度"]]):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("Each interaction pair must contain exactly two variable names.")
        interaction_pairs.append((str(pair[0]), str(pair[1])))

    interaction_terms: list[tuple[str, ...]] = []
    raw_terms = grid.get("interaction_terms")
    if raw_terms is None:
        interaction_terms = [tuple(pair) for pair in interaction_pairs]
    else:
        for term in raw_terms:
            if not isinstance(term, (list, tuple)) or len(term) < 2:
                raise ValueError("Each interaction term must contain at least two variable names.")
            interaction_terms.append(tuple(str(item) for item in term))

    unknown = [variant_id for variant_id in variant_ids if variant_id not in VARIANT_LIBRARY]
    if unknown:
        raise ValueError(f"Unknown variant_ids in model grid: {unknown}")

    return ModelGridConfig(
        variant_ids=variant_ids,
        interaction_pairs=interaction_pairs,
        interaction_terms=interaction_terms,
    )


def apply_selection(
    candidates: pd.DataFrame,
    selection_config: SelectionConfig,
    cli_model_ids: list[str] | None,
) -> pd.DataFrame:
    if cli_model_ids:
        selected = candidates[candidates["model_id"].isin(cli_model_ids)].copy()
        if selected.empty:
            raise ValueError("No candidate models matched the requested --model-ids values.")
        return selected

    if selection_config.selected_model_ids:
        selected = candidates[candidates["model_id"].isin(selection_config.selected_model_ids)].copy()
        if selected.empty:
            raise ValueError("No candidate models matched `selected_model_ids` in the selection file.")
        return selected

    if selection_config.selected_scheme_ids:
        selected = candidates[
            (candidates["scheme_id"].isin(selection_config.selected_scheme_ids))
            & (candidates["fe_label"] == selection_config.default_fe_label)
        ].copy()
        if selected.empty:
            raise ValueError(
                "No candidate models matched `selected_scheme_ids` with the configured `default_fe_label`."
            )
        return selected

    return candidates.copy()


def z_standardize(series: pd.Series, label: str) -> tuple[pd.Series, dict[str, float]]:
    std = series.std(ddof=0)
    if pd.isna(std) or std == 0:
        raise ValueError(f"Cannot standardize predictor `{label}` because its std is zero.")
    mean = series.mean()
    return (series - mean) / std, {"mean": float(mean), "std": float(std)}


def standardize_variables(
    model_df: pd.DataFrame,
    variables: list[str],
) -> tuple[pd.DataFrame, dict[str, str], dict[str, dict[str, float]]]:
    df = model_df.copy()
    z_map: dict[str, str] = {}
    scaling: dict[str, dict[str, float]] = {}

    for var in variables:
        z_series, scaling[var] = z_standardize(df[var], var)
        z_col = f"z__{normalize_name(var)}"
        df[z_col] = z_series
        z_map[var] = z_col
    return df, z_map, scaling


def build_mundlak_blocks(
    df: pd.DataFrame,
    variables: list[str],
    z_map: dict[str, str],
) -> tuple[pd.DataFrame, list[TermBlock], dict[str, object]]:
    grouped = df.groupby("Province")
    within_cols: list[str] = []
    between_cols: list[str] = []

    for var in variables:
        within_col = f"within__{normalize_name(var)}"
        between_col = f"between__{normalize_name(var)}"
        df[between_col] = grouped[z_map[var]].transform("mean")
        df[within_col] = df[z_map[var]] - df[between_col]
        within_cols.append(within_col)
        between_cols.append(between_col)

    blocks = [
        TermBlock(name="within", labels=variables.copy(), cols=within_cols, prior_sigma=0.5),
        TermBlock(name="between", labels=variables.copy(), cols=between_cols, prior_sigma=0.5),
    ]
    metadata = {
        "term_definition": {
            "within": "Within-province deviation from the province mean after z-standardizing the analysis sample.",
            "between": "Province-level mean after z-standardizing the analysis sample.",
        },
        "within_terms": dict(zip(variables, within_cols)),
        "between_terms": dict(zip(variables, between_cols)),
    }
    return df, blocks, metadata


def build_main_blocks(
    variables: list[str],
    z_map: dict[str, str],
) -> tuple[list[TermBlock], dict[str, object]]:
    blocks = [TermBlock(name="main", labels=variables.copy(), cols=[z_map[var] for var in variables], prior_sigma=0.5)]
    metadata = {
        "term_definition": {
            "main": "Z-standardized predictors pooled at the analysis-sample level.",
        },
        "main_terms": dict(zip(variables, [z_map[var] for var in variables])),
    }
    return blocks, metadata


def build_interaction_blocks(
    df: pd.DataFrame,
    base_blocks: list[TermBlock],
    variant: VariantSpec,
    grid_config: ModelGridConfig,
) -> tuple[pd.DataFrame, list[TermBlock], dict[str, object]]:
    if not variant.include_interaction:
        return df, [], {"interaction_pairs": []}

    if variant.use_mundlak:
        source_map = {block.name: dict(zip(block.labels, block.cols)) for block in base_blocks}
        definitions = [
            ("within_interaction", "within"),
            ("between_interaction", "between"),
        ]
    else:
        source_map = {"interaction": dict(zip(base_blocks[0].labels, base_blocks[0].cols))}
        definitions = [("interaction", "interaction")]

    blocks: list[TermBlock] = []
    metadata_terms: list[dict[str, object]] = []
    term_maps: dict[str, dict[str, str]] = {}
    interaction_terms = VARIANT_INTERACTION_TERMS.get(variant.variant_id, grid_config.interaction_terms)

    for block_name, source_name in definitions:
        labels: list[str] = []
        cols: list[str] = []
        for term in interaction_terms:
            if any(item not in source_map[source_name] for item in term):
                continue
            label = " × ".join(term)
            raw = pd.Series(1.0, index=df.index)
            for item in term:
                raw = raw * df[source_map[source_name][item]]
            standardized, _ = z_standardize(raw, f"{block_name} `{label}`")
            col = f"{block_name}__{'×'.join(normalize_name(item) for item in term)}"
            df[col] = standardized
            labels.append(label)
            cols.append(col)
            term_maps.setdefault(block_name, {})[label] = col
            metadata_terms.append({"terms": list(term), "order": len(term), "label": label})

        if labels:
            blocks.append(TermBlock(name=block_name, labels=labels, cols=cols, prior_sigma=0.35))

    metadata = {
        "interaction_pairs": [
            {"left": item["terms"][0], "right": item["terms"][1], "label": item["label"]}
            for item in metadata_terms
            if item["order"] == 2
        ],
        "interaction_term_definitions": metadata_terms,
        **{f"{block_name}_term_columns": mapping for block_name, mapping in term_maps.items()},
    }
    return df, blocks, metadata


def build_variant_design(
    model_df: pd.DataFrame,
    variables: list[str],
    variant: VariantSpec,
    grid_config: ModelGridConfig,
) -> tuple[pd.DataFrame, list[TermBlock], dict[str, object]]:
    df, z_map, scaling = standardize_variables(model_df, variables)
    metadata: dict[str, object] = {
        "standardization": scaling,
        "variant_id": variant.variant_id,
        "variant_label": variant.label,
        "variant_rationale": variant.rationale,
        "variant_flags": {
            "include_year": variant.include_year,
            "include_province": variant.include_province,
            "use_mundlak": variant.use_mundlak,
            "include_interaction": variant.include_interaction,
        },
    }

    if variant.use_mundlak:
        df, base_blocks, base_meta = build_mundlak_blocks(df, variables, z_map)
    else:
        base_blocks, base_meta = build_main_blocks(variables, z_map)

    df, interaction_blocks, interaction_meta = build_interaction_blocks(df, base_blocks, variant, grid_config)
    metadata.update(base_meta)
    metadata.update(interaction_meta)
    return df, [*base_blocks, *interaction_blocks], metadata


def summarize_beta_draws(beta_draws, effect_scope: str, coord_name: str) -> pd.DataFrame:
    variables = beta_draws[coord_name].values.tolist()
    return pd.DataFrame(
        {
            "term_id": [f"{effect_scope}__{normalize_name(var)}" for var in variables],
            "variable": variables,
            "effect_scope": effect_scope,
            "posterior_mean": beta_draws.mean("sample").values,
            "posterior_sd": beta_draws.std("sample").values,
            "crI_2_5": beta_draws.quantile(0.025, dim="sample").values,
            "crI_97_5": beta_draws.quantile(0.975, dim="sample").values,
            "prob_gt_0": (beta_draws > 0).mean("sample").values,
        }
    )


def annotate_diagnostics(diag: pd.DataFrame) -> pd.DataFrame:
    result = diag.copy()
    result["effect_scope"] = "global"
    result["variable"] = ""

    for idx, parameter in result["parameter"].items():
        match = re.match(r"beta_(.+)\[(.*)\]$", str(parameter), flags=re.S)
        if match:
            result.at[idx, "effect_scope"] = match.group(1)
            result.at[idx, "variable"] = match.group(2)
    return result


def fit_variant_model(
    model_df: pd.DataFrame,
    variables: list[str],
    variant: VariantSpec,
    grid_config: ModelGridConfig,
    run_config: RunConfig,
):
    try:
        import arviz as az
        import pymc as pm
        import pytensor.tensor as pt
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Missing Bayesian dependencies. Install packages from "
            "`4 贝叶斯分析/requirements-bayes.txt` into the `code_health_bayes` conda environment first."
        ) from exc

    df, term_blocks, design_meta = build_variant_design(model_df, variables, variant, grid_config)
    y = df["AMR_AGG_z"].to_numpy(dtype=float)
    prov_codes, prov_levels = pd.factorize(df["Province"], sort=True)
    year_codes, year_levels = pd.factorize(df["Year"], sort=True)

    coords: dict[str, object] = {"obs_id": np.arange(len(df))}
    for block in term_blocks:
        coords[f"{block.name}_covariate"] = block.labels
    if variant.include_province:
        coords["province"] = prov_levels.astype(str).tolist()
    if variant.include_year:
        coords["year"] = year_levels.astype(str).tolist()

    with pm.Model(coords=coords) as model:
        y_data = pm.Data("y_data", y, dims="obs_id")
        mu = 0.0
        block_names: list[str] = []

        for block in term_blocks:
            coord_name = f"{block.name}_covariate"
            X = df[block.cols].to_numpy(dtype=float)
            X_data = pm.Data(f"X_{block.name}", X, dims=("obs_id", coord_name))
            beta = pm.Normal(
                f"beta_{block.name}",
                mu=0.0,
                sigma=block.prior_sigma,
                dims=coord_name,
            )
            mu = mu + pt.dot(X_data, beta)
            block_names.append(block.name)

        alpha = pm.Normal("alpha", mu=0.0, sigma=1.0)
        mu = mu + alpha

        if variant.include_province:
            prov_idx = pm.Data("prov_idx", prov_codes, dims="obs_id")
            sigma_province = pm.HalfNormal("sigma_province", sigma=0.5)
            province_offset = pm.Normal("province_offset", mu=0.0, sigma=1.0, dims="province")
            province_effect = pm.Deterministic(
                "province_effect",
                province_offset * sigma_province,
                dims="province",
            )
            mu = mu + province_effect[prov_idx]

        if variant.include_year:
            year_idx = pm.Data("year_idx", year_codes, dims="obs_id")
            year_raw = pm.Normal("year_raw", mu=0.0, sigma=0.5, dims="year")
            year_effect = pm.Deterministic(
                "year_effect",
                year_raw - pt.mean(year_raw),
                dims="year",
            )
            mu = mu + year_effect[year_idx]

        sigma_residual = pm.HalfNormal("sigma_residual", sigma=0.5)
        pm.Normal("y_obs", mu=mu, sigma=sigma_residual, observed=y_data, dims="obs_id")

        trace = pm.sample(
            draws=run_config.draws,
            tune=run_config.tune,
            chains=run_config.chains,
            cores=run_config.cores,
            target_accept=run_config.target_accept,
            progressbar=True,
            random_seed=42,
            return_inferencedata=True,
        )

    posterior_tables = []
    for block in term_blocks:
        draws = trace.posterior[f"beta_{block.name}"].stack(sample=("chain", "draw"))
        posterior_tables.append(
            summarize_beta_draws(draws, block.name, f"{block.name}_covariate")
        )
    posterior_summary = pd.concat(posterior_tables, ignore_index=True)

    var_names = ["alpha", *[f"beta_{block.name}" for block in term_blocks], "sigma_residual"]
    if variant.include_province:
        var_names.append("sigma_province")
    diag = az.summary(trace, var_names=var_names, hdi_prob=0.95).reset_index(names="parameter")
    diag = annotate_diagnostics(diag)

    metadata = {
        "n_obs": int(len(df)),
        "n_provinces": int(df["Province"].nunique()),
        "n_years": int(df["Year"].nunique()),
        "variables": variables,
        "term_blocks": [asdict(block) for block in term_blocks],
        **design_meta,
    }
    return trace, posterior_summary, diag, metadata


def sanitize_stem(value: str) -> str:
    text = value.replace(" | ", "__").replace(":", "").replace("/", "-")
    for token in [" ", "(", ")", "（", "）"]:
        text = text.replace(token, "")
    return text


def save_outputs(
    output_dir: Path,
    row: pd.Series,
    variant: VariantSpec,
    posterior_summary: pd.DataFrame,
    diag: pd.DataFrame,
    metadata: dict[str, object],
    run_config: RunConfig,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = sanitize_stem(str(row["model_id"]))
    suffix = f"{stem}__{variant.variant_id}"
    posterior_summary.to_csv(
        output_dir / f"{suffix}_posterior_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    diag.to_csv(output_dir / f"{suffix}_diagnostics.csv", index=False, encoding="utf-8-sig")

    merged_meta = {
        "model_id": row["model_id"],
        "scheme_id": row["scheme_id"],
        "scheme_source": row["scheme_source"],
        "fe_label": row["fe_label"],
        "performance_rank": int(row["performance_rank"]),
        "performance_score": float(row["performance_score"]),
        "freq_coef_R1xday": float(row["coef_R1xday"]),
        "freq_p_R1xday": float(row["p_R1xday"]),
        "freq_coef_AMC": float(row["coef_AMC"]),
        "freq_p_AMC": float(row["p_AMC"]),
        "variant_id": variant.variant_id,
        "variant_label": variant.label,
        "variant_rationale": variant.rationale,
        "run_config": asdict(run_config),
        **metadata,
    }
    (output_dir / f"{suffix}_metadata.json").write_text(
        json.dumps(merged_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_focus_bridge_summary(combined_posterior: pd.DataFrame) -> pd.DataFrame:
    focus = combined_posterior[combined_posterior["variable"].isin(FOCUS_VARIABLES)].copy()
    if focus.empty:
        return pd.DataFrame()

    id_cols = [
        "variant_id",
        "variant_label",
        "model_id",
        "scheme_id",
        "scheme_source",
        "fe_label",
        "freq_coef_R1xday",
        "freq_p_R1xday",
        "freq_coef_AMC",
        "freq_p_AMC",
    ]
    records: list[dict[str, object]] = []
    for keys, group in focus.groupby(id_cols, dropna=False):
        record = dict(zip(id_cols, keys))
        for _, row in group.iterrows():
            alias = CORE_ALIASES.get(row["variable"], normalize_name(row["variable"]))
            prefix = f"{row['effect_scope']}_{alias}"
            record[f"{prefix}_posterior_mean"] = float(row["posterior_mean"])
            record[f"{prefix}_crI_2_5"] = float(row["crI_2_5"])
            record[f"{prefix}_crI_97_5"] = float(row["crI_97_5"])
            record[f"{prefix}_prob_gt_0"] = float(row["prob_gt_0"])
        records.append(record)
    return pd.DataFrame(records).sort_values(["scheme_source", "scheme_id", "variant_id"]).reset_index(drop=True)


def save_combined_outputs(
    output_dir: Path,
    posterior_tables: list[pd.DataFrame],
    diagnostic_tables: list[pd.DataFrame],
) -> None:
    if not posterior_tables:
        return

    combined_posterior = pd.concat(posterior_tables, ignore_index=True)
    combined_posterior = combined_posterior.sort_values(
        ["scheme_source", "scheme_id", "variant_id", "effect_scope", "variable"]
    ).reset_index(drop=True)
    combined_posterior.to_csv(
        output_dir / "combined_posterior_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    focus_summary = combined_posterior[combined_posterior["variable"].isin(FOCUS_VARIABLES)].copy()
    if not focus_summary.empty:
        focus_summary.to_csv(
            output_dir / "focus_posterior_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
        focus_summary[
            focus_summary["effect_scope"].isin(["main", "interaction", "within", "within_interaction"])
        ].to_csv(
            output_dir / "focus_primary_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
        build_focus_bridge_summary(focus_summary).to_csv(
            output_dir / "focus_variant_bridge_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )

    if diagnostic_tables:
        combined_diagnostics = pd.concat(diagnostic_tables, ignore_index=True)
        combined_diagnostics = combined_diagnostics.sort_values(
            ["scheme_source", "scheme_id", "variant_id", "effect_scope", "parameter"]
        ).reset_index(drop=True)
        combined_diagnostics.to_csv(
            output_dir / "combined_diagnostics.csv",
            index=False,
            encoding="utf-8-sig",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Bayesian model grid that mirrors FE comparison logic before lag extensions.",
    )
    parser.add_argument(
        "--amr-path",
        type=Path,
        default=repo_root() / "amr_rate.csv",
    )
    parser.add_argument(
        "--x-path",
        type=Path,
        default=repo_root() / "climate_social_eco.csv",
    )
    parser.add_argument(
        "--candidate-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "2 固定效应模型" / "results" / "model_archive_12" / "selected_models.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "model_summaries",
    )
    parser.add_argument(
        "--selection-file",
        type=Path,
        default=Path(__file__).resolve().parent / "model_selection.toml",
    )
    parser.add_argument(
        "--model-ids",
        nargs="*",
        default=None,
        help="Optional list of exact model_id values to run.",
    )
    parser.add_argument(
        "--variant-ids",
        nargs="*",
        default=None,
        help="Optional override of model-grid variants to run.",
    )
    parser.add_argument("--draws", type=int, default=1000)
    parser.add_argument("--tune", type=int, default=1000)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--cores", type=int, default=2)
    parser.add_argument("--target-accept", type=float, default=0.9)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data, candidate combinations, and the Bayesian model grid without sampling.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    merged = load_analysis_frame(args.amr_path, args.x_path)
    all_candidates = pd.read_csv(args.candidate_file)
    selection_config = load_selection_config(args.selection_file)
    grid_config = load_model_grid_config(args.selection_file)
    if args.variant_ids:
        unknown = [variant_id for variant_id in args.variant_ids if variant_id not in VARIANT_LIBRARY]
        if unknown:
            raise ValueError(f"Unknown --variant-ids values: {unknown}")
        grid_config = ModelGridConfig(
            variant_ids=args.variant_ids,
            interaction_pairs=grid_config.interaction_pairs,
            interaction_terms=grid_config.interaction_terms,
        )
    candidates = apply_selection(all_candidates, selection_config, args.model_ids)

    run_config = RunConfig(
        draws=args.draws,
        tune=args.tune,
        chains=args.chains,
        cores=args.cores,
        target_accept=args.target_accept,
    )

    print(f"Loaded merged frame with {len(merged)} rows and {merged['Province'].nunique()} provinces.")
    print(f"Preparing {len(candidates)} candidate combinations across {len(grid_config.variant_ids)} Bayesian variants.")
    print(f"Variants: {grid_config.variant_ids}")
    print(f"Interaction terms: {grid_config.interaction_terms}")
    print("Selection source:", args.selection_file if not args.model_ids else "CLI --model-ids override")

    posterior_tables: list[pd.DataFrame] = []
    diagnostic_tables: list[pd.DataFrame] = []

    for _, row in candidates.iterrows():
        model_df, variables, frame_meta = prepare_model_frame(merged, row)
        column_report = frame_meta["missing_value_strategy"]["column_report"]
        imputed_summary = {
            item["column"]: item["missing_before"]
            for item in column_report
            if int(item["missing_before"]) > 0
        }
        print(
            f"- {row['model_id']}: n_obs={len(model_df)}, n_vars={len(variables)}, "
            f"vars={variables}, imputed={imputed_summary or 'none'}"
        )
        for variant_id in grid_config.variant_ids:
            variant = VARIANT_LIBRARY[variant_id]
            design_df, term_blocks, _ = build_variant_design(model_df, variables, variant, grid_config)
            print(
                f"  * {variant.variant_id}: blocks={[block.name for block in term_blocks]}, "
                f"provinces={design_df['Province'].nunique()}, years={design_df['Year'].nunique()}"
            )
            if args.dry_run:
                continue

            _, posterior_summary, diag, metadata = fit_variant_model(
                model_df=model_df,
                variables=variables,
                variant=variant,
                grid_config=grid_config,
                run_config=run_config,
            )
            metadata.update(frame_meta)
            posterior_summary = posterior_summary.assign(
                variant_id=variant.variant_id,
                variant_label=variant.label,
                model_id=row["model_id"],
                scheme_id=row["scheme_id"],
                scheme_source=row["scheme_source"],
                fe_label=row["fe_label"],
                freq_coef_R1xday=float(row["coef_R1xday"]),
                freq_p_R1xday=float(row["p_R1xday"]),
                freq_coef_AMC=float(row["coef_AMC"]),
                freq_p_AMC=float(row["p_AMC"]),
            )
            diag = diag.assign(
                variant_id=variant.variant_id,
                variant_label=variant.label,
                model_id=row["model_id"],
                scheme_id=row["scheme_id"],
                scheme_source=row["scheme_source"],
                fe_label=row["fe_label"],
            )
            save_outputs(args.output_dir, row, variant, posterior_summary, diag, metadata, run_config)
            posterior_tables.append(posterior_summary)
            diagnostic_tables.append(diag)

    if args.dry_run:
        print("Dry run completed.")
    else:
        save_combined_outputs(args.output_dir, posterior_tables, diagnostic_tables)
        print(f"Saved Bayesian model-grid outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
