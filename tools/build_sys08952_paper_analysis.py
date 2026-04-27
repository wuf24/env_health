from __future__ import annotations

import csv
import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "public_dashboards" / "sys-08952-paper-analysis"
DATA_DIR = OUTPUT_DIR / "data"
OUTPUT_HTML = OUTPUT_DIR / "index.html"
OUTPUT_PAYLOAD = DATA_DIR / "sys08952_paper_payload.json"

DECISION_PAYLOAD = (
    ROOT
    / "public_dashboards"
    / "variable-group-deep-dive"
    / "data"
    / "decision_payload.json"
)
BAYES_DIR = ROOT / "4 贝叶斯分析" / "results" / "model_summaries"
COUNTERFACTUAL_OVERALL = (
    ROOT
    / "5 反事实推演"
    / "results"
    / "AMR_AGG"
    / "counterfactual_outputs"
    / "national_overall.csv"
)
FUTURE_2050_COMPARE = (
    ROOT
    / "6 未来情景分析"
    / "results"
    / "baseline_mode_compare"
    / "main_model_2050_compare.csv"
)

TARGET_SCHEME_ID = "SYS_08952"
TARGET_MODEL_ID = "SYS_08952 | Province: No / Year: Yes"

SCENARIO_ORDER = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
SCENARIO_LABELS = {
    "ssp119": "SSP1-1.9",
    "ssp126": "SSP1-2.6",
    "ssp245": "SSP2-4.5",
    "ssp370": "SSP3-7.0",
    "ssp585": "SSP5-8.5",
}
BAYES_VARIANT_ORDER = [
    "year_only_additive",
    "year_only_amplification",
    "province_only_additive",
    "province_only_amplification",
    "province_year_additive",
    "province_year_amplification",
]
BAYES_VARIANT_LABELS = {
    "year_only_additive": "Year-only 主效应",
    "year_only_amplification": "Year-only 放大效应",
    "province_only_additive": "Province-only 主效应",
    "province_only_amplification": "Province-only 放大效应",
    "province_year_additive": "Province + Year 主效应",
    "province_year_amplification": "Province + Year 放大效应",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value: Any, digits: int = 3, *, signed: bool = False) -> str:
    numeric = as_float(value)
    if numeric is None:
        return "—"
    prefix = "+" if signed and numeric > 0 else ""
    return f"{prefix}{numeric:.{digits}f}"


def fmt_pct(value: Any, digits: int = 1) -> str:
    numeric = as_float(value)
    if numeric is None:
        return "—"
    return f"{numeric:.{digits}f}%"


def fmt_prob(value: Any) -> str:
    numeric = as_float(value)
    if numeric is None:
        return "—"
    return f"{100 * numeric:.1f}%"


def fmt_p(value: Any) -> str:
    numeric = as_float(value)
    if numeric is None:
        return "—"
    if numeric < 0.0001:
        return "<0.0001"
    return f"{numeric:.4f}"


def fmt_interval(low: Any, high: Any, digits: int = 3) -> str:
    low_num = as_float(low)
    high_num = as_float(high)
    if low_num is None or high_num is None:
        return "—"
    return f"[{low_num:.{digits}f}, {high_num:.{digits}f}]"


def clean_variable(value: Any) -> str:
    return str(value).replace("\r\n", "\n").replace("\n-", " - ").replace("\n", " ").strip()


def signed_class(value: Any) -> str:
    numeric = as_float(value)
    if numeric is None:
        return ""
    return "positive" if numeric >= 0 else "negative"


def find_target_model(decision_payload: dict[str, Any]) -> dict[str, Any]:
    for model in decision_payload.get("models", []):
        if model.get("scheme_id") == TARGET_SCHEME_ID and model.get("model_id") == TARGET_MODEL_ID:
            return model
    raise KeyError(f"Could not find {TARGET_MODEL_ID} in {DECISION_PAYLOAD}")


def bayes_summary_path(variant_id: str) -> Path:
    return BAYES_DIR / (
        f"SYS_08952__ProvinceNo-YearYes__{variant_id}_posterior_summary.csv"
    )


def load_bayes_rows() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for variant_id in BAYES_VARIANT_ORDER:
        path = bayes_summary_path(variant_id)
        if not path.exists():
            out[variant_id] = []
            continue
        rows = []
        for row in read_csv(path):
            rows.append(
                {
                    **row,
                    "variable": clean_variable(row.get("variable")),
                    "posterior_mean": as_float(row.get("posterior_mean")),
                    "crI_2_5": as_float(row.get("crI_2_5")),
                    "crI_97_5": as_float(row.get("crI_97_5")),
                    "prob_gt_0": as_float(row.get("prob_gt_0")),
                }
            )
        out[variant_id] = rows
    return out


def first_bayes_row(
    bayes_rows: dict[str, list[dict[str, Any]]],
    variant_id: str,
    variable: str,
    effect_scope: str | None = None,
) -> dict[str, Any] | None:
    for row in bayes_rows.get(variant_id, []):
        if row.get("variable") != variable:
            continue
        if effect_scope is not None and row.get("effect_scope") != effect_scope:
            continue
        return row
    return None


def load_future_rows() -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(FUTURE_2050_COMPARE):
        if row.get("scheme_id") != TARGET_SCHEME_ID:
            continue
        if row.get("statistic") != "median":
            continue
        rows.append(
            {
                **row,
                "baseline_pred_mean": as_float(row.get("baseline_pred_mean")),
                "scenario_adjustment_mean": as_float(row.get("scenario_adjustment_mean")),
                "scenario_pred_mean": as_float(row.get("scenario_pred_mean")),
                "delta_vs_baseline_mean": as_float(row.get("delta_vs_baseline_mean")),
                "delta_vs_last_observed": as_float(row.get("delta_vs_last_observed")),
                "rx1day_baseline_mean": as_float(row.get("rx1day_baseline_mean")),
                "rx1day_scenario_mean": as_float(row.get("rx1day_scenario_mean")),
            }
        )
    return rows


