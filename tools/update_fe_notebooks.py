import nbformat
from nbformat.v4 import new_markdown_cell
from pathlib import Path


BASE_DIR = Path(r"e:\MALA\Code_health\2 固定效应模型")


MODEL_CONFIG = {
    "fixed_effects_master_time.ipynb": {
        "tag": "time",
        "title": "Time FE版",
        "label": "Year FE only",
        "zh": "仅 Year FE + 省份聚类稳健 SE",
        "entity": False,
        "time": True,
    },
    "fixed_effects_master_entity.ipynb": {
        "tag": "entity",
        "title": "Entity FE版",
        "label": "Entity FE only",
        "zh": "仅 Province FE + 省份聚类稳健 SE",
        "entity": True,
        "time": False,
    },
    "fixed_effects_master_both.ipynb": {
        "tag": "both",
        "title": "双固定效应版",
        "label": "Two-way FE",
        "zh": "Province FE + Year FE + 省份聚类稳健 SE",
        "entity": True,
        "time": True,
    },
}


def update_master_notebook(path: Path, cfg: dict) -> None:
    nb = nbformat.read(path, as_version=4)

    nb.cells[0].source = f"""# AMR（省份×年份）固定效应主流程（{cfg['title']}）

本 notebook 以原 `amr_lancet_fe_from_raw_csv.ipynb` 为主文件，并合并了原 `fixed_effects_model.ipynb` 中仍需保留的输出逻辑，包括 `FE_OUTPUT` 简化结果表和系数图。

- 原始设计：Province FE + Year FE（双固定效应）
- 当前设定：{cfg['zh']}
- Baseline 和 Lag-1 使用相同的固定效应设定
- 导出文件带 `_{cfg['tag']}` 后缀，避免覆盖其他版本结果
"""

    nb.cells[10].source = f"## 5) 主固定效应模型（当前：{cfg['zh']}）"

    nb.cells[11].source = f"""# =========================
# 5) Fixed-effects regression ({cfg['label']})
# =========================
Y_COL = "AMR_AGG_z"      # <-- 可改为某个单项 AMR
X_COLS = X_cols_used     # 当前主模型使用的中文变量名
MODEL_TAG = "{cfg['tag']}"
MODEL_LABEL = "{cfg['label']}"

# X 全部 z-score（与固定主线保持一致，便于比较标准化系数）
for c in X_COLS:
    df[c] = zscore_x(df[c])

# panel index
d = df.set_index(["Province","Year"]).sort_index()

Y = to_float(d[Y_COL])
X = d[X_COLS].copy()

# drop missing
tmp = pd.concat([Y, X], axis=1).dropna()
Y = tmp[Y_COL]
X = tmp[X_COLS]

ENTITY_EFFECTS = {cfg['entity']}
TIME_EFFECTS = {cfg['time']}

# 通过这两个开关控制是否纳入省份/年份固定效应
mod = PanelOLS(Y, X, entity_effects=ENTITY_EFFECTS, time_effects=TIME_EFFECTS)
res = mod.fit(cov_type="clustered", cluster_entity=True)

print(res.summary)
"""

    nb.cells[17].source = "## 8) 导出 Lancet 风格结果表（文件名附模型后缀）"
    nb.cells[19].source = "### **滞后一年（沿用与主模型相同的固定效应设定）**"

    nb.cells[20].source = """# 对所有变量构造 Lag-1 并跑固定效应（沿用与主模型相同的 FE 设定）
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

# -------------------------
# 1) 构造所有 X 的 Lag-1
# -------------------------
d_l1 = d.copy()

X_L1_COLS = []
for v in X_COLS:
    newv = f"{v}_L1"
    d_l1[newv] = d_l1.groupby(level=0)[v].shift(1)  # 按省份滞后1期
    X_L1_COLS.append(newv)

# -------------------------
# 2) 用所有 X_L1 作为解释变量跑 FE
# -------------------------
tmp_l1 = d_l1[[Y_COL] + X_L1_COLS].dropna()
Y_l1 = tmp_l1[Y_COL]
X_l1 = tmp_l1[X_L1_COLS]

L1_ENTITY_EFFECTS = ENTITY_EFFECTS
L1_TIME_EFFECTS = TIME_EFFECTS
mod_l1 = PanelOLS(Y_l1, X_l1, entity_effects=L1_ENTITY_EFFECTS, time_effects=L1_TIME_EFFECTS)
res_l1_all = mod_l1.fit(cov_type="clustered", cluster_entity=True)

print(res_l1_all.summary)
print("Lag-1 FE setting:", MODEL_LABEL)
print("Lag-1 N:", int(res_l1_all.nobs), "R2(within):", float(res_l1_all.rsquared_within))
"""

    nb.cells[23].source = """OUT_DIR = "outputs_lancet_fe"
os.makedirs(OUT_DIR, exist_ok=True)

csv_l1 = os.path.join(OUT_DIR, f"lancet_table_{Y_COL}_{MODEL_TAG}_lag1.csv")
xlsx_l1 = os.path.join(OUT_DIR, f"lancet_table_{Y_COL}_{MODEL_TAG}_lag1.xlsx")
tab_l1_lancet.to_csv(csv_l1, index=False, encoding="utf-8-sig")
tab_l1_lancet.to_excel(xlsx_l1, index=False)

csv_compare = os.path.join(OUT_DIR, f"lancet_compare_{Y_COL}_{MODEL_TAG}_vs_lag1.csv")
xlsx_compare = os.path.join(OUT_DIR, f"lancet_compare_{Y_COL}_{MODEL_TAG}_vs_lag1.xlsx")
final2.to_csv(csv_compare, index=False, encoding="utf-8-sig")
final2.to_excel(xlsx_compare, index=False)

print("Saved:", csv_l1)
print("Saved:", xlsx_l1)
print("Saved:", csv_compare)
print("Saved:", xlsx_compare)
"""

    nb.cells[24].source = f"""## 9) 额外导出简化 FE 结果表与系数图（由原 `fixed_effects_model.ipynb` 合并）

这一节保留了原 `fixed_effects_model.ipynb` 中更偏分析流程的两个输出：

- `FE_OUTPUT/AMR_AGG_z_FE_table_{cfg['tag']}.csv/.xlsx`
- `FE_OUTPUT/AMR_AGG_z_FE_coefplot_{cfg['tag']}.png`
"""

    nb.cells[25].source = """# =========================
# 9) Export simplified FE table (merged from former fixed_effects_model.ipynb)
# =========================
FE_OUT_DIR = "FE_OUTPUT"
os.makedirs(FE_OUT_DIR, exist_ok=True)

def fmt_ci_paren(lo: float, hi: float, digits=4) -> str:
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return ""
    return f"({lo:.{digits}f}, {hi:.{digits}f})"

ci_fe = res.conf_int()
ci_fe_lo = ci_fe.iloc[:, 0]
ci_fe_hi = ci_fe.iloc[:, 1]

rows_fe = []
for v in X_COLS:
    if v not in res.params.index:
        continue
    b = float(res.params.get(v, np.nan))
    p = float(res.pvalues.get(v, np.nan))
    lo = float(ci_fe_lo.loc[v]) if v in ci_fe_lo.index else np.nan
    hi = float(ci_fe_hi.loc[v]) if v in ci_fe_hi.index else np.nan
    rows_fe.append({
        "Predictor": v,
        "Coefficient": fmt_coef(b, 4, p_to_stars(p)),
        "95% CI": fmt_ci_paren(lo, hi, 4),
        "p value": p_to_text(p),
    })

table_fe = pd.DataFrame(rows_fe)
table_fe = pd.concat([
    table_fe,
    pd.DataFrame([
        {"Predictor": "Province", "Coefficient": "Yes" if ENTITY_EFFECTS else "No", "95% CI": "", "p value": ""},
        {"Predictor": "Year", "Coefficient": "Yes" if TIME_EFFECTS else "No", "95% CI": "", "p value": ""},
        {"Predictor": "N (observations)", "Coefficient": f"{int(res.nobs)}", "95% CI": "", "p value": ""},
        {"Predictor": "R-squared (within)", "Coefficient": f"{float(res.rsquared_within):.3f}", "95% CI": "", "p value": ""},
    ])
], ignore_index=True)

csv_fe = os.path.join(FE_OUT_DIR, f"AMR_AGG_z_FE_table_{MODEL_TAG}.csv")
xlsx_fe = os.path.join(FE_OUT_DIR, f"AMR_AGG_z_FE_table_{MODEL_TAG}.xlsx")
table_fe.to_csv(csv_fe, index=False, encoding="utf-8-sig")
table_fe.to_excel(xlsx_fe, index=False)

print("Saved:", csv_fe)
print("Saved:", xlsx_fe)
table_fe
"""

    nb.cells[26].source = """# =========================
# 10) Coefficient plot (merged from former fixed_effects_model.ipynb)
# =========================
import matplotlib as mpl
import matplotlib.pyplot as plt

mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
mpl.rcParams["axes.unicode_minus"] = False

coef = res.params.reindex(X_COLS)
ci_plot = res.conf_int().reindex(X_COLS)
lo = ci_plot.iloc[:, 0]
hi = ci_plot.iloc[:, 1]

plot_df = pd.DataFrame({
    "Predictor": X_COLS,
    "coef": coef.values,
    "lo": lo.values,
    "hi": hi.values,
    "p": res.pvalues.reindex(X_COLS).values,
}).sort_values("coef")

plt.figure(figsize=(8, 5))
ypos = np.arange(len(plot_df))
plt.hlines(y=ypos, xmin=plot_df["lo"], xmax=plot_df["hi"])
plt.plot(plot_df["coef"], ypos, "o")
plt.yticks(ypos, plot_df["Predictor"])
plt.axvline(0, linewidth=1)
plt.title(f"AMR_AGG_z: {MODEL_LABEL} coefficients\\nClustered SE by province")
plt.xlabel("Coefficient (95% CI)")
plt.tight_layout()

fig_path = os.path.join(FE_OUT_DIR, f"AMR_AGG_z_FE_coefplot_{MODEL_TAG}.png")
plt.savefig(fig_path, dpi=300)
plt.show()
print("Saved:", fig_path)
"""

    # Cell 18 saves baseline table.
    nb.cells[18].source = """# =========================
# 8) Export baseline Lancet-style table
# =========================
OUT_DIR = "outputs_lancet_fe"
os.makedirs(OUT_DIR, exist_ok=True)

csv_out = os.path.join(OUT_DIR, f"lancet_table_{Y_COL}_{MODEL_TAG}.csv")
xlsx_out = os.path.join(OUT_DIR, f"lancet_table_{Y_COL}_{MODEL_TAG}.xlsx")

tab_lancet.to_csv(csv_out, index=False, encoding="utf-8-sig")
tab_lancet.to_excel(xlsx_out, index=False)

print("Saved:", csv_out)
print("Saved:", xlsx_out)
"""

    nbformat.write(nb, path)


