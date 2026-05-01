# AMR_AGG_raw_mean future projection notes

## Version: Lancet-like ETS baseline

- baseline_mode: `lancet_ets`
- meaning: Use ETS on the outcome itself as the future baseline, then add scenario deltas from future climate paths such as R1xday and supported temperature proxies.
- model source: `5 反事实推演/results/AMR_AGG/model_screening/selected_models.csv`
- projection window: `2024-2050`
- roles: `main_model, strict_main_model, strict_top_02, strict_top_03, strict_top_04, strict_top_05, strict_top_06, strict_top_07, strict_top_08, robust_systematic, robust_systematic_2, robust_low_vif`
- current scope: reuse the current 12-model archive instead of discussing only `main_model`
- external scenario variables: `R1xday`, plus `TA（°C）` / `省平均气温` when present in the model; `抗菌药物使用强度` can be reduced by intervention scenario.
- climate scenarios: annual CCKP `rx1day` and `tas` for `ssp119 / ssp126 / ssp245 / ssp370 / ssp585`; intervention scenario: `amc_reduce_50` linearly reaches 50% of baseline AMC by 2050.
- uncertainty paths: `median / p10 / p90`
- national result rule: project province-level AMR first, then take arithmetic mean across provinces without weighting.

## 12-model archive

- The future workflow now inherits the same 12 archived model roles used by the counterfactual module.
- Detailed per-model interpretation is written to `model_role_detailed_analysis.md`; each role is discussed separately rather than only extending `main_model`.

## Key role summary

| model        | scheme            |   coef_r1xday |   baseline_2050 | strongest_scenario   |   strongest_delta |   spread_2050 |
|:-------------|:------------------|--------------:|----------------:|:---------------------|------------------:|--------------:|
| 主模型       | SYS_08952         |      0.868143 |           27.21 | SSP5-8.5（climate）  |           1.48728 |       3.00623 |
| 严筛主模型   | SYS_09851         |      0.855329 |           27.21 | SSP5-8.5（climate）  |           1.31087 |       2.63173 |
| 严筛模型 2   | SYS_10001         |      0.891809 |           27.21 | SSP5-8.5（climate）  |           1.29095 |       2.59633 |
| 严筛模型 3   | SYS_10002         |      0.914797 |           27.21 | SSP5-8.5（climate）  |           1.81068 |       3.18706 |
| 严筛模型 4   | SYS_09941         |      0.979014 |           27.21 | SSP5-8.5（climate）  |           1.43481 |       2.99034 |
| 严筛模型 5   | SYS_09926         |      0.946959 |           27.21 | SSP5-8.5（climate）  |           1.47948 |       3.03275 |
| 严筛模型 6   | SYS_09927         |      0.981324 |           27.21 | SSP5-8.5（climate）  |           2.0165  |       3.61105 |
| 严筛模型 7   | SYS_09791         |      0.984922 |           27.21 | SSP5-8.5（climate）  |           1.59235 |       3.12317 |
| 严筛模型 8   | SYS_09776         |      0.954418 |           27.21 | SSP5-8.5（climate）  |           1.63373 |       3.1627  |
| 稳健性模型 2 | SYS_09556         |      1.06376  |           27.21 | SSP5-8.5（climate）  |           1.04066 |       2.48623 |
| 稳健性模型 3 | SYS_09557         |      1.07481  |           27.21 | SSP5-8.5（climate）  |           1.345   |       2.82192 |
| 稳健性模型 1 | 方案F_低VIF主线组 |      0.872837 |           27.21 | SSP5-8.5（climate）  |           1.39507 |       2.96267 |
