# Dashboard Backup Manifest

备份时间: 2026-04-17 17:02:11

这份备份用于保留 `2 固定效应模型` 下当前 dashboard 的页面文件，以及生成这些页面所依赖的关键脚本和数据快照。

## 备份内容

### 1. 已生成页面

- `results_dashboard.html`
- `results_dashboard_lancet.html`
- `results_dashboard_matrix.html`

### 2. 生成脚本

- `tools/build_results_dashboard.py`
- `tools/run_variable_space_exhaustive.py`

### 3. 原始输入数据

- `raw_inputs/amr_rate.csv`
- `raw_inputs/climate_social_eco.csv`

### 4. 中间结果快照

位于 `results_snapshot/`，包含当前 dashboard 所依赖的 `exhaustive_*` 结果文件快照。

## 生成链路

1. `raw_inputs/amr_rate.csv` 和 `raw_inputs/climate_social_eco.csv`
2. `tools/run_variable_space_exhaustive.py`
3. `results_snapshot/exhaustive_*`
4. `tools/build_results_dashboard.py`
5. `results_dashboard*.html`

## 说明

- 这是一份“可回溯”的快照备份，目的是避免后续更新脚本、结果文件或页面后，无法恢复当前 dashboard 状态。
- 原项目中的对应文件没有删除，也没有替换。
