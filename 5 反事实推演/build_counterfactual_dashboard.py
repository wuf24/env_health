from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SECTION_DIR = ROOT / "5 反事实推演"
RESULT_ROOT = SECTION_DIR / "results"

FE_COEF_PATH = ROOT / "2 固定效应模型" / "results" / "exhaustive_model_coefficients.csv"
TEMPERATURE_VARS = {"主要城市平均气温", "省平均气温", "TA（°C）"}

FE_LABEL_TO_SPEC = {
    "Province: No / Year: Yes": "NoYes_YearFE",
    "Province: Yes / Year: No": "YesNo_EntityFE",
    "Province: Yes / Year: Yes": "YesYes_TwoWayFE",
}


def fmt_num(value: object, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}"


def fmt_pct_share(value: object, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{100 * float(value):.{digits}f}%"


def fmt_signed(value: object, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):+.{digits}f}"


def fmt_p(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    if value < 0.0001:
        return "<0.0001"
    return f"{value:.4f}"


def html_table(df: pd.DataFrame, columns: list[str], classes: str = "data-table") -> str:
    head = "".join(f"<th>{escape(str(col))}</th>" for col in columns)
    body_rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{escape(str(row[col]))}</td>" for col in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows)
    return f'<table class="{classes}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def load_inputs(outcome: str) -> dict[str, pd.DataFrame | Path]:
    base = RESULT_ROOT / outcome
    return {
        "base": base,
        "fe": pd.read_csv(base / "model_screening" / "fe_spec_comparison.csv"),
        "selected": pd.read_csv(base / "model_screening" / "selected_models.csv"),
        "bayes": pd.read_csv(base / "model_screening" / "bayes_variant_summary.csv"),
        "panel_predictions": pd.read_csv(base / "counterfactual_outputs" / "counterfactual_panel_predictions.csv"),
        "overall": pd.read_csv(base / "counterfactual_outputs" / "national_overall.csv"),
        "yearly": pd.read_csv(base / "counterfactual_outputs" / "national_yearly.csv"),
        "province_average": pd.read_csv(base / "counterfactual_outputs" / "province_average.csv"),
        "latest": pd.read_csv(base / "counterfactual_outputs" / "latest_year_province.csv"),
        "coefficients": pd.read_csv(FE_COEF_PATH),
    }


def build_selected_model_cards(selected: pd.DataFrame) -> str:
    cards = []
    for _, row in selected.iterrows():
        cards.append(
            f"""
            <article class="model-card">
              <div class="card-top">
                <span class="eyebrow">{escape(str(row['role_label']))}</span>
                <span class="chip">{escape(str(row['fe_label']))}</span>
              </div>
              <h3>{escape(str(row['scheme_id']))}</h3>
              <p class="muted">{escape(str(row['reason']))}</p>
              <div class="metric-row">
                <div><strong>R1xday</strong><span>{fmt_num(row['coef_R1xday'])} (p={fmt_p(row['p_R1xday'])})</span></div>
                <div><strong>AMC</strong><span>{fmt_num(row['coef_AMC'])} (p={fmt_p(row['p_AMC'])})</span></div>
                <div><strong>R²</strong><span>{fmt_num(row['r2_model'])}</span></div>
                <div><strong>Max VIF</strong><span>{fmt_num(row['max_vif_z'])}</span></div>
              </div>
              <details>
                <summary>查看变量组合</summary>
                <div class="var-list">{escape(str(row['variables'])).replace(' | ', '<span> | </span>')}</div>
              </details>
              <button class="focus-jump" data-model-id="{escape(str(row['model_id']))}">在下方聚焦分析这个模型</button>
            </article>
            """
        )
    return "".join(cards)


def build_key_coef_table(selected: pd.DataFrame, coef_df: pd.DataFrame) -> str:
    rows = []
    for _, model in selected.iterrows():
        predictors = ["R1xday", "抗菌药物使用强度"]
        var_list = str(model["variables"]).split(" | ")
        temp_vars = [var for var in var_list if var in TEMPERATURE_VARS]
        predictors.extend(temp_vars[:1])
        fe_spec = FE_LABEL_TO_SPEC[str(model["fe_label"])]
        sub = coef_df[(coef_df["scheme_id"] == model["scheme_id"]) & (coef_df["fe_spec"] == fe_spec)]
        for predictor in predictors:
            pick = sub[sub["predictor"] == predictor]
            if pick.empty:
                continue
            row = pick.iloc[0]
            rows.append(
                {
                    "模型": f"{model['role_label']} | {model['scheme_id']}",
                    "变量": predictor,
                    "系数": fmt_signed(row["coef"]),
                    "P值": fmt_p(row["p_value"]),
                    "95% CI": f"[{fmt_num(row['ci_low'])}, {fmt_num(row['ci_high'])}]",
                }
            )
    return html_table(pd.DataFrame(rows), ["模型", "变量", "系数", "P值", "95% CI"])


def build_overall_matrix(overall: pd.DataFrame) -> str:
    pivot = overall.pivot(index="role_label", columns="scenario_label", values="actual_minus_counterfactual_mean")
    pivot = pivot.reset_index().rename(columns={"role_label": "模型"})
    for col in pivot.columns[1:]:
        pivot[col] = pivot[col].map(fmt_signed)
    return html_table(pivot, list(pivot.columns))


def build_fe_table(fe: pd.DataFrame) -> str:
    view = fe.copy()
    view["top10_mean_score"] = view["top10_mean_score"].map(fmt_num)
    view["share_r1xday_positive"] = view["share_r1xday_positive"].map(fmt_pct_share)
    view["share_r1xday_sig_005"] = view["share_r1xday_sig_005"].map(fmt_pct_share)
    view["share_amc_positive"] = view["share_amc_positive"].map(fmt_pct_share)
    view["share_amc_sig_005"] = view["share_amc_sig_005"].map(fmt_pct_share)
    view["mean_r2_model"] = view["mean_r2_model"].map(fmt_num)
    view["median_max_vif_z"] = view["median_max_vif_z"].map(fmt_num)
    view = view.rename(
        columns={
            "fe_label": "FE 设定",
            "top10_mean_score": "Top10 平均综合分",
            "share_r1xday_positive": "R1xday 为正比例",
            "share_r1xday_sig_005": "R1xday 显著比例",
            "share_amc_positive": "AMC 为正比例",
            "share_amc_sig_005": "AMC 显著比例",
            "mean_r2_model": "平均 R²",
            "median_max_vif_z": "中位 Max VIF(z)",
        }
    )
    cols = ["FE 设定", "Top10 平均综合分", "R1xday 为正比例", "R1xday 显著比例", "AMC 为正比例", "AMC 显著比例", "平均 R²", "中位 Max VIF(z)"]
    return html_table(view[cols], cols)


def build_bayes_table(bayes: pd.DataFrame) -> str:
    view = bayes.copy()
    for col in [
        "share_main_r1xday_prob_gt_095",
        "share_main_amc_prob_gt_095",
        "share_interaction_prob_gt_095",
    ]:
        view[col] = view[col].map(fmt_pct_share)
    for col in ["mean_main_r1xday", "mean_main_amc", "mean_interaction"]:
        view[col] = view[col].map(fmt_num)
    view = view.rename(
        columns={
            "variant_label": "贝叶斯变体",
            "mean_main_r1xday": "R1xday 后验均值",
            "mean_main_amc": "AMC 后验均值",
            "share_main_r1xday_prob_gt_095": "R1xday P(β>0)≥0.95 占比",
            "share_main_amc_prob_gt_095": "AMC P(β>0)≥0.95 占比",
            "mean_interaction": "交互项后验均值",
            "share_interaction_prob_gt_095": "交互项 P(β>0)≥0.95 占比",
        }
    )
    cols = [
        "贝叶斯变体",
        "R1xday 后验均值",
        "AMC 后验均值",
        "R1xday P(β>0)≥0.95 占比",
        "AMC P(β>0)≥0.95 占比",
        "交互项后验均值",
        "交互项 P(β>0)≥0.95 占比",
    ]
    return html_table(view[cols], cols)


def build_top_lists(province_average: pd.DataFrame, latest: pd.DataFrame) -> dict[str, pd.DataFrame]:
    avg_main = province_average[
        (province_average["role_id"] == "main_model") & (province_average["scenario_id"] == "all_climate_to_baseline")
    ].copy()
    latest_main = latest[
        (latest["role_id"] == "main_model") & (latest["scenario_id"] == "all_climate_to_baseline")
    ].copy()

    def prep(df: pd.DataFrame, ascending: bool) -> pd.DataFrame:
        out = df.sort_values("actual_minus_counterfactual_mean", ascending=ascending).head(8).copy()
        out["actual_minus_counterfactual_mean"] = out["actual_minus_counterfactual_mean"].map(fmt_signed)
        out["relative_change_pct_mean"] = out["relative_change_pct_mean"].map(lambda x: fmt_signed(x, 1))
        return out[["Province", "actual_minus_counterfactual_mean", "relative_change_pct_mean"]].rename(
            columns={
                "Province": "省份",
                "actual_minus_counterfactual_mean": "差值",
                "relative_change_pct_mean": "相对变化率(%)",
            }
        )

    return {
        "avg_pos": prep(avg_main, ascending=False),
        "avg_neg": prep(avg_main, ascending=True),
        "latest_pos": prep(latest_main, ascending=False),
        "latest_neg": prep(latest_main, ascending=True),
    }


def build_summary_cards(fe: pd.DataFrame, selected: pd.DataFrame, overall: pd.DataFrame, province_average: pd.DataFrame, latest: pd.DataFrame) -> str:
    top_fe = fe.sort_values("fe_rank_by_top10").iloc[0]
    main = selected[selected["role_id"] == "main_model"].iloc[0]
    all_climate = overall[overall["scenario_label"] == "所有气候变量恢复基准"]
    r1_only = overall[overall["scenario_label"] == "仅 R1xday 恢复基准"]
    temp_only = overall[overall["scenario_label"] == "仅温度变量恢复基准"]

    avg_main = province_average[
        (province_average["role_id"] == "main_model") & (province_average["scenario_id"] == "all_climate_to_baseline")
    ]
    latest_main = latest[
        (latest["role_id"] == "main_model") & (latest["scenario_id"] == "all_climate_to_baseline")
    ]

    return f"""
    <div class="summary-grid">
      <article class="summary-card accent-red">
        <span class="eyebrow">主推 FE</span>
        <h3>{escape(str(top_fe['fe_label']))}</h3>
        <p>Top10 平均综合分 {fmt_num(top_fe['top10_mean_score'])}，R1xday 为正比例 {fmt_pct_share(top_fe['share_r1xday_positive'])}。</p>
      </article>
      <article class="summary-card accent-blue">
        <span class="eyebrow">主模型</span>
        <h3>{escape(str(main['scheme_id']))}</h3>
        <p>R1xday = {fmt_num(main['coef_R1xday'])}，AMC = {fmt_num(main['coef_AMC'])}，二者都在 Year FE 下保留正向信号。</p>
      </article>
      <article class="summary-card accent-green">
        <span class="eyebrow">最稳结果</span>
        <h3>气候总体负担为正</h3>
        <p>“所有气候变量恢复基准”情景下，{int((all_climate['actual_minus_counterfactual_mean'] > 0).sum())}/{all_climate.shape[0]} 个入选模型为正差值。</p>
      </article>
      <article class="summary-card accent-gold">
        <span class="eyebrow">最敏感结果</span>
        <h3>温度单独通道</h3>
        <p>“仅温度变量恢复基准”情景下，{int((temp_only['actual_minus_counterfactual_mean'] > 0).sum())}/{temp_only.shape[0]} 个模型为正，方向受代理变量与 FE 设定影响明显。</p>
      </article>
      <article class="summary-card">
        <span class="eyebrow">R1xday 情景</span>
        <h3>{int((r1_only['actual_minus_counterfactual_mean'] > 0).sum())}/{r1_only.shape[0]} 模型为正</h3>
        <p>Year FE 的 3 个模型都为正，但双向 FE 近似归零，说明极端降雨通道存在但更保守的识别会显著压缩它。</p>
      </article>
      <article class="summary-card">
        <span class="eyebrow">空间异质性</span>
        <h3>{int((avg_main['actual_minus_counterfactual_mean'] > 0).sum())}/31 省长期平均为正</h3>
        <p>到 2023 年时只剩 {int((latest_main['actual_minus_counterfactual_mean'] > 0).sum())}/31 省为正，说明全国平均不代表所有省份同步变化。</p>
      </article>
    </div>
    """


def build_interpretation_blocks(selected: pd.DataFrame, overall: pd.DataFrame, province_average: pd.DataFrame, latest: pd.DataFrame) -> str:
    main = selected[selected["role_id"] == "main_model"].iloc[0]
    strict = selected[selected["role_id"] == "robust_strict_fe"].iloc[0]
    all_climate = overall[overall["scenario_label"] == "所有气候变量恢复基准"].sort_values(
        "actual_minus_counterfactual_mean", ascending=False
    )
    r1_only = overall[overall["scenario_label"] == "仅 R1xday 恢复基准"].sort_values(
        "actual_minus_counterfactual_mean", ascending=False
    )
    temp_only = overall[overall["scenario_label"] == "仅温度变量恢复基准"].sort_values(
        "actual_minus_counterfactual_mean", ascending=False
    )

    avg_main = province_average[
        (province_average["role_id"] == "main_model") & (province_average["scenario_id"] == "all_climate_to_baseline")
    ]
    latest_main = latest[
        (latest["role_id"] == "main_model") & (latest["scenario_id"] == "all_climate_to_baseline")
    ]
    pos_avg = ", ".join(avg_main.sort_values("actual_minus_counterfactual_mean", ascending=False).head(5)["Province"].tolist())
    neg_avg = ", ".join(avg_main.sort_values("actual_minus_counterfactual_mean", ascending=True).head(5)["Province"].tolist())
    pos_latest = ", ".join(latest_main.sort_values("actual_minus_counterfactual_mean", ascending=False).head(5)["Province"].tolist())
    neg_latest = ", ".join(latest_main.sort_values("actual_minus_counterfactual_mean", ascending=True).head(5)["Province"].tolist())

    return f"""
    <div class="insight-grid">
      <article class="insight-card">
        <h3>1. 主模型为何能承接正文</h3>
        <p><strong>{escape(str(main['scheme_id']))}</strong> 在 Year FE 下同时保留了 <code>R1xday</code> 和 <code>抗菌药物使用强度</code> 的正向信号，最适合承接“气候相关暴露在既有抗菌药物使用背景下提高 AMR 风险”的主叙事。</p>
      </article>
      <article class="insight-card">
        <h3>2. 哪些结果较稳</h3>
        <p>“所有气候变量恢复基准”情景在 4 个入选模型中全部为正差值，范围为 {fmt_signed(all_climate['actual_minus_counterfactual_mean'].min())} 到 {fmt_signed(all_climate['actual_minus_counterfactual_mean'].max())}。总体气候负担方向较稳。</p>
      </article>
      <article class="insight-card">
        <h3>3. 哪些结果更敏感</h3>
        <p>“仅 R1xday 恢复基准”在 3 个 Year FE 模型中都为正，但双向 FE 的差值仅为 {fmt_signed(r1_only[r1_only['role_label']=='稳健性模型 3']['actual_minus_counterfactual_mean'].iloc[0])}；“仅温度变量恢复基准”在主模型中接近 0，但在另外两个 Year FE 稳健性模型中明显为正。</p>
      </article>
      <article class="insight-card">
        <h3>4. 双向 FE 应如何解释</h3>
        <p>双向 FE 口径下，主模型同变量集的 <code>R1xday</code> 系数已收缩为 {fmt_num(strict['coef_R1xday'])}，说明它更适合作为保守下界，而不是正文中的主量化入口。</p>
      </article>
      <article class="insight-card wide">
        <h3>5. 分省异质性如何写</h3>
        <p>在主模型主情景下，长期平均正差值较高的省份主要包括 <strong>{escape(pos_avg)}</strong>；负差值较高的省份主要包括 <strong>{escape(neg_avg)}</strong>。到 2023 年，正差值较高的省份主要转向 <strong>{escape(pos_latest)}</strong>，负差值较高的省份则集中在 <strong>{escape(neg_latest)}</strong>。这说明全国平均结果可以支持总体 burden 的存在，但空间分布具有明显异质性。</p>
      </article>
    </div>
    """


def build_top_tables(top_lists: dict[str, pd.DataFrame]) -> str:
    sections = [
        ("长期平均正差值最高的省份", top_lists["avg_pos"]),
        ("长期平均负差值最高的省份", top_lists["avg_neg"]),
        ("2023 年正差值最高的省份", top_lists["latest_pos"]),
        ("2023 年负差值最高的省份", top_lists["latest_neg"]),
    ]
    html_parts = []
    for title, df in sections:
        html_parts.append(
            f"""
            <div class="mini-table-card">
              <h3>{escape(title)}</h3>
              {html_table(df, list(df.columns), classes="data-table compact")}
            </div>
            """
        )
    return "".join(html_parts)


def json_records(df: pd.DataFrame) -> str:
    return json.dumps(df.to_dict(orient="records"), ensure_ascii=False)


def build_focus_coefficient_records(selected: pd.DataFrame, coef_df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, model in selected.iterrows():
        predictors = ["R1xday", "抗菌药物使用强度"]
        var_list = str(model["variables"]).split(" | ")
        temp_vars = [var for var in var_list if var in TEMPERATURE_VARS]
        predictors.extend(temp_vars[:1])
        fe_spec = FE_LABEL_TO_SPEC[str(model["fe_label"])]
        sub = coef_df[(coef_df["scheme_id"] == model["scheme_id"]) & (coef_df["fe_spec"] == fe_spec)]
        for predictor in predictors:
            pick = sub[sub["predictor"] == predictor]
            if pick.empty:
                continue
            row = pick.iloc[0]
            rows.append(
                {
                    "model_id": model["model_id"],
                    "predictor": predictor,
                    "coef": float(row["coef"]),
                    "p_value": float(row["p_value"]),
                    "ci_low": float(row["ci_low"]),
                    "ci_high": float(row["ci_high"]),
                }
            )
    return rows


def build_model_equation_records(selected: pd.DataFrame, coef_df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, model in selected.iterrows():
        var_list = str(model["variables"]).split(" | ")
        fe_spec = FE_LABEL_TO_SPEC[str(model["fe_label"])]
        sub = coef_df[(coef_df["scheme_id"] == model["scheme_id"]) & (coef_df["fe_spec"] == fe_spec)].copy()
        order_map = {var: idx for idx, var in enumerate(var_list)}
        sub = sub[sub["predictor"].isin(order_map)].copy()
        if sub.empty:
            continue
        sub["order"] = sub["predictor"].map(order_map)
        sub = sub.sort_values("order")
        for _, row in sub.iterrows():
            rows.append(
                {
                    "model_id": model["model_id"],
                    "predictor": row["predictor"],
                    "coef": float(row["coef"]),
                    "p_value": float(row["p_value"]),
                    "order": int(row["order"]),
                }
            )
    return rows


def build_dashboard_html(outcome: str, inputs: dict[str, pd.DataFrame | Path]) -> str:
    fe = inputs["fe"]
    selected = inputs["selected"]
    bayes = inputs["bayes"]
    panel_predictions = inputs["panel_predictions"]
    overall = inputs["overall"]
    yearly = inputs["yearly"]
    province_average = inputs["province_average"]
    latest = inputs["latest"]
    coefficients = inputs["coefficients"]

    top_lists = build_top_lists(province_average, latest)
    summary_cards = build_summary_cards(fe, selected, overall, province_average, latest)
    selected_model_cards = build_selected_model_cards(selected)
    interpretation_blocks = build_interpretation_blocks(selected, overall, province_average, latest)
    key_coef_table = build_key_coef_table(selected, coefficients)
    fe_table = build_fe_table(fe)
    bayes_table = build_bayes_table(bayes)
    overall_matrix = build_overall_matrix(overall)
    top_tables = build_top_tables(top_lists)
    focus_coefficient_records = build_focus_coefficient_records(selected, coefficients)
    model_equation_records = build_model_equation_records(selected, coefficients)
    default_focus_model_id = str(
        selected.loc[selected["role_id"] == "main_model", "model_id"].iloc[0]
        if (selected["role_id"] == "main_model").any()
        else selected.iloc[0]["model_id"]
    )
    baseline_text = "2014"
    if isinstance(panel_predictions, pd.DataFrame) and not panel_predictions.empty and "baseline_years" in panel_predictions.columns:
        baseline_text = str(panel_predictions["baseline_years"].dropna().astype(str).iloc[0])
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(outcome)} 反事实推演结果页</title>
  <style>
    :root {{
      --bg: #f5f0e8; --panel: rgba(255,255,255,0.88); --ink: #1f2a30; --muted: #5f6b72;
      --line: #d9cec0; --accent: #b5523b; --accent-2: #2f6c7a; --accent-3: #688f58; --accent-4: #c38f2b;
      --shadow: 0 18px 48px rgba(61,46,34,0.12); --radius: 24px;
    }}
    * {{ box-sizing: border-box; }} body {{ margin:0; color:var(--ink); background:linear-gradient(180deg,#faf6ef 0%,var(--bg) 100%); font-family:"Segoe UI","Microsoft YaHei",sans-serif; line-height:1.65; }}
    a {{ color: var(--accent-2); text-decoration:none; }} .page {{ width:min(1280px, calc(100vw - 40px)); margin:0 auto; padding:28px 0 56px; }}
    .topbar {{ position:sticky; top:12px; z-index:50; display:flex; justify-content:space-between; align-items:center; gap:16px; padding:14px 20px; margin-bottom:20px; border:1px solid rgba(255,255,255,0.5); border-radius:999px; background:rgba(250,246,239,0.86); backdrop-filter:blur(14px); box-shadow:var(--shadow); }}
    .brand {{ display:flex; align-items:center; gap:12px; font-weight:700; }} .brand-badge {{ width:38px; height:38px; display:grid; place-items:center; border-radius:14px; background:linear-gradient(135deg,var(--accent),#d88952); color:#fff; }}
    .nav {{ display:flex; flex-wrap:wrap; gap:10px 16px; font-size:14px; }} .nav a {{ padding:6px 10px; border-radius:999px; color:var(--muted); }} .nav a:hover {{ background:rgba(181,82,59,0.08); color:var(--ink); }}
    .hero {{ display:grid; grid-template-columns:1.35fr 1fr; gap:22px; align-items:stretch; margin-bottom:24px; }}
    .hero-main,.hero-side,section,.explorer-panel {{ background:var(--panel); border:1px solid rgba(255,255,255,0.65); border-radius:var(--radius); box-shadow:var(--shadow); }}
    .hero-main {{ padding:34px; position:relative; overflow:hidden; }} .hero-side {{ padding:24px; display:grid; gap:14px; align-content:start; }}
    .eyebrow {{ display:inline-flex; align-items:center; gap:8px; font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:var(--accent); font-weight:700; }}
    h1 {{ margin:12px 0 14px; font-size:clamp(30px,4vw,48px); line-height:1.08; }} h2 {{ margin:0 0 14px; font-size:24px; }} h3 {{ margin:0 0 10px; font-size:18px; }}
    p {{ margin:0 0 12px; }} .muted {{ color:var(--muted); }}
    .hero-notes {{ display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:12px; margin-top:20px; }} .note {{ padding:14px 16px; border-radius:18px; background:rgba(255,255,255,0.78); border:1px solid rgba(217,206,192,0.9); }}
    .summary-grid,.model-grid,.insight-grid,.chart-grid,.mini-grid,.explorer-controls,.focus-grid,.focus-toolbar,.focus-stat-grid,.equation-grid {{ display:grid; gap:16px; }}
    .summary-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }} .model-grid,.chart-grid,.mini-grid,.focus-grid,.equation-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .insight-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .focus-toolbar {{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }} .focus-stat-grid {{ grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .summary-card,.model-card,.insight-card,.mini-table-card,.chart-card,.focus-panel,.equation-card {{ padding:20px; border-radius:22px; background:rgba(255,255,255,0.82); border:1px solid rgba(217,206,192,0.9); }}
    .insight-card.wide,.focus-panel.wide {{ grid-column:1 / -1; }} .accent-red {{ border-top:5px solid var(--accent); }} .accent-blue {{ border-top:5px solid var(--accent-2); }} .accent-green {{ border-top:5px solid var(--accent-3); }} .accent-gold {{ border-top:5px solid var(--accent-4); }}
    section {{ padding:24px; margin-bottom:22px; }} .section-head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:18px; }} .section-head p {{ max-width:760px; }} .section-grid-2 {{ display:grid; grid-template-columns:1.1fr 0.9fr; gap:18px; }}
    .card-top {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:8px; }} .chip {{ padding:6px 10px; border-radius:999px; background:rgba(47,108,122,0.08); color:var(--accent-2); font-size:12px; font-weight:700; }}
    .metric-row {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:14px 0; }} .metric-row div,.focus-stat {{ padding:10px 12px; border-radius:14px; background:rgba(245,240,232,0.72); border:1px solid rgba(217,206,192,0.6); }} .metric-row strong,.metric-row span,.focus-stat strong,.focus-stat span {{ display:block; }} .metric-row span,.focus-stat span {{ color:var(--muted); font-size:14px; }}
    details summary {{ cursor:pointer; color:var(--accent-2); font-weight:700; }} .var-list {{ margin-top:10px; color:var(--muted); word-break:break-word; }} .var-list span {{ color:rgba(95,107,114,0.55); }}
    .data-table {{ width:100%; border-collapse:collapse; font-size:14px; background:rgba(255,255,255,0.75); }} .data-table th,.data-table td {{ padding:12px 14px; border-bottom:1px solid rgba(217,206,192,0.7); text-align:left; vertical-align:top; }} .data-table thead th {{ background:#f8f2ea; color:var(--muted); font-size:12px; letter-spacing:0.04em; text-transform:uppercase; }} .data-table.compact th,.data-table.compact td {{ padding:10px 12px; font-size:13px; }} .data-table tbody tr.is-current td {{ background:rgba(181,82,59,0.07); }}
    .table-wrap {{ overflow:auto; border-radius:18px; border:1px solid rgba(217,206,192,0.65); }}
    .chart-card img {{ width:100%; border-radius:16px; border:1px solid rgba(217,206,192,0.8); background:#fff; }} .chart-card p {{ margin-top:12px; color:var(--muted); font-size:14px; }}
    .explorer-panel {{ padding:24px; }} .explorer-controls {{ grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:14px; }}
    .control label {{ display:block; margin-bottom:6px; font-size:12px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em; }} .control select,.control input {{ width:100%; padding:11px 12px; border-radius:14px; border:1px solid rgba(217,206,192,0.9); background:#fff; color:var(--ink); font:inherit; }}
    .focus-layout {{ display:grid; gap:16px; }} .focus-panel h3 + p {{ color:var(--muted); }} .focus-chart {{ width:100%; height:auto; display:block; margin-top:8px; border-radius:18px; background:#fff; border:1px solid rgba(217,206,192,0.75); }} .focus-legend {{ display:flex; flex-wrap:wrap; gap:16px; margin-top:12px; color:var(--muted); font-size:13px; }} .legend-item {{ display:inline-flex; align-items:center; gap:8px; }} .legend-dot {{ width:10px; height:10px; border-radius:999px; display:inline-block; }} .focus-jump {{ margin-top:14px; padding:10px 12px; border:none; border-radius:14px; background:rgba(47,108,122,0.12); color:var(--accent-2); font:inherit; font-weight:700; cursor:pointer; }} .focus-jump:hover {{ background:rgba(47,108,122,0.18); }} .focus-empty {{ padding:14px 16px; border-radius:16px; background:rgba(245,240,232,0.72); color:var(--muted); }} .formula-block {{ margin-top:12px; padding:14px 16px; border-radius:16px; background:#fbf8f2; border:1px solid rgba(217,206,192,0.8); font-family:"Cascadia Mono","Consolas","Courier New",monospace; font-size:14px; line-height:1.8; white-space:normal; overflow:auto; }} .formula-caption {{ margin-top:10px; color:var(--muted); font-size:13px; }} .term-chip {{ display:inline-flex; padding:2px 8px; border-radius:999px; background:rgba(181,82,59,0.10); color:var(--accent); font-size:12px; font-weight:700; margin:0 6px 6px 0; }} .term-chip.is-fixed {{ background:rgba(47,108,122,0.12); color:var(--accent-2); }}
    .footer-links {{ display:flex; flex-wrap:wrap; gap:10px 16px; margin-top:10px; font-size:14px; }} .footer-links a {{ padding:8px 12px; border-radius:999px; background:rgba(47,108,122,0.08); }}
    @media (max-width:1100px) {{ .hero,.section-grid-2,.chart-grid,.model-grid,.insight-grid,.mini-grid,.summary-grid,.explorer-controls,.hero-notes,.focus-grid,.focus-toolbar,.focus-stat-grid,.equation-grid {{ grid-template-columns:1fr; }} .topbar {{ border-radius:24px; }} }}
  </style>
</head>
<body>
  <div class="page">
    <div class="topbar">
      <div class="brand"><div class="brand-badge">CF</div><div><div>AMR 反事实结果页</div><div class="muted" style="font-size:12px;">自动生成于 {escape(generated_at)}</div></div></div>
      <nav class="nav"><a href="#overview">概览</a><a href="#screening">模型筛选</a><a href="#equations">推演方程</a><a href="#focus">单模型分析</a><a href="#figures">图形总览</a><a href="#scenarios">情景比较</a><a href="#province">省级异质性</a><a href="#explorer">结果浏览</a></nav>
    </div>
    <div class="hero" id="overview">
      <div class="hero-main">
        <span class="eyebrow">Counterfactual Dashboard</span>
        <h1>{escape(outcome)} 反事实推演结果与解释</h1>
        <p>这一页把“模型筛选 + 反事实推演 + 结果解释”合在一起展示。逻辑起点不是重新建一个普通回归，而是从你已有的大量固定效应候选模型中先做筛选，再用入选 FE 模型去比较 <strong>actual scenario</strong> 与 <strong>counterfactual benchmark</strong>。</p>
        <p class="muted">当前网页聚焦 <code>AMR_AGG_z</code>。基准期默认取 2014 年，含主模型与 3 个稳健性模型，并串联你已经完成的 FE 与贝叶斯桥接结果。</p>
        <div class="hero-notes">
          <div class="note"><strong>怎么读这页</strong><p>上半页负责“选模型”，下半页负责“定了一个模型之后怎么看”。绝对差值 <code>Actual - Counterfactual</code> 是本页的主解释量。</p></div>
          <div class="note"><strong>这页解决什么问题</strong><p>如果把气候变量恢复到基准状态，中国 AMR 综合风险会下降多少？这个结果在不同模型设定下是否一致？</p></div>
          <div class="note"><strong>结果解读边界</strong><p>全国平均方向可以较稳地支持 climate-related burden，但温度拆分与空间排序对模型设定更敏感。</p></div>
          <div class="note"><strong>与前文衔接</strong><p>单因素负责筛选，固定效应负责主分析，贝叶斯负责桥接，本页负责把筛选后的 FE 模型推进到反事实量化。</p></div>
        </div>
      </div>
      <aside class="hero-side"><div class="section-head" style="margin-bottom:6px;"><div><span class="eyebrow">一页摘要</span><h2 style="margin-top:8px;">先看结论</h2></div></div>{summary_cards}</aside>
    </div>
    <section id="screening"><div class="section-head"><div><span class="eyebrow">Model Screening</span><h2>模型筛选结论</h2><p>这一步先比较三类 FE 设定的整体表现，再明确为什么 Year FE 适合作正文反事实入口，为什么双向 FE 更适合作为保守敏感性检验。模型卡片底部按钮可直接跳转到下方单模型分析。</p></div></div><div class="section-grid-2"><div class="table-wrap">{fe_table}</div><div class="table-wrap">{bayes_table}</div></div><div style="height:18px;"></div><div class="model-grid">{selected_model_cards}</div><div style="height:18px;"></div><div class="table-wrap">{key_coef_table}</div></section>
    <section id="equations"><div class="section-head"><div><span class="eyebrow">Counterfactual Equations</span><h2>反事实推演方程</h2><p>这一部分把“模型怎么写成方程”补完整。这里不是重新建一个普通 OLS，而是沿用已筛选固定效应模型的估计系数与固定效应项，再把指定气候变量替换为基准期值，得到反事实预测。</p></div></div><div class="equation-grid"><article class="equation-card"><h3>1. 固定效应主方程</h3><div class="formula-block">y_it = Σ_k (β_k · X_kit^(z)) + FE_i + FE_t + ε_it</div><p class="formula-caption">其中，<code>y_it</code> 是 <code>AMR_AGG_z</code>；<code>X_kit^(z)</code> 是进入当前模型的标准化解释变量；<code>FE_i</code> 表示省份固定效应，<code>FE_t</code> 表示年份固定效应。对于仅年份固定效应模型，仅保留 <code>FE_t</code>；对于双向固定效应模型，同时保留二者。本页当前输出的基准期是 <strong>{escape(baseline_text)}</strong>。</p></article><article class="equation-card"><h3>2. 反事实替换方程</h3><div class="formula-block">ŷ_it^cf(s) = Σ_(k∉S_s) (β̂_k · X_kit,actual^(z)) + Σ_(k∈S_s) (β̂_k · X_ki,base^(z)) + FÊ_i + FÊ_t</div><p class="formula-caption"><code>S_s</code> 是情景 <code>s</code> 下被恢复到基准期的变量集合，例如“仅 R1xday 恢复基准”或“所有气候变量恢复基准”。<code>X_ki,base</code> 取该省在基准期内的均值，其他变量保持实际观测值不变。</p></article><article class="equation-card"><h3>3. 结果差值与相对变化</h3><div class="formula-block">Δ_it^(s) = ŷ_it^actual - ŷ_it^cf(s)\nRelChange_it^(s) = 100 × Δ_it^(s) / |ŷ_it^cf(s)|</div><p class="formula-caption">当 <code>Δ_it^(s) &gt; 0</code> 时，表示相对于“恢复基准”的世界，实际气候轨迹对应更高的预测 AMR。网页中的全国年度平均、分省长期平均和最新年份结果，都是在这个差值基础上继续汇总得到的。</p></article><article class="equation-card"><h3>4. 汇总指标怎么来</h3><div class="formula-block">全国年度平均:  Δ̄_t^(s) = (1 / N_t) · Σ_i Δ_it^(s)\n分省长期平均:  Δ̄_i^(s) = (1 / T_i) · Σ_t Δ_it^(s)</div><p class="formula-caption">所以这页上你看到的时间序列图、分省地图和模型比较图，实质上都是对 <code>Δ_it^(s)</code> 在不同维度上的再汇总。</p></article></div></section>
    <section id="focus"><div class="section-head"><div><span class="eyebrow">Single Model View</span><h2>单模型聚焦分析</h2><p>如果上面的部分是在帮你“选模型”，这里就是帮你“定下一个模型后只看它”。切换模型后，页面不仅展示该模型下的全国情景结果、年度趋势、关键系数和分省异质性，也会把这个模型的具体估计方程展开给你看。</p></div></div><div class="focus-layout"><div class="focus-toolbar"><div class="control"><label for="focusModelSelect">当前模型</label><select id="focusModelSelect"></select></div><div class="control"><label for="focusScenarioSelect">当前情景</label><select id="focusScenarioSelect"></select></div></div><div class="focus-grid"><article class="focus-panel" id="focusModelMeta"></article><article class="focus-panel" id="focusInterpretation"></article></div><div class="focus-grid"><article class="focus-panel" id="focusScenarioTable"></article><article class="focus-panel" id="focusEquation"></article></div><div class="focus-grid"><article class="focus-panel wide" id="focusCoefficientTable"></article></div><div class="focus-grid"><article class="focus-panel wide" id="focusYearlyTrend"></article></div><div class="focus-grid"><article class="focus-panel" id="focusProvinceAverage"></article><article class="focus-panel" id="focusProvinceLatest"></article></div></div></section>
    <section><div class="section-head"><div><span class="eyebrow">Interpretation</span><h2>整体结果分析</h2><p>这里把“哪些结论较稳、哪些对模型设定敏感、R1xday 和抗菌药物使用强度在主模型里处于什么位置”直接写成可用于结果段落的解释。</p></div></div>{interpretation_blocks}</section>
    <section id="figures"><div class="section-head"><div><span class="eyebrow">Figures</span><h2>图形总览</h2><p>四张图对应四个层面：主模型全国时间序列、2023 年模型比较、不同情景的全国平均对比，以及主情景下的分省地图。</p></div></div><div class="chart-grid"><article class="chart-card"><img src="figures/national_yearly_main_model.png" alt="主模型全国年度时间序列图" /><p>主模型里，“所有气候变量恢复基准”和“仅 R1xday 恢复基准”大多数年份给出正差值；温度单独情景则在主模型里接近于零。</p></article><article class="chart-card"><img src="figures/model_comparison_heatmap_latest_year.png" alt="不同模型比较热图" /><p>2023 年的热图显示：Year FE 稳健性模型普遍给出更大的正向差值，而双向 FE 显著收缩。</p></article><article class="chart-card"><img src="figures/scenario_comparison_bar.png" alt="不同情景比较柱状图" /><p>柱状图最适合看“哪种情景最稳、哪种情景最敏感”。总体气候和 R1xday 通道更稳，温度单独通道更依赖模型设定。</p></article><article class="chart-card"><img src="figures/province_map_main_model_latest_year.png" alt="分省地图" /><p>地图展示的是 2023 年主模型主情景下的省级差值。可以看到全国平均为正并不意味着所有省份都同方向。</p></article></div></section>
    <section id="scenarios"><div class="section-head"><div><span class="eyebrow">Scenario Comparison</span><h2>情景比较与稳健性</h2><p>表中展示的是全国平均的 <code>Actual - Counterfactual</code>。正值表示：相对于“恢复基准”的世界，实际气候轨迹对应更高的预测 AMR。</p></div></div><div class="table-wrap">{overall_matrix}</div></section>
    <section id="province"><div class="section-head"><div><span class="eyebrow">Province Heterogeneity</span><h2>省级异质性</h2><p>主模型在“所有气候变量恢复基准”情景下，长期平均有明显的正差值省份集群，但 2023 年的排序已经发生变化，说明空间分布存在动态性。</p></div></div><div class="mini-grid">{top_tables}</div></section>
    <section id="explorer"><div class="section-head"><div><span class="eyebrow">Explorer</span><h2>结果浏览器</h2><p>如果你想继续看某个模型、某个情景、某个年份的详细结果，这里可以直接筛选并浏览完整表。</p></div></div><div class="explorer-panel"><div class="explorer-controls"><div class="control"><label for="datasetSelect">数据层级</label><select id="datasetSelect"><option value="province_average">分省长期平均</option><option value="latest">2023 年分省结果</option><option value="yearly">全国年度结果</option></select></div><div class="control"><label for="roleSelect">模型</label><select id="roleSelect"></select></div><div class="control"><label for="scenarioSelect">情景</label><select id="scenarioSelect"></select></div><div class="control"><label for="searchInput">搜索省份 / 年份</label><input id="searchInput" type="text" placeholder="输入省份名或年份" /></div></div><div class="table-wrap"><table class="data-table" id="explorerTable"><thead></thead><tbody></tbody></table></div></div></section>
    <section><div class="section-head"><div><span class="eyebrow">Files</span><h2>原始结果文件</h2><p>网页中的表和图都直接来自当前项目输出，下面这些链接可以继续追到 CSV、说明文档和图片源文件。</p></div></div><div class="footer-links"><a href="model_screening/selected_models.csv">selected_models.csv</a><a href="model_screening/fe_spec_comparison.csv">fe_spec_comparison.csv</a><a href="counterfactual_outputs/national_overall.csv">national_overall.csv</a><a href="counterfactual_outputs/national_yearly.csv">national_yearly.csv</a><a href="counterfactual_outputs/province_average.csv">province_average.csv</a><a href="counterfactual_outputs/latest_year_province.csv">latest_year_province.csv</a><a href="selection_and_writeup_notes.md">selection_and_writeup_notes.md</a></div></section>
  </div>
  <script>
    const selectedModels = {json_records(selected)};
    const overallRecords = {json_records(overall)};
    const provinceAverage = {json_records(province_average)};
    const latestYear = {json_records(latest)};
    const yearly = {json_records(yearly)};
    const focusCoefficientRecords = {json.dumps(focus_coefficient_records, ensure_ascii=False)};
    const modelEquationRecords = {json.dumps(model_equation_records, ensure_ascii=False)};
    const defaultFocusModelId = {json.dumps(default_focus_model_id, ensure_ascii=False)};
    const temperatureVars = new Set(["主要城市平均气温", "省平均气温", "TA（°C）"]);
    const hydroVars = new Set(["R1xday", "R5xday", "主要城市降水量", "省平均降水", "PA（%）"]);
    const climateVars = new Set([...temperatureVars, ...hydroVars]);
    const datasets = {{
      province_average: {{ rows: provinceAverage, key: "Province", columns: ["Province", "actual_pred_mean", "counterfactual_pred_mean", "actual_minus_counterfactual_mean", "relative_change_pct_mean"] }},
      latest: {{ rows: latestYear, key: "Province", columns: ["Province", "actual_pred_mean", "counterfactual_pred_mean", "actual_minus_counterfactual_mean", "relative_change_pct_mean"] }},
      yearly: {{ rows: yearly, key: "Year", columns: ["Year", "actual_pred_mean", "counterfactual_pred_mean", "actual_minus_counterfactual_mean", "relative_change_pct_mean"] }}
    }};
    const labels = {{ Province:"省份", Year:"年份", actual_pred_mean:"实际预测值", counterfactual_pred_mean:"反事实预测值", actual_minus_counterfactual_mean:"差值", relative_change_pct_mean:"相对变化率(%)" }};
    const datasetSelect = document.getElementById("datasetSelect");
    const roleSelect = document.getElementById("roleSelect");
    const scenarioSelect = document.getElementById("scenarioSelect");
    const searchInput = document.getElementById("searchInput");
    const table = document.getElementById("explorerTable");
    const focusModelSelect = document.getElementById("focusModelSelect");
    const focusScenarioSelect = document.getElementById("focusScenarioSelect");
    const focusModelMeta = document.getElementById("focusModelMeta");
    const focusInterpretation = document.getElementById("focusInterpretation");
    const focusScenarioTable = document.getElementById("focusScenarioTable");
    const focusEquation = document.getElementById("focusEquation");
    const focusCoefficientTable = document.getElementById("focusCoefficientTable");
    const focusYearlyTrend = document.getElementById("focusYearlyTrend");
    const focusProvinceAverage = document.getElementById("focusProvinceAverage");
    const focusProvinceLatest = document.getElementById("focusProvinceLatest");
    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}
    function uniqueValues(rows, field) {{ return [...new Set(rows.map(row => row[field]))].filter(Boolean); }}
    function fmtNum(value, digits = 3) {{
      const num = Number(value);
      return Number.isFinite(num) ? num.toFixed(digits) : "—";
    }}
    function fmtSigned(value, digits = 3) {{
      const num = Number(value);
      if (!Number.isFinite(num)) return "—";
      return `${{num >= 0 ? "+" : ""}}${{num.toFixed(digits)}}`;
    }}
    function fmtPct(value, digits = 1) {{
      const num = Number(value);
      return Number.isFinite(num) ? `${{num.toFixed(digits)}}%` : "—";
    }}
    function fmtP(value) {{
      const num = Number(value);
      if (!Number.isFinite(num)) return "—";
      if (num < 0.0001) return "<0.0001";
      return num.toFixed(4);
    }}
    function setOptions(select, options, preferredValue = null) {{
      const normalized = options.map(option => typeof option === "string" ? {{ value: option, label: option }} : option);
      const fallback = normalized[0] ? normalized[0].value : "";
      const current = preferredValue ?? select.value ?? fallback;
      select.innerHTML = normalized.map(option => `<option value="${{escapeHtml(option.value)}}">${{escapeHtml(option.label)}}</option>`).join("");
      const values = normalized.map(option => option.value);
      select.value = values.includes(current) ? current : fallback;
    }}
    function getModelMeta(modelId) {{
      return selectedModels.find(row => row.model_id === modelId);
    }}
    function getModelOverall(modelId) {{
      return overallRecords.filter(row => row.model_id === modelId);
    }}
    function getModelYearly(modelId, scenarioId) {{
      return yearly.filter(row => row.model_id === modelId && row.scenario_id === scenarioId).sort((a, b) => Number(a.Year) - Number(b.Year));
    }}
    function getModelVariables(model) {{
      return String(model.variables || "").split(" | ").filter(Boolean);
    }}
    function getScenarioVariableNames(model, scenarioId) {{
      const variables = getModelVariables(model);
      if (scenarioId === "all_climate_to_baseline") return variables.filter(variable => climateVars.has(variable));
      if (scenarioId === "r1xday_to_baseline") return variables.filter(variable => variable === "R1xday");
      if (scenarioId === "temperature_to_baseline") return variables.filter(variable => temperatureVars.has(variable));
      if (scenarioId === "r1xday_plus_temperature_to_baseline") {{
        return variables.filter(variable => variable === "R1xday" || temperatureVars.has(variable));
      }}
      return [];
    }}
    function getFeTermText(feLabel) {{
      if (feLabel === "Province: No / Year: Yes") return "年份固定效应 FE_t";
      if (feLabel === "Province: Yes / Year: No") return "省份固定效应 FE_i";
      if (feLabel === "Province: Yes / Year: Yes") return "省份固定效应 FE_i + 年份固定效应 FE_t";
      return "固定效应项";
    }}
    function getProvinceRows(dataset, modelId, scenarioId) {{
      return dataset
        .filter(row => row.model_id === modelId && row.scenario_id === scenarioId)
        .slice()
        .sort((a, b) => Number(b.actual_minus_counterfactual_mean) - Number(a.actual_minus_counterfactual_mean));
    }}
    function syncFilters() {{
      const dataset = datasets[datasetSelect.value];
      const roleValues = uniqueValues(dataset.rows, "role_label");
      setOptions(roleSelect, roleValues);
      const scenarioValues = uniqueValues(dataset.rows.filter(row => row.role_label === roleSelect.value), "scenario_label");
      setOptions(scenarioSelect, scenarioValues);
    }}
    function renderTable() {{
      const dataset = datasets[datasetSelect.value];
      const searchText = searchInput.value.trim().toLowerCase();
      const filtered = dataset.rows
        .filter(row => row.role_label === roleSelect.value)
        .filter(row => row.scenario_label === scenarioSelect.value)
        .filter(row => !searchText || String(row[dataset.key]).toLowerCase().includes(searchText))
        .sort((a, b) => Number(b.actual_minus_counterfactual_mean ?? 0) - Number(a.actual_minus_counterfactual_mean ?? 0));
      const columns = [dataset.key].concat(dataset.columns.filter(col => col !== dataset.key));
      table.querySelector("thead").innerHTML = `<tr>${{columns.map(col => `<th>${{labels[col] || col}}</th>`).join("")}}</tr>`;
      table.querySelector("tbody").innerHTML = filtered.map(row => `<tr>${{columns.map(col => typeof row[col] === "number" ? `<td>${{col === "relative_change_pct_mean" ? fmtPct(row[col], 1) : fmtNum(row[col], 3)}}</td>` : `<td>${{escapeHtml(row[col] ?? "—")}}</td>`).join("")}}</tr>`).join("");
    }}
    function syncFocusScenarioOptions(preferredScenarioId = null) {{
      const modelRows = getModelOverall(focusModelSelect.value);
      const options = modelRows.map(row => ({{ value: row.scenario_id, label: row.scenario_label }}));
      const fallback = options.some(option => option.value === "all_climate_to_baseline") ? "all_climate_to_baseline" : (options[0] ? options[0].value : "");
      setOptions(focusScenarioSelect, options, preferredScenarioId ?? fallback);
    }}
    function buildCurrentScenarioTable(rows, currentScenarioId) {{
      const head = `<thead><tr><th>情景</th><th>实际预测值</th><th>反事实预测值</th><th>差值</th><th>相对变化率(%)</th></tr></thead>`;
      const body = rows.map(row => `<tr class="${{row.scenario_id === currentScenarioId ? "is-current" : ""}}"><td>${{escapeHtml(row.scenario_label)}}</td><td>${{fmtNum(row.actual_pred_mean)}}</td><td>${{fmtNum(row.counterfactual_pred_mean)}}</td><td>${{fmtSigned(row.actual_minus_counterfactual_mean)}}</td><td>${{fmtPct(row.relative_change_pct_mean, 1)}}</td></tr>`).join("");
      return `<table class="data-table compact">${{head}}<tbody>${{body}}</tbody></table>`;
    }}
    function renderFocusModelMeta(model, scenarioRows, currentScenario, avgRows, latestRows) {{
      const positiveScenarioCount = scenarioRows.filter(row => Number(row.actual_minus_counterfactual_mean) > 0).length;
      const avgPositiveCount = avgRows.filter(row => Number(row.actual_minus_counterfactual_mean) > 0).length;
      const latestPositiveCount = latestRows.filter(row => Number(row.actual_minus_counterfactual_mean) > 0).length;
      focusModelMeta.innerHTML = `<div class="card-top"><div><span class="eyebrow">${{escapeHtml(model.role_label)}}</span><h3 style="margin-top:8px;">${{escapeHtml(model.scheme_id)}}</h3></div><span class="chip">${{escapeHtml(model.fe_label)}}</span></div><p>${{escapeHtml(model.reason)}}</p><p class="muted">选择逻辑：${{escapeHtml(model.selection_rule)}}</p><div class="focus-stat-grid"><div class="focus-stat"><strong>R²</strong><span>${{fmtNum(model.r2_model)}}</span></div><div class="focus-stat"><strong>Max VIF</strong><span>${{fmtNum(model.max_vif_z)}}</span></div><div class="focus-stat"><strong>正向情景</strong><span>${{positiveScenarioCount}} / ${{scenarioRows.length}}</span></div><div class="focus-stat"><strong>当前情景差值</strong><span>${{fmtSigned(currentScenario.actual_minus_counterfactual_mean)}}</span></div><div class="focus-stat"><strong>当前相对变化</strong><span>${{fmtPct(currentScenario.relative_change_pct_mean, 1)}}</span></div><div class="focus-stat"><strong>长期平均正差值省份</strong><span>${{avgPositiveCount}} / ${{avgRows.length || 31}}</span></div><div class="focus-stat"><strong>最新年份正差值省份</strong><span>${{latestPositiveCount}} / ${{latestRows.length || 31}}</span></div><div class="focus-stat"><strong>当前情景</strong><span>${{escapeHtml(currentScenario.scenario_label)}}</span></div></div><details><summary>查看变量组合</summary><div class="var-list">${{escapeHtml(model.variables).replaceAll(" | ", "<span> | </span>").replaceAll("\\n", "<br />")}}</div></details>`;
    }}
    function renderFocusInterpretation(model, scenarioRows, currentScenario, avgRows, latestRows) {{
      const strongest = scenarioRows.slice().sort((a, b) => Number(b.actual_minus_counterfactual_mean) - Number(a.actual_minus_counterfactual_mean))[0];
      const weakest = scenarioRows.slice().sort((a, b) => Number(a.actual_minus_counterfactual_mean) - Number(b.actual_minus_counterfactual_mean))[0];
      const topAvg = avgRows[0];
      const bottomAvg = avgRows[avgRows.length - 1];
      const topLatest = latestRows[0];
      const bottomLatest = latestRows[latestRows.length - 1];
      focusInterpretation.innerHTML = `<div class="card-top"><div><span class="eyebrow">Model Reading</span><h3 style="margin-top:8px;">这个模型下应该怎么看</h3></div></div><p>在 <strong>${{escapeHtml(currentScenario.scenario_label)}}</strong> 情景下，全国平均 <code>Actual - Counterfactual</code> 为 <strong>${{fmtSigned(currentScenario.actual_minus_counterfactual_mean)}}</strong>，相对变化为 <strong>${{fmtPct(currentScenario.relative_change_pct_mean, 1)}}</strong>。这表示在该模型设定下，实际气候轨迹对应的预测 AMR 水平相对于“恢复基准”的世界更高。</p><p>在该模型内部，影响最大的情景是 <strong>${{escapeHtml(strongest.scenario_label)}}</strong>（差值 ${{fmtSigned(strongest.actual_minus_counterfactual_mean)}}），影响最弱的是 <strong>${{escapeHtml(weakest.scenario_label)}}</strong>（差值 ${{fmtSigned(weakest.actual_minus_counterfactual_mean)}}）。因此你可以先在同一模型内部判断“哪个通道最重要”，再与其他稳健性模型比较。</p><p>空间上，长期平均正差值最高的省份是 <strong>${{topAvg ? escapeHtml(topAvg.Province) : "—"}}</strong>，最低的是 <strong>${{bottomAvg ? escapeHtml(bottomAvg.Province) : "—"}}</strong>；最新年份正差值最高的省份是 <strong>${{topLatest ? escapeHtml(topLatest.Province) : "—"}}</strong>，最低的是 <strong>${{bottomLatest ? escapeHtml(bottomLatest.Province) : "—"}}</strong>。这能帮助你区分“长期平均格局”和“最新年份格局”是否一致。</p>`;
    }}
    function renderFocusScenarioTable(model, scenarioRows, currentScenarioId) {{
      focusScenarioTable.innerHTML = `<div class="card-top"><div><span class="eyebrow">Scenario Matrix</span><h3 style="margin-top:8px;">该模型下的全部情景结果</h3></div><span class="chip">${{escapeHtml(model.role_label)}}</span></div><p class="muted">这里不混入其他模型，只比较当前模型自身在不同反事实情景下的全国平均结果。浅红色高亮的是当前正在查看的情景。</p><div class="table-wrap">${{buildCurrentScenarioTable(scenarioRows, currentScenarioId)}}</div>`;
    }}
    function renderFocusEquation(model, currentScenario) {{
      const variables = getModelVariables(model);
      const scenarioVars = new Set(getScenarioVariableNames(model, currentScenario.scenario_id));
      const equationRows = modelEquationRecords
        .filter(row => row.model_id === model.model_id)
        .slice()
        .sort((a, b) => Number(a.order) - Number(b.order));
      const termHtml = equationRows.map((row, index) => {{
        const sign = row.coef >= 0 ? (index === 0 ? "" : " + ") : " - ";
        return `${{sign}}${{Math.abs(row.coef).toFixed(3)}} × ${{
          scenarioVars.has(row.predictor)
            ? `${{escapeHtml(row.predictor)}}_base^z`
            : `${{escapeHtml(row.predictor)}}_actual^z`
        }}`;
      }}).join("");
      const actualEquation = equationRows.map((row, index) => {{
        const sign = row.coef >= 0 ? (index === 0 ? "" : " + ") : " - ";
        return `${{sign}}${{Math.abs(row.coef).toFixed(3)}} × ${{escapeHtml(row.predictor)}}_actual^z`;
      }}).join("");
      const scenarioBadges = variables.map(variable => `<span class="term-chip${{scenarioVars.has(variable) ? "" : " is-fixed"}}">${{escapeHtml(variable)}}${{scenarioVars.has(variable) ? " → 基准期值" : " → 实际值"}}</span>`).join("");
      focusEquation.innerHTML = `<div class="card-top"><div><span class="eyebrow">Model Equation</span><h3 style="margin-top:8px;">当前模型的具体推演方程</h3></div><span class="chip">${{escapeHtml(currentScenario.scenario_label)}}</span></div><p class="muted">这里展示的是当前选中模型在当前情景下真正用于计算的预测方程。由于采用固定效应模型，网页把共同截距写入固定效应项中，而不单列一个普通 OLS 截距。</p><div class="formula-block">实际预测：<br />ŷ_it^actual = ${{actualEquation}} + ${{getFeTermText(model.fe_label)}}</div><div class="formula-block">当前反事实：<br />ŷ_it^cf(s) = ${{termHtml}} + ${{getFeTermText(model.fe_label)}}</div><div class="formula-block">差值定义：<br />Δ_it^(s) = ŷ_it^actual - ŷ_it^cf(s)</div><p class="formula-caption">变量替换规则：</p><div>${{scenarioBadges}}</div><p class="formula-caption">标准化处理沿用建模时使用的全样本 z-score，因此网页上的系数就是你在固定效应回归中估计得到的 β̂，反事实推演只替换变量取值，不重新估计模型。</p>`;
    }}
    function renderFocusCoefficientTable(model) {{
      const rows = focusCoefficientRecords.filter(row => row.model_id === model.model_id);
      if (!rows.length) {{
        focusCoefficientTable.innerHTML = '<div class="focus-empty">当前模型没有提取到关键系数。</div>';
        return;
      }}
      const head = `<thead><tr><th>变量</th><th>系数</th><th>P 值</th><th>95% CI</th><th>方向</th></tr></thead>`;
      const body = rows.map(row => `<tr><td>${{escapeHtml(row.predictor)}}</td><td>${{fmtSigned(row.coef)}}</td><td>${{fmtP(row.p_value)}}</td><td>[${{fmtNum(row.ci_low)}}, ${{fmtNum(row.ci_high)}}]</td><td>${{row.coef > 0 ? "正向" : row.coef < 0 ? "负向" : "接近 0"}}</td></tr>`).join("");
      focusCoefficientTable.innerHTML = `<div class="card-top"><div><span class="eyebrow">Key Coefficients</span><h3 style="margin-top:8px;">该模型的关键变量地位</h3></div></div><p class="muted">这里固定展示 R1xday、抗菌药物使用强度，以及当前模型里实际纳入的一个温度代理变量，用来帮助你判断这一模型的叙述重点。</p><div class="table-wrap"><table class="data-table compact">${{head}}<tbody>${{body}}</tbody></table></div>`;
    }}
    function buildLinePath(rows, field, xScale, yScale) {{
      return rows.map((row, index) => `${{index === 0 ? "M" : "L"}} ${{xScale(index).toFixed(1)}} ${{yScale(Number(row[field])).toFixed(1)}}`).join(" ");
    }}
    function renderFocusYearlyTrend(model, currentScenario) {{
      const rows = getModelYearly(model.model_id, currentScenario.scenario_id);
      if (!rows.length) {{
        focusYearlyTrend.innerHTML = '<div class="focus-empty">当前模型与情景下没有年度趋势数据。</div>';
        return;
      }}
      const values = rows.flatMap(row => [Number(row.actual_pred_mean), Number(row.counterfactual_pred_mean)]);
      let minValue = Math.min(...values);
      let maxValue = Math.max(...values);
      if (minValue === maxValue) {{
        minValue -= 1;
        maxValue += 1;
      }}
      const padding = (maxValue - minValue) * 0.12;
      minValue -= padding;
      maxValue += padding;
      const width = 860;
      const height = 320;
      const left = 52;
      const right = 18;
      const top = 22;
      const bottom = 38;
      const xScale = index => left + (width - left - right) * (rows.length === 1 ? 0.5 : index / (rows.length - 1));
      const yScale = value => top + (height - top - bottom) * (1 - (value - minValue) / (maxValue - minValue));
      const actualPath = buildLinePath(rows, "actual_pred_mean", xScale, yScale);
      const counterfactualPath = buildLinePath(rows, "counterfactual_pred_mean", xScale, yScale);
      const yearLabels = rows.map((row, index) => `<g><line x1="${{xScale(index).toFixed(1)}}" y1="${{height - bottom}}" x2="${{xScale(index).toFixed(1)}}" y2="${{height - bottom + 6}}" stroke="#9aa5ab" /><text x="${{xScale(index).toFixed(1)}}" y="${{height - bottom + 20}}" font-size="12" text-anchor="middle" fill="#5f6b72">${{escapeHtml(row.Year)}}</text></g>`).join("");
      const yTicks = [0, 0.25, 0.5, 0.75, 1].map(part => {{
        const value = minValue + (maxValue - minValue) * part;
        const y = yScale(value);
        return `<g><line x1="${{left}}" y1="${{y.toFixed(1)}}" x2="${{width - right}}" y2="${{y.toFixed(1)}}" stroke="rgba(217,206,192,0.7)" /><text x="${{left - 8}}" y="${{(y + 4).toFixed(1)}}" font-size="12" text-anchor="end" fill="#5f6b72">${{fmtNum(value, 2)}}</text></g>`;
      }}).join("");
      const actualPoints = rows.map((row, index) => `<circle cx="${{xScale(index).toFixed(1)}}" cy="${{yScale(Number(row.actual_pred_mean)).toFixed(1)}}" r="4" fill="#b5523b" />`).join("");
      const cfPoints = rows.map((row, index) => `<circle cx="${{xScale(index).toFixed(1)}}" cy="${{yScale(Number(row.counterfactual_pred_mean)).toFixed(1)}}" r="4" fill="#2f6c7a" />`).join("");
      const peak = rows.reduce((best, row) => Number(row.actual_minus_counterfactual_mean) > Number(best.actual_minus_counterfactual_mean) ? row : best, rows[0]);
      const trough = rows.reduce((best, row) => Number(row.actual_minus_counterfactual_mean) < Number(best.actual_minus_counterfactual_mean) ? row : best, rows[0]);
      focusYearlyTrend.innerHTML = `<div class="card-top"><div><span class="eyebrow">Yearly Trend</span><h3 style="margin-top:8px;">年度轨迹：实际情景 vs 反事实情景</h3></div><span class="chip">${{escapeHtml(currentScenario.scenario_label)}}</span></div><p class="muted">这张图只看当前模型和当前情景。红线是实际情景预测值，蓝线是反事实情景预测值，二者垂直距离越大，说明该年份的反事实效应越强。</p><svg class="focus-chart" viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="当前模型年度趋势图"><rect x="0" y="0" width="${{width}}" height="${{height}}" fill="#ffffff"></rect>${{yTicks}}<line x1="${{left}}" y1="${{height - bottom}}" x2="${{width - right}}" y2="${{height - bottom}}" stroke="#9aa5ab" /><path d="${{actualPath}}" fill="none" stroke="#b5523b" stroke-width="3"></path><path d="${{counterfactualPath}}" fill="none" stroke="#2f6c7a" stroke-width="3"></path>${{actualPoints}}${{cfPoints}}${{yearLabels}}</svg><div class="focus-legend"><span class="legend-item"><span class="legend-dot" style="background:#b5523b;"></span>实际预测值</span><span class="legend-item"><span class="legend-dot" style="background:#2f6c7a;"></span>反事实预测值</span></div><p class="muted">当前情景下，差值最大的年份是 <strong>${{escapeHtml(peak.Year)}}</strong> 年（${{fmtSigned(peak.actual_minus_counterfactual_mean)}}），最小的是 <strong>${{escapeHtml(trough.Year)}}</strong> 年（${{fmtSigned(trough.actual_minus_counterfactual_mean)}}）。</p>`;
    }}
    function buildProvinceTableCard(title, rows) {{
      const head = `<thead><tr><th>省份</th><th>差值</th><th>相对变化率(%)</th></tr></thead>`;
      const body = rows.map(row => `<tr><td>${{escapeHtml(row.Province)}}</td><td>${{fmtSigned(row.actual_minus_counterfactual_mean)}}</td><td>${{fmtPct(row.relative_change_pct_mean, 1)}}</td></tr>`).join("");
      return `<div class="mini-table-card"><h3>${{escapeHtml(title)}}</h3><table class="data-table compact">${{head}}<tbody>${{body}}</tbody></table></div>`;
    }}
    function renderProvincePanels(model, currentScenario) {{
      const avgRows = getProvinceRows(provinceAverage, model.model_id, currentScenario.scenario_id);
      const latestRows = getProvinceRows(latestYear, model.model_id, currentScenario.scenario_id);
      const avgTop = avgRows.slice(0, 5);
      const avgBottom = avgRows.slice(-5).reverse();
      const latestTop = latestRows.slice(0, 5);
      const latestBottom = latestRows.slice(-5).reverse();
      focusProvinceAverage.innerHTML = `<div class="card-top"><div><span class="eyebrow">Province Average</span><h3 style="margin-top:8px;">分省长期平均结果</h3></div></div><p class="muted">当前模型与当前情景下，各省跨年份平均后的反事实差值。适合用来描述“长期空间格局”。</p><div class="focus-stat-grid"><div class="focus-stat"><strong>正差值省份</strong><span>${{avgRows.filter(row => Number(row.actual_minus_counterfactual_mean) > 0).length}} / ${{avgRows.length || 31}}</span></div><div class="focus-stat"><strong>最高省份</strong><span>${{avgTop[0] ? escapeHtml(avgTop[0].Province) : "—"}}</span></div><div class="focus-stat"><strong>最低省份</strong><span>${{avgBottom[0] ? escapeHtml(avgBottom[0].Province) : "—"}}</span></div><div class="focus-stat"><strong>当前情景</strong><span>${{escapeHtml(currentScenario.scenario_label)}}</span></div></div><div class="mini-grid" style="margin-top:16px;">${{buildProvinceTableCard("长期平均正差值最高的省份", avgTop)}}${{buildProvinceTableCard("长期平均负差值最高的省份", avgBottom)}}</div>`;
      focusProvinceLatest.innerHTML = `<div class="card-top"><div><span class="eyebrow">Latest Year</span><h3 style="margin-top:8px;">最新年份分省结果</h3></div></div><p class="muted">这里固定展示最新年份的分省结果。适合用来说明“当前格局”和长期平均是否一致。</p><div class="focus-stat-grid"><div class="focus-stat"><strong>正差值省份</strong><span>${{latestRows.filter(row => Number(row.actual_minus_counterfactual_mean) > 0).length}} / ${{latestRows.length || 31}}</span></div><div class="focus-stat"><strong>最高省份</strong><span>${{latestTop[0] ? escapeHtml(latestTop[0].Province) : "—"}}</span></div><div class="focus-stat"><strong>最低省份</strong><span>${{latestBottom[0] ? escapeHtml(latestBottom[0].Province) : "—"}}</span></div><div class="focus-stat"><strong>当前情景</strong><span>${{escapeHtml(currentScenario.scenario_label)}}</span></div></div><div class="mini-grid" style="margin-top:16px;">${{buildProvinceTableCard("最新年份正差值最高的省份", latestTop)}}${{buildProvinceTableCard("最新年份负差值最高的省份", latestBottom)}}</div>`;
    }}
    function renderFocus() {{
      const model = getModelMeta(focusModelSelect.value);
      const scenarioRows = getModelOverall(model.model_id);
      const currentScenario = scenarioRows.find(row => row.scenario_id === focusScenarioSelect.value) || scenarioRows[0];
      const avgRows = getProvinceRows(provinceAverage, model.model_id, currentScenario.scenario_id);
      const latestRows = getProvinceRows(latestYear, model.model_id, currentScenario.scenario_id);
      renderFocusModelMeta(model, scenarioRows, currentScenario, avgRows, latestRows);
      renderFocusInterpretation(model, scenarioRows, currentScenario, avgRows, latestRows);
      renderFocusScenarioTable(model, scenarioRows, currentScenario.scenario_id);
      renderFocusEquation(model, currentScenario);
      renderFocusCoefficientTable(model);
      renderFocusYearlyTrend(model, currentScenario);
      renderProvincePanels(model, currentScenario);
    }}
    function initializeFocus() {{
      const modelOptions = selectedModels.map(model => ({{ value: model.model_id, label: `${{model.role_label}}｜${{model.scheme_id}}｜${{model.fe_label}}` }}));
      setOptions(focusModelSelect, modelOptions, defaultFocusModelId);
      syncFocusScenarioOptions("all_climate_to_baseline");
      renderFocus();
    }}
    datasetSelect.addEventListener("change", () => {{ syncFilters(); renderTable(); }});
    roleSelect.addEventListener("change", () => {{ syncFilters(); renderTable(); }});
    scenarioSelect.addEventListener("change", renderTable);
    searchInput.addEventListener("input", renderTable);
    focusModelSelect.addEventListener("change", () => {{ syncFocusScenarioOptions("all_climate_to_baseline"); renderFocus(); }});
    focusScenarioSelect.addEventListener("change", renderFocus);
    document.querySelectorAll(".focus-jump").forEach(button => {{
      button.addEventListener("click", () => {{
        focusModelSelect.value = button.dataset.modelId;
        syncFocusScenarioOptions("all_climate_to_baseline");
        renderFocus();
        document.getElementById("focus").scrollIntoView({{ behavior: "smooth", block: "start" }});
      }});
    }});
    syncFilters();
    renderTable();
    initializeFocus();
  </script>
</body>
</html>"""


def build_dashboard(outcome: str = "AMR_AGG") -> Path:
    inputs = load_inputs(outcome)
    html = build_dashboard_html(outcome, inputs)
    output_path = Path(inputs["base"]) / "counterfactual_results_dashboard.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = build_dashboard("AMR_AGG")
    print(f"[done] dashboard={path}")
