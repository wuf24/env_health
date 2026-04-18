# 4 贝叶斯分析

这个目录现在的主任务不是“只做一个贝叶斯版本”，而是先把贝叶斯分析做成一套 **与固定效应三种情境相对应的模型网格**，然后再决定哪一条线值得进入 lag。

一句话说，就是：

> 先镜像 FE 的三种情境做多种贝叶斯尝试，再根据第一轮结果选择 lag 方向，而不是一开始就押宝某一个规格。

## 为什么不再只做 within / between

之前把贝叶斯主线直接做成 `within-between / Mundlak`，是因为那样最接近严格 FE 识别逻辑。  
但这并不应该成为唯一主线，原因很简单：

- 你的固定效应分析本来就是三种情境并行比较：
  - 只固定年份
  - 只固定省份
  - 省份和年份都控制
- 当前项目真正想回答的，也不是单一“纯省内变化”问题
- 所以贝叶斯第一轮更合理的做法，是先把这三种情境都镜像出来

因此现在的结构是：

1. `year_only_*`
2. `province_only_*`
3. `province_year_*`

`Mundlak / within-between` 还保留，但不再是默认主规格，而是第二轮诊断工具。

## amplification 是什么意思

这里的 `amplification` 不是一个抽象口号，而是一个很具体的模型项：

```text
R1xday × 抗菌药物使用强度
```

含义是：

- 当 `R1xday` 更高时，`抗菌药物使用强度` 与 `AMR` 的关联是否更强
- 或者反过来，当 `抗菌药物使用强度` 更高时，`R1xday` 对 `AMR` 的影响是否更强

也就是说，它是在直接检验题目里的：

> Climate change amplifies the threat of antimicrobial resistance

如果交互项稳定为正，才更接近“放大效应”这层叙事。  
如果只有主效应为正，而交互项不稳，那更接近“共同相关”而不是“放大”。

## 当前第一轮贝叶斯网格

当前默认跑的 6 个变体都在 [model_selection.toml](</e:/MALA/Code_health/4 贝叶斯分析/model_selection.toml:1>) 里：

1. `year_only_additive`
2. `year_only_amplification`
3. `province_only_additive`
4. `province_only_amplification`
5. `province_year_additive`
6. `province_year_amplification`

它们对应 FE 的三种情境：

- `year_only_*` 对应 “只固定年份”
- `province_only_*` 对应 “只固定省份”
- `province_year_*` 对应 “两者都控制”

其中：

- `additive` 只看主效应
- `amplification` 额外加入 `R1xday × 抗菌药物使用强度`

## 缺失值处理

贝叶斯分析现在对 **X 变量** 使用逐省按年份的补缺规则，而不是简单 `dropna()`，也不是统一用中位数填补。

具体步骤是：

1. 先把当前组合中的自变量转成数值
2. 如果 `2014` 缺失，优先用 `2015` 填
3. 如果 `2015` 也缺，就用该省 `2014` 之后第一个非缺失年份的值
4. 其他年份如果缺失：
   - 两侧都有值：用前后两个非缺失年份的均值
   - 只有一侧有值：用最近一侧的值

`AMR_AGG_z` 不做插补，只在 X 补完后再剔除缺失结果变量。
如果某个省在整个观察期内某个 X 都完全缺失，这套规则也不会凭空造值；这类行会在最终建模前随 `dropna` 一起剔除。

每个模型输出的 `*_metadata.json` 里会记录：

- 本次采用的 `missing_value_strategy`
- 每一列补缺前后的缺失数 `column_report`
- 每条补缺使用了哪条规则的 `imputation_log`
- `AMR_AGG_z` 是怎样处理的 `outcome_handling`

## 当前默认组合

第一轮默认跑的是这三组：

- `方案A_平衡主线组`
- `SYS_09556`
- `SYS_09557`

选择逻辑是：

- `方案A`：人工主线，最适合承接论文叙事
- `SYS_09556 / SYS_09557`：系统穷举里 `R1xday` 和 `AMC` 都显著，适合优先检验 amplification

候选清单见：

- [bayes_candidate_models.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/bayes_candidate_models.csv:1>)

## 第一轮结果怎么读

最值得直接看的汇总表是：

- [focus_variant_bridge_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_variant_bridge_summary.csv>)
- [focus_primary_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_primary_summary.csv>)

### 1. `year_only_*` 最接近当前 Year FE 主线

三组里都比较一致：

- `R1xday` 主效应稳定为正
- `AMC` 主效应稳定为正

