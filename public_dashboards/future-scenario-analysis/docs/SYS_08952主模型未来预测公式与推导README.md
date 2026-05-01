# SYS_08952 主模型未来预测公式与推导

这份说明专门对应当前未来情景分析模块中的主模型 `SYS_08952 / main_model`，目的是把以下几个问题一次讲清楚：

1. 当前主模型的历史固定效应方程到底是什么。
2. `x_driven` / direct projection 和 `baseline + delta` 到底是什么关系。
3. `c*`、`λ_t*` 这些量是怎么得到的。
4. 在当前实现里，哪些自变量真的进入未来情景变化，哪些只是沿 baseline 延续。
5. 如何把这套方法写进论文的方法部分。

## 1. 这份文档对应哪个模型

当前未来情景模块默认预测对象是：

- `AMR_AGG_RAW`

它表示：

- `13` 个 AMR 指标原始百分比的行均值

这和固定效应筛选阶段常见的 `AMR_AGG_z` 不完全相同。未来情景模块当前是：

- 用 `AMR_AGG` 归档筛出来的变量组合
- 但把结果变量切换到 `AMR_AGG_RAW` 来做未来预测

对应配置可见：

- `results/run_metadata.json`
- `scripts/future_scenario_common.py`

## 2. 当前主模型的变量和系数

当前主模型 `SYS_08952 / main_model` 的变量组合是：

- `R1xday`
- `抗菌药物使用强度`
- `TA（°C）`
- `氮氧化物`
- `医疗水平`
- `人均日生活用水量(升)`
- `牲畜饲养-猪年底头数`
- `文盲比例`

未来情景模块里为该模型重新拟合得到的系数为：

- `β_R1xday = 0.8681434804`
- `β_AMC = 0.7386021840`
- `β_TA = 0.5511428509`
- `β_NOx = 1.2342681115`
- `β_医疗水平 = 1.4591550495`
- `β_生活用水 = 0.0164365941`
- `β_牲畜 = 0.8136772860`
- `β_文盲比例 = 0.7899568465`

这些系数来自：

- `results/model_screening/future_projection_coefficients.csv`

## 3. 记号定义

设：

- `i` 表示省份
- `t` 表示年份
- `k` 表示第 `k` 个自变量
- `y_it` 表示省份 `i` 在年份 `t` 的结果变量
- `x_itk` 表示第 `k` 个自变量的原始值
- `μ_k` 表示第 `k` 个自变量在历史样本中的均值
- `σ_k` 表示第 `k` 个自变量在历史样本中的标准差
- `z_itk = (x_itk - μ_k) / σ_k` 表示标准化后的自变量
- `β_k` 表示历史模型中该变量的估计系数
- `λ_t` 表示年份固定效应
- `ε_it` 表示误差项

注意：当前主模型的固定效应设定是：

- `Province: No / Year: Yes`

因此这个模型没有单独的省固定效应 `α_i`，只有年份固定效应 `λ_t`。

## 4. 历史固定效应方程

历史期方程可写成：

```text
y_it
= λ_t
+ 0.8681434804 · z(R1xday_it)
+ 0.7386021840 · z(抗菌药物使用强度_it)
+ 0.5511428509 · z(TA_it)
+ 1.2342681115 · z(氮氧化物_it)
+ 1.4591550495 · z(医疗水平_it)
+ 0.0164365941 · z(人均日生活用水量_it)
+ 0.8136772860 · z(牲畜饲养-猪年底头数_it)
+ 0.7899568465 · z(文盲比例_it)
+ ε_it
```

其中标准化定义为：

```text
z(X_it) = (X_it - μ_X) / σ_X
```

这里的 `μ_X` 和 `σ_X` 都固定取自历史样本，不会因为未来情景不同而改变。

## 5. 当前 x_driven 的 future baseline 公式

在 `x_driven` 下，先给每个自变量生成一条未来 baseline 路径：

```text
X_it^base
```

