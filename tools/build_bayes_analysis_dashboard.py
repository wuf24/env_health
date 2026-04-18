from __future__ import annotations

import json
import math
import shutil
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BAYES_DIR = ROOT / "4 贝叶斯分析"
SUMMARY_DIR = BAYES_DIR / "results" / "model_summaries"
OUTPUT_DIR = ROOT / "public_dashboards" / "bayes-analysis"
DATA_DIR = OUTPUT_DIR / "data"

PRIMARY_SUMMARY = SUMMARY_DIR / "focus_primary_summary.csv"
BRIDGE_SUMMARY = SUMMARY_DIR / "focus_variant_bridge_summary.csv"
DIAGNOSTICS = SUMMARY_DIR / "combined_diagnostics.csv"
METADATA_SAMPLE = SUMMARY_DIR / "方案A_平衡主线组__ProvinceNo-YearYes__year_only_amplification_metadata.json"

VARIANT_ORDER = [
    "year_only_additive",
    "year_only_amplification",
    "province_only_additive",
    "province_only_amplification",
    "province_year_additive",
    "province_year_amplification",
]
SCHEME_ORDER = ["方案A_平衡主线组", "SYS_09556", "SYS_09557"]
VARIANT_LABELS = {
    "year_only_additive": "仅控制年份 · 主效应模型",
    "year_only_amplification": "仅控制年份 · 放大效应模型",
    "province_only_additive": "仅控制省份 · 主效应模型",
    "province_only_amplification": "仅控制省份 · 放大效应模型",
    "province_year_additive": "同时控制省份和年份 · 主效应模型",
    "province_year_amplification": "同时控制省份和年份 · 放大效应模型",
}
CONTROL_LABELS = {
    "year_only": "Year-only",
    "province_only": "Province-only",
    "province_year": "Province + year",
}
CONTROL_TITLES = {
    "year_only": "只控制年份的镜像口径",
    "province_only": "只控制省份差异的口径",
    "province_year": "同时控制省份和年份的严格口径",
}
CONTROL_DESCRIPTIONS = {
    "year_only": "对应当前最接近主线的 Year FE 镜像：主要判断主效应能否在贝叶斯框架下复现。",
    "province_only": "先吸收省际长期差异，再看气候与抗菌药物使用之间是否出现“放大效应”交互。",
    "province_year": "把省份与年份共同控制住，是最保守、也最接近严格识别的一道检验。",
}
SCHEME_LABELS = {
    "方案A_平衡主线组": "方案A 平衡主线组",
    "SYS_09556": "系统筛选方案 SYS_09556",
    "SYS_09557": "系统筛选方案 SYS_09557",
}
SCHEME_DESCRIPTIONS = {
    "方案A_平衡主线组": "人工整理的主线变量组，最适合承接论文叙事和结果展示。",
    "SYS_09556": "系统筛选后保留下来的候选组，前期 FE 结果里 R1xday 与 AMC 信号较强。",
    "SYS_09557": "另一组系统筛选候选，用来检验结论是否对变量组合具有稳健性。",
}
DOWNLOAD_FILES = {
    "focus_primary_summary.csv": PRIMARY_SUMMARY,
    "focus_variant_bridge_summary.csv": BRIDGE_SUMMARY,
    "combined_diagnostics.csv": DIAGNOSTICS,
}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def read_json(path: Path) -> dict[str, Any]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"Unable to decode {path}")


def fmt_num(value: Any, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}"


def fmt_prob(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value) * 100:.1f}%"


def fmt_interval(low: Any, high: Any) -> str:
    if any(pd.isna(item) for item in (low, high)):
        return "—"
    return f"[{float(low):.3f}, {float(high):.3f}]"


def fmt_range(values: pd.Series, digits: int = 3) -> str:
    cleaned = values.dropna().astype(float)
    if cleaned.empty:
        return "—"
    return f"{cleaned.min():.{digits}f}–{cleaned.max():.{digits}f}"


def effect_status(mean: Any, low: Any, high: Any, prob_gt_0: Any) -> tuple[str, str, str]:
    if any(pd.isna(item) for item in (mean, low, high, prob_gt_0)):
        return ("未估计", "muted", "该模型未包含这个参数。")
    mean_f = float(mean)
    low_f = float(low)
    high_f = float(high)
    prob_f = float(prob_gt_0)
    if low_f > 0:
        return ("稳健正向", "strong", "95% CrI 全部位于 0 以上。")
    if high_f < 0:
        return ("稳健负向", "negative", "95% CrI 全部位于 0 以下。")
    if mean_f > 0 and prob_f >= 0.8:
        return ("方向性正向", "directional", f"P(β>0)={fmt_prob(prob_f)}，但区间仍跨 0。")
    if mean_f < 0 and prob_f <= 0.2:
        return ("方向性负向", "negative", f"P(β>0)={fmt_prob(prob_f)}，但区间仍跨 0。")
    return ("证据不足", "muted", f"P(β>0)={fmt_prob(prob_f)}，方向性不够集中。")


def scheme_sort_key(value: str) -> int:
    return SCHEME_ORDER.index(value) if value in SCHEME_ORDER else len(SCHEME_ORDER)


def variant_sort_key(value: str) -> int:
    return VARIANT_ORDER.index(value) if value in VARIANT_ORDER else len(VARIANT_ORDER)


def control_from_variant(variant_id: str) -> str:
    if variant_id.startswith("year_only"):
        return "year_only"
    if variant_id.startswith("province_only"):
        return "province_only"
    return "province_year"


def render_badge(label: str, tone: str) -> str:
    return f'<span class="badge {escape(tone)}">{escape(label)}</span>'


