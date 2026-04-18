# 1 单因素分析

这个目录负责固定效应主分析之前的变量探索、分类出图和最终单因素展示，是整个项目里“先看变量长什么样、再决定主线保留什么”的前置环节。

## 目录里主要有什么

- `amr_final.ipynb`
  - 当前单因素展示主入口。
  - 围绕 9 个重点变量输出 13 个 AMR 指标及综合指标 `AMR_AGG_z` 的最终图。
- `amr_climate.ipynb`
  - 偏早期探索底稿，保留缺失处理、去均值和 within 回归等分析过程。
- `amr_cmt_sc_plt.ipynb`
  - 偏当前实用出图流程，适合快速重做分类图和补图。
- `AMR_CLIMATE/`、`AMR_ENV/`、`AMR_SOCIO/`
  - 三类变量主题图输出目录。
- `AMR_selected9/`
  - 9 个精选变量对应的最终展示图。
- `AMR_OVERALL/`
  - 综合指标 `AMR_AGG_z` 的最终图。
- `figs/`
  - 汇报或论文中更适合直接引用的汇总图片。

## 三份 notebook 的分工

- `amr_final.ipynb`
  - 适合看当前最终口径，不建议再拿它回溯早期筛选逻辑。
- `amr_climate.ipynb`
  - 适合回看候选变量怎么被筛进或筛出，也适合检查探索阶段的处理方法。
- `amr_cmt_sc_plt.ipynb`
  - 适合快速重做图件，是当前最实用的补图入口。

## 当前固定保留的 9 个重点变量

- `TA`
- `PA`
- `R1xday`
- `PM25`
- `MED`
- `GDP`
- `WATER`
- `WASTE`
- `AMC`

## 推荐使用顺序

1. 先看 `amr_final.ipynb`，确认当前展示口径。
2. 需要回溯筛选逻辑时，再看 `amr_climate.ipynb`。
3. 需要快速补图时，优先用 `amr_cmt_sc_plt.ipynb`。

## 数据与维护说明

- 这些 notebook 里仍可能引用 `C:\Users\lunch\Downloads\amr_rate.csv` 与 `C:\Users\lunch\Downloads\climate_social_eco.csv` 这样的本机路径。
- 换机器前，先统一检查输入路径是否需要改到仓库根目录。
- 早期草稿 `amr_plotter.ipynb` 已移入 `../bakeup/1 单因素分析/`，需要时可回溯，但不建议再作为当前主线入口。
