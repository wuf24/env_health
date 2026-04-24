# 5 反事实推演

新增方法说明见：

- [论文格式方法小结.md](</e:/MALA/Code_health/5 反事实推演/论文格式方法小结.md>)

这个目录不是重新从头拟合一个普通多元回归，而是在固定效应主筛选已经完成后，继续回答：

- 如果把气候变量恢复到基准状态，预测的 AMR 会怎样变化？
- 这种变化在不同模型角色之间是否一致？
- 哪些结果是“方向稳定”的，哪些对模型设定更敏感？

## 这个目录在整条链里的位置

它承接的是前三层工作：

1. `1 单因素分析/`
   - 已完成变量摸底和展示。
2. `2 固定效应模型/`
   - 已完成 FE 比较、系统穷举、strict top-8 和统一 `12` 模型归档。
3. `4 贝叶斯分析/`
   - 已对重点候选模型做 Year-only / Province-only / Province+year 的桥接检验。

因此，这里正确的工作方式是：

- 先读取已有 FE 模型归档；
- 再在同一套模型之上做 observed vs counterfactual 对照；
- 而不是重新回到“从头选变量”的阶段。

## 当前默认口径

### 脚本入口

```bash
python -X utf8 "5 反事实推演/run_counterfactual_analysis.py"
```

### 页面入口

```bash
python -X utf8 "5 反事实推演/build_counterfactual_dashboard.py"
```

### 当前生成页面

- `results/AMR_AGG/counterfactual_results_dashboard.html`

### 默认行为

- outcome 先跑 `AMR_AGG`
- 默认基准年为 `2014`
- 默认地图与模型比较图展示 `2023`
- 默认读取 `2 固定效应模型/results/model_archive_12/selected_models.csv`

## 当前 12 模型归档怎么接入这里

反事实部分现在承接的是统一的 `12` 模型归档，而不是旧版“只围绕主模型 + 少量稳健性模型”的口径。

这 `12` 个角色包括：

- 手选 Year FE `4` 模型：
  - `main_model`
  - `robust_low_vif`
  - `robust_systematic`
  - `robust_systematic_2`
- 严筛 `8` 模型：
  - `strict_main_model`
  - `strict_top_02` 到 `strict_top_08`

这意味着当前反事实推演的口径已经变成：

- `main_model` 仍然是正文主叙事入口；
- 但其余 `11` 个模型也一起参与反事实量化；
- 输出中会显式区分“方向稳定的结论”和“对设定敏感的结论”。

## 反事实情景设计

脚本会按模型变量构成自动生成情景，并对重复情景自动去重。  
当前常见情景包括：

1. 所有气候变量恢复基准
2. 仅 `R1xday` 恢复基准
3. 仅温度变量恢复基准
4. `R1xday + 温度变量` 共同恢复基准

这里“恢复基准”的含义是：

- 按省份取基准年份或基准期的省内均值；
- 其他协变量保持实际值；
- 使用原 FE 模型同一套系数和固定效应做 observed / counterfactual 对照。

## 当前输出结构

以 `AMR_AGG` 为例，结果会写到三个层次：

- `results/AMR_AGG/model_screening/`
- `results/AMR_AGG/counterfactual_outputs/`
- `results/AMR_AGG/figures/`

同时还会生成：

- `results/AMR_AGG/run_metadata.json`
- `results/AMR_AGG/counterfactual_results_dashboard.html`
- `results/AMR_AGG/model_role_detail_summary.csv`
- `results/AMR_AGG/model_role_detailed_analysis.md`

## 结果文件分别做什么

### `model_screening/`

这里主要保存“本次推演到底读取了哪些模型”的说明文件：

- `selected_models.csv`
  - 当前进入反事实推演的模型清单
- `selected_models_source_snapshot.csv`
  - 统一 `12` 模型归档的快照副本
- `fe_spec_comparison.csv`
  - FE 设定层面的汇总比较
- `bayes_variant_summary.csv`
  - 来自贝叶斯桥接的补充摘要
- `top20_ranking_snapshot.csv`
  - 当时引用的高分模型快照

