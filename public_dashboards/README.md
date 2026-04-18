# public_dashboards

这个目录是项目对外展示层，只存放适合公开访问的静态页面与发布快照，不承担研究过程中的中间结果整理职责。

## 这个目录和研究目录怎么分工

- `2 固定效应模型/`
  - 保留分析过程、原始构建产物和研究侧 dashboard。
- `4 贝叶斯分析/`
  - 保留贝叶斯结果与汇总表。
- `public_dashboards/`
  - 提供稳定访问入口、公开发布包和历史 release 快照。

## 当前主要 bundle

- `latest/`
  - 当前主线 FE exhaustive dashboard。
- `legacy-12models/`
  - 旧版 12 模型对照 dashboard。
- `bayes-analysis/`
  - 贝叶斯辅助分析 dashboard。
- `releases/`
  - 带时间戳的历史发布快照。
- `index.html`
  - 发布首页，聚合各 bundle 的入口。
- `manifest.json`
  - 首页和 bundle 元信息。
- `.nojekyll`
  - GitHub Pages 所需的保留文件，虽然是空文件，但不能删除。

## 常用命令

重新构建并发布：

```bash
python -X utf8 tools/deploy_public_dashboards.py
```

只发布已有 HTML，不重跑上游 builder：

```bash
python -X utf8 tools/deploy_public_dashboards.py --skip-build
```

保留更多历史 release：

```bash
python -X utf8 tools/deploy_public_dashboards.py --retain-releases 12
```

## 上游来源

- FE 主 dashboard：`tools/build_results_dashboard.py`
- 贝叶斯 dashboard：`tools/build_bayes_analysis_dashboard.py`
- 旧版 12 模型 dashboard：`2 固定效应模型/backups/legacy_12models_dashboard_20260417/process/build_results_dashboard_legacy_12models.py`

## 发布与维护提醒

- 建议通过 GitHub Actions 发布，而不是手工维护静态页面分支。
- 仓库中的页面默认使用相对链接，可直接部署到项目子路径。
- GitHub Pages 面向公开访问，复制进来的数据和页面应默认视为可公开内容。
- `latest/`、`legacy-12models/`、`bayes-analysis/` 会覆盖到当前稳定版本；需要保留历史状态时，应看 `releases/<timestamp>/`。