然后按历史均值和标准差标准化：

```text
z(X_it^base) = (X_it^base - μ_X) / σ_X
```

于是未来 baseline 可以写成：

```text
ŷ_it^base
= c*
+ λ_t*
+ 0.8681434804 · z(R1xday_it^base)
+ 0.7386021840 · z(抗菌药物使用强度_it^base)
+ 0.5511428509 · z(TA_it^base)
+ 1.2342681115 · z(氮氧化物_it^base)
+ 1.4591550495 · z(医疗水平_it^base)
+ 0.0164365941 · z(人均日生活用水量_it^base)
+ 0.8136772860 · z(牲畜饲养-猪年底头数_it^base)
+ 0.7899568465 · z(文盲比例_it^base)
```

这里：

- `c*` 是历史剩余项的总体平均水平
- `λ_t*` 是未来年份效应
- 所有 `X_it^base` 都是未来 baseline 路径下的原始值

## 6. 直接代入 future scenario 的公式

如果某个未来情景下，各变量的未来值是：

```text
X_it^scen
```

则直接代入的未来情景预测公式为：

```text
ŷ_it^scen
= c*
+ λ_t*
+ 0.8681434804 · z(R1xday_it^scen)
+ 0.7386021840 · z(抗菌药物使用强度_it^scen)
+ 0.5511428509 · z(TA_it^scen)
+ 1.2342681115 · z(氮氧化物_it^scen)
+ 1.4591550495 · z(医疗水平_it^scen)
+ 0.0164365941 · z(人均日生活用水量_it^scen)
+ 0.8136772860 · z(牲畜饲养-猪年底头数_it^scen)
+ 0.7899568465 · z(文盲比例_it^scen)
```

这就是最直观的 “把未来每年的自变量值直接带进方程里” 的写法。

## 7. baseline + delta 的等价改写

上面 future baseline 和 future scenario 两式相减：

```text
ŷ_it^scen - ŷ_it^base
= [c* + λ_t* + Σ β_k z(X_itk^scen)]
 - [c* + λ_t* + Σ β_k z(X_itk^base)]
= Σ β_k [ z(X_itk^scen) - z(X_itk^base) ]
```

定义：

```text
Δ_it^scen = Σ β_k [ z(X_itk^scen) - z(X_itk^base) ]
```

则有：

```text
ŷ_it^scen = ŷ_it^base + Δ_it^scen
```

这就是 `baseline + delta`。

也就是说：

- `direct projection`
- `baseline + delta`

在 `x_driven` 框架下是完全等价的，不是两套不同方法。

## 8. delta 的原始量纲写法

因为：

```text
z(X_it^scen) - z(X_it^base)
= [(X_it^scen - μ_X) - (X_it^base - μ_X)] / σ_X
= (X_it^scen - X_it^base) / σ_X
```

所以可以把 `Δ_it^scen` 直接写成：

```text
Δ_it^scen
= 0.8681434804 · (R1xday_it^scen - R1xday_it^base) / σ_R1xday
+ 0.7386021840 · (抗菌药物使用强度_it^scen - 抗菌药物使用强度_it^base) / σ_AMC
+ 0.5511428509 · (TA_it^scen - TA_it^base) / σ_TA
+ 1.2342681115 · (氮氧化物_it^scen - 氮氧化物_it^base) / σ_NOx
+ 1.4591550495 · (医疗水平_it^scen - 医疗水平_it^base) / σ_医疗水平
+ 0.0164365941 · (人均日生活用水量_it^scen - 人均日生活用水量_it^base) / σ_生活用水
+ 0.8136772860 · (牲畜饲养-猪年底头数_it^scen - 牲畜饲养-猪年底头数_it^base) / σ_牲畜
+ 0.7899568465 · (文盲比例_it^scen - 文盲比例_it^base) / σ_文盲比例
```

最终：

```text
ŷ_it^scen = ŷ_it^base + Δ_it^scen
```

