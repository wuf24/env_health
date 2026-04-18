# 2 固定效应模型

这个文件夹是整个课题 **Climate change amplifies the threat of antimicrobial resistance in China** 的核心实证区。  
如果说：

- `1 单因素分析/` 负责做变量筛选、分类出图和“先看关系长什么样”
- `2 固定效应模型/` 负责做面板回归、变量组比较和主结果整理
- `3 单固定效应模型/` 负责把 13 个 AMR 指标拆开，检查异质性

那么本文件夹就是目前最接近“论文主结果”的地方。

## 一句话先讲清楚当前项目在说什么

当前仓库最稳的结论，不是“在所有严格固定效应设定下，气候变化都稳定显著推高 AMR”，而是：

- 在 **Year FE only** 的口径下，极端降雨代理 `R1xday` 和 `抗菌药物使用强度` 往往对综合耐药指标 `AMR_AGG_z` 呈正向关系
- 但一旦转到 **Province FE** 或 **Two-way FE**，这个信号会明显减弱，甚至接近于零
- 所以现阶段的证据更像是在支持“跨省差异 + 年度共同冲击层面，气候与 AMR 风险同向变化”，而不是已经完成了很强的“省内年际因果识别”

这点非常重要，因为它决定了题目里 **amplifies** 这个词目前在代码里是怎样被 operationalize 的。

## 题目与当前代码的关系

论文题目是：

> Climate change amplifies the threat of antimicrobial resistance in China

但就当前代码而言，主模型大多是 **加性固定效应模型**，并没有直接估计：

- `气候 × 抗菌药物使用强度`
- `气候 × 卫生条件`
- `气候 × 污染`

这样的交互项。

因此，当前实证口径更接近下面这个问题：

> 在控制抗菌药物使用、污染、社会经济、供水卫生和畜牧因素之后，气候及极端天气代理变量是否仍与更高的 AMR 水平相关？

如果后续要更严格地支撑 **amplifies** 这层叙事，建议下一步补：

- climate interaction terms
- distributed lag / dynamic panel
- 更明确的机制分层分析

## 当前数据口径

| 项目 | 当前口径 |
| --- | --- |
| AMR 原始数据 | 根目录 `amr_rate.csv` |
| 气候/社会/经济数据 | 根目录 `climate_social_eco.csv` |
| 面板时期 | `2014-2023` |
| 地理单元 | `34` 个省级单元 |
| 合并后主样本 | `307` 个观测 |
| 综合因变量 | `AMR_AGG_z` |
| `AMR_AGG_z` 定义 | 13 个 AMR 指标分别做 z-score 后取行均值 |

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

当前项目中的解释变量大致分成 7 组概念代理：

- 温度代理：`主要城市平均气温`、`省平均气温`、`TA（°C）`
- 降水/湿度/极端降雨代理：`主要城市降水量`、`省平均降水`、`PA（%）`、`R1xday`、`R5xday`
- 空气污染代理：`PM2.5`、`氮氧化物`、`二氧化硫`
- 发展/医疗代理：`GDP`、`可支配收入`、`医疗水平`
- 社会环境代理：`文盲比例`、`建成区绿化覆盖率`、`食品消费量`、`主要城市日照时数`
- 供水/卫生代理：`城市用水普及率`、`生活垃圾无害化处理率`、`人均日生活用水量(升)` 等
- 畜牧代理：`牲畜饲养-猪/羊/大牲畜年底头数`

其中在变量组比较和全空间穷举里，当前被**固定保留**的两个核心变量是：

- `R1xday`
- `抗菌药物使用强度`

## 这个文件夹里到底有几条分析线

当前可以把本文件夹理解成 6 条并行但相关的线：

| 文件 / 脚本 | 作用 | 当前地位 |
| --- | --- | --- |
| `fixed_effects_master_time.ipynb` | 旧主线 FE notebook，只有年份固定效应 | 当前最接近“主结果展示稿” |
| `fixed_effects_master_entity.ipynb` | 省份固定效应版本 | 敏感性分析 |
| `fixed_effects_master_both.ipynb` | 双固定效应版本 | 更严格稳健性分析 |
| `variable_group_schemes.ipynb` | 四套人工变量组并行比较 | 当前最重要的“变量重构”线 |
| `tools/run_variable_space_exhaustive.py` | 科学约束下的全空间穷举 | 当前最重要的“模型发现”线 |
| `revise.ipynb` | 双固定效应 + `log1p(abs())` 诊断稿 | 方法诊断，不建议直接当主结果 |

