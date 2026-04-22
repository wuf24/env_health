# 6 未来情景分析

这个目录已经进一步整理。

现在的原则是：

- `results/` 直接放当前主线结果
- 不再额外套一层 `AMR_AGG_RAW/`
- 旧版、重复版、归档内容统一移到 `bakeup/`

`bakeup` 按你的原话保留这个拼写。

## 当前最清晰的目录

```text
6 未来情景分析/
├─ README.md
├─ data_raw/
├─ data_processed/
├─ docs/
├─ logs/
├─ results/
│  ├─ common_inputs/
│  ├─ model_screening/
│  ├─ baseline_mode_compare/
│  ├─ lancet_ets/
│  ├─ x_driven/
│  └─ run_metadata.json
├─ scripts/
└─ bakeup/
```

## 1. 现在应该只看哪里

### 1.1 主结果

- `Lancet ETS` 版：
  - [future_scenario_projection_panel.csv](</e:/MALA/Code_health/6 未来情景分析/results/lancet_ets/projection_outputs/future_scenario_projection_panel.csv>)
  - [figure5_style_main.png](</e:/MALA/Code_health/6 未来情景分析/results/lancet_ets/figures/figure5_style_main.png>)

- `X-driven` 版：
  - [future_scenario_projection_panel.csv](</e:/MALA/Code_health/6 未来情景分析/results/x_driven/projection_outputs/future_scenario_projection_panel.csv>)
  - [figure5_style_main.png](</e:/MALA/Code_health/6 未来情景分析/results/x_driven/figures/figure5_style_main.png>)

- 两版对照：
  - [main_model_2050_compare.csv](</e:/MALA/Code_health/6 未来情景分析/results/baseline_mode_compare/main_model_2050_compare.csv>)
  - [scenario_summary_2050_compare.csv](</e:/MALA/Code_health/6 未来情景分析/results/baseline_mode_compare/scenario_summary_2050_compare.csv>)
  - [baseline_mode_comparison.md](</e:/MALA/Code_health/6 未来情景分析/results/baseline_mode_compare/baseline_mode_comparison.md>)

### 1.2 地区版结果

分区映射表：

- [province_to_region_7zones.csv](</e:/MALA/Code_health/6 未来情景分析/data_processed/province_to_region_7zones.csv>)

地区结果：

- `Lancet ETS` 版：
  - [regional_yearly.csv](</e:/MALA/Code_health/6 未来情景分析/results/lancet_ets/regional_outputs/regional_yearly.csv>)
  - [region_summary_2050.csv](</e:/MALA/Code_health/6 未来情景分析/results/lancet_ets/regional_outputs/region_summary_2050.csv>)
  - [regional_figure5_grid.png](</e:/MALA/Code_health/6 未来情景分析/results/lancet_ets/regional_figures/regional_figure5_grid.png>)
  - [regional_delta_2050_heatmap.png](</e:/MALA/Code_health/6 未来情景分析/results/lancet_ets/regional_figures/regional_delta_2050_heatmap.png>)

- `X-driven` 版：
  - [regional_yearly.csv](</e:/MALA/Code_health/6 未来情景分析/results/x_driven/regional_outputs/regional_yearly.csv>)
  - [region_summary_2050.csv](</e:/MALA/Code_health/6 未来情景分析/results/x_driven/regional_outputs/region_summary_2050.csv>)
  - [regional_figure5_grid.png](</e:/MALA/Code_health/6 未来情景分析/results/x_driven/regional_figures/regional_figure5_grid.png>)
  - [regional_delta_2050_heatmap.png](</e:/MALA/Code_health/6 未来情景分析/results/x_driven/regional_figures/regional_delta_2050_heatmap.png>)

- 地区总对照：
  - [regional_summary_2050_compare.csv](</e:/MALA/Code_health/6 未来情景分析/results/baseline_mode_compare/regional_summary_2050_compare.csv>)

## 2. 脚本保留什么

### 数据准备

- `download_cckp_rx1day.py`
- `check_cckp_files.py`
- `merge_cckp_rx1day.py`
- `download_cckp_rx1day_timeseries.py`
- `check_cckp_rx1day_timeseries_files.py`
- `merge_cckp_rx1day_timeseries.py`

### 未来情景预测

- [run_future_scenario_projection.py](</e:/MALA/Code_health/6 未来情景分析/scripts/run_future_scenario_projection.py>)
  - 生成全国层面的双 baseline 结果

