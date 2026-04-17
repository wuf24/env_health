import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
from pathlib import Path


NOTEBOOK_PATH = Path(r"e:\MALA\Code_health\2 固定效应模型\variable_group_schemes.ipynb")


cells = [
    new_markdown_cell(
        """# 变量组方案 × 固定效应组合比较

这个 notebook 用于系统比较：

- 4 套解释变量组
- 3 种固定效应组合
  - `Province = No, Year = Yes`
  - `Province = Yes, Year = No`
  - `Province = Yes, Year = Yes`

统一口径：

- 因变量：`AMR_AGG_z`
- 自变量：按省份中位数 + 全局中位数补缺，再做 z-score 进入回归
- 标准误：按省份聚类稳健 SE
- 目标：在**保留 `R1xday` 与 `抗菌药物使用强度`**的前提下，比较不同变量组和不同固定方式的表现

本 notebook 会输出：

- 长表形式的模型汇总表
- 横向对比总表
- 系数明细表
- 原始尺度 / 标准化后 VIF 对比表
- 每个模型的 Lancet 风格结果表

## R-squared、R-squared (Overall)、R² (within) 的关系

- `R-squared`
  - `PanelOLS` 主结果里报告的模型拟合优度，是当前估计模型对应的“主 R²”。
- `R-squared (Overall)`
  - 忽略固定效应时，因变量与解释变量整体拟合程度的参考指标。
  - 更接近“省际差异 + 省内变化一起看”的整体解释度。
- `R² (within)`
  - 关注在固定效应处理之后，模型对“组内变化”解释得怎么样。
  - 在固定效应模型里通常最严格，也最容易偏低甚至为负。

这三个指标不是互相替代关系，而是从不同角度看同一个模型：

- `R-squared`：主结果摘要
- `R-squared (Overall)`：整体层面参考
- `R² (within)`：固定效应识别层面的核心参考

因此后面的 Lancet 表会把这 3 个指标全部列出来。"""
    ),
    new_code_cell(
        """import os
import re
import warnings

import numpy as np
import pandas as pd
from IPython.display import Markdown, display
from linearmodels.panel import PanelOLS
from statsmodels.stats.outliers_influence import variance_inflation_factor

warnings.filterwarnings("ignore")
pd.set_option("display.max_columns", 200)
pd.set_option("display.width", 220)

RESULT_DIR = "results"
os.makedirs(RESULT_DIR, exist_ok=True)

AMR_PATH = r"C:\\Users\\lunch\\Downloads\\amr_rate.csv"
X_PATH = r"C:\\Users\\lunch\\Downloads\\climate_social_eco.csv"

AMR_COLS = [
    "MRCNS", "VREFS", "VREFM", "PRSP", "ERSP", "3GCRKP",
    "MRSA", "3GCREC", "CREC", "QREC", "CRPA", "CRKP", "CRAB"
]

FE_SPECS = {
    "NoYes_YearFE": {
        "entity_effects": False,
        "time_effects": True,
        "province_fe": "No",
        "year_fe": "Yes",
        "label": "Province: No / Year: Yes",
    },
    "YesNo_EntityFE": {
        "entity_effects": True,
        "time_effects": False,
        "province_fe": "Yes",
        "year_fe": "No",
        "label": "Province: Yes / Year: No",
    },
    "YesYes_TwoWayFE": {
        "entity_effects": True,
        "time_effects": True,
        "province_fe": "Yes",
        "year_fe": "Yes",
        "label": "Province: Yes / Year: Yes",
    },
}

def to_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)

def zscore_series(s: pd.Series) -> pd.Series:
    s = to_float(s)
    mu = np.nanmean(s.values)
    sd = np.nanstd(s.values, ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - mu) / sd

def fill_panel_median(df: pd.DataFrame, col: str) -> pd.Series:
    out = to_float(df[col])
    out = out.groupby(df["Province"]).transform(lambda s: s.fillna(s.median()))
    out = out.fillna(out.median())
    return out

def compute_vif(x: pd.DataFrame) -> pd.DataFrame:
    vals = x.values.astype(float)
    return pd.DataFrame({
        "feature": x.columns,
        "VIF": [variance_inflation_factor(vals, i) for i in range(len(x.columns))]
    })

def p_to_text(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 1e-4:
        return "<0.0001"
    return f"{p:.4f}".rstrip("0").rstrip(".")

def p_to_stars(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""

def fmt_coef(x: float, digits=4, stars="") -> str:
    if not np.isfinite(x):
        return ""
    return f"{x:.{digits}f}".rstrip("0").rstrip(".") + stars

def fmt_ci(lo: float, hi: float, digits=4) -> str:
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return ""
    return f"({lo:.{digits}f}, {hi:.{digits}f})"

def safe_sheet_name(name: str) -> str:
    name = re.sub(r"[\\\\/*?:\\[\\]]", "_", name)
    return name[:31]

def build_lancet_table(res, x_cols, scheme_name: str, fe_name: str, fe_cfg: dict) -> pd.DataFrame:
    ci = res.conf_int()
    ci_lo = ci.iloc[:, 0]
    ci_hi = ci.iloc[:, 1]

    rows = []
    for xname in x_cols:
        b = float(res.params.get(xname, np.nan))
        p = float(res.pvalues.get(xname, np.nan))
        lo = float(ci_lo.loc[xname]) if xname in ci_lo.index else np.nan
        hi = float(ci_hi.loc[xname]) if xname in ci_hi.index else np.nan
        rows.append({
            "Predictor": xname,
            "Coefficient": fmt_coef(b, 4, p_to_stars(p)),
            "95% CI": fmt_ci(lo, hi, 4),
            "p value": p_to_text(p),
        })

    rows.extend([
        {"Predictor": "Province", "Coefficient": fe_cfg["province_fe"], "95% CI": "", "p value": ""},
        {"Predictor": "Year", "Coefficient": fe_cfg["year_fe"], "95% CI": "", "p value": ""},
        {"Predictor": "R-squared", "Coefficient": fmt_coef(float(res.rsquared), 3), "95% CI": "", "p value": ""},
        {"Predictor": "R-squared (Overall)", "Coefficient": fmt_coef(float(res.rsquared_overall), 3), "95% CI": "", "p value": ""},
        {"Predictor": "R² (within)", "Coefficient": fmt_coef(float(res.rsquared_within), 3), "95% CI": "", "p value": ""},
        {"Predictor": "Total number of observations", "Coefficient": str(int(res.nobs)), "95% CI": "", "p value": ""},
    ])
    return pd.DataFrame(rows)

def build_lancet_export_block(table: pd.DataFrame, scheme_name: str, fe_cfg: dict) -> pd.DataFrame:
    title_row = pd.DataFrame([{
        "Predictor": f"{scheme_name} | {fe_cfg['label']}",
        "Coefficient": "",
        "95% CI": "",
        "p value": "",
    }])
    spacer_row = pd.DataFrame([{
        "Predictor": "",
        "Coefficient": "",
        "95% CI": "",
        "p value": "",
    }])
    return pd.concat([title_row, table, spacer_row], ignore_index=True)

def explain_result(row: pd.Series) -> str:
    sig_txt = row["sig_predictors_p_lt_0_05"] if row["sig_predictors_p_lt_0_05"] else "无变量达到 p<0.05"
    return (
        f"**结果解释**  \\n"
        f"- 固定效应设定：{row['fe_label']}  \\n"
        f"- 综合排序：第 {int(row['performance_rank'])} 名，综合得分={row['performance_score']:.3f}  \\n"
        f"- 主模型 `R-squared={row['r2_model']:.3f}`，`R-squared (Overall)={row['r2_overall']:.3f}`，`R² (within)={row['r2_within']:.3f}`  \\n"
        f"- `R1xday` 系数={row['coef_R1xday']:.4f}，p={row['p_R1xday']:.4f}  \\n"
        f"- `抗菌药物使用强度` 系数={row['coef_AMC']:.4f}，p={row['p_AMC']:.4f}  \\n"
        f"- 显著变量：{sig_txt}  \\n"
        f"- VIF：raw 最大值={row['max_vif_raw']:.2f}，z-score 后最大值={row['max_vif_z']:.2f}"
    )
"""
    ),
    new_code_cell(
        """amr = pd.read_csv(AMR_PATH, encoding="utf-8-sig")
x = pd.read_csv(X_PATH, encoding="utf-8-sig")

# 显式固定 climate 表前两列为 Province / Year，避免中英文列名混杂
x = x.rename(columns={x.columns[0]: "Province", x.columns[1]: "Year"})

for df_temp in [amr, x]:
    if "Province" not in df_temp.columns:
        raise ValueError("Province column not found")
    if "Year" not in df_temp.columns:
        raise ValueError("Year column not found")
    df_temp["Province"] = df_temp["Province"].astype(str).str.strip()
    df_temp["Year"] = pd.to_numeric(df_temp["Year"], errors="coerce").astype("Int64")

df = amr.merge(x, on=["Province", "Year"], how="inner")
df = df[df["Year"].between(2014, 2023)].dropna(subset=["Province", "Year"]).copy()

for c in AMR_COLS:
    df[c] = to_float(df[c])

df["AMR_AGG"] = df[AMR_COLS].mean(axis=1, skipna=True)
z_amr = pd.DataFrame({c: zscore_series(df[c]) for c in AMR_COLS})
df["AMR_AGG_z"] = z_amr.mean(axis=1, skipna=True)

print("Merged shape:", df.shape)
print("Years:", int(df["Year"].min()), "-", int(df["Year"].max()))
print("Provinces:", df["Province"].nunique())"""
    ),
    new_markdown_cell(
        """## 候选变量组

这里先比较 4 套候选方案：

- `方案A_平衡主线组`
- `方案D_城市气候组`
- `方案F_低VIF主线组`
- `方案C_污染替代组`

每套方案都会继续与 3 种固定效应组合交叉，形成 12 个模型。"""
    ),
    new_code_cell(
        """SCHEMES = {
    "方案A_平衡主线组": {
        "note": "推荐主线候选：R1xday 与 AMC 都较稳，VIF 仍在可接受范围内。",
        "vars": ["省平均气温", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "人均日生活用水量(升)", "牲畜饲养\\n-猪年底头数"],
    },
    "方案D_城市气候组": {
        "note": "用主要城市平均气温和绿化覆盖率替换部分省级代理，适合做城市环境视角的敏感性分析。",
        "vars": ["主要城市平均气温", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "建成区绿化覆盖率", "牲畜饲养\\n-猪年底头数"],
    },
    "方案F_低VIF主线组": {
        "note": "当前 VIF 最低的一组，适合做低共线性参考版本。",
        "vars": ["TA（°C）", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "人均日生活用水量(升)", "牲畜饲养\\n-猪年底头数", "主要城市日照时数"],
    },
    "方案C_污染替代组": {
        "note": "用氮氧化物和可支配收入替换 PM2.5 / GDP 的一种替代规格。",
        "vars": ["省平均气温", "R1xday", "氮氧化物", "抗菌药物使用强度", "可支配收入", "建成区绿化覆盖率", "人均日生活用水量(升)", "牲畜饲养\\n-猪年底头数"],
    },
}"""
    ),
    new_code_cell(
        """def run_model(df_raw: pd.DataFrame, scheme_name: str, scheme_spec: dict, fe_name: str, fe_cfg: dict):
    cols = scheme_spec["vars"]
    work = df_raw.copy()
    raw_x = pd.DataFrame(index=work.index)

    for c in cols:
        raw_x[c] = fill_panel_median(work, c)
        work[c] = zscore_series(raw_x[c])

    z_x = work[cols].copy()
    vif_raw = compute_vif(raw_x).rename(columns={"VIF": "vif_raw"})
    vif_z = compute_vif(z_x).rename(columns={"VIF": "vif_z"})
    vif_table = vif_raw.merge(vif_z, on="feature", how="inner")
    vif_table["abs_diff"] = (vif_table["vif_raw"] - vif_table["vif_z"]).abs()

    panel = work.set_index(["Province", "Year"]).sort_index()
    tmp = pd.concat([panel["AMR_AGG_z"], panel[cols]], axis=1).dropna()
    y = tmp["AMR_AGG_z"]
    x_model = tmp[cols]

    res = PanelOLS(
        y,
        x_model,
        entity_effects=fe_cfg["entity_effects"],
        time_effects=fe_cfg["time_effects"],
    ).fit(cov_type="clustered", cluster_entity=True)

    summary_row = {
        "scheme": scheme_name,
        "scheme_note": scheme_spec["note"],
        "fe_spec": fe_name,
        "fe_label": fe_cfg["label"],
        "province_fe": fe_cfg["province_fe"],
        "year_fe": fe_cfg["year_fe"],
        "n_vars": len(cols),
        "variables": " | ".join(cols),
        "nobs": int(res.nobs),
        "r2_model": float(res.rsquared),
        "r2_overall": float(res.rsquared_overall),
        "r2_within": float(res.rsquared_within),
        "max_vif_raw": float(vif_table["vif_raw"].max()),
        "median_vif_raw": float(vif_table["vif_raw"].median()),
        "max_vif_z": float(vif_table["vif_z"].max()),
        "median_vif_z": float(vif_table["vif_z"].median()),
        "max_abs_vif_diff": float(vif_table["abs_diff"].max()),
        "coef_R1xday": float(res.params["R1xday"]),
        "p_R1xday": float(res.pvalues["R1xday"]),
        "coef_AMC": float(res.params["抗菌药物使用强度"]),
        "p_AMC": float(res.pvalues["抗菌药物使用强度"]),
        "sig_predictors_p_lt_0_05": ", ".join([c for c in cols if float(res.pvalues[c]) < 0.05]),
    }

    coef_table = pd.DataFrame({
        "scheme": scheme_name,
        "fe_spec": fe_name,
        "predictor": res.params.index,
        "coef": res.params.values,
        "p_value": res.pvalues.values,
        "ci_low": res.conf_int().iloc[:, 0].values,
        "ci_high": res.conf_int().iloc[:, 1].values,
    })

    vif_table = vif_table.rename(columns={"feature": "predictor"})
    vif_table["scheme"] = scheme_name
    vif_table["fe_spec"] = fe_name

    tab_lancet = build_lancet_table(res, cols, scheme_name, fe_name, fe_cfg)
    return summary_row, coef_table, vif_table, tab_lancet


summary_rows = []
coef_tables = []
vif_tables = []
lancet_tables = {}
lancet_export_blocks = []

for scheme_name, scheme_spec in SCHEMES.items():
    for fe_name, fe_cfg in FE_SPECS.items():
        summary_row, coef_table, vif_table, tab_lancet = run_model(df, scheme_name, scheme_spec, fe_name, fe_cfg)
        summary_rows.append(summary_row)
        coef_tables.append(coef_table)
        vif_tables.append(vif_table)
        lancet_tables[(scheme_name, fe_name)] = tab_lancet
        lancet_export_blocks.append(build_lancet_export_block(tab_lancet, scheme_name, fe_cfg))

summary_df = pd.DataFrame(summary_rows).sort_values(["scheme", "fe_spec"])
coef_df = pd.concat(coef_tables, ignore_index=True)
vif_df = pd.concat(vif_tables, ignore_index=True)
lancet_long_df = pd.concat(lancet_export_blocks, ignore_index=True)

summary_df"""
    ),
    new_markdown_cell(
        """## 横向对比总表

下面这张表把 12 个模型的关键指标横向展开，适合快速比较：

- `R-squared`
- `R-squared (Overall)`
- `R² (within)`
- `R1xday` 的系数和 p 值
- `抗菌药物使用强度` 的系数和 p 值
- 最大 VIF（raw / z-score 后）"""
    ),
    new_code_cell(
        """horizontal_metrics = [
    "r2_model",
    "r2_overall",
    "r2_within",
    "coef_R1xday",
    "p_R1xday",
    "coef_AMC",
    "p_AMC",
    "max_vif_raw",
    "max_vif_z",
]

summary_df["model_id"] = summary_df["scheme"] + " | " + summary_df["fe_label"]
horizontal_compare_df = (
    summary_df[["model_id"] + horizontal_metrics]
    .set_index("model_id")
    .T
    .reset_index()
    .rename(columns={"index": "metric"})
)

horizontal_compare_df"""
    ),
    new_markdown_cell(
        """## 模型性能排序

这里额外给出一个综合排序，方便快速挑主模型。这个排序不是单看某一个 `R²`，而是把三类信息一起考虑：

- `45%`：核心变量支持度
  - 优先奖励 `R1xday` 与 `抗菌药物使用强度` 系数为正、且 `p value` 更小的模型
- `35%`：模型拟合度
  - 综合 `R-squared`、`R-squared (Overall)`、`R² (within)`
- `20%`：共线性
  - `max_vif_z` 越低越好

这是一张“便于筛选”的工作排序表，不替代你对主文模型和附录模型的最终判断。"""
    ),
    new_code_cell(
        """def minmax01(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    if np.isclose(s.max(), s.min()):
        return pd.Series(np.ones(len(s)), index=s.index)
    return (s - s.min()) / (s.max() - s.min())

summary_df["r1xday_support_raw"] = np.sign(summary_df["coef_R1xday"]) * (
    -np.log10(summary_df["p_R1xday"].clip(lower=1e-12))
)
summary_df["amc_support_raw"] = np.sign(summary_df["coef_AMC"]) * (
    -np.log10(summary_df["p_AMC"].clip(lower=1e-12))
)
summary_df["core_positive_count"] = (
    (summary_df["coef_R1xday"] > 0).astype(int) +
    (summary_df["coef_AMC"] > 0).astype(int)
)
summary_df["core_sig_count_p_lt_0_05"] = (
    (summary_df["p_R1xday"] < 0.05).astype(int) +
    (summary_df["p_AMC"] < 0.05).astype(int)
)
summary_df["core_signal_score"] = (
    minmax01(summary_df["r1xday_support_raw"]) +
    minmax01(summary_df["amc_support_raw"])
) / 2
summary_df["fit_score"] = (
    minmax01(summary_df["r2_model"]) +
    minmax01(summary_df["r2_overall"]) +
    minmax01(summary_df["r2_within"])
) / 3
summary_df["vif_score"] = 1 - minmax01(np.log1p(summary_df["max_vif_z"]))
summary_df["performance_score"] = (
    0.45 * summary_df["core_signal_score"] +
    0.35 * summary_df["fit_score"] +
    0.20 * summary_df["vif_score"]
)
summary_df["performance_rank"] = (
    summary_df["performance_score"]
    .rank(method="dense", ascending=False)
    .astype(int)
)

ranking_df = (
    summary_df[[
        "performance_rank",
        "model_id",
        "scheme",
        "fe_label",
        "performance_score",
        "core_signal_score",
        "fit_score",
        "vif_score",
        "core_positive_count",
        "core_sig_count_p_lt_0_05",
        "coef_R1xday",
        "p_R1xday",
        "coef_AMC",
        "p_AMC",
        "r2_model",
        "r2_overall",
        "r2_within",
        "max_vif_z",
        "sig_predictors_p_lt_0_05",
    ]]
    .sort_values(["performance_rank", "performance_score"], ascending=[True, False])
    .reset_index(drop=True)
)

ranking_df"""
    ),
    new_markdown_cell(
        """## Lancet 风格结果表

下面会把 12 个模型逐张打印。每张表都包含：

- 表标题中显示 `scheme` 和固定效应组合
- 表内只保留 `Predictor / Coefficient / 95% CI / p value` 4 列
- `Province`
- `Year`
- `R-squared`
- `R-squared (Overall)`
- `R² (within)`
- `Total number of observations`

导出的 `all_tables` 也不再额外保留 `scheme` 或 `fe_spec` 两列，而是用每张表的首行标题来区分模型。

因此你可以直接在 notebook 里纵向看单个模型，也可以通过上面的横向总表横着比较。"""
    ),
    new_code_cell(
        """for scheme_name, scheme_spec in SCHEMES.items():
    display(Markdown(f"## {scheme_name}"))
    display(Markdown(scheme_spec["note"]))
    for fe_name, fe_cfg in FE_SPECS.items():
        row = summary_df[(summary_df["scheme"] == scheme_name) & (summary_df["fe_spec"] == fe_name)].iloc[0]
        display(Markdown(f"### {fe_cfg['label']}"))
        display(Markdown(explain_result(row)))
        display(lancet_tables[(scheme_name, fe_name)])"""
    ),
    new_code_cell(
        """summary_csv = os.path.join(RESULT_DIR, "variable_group_scheme_summary.csv")
summary_xlsx = os.path.join(RESULT_DIR, "variable_group_scheme_summary.xlsx")
coef_csv = os.path.join(RESULT_DIR, "variable_group_scheme_coefficients.csv")
coef_xlsx = os.path.join(RESULT_DIR, "variable_group_scheme_coefficients.xlsx")
vif_csv = os.path.join(RESULT_DIR, "variable_group_scheme_vif.csv")
vif_xlsx = os.path.join(RESULT_DIR, "variable_group_scheme_vif.xlsx")
lancet_csv = os.path.join(RESULT_DIR, "variable_group_scheme_lancet_tables.csv")
lancet_xlsx = os.path.join(RESULT_DIR, "variable_group_scheme_lancet_tables.xlsx")
horizontal_csv = os.path.join(RESULT_DIR, "variable_group_scheme_horizontal_compare.csv")
horizontal_xlsx = os.path.join(RESULT_DIR, "variable_group_scheme_horizontal_compare.xlsx")
ranking_csv = os.path.join(RESULT_DIR, "variable_group_scheme_ranking.csv")
ranking_xlsx = os.path.join(RESULT_DIR, "variable_group_scheme_ranking.xlsx")

summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
summary_df.to_excel(summary_xlsx, index=False)
coef_df.to_csv(coef_csv, index=False, encoding="utf-8-sig")
coef_df.to_excel(coef_xlsx, index=False)
vif_df.to_csv(vif_csv, index=False, encoding="utf-8-sig")
vif_df.to_excel(vif_xlsx, index=False)
lancet_long_df.to_csv(lancet_csv, index=False, encoding="utf-8-sig")
horizontal_compare_df.to_csv(horizontal_csv, index=False, encoding="utf-8-sig")
ranking_df.to_csv(ranking_csv, index=False, encoding="utf-8-sig")

with pd.ExcelWriter(lancet_xlsx) as writer:
    lancet_long_df.to_excel(writer, sheet_name="all_tables", index=False)
    for (scheme_name, fe_name), table in lancet_tables.items():
        sheet = safe_sheet_name(f"{scheme_name}_{fe_name}")
        table.to_excel(writer, sheet_name=sheet, index=False)

horizontal_compare_df.to_excel(horizontal_xlsx, index=False)
ranking_df.to_excel(ranking_xlsx, index=False)

print("Saved:", summary_csv)
print("Saved:", summary_xlsx)
print("Saved:", coef_csv)
print("Saved:", coef_xlsx)
print("Saved:", vif_csv)
print("Saved:", vif_xlsx)
print("Saved:", lancet_csv)
print("Saved:", lancet_xlsx)
print("Saved:", horizontal_csv)
print("Saved:", horizontal_xlsx)
print("Saved:", ranking_csv)
print("Saved:", ranking_xlsx)"""
    ),
    new_markdown_cell(
        """## 怎么看这些结果

- 先看 `variable_group_scheme_ranking.xlsx`
  - 适合先快速筛出综合表现最好的模型
- 再看 `variable_group_scheme_horizontal_compare.xlsx`
  - 适合一眼比较 12 个模型的核心统计量
- 再看 `variable_group_scheme_summary.xlsx`
  - 适合看长表形式的全量汇总
- 再看 `variable_group_scheme_lancet_tables.xlsx`
  - `all_tables` 用首行标题区分模型；各单独 sheet 则是一张模型一张表
- 如果你要检查共线性，再看 `variable_group_scheme_vif.xlsx`

通常可以按这个顺序筛主模型：

1. `R1xday` 和 `抗菌药物使用强度` 是否方向稳定
2. 这两个变量是否显著或接近显著
3. `R-squared (Overall)` 和 `R² (within)` 是否至少在可接受区间
4. `max_vif_z` 是否仍然偏高
5. 再决定哪套放主文、哪套放附录"""
    ),
]


nb = new_notebook(
    cells=cells,
    metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
)
nbformat.write(nb, NOTEBOOK_PATH)
print(f"Created {NOTEBOOK_PATH}")
