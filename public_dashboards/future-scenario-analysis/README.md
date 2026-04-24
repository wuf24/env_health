# 6 未来情景分析

这个目录保存当前主线的未来情景预测流程、结果页面、输入快照和配套说明。  
它对应的是：

> 固定效应模型筛选 -> 统一 12 模型归档 -> 未来路径替换 -> 全国 / 地区 / 省级汇总

这一条完整流水线。

与早期版本不同，当前主线已经不再额外套 `AMR_AGG_RAW/` 作为外层目录，而是直接使用扁平的结果结构。

## 当前整理原则

- `results/` 只放当前主线输出；
- `index.html` 是本模块的人读入口；
- 旧版、重复版和历史结构统一放到 `bakeup/`；
- `bakeup` 继续保留这个拼写，不再改名；
- public 副本 `public_dashboards/future-scenario-analysis/README.md` 当前应与本 README 保持同步。

## 先看哪里

如果你是第一次回来接这个模块，推荐按下面顺序看：

1. 总览页面：`index.html`
2. 本地温度专页：`temperature_dashboard.html`
3. baseline 口径说明：`docs/两种baseline版本详解.md`
4. 当前运行元数据：`results/run_metadata.json`
5. baseline 对照总结：`results/baseline_mode_compare/baseline_mode_comparison.md`
6. 两套主结果：
   - `results/lancet_ets/projection_outputs/future_scenario_projection_panel.csv`
   - `results/x_driven/projection_outputs/future_scenario_projection_panel.csv`

## 一页看懂当前口径

| 项目 | 当前设置 | 说明 |
| --- | --- | --- |
| 预测对象 | `AMR_AGG_RAW` | 13 个 AMR 指标原始百分比的行均值 |
| 预测年份 | `2024-2050` | 见 `results/run_metadata.json` |
| baseline 模式 | `lancet_ets`、`x_driven` | 只差 baseline 生成方式，回归系数和已激活的未来协变量路径一致 |
| 模型来源 | 统一 `12` 个归档模型 | 与固定效应、贝叶斯、反事实模块保持同一套模型归档 |
| 已接入 SSP 替换的未来协变量 | `R1xday` + 温度通道（`TA` / `省平均气温`） | 温度已正式进入主流程；模型按各自温度变量自动读取对应 SSP 路径 |
| 温度输入口径 | `TA_future_panel.csv` + `ssp_province_mean_tas_panel.csv` | `TA` 走 anomaly 路径；不含 `TA` 但含 `省平均气温` 的模型走重处理后的 SSP 省平均气温 |
| 温度专页 | `temperature_dashboard.html` | 独立于 `index.html` 的本地页面，图件先生成到本地 PNG 再在 HTML 中引用 |
| 空间覆盖 | `31` 个省级单元 | 默认不含香港、澳门、台湾 |
| 全国汇总口径 | 先省级预测，再做算术平均 | 不是先构造全国协变量再代模型 |

## 当前主线到底在做什么

可以把这套流程理解成 4 步：

1. 从 `2 固定效应模型/results/model_archive_12/selected_models.csv` 读取统一 `12` 模型归档；
2. 读取历史回归系数、未来 `R1xday` 与温度情景路径，以及 baseline 设定；
3. 在省级层面生成未来 `AMR` 预测，并为温度相关模型记录 `temperature_baseline / temperature_scenario / temperature_delta`；
4. 再把省级结果汇总成全国、七大区、省级图、双情景对照图，以及独立的温度专页。

当前统一使用的 `12` 个模型角色见：

- `results/model_screening/selected_models_snapshot.csv`

其中包括：

- 原始主线 `4` 模型：
  - `main_model`
  - `robust_low_vif`
  - `robust_systematic`
  - `robust_systematic_2`
- 严筛扩展 `8` 模型：
  - `strict_main_model`
  - `strict_top_02` 到 `strict_top_08`

这意味着未来情景分析已经不再只对应单个“主模型”，而是和贝叶斯分析、反事实推演共享一套统一的模型归档。

## 两种 baseline 的区别

详细说明见：

- `docs/两种baseline版本详解.md`

这里先抓核心：

### `lancet_ets`

- 让结果变量 `AMR` 自己按历史趋势做 ETS 延伸，作为 baseline；
- 更接近 Lancet 2023 Figure 5 那种 “baseline scenario continued at current rates” 的写法。

### `x_driven`

- 让未来协变量路径决定 baseline，再代回历史回归结构；
- 更强调未来气候/协变量路径本身的驱动作用。

### 两种 baseline 的共同点

- 使用同一套历史回归系数；
- 使用同一套未来激活协变量路径（当前包括 `R1xday` 和温度通道）；
- 使用同一套 `12` 模型归档。

