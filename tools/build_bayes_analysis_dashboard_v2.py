from __future__ import annotations

import json
import shutil
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "4 贝叶斯分析" / "results" / "model_summaries"
MODEL_ARCHIVE_PATH = ROOT / "2 固定效应模型" / "results" / "model_archive_12" / "selected_models.csv"
PUBLIC_OUTPUT_DIR = ROOT / "public_dashboards" / "bayes-analysis"
PUBLIC_DATA_DIR = PUBLIC_OUTPUT_DIR / "data"
PUBLIC_METADATA_PATH = PUBLIC_OUTPUT_DIR / "metadata.json"
LOCAL_OUTPUT_PATH = ROOT / "4 贝叶斯分析" / "index.html"

PRIMARY_SUMMARY = SUMMARY_DIR / "focus_primary_summary.csv"
BRIDGE_SUMMARY = SUMMARY_DIR / "focus_variant_bridge_summary.csv"
DIAGNOSTICS = SUMMARY_DIR / "combined_diagnostics.csv"

DOWNLOAD_FILES = {
    "focus_primary_summary.csv": PRIMARY_SUMMARY,
    "focus_variant_bridge_summary.csv": BRIDGE_SUMMARY,
    "combined_diagnostics.csv": DIAGNOSTICS,
    "selected_models.csv": MODEL_ARCHIVE_PATH,
}

PUBLIC_DOWNLOAD_TARGETS = {
    name: f"./data/{name}" for name in DOWNLOAD_FILES
}

LOCAL_DOWNLOAD_TARGETS = {
    "focus_primary_summary.csv": "results/model_summaries/focus_primary_summary.csv",
    "focus_variant_bridge_summary.csv": "results/model_summaries/focus_variant_bridge_summary.csv",
    "combined_diagnostics.csv": "results/model_summaries/combined_diagnostics.csv",
    "selected_models.csv": "../2 固定效应模型/results/model_archive_12/selected_models.csv",
}

VARIANT_META = {
    "year_only_additive": {
        "label": "Year-only additive",
        "family": "Year-only",
        "description": "最接近主线 Year FE 的贝叶斯镜像，只检验主效应能否稳定复现。",
    },
    "year_only_amplification": {
        "label": "Year-only amplification",
        "family": "Year-only",
        "description": "在 Year-only 口径下增加交互项，检验极端降雨是否会放大 AMC-AMR 关联。",
    },
    "province_only_additive": {
        "label": "Province-only additive",
        "family": "Province-only",
        "description": "先吸收省际长期差异，再看主效应还能保留多少。",
    },
    "province_only_amplification": {
        "label": "Province-only amplification",
        "family": "Province-only",
        "description": "当前最适合盯放大效应的一条线，看交互项在省际差异控制后是否仍然抬起。",
    },
    "province_year_additive": {
        "label": "Province + year additive",
        "family": "Province + year",
        "description": "最严格口径下的主效应检查，用来判断核心信号是否被双重控制压缩。",
    },
    "province_year_amplification": {
        "label": "Province + year amplification",
        "family": "Province + year",
        "description": "最严格口径下的交互项检查，方向若还能抬起，解释力最强；若压回零，也最容易理解。",
    },
}

VARIANT_ORDER = list(VARIANT_META)
MODEL_COLUMNS = [
    "archive_rank",
    "role_label",
    "scheme_id",
    "fe_label",
    "performance_rank",
    "performance_score",
    "coef_R1xday",
    "p_R1xday",
    "coef_AMC",
    "p_AMC",
    "coef_TA",
    "p_TA",
    "r2_model",
    "variables",
]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def fmt_num(value: object, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}"


def fmt_signed(value: object, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):+.{digits}f}"