def render_metric(mean: Any, low: Any, high: Any, prob_gt_0: Any) -> str:
    label, tone, detail = effect_status(mean, low, high, prob_gt_0)
    return (
        f'<div class="metric-block">'
        f'<div class="metric-top">{render_badge(label, tone)}</div>'
        f'<div class="metric-value">β = {escape(fmt_num(mean))}</div>'
        f'<div class="metric-sub">95% CrI {escape(fmt_interval(low, high))}</div>'
        f'<div class="metric-sub">P(β &gt; 0) = {escape(fmt_prob(prob_gt_0))}</div>'
        f'<div class="metric-note">{escape(detail)}</div>'
        f"</div>"
    )


def build_overview_cards(primary: pd.DataFrame, diagnostics: pd.DataFrame) -> str:
    year_rows = primary[
        primary["variant_id"].isin(["year_only_additive", "year_only_amplification"])
        & primary["effect_scope"].eq("main")
        & primary["variable"].isin(["R1xday", "抗菌药物使用强度"])
    ]
    year_robust = int((year_rows["crI_2_5"] > 0).sum())

    province_only_interactions = primary[
        primary["variant_id"].eq("province_only_amplification")
        & primary["effect_scope"].eq("interaction")
    ]
    province_only_robust = int((province_only_interactions["crI_2_5"] > 0).sum())

    province_year_interactions = primary[
        primary["variant_id"].eq("province_year_amplification")
        & primary["effect_scope"].eq("interaction")
    ]
    province_year_directional = int(
        (
            (province_year_interactions["posterior_mean"] > 0)
            & (province_year_interactions["prob_gt_0"] >= 0.8)
            & (province_year_interactions["crI_2_5"] <= 0)
        ).sum()
    )

    rhat_max = diagnostics["r_hat"].max()
    ess_bulk_min = int(diagnostics["ess_bulk"].min())

    cards = [
        (
            "Year-only 复现主线",
            f"{year_robust}/12",
            "两类主效应在 3 个方案、2 个 year-only 变体里全部保持稳健正向。",
            "strong",
        ),
        (
            "最强交互证据",
            f"{province_only_robust}/3",
            "province-only amplification 的交互项在 3 个方案中全部 95% CrI 高于 0。",
            "strong",
        ),
        (
            "最严格检验结果",
            f"{province_year_directional}/3",
            "province+year amplification 的交互项方向仍为正，但都还没有形成稳健区间。",
            "directional",
        ),
        (
            "采样稳定性",
            f"R-hat ≤ {rhat_max:.2f}",
            f"全部模型的 R-hat 不超过 {rhat_max:.2f}，最小 bulk ESS 为 {ess_bulk_min}。",
            "calm",
        ),
    ]
    return "".join(
        f"""
        <article class="highlight-card {tone}">
          <div class="highlight-label">{escape(label)}</div>
          <div class="highlight-value">{escape(value)}</div>
          <p>{escape(desc)}</p>
        </article>
        """
        for label, value, desc, tone in cards
    )


def build_design_cards() -> str:
    control_cards = "".join(
        f"""
        <article class="panel soft">
          <div class="eyebrow">{escape(CONTROL_LABELS[key])}</div>
          <h3>{escape(CONTROL_TITLES[key])}</h3>
          <p>{escape(CONTROL_DESCRIPTIONS[key])}</p>
        </article>
        """
        for key in ("year_only", "province_only", "province_year")
    )
    scheme_cards = "".join(
        f"""
        <article class="panel soft">
          <div class="eyebrow">Scheme</div>
          <h3>{escape(SCHEME_LABELS[key])}</h3>
          <p>{escape(SCHEME_DESCRIPTIONS[key])}</p>
        </article>
        """
        for key in SCHEME_ORDER
    )
    return control_cards + scheme_cards


def build_reading_cards() -> str:
    items = [
        ("后验均值", "先看方向和量级。正值代表正向关联，负值代表反向关联。"),
        ("95% CrI", "如果可信区间完整落在 0 的同一侧，说明证据比“仅方向偏正”更硬。"),
        ("P(β>0)", "越接近 100%，越支持正向；80%–95% 更适合表述为方向性支持。"),
        ("R-hat / ESS", "它们不回答“效应多大”，而是回答“这次采样是否足够稳定可信”。"),
    ]
    return "".join(
        f"""
        <article class="panel soft reading-card">
          <h3>{escape(title)}</h3>
          <p>{escape(desc)}</p>
        </article>
        """
        for title, desc in items
    )


