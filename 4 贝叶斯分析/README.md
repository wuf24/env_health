# 4 贝叶斯分析

这个目录当前的任务，不是“只做一个贝叶斯版本”，而是把贝叶斯分析做成一套 **镜像固定效应三种控制口径的模型网格**，再据此判断：

- 主线信号在不同口径下是否还能保留；
- `R1xday × 抗菌药物使用强度` 的交互项是否有足够证据支持 `amplifies`；
- 哪些变体值得继续进入 lag 或更严格诊断。

## 当前方法定位

一句话说：

> 先镜像 FE 的三种情境做多种贝叶斯尝试，再根据结果挑值得继续追的线，而不是一开始就押宝某一个规格。

这也是为什么现在默认逻辑不再只围绕 `within-between / Mundlak`。

## 为什么不再只做 within / between

此前把贝叶斯主线做成 `within-between / Mundlak`，是因为那样最接近严格 FE 识别逻辑。  
但当前项目真正需要回答的，不只是“纯省内变化”这一种问题。

固定效应主分析本身就是三种口径并行比较：

- 只固定年份
- 只固定省份
- 同时控制省份和年份

因此当前贝叶斯第一轮更合理的做法，是先把这三种 FE 情境全部镜像出来：

1. `year_only_*`
2. `province_only_*`
3. `province_year_*`

`Mundlak / within-between` 仍可作为第二轮诊断工具，但不再是默认第一入口。

## amplification 到底是什么意思

这里的 `amplification` 不是抽象口号，而是一个具体模型项：

```text
R1xday × 抗菌药物使用强度
```

它在检验的是：

- 当 `R1xday` 更高时，`AMC` 与 `AMR` 的关联是否更强；
- 或者当 `AMC` 更高时，`R1xday` 对 `AMR` 的影响是否更强。

也就是说，它是当前代码里最直接对接题目

> Climate change amplifies the threat of antimicrobial resistance

这层叙事的模型化实现。

## 当前配置文件怎么控制默认运行

核心配置文件是：

- `model_selection.toml`

其中当前默认设置有两个要点：

### 1. 变体网格固定为 6 个

- `year_only_additive`
- `year_only_amplification`
- `province_only_additive`
- `province_only_amplification`
- `province_year_additive`
- `province_year_amplification`

### 2. 候选模型默认读取当前候选清单全部行

当前 `model_selection.toml` 中：

- `selected_model_ids = []`
- `selected_scheme_ids = []`

这意味着如果你不手动指定，脚本会直接使用：

- `results/bayes_candidate_models.csv`

里的当前候选清单。

截至当前仓库版本，这份候选清单至少包括：

- 人工主线：`方案A_平衡主线组`
- 低 VIF 参考：`方案F_低VIF主线组`
- 系统穷举桥接候选：`SYS_09556`、`SYS_09557`
- 其他高分 systematic 候选：例如 `SYS_01678`、`SYS_00553`

## 当前输出结构

### 核心目录

- `results/model_summaries/`
  - 当前正式使用的 posterior summary、diagnostics 与 metadata。
- `results/backups/model_summaries_pre_strict_top8_20260423-010048/`
  - strict top-8 扩展前的一份阶段性备份。

这说明当前结果目录并不是单一阶段的“只读快照”，而是已经经历过一轮从早期 curated/systematic 候选到更严格模型扩展的演进。

## 当前最值得直接看的文件

### 汇总短表

- `results/model_summaries/focus_primary_summary.csv`
- `results/model_summaries/focus_variant_bridge_summary.csv`
- `results/model_summaries/focus_posterior_summary.csv`
- `results/model_summaries/combined_posterior_summary.csv`
- `results/model_summaries/combined_diagnostics.csv`

### 候选与配置

- `results/bayes_candidate_models.csv`
- `model_selection.toml`
- `run_bayes_selected_models.py`

### 页面入口

- `index.html`
  - 本地人读入口
- `public_dashboards/bayes-analysis/`
  - public 发布副本

## 当前结果应该怎么读

### 1. `year_only_*` 负责镜像当前 Year FE 主线

这一组通常最接近当前固定效应主线，会回答：

- `R1xday` 主效应是否仍为正；
- `AMC` 主效应是否仍为正；
- Year FE 主线在贝叶斯口径下是否还能被复现。

如果 `year_only_additive` 都不能复现主线，那就说明当前 FE 主线本身并不稳。

### 2. `province_only_*` 更容易观察交互项有没有“省份层级上的放大迹象”

当前仓库已有结果里，最值得注意的正向交互通常出现在：

- `province_only_amplification`

这条线的含义是：

- 先吸收省际长期差异；
- 再看 `R1xday × AMC` 是否还会稳定偏正。

这也是目前最接近题目里 “amplifies” 叙事的一条线。

### 3. `province_year_*` 是最严谨的检验

如果交互项在这里仍然稳定，那解释力最强；  
如果在这里被压缩到接近零，也最容易解释为：

