# 3 单固定效应模型

这个目录负责把 13 个 AMR 指标拆开，分别运行固定效应模型，检查综合指标主线在单菌种层面是否还能成立。它更偏“异质性核对”和“结果拆解”，而不是当前论文主结果的第一入口。

## 目录结构

- `1_VIF.ipynb`
  - 检查解释变量间的多重共线性。
- `2_single_species.ipynb`
  - 单菌种固定效应主流程，对 13 个 AMR 指标逐个建模。
- `3_selected_X.ipynb`
  - 在单菌种分析中保留筛选后的重点自变量，便于聚焦解释。
- `0 初始待办记录.ipynb`
  - 早期待办和思路记录，保留背景信息，不属于当前正式主流程。
- `outputs_single_species_fe/`
  - 当前主线导出的单菌种长表结果。
- `outputs_compare_tables/`
  - 汇总后的对比表，适合横向比较 13 个 AMR 指标。
- `lancet_tables_by_species/`
  - 分菌种的 Lancet 风格结果表。

## 当前应以哪些结果文件为准

- 当前现存代码明确导出的标准结果是：
  - `single_species_FE_long_FIXED.csv`
  - `single_species_FE_long_FIXED.xlsx`
- 不带 `FIXED` 后缀的 `single_species_FE_long.csv/.xlsx` 已视为历史版本，现已移入 `../bakeup/3 单固定效应模型/outputs_single_species_fe/`。

## 这个目录最适合回答什么问题

- `R1xday` 与 `抗菌药物使用强度` 的正向信号，是否会在所有单菌种里同时出现？
- 哪些单菌种对气候、污染、发展或卫生代理更敏感？
- 综合指标 `AMR_AGG_z` 的发现，是否主要来自少数指标驱动？

## 推荐查看顺序

1. 先打开 `1_VIF.ipynb`，确认重点变量组合是否存在明显共线性问题。
2. 再看 `2_single_species.ipynb`，理解逐菌种建模流程。
3. 最后结合 `3_selected_X.ipynb` 与 `outputs_compare_tables/` 看重点变量的横向表现。

## 归档说明

- 原始命名 `singal.ipynb` 已归档到 `../bakeup/3 单固定效应模型/`。
- 历史长表结果也已归档到 `bakeup/`，避免和当前主线导出文件混淆。

## 数据依赖

- 一些旧 notebook 仍默认读取：
  - `C:\Users\lunch\Downloads\amr_rate.csv`
  - `C:\Users\lunch\Downloads\climate_social_eco.csv`
- 换环境前，建议优先改成读取仓库根目录下的两份 CSV。