一个很实用的理解方式是：

- `fixed_effects_master_*` 是“旧主线单一规格”
- `variable_group_schemes.ipynb` 是“人工比较 4 套候选规格”
- `run_variable_space_exhaustive.py` 是“系统搜索更多可行规格”

## 旧主线 FE notebook 目前告诉了我们什么

旧主线 notebook 使用的是一套固定 9 变量规格：

- `省平均气温`
- `省平均降水`
- `R1xday`
- `PM2.5`
- `医疗水平`
- `GDP`
- `城市用水普及率`
- `生活垃圾无害化处理率`
- `抗菌药物使用强度`

对应的三个固定效应版本，当前结果可以概括成下面这张表。

| 模型 | 关键结果 | 当前解读 |
| --- | --- | --- |
| `Year FE only` | `R1xday = 0.1049, p=0.1588`；`抗菌药物使用强度 = 0.1159, p=0.0067`；`GDP = 0.187, p=0.0231`；`R-squared = 0.3841` | AMC 很稳，极端降雨方向为正但未到 0.05 |
| `Province FE only` | `R1xday = -0.0043, p=0.8389`；`抗菌药物使用强度 = -0.0176, p=0.3014` | 一旦只看省内变化，核心信号基本消失 |
| `Two-way FE` | `R1xday = -0.0024, p=0.8986`；`抗菌药物使用强度 = 0.0094, p=0.4591`；`R-squared = 0.0293` | 更严格识别下，核心结果目前不稳 |

旧主线里的 lag-1 检查也有类似结论：

- 在 `Year FE only` 下，`抗菌药物使用强度_L1` 仍显著为正
- `R1xday_L1` 不显著
- 到 `Province FE` 或 `Two-way FE` 后，lag 结果同样不稳

所以如果只看旧主线 notebook，目前最稳的说法应当是：

- `抗菌药物使用强度` 对 `AMR_AGG_z` 的正向关系比较稳定，尤其在 `Year FE only`
- `R1xday` 的正向关系存在，但证据强度弱于 AMC
- 严格 FE 设定下，气候主信号并不强

## 变量组比较线当前的核心发现

`variable_group_schemes.ipynb` 把 4 套人工方案放到统一口径下比较：

- 因变量统一为 `AMR_AGG_z`
- FE 规格统一可切换
- 同时看 `R2`、`R1xday`、`AMC`、VIF 和显著变量

四套人工方案分别是：

| 方案 | 主要定位 | 变量特征 |
| --- | --- | --- |
| `方案A_平衡主线组` | 最接近当前论文直觉的平衡组合 | `省平均气温 + R1xday + PM2.5 + AMC + GDP + 文盲比例 + 用水 + 猪` |
| `方案C_污染替代组` | 用替代污染和发展代理改写主线 | `氮氧化物 + 可支配收入 + 绿化` 替代部分旧变量 |
| `方案D_城市气候组` | 偏城市气候与城市环境视角 | `主要城市平均气温 + PM2.5 + 绿化` |
| `方案F_低VIF主线组` | 更强调低共线性和平衡性 | `TA（°C） + 日照 + 用水 + 猪` |

### 在 4 套人工方案里，当前最重要的结论

`results/variable_group_scheme_summary.csv` 和 `...ranking.csv` 显示：

| 排名 | 模型 | 关键信息 |
| --- | --- | --- |
| 1 | `方案F_低VIF主线组 + Year FE only` | 综合分最高 `0.8157`；`R1xday = 0.1344, p=0.0511`；`AMC = 0.1283, p=0.0034`；`max_vif_z = 1.8204` |
| 2 | `方案D_城市气候组 + Year FE only` | `R1xday = 0.1519, p=0.0632`；`AMC = 0.1197, p=0.0012`；城市温度与绿化也进入显著变量列表 |
| 3 | `方案C_污染替代组 + Year FE only` | `R2` 最高 `0.5320`，但 `R1xday` 不显著；更像高拟合替代规格 |
| 4 | `方案A_平衡主线组 + Year FE only` | `R1xday = 0.1508, p=0.0426`；`AMC = 0.1310, p=0.0034`；四套里最接近“两核心变量同时显著”的主线版本 |