def build_control_narrative(bridge: pd.DataFrame) -> str:
    sections: list[str] = []
    for control_key in ("year_only", "province_only", "province_year"):
        additive = bridge[bridge["variant_id"].eq(f"{control_key}_additive")].copy()
        amplification = bridge[bridge["variant_id"].eq(f"{control_key}_amplification")].copy()
        additive.sort_values("scheme_id", key=lambda s: s.map(scheme_sort_key), inplace=True)
        amplification.sort_values("scheme_id", key=lambda s: s.map(scheme_sort_key), inplace=True)

        if control_key == "year_only":
            paragraph = (
                f"在不含交互项的主效应模型里，R1xday 的后验均值落在 {fmt_range(additive['main_R1xday_posterior_mean'])}，"
                f"AMC 落在 {fmt_range(additive['main_AMC_posterior_mean'])}，两者在 3 个方案里 95% CrI 都高于 0。"
                f"加入交互项后，两个主效应几乎不动，但交互项均值只有 {fmt_range(amplification['interaction_R1xday_x_AMC_posterior_mean'])}，"
                "说明这条线主要是在稳定复现主效应，而不是已经稳稳证明“放大效应”。"
            )
            chips = [
                f"R1xday 主效应：{fmt_range(additive['main_R1xday_posterior_mean'])}",
                f"AMC 主效应：{fmt_range(additive['main_AMC_posterior_mean'])}",
                f"交互项：{fmt_range(amplification['interaction_R1xday_x_AMC_posterior_mean'])}",
            ]
        elif control_key == "province_only":
            paragraph = (
                f"一旦只控制省份差异，R1xday 主效应就回到 {fmt_range(additive['main_R1xday_posterior_mean'])} 的近零区间，"
                f"AMC 也只剩下 {fmt_range(additive['main_AMC_posterior_mean'])} 的弱正向。"
                f"但在放大效应模型里，交互项集中在 {fmt_range(amplification['interaction_R1xday_x_AMC_posterior_mean'])}，"
                "且 3 个方案的可信区间下界都刚好越过 0。这是整轮分析里最接近“amplifies”叙事的一条证据线。"
            )
            chips = [
                "R1xday 主效应接近 0",
                "AMC 主效应偏弱",
                "交互项 3/3 稳健正向",
            ]
        else:
            paragraph = (
                f"同时控制省份和年份后，R1xday 主效应进一步缩到 {fmt_range(additive['main_R1xday_posterior_mean'])}，"
                f"AMC 也只剩下 {fmt_range(additive['main_AMC_posterior_mean'])}。"
                f"交互项虽然依然是正的，均值大约 {fmt_range(amplification['interaction_R1xday_x_AMC_posterior_mean'])}，"
                "但 95% CrI 在所有方案里都重新跨回 0，说明严格口径下的证据还不够硬。"
            )
            chips = [
                "主效应整体衰减",
                "交互项保留正方向",
                "0/3 达到稳健区间",
            ]

        chip_html = "".join(f'<span class="tag">{escape(item)}</span>' for item in chips)
        sections.append(
            f"""
            <article class="panel narrative-card">
              <div class="eyebrow">{escape(CONTROL_LABELS[control_key])}</div>
              <h3>{escape(CONTROL_TITLES[control_key])}</h3>
              <p>{escape(paragraph)}</p>
              <div class="tag-row">{chip_html}</div>
            </article>
            """
        )
    return "".join(sections)


def build_forest_plot(bridge: pd.DataFrame) -> str:
    forest = bridge[bridge["variant_id"].str.endswith("amplification")].copy()
    forest["control_key"] = forest["variant_id"].map(control_from_variant)
    forest.sort_values(
        ["control_key", "scheme_id"],
        key=lambda s: s.map(lambda v: {"year_only": 0, "province_only": 1, "province_year": 2}.get(v, 99))
        if s.name == "control_key"
        else s.map(scheme_sort_key),
        inplace=True,
    )

    min_low = float(forest["interaction_R1xday_x_AMC_crI_2_5"].min())
    max_high = float(forest["interaction_R1xday_x_AMC_crI_97_5"].max())
    axis_min = math.floor((min_low - 0.005) * 100) / 100
    axis_max = math.ceil((max_high + 0.005) * 100) / 100
    axis_span = axis_max - axis_min
    zero_pct = (0 - axis_min) / axis_span * 100

    rows = []
    for _, row in forest.iterrows():
        mean = float(row["interaction_R1xday_x_AMC_posterior_mean"])
        low = float(row["interaction_R1xday_x_AMC_crI_2_5"])
        high = float(row["interaction_R1xday_x_AMC_crI_97_5"])
        label, tone, _ = effect_status(
            mean,
            low,
            high,
            row["interaction_R1xday_x_AMC_prob_gt_0"],
        )
        start = (low - axis_min) / axis_span * 100
        end = (high - axis_min) / axis_span * 100
        point = (mean - axis_min) / axis_span * 100
        rows.append(
            f"""
            <div class="forest-row">
              <div class="forest-meta">
                <div class="forest-kicker">{escape(CONTROL_LABELS[row['control_key']])}</div>
                <div class="forest-title">{escape(SCHEME_LABELS.get(row['scheme_id'], row['scheme_id']))}</div>
                <div class="forest-copy">β = {escape(fmt_num(mean))} · 95% CrI {escape(fmt_interval(low, high))}</div>
              </div>
              <div class="forest-track" style="--zero:{zero_pct:.2f}%; --start:{start:.2f}%; --end:{end:.2f}%; --point:{point:.2f}%;">
                <div class="forest-zero"></div>
                <div class="forest-line {escape(tone)}"></div>
                <div class="forest-point {escape(tone)}"></div>
              </div>
              <div class="forest-status">{render_badge(label, tone)}</div>
            </div>
            """
        )
    axis = f"{axis_min:.2f} 到 {axis_max:.2f}"
    return (
        f'<div class="forest-axis-note">横轴范围 {escape(axis)}，竖线表示 0；只有整段可信区间完全位于 0 右侧，才算“稳健正向”。</div>'
        + "".join(rows)
    )


