# AMR_AGG_raw_mean 未来情景预测说明

## 这套脚本如何承接 Lancet 文章

1. 先沿用 `5 反事实推演` 已筛出的固定效应模型，不重新发明一套新的主模型。
   当前读取模型来源目录：`5 反事实推演/results/AMR_AGG/model_screening/selected_models.csv`。
2. 用历史面板重新拟合 FE 关联模型，保留各协变量在历史样本中的标准化尺度和回归系数。
3. 对 outcome 本身先做省级 ETS 基线外推，这一步对应 Lancet 文章里“baseline scenario continued at current rates, as estimated by ETS models”的思路。
4. 对未来情景不直接重算 FE，而是在 ETS 基线之上叠加情景调整项：未来协变量路径相对基线路径的变化，经历史 FE 系数折算后加回基线。
5. 当前只让 `R1xday` 进入未来情景控制，其余协变量默认沿基线延续；这一步是刻意对齐你现在的研究设定，相当于论文里只控制 PM2.5 的那条主线。

## 本次默认设置

- 投影区间：2024–2050
- 运行模型角色：main_model, robust_low_vif, robust_systematic, robust_strict_fe
- 未来外部情景变量：`R1xday`
- 基线：省级 ETS 外推
- 气候情景：CCKP 逐年 `rx1day` 的 `ssp119/126/245/370/585`
- 不确定性带：直接保留 CCKP 的 `median / p10 / p90` 三条路径

## 数学表达

历史关联模型：
```text
Y_it = α_i + λ_t + Σ_k β_k Z_itk + ε_it
```

未来基线：
```text
Y^base_it = ETS(Y_i,1...T)
```

未来情景调整：
```text
Δ^scenario_it = Σ_k β_k × ( Z^scenario_itk - Z^base_itk )
```

最终情景预测：
```text
Y^scenario_it = Y^base_it + Δ^scenario_it
```

如果后续补齐死亡负担模块，还可以在预测的 AMR prevalence 基础上继续套：
```text
PAF = p (RR - 1) / [1 + p (RR - 1)]
```

也就是 Lancet 文中从耐药流行率进一步推死亡负担的那一步；当前仓库暂无省级感染死亡数和 RR 输入，所以代码里只保留接口，默认不启用。