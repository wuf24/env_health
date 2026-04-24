# Legacy 12-Model Dashboard Backup

这个目录保存的是 **旧版人工变量组比较线** 的页面快照。  
它固定对应：

- `4` 套人工方案：`方案A / 方案C / 方案D / 方案F`
- `3` 种固定效应：`Year FE / Province FE / Two-way FE`
- 合计 `12` 个模型

它的定位不是当前主线，而是：

> 在 exhaustive 搜索和统一 `12` 模型归档成型之前，人工变量组比较时代的公开页面备份。

## 它和当前主线的关系

当前项目主筛选已经升级到：

- `2 固定效应模型/results/exhaustive_model_summary.csv`
- `2 固定效应模型/results/strict_top8_archive/strict_top8_models.csv`
- `2 固定效应模型/results/model_archive_12/selected_models.csv`

因此这个目录现在的主要作用是：

- 回看人工方案比较时代的页面结构；
- 和当前 exhaustive 版页面并排对照；
- 保留历史 public bundle 的可重建能力。

## 页面结构

- `results_dashboard_legacy_12models.html`
  - 主页面：首页概览、方案 × FE 总览、综合排序、单模型详情
- `results_dashboard_legacy_12models_lancet.html`
  - 子页面：12 个模型的完整 Lancet 风格结果表
- `results_dashboard_legacy_12models_matrix.html`
  - 子页面：横向比较矩阵

## 目录说明

- `data/`
  - 旧版 dashboard 使用的 `variable_group_scheme_*.csv` 快照
- `process/variable_group_schemes.ipynb`
  - 当时生成旧版结果的 notebook 快照
- `process/build_variable_group_schemes_notebook.py`
  - 上述 notebook 的脚本化构建器快照
- `process/build_results_dashboard_legacy_12models.py`
  - 基于这批旧版 CSV 重新生成三页 HTML 的脚本

## 什么时候看这里

- 你需要解释“人工方案时代”和“当前 exhaustive / 统一模型归档时代”有什么差别；
- 你要回看 2026-04-17 那一版公开页面到底长什么样；
- 你要复原旧版 12 模型比较页做历史对照。

如果你想看当前主线，请优先回到：

- `../../README.md`
- `../../results_dashboard.html`
- `../../results/model_archive_12/selected_models.csv`

## 重新生成

在仓库根目录执行：

```powershell
python -X utf8 ".\2 固定效应模型\backups\legacy_12models_dashboard_20260417\process\build_results_dashboard_legacy_12models.py"
```

脚本会读取本备份目录下的 `data/*.csv`，重新生成同目录下的三个 HTML 页面。

## 一句话记住这个目录

这是“人工变量组 12 模型比较页”的历史快照，不是当前 exhaustive 主线页面。
