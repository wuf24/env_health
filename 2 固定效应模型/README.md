# 2 固定效应模型

这个目录是整个项目当前最接近“论文主结果”和“模型筛选中心”的地方。  
它不仅负责跑固定效应回归，还承担了三类更关键的工作：

1. 统一比较 Year FE / Province FE / Two-way FE 三种口径。
2. 从人工方案和系统穷举中筛出当前最值得继续推进的模型。
3. 为贝叶斯、反事实推演、未来情景分析提供统一的模型归档。

## 当前主线结论怎么理解

截至当前仓库版本，这里的主线不是：

> 在所有严格固定效应设定下，气候变化都稳定显著推高 AMR。

而更接近：

- 在 **Year FE only** 口径下，`R1xday` 与 `抗菌药物使用强度` 往往对综合指标 `AMR_AGG_z` 呈正向关系；
- 一旦进入 **Province FE** 或 **Two-way FE**，这些信号会明显减弱；
- 因此目前最稳的证据更像“跨省差异 + 年度共同冲击层面，气候与 AMR 风险同向变化”，而不是已经完成强形式的省内年际因果识别。

这也是为什么题目里的 **amplifies** 目前主要还需要借助 `4 贝叶斯分析/` 的交互项检验来补强。

## 这个目录在整条分析链里的角色

- 上游：承接 `1 单因素分析/` 的变量展示与候选池。
- 本层：完成 FE 对比、变量重构、系统穷举和模型归档。
- 下游：
  - `4 贝叶斯分析/` 读取这里筛出的候选模型；
  - `5 反事实推演/` 读取这里统一整理的 `12` 模型归档；
  - `6 未来情景分析/` 也读取同一套 `12` 模型归档。

换句话说，后面三个模块现在共享的模型来源，都是从这里出来的。

## 当前数据口径

| 项目 | 当前口径 |
| --- | --- |
| AMR 原始数据 | 根目录 `amr_rate.csv` |
| 协变量主表 | 根目录 `climate_social_eco.csv` |
| 面板时期 | `2014-2023` |
| 地理单元 | `34` 个省级单元 |
| 合并后主样本 | `307` 个观测 |
| 综合因变量 | `AMR_AGG_z` |
| 指标定义 | 13 个 AMR 指标分别做 z-score 后取行均值 |

当前纳入 `AMR_AGG_z` 的 13 个耐药指标为：

- `MRCNS`
- `VREFS`
- `VREFM`
- `PRSP`
- `ERSP`
- `3GCRKP`
- `MRSA`
- `3GCREC`
- `CREC`
- `QREC`
- `CRPA`
- `CRKP`
- `CRAB`

在变量组比较和系统穷举中，当前被**固定保留**的两个核心变量是：

- `R1xday`
- `抗菌药物使用强度`

## 当前目录结构

### notebook 主线

- `fixed_effects_master_time.ipynb`
  - 旧主线 Year FE notebook。
- `fixed_effects_master_entity.ipynb`
  - Province FE 版本。
- `fixed_effects_master_both.ipynb`
  - Two-way FE 版本。
- `variable_group_schemes.ipynb`
  - 四套人工变量组比较线。
- `revise.ipynb`
  - `log1p(abs())` 诊断稿，不建议直接当主结果。

### 输出目录

- `FE_OUTPUT/`
  - 旧主线 FE 简表和系数图。
- `outputs_lancet_fe/`
  - 旧主线及 lag 版本的 Lancet 风格结果表。
- `results/`
  - 当前真正需要优先看的结果目录。

### 页面入口

- `results_dashboard.html`
  - 当前 exhaustive 版综合排序首页。
- `results_dashboard_lancet.html`
  - 格式化结果表页。
- `results_dashboard_matrix.html`
  - 横向比较矩阵页。

## 这个目录里有哪几条分析线

可以把本目录理解成 5 条主线：

### 1. 旧主线 notebook

- 用于保留最早的 FE 叙事和结果展示逻辑。
- 适合作为“最初论文主线是怎么搭起来的”回溯入口。