def fmt_prob(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{100 * float(value):.1f}%"


def fmt_p(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = float(value)
    if value < 0.0001:
        return "<0.0001"
    return f"{value:.4f}"


def fmt_interval(low: object, high: object) -> str:
    if any(pd.isna(item) for item in (low, high)):
        return "—"
    return f"[{float(low):.3f}, {float(high):.3f}]"


def effect_status(mean: object, low: object, high: object, prob_gt_0: object) -> tuple[str, str]:
    if any(pd.isna(item) for item in (mean, low, high, prob_gt_0)):
        return ("未估计", "muted")
    mean_f = float(mean)
    low_f = float(low)
    high_f = float(high)
    prob_f = float(prob_gt_0)
    if low_f > 0:
        return ("稳健正向", "strong")
    if high_f < 0:
        return ("稳健负向", "negative")
    if mean_f > 0 and prob_f >= 0.8:
        return ("方向性正向", "directional")
    if mean_f < 0 and prob_f <= 0.2:
        return ("方向性负向", "negative")
    return ("证据不足", "muted")


def badge(label: str, tone: str) -> str:
    return f'<span class="badge {escape(tone)}">{escape(label)}</span>'


def model_sort_key(model_id: str, archive_df: pd.DataFrame) -> int:
    match = archive_df.loc[archive_df["model_id"] == model_id, "archive_rank"]
    if match.empty:
        return 999
    return int(match.iloc[0])


def build_variant_summary_cards(bridge: pd.DataFrame) -> str:
    cards: list[str] = []
    for variant_id in VARIANT_ORDER:
        sub = bridge[bridge["variant_id"] == variant_id].copy()
        if sub.empty:
            continue
        meta = VARIANT_META[variant_id]
        r1_strong = int(((sub["main_R1xday_crI_2_5"] > 0) & (sub["main_R1xday_prob_gt_0"] >= 0.95)).sum())
        amc_strong = int(((sub["main_AMC_crI_2_5"] > 0) & (sub["main_AMC_prob_gt_0"] >= 0.95)).sum())
        interaction_rows = sub[sub["interaction_R1xday_x_AMC_prob_gt_0"].notna()]
        interaction_strong = int(
            (
                interaction_rows["interaction_R1xday_x_AMC_crI_2_5"] > 0
            ).sum()
        )
        interaction_prob = int((interaction_rows["interaction_R1xday_x_AMC_prob_gt_0"] >= 0.95).sum())
        cards.append(
            f"""
            <article class="summary-card">
              <div class="eyebrow">{escape(meta['family'])}</div>
              <h3>{escape(meta['label'])}</h3>
              <p>{escape(meta['description'])}</p>
              <div class="stats">
                <div><strong>{r1_strong}/{len(sub)}</strong><span>R1xday 稳健正向</span></div>
                <div><strong>{amc_strong}/{len(sub)}</strong><span>AMC 稳健正向</span></div>
                <div><strong>{interaction_strong}/{max(len(interaction_rows), 1)}</strong><span>交互项 CrI &gt; 0</span></div>
                <div><strong>{interaction_prob}/{max(len(interaction_rows), 1)}</strong><span>交互项 P(&gt;0) ≥ 95%</span></div>
              </div>
            </article>
            """
        )
    return "".join(cards)


def build_archive_cards(archive_df: pd.DataFrame) -> str:
    cards: list[str] = []
    for _, row in archive_df.sort_values("archive_rank").iterrows():
        temp_label = str(row.get("temperature_proxy", "温度代理"))
        temp_coef = row.get("coef_temperature_proxy", row.get("coef_TA"))
        temp_p = row.get("p_temperature_proxy", row.get("p_TA"))
        variable_chips = "".join(
            f"<span>{escape(item.strip())}</span>"
            for item in str(row["variables"]).split(" | ")
            if item.strip()
        )
        cards.append(
            f"""
            <article class="model-card">
              <div class="card-top">
                <span class="eyebrow">#{int(row['archive_rank'])} · {escape(str(row['role_label']))}</span>
                <span class="chip">{escape(str(row['fe_label']))}</span>
              </div>
              <h3>{escape(str(row['scheme_id']))}</h3>
              <p>{escape(str(row['reason']))}</p>
              <div class="eyebrow" style="margin-top:6px;">{escape(str(row.get('archive_group_label', '模型归档')))}</div>
              <div class="chip-row">{variable_chips}</div>
              <div class="metric-grid">
                <div><strong>R1xday</strong><span>{fmt_signed(row['coef_R1xday'])} · p={fmt_p(row['p_R1xday'])}</span></div>
                <div><strong>AMC</strong><span>{fmt_signed(row['coef_AMC'])} · p={fmt_p(row['p_AMC'])}</span></div>
                <div><strong>{escape(temp_label)}</strong><span>{fmt_signed(temp_coef)} · p={fmt_p(temp_p)}</span></div>
                <div><strong>R²</strong><span>{fmt_num(row['r2_model'])}</span></div>
              </div>
            </article>
            """
        )
    return "".join(cards)


def build_diagnostic_summary(diag: pd.DataFrame) -> dict[str, str]:
    if diag.empty:
        return {"max_rhat": "—", "min_ess_bulk": "—", "min_ess_tail": "—"}
    return {
        "max_rhat": fmt_num(diag["r_hat"].max(), 2),
        "min_ess_bulk": f"{int(diag['ess_bulk'].min()):,}",
        "min_ess_tail": f"{int(diag['ess_tail'].min()):,}",
    }


def build_variant_tables(bridge: pd.DataFrame, diag: pd.DataFrame, archive_df: pd.DataFrame) -> str:
    sections: list[str] = []
    diag_summary = (
        diag.groupby(["model_id", "variant_id"], as_index=False)
        .agg(max_rhat=("r_hat", "max"), min_ess_bulk=("ess_bulk", "min"), min_ess_tail=("ess_tail", "min"))
    )

    for variant_id in VARIANT_ORDER:
        sub = bridge[bridge["variant_id"] == variant_id].copy()
        if sub.empty:
            continue
        meta = VARIANT_META[variant_id]
        sub = sub.sort_values("model_id", key=lambda s: s.map(lambda v: model_sort_key(v, archive_df)))
        rows: list[str] = []
        for _, row in sub.iterrows():
            diag_row = diag_summary[
                (diag_summary["model_id"] == row["model_id"]) & (diag_summary["variant_id"] == variant_id)
            ]
            diag_pick = diag_row.iloc[0] if not diag_row.empty else None
            r1_label, r1_tone = effect_status(
                row["main_R1xday_posterior_mean"],
                row["main_R1xday_crI_2_5"],
                row["main_R1xday_crI_97_5"],
                row["main_R1xday_prob_gt_0"],
            )
            amc_label, amc_tone = effect_status(
                row["main_AMC_posterior_mean"],
                row["main_AMC_crI_2_5"],
                row["main_AMC_crI_97_5"],
                row["main_AMC_prob_gt_0"],
            )
            interaction_text = "—"
            if pd.notna(row["interaction_R1xday_x_AMC_posterior_mean"]):
                int_label, int_tone = effect_status(
                    row["interaction_R1xday_x_AMC_posterior_mean"],
                    row["interaction_R1xday_x_AMC_crI_2_5"],
                    row["interaction_R1xday_x_AMC_crI_97_5"],
                    row["interaction_R1xday_x_AMC_prob_gt_0"],
                )
                interaction_text = (
                    f"{badge(int_label, int_tone)}<div class=\"stack\">"
                    f"<span>{fmt_signed(row['interaction_R1xday_x_AMC_posterior_mean'])}</span>"
                    f"<span>{escape(fmt_interval(row['interaction_R1xday_x_AMC_crI_2_5'], row['interaction_R1xday_x_AMC_crI_97_5']))}</span>"
                    f"<span>P(&gt;0)={escape(fmt_prob(row['interaction_R1xday_x_AMC_prob_gt_0']))}</span>"
                    f"</div>"
                )
            rows.append(
                f"""
                <tr>
                  <td>
                    <strong>{escape(str(row['scheme_id']))}</strong><br />
                    <span class="muted">{escape(str(row['model_id']))}</span>
                  </td>
                  <td>
                    {badge(r1_label, r1_tone)}
                    <div class="stack">
                      <span>{fmt_signed(row['main_R1xday_posterior_mean'])}</span>
                      <span>{escape(fmt_interval(row['main_R1xday_crI_2_5'], row['main_R1xday_crI_97_5']))}</span>
                      <span>P(&gt;0)={escape(fmt_prob(row['main_R1xday_prob_gt_0']))}</span>
                    </div>
                  </td>
                  <td>
                    {badge(amc_label, amc_tone)}
                    <div class="stack">
                      <span>{fmt_signed(row['main_AMC_posterior_mean'])}</span>
                      <span>{escape(fmt_interval(row['main_AMC_crI_2_5'], row['main_AMC_crI_97_5']))}</span>
                      <span>P(&gt;0)={escape(fmt_prob(row['main_AMC_prob_gt_0']))}</span>
                    </div>
                  </td>
                  <td>{interaction_text}</td>
                  <td>
                    <div class="stack">
                      <span>freq R1={fmt_signed(row['freq_coef_R1xday'])}</span>
                      <span>freq AMC={fmt_signed(row['freq_coef_AMC'])}</span>
                      <span>max R̂={fmt_num(diag_pick['max_rhat'], 2) if diag_pick is not None else '—'}</span>
                    </div>
                  </td>
                </tr>
                """
            )
        sections.append(
            f"""
            <section class="variant-block">
              <div class="section-head">
                <div>
                  <div class="eyebrow">{escape(meta['family'])}</div>
                  <h3>{escape(meta['label'])}</h3>
                </div>
                <p>{escape(meta['description'])}</p>
              </div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>模型</th>
                      <th>R1xday</th>
                      <th>AMC</th>
                      <th>Interaction</th>
                      <th>频率学 / 诊断</th>
                    </tr>
                  </thead>
                  <tbody>
                    {''.join(rows)}
                  </tbody>
                </table>
              </div>
            </section>
            """
        )
    return "".join(sections)


def build_control_family_notes(bridge: pd.DataFrame) -> str:
    rows: list[str] = []
    for family in ["Year-only", "Province-only", "Province + year"]:
        family_variants = [key for key, value in VARIANT_META.items() if value["family"] == family]
        family_df = bridge[bridge["variant_id"].isin(family_variants)].copy()
        if family_df.empty:
            continue
        r1_positive = int((family_df["main_R1xday_prob_gt_0"] >= 0.95).sum())
        amc_positive = int((family_df["main_AMC_prob_gt_0"] >= 0.95).sum())
        interaction_df = family_df[family_df["interaction_R1xday_x_AMC_prob_gt_0"].notna()]
        interaction_positive = int((interaction_df["interaction_R1xday_x_AMC_prob_gt_0"] >= 0.95).sum())
        rows.append(
            f"""
            <article class="note-card">
              <div class="eyebrow">{escape(family)}</div>
              <h3>{escape(family)} 的读法</h3>
              <p>这组口径一共覆盖 {len(family_df)} 个模型结果。R1xday 后验 P(&gt;0)≥95% 的有 {r1_positive} 个，AMC 对应有 {amc_positive} 个，交互项达到 95% 的有 {interaction_positive}/{max(len(interaction_df), 1)} 个。</p>
            </article>
            """
        )
    return "".join(rows)


def build_download_links(download_targets: dict[str, str]) -> str:
    links = []
    for name, target in download_targets.items():
        links.append(f'<a href="{escape(target)}">{escape(name)}</a>')
    return "".join(links)


def build_metadata_payload(
    archive_df: pd.DataFrame,
    bridge: pd.DataFrame,
    primary: pd.DataFrame,
    diag: pd.DataFrame,
) -> dict[str, object]:
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_count": int(len(archive_df)),
        "variant_count": int(bridge["variant_id"].nunique()),
        "bridge_rows": int(len(bridge)),
        "primary_rows": int(len(primary)),
        "diagnostic_rows": int(len(diag)),
        "source_dir": str(SUMMARY_DIR.relative_to(ROOT)).replace("\\", "/"),
        "archive_path": str(MODEL_ARCHIVE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "downloads": list(DOWNLOAD_FILES),
    }


def build_html(
    archive_df: pd.DataFrame,
    bridge: pd.DataFrame,
    primary: pd.DataFrame,
    diag: pd.DataFrame,
    download_targets: dict[str, str],
    metadata_payload: dict[str, object],
) -> str:
    diagnostics = build_diagnostic_summary(diag)
    year_only_add = bridge[bridge["variant_id"] == "year_only_additive"]
    province_amp = bridge[bridge["variant_id"] == "province_only_amplification"]
    province_year_add = bridge[bridge["variant_id"] == "province_year_additive"]

    hero_stats = [
        ("Archived models", str(len(archive_df)), "原始主线 4 模型与严筛扩展 8 模型一起进入贝叶斯镜像。"),
        ("Bayesian variants", str(bridge["variant_id"].nunique()), "每个模型都跑 6 个 Bayesian variants。"),
        (
            "Year-only robust R1",
            f"{int((year_only_add['main_R1xday_crI_2_5'] > 0).sum())}/{len(year_only_add)}",
            "Year-only additive 下 R1xday 95% CrI 完全高于 0 的模型数。",
        ),
        (
            "Province-only interaction",
            f"{int((province_amp['interaction_R1xday_x_AMC_prob_gt_0'] >= 0.95).sum())}/{len(province_amp)}",
            "Province-only amplification 下交互项 P(>0)≥95% 的模型数。",
        ),
        (
            "Two-way compression",
            f"{int((province_year_add['main_R1xday_prob_gt_0'] >= 0.95).sum())}/{len(province_year_add)}",
            "Province + year additive 下 R1xday 还保持高后验支持的模型数。",
        ),
        ("Max R̂", diagnostics["max_rhat"], "用于快速看链是否稳定。"),
    ]

    hero_cards = "".join(
        f"""
        <article class="hero-card">
          <div class="eyebrow">{escape(title)}</div>
          <strong>{escape(value)}</strong>
          <p>{escape(note)}</p>
        </article>
        """
        for title, value, note in hero_stats
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>贝叶斯分析 · 12 模型归档</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --panel: rgba(255,255,255,0.92);
      --panel-strong: #ffffff;
      --ink: #1b2730;
      --muted: #5d6b73;
      --line: rgba(27,39,48,0.10);
      --accent: #b45332;
      --accent-2: #1f6a72;
      --accent-3: #4d7b56;
      --shadow: 0 18px 48px rgba(27,39,48,0.10);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 14px;
      --sans: "Trebuchet MS", "Segoe UI", sans-serif;
      --mono: "Cascadia Mono", Consolas, monospace;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: var(--sans);
      background:
        radial-gradient(circle at top left, rgba(180,83,50,0.10), transparent 26%),
        radial-gradient(circle at top right, rgba(31,106,114,0.12), transparent 24%),
        linear-gradient(180deg, #faf8f3 0%, #f1eee8 100%);
    }}
    .page {{
      width: min(1380px, calc(100vw - 26px));
      margin: 16px auto 28px;
      display: grid;
      gap: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 28px;
      display: grid;
      gap: 22px;
    }}
    .hero-top {{
      display: grid;
      grid-template-columns: 1.5fr 1fr;
      gap: 20px;
      align-items: start;
    }}
    .eyebrow {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent-2);
      font-weight: 700;
    }}
    h1, h2, h3, h4 {{
      margin: 0;
      line-height: 1.15;
    }}
    h1 {{
      font-size: clamp(34px, 4vw, 54px);
      max-width: 14ch;
    }}
    .hero p, .section-head p, .model-card p, .note-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.65;
      font-size: 15px;
    }}
    .hero-copy {{
      display: grid;
      gap: 14px;
    }}
    .hero-side {{
      display: grid;
      gap: 12px;
    }}
    .hero-note, .note-card {{
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 16px 18px;
      display: grid;
      gap: 8px;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .hero-card {{
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 16px 18px;
      display: grid;
      gap: 8px;
    }}
    .hero-card strong {{
      font-size: 24px;
    }}
    .nav {{
      position: sticky;
      top: 10px;
      z-index: 5;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 14px 18px;
      background: rgba(255,255,255,0.82);
      border: 1px solid var(--line);
      border-radius: 999px;
      backdrop-filter: blur(12px);
    }}
    .nav a {{
      text-decoration: none;
      color: var(--ink);
      padding: 9px 12px;
      border-radius: 999px;
      font-weight: 700;
      background: rgba(31,106,114,0.06);
    }}
    .section {{
      padding: 24px 26px;
      display: grid;
      gap: 18px;
    }}
    .section-head {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr);
      gap: 16px;
      align-items: end;
    }}
    .summary-grid, .archive-grid, .notes-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }}
    .summary-card, .model-card {{
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 16px 18px;
      display: grid;
      gap: 10px;
    }}
    .summary-card .stats {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .summary-card .stats div {{
      background: rgba(180,83,50,0.06);
      border-radius: var(--radius-md);
      padding: 10px 12px;
      display: grid;
      gap: 4px;
    }}
    .summary-card .stats strong {{
      font-size: 18px;
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .chip, .chip-row span {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      border: 1px solid rgba(27,39,48,0.10);
      background: rgba(31,106,114,0.08);
      color: var(--accent-2);
      font-weight: 700;
    }}
    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric-grid div {{
      display: grid;
      gap: 4px;
      padding: 10px 12px;
      border-radius: var(--radius-md);
      background: rgba(27,39,48,0.04);
    }}
    .metric-grid strong {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      background: var(--panel-strong);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 980px;
    }}
    th, td {{
      text-align: left;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #f8f6f1;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-size: 12px;
      z-index: 1;
    }}
    tr:last-child td {{
      border-bottom: none;
    }}
    .variant-stack {{
      display: grid;
      gap: 14px;
    }}
    .variant-block {{
      display: grid;
      gap: 12px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 8px;
    }}
    .badge.strong {{
      color: #175c36;
      background: rgba(77,123,86,0.14);
    }}
    .badge.directional {{
      color: #7a4c12;
      background: rgba(180,83,50,0.16);
    }}
    .badge.negative {{
      color: #8d2431;
      background: rgba(168, 73, 91, 0.14);
    }}
    .badge.muted {{
      color: var(--muted);
      background: rgba(27,39,48,0.08);
    }}
    .stack {{
      display: grid;
      gap: 2px;
      color: var(--muted);
    }}
    .muted {{
      color: var(--muted);
    }}
    .downloads {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .downloads a {{
      text-decoration: none;
      color: var(--ink);
      padding: 10px 13px;
      border-radius: 999px;
      background: rgba(31,106,114,0.08);
      border: 1px solid rgba(31,106,114,0.12);
      font-weight: 700;
    }}
    .footer {{
      padding: 0 4px 8px;
      color: var(--muted);
      text-align: center;
      font-size: 13px;
    }}
    @media (max-width: 1024px) {{
      .hero-top, .section-head {{
        grid-template-columns: 1fr;
      }}
      .hero-grid {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
    @media (max-width: 720px) {{
      .page {{
        width: calc(100vw - 12px);
        margin: 8px auto 18px;
      }}
      .hero, .section {{
        padding: 18px;
      }}
      .hero-grid {{
        grid-template-columns: 1fr;
      }}
      .metric-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="hero panel">
      <div class="hero-top">
        <div class="hero-copy">
          <div class="eyebrow">Bayesian Analysis</div>
          <h1>把原始主线 4 模型与严筛扩展 8 模型一起镜像到贝叶斯分析里。</h1>
          <p>这页不再沿用旧的“三方案”写死结构，而是直接围绕当前 12 模型归档展开。先看整体结论，再看每个变体，再追到单模型结果和诊断，这样更适合写结果段和方法补充。</p>
        </div>
        <div class="hero-side">
          <div class="hero-note">
            <strong>核心读法</strong>
            <p>如果 Year-only additive 下 R1xday 和 AMC 都稳定为正，说明主效应在贝叶斯框架里被复现；如果 province-only amplification 下交互项抬起，说明“放大效应”更像省际差异控制后的附加证据。</p>
          </div>
          <div class="hero-note">
            <strong>这页接了什么</strong>
            <p>直接读取 `selected_models.csv` 的 12 模型归档，再对每个模型跑 6 个 Bayesian variants，共 72 个 posterior bridge 结果。</p>
          </div>
          <div class="hero-note">
            <strong>解释边界</strong>
            <p>贝叶斯页主要回答“频率学主线能否复现”和“交互项有没有抬起来”。它不是新的选模入口，而是对已归档模型的概率化复核。</p>
          </div>
        </div>
      </div>
      <div class="hero-grid">
        {hero_cards}
      </div>
    </header>

    <nav class="nav panel">
      <a href="#overview">变体概览</a>
      <a href="#archive">模型归档</a>
      <a href="#variants">逐变体结果</a>
      <a href="#downloads">数据下载</a>
    </nav>

    <section class="section panel" id="overview">
      <div class="section-head">
        <div>
          <div class="eyebrow">Variant Overview</div>
          <h2>先看 6 条贝叶斯镜像线各自复现了什么。</h2>
        </div>
        <p>每张卡片都在回答同一件事：这条口径下，R1xday、AMC 和交互项分别有多少模型达到了“稳健正向”或高后验支持。</p>
      </div>
      <div class="summary-grid">
        {build_variant_summary_cards(bridge)}
      </div>
      <div class="notes-grid">
        {build_control_family_notes(bridge)}
      </div>
    </section>

    <section class="section panel" id="archive">
      <div class="section-head">
        <div>
          <div class="eyebrow">Archived Models</div>
          <h2>这 12 个模型就是当前贝叶斯页的完整输入。</h2>
        </div>
        <p>这里直接把“原始主线 4 模型 + 严筛扩展 8 模型”的归档摆出来，方便你把频率学筛选、贝叶斯桥接、后续反事实和未来情景的模型来源串成同一条主线。</p>
      </div>
      <div class="archive-grid">
        {build_archive_cards(archive_df)}
      </div>
    </section>

    <section class="section panel" id="variants">
      <div class="section-head">
        <div>
          <div class="eyebrow">Variant Results</div>
          <h2>逐变体查看 12 模型的 posterior 结果。</h2>
        </div>
        <p>表里同时放了频率学系数、贝叶斯 posterior 和收敛诊断，便于直接判断“信号方向”“区间是否跨 0”以及“链是否稳定”。</p>
      </div>
      <div class="variant-stack">
        {build_variant_tables(bridge, diag, archive_df)}
      </div>
    </section>

    <section class="section panel" id="downloads">
      <div class="section-head">
        <div>
          <div class="eyebrow">Downloads</div>
          <h2>网页里的关键表都可以直接继续追到源 CSV。</h2>
        </div>
        <p>如果你要写方法补充、核对模型收敛或继续做可视化，优先用下面这些文件。</p>
      </div>
      <div class="downloads">
        {build_download_links(download_targets)}
      </div>
    </section>

    <div class="footer">Generated at {escape(metadata_payload['generated_at'])} · Source: 4 贝叶斯分析/results/model_summaries</div>
  </div>
</body>
</html>
"""


def main() -> None:
    PUBLIC_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    archive_df = read_csv(MODEL_ARCHIVE_PATH)
    primary = read_csv(PRIMARY_SUMMARY)
    bridge = read_csv(BRIDGE_SUMMARY)
    diag = read_csv(DIAGNOSTICS)

    for name, source in DOWNLOAD_FILES.items():
        shutil.copy2(source, PUBLIC_DATA_DIR / name)

    metadata_payload = build_metadata_payload(archive_df, bridge, primary, diag)
    PUBLIC_METADATA_PATH.write_text(
        json.dumps(metadata_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    public_html = build_html(
        archive_df,
        bridge,
        primary,
        diag,
        download_targets=PUBLIC_DOWNLOAD_TARGETS,
        metadata_payload=metadata_payload,
    )
    (PUBLIC_OUTPUT_DIR / "index.html").write_text(public_html, encoding="utf-8")

    local_html = build_html(
        archive_df,
        bridge,
        primary,
        diag,
        download_targets=LOCAL_DOWNLOAD_TARGETS,
        metadata_payload=metadata_payload,
    )
    LOCAL_OUTPUT_PATH.write_text(local_html, encoding="utf-8")

    print(f"Wrote Bayesian dashboard to {PUBLIC_OUTPUT_DIR / 'index.html'}")
    print(f"Wrote Bayesian local dashboard to {LOCAL_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