例如：

- `方案A / year_only_additive`
  - `R1xday = 0.1226`, `95% CrI [0.0402, 0.2047]`
  - `AMC = 0.1050`, `95% CrI [0.0403, 0.1702]`
- `SYS_09556 / year_only_additive`
  - `R1xday = 0.1883`, `95% CrI [0.1105, 0.2653]`
  - `AMC = 0.1095`, `95% CrI [0.0460, 0.1729]`

这说明贝叶斯 `year_only` 版本基本复现了你当前 Year FE 的主线。

### 1.1 `方案A / year_only_amplification` 目前怎么读

这个变体最接近下面这个问题：

> 在只控制年份共同冲击的前提下，`R1xday` 和 `AMC` 本身是否仍为正，而且 `R1xday × AMC` 是否也支持“放大效应”？

`方案A / year_only_amplification` 当前结果是：

- `R1xday = 0.1062`, `95% CrI [0.0288, 0.1840]`, `P(beta > 0) = 0.996`
- `AMC = 0.1117`, `95% CrI [0.0551, 0.1682]`, `P(beta > 0) = 1.000`
- `R1xday × AMC = 0.0304`, `95% CrI [-0.0254, 0.0866]`, `P(beta > 0) = 0.848`

因此它的结论不是“放大效应已经被稳健证明”，而是：

- 主效应这条线是好的，`R1xday` 和 `AMC` 都稳定为正
- 交互项方向也偏正，说明这条线值得继续追
- 但交互项的区间仍然跨 0，所以现在更适合表述成“对 amplification 有方向性支持，但证据还不够强”

如果只问这个变体“效果怎么样”，最准确的回答是：

- 对主线叙事来说，**不错**
- 对题目里最严格的 `amplifies` 交互叙事来说，**还不够稳**

### 2. `province_only_*` 与 `province_year_*` 会明显削弱 `R1xday` 主效应

这也和 FE 主线一致：

- `province_only_additive` 下，三组 `R1xday` 都接近 0 或略负
- `province_year_additive` 下，三组 `R1xday` 也都接近 0

也就是说，一旦把省份差异控制进去，气候主效应会明显减弱。

### 3. amplification 交互项目前最有意思的地方在 `province_only_amplification`

这里出现了第一轮最强的正向交互信号：

- `方案A`
  - `interaction = 0.0383`, `95% CrI [0.0004, 0.0775]`
- `SYS_09556`
  - `interaction = 0.0413`, `95% CrI [0.0001, 0.0817]`
- `SYS_09557`
  - `interaction = 0.0408`, `95% CrI [0.0006, 0.0795]`

这意味着：

- 在“只控制省份差异”的贝叶斯口径下，`R1xday × AMC` 的交互项是三组都偏正，且下界刚好越过 0

这是当前最接近“amplifies”题目叙事的一条线。

### 4. 但 amplification 一旦加上年份控制，就还不够稳

- `year_only_amplification`
  - `方案A` 的交互项偏正，但区间跨 0
  - `SYS_09556 / SYS_09557` 也都偏正，但区间跨 0
- `province_year_amplification`
  - 三组交互项都偏正
  - 但 `95% CrI` 仍然都跨 0

这说明：

- 当前“放大效应”信号最明显的口径是 `province_only_amplification`
- 但一旦加上年份共同冲击控制，这个交互还没有稳到可以直接下强结论

## 当前最合理的方法判断

现在最有逻辑的读法是：

1. `year_only` 负责复现你当前最强的主线信号
2. `province_only` 负责检验交互项有没有省份层级上的放大迹象
3. `province_year` 负责做最关键的严谨检验
4. `Mundlak` 暂时退到第二轮，作为更严格的分解诊断

换句话说，当前贝叶斯第一轮不是在说：

> 已经稳稳证明了 climate change amplifies AMR in China

而是在说：

> “放大效应”在不同控制口径下表现不一样，当前最有力的正向交互出现在 province-only 版本，但在 year-only 和 province+year 下还不够稳。

## 所以下一步为什么应该先做 lag

第一轮多尝试已经完成了，现在最自然的第二轮不是再无穷加新规格，而是把 lag 放到 **最有信息量的几条线** 上：

1. `year_only_amplification`
   原因：最接近你当前 FE 主线
2. `province_only_amplification`
   原因：目前交互项最强
3. `province_year_amplification`
   原因：最严谨、最关键

这样第二轮 lag 才是有逻辑地推进，而不是盲目扩模型。

