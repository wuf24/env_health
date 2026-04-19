# Code_health

这个仓库用于整理“Climate change amplifies the threat of antimicrobial resistance in China”这一组分析工作的主工作区，包含单因素探索、固定效应主分析、单菌种拆分、贝叶斯辅助分析、公开 dashboard 发布层，以及归档目录。

## 根目录结构

- `amr_rate.csv`
  - 原始 AMR 数据主表。
- `climate_social_eco.csv`
  - 气候、社会经济与环境代理变量主表。
- `1 单因素分析/`
  - 单因素探索、分类出图和最终展示图。
- `2 固定效应模型/`
  - 当前最接近论文主线的面板固定效应分析、变量组比较与 exhaustive 搜索结果。
- `3 单固定效应模型/`
  - 将 13 个 AMR 指标拆开后的单菌种固定效应分析。
- `4 贝叶斯分析/`
  - 镜像 FE 三种控制口径的贝叶斯模型网格与结果汇总。
- `5 反事实推演/`
  - 基于已筛选固定效应模型的 counterfactual simulation、全国年度/分省结果与图形输出。
- `public_dashboards/`
  - 对外发布的静态 dashboard 目录，含当前稳定入口与历史 release 快照。
- `tools/`
  - 各类脚本化构建器、发布脚本和 notebook 维护脚本。
- `bakeup/`
  - 从主工作区移出的历史文件、旧结果和运行产物归档区。

## 推荐阅读顺序

1. 先看 `2 固定效应模型/README.md`，了解当前论文主线与最稳的结果口径。
2. 再看 `1 单因素分析/README.md`，回溯变量筛选和展示图来源。
3. 需要检查异质性时，看 `3 单固定效应模型/README.md`。
4. 需要检验放大效应叙事时，看 `4 贝叶斯分析/README.md`。
5. 需要把主模型推进到反事实量化时，看 `5 反事实推演/README.md`。
6. 需要发布或核对静态页面时，看 `public_dashboards/README.md` 和 `tools/README.md`。

## 常用入口

- 变量空间穷举：`python -X utf8 tools/run_variable_space_exhaustive.py`
- 构建 FE dashboard：`python -X utf8 tools/build_results_dashboard.py`
- 生成贝叶斯候选清单：`python -X utf8 tools/build_bayes_candidate_models.py`
- 运行反事实推演：`python -X utf8 "5 反事实推演/run_counterfactual_analysis.py"`
- 发布公共 dashboard：`python -X utf8 tools/deploy_public_dashboards.py`

## 当前整理约定

- 明确无用且为空的日志文件可直接删除。
- 非空但不再需要的运行产物，不直接删除，而是移动到 `bakeup/cleanup_YYYYMMDD/`。
- 归档时尽量保留原始相对路径，方便追溯来源。
- `public_dashboards/.nojekyll` 这类“空但有用途”的文件需要保留。

## 使用注意

- 一部分旧 notebook 仍保留 `C:\Users\lunch\Downloads\...` 形式的数据路径；换机器前先检查输入路径。
- `public_dashboards/` 面向公开发布，不要把不希望公开的数据复制进去。
- `bakeup/` 是项目内约定的归档层，不是待清空的垃圾桶。