### `counterfactual_outputs/`

这里是定量结果主区：

- `counterfactual_panel_predictions.csv`
  - 每个“模型 × 情景 × 省份 × 年份”的实际预测值、反事实预测值、差值和相对变化
- `national_yearly.csv`
  - 全国年度平均结果
- `national_overall.csv`
  - 全国层面的总体汇总
- `province_average.csv`
  - 分省长期平均结果
- `latest_year_province.csv`
  - 目标年份的分省结果，适合地图

### `figures/`

当前图形已经不只围绕 `main_model`，而是覆盖全部 `12` 个模型角色。  
例如：

- `national_yearly_main_model.png`
- `national_yearly_robust_low_vif.png`
- `national_yearly_robust_systematic.png`
- `national_yearly_robust_systematic_2.png`
- `national_yearly_strict_main_model.png`
- `national_yearly_strict_top_02.png` 到 `strict_top_08.png`
- 各模型对应的 `province_map_*_latest_year.png`
- `model_comparison_heatmap_latest_year.png`
- `scenario_comparison_bar.png`

## 页面入口怎么用

`counterfactual_results_dashboard.html` 现在不只是一个“主模型单页”。

它至少包含三层用途：

1. 看 `12` 模型整体比较；
2. 在“单模型聚焦分析”中切换不同模型角色；
3. 查看某个模型在不同情景下的全国趋势、省级异质性和比较矩阵。

也就是说，这个页面已经从“展示一个主模型”升级成“展示统一模型归档的反事实层”。

## 当前最值得直接看的文件

如果只想快速把握当前结果，优先看：

- `results/AMR_AGG/run_metadata.json`
- `results/AMR_AGG/model_screening/selected_models.csv`
- `results/AMR_AGG/counterfactual_outputs/national_overall.csv`
- `results/AMR_AGG/counterfactual_outputs/national_yearly.csv`
- `results/AMR_AGG/model_role_detail_summary.csv`
- `results/AMR_AGG/model_role_detailed_analysis.md`
- `results/AMR_AGG/selection_and_writeup_notes.md`

## 当前写作上怎么使用这层

这层最适合支撑：

- “如果气候变量恢复到基准状态，AMR 风险将怎样变化”的量化表达；
- 主模型与稳健性模型之间结果方向是否一致的比较；
- 全国平均、分省和目标年份地图的叙事；
- 对“当前主结论是否高度依赖某一个模型”的回答。

它不适合替代的内容包括：

- 前面 FE 的变量筛选逻辑；
- 贝叶斯交互项对 `amplifies` 的检验；
- 单菌种异质性的细粒度讨论。

## 如何扩展到单独 AMR 指标

当前脚本流程已经拆成：

1. outcome 构造
2. FE 结果筛选
3. 模型拟合
4. counterfactual simulation
5. 汇总与出图

扩展到单独指标时，建议直接指定 outcome：

```bash
python -X utf8 "5 反事实推演/run_counterfactual_analysis.py" --outcome CRKP --single-outcome-scale raw
python -X utf8 "5 反事实推演/run_counterfactual_analysis.py" --outcome CRAB --single-outcome-scale raw
```

需要特别注意两点：

- 如果要与 `3 单固定效应模型/` 严格对齐，先确认单指标主分析使用的是原始率还是标准化率，再决定 `--single-outcome-scale`；
- 如果后续希望每个单指标也先做候选模型筛选，建议先按 outcome 生成对应模型归档，再重复同样的反事实流程。

## 与 public dashboard 的关系

当前 public 发布副本位于：

- `public_dashboards/counterfactual-amr-agg/`

public bundle 会同步：

- dashboard 页面
- 关键 CSV
- 主要 figures
- `selection_and_writeup_notes.md`

因此写 README 或结果说明时，默认应以 `results/AMR_AGG/` 里的源文件为准，再由 public 层做发布复制。

## 一句话记住这个目录

这里负责把“当前最值得保留的 FE 模型”推进成可量化、可比较、可出图的反事实结果层，而且已经从单主模型扩展成统一 `12` 模型归档框架。