所以经常会看到：

- `scenario_pred_mean` 的水平不同；
- 但 `delta_vs_baseline` 的情景增量非常接近。

## 当前目录结构

```text
6 未来情景分析/
├─ README.md
├─ index.html
├─ temperature_dashboard.html
├─ data_raw/
│  ├─ cckp_rx1day/
│  ├─ cckp_rx1day_timeseries/
│  └─ cckp_tas_timeseries/
├─ data_processed/
├─ docs/
├─ logs/
├─ results/
│  ├─ common_inputs/
│  ├─ model_screening/
│  ├─ baseline_mode_compare/
│  ├─ lancet_ets/
│  ├─ temperature_dashboard_figures/
│  ├─ x_driven/
│  └─ run_metadata.json
├─ scripts/
└─ bakeup/
```

## 数据与输入文件说明

### 1. 历史模型输入

历史协变量主表是根目录：

- `../climate_social_eco.csv`

其中历史 `TA（°C）` 的定义是：

```text
TA_obs(i,t) = 省观测年均气温(i,t) - 该省1991-2020观测平均气温(i)
```

这套历史温度异常值的外部复核来源是：

- `E:/EnvHelth/省级平均气温统计_逐年.xlsx`

### 2. 模型筛选快照

未来主流程运行时会先读取：

- `results/model_screening/future_projection_coefficients.csv`
- `results/model_screening/selected_models_snapshot.csv`
- `results/model_screening/covariate_ets_methods_snapshot.csv`

它们分别记录：

- 当前使用的回归系数；
- 当前使用的 `12` 模型角色；
- 各协变量的 ETS / baseline 处理方法。

### 3. CCKP `R1xday` 数据

当前已经正式接入主流程的未来气候驱动变量是 `R1xday`。

常用文件包括：

- `data_processed/cckp_rx1day_timeseries_panel.csv`
- `data_processed/province_to_region_7zones.csv`
- `results/common_inputs/rx1day_future_aligned.csv`
- `results/common_inputs/rx1day_bias_correction.csv`

### 4. CCKP `tas` 与未来 `TA`

温度这条线现在已经正式并入主流程，但需要区分两种代理路径：

- 含 `TA（°C）` 的模型，走未来 `TA` anomaly 路径；
- 不含 `TA` 但含 `省平均气温` 的模型，走从 `data_raw` 再处理出来的 SSP 省平均气温绝对温度路径。

关键文件包括：

- `data_processed/cckp_tas_timeseries_panel.csv`
- `data_processed/cckp_tas_timeseries_historical_panel.csv`
- `data_processed/cckp_tas_timeseries_combined_panel.csv`
- `data_processed/cckp_tas_reference_1991_2020.csv`
- `data_processed/TA_future_panel.csv`
- `data_processed/ssp_province_mean_tas_panel.csv`
- `results/common_inputs/ta_future_panel.csv`
- `results/common_inputs/province_tas_future_aligned.csv`
- `results/common_inputs/province_tas_bias_correction.csv`

`TA_future_panel.csv` 的含义不是未来绝对温度，而是按 CMIP6 自身参考期计算的未来温度异常值：

```text
tas_ref_1991_2020(i,s,stat)
= mean[ historical(i,1991:2014,stat) + same_scenario(i,2015:2020,s,stat) ]

TA_future(i,t,s,stat)
= tas_future(i,t,s,stat) - tas_ref_1991_2020(i,s,stat)
```

这样处理是因为：

- CCKP 历史 `tas` 只到 `2014`；
- CCKP 未来 `tas` 从 `2015` 开始；
- 若要得到统一口径的 `1991-2020` 参考期，必须把这两段拼起来。

对不含 `TA` 但含 `省平均气温` 的模型，主流程不会直接拿 `TA_future_panel.csv` 代替，而是先从 `data_raw/cckp_tas_timeseries/` 重处理出 `ssp_province_mean_tas_panel.csv`，再做历史口径的 bias correction / alignment，实际投影读取的是 `results/common_inputs/province_tas_future_aligned.csv`。

当前温度输入的覆盖范围是：

- `31` 个省级单元；
- `2024-2100`；
- `ssp119 / ssp126 / ssp245 / ssp370 / ssp585`；
- `median / p10 / p90`。

另外，若某个模型包含的是 `主要城市平均气温`，当前并不会强行映射到省级 SSP 温度路径；这类模型不会自动获得这条新的省级温度替换通道。

## 当前最容易混淆的几件事

### 1. 温度已经接进主流程，但不同模型用的不是同一条温度路径

当前代码主线里，正式接入 SSP 替换的温度通道分成两类：