- [run_regional_future_figure5.py](</e:/MALA/Code_health/6 未来情景分析/scripts/run_regional_future_figure5.py>)
  - 把省级预测汇总成 7 大区结果和地区图

## 3. 运行命令

从项目根目录运行。

### 3.1 全国主流程

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_future_scenario_projection.py"
```

如果只跑某一种 baseline：

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_future_scenario_projection.py" --baseline-modes lancet_ets
python -X utf8 ".\6 未来情景分析\scripts\run_future_scenario_projection.py" --baseline-modes x_driven
```

### 3.2 地区版流程

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_regional_future_figure5.py"
```

如果只跑某一种 baseline：

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_regional_future_figure5.py" --baseline-modes lancet_ets
python -X utf8 ".\6 未来情景分析\scripts\run_regional_future_figure5.py" --baseline-modes x_driven
```

## 4. bakeup 里有什么

已经移到 [bakeup](</e:/MALA/Code_health/6 未来情景分析/bakeup>) 的内容包括：

- 旧版 `AMR_AGG`
- 以前那套 `results/AMR_AGG_RAW/` 嵌套目录
- 旧根目录重复输出
- 旧日志
- `__pycache__`

也就是说，`results/AMR_AGG_RAW/` 现在已经不是当前主线，而是旧结构，已经归档。

## 5. 现在不要再看的旧路径

下面这些都不再是当前主线：

- `results/AMR_AGG_RAW/`
- `bakeup/results_legacy/AMR_AGG/`
- `bakeup/results_legacy/AMR_AGG_RAW_root_legacy/`
- `bakeup/results_legacy/AMR_AGG_RAW_nested_outcome_dir/`

## 6. 当前推荐阅读顺序

1. 先看 [两种baseline版本详解.md](</e:/MALA/Code_health/6 未来情景分析/docs/两种baseline版本详解.md>)
2. 再看 `results/lancet_ets/` 和 `results/x_driven/`
3. 然后看 `results/baseline_mode_compare/`
4. 最后看 `regional_outputs/` 和 `regional_figures/`

## 7. 省级尺度科学图

新增脚本：

- [run_provincial_future_figure.py](</e:/MALA/Code_health/6 未来情景分析/scripts/run_provincial_future_figure.py>)
  - 读取现有 `future_scenario_projection_panel.csv`
  - 输出“全国均值情景轨迹 + 省份×年份热图”的省级未来情景图
  - 省份按七大区分组，并按 2050 年情景平均增量排序

运行命令：

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_provincial_future_figure.py"
```

如只跑某一类 baseline：

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_provincial_future_figure.py" --baseline-modes lancet_ets
python -X utf8 ".\6 未来情景分析\scripts\run_provincial_future_figure.py" --baseline-modes x_driven
```

默认输出位置：

- `results/lancet_ets/provincial_figures/provincial_future_scenario_panel.png`
- `results/x_driven/provincial_figures/provincial_future_scenario_panel.png`

## 8. 双情景对比图

新增脚本：

- [run_dual_scenario_compare_figure.py](</e:/MALA/Code_health/6 未来情景分析/scripts/run_dual_scenario_compare_figure.py>)
  - 上方输出全国轨迹图
  - 左下输出省级玫瑰图
  - 右下输出 2050 年省级哑铃排序图
  - 默认比较 `SSP1-1.9` 与 `SSP5-8.5`

运行命令：

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_dual_scenario_compare_figure.py"
```

如需切换为其他两种情景：

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_dual_scenario_compare_figure.py" --scenario-pair ssp126 ssp370
```

默认输出位置：

- `results/lancet_ets/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585.png`
- `results/x_driven/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585.png`

## 8.1 Dual-scenario update (2026-04-22)

- Default dual-scenario rendering now uses `--value-mode delta`
- Top national trajectory and the bottom-left rose chart show `ΔAMR vs baseline`
- The bottom-right dumbbell panel is re-centered to `SSP1-1.9 = 0`, so line length equals the provincial SSP gap
- If you need the previous absolute-AMR view, run:

```bash
python -X utf8 ".\6 未来情景分析\scripts\run_dual_scenario_compare_figure.py" --value-mode predicted
```

- Updated default output paths:
  - `results/lancet_ets/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585_delta.png`
  - `results/x_driven/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585_delta.png`
