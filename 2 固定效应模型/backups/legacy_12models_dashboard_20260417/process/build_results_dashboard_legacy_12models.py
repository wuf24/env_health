from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BACKUP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKUP_DIR / "data"
OUTPUT_HOME_HTML = BACKUP_DIR / "results_dashboard_legacy_12models.html"
OUTPUT_LANCET_HTML = BACKUP_DIR / "results_dashboard_legacy_12models_lancet.html"
OUTPUT_MATRIX_HTML = BACKUP_DIR / "results_dashboard_legacy_12models_matrix.html"

SCHEME_ORDER = [
    "方案A_平衡主线组",
    "方案C_污染替代组",
    "方案D_城市气候组",
    "方案F_低VIF主线组",
]
FE_ORDER = [
    "Province: No / Year: Yes",
    "Province: Yes / Year: No",
    "Province: Yes / Year: Yes",
]
FE_SHORT = {
    "Province: No / Year: Yes": "Year FE",
    "Province: Yes / Year: No": "Province FE",
    "Province: Yes / Year: Yes": "Two-way FE",
}
META_ROWS = [
    "Province",
    "Year",
    "R-squared",
    "R-squared (Overall)",
    "R² (within)",
    "R2 (within)",
    "Total number of observations",
]
DISPLAY_VIF_TOP_N = 10
FAMILY_CANDIDATES = {
    "温度代理": ["TA（℃）", "省平均气温", "主要城市平均气温"],
    "污染代理": ["PM2.5", "氮氧化物", "二氧化硫"],
    "发展代理": ["GDP", "可支配收入", "医疗水平"],
    "供水/卫生代理": ["人均日生活用水量(升)", "城市用水普及率", "生活垃圾无害化处理率"],
    "畜牧代理": ["牲畜饲养\n-猪年末头数", "牲畜饲养\n-大牲畜年末头数", "牲畜饲养\n-羊年末头数"],
    "社会环境代理": ["文盲比例", "建成区绿化覆盖率", "食品消费量"],
    "水文/日照代理": ["PA（百帕）", "省平均降雨", "主要城市降水量", "主要城市日照时数"],
}


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
    return pd.read_csv(DATA_DIR / name, encoding="utf-8-sig")


