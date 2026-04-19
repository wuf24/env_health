from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "2 固定效应模型"
RESULT_DIR = MODEL_DIR / "results"
COUNTERFACTUAL_SELECTED_MODELS = (
    ROOT / "5 反事实推演" / "results" / "AMR_AGG" / "model_screening" / "selected_models.csv"
)
OUTPUT_HOME_HTML = MODEL_DIR / "results_dashboard.html"
OUTPUT_LANCET_HTML = MODEL_DIR / "results_dashboard_lancet.html"
OUTPUT_MATRIX_HTML = MODEL_DIR / "results_dashboard_matrix.html"

DISPLAY_RANK_LIMIT = 200
DISPLAY_VIF_TOP_N = 12
FE_ORDER = [
    "Province: No / Year: Yes",
    "Province: Yes / Year: No",
    "Province: Yes / Year: Yes",
]
FAMILY_LABELS = {
    "temperature_proxy": "温度代理",
    "pollution_proxy": "污染代理",
    "development_proxy": "发展代理",
    "water_sanitation_proxy": "供水/卫生代理",
    "livestock_proxy": "畜牧代理",
    "social_env_proxy": "社会环境代理",
    "hydro_proxy": "水文代理",
}
FAMILY_ORDER = [
    "temperature_proxy",
    "pollution_proxy",
    "development_proxy",
    "water_sanitation_proxy",
    "livestock_proxy",
    "social_env_proxy",
    "hydro_proxy",
]


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, str):
        return value.replace("\r\n", "\n").strip()
    return value


def split_items(value: Any, sep: str) -> list[str]:
    text = clean_value(value)
    if not text:
        return []
    return [item.strip() for item in str(text).split(sep) if item and item.strip()]


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(RESULT_DIR / name, encoding="utf-8-sig")


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def parse_family_selection(value: Any) -> dict[str, str]:
    text = clean_value(value)
    if not text or text == "manual_curated":
        return {}
    out: dict[str, str] = {}
    for part in str(text).split(" ; "):
        if "=" not in part:
            continue
        key, item = part.split("=", 1)
        out[key.strip()] = item.strip()
    return out