这里最值得记住的不是“谁排第 1”，而是下面这几个结构性事实：

- 4 个 `Year FE only` 模型包揽了人工方案排序前 4 名
- 在这 4 个 `Year FE only` 模型里，`AMC` 全部为正且全部显著
- `R1xday` 在这 4 个模型里全部为正，但只有 `方案A` 达到 `p < 0.05`，`方案D/F` 接近边界
- 一旦改成 `Province FE` 或 `Two-way FE`，`R1xday` 与 `AMC` 的核心信号基本一起衰减

因此，这条线给出的最实用结论是：

- 如果你想保留题目叙事中的“气候 + AMC”双核心，`方案A` 最容易讲故事
- 如果你想优先控制标准化后的共线性并保持较好的综合得分，`方案F` 更适合作为当前主线候选

## 全空间穷举当前说明了什么

`tools/run_variable_space_exhaustive.py` 的规则不是“无脑全排列”，而是带科学约束的系统穷举：

- 固定保留 `R1xday` 与 `抗菌药物使用强度`
- 每个高相关代理家族最多取 1 个变量
- 同时保留人工主线方案
- 变量数限制在 `7-15`

这条线的价值，在于它能回答一个比“哪套人工方案最好”更深的问题：

> 如果不只看我们主观挑出来的 4 套规格，而是在科学约束下系统搜索，什么样的变量组合最容易跑出稳定结果？

当前 `results/exhaustive_model_ranking.csv` 给出的结论非常集中：

- 排名前 `50` 的模型全部来自 `systematic`
- 排名前 `50` 的模型全部是 `Province: No / Year: Yes`

也就是说，系统搜索目前也在重复告诉我们同一件事：

> 当前这批数据里，最“好看”的 AMR 综合模型几乎都依赖 `Year FE only`

前 50 个穷举高分模型里，变量出现频次最高的是：

- `R1xday`：`50/50`
- `抗菌药物使用强度`：`50/50`
- `GDP`：`50/50`
- `氮氧化物`：`32/50`
- `建成区绿化覆盖率`：`32/50`
- `牲畜饲养-猪年底头数`：`28/50`
- `城市用水普及率`：`24/50`
- `主要城市平均气温`：`20/50`
- `省平均气温`：`19/50`
- `PM2.5`：只有 `2/50`

这条结果很有启发性，因为它说明：

- 在系统搜索里，`PM2.5` 并不是高分模型最常见的污染代理
- `氮氧化物`、`绿化`、`用水/垃圾处理`、`GDP` 和 `畜牧` 更频繁地与高分模型同时出现
- 也就是说，当前模型更新方向正在从“单一旧主线变量表”走向“气候 + 发展 + 污染 + 卫生 + 畜牧”的复合代理框架

但需要注意：

- 穷举高分不等于可以直接当论文主结果
- 这条线更适合做“发现候选规格”
- 最终写作时仍要同时审查 `可解释性`、`共线性` 和 `题目叙事一致性`

## 单菌种结果对主结论有什么提醒

虽然单菌种分析在 `../3 单固定效应模型/`，但它对本文件夹的主线判断非常关键。

当前导出的 `outputs_single_species_fe/single_species_FE_long_FIXED.csv` 对 13 个 AMR 指标跑的是**双固定效应**长表。  
从结果看：

- `R1xday` 在 `13/13` 个单菌种模型里都**没有**达到 `p < 0.05`
- `抗菌药物使用强度` 在 `13/13` 个单菌种模型里也**没有**达到 `p < 0.05`
- 显著结果只零散地出现在少数菌种-变量配对上，例如：
  - `CRAB ~ 省平均气温` 为正
  - `CRPA ~ 省平均降水` 为负
  - `3GCRKP ~ PM2.5` 为正
  - `VREFS ~ PM2.5` 为负