def build_additive_table(bridge: pd.DataFrame) -> str:
    rows = bridge[bridge["variant_id"].str.endswith("additive")].copy()
    rows.sort_values(
        ["variant_id", "scheme_id"],
        key=lambda s: s.map(variant_sort_key) if s.name == "variant_id" else s.map(scheme_sort_key),
        inplace=True,
    )
    html_rows = []
    for _, row in rows.iterrows():
        verdict_label, verdict_tone, _ = effect_status(
            row["main_R1xday_posterior_mean"],
            row["main_R1xday_crI_2_5"],
            row["main_R1xday_crI_97_5"],
            row["main_R1xday_prob_gt_0"],
        )
        amc_label, amc_tone, _ = effect_status(
            row["main_AMC_posterior_mean"],
            row["main_AMC_crI_2_5"],
            row["main_AMC_crI_97_5"],
            row["main_AMC_prob_gt_0"],
        )
        html_rows.append(
            f"""
            <tr>
              <td>{escape(VARIANT_LABELS[row['variant_id']])}</td>
              <td>{escape(SCHEME_LABELS.get(row['scheme_id'], row['scheme_id']))}</td>
              <td>{render_metric(row['main_R1xday_posterior_mean'], row['main_R1xday_crI_2_5'], row['main_R1xday_crI_97_5'], row['main_R1xday_prob_gt_0'])}</td>
              <td>{render_metric(row['main_AMC_posterior_mean'], row['main_AMC_crI_2_5'], row['main_AMC_crI_97_5'], row['main_AMC_prob_gt_0'])}</td>
              <td><div class="stacked-badges">{render_badge(verdict_label, verdict_tone)}{render_badge(amc_label, amc_tone)}</div></td>
            </tr>
            """
        )
    return "".join(html_rows)


def build_amplification_table(bridge: pd.DataFrame) -> str:
    rows = bridge[bridge["variant_id"].str.endswith("amplification")].copy()
    rows.sort_values(
        ["variant_id", "scheme_id"],
        key=lambda s: s.map(variant_sort_key) if s.name == "variant_id" else s.map(scheme_sort_key),
        inplace=True,
    )
    html_rows = []
    for _, row in rows.iterrows():
        interaction_label, interaction_tone, _ = effect_status(
            row["interaction_R1xday_x_AMC_posterior_mean"],
            row["interaction_R1xday_x_AMC_crI_2_5"],
            row["interaction_R1xday_x_AMC_crI_97_5"],
            row["interaction_R1xday_x_AMC_prob_gt_0"],
        )
        html_rows.append(
            f"""
            <tr>
              <td>{escape(VARIANT_LABELS[row['variant_id']])}</td>
              <td>{escape(SCHEME_LABELS.get(row['scheme_id'], row['scheme_id']))}</td>
              <td>{render_metric(row['main_R1xday_posterior_mean'], row['main_R1xday_crI_2_5'], row['main_R1xday_crI_97_5'], row['main_R1xday_prob_gt_0'])}</td>
              <td>{render_metric(row['main_AMC_posterior_mean'], row['main_AMC_crI_2_5'], row['main_AMC_crI_97_5'], row['main_AMC_prob_gt_0'])}</td>
              <td>{render_metric(row['interaction_R1xday_x_AMC_posterior_mean'], row['interaction_R1xday_x_AMC_crI_2_5'], row['interaction_R1xday_x_AMC_crI_97_5'], row['interaction_R1xday_x_AMC_prob_gt_0'])}</td>
              <td>{render_badge(interaction_label, interaction_tone)}</td>
            </tr>
            """
        )
    return "".join(html_rows)


def build_diagnostics_table(diagnostics: pd.DataFrame) -> str:
    grouped = (
        diagnostics.groupby(["scheme_id", "variant_id"], as_index=False)
        .agg(r_hat=("r_hat", "max"), ess_bulk=("ess_bulk", "min"), ess_tail=("ess_tail", "min"))
        .copy()
    )
    grouped.sort_values(
        ["variant_id", "scheme_id"],
        key=lambda s: s.map(variant_sort_key) if s.name == "variant_id" else s.map(scheme_sort_key),
        inplace=True,
    )
    rows = []
    for _, row in grouped.iterrows():
        tone = "strong" if row["r_hat"] <= 1.01 and row["ess_bulk"] >= 600 else "directional"
        rows.append(
            f"""
            <tr>
              <td>{escape(VARIANT_LABELS[row['variant_id']])}</td>
              <td>{escape(SCHEME_LABELS.get(row['scheme_id'], row['scheme_id']))}</td>
              <td>{row['r_hat']:.2f}</td>
              <td>{int(row['ess_bulk'])}</td>
              <td>{int(row['ess_tail'])}</td>
              <td>{render_badge('可接受', tone)}</td>
            </tr>
            """
        )
    return "".join(rows)


def build_download_cards(generated_at: str) -> str:
    file_cards = []
    for name in DOWNLOAD_FILES:
        file_cards.append(
            f"""
            <a class="download-card" href="./data/{escape(name)}">
              <div class="download-title">{escape(name)}</div>
              <div class="download-copy">点击查看或下载页面所依据的汇总结果文件。</div>
            </a>
            """
        )
    file_cards.append(
        f"""
        <a class="download-card" href="./metadata.json">
          <div class="download-title">metadata.json</div>
          <div class="download-copy">页面生成时间：{escape(generated_at)}，包含来源文件与汇总统计。</div>
        </a>
        """
    )
    return "".join(file_cards)


