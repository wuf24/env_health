# 贝叶斯辅助分析方案

## 当前总策略

贝叶斯分析现在分两步走：

1. **第一轮多尝试**
   先镜像固定效应的三种情境，比较哪一类贝叶斯口径最支持主线
2. **第二轮 lag**
   再把 lag 接到第一轮最有信息量的 amplification 版本上

这比“直接选一个贝叶斯模型一路跑到底”更符合当前项目结构。

## 第一步为什么要做 model grid

当前 FE 主线已经说明了一个事实：

- `Year FE only` 最容易出现正向结果
- `Province FE only` 和 `Two-way FE` 更保守

所以贝叶斯第一轮最合理的任务，不是立刻深究某个单一 strict-within 规格，而是先把下面三种情境都镜像出来：

1. `year_only`
2. `province_only`
3. `province_year`

每一种再分成：

- `additive`
- `amplification`

于是当前第一轮网格是 6 个模型变体。

## 缺失值补全口径

贝叶斯分析现在不再单纯用 `dropna()` 缩样本，而是对选定 X 做逐省按年的时间补缺。

统一规则是：

1. 先把当前组合中的自变量转成数值
2. `2014` 缺失时优先用 `2015`
3. 如果 `2015` 也缺，就用该省 `2014` 之后第一个非缺失年份
4. 其他年份缺失时：
   - 两侧都有值：用前后最近非缺失年份均值
   - 只有一侧有值：用最近一侧的值
5. `AMR_AGG_z` 不做插补，只在 X 补完后再丢掉缺失结果值

如果某个省某个变量在整个观察期都没有值，这套时间补缺本身也无法生成信息；这种情况保留为缺失，并在最终建模时随 `dropna` 去掉。

这样做的目的不是“人为增强结果”，而是让时间序列结构在补缺时保留下来，尤其是 `抗菌药物使用强度` 这种按省逐年变化、且 2014 明显有系统缺口的变量。

## amplification 的定义

这里的 amplification 被 operationalize 成一个交互项：

```text
R1xday × 抗菌药物使用强度
```

它检验的是：

- 当极端降雨代理更高时，AMC 与 AMR 的关联是否更强

如果这个交互项稳定为正，才更接近题目里的“放大效应”。

## 当前默认组合

第一轮优先组合：

1. `方案A_平衡主线组`
2. `SYS_09556`
3. `SYS_09557`

原因：

- `方案A` 是人工主线
- `SYS_09556 / SYS_09557` 是系统穷举里 `R1xday` 和 `AMC` 都显著的高分组

## 第一轮已经得到的结果

当前第一轮 3 组 × 6 变体已经跑完。

主要结论是：

### 1. `year_only_*` 最能复现当前 FE 主线

- `R1xday` 主效应稳定为正
- `AMC` 主效应稳定为正

这说明贝叶斯 `year_only` 版本和你现有的 Year FE 线是对得上的。

### 2. `province_only_*` 与 `province_year_*` 会明显削弱 `R1xday` 主效应

这和 FE 结果也是一致的。

### 3. 第一轮最强的 amplification 信号出现在 `province_only_amplification`

三组交互项都为正，且 `95% CrI` 下界刚好越过 0：

- `方案A`: `0.0383 [0.0004, 0.0775]`
- `SYS_09556`: `0.0413 [0.0001, 0.0817]`
- `SYS_09557`: `0.0408 [0.0006, 0.0795]`

### 4. 但只要把年份控制进去，交互项就不再稳

- `year_only_amplification` 的交互项都偏正，但区间跨 0
- `province_year_amplification` 的交互项也偏正，但区间仍跨 0

所以当前最稳妥的判断是：

> amplification 在 province-only 口径下有较明确迹象，但在包含年份控制的版本里还不够稳。

## 这意味着什么

这一步最重要的价值，不是马上宣布“已经证明题目”，而是把后续路线选出来：

- 哪条线更适合做 lag
- 哪条线只是辅助参照
- 哪条线最接近当前主线

## 第二步为什么轮到 lag

既然第一轮已经把口径差异跑清楚，第二轮最合理的推进就是把 lag 接到 3 条最关键的 amplification 线：

1. `year_only_amplification`
2. `province_only_amplification`
3. `province_year_amplification`

原因分别是：

- `year_only_amplification`：最接近当前 FE 主线
- `province_only_amplification`：交互项最强
- `province_year_amplification`：最严谨

## Mundlak 现在放在哪里

`within-between / Mundlak` 不会被废弃，但它现在更适合第二轮或第三轮诊断：

- 用来拆解省内与省际信号
- 用来回答“当前正向结果到底更像哪里来的”

它不再是第一轮唯一的默认主规格。

## 当前文件与输出

- 主脚本：
  [run_bayes_selected_models.py](</e:/MALA/Code_health/4 贝叶斯分析/run_bayes_selected_models.py:1>)
- 选择接口：
  [model_selection.toml](</e:/MALA/Code_health/4 贝叶斯分析/model_selection.toml:1>)
- 候选清单：
  [bayes_candidate_models.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/bayes_candidate_models.csv:1>)

关键输出：

- [focus_variant_bridge_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_variant_bridge_summary.csv>)
- [focus_primary_summary.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/focus_primary_summary.csv>)
- [combined_diagnostics.csv](</e:/MALA/Code_health/4 贝叶斯分析/results/model_summaries/combined_diagnostics.csv>)

## 参考文献

- [Nature Medicine 文章](https://www.nature.com/articles/s41591-025-03629-3)
- [原文 INLA 脚本](https://raw.githubusercontent.com/Code-Storehouse/AMR-in-climate-change/main/3%20INLA%20model/INLA%20model.R)
- [Mundlak (1978)](https://people.stern.nyu.edu/wgreene/Econometrics/Mundlak-1978.pdf)
- [Bell, Fairbrother, Jones (2019)](https://research-information.bris.ac.uk/ws/portalfiles/portal/196855552/Bell2019_Article_FixedAndRandomEffectsModelsMak.pdf)