### 2. 人工变量组比较

- 由 `variable_group_schemes.ipynb` 负责。
- 核心价值是回答：人工设计的候选变量组里，哪套最适合主叙事、哪套更低共线性、哪套拟合更强。

当前最常被引用的四套人工方案是：

- `方案A_平衡主线组`
- `方案C_污染替代组`
- `方案D_城市气候组`
- `方案F_低VIF主线组`

### 3. 系统穷举

- 由 `tools/run_variable_space_exhaustive.py` 负责。
- 不是无约束全排列，而是在科学约束下搜索更优的 Year FE 组合。

约束包括：

- 固定保留 `R1xday` 与 `抗菌药物使用强度`
- 每个高相关代理家族最多取 `1` 个变量
- 同时保留人工方案
- 变量数限制在 `7-15`

### 4. 严筛 top-8 归档

- 产物位于 `results/strict_top8_archive/strict_top8_models.csv`
- 由 `tools/build_strict_top8_archive.py` 生成

这条线从 exhaustive 结果里进一步提炼：

- `R1xday / AMC / TA` 显著
- 污染代理固定为 `PM2.5`
- 其他系数不为负

它的作用是形成一组强约束的“严筛模型池”，供后续稳健性比较。

### 5. 统一 12 模型归档

- 产物位于 `results/model_archive_12/selected_models.csv`
- 由 `tools/build_model_archive_12.py` 生成

这是目前最关键的一层，因为后面的贝叶斯、反事实和未来情景都在用它。

这 `12` 个模型由两部分组成：

- `4` 个手选 Year FE 模型：
  - `main_model`
  - `robust_low_vif`
  - `robust_systematic`
  - `robust_systematic_2`
- `8` 个严筛模型：
  - `strict_main_model`
  - `strict_top_02` 到 `strict_top_08`

## 旧主线 notebook 当前告诉了我们什么

旧主线使用的是一套固定 `9` 变量规格：

- `省平均气温`
- `省平均降水`
- `R1xday`
- `PM2.5`
- `医疗水平`
- `GDP`
- `城市用水普及率`
- `生活垃圾无害化处理率`
- `抗菌药物使用强度`

其结论可以简化为：

| 模型 | 关键结果 | 当前解读 |
| --- | --- | --- |
| `Year FE only` | `R1xday` 为正但边界；`AMC` 稳定显著为正 | 当前主线最容易讲通的版本 |
| `Province FE only` | `R1xday` 与 `AMC` 均明显衰减 | 省内变化口径下主信号不稳 |
| `Two-way FE` | 核心气候信号进一步减弱 | 严格识别下仍缺强证据 |

所以如果只看旧主线，当前最稳的说法是：

- `AMC` 的正向关系比 `R1xday` 更稳；
- `R1xday` 常常为正，但证据强度弱于 `AMC`；
- 更严格的 FE 控制会压缩核心信号。

## 人工变量组比较当前怎么读

`results/variable_group_scheme_summary.csv`、`...ranking.csv` 和 `...coefficients.csv` 是这一条线的核心文件。

当前最值得记住的结构性结论是：

- 排序最靠前的人工方案都集中在 `Year FE only`；
- 在这些 Year FE 人工方案里，`AMC` 往往稳定显著为正；
- `R1xday` 多数也是正向，但显著性弱一些；
- `方案A` 更适合承接论文叙事；
- `方案F` 更强调较低 VIF 和整体平衡。

如果你是为了写作选择“更好讲的主模型”，优先看 `方案A`；  
如果你是为了方法上追求更低共线性，优先看 `方案F`。

## exhaustive 搜索当前怎么读

当前 `results/exhaustive_model_ranking.csv` 和 `results/exhaustive_model_summary.csv` 呈现的信号非常集中：

- 高分模型大多来自 `systematic`
- 高分模型几乎都依赖 `Province: No / Year: Yes`

也就是说，系统搜索本身也在强化同一个事实：