def update_revise_notebook(path: Path) -> None:
    nb = nbformat.read(path, as_version=4)

    intro = new_markdown_cell(
        """# revise：双固定效应诊断稿

这个 notebook 用于做一版独立的探索性诊断：

- 因变量使用 `AMR_AGG`
- 对 `X` 与 `Y` 做 `log1p(abs())`
- 主模型使用双固定效应（Province FE + Year FE）
- 同时给出 `Pooled OLS + dummies` 的整体 R² 作为对照

它不是当前主线 `fixed_effects_master_time.ipynb` 的直接替代版本，更适合作为方法诊断或附录草稿。
"""
    )

    code = """import os
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS, PooledOLS
from statsmodels.stats.outliers_influence import variance_inflation_factor

warnings.filterwarnings("ignore")

# ==========================================
# 1. 数据读取与主键整理
# ==========================================
amr_path = r"C:\\Users\\lunch\\Downloads\\amr_rate.csv"
x_path = r"C:\\Users\\lunch\\Downloads\\climate_social_eco.csv"

amr = pd.read_csv(amr_path, encoding="utf-8-sig")
x = pd.read_csv(x_path, encoding="utf-8-sig")

# 为避免中英文列名混杂，这里显式固定 climate 表前两列为 Province / Year
x = x.rename(columns={x.columns[0]: "Province", x.columns[1]: "Year"})

def normalize_key_cols(df):
    col_map = {}
    for c in df.columns:
        cc = str(c).strip().lower()
        if cc in ["province", "prov", "省份"]:
            col_map[c] = "Province"
        if cc in ["year", "yr", "年份"]:
            col_map[c] = "Year"
    return df.rename(columns=col_map)

amr = normalize_key_cols(amr)
x = normalize_key_cols(x)

for df_temp in [amr, x]:
    df_temp["Province"] = df_temp["Province"].astype(str).str.strip()
    df_temp["Year"] = pd.to_numeric(df_temp["Year"], errors="coerce").astype("Int64")

df = amr.merge(x, on=["Province", "Year"], how="inner")
df = df[df["Year"].between(2014, 2023)].dropna(subset=["Province", "Year"]).copy()

# ==========================================
# 2. 变量定义：这一版是诊断稿，不与主线强行保持同一口径
# ==========================================
X_cols = ["PM2.5", "省平均气温", "医疗水平", "抗菌药物使用强度", "GDP", "城市用水普及率", "生活垃圾无害化处理率", "省平均降水", "R1xday"]
Y_col = "AMR_AGG"
RESULT_PATH = "results/revise_two_way_log_diagnostic.csv"
SUMMARY_PATH = "results/revise_two_way_log_summary.csv"

AMR_COLS = ["MRCNS", "VREFS", "VREFM", "PRSP", "ERSP", "3GCRKP", "MRSA", "3GCREC", "CREC", "QREC", "CRPA", "CRKP", "CRAB"]
df[Y_col] = df[AMR_COLS].apply(pd.to_numeric, errors="coerce").mean(axis=1)

# 先做数值化，再按省份中位数 + 全局中位数补缺
for c in X_cols + [Y_col]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
    df[c] = df.groupby("Province")[c].transform(lambda s: s.fillna(s.median()))
    df[c] = df[c].fillna(df[c].median())

# 这版保留 log1p(abs()) 设定，仅用于探索“对数化 + 双固定效应”的表现
df_log = df.copy()
for col in X_cols + [Y_col]:
    df_log[col] = np.log1p(df_log[col].abs())

df_log = df_log.replace([np.inf, -np.inf], np.nan).dropna(subset=X_cols + [Y_col])
df_log = df_log.set_index(["Province", "Year"]).sort_index()

# ==========================================
# 3. 多重共线性诊断
# ==========================================
def check_vif(X):
    X_clean = X.dropna()
    vif_data = pd.DataFrame()
    vif_data["feature"] = X_clean.columns
    vif_data["VIF"] = [variance_inflation_factor(X_clean.values, i) for i in range(len(X_clean.columns))]
    return vif_data

vif_table = check_vif(df_log[X_cols])
print("--- 多重共线性检查 (VIF) ---")
print(vif_table)

# ==========================================
# 4. 模型运行
# ==========================================
model_fe = PanelOLS(df_log[Y_col], df_log[X_cols], entity_effects=True, time_effects=True)
res_fe = model_fe.fit(cov_type="clustered", cluster_entity=True)

print("\\n--- 方案 A: PanelOLS (双固定效应诊断) ---")
print(f"R2 within:  {res_fe.rsquared_within:.4f}")
print(f"R2 overall: {res_fe.rsquared_overall:.4f}")

df_dummy = df_log.reset_index()
X_with_dummies = pd.get_dummies(
    df_dummy[["Province", "Year"] + X_cols],
    columns=["Province", "Year"],
    drop_first=True,
)
X_with_dummies = sm.add_constant(X_with_dummies.astype(float))

df_dummy_indexed = df_dummy.set_index(["Province", "Year"])
X_with_dummies.index = df_dummy_indexed.index

X_final = X_with_dummies.dropna()
Y_final = df_dummy_indexed[Y_col].loc[X_final.index]

model_pooled = PooledOLS(Y_final, X_final)
res_pooled = model_pooled.fit(cov_type="clustered", cluster_entity=True)

print("\\n--- 方案 B: Pooled OLS + 虚拟变量（仅作 R2 对照） ---")
print(f"整体 R2: {res_pooled.rsquared:.4f}")

# ==========================================
# 5. 结果导出
# ==========================================
output_table = pd.DataFrame({
    "Predictor": res_fe.params.index,
    "Coefficient": res_fe.params.values,
    "p-value": res_fe.pvalues,
    "Lower CI": res_fe.conf_int().iloc[:, 0],
    "Upper CI": res_fe.conf_int().iloc[:, 1],
})

summary_table = pd.DataFrame([
    {"Metric": "nobs", "Value": int(res_fe.nobs)},
    {"Metric": "r2_within", "Value": float(res_fe.rsquared_within)},
    {"Metric": "r2_overall", "Value": float(res_fe.rsquared_overall)},
    {"Metric": "pooled_r2", "Value": float(res_pooled.rsquared)},
    {"Metric": "max_vif", "Value": float(vif_table["VIF"].max())},
    {"Metric": "median_vif", "Value": float(vif_table["VIF"].median())},
])

os.makedirs("results", exist_ok=True)
output_table.to_csv(RESULT_PATH, index=False, encoding="utf-8-sig")
summary_table.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

print("\\n分析完成。")
print("Detailed coefficients:", RESULT_PATH)
print("Diagnostic summary:", SUMMARY_PATH)
"""

    nb.cells = [intro, nbformat.v4.new_code_cell(code)]
    nbformat.write(nb, path)


if __name__ == "__main__":
    for name, cfg in MODEL_CONFIG.items():
        update_master_notebook(BASE_DIR / name, cfg)
    update_revise_notebook(BASE_DIR / "revise.ipynb")
    print("Updated master notebooks and revise notebook.")