def infer_family_selection(variables: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family, candidates in FAMILY_CANDIDATES.items():
        match = next((candidate for candidate in candidates if candidate in variables), None)
        if match:
            mapping[family] = match
    return mapping


def parse_lancet_tables(df: pd.DataFrame, model_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    model_set = set(model_ids)
    tables = {model_id: [] for model_id in model_ids}
    current_model: str | None = None
    for row in df.to_dict(orient="records"):
        predictor = clean_value(row.get("Predictor"))
        coefficient = clean_value(row.get("Coefficient"))
        ci = clean_value(row.get("95% CI"))
        p_value = clean_value(row.get("p value"))
        is_title = predictor in model_set and coefficient in (None, "") and ci in (None, "") and p_value in (None, "")
        is_spacer = predictor is None and coefficient is None and ci is None and p_value is None
        if is_title:
            current_model = str(predictor)
            continue
        if is_spacer or current_model is None:
            continue
        tables[current_model].append({
            "Predictor": predictor,
            "Coefficient": coefficient,
            "95% CI": ci,
            "p value": p_value,
        })
    return tables

def build_payload() -> dict[str, Any]:
    ranking = load_csv("variable_group_scheme_ranking.csv").sort_values("performance_rank")
    summary = load_csv("variable_group_scheme_summary.csv")
    vif = load_csv("variable_group_scheme_vif.csv")
    horizontal = load_csv("variable_group_scheme_horizontal_compare.csv")
    lancet = load_csv("variable_group_scheme_lancet_tables.csv")

    display_ids = [clean_value(item) for item in ranking["model_id"].tolist()]
    summary_map = {
        clean_value(row["model_id"]): {key: clean_value(value) for key, value in row.items()}
        for row in summary.to_dict(orient="records")
    }
    vif_model_map = {
        (clean_value(row["scheme"]), clean_value(row["fe_spec"])): clean_value(row["model_id"])
        for row in summary.to_dict(orient="records")
    }

    ranking_records: list[dict[str, Any]] = []
    for row in ranking.to_dict(orient="records"):
        record = {key: clean_value(value) for key, value in row.items()}
        full = summary_map[record["model_id"]]
        variables_list = split_items(full.get("variables"), " | ")
        family_map = infer_family_selection(variables_list)
        record.update({
            "scheme_id": record.get("scheme"),
            "scheme_note": full.get("scheme_note"),
            "variables_list": variables_list,
            "significant_predictors": split_items(record.get("sig_predictors_p_lt_0_05"), ","),
            "province_fe": full.get("province_fe"),
            "year_fe": full.get("year_fe"),
            "nobs": full.get("nobs"),
            "n_vars": full.get("n_vars"),
            "n_vars_label": f"{int(full['n_vars'])} vars" if full.get("n_vars") is not None else "—",
            "family_pairs": [{"label": key, "value": value} for key, value in family_map.items()],
            "temperature_proxy": family_map.get("温度代理", "未纳入"),
            "pollution_proxy": family_map.get("污染代理", "未纳入"),
            "fe_short": FE_SHORT.get(record["fe_label"], record["fe_label"]),
            "search_text": " ".join(str(item).lower() for item in [record.get("model_id"), record.get("scheme"), record.get("fe_label"), full.get("scheme_note"), full.get("variables"), record.get("sig_predictors_p_lt_0_05")] if item),
        })
        ranking_records.append(record)

    vif_rows = []
    for row in vif.to_dict(orient="records"):
        model_id = vif_model_map.get((clean_value(row.get("scheme")), clean_value(row.get("fe_spec"))))
        if model_id:
            vif_rows.append({
                "model_id": model_id,
                "predictor": clean_value(row.get("predictor")),
                "vif_raw": clean_value(row.get("vif_raw")),
                "vif_z": clean_value(row.get("vif_z")),
                "abs_diff": clean_value(row.get("abs_diff")),
            })
    vif_df = pd.DataFrame(vif_rows)
    vif_map = {model_id: [] for model_id in display_ids}
    if not vif_df.empty:
        vif_df = vif_df.sort_values(["model_id", "vif_z"], ascending=[True, False])
        for row in vif_df.to_dict(orient="records"):
            vif_map[row["model_id"]].append(row)
    for model_id in list(vif_map):
        vif_map[model_id] = vif_map[model_id][:DISPLAY_VIF_TOP_N]

    matrix_model_ids = [model_id for model_id in display_ids if model_id in horizontal.columns]
    matrix_rows = [{"metric": clean_value(row.get("metric")), "values": {model_id: clean_value(row.get(model_id)) for model_id in matrix_model_ids}} for row in horizontal.to_dict(orient="records")]

    best_by_fe = []
    for fe_label in FE_ORDER:
        rows = [item for item in ranking_records if item["fe_label"] == fe_label]
        if rows:
            row = sorted(rows, key=lambda item: item["performance_rank"])[0]
            best_by_fe.append({"fe_label": fe_label, "fe_short": FE_SHORT.get(fe_label, fe_label), "model_id": row["model_id"], "scheme": row["scheme"], "performance_rank": row["performance_rank"], "performance_score": row["performance_score"]})

    scheme_board = []
    for scheme in SCHEME_ORDER:
        cells = []
        for fe_label in FE_ORDER:
            row = next((item for item in ranking_records if item["scheme"] == scheme and item["fe_label"] == fe_label), None)
            cells.append({"fe_label": fe_label, "fe_short": FE_SHORT.get(fe_label, fe_label), "model_id": row["model_id"] if row else None, "performance_rank": row["performance_rank"] if row else None, "performance_score": row["performance_score"] if row else None, "coef_R1xday": row["coef_R1xday"] if row else None, "coef_AMC": row["coef_AMC"] if row else None})
        scheme_board.append({"scheme": scheme, "cells": cells})

    family_counts: dict[str, dict[str, int]] = {}
    variable_counts: dict[str, int] = {}
    for row in ranking_records:
        for pair in row["family_pairs"]:
            family_counts.setdefault(pair["label"], {})
            family_counts[pair["label"]][pair["value"]] = family_counts[pair["label"]].get(pair["value"], 0) + 1
        for variable in row["variables_list"]:
            variable_counts[variable] = variable_counts.get(variable, 0) + 1

    family_summary = []
    for label, counts in family_counts.items():
        top_items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        family_summary.append({"label": label, "choices": [{"label": name, "count": count, "share_text": f"{(count / len(ranking_records)):.1%}" if ranking_records else "0%"} for name, count in top_items]})
    variable_frequency = [{"label": name, "count": count, "share_text": f"{(count / len(ranking_records)):.1%}" if ranking_records else "0%"} for name, count in sorted(variable_counts.items(), key=lambda item: (-item[1], item[0]))[:6]]

    signal_summary = {
        "r1_sig_count": int((ranking["p_R1xday"] < 0.05).sum()),
        "amc_sig_count": int((ranking["p_AMC"] < 0.05).sum()),
        "both_positive_count": int(((ranking["coef_R1xday"] > 0) & (ranking["coef_AMC"] > 0)).sum()),
    }
    best_model = ranking_records[0]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "scope_note": "旧版比较线固定为 4 套人工方案 × 3 种固定效应，共 12 个模型。",
        "meta_rows": META_ROWS,
        "total_models": len(ranking_records),
        "scheme_count": len(SCHEME_ORDER),
        "fe_count": len(FE_ORDER),
        "best_model": {"model_id": best_model["model_id"], "scheme": best_model["scheme"], "fe_short": best_model["fe_short"], "performance_rank": best_model["performance_rank"], "performance_score": best_model["performance_score"]},
        "signal_summary": signal_summary,
        "best_by_fe": best_by_fe,
        "scheme_board": scheme_board,
        "family_summary": family_summary,
        "variable_frequency": variable_frequency,
        "ranking": ranking_records,
        "matrix_model_ids": matrix_model_ids,
        "matrix_rows": matrix_rows,
        "lancet_tables": parse_lancet_tables(lancet, display_ids),
        "vif_tables": vif_map,
        "scheme_labels": [scheme for scheme in SCHEME_ORDER if any(item["scheme"] == scheme for item in ranking_records)],
        "fe_labels": [label for label in FE_ORDER if any(item["fe_label"] == label for item in ranking_records)],
        "temperature_labels": sorted({row["temperature_proxy"] for row in ranking_records}),
        "pollution_labels": sorted({row["pollution_proxy"] for row in ranking_records}),
        "n_var_labels": [f"{n} vars" for n in sorted({int(row["n_vars"]) for row in ranking_records if row.get("n_vars") is not None})],
    }

def build_html(payload: dict[str, Any], page_kind: str) -> str:
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Legacy 12-Model Dashboard</title>
<style>
:root{--bg:#f6efe7;--panel:rgba(255,250,244,.92);--ink:#20363c;--muted:#667b80;--line:rgba(32,54,60,.12);--accent:#b45735;--accent2:#2f6f74;--gold:#d09d47;--shadow:0 16px 44px rgba(39,35,31,.10)}
*{box-sizing:border-box} html{scroll-behavior:smooth}
body{margin:0;font-family:"Trebuchet MS","Segoe UI",sans-serif;color:var(--ink);background:radial-gradient(circle at top left,rgba(180,87,53,.15),transparent 26%),radial-gradient(circle at top right,rgba(47,111,116,.12),transparent 28%),linear-gradient(180deg,#faf4eb 0%,#eef3f1 100%)}
.page{width:min(1480px,calc(100vw - 24px));margin:12px auto 24px}.hero,.card{background:var(--panel);border:1px solid rgba(255,255,255,.6);box-shadow:var(--shadow);backdrop-filter:blur(10px)}
.hero{border-radius:32px;padding:30px;background:linear-gradient(135deg,rgba(25,47,53,.98),rgba(42,96,97,.94));color:#fbf7f1;position:relative;overflow:hidden}.hero:after{content:"";position:absolute;right:-40px;top:-40px;width:250px;height:250px;border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.18),transparent 66%)}
.hero-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:24px;align-items:end}.eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;opacity:.75;margin-bottom:10px}
h1,h2,h3{margin:0;font-family:Georgia,"Times New Roman",serif;letter-spacing:-.02em}h1{font-size:clamp(34px,4vw,54px);line-height:1.02;margin-bottom:12px}
.hero p,.section-head p{margin:0;line-height:1.72;font-size:15px}.hero p{color:rgba(251,247,241,.86)}.section-head p{color:var(--muted);font-size:14px;margin-top:6px}
.hero-meta,.chips,.filters,.pill-list,.page-nav{display:flex;flex-wrap:wrap;gap:8px}.nav-link{display:inline-flex;align-items:center;padding:10px 14px;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.12);color:#fff8f2;text-decoration:none;font-size:13px}.nav-link.active{background:linear-gradient(135deg,var(--gold),#ca8d2d);color:#18343b;border-color:transparent;font-weight:700}
.hero-chip,.chip,.pill,.filter,.mini-btn{border-radius:999px;padding:9px 12px;font-size:12px}.hero-chip{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.12);color:#fff8f2}.chip{background:rgba(47,111,116,.11);border:1px solid rgba(47,111,116,.12);color:var(--accent2);font-weight:700}.chip.scheme{background:rgba(180,87,53,.12);border-color:rgba(180,87,53,.1);color:#974627}.chip.soft,.pill{background:rgba(32,54,60,.06);border:1px solid rgba(32,54,60,.08);color:var(--ink)}.pill.good{background:rgba(47,111,116,.11);border-color:rgba(47,111,116,.12);color:var(--accent2)}
.hero-stats{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.hero-stat{padding:16px;border-radius:18px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.12)}.hero-stat .k{font-size:12px;opacity:.76;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}.hero-stat .v{font-size:30px;font-weight:800;line-height:1;margin-bottom:6px}.hero-stat .h{font-size:12px;line-height:1.45;color:rgba(251,247,241,.82)}
.layout{display:grid;gap:18px;margin-top:18px}.summary-grid{display:grid;grid-template-columns:1.15fr .9fr .95fr;gap:18px}.content{display:grid;gap:18px}.card{border-radius:28px;padding:22px}.section-head{display:flex;justify-content:space-between;gap:12px;align-items:start;margin-bottom:14px}
.filters-stack{display:grid;gap:14px}.filter-row{display:grid;gap:8px}.subhead{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}.filter,.mini-btn{cursor:pointer;border:1px solid var(--line);background:rgba(255,255,255,.72);color:var(--ink)}.filter.active,.mini-btn.active{background:linear-gradient(135deg,var(--accent),#984327);color:#fff8f1;border-color:transparent}.control-select,.control-input{width:100%;padding:11px 12px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.84);color:var(--ink);font:inherit}
.overview-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.overview-item,.mini-card,.scheme-label,.scheme-cell,.metric,.panel,.pick{border-radius:18px;border:1px solid rgba(32,54,60,.08);background:rgba(255,255,255,.78)}.overview-item,.mini-card,.scheme-label,.scheme-cell,.metric,.pick{padding:16px}.overview-item .label,.metric .k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}.overview-item .value{font-size:28px;font-weight:800;color:#994327;line-height:1.05}.overview-item .hint{margin-top:8px;font-size:12px;color:var(--muted)}.mini-card,.pick{display:grid;gap:8px}.mini-card .title{font-weight:700;line-height:1.5}
.scheme-board{display:grid;gap:12px}.scheme-row{display:grid;grid-template-columns:200px repeat(3,minmax(0,1fr));gap:10px;align-items:stretch}.scheme-label{display:grid;align-content:center;gap:6px;background:linear-gradient(180deg,rgba(255,252,247,.96),rgba(246,238,228,.94))}.scheme-cell{display:grid;gap:8px;min-height:112px}
.table-wrap{overflow:auto;border:1px solid rgba(32,54,60,.08);border-radius:18px;background:rgba(255,255,255,.78)}table{width:100%;border-collapse:collapse;min-width:760px}th,td{padding:12px 14px;border-bottom:1px solid rgba(32,54,60,.08);text-align:left;vertical-align:top;font-size:13px;line-height:1.55}th{position:sticky;top:0;background:#fcf8f1;z-index:1;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.sort-btn{border:0;background:none;padding:0;font:inherit;color:inherit;display:inline-flex;align-items:center;gap:8px;cursor:pointer}.sort-btn .arrows{display:inline-grid;line-height:.7;gap:1px;opacity:.28}.sort-btn .arrows span{display:block;font-size:10px}.sort-btn.active .arrows{opacity:.95}.sort-btn.active.asc .up,.sort-btn.active.desc .down{color:var(--accent);font-weight:800}
.ranking tbody tr{cursor:pointer}.ranking tbody tr:hover{background:rgba(47,111,116,.06)}.ranking tbody tr.on{background:rgba(180,87,53,.09);box-shadow:inset 4px 0 0 var(--accent)}.badge{width:max-content;padding:6px 10px;border-radius:999px;font-size:12px;font-weight:700;color:#fff;background:linear-gradient(135deg,var(--gold),#ba8623)}.badge.r2{background:linear-gradient(135deg,#7f9ca2,#5c747a)}.badge.r3{background:linear-gradient(135deg,#c57d54,#9c5538)}.badge.rn{background:linear-gradient(135deg,var(--accent2),#1f5a5f)}
.score{font-weight:800;color:#934424}.good{color:#1c7c64;font-weight:700}.mid{color:#9a6d1d;font-weight:700}.bad{color:var(--muted)}.pos{color:#1d6c6f;font-weight:700}.neg{color:#a04834;font-weight:700}
.score-strip,.detail-grid,.metric-grid{display:grid;gap:16px}.score-strip{grid-template-columns:1.45fr .9fr;margin-bottom:16px}.detail-grid{grid-template-columns:1.45fr .95fr}.metric-grid{grid-template-columns:repeat(4,1fr);margin-bottom:16px}.panel{padding:18px}.big{font-size:44px;line-height:1;font-weight:800;color:#964427}.bar{height:10px;border-radius:999px;background:rgba(32,54,60,.08);overflow:hidden;margin-top:12px}.bar>span{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--gold))}.meta-row td{background:rgba(32,54,60,.04);color:var(--muted);font-weight:700}.matrix th:first-child,.matrix td:first-child{position:sticky;left:0;z-index:2}.matrix th:first-child{background:#fcf8f1}.matrix td:first-child{background:rgba(252,248,241,.98);font-weight:700}.empty{padding:24px;border-radius:18px;background:rgba(255,255,255,.74);border:1px dashed rgba(32,54,60,.18);text-align:center;color:var(--muted)}.lancet-stack{display:grid;gap:18px}.scroll-window{max-height:min(48vh,520px);overflow:auto;padding-right:4px;scrollbar-gutter:stable}.scroll-window.compact{max-height:min(34vh,320px)}.scroll-window.tall{max-height:min(72vh,920px)}.table-wrap.windowed{max-height:min(58vh,760px);scrollbar-gutter:stable}.table-wrap.windowed.compact{max-height:min(34vh,320px)}#homeRankingSection .table-wrap.windowed{height:auto;max-height:none;flex:1;min-height:0}#detail{display:grid;gap:16px;align-content:start;max-height:none;overflow:visible;padding-right:0}.pill-list.compact .pill{padding:7px 10px;font-size:11px}.metric .k{font-size:11px}.metric .v{font-size:22px}.hidden{display:none!important}
#homeOverviewSection,#homeSchemeBoardSection,#lancetSection,#matrixSection{grid-column:1 / -1}#homeRankingSection,#homeDetailSection{min-height:min(76vh,980px)}#homeRankingSection{grid-column:1 / span 7;display:flex;flex-direction:column}#homeDetailSection{grid-column:8 / span 5;display:flex;flex-direction:column}
@media (min-width:1181px){.content{grid-template-columns:repeat(12,minmax(0,1fr))}}@media (max-width:1320px){.summary-grid{grid-template-columns:1fr}}@media (max-width:1180px){.hero-grid,.score-strip,.detail-grid{grid-template-columns:1fr}.overview-grid{grid-template-columns:repeat(2,1fr)}.scheme-row{grid-template-columns:1fr}#homeRankingSection,#homeDetailSection{grid-column:1 / -1;position:static;min-height:auto}}@media (max-width:760px){.page{width:calc(100vw - 12px);margin:6px auto 16px}.hero,.card{padding:18px;border-radius:22px}.hero-stats,.metric-grid,.overview-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="page"><header class="hero"><div class="hero-grid"><div><div class="eyebrow">Legacy Backup Snapshot</div><h1>旧版 12 模型 Dashboard 备份</h1><p>这版页面固定对应旧项目里的 <code>4 套人工方案 × 3 种固定效应 = 12 个模型</code>。首页保留排序、结构总览和单模型解读，完整 Lancet 表与横向矩阵拆到两个子页面，方便和当前 exhaustive 版并排对照。</p><div class="hero-meta" id="heroMeta"></div><nav class="page-nav" id="pageNav"><a class="nav-link" data-page="home" href="results_dashboard_legacy_12models.html">首页</a><a class="nav-link" data-page="lancet" href="results_dashboard_legacy_12models_lancet.html">Lancet 表</a><a class="nav-link" data-page="matrix" href="results_dashboard_legacy_12models_matrix.html">横向矩阵</a></nav></div><div class="hero-stats" id="heroStats"></div></div></header>
<div class="layout"><section class="summary-grid"><div class="card"><div class="section-head"><div><h2>筛选与范围</h2><p id="scopeNote">按方案、固定效应与代理变量切换旧版 12 个模型。</p></div></div><div class="filters-stack"><div class="filter-row"><div class="subhead">方案</div><div class="filters" id="schemeFilters"></div></div><div class="filter-row"><div class="subhead">固定效应</div><div class="filters" id="feFilters"></div></div><div class="filter-row"><div class="subhead">温度代理</div><select class="control-select" id="temperatureSelect"></select></div><div class="filter-row"><div class="subhead">污染代理</div><select class="control-select" id="pollutionSelect"></select></div><div class="filter-row"><div class="subhead">变量数</div><select class="control-select" id="nVarSelect"></select></div><div class="filter-row"><div class="subhead">检索</div><input class="control-input" id="searchInput" placeholder="搜索 model / variable / note" /></div><div class="filter-row"><div class="subhead">页面上限</div><div class="filters" id="pageLimitControls"></div></div></div></div><div class="card"><div class="section-head"><div><h2>固定效应最佳</h2><p>每种 FE 里表现最好的模型，方便先看方向差异。</p></div></div><div id="bestByFe"></div></div><div class="card"><div class="section-head"><div><h2>旧版线索</h2><p>从这 12 个模型里提炼几个最值得回看的结构信号。</p></div></div><div id="batchInsight"></div></div></section>
<main class="content"><section class="card" id="homeOverviewSection"><div class="section-head"><div><h2>首页概览</h2><p>先看旧版 12 模型的整体面貌，再往下看排序与单模型细节。</p></div></div><div class="overview-grid" id="overviewGrid"></div></section><section class="card" id="homeSchemeBoardSection"><div class="section-head"><div><h2>方案 × FE 总览</h2><p>4 套方案在 3 种固定效应下的完整 12 模型布局，首页直接看清每个位置。</p></div></div><div class="scheme-board" id="schemeBoard"></div></section><section class="card" id="homeRankingSection"><div class="section-head"><div><h2>综合排序</h2><p>首页只保留排序表与单模型阅读，不再把完整长表堆在主页面。</p></div><div class="chips"><span class="chip soft" id="countChip"></span></div></div><div class="table-wrap windowed"><table class="ranking" id="rankingTable"></table></div></section><section class="card" id="homeDetailSection"><div class="section-head"><div><h2>模型详情</h2><p>点击左侧任意一行即可切换；完整系数表和横向矩阵都拆到子页面。</p></div></div><div id="detail"></div></section><section class="card hidden" id="lancetSection"><div class="section-head"><div><h2>Lancet 风格结果表</h2><p>12 个旧版模型的完整回归表统一放到这个子页面里。</p></div><div class="chips"><span class="chip soft" id="lancetCountChip"></span></div></div><div class="lancet-stack" id="lancetGallery"></div></section><section class="card hidden" id="matrixSection"><div class="section-head"><div><h2>横向比较矩阵</h2><p>矩阵直接读取 <code>variable_group_scheme_horizontal_compare.csv</code>，适合并排看 12 个模型。</p></div><div class="chips"><span class="chip soft" id="matrixCountChip"></span></div></div><div class="table-wrap windowed"><table class="matrix" id="matrixTable"></table></div></section></main></div></div>
<script id="dashboard-data" type="application/json">__PAYLOAD__</script>
<script>
const data=JSON.parse(document.getElementById('dashboard-data').textContent);const pageKind="__PAGE_KIND__";const matrixModelSet=new Set(data.matrix_model_ids||[]);
const state={scheme:'全部',fe:'全部',temperature:'全部',pollution:'全部',nvars:'全部',search:'',selected:data.ranking[0]?data.ranking[0].model_id:null,sortKey:'performance_rank',sortDir:'asc',lancetLimit:12,matrixLimit:12};
const heroItems=[['模型数量',data.total_models,'固定为旧版 12 个模型'],['方案数量',data.scheme_count,'A / C / D / F 四套人工方案'],['固定效应',data.fe_count,'Year / Province / Two-way'],['最佳模型',data.best_model?`#${data.best_model.performance_rank}`:'—',data.best_model?data.best_model.model_id:'当前没有结果']];
const sortDefaults={performance_rank:'asc',scheme_id:'asc',performance_score:'desc',coef_R1xday:'desc',coef_AMC:'desc',r2_model:'desc',n_vars:'asc',max_vif_z:'asc'};const metaRows=new Set(data.meta_rows||[]);
const html=v=>v===null||v===undefined?'':String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');const label=v=>html(v).replace(/\\n/g,'<br>');
const parseNum=v=>{if(v===null||v===undefined||v==='')return Number.NaN;if(typeof v==='string'){const t=v.trim();if(t.startsWith('<'))return Number(t.slice(1));const n=Number(t.replace(/\\*+/g,''));return Number.isFinite(n)?n:Number.NaN}const n=Number(v);return Number.isFinite(n)?n:Number.NaN};
const num=(v,d=3)=>{const n=parseNum(v);return Number.isFinite(n)?n.toFixed(d):'—'};const short=v=>{const n=parseNum(v);return Number.isFinite(n)?n.toFixed(3):'—'};const pcls=v=>{const n=parseNum(v);if(!Number.isFinite(n))return 'bad';if(n<0.05)return 'good';if(n<0.10)return 'mid';return 'bad'};const ccls=v=>{const n=parseNum(v);if(!Number.isFinite(n))return '';return n>=0?'pos':'neg'};const badge=r=>r===1?'':r===2?' r2':r===3?' r3':' rn';const stars=p=>{const n=parseNum(p);if(!Number.isFinite(n))return '';if(n<0.001)return '***';if(n<0.01)return '**';if(n<0.05)return '*';return ''};
const filteredBase=()=>data.ranking.filter(row=>(state.scheme==='全部'||row.scheme===state.scheme)&&(state.fe==='全部'||row.fe_label===state.fe)&&(state.temperature==='全部'||row.temperature_proxy===state.temperature)&&(state.pollution==='全部'||row.pollution_proxy===state.pollution)&&(state.nvars==='全部'||row.n_vars_label===state.nvars)&&(!state.search||String(row.search_text||'').includes(state.search.toLowerCase())));
const compareValue=(a,b,key)=>{const va=a[key],vb=b[key];if(key==='model_id'||key==='scheme_id')return String(va||'').localeCompare(String(vb||''),'zh');const na=parseNum(va),nb=parseNum(vb);if(!Number.isFinite(na)&&!Number.isFinite(nb))return 0;if(!Number.isFinite(na))return 1;if(!Number.isFinite(nb))return -1;return na-nb};
const getSortedList=()=>{const list=filteredBase().slice();list.sort((a,b)=>{const cmp=compareValue(a,b,state.sortKey);if(cmp===0)return compareValue(a,b,'performance_rank');return state.sortDir==='asc'?cmp:-cmp});return list};const performanceOrdered=list=>list.slice().sort((a,b)=>compareValue(a,b,'performance_rank'));
const setSort=key=>{if(state.sortKey===key)state.sortDir=state.sortDir==='asc'?'desc':'asc';else{state.sortKey=key;state.sortDir=sortDefaults[key]||'desc'}};const ensureSelection=list=>{if(!list.length){state.selected=null;return}if(!list.some(item=>item.model_id===state.selected))state.selected=performanceOrdered(list)[0].model_id};
function renderHero(){document.getElementById('heroMeta').innerHTML=[`生成时间：${html(data.generated_at)}`,'来源：variable_group_scheme_*',html(data.scope_note)].map(t=>`<span class="hero-chip">${t}</span>`).join('');document.getElementById('scopeNote').textContent=data.scope_note;document.getElementById('heroStats').innerHTML=heroItems.map(([k,v,h])=>`<div class="hero-stat"><div class="k">${html(k)}</div><div class="v">${html(v)}</div><div class="h">${html(h)}</div></div>`).join('');document.querySelectorAll('#pageNav .nav-link').forEach(link=>link.classList.toggle('active',link.dataset.page===pageKind))}
function renderFilters(){const btns=(id,values,current,key)=>document.getElementById(id).innerHTML=values.map(v=>`<button class="filter ${current===v?'active':''}" data-filter-key="${key}" data-filter-value="${html(v)}">${html(v)}</button>`).join('');btns('schemeFilters',['全部',...data.scheme_labels],state.scheme,'scheme');btns('feFilters',['全部',...data.fe_labels],state.fe,'fe');const fill=(id,values,current)=>document.getElementById(id).innerHTML=['全部',...values].map(v=>`<option value="${html(v)}" ${v===current?'selected':''}>${html(v)}</option>`).join('');fill('temperatureSelect',data.temperature_labels,state.temperature);fill('pollutionSelect',data.pollution_labels,state.pollution);fill('nVarSelect',data.n_var_labels,state.nvars);document.querySelectorAll('[data-filter-key]').forEach(btn=>btn.onclick=()=>{state[btn.dataset.filterKey]=btn.dataset.filterValue;renderAll()});document.getElementById('temperatureSelect').onchange=e=>{state.temperature=e.target.value;renderAll(false)};document.getElementById('pollutionSelect').onchange=e=>{state.pollution=e.target.value;renderAll(false)};document.getElementById('nVarSelect').onchange=e=>{state.nvars=e.target.value;renderAll(false)};const s=document.getElementById('searchInput');if(s.value!==state.search)s.value=state.search;s.oninput=e=>{state.search=e.target.value;renderAll(false)};const controls=pageKind==='matrix'?[4,8,12].map(v=>({k:'matrixLimit',v,l:`矩阵 ${v} 列`})):pageKind==='lancet'?[4,8,12].map(v=>({k:'lancetLimit',v,l:`Lancet ${v} 张`})):[{k:'sortPreset',v:'rank',l:'按 Rank'},{k:'sortPreset',v:'score',l:'按 Score'}];document.getElementById('pageLimitControls').innerHTML=controls.map(item=>{const active=item.k==='matrixLimit'?state.matrixLimit===item.v:item.k==='lancetLimit'?state.lancetLimit===item.v:(item.v==='rank'?state.sortKey==='performance_rank':state.sortKey==='performance_score');return `<button class="mini-btn ${active?'active':''}" data-limit-kind="${item.k}" data-limit-value="${item.v}">${html(item.l)}</button>`}).join('');document.querySelectorAll('[data-limit-kind]').forEach(btn=>btn.onclick=()=>{if(btn.dataset.limitKind==='matrixLimit')state.matrixLimit=Number(btn.dataset.limitValue);else if(btn.dataset.limitKind==='lancetLimit')state.lancetLimit=Number(btn.dataset.limitValue);else if(btn.dataset.limitValue==='rank'){state.sortKey='performance_rank';state.sortDir='asc'}else{state.sortKey='performance_score';state.sortDir='desc'}renderAll()})}
function renderOverview(){const s=data.signal_summary||{},b=data.best_model;document.getElementById('overviewGrid').innerHTML=[['最佳模型',b?b.model_id:'—',b?`${b.fe_short} · Score ${num(b.performance_score)}`:''],['R1xday 显著',`${s.r1_sig_count||0} / ${data.total_models}`,'p < 0.05 的模型数'],['AMC 显著',`${s.amc_sig_count||0} / ${data.total_models}`,'p < 0.05 的模型数'],['双正系数',`${s.both_positive_count||0} / ${data.total_models}`,'R1xday 与 AMC 同时为正']].map(([k,v,h])=>`<div class="overview-item"><div class="label">${html(k)}</div><div class="value">${html(v)}</div><div class="hint">${html(h)}</div></div>`).join('')}
function renderBestByFe(){const items=data.best_by_fe||[];document.getElementById('bestByFe').innerHTML=items.length?items.map(item=>`<div class="mini-card"><div class="chips"><span class="chip">${html(item.fe_short)}</span><span class="chip soft">#${html(item.performance_rank)}</span></div><div class="title">${label(item.model_id)}</div><div style="font-size:12px;color:var(--muted)">方案 ${html(item.scheme)} · Score ${num(item.performance_score)}</div></div>`).join(''):'<div class="empty">当前没有 FE 对照结果。</div>'}
function renderBatchInsight(){const fam=(data.family_summary||[]).slice(0,3).map(group=>{const first=group.choices&&group.choices[0];return first?`<div class="pick"><div class="chips"><span class="chip soft">${html(group.label)}</span></div><div style="font-size:12px;color:var(--muted)">${label(first.label)} · ${html(first.share_text)}</div></div>`:''}).join('');const vars=(data.variable_frequency||[]).slice(0,3).map(item=>`<span class="pill">${label(item.label)} · ${html(item.share_text)}</span>`).join('');document.getElementById('batchInsight').innerHTML=`<div class="pick"><div class="chips"><span class="chip soft">固定范围</span></div><div style="font-size:12px;color:var(--muted)">4 套方案 · 3 种 FE · 共 12 个模型</div></div><div class="pick"><div class="chips"><span class="chip soft">显著信号</span></div><div style="font-size:12px;color:var(--muted)">R1xday 显著 ${html((data.signal_summary||{}).r1_sig_count)} / 12 · AMC 显著 ${html((data.signal_summary||{}).amc_sig_count)} / 12</div></div>${fam}<div class="pick"><div class="chips"><span class="chip soft">高频变量</span></div><div class="pill-list">${vars||'<span class="pill">暂无统计</span>'}</div></div>`}
function renderSchemeBoard(){document.getElementById('schemeBoard').innerHTML=(data.scheme_board||[]).map(row=>`<div class="scheme-row"><div class="scheme-label"><div class="chips"><span class="chip scheme">${html(row.scheme)}</span></div><div style="font-size:13px;color:var(--muted)">同一方案在三种固定效应下的完整位置</div></div>${row.cells.map(cell=>`<div class="scheme-cell"><div class="chips"><span class="chip">${html(cell.fe_short)}</span><span class="chip soft">${cell.performance_rank?`#${html(cell.performance_rank)}`:'—'}</span></div><div style="font-weight:700;line-height:1.5">${label(cell.model_id||'无结果')}</div><div style="font-size:12px;color:var(--muted)">Score ${num(cell.performance_score)} · R1xday ${num(cell.coef_R1xday,4)} · AMC ${num(cell.coef_AMC,4)}</div></div>`).join('')}</div>`).join('')}
function renderRanking(list){document.getElementById('countChip').textContent=`当前显示 ${list.length} / ${data.total_models} 个旧版模型`;const table=document.getElementById('rankingTable');if(!list.length){table.innerHTML='<tbody><tr><td class="empty">当前筛选条件下没有模型。</td></tr></tbody>';return}const head=(k,t)=>`<button class="sort-btn ${state.sortKey===k?`active ${state.sortDir}`:''}" data-sort="${k}"><span>${t}</span><span class="arrows"><span class="up">▲</span><span class="down">▼</span></span></button>`;table.innerHTML=`<thead><tr><th>${head('performance_rank','Rank')}</th><th>${head('scheme_id','Scheme')}</th><th>Proxy Mix</th><th>${head('performance_score','Score')}</th><th>${head('coef_R1xday','R1xday')}</th><th>${head('coef_AMC','AMC')}</th><th>${head('r2_model','R²')}</th><th>${head('max_vif_z','VIF(z)')}</th></tr></thead><tbody>${list.map(row=>`<tr data-model="${html(row.model_id)}" class="${row.model_id===state.selected?'on':''}"><td><span class="badge${badge(row.performance_rank)}">#${row.performance_rank}</span></td><td><div style="font-weight:700;line-height:1.5">${label(row.scheme_id||row.model_id)}</div><div class="chips" style="margin-top:6px"><span class="chip scheme">${html(row.scheme)}</span><span class="chip soft">${html(row.fe_short)}</span></div></td><td><div>${label(row.temperature_proxy)}</div><div style="font-size:12px;color:var(--muted)">${label(row.pollution_proxy)} · ${html(row.n_vars_label)}</div></td><td class="score">${num(row.performance_score)}</td><td><div class="${ccls(row.coef_R1xday)}">${num(row.coef_R1xday,4)}${stars(row.p_R1xday)}</div><div class="${pcls(row.p_R1xday)}" style="font-size:12px">p=${num(row.p_R1xday,4)}</div></td><td><div class="${ccls(row.coef_AMC)}">${num(row.coef_AMC,4)}${stars(row.p_AMC)}</div><div class="${pcls(row.p_AMC)}" style="font-size:12px">p=${num(row.p_AMC,4)}</div></td><td>${num(row.r2_model)}</td><td>${num(row.max_vif_z)}</td></tr>`).join('')}</tbody>`;table.querySelectorAll('[data-sort]').forEach(btn=>btn.onclick=e=>{e.stopPropagation();setSort(btn.dataset.sort);renderAll(false)});table.querySelectorAll('tbody tr[data-model]').forEach(row=>row.onclick=()=>{state.selected=row.dataset.model;renderAll(false)})}
function renderDetail(model){const target=document.getElementById('detail');if(!model){target.innerHTML='<div class="empty">没有可展示的模型，请调整筛选条件。</div>';return}const vif=(data.vif_tables[model.model_id]||[]).slice(0,10);const sigs=model.significant_predictors&&model.significant_predictors.length?model.significant_predictors.map(item=>`<span class="pill good">${label(item)}</span>`).join(''):'<span class="pill">当前无 p&lt;0.05 的解释变量</span>';const vars=(model.variables_list||[]).map(item=>`<span class="pill">${label(item)}</span>`).join('');const fam=model.family_pairs&&model.family_pairs.length?model.family_pairs.map(item=>`<span class="pill">${html(item.label)}: ${label(item.value)}</span>`).join(''):'<span class="pill">旧版结果没有 family_selection 字段，这里按变量名近似识别</span>';const pct=Math.max(0,Math.min(100,Number(model.performance_score||0)*100));const lancetLink=`results_dashboard_legacy_12models_lancet.html#${encodeURIComponent(model.model_id)}`;target.innerHTML=`<div class="score-strip"><div class="panel"><div class="eyebrow" style="color:var(--muted)">Selected Model</div><h3>${label(model.model_id)}</h3><p style="margin-top:10px;color:var(--muted);line-height:1.7">${html(model.scheme_note||'旧版人工方案比较模型')}</p><div class="chips" style="margin-top:12px"><span class="chip scheme">${html(model.scheme)}</span><span class="chip">${html(model.fe_short)}</span><span class="chip soft">Rank ${html(model.performance_rank)}</span><span class="chip soft">${html(model.n_vars_label)}</span></div><div class="bar"><span style="width:${pct}%"></span></div></div><div class="panel"><div class="eyebrow" style="color:var(--muted)">Composite Score</div><div class="big">${num(model.performance_score)}</div><div style="font-size:12px;color:var(--muted);margin-top:8px">core ${num(model.core_signal_score)} · fit ${num(model.fit_score)} · vif ${num(model.vif_score)}</div><div class="pill-list" style="margin-top:14px"><a class="pill" href="${lancetLink}">看完整 Lancet 表</a><a class="pill" href="results_dashboard_legacy_12models_matrix.html">去横向矩阵页</a></div></div></div><div class="metric-grid"><div class="metric"><div class="k">R-squared</div><div class="v">${num(model.r2_model)}</div></div><div class="metric"><div class="k">R-squared (Overall)</div><div class="v">${num(model.r2_overall)}</div></div><div class="metric"><div class="k">R² (within)</div><div class="v">${num(model.r2_within)}</div></div><div class="metric"><div class="k">max VIF(z)</div><div class="v">${num(model.max_vif_z)}</div></div></div><div class="detail-grid"><div style="display:grid;gap:16px"><div class="panel"><div class="section-head"><div><h3>代理家族</h3><p>旧版没有 family_selection 字段，这里按变量名做近似识别。</p></div></div><div class="pill-list">${fam}</div></div><div class="panel"><div class="section-head"><div><h3>变量组成</h3><p>这套模型当前使用 ${html(model.n_vars)} 个解释变量，样本量 ${html(model.nobs)}。</p></div></div><div class="pill-list">${vars}</div></div><div class="panel"><div class="section-head"><div><h3>显著结果提示</h3><p>这里展示 summary 表里当前记为显著的解释变量。</p></div></div><div class="pill-list">${sigs}</div></div></div><div style="display:grid;gap:16px"><div class="panel"><div class="section-head"><div><h3>核心变量快照</h3><p>优先看 R1xday 和抗菌药物使用强度的方向与显著性。</p></div></div><div class="pill-list"><span class="pill good">R1xday = ${num(model.coef_R1xday,4)}</span><span class="pill ${pcls(model.p_R1xday)==='good'?'good':''}">p = ${num(model.p_R1xday,4)}</span><span class="pill good">AMC = ${num(model.coef_AMC,4)}</span><span class="pill ${pcls(model.p_AMC)==='good'?'good':''}">p = ${num(model.p_AMC,4)}</span></div></div><div class="panel"><div class="section-head"><div><h3>VIF Top ${vif.length}</h3><p>按 vif_z 从高到低排列，用来快速识别共线性压力。</p></div></div><div class="table-wrap windowed compact"><table><thead><tr><th>Predictor</th><th>VIF raw</th><th>VIF z</th><th>|diff|</th></tr></thead><tbody>${vif.map(row=>`<tr><td>${label(row.predictor)}</td><td>${num(row.vif_raw)}</td><td>${num(row.vif_z)}</td><td>${num(row.abs_diff)}</td></tr>`).join('')}</tbody></table></div></div><div class="panel"><div class="section-head"><div><h3>子页面入口</h3><p>完整回归表和横向比较已拆到两个子页面。</p></div></div><div class="pill-list"><a class="pill" href="${lancetLink}">打开这套模型的 Lancet 表</a><a class="pill" href="results_dashboard_legacy_12models_matrix.html">打开横向矩阵页</a></div></div></div></div>`}
function renderLancetGallery(list){const rows=performanceOrdered(list).slice(0,state.lancetLimit);document.getElementById('lancetCountChip').textContent=`当前显示 ${rows.length} 张 / 命中 ${list.length} 张`;document.getElementById('lancetGallery').innerHTML=rows.length?rows.map(model=>{const lancet=data.lancet_tables[model.model_id]||[];return `<div class="panel" id="${encodeURIComponent(model.model_id)}"><div class="section-head"><div><h3>${label(model.model_id)}</h3><p>${html(model.scheme_note||'旧版人工方案比较模型')}</p></div><div class="chips"><span class="chip scheme">${html(model.scheme)}</span><span class="chip">${html(model.fe_short)}</span><span class="chip soft">Score ${num(model.performance_score)}</span></div></div><div class="table-wrap windowed compact"><table><thead><tr><th>Predictor</th><th>Coefficient</th><th>95% CI</th><th>p value</th></tr></thead><tbody>${lancet.map(row=>`<tr class="${metaRows.has(row.Predictor)?'meta-row':''}"><td>${label(row.Predictor)}</td><td>${html(row.Coefficient||'—')}</td><td>${html(row['95% CI']||'—')}</td><td class="${pcls(row['p value'])}">${html(row['p value']||'—')}</td></tr>`).join('')}</tbody></table></div></div>`}).join(''):'<div class="empty">当前筛选条件下没有 Lancet 风格结果表。</div>'}
 function renderDetail(model){const target=document.getElementById('detail');if(!model){target.innerHTML='<div class="empty">当前筛选条件下没有可展示的模型。</div>';return}const vif=(data.vif_tables[model.model_id]||[]).slice(0,8);const sigs=model.significant_predictors&&model.significant_predictors.length?model.significant_predictors.map(item=>`<span class="pill good">${label(item)}</span>`).join(''):'<span class="pill">当前无 p&lt;0.05 的解释变量</span>';const vars=(model.variables_list||[]).map(item=>`<span class="pill">${label(item)}</span>`).join('');const fam=model.family_pairs&&model.family_pairs.length?model.family_pairs.map(item=>`<span class="pill">${html(item.label)}: ${label(item.value)}</span>`).join(''):'<span class="pill">旧版结果没有 family_selection 字段，这里按变量名近似识别</span>';const pct=Math.max(0,Math.min(100,Number(model.performance_score||0)*100));const lancetLink=`results_dashboard_legacy_12models_lancet.html#${encodeURIComponent(model.model_id)}`;target.innerHTML=`<div class="score-strip"><div class="panel"><div class="eyebrow" style="color:var(--muted)">Selected Model</div><h3>${label(model.model_id)}</h3><p style="margin-top:10px;color:var(--muted);line-height:1.62">${html(model.scheme_note||'旧版人工方案比较模型')}</p><div class="chips" style="margin-top:12px"><span class="chip scheme">${html(model.scheme)}</span><span class="chip">${html(model.fe_short)}</span><span class="chip soft">Rank ${html(model.performance_rank)}</span><span class="chip soft">${html(model.n_vars_label)}</span></div><div class="bar"><span style="width:${pct}%"></span></div></div><div class="panel"><div class="eyebrow" style="color:var(--muted)">Composite Score</div><div class="big">${num(model.performance_score)}</div><div style="font-size:12px;color:var(--muted);margin-top:8px">core ${num(model.core_signal_score)} · fit ${num(model.fit_score)} · vif ${num(model.vif_score)} · n=${html(model.nobs)}</div><div class="pill-list compact" style="margin-top:14px"><a class="pill" href="${lancetLink}">看完整 Lancet 表</a><a class="pill" href="results_dashboard_legacy_12models_matrix.html">去横向矩阵页</a></div></div></div><div class="metric-grid"><div class="metric"><div class="k">R-squared</div><div class="v">${num(model.r2_model)}</div></div><div class="metric"><div class="k">R-squared (Overall)</div><div class="v">${num(model.r2_overall)}</div></div><div class="metric"><div class="k">R² (within)</div><div class="v">${num(model.r2_within)}</div></div><div class="metric"><div class="k">max VIF(z)</div><div class="v">${num(model.max_vif_z)}</div></div></div><div class="detail-grid"><div style="display:grid;gap:16px"><div class="panel"><div class="section-head"><div><h3>结构解读</h3><p>把代理家族、变量组成和显著结果合并起来，首页只保留最关键的信息。</p></div></div><div style="display:grid;gap:14px"><div><div class="eyebrow" style="color:var(--muted)">代理家族</div><div class="pill-list compact">${fam}</div></div><div><div class="eyebrow" style="color:var(--muted)">变量组成</div><div class="pill-list compact">${vars}</div></div><div><div class="eyebrow" style="color:var(--muted)">显著结果</div><div class="pill-list compact">${sigs}</div></div></div></div></div><div style="display:grid;gap:16px"><div class="panel"><div class="section-head"><div><h3>核心变量快照</h3><p>优先看 R1xday 和抗菌药物使用强度的方向与显著性。</p></div></div><div class="pill-list compact"><span class="pill good">R1xday = ${num(model.coef_R1xday,4)}</span><span class="pill ${pcls(model.p_R1xday)==='good'?'good':''}">p = ${num(model.p_R1xday,4)}</span><span class="pill good">AMC = ${num(model.coef_AMC,4)}</span><span class="pill ${pcls(model.p_AMC)==='good'?'good':''}">p = ${num(model.p_AMC,4)}</span></div></div><div class="panel"><div class="section-head"><div><h3>VIF Top ${vif.length}</h3><p>按 vif_z 从高到低排列，用来快速识别共线性压力。</p></div></div><div class="table-wrap"><table><thead><tr><th>Predictor</th><th>VIF raw</th><th>VIF z</th><th>|diff|</th></tr></thead><tbody>${vif.map(row=>`<tr><td>${label(row.predictor)}</td><td>${num(row.vif_raw)}</td><td>${num(row.vif_z)}</td><td>${num(row.abs_diff)}</td></tr>`).join('')}</tbody></table></div></div><div class="panel"><div class="section-head"><div><h3>子页面入口</h3><p>完整回归表和横向比较都放到子页面，首页不再重复堆长表。</p></div></div><div class="pill-list compact"><a class="pill" href="${lancetLink}">打开完整 Lancet 页</a><a class="pill" href="results_dashboard_legacy_12models_matrix.html">打开横向矩阵页</a></div></div></div></div>`}
 function renderLancetGallery(list){const rows=performanceOrdered(list).slice(0,state.lancetLimit);document.getElementById('lancetCountChip').textContent=`当前显示 ${rows.length} 张 / 命中 ${list.length} 张`;document.getElementById('lancetGallery').innerHTML=rows.length?rows.map(model=>{const lancet=data.lancet_tables[model.model_id]||[];return `<div class="panel" id="${encodeURIComponent(model.model_id)}"><div class="section-head"><div><h3>${label(model.model_id)}</h3><p>${html(model.scheme_note||'旧版人工方案比较模型')}</p></div><div class="chips"><span class="chip scheme">${html(model.scheme)}</span><span class="chip">${html(model.fe_short)}</span><span class="chip soft">Score ${num(model.performance_score)}</span></div></div><div class="table-wrap"><table><thead><tr><th>Predictor</th><th>Coefficient</th><th>95% CI</th><th>p value</th></tr></thead><tbody>${lancet.map(row=>`<tr class="${metaRows.has(row.Predictor)?'meta-row':''}"><td>${label(row.Predictor)}</td><td>${html(row.Coefficient||'—')}</td><td>${html(row['95% CI']||'—')}</td><td class="${pcls(row['p value'])}">${html(row['p value']||'—')}</td></tr>`).join('')}</tbody></table></div></div>`}).join(''):'<div class="empty">当前筛选条件下没有 Lancet 风格结果表。</div>'}
 function renderDetailCompact(model){const target=document.getElementById('detail');if(!model){target.innerHTML='<div class="empty">当前筛选条件下没有可展示的模型。</div>';return}const fam=model.family_pairs&&model.family_pairs.length?model.family_pairs.map(item=>`<span class="pill">${html(item.label)}: ${label(item.value)}</span>`).join(''):'<span class="pill">旧版结果没有 family_selection 字段，这里按变量名近似识别</span>';const vars=(model.variables_list||[]).map(item=>`<span class="pill">${label(item)}</span>`).join('');const pct=Math.max(0,Math.min(100,Number(model.performance_score||0)*100));const lancetLink=`results_dashboard_legacy_12models_lancet.html#${encodeURIComponent(model.model_id)}`;target.innerHTML=`<div class="score-strip"><div class="panel"><div class="eyebrow" style="color:var(--muted)">Selected Model</div><h3>${label(model.model_id)}</h3><p style="margin-top:10px;color:var(--muted);line-height:1.62">${html(model.scheme_note||'旧版人工方案比较模型')}</p><div class="chips" style="margin-top:12px"><span class="chip scheme">${html(model.scheme)}</span><span class="chip">${html(model.fe_short)}</span><span class="chip soft">Rank ${html(model.performance_rank)}</span><span class="chip soft">${html(model.n_vars_label)}</span></div><div class="bar"><span style="width:${pct}%"></span></div></div><div class="panel"><div class="eyebrow" style="color:var(--muted)">Composite Score</div><div class="big">${num(model.performance_score)}</div><div style="font-size:12px;color:var(--muted);margin-top:8px">core ${num(model.core_signal_score)} · fit ${num(model.fit_score)} · vif ${num(model.vif_score)} · n=${html(model.nobs)}</div><div class="pill-list compact" style="margin-top:14px"><a class="pill" href="${lancetLink}">打开 Lancet 页</a><a class="pill" href="results_dashboard_legacy_12models_matrix.html">打开横向矩阵页</a></div></div></div><div class="metric-grid"><div class="metric"><div class="k">R-squared</div><div class="v">${num(model.r2_model)}</div></div><div class="metric"><div class="k">R-squared (Overall)</div><div class="v">${num(model.r2_overall)}</div></div><div class="metric"><div class="k">R² (within)</div><div class="v">${num(model.r2_within)}</div></div><div class="metric"><div class="k">max VIF(z)</div><div class="v">${num(model.max_vif_z)}</div></div></div><div class="detail-grid"><div class="panel"><div class="section-head"><div><h3>结构解读</h3><p>首页只保留不能从 Lancet 表直接读出的结构信息。</p></div></div><div style="display:grid;gap:14px"><div><div class="eyebrow" style="color:var(--muted)">Proxy Mix</div><div class="pill-list compact"><span class="pill">${label(model.temperature_proxy||'—')}</span><span class="pill">${label(model.pollution_proxy||'—')}</span><span class="pill">${html(model.n_vars_label||'')}</span></div></div><div><div class="eyebrow" style="color:var(--muted)">代理家族</div><div class="pill-list compact">${fam}</div></div><div><div class="eyebrow" style="color:var(--muted)">变量组成</div><div class="pill-list compact">${vars}</div></div></div></div><div class="panel"><div class="section-head"><div><h3>阅读入口</h3><p>系数方向、95% CI 和显著性统一到 Lancet 子页查看，首页不再重复展示。</p></div></div><div style="display:grid;gap:12px"><div style="padding:14px 16px;border-radius:16px;background:rgba(32,54,60,.04);border:1px solid rgba(32,54,60,.08);font-size:12px;color:var(--muted);line-height:1.7">n = ${html(model.nobs)} · scheme = ${html(model.scheme)} · FE = ${html(model.fe_short)}</div><div style="padding:14px 16px;border-radius:16px;background:rgba(32,54,60,.04);border:1px solid rgba(32,54,60,.08);font-size:12px;color:var(--muted);line-height:1.7">先看这一页的代理结构和变量组成，再去 Lancet 表读 R1xday、AMC 和其余系数。</div><div class="pill-list compact"><a class="pill" href="${lancetLink}">看完整 Lancet 表</a><a class="pill" href="results_dashboard_legacy_12models_matrix.html">看横向矩阵</a></div></div></div></div>`}
 function renderMatrix(list){const rows=performanceOrdered(list.filter(item=>matrixModelSet.has(item.model_id))).slice(0,state.matrixLimit),total=list.filter(item=>matrixModelSet.has(item.model_id)).length;document.getElementById('matrixCountChip').textContent=`当前显示 ${rows.length} 列 / 命中 ${total} 列`;const table=document.getElementById('matrixTable');if(!rows.length){table.innerHTML='<tbody><tr><td class="empty">当前筛选条件下没有矩阵列。</td></tr></tbody>';return}const ids=rows.map(item=>item.model_id);table.innerHTML=`<thead><tr><th>Metric</th>${ids.map(id=>`<th>${label(id)}</th>`).join('')}</tr></thead><tbody>${data.matrix_rows.map(row=>`<tr><td>${html(row.metric)}</td>${ids.map(id=>{const value=row.values?row.values[id]:null;return `<td class="${String(row.metric).startsWith('p_')?pcls(value):''}">${short(value)}</td>`}).join('')}</tr>`).join('')}</tbody>`}
function applyPageMode(){const showHome=pageKind==='home';['homeOverviewSection','homeSchemeBoardSection','homeRankingSection','homeDetailSection'].forEach(id=>document.getElementById(id).classList.toggle('hidden',!showHome));document.getElementById('lancetSection').classList.toggle('hidden',pageKind!=='lancet');document.getElementById('matrixSection').classList.toggle('hidden',pageKind!=='matrix')}
function renderAll(refilter=true){if(refilter)renderFilters();applyPageMode();renderOverview();renderBestByFe();renderBatchInsight();renderSchemeBoard();const list=getSortedList();ensureSelection(list);if(pageKind==='home'){renderRanking(list);renderDetailCompact(list.find(item=>item.model_id===state.selected)||null)}else if(pageKind==='lancet')renderLancetGallery(list);else if(pageKind==='matrix')renderMatrix(list)}
try{renderHero();renderAll()}catch(error){document.body.innerHTML=`<div style="max-width:960px;margin:32px auto;padding:24px;border-radius:18px;background:#fff7f3;border:1px solid rgba(180,87,53,.22);font-family:'Segoe UI',sans-serif;color:#5f2a1a;line-height:1.7"><h2 style="margin:0 0 12px;font-family:Georgia,serif">Dashboard 脚本初始化失败</h2><p style="margin:0 0 10px">页面框架已经生成，但前端脚本运行时报错，所以数据没有渲染出来。</p><pre style="white-space:pre-wrap;background:#fff;border-radius:12px;padding:14px;border:1px solid rgba(32,54,60,.08)">${html(error&&error.stack?error.stack:String(error))}</pre></div>`}
</script>
</body>
</html>"""
    return template.replace("__PAYLOAD__", data_json).replace("__PAGE_KIND__", page_kind)


def main() -> None:
    payload = build_payload()
    for kind, path in {"home": OUTPUT_HOME_HTML, "lancet": OUTPUT_LANCET_HTML, "matrix": OUTPUT_MATRIX_HTML}.items():
        path.write_text(build_html(payload, kind), encoding="utf-8")
        print(f"Saved legacy dashboard backup: {path}")


if __name__ == "__main__":
    main()