- 含 `TA` 的模型读取 `results/common_inputs/ta_future_panel.csv`
- 含 `省平均气温` 的模型读取 `results/common_inputs/province_tas_future_aligned.csv`

因此，不能把“温度已接入主流程”简单理解成所有模型都统一替换成 `TA_future_panel.csv`。

### 2. 历史 `TA` 和未来 `TA` 不是同一来源体系

- 历史 `TA（°C）`：观测基准 anomaly
- 未来 `TA_future`：CMIP6 `tas` 自参考 anomaly

它们现在已经并存于主流程，但在图上不一定天然首尾无缝。温度专页因此同时提供 `Raw SSP` 和 `2023 Anchored` 两种展示模式；后者只用于视觉衔接，不改预测输入。

### 3. `省平均气温` 做了 bias correction，不等于 2023-2024 必然无缝对上

`results/common_inputs/province_tas_future_aligned.csv` 的对齐目标是让历史重叠期口径一致，而不是强制让 `2023` 的历史观测点和 `2024` 的未来路径端点完全重合。

### 4. 全国结果是“先省后国”，不是“先全国后代模”

当前口径是：

```text
先得到 AMR_scenario_it
再计算 AMR_scenario_t = (1 / N_t) * Σ_i AMR_scenario_it
```

因此全国曲线是省级预测的算术平均，不是全国协变量先聚合后的回归结果。

### 5. 当前主线已经不是单模型，而是统一 `12` 模型归档

这一点在写方法或解释敏感性分析时很重要。  
现在未来情景分析读取的是统一归档的 `12` 个模型角色，而不是只盯着 `main_model` 一条线。

## 当前最值得直接看的结果文件

### 1. 全国主结果

如果只想先看主线结论，优先看：

- `results/lancet_ets/projection_outputs/future_scenario_projection_panel.csv`
- `results/lancet_ets/projection_notes.md`
- `results/x_driven/projection_outputs/future_scenario_projection_panel.csv`
- `results/x_driven/projection_notes.md`

`future_scenario_projection_panel.csv` 是最核心的数据表，里面至少包含：

- 年份
- baseline mode
- model role
- SSP 情景
- 全国均值预测
- 相对 baseline 的变化量

### 2. 温度专页与温度输入对照

如果想单独看温度，而不是和 `R1xday` 共用叙事，优先看：

- `temperature_dashboard.html`
- `results/temperature_dashboard_figures/`
- `results/common_inputs/ta_future_panel.csv`
- `results/common_inputs/province_tas_future_aligned.csv`
- `results/common_inputs/province_tas_bias_correction.csv`

这套页面当前采用浅色学术风格，图件先落本地 PNG，再由 HTML 引用；不确定性表达统一用 `p10-p90` ribbon / whisker。

### 3. baseline 对照结果

如果想看“两种 baseline 究竟差在哪”，直接看：

- `results/baseline_mode_compare/national_yearly_compare.csv`
- `results/baseline_mode_compare/main_model_2050_compare.csv`
- `results/baseline_mode_compare/model_role_2050_compare.csv`
- `results/baseline_mode_compare/scenario_summary_2050_compare.csv`
- `results/baseline_mode_compare/regional_summary_2050_compare.csv`
- `results/baseline_mode_compare/baseline_mode_comparison.md`

同时，本目录下还保留了：

- `dual_scenario_run_metadata_ssp119_vs_ssp585.json`
- `dual_scenario_run_metadata_ssp119_vs_ssp585_delta.json`
- `provincial_run_metadata.json`
- `regional_run_metadata.json`

这些元数据文件可以帮助你回溯某次图件或比较结果是按什么配置生成的。

### 4. 地区结果

七大区分析常用文件：

- `data_processed/province_to_region_7zones.csv`
- `results/lancet_ets/regional_outputs/regional_yearly.csv`
- `results/lancet_ets/regional_outputs/region_summary_2050.csv`
- `results/x_driven/regional_outputs/regional_yearly.csv`
- `results/x_driven/regional_outputs/region_summary_2050.csv`

### 5. 省级图和双情景图

常用图件包括：

- `results/lancet_ets/provincial_figures/provincial_future_scenario_panel.png`
- `results/x_driven/provincial_figures/provincial_future_scenario_panel.png`
- `results/lancet_ets/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585_delta.png`
- `results/x_driven/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585_delta.png`

### 6. 逐模型详细解读

当前结果目录里已经补上了逐模型说明：

- `results/lancet_ets/model_role_detail_summary.csv`
- `results/lancet_ets/model_role_detailed_analysis.md`
- `results/x_driven/model_role_detail_summary.csv`
- `results/x_driven/model_role_detailed_analysis.md`