## 9. `c*` 和 `λ_t*` 是怎么来的

它们不是在固定效应结果表里直接现成给出的，而是历史模型估计完成后再重建出来的。

### 9.1 第一步：计算历史样本中的自变量贡献

对每个历史观测点，先计算：

```text
history_component_it = Σ β_k z(X_itk)
```

对 `SYS_08952` 来说就是：

```text
history_component_it
= 0.8681434804 · z(R1xday_it)
+ 0.7386021840 · z(抗菌药物使用强度_it)
+ 0.5511428509 · z(TA_it)
+ 1.2342681115 · z(氮氧化物_it)
+ 1.4591550495 · z(医疗水平_it)
+ 0.0164365941 · z(人均日生活用水量_it)
+ 0.8136772860 · z(牲畜饲养-猪年底头数_it)
+ 0.7899568465 · z(文盲比例_it)
```

### 9.2 第二步：用真实结果变量减去自变量贡献

```text
remainder_it = y_it - history_component_it
```

这个 `remainder_it` 里包含的是：

```text
remainder_it ≈ c + λ_t + ε_it
```

### 9.3 第三步：取总体平均，得到 `c*`

```text
c* = mean(remainder_it)
```

### 9.4 第四步：取每个年份的平均偏离，得到历史 `λ_t`

因为当前主模型没有省固定效应，所以从 `remainder_it` 中扣掉总体平均后，按年份求平均：

```text
λ_t(hist) = mean_i(remainder_it - c*)
```

### 9.5 第五步：把历史年份效应继续外推到未来，得到 `λ_t*`

未来年份没有真实观测值，所以不能直接知道，只能外推。当前实现是：

```text
λ_t* = ETS( λ_t(hist) )
```

于是未来 baseline 才能写成：

```text
ŷ_it^base = c* + λ_t* + Σ β_k z(X_itk^base)
```

## 10. 当前项目里，哪些变量真的进入了情景变化

理论上，对 `SYS_08952` 来说，上面 8 个变量都可以出现在 `Δ_it^scen` 里。

但在当前实现里，不同情景并不是所有变量都真的变化。

### 10.1 气候 SSP 情景

当前 `ssp119 / ssp126 / ssp245 / ssp370 / ssp585` 这类 climate SSP 情景，真正被外部 future path 替换的主要是：

- `R1xday`
- `TA（°C）`

其余变量当前仍按各自的 baseline 路径延续。因此对当前主模型来说，climate 情景下的 `delta` 会简化成：

```text
Δ_it^climate
= 0.8681434804 · (R1xday_it^scen - R1xday_it^base) / σ_R1xday
+ 0.5511428509 · (TA_it^scen - TA_it^base) / σ_TA
```

其余项等于 `0`，因为：

```text
X_it^scen = X_it^base
```

### 10.2 AMC -50% 干预情景

当前还存在一个单独的 `amc_reduce_50` 干预情景。它定义为：

- 保持气候和其他变量都在 baseline 路径上
- 仅将 `抗菌药物使用强度` 从未来起始年到 `2050` 年线性缩放到 baseline 的 `50%`

于是：

```text
Δ_it^AMC-50%
= 0.7386021840 · (抗菌药物使用强度_it^scen - 抗菌药物使用强度_it^base) / σ_AMC
```

其中：

```text
抗菌药物使用强度_it^scen = s_t · 抗菌药物使用强度_it^base
```

`s_t` 是线性下降的年度比例系数。

## 11. 与 `lancet_ets` 的根本区别

上面这些推导都属于：

- `x_driven`
- `direct projection`
- `baseline + delta`

它们是一类方法。

`lancet_ets` 不一样。它不是先由 future covariates 重建 baseline，而是：

```text
ŷ_it^base = ETS(y_i 的历史序列)
```

然后再加情景增量：

```text
ŷ_it^scen = ŷ_it^base + Δ_it^scen
```

因此：