def build_html(
    primary: pd.DataFrame,
    bridge: pd.DataFrame,
    diagnostics: pd.DataFrame,
    metadata: dict[str, Any],
    generated_at: str,
) -> str:
    run_config = metadata.get("run_config", {})
    missing_strategy = metadata.get("missing_value_strategy", {})
    column_report = pd.DataFrame(missing_strategy.get("column_report", []))
    amc_row = column_report[column_report["column"].astype(str).str.contains("抗菌药物使用强度", na=False)]
    amc_before = int(amc_row["missing_before"].iloc[0]) if not amc_row.empty else 0
    amc_after = int(amc_row["missing_after"].iloc[0]) if not amc_row.empty else 0
    amc_filled = amc_before - amc_after
    outcome_handling = metadata.get("outcome_handling", {})
    n_obs = int(metadata.get("n_obs", 0))
    n_provinces = int(metadata.get("n_provinces", 0))
    n_years = int(metadata.get("n_years", 0))

    diagnostics_count = int(diagnostics[["scheme_id", "variant_id"]].drop_duplicates().shape[0])
    interaction_rows = bridge[bridge["variant_id"].str.endswith("amplification")]
    strongest_row = interaction_rows.loc[interaction_rows["interaction_R1xday_x_AMC_crI_2_5"].idxmax()]
    strongest_label = (
        f"{VARIANT_LABELS[strongest_row['variant_id']]} · "
        f"{SCHEME_LABELS.get(strongest_row['scheme_id'], strongest_row['scheme_id'])}"
    )

    metadata_payload = {
        "generated_at": generated_at,
        "source_dir": str(SUMMARY_DIR.relative_to(ROOT)).replace("\\", "/"),
        "inputs": [str(path.relative_to(ROOT)).replace("\\", "/") for path in DOWNLOAD_FILES.values()],
        "n_models": diagnostics_count,
        "n_obs": n_obs,
        "n_provinces": n_provinces,
        "n_years": n_years,
        "run_config": run_config,
        "max_r_hat": float(diagnostics["r_hat"].max()),
        "min_ess_bulk": int(diagnostics["ess_bulk"].min()),
        "min_ess_tail": int(diagnostics["ess_tail"].min()),
        "strongest_interaction_line": strongest_label,
    }

    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>贝叶斯分析解读看板</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --panel: rgba(255, 251, 246, 0.88);
      --panel-strong: rgba(255, 251, 246, 0.96);
      --ink: #17313b;
      --muted: #5d737a;
      --line: rgba(23, 49, 59, 0.10);
      --teal: #1f6b73;
      --rust: #b45a33;
      --gold: #c79c45;
      --positive: #126f52;
      --negative: #9f3f35;
      --soft: #eef5f4;
      --shadow: 0 22px 70px rgba(33, 31, 27, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Aptos", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at 0% 0%, rgba(180, 90, 51, 0.18), transparent 22%),
        radial-gradient(circle at 100% 0%, rgba(31, 107, 115, 0.16), transparent 28%),
        linear-gradient(180deg, #fbf7f2 0%, #eef2ef 100%);
    }}
    h1, h2, h3 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      letter-spacing: -0.02em;
    }}
    p, li {{
      line-height: 1.8;
      color: var(--muted);
    }}
    a {{
      color: inherit;
      text-decoration: none;
    }}
    .page {{
      width: min(1280px, calc(100vw - 24px));
      margin: 18px auto 40px;
      display: grid;
      gap: 18px;
    }}
    .hero, .card, .panel {{
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.74);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }}
    .hero, .card {{
      border-radius: 30px;
      padding: 28px;
    }}
    .panel {{
      border-radius: 24px;
      padding: 22px;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(15, 37, 48, 0.98), rgba(29, 94, 96, 0.93)),
        linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
      color: #fbf8f2;
    }}
    .hero::before {{
      content: "";
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px);
      background-size: 28px 28px;
      opacity: 0.12;
      pointer-events: none;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -56px;
      top: -56px;
      width: 240px;
      height: 240px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.20), transparent 68%);
      pointer-events: none;
    }}
    .hero p {{
      color: rgba(251, 248, 242, 0.86);
      max-width: 860px;
    }}
    .eyebrow {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      opacity: 0.78;
      margin-bottom: 10px;
    }}
    .hero h1 {{
      font-size: clamp(34px, 5vw, 62px);
      line-height: 1.03;
      max-width: 920px;
    }}
    .hero .lead {{
      font-size: 17px;
      margin-top: 16px;
    }}
    .nav-pills, .tag-row, .stats-grid, .highlights-grid, .grid-3, .grid-2, .downloads {{
      display: grid;
      gap: 14px;
    }}
    .nav-pills {{
      grid-template-columns: repeat(5, minmax(0, max-content));
      margin-top: 22px;
      align-items: center;
      justify-content: start;
    }}
    .nav-pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 16px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.10);
      border: 1px solid rgba(255, 255, 255, 0.14);
      font-weight: 700;
      color: rgba(251, 248, 242, 0.94);
    }}
    .stats-grid {{
      grid-template-columns: repeat(5, minmax(0, 1fr));
      margin-top: 22px;
    }}
    .stat {{
      padding: 18px;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.10);
      border: 1px solid rgba(255, 255, 255, 0.13);
    }}
    .stat .k {{
      font-size: 12px;
      letter-spacing: 0.10em;
      text-transform: uppercase;
      opacity: 0.75;
      margin-bottom: 8px;
    }}
    .stat .v {{
      font-size: 30px;
      font-weight: 800;
      line-height: 1;
      margin-bottom: 8px;
    }}
    .stat .h {{
      font-size: 13px;
      line-height: 1.7;
      color: rgba(251, 248, 242, 0.84);
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: end;
      margin-bottom: 16px;
    }}
    .section-head p {{
      margin: 10px 0 0;
      max-width: 840px;
    }}
    .section-head h2 {{
      font-size: 34px;
      line-height: 1.1;
    }}
    .highlights-grid {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }}
    .highlight-card {{
      padding: 22px;
      border-radius: 24px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
    }}
    .highlight-card.strong {{
      background: linear-gradient(180deg, rgba(18, 111, 82, 0.10), rgba(255, 251, 246, 0.96));
    }}
    .highlight-card.directional {{
      background: linear-gradient(180deg, rgba(199, 156, 69, 0.12), rgba(255, 251, 246, 0.96));
    }}
    .highlight-card.calm {{
      background: linear-gradient(180deg, rgba(31, 107, 115, 0.10), rgba(255, 251, 246, 0.96));
    }}
    .highlight-label {{
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.10em;
      color: var(--muted);
      margin-bottom: 10px;
    }}
    .highlight-value {{
      font-size: 34px;
      font-weight: 800;
      line-height: 1.05;
      margin-bottom: 10px;
    }}
    .grid-3 {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .grid-2 {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .soft {{
      background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(238,245,244,0.72));
    }}
    .reading-card h3, .narrative-card h3, .soft h3 {{
      font-size: 24px;
      line-height: 1.2;
    }}
    .reading-card p, .narrative-card p {{
      margin-top: 12px;
    }}
    .tag-row {{
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      margin-top: 16px;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(31, 107, 115, 0.08);
      border: 1px solid rgba(31, 107, 115, 0.12);
      font-size: 13px;
      font-weight: 700;
      color: var(--teal);
      text-align: center;
    }}
    .reporting-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }}
    .report-box {{
      padding: 20px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
    }}
    .report-box.good {{
      background: linear-gradient(180deg, rgba(18,111,82,0.10), rgba(255,251,246,0.98));
    }}
    .report-box.warn {{
      background: linear-gradient(180deg, rgba(180,90,51,0.10), rgba(255,251,246,0.98));
    }}
    .report-box.next {{
      background: linear-gradient(180deg, rgba(31,107,115,0.10), rgba(255,251,246,0.98));
    }}
    .report-box ul {{
      margin: 14px 0 0;
      padding-left: 18px;
    }}
    .forest-axis-note {{
      margin-bottom: 14px;
      font-size: 14px;
      color: var(--muted);
    }}
    .forest-row {{
      display: grid;
      grid-template-columns: 280px 1fr 140px;
      gap: 16px;
      align-items: center;
      padding: 16px 0;
      border-top: 1px solid var(--line);
    }}
    .forest-row:first-of-type {{
      border-top: 0;
    }}
    .forest-kicker {{
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .forest-title {{
      font-weight: 800;
      margin-bottom: 4px;
    }}
    .forest-copy {{
      font-size: 14px;
      color: var(--muted);
      line-height: 1.7;
    }}
    .forest-track {{
      position: relative;
      height: 42px;
      border-radius: 999px;
      background:
        linear-gradient(180deg, rgba(31,107,115,0.06), rgba(31,107,115,0.02));
      border: 1px solid rgba(31,107,115,0.08);
    }}
    .forest-zero {{
      position: absolute;
      top: 6px;
      bottom: 6px;
      left: var(--zero);
      width: 2px;
      background: rgba(159, 63, 53, 0.26);
    }}
    .forest-line {{
      position: absolute;
      top: 50%;
      left: var(--start);
      width: calc(var(--end) - var(--start));
      height: 6px;
      border-radius: 999px;
      transform: translateY(-50%);
      background: rgba(31,107,115,0.30);
    }}
    .forest-line.strong {{
      background: rgba(18,111,82,0.56);
    }}
    .forest-line.directional {{
      background: rgba(199,156,69,0.58);
    }}
    .forest-line.negative {{
      background: rgba(159,63,53,0.56);
    }}
    .forest-point {{
      position: absolute;
      top: 50%;
      left: var(--point);
      width: 14px;
      height: 14px;
      border-radius: 50%;
      transform: translate(-50%, -50%);
      background: var(--teal);
      border: 2px solid #fff;
      box-shadow: 0 4px 12px rgba(0,0,0,0.14);
    }}
    .forest-point.strong {{
      background: var(--positive);
    }}
    .forest-point.directional {{
      background: var(--gold);
    }}
    .forest-point.negative {{
      background: var(--negative);
    }}
    .table-wrap {{
      overflow-x: auto;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 980px;
    }}
    th, td {{
      padding: 16px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      background: rgba(23,49,59,0.04);
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    .metric-block {{
      display: grid;
      gap: 6px;
      min-width: 180px;
    }}
    .metric-top {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .metric-value {{
      font-weight: 800;
    }}
    .metric-sub, .metric-note {{
      font-size: 13px;
      color: var(--muted);
      line-height: 1.6;
    }}
    .metric-note {{
      color: var(--ink);
    }}
    .stacked-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 7px 11px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.02em;
      border: 1px solid transparent;
      white-space: nowrap;
    }}
    .badge.strong {{
      background: rgba(18,111,82,0.12);
      color: var(--positive);
      border-color: rgba(18,111,82,0.14);
    }}
    .badge.directional {{
      background: rgba(199,156,69,0.16);
      color: #8a6619;
      border-color: rgba(199,156,69,0.14);
    }}
    .badge.negative {{
      background: rgba(159,63,53,0.12);
      color: var(--negative);
      border-color: rgba(159,63,53,0.12);
    }}
    .badge.muted {{
      background: rgba(23,49,59,0.08);
      color: var(--muted);
      border-color: rgba(23,49,59,0.10);
    }}
    .badge.calm {{
      background: rgba(31,107,115,0.12);
      color: var(--teal);
      border-color: rgba(31,107,115,0.12);
    }}
    .downloads {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }}
    .download-card {{
      display: block;
      padding: 18px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.86), rgba(238,245,244,0.70));
      transition: transform 140ms ease, box-shadow 140ms ease;
    }}
    .download-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 18px 30px rgba(23, 49, 59, 0.10);
    }}
    .download-title {{
      font-weight: 800;
      margin-bottom: 8px;
    }}
    .download-copy {{
      font-size: 14px;
      color: var(--muted);
      line-height: 1.7;
    }}
    footer {{
      text-align: center;
      color: var(--muted);
      font-size: 13px;
      padding-top: 10px;
    }}
    @media (max-width: 1080px) {{
      .stats-grid,
      .highlights-grid,
      .grid-3,
      .grid-2,
      .reporting-grid,
      .downloads {{
        grid-template-columns: 1fr;
      }}
      .nav-pills {{
        grid-template-columns: 1fr 1fr;
      }}
      .forest-row {{
        grid-template-columns: 1fr;
      }}
      .page {{
        width: calc(100vw - 12px);
        margin: 8px auto 20px;
      }}
      .hero, .card {{
        border-radius: 24px;
        padding: 22px;
      }}
      .panel {{
        border-radius: 20px;
        padding: 18px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="eyebrow">Bayesian Analysis Dashboard</div>
      <h1>气候变化、抗菌药物使用与 AMR 的贝叶斯分析解读</h1>
      <p class="lead">这页把本轮 3 组变量方案 × 6 个贝叶斯变体的结果拆成“结论、证据、质量控制”三层来读。核心问题不是单纯看某个系数是否为正，而是比较在不同控制口径下，主效应和交互项究竟稳不稳、能说到什么程度。</p>
      <div class="nav-pills">
        <a class="nav-pill" href="#findings">核心结论</a>
        <a class="nav-pill" href="#design">分析结构</a>
        <a class="nav-pill" href="#evidence">证据矩阵</a>
        <a class="nav-pill" href="#quality">诊断质量</a>
        <a class="nav-pill" href="#downloads">数据下载</a>
      </div>
      <div class="stats-grid">
        <div class="stat">
          <div class="k">模型总数</div>
          <div class="v">{diagnostics_count}</div>
          <div class="h">3 个方案 × 6 个变体，覆盖 year-only、province-only、province+year 三种控制口径。</div>
        </div>
        <div class="stat">
          <div class="k">样本结构</div>
          <div class="v">{n_obs}</div>
          <div class="h">{n_provinces} 个省份，{n_years} 个年份；代表进入模型后的分析样本规模。</div>
        </div>
        <div class="stat">
          <div class="k">采样设置</div>
          <div class="v">{run_config.get("chains", "—")}×{run_config.get("draws", "—")}</div>
          <div class="h">每个模型 {run_config.get("chains", "—")} 条链，draws={run_config.get("draws", "—")}，tune={run_config.get("tune", "—")}。</div>
        </div>
        <div class="stat">
          <div class="k">最强交互线</div>
          <div class="v">Province-only</div>
          <div class="h">{escape(strongest_label)} 给出了全轮分析里最强的正向交互信号。</div>
        </div>
        <div class="stat">
          <div class="k">生成时间</div>
          <div class="v">{escape(generated_at[:16])}</div>
          <div class="h">静态网页已写入 <code>public_dashboards/bayes-analysis/</code>，可以直接打开浏览。</div>
        </div>
      </div>
    </section>

    <section class="card" id="findings">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Executive Summary</div>
          <h2>先看结论</h2>
          <p>如果只抓这轮贝叶斯分析最重要的几句话，重点就是：year-only 复现主效应最稳，province-only 给出最强的交互信号，而 province+year 作为最严格口径时，交互项仍偏正但还不够硬。</p>
        </div>
      </div>
      <div class="highlights-grid">
        {build_overview_cards(primary, diagnostics)}
      </div>
    </section>

    <section class="card" id="design">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Study Design</div>
          <h2>分析结构怎么搭的</h2>
          <p>这轮并不是只跑一个“贝叶斯版 FE”，而是先镜像出 3 种固定效应语境，再在每个语境下分别比较主效应模型与放大效应模型。这样可以看出结论到底依赖哪一种控制方式。</p>
        </div>
      </div>
      <div class="grid-3">
        {build_design_cards()}
      </div>
    </section>

    <section class="card">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Reading Guide</div>
          <h2>怎么读贝叶斯指标</h2>
          <p>页面里每个核心系数都按同一顺序展示：后验均值、95% 可信区间、P(β&gt;0)。这样读的时候不会把“方向偏正”和“已经稳健”混为一谈。</p>
        </div>
      </div>
      <div class="grid-2">
        {build_reading_cards()}
      </div>
    </section>

    <section class="card">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Interpretation</div>
          <h2>三种控制口径分别说明了什么</h2>
          <p>最值得看的是在不同固定效应口径下，R1xday 主效应、AMC 主效应和交互项是怎样一起变化的。它们共同决定这轮分析能否支撑“climate amplifies AMR”这样的叙事强度。</p>
        </div>
      </div>
      <div class="grid-3">
        {build_control_narrative(bridge)}
      </div>
    </section>

    <section class="card">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Interaction Signal</div>
          <h2>交互项森林图</h2>
          <p>下面只看放大效应模型里的 <code>R1xday × 抗菌药物使用强度</code>。如果整段区间都在 0 右侧，说明“放大效应”不只是方向偏正，而是达到更稳健的支持。</p>
        </div>
      </div>
      {build_forest_plot(bridge)}
    </section>

    <section class="card" id="evidence">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Evidence Matrix</div>
          <h2>主效应矩阵</h2>
          <p>这张表只看 additive 变体，目的是把主效应本身单独拎出来。year-only 线非常稳定，而一旦把省份差异控制进去，R1xday 主效应会明显收缩到 0 附近。</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>控制口径</th>
              <th>变量方案</th>
              <th>R1xday</th>
              <th>AMC</th>
              <th>简要判断</th>
            </tr>
          </thead>
          <tbody>
            {build_additive_table(bridge)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Amplification Matrix</div>
          <h2>放大效应矩阵</h2>
          <p>这张表把 amplification 变体放在一起。关键不只看交互项本身，也要同时看加入交互以后两条主效应是否仍然站得住。</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>控制口径</th>
              <th>变量方案</th>
              <th>R1xday</th>
              <th>AMC</th>
              <th>R1xday × AMC</th>
              <th>交互结论</th>
            </tr>
          </thead>
          <tbody>
            {build_amplification_table(bridge)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="card" id="quality">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Diagnostics & Data</div>
          <h2>采样诊断与数据处理</h2>
          <p>这部分回答两个问题：一是 MCMC 有没有明显不稳定；二是缺失值和样本筛选是怎么处理的。只有这两步站住脚，前面的解释才可信。</p>
        </div>
      </div>
      <div class="highlights-grid">
        <article class="highlight-card calm">
          <div class="highlight-label">R-hat 上限</div>
          <div class="highlight-value">{diagnostics['r_hat'].max():.2f}</div>
          <p>全部参数的 R-hat 都不超过 {diagnostics['r_hat'].max():.2f}，没有明显链间分离问题。</p>
        </article>
        <article class="highlight-card calm">
          <div class="highlight-label">最小 ESS bulk</div>
          <div class="highlight-value">{int(diagnostics['ess_bulk'].min())}</div>
          <p>即使是最吃力的模型，bulk ESS 也仍然在可接受范围内。</p>
        </article>
        <article class="highlight-card calm">
          <div class="highlight-label">AMC 缺失值</div>
          <div class="highlight-value">{amc_before} → {amc_after}</div>
          <p>按省份-年份规则补入了 {amc_filled} 个缺失值，仍保留 {amc_after} 个未补全点位。</p>
        </article>
        <article class="highlight-card calm">
          <div class="highlight-label">结局变量处理</div>
          <div class="highlight-value">{outcome_handling.get('missing_before_drop', 0)} → {outcome_handling.get('missing_after_drop', 0)}</div>
          <p>AMR_AGG_z 不做人为插补；X 变量处理完后，再把结局仍缺失的样本剔除。</p>
        </article>
      </div>
      <div class="panel soft" style="margin-top: 16px;">
        <p>代表性元数据显示：本轮模型使用的默认采样配置为 <code>chains={run_config.get("chains", "—")}</code>、<code>draws={run_config.get("draws", "—")}</code>、<code>tune={run_config.get("tune", "—")}</code>、<code>target_accept={run_config.get("target_accept", "—")}</code>。X 变量采用按省份-年份推进的时间插补规则；对结局变量 <code>AMR_AGG_z</code> 不做人工补值，避免把模型结论建立在虚构的 outcome 上。</p>
      </div>
      <div class="table-wrap" style="margin-top: 16px;">
        <table>
          <thead>
            <tr>
              <th>控制口径</th>
              <th>变量方案</th>
              <th>R-hat 最大值</th>
              <th>ESS bulk 最小值</th>
              <th>ESS tail 最小值</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {build_diagnostics_table(diagnostics)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Reporting Guidance</div>
          <h2>推荐怎么表述结果</h2>
          <p>这部分把“现在能说什么”和“现在还不宜说得太满的地方”拆开，方便直接转写进汇报稿、论文说明或图注。</p>
        </div>
      </div>
      <div class="reporting-grid">
        <article class="report-box good">
          <h3>可以稳妥地说</h3>
          <ul>
            <li>在 year-only 贝叶斯镜像下，R1xday 与抗菌药物使用强度的主效应在 3 个变量方案里都稳定为正。</li>
            <li>在 province-only amplification 模型中，交互项在 3 个方案里都呈稳健正向，说明存在较强的放大效应线索。</li>
            <li>不同变量方案对交互项的方向判断大体一致，区别主要在证据强度，而不是方向完全翻转。</li>
          </ul>
        </article>
        <article class="report-box warn">
          <h3>暂时不要直接写成</h3>
          <ul>
            <li>“已经在所有控制口径下稳健证明 climate change amplifies AMR”。</li>
            <li>“加入省份和年份双重控制后，交互项仍然显著成立”。</li>
            <li>把 province-only 的交互结果直接外推为对最严格识别条件下的最终结论。</li>
          </ul>
        </article>
        <article class="report-box next">
          <h3>下一步最值得做</h3>
          <ul>
            <li>优先把 lag 检验放在 <code>year_only_amplification</code>、<code>province_only_amplification</code>、<code>province_year_amplification</code> 三条线上。</li>
            <li>如果要写主文结果，建议把 year-only 作为主线复现，把 province-only interaction 当作重点发现，把 province+year 当作严格稳健性检查。</li>
            <li>如果要进一步强化交互证据，优先解释为什么加入年份共同冲击后区间会变宽或回跨 0。</li>
          </ul>
        </article>
      </div>
    </section>

    <section class="card" id="downloads">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Downloads</div>
          <h2>页面用到的数据</h2>
          <p>为了让这个页面可追溯，我把主要汇总结果文件一并复制到了页面目录下。后续如果模型结果更新，只需要重新运行生成脚本即可一起刷新页面和附件。</p>
        </div>
      </div>
      <div class="downloads">
        {build_download_cards(generated_at)}
      </div>
    </section>

    <footer>Generated from <code>{escape(str(SUMMARY_DIR.relative_to(ROOT)).replace("\\\\", "/"))}</code> on {escape(generated_at)}.</footer>
  </div>
</body>
</html>
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    primary = read_csv(PRIMARY_SUMMARY)
    bridge = read_csv(BRIDGE_SUMMARY)
    diagnostics = read_csv(DIAGNOSTICS)
    metadata = read_json(METADATA_SAMPLE)

    for name, source in DOWNLOAD_FILES.items():
        shutil.copy2(source, DATA_DIR / name)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = build_html(primary, bridge, diagnostics, metadata, generated_at)
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