- 放大效应目前证据还不够硬；
- 可能更多是弱方向性支持，而非强结论。

## 当前最合理的方法判断

现在更有逻辑的读法是：

1. `year_only` 用来复现 FE 主线；
2. `province_only` 用来观察交互项有没有放大迹象；
3. `province_year` 用来做最关键的严谨检验；
4. 第二轮再决定是否把 lag 接到最有信息量的 amplification 版本。

所以当前贝叶斯第一轮不是在说：

> 已经稳稳证明了 climate change amplifies AMR in China

而更接近在说：

> 放大效应在不同控制口径下表现不一样，当前最有力的正向交互往往出现在 `province_only_amplification`，但更严格口径下仍需谨慎表述。

## 缺失值处理

贝叶斯分析当前对 **X 变量** 使用逐省按年份的补缺规则，而不是简单 `dropna()` 或统一中位数填补。

基本逻辑是：

1. 先把当前模型组合中的自变量转成数值；
2. 如果 `2014` 缺失，优先用 `2015`；
3. 若邻近年份也缺，再向最近非缺失值回填；
4. 中间年份优先用前后非缺失值均值，边界年份取最近值。

`AMR_AGG_z` 不做插补，只在 X 补完后再剔除缺失结果变量。

每个 `*_metadata.json` 里都会记录：

- `missing_value_strategy`
- `column_report`
- `imputation_log`
- `outcome_handling`

## 单个文件分别是什么意思

对于任一模型变体，通常会得到三类配套文件：

### `*_posterior_summary.csv`

最核心的结果表，主要看：

- `posterior_mean`
- `crI_2_5 / crI_97_5`
- `prob_gt_0`

### `*_diagnostics.csv`

主要看采样质量：

- `r_hat`
- `ess_bulk`
- `ess_tail`

### `*_metadata.json`

相当于该模型的说明书，记录：

- `scheme_id`
- `variant_id`
- `draws / tune / chains`
- `n_obs / n_provinces / n_years`
- 标准化信息
- 缺失值补缺信息
- 该组合在 FE 筛选阶段的表现

## 汇总表分别适合做什么

### `combined_posterior_summary.csv`

适合：

- 全局检索；
- 做二次筛选；
- 搜索哪些组合/变体里核心参数最稳定。

### `focus_posterior_summary.csv`

适合：

- 只盯核心参数；
- 聚焦 `R1xday / AMC / R1xday × AMC`。

### `focus_primary_summary.csv`

适合：

- 论文主文短表；
- 快速写作引用；
- 与固定效应和反事实模块做桥接。

### `focus_variant_bridge_summary.csv`

适合：

- 横向比较同一模型在 `year_only / province_only / province_year` 下怎么变化；
- 看“同一组变量换控制口径后还剩多少信号”。

### `combined_diagnostics.csv`

适合：

- 批量检查 `r_hat`、`ESS`；
- 找出需要重跑或重点复核的变体。

## 推荐运行方式

### 先检查默认网格

```bash
conda activate code_health_bayes
python -X utf8 "4 贝叶斯分析\run_bayes_selected_models.py" --dry-run
```

### 跑完整默认网格

```bash
conda activate code_health_bayes
python -X utf8 "4 贝叶斯分析\run_bayes_selected_models.py" --draws 800 --tune 800 --chains 4
```

### 只跑重点 amplification 变体

```bash
conda activate code_health_bayes
python -X utf8 "4 贝叶斯分析\run_bayes_selected_models.py" --variant-ids year_only_amplification province_only_amplification province_year_amplification
```

### 如果想手动限制候选模型

优先编辑：

- `model_selection.toml`

只填：

- `selected_model_ids`
  或
- `selected_scheme_ids`

不要直接改动结果目录里的历史输出文件名。

## 环境

当前正式环境是：

- `code_health_bayes`

建议创建方式：

```bash
conda --no-plugins create --solver=classic -y -n code_health_bayes python=3.12 pip numpy pandas scipy matplotlib ipykernel openpyxl
conda --no-plugins install --solver=classic -y -n code_health_bayes m2w64-toolchain
conda activate code_health_bayes
python -m pip install -r "4 贝叶斯分析\requirements-bayes.txt"
```

## 参考文献

- [Nature Medicine 文章](https://www.nature.com/articles/s41591-025-03629-3)
- [原文 INLA 脚本](https://raw.githubusercontent.com/Code-Storehouse/AMR-in-climate-change/main/3%20INLA%20model/INLA%20model.R)
- [Mundlak (1978)](https://people.stern.nyu.edu/wgreene/Econometrics/Mundlak-1978.pdf)
- [Bell, Fairbrother, Jones (2019)](https://research-information.bris.ac.uk/ws/portalfiles/portal/196855552/Bell2019_Article_FixedAndRandomEffectsModelsMak.pdf)

## 一句话记住这个目录

这里负责把固定效应主线拆成多种贝叶斯口径来复核，并判断“主线是否成立”和“放大效应有多强”到底是两回事还是一回事。
