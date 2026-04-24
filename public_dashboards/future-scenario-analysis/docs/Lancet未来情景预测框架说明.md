# Lancet 未来情景预测框架说明

这份说明对应 `6 未来情景分析/scripts/run_future_scenario_projection.py`，目标是把 `5 反事实推演` 里已经成熟的固定效应建模思路，改造成更接近参考文献 Figure 5 的“前向情景预测”框架。

## 一句话概括

不是把未来情景分析简单理解成“反事实的反方向”，而是：

1. 先用历史省级面板估计协变量与 AMR 的关联结构。
2. 再为未来 baseline 构造一条延续路径。
3. 最后把未来情景下协变量相对 baseline 的变化，按历史系数折算成情景调整项，加回 baseline。

## 与 `5 反事实推演` 的关系

`5 反事实推演` 的核心是：

```text
历史观测值 -> 读取模型归档 -> 用同一套 FE 系数做基准替换 -> 比较 actual 与 counterfactual
```

这里改成：

```text
历史观测值 -> 读取同一套 12 模型归档 -> 用同一套 FE 系数做未来情景调整 -> 比较 baseline 与 future scenario
```

也就是说，保留了：

- 既有模型筛选结果
- 固定效应主模型与稳健性模型
- 历史标准化尺度
- 省级面板结构

替换掉的是：

- “把某些变量恢复到基准年”的反事实设定
- 改为“让某些变量沿未来情景路径前进”的前向预测设定

## 当前不是单模型，而是 12 模型归档

这一点和旧版理解最不一样。当前未来情景分析读取的不是单个 `main_model`，而是与反事实模块共享的统一 12 模型归档：

- 原始主线 4 个：`main_model`、`robust_low_vif`、`robust_systematic`、`robust_systematic_2`
- 严筛扩展 8 个：`strict_main_model`、`strict_top_02` 到 `strict_top_08`

因此当前写法应该是：

- `main_model` 负责最清晰的正文主叙事
- 其余 11 个模型负责说明结果在变量代理、筛选门槛和模型来源变化下是否仍稳定
- 结果页和说明文档都应支持逐模型查看，而不只是继续延伸主模型

## 严格参照 Lancet 文章时，对应的关键步骤

参考文献公开文本中可以确认的要点是：

1. 用历史面板做固定效应回归。
2. baseline 不是直接把回归方程一路往前算，而是先让结局变量或协变量按 baseline 方法延续。
3. 不同 SSP 情景是在 baseline 之上叠加协变量变化形成的。
4. 如果要走到疾病负担，还需要把预测耐药率继续折算成死亡或 YLL。

在本项目里，对应成：

### 第一步：历史关联模型

```text
Y_it = α_i + λ_t + Σ_k β_k Z_itk + ε_it
```

- `Y_it`：历史 AMR 指标
- `α_i`：省固定效应
- `λ_t`：年固定效应
- `Z_itk`：按历史样本均值和标准差标准化后的协变量
- `β_k`：历史面板中识别出的关联系数

### 第二步：baseline 路径

当前仓库同时保留两种 baseline：

- `lancet_ets`
  让结局 `AMR` 自身按历史趋势做 ETS 外推
- `x_driven`
  让未来协变量路径先形成 baseline，再代回历史面板结构

### 第三步：未来情景调整

```text
Δ_it^scenario = Σ_k β_k × (Z_itk^scenario - Z_itk^base)
```

### 第四步：未来情景预测值

```text
Y_it^scenario = Y_it^base + Δ_it^scenario
```

## 当前仓库里已经做成了什么

当前已经能稳定运行的是：

- 历史 outcome：`AMR_AGG_RAW` 或单一 AMR 指标
- 历史协变量：沿用 `climate_social_eco.csv`
- 外部未来路径：CCKP 中国省级逐年 `rx1day`
- baseline 版本：`lancet_ets` 与 `x_driven`
- 情景组：`ssp119 / ssp126 / ssp245 / ssp370 / ssp585`
- 不确定性路径：`median / p10 / p90`
- 模型口径：统一 12 模型归档

## 为什么当前先只把 `R1xday` 接进来

因为当前已经真正落地并核验过的未来省级逐年变量，正式进入主流程的只有：

- `R1xday`

而参考框架中还会涉及：

- 抗菌药物使用
- 供水/卫生
- 经济与医疗投入
- 更完整的 SSP 社会经济路径

这些在当前仓库里还没有同口径省级未来路径，所以这一步先把框架搭好：

- 先让 `R1xday` 真正驱动未来情景分化
- 其余协变量先沿 baseline 路径延续
- 后面再逐个往里补未来输入表

## 为什么要做外部气候路径与历史观测的对齐

CCKP 的逐年 `rx1day` 来自气候模型集合，并不等于历史面板里直接使用的观测口径。为此脚本默认做了一个稳妥处理：

- 用历史重叠年份计算每个省在每个 SSP/统计量下的平均偏差
- 对未来 `rx1day` 路径先做 bias correction
- 再与历史口径下的 baseline 路径比较

这样比“直接拼接”更适合作为论文主线版本。

## 当前应该如何阅读结果

当前最重要的不是只盯着 `main_model` 的一条线，而是同时看三层：

1. 主模型图：帮助快速把握正文主叙事。
2. 12 模型总览表：帮助判断哪些结论对模型设定稳健。
3. 逐模型详细分析：帮助解释为什么有的模型对 SSP spread 更敏感，有的模型 baseline 更高或更低。

当前结果目录里已经补充了对应文件：

- `results/lancet_ets/model_role_detail_summary.csv`
- `results/lancet_ets/model_role_detailed_analysis.md`
- `results/x_driven/model_role_detail_summary.csv`
- `results/x_driven/model_role_detailed_analysis.md`
- `results/baseline_mode_compare/model_role_2050_compare.csv`

## 如果后面要继续贴近 Lancet Figure 5

下一步最值得补的不是再改公式，而是补输入：

1. 省级未来抗菌药物使用路径
2. 省级未来供水与卫生条件路径
3. 省级未来经济与医疗投入路径
4. 如果要走到死亡负担，还要补省级感染死亡数和 RR

一旦这些输入补齐，这套框架就可以自然扩展到：

- 单因素控制情景
- 多因素联合控制情景
- 2050 多情景比较图
- 死亡负担与经济负担模块
