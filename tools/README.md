# tools

这个目录存放仓库中可复用的脚本化工具，主要负责三类工作：结果整理、dashboard 构建发布、以及 notebook 主线维护。

## 脚本总览

| 脚本 | 作用 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `run_variable_space_exhaustive.py` | 在科学约束下系统搜索 FE 变量组合 | 根目录两份 CSV | `2 固定效应模型/results/` 下的 exhaustive 结果表 |
| `build_results_dashboard.py` | 用 FE 结果生成三页 HTML dashboard | `2 固定效应模型/results/` | `2 固定效应模型/results_dashboard*.html` |
| `build_bayes_candidate_models.py` | 从 FE 排名里筛选贝叶斯候选组合 | FE ranking 与 catalog | `4 贝叶斯分析/results/bayes_candidate_models.csv` |
| `build_bayes_analysis_dashboard.py` | 用贝叶斯汇总表生成公开页面 | `4 贝叶斯分析/results/model_summaries/` | `public_dashboards/bayes-analysis/` |
| `deploy_public_dashboards.py` | 统一重建并发布 public dashboards | FE / Bayes builder 产物 | `public_dashboards/` 与 `public_dashboards/releases/` |
| `update_fe_notebooks.py` | 批量更新三份 FE 主 notebook 的模板结构 | `2 固定效应模型/*.ipynb` | 覆盖写回 notebook |
| `build_variable_group_schemes_notebook.py` | 脚本化生成 `variable_group_schemes.ipynb` | 脚本内模板 | `2 固定效应模型/variable_group_schemes.ipynb` |
| `variable_group_probe.py` | 快速评估几套变量组的表现 | 根目录两份 CSV | 终端输出 / 快速诊断结果 |

## 常用流程

1. 更新或重跑固定效应结果后，先运行 `run_variable_space_exhaustive.py`。
2. 需要查看 FE 页面时，运行 `build_results_dashboard.py`。
3. 准备贝叶斯模型池时，运行 `build_bayes_candidate_models.py`。
4. 贝叶斯结果更新后，运行 `build_bayes_analysis_dashboard.py`。
5. 最后统一发布时，运行 `deploy_public_dashboards.py`。

## 依赖

- 面板回归相关：`pandas`、`numpy`、`linearmodels`、`statsmodels`
- dashboard 相关：`pandas`
- notebook 维护相关：`nbformat`
- 公开页面打包相关：标准库为主，附加依赖见 `requirements-dashboard.txt`

## 维护建议

- 这些脚本大多默认从仓库根目录读取 `amr_rate.csv` 与 `climate_social_eco.csv`，重命名或移动数据文件前先统一检查。
- 与发布相关的脚本会写入 `public_dashboards/`，运行前确认目录中的内容可以公开。
- `__pycache__/` 属于运行缓存，不属于需要长期保存的项目资产。
