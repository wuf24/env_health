# public_dashboards

这个目录是 dashboard 的公开发布层，用来给 GitHub Pages 提供稳定入口。

- 研究目录继续保留在 `2 固定效应模型/`
- 对外页面统一从 `public_dashboards/` 发布

## 在线地址

- GitHub 仓库：`https://github.com/wuf24/env_health`
- GitHub Pages 首页：`https://wuf24.github.io/env_health/`
- 最新版 dashboard：首页：`https://wuf24.github.io/env_health/latest/index.html`
- 最新版 Lancet 子页：`https://wuf24.github.io/env_health/latest/results_dashboard_lancet.html`
- 最新版矩阵页：`https://wuf24.github.io/env_health/latest/results_dashboard_matrix.html`
- 旧版 12 模型：首页：`https://wuf24.github.io/env_health/legacy-12models/index.html`
- 旧版 12 模型 Lancet 子页：`https://wuf24.github.io/env_health/legacy-12models/results_dashboard_legacy_12models_lancet.html`
- 旧版 12 模型矩阵页：`https://wuf24.github.io/env_health/legacy-12models/results_dashboard_legacy_12models_matrix.html`

## 当前发布结构

```text
public_dashboards/
  index.html
  manifest.json
  latest/
  legacy-12models/
  releases/<timestamp>/
```

- `latest/` 始终指向当前最新版
- `legacy-12models/` 始终指向旧版 12 模型备份
- `releases/<timestamp>/` 保留历史快照，方便回看

## 以后怎么更新

建议一直在本地安全分支 `public-main` 上更新，然后把它推到远程 `main`。

1. 切到安全发布分支：

```bash
git checkout public-main
```

2. 如果 dashboard 逻辑或结果有变，重新生成公开页面：

```bash
python -X utf8 tools/deploy_public_dashboards.py --retain-releases 12
```

如果只是重发当前已有 HTML，不重跑上游 builder：

```bash
python -X utf8 tools/deploy_public_dashboards.py --skip-build --retain-releases 12
```

3. 提交本次更新：

```bash
git add .
git commit -m "Update dashboards"
```

4. 推到 GitHub：

```bash
git push origin public-main:main
```

5. 等 GitHub Actions 跑完后，到这里查看：

- Actions：`https://github.com/wuf24/env_health/actions`
- Pages 首页：`https://wuf24.github.io/env_health/`

## 相关文件

- 公开站入口页：`public_dashboards/index.html`
- 自动部署脚本：`tools/deploy_public_dashboards.py`
- GitHub Pages workflow：`.github/workflows/deploy-github-pages.yml`
- latest 页面构建入口：`tools/build_results_dashboard.py`
- legacy 页面构建入口：`2 固定效应模型/backups/legacy_12models_dashboard_20260417/process/build_results_dashboard_legacy_12models.py`

## 安全提醒

- 不要把本地内部历史分支 `main` 直接推到 GitHub。
- 对外发布只推 `public-main:main`。
- 原始输入数据 `amr_rate.csv`、`climate_social_eco.csv` 和 `bakeup/.../raw_inputs/` 已加入忽略规则，不应进入公开仓库。