这说明两件事：

- 综合指标 `AMR_AGG_z` 的正向信号，未必能在严格的单菌种双 FE 里被普遍复制
- 当前题目更适合写成“综合耐药风险的气候相关性分析”，而不是“所有单一病原体/耐药类型都同样响应气候变化”

## `revise.ipynb` 为什么更像诊断稿

`results/revise_two_way_log_summary.csv` 当前显示：

- `nobs = 310`
- `r2_within = -0.0851`
- `r2_overall = 0.4581`
- `pooled_r2 = 0.9218`
- `max_vif = 5818.49`
- `median_vif = 348.38`

这说明这条 log 口径虽然可以提供方法诊断视角，但它当前的多重共线性非常严重。  
所以更合理的使用方式是：

- 把它当作“我试过这个设定，它说明了哪些方法问题”
- 不要把它直接当成论文主结果规格

## 这份 README 建议怎么用

### 如果你是第一次回到这个项目

推荐顺序：

1. 先看 `fixed_effects_master_time.ipynb`
2. 再看 `variable_group_schemes.ipynb`
3. 然后打开 `results_dashboard.html`
4. 如果要扩展找新模型，再跑 `tools/run_variable_space_exhaustive.py`
5. 如果要做稳健性，再看 `fixed_effects_master_entity.ipynb`、`fixed_effects_master_both.ipynb`
6. 如果要检查菌种异质性，再去 `../3 单固定效应模型/`

### 如果你现在要准备论文主线

当前更适合优先比较的是：

- `旧主线 9 变量 + Year FE`
- `方案A_平衡主线组 + Year FE`
- `方案F_低VIF主线组 + Year FE`

它们分别对应：

- 已有 notebook 叙事
- 最容易讲“R1xday + AMC 双核心”的版本
- 当前综合表现最均衡的版本

## 输出目录说明

### `FE_OUTPUT/`

旧主线固定效应结果的简化表和系数图：

- `AMR_AGG_z_FE_table_time.*`
- `AMR_AGG_z_FE_table_entity.*`
- `AMR_AGG_z_FE_table_both.*`
- `AMR_AGG_z_FE_coefplot_time.png`
- `AMR_AGG_z_FE_coefplot_entity.png`
- `AMR_AGG_z_FE_coefplot_both.png`

### `outputs_lancet_fe/`

旧主线和 lag 版本的 Lancet 风格结果表：

- `lancet_table_AMR_AGG_z_time.*`
- `lancet_table_AMR_AGG_z_entity.*`
- `lancet_table_AMR_AGG_z_both.*`
- `*_lag1.*`
- `lancet_compare_*`

### `results/`

当前最值得反复查看的目录，里面放的是变量组比较、系统穷举和诊断结果：

- `variable_group_scheme_summary.csv/.xlsx`
- `variable_group_scheme_ranking.csv/.xlsx`
- `variable_group_scheme_coefficients.csv/.xlsx`
- `variable_group_scheme_vif.csv/.xlsx`
- `exhaustive_scheme_catalog.csv/.xlsx`
- `exhaustive_model_summary.csv/.xlsx`
- `exhaustive_model_ranking.csv/.xlsx`
- `exhaustive_model_coefficients.csv`
- `exhaustive_model_vif.csv`
- `revise_two_way_log_summary.csv`
- `revise_two_way_log_diagnostic.csv`

### `results_dashboard*.html`

这三份 html 是当前最省时间的浏览入口：

- `results_dashboard.html`：综合排序首页
- `results_dashboard_lancet.html`：格式化结果表页
- `results_dashboard_matrix.html`：横向指标矩阵页

## 数据路径与复现注意事项

这里有一个当前仓库里很容易让人混淆的点：

- 新脚本，例如 `tools/run_variable_space_exhaustive.py`，已经直接读取仓库根目录下的 `amr_rate.csv` 与 `climate_social_eco.csv`
- 部分 notebook 仍保留本机路径：
  - `C:\Users\lunch\Downloads\amr_rate.csv`
  - `C:\Users\lunch\Downloads\climate_social_eco.csv`

