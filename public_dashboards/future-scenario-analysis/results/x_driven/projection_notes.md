# AMR_AGG_raw_mean future projection notes

## Version: X-driven / Nature-like simplified baseline

- baseline_mode: `x_driven`
- meaning: Use future covariate paths as the baseline driver; baseline R1xday and other covariates follow ETS extensions, then future AMR is reconstructed from the historical association model.
- model source: `5 反事实推演/results/AMR_AGG/model_screening/selected_models.csv`
- projection window: `2024-2050`
- roles: `strict_main_model, strict_top_02, strict_top_03, strict_top_04, strict_top_05, strict_top_06, strict_top_07, strict_top_08, robust_systematic, robust_systematic_2, robust_low_vif, main_model`
- current scope: reuse the current 12-model archive instead of discussing only `main_model`
- external scenario variable: `R1xday`
- climate scenarios: annual CCKP `rx1day` for `ssp119 / ssp126 / ssp245 / ssp370 / ssp585`
- uncertainty paths: `median / p10 / p90`
- national result rule: project province-level AMR first, then take arithmetic mean across provinces without weighting.

## 12-model archive

- The future workflow now inherits the same 12 archived model roles used by the counterfactual module.
- Detailed per-model interpretation is written to `model_role_detailed_analysis.md`; each role is discussed separately rather than only extending `main_model`.

## Key role summary

| model        | scheme            |   coef_r1xday |   baseline_2050 | strongest_scenario   |   strongest_delta |   spread_2050 |
|:-------------|:------------------|--------------:|----------------:|:---------------------|------------------:|--------------:|
| 严筛主模型   | SYS_09851         |      0.855329 |         34.7017 | SSP5-8.5（rx1day）   |          0.277843 |      0.127365 |
| 严筛模型 2   | SYS_10001         |      0.891809 |         34.4286 | SSP5-8.5（rx1day）   |          0.289693 |      0.132797 |
| 严筛模型 3   | SYS_10002         |      0.914797 |         34.666  | SSP5-8.5（rx1day）   |          0.29716  |      0.136221 |
| 严筛模型 4   | SYS_09941         |      0.979014 |         34.3824 | SSP5-8.5（rx1day）   |          0.31802  |      0.145783 |
| 严筛模型 5   | SYS_09926         |      0.946959 |         34.5879 | SSP5-8.5（rx1day）   |          0.307608 |      0.14101  |
| 严筛模型 6   | SYS_09927         |      0.981324 |         34.8673 | SSP5-8.5（rx1day）   |          0.318771 |      0.146127 |
| 严筛模型 7   | SYS_09791         |      0.984922 |         34.897  | SSP5-8.5（rx1day）   |          0.319939 |      0.146663 |
| 严筛模型 8   | SYS_09776         |      0.954418 |         35.0155 | SSP5-8.5（rx1day）   |          0.310031 |      0.14212  |
| 稳健性模型 2 | SYS_09556         |      1.06376  |         32.0123 | SSP5-8.5（rx1day）   |          0.345549 |      0.158402 |
| 稳健性模型 3 | SYS_09557         |      1.07481  |         31.7098 | SSP5-8.5（rx1day）   |          0.34914  |      0.160048 |
| 稳健性模型 1 | 方案F_低VIF主线组 |      0.872837 |         30.7911 | SSP5-8.5（rx1day）   |          0.28353  |      0.129972 |
| 主模型       | 方案A_平衡主线组  |      0.868613 |         29.4214 | SSP5-8.5（rx1day）   |          0.282158 |      0.129343 |
