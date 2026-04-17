# 3 单固定效应模型

这个文件夹用于存放按单个 AMR 指标分别建模的固定效应分析、共线性检查和结果矩阵整理。和“整体 AMR”主线不同，这里重点是把 13 个耐药指标拆开，逐个观察各解释变量的系数表现。

## 主要 notebook

- `1_VIF.ipynb`
  - 用于检查解释变量之间的多重共线性。
  - 包含 VIF 计算，以及对个别变量关系的补充检验。

- `2_single_species.ipynb`
  - 单菌种固定效应分析主 notebook。
  - 对 13 个 AMR 指标分别运行固定效应模型，并输出长表结果。

- `3_selected_X.ipynb`
  - 在单菌种分析基础上保留你筛选过的重点自变量。
  - 虽然和 `2_single_species.ipynb` 有较强重叠，但它反映了你主观筛选后的变量口径，所以需要保留。

- `0 初始待办记录.ipynb`
  - 原 `singal.ipynb` 的重命名版本。
  - 这是你创建“3 单固定效应模型”时最早的待办/思路记录，不是正式分析主流程，但值得保留做背景备注。

## 输出目录

- `outputs_single_species_fe/`
  - 单菌种固定效应结果长表。
  - 包含：
    - `single_species_FE_long_FIXED.csv`
    - `single_species_FE_long_FIXED.xlsx`

- `outputs_compare_tables/`
  - 汇总后的对比表。
  - 当前核心文件：
    - `AMR_13x9_coef_matrix_with_significance.xlsx`

- `lancet_tables_by_species/`
  - 按菌种拆分的 Lancet 风格表格目录。
  - 每个 `Lancet_*.csv` 对应一种 AMR 指标。

## 关于 `single_species_FE_long.*`

- 当前仓库中仍能明确找到的导出代码，只会输出：
  - `single_species_FE_long_FIXED.csv`
  - `single_species_FE_long_FIXED.xlsx`

- 现存代码里没有 notebook 直接写出：
  - `single_species_FE_long.csv`
  - `single_species_FE_long.xlsx`

因此，这两份 `single_species_FE_long.*` 更像是更早版本运行后留下的历史结果，而不是当前代码主线直接生成的结果。

- 这两份历史文件现已移入根目录：
  - `bakeup/3 单固定效应模型/outputs_single_species_fe/`

## 已归档文件

- 原始文件名 `singal.ipynb` 已保留到根目录 `bakeup/3 单固定效应模型/`。
- 现在工作区内使用更清晰的名称：`0 初始待办记录.ipynb`。
- 历史输出 `single_species_FE_long.csv/.xlsx` 也已移入 `bakeup/`。

## 推荐查看顺序

1. 先看 `1_VIF.ipynb`，确认变量共线性情况。
2. 再看 `2_single_species.ipynb`，理解单菌种固定效应主流程。
3. 最后看 `3_selected_X.ipynb` 和各输出表，查看筛选后的重点结果。

## 数据依赖

这些 notebook 当前默认读取本机路径下的原始数据：

- `C:\Users\lunch\Downloads\amr_rate.csv`
- `C:\Users\lunch\Downloads\climate_social_eco.csv`
