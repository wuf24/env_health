# 1 单因素分析

这个文件夹用于存放固定效应模型之外的单因素探索、分类出图和最终单因素展示结果。当前主线是先做气候、环境、社会经济三类变量的探索，再在 `amr_final.ipynb` 中收敛到最终选出的 9 个重点变量。

## 主要 notebook

- `amr_final.ipynb`
  - 当前单因素展示的最终版 notebook。
  - 固定使用 9 个重点变量：
    - `TA`
    - `PA`
    - `R1xday`
    - `PM25`
    - `MED`
    - `GDP`
    - `WATER`
    - `WASTE`
    - `AMC`
  - 为 13 个 AMR 指标和综合指标 `AMR_AGG_z` 生成最终图。

- `amr_climate.ipynb`
  - 偏探索分析的 notebook。
  - 除了分类出图，还保留了缺失处理、两维去均值、`run_cluster_ols` 和多 AMR 的 within 回归等过程。
  - 用法：当你想回头看候选变量筛选过程，或检查某一类变量在更早探索阶段的表现时看这个文件。

- `amr_cmt_sc_plt.ipynb`
  - 偏向分类出图和排版的 notebook。
  - 已覆盖主线最常用的部分：按省插值补缺、GDP 分组、`AMR_AGG_z` 构造，以及 `AMR_ENV / AMR_CLIMATE / AMR_SOCIO` 三类图的导出。
  - 用法：当你想快速查看三大类变量的图，或补充 `amr_final.ipynb` 之外的候选变量展示时，优先看这个文件。

## `amr_climate.ipynb` 与 `amr_cmt_sc_plt.ipynb` 的关系

- 两者有明显重叠，后半段的分类出图结果大体相通。
- `amr_cmt_sc_plt.ipynb` 更接近当前实用主线，适合快速出图和按类别回看变量。
- `amr_climate.ipynb` 更像早期探索底稿，保留了 `amr_cmt_sc_plt.ipynb` 里没有的去均值/within 回归过程。
- 现在如果只想补图或补变量展示，优先使用 `amr_cmt_sc_plt.ipynb`；如果想回溯分析思路，再看 `amr_climate.ipynb`。

## 输出目录

- `AMR_CLIMATE`
  - 气候因素相关图。

- `AMR_ENV`
  - 环境污染因素相关图。

- `AMR_SOCIO`
  - 社会经济因素相关图。

- `AMR_selected9`
  - 13 个 AMR 指标对应 9 个精选变量的最终图。

- `AMR_OVERALL`
  - 综合 AMR 指标 `AMR_AGG_z` 的最终图。

- `figs`
  - 适合汇报或论文插图的汇总图片。

## 已归档文件

- 早期草稿绘图 notebook `amr_plotter.ipynb` 已移入根目录 `bakeup/1 单因素分析/`。
- 归档不等于真正删除；如果后续需要恢复，可以从 `bakeup` 中取回。

## 推荐查看顺序

1. 先看 `amr_final.ipynb`，理解当前单因素最终口径。
2. 再看 `amr_climate.ipynb` 和 `amr_cmt_sc_plt.ipynb`，查看各类别候选变量和分类图。
3. 如果要回溯旧草稿，再去根目录 `bakeup/` 查看历史文件。

## 数据依赖

这些 notebook 当前默认读取本机路径下的原始数据：

- `C:\Users\lunch\Downloads\amr_rate.csv`
- `C:\Users\lunch\Downloads\climate_social_eco.csv`

如果换机器或换目录，需要先修改 notebook 中的输入路径。
