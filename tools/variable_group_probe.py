import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from statsmodels.stats.outliers_influence import variance_inflation_factor


AMR_PATH = r"C:\Users\lunch\Downloads\amr_rate.csv"
X_PATH = r"C:\Users\lunch\Downloads\climate_social_eco.csv"

AMR_COLS = [
    "MRCNS",
    "VREFS",
    "VREFM",
    "PRSP",
    "ERSP",
    "3GCRKP",
    "MRSA",
    "3GCREC",
    "CREC",
    "QREC",
    "CRPA",
    "CRKP",
    "CRAB",
]

SCHEMES = {
    "scheme_a": ["省平均气温", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "人均日生活用水量(升)", "牲畜饲养\n-猪年底头数"],
    "scheme_b": ["TA（°C）", "R1xday", "PM2.5", "抗菌药物使用强度", "可支配收入", "文盲比例", "卫生程度\n（日污水处理能力）", "牲畜饲养\n-猪年底头数"],
    "scheme_c": ["省平均气温", "R1xday", "氮氧化物", "抗菌药物使用强度", "可支配收入", "建成区绿化覆盖率", "人均日生活用水量(升)", "牲畜饲养\n-猪年底头数"],
    "scheme_d": ["主要城市平均气温", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "建成区绿化覆盖率", "牲畜饲养\n-猪年底头数"],
    "scheme_e": ["省平均气温", "R1xday", "PM2.5", "抗菌药物使用强度", "可支配收入", "文盲比例", "建成区绿化覆盖率", "人均日生活用水量(升)", "牲畜饲养\n-猪年底头数"],
    "scheme_f": ["TA（°C）", "R1xday", "PM2.5", "抗菌药物使用强度", "GDP", "文盲比例", "人均日生活用水量(升)", "牲畜饲养\n-猪年底头数", "主要城市日照时数"],
}


def to_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)


def zscore(s: pd.Series) -> pd.Series:
    s = to_float(s)
    mu = np.nanmean(s.values)
    sd = np.nanstd(s.values, ddof=0)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - mu) / sd


def load_panel() -> pd.DataFrame:
    amr = pd.read_csv(AMR_PATH, encoding="utf-8-sig")
    x = pd.read_csv(X_PATH, encoding="utf-8-sig")
    x = x.rename(columns={x.columns[0]: "Province", x.columns[1]: "Year"})
    amr["Province"] = amr["Province"].astype(str).str.strip()
    x["Province"] = x["Province"].astype(str).str.strip()
    amr["Year"] = pd.to_numeric(amr["Year"], errors="coerce").astype("Int64")
    x["Year"] = pd.to_numeric(x["Year"], errors="coerce").astype("Int64")
    df = amr.merge(x, on=["Province", "Year"], how="inner")
    df = df[df["Year"].between(2014, 2023)].dropna(subset=["Province", "Year"]).copy()

    for c in AMR_COLS:
        df[c] = to_float(df[c])
    z_amr = pd.DataFrame({c: zscore(df[c]) for c in AMR_COLS})
    df["AMR_AGG_z"] = z_amr.mean(axis=1, skipna=True)
    return df


def evaluate_scheme(df: pd.DataFrame, cols: list[str]) -> dict:
    work = df.copy()
    for c in cols:
        work[c] = to_float(work[c])
        work[c] = work.groupby("Province")[c].transform(lambda s: s.fillna(s.median()))
        work[c] = work[c].fillna(work[c].median())
        work[c] = zscore(work[c])

    vals = work[cols].values.astype(float)
    vifs = [variance_inflation_factor(vals, i) for i in range(len(cols))]

    panel = work.set_index(["Province", "Year"]).sort_index()
    tmp = pd.concat([panel["AMR_AGG_z"], panel[cols]], axis=1).dropna()
    y = tmp["AMR_AGG_z"]
    x = tmp[cols]
    res = PanelOLS(y, x, entity_effects=False, time_effects=True).fit(
        cov_type="clustered", cluster_entity=True
    )

    row = {
        "max_vif": float(np.max(vifs)),
        "median_vif": float(np.median(vifs)),
        "nobs": int(res.nobs),
        "r2_within": float(res.rsquared_within),
        "r2_overall": float(res.rsquared_overall),
        "coef_R1xday": float(res.params["R1xday"]),
        "p_R1xday": float(res.pvalues["R1xday"]),
        "coef_AMC": float(res.params["抗菌药物使用强度"]),
        "p_AMC": float(res.pvalues["抗菌药物使用强度"]),
    }
    return row


if __name__ == "__main__":
    panel = load_panel()
    rows = []
    for name, cols in SCHEMES.items():
        row = {"scheme": name, "variables": " | ".join(cols)}
        row.update(evaluate_scheme(panel, cols))
        rows.append(row)
    out = pd.DataFrame(rows).sort_values(["max_vif", "p_AMC", "p_R1xday"])
    print(out.to_string(index=False))