所以如果换机器或重跑 notebook，第一件事不是看模型，而是先检查输入路径。

当前至少需要的 Python 依赖包括：

- `linearmodels`
- `pandas`
- `numpy`
- `statsmodels`
- `matplotlib`

如果要继续做“选定组合的贝叶斯辅助分析”，现在请转到新目录：

- [../4 贝叶斯分析/README.md](../4%20贝叶斯分析/README.md)

贝叶斯分析已经从本目录拆出，避免和固定效应主分析混在一起。

需要特别记住的是：

- 现在贝叶斯第一轮已经改成 **model grid**，不再只押一个规格
- 这条网格先镜像 FE 的三种情境：`year_only / province_only / province_year`
- 每种情境再分成 `additive` 和 `amplification` 两版，其中 `amplification` 指显式加入 `R1xday × AMC`
- 只有第一轮把多种口径跑清楚之后，才会把 lag 接到最有信息量的 amplification 版本上

## 已归档文件

以下旧文件已移入根目录 `bakeup/2 固定效应模型/`：

- `amr_lancet_fe_from_raw_csv.ipynb`
- `fixed_effects_model.ipynb`
- `cluster.ipynb`
- `AMR_AGG_z_FE_results.csv`
- `AMR_AGG_z_FE_results.xlsx`
- `AMR_AGG_z_FE_results.tex`
- `CoefficientForest.ipynb`
- `AMR_AGG_z_FE_forest.png`
- `AMR_AGG_z_FE_forest.pdf`

## 当前最值得记住的 5 句话

1. 这个文件夹是整个项目的主实证核心，不只是“跑 FE”的地方。
2. 当前最稳的正向信号来自 `Year FE only`，尤其是 `抗菌药物使用强度`。
3. `R1xday` 经常是正向，但显著性弱于 AMC，且在更严格 FE 下明显衰减。
4. 变量重构和系统穷举都在暗示：高分模型更依赖“复合代理框架”，而不是单一旧主线变量表。
5. 题目里的 **amplifies** 目前还没有被交互项直接识别，后续仍有升级空间。

## 贝叶斯分析去哪里看

贝叶斯辅助分析现已独立到：

- [../4 贝叶斯分析/README.md](../4%20贝叶斯分析/README.md)
- [../4 贝叶斯分析/BAYES_AUXILIARY_ANALYSIS_PLAN.md](../4%20贝叶斯分析/BAYES_AUXILIARY_ANALYSIS_PLAN.md)

当前这条贝叶斯线的核心作用已经不是“做个补充版本”，而是：

- 用 FE 先筛出 `R1xday` 和 `AMC` 更有解释力的组合
- 再用一套镜像 FE 三情境的贝叶斯网格，检查主线在不同控制口径下是否还成立
- 最后再把 lag 接到最值得继续追的 amplification 版本上
- 贝叶斯前处理现在单独记录了逐省按年的 X 补缺规则：`2014 -> 2015`，其他年份优先取前后非缺失值均值，边界年份取最近值

截至当前已经正式跑完的第一轮 3 组 × 6 贝叶斯变体看：

- `year_only` 贝叶斯版本最接近当前 Year FE 主线，`R1xday` 和 `AMC` 都稳定为正
- `province_only` 与 `province_year` 会明显削弱 `R1xday` 主效应，这点和 FE 结果一致
- 第一轮最强的 amplification 信号出现在 `province_only_amplification`
- 但只要加上年份控制，交互项就还不够稳

这进一步说明：当前题目叙事里最接近 **amplifies** 的证据，是“只控制省份”的交互项结果；但如果正文要坚持更强表述，还需要看第二轮 lag 能不能把这条线补强。

旧的 `Bayes_ana.ipynb` 已归档到：

- [../bakeup/4 贝叶斯分析/Bayes_ana_legacy_from_2固定效应模型_20260418.ipynb](../bakeup/4%20贝叶斯分析/Bayes_ana_legacy_from_2固定效应模型_20260418.ipynb)

这样本目录继续专注于：

- FE 主结果
- 变量组比较
- 全空间穷举
