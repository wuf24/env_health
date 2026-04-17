# bakeup

这个文件夹用于存放“从主工作区移出，但不真正删除”的文件。

## 目的

- 避免直接删文件后无法追溯。
- 让主目录保持整洁，只保留当前分析主线需要的文件。
- 保留旧版 notebook、旧版结果表、早期草稿和被替换的文件名版本。

## 规则

- 需要“删除”的文件，不做真正删除，而是移动到 `bakeup/`。
- 在 `bakeup/` 中尽量保留原来的目录层级，方便回溯来源。
- 如果只是改名，也保留原始文件名版本到 `bakeup/`。

## 当前已归档内容

- `1 单因素分析/amr_plotter.ipynb`
  - 早期草稿绘图 notebook。

- `2 固定效应模型/cluster.ipynb`
  - 旧版固定效应 notebook。

- `2 固定效应模型/AMR_AGG_z_FE_results.csv`
- `2 固定效应模型/AMR_AGG_z_FE_results.xlsx`
- `2 固定效应模型/AMR_AGG_z_FE_results.tex`
  - 由旧版 `cluster.ipynb` 生成的结果文件。

- `2 固定效应模型/CoefficientForest.ipynb`
- `2 固定效应模型/AMR_AGG_z_FE_forest.png`
- `2 固定效应模型/AMR_AGG_z_FE_forest.pdf`
  - 旧版固定效应森林图流程及产物。

- `2 固定效应模型/amr_lancet_fe_from_raw_csv.ipynb`
- `2 固定效应模型/fixed_effects_model.ipynb`
  - 原来并行存在的两份固定效应主 notebook。
  - 后续已整理为工作区中的 `fixed_effects_master_time.ipynb`、`fixed_effects_master_entity.ipynb`、`fixed_effects_master_both.ipynb`。

- `2 固定效应模型/legacy_outputs/FE_OUTPUT/*`
- `2 固定效应模型/legacy_outputs/outputs_lancet_fe/*`
  - 早期没有模型后缀的固定效应导出文件。
  - 为避免与当前 `time / entity / both` 三套结果混淆，已整体归档到 `legacy_outputs/`。

- `3 单固定效应模型/singal.ipynb`
  - 原始文件名版本已归档。
  - 当前工作区内已改名为 `0 初始待办记录.ipynb`。

- `3 单固定效应模型/outputs_single_species_fe/single_species_FE_long.csv`
- `3 单固定效应模型/outputs_single_species_fe/single_species_FE_long.xlsx`
  - 较早版本运行后留下的历史单菌种长表。
  - 当前现存主线代码明确导出的已是 `single_species_FE_long_FIXED.csv/.xlsx`。

## 说明

`bakeup` 是当前项目中的归档约定。后续如果还要“删除”文件，优先移动到这里，而不是直接移除。
