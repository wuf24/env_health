# Code_health

这个仓库是课题 **Climate change amplifies the threat of antimicrobial resistance in China** 的当前主工作区。  
它不是单一脚本仓库，而是一条已经分层的分析流水线，包含：

- 变量探索与展示
- 固定效应主分析与系统穷举
- 单菌种异质性核对
- 贝叶斯模型网格
- 反事实推演
- 未来情景预测
- public dashboard 发布层
- 历史结果与运行产物归档层

## 当前主线一句话

如果只想先抓住当前仓库的主结论和主流程，可以这样理解：

1. `2 固定效应模型/` 先给出 Year FE 主线、人工变量组比较、exhaustive 搜索，以及当前统一的 `12` 模型归档。
2. `4 贝叶斯分析/` 用镜像 FE 三种控制口径的贝叶斯网格，检查主线和 `amplification` 交互项在不同口径下是否还能站住。
3. `5 反事实推演/` 基于统一 `12` 模型归档，对 `AMR_AGG` 做 observed vs counterfactual 对照。
4. `6 未来情景分析/` 使用同一套 `12` 模型归档，开展双 baseline 的 `2024-2050` 未来预测。
5. `public_dashboards/` 则把这些结果整理成可公开访问的稳定页面和 release 快照。

## 项目地图

### 数据根文件

- `amr_rate.csv`
  - AMR 原始主表，是固定效应、单菌种与部分 notebook 的共同输入。
- `climate_social_eco.csv`
  - 气候、社会经济、卫生、污染、畜牧等协变量主表。

### 分析目录

- `1 单因素分析/`
  - 单因素关系摸底、分类图和论文展示图入口。
- `2 固定效应模型/`
  - 当前主实证中心，包含旧主线 notebook、变量组比较、系统穷举、`strict_top8_archive/` 和 `model_archive_12/`。
- `3 单固定效应模型/`
  - 13 个单独 AMR 指标的固定效应模型与横向比较表。
- `4 贝叶斯分析/`
  - 镜像 `year_only / province_only / province_year` 三种 FE 口径的贝叶斯模型网格。
- `5 反事实推演/`
  - 基于固定效应筛选结果的 counterfactual simulation 和写作说明。
- `6 未来情景分析/`
  - `2024-2050` 未来情景预测、双 baseline 对比、地区和省级图件。

### 发布与归档目录

- `public_dashboards/`
  - 对外发布层，包含稳定 bundle、历史 release 快照和 `manifest.json`。
- `tools/`
  - 各类 builder、归档器、部署脚本、notebook 维护脚本。
- `bakeup/`
  - 项目内约定的归档层，用于保存旧 notebook、旧结果和清理出的运行产物。
- `.tmp_amr_climate_repo/`
  - 从外部仓库拉回的临时参考镜像，不属于当前 Python 主线工作区。

## 当前最重要的共享结果

如果你只想先确认“现在全仓库共同依赖哪几份结果”，优先看下面这些文件：

- `2 固定效应模型/results/exhaustive_model_summary.csv`
  - 系统穷举主汇总。
- `2 固定效应模型/results/strict_top8_archive/strict_top8_models.csv`
  - 严筛强相关 `8` 模型归档。
- `2 固定效应模型/results/model_archive_12/selected_models.csv`
  - 当前统一 `12` 模型归档。
  - 结构上是 `4` 个手选 Year FE 模型 + `8` 个 strict top-8 模型。
- `4 贝叶斯分析/results/bayes_candidate_models.csv`
  - 贝叶斯候选清单。
- `4 贝叶斯分析/results/model_summaries/focus_primary_summary.csv`
  - 贝叶斯主结果短表。
- `5 反事实推演/results/AMR_AGG/run_metadata.json`
  - 反事实运行元数据。
- `6 未来情景分析/results/run_metadata.json`
  - 未来情景运行元数据。
- `public_dashboards/manifest.json`
  - public 发布层的 bundle 清单和 release 信息。

## 当前 end-to-end 工作流

推荐把整个项目理解成下面这条链：