## 运行方式

先检查网格：

```bash
conda activate code_health_bayes
python -X utf8 "4 贝叶斯分析\run_bayes_selected_models.py" --dry-run
```

第一轮网格筛选：

```bash
conda activate code_health_bayes
python -X utf8 "4 贝叶斯分析\run_bayes_selected_models.py" --draws 800 --tune 800 --chains 4
```

如果想只跑某几个变体：

```bash
conda activate code_health_bayes
python -X utf8 "4 贝叶斯分析\run_bayes_selected_models.py" --variant-ids year_only_amplification province_only_amplification province_year_amplification
```

## 当前输出

当前主要看：

- [combined_posterior_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/combined_posterior_summary.csv>)
- [focus_posterior_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_posterior_summary.csv>)
- [focus_primary_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_primary_summary.csv>)
- [focus_variant_bridge_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_variant_bridge_summary.csv>)
- [combined_diagnostics.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/combined_diagnostics.csv>)

单个模型文件现在都带 `variant_id`，避免把不同口径混在一起。

### 单个结果文件分别是什么意思

对某一个模型变体，你通常会看到 3 个配套文件：

1. `*_posterior_summary.csv`
   这是最核心的结果表，按参数逐行给出：
   - `posterior_mean`：后验均值，先看方向和大致大小
   - `crI_2_5 / crI_97_5`：95% credible interval，先看是否跨 0
   - `prob_gt_0`：系数大于 0 的后验概率，越接近 1 越支持“正向”

2. `*_diagnostics.csv`
   这是采样诊断表，主要看：
   - `r_hat`：越接近 1 越好，通常 `<= 1.01` 算比较干净
   - `ess_bulk / ess_tail`：有效样本量，越大越稳定
   - 这张表不回答“结果方向”，它回答“这次采样靠不靠谱”

3. `*_metadata.json`
   这是这次模型的说明书，记录：
   - 这次跑的是哪个 `scheme_id`、哪个 `variant_id`
   - 采样设置 `draws / tune / chains`
   - 实际进入模型的 `n_obs / n_provinces / n_years`
   - 用了哪些变量、这些变量的 z-score 标准化均值和标准差
   - 缺失值如何按年份补、补了多少、哪些点最终因为无法补而被删掉
   - 以及这个组合在前面的 FE 筛选阶段表现如何

### 汇总结果文件分别是什么意思

- [combined_posterior_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/combined_posterior_summary.csv>)
  把所有模型、所有变体、所有参数的 posterior summary 拼在一起。适合全局搜索和做二次筛选。

- [focus_posterior_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_posterior_summary.csv>)
  从 `combined_posterior_summary` 里抽出核心变量和交互项，便于只盯 `R1xday / AMC / R1xday × AMC`。

- [focus_primary_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_primary_summary.csv>)
  进一步保留最关键的主效应和交互项，是做论文主文图表时最方便的一张短表。

- [focus_variant_bridge_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_variant_bridge_summary.csv>)
  这是“桥接表”。它把同一个模型在 6 个变体里的核心结果摆在一起，最适合横向看：
  - `year_only`
  - `province_only`
  - `province_year`
  之间到底怎么变

- [combined_diagnostics.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/combined_diagnostics.csv>)
  把所有变体的采样诊断合并到一起，适合批量检查 `r_hat`、`ESS` 是否异常。

### 看结果时最该盯哪些指标

建议固定按这 4 步读：

1. 先看 `posterior_mean`
   方向对不对，大小大概多大。
2. 再看 `95% CrI`
   有没有完全落在 0 的同一侧。
3. 再看 `prob_gt_0`
   - 接近 `1.0`：正向支持很强
   - `0.8-0.95`：有方向性支持，但不算特别硬
   - `0.5` 左右：基本没什么方向信息
4. 最后看 `diagnostics`
   `r_hat`、`ESS` 是否正常，避免把不稳定采样误当成结论

如果你当前最关心题目主线，可以优先只看：

- `R1xday`
- `抗菌药物使用强度`
- `R1xday × 抗菌药物使用强度`

其中：

- 主效应是否为正，决定“这组变量是否仍支持主线”
- 交互项是否为正且区间不过 0，才更接近“amplifies”这层叙事

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

## 一句话记住现在的逻辑

不是“先决定贝叶斯要证明什么”，而是：

> 先用贝叶斯把 FE 的三种情境都镜像出来，看哪一类口径最支持主线，再把 lag 接到最有信息量的 amplification 版本上。 
