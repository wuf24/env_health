# tools

这个目录存放仓库里的可复用脚本化工具，当前主要承担四类工作：

1. 固定效应结果整理与模型筛选
2. 模型归档构建
3. dashboard 构建与 public 发布
4. notebook 模板维护与快速诊断

## 先记住一个使用原则

如果你只是想“跑分析”，优先去各模块目录执行模块脚本；  
如果你想“整理结果、构建归档、生成页面或发布 public bundle”，优先回到 `tools/` 看这里的 builder。

## 当前脚本分组

### 1. 固定效应搜索与筛选

| 脚本 | 作用 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `run_variable_space_exhaustive.py` | 在科学约束下系统搜索 FE 变量组合 | 根目录两份 CSV | `2 固定效应模型/results/` 下的 exhaustive 系列表 |
| `variable_group_probe.py` | 快速评估少量变量组表现 | 根目录两份 CSV | 终端输出 / 快速诊断 |

### 2. 模型归档构建

| 脚本 | 作用 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `build_strict_top8_archive.py` | 从 exhaustive 结果中筛出严筛 `8` 模型 | FE dashboard payload / exhaustive summary | `2 固定效应模型/results/strict_top8_archive/` |
| `build_model_archive_12.py` | 生成统一 `12` 模型归档 | exhaustive summary、Bayes 候选、strict top-8 | `2 固定效应模型/results/model_archive_12/selected_models.csv` |
| `build_bayes_candidate_models.py` | 从 FE 排名里筛选贝叶斯候选组合 | FE ranking 与 catalog | `4 贝叶斯分析/results/bayes_candidate_models.csv` |

### 3. 页面构建与发布

| 脚本 | 作用 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `build_results_dashboard.py` | 生成 FE exhaustive 三页 HTML dashboard | `2 固定效应模型/results/` | `2 固定效应模型/results_dashboard*.html` |
| `build_bayes_analysis_dashboard_v2.py` | 生成当前使用的 Bayes dashboard | `4 贝叶斯分析/results/model_summaries/` | `4 贝叶斯分析/index.html` 与 `public_dashboards/bayes-analysis/` |
| `build_future_scenario_dashboard.py` | 提供未来情景 dashboard 的数据读取与交互页基础逻辑 | `6 未来情景分析/results/` | `6 未来情景分析/index.html` 的交互版基础 |
| `build_future_scenario_dashboard_report.py` | 生成当前 public 使用的未来情景叙事页（含模型下拉切换） | `6 未来情景分析/results/` | `6 未来情景分析/index.html` 与 `public_dashboards/future-scenario-analysis/` |
| `build_variable_group_deep_dive_dashboard.py` | 生成最终模型决策页 | FE / Bayes / 反事实 / 未来情景结果 | `public_dashboards/variable-group-deep-dive/` |
| `deploy_public_dashboards.py` | 统一重建并发布所有 public bundles | 各 builder 产物 | `public_dashboards/` 与 `public_dashboards/releases/` |

### 4. notebook 与模板维护

| 脚本 | 作用 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `update_fe_notebooks.py` | 批量更新三份 FE 主 notebook 模板结构 | `2 固定效应模型/*.ipynb` | 覆盖写回 notebook |
| `build_variable_group_schemes_notebook.py` | 脚本化生成 `variable_group_schemes.ipynb` | 脚本内模板 | `2 固定效应模型/variable_group_schemes.ipynb` |

## 当前推荐工作流

### 如果你要更新 FE 主筛选链

1. 运行 `run_variable_space_exhaustive.py`
2. 运行 `build_strict_top8_archive.py`
3. 运行 `build_model_archive_12.py`
4. 运行 `build_results_dashboard.py`
5. 如需推进贝叶斯，再运行 `build_bayes_candidate_models.py`

### 如果你要更新 public 页面

1. 确认各模块源目录结果已经更新
2. 先单独运行需要的 builder
3. 最后运行 `deploy_public_dashboards.py`

### 如果你只是要做一次完整 public 同步

```bash
python -X utf8 tools/deploy_public_dashboards.py
```

## 最常用的几个命令

### 变量空间穷举

```bash
python -X utf8 tools/run_variable_space_exhaustive.py
```

### 生成 strict top-8

```bash
python -X utf8 tools/build_strict_top8_archive.py
```

### 生成统一 12 模型归档

```bash
python -X utf8 tools/build_model_archive_12.py
```

### 构建 FE dashboard

```bash
python -X utf8 tools/build_results_dashboard.py
```

### 构建 Bayes public 页面

```bash
python -X utf8 tools/build_bayes_analysis_dashboard_v2.py
```

### 部署所有 public bundles

```bash
python -X utf8 tools/deploy_public_dashboards.py
```

## 旧脚本与当前默认脚本

当前有一个需要特别注意的地方：

- `build_bayes_analysis_dashboard.py`
  - 属于较早的 Bayes 页面脚本；
- `build_bayes_analysis_dashboard_v2.py`
  - 是当前 public 发布层实际使用的版本。

因此如果你是要更新当前 Bayes public 页面，优先用 `v2`。

## 这些脚本和各模块的关系

- `2 固定效应模型/`
  - 主要依赖 `run_variable_space_exhaustive.py`、`build_strict_top8_archive.py`、`build_model_archive_12.py`、`build_results_dashboard.py`
- `4 贝叶斯分析/`
  - 主要依赖 `build_bayes_candidate_models.py`、`build_bayes_analysis_dashboard_v2.py`
- `6 未来情景分析/`
  - public 层发布时主要依赖 `build_future_scenario_dashboard_report.py`
- `public_dashboards/`
  - 最终统一由 `deploy_public_dashboards.py` 收口

## 依赖

- 面板回归相关：
  - `pandas`
  - `numpy`
  - `linearmodels`
  - `statsmodels`
- dashboard 相关：
  - `pandas`
- notebook 维护相关：
  - `nbformat`
- 公开页面打包相关：
  - 标准库为主
  - 额外依赖见 `requirements-dashboard.txt`

## 维护建议

- 这些脚本大多默认从仓库根目录读取 `amr_rate.csv` 与 `climate_social_eco.csv`，重命名或移动数据文件前先统一检查。
- 与发布相关的脚本会写入 `public_dashboards/`，运行前确认目录中的内容可以公开。
- `deploy_public_dashboards.py` 会覆盖稳定 bundle，并写入 `releases/` 快照，运行前确认你是否真的要刷新发布层。
- `__pycache__/` 属于运行缓存，不属于需要长期保存的项目资产。