1. 在 `1 单因素分析/` 看变量与 AMR 的单因素关系，明确候选变量池和展示口径。
2. 在 `2 固定效应模型/` 做 Year FE / Province FE / Two-way FE 对比、变量组比较和 exhaustive 搜索。
3. 由 `tools/build_strict_top8_archive.py` 和 `tools/build_model_archive_12.py` 整理出统一模型归档。
4. 在 `4 贝叶斯分析/` 基于候选清单跑 6 个贝叶斯变体，检查主效应与 `R1xday × AMC` 的稳定性。
5. 在 `5 反事实推演/` 基于统一 `12` 模型归档生成 counterfactual 结果、图件和写作说明。
6. 在 `6 未来情景分析/` 使用同一套模型归档做双 baseline 的未来情景预测。
7. 最后由 `tools/deploy_public_dashboards.py` 把固定效应、贝叶斯、反事实、未来情景和最终决策页发布到 `public_dashboards/`。

## 推荐阅读顺序

### 如果你是第一次接手这个仓库

1. 先看 `2 固定效应模型/README.md`
   - 这是当前主结果和模型筛选逻辑的中心。
2. 再看 `4 贝叶斯分析/README.md`
   - 这里决定题目里 `amplifies` 这层叙事目前证据有多强。
3. 然后看 `5 反事实推演/README.md`
   - 了解筛选后的模型如何被推进到 counterfactual 量化。
4. 再看 `6 未来情景分析/README.md`
   - 了解统一模型归档如何被用于 `2024-2050` 预测。
5. 需要回溯变量来源时，再看 `1 单因素分析/README.md` 和 `3 单固定效应模型/README.md`。
6. 需要发布或核对页面时，再看 `public_dashboards/README.md` 与 `tools/README.md`。

### 如果你只想快速确认“现在该引用什么”

- 主筛选和模型归档：`2 固定效应模型/results/model_archive_12/selected_models.csv`
- 贝叶斯主短表：`4 贝叶斯分析/results/model_summaries/focus_primary_summary.csv`
- 反事实主入口：`5 反事实推演/results/AMR_AGG/counterfactual_results_dashboard.html`
- 未来情景主入口：`6 未来情景分析/index.html`
- 温度专页入口：`6 未来情景分析/temperature_dashboard.html`
- public bundle 清单：`public_dashboards/manifest.json`

## 常用命令

### 固定效应与归档

- 变量空间穷举：`python -X utf8 tools/run_variable_space_exhaustive.py`
- 生成 strict top-8：`python -X utf8 tools/build_strict_top8_archive.py`
- 生成统一 12 模型归档：`python -X utf8 tools/build_model_archive_12.py`
- 构建 FE dashboard：`python -X utf8 tools/build_results_dashboard.py`

### 贝叶斯

- 生成贝叶斯候选清单：`python -X utf8 tools/build_bayes_candidate_models.py`
- 检查默认网格：`python -X utf8 "4 贝叶斯分析/run_bayes_selected_models.py" --dry-run`
- 运行默认网格：`python -X utf8 "4 贝叶斯分析/run_bayes_selected_models.py" --draws 800 --tune 800 --chains 4`

### 反事实与未来情景

- 运行反事实推演：`python -X utf8 "5 反事实推演/run_counterfactual_analysis.py"`
- 构建反事实 dashboard：`python -X utf8 "5 反事实推演/build_counterfactual_dashboard.py"`
- 运行未来情景预测：`python -X utf8 ".\6 未来情景分析\scripts\run_future_scenario_projection.py"`
- 构建独立温度专页：`python -X utf8 ".\tools\build_temperature_dashboard.py"`

### public dashboards

- 构建并发布所有 public bundles：`python -X utf8 tools/deploy_public_dashboards.py`
- 仅部署已有 bundle：`python -X utf8 tools/deploy_public_dashboards.py --skip-build`

## 当前整理约定

- 明确无用且为空的日志文件可直接删除。
- 非空但不再需要的运行产物，不直接删除，而是优先移动到 `bakeup/cleanup_YYYYMMDD/`。
- 归档时尽量保留原始相对路径，方便追溯来源。
- `public_dashboards/.nojekyll` 这类“空但有用途”的文件必须保留。
- 与当前主线共享的权威结果，优先保存在各模块 `results/` 下，而不是散落到根目录。

## 使用注意

- 一部分旧 notebook 仍保留 `C:\Users\lunch\Downloads\...` 形式的数据路径；换机器前先检查输入路径。
- `public_dashboards/` 面向公开发布，不要把不希望公开的数据复制进去。
- `bakeup/` 是项目内约定的归档层，不是待清空的垃圾桶。
- `.tmp_amr_climate_repo/` 是外部参考镜像，不要把它误当作当前主线的可复现实验入口。
