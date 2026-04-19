# public_dashboards

这个目录是 dashboard 的长期发布层。

它和研究目录的职责分开：

- `2 固定效应模型/` 继续保存分析过程和原始构建产物。
- `public_dashboards/` 提供稳定链接、发布入口和历史归档。

## 当前结构

```text
public_dashboards/
  index.html
  manifest.json
  latest/
  legacy-12models/
  bayes-analysis/
  counterfactual-amr-agg/
  releases/20260419-170413/
```

## 维护命令

重新构建并发布：

```bash
python -X utf8 tools/deploy_public_dashboards.py
```

只发布已有 HTML，不重跑上游 builder：

```bash
python -X utf8 tools/deploy_public_dashboards.py --skip-build
```

在 GitHub Actions 里建议加上快照保留，例如：

```bash
python -X utf8 tools/deploy_public_dashboards.py --retain-releases 12
```

## 上游维护入口

- latest builder：`tools/build_results_dashboard.py`
- legacy-12models builder：`2 固定效应模型/backups/legacy_12models_dashboard_20260417/process/build_results_dashboard_legacy_12models.py`
- bayes-analysis builder：`tools/build_bayes_analysis_dashboard.py`
- counterfactual-amr-agg builder：`5 反事实推演/build_counterfactual_dashboard.py`

## GitHub Pages

- 推荐使用 GitHub Actions 发布，而不是手工提交生成后的静态文件分支。
- 工作流文件见：`.github/workflows/deploy-github-pages.yml`。
- 仓库设置路径：`Settings -> Pages -> Build and deployment -> Source -> GitHub Actions`。
- 项目页默认 URL 一般是：`https://<用户名>.github.io/<仓库名>/`。
- 这个站点内部已经统一使用相对链接，所以可以直接部署到项目子路径，不需要额外改 base URL。
- 如果仓库是私有仓库，GitHub Pages 是否可用取决于你的 GitHub 方案；公开仓库在 GitHub Free 下可用。
- GitHub Pages 站点是公开可访问的，不要把不希望公开的数据一起发布。

## 首次启用步骤

1. 把仓库推到 GitHub。
2. 进入仓库的 `Settings -> Pages`，把 Source 设为 `GitHub Actions`。
3. 推送到默认分支后，等待 `Deploy GitHub Pages` 工作流完成。
4. 首次成功后，在 Pages 设置页里复制公开 URL。

## 自定义域名

- GitHub 官方建议先验证域名，再把域名接到 Pages，避免域名接管风险。
- 如果你使用自定义 GitHub Actions workflow，需要在仓库 `Settings -> Pages` 里配置 Custom domain；仅靠仓库里的 `CNAME` 文件并不会自动新增或移除域名设置。
- 域名生效后，再勾选 `Enforce HTTPS`。

## 说明

- `latest/` 和 `legacy-12models/` 始终覆盖为最近一次部署后的稳定版本。
- `releases/<timestamp>/` 会保留部署当时的归档快照，方便对照和回滚。
- 每个 bundle 目录下都有 `metadata.json`，可用于排查来源和生成脚本。
