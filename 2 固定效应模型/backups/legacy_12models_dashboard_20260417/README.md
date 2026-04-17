# Legacy 12-Model Dashboard Backup

这份备份固定对应旧版比较线：

- 4 套人工方案：`方案A / 方案C / 方案D / 方案F`
- 3 种固定效应：`Year FE / Province FE / Two-way FE`
- 合计 12 个模型

## 页面结构

- `results_dashboard_legacy_12models.html`
  - 主页面：首页概览、方案 × FE 总览、综合排序、单模型详情
- `results_dashboard_legacy_12models_lancet.html`
  - 子页面：12 个模型的完整 Lancet 风格结果表
- `results_dashboard_legacy_12models_matrix.html`
  - 子页面：`variable_group_scheme_horizontal_compare.csv` 的横向比较矩阵

## 目录说明

- `data/`
  - 旧版 dashboard 使用的 `variable_group_scheme_*.csv` 快照
- `process/variable_group_schemes.ipynb`
  - 生成旧版结果的 notebook 快照
- `process/build_variable_group_schemes_notebook.py`
  - 上述 notebook 的脚本化构建器快照
- `process/build_results_dashboard_legacy_12models.py`
  - 基于这批旧版 CSV 重新生成三页 HTML 的脚本

## 重新生成

在仓库根目录执行：

```powershell
python -X utf8 ".\2 固定效应模型\backups\legacy_12models_dashboard_20260417\process\build_results_dashboard_legacy_12models.py"
```

脚本会读取当前备份目录下的 `data/*.csv`，重新生成同目录下的三个 HTML 页面。