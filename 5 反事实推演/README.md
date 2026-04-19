# 5 反事实推演

新增论文格式方法小结：
- [论文格式方法小结.md](</e:/MALA/Code_health/5 反事实推演/论文格式方法小结.md>)

这一部分不是重新从头建立一个普通多元线性回归，而是站在你已经完成的三条主线上继续往前走：

1. `1 单因素分析/` 已经完成变量筛选与关系摸底。
2. `2 固定效应模型/` 已经完成多组候选模型、三类 FE 设定和系统穷举。
3. `4 贝叶斯分析/` 已经对重点候选模型做了 year-only / province-only / province+year 的桥接验证。

因此这里的正确入口是：

- 先比较既有 FE 候选模型，而不是重建普通回归。
- 再从中筛出主模型和稳健性模型。
- 最后基于这些已筛出的 FE 模型做 counterfactual simulation。

## 文献借鉴的分工

- Lancet Planetary Health 2023
  你给的 Lancet 链接对应的是 2023 年发表的全球 PM2.5 与临床耐药分析。我这里只借它的环境-AMR 主分析框架、控制变量组织方式和结果表风格，不照搬全球模型。
- Nature Medicine 2025
  借它“单因素筛选 → 多因素整合 → 扩展分析/情景预测”的衔接逻辑，并用现有贝叶斯结果作为 FE 选模后的桥接证据。
- Nature 2023
  借它“先确定主模型，再拿 benchmark 状态与 observed state 做 counterfactual comparison”的思路；这里的 benchmark 改写为省级气候变量在基准年份或基准期的水平。

## 当前脚本做了什么

脚本入口：

```bash
python -X utf8 "5 反事实推演/run_counterfactual_analysis.py"
```

网页入口：

```bash
python -X utf8 "5 反事实推演/build_counterfactual_dashboard.py"
```

生成后的网页文件：

- [results/AMR_AGG/counterfactual_results_dashboard.html](</e:/MALA/Code_health/5 反事实推演/results/AMR_AGG/counterfactual_results_dashboard.html>)

默认行为：

- 先跑 `AMR_AGG`
- 默认基准年为 `2014`
- 默认地图和模型对比图展示 `2023`

默认筛选逻辑：

1. 先汇总 `2 固定效应模型/results/exhaustive_model_summary.csv`
2. 比较三类 FE 设定的综合分、核心变量方向稳定性和显著性占比
3. 将 `Year FE only` 作为正文反事实推演的主入口
4. 选出 4 个模型：
   - 主模型：理论最完整且 `R1xday` 与 `AMC` 同时显著的 curated Year FE
   - 稳健性模型 1：低 VIF 的 curated Year FE
   - 稳健性模型 2：已有贝叶斯桥接的 systematic Year FE
   - 稳健性模型 3：主模型同变量集下的双向 FE

## 反事实情景

脚本会按模型变量构成自动生成以下情景，并对重复情景自动去重：

1. 所有气候变量恢复基准
2. 仅 `R1xday` 恢复基准
3. 仅温度变量恢复基准
4. `R1xday + 温度变量` 共同恢复基准

这里的“恢复基准”是指：

- 按省份取基准年份或基准期的省内水平
- 其他协变量保持实际值
- 用原 FE 模型同一套系数和固定效应做 observed / counterfactual 对照

## 输出目录

以 `AMR_AGG` 为例，结果会写到：

- [results/AMR_AGG/model_screening](</e:/MALA/Code_health/5 反事实推演/results/AMR_AGG/model_screening>)
- [results/AMR_AGG/counterfactual_outputs](</e:/MALA/Code_health/5 反事实推演/results/AMR_AGG/counterfactual_outputs>)
- [results/AMR_AGG/figures](</e:/MALA/Code_health/5 反事实推演/results/AMR_AGG/figures>)

主要文件包括：

- `fe_spec_comparison.csv`
  三类 FE 设定的汇总比较
- `selected_models.csv`
  主模型与稳健性模型清单
- `counterfactual_panel_predictions.csv`
  每个“模型 × 情景 × 省份 × 年份”的实际预测值、反事实预测值、差值和相对变化
- `national_yearly.csv`
  全国年度平均结果
- `province_average.csv`
  分省平均结果
- `latest_year_province.csv`
  目标年份的分省结果，适合做地图
- `selection_and_writeup_notes.md`
  面向正文写作的解释说明

## 图形输出

脚本至少会生成：

- `national_yearly_main_model.png`
  主模型下全国年度实际情景与反事实情景时间序列图
- `province_map_main_model_latest_year.png`
  主模型主情景在目标年份的分省地图
- `model_comparison_heatmap_latest_year.png`
  不同模型下反事实结果对比图
- `scenario_comparison_bar.png`
  不同情景下反事实结果对比图

此外还会生成一个静态网页，把模型筛选、结果解释、图形和结果表整合到同一页里，适合直接查看和汇报展示。

## 如何扩展到 13 个单独 AMR 指标

这套脚本已经把流程拆成了：

1. outcome 构造
2. FE 结果筛选
3. 模型拟合
4. counterfactual simulation
5. 汇总与出图

扩展时建议这样做：

```bash
python -X utf8 "5 反事实推演/run_counterfactual_analysis.py" --outcome CRKP --single-outcome-scale raw
python -X utf8 "5 反事实推演/run_counterfactual_analysis.py" --outcome CRAB --single-outcome-scale raw
```

注意两点：

- 如果要与 `3 单固定效应模型/` 严格保持一致，请先确认单指标主分析使用的是原始率还是标准化率，再决定 `--single-outcome-scale`。
- 如果后续希望每个单指标也先做“候选模型筛选”，可以把当前的 `build_selected_models()` 扩展为按 outcome 单独读取对应的 FE 长表或结果汇总，再重复同样的筛选逻辑。