- `x_driven` 可以被看成 “future X directly drives future Y”
- `lancet_ets` 则是 “future Y baseline 先由 Y 自身历史惯性决定，再叠加情景偏移”

## 12. 论文方法部分的推荐写法

下面给出一版可直接用于论文的方法描述。

### 12.1 简洁版

本研究在未来情景预测模块中采用主模型 `SYS_08952` 作为正文主线模型。该模型为仅包含年份固定效应的省级面板回归，解释变量包括极端降水指数 `R1xday`、抗菌药物使用强度、温度异常 `TA`、氮氧化物、医疗水平、人均日生活用水量、牲畜饲养规模和文盲比例。历史期模型首先基于各解释变量的标准化值估计其与综合耐药指标 `AMR_AGG_RAW` 的关联系数。随后，在未来预测阶段，对各协变量 baseline 路径进行省级年度外推，并基于历史系数和未来协变量路径重建 future baseline。对给定情景 `s`，未来预测值可写为：

```text
ŷ_it^s = ŷ_it^base + Σ_k β_k (X_itk^s - X_itk^base) / σ_k
```

其中，`β_k` 为历史模型估计系数，`X_itk^base` 和 `X_itk^s` 分别表示 baseline 与情景路径下的未来协变量原始值，`σ_k` 为变量 `k` 在历史样本中的标准差。该写法与直接将 future scenario covariates 代入预测方程在数学上等价，但更便于区分 baseline 水平与情景增量的相对贡献。

### 12.2 展开版

本研究基于历史省级面板数据构建未来情景预测模型。对于主模型 `SYS_08952`，设省份 `i` 在年份 `t` 的综合耐药指标为 `y_it`，则历史期回归方程为：

```text
y_it = λ_t + Σ_k β_k z(X_itk) + ε_it
```

其中，`λ_t` 表示年份固定效应，`z(X_itk)` 表示协变量 `X_itk` 按历史样本均值和标准差标准化后的数值。未来预测阶段首先为各协变量生成 baseline 路径，并基于历史剩余项重建未来共同水平项和年份效应，从而得到：

```text
ŷ_it^base = c* + λ_t* + Σ_k β_k z(X_itk^base)
```

对于任一未来情景 `s`，未来预测值写为：

```text
ŷ_it^s = c* + λ_t* + Σ_k β_k z(X_itk^s)
```

进一步可改写为：

```text
ŷ_it^s = ŷ_it^base + Σ_k β_k [ z(X_itk^s) - z(X_itk^base) ]
       = ŷ_it^base + Σ_k β_k (X_itk^s - X_itk^base) / σ_k
```

因此，本文的 future scenario prediction 既可理解为“将 future covariate paths 直接代入历史估计结构”，也可理解为“在 baseline 之上累加情景增量”。当前主分析中，气候情景主要通过 `R1xday` 和 `TA` 的省级 SSP 路径进入模型，而其余协变量在未提供外部未来情景路径时沿各自 baseline 路径延续。

## 13. 结果解释时的推荐表述

在写结果时，可以把这套公式翻译成下面三句话：

1. 主模型 `SYS_08952` 的未来预测值由两部分组成：future baseline 和情景增量。
2. future baseline 由历史固定效应结构与各协变量 baseline 路径共同决定。
3. 情景之间的差异来源于那些真正被情景替换或缩放的变量，例如当前主流程中的 `R1xday`、`TA` 和特定干预下的 `抗菌药物使用强度`。

## 14. 一句话总结

对当前主模型 `SYS_08952` 来说：

- 如果写成 direct projection，就是：

```text
ŷ_it^scen = c* + λ_t* + Σ β_k z(X_itk^scen)
```

- 如果写成 baseline + delta，就是：

```text
ŷ_it^scen = ŷ_it^base + Σ β_k (X_itk^scen - X_itk^base) / σ_k
```

二者完全等价；区别只在于表达方式，不在于计算逻辑。
