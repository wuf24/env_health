# AMR_AGG_raw_mean future projection notes

## Version: X-driven / Nature-like simplified baseline

- baseline_mode: `x_driven`
- meaning: Use future covariate paths as the baseline driver; baseline covariates follow ETS extensions, then future AMR is reconstructed from the historical association model and perturbed by supported climate scenario inputs.
- model source: `5 反事实推演/results/AMR_AGG/model_screening/selected_models.csv`
- projection window: `2024-2050`
- roles: `main_model, strict_main_model, strict_top_02, strict_top_03, strict_top_04, strict_top_05, strict_top_06, strict_top_07, strict_top_08, robust_systematic, robust_systematic_2, robust_low_vif`
- current scope: reuse the current 12-model archive instead of discussing only `main_model`
- external scenario variables: `R1xday`, plus `TA（°C）` / `省平均气温` when present in the model
- climate scenarios: annual CCKP `rx1day` and `tas` for `ssp119 / ssp126 / ssp245 / ssp370 / ssp585`
- uncertainty paths: `median / p10 / p90`
- national result rule: project province-level AMR first, then take arithmetic mean across provinces without weighting.

## 12-model archive

- The future workflow now inherits the same 12 archived model roles used by the counterfactual module.
- Detailed per-model interpretation is written to `model_role_detailed_analysis.md`; each role is discussed separately rather than only extending `main_model`.

## Key role summary

| model        | scheme            |   coef_r1xday |   baseline_2050 | strongest_scenario   |   strongest_delta |   spread_2050 |
|:-------------|:------------------|--------------:|----------------:|:---------------------|------------------:|--------------:|
| 主模型       | SYS_08952         |      0.868143 |         33.5221 | SSP5-8.5（climate）  |           1.48728 |       2.37774 |
| 严筛主模型   | SYS_09851         |      0.855329 |         34.7017 | SSP5-8.5（climate）  |           1.31087 |       2.0545  |
| 严筛模型 2   | SYS_10001         |      0.891809 |         34.4286 | SSP5-8.5（climate）  |           1.29095 |       2.00066 |
| 严筛模型 3   | SYS_10002         |      0.914797 |         34.666  | SSP5-8.5（climate）  |           1.81068 |       2.95973 |
| 严筛模型 4   | SYS_09941         |      0.979014 |         34.3824 | SSP5-8.5（climate）  |           1.43481 |       2.22918 |
| 严筛模型 5   | SYS_09926         |      0.946959 |         34.5879 | SSP5-8.5（climate）  |           1.47948 |       2.32716 |
| 严筛模型 6   | SYS_09927         |      0.981324 |         34.8673 | SSP5-8.5（climate）  |           2.0165  |       3.31327 |
| 严筛模型 7   | SYS_09791         |      0.984922 |         34.897  | SSP5-8.5（climate）  |           1.59235 |       2.52036 |
| 严筛模型 8   | SYS_09776         |      0.954418 |         35.0155 | SSP5-8.5（climate）  |           1.63373 |       2.6115  |
| 稳健性模型 2 | SYS_09556         |      1.06376  |         32.0123 | SSP5-8.5（climate）  |           1.04066 |       1.45515 |
| 稳健性模型 3 | SYS_09557         |      1.07481  |         31.7098 | SSP5-8.5（climate）  |           1.345   |       2.01784 |
| 稳健性模型 1 | 方案F_低VIF主线组 |      0.872837 |         30.7911 | SSP5-8.5（climate）  |           1.39507 |       2.20358 |