> 当前这批数据里，最“好看”的综合 AMR 模型仍主要来自 Year FE only。

同时，穷举结果也提示模型更新方向正在从“单一旧主线变量表”走向更复合的代理框架，例如：

- 气候
- 发展
- 污染
- 卫生
- 畜牧

这为 strict top-8 和统一 12 模型归档提供了模型发现基础。

## 当前最值得直接看的结果文件

### 人工方案

- `results/variable_group_scheme_summary.csv`
- `results/variable_group_scheme_ranking.csv`
- `results/variable_group_scheme_coefficients.csv`
- `results/variable_group_scheme_vif.csv`

### exhaustive

- `results/exhaustive_scheme_catalog.csv`
- `results/exhaustive_model_summary.csv`
- `results/exhaustive_model_ranking.csv`
- `results/exhaustive_model_coefficients.csv`
- `results/exhaustive_model_vif.csv`

### 归档

- `results/strict_top8_archive/strict_top8_models.csv`
- `results/model_archive_12/selected_models.csv`

### 页面

- `results_dashboard.html`
- `results_dashboard_lancet.html`
- `results_dashboard_matrix.html`

## 当前推荐工作顺序

### 如果你是第一次回来接这个模块

1. 先看 `results/model_archive_12/selected_models.csv`
2. 再看 `results/exhaustive_model_summary.csv`
3. 然后打开 `results_dashboard.html`
4. 如需理解人工方案，再看 `variable_group_schemes.ipynb`
5. 如需理解旧主线叙事，再看 `fixed_effects_master_time.ipynb`

### 如果你要更新主筛选结果

1. 运行 `tools/run_variable_space_exhaustive.py`
2. 运行 `tools/build_strict_top8_archive.py`
3. 运行 `tools/build_model_archive_12.py`
4. 运行 `tools/build_results_dashboard.py`
5. 如需推进贝叶斯，再运行 `tools/build_bayes_candidate_models.py`

## 与其他模块的连接关系

### 贝叶斯

`4 贝叶斯分析/` 现在不再只押单一模型，而是从这里读取候选清单并镜像三类 FE 情境：

- `year_only`
- `province_only`
- `province_year`

再分别比较 `additive` 和 `amplification` 版本。

### 反事实

`5 反事实推演/` 当前直接读取：

- `results/model_archive_12/selected_models.csv`

因此反事实不再只围绕单个主模型，而是围绕统一 `12` 模型归档。

### 未来情景

`6 未来情景分析/` 也使用同一套 `12` 模型归档，当前运行元数据里保留的角色包括：

- `strict_main_model`
- `strict_top_02` 到 `strict_top_08`
- `robust_systematic`
- `robust_systematic_2`
- `robust_low_vif`
- `main_model`

## 数据路径与复现注意事项

- 新脚本已经直接读取仓库根目录下的 `amr_rate.csv` 与 `climate_social_eco.csv`
- 部分 notebook 仍保留本机路径：
  - `C:\Users\lunch\Downloads\amr_rate.csv`
  - `C:\Users\lunch\Downloads\climate_social_eco.csv`

所以如果换机器或重跑 notebook，第一件事不是看模型，而是先检查输入路径。

当前常见依赖包括：

- `linearmodels`
- `pandas`
- `numpy`
- `statsmodels`
- `matplotlib`

## 已归档内容

以下旧文件已移入 `../bakeup/2 固定效应模型/`：

- `amr_lancet_fe_from_raw_csv.ipynb`
- `fixed_effects_model.ipynb`
- `cluster.ipynb`
- `AMR_AGG_z_FE_results.csv`
- `AMR_AGG_z_FE_results.xlsx`
- `AMR_AGG_z_FE_results.tex`
- `CoefficientForest.ipynb`
- `AMR_AGG_z_FE_forest.png`
- `AMR_AGG_z_FE_forest.pdf`

## 一句话记住这个目录

这里不只是“跑 FE”的地方，而是整个项目把候选变量、主叙事模型、严筛模型和统一 `12` 模型归档串起来的中心枢纽。