def share_text(count: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{count / total:.1%}"


def build_breakdown(series: pd.Series) -> list[dict[str, Any]]:
    total = int(series.shape[0])
    counter = series.value_counts()
    return [
        {
            "label": str(label),
            "count": int(count),
            "share": count / total if total else 0,
            "share_text": share_text(int(count), total),
        }
        for label, count in counter.items()
    ]


def build_signal_summary(df: pd.DataFrame, label: str) -> dict[str, Any]:
    count = int(df.shape[0])
    return {
        "label": label,
        "count": count,
        "avg_score": clean_value(df["performance_score"].mean()) if count else None,
        "r1_sig_count": int((df["p_R1xday"] < 0.05).sum()) if count else 0,
        "amc_sig_count": int((df["p_AMC"] < 0.05).sum()) if count else 0,
        "both_positive_count": int(((df["coef_R1xday"] > 0) & (df["coef_AMC"] > 0)).sum()) if count else 0,
    }


def load_counterfactual_selection() -> pd.DataFrame:
    if not COUNTERFACTUAL_SELECTED_MODELS.exists():
        return pd.DataFrame()
    return pd.read_csv(COUNTERFACTUAL_SELECTED_MODELS, encoding="utf-8-sig")


def build_counterfactual_force_include(
    ranking: pd.DataFrame, selected_models: pd.DataFrame
) -> dict[str, Any]:
    if selected_models.empty or "scheme_id" not in selected_models.columns:
        return {
            "selected_roles": [],
            "selected_scheme_ids": [],
            "forced_model_ids": [],
        }

    ranking_model_ids = set(ranking["model_id"].astype(str))
    selected_roles = []
    selected_scheme_ids: list[str] = []
    for row in selected_models.to_dict(orient="records"):
        scheme_id = clean_value(row.get("scheme_id"))
        if not scheme_id:
            continue
        scheme_text = str(scheme_id)
        selected_scheme_ids.append(scheme_text)
        selected_roles.append(
            {
                "role_id": clean_value(row.get("role_id")),
                "role_label": clean_value(row.get("role_label")),
                "scheme_id": scheme_text,
                "model_id": clean_value(row.get("model_id")),
            }
        )

    forced_model_ids: list[str] = []
    for scheme_id in dedupe_preserve_order(selected_scheme_ids):
        for fe_label in FE_ORDER:
            model_id = f"{scheme_id} | {fe_label}"
            if model_id in ranking_model_ids:
                forced_model_ids.append(model_id)

    return {
        "selected_roles": selected_roles,
        "selected_scheme_ids": dedupe_preserve_order(selected_scheme_ids),
        "forced_model_ids": dedupe_preserve_order(forced_model_ids),
    }


def parse_lancet_tables(df: pd.DataFrame, model_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for row in df[df["model_id"].isin(model_ids)].to_dict(orient="records"):
        model_id = clean_value(row.get("model_id"))
        predictor = clean_value(row.get("Predictor"))
        coef = clean_value(row.get("Coefficient"))
        ci = clean_value(row.get("95% CI"))
        p_value = clean_value(row.get("p value"))

        is_title = predictor == model_id and coef is None and ci is None and p_value is None
        is_spacer = predictor is None and coef is None and ci is None and p_value is None

        if is_title or is_spacer or not model_id:
            continue

        tables.setdefault(model_id, []).append(
            {
                "Predictor": predictor,
                "Coefficient": coef,
                "95% CI": ci,
                "p value": p_value,
            }
        )
    return tables


def build_matrix_rows(
    horizontal: pd.DataFrame,
    matrix_model_ids: list[str],
    ranking_map: dict[str, dict[str, Any]],
    summary_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    horizontal_index = horizontal.set_index("metric")
    matrix_rows: list[dict[str, Any]] = []
    for metric in [clean_value(item) for item in horizontal["metric"].tolist()]:
        source_row = horizontal_index.loc[metric] if metric in horizontal_index.index else None
        values: dict[str, Any] = {}
        for model_id in matrix_model_ids:
            value = None
            if source_row is not None and model_id in source_row.index:
                value = clean_value(source_row.get(model_id))
            if value is None:
                value = summary_map.get(model_id, {}).get(metric)
            if value is None:
                value = ranking_map.get(model_id, {}).get(metric)
            values[model_id] = clean_value(value)
        matrix_rows.append({"metric": metric, "values": values})
    return matrix_rows


def build_payload() -> dict[str, Any]:
    ranking = load_csv("exhaustive_model_ranking.csv")
    summary = load_csv("exhaustive_model_summary.csv")
    vif = load_csv("exhaustive_model_vif.csv")
    horizontal = load_csv("exhaustive_model_horizontal_compare_top200.csv")
    lancet = load_csv("exhaustive_model_lancet_tables.csv")
    scheme_catalog = load_csv("exhaustive_scheme_catalog.csv")
    counterfactual_selected = load_counterfactual_selection()
    counterfactual_force = build_counterfactual_force_include(ranking, counterfactual_selected)

    display_ids = list(
        dict.fromkeys(
            ranking.head(DISPLAY_RANK_LIMIT)["model_id"].tolist()
            + counterfactual_force["forced_model_ids"]
            + ranking.loc[ranking["scheme_source"] == "curated", "model_id"].tolist()
        )
    )
    display_id_set = set(display_ids)

    ranking_map = {
        clean_value(row["model_id"]): {k: clean_value(v) for k, v in row.items()}
        for row in ranking[ranking["model_id"].isin(display_id_set)].to_dict(orient="records")
    }
    summary_map = {
        clean_value(row["model_id"]): {k: clean_value(v) for k, v in row.items()}
        for row in summary[summary["model_id"].isin(display_id_set)].to_dict(orient="records")
    }
    display_ranking = ranking[ranking["model_id"].isin(display_id_set)].sort_values("performance_rank")
    counterfactual_forced_set = set(counterfactual_force["forced_model_ids"])

    ranking_records: list[dict[str, Any]] = []
    for row in display_ranking.to_dict(orient="records"):
        rec = {k: clean_value(v) for k, v in row.items()}
        full = summary_map[rec["model_id"]]
        family_map = parse_family_selection(full.get("family_selection"))
        source_group = rec.get("scheme_source")
        temperature_proxy = family_map.get("temperature_proxy") or ("人工方案" if source_group == "curated" else "未标注")
        pollution_proxy = family_map.get("pollution_proxy") or ("人工方案" if source_group == "curated" else "未标注")
        family_pairs = [
            {"label": FAMILY_LABELS.get(key, key), "value": value}
            for key, value in family_map.items()
        ]
        search_parts = [
            rec.get("model_id"),
            full.get("scheme_id"),
            full.get("scheme_note"),
            full.get("variables"),
            rec.get("sig_predictors_p_lt_0_05"),
            temperature_proxy,
            pollution_proxy,
            " ".join(value for value in family_map.values() if value),
        ]

        rec.update(
            {
                "scheme_id": full.get("scheme_id"),
                "scheme_note": full.get("scheme_note"),
                "variables_list": split_items(full.get("variables"), " | "),
                "significant_predictors": split_items(rec.get("sig_predictors_p_lt_0_05"), ","),
                "province_fe": full.get("province_fe"),
                "year_fe": full.get("year_fe"),
                "nobs": full.get("nobs"),
                "n_vars": full.get("n_vars"),
                "n_vars_label": f"{int(full['n_vars'])} vars" if full.get("n_vars") is not None else "—",
                "median_vif_z": full.get("median_vif_z"),
                "max_vif_raw": full.get("max_vif_raw"),
                "variables": full.get("variables"),
                "source_group": source_group,
                "family_pairs": family_pairs,
                "temperature_proxy": temperature_proxy,
                "pollution_proxy": pollution_proxy,
                "counterfactual_anchor": rec["model_id"] in counterfactual_forced_set,
                "search_text": " ".join(str(item) for item in search_parts if item).lower(),
            }
        )
        ranking_records.append(rec)

    vif_map: dict[str, list[dict[str, Any]]] = {model_id: [] for model_id in display_ids}
    vif_work = vif[vif["model_id"].isin(display_id_set)].sort_values(["model_id", "vif_z"], ascending=[True, False])
    for row in vif_work.to_dict(orient="records"):
        model_id = clean_value(row.get("model_id"))
        vif_map.setdefault(model_id, []).append(
            {
                "predictor": clean_value(row.get("predictor")),
                "vif_raw": clean_value(row.get("vif_raw")),
                "vif_z": clean_value(row.get("vif_z")),
                "abs_diff": clean_value(row.get("abs_diff")),
            }
        )
    for model_id in list(vif_map):
        vif_map[model_id] = vif_map[model_id][:DISPLAY_VIF_TOP_N]

    matrix_model_ids = display_ids
    matrix_rows = build_matrix_rows(horizontal, matrix_model_ids, ranking_map, summary_map)

    dashboard_summary = summary[summary["model_id"].isin(display_id_set)].sort_values("performance_rank")
    family_counters: dict[str, Counter[str]] = defaultdict(Counter)
    for item in dashboard_summary["family_selection"]:
        mapping = parse_family_selection(item)
        for family in FAMILY_ORDER:
            family_counters[family][mapping.get(family, "skip")] += 1
    family_summary = []
    family_total = max(int(dashboard_summary.shape[0]), 1)
    for family in FAMILY_ORDER:
        if not family_counters[family]:
            continue
        family_summary.append(
            {
                "label": FAMILY_LABELS.get(family, family),
                "choices": [
                    {
                        "label": name if name != "skip" else "未纳入",
                        "count": int(count),
                        "share": count / family_total,
                        "share_text": share_text(int(count), family_total),
                    }
                    for name, count in family_counters[family].most_common(4)
                ],
            }
        )

    variable_counter: Counter[str] = Counter()
    for text in summary.sort_values("performance_rank").head(100)["variables"]:
        for item in split_items(text, " | "):
            variable_counter[item] += 1
    variable_frequency = [
        {
            "label": label,
            "count": int(count),
            "share": count / 100,
            "share_text": share_text(int(count), 100),
        }
        for label, count in variable_counter.most_common(12)
    ]

    signal_windows = []
    for top_n in [20, 50, 100, 200]:
        top = ranking.head(top_n)
        signal_windows.append(build_signal_summary(top, f"Top {top_n}"))
    dashboard_signal_summary = build_signal_summary(display_ranking, "Dashboard 展示集")

    curated_work = ranking.merge(
        summary[["model_id", "scheme_note", "variables", "n_vars"]],
        on="model_id",
        how="left",
    )
    curated_highlights = []
    for row in curated_work[curated_work["scheme_source"] == "curated"].sort_values("performance_rank").head(8).to_dict(orient="records"):
        curated_highlights.append(
            {
                "performance_rank": clean_value(row.get("performance_rank")),
                "model_id": clean_value(row.get("model_id")),
                "fe_label": clean_value(row.get("fe_label")),
                "performance_score": clean_value(row.get("performance_score")),
                "coef_R1xday": clean_value(row.get("coef_R1xday")),
                "p_R1xday": clean_value(row.get("p_R1xday")),
                "coef_AMC": clean_value(row.get("coef_AMC")),
                "p_AMC": clean_value(row.get("p_AMC")),
                "n_vars": clean_value(row.get("n_vars")),
                "scheme_note": clean_value(row.get("scheme_note")),
                "variables_list": split_items(row.get("variables"), " | "),
            }
        )

    best_curated_df = ranking[ranking["scheme_source"] == "curated"].sort_values("performance_rank").head(1)
    best_curated = best_curated_df.iloc[0].to_dict() if not best_curated_df.empty else {}
    top_row = ranking.iloc[0].to_dict()

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_prefix": "exhaustive_*",
        "scope_note": (
            f"全量统计来自 {len(ranking):,} 个 exhaustive 模型；"
            f"页面展示集以 Top {DISPLAY_RANK_LIMIT} 为基础，额外强制纳入反事实入选方案展开后的 "
            f"{len(counterfactual_force['forced_model_ids']):,} 个 FE 模型，并保留全部 curated，共 {len(ranking_records):,} 个模型。"
        ),
        "total_models_all": int(len(ranking)),
        "total_schemes_all": int(scheme_catalog["scheme_id"].nunique()),
        "dashboard_models": int(len(ranking_records)),
        "dashboard_rank_limit": DISPLAY_RANK_LIMIT,
        "dashboard_scope_label": "Top 200 基础窗口 + 反事实入选方案三类 FE + 全部 curated",
        "dashboard_required_models": int(len(counterfactual_force["forced_model_ids"])),
        "dashboard_required_roles": int(len(counterfactual_force["selected_roles"])),
        "dashboard_required_schemes": int(len(counterfactual_force["selected_scheme_ids"])),
        "dashboard_required_model_ids": counterfactual_force["forced_model_ids"],
        "total_curated_models": int((ranking["scheme_source"] == "curated").sum()),
        "total_systematic_models": int((ranking["scheme_source"] == "systematic").sum()),
        "source_breakdown_all": build_breakdown(ranking["scheme_source"]),
        "fe_breakdown_all": build_breakdown(ranking["fe_label"]),
        "fe_breakdown_top200": build_breakdown(display_ranking["fe_label"]),
        "top_model": {
            "model_id": clean_value(top_row.get("model_id")),
            "performance_score": clean_value(top_row.get("performance_score")),
        },
        "best_curated": {
            "model_id": clean_value(best_curated.get("model_id")),
            "performance_rank": clean_value(best_curated.get("performance_rank")),
            "performance_score": clean_value(best_curated.get("performance_score")),
        },
        "family_summary_top200": family_summary,
        "dashboard_signal_summary": dashboard_signal_summary,
        "variable_frequency_top100": variable_frequency,
        "signal_windows": signal_windows,
        "curated_highlights": curated_highlights,
        "ranking": ranking_records,
        "matrix_model_ids": matrix_model_ids,
        "matrix_rows": matrix_rows,
        "lancet_tables": parse_lancet_tables(lancet, display_id_set),
        "vif_tables": vif_map,
        "source_labels": [label for label in ["systematic", "curated"] if label in {rec["source_group"] for rec in ranking_records}],
        "fe_labels": [label for label in FE_ORDER if label in {rec["fe_label"] for rec in ranking_records}],
        "temperature_labels": sorted({rec["temperature_proxy"] for rec in ranking_records}),
        "pollution_labels": sorted({rec["pollution_proxy"] for rec in ranking_records}),
        "n_var_labels": [f"{n} vars" for n in sorted({int(rec["n_vars"]) for rec in ranking_records if rec.get("n_vars") is not None})],
    }
    return payload


def build_html(payload: dict[str, Any], page_kind: str) -> str:
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AMR Exhaustive Dashboard</title>
  <style>
    :root{--bg:#f6efe7;--panel:rgba(255,249,242,.9);--ink:#18353c;--muted:#63777c;--line:rgba(24,53,60,.12);--accent:#bf5c39;--accent2:#2e7277;--gold:#d6a54c;--shadow:0 16px 48px rgba(39,35,31,.11);--r:22px;--r2:16px}
    *{box-sizing:border-box} html{scroll-behavior:smooth}
    body{margin:0;font-family:"Trebuchet MS","Segoe UI",sans-serif;color:var(--ink);background:radial-gradient(circle at top left,rgba(191,92,57,.15),transparent 26%),radial-gradient(circle at top right,rgba(46,114,119,.12),transparent 28%),linear-gradient(180deg,#f8f2e9 0%,#eef4f2 100%)}
    .page{width:min(1480px,calc(100vw - 24px));margin:12px auto 24px}
    .hero,.card{background:var(--panel);border:1px solid rgba(255,255,255,.55);box-shadow:var(--shadow);backdrop-filter:blur(10px)}
    .hero{border-radius:32px;padding:30px;background:linear-gradient(135deg,rgba(24,53,60,.97),rgba(42,96,97,.94));color:#faf6ef;overflow:hidden;position:relative}
    .hero:after{content:"";position:absolute;right:-40px;top:-40px;width:240px;height:240px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.18),transparent 66%)}
    .hero-grid{display:grid;grid-template-columns:1.6fr 1fr;gap:24px;align-items:end}
    .eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;opacity:.75;margin-bottom:10px}
    h1,h2,h3{margin:0;font-family:Georgia,"Times New Roman",serif;letter-spacing:-.02em}
    h1{font-size:clamp(32px,4vw,52px);line-height:1.02;margin-bottom:12px}
    .hero p,.sub{margin:0;color:rgba(250,246,239,.86);line-height:1.72;font-size:15px}
    .page-nav{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 0}
    .nav-link{display:inline-flex;align-items:center;gap:8px;padding:10px 14px;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.12);color:#fff8f2;text-decoration:none;font-size:13px;transition:.18s}
    .nav-link:hover{transform:translateY(-1px);background:rgba(255,255,255,.14)}
    .nav-link.active{background:linear-gradient(135deg,var(--gold),#c88d2b);border-color:transparent;color:#17343a;box-shadow:0 10px 24px rgba(215,165,76,.25);font-weight:700}
    .hero-meta,.chips,.pills,.filters{display:flex;flex-wrap:wrap;gap:8px}
    .hero-chip,.chip,.pill,.filter{border-radius:999px;padding:9px 12px;font-size:12px;border:1px solid rgba(255,255,255,.12)}
    .hero-chip{background:rgba(255,255,255,.1);color:#fffaf2}
    .hero-stats{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
    .hero-stat{padding:16px;border-radius:18px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.12)}
    .hero-stat .k{font-size:12px;opacity:.76;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}
    .hero-stat .v{font-size:29px;font-weight:800;line-height:1;margin-bottom:6px}
    .hero-stat .h{font-size:12px;line-height:1.45;color:rgba(250,246,239,.82)}
    .layout{display:grid;grid-template-columns:1fr;gap:18px;margin-top:18px}
    .sidebar{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;align-self:start;position:static}
    .card{border-radius:28px;padding:22px}
    .section-head{display:flex;justify-content:space-between;gap:12px;align-items:start;margin-bottom:14px}
    .section-head p{margin:6px 0 0;color:var(--muted);font-size:14px;line-height:1.6}
    .filter{cursor:pointer;border:1px solid var(--line);background:rgba(255,255,255,.7);color:var(--ink);transition:.18s}
    .filter.active{background:linear-gradient(135deg,var(--accent),#9a4326);border-color:transparent;color:#fff8f2;box-shadow:0 10px 22px rgba(191,92,57,.2)}
    .control-select,.control-input{width:100%;padding:11px 12px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.84);color:var(--ink);font:inherit}
    .mini-btn{cursor:pointer;border-radius:999px;padding:9px 12px;font-size:12px;border:1px solid var(--line);background:rgba(255,255,255,.7);color:var(--ink);transition:.18s}
    .mini-btn.active{background:linear-gradient(135deg,var(--accent),#9a4326);border-color:transparent;color:#fff8f2;box-shadow:0 10px 22px rgba(191,92,57,.2)}
    .pick{padding:14px;border-radius:18px;background:linear-gradient(180deg,rgba(255,255,255,.94),rgba(255,247,239,.92));border:1px solid rgba(24,53,60,.08);display:grid;gap:8px}
    .pick + .pick{margin-top:12px}
    .badge{width:max-content;padding:6px 10px;border-radius:999px;font-size:12px;font-weight:700;color:#fff;background:linear-gradient(135deg,var(--gold),#ba8623)}
    .badge.r2{background:linear-gradient(135deg,#7f9ca2,#5c747a)} .badge.r3{background:linear-gradient(135deg,#c57d54,#9c5538)} .badge.rn{background:linear-gradient(135deg,var(--accent2),#1f5a5f)}
    .chip{background:rgba(46,114,119,.1);color:var(--accent2);border-color:rgba(46,114,119,.1);font-weight:700}
    .chip.scheme{background:rgba(191,92,57,.12);color:#964427;border-color:rgba(191,92,57,.1)}
    .chip.source-curated{background:rgba(214,165,76,.15);color:#8e6215;border-color:rgba(214,165,76,.16)}
    .chip.source-systematic{background:rgba(46,114,119,.1);color:var(--accent2);border-color:rgba(46,114,119,.1)}
    .chip.soft,.pill{background:rgba(24,53,60,.06);color:var(--ink);border:1px solid rgba(24,53,60,.08)}
    .pill.good{background:rgba(46,114,119,.1);color:var(--accent2);border-color:rgba(46,114,119,.1)}
    .content{display:grid;gap:18px}
    #homeRankingSection,#homeDetailSection{min-height:min(76vh,980px)}
    #homeRankingSection{grid-column:1 / span 7;display:flex;flex-direction:column}
    #homeDetailSection{grid-column:8 / span 5;display:flex;flex-direction:column}
    #lancetSection,#matrixSection{grid-column:1 / -1}
    @media (min-width:1181px){.content{grid-template-columns:repeat(12,minmax(0,1fr))}}
    .table-wrap{overflow:auto;border:1px solid rgba(24,53,60,.08);border-radius:18px;background:rgba(255,255,255,.76)}
    table{width:100%;border-collapse:collapse;min-width:760px}
    th,td{padding:12px 14px;border-bottom:1px solid rgba(24,53,60,.08);text-align:left;vertical-align:top;font-size:13px;line-height:1.55}
    th{position:sticky;top:0;background:#fcf7ef;z-index:1;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
    .sort-btn{border:0;background:none;padding:0;font:inherit;color:inherit;display:inline-flex;align-items:center;gap:8px;cursor:pointer}
    .sort-btn .arrows{display:inline-grid;line-height:.7;gap:1px;opacity:.28;transition:.18s}
    .sort-btn .arrows span{display:block;font-size:10px}
    th:hover .sort-btn .arrows,.sort-btn.active .arrows{opacity:.95}
    .sort-btn.active.asc .up,.sort-btn.active.desc .down{color:var(--accent);font-weight:800}
    .ranking tbody tr{cursor:pointer;transition:.18s}
    .ranking tbody tr:hover{background:rgba(46,114,119,.06)} .ranking tbody tr.on{background:rgba(191,92,57,.09);box-shadow:inset 4px 0 0 var(--accent)}
    .score{font-weight:800;color:#934424}.good{color:#1c7c64;font-weight:700}.mid{color:#9a6d1d;font-weight:700}.bad{color:var(--muted)}
    .pos{color:#1d6c6f;font-weight:700}.neg{color:#a04834;font-weight:700}
    .score-strip,.detail-grid,.metric-grid{display:grid;gap:16px}
    .score-strip{grid-template-columns:1.45fr .9fr;margin-bottom:16px}
    .detail-grid{grid-template-columns:1.45fr .95fr}
    .metric-grid{grid-template-columns:repeat(4,1fr);margin-bottom:16px}
    .panel{border-radius:18px;border:1px solid rgba(24,53,60,.08);background:rgba(255,255,255,.78);padding:18px}
    .big{font-size:44px;line-height:1;font-weight:800;color:#964427}
    .bar{height:10px;border-radius:999px;background:rgba(24,53,60,.08);overflow:hidden;margin-top:12px}.bar>span{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--gold))}
    .metric{padding:16px;border-radius:16px;background:rgba(255,255,255,.8);border:1px solid rgba(24,53,60,.08)}
    .metric .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}.metric .v{font-size:22px;font-weight:800;line-height:1.1}
    .meta-row td{background:rgba(24,53,60,.04);color:var(--muted);font-weight:700}
    .matrix th:first-child,.matrix td:first-child{position:sticky;left:0;z-index:2}
    .matrix th:first-child{background:#fcf7ef}.matrix td:first-child{background:rgba(252,247,239,.98);font-weight:700}
    .bar-line{display:grid;gap:6px}
    .bar-line-head{display:flex;justify-content:space-between;gap:10px;font-size:12px;color:var(--muted)}
    .empty{padding:24px;border-radius:18px;background:rgba(255,255,255,.74);border:1px dashed rgba(24,53,60,.18);text-align:center;color:var(--muted)}
    .lancet-stack{display:grid;gap:18px}
    .scroll-window{max-height:min(48vh,520px);overflow:auto;padding-right:4px;scrollbar-gutter:stable}
    .scroll-window.compact{max-height:min(34vh,320px)}
    .scroll-window.tall{max-height:min(72vh,920px)}
    .table-wrap.windowed{max-height:min(58vh,760px);scrollbar-gutter:stable}
    .table-wrap.windowed.compact{max-height:min(34vh,320px)}
    #homeRankingSection .table-wrap.windowed{height:auto;max-height:none;flex:1;min-height:0}
    #detail{display:grid;gap:16px;align-content:start;flex:1;min-height:0;overflow:auto;padding-right:4px;scrollbar-gutter:stable}
    .pills.compact .pill{padding:7px 10px;font-size:11px}
    .hidden{display:none !important}
    @media (max-width:1320px){.sidebar{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media (max-width:1180px){.hero-grid,.layout,.score-strip,.detail-grid{grid-template-columns:1fr}.sidebar{position:static;grid-template-columns:1fr}.metric-grid{grid-template-columns:repeat(2,1fr)}#homeRankingSection,#homeDetailSection{grid-column:1 / -1;position:static;min-height:auto}}
    @media (max-width:760px){.page{width:calc(100vw - 12px);margin:6px auto 16px}.hero,.card{padding:18px;border-radius:22px}.hero-stats,.metric-grid{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <div class="page">
    <header class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">Exhaustive Search Dashboard</div>
          <h1>固定效应模型全空间结果仪表板</h1>
          <p>这版页面直接读取 <code>exhaustive_*</code> 结果。全量统计覆盖整批穷举模型，页面明细则聚焦 Top 模型与 curated 对照，帮助你更快判断哪些代理家族、哪些固定效应、哪些人工方案值得进入主线。</p>
          <div class="hero-meta" id="heroMeta"></div>
          <nav class="page-nav" id="pageNav">
            <a class="nav-link" data-page="home" href="results_dashboard.html">首页</a>
            <a class="nav-link" data-page="lancet" href="results_dashboard_lancet.html">Lancet 表</a>
            <a class="nav-link" data-page="matrix" href="results_dashboard_matrix.html">横向矩阵</a>
          </nav>
        </div>
        <div class="hero-stats" id="heroStats"></div>
      </div>
    </header>

    <div class="layout">
      <aside class="sidebar">
        <section class="card">
          <div class="section-head"><div><h2>筛选与范围</h2><p id="scopeNote">按来源、固定效应与代理家族快速筛选 dashboard 范围。</p></div></div>
          <div class="sub" style="color:var(--muted);font-size:12px;margin-bottom:8px">模型来源</div>
          <div class="filters" id="schemeFilters"></div>
          <div class="sub" style="color:var(--muted);font-size:12px;margin:16px 0 8px">固定效应</div>
          <div class="filters" id="feFilters"></div>
          <div class="sub" style="color:var(--muted);font-size:12px;margin:16px 0 8px">温度代理</div>
          <select class="control-select" id="temperatureSelect"></select>
          <div class="sub" style="color:var(--muted);font-size:12px;margin:16px 0 8px">污染代理</div>
          <select class="control-select" id="pollutionSelect"></select>
          <div class="sub" style="color:var(--muted);font-size:12px;margin:16px 0 8px">变量数</div>
          <select class="control-select" id="nVarSelect"></select>
          <div class="sub" style="color:var(--muted);font-size:12px;margin:16px 0 8px">搜索</div>
          <input class="control-input" id="searchInput" placeholder="搜 model / variable / note" />
          <div class="sub" style="color:var(--muted);font-size:12px;margin:16px 0 8px">页面上限</div>
          <div class="filters" id="pageLimitControls"></div>
        </section>
        <section class="card">
          <div class="section-head"><div><h2>当前 Top Picks</h2><p>跟随筛选条件实时变化。</p></div></div>
          <div id="topPicks"></div>
        </section>
        <section class="card">
          <div class="section-head"><div><h2>Curated 对照</h2><p>人工方案放回全空间排名后的相对位置。</p></div></div>
          <div id="schemeBest"></div>
        </section>
        <section class="card">
          <div class="section-head"><div><h2>全量线索</h2><p>这里只放整批 exhaustive 结果里最关键的结构信号。</p></div></div>
          <div id="batchInsight"></div>
        </section>
      </aside>

      <main class="content">
        <section class="card" id="homeRankingSection">
          <div class="section-head"><div><h2>模型浏览表</h2><p>首页只展示 dashboard 范围内的模型；全量 exhaustive 统计已上移到摘要卡。</p></div><div class="chips"><span class="chip soft" id="countChip"></span></div></div>
          <div class="table-wrap windowed"><table class="ranking" id="rankingTable"></table></div>
        </section>
        <section class="card" id="homeDetailSection">
          <div class="section-head"><div><h2>模型详情</h2><p>点击上表任意一行即可切换。这里会把代理家族、Lancet 表与 VIF 压到同一屏。</p></div></div>
          <div id="detail"></div>
        </section>
        <section class="card hidden" id="lancetSection">
          <div class="section-head"><div><h2>Lancet 风格结果表</h2><p>这里按当前筛选与页内上限展开结果表，避免一次性塞入过多模型。</p></div><div class="chips"><span class="chip soft" id="lancetCountChip"></span></div></div>
          <div class="lancet-stack" id="lancetGallery"></div>
        </section>
        <section class="card hidden" id="matrixSection">
          <div class="section-head"><div><h2>横向比较矩阵</h2><p>矩阵以 <code>exhaustive_model_horizontal_compare_top200.csv</code> 为基础，并为反事实锚点与 curated 补齐额外列，所以这里显示的是完整 dashboard 展示集。</p></div><div class="chips"><span class="chip soft" id="matrixCountChip"></span></div></div>
          <div class="table-wrap windowed"><table class="matrix" id="matrixTable"></table></div>
        </section>
      </main>
    </div>
  </div>

  <script id="dashboard-data" type="application/json">__PAYLOAD__</script>
  <script>
    const data = JSON.parse(document.getElementById('dashboard-data').textContent);
    const pageKind = "__PAGE_KIND__";
    const matrixModelSet = new Set(data.matrix_model_ids || []);
    const state = {
      source: '全部',
      fe: '全部',
      temperature: '全部',
      pollution: '全部',
      nvars: '全部',
      search: '',
      selected: data.ranking[0] ? data.ranking[0].model_id : null,
      sortKey: 'performance_rank',
      sortDir: 'asc',
      lancetLimit: 18,
      matrixLimit: 12,
    };
    const heroItems = [
      ['全量模型数', data.total_models_all, '来自 exhaustive_model_ranking.csv'],
      ['方案数量', data.total_schemes_all, 'systematic + curated 的唯一 scheme_id'],
      ['首页明细范围', data.dashboard_models, data.dashboard_scope_label || `Top ${data.dashboard_rank_limit} + curated`],
      ['最佳人工方案', data.best_curated && data.best_curated.performance_rank ? `#${data.best_curated.performance_rank}` : '—', data.best_curated && data.best_curated.model_id ? data.best_curated.model_id : '当前未找到 curated'],
    ];
    const sortDefaults = {
      performance_rank: 'asc',
      model_id: 'asc',
      scheme_id: 'asc',
      performance_score: 'desc',
      coef_R1xday: 'desc',
      coef_AMC: 'desc',
      r2_model: 'desc',
      n_vars: 'asc',
      max_vif_z: 'asc',
    };

    const metaRows = new Set(['Province','Year','R-squared','R-squared (Overall)','R² (within)','Total number of observations']);
    const html = (v) => (v === null || v === undefined ? '' : String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;'));
    const label = (v) => html(v).replace(/\\n/g,'<br>');
    const parseNum = (v) => {
      if (v === null || v === undefined || v === '') return Number.NaN;
      if (typeof v === 'string') {
        const text = v.trim();
        if (text.startsWith('<')) return Number(text.slice(1));
        const cleaned = text.replace(/\\*+/g, '');
        const n = Number(cleaned);
        return Number.isFinite(n) ? n : Number.NaN;
      }
      const n = Number(v);
      return Number.isFinite(n) ? n : Number.NaN;
    };
    const num = (v,d=3) => { const n = parseNum(v); return Number.isFinite(n) ? n.toFixed(d) : '—'; };
    const short = (v) => { const n = parseNum(v); return Number.isFinite(n) ? n.toFixed(3) : '—'; };
    const pcls = (v) => { const n = parseNum(v); if (!Number.isFinite(n)) return 'bad'; if (n < 0.05) return 'good'; if (n < 0.10) return 'mid'; return 'bad'; };
    const ccls = (v) => { const n = parseNum(v); if (!Number.isFinite(n)) return ''; return n >= 0 ? 'pos' : 'neg'; };
    const badge = (rank) => rank === 1 ? '' : rank === 2 ? ' r2' : rank === 3 ? ' r3' : ' rn';
    const sourceCls = (v) => v === 'curated' ? 'source-curated' : 'source-systematic';
    const stars = (p) => {
      const n = parseNum(p);
      if (!Number.isFinite(n)) return '';
      if (n < 0.001) return '***';
      if (n < 0.01) return '**';
      if (n < 0.05) return '*';
      return '';
    };

    function filteredBase() {
      return data.ranking.filter(row =>
        (state.source === '全部' || row.source_group === state.source) &&
        (state.fe === '全部' || row.fe_label === state.fe) &&
        (state.temperature === '全部' || row.temperature_proxy === state.temperature) &&
        (state.pollution === '全部' || row.pollution_proxy === state.pollution) &&
        (state.nvars === '全部' || row.n_vars_label === state.nvars) &&
        (!state.search || String(row.search_text || '').includes(state.search.toLowerCase()))
      );
    }
    function compareValue(a, b, key) {
      const va = a[key];
      const vb = b[key];
      if (key === 'model_id' || key === 'scheme_id') return String(va || '').localeCompare(String(vb || ''), 'zh');
      const na = parseNum(va);
      const nb = parseNum(vb);
      if (!Number.isFinite(na) && !Number.isFinite(nb)) return 0;
      if (!Number.isFinite(na)) return 1;
      if (!Number.isFinite(nb)) return -1;
      return na - nb;
    }
    function getSortedList() {
      const list = filteredBase().slice();
      list.sort((a, b) => {
        const cmp = compareValue(a, b, state.sortKey);
        if (cmp === 0) return compareValue(a, b, 'performance_rank');
        return state.sortDir === 'asc' ? cmp : -cmp;
      });
      return list;
    }
    function performanceOrdered(list) {
      return list.slice().sort((a, b) => compareValue(a, b, 'performance_rank'));
    }
    function setSort(key) {
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortKey = key;
        state.sortDir = sortDefaults[key] || 'desc';
      }
    }
    function ensure(list) {
      if (!list.length) { state.selected = null; return; }
      if (!list.some(x => x.model_id === state.selected)) state.selected = performanceOrdered(list)[0].model_id;
    }

    function renderHero() {
      document.getElementById('heroMeta').innerHTML = [
        `生成时间：${html(data.generated_at)}`,
        `来源：${html(data.source_prefix)}`,
        html(data.scope_note),
      ].map(t => `<span class="hero-chip">${t}</span>`).join('');
      const scope = document.getElementById('scopeNote');
      if (scope) scope.textContent = data.scope_note;
      document.getElementById('heroStats').innerHTML = heroItems.map(([k,v,h]) => `<div class="hero-stat"><div class="k">${html(k)}</div><div class="v">${html(v)}</div><div class="h">${html(h)}</div></div>`).join('');
    }
    function renderPageNav() {
      document.querySelectorAll('#pageNav .nav-link').forEach(link => {
        link.classList.toggle('active', link.dataset.page === pageKind);
      });
    }

    function renderFilters() {
      const mk = (items, current, kind, target) => {
        target.innerHTML = items.map(v => `<button class="filter ${current === v ? 'active' : ''}" data-kind="${kind}" data-value="${html(v)}">${html(v)}</button>`).join('');
      };
      mk(['全部', ...data.source_labels], state.source, 'source', document.getElementById('schemeFilters'));
      mk(['全部', ...data.fe_labels], state.fe, 'fe', document.getElementById('feFilters'));
      const fillSelect = (id, values, current) => {
        const target = document.getElementById(id);
        target.innerHTML = ['全部', ...values].map(v => `<option value="${html(v)}" ${v === current ? 'selected' : ''}>${html(v)}</option>`).join('');
      };
      fillSelect('temperatureSelect', data.temperature_labels, state.temperature);
      fillSelect('pollutionSelect', data.pollution_labels, state.pollution);
      fillSelect('nVarSelect', data.n_var_labels, state.nvars);
      document.querySelectorAll('.filter').forEach(btn => btn.onclick = () => { state[btn.dataset.kind] = btn.dataset.value; renderAll(); });
      document.getElementById('temperatureSelect').onchange = (e) => { state.temperature = e.target.value; renderAll(false); };
      document.getElementById('pollutionSelect').onchange = (e) => { state.pollution = e.target.value; renderAll(false); };
      document.getElementById('nVarSelect').onchange = (e) => { state.nvars = e.target.value; renderAll(false); };
      const search = document.getElementById('searchInput');
      if (search.value !== state.search) search.value = state.search;
      search.oninput = (e) => { state.search = e.target.value; renderAll(false); };

      const pageLimitControls = document.getElementById('pageLimitControls');
      const items = pageKind === 'matrix'
        ? [12, 24, 36, 60].map(v => ({ label: `矩阵 ${v} 列`, key: 'matrixLimit', value: v }))
        : pageKind === 'lancet'
          ? [12, 18, 24, 36].map(v => ({ label: `Lancet ${v} 张`, key: 'lancetLimit', value: v }))
          : [
              { label: '排序按 Rank', key: 'sortPreset', value: 'rank' },
              { label: '排序按 Score', key: 'sortPreset', value: 'score' },
            ];
      pageLimitControls.innerHTML = items.map(item => {
        const active = item.key === 'matrixLimit'
          ? state.matrixLimit === item.value
          : item.key === 'lancetLimit'
            ? state.lancetLimit === item.value
            : (item.value === 'rank' ? state.sortKey === 'performance_rank' : state.sortKey === 'performance_score');
        return `<button class="mini-btn ${active ? 'active' : ''}" data-limit-kind="${item.key}" data-limit-value="${item.value}">${html(item.label)}</button>`;
      }).join('');
      document.querySelectorAll('[data-limit-kind]').forEach(btn => btn.onclick = () => {
        if (btn.dataset.limitKind === 'matrixLimit') {
          state.matrixLimit = Number(btn.dataset.limitValue);
        } else if (btn.dataset.limitKind === 'lancetLimit') {
          state.lancetLimit = Number(btn.dataset.limitValue);
        } else if (btn.dataset.limitValue === 'rank') {
          state.sortKey = 'performance_rank';
          state.sortDir = 'asc';
        } else {
          state.sortKey = 'performance_score';
          state.sortDir = 'desc';
        }
        renderAll();
      });
    }

    function renderTop(list) {
      const target = document.getElementById('topPicks');
      if (!list.length) { target.innerHTML = '<div class="empty">当前筛选条件下没有模型。</div>'; return; }
      target.innerHTML = performanceOrdered(list).slice(0,3).map(row => `<div class="pick"><span class="badge${badge(row.performance_rank)}">Rank ${row.performance_rank}</span><div style="font-weight:700;line-height:1.5">${label(row.scheme_id || row.model_id)}</div><div class="chips"><span class="chip ${sourceCls(row.source_group)}">${html(row.source_group)}</span><span class="chip">${html(row.fe_label)}</span></div><div style="font-size:12px;color:var(--muted)">${label(row.temperature_proxy)} · ${label(row.pollution_proxy)} · Score ${num(row.performance_score)}</div></div>`).join('');
    }

    function renderBest() {
      const target = document.getElementById('schemeBest');
      const rows = (data.curated_highlights || []).slice(0,4);
      target.innerHTML = rows.length ? rows.map(row => `<div class="pick"><div class="chips"><span class="chip source-curated">curated</span><span class="chip">#${row.performance_rank}</span></div><div style="font-weight:700;line-height:1.5">${label(row.model_id)}</div><div style="font-size:12px;color:var(--muted)">${html(row.fe_label)} · Score ${num(row.performance_score)} · AMC p=${num(row.p_AMC,4)}</div></div>`).join('') : '<div class="empty">当前没有 curated 对照结果。</div>';
    }

    function renderBatchInsight() {
      const target = document.getElementById('batchInsight');
      const top200Year = (data.fe_breakdown_top200 || []).find(item => item.label === 'Province: No / Year: Yes');
      const topWindow = data.dashboard_signal_summary || null;
      const familySnaps = (data.family_summary_top200 || []).slice(0,3).map(group => {
        const first = group.choices && group.choices[0];
        return first ? `<div class="bar-line"><div class="bar-line-head"><span>${html(group.label)}</span><strong>${label(first.label)}</strong></div><div style="font-size:12px;color:var(--muted)">${first.share_text}</div></div>` : '';
      }).join('');
      target.innerHTML = `
        <div class="pick"><div class="chips"><span class="chip soft">全量结构</span></div><div style="font-size:12px;color:var(--muted)">systematic ${data.total_systematic_models} · curated ${data.total_curated_models}</div></div>
        <div class="pick"><div class="chips"><span class="chip soft">展示集 FE</span></div><div style="font-size:12px;color:var(--muted)">Year FE only 占比 ${top200Year ? top200Year.share_text : '—'} · 反事实锚点 ${data.dashboard_required_models || 0} 个</div></div>
        <div class="pick"><div class="chips"><span class="chip soft">展示集信号</span></div><div style="font-size:12px;color:var(--muted)">R1xday 显著 ${topWindow ? `${topWindow.r1_sig_count}/${topWindow.count}` : '—'} · AMC 显著 ${topWindow ? `${topWindow.amc_sig_count}/${topWindow.count}` : '—'}</div></div>
        <div class="pick"><div class="chips"><span class="chip soft">展示集家族偏好</span></div>${familySnaps || '<div style="font-size:12px;color:var(--muted)">暂无 family 统计</div>'}</div>
      `;
    }

    function renderRanking(list) {
      document.getElementById('countChip').textContent = `当前显示 ${list.length} / ${data.dashboard_models} 个 dashboard 模型`;
      const table = document.getElementById('rankingTable');
      if (!list.length) { table.innerHTML = '<tbody><tr><td class="empty">当前筛选条件下没有模型。</td></tr></tbody>'; return; }
      const sortHead = (key, labelText) => `<button class="sort-btn ${state.sortKey === key ? `active ${state.sortDir}` : ''}" data-sort="${key}" title="点击按 ${labelText} 排序"><span>${labelText}</span><span class="arrows"><span class="up">▲</span><span class="down">▼</span></span></button>`;
      table.innerHTML = `<thead><tr><th>${sortHead('performance_rank','Rank')}</th><th>${sortHead('scheme_id','Scheme')}</th><th>Proxy Mix</th><th>${sortHead('performance_score','Score')}</th><th>${sortHead('coef_R1xday','R1xday')}</th><th>${sortHead('coef_AMC','AMC')}</th><th>${sortHead('r2_model','R²')}</th><th>${sortHead('max_vif_z','VIF(z)')}</th></tr></thead><tbody>${list.map(row => `<tr data-model="${html(row.model_id)}" class="${row.model_id === state.selected ? 'on' : ''}"><td><span class="badge${badge(row.performance_rank)}">#${row.performance_rank}</span></td><td><div style="font-weight:700;line-height:1.5">${label(row.scheme_id || row.model_id)}</div><div class="chips" style="margin-top:6px"><span class="chip ${sourceCls(row.source_group)}">${html(row.source_group)}</span><span class="chip soft">${html(row.fe_label)}</span>${row.counterfactual_anchor ? '<span class="chip scheme">反事实锚点</span>' : ''}</div></td><td><div>${label(row.temperature_proxy)}</div><div style="font-size:12px;color:var(--muted)">${label(row.pollution_proxy)} · ${html(row.n_vars_label)}</div></td><td class="score">${num(row.performance_score)}</td><td><div class="${ccls(row.coef_R1xday)}">${num(row.coef_R1xday,4)}${stars(row.p_R1xday)}</div><div class="${pcls(row.p_R1xday)}" style="font-size:12px">p=${num(row.p_R1xday,4)}</div></td><td><div class="${ccls(row.coef_AMC)}">${num(row.coef_AMC,4)}${stars(row.p_AMC)}</div><div class="${pcls(row.p_AMC)}" style="font-size:12px">p=${num(row.p_AMC,4)}</div></td><td>${num(row.r2_model)}</td><td>${num(row.max_vif_z)}</td></tr>`).join('')}</tbody>`;
      table.querySelectorAll('[data-sort]').forEach(btn => btn.onclick = (event) => { event.stopPropagation(); setSort(btn.dataset.sort); renderAll(false); });
      table.querySelectorAll('tbody tr[data-model]').forEach(tr => tr.onclick = () => { state.selected = tr.dataset.model; renderAll(false); });
    }

    function renderDetail(model) {
      const target = document.getElementById('detail');
      if (!model) { target.innerHTML = '<div class="empty">没有可展示的模型，请调整筛选条件。</div>'; return; }
      const vif = (data.vif_tables[model.model_id] || []).slice(0,8);
      const sigs = model.significant_predictors && model.significant_predictors.length ? model.significant_predictors.map(x => `<span class="pill good">${label(x)}</span>`).join('') : '<span class="pill">当前无 p&lt;0.05 的自变量</span>';
      const vars = (model.variables_list || []).map(x => `<span class="pill">${label(x)}</span>`).join('');
      const familyPairs = model.family_pairs && model.family_pairs.length ? model.family_pairs.map(x => `<span class="pill">${html(x.label)}: ${label(x.value)}</span>`).join('') : '<span class="pill">人工方案，无 family_selection 标签</span>';
      const pct = Math.max(0, Math.min(100, Number(model.performance_score || 0) * 100));
      const lancetLink = `results_dashboard_lancet.html#${encodeURIComponent(model.model_id)}`;
      target.innerHTML = `
        <div class="score-strip">
          <div class="panel"><div class="eyebrow" style="color:var(--muted)">Selected Model</div><h3>${label(model.model_id)}</h3><p style="margin:10px 0 0;color:var(--muted);line-height:1.7">${html(model.scheme_note || '该 systematic 方案来自 family 组合。')}</p><div class="chips" style="margin-top:12px"><span class="chip ${sourceCls(model.source_group)}">${html(model.source_group)}</span><span class="chip">${html(model.fe_label)}</span><span class="chip soft">Rank ${model.performance_rank}</span><span class="chip soft">${html(model.n_vars_label)}</span>${model.counterfactual_anchor ? '<span class="chip scheme">反事实锚点</span>' : ''}</div><div class="bar"><span style="width:${pct}%"></span></div></div>
          <div class="panel"><div class="eyebrow" style="color:var(--muted)">Composite Score</div><div class="big">${num(model.performance_score)}</div><div style="font-size:12px;color:var(--muted);margin-top:8px">core ${num(model.core_signal_score)} · fit ${num(model.fit_score)} · vif ${num(model.vif_score)}</div></div>
        </div>
        <div class="metric-grid">
          <div class="metric"><div class="k">R-squared</div><div class="v">${num(model.r2_model)}</div></div>
          <div class="metric"><div class="k">R-squared (Overall)</div><div class="v">${num(model.r2_overall)}</div></div>
          <div class="metric"><div class="k">R² (within)</div><div class="v">${num(model.r2_within)}</div></div>
          <div class="metric"><div class="k">max VIF(z)</div><div class="v">${num(model.max_vif_z)}</div></div>
        </div>
        <div class="detail-grid">
          <div style="display:grid;gap:16px">
            <div class="panel"><div class="section-head"><div><h3>代理家族</h3><p>systematic 模型更应该按 family 组合读，而不是只看 SYS 编号。</p></div></div><div class="pills">${familyPairs}</div></div>
            <div class="panel"><div class="section-head"><div><h3>变量组成</h3><p>这套模型当前使用 ${html(model.n_vars)} 个解释变量，样本量 ${html(model.nobs)}。</p></div></div><div class="pills">${vars}</div></div>
            <div class="panel"><div class="section-head"><div><h3>显著结果提示</h3><p>这里展示 summary 表里当前记为显著的预测变量。</p></div></div><div class="pills">${sigs}</div></div>
            <div class="panel"><div class="section-head"><div><h3>Lancet 风格结果表</h3><p>保留 Province、Year、R-squared、R-squared (Overall)、R² (within) 这些元信息行。</p></div></div><div class="table-wrap windowed compact"><table><thead><tr><th>Predictor</th><th>Coefficient</th><th>95% CI</th><th>p value</th></tr></thead><tbody>${lancet.map(row => `<tr class="${metaRows.has(row.Predictor) ? 'meta-row' : ''}"><td>${label(row.Predictor)}</td><td>${html(row.Coefficient || '—')}</td><td>${html(row['95% CI'] || '—')}</td><td class="${pcls(row['p value'])}">${html(row['p value'] || '—')}</td></tr>`).join('')}</tbody></table></div></div>
          </div>
          <div style="display:grid;gap:16px">
            <div class="panel"><div class="section-head"><div><h3>核心变量快照</h3><p>优先关注 R1xday 和抗菌药物使用强度 的方向与显著性。</p></div></div><div class="pills"><span class="pill good">R1xday = ${num(model.coef_R1xday,4)}</span><span class="pill ${pcls(model.p_R1xday) === 'good' ? 'good' : ''}">p = ${num(model.p_R1xday,4)}</span><span class="pill good">AMC = ${num(model.coef_AMC,4)}</span><span class="pill ${pcls(model.p_AMC) === 'good' ? 'good' : ''}">p = ${num(model.p_AMC,4)}</span></div></div>
            <div class="panel"><div class="section-head"><div><h3>VIF Top ${vif.length}</h3><p>按 vif_z 从高到低排列，便于快速看共线性压力。</p></div></div><div class="table-wrap windowed compact"><table><thead><tr><th>Predictor</th><th>VIF raw</th><th>VIF z</th><th>|diff|</th></tr></thead><tbody>${vif.map(row => `<tr><td>${label(row.predictor)}</td><td>${num(row.vif_raw)}</td><td>${num(row.vif_z)}</td><td>${num(row.abs_diff)}</td></tr>`).join('')}</tbody></table></div></div>
          </div>
        </div>`;
    }

    function renderLancetGallery(list) {
      const target = document.getElementById('lancetGallery');
      const chip = document.getElementById('lancetCountChip');
      const rows = performanceOrdered(list).slice(0, state.lancetLimit);
      chip.textContent = `当前显示 ${rows.length} 张 / 命中 ${list.length} 张`;
      if (!rows.length) {
        target.innerHTML = '<div class="empty">当前筛选条件下没有 Lancet 风格结果表。</div>';
        return;
      }
      target.innerHTML = rows.map(model => {
        const lancet = data.lancet_tables[model.model_id] || [];
        return `<div class="panel"><div class="section-head"><div><h3>${label(model.model_id)}</h3><p>${html(model.scheme_note || 'systematic family 组合模型')}</p></div><div class="chips"><span class="chip ${sourceCls(model.source_group)}">${html(model.source_group)}</span><span class="chip">${html(model.fe_label)}</span><span class="chip soft">Score ${num(model.performance_score)}</span></div></div><div class="table-wrap windowed compact"><table><thead><tr><th>Predictor</th><th>Coefficient</th><th>95% CI</th><th>p value</th></tr></thead><tbody>${lancet.map(row => `<tr class="${metaRows.has(row.Predictor) ? 'meta-row' : ''}"><td>${label(row.Predictor)}</td><td>${html(row.Coefficient || '—')}</td><td>${html(row['95% CI'] || '—')}</td><td class="${pcls(row['p value'])}">${html(row['p value'] || '—')}</td></tr>`).join('')}</tbody></table></div></div>`;
      }).join('');
    }

    function renderDetail(model) {
      const target = document.getElementById('detail');
      if (!model) { target.innerHTML = '<div class="empty">当前筛选条件下没有可展示的模型。</div>'; return; }
      const vif = (data.vif_tables[model.model_id] || []).slice(0,8);
      const sigs = model.significant_predictors && model.significant_predictors.length ? model.significant_predictors.map(x => `<span class="pill good">${label(x)}</span>`).join('') : '<span class="pill">当前无 p&lt;0.05 的自变量</span>';
      const vars = (model.variables_list || []).map(x => `<span class="pill">${label(x)}</span>`).join('');
      const familyPairs = model.family_pairs && model.family_pairs.length ? model.family_pairs.map(x => `<span class="pill">${html(x.label)}: ${label(x.value)}</span>`).join('') : '<span class="pill">人工方案，无 family_selection 标签</span>';
      const pct = Math.max(0, Math.min(100, Number(model.performance_score || 0) * 100));
      const lancetLink = `results_dashboard_lancet.html#${encodeURIComponent(model.model_id)}`;
      target.innerHTML = `
        <div class="score-strip">
          <div class="panel"><div class="eyebrow" style="color:var(--muted)">Selected Model</div><h3>${label(model.model_id)}</h3><p style="margin:10px 0 0;color:var(--muted);line-height:1.62">${html(model.scheme_note || '该 systematic 方案来自 family 组合。')}</p><div class="chips" style="margin-top:12px"><span class="chip ${sourceCls(model.source_group)}">${html(model.source_group)}</span><span class="chip">${html(model.fe_label)}</span><span class="chip soft">Rank ${model.performance_rank}</span><span class="chip soft">${html(model.n_vars_label)}</span></div><div class="bar"><span style="width:${pct}%"></span></div></div>
          <div class="panel"><div class="eyebrow" style="color:var(--muted)">Composite Score</div><div class="big">${num(model.performance_score)}</div><div style="font-size:12px;color:var(--muted);margin-top:8px">core ${num(model.core_signal_score)} · fit ${num(model.fit_score)} · vif ${num(model.vif_score)} · n=${html(model.nobs)}</div><div class="pills compact" style="margin-top:14px"><a class="pill" href="${lancetLink}">看完整 Lancet 表</a><a class="pill" href="results_dashboard_matrix.html">去横向矩阵页</a></div></div>
        </div>
        <div class="metric-grid">
          <div class="metric"><div class="k">R-squared</div><div class="v">${num(model.r2_model)}</div></div>
          <div class="metric"><div class="k">R-squared (Overall)</div><div class="v">${num(model.r2_overall)}</div></div>
          <div class="metric"><div class="k">R² (within)</div><div class="v">${num(model.r2_within)}</div></div>
          <div class="metric"><div class="k">max VIF(z)</div><div class="v">${num(model.max_vif_z)}</div></div>
        </div>
        <div class="detail-grid">
          <div style="display:grid;gap:16px">
            <div class="panel"><div class="section-head"><div><h3>结构解读</h3><p>把代理家族、变量组成和显著结果整合在一起，首页只保留最关键的阅读入口。</p></div></div><div style="display:grid;gap:14px"><div><div class="eyebrow" style="color:var(--muted)">代理家族</div><div class="pills compact">${familyPairs}</div></div><div><div class="eyebrow" style="color:var(--muted)">变量组成</div><div class="pills compact">${vars}</div></div><div><div class="eyebrow" style="color:var(--muted)">显著结果</div><div class="pills compact">${sigs}</div></div></div></div>
          </div>
          <div style="display:grid;gap:16px">
            <div class="panel"><div class="section-head"><div><h3>核心变量快照</h3><p>优先关注 R1xday 和抗菌药物使用强度的方向与显著性。</p></div></div><div class="pills compact"><span class="pill good">R1xday = ${num(model.coef_R1xday,4)}</span><span class="pill ${pcls(model.p_R1xday) === 'good' ? 'good' : ''}">p = ${num(model.p_R1xday,4)}</span><span class="pill good">AMC = ${num(model.coef_AMC,4)}</span><span class="pill ${pcls(model.p_AMC) === 'good' ? 'good' : ''}">p = ${num(model.p_AMC,4)}</span></div></div>
            <div class="panel"><div class="section-head"><div><h3>VIF Top ${vif.length}</h3><p>按 vif_z 从高到低排列，便于快速看共线性压力。</p></div></div><div class="table-wrap"><table><thead><tr><th>Predictor</th><th>VIF raw</th><th>VIF z</th><th>|diff|</th></tr></thead><tbody>${vif.map(row => `<tr><td>${label(row.predictor)}</td><td>${num(row.vif_raw)}</td><td>${num(row.vif_z)}</td><td>${num(row.abs_diff)}</td></tr>`).join('')}</tbody></table></div></div>
            <div class="panel"><div class="section-head"><div><h3>子页面入口</h3><p>完整 Lancet 表和横向矩阵都放在子页面，首页不再重复堆长表。</p></div></div><div class="pills compact"><a class="pill" href="${lancetLink}">打开完整 Lancet 页</a><a class="pill" href="results_dashboard_matrix.html">打开横向矩阵页</a></div></div>
          </div>
        </div>`;
    }

    function renderLancetGallery(list) {
      const target = document.getElementById('lancetGallery');
      const chip = document.getElementById('lancetCountChip');
      const rows = performanceOrdered(list).slice(0, state.lancetLimit);
      chip.textContent = `当前显示 ${rows.length} 张 / 命中 ${list.length} 张`;
      if (!rows.length) {
        target.innerHTML = '<div class="empty">当前筛选条件下没有 Lancet 风格结果表。</div>';
        return;
      }
      target.innerHTML = rows.map(model => {
        const lancet = data.lancet_tables[model.model_id] || [];
        return `<div class="panel"><div class="section-head"><div><h3>${label(model.model_id)}</h3><p>${html(model.scheme_note || 'systematic family 组合模型')}</p></div><div class="chips"><span class="chip ${sourceCls(model.source_group)}">${html(model.source_group)}</span><span class="chip">${html(model.fe_label)}</span><span class="chip soft">Score ${num(model.performance_score)}</span></div></div><div class="table-wrap"><table><thead><tr><th>Predictor</th><th>Coefficient</th><th>95% CI</th><th>p value</th></tr></thead><tbody>${lancet.map(row => `<tr class="${metaRows.has(row.Predictor) ? 'meta-row' : ''}"><td>${label(row.Predictor)}</td><td>${html(row.Coefficient || '—')}</td><td>${html(row['95% CI'] || '—')}</td><td class="${pcls(row['p value'])}">${html(row['p value'] || '—')}</td></tr>`).join('')}</tbody></table></div></div>`;
      }).join('');
    }

    function renderDetailCompact(model) {
      const target = document.getElementById('detail');
      if (!model) {
        target.innerHTML = '<div class="empty">当前筛选条件下没有可展示的模型。</div>';
        return;
      }
      const familyPairs = model.family_pairs && model.family_pairs.length
        ? model.family_pairs.map(item => `<span class="pill">${html(item.label)}: ${label(item.value)}</span>`).join('')
        : '<span class="pill">人工方案暂无 family_selection 标签</span>';
      const vars = (model.variables_list || []).map(item => `<span class="pill">${label(item)}</span>`).join('');
      const pct = Math.max(0, Math.min(100, Number(model.performance_score || 0) * 100));
      const lancetLink = `results_dashboard_lancet.html#${encodeURIComponent(model.model_id)}`;
      target.innerHTML = `
        <div class="score-strip">
          <div class="panel">
            <div class="eyebrow" style="color:var(--muted)">Selected Model</div>
            <h3>${label(model.model_id)}</h3>
            <p style="margin:10px 0 0;color:var(--muted);line-height:1.62">${html(model.scheme_note || 'systematic 方案来自 family 组合。')}</p>
            <div class="chips" style="margin-top:12px">
              <span class="chip ${sourceCls(model.source_group)}">${html(model.source_group)}</span>
              <span class="chip">${html(model.fe_label)}</span>
              <span class="chip soft">Rank ${model.performance_rank}</span>
              <span class="chip soft">${html(model.n_vars_label)}</span>
            </div>
            <div class="bar"><span style="width:${pct}%"></span></div>
          </div>
          <div class="panel">
            <div class="eyebrow" style="color:var(--muted)">Composite Score</div>
            <div class="big">${num(model.performance_score)}</div>
            <div style="font-size:12px;color:var(--muted);margin-top:8px">core ${num(model.core_signal_score)} · fit ${num(model.fit_score)} · vif ${num(model.vif_score)} · n=${html(model.nobs)}</div>
            <div class="pills compact" style="margin-top:14px">
              <a class="pill" href="${lancetLink}">打开 Lancet 页</a>
              <a class="pill" href="results_dashboard_matrix.html">打开横向矩阵页</a>
            </div>
          </div>
        </div>
        <div class="metric-grid">
          <div class="metric"><div class="k">R-squared</div><div class="v">${num(model.r2_model)}</div></div>
          <div class="metric"><div class="k">R-squared (Overall)</div><div class="v">${num(model.r2_overall)}</div></div>
          <div class="metric"><div class="k">R² (within)</div><div class="v">${num(model.r2_within)}</div></div>
          <div class="metric"><div class="k">max VIF(z)</div><div class="v">${num(model.max_vif_z)}</div></div>
        </div>
        <div class="detail-grid">
          <div class="panel">
            <div class="section-head"><div><h3>结构解读</h3><p>首页只保留不能从 Lancet 表直接读出的结构信息。</p></div></div>
            <div style="display:grid;gap:14px">
              <div>
                <div class="eyebrow" style="color:var(--muted)">Proxy Mix</div>
                <div class="pills compact">
                  <span class="pill">${label(model.temperature_proxy || '—')}</span>
                  <span class="pill">${label(model.pollution_proxy || '—')}</span>
                  <span class="pill">${html(model.n_vars_label || '')}</span>
                </div>
              </div>
              <div>
                <div class="eyebrow" style="color:var(--muted)">代理家族</div>
                <div class="pills compact">${familyPairs}</div>
              </div>
              <div>
                <div class="eyebrow" style="color:var(--muted)">变量组成</div>
                <div class="pills compact">${vars}</div>
              </div>
            </div>
          </div>
          <div class="panel">
            <div class="section-head"><div><h3>阅读入口</h3><p>系数方向、95% CI 和显著性统一到 Lancet 子页查看，首页不再重复展示。</p></div></div>
            <div style="display:grid;gap:12px">
              <div style="padding:14px 16px;border-radius:16px;background:rgba(24,53,60,.04);border:1px solid rgba(24,53,60,.08);font-size:12px;color:var(--muted);line-height:1.7">n = ${html(model.nobs)} · source = ${html(model.source_group)} · FE = ${html(model.fe_label)}</div>
              <div style="padding:14px 16px;border-radius:16px;background:rgba(24,53,60,.04);border:1px solid rgba(24,53,60,.08);font-size:12px;color:var(--muted);line-height:1.7">先看这一页的代理结构和变量组成，再去 Lancet 表读 R1xday、AMC 和其余系数。</div>
              <div class="pills compact">
                <a class="pill" href="${lancetLink}">看完整 Lancet 表</a>
                <a class="pill" href="results_dashboard_matrix.html">看横向矩阵</a>
              </div>
            </div>
          </div>
        </div>`;
    }

    function renderDetailCompact(model) {
      const target = document.getElementById('detail');
      if (!model) {
        target.innerHTML = '<div class="empty">当前筛选条件下没有可展示的模型。</div>';
        return;
      }
      const lancet = data.lancet_tables[model.model_id] || [];
      const familyPairs = model.family_pairs && model.family_pairs.length
        ? model.family_pairs.map(item => `<span class="pill">${html(item.label)}: ${label(item.value)}</span>`).join('')
        : '<span class="pill">人工方案暂无 family_selection 标签</span>';
      const vars = (model.variables_list || []).map(item => `<span class="pill">${label(item)}</span>`).join('');
      const pct = Math.max(0, Math.min(100, Number(model.performance_score || 0) * 100));
      const lancetLink = `results_dashboard_lancet.html#${encodeURIComponent(model.model_id)}`;
      target.innerHTML = `
        <div class="score-strip">
          <div class="panel">
            <div class="eyebrow" style="color:var(--muted)">Selected Model</div>
            <h3>${label(model.model_id)}</h3>
            <p style="margin:10px 0 0;color:var(--muted);line-height:1.62">${html(model.scheme_note || 'systematic 方案来自 family 组合。')}</p>
            <div class="chips" style="margin-top:12px">
              <span class="chip ${sourceCls(model.source_group)}">${html(model.source_group)}</span>
              <span class="chip">${html(model.fe_label)}</span>
              <span class="chip soft">Rank ${model.performance_rank}</span>
              <span class="chip soft">${html(model.n_vars_label)}</span>
            </div>
            <div class="bar"><span style="width:${pct}%"></span></div>
          </div>
          <div class="panel">
            <div class="eyebrow" style="color:var(--muted)">Composite Score</div>
            <div class="big">${num(model.performance_score)}</div>
            <div style="font-size:12px;color:var(--muted);margin-top:8px">core ${num(model.core_signal_score)} · fit ${num(model.fit_score)} · vif ${num(model.vif_score)} · n=${html(model.nobs)}</div>
            <div class="pills compact" style="margin-top:14px">
              <a class="pill" href="${lancetLink}">打开 Lancet 页</a>
              <a class="pill" href="results_dashboard_matrix.html">打开横向矩阵页</a>
            </div>
          </div>
        </div>
        <div class="metric-grid">
          <div class="metric"><div class="k">R-squared</div><div class="v">${num(model.r2_model)}</div></div>
          <div class="metric"><div class="k">R-squared (Overall)</div><div class="v">${num(model.r2_overall)}</div></div>
          <div class="metric"><div class="k">R² (within)</div><div class="v">${num(model.r2_within)}</div></div>
          <div class="metric"><div class="k">max VIF(z)</div><div class="v">${num(model.max_vif_z)}</div></div>
        </div>
        <div class="detail-grid">
          <div class="panel">
            <div class="section-head"><div><h3>结构解读</h3><p>首页先读代理结构和变量组成，再往下看当前模型的 Lancet 表。</p></div></div>
            <div style="display:grid;gap:14px">
              <div>
                <div class="eyebrow" style="color:var(--muted)">Proxy Mix</div>
                <div class="pills compact">
                  <span class="pill">${label(model.temperature_proxy || '—')}</span>
                  <span class="pill">${label(model.pollution_proxy || '—')}</span>
                  <span class="pill">${html(model.n_vars_label || '')}</span>
                </div>
              </div>
              <div>
                <div class="eyebrow" style="color:var(--muted)">代理家族</div>
                <div class="pills compact">${familyPairs}</div>
              </div>
              <div>
                <div class="eyebrow" style="color:var(--muted)">变量组成</div>
                <div class="pills compact">${vars}</div>
              </div>
            </div>
          </div>
          <div class="panel">
            <div class="section-head"><div><h3>阅读入口</h3><p>左侧切换模型后，右侧会同步更新结构信息和 Lancet 风格结果表。</p></div></div>
            <div style="display:grid;gap:12px">
              <div style="padding:14px 16px;border-radius:16px;background:rgba(24,53,60,.04);border:1px solid rgba(24,53,60,.08);font-size:12px;color:var(--muted);line-height:1.7">n = ${html(model.nobs)} · source = ${html(model.source_group)} · FE = ${html(model.fe_label)}</div>
              <div style="padding:14px 16px;border-radius:16px;background:rgba(24,53,60,.04);border:1px solid rgba(24,53,60,.08);font-size:12px;color:var(--muted);line-height:1.7">当前卡片里直接看选中模型的 Lancet 表；子页面用于完整展开和跨模型对比。</div>
              <div class="pills compact">
                <a class="pill" href="${lancetLink}">看完整 Lancet 表</a>
                <a class="pill" href="results_dashboard_matrix.html">看横向矩阵</a>
              </div>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="section-head"><div><h3>Lancet 风格结果表</h3><p>当前选中模型的系数、95% CI 和 p value 直接放在首页详情区。</p></div></div>
          <div class="table-wrap"><table><thead><tr><th>Predictor</th><th>Coefficient</th><th>95% CI</th><th>p value</th></tr></thead><tbody>${lancet.map(row => `<tr class="${metaRows.has(row.Predictor) ? 'meta-row' : ''}"><td>${label(row.Predictor)}</td><td>${html(row.Coefficient || '—')}</td><td>${html(row['95% CI'] || '—')}</td><td class="${pcls(row['p value'])}">${html(row['p value'] || '—')}</td></tr>`).join('')}</tbody></table></div>
        </div>`;
    }

    function renderMatrix(list) {
      const table = document.getElementById('matrixTable');
      const matrixRows = performanceOrdered(list.filter(row => matrixModelSet.has(row.model_id))).slice(0, state.matrixLimit);
      document.getElementById('matrixCountChip').textContent = `当前显示 ${matrixRows.length} 列 / 命中 ${list.filter(row => matrixModelSet.has(row.model_id)).length} 列`;
      if (!matrixRows.length) { table.innerHTML = '<tbody><tr><td class="empty">当前筛选条件下，没有命中 dashboard 展示集矩阵的数据。</td></tr></tbody>'; return; }
      const ids = matrixRows.map(row => row.model_id);
      table.innerHTML = `<thead><tr><th>Metric</th>${ids.map(id => `<th>${label(id)}</th>`).join('')}</tr></thead><tbody>${data.matrix_rows.map(row => `<tr><td>${html(row.metric)}</td>${ids.map(id => { const val = row.values ? row.values[id] : null; return `<td class="${String(row.metric).startsWith('p_') ? pcls(val) : ''}">${short(val)}</td>`; }).join('')}</tr>`).join('')}</tbody>`;
    }

    function applyPageMode() {
      const showHome = pageKind === 'home';
      const showLancet = pageKind === 'lancet';
      const showMatrix = pageKind === 'matrix';
      document.getElementById('homeRankingSection').classList.toggle('hidden', !showHome);
      document.getElementById('homeDetailSection').classList.toggle('hidden', !showHome);
      document.getElementById('lancetSection').classList.toggle('hidden', !showLancet);
      document.getElementById('matrixSection').classList.toggle('hidden', !showMatrix);
    }

    function renderAll(refilter=true) {
      if (refilter) renderFilters();
      renderPageNav();
      applyPageMode();
      const list = getSortedList();
      ensure(list);
      renderTop(list);
      renderBest();
      renderBatchInsight();
      if (pageKind === 'home') {
        renderRanking(list);
        renderDetailCompact(list.find(x => x.model_id === state.selected) || null);
      } else if (pageKind === 'lancet') {
        renderLancetGallery(list);
      } else if (pageKind === 'matrix') {
        renderMatrix(list);
      }
    }

    try {
      renderHero();
      renderAll();
    } catch (error) {
      document.body.innerHTML = `
        <div style="max-width:960px;margin:32px auto;padding:24px;border-radius:18px;background:#fff7f3;border:1px solid rgba(191,92,57,.22);font-family:'Segoe UI',sans-serif;color:#5f2a1a;line-height:1.7">
          <h2 style="margin:0 0 12px;font-family:Georgia,serif">Dashboard 脚本初始化失败</h2>
          <p style="margin:0 0 10px">页面框架已经生成，但前端脚本运行时报错，所以数据和图表没有渲染出来。</p>
          <pre style="white-space:pre-wrap;background:#fff;border-radius:12px;padding:14px;border:1px solid rgba(24,53,60,.08)">${html(error && error.stack ? error.stack : String(error))}</pre>
        </div>`;
    }
  </script>
</body>
</html>"""
    return template.replace("__PAYLOAD__", data_json).replace("__PAGE_KIND__", page_kind)


def main() -> None:
    payload = build_payload()
    outputs = {
        "home": OUTPUT_HOME_HTML,
        "lancet": OUTPUT_LANCET_HTML,
        "matrix": OUTPUT_MATRIX_HTML,
    }
    for kind, path in outputs.items():
        html = build_html(payload, page_kind=kind)
        path.write_text(html, encoding="utf-8")
        print(f"Saved dashboard: {path}")


if __name__ == "__main__":
    main()
