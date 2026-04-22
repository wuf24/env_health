# 两种 baseline 版本详解

## 这次新增了什么

- `lancet_ets`：Lancet 风格 baseline。
- `x_driven`：X-driven / 简化 Nature Medicine 风格 baseline。

两版都沿用同一套历史省级模型、同一批未来 `R1xday` 情景、同一套全国算术平均口径。  
唯一核心差异，是“未来 baseline 到底怎么生成”。

## 共同框架

无论哪一版，都是先做省级预测，再做全国算术平均：

```text
先得到 AMR^scenario_it
再计算 AMR^scenario_t = (1 / N_t) * Σ_i AMR^scenario_it
```

这里：

- `i` 表示省份
- `t` 表示年份
- `N_t` 表示该年的省份数

也就是说，不是先算一个“全国 R1xday”再代模型，而是：

1. 每个省都有自己的 `R1xday_it`
2. 每个省先预测自己的 `AMR_it`
3. 最后对各省预测值取算术平均，得到全国结果

这和你前面要求的 Lancet 口径是一致的。

## 版本一：lancet_ets

### 核心思想

这版最接近 Lancet 文章里那句：

```text
baseline scenario continued at current rates, as estimated by ETS models
```

意思是：

- 先让 `AMR` 自己按历史趋势往未来延伸
- 这条延伸出来的结果，就是 baseline
- 然后再把未来 `R1xday` 情景的影响，作为“增量”叠加到 baseline 上

### 公式

历史模型：

```text
Y_it = α_i + λ_t + Σ_k β_k Z_itk + ε_it
```

未来 baseline：

```text
Y^base_it = ETS(Y_i, historical series)
```

未来情景增量：

```text
Δ^scenario_it = Σ_k β_k × (Z^scenario_itk - Z^base_itk)
```

最终未来预测：

```text
Y^scenario_it = Y^base_it + Δ^scenario_it
```

### 这版的特点

- 优点：最贴近 Lancet 2023 的表述和实现思路。
- 缺点：未来曲线容易被 AMR 自身的历史惯性主导。
- 结果表现：如果历史 AMR 在下降，未来 baseline 往往也更容易继续下降。

### 什么时候优先看它

- 当你要强调“我严格参考 Lancet 文章”
- 当你希望保留“结果变量自身趋势延续”的解释

## 版本二：x_driven

### 核心思想

这版不再让 `AMR` 自己决定 baseline，而是让未来协变量路径决定 baseline。

也就是说：

- 先给未来协变量一条 baseline 路径
- 再把这些未来协变量代回历史模型
- 用模型结构重建未来 `AMR`

这更接近 Nature Medicine 2025 的精神，只是目前还是简化版。

### 公式

历史模型：

```text
Y_it = α_i + λ_t + Σ_k β_k Z_itk + ε_it
```

未来 baseline：

```text
Y^base_it = α_i^* + λ_t^* + Σ_k β_k Z^base_itk
```

未来情景：

```text
Y^scenario_it = α_i^* + λ_t^* + Σ_k β_k Z^scenario_itk
```

如果当前只控制 `R1xday`，则可以写成：

```text
Y^scenario_it = Y^base_it + β_R × (R1xday^scenario_it - R1xday^base_it)
```

### 这里的 `R1xday^base_it` 是什么

它表示：

```text
省 i、年份 t、baseline 路径下的 R1xday
```

在当前实现里：

- `R1xday^base_it` 先按历史省级 `R1xday` 序列做 ETS 延续
- 其他协变量的 baseline 路径也做各自 ETS 延续
- 然后再一起代回历史面板模型

### 这版的特点

- 优点：未来曲线更受未来协变量路径影响，机制解释更强。
- 缺点：还不是 Nature Medicine 那种完整的时空贝叶斯模型。
- 结果表现：不同 SSP 之间通常会比 `lancet_ets` 更容易拉开差距。

### 什么时候优先看它

- 当你更关心“未来气候路径如何驱动 AMR”
- 当你不想让结果被历史 AMR 的单边惯性锁死

## 你现在应该怎么用

如果你的目标是“尽量贴近 Lancet 写法”，优先看：

- `results/lancet_ets/`

如果你的目标是“更强调未来 `R1xday` 情景驱动”，优先看：

- `results/x_driven/`

如果你要写论文方法部分，建议两版都保留：

- 主分析：`lancet_ets`
- 扩展/敏感性分析：`x_driven`

这样既能对齐参考文献，也能回应“为什么未来结果会被 baseline 设定影响”的方法学问题。

## 当前这次结果为什么两版的情景增量几乎一样

这次你会看到一个很重要的现象：

- 两版的 `scenario_pred_mean` 水平不同
- 但 `delta_vs_baseline` 基本相同

原因是当前实现里：

1. 两版都使用同一套历史回归系数 `β_R`
2. 两版都使用同一套未来 `R1xday` 情景路径
3. 两版的差异只在于 baseline 本身怎么生成

因此当前可以写成：

```text
Y^scenario_it = Y^base_it + β_R × (R1xday^scenario_it - R1xday^base_it)
```

只要右边的 `β_R` 和 `R1xday` 情景差值相同，那么：

- 情景相对 baseline 的增量会相同
- 不同的只是 baseline 水平本身

所以目前这两版更像是在回答两个不同问题：

- `lancet_ets`：如果 AMR 自身惯性延续，未来情景会把它往上推多少？
- `x_driven`：如果未来 baseline 由协变量路径决定，未来情景又会把它往上推多少？
