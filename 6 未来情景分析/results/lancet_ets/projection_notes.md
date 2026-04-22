# AMR_AGG_raw_mean future projection notes

## Version: Lancet-like ETS baseline

- baseline_mode: `lancet_ets`
- meaning: Use ETS on the outcome itself as the future baseline, then add scenario deltas from future R1xday paths.
- model source: `5 ?????/results/AMR_AGG/model_screening/selected_models.csv`
- projection window: `2024-2050`
- roles: `main_model, robust_low_vif, robust_systematic, robust_strict_fe`
- external scenario variable: `R1xday`
- climate scenarios: annual CCKP `rx1day` for `ssp119 / ssp126 / ssp245 / ssp370 / ssp585`
- uncertainty paths: `median / p10 / p90`
- national result rule: project province-level AMR first, then take arithmetic mean across provinces without weighting.

## Workflow

1. Reuse the selected historical province-year models from `5 ?????`.
2. Re-estimate the historical panel coefficients and keep the historical scaling of covariates.
3. Only let `R1xday` vary by future scenario; all other covariates follow baseline paths.
4. Project AMR province by province, then average across provinces to obtain national trajectories and Figure-5-style outputs.

## Formula

```text
Y_it = alpha_i + lambda_t + sum_k beta_k Z_itk + epsilon_it
Y^base_it = ETS(Y_i, historical series)
Delta^scenario_it = sum_k beta_k * (Z^scenario_itk - Z^base_itk)
Y^scenario_it = Y^base_it + Delta^scenario_it
```

## Interpretation

- This version is closest to Lancet 2023: future baseline comes from ETS on AMR itself.
- Future R1xday scenarios are layered on top of ETS(AMR) as increments.
- The curve shape is therefore more strongly influenced by historical AMR inertia.

## Mortality extension

- The current repository still stops at antibiotic resistance rather than attributable deaths.
- If infection deaths and RR are added later, the Lancet-style PAF formula can be appended:

```text
PAF = p (RR - 1) / [1 + p (RR - 1)]
```