def future_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(row["baseline_mode"], {})[row["scenario_id"]] = row
    return out


def load_counterfactual_rows() -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(COUNTERFACTUAL_OVERALL):
        if row.get("scheme_id") != TARGET_SCHEME_ID or row.get("role_id") != "main_model":
            continue
        rows.append(
            {
                **row,
                "actual_minus_counterfactual_mean": as_float(
                    row.get("actual_minus_counterfactual_mean")
                ),
                "relative_change_pct_mean": as_float(row.get("relative_change_pct_mean")),
            }
        )
    return rows


def html_list(items: list[str]) -> str:
    return "".join(f"<li>{escape(item)}</li>" for item in items)


def coefficient_table(model: dict[str, Any]) -> str:
    rows = []
    for item in model["fe"]["coefficients"]:
        coef = as_float(item.get("coef"))
        p_value = as_float(item.get("p_value"))
        tag = "核心变量" if item.get("is_core") else ("显著控制项" if p_value is not None and p_value < 0.05 else "控制项")
        rows.append(
            f"""
            <tr>
              <td><strong>{escape(clean_variable(item.get("predictor")))}</strong><span>{escape(tag)}</span></td>
              <td class="{signed_class(coef)}">{fmt(coef, 3, signed=True)}</td>
              <td>{fmt_interval(item.get("ci_low"), item.get("ci_high"), 3)}</td>
              <td>{fmt_p(p_value)}</td>
              <td>{interpret_coefficient(clean_variable(item.get("predictor")), coef, p_value)}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def interpret_coefficient(variable: str, coef: float | None, p_value: float | None) -> str:
    if coef is None:
        return "未估计。"
    if variable == "R1xday":
        return "极端单日降雨越高，AMR 指标越高；这是主气候暴露。"
    if variable == "抗菌药物使用强度":
        return "抗菌药物使用越强，AMR 指标越高；这是核心人类压力变量。"
    if variable == "TA（°C）":
        return "温度通道为正且显著，是反事实和未来情景里最主要的气候贡献来源。"
    if variable == "氮氧化物":
        return "污染代理为正且显著，提示城市/工业环境压力与 AMR 同向。"
    if variable == "医疗水平":
        return "医疗系统暴露或检测能力代理为正，论文中宜作为调整变量解释。"
    if p_value is not None and p_value < 0.05:
        return "方向和统计证据较明确，可作为控制项结果报告。"
    direction = "正向" if coef > 0 else "负向"
    return f"{direction}但证据不足，主要承担控制混杂的作用。"


def bayes_core_table(bayes_rows: dict[str, list[dict[str, Any]]]) -> str:
    rows = []
    for variant_id in BAYES_VARIANT_ORDER:
        r1 = first_bayes_row(bayes_rows, variant_id, "R1xday", "main")
        amc = first_bayes_row(bayes_rows, variant_id, "抗菌药物使用强度", "main")
        interaction = first_bayes_row(
            bayes_rows,
            variant_id,
            "R1xday × 抗菌药物使用强度",
            "interaction",
        )
        rows.append(
            f"""
            <tr>
              <td><strong>{escape(BAYES_VARIANT_LABELS[variant_id])}</strong><span>{escape(variant_id)}</span></td>
              <td>{bayes_cell(r1)}</td>
              <td>{bayes_cell(amc)}</td>
              <td>{bayes_cell(interaction)}</td>
              <td>{bayes_variant_reading(variant_id, r1, amc, interaction)}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def bayes_cell(row: dict[str, Any] | None) -> str:
    if row is None:
        return "<span class=\"muted\">未设该项</span>"
    return (
        f"<strong>{fmt(row.get('posterior_mean'), 3, signed=True)}</strong>"
        f"<span>95% CrI {fmt_interval(row.get('crI_2_5'), row.get('crI_97_5'), 3)}</span>"
        f"<span>P(&gt;0) {fmt_prob(row.get('prob_gt_0'))}</span>"
    )


def crosses_zero(row: dict[str, Any] | None) -> bool:
    if row is None:
        return False
    low = as_float(row.get("crI_2_5"))
    high = as_float(row.get("crI_97_5"))
    if low is None or high is None:
        return False
    return low <= 0 <= high


def bayes_variant_reading(
    variant_id: str,
    r1: dict[str, Any] | None,
    amc: dict[str, Any] | None,
    interaction: dict[str, Any] | None,
) -> str:
    if variant_id == "year_only_additive":
        return "与主模型 Year FE 口径最贴近；R1xday 与 AMC 的可信区间均在 0 以上。"
    if variant_id == "year_only_amplification":
        if crosses_zero(interaction):
            return "主效应仍稳健；交互项均值为正，但可信区间跨 0，适合作方向性支持。"
        return "主效应与交互项均支持放大效应。"
    if variant_id.startswith("province_year"):
        return "双重控制后主效应明显收缩，说明信号很大部分来自年份控制后的跨省/结构差异。"
    if variant_id.startswith("province_only"):
        return "吸收省际长期差异后主效应减弱；交互项方向可作为稳健性参考。"
    return "作为 Bayes 稳健性桥接结果报告。"


def counterfactual_table(rows: list[dict[str, Any]]) -> str:
    ordered = {
        "all_climate_to_baseline": 1,
        "temperature_to_baseline": 2,
        "r1xday_to_baseline": 3,
    }
    rows = sorted(rows, key=lambda row: ordered.get(row["scenario_id"], 99))
    return "\n".join(
        f"""
        <tr>
          <td><strong>{escape(row['scenario_label'])}</strong><span>{escape(row['scenario_id'])}</span></td>
          <td class="{signed_class(row.get('actual_minus_counterfactual_mean'))}">{fmt(row.get('actual_minus_counterfactual_mean'), 3, signed=True)}</td>
          <td>{fmt_pct(row.get('relative_change_pct_mean'), 1)}</td>
          <td>{counterfactual_reading(row['scenario_id'])}</td>
        </tr>
        """
        for row in rows
    )


def counterfactual_reading(scenario_id: str) -> str:
    if scenario_id == "all_climate_to_baseline":
        return "主气候归因结果：当前气候暴露相对基准期抬高 AMR 指标。"
    if scenario_id == "temperature_to_baseline":
        return "温度贡献最大，是气候通道中最强的组成部分。"
    if scenario_id == "r1xday_to_baseline":
        return "极端降雨贡献较小但方向一致，支撑 R1xday 主线。"
    return "气候变量回拨情景。"


def future_table(rows: list[dict[str, Any]], mode_id: str) -> str:
    lookup = future_lookup(rows).get(mode_id, {})
    return "\n".join(
        future_row_html(lookup[scenario_id])
        for scenario_id in SCENARIO_ORDER
        if scenario_id in lookup
    )


def future_row_html(row: dict[str, Any]) -> str:
    return f"""
      <tr>
        <td><strong>{escape(SCENARIO_LABELS.get(row['scenario_id'], row['scenario_id']))}</strong><span>{escape(row.get('scenario_label', ''))}</span></td>
        <td>{fmt(row.get('baseline_pred_mean'), 2)}</td>
        <td class="{signed_class(row.get('delta_vs_baseline_mean'))}">{fmt(row.get('delta_vs_baseline_mean'), 3, signed=True)}</td>
        <td>{fmt(row.get('scenario_pred_mean'), 2)}</td>
        <td>{fmt(row.get('rx1day_scenario_mean'), 2)}</td>
      </tr>
    """


def scenario_delta_bar(rows: list[dict[str, Any]]) -> str:
    lookup = future_lookup(rows).get("lancet_ets", {})
    values = [
        as_float(lookup.get(scenario_id, {}).get("delta_vs_baseline_mean"))
        for scenario_id in SCENARIO_ORDER
    ]
    usable = [value for value in values if value is not None]
    if not usable:
        return ""
    low = min(usable)
    high = max(usable)
    span = max(high - low, 1e-9)
    blocks = []
    for scenario_id, value in zip(SCENARIO_ORDER, values):
        if value is None:
            continue
        left = (value - low) / span * 100
        width = max(4, abs(value) / max(abs(low), abs(high), 1e-9) * 46)
        blocks.append(
            f"""
            <div class="delta-row">
              <span>{escape(SCENARIO_LABELS[scenario_id])}</span>
              <div class="delta-track">
                <i style="left:{left:.2f}%; width:{width:.2f}%;" class="{signed_class(value)}"></i>
              </div>
              <strong class="{signed_class(value)}">{fmt(value, 3, signed=True)}</strong>
            </div>
            """
        )
    return "\n".join(blocks)


def write_payload(
    model: dict[str, Any],
    bayes_rows: dict[str, list[dict[str, Any]]],
    counterfactual_rows: list[dict[str, Any]],
    future_rows: list[dict[str, Any]],
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": model,
        "bayes_posterior_rows": bayes_rows,
        "counterfactual_rows": counterfactual_rows,
        "future_2050_rows": future_rows,
    }
    OUTPUT_PAYLOAD.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def build_html(
    model: dict[str, Any],
    bayes_rows: dict[str, list[dict[str, Any]]],
    counterfactual_rows: list[dict[str, Any]],
    future_rows: list[dict[str, Any]],
) -> str:
    fe = model["fe"]
    year_add_r1 = first_bayes_row(bayes_rows, "year_only_additive", "R1xday", "main")
    year_add_amc = first_bayes_row(
        bayes_rows, "year_only_additive", "抗菌药物使用强度", "main"
    )
    year_amp_interaction = first_bayes_row(
        bayes_rows,
        "year_only_amplification",
        "R1xday × 抗菌药物使用强度",
        "interaction",
    )
    cf_map = {row["scenario_id"]: row for row in counterfactual_rows}
    future_by_mode = future_lookup(future_rows)
    lancet_585 = future_by_mode["lancet_ets"]["ssp585"]
    lancet_119 = future_by_mode["lancet_ets"]["ssp119"]
    x_585 = future_by_mode["x_driven"]["ssp585"]
    x_119 = future_by_mode["x_driven"]["ssp119"]
    spread_585_119 = (
        as_float(lancet_585["delta_vs_baseline_mean"])
        - as_float(lancet_119["delta_vs_baseline_mean"])
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SYS_08952 论文分析专页</title>
  <style>
    :root {{
      --bg: #f7f9fb;
      --surface: #ffffff;
      --surface-2: #eef4f6;
      --ink: #17252c;
      --muted: #61717a;
      --line: #d8e1e6;
      --teal: #0f766e;
      --blue: #2563eb;
      --amber: #b45309;
      --rose: #be123c;
      --shadow: 0 18px 40px rgba(21, 32, 39, 0.10);
      --serif: Georgia, "Times New Roman", serif;
      --sans: "Segoe UI", "Microsoft YaHei UI", Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      color: var(--ink);
      background:
        linear-gradient(180deg, #edf3f5 0%, #f7f9fb 32%, #eef4f6 100%);
    }}
    a {{ color: inherit; }}
    .page {{
      width: min(1180px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 18px 0 42px;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 14px;
      font-size: 14px;
    }}
    .topbar a {{
      text-decoration: none;
      color: var(--muted);
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      padding: 9px 12px;
      border-radius: 8px;
      transition: border-color 180ms ease, color 180ms ease, background 180ms ease;
    }}
    .topbar a:hover, .topbar a:focus-visible {{
      color: var(--teal);
      border-color: rgba(15, 118, 110, 0.38);
      background: #fff;
      outline: none;
    }}
    .hero {{
      border-radius: 8px;
      background: linear-gradient(135deg, #16343a 0%, #0f766e 58%, #204564 100%);
      color: #f9fcfb;
      padding: clamp(24px, 5vw, 46px);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .eyebrow {{
      margin: 0 0 10px;
      font-size: 12px;
      line-height: 1.4;
      letter-spacing: 0.11em;
      text-transform: uppercase;
      color: rgba(249, 252, 251, 0.78);
    }}
    h1, h2, h3 {{
      margin: 0;
      letter-spacing: 0;
    }}
    h1 {{
      max-width: 960px;
      font-family: var(--serif);
      font-size: clamp(34px, 5vw, 58px);
      line-height: 1.05;
    }}
    .hero p {{
      max-width: 980px;
      margin: 18px 0 0;
      color: rgba(249, 252, 251, 0.90);
      line-height: 1.8;
      font-size: 17px;
    }}
    .hero strong {{ color: #ffffff; }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-top: 26px;
    }}
    .metric {{
      min-height: 126px;
      border: 1px solid rgba(255, 255, 255, 0.20);
      background: rgba(255, 255, 255, 0.10);
      border-radius: 8px;
      padding: 14px;
    }}
    .metric span {{
      display: block;
      min-height: 30px;
      color: rgba(249, 252, 251, 0.74);
      font-size: 12px;
      line-height: 1.45;
    }}
    .metric strong {{
      display: block;
      margin: 8px 0 6px;
      font-size: clamp(21px, 2.5vw, 34px);
      line-height: 1;
      overflow-wrap: anywhere;
    }}
    .metric em {{
      display: block;
      font-style: normal;
      color: rgba(249, 252, 251, 0.82);
      font-size: 12px;
      line-height: 1.45;
    }}
    .nav {{
      position: sticky;
      top: 0;
      z-index: 3;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 14px 0;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(247, 249, 251, 0.94);
      backdrop-filter: blur(12px);
    }}
    .nav a {{
      text-decoration: none;
      padding: 8px 10px;
      border-radius: 8px;
      color: var(--muted);
      font-weight: 700;
      font-size: 13px;
    }}
    .nav a:hover, .nav a:focus-visible {{
      color: var(--teal);
      background: #e7f3f1;
      outline: none;
    }}
    section.block {{
      margin-top: 14px;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
      box-shadow: 0 10px 28px rgba(21, 32, 39, 0.06);
      padding: clamp(20px, 3vw, 30px);
    }}
    .section-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: start;
      margin-bottom: 18px;
    }}
    .section-head .eyebrow {{ color: var(--teal); }}
    h2 {{
      font-family: var(--serif);
      font-size: clamp(26px, 3vw, 38px);
      line-height: 1.12;
    }}
    h3 {{
      font-size: 18px;
      line-height: 1.25;
    }}
    p {{
      margin: 10px 0 0;
      color: var(--muted);
      line-height: 1.85;
      font-size: 15px;
    }}
    .callout {{
      border-left: 4px solid var(--teal);
      background: #f1f7f6;
      padding: 14px 16px;
      border-radius: 8px;
      color: #284247;
      line-height: 1.85;
    }}
    .grid {{
      display: grid;
      gap: 12px;
    }}
    .grid.two {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .grid.three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .mini-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #fbfdfe;
    }}
    .mini-card strong {{
      display: block;
      font-size: 22px;
      line-height: 1.1;
      margin-top: 8px;
    }}
    .mini-card span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }}
    .mini-card p {{ font-size: 14px; }}
    .tag-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      border: 1px solid #cddae0;
      background: #f6fafb;
      color: #284247;
      border-radius: 8px;
      padding: 5px 9px;
      font-size: 13px;
    }}
    .table-wrap {{
      width: 100%;
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }}
    table {{
      width: 100%;
      min-width: 760px;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th {{
      text-align: left;
      padding: 11px 12px;
      background: #edf4f6;
      color: #34484f;
      border-bottom: 1px solid var(--line);
      white-space: nowrap;
    }}
    td {{
      padding: 12px;
      border-bottom: 1px solid #edf1f3;
      vertical-align: top;
      line-height: 1.55;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    td span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-top: 3px;
    }}
    .positive {{ color: var(--teal); font-weight: 800; }}
    .negative {{ color: var(--rose); font-weight: 800; }}
    .muted {{ color: var(--muted); }}
    .figure-grid {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 12px;
      margin-top: 14px;
    }}
    figure {{
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }}
    figure img {{
      display: block;
      width: 100%;
      height: auto;
      background: #f5f8fa;
    }}
    figcaption {{
      padding: 10px 12px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
      border-top: 1px solid var(--line);
    }}
    .delta-panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #fbfdfe;
    }}
    .delta-row {{
      display: grid;
      grid-template-columns: 82px minmax(150px, 1fr) 80px;
      gap: 10px;
      align-items: center;
      margin: 12px 0;
      font-size: 13px;
    }}
    .delta-track {{
      position: relative;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(90deg, #f2d7df 0 50%, #dcefeb 50% 100%);
      overflow: hidden;
    }}
    .delta-track::after {{
      content: "";
      position: absolute;
      top: -4px;
      bottom: -4px;
      left: 50%;
      width: 1px;
      background: rgba(23, 37, 44, 0.34);
    }}
    .delta-track i {{
      position: absolute;
      top: 2px;
      height: 6px;
      border-radius: 999px;
      transform: translateX(-50%);
      background: var(--teal);
    }}
    .delta-track i.negative {{ background: var(--rose); }}
    .writing {{
      display: grid;
      gap: 12px;
    }}
    .writing article {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #fbfdfe;
    }}
    .writing h3 {{
      color: #21383f;
      margin-bottom: 8px;
    }}
    .writing p {{
      color: #41545b;
      margin: 0;
    }}
    .note-list {{
      margin: 12px 0 0;
      padding-left: 20px;
      color: var(--muted);
      line-height: 1.8;
    }}
    code {{
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 0.95em;
      color: #203a44;
      background: #edf4f6;
      border: 1px solid #d9e5e8;
      padding: 1px 6px;
      border-radius: 6px;
    }}
    @media (max-width: 980px) {{
      .hero-grid, .grid.two, .grid.three, .figure-grid, .section-head {{
        grid-template-columns: 1fr;
      }}
      .nav {{ position: static; }}
    }}
    @media (max-width: 560px) {{
      .page {{ width: calc(100vw - 14px); padding-top: 8px; }}
      .topbar {{ flex-direction: column; align-items: stretch; }}
      .hero, section.block {{ padding: 18px; }}
      .delta-row {{ grid-template-columns: 76px 1fr; }}
      .delta-row strong {{ grid-column: 2; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <div class="topbar">
      <a href="../index.html">返回发布入口</a>
      <div class="tag-row" aria-label="source links">
        <a href="../variable-group-deep-dive/index.html">模型决策页</a>
        <a href="../bayes-analysis/index.html">Bayes</a>
        <a href="../counterfactual-amr-agg/index.html">反事实</a>
        <a href="../future-scenario-analysis/index.html">未来情景</a>
      </div>
    </div>

    <header class="hero">
      <div class="eyebrow">Final Paper Model Only</div>
      <h1>SYS_08952 论文分析专页</h1>
      <p>
        本页只展示 <strong>SYS_08952 | Province: No / Year: Yes</strong>，并按论文写作顺序把
        “模型选择 → 固定效应主结果 → Bayes 验证 → 反事实归因 → 未来情景 → 写作边界”
        串成一条完整证据链。这里不再横向展开 12 个候选模型，避免最终论文分析被备选模型分散。
      </p>
      <div class="hero-grid">
        <div class="metric"><span>模型定位</span><strong>主模型</strong><em>12 模型归档第 1；全空间性能排名第 {escape(str(fe.get('performance_rank')))}</em></div>
        <div class="metric"><span>固定效应解释力</span><strong>{fmt(fe.get('r2_model'), 3)}</strong><em>R² model；Year FE 主规格</em></div>
        <div class="metric"><span>Bayes 主气候效应</span><strong>{fmt(year_add_r1.get('posterior_mean') if year_add_r1 else None, 3, signed=True)}</strong><em>R1xday 95% CrI {fmt_interval(year_add_r1.get('crI_2_5') if year_add_r1 else None, year_add_r1.get('crI_97_5') if year_add_r1 else None, 3)}</em></div>
        <div class="metric"><span>反事实气候贡献</span><strong>{fmt(cf_map['all_climate_to_baseline']['actual_minus_counterfactual_mean'], 3, signed=True)}</strong><em>全部气候变量恢复基准</em></div>
        <div class="metric"><span>2050 高排放增量</span><strong>{fmt(lancet_585['delta_vs_baseline_mean'], 3, signed=True)}</strong><em>SSP5-8.5 相对 Lancet ETS baseline</em></div>
      </div>
    </header>

    <nav class="nav" aria-label="page sections">
      <a href="#selection">模型选择</a>
      <a href="#fe">固定效应</a>
      <a href="#bayes">Bayes</a>
      <a href="#counterfactual">反事实</a>
      <a href="#future">未来情景</a>
      <a href="#writing">论文表述</a>
      <a href="#limits">边界</a>
    </nav>

    <section class="block" id="selection">
      <div class="section-head">
        <div>
          <div class="eyebrow">1. Model Choice</div>
          <h2>为什么最终主模型可以选 SYS_08952</h2>
          <p>选择它的核心理由不是单一指标最高，而是“统计信号、变量故事、后续推演可承接性”最均衡。</p>
        </div>
      </div>
      <div class="callout">
        <strong>一句话结论：</strong>SYS_08952 在 Year FE 口径下保留了 R1xday、抗菌药物使用强度、温度和污染代理的同向正效应，
        同时变量组足够紧凑，能自然连接到 Bayes 放大效应、气候反事实和 2050 SSP 情景。
      </div>
      <div class="grid two" style="margin-top: 12px;">
        <article class="mini-card">
          <span>固定效应设定</span>
          <strong>Province: No / Year: Yes</strong>
          <p>Year FE 吸收每一年全国共同变化，例如宏观政策、检测体系、全国性医疗变化和共同时间冲击。没有加入 Province FE，意味着模型仍保留省际结构差异中与气候、AMC 和社会环境相关的解释信息。</p>
        </article>
        <article class="mini-card">
          <span>论文里的解释口径</span>
          <strong>年份共同冲击被控制后的关联</strong>
          <p>它更适合写成“在控制年份共同变化后，极端降雨、抗菌药物使用强度和温度与 AMR 水平呈正相关”，而不是写成严格的单一因果效应。</p>
        </article>
      </div>
      <div class="tag-row">
        {"".join(f'<span class="tag">{escape(clean_variable(item))}</span>' for item in model.get("variables", []))}
      </div>
      <div class="grid three" style="margin-top: 12px;">
        <article class="mini-card"><span>论文平衡排名</span><strong>{escape(str(model['scores'].get('paper_rank')))}</strong><p>在最终候选中作为正文主模型最顺畅。</p></article>
        <article class="mini-card"><span>R² 排名</span><strong>{escape(str(model['scores'].get('r2_rank')))}</strong><p>拟合表现是候选组内最强之一。</p></article>
        <article class="mini-card"><span>最大标准化 VIF</span><strong>{fmt(fe.get('max_vif_z'), 2)}</strong><p>没有出现明显破坏主线解释的共线性压力。</p></article>
      </div>
    </section>

    <section class="block" id="fe">
      <div class="section-head">
        <div>
          <div class="eyebrow">2. Fixed Effects Main Result</div>
          <h2>固定效应主模型回答“哪些因素与 AMR 同向变化”</h2>
          <p>这一层是论文主结果的骨架。系数可理解为当前标准化建模尺度下的条件关联方向和强度。</p>
        </div>
      </div>
      <div class="grid three">
        <article class="mini-card"><span>R1xday</span><strong class="positive">{fmt(fe.get('coef_R1xday'), 3, signed=True)}</strong><p>p={fmt_p(fe.get('p_R1xday'))}，极端单日降雨主线成立。</p></article>
        <article class="mini-card"><span>AMC</span><strong class="positive">{fmt(fe.get('coef_AMC'), 3, signed=True)}</strong><p>p={fmt_p(fe.get('p_AMC'))}，抗菌药物压力信号更强。</p></article>
        <article class="mini-card"><span>温度代理</span><strong class="positive">{fmt(fe.get('coef_temperature_proxy'), 3, signed=True)}</strong><p>{escape(fe.get('temperature_proxy', ''))}，p={fmt_p(fe.get('p_temperature_proxy'))}。</p></article>
      </div>
      <div class="table-wrap" style="margin-top: 14px;">
        <table>
          <thead>
            <tr>
              <th>变量</th>
              <th>系数</th>
              <th>95% CI</th>
              <th>p 值</th>
              <th>论文解释</th>
            </tr>
          </thead>
          <tbody>
            {coefficient_table(model)}
          </tbody>
        </table>
      </div>
      <ul class="note-list">
        <li>R1xday、AMC、TA 和氮氧化物均为正且达到常用显著性阈值，这让主模型具备清晰的“气候暴露 + 抗菌药物压力 + 环境压力”叙事。</li>
        <li>医疗水平为正且显著，论文中更适合解释为医疗接触、检测能力或医疗系统暴露的控制代理，而不是简单写成医疗水平导致 AMR 升高。</li>
        <li>人均生活用水量、猪年底头数、文盲比例在该规格中更多承担调整混杂作用，不宜把它们写成强结论。</li>
      </ul>
    </section>

    <section class="block" id="bayes">
      <div class="section-head">
        <div>
          <div class="eyebrow">3. Bayesian Bridge</div>
          <h2>Bayes 层检验“主效应是否稳、放大效应是否够强”</h2>
          <p>Bayes 不是替代固定效应，而是把主模型换成概率语言：看后验均值、可信区间和大于 0 的概率。</p>
        </div>
      </div>
      <div class="grid three">
        <article class="mini-card"><span>Year-only R1xday</span><strong class="positive">{fmt(year_add_r1.get('posterior_mean') if year_add_r1 else None, 3, signed=True)}</strong><p>95% CrI {fmt_interval(year_add_r1.get('crI_2_5') if year_add_r1 else None, year_add_r1.get('crI_97_5') if year_add_r1 else None, 3)}，P(&gt;0) {fmt_prob(year_add_r1.get('prob_gt_0') if year_add_r1 else None)}。</p></article>
        <article class="mini-card"><span>Year-only AMC</span><strong class="positive">{fmt(year_add_amc.get('posterior_mean') if year_add_amc else None, 3, signed=True)}</strong><p>95% CrI {fmt_interval(year_add_amc.get('crI_2_5') if year_add_amc else None, year_add_amc.get('crI_97_5') if year_add_amc else None, 3)}，P(&gt;0) {fmt_prob(year_add_amc.get('prob_gt_0') if year_add_amc else None)}。</p></article>
        <article class="mini-card"><span>R1xday × AMC</span><strong class="positive">{fmt(year_amp_interaction.get('posterior_mean') if year_amp_interaction else None, 3, signed=True)}</strong><p>95% CrI {fmt_interval(year_amp_interaction.get('crI_2_5') if year_amp_interaction else None, year_amp_interaction.get('crI_97_5') if year_amp_interaction else None, 3)}，方向为正但跨 0。</p></article>
      </div>
      <div class="table-wrap" style="margin-top: 14px;">
        <table>
          <thead>
            <tr>
              <th>Bayes 规格</th>
              <th>R1xday 后验</th>
              <th>AMC 后验</th>
              <th>交互项后验</th>
              <th>论文读法</th>
            </tr>
          </thead>
          <tbody>
            {bayes_core_table(bayes_rows)}
          </tbody>
        </table>
      </div>
      <div class="callout" style="margin-top: 14px;">
        <strong>建议写法：</strong>Bayesian year-only model reproduced the positive R1xday and AMC main effects.
        The R1xday × AMC interaction was positive on average but its 95% credible interval crossed zero; therefore,
        amplification should be described as directionally supported rather than a strong confirmatory result.
      </div>
    </section>

    <section class="block" id="counterfactual">
      <div class="section-head">
        <div>
          <div class="eyebrow">4. Counterfactual Attribution</div>
          <h2>反事实层回答“如果气候暴露回到基准期，AMR 会低多少”</h2>
          <p><code>actual - counterfactual</code> 为正，表示当前气候暴露相对于基准期抬高了模型预测的 AMR 指标。</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>反事实设定</th>
              <th>Actual - Counterfactual</th>
              <th>相对变化</th>
              <th>解释</th>
            </tr>
          </thead>
          <tbody>
            {counterfactual_table(counterfactual_rows)}
          </tbody>
        </table>
      </div>
      <div class="figure-grid">
        <figure>
          <img src="../counterfactual-amr-agg/figures/national_yearly_main_model.png" alt="SYS_08952 反事实全国年度轨迹" loading="lazy" />
          <figcaption>主模型全国年度反事实轨迹。它用于展示实际预测与气候变量回拨情景之间的距离。</figcaption>
        </figure>
        <div class="grid">
          <article class="mini-card"><span>全部气候变量恢复基准</span><strong class="positive">{fmt(cf_map['all_climate_to_baseline']['actual_minus_counterfactual_mean'], 3, signed=True)}</strong><p>这是论文最适合报告的总体气候归因数字。</p></article>
          <article class="mini-card"><span>仅温度恢复基准</span><strong class="positive">{fmt(cf_map['temperature_to_baseline']['actual_minus_counterfactual_mean'], 3, signed=True)}</strong><p>温度贡献约占主体，说明未来情景里温度通道不能被忽略。</p></article>
          <article class="mini-card"><span>仅 R1xday 恢复基准</span><strong class="positive">{fmt(cf_map['r1xday_to_baseline']['actual_minus_counterfactual_mean'], 3, signed=True)}</strong><p>R1xday 的边际贡献较小，但方向与 FE/Bayes 一致。</p></article>
        </div>
      </div>
      <ul class="note-list">
        <li>这里的反事实不是随机试验，而是基于已选模型系数的情景替换：固定其他变量，把气候变量替换到基准期水平。</li>
        <li>总体贡献约等于温度贡献加 R1xday 贡献，说明 SYS_08952 的气候归因主要由温度驱动，R1xday 提供额外但较小的极端降雨通道。</li>
      </ul>
    </section>

    <section class="block" id="future">
      <div class="section-head">
        <div>
          <div class="eyebrow">5. Future Scenario Projection</div>
          <h2>未来情景层回答“不同 SSP 路径会把 2050 AMR 推向哪里”</h2>
          <p>两个 baseline 口径影响绝对水平；气候情景增量则来自同一组气候路径和 SYS_08952 系数，因此两种 baseline 下的 SSP 增量一致。</p>
        </div>
      </div>
      <div class="grid three">
        <article class="mini-card"><span>Lancet ETS 2050 baseline</span><strong>{fmt(lancet_585.get('baseline_pred_mean'), 2)}</strong><p>SSP5-8.5 预测值 {fmt(lancet_585.get('scenario_pred_mean'), 2)}；SSP1-1.9 预测值 {fmt(lancet_119.get('scenario_pred_mean'), 2)}。</p></article>
        <article class="mini-card"><span>X-driven 2050 baseline</span><strong>{fmt(x_585.get('baseline_pred_mean'), 2)}</strong><p>SSP5-8.5 预测值 {fmt(x_585.get('scenario_pred_mean'), 2)}；SSP1-1.9 预测值 {fmt(x_119.get('scenario_pred_mean'), 2)}。</p></article>
        <article class="mini-card"><span>SSP5-8.5 与 SSP1-1.9 spread</span><strong class="positive">{fmt(spread_585_119, 3, signed=True)}</strong><p>高排放与低排放路径在 2050 的气候增量差距。</p></article>
      </div>
      <div class="grid two" style="margin-top: 14px;">
        <div>
          <h3>Lancet ETS baseline</h3>
          <div class="table-wrap" style="margin-top: 8px;">
            <table>
              <thead><tr><th>情景</th><th>Baseline</th><th>Δ vs baseline</th><th>Scenario pred</th><th>R1xday</th></tr></thead>
              <tbody>{future_table(future_rows, "lancet_ets")}</tbody>
            </table>
          </div>
        </div>
        <div>
          <h3>X-driven baseline</h3>
          <div class="table-wrap" style="margin-top: 8px;">
            <table>
              <thead><tr><th>情景</th><th>Baseline</th><th>Δ vs baseline</th><th>Scenario pred</th><th>R1xday</th></tr></thead>
              <tbody>{future_table(future_rows, "x_driven")}</tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="figure-grid">
        <figure>
          <img src="../future-scenario-analysis/results/lancet_ets/figures/figure5_style_main.png" alt="SYS_08952 Lancet ETS 未来情景主图" loading="lazy" />
          <figcaption>Lancet ETS 口径下的主模型未来情景图。Baseline 更贴近既有 AMR 历史趋势外推。</figcaption>
        </figure>
        <div class="delta-panel">
          <h3>2050 SSP 气候增量</h3>
          <p>以 Lancet ETS 口径展示，X-driven 下的增量相同。</p>
          {scenario_delta_bar(future_rows)}
        </div>
      </div>
      <ul class="note-list">
        <li>SSP5-8.5 相对 baseline 增加 {fmt(lancet_585.get('delta_vs_baseline_mean'), 3, signed=True)}，SSP1-1.9 相对 baseline 为 {fmt(lancet_119.get('delta_vs_baseline_mean'), 3, signed=True)}。</li>
        <li>SSP3-7.0 不一定高于 SSP2-4.5，说明当前未来情景的排序由省级 R1xday 路径和模型系数共同决定，不宜机械写成排放越高必然单调越高。</li>
      </ul>
    </section>

    <section class="block" id="writing">
      <div class="section-head">
        <div>
          <div class="eyebrow">6. Paper Narrative</div>
          <h2>可直接转化为论文段落的论文陈述逻辑</h2>
          <p>下面按结果章节的自然顺序组织，重点是让读者理解每一层分析为什么接在上一层之后。</p>
        </div>
      </div>
      <div class="writing">
        <article>
          <h3>模型选择段</h3>
          <p>在系统穷举模型中，SYS_08952 在 Year fixed effects 设定下表现为兼具拟合度和解释一致性的主模型。该模型同时纳入 R1xday、抗菌药物使用强度、TA、氮氧化物以及医疗、用水、畜牧和教育相关控制变量，能够在保留核心气候暴露与抗菌药物压力变量的同时，对主要社会环境混杂因素进行调整。因此，后续 Bayesian 验证、反事实推演和未来情景预测均以 SYS_08952 作为正文主模型。</p>
        </article>
        <article>
          <h3>固定效应结果段</h3>
          <p>在控制年份共同冲击后，R1xday 与 AMR 指标呈正相关（β={fmt(fe.get('coef_R1xday'), 3, signed=True)}, p={fmt_p(fe.get('p_R1xday'))}），抗菌药物使用强度同样呈显著正相关（β={fmt(fe.get('coef_AMC'), 3, signed=True)}, p={fmt_p(fe.get('p_AMC'))}）。温度代理 TA（β={fmt(fe.get('coef_temperature_proxy'), 3, signed=True)}, p={fmt_p(fe.get('p_temperature_proxy'))}）和污染代理氮氧化物（β={fmt(fe.get('coef_pollution_proxy'), 3, signed=True)}, p={fmt_p(fe.get('p_pollution_proxy'))}）也保持正向显著，提示 AMR 变化可能受到极端降雨、热环境、抗菌药物压力和城市环境压力的共同影响。</p>
        </article>
        <article>
          <h3>Bayes 验证段</h3>
          <p>Bayesian year-only additive model 对主效应提供了概率层面的支持：R1xday 的后验均值为 {fmt(year_add_r1.get('posterior_mean') if year_add_r1 else None, 3)}，95% CrI 为 {fmt_interval(year_add_r1.get('crI_2_5') if year_add_r1 else None, year_add_r1.get('crI_97_5') if year_add_r1 else None, 3)}；抗菌药物使用强度的后验均值为 {fmt(year_add_amc.get('posterior_mean') if year_add_amc else None, 3)}，95% CrI 为 {fmt_interval(year_add_amc.get('crI_2_5') if year_add_amc else None, year_add_amc.get('crI_97_5') if year_add_amc else None, 3)}。在包含 R1xday × AMC 的 amplification model 中，交互项后验均值为 {fmt(year_amp_interaction.get('posterior_mean') if year_amp_interaction else None, 3, signed=True)}，但可信区间跨 0，因此论文中应将放大效应表述为方向性支持，而非强确定性结论。</p>
        </article>
        <article>
          <h3>反事实段</h3>
          <p>基于 SYS_08952 的反事实推演显示，当所有气候变量恢复至基准期水平时，全国平均 AMR 指标相对于实际情景下降 {fmt(cf_map['all_climate_to_baseline']['actual_minus_counterfactual_mean'], 3)}。分解来看，温度变量恢复基准对应的差值为 {fmt(cf_map['temperature_to_baseline']['actual_minus_counterfactual_mean'], 3)}，仅 R1xday 恢复基准对应的差值为 {fmt(cf_map['r1xday_to_baseline']['actual_minus_counterfactual_mean'], 3)}。这说明在当前主模型下，温度通道贡献较大，极端降雨通道较小但方向一致。</p>
        </article>
        <article>
          <h3>未来情景段</h3>
          <p>在 2050 年 Lancet ETS baseline 下，SYS_08952 的 baseline 为 {fmt(lancet_585.get('baseline_pred_mean'), 2)}。相对于该 baseline，SSP5-8.5 的气候增量为 {fmt(lancet_585.get('delta_vs_baseline_mean'), 3, signed=True)}，SSP1-1.9 为 {fmt(lancet_119.get('delta_vs_baseline_mean'), 3, signed=True)}。在 X-driven baseline 下，2050 baseline 为 {fmt(x_585.get('baseline_pred_mean'), 2)}，但各 SSP 的气候增量保持一致，表明两种 baseline 主要改变未来 AMR 的绝对水平，而不改变气候情景增量的方向判断。</p>
        </article>
      </div>
    </section>

    <section class="block" id="limits">
      <div class="section-head">
        <div>
          <div class="eyebrow">7. Boundary Conditions</div>
          <h2>论文中需要主动说明的边界</h2>
        </div>
      </div>
      <div class="grid two">
        <article class="mini-card">
          <span>不是随机因果识别</span>
          <strong>用“关联”和“情景归因”更稳妥</strong>
          <p>固定效应、Bayes 和反事实构成的是一致性证据链，但不能等同于随机试验或自然实验意义上的因果效应。</p>
        </article>
        <article class="mini-card">
          <span>交互项不宜过度写强</span>
          <strong>方向支持，不作强结论</strong>
          <p>R1xday × AMC 后验均值为正，但 95% CrI 跨 0；正文可写为“suggestive amplification”。</p>
        </article>
        <article class="mini-card">
          <span>Year FE 的含义要讲清楚</span>
          <strong>保留省际结构信息</strong>
          <p>主模型没有 Province FE，因此解释重点是控制年份共同冲击后的省份间和省份年差异，不是严格的省内变化估计。</p>
        </article>
        <article class="mini-card">
          <span>未来情景看增量也看 baseline</span>
          <strong>两种 baseline 服务不同问题</strong>
          <p>Lancet ETS 更适合与文献口径对齐；X-driven 更适合展示未来协变量路径如何推开绝对水平。</p>
        </article>
      </div>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    decision_payload = load_json(DECISION_PAYLOAD)
    model = find_target_model(decision_payload)
    bayes_rows = load_bayes_rows()
    counterfactual_rows = load_counterfactual_rows()
    future_rows = load_future_rows()

    if not counterfactual_rows:
        raise RuntimeError("No counterfactual rows found for SYS_08952.")
    if not future_rows:
        raise RuntimeError("No future-scenario rows found for SYS_08952.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_payload(model, bayes_rows, counterfactual_rows, future_rows)
    OUTPUT_HTML.write_text(
        build_html(model, bayes_rows, counterfactual_rows, future_rows),
        encoding="utf-8",
    )
    print(f"Wrote SYS_08952 paper analysis to {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