这意味着未来情景模块现在不仅能说“主模型如何”，还能说明“不同模型角色在未来路径下分别如何”。

## 脚本结构

### 数据准备脚本

- `scripts/download_cckp_rx1day.py`
- `scripts/check_cckp_files.py`
- `scripts/merge_cckp_rx1day.py`
- `scripts/download_cckp_rx1day_timeseries.py`
- `scripts/check_cckp_rx1day_timeseries_files.py`
- `scripts/merge_cckp_rx1day_timeseries.py`
- `scripts/build_cckp_tas_future_panel.py`
- `scripts/validate_cckp_rx1day_timeseries_url.py`

### 预测与出图脚本

- `scripts/run_future_scenario_projection.py`
  - 全国主流程
- `scripts/run_regional_future_figure5.py`
  - 七大区结果与地区图
- `scripts/run_provincial_future_figure.py`
  - 省级图
- `scripts/run_dual_scenario_compare_figure.py`
  - 双情景对照图

### 页面构建脚本

- `tools/build_temperature_dashboard.py`
  - 生成独立的 `temperature_dashboard.html` 与 `results/temperature_dashboard_figures/*.png`
  - 只更新温度专页，不覆盖 `index.html`

### 公共配置与公共函数

- `scripts/config_future_scenario_projection.py`
- `scripts/future_scenario_common.py`
- `scripts/cckp_rx1day_common.py`
- `scripts/cckp_rx1day_timeseries_common.py`

## 推荐运行顺序

从项目根目录运行。

### 1. 如需重建未来输入

`R1xday` 逐年面板：

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\download_cckp_rx1day_timeseries.py"
python -X utf8 ".\\6 未来情景分析\\scripts\\merge_cckp_rx1day_timeseries.py"
```

未来 `TA` 面板：

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\build_cckp_tas_future_panel.py"
```

如需强制重新下载 `tas` 原始 JSON：

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\build_cckp_tas_future_panel.py" --force-download
```

### 2. 全国主流程

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\run_future_scenario_projection.py"
```

只跑一种 baseline：

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\run_future_scenario_projection.py" --baseline-modes lancet_ets
python -X utf8 ".\\6 未来情景分析\\scripts\\run_future_scenario_projection.py" --baseline-modes x_driven
```

### 3. 温度专页

在全国主流程之后，如果要刷新独立的温度页面：

```bash
python -X utf8 ".\\tools\\build_temperature_dashboard.py"
```

### 4. 地区汇总和图

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\run_regional_future_figure5.py"
```

### 5. 省级图

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\run_provincial_future_figure.py"
```

### 6. 双情景对比图

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\run_dual_scenario_compare_figure.py"
```

如果要换情景对：

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\run_dual_scenario_compare_figure.py" --scenario-pair ssp126 ssp370
```

如果需要旧的绝对值视图，而不是 `delta_vs_baseline`：

```bash
python -X utf8 ".\\6 未来情景分析\\scripts\\run_dual_scenario_compare_figure.py" --value-mode predicted
```

## 与 public dashboard 的关系

当前 public 发布副本位于：

- `public_dashboards/future-scenario-analysis/`

该 bundle 会同步：

- `index.html`
- `results/`
- `docs/`
- `README.md`
- `data_processed/province_to_region_7zones.csv`

当前独立温度专页 `temperature_dashboard.html` 与 `results/temperature_dashboard_figures/` 仍是模块工作目录下的本地页面，尚未单独同步到 `public_dashboards/future-scenario-analysis/`。

因此，如果你是更新方法说明，源文件应优先改这里的 README，再同步到 public 副本；如果你是更新温度专页，还需要额外决定是否要把这套本地页面单独发布到 public。

## 归档说明

`bakeup/` 里放的是已经退出当前主线的旧内容，包括：

- 旧版 `AMR_AGG`
- 以前的 `results/AMR_AGG_RAW/` 嵌套结构
- 旧根目录重复输出
- 旧日志
- `__pycache__`

也就是说，下面这些都不是当前应优先引用的主线结果：

- `results/AMR_AGG_RAW/`
- `bakeup/results_legacy/AMR_AGG/`
- `bakeup/results_legacy/AMR_AGG_RAW_root_legacy/`
- `bakeup/results_legacy/AMR_AGG_RAW_nested_outcome_dir/`

## 一句话记住这个目录

这里负责把统一 `12` 模型归档推进成可比较的未来情景预测；当前真正接入主流程的未来气候变量已经包括 `R1xday` 和温度通道（`TA` / `省平均气温`），并且另有一个不改 `index.html` 的独立温度专页 `temperature_dashboard.html`。
