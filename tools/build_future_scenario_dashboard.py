from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "6 未来情景分析"
RESULTS_DIR = PROJECT_DIR / "results"
OUT_FILE = PROJECT_DIR / "index.html"


MODE_META = [
    {
        "id": "lancet_ets",
        "label": "Lancet-like ETS baseline",
        "short_label": "Lancet ETS",
        "tagline": "先让 AMR 自身按 ETS 延续，再把未来 R1xday 情景增量叠加上去。",
        "use_case": "当你要强调对 Lancet 2023 Figure 5 写法的贴近度时，优先看这一版。",
    },
    {
        "id": "x_driven",
        "label": "X-driven / Nature-like simplified baseline",
        "short_label": "X-driven",
        "tagline": "先用未来协变量路径形成 baseline，再由历史系数重建未来 AMR。",
        "use_case": "当你更关心未来气候路径如何拉开情景差距时，优先看这一版。",
    },
]

SCENARIO_META = [
    {"id": "baseline_ets", "short_label": "Baseline", "label": "Baseline", "family": "baseline"},
    {"id": "ssp119", "short_label": "SSP1-1.9", "label": "SSP1-1.9（rx1day）", "family": "rx1day_ssp"},
    {"id": "ssp126", "short_label": "SSP1-2.6", "label": "SSP1-2.6（rx1day）", "family": "rx1day_ssp"},
    {"id": "ssp245", "short_label": "SSP2-4.5", "label": "SSP2-4.5（rx1day）", "family": "rx1day_ssp"},
    {"id": "ssp370", "short_label": "SSP3-7.0", "label": "SSP3-7.0（rx1day）", "family": "rx1day_ssp"},
    {"id": "ssp585", "short_label": "SSP5-8.5", "label": "SSP5-8.5（rx1day）", "family": "rx1day_ssp"},
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def maybe_add(catalog: list[dict[str, str]], label: str, relative_path: str, note: str) -> None:
    path = PROJECT_DIR / relative_path
    if path.exists():
        catalog.append({"label": label, "path": rel(path), "note": note})


def pick_rows(rows: list[dict[str, str]], fields: list[str]) -> list[dict[str, str]]:
    return [{field: row.get(field, "") for field in fields} for row in rows]


def summarize_lancet_methods(rows: list[dict[str, str]], role_rank: dict[str, int]) -> list[dict[str, object]]:
    counter: Counter[tuple[str, str, str]] = Counter()
    for row in rows:
        counter[(row["role_id"], row["role_label"], row.get("method") or row.get("ets_method", ""))] += 1
    summary = [
        {
            "role_id": role_id,
            "role_label": role_label,
            "method": method,
            "province_n": count,
        }
        for (role_id, role_label, method), count in counter.items()
    ]
    summary.sort(key=lambda item: (role_rank.get(str(item["role_id"]), 99), str(item["method"])))
    return summary


def summarize_covariate_methods(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[row["variable"]][row["ets_method"]] += 1
    summary: list[dict[str, object]] = []
    for variable, methods in grouped.items():
        dominant_method, province_n = methods.most_common(1)[0]
        summary.append(
            {
                "variable": variable,
                "dominant_method": dominant_method,
                "province_n": province_n,
                "method_n": len(methods),
            }
        )
    summary.sort(key=lambda item: str(item["variable"]))
    return summary


def summarize_bias(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(row["scenario"], row["statistic"])].append(float(row["additive_bias"]))
    scenario_rank = {item["id"]: index for index, item in enumerate(SCENARIO_META)}
    stat_rank = {"median": 0, "p10": 1, "p90": 2}
    summary: list[dict[str, object]] = []
    for (scenario, statistic), values in grouped.items():
        summary.append(
            {
                "scenario": scenario,
                "statistic": statistic,
                "province_n": len(values),
                "mean_bias": sum(values) / len(values),
                "min_bias": min(values),
                "max_bias": max(values),
            }
        )
    summary.sort(
        key=lambda item: (
            scenario_rank.get(str(item["scenario"]), 99),
            stat_rank.get(str(item["statistic"]), 99),
        )
    )
    return summary


def enrich_province_rows(rows: list[dict[str, str]], mapping_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    province_map = {row["province"]: row for row in mapping_rows}
    enriched: list[dict[str, str]] = []
    for row in rows:
        province_info = province_map.get(row["Province"], {})
        enriched.append(
            {
                **row,
                "region": province_info.get("region", ""),
                "region_en": province_info.get("region_en", ""),
                "region_order": province_info.get("region_order", ""),
            }
        )
    return enriched


def build_assets() -> dict[str, object]:
    return {
        "lancet_ets": {
            "national": [
                {
                    "label": "Figure 5 entry role",
                    "path": "results/lancet_ets/figures/figure5_style_main.png",
                    "note": "以正文入口模型呈现的全国 Figure 5 风格总图；逐模型请结合 role 详解文件。",
                },
                {
                    "label": "National yearly entry role",
                    "path": "results/lancet_ets/figures/national_yearly_main_model.png",
                    "note": "正文入口模型的全国年序列轨迹图。",
                },
                {
                    "label": "Scenario delta 2050",
                    "path": "results/lancet_ets/figures/scenario_delta_2050_main_model.png",
                    "note": "正文入口模型在 2050 年各情景相对 baseline 的增量。",
                },
            ],
            "regional": [
                {
                    "label": "Regional figure grid",
                    "path": "results/lancet_ets/regional_figures/regional_figure5_grid.png",
                    "note": "七大区的轨迹小图矩阵。",
                },
                {
                    "label": "Regional 2050 heatmap",
                    "path": "results/lancet_ets/regional_figures/regional_delta_2050_heatmap.png",
                    "note": "七大区 2050 增量热图。",
                },
            ],
            "provincial": [
                {
                    "label": "Provincial future panel",
                    "path": "results/lancet_ets/provincial_figures/provincial_future_scenario_panel.png",
                    "note": "省级热图与全国均值轨迹。",
                },
                {
                    "label": "Dual-scenario delta figure",
                    "path": "results/lancet_ets/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585_delta.png",
                    "note": "默认的 ΔAMR 双情景比较图。",
                },
                {
                    "label": "Dual-scenario legacy absolute figure",
                    "path": "results/lancet_ets/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585.png",
                    "note": "保留的绝对 AMR 版本对照图。",
                },
            ],
        },
        "x_driven": {
            "national": [
                {
                    "label": "Figure 5 entry role",
                    "path": "results/x_driven/figures/figure5_style_main.png",
                    "note": "X-driven 版本中以正文入口模型呈现的全国总图。",
                },
                {
                    "label": "National yearly entry role",
                    "path": "results/x_driven/figures/national_yearly_main_model.png",
                    "note": "正文入口模型的全国年序列轨迹图。",
                },
                {
                    "label": "Scenario delta 2050",
                    "path": "results/x_driven/figures/scenario_delta_2050_main_model.png",
                    "note": "正文入口模型在 2050 年各情景相对 baseline 的增量。",
                },
            ],
            "regional": [
                {
                    "label": "Regional figure grid",
                    "path": "results/x_driven/regional_figures/regional_figure5_grid.png",
                    "note": "七大区的轨迹小图矩阵。",
                },
                {
                    "label": "Regional 2050 heatmap",
                    "path": "results/x_driven/regional_figures/regional_delta_2050_heatmap.png",
                    "note": "七大区 2050 增量热图。",
                },
            ],
            "provincial": [
                {
                    "label": "Provincial future panel",
                    "path": "results/x_driven/provincial_figures/provincial_future_scenario_panel.png",
                    "note": "省级热图与全国均值轨迹。",
                },
                {
                    "label": "Dual-scenario delta figure",
                    "path": "results/x_driven/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585_delta.png",
                    "note": "默认的 ΔAMR 双情景比较图。",
                },
                {
                    "label": "Dual-scenario legacy absolute figure",
                    "path": "results/x_driven/dual_scenario_figures/dual_scenario_compare_ssp119_vs_ssp585.png",
                    "note": "保留的绝对 AMR 版本对照图。",
                },
            ],
        },
    }


def build_file_catalog() -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []

    notes_items: list[dict[str, str]] = []
    maybe_add(notes_items, "README", "README.md", "目录、运行命令与推荐阅读顺序。")
    maybe_add(
        notes_items,
        "Framework note",
        "docs/Lancet未来情景预测框架说明.md",
        "Lancet 风格未来情景预测框架说明。",
    )
    maybe_add(
        notes_items,
        "Baseline note",
        "docs/两种baseline版本详解.md",
        "两种 baseline 版本差异的详细解释。",
    )
    maybe_add(notes_items, "Run metadata", "results/run_metadata.json", "这次构建的全局元数据和输出路径。")
    groups.append({"title": "项目说明", "items": notes_items})

    compare_items: list[dict[str, str]] = []
    maybe_add(compare_items, "national_yearly_compare.csv", "results/baseline_mode_compare/national_yearly_compare.csv", "全国年序列双 baseline 合并表。")
    maybe_add(compare_items, "scenario_summary_2050_compare.csv", "results/baseline_mode_compare/scenario_summary_2050_compare.csv", "2050 情景总表，包含全部 role。")
    maybe_add(compare_items, "model_role_2050_compare.csv", "results/baseline_mode_compare/model_role_2050_compare.csv", "12 个归档模型的 2050 双 baseline 对照总表。")
    maybe_add(compare_items, "main_model_2050_compare.csv", "results/baseline_mode_compare/main_model_2050_compare.csv", "正文入口主模型的 2050 对照表。")
    maybe_add(compare_items, "regional_summary_2050_compare.csv", "results/baseline_mode_compare/regional_summary_2050_compare.csv", "七大区结果对照表。")
    maybe_add(compare_items, "baseline_mode_comparison.md", "results/baseline_mode_compare/baseline_mode_comparison.md", "两种 baseline 的解释说明。")
    groups.append({"title": "双 baseline 对照", "items": compare_items})

    for mode in ("lancet_ets", "x_driven"):
        label = "Lancet ETS" if mode == "lancet_ets" else "X-driven"
        items: list[dict[str, str]] = []
        maybe_add(items, "projection_notes.md", f"results/{mode}/projection_notes.md", f"{label} 版本的结果说明。")
        maybe_add(items, "model_role_detail_summary.csv", f"results/{mode}/model_role_detail_summary.csv", f"{label} 版本的 12 模型摘要表。")
        maybe_add(items, "model_role_detailed_analysis.md", f"results/{mode}/model_role_detailed_analysis.md", f"{label} 版本的逐模型详细分析。")
        maybe_add(items, "national_yearly.csv", f"results/{mode}/projection_outputs/national_yearly.csv", "全国年序列结果。")
        maybe_add(items, "historical_national.csv", f"results/{mode}/projection_outputs/historical_national.csv", "历史全国序列。")
        maybe_add(items, "scenario_summary_2050.csv", f"results/{mode}/projection_outputs/scenario_summary_2050.csv", "2050 情景结果总表。")
        maybe_add(items, "province_projection_2050.csv", f"results/{mode}/projection_outputs/province_projection_2050.csv", "省级 2050 结果总表。")
        maybe_add(items, "future_scenario_projection_panel.csv", f"results/{mode}/projection_outputs/future_scenario_projection_panel.csv", "完整省级逐年未来情景面板。")
        maybe_add(items, "region_summary_2050.csv", f"results/{mode}/regional_outputs/region_summary_2050.csv", "七大区 2050 结果。")
        maybe_add(items, "regional_yearly.csv", f"results/{mode}/regional_outputs/regional_yearly.csv", "七大区逐年结果。")
        maybe_add(items, "province_order_2050.csv", f"results/{mode}/provincial_outputs/province_order_2050.csv", "省级排序输出。")
        maybe_add(items, "dual_scenario_compare_ssp119_vs_ssp585_delta_2050.csv", f"results/{mode}/dual_scenario_outputs/dual_scenario_compare_ssp119_vs_ssp585_delta_2050.csv", "默认双情景 2050 差值表。")
        maybe_add(items, "figure5_style_main.png", f"results/{mode}/figures/figure5_style_main.png", "全国主图。")
        maybe_add(items, "regional_figure5_grid.png", f"results/{mode}/regional_figures/regional_figure5_grid.png", "地区结果图。")
        maybe_add(items, "provincial_future_scenario_panel.png", f"results/{mode}/provincial_figures/provincial_future_scenario_panel.png", "省级未来情景图。")
        groups.append({"title": f"{label} 输出", "items": items})

    provenance_items: list[dict[str, str]] = []
    maybe_add(provenance_items, "selected_models_snapshot.csv", "results/model_screening/selected_models_snapshot.csv", "当前归档模型快照。")
    maybe_add(provenance_items, "future_projection_coefficients.csv", "results/model_screening/future_projection_coefficients.csv", "用于未来投影的协变量系数。")
    maybe_add(provenance_items, "covariate_ets_methods_snapshot.csv", "results/model_screening/covariate_ets_methods_snapshot.csv", "协变量 ETS 方法快照。")
    maybe_add(provenance_items, "rx1day_future_aligned.csv", "results/common_inputs/rx1day_future_aligned.csv", "偏差订正后的未来 rx1day 路径。")
    maybe_add(provenance_items, "rx1day_bias_correction.csv", "results/common_inputs/rx1day_bias_correction.csv", "历史与外部气候路径的 bias correction 表。")
    maybe_add(provenance_items, "province_to_region_7zones.csv", "data_processed/province_to_region_7zones.csv", "省份到七大区映射表。")
    groups.append({"title": "模型与输入来源", "items": provenance_items})

    return groups


def build_data() -> dict[str, object]:
    run_metadata = read_json(RESULTS_DIR / "run_metadata.json")
    selected_models_raw = read_csv(RESULTS_DIR / "model_screening" / "selected_models_snapshot.csv")
    selected_models = [row for row in selected_models_raw if row["role_id"] == "main_model"] + [
        row for row in selected_models_raw if row["role_id"] != "main_model"
    ]
    role_order = [row["role_id"] for row in selected_models]
    role_rank = {role_id: index for index, role_id in enumerate(role_order)}

    national_yearly_raw = read_csv(RESULTS_DIR / "baseline_mode_compare" / "national_yearly_compare.csv")
    national_yearly = pick_rows(
        [
            row
            for row in national_yearly_raw
            if row["statistic"] in {"baseline", "median"}
        ],
        [
            "baseline_mode",
            "role_id",
            "scenario_id",
            "scenario_label",
            "statistic",
            "Year",
            "scenario_pred_mean",
            "delta_vs_baseline_mean",
        ],
    )
    scenario_summary = pick_rows(
        read_csv(RESULTS_DIR / "baseline_mode_compare" / "scenario_summary_2050_compare.csv"),
        [
            "baseline_mode",
            "role_id",
            "role_label",
            "scheme_id",
            "scenario_id",
            "scenario_label",
            "statistic",
            "baseline_pred_mean",
            "scenario_pred_mean",
            "delta_vs_baseline_mean",
            "delta_vs_last_observed",
            "rx1day_scenario_mean",
        ],
    )
    regional_summary_raw = read_csv(RESULTS_DIR / "lancet_ets" / "regional_outputs" / "region_summary_2050.csv")
    regional_summary_raw += read_csv(RESULTS_DIR / "x_driven" / "regional_outputs" / "region_summary_2050.csv")
    regional_summary = pick_rows(
        [row for row in regional_summary_raw if row["statistic"] == "median"],
        [
            "baseline_mode",
            "role_id",
            "scenario_id",
            "region",
            "region_en",
            "region_order",
            "province_n",
            "baseline_pred_mean",
            "scenario_pred_mean",
            "delta_vs_baseline_mean",
            "rx1day_baseline_mean",
            "rx1day_scenario_mean",
        ],
    )

    province_mapping = read_csv(PROJECT_DIR / "data_processed" / "province_to_region_7zones.csv")
    province_rows_raw = read_csv(RESULTS_DIR / "lancet_ets" / "projection_outputs" / "province_projection_2050.csv")
    province_rows_raw += read_csv(RESULTS_DIR / "x_driven" / "projection_outputs" / "province_projection_2050.csv")
    province_rows = enrich_province_rows(
        pick_rows(
            [row for row in province_rows_raw if row["statistic"] == "median"],
            [
                "Province",
                "role_id",
                "scenario_id",
                "scenario_pred",
                "delta_vs_baseline",
                "rx1day_delta",
                "baseline_mode",
            ],
        ),
        province_mapping,
    )

    coefficients = read_csv(RESULTS_DIR / "model_screening" / "future_projection_coefficients.csv")
    lancet_methods = read_csv(RESULTS_DIR / "lancet_ets" / "model_screening" / "baseline_method_snapshot.csv")
    x_driven_methods = read_csv(RESULTS_DIR / "x_driven" / "model_screening" / "baseline_method_snapshot.csv")
    covariate_methods = read_csv(RESULTS_DIR / "model_screening" / "covariate_ets_methods_snapshot.csv")
    bias_rows = read_csv(RESULTS_DIR / "common_inputs" / "rx1day_bias_correction.csv")

    roles = [
        {
            "id": row["role_id"],
            "label": row["role_label"],
            "model_id": row["model_id"],
            "scheme_id": row["scheme_id"],
            "scheme_source": row["scheme_source"],
            "fe_label": row["fe_label"],
            "variables": [part.strip() for part in row["variables"].replace("\n", " ").split("|") if part.strip()],
        }
        for row in selected_models
    ]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_title": "未来情景分析",
        "outcome": run_metadata["outcome"],
        "outcome_label": run_metadata["outcome_label"],
        "outcome_note": run_metadata["outcome_note"],
        "start_year": run_metadata["start_year"],
        "end_year": run_metadata["end_year"],
        "province_count": 31,
        "region_count": 7,
        "mode_count": len(run_metadata["baseline_modes"]),
        "role_count": len(roles),
        "scenario_count": len([item for item in SCENARIO_META if item["family"] != "baseline"]),
        "uncertainty_paths": ["median", "p10", "p90"],
        "default_mode": "lancet_ets",
        "default_role": "main_model" if "main_model" in role_order else (role_order[0] if role_order else "main_model"),
        "default_scenario": "ssp585",
        "mode_meta": MODE_META,
        "scenario_meta": SCENARIO_META,
        "role_order": role_order,
        "roles": roles,
        "national_yearly": national_yearly,
        "scenario_summary_2050": scenario_summary,
        "regional_summary_2050": regional_summary,
        "province_projection_2050": province_rows,
        "coefficients": coefficients,
        "lancet_method_summary": summarize_lancet_methods(lancet_methods, role_rank),
        "x_driven_method_rows": x_driven_methods,
        "covariate_method_summary": summarize_covariate_methods(covariate_methods),
        "bias_summary": summarize_bias(bias_rows),
        "assets": build_assets(),
        "file_catalog": build_file_catalog(),
    }


def build_styles() -> str:
    return """  <style>
    :root {
      --bg: #eff4fb;
      --panel: rgba(255, 255, 255, 0.86);
      --ink: #10233a;
      --muted: #5b6f86;
      --line: rgba(16, 35, 58, 0.12);
      --primary: #1e40af;
      --primary-soft: rgba(30, 64, 175, 0.10);
      --secondary: #0f766e;
      --accent: #d97706;
      --shadow: 0 24px 70px rgba(15, 23, 42, 0.12);
      --radius-xl: 30px;
      --radius-lg: 22px;
      --radius-md: 16px;
      --mono: "Fira Code", Consolas, "SFMono-Regular", monospace;
      --sans: "Fira Sans", "Segoe UI", "Trebuchet MS", sans-serif;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: var(--sans);
      background:
        radial-gradient(circle at top left, rgba(30, 64, 175, 0.13), transparent 28%),
        radial-gradient(circle at top right, rgba(217, 119, 6, 0.10), transparent 26%),
        linear-gradient(180deg, #fbfdff 0%, #eef4fb 46%, #f8fafc 100%);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(16, 35, 58, 0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(16, 35, 58, 0.02) 1px, transparent 1px);
      background-size: 28px 28px;
      mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.6), transparent 85%);
    }
    .page {
      width: min(1400px, calc(100vw - 32px));
      margin: 20px auto 40px;
      display: grid;
      gap: 18px;
      position: relative;
    }
    .card, .section, .sticky-panel {
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.78);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }
    .hero {
      position: relative;
      overflow: hidden;
      border-radius: var(--radius-xl);
      background:
        radial-gradient(circle at right top, rgba(255, 255, 255, 0.15), transparent 32%),
        linear-gradient(135deg, rgba(11, 25, 46, 0.98), rgba(26, 70, 149, 0.95));
      color: #f7fbff;
      padding: 34px;
      display: grid;
      gap: 24px;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -40px -70px auto;
      width: 240px;
      height: 240px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(217, 119, 6, 0.32), transparent 70%);
    }
    .hero-grid {
      display: grid;
      grid-template-columns: 1.6fr 1fr;
      gap: 24px;
      align-items: start;
      position: relative;
      z-index: 1;
    }
    .eyebrow {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      opacity: 0.78;
      margin-bottom: 14px;
    }
    h1, h2, h3 {
      margin: 0;
      line-height: 1.06;
      letter-spacing: -0.02em;
    }
    h1 { font-size: clamp(34px, 4vw, 58px); max-width: 12ch; }
    h2 { font-size: clamp(24px, 2.6vw, 34px); }
    h3 { font-size: 18px; }
    p {
      margin: 0;
      line-height: 1.7;
      color: var(--muted);
      font-size: 15px;
    }
    .hero p { color: rgba(247, 251, 255, 0.90); max-width: 64ch; }
    .tag-row, .anchor-nav, .stat-grid, .gallery-grid, .split-grid, .two-col, .three-col, .steps {
      display: grid;
      gap: 14px;
    }
    .tag-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }
    .tag {
      display: inline-flex;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.10);
      border: 1px solid rgba(255, 255, 255, 0.14);
      color: #f7fbff;
      font-size: 13px;
      white-space: nowrap;
    }
    .hero-side {
      display: grid;
      gap: 12px;
    }
    .hero-note {
      padding: 18px;
      border-radius: var(--radius-lg);
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.12);
      display: grid;
      gap: 8px;
    }
    .hero-note strong { font-size: 14px; }
    .stat-grid {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 6px;
    }
    .stat {
      padding: 18px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.12);
      display: grid;
      gap: 6px;
      min-height: 132px;
    }
    .stat .k {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: rgba(247, 251, 255, 0.72);
    }
    .stat .v {
      font-size: clamp(26px, 3vw, 40px);
      font-weight: 800;
      line-height: 1;
      color: #ffffff;
      overflow-wrap: anywhere;
    }
    .stat .h {
      font-size: 13px;
      line-height: 1.6;
      color: rgba(247, 251, 255, 0.84);
    }
    .anchor-nav {
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    }
    .anchor-link, .link-btn, .choice button {
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease, background 180ms ease, color 180ms ease;
    }
    .anchor-link {
      display: inline-flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--line);
      color: var(--ink);
      text-decoration: none;
      font-weight: 700;
    }
    .anchor-link:hover,
    .anchor-link:focus-visible,
    .choice button:hover,
    .choice button:focus-visible,
    .link-btn:hover,
    .link-btn:focus-visible,
    details summary:hover,
    details summary:focus-visible {
      transform: translateY(-1px);
      border-color: rgba(30, 64, 175, 0.24);
      box-shadow: 0 10px 28px rgba(30, 64, 175, 0.10);
      outline: none;
    }
    .section {
      border-radius: var(--radius-xl);
      padding: 28px;
      display: grid;
      gap: 20px;
    }
    .section-head {
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 20px;
      align-items: end;
    }
    .section-head p { max-width: 64ch; }
    .sticky-panel {
      position: sticky;
      top: 12px;
      z-index: 8;
      border-radius: 24px;
      padding: 18px;
      display: grid;
      gap: 14px;
    }
    .control-grid {
      display: grid;
      grid-template-columns: 1.4fr 1.4fr 1fr 1fr;
      gap: 14px;
      align-items: start;
    }
    .control-block {
      display: grid;
      gap: 8px;
    }
    .control-label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
    }
    .choice {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .choice button {
      appearance: none;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.84);
      color: var(--ink);
      padding: 10px 14px;
      border-radius: 999px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .choice button.active {
      background: linear-gradient(135deg, var(--primary), #15368d);
      color: #ffffff;
      border-color: transparent;
      box-shadow: 0 12px 24px rgba(30, 64, 175, 0.20);
    }
    .choice button.subtle-active {
      background: linear-gradient(135deg, var(--secondary), #0b5f59);
      color: #ffffff;
      border-color: transparent;
    }
    .narrative {
      padding: 18px;
      border-radius: 20px;
      background: linear-gradient(135deg, rgba(30, 64, 175, 0.08), rgba(15, 118, 110, 0.06));
      border: 1px solid rgba(30, 64, 175, 0.10);
      color: var(--ink);
      line-height: 1.8;
    }
    .narrative strong { color: var(--primary); }
    .split-grid { grid-template-columns: 1.18fr 0.82fr; }
    .two-col { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .three-col { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .info-card, .metric-card, .panel-card, .chart-card, .gallery-card, .table-card, .model-card, .method-card {
      border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.74);
      padding: 20px;
      display: grid;
      gap: 12px;
    }
    .metric-card { gap: 8px; min-height: 148px; }
    .metric-card .label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
    }
    .metric-card .value {
      font-size: clamp(24px, 3vw, 38px);
      line-height: 1.05;
      font-weight: 800;
    }
    .metric-card .sub { font-size: 14px; color: var(--muted); line-height: 1.65; }
    .mode-card { position: relative; padding-top: 22px; }
    .mode-card::before {
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      height: 4px;
      border-radius: 22px 22px 0 0;
      background: linear-gradient(90deg, var(--primary), var(--accent));
    }
    .mode-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      width: fit-content;
      padding: 7px 10px;
      border-radius: 999px;
      background: var(--primary-soft);
      color: var(--primary);
      font-size: 12px;
      font-weight: 700;
    }
    .steps {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .step {
      padding: 18px;
      border-radius: 18px;
      background: rgba(16, 35, 58, 0.04);
      border: 1px solid var(--line);
      display: grid;
      gap: 8px;
    }
    .step .num {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      display: inline-grid;
      place-items: center;
      background: linear-gradient(135deg, var(--primary), #15368d);
      color: #fff;
      font-weight: 800;
      font-size: 14px;
    }
    .formula {
      padding: 16px;
      border-radius: 18px;
      background: rgba(16, 35, 58, 0.04);
      border: 1px solid var(--line);
      font-family: var(--mono);
      font-size: 13px;
      line-height: 1.7;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }
    .chart-card svg {
      width: 100%;
      height: auto;
      display: block;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(248, 251, 255, 0.86), rgba(240, 245, 252, 0.9));
      border: 1px solid rgba(16, 35, 58, 0.06);
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(16, 35, 58, 0.04);
      border: 1px solid var(--line);
      font-size: 13px;
    }
    .legend-swatch {
      width: 11px;
      height: 11px;
      border-radius: 50%;
      flex: 0 0 auto;
    }
    .table-wrap {
      overflow-x: auto;
      border-radius: 16px;
      border: 1px solid var(--line);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 680px;
      background: rgba(255, 255, 255, 0.72);
    }
    th, td {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
      line-height: 1.55;
    }
    thead th {
      background: rgba(16, 35, 58, 0.05);
      color: var(--ink);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    tbody tr:hover { background: rgba(30, 64, 175, 0.04); }
    .row-highlight { background: rgba(30, 64, 175, 0.06); }
    .delta-up { color: #b45309; font-weight: 700; }
    .delta-down { color: var(--secondary); font-weight: 700; }
    .code {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 10px;
      background: rgba(16, 35, 58, 0.05);
      border: 1px solid rgba(16, 35, 58, 0.08);
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.6;
      overflow-wrap: anywhere;
    }
    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(16, 35, 58, 0.05);
      border: 1px solid var(--line);
      font-size: 13px;
      line-height: 1.4;
    }
    .model-card.active {
      border-color: rgba(30, 64, 175, 0.24);
      box-shadow: 0 18px 36px rgba(30, 64, 175, 0.10);
    }
    .coeff-row {
      display: grid;
      grid-template-columns: minmax(0, 180px) 1fr auto;
      gap: 14px;
      align-items: center;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
    }
    .coeff-row:last-child { border-bottom: none; }
    .coeff-track {
      position: relative;
      height: 10px;
      border-radius: 999px;
      background: rgba(16, 35, 58, 0.08);
      overflow: hidden;
    }
    .coeff-track::before {
      content: "";
      position: absolute;
      left: 50%;
      top: 0;
      bottom: 0;
      width: 1px;
      background: rgba(16, 35, 58, 0.18);
    }
    .coeff-bar {
      position: absolute;
      top: 0;
      bottom: 0;
      border-radius: 999px;
    }
    .coeff-pos { background: linear-gradient(90deg, rgba(217, 119, 6, 0.72), rgba(217, 119, 6, 1)); }
    .coeff-neg { background: linear-gradient(90deg, rgba(15, 118, 110, 1), rgba(15, 118, 110, 0.72)); }
    .gallery-grid {
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }
    .gallery-card {
      overflow: hidden;
      padding: 0;
      gap: 0;
    }
    .gallery-card img {
      width: 100%;
      height: 220px;
      object-fit: cover;
      display: block;
      background: #edf2f8;
      border-bottom: 1px solid var(--line);
    }
    .gallery-body {
      padding: 16px;
      display: grid;
      gap: 10px;
    }
    .link-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 11px 14px;
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.84);
      border: 1px solid var(--line);
    }
    .link-btn.primary {
      background: linear-gradient(135deg, var(--primary), #15368d);
      color: #ffffff;
      border-color: transparent;
    }
    .link-btn.ghost {
      background: var(--primary-soft);
      color: var(--primary);
      border-color: rgba(30, 64, 175, 0.12);
    }
    .callout {
      padding: 18px;
      border-radius: 18px;
      background: linear-gradient(135deg, rgba(217, 119, 6, 0.10), rgba(30, 64, 175, 0.06));
      border: 1px solid rgba(217, 119, 6, 0.12);
    }
    details {
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      overflow: hidden;
    }
    details + details { margin-top: 10px; }
    details summary {
      list-style: none;
      cursor: pointer;
      padding: 16px 18px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      transition: background 180ms ease;
    }
    details summary::-webkit-details-marker { display: none; }
    details[open] summary { background: rgba(16, 35, 58, 0.04); }
    .detail-body {
      padding: 0 18px 18px;
      display: grid;
      gap: 12px;
    }
    .command {
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(14, 25, 47, 0.94);
      color: #f7fbff;
      font-family: var(--mono);
      font-size: 13px;
      line-height: 1.65;
      overflow-x: auto;
    }
    .footer {
      padding: 18px 4px 6px;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
    }
    .reveal { animation: rise 480ms ease both; }
    @keyframes rise {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      .reveal, .anchor-link, .choice button, .link-btn, details summary { animation: none; transition: none; }
    }
    @media (max-width: 1120px) {
      .hero-grid,
      .section-head,
      .split-grid,
      .control-grid,
      .two-col,
      .three-col,
      .kpi-grid,
      .steps,
      .stat-grid {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 780px) {
      .page {
        width: calc(100vw - 12px);
        margin: 8px auto 18px;
      }
      .hero, .section { padding: 18px; }
      .stat { min-height: unset; }
      .gallery-card img { height: 180px; }
      .coeff-row { grid-template-columns: 1fr; }
    }
  </style>"""


def build_body() -> str:
    return (
        build_body_intro()
        + build_body_overview()
        + build_body_framework()
        + build_body_results()
        + build_body_provenance()
        + build_body_catalog()
        + build_body_outro()
    )


def build_body_intro() -> str:
    return """  <div class="page">
    <header class="hero reveal">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">6 未来情景分析</div>
          <h1>把两种 baseline、四类模型角色和全国到省级结果放在同一页里读清楚。</h1>
          <p>
            这页不是单纯把所有 CSV 堆出来，而是按“方法框架 → baseline 差异 → 全国/地区/省级结果 → 模型与输入来源 → 文件入口”
            重新组织。你可以直接切换 baseline mode、role 和情景，快速判断差异究竟来自 baseline 设定、协变量路径，还是模型角色本身。
          </p>
          <div class="tag-row">
            <span class="tag">AMR_AGG_RAW</span>
            <span class="tag">2024-2050</span>
            <span class="tag">31 Provinces</span>
            <span class="tag">7 Regions</span>
            <span class="tag">5 SSP + 3 uncertainty paths</span>
          </div>
        </div>
        <div class="hero-side">
          <div class="hero-note">
            <strong>这页的核心读法</strong>
            <p>先看全国 baseline 水平，再看 2050 情景增量；如果两种 baseline 的增量几乎一致而水平不同，说明真正主导差异的是 baseline 的生成方式，而不是 R1xday 情景本身。</p>
          </div>
          <div class="hero-note">
            <strong>当前范围</strong>
            <p>当前只有 <span class="code">R1xday</span> 真正接入了未来情景路径；抗菌药物使用、供水/卫生、经济与卫生投入等协变量仍沿 baseline 路径延续。</p>
          </div>
          <div class="hero-note">
            <strong>默认双情景图已更新</strong>
            <p>底部双情景对照默认显示 <span class="code">ΔAMR vs baseline</span>，并把右下哑铃图重心放在 <span class="code">SSP1-1.9 = 0</span>。</p>
          </div>
        </div>
      </div>
      <div class="stat-grid" id="heroStats"></div>
    </header>

    <nav class="anchor-nav reveal">
      <a class="anchor-link" href="#overview"><span>总览判断</span><span>01</span></a>
      <a class="anchor-link" href="#framework"><span>框架与 baseline</span><span>02</span></a>
      <a class="anchor-link" href="#national"><span>全国结果</span><span>03</span></a>
      <a class="anchor-link" href="#regional"><span>地区结果</span><span>04</span></a>
      <a class="anchor-link" href="#provincial"><span>省级结果</span><span>05</span></a>
      <a class="anchor-link" href="#provenance"><span>模型与来源</span><span>06</span></a>
      <a class="anchor-link" href="#catalog"><span>文件入口</span><span>07</span></a>
    </nav>

    <section class="sticky-panel reveal">
      <div class="control-grid">
        <div class="control-block">
          <div class="control-label">Baseline Mode</div>
          <div class="choice" id="modeControls"></div>
        </div>
        <div class="control-block">
          <div class="control-label">Model Role</div>
          <div class="choice" id="roleControls"></div>
        </div>
        <div class="control-block">
          <div class="control-label">Focus Scenario</div>
          <div class="choice" id="scenarioControls"></div>
        </div>
        <div class="control-block">
          <div class="control-label">National Chart</div>
          <div class="choice" id="metricControls"></div>
        </div>
      </div>
      <div class="narrative" id="stateNarrative"></div>
    </section>
"""


def build_body_overview() -> str:
    return """    <section class="section reveal" id="overview">
      <div class="section-head">
        <div>
          <div class="eyebrow">Overview</div>
          <h2>先抓住现在这版结果最重要的三个判断。</h2>
        </div>
        <p>
          这一部分专门回答“当前选中的 baseline、role、情景到底意味着什么”。它不会代替完整结果表，但能帮你先定位：全国水平是多少、情景抬升多少、地区和省份哪个地方反应最强。
        </p>
      </div>
      <div class="kpi-grid" id="overviewCards"></div>
      <div class="split-grid">
        <div class="info-card">
          <div class="eyebrow">Cross-Baseline Compare</div>
          <h3>相同 role、相同情景下，两种 baseline 的差异</h3>
          <p>这一块专门用来判断你现在看到的差异到底来自 baseline 设定，还是来自情景增量。当前实现只让 <span class="code">R1xday</span> 随 SSP 变化，所以两种 baseline 的增量通常更接近，差异更多来自 baseline 水平本身。</p>
          <div class="three-col" id="baselineCompareCards"></div>
        </div>
        <div class="info-card">
          <div class="eyebrow">Role Sensitivity</div>
          <h3>同一 baseline 下，不同 role 的稳健性对照</h3>
          <p>role 切换并不是简单换个名字，而是换一套历史系数和固定效应配置。这里放在一起看，有助于判断主结论是否只依赖某一个模型设定。</p>
          <div id="roleSensitivity"></div>
        </div>
      </div>
    </section>
"""


def build_body_framework() -> str:
    return """    <section class="section reveal" id="framework">
      <div class="section-head">
        <div>
          <div class="eyebrow">Framework</div>
          <h2>这套前向情景预测不是“把回归方程往前延长”那么简单。</h2>
        </div>
        <p>
          仓库里真正实现的是“历史 panel 系数 + future baseline + scenario adjustment”的组合框架。也就是说，先决定未来 baseline 怎么走，再把未来情景路径相对 baseline 的偏离折算成 AMR 的增量。
        </p>
      </div>
      <div class="steps">
        <div class="step">
          <div class="num">1</div>
          <h3>历史面板识别</h3>
          <p>从统一的 12 模型归档里读取原始主线 4 个角色和严筛扩展 8 个角色，保留协变量标准化口径与历史系数。</p>
        </div>
        <div class="step">
          <div class="num">2</div>
          <h3>生成 baseline</h3>
          <p><strong>Lancet ETS</strong> 用 ETS 延续 AMR 自身；<strong>X-driven</strong> 用未来协变量路径先重建 baseline。</p>
        </div>
        <div class="step">
          <div class="num">3</div>
          <h3>叠加 scenario delta</h3>
          <p>当前只有 <span class="code">R1xday</span> 会随着 SSP 情景真实变化，其余协变量沿 baseline 路径延伸。</p>
        </div>
        <div class="step">
          <div class="num">4</div>
          <h3>先省级后全国</h3>
          <p>先算每个省的未来 AMR，再取省级算术平均形成全国结果，而不是先做全国气候均值再代回模型。</p>
        </div>
      </div>
      <div class="two-col">
        <div class="mode-card info-card">
          <span class="mode-badge">Lancet ETS</span>
          <h3>结果变量自身趋势先走</h3>
          <p>如果你更在意“baseline scenario continued at current rates, as estimated by ETS models”这句话的实现口径，就看这一版。</p>
          <div class="formula">Y_it = α_i + λ_t + Σ β_k Z_itk + ε_it
Y^base_it = ETS(Y_i, historical series)
Δ^scenario_it = Σ β_k × (Z^scenario_itk - Z^base_itk)
Y^scenario_it = Y^base_it + Δ^scenario_it</div>
        </div>
        <div class="mode-card info-card">
          <span class="mode-badge">X-driven</span>
          <h3>协变量路径先走，再重建 AMR</h3>
          <p>如果你更关心未来气候路径怎样拉开情景差距，而不希望 AMR 历史惯性把未来结果锁死，就更适合看这一版。</p>
          <div class="formula">Y_it = α_i + λ_t + Σ β_k Z_itk + ε_it
Y^base_it = α_i* + λ_t* + Σ β_k Z^base_itk
Y^scenario_it = α_i* + λ_t* + Σ β_k Z^scenario_itk
If only R1xday varies:
Y^scenario_it = Y^base_it + β_R × (R1xday^scenario_it - R1xday^base_it)</div>
        </div>
      </div>
      <div class="callout">
        <strong>为什么当前两种 baseline 的情景增量常常非常接近？</strong>
        <p>
          因为现在真正被未来 SSP 路径替换的外部变量只有 <span class="code">R1xday</span>。只要两种 baseline 使用的是同一套历史 <span class="code">β_R</span>
          和同一套未来 <span class="code">R1xday</span> 情景差值，那么情景相对 baseline 的增量就会非常接近，真正明显分开的往往是 baseline 水平本身。
        </p>
      </div>
    </section>
"""


def build_body_results() -> str:
    return """    <section class="section reveal" id="national">
      <div class="section-head">
        <div>
          <div class="eyebrow">National</div>
          <h2>全国结果先看轨迹，再看 2050 情景表。</h2>
        </div>
        <p>
          图里默认展示当前 baseline + role 下的全部情景轨迹；下表则把 2050 年的 baseline、scenario prediction、delta 和相对最后观测值变化放在一起，适合直接写结果段落。
        </p>
      </div>
      <div class="split-grid">
        <div class="chart-card">
          <div class="eyebrow">Trajectory</div>
          <h3>全国年序列</h3>
          <div class="legend" id="nationalLegend"></div>
          <div id="nationalChart"></div>
        </div>
        <div class="panel-card">
          <div class="eyebrow">Figures</div>
          <h3>当前 baseline 的主模型静态图</h3>
          <p>这里保留的是脚本已导出的正文入口主模型 PNG，方便你和页面里的交互式读法互相核对。它们不会随着上面的 <span class="code">Model Role</span> 一起切换；真正按 role 变化的是左侧交互图和下方结果表。</p>
          <div class="gallery-grid" id="nationalFigures"></div>
        </div>
      </div>
      <div class="table-card">
        <div class="eyebrow">2050 Summary</div>
        <h3>全国 2050 情景表</h3>
        <p>表里同时放了中位数结果和不确定性区间；如果你只需要主结果，先看 <span class="code">median</span> 行即可。</p>
        <div class="table-wrap" id="scenarioTable"></div>
      </div>
    </section>

    <section class="section reveal" id="regional">
      <div class="section-head">
        <div>
          <div class="eyebrow">Regional</div>
          <h2>地区结果帮助你判断“全国平均”被哪些地带推着走。</h2>
        </div>
        <p>
          七大区结果的意义不在于替代省级，而在于把空间结构先压缩成可读层级。正值表示在该情景下相对 baseline 抬升，负值表示相对 baseline 下降。
        </p>
      </div>
      <div class="split-grid">
        <div class="chart-card">
          <div class="eyebrow">Regional Delta</div>
          <h3>七大区 2050 增量</h3>
          <div id="regionalChart"></div>
        </div>
        <div class="panel-card">
          <div class="eyebrow">Figures</div>
          <h3>地区主模型图件</h3>
          <p>这两张 PNG 同样对应正文入口主模型，用来快速核对空间结构；如果你切换了 <span class="code">Model Role</span>，请优先以上面的交互条形图和下表为准。</p>
          <div class="gallery-grid" id="regionalFigures"></div>
        </div>
      </div>
      <div class="table-card">
        <div class="eyebrow">Region Table</div>
        <h3>七大区 2050 结果表</h3>
        <div class="table-wrap" id="regionalTable"></div>
      </div>
    </section>

    <section class="section reveal" id="provincial">
      <div class="section-head">
        <div>
          <div class="eyebrow">Provincial</div>
          <h2>省级层面最适合看两个问题：谁对当前情景最敏感，谁对情景分歧最敏感。</h2>
        </div>
        <p>
          左右两张表分别是当前选中情景下的增量最高省份和最低省份；下方的双情景 gap 表专门回答“到 2050 年，SSP5-8.5 和 SSP1-1.9 哪些省份差得最大”。
        </p>
      </div>
      <div class="two-col">
        <div class="table-card">
          <div class="eyebrow">Top Positive</div>
          <h3>当前情景下增量最高的省份</h3>
          <div class="table-wrap" id="provincePositive"></div>
        </div>
        <div class="table-card">
          <div class="eyebrow">Top Negative</div>
          <h3>当前情景下增量最低的省份</h3>
          <div class="table-wrap" id="provinceNegative"></div>
        </div>
      </div>
      <div class="table-card">
        <div class="eyebrow">Dual Scenario Gap</div>
        <h3>SSP5-8.5 与 SSP1-1.9 的省级 gap</h3>
        <p>这里固定比较默认双情景对；gap 越大，说明该省对未来气候路径分化越敏感。</p>
        <div class="table-wrap" id="dualScenarioTable"></div>
      </div>
      <div class="panel-card">
        <div class="eyebrow">Figures</div>
        <h3>省级主模型图件</h3>
        <p>这里展示的也是正文入口主模型静态图。不同 role 的省级差异请以上面的排序表和双情景 gap 表为准。</p>
        <div class="gallery-grid" id="provincialFigures"></div>
      </div>
    </section>
"""


def build_body_provenance() -> str:
    return """    <section class="section reveal" id="provenance">
      <div class="section-head">
        <div>
          <div class="eyebrow">Provenance</div>
          <h2>把这页背后的模型角色、系数和输入来源都摆出来。</h2>
        </div>
        <p>
          结果页面如果只给图不给模型来源，很难写方法和讨论。这一节把 12 个归档模型角色的变量组合、未来投影用到的系数、baseline 的 ETS 方法快照以及 rx1day bias correction 都并排放在一起。
        </p>
      </div>
      <div class="two-col">
        <div class="panel-card">
          <div class="eyebrow">Selected Models</div>
          <h3>12 个 role 的模型快照</h3>
          <div id="modelCards"></div>
        </div>
        <div class="panel-card">
          <div class="eyebrow">Projection Coefficients</div>
          <h3>当前 role 的历史系数</h3>
          <p>条形长度表示系数绝对值，方向表示正负。这里只显示未来投影阶段真正拿来做 adjustment 的协变量系数。</p>
          <div id="coefficientBars"></div>
        </div>
      </div>
      <div class="three-col">
        <div class="method-card">
          <div class="eyebrow">Lancet ETS Snapshot</div>
          <h3>Outcome baseline 方法</h3>
          <p>这张表是 Lancet ETS 版对 outcome 自身做 ETS 延续时的快照计数。</p>
          <div class="table-wrap" id="lancetMethodTable"></div>
        </div>
        <div class="method-card">
          <div class="eyebrow">X-driven Snapshot</div>
          <h3>X-driven baseline 组件</h3>
          <p>这张表显示 X-driven 版在整体水平项和时间项上的 baseline 处理方式。</p>
          <div class="table-wrap" id="xDrivenMethodTable"></div>
        </div>
        <div class="method-card">
          <div class="eyebrow">Covariate ETS</div>
          <h3>协变量 baseline 方法</h3>
          <p>主导方法与覆盖省份数，帮助你快速确认当前协变量 baseline 是如何延伸的。</p>
          <div class="table-wrap" id="covariateMethodTable"></div>
        </div>
      </div>
      <div class="two-col">
        <div class="method-card">
          <div class="eyebrow">Bias Correction</div>
          <h3>rx1day 外部路径对齐概览</h3>
          <p>外部气候路径与历史观测不是同一口径，所以这里单独给出 bias correction 的均值、最小值和最大值概览。</p>
          <div class="table-wrap" id="biasTable"></div>
        </div>
        <div class="method-card">
          <div class="eyebrow">Read This With</div>
          <h3>写作时最建议并排看的材料</h3>
          <p>方法部分建议和 framework / baseline docs 一起读；结果部分建议全国总表、逐模型总表、地区总表、省级双情景图件一起用，避免只盯着一条全国均值曲线或单一 role。</p>
          <div class="chip-row">
            <span class="chip">Framework note</span>
            <span class="chip">Baseline compare note</span>
            <span class="chip">scenario_summary_2050_compare.csv</span>
            <span class="chip">model_role_2050_compare.csv</span>
            <span class="chip">model_role_detailed_analysis.md</span>
            <span class="chip">region_summary_2050_compare.csv</span>
            <span class="chip">dual_scenario_compare_ssp119_vs_ssp585_delta.png</span>
          </div>
        </div>
      </div>
    </section>
"""


def build_body_catalog() -> str:
    return """    <section class="section reveal" id="catalog">
      <div class="section-head">
        <div>
          <div class="eyebrow">Catalog</div>
          <h2>所有关键文件入口都在这里，不用再回目录里翻。</h2>
        </div>
        <p>
          这一节按“说明、双 baseline 对照、两套主结果、模型与输入来源”分组。每组都只放当前真正有用的核心文件，避免把归档和旧路径再次混进来。
        </p>
      </div>
      <div id="fileCatalog"></div>
      <div class="two-col">
        <div class="panel-card">
          <div class="eyebrow">Recommended Commands</div>
          <h3>最常用运行命令</h3>
          <div class="command">python -X utf8 ".\\6 未来情景分析\\scripts\\run_future_scenario_projection.py"
python -X utf8 ".\\6 未来情景分析\\scripts\\run_regional_future_figure5.py"
python -X utf8 ".\\6 未来情景分析\\scripts\\run_provincial_future_figure.py"
python -X utf8 ".\\6 未来情景分析\\scripts\\run_dual_scenario_compare_figure.py"</div>
        </div>
        <div class="panel-card">
          <div class="eyebrow">Output Logic</div>
          <h3>当前主线目录约定</h3>
          <p><span class="code">results/</span> 只保留当前主线结果；旧结构和归档统一放到 <span class="code">bakeup/</span>。如果你需要写当前分析，请优先使用这页和它引用的 <span class="code">results/</span> 路径。</p>
          <div class="chip-row">
            <span class="chip">results/ 是当前主线</span>
            <span class="chip">不再使用 results/AMR_AGG_RAW/ 旧嵌套结构</span>
            <span class="chip">bakeup/ 只作归档</span>
          </div>
        </div>
      </div>
    </section>
"""


def build_body_outro() -> str:
    return """    <div class="footer">Generated at __GENERATED_AT__ · Source: 6 未来情景分析</div>
  </div>"""


def build_scripts(data_json: str) -> str:
    return (
        build_script_intro(data_json)
        + build_script_helpers()
        + build_script_renderers()
        + build_script_bootstrap()
    )


def build_script_intro(data_json: str) -> str:
    return f"""  <script>
    const DATA = {data_json};

    const scenarioColors = {{
      baseline_ets: "#1e40af",
      ssp119: "#0f766e",
      ssp126: "#0891b2",
      ssp245: "#4f46e5",
      ssp370: "#d97706",
      ssp585: "#b91c1c"
    }};

    const metricMeta = [
      {{ id: "scenario_pred_mean", label: "Trajectory" }},
      {{ id: "delta_vs_baseline_mean", label: "Δ vs Baseline" }}
    ];

    const state = {{
      mode: DATA.default_mode,
      role: DATA.default_role,
      scenario: DATA.default_scenario,
      nationalMetric: "scenario_pred_mean"
    }};

    const roleMap = Object.fromEntries(DATA.roles.map(item => [item.id, item]));
    const modeMap = Object.fromEntries(DATA.mode_meta.map(item => [item.id, item]));
    const scenarioMap = Object.fromEntries(DATA.scenario_meta.map(item => [item.id, item]));
"""


def build_script_helpers() -> str:
    return """    function num(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function fmt(value, digits = 2) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return "—";
      return parsed.toLocaleString("zh-CN", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      });
    }

    function fmtSigned(value, digits = 2) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return "—";
      const prefix = parsed > 0 ? "+" : "";
      return prefix + fmt(parsed, digits);
    }

    function el(id) {
      return document.getElementById(id);
    }

    function renderChoices(id, items, activeValue, onChange, activeClass = "active") {
      el(id).innerHTML = items.map(item => `
        <button
          type="button"
          class="${item.id === activeValue ? activeClass : ""}"
          data-value="${escapeHtml(item.id)}"
        >${escapeHtml(item.label)}</button>
      `).join("");
      el(id).querySelectorAll("button").forEach(button => {
        button.addEventListener("click", () => onChange(button.dataset.value || ""));
      });
    }

    function scenarioRows(mode = state.mode, role = state.role) {
      return DATA.scenario_summary_2050.filter(row => row.baseline_mode === mode && row.role_id === role);
    }

    function summaryRow(mode, role, scenarioId, statistic) {
      return scenarioRows(mode, role).find(
        row => row.scenario_id === scenarioId && row.statistic === statistic
      ) || null;
    }

    function yearlyRows(mode = state.mode, role = state.role) {
      return DATA.national_yearly.filter(row => row.baseline_mode === mode && row.role_id === role);
    }

    function currentScenarioMedian() {
      return summaryRow(state.mode, state.role, state.scenario, "median");
    }

    function baselineRow(mode = state.mode, role = state.role) {
      return summaryRow(mode, role, "baseline_ets", "baseline");
    }

    function otherMode(mode) {
      return mode === "lancet_ets" ? "x_driven" : "lancet_ets";
    }

    function regionRowsForState() {
      return DATA.regional_summary_2050
        .filter(
          row =>
            row.baseline_mode === state.mode &&
            row.role_id === state.role &&
            row.scenario_id === state.scenario &&
            row.statistic === "median"
        )
        .sort((a, b) => num(a.region_order) - num(b.region_order));
    }

    function provinceRowsForState() {
      return DATA.province_projection_2050
        .filter(
          row =>
            row.baseline_mode === state.mode &&
            row.role_id === state.role &&
            row.scenario_id === state.scenario &&
            row.statistic === "median"
        )
        .sort((a, b) => num(b.delta_vs_baseline) - num(a.delta_vs_baseline));
    }

    function dualGapRowsForState() {
      const source = DATA.province_projection_2050.filter(
        row =>
          row.baseline_mode === state.mode &&
          row.role_id === state.role &&
          row.statistic === "median" &&
          (row.scenario_id === "ssp119" || row.scenario_id === "ssp585")
      );
      const ssp119 = new Map(source.filter(row => row.scenario_id === "ssp119").map(row => [row.Province, row]));
      const ssp585 = new Map(source.filter(row => row.scenario_id === "ssp585").map(row => [row.Province, row]));
      const rows = [];
      ssp585.forEach((highRow, province) => {
        const lowRow = ssp119.get(province);
        if (!lowRow) return;
        const gap = num(highRow.delta_vs_baseline) - num(lowRow.delta_vs_baseline);
        rows.push({
          Province: province,
          region: highRow.region,
          ssp119: num(lowRow.delta_vs_baseline),
          ssp585: num(highRow.delta_vs_baseline),
          scenario_gap: gap,
          scenario_gap_abs: Math.abs(gap)
        });
      });
      rows.sort((a, b) => b.scenario_gap_abs - a.scenario_gap_abs);
      return rows;
    }

    function roleSensitivityRows() {
      return DATA.role_order
        .map(roleId => summaryRow(state.mode, roleId, state.scenario, "median"))
        .filter(Boolean);
    }

    function chartSeries() {
      return DATA.scenario_meta
        .map(meta => {
          const statistic = meta.id === "baseline_ets" ? "baseline" : "median";
          const values = yearlyRows()
            .filter(row => row.scenario_id === meta.id && row.statistic === statistic)
            .sort((a, b) => num(a.Year) - num(b.Year))
            .map(row => ({
              x: num(row.Year),
              y: num(row[state.nationalMetric]),
              label: row.scenario_label
            }))
            .filter(point => point.x !== null && point.y !== null);
          if (!values.length) return null;
          return {
            id: meta.id,
            label: meta.short_label,
            color: scenarioColors[meta.id] || "#1e40af",
            values
          };
        })
        .filter(Boolean);
    }

    function makeLineChart(series) {
      if (!series.length) return "<p>暂无数据。</p>";
      const width = 980;
      const height = 360;
      const margin = { top: 22, right: 88, bottom: 42, left: 52 };
      const xs = series.flatMap(item => item.values.map(point => point.x));
      const ys = series.flatMap(item => item.values.map(point => point.y));
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      let minY = Math.min(...ys);
      let maxY = Math.max(...ys);
      if (minY === maxY) {
        minY -= 1;
        maxY += 1;
      }
      const padding = (maxY - minY) * 0.12;
      minY -= padding;
      maxY += padding;

      const xScale = value =>
        margin.left + ((value - minX) / Math.max(maxX - minX, 1)) * (width - margin.left - margin.right);
      const yScale = value =>
        height - margin.bottom - ((value - minY) / Math.max(maxY - minY, 1)) * (height - margin.top - margin.bottom);

      const ticks = 5;
      const yTicks = Array.from({ length: ticks + 1 }, (_, index) => minY + ((maxY - minY) / ticks) * index);
      const xTicks = [minX, minX + 5, minX + 10, minX + 15, minX + 20, maxX].filter(
        (value, index, arr) => arr.indexOf(value) === index && value <= maxX
      );

      const gridLines = yTicks.map(value => `
        <line x1="${margin.left}" y1="${yScale(value)}" x2="${width - margin.right}" y2="${yScale(value)}" stroke="rgba(16,35,58,0.09)" stroke-width="1" />
        <text x="${margin.left - 10}" y="${yScale(value) + 4}" text-anchor="end" fill="#5b6f86" font-size="12">${escapeHtml(fmt(value, 1))}</text>
      `).join("");

      const xLines = xTicks.map(value => `
        <line x1="${xScale(value)}" y1="${margin.top}" x2="${xScale(value)}" y2="${height - margin.bottom}" stroke="rgba(16,35,58,0.05)" stroke-width="1" />
        <text x="${xScale(value)}" y="${height - margin.bottom + 24}" text-anchor="middle" fill="#5b6f86" font-size="12">${escapeHtml(String(Math.round(value)))}</text>
      `).join("");

      const seriesLines = series.map(item => {
        const path = item.values.map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(point.x)} ${yScale(point.y)}`).join(" ");
        const lastPoint = item.values[item.values.length - 1];
        const strokeWidth = item.id === state.scenario ? 3.8 : item.id === "baseline_ets" ? 3.2 : 2.4;
        const dash = item.id === "baseline_ets" && state.nationalMetric === "delta_vs_baseline_mean" ? 'stroke-dasharray="6 5"' : "";
        return `
          <path d="${path}" fill="none" stroke="${item.color}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" ${dash} />
          <circle cx="${xScale(lastPoint.x)}" cy="${yScale(lastPoint.y)}" r="${item.id === state.scenario ? 4.5 : 3.2}" fill="${item.color}" />
          <text x="${xScale(lastPoint.x) + 8}" y="${yScale(lastPoint.y) + 4}" fill="${item.color}" font-size="12" font-weight="700">${escapeHtml(item.label)}</text>
        `;
      }).join("");

      const metricLabel = state.nationalMetric === "scenario_pred_mean" ? "Predicted AMR" : "Δ vs baseline";

      return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="National scenario chart">
          <text x="${margin.left}" y="16" fill="#10233a" font-size="13" font-weight="700">${escapeHtml(metricLabel)}</text>
          ${gridLines}
          ${xLines}
          <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="rgba(16,35,58,0.15)" stroke-width="1.2" />
          <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" stroke="rgba(16,35,58,0.15)" stroke-width="1.2" />
          ${seriesLines}
        </svg>
      `;
    }

    function makeRegionChart(rows) {
      if (!rows.length) return "<p>暂无地区数据。</p>";
      const width = 760;
      const barHeight = 30;
      const gap = 10;
      const left = 110;
      const right = 86;
      const top = 22;
      const bottom = 22;
      const height = top + bottom + rows.length * (barHeight + gap);
      const values = rows.map(row => num(row.delta_vs_baseline_mean) || 0);
      const maxAbs = Math.max(...values.map(value => Math.abs(value)), 0.1);
      const zeroX = left + (width - left - right) / 2;
      const scale = value => (Math.abs(value) / maxAbs) * ((width - left - right) / 2);
      const axis = `
        <line x1="${left}" y1="${top - 8}" x2="${width - right}" y2="${top - 8}" stroke="rgba(16,35,58,0.04)" />
        <line x1="${zeroX}" y1="${top - 12}" x2="${zeroX}" y2="${height - bottom + 6}" stroke="rgba(16,35,58,0.18)" />
      `;
      const bars = rows.map((row, index) => {
        const value = num(row.delta_vs_baseline_mean) || 0;
        const y = top + index * (barHeight + gap);
        const positive = value >= 0;
        const widthValue = scale(value);
        const x = positive ? zeroX : zeroX - widthValue;
        const color = positive ? "#d97706" : "#0f766e";
        return `
          <text x="${left - 12}" y="${y + 20}" text-anchor="end" fill="#10233a" font-size="13">${escapeHtml(row.region)}</text>
          <rect x="${x}" y="${y}" width="${Math.max(widthValue, 1)}" height="${barHeight}" rx="10" fill="${color}" opacity="0.92"></rect>
          <text x="${positive ? x + widthValue + 8 : x - 8}" y="${y + 20}" text-anchor="${positive ? "start" : "end"}" fill="${color}" font-size="12" font-weight="700">${escapeHtml(fmtSigned(value, 2))}</text>
        `;
      }).join("");
      return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Regional delta chart">
          ${axis}
          ${bars}
        </svg>
      `;
    }
"""


def build_script_renderers() -> str:
    return """    function renderHeroStats() {
      el("heroStats").innerHTML = [
        { label: "Outcome", value: escapeHtml(DATA.outcome_label), hint: escapeHtml(DATA.outcome_note) },
        { label: "Projection Window", value: `${DATA.start_year}-${DATA.end_year}`, hint: `${DATA.province_count} 省份，${DATA.region_count} 大区` },
        { label: "Model Roles", value: String(DATA.role_count), hint: "当前归档纳入的模型角色数量" },
        { label: "Scenario Space", value: String(DATA.scenario_count), hint: "SSP 情景；每个情景含 median / p10 / p90" }
      ].map(item => `
        <div class="stat">
          <div class="k">${item.label}</div>
          <div class="v">${item.value}</div>
          <div class="h">${item.hint}</div>
        </div>
      `).join("");
    }

    function renderOverview() {
      const current = currentScenarioMedian();
      const baseline = baselineRow();
      const regions = regionRowsForState().slice().sort((a, b) => num(b.delta_vs_baseline_mean) - num(a.delta_vs_baseline_mean));
      const provinceRows = provinceRowsForState();
      const topProvince = provinceRows[0];
      const lowProvince = provinceRows[provinceRows.length - 1];
      const gapRows = dualGapRowsForState();
      const gapTop = gapRows[0];
      const compareBaseline = baselineRow(otherMode(state.mode), state.role);
      const compareScenario = summaryRow(otherMode(state.mode), state.role, state.scenario, "median");

      el("overviewCards").innerHTML = `
        <div class="metric-card">
          <div class="label">2050 baseline</div>
          <div class="value">${fmt(num(baseline?.baseline_pred_mean), 2)}</div>
          <div class="sub">${escapeHtml(modeMap[state.mode].short_label)} · ${escapeHtml(roleMap[state.role].label)}</div>
        </div>
        <div class="metric-card">
          <div class="label">${escapeHtml(scenarioMap[state.scenario].short_label)} 2050</div>
          <div class="value">${fmt(num(current?.scenario_pred_mean), 2)}</div>
          <div class="sub">相对 baseline ${fmtSigned(num(current?.delta_vs_baseline_mean), 2)}</div>
        </div>
        <div class="metric-card">
          <div class="label">most sensitive region</div>
          <div class="value">${escapeHtml(regions[0]?.region || "—")}</div>
          <div class="sub">${fmtSigned(num(regions[0]?.delta_vs_baseline_mean), 2)} · 最低为 ${escapeHtml(regions[regions.length - 1]?.region || "—")} ${fmtSigned(num(regions[regions.length - 1]?.delta_vs_baseline_mean), 2)}</div>
        </div>
        <div class="metric-card">
          <div class="label">largest dual gap</div>
          <div class="value">${escapeHtml(gapTop?.Province || "—")}</div>
          <div class="sub">SSP5-8.5 vs SSP1-1.9 gap = ${fmtSigned(num(gapTop?.scenario_gap), 2)}</div>
        </div>
      `;

      const baselineDiff = num(baseline?.baseline_pred_mean) - num(compareBaseline?.baseline_pred_mean);
      const scenarioDiff = num(current?.scenario_pred_mean) - num(compareScenario?.scenario_pred_mean);
      const deltaDiff = num(current?.delta_vs_baseline_mean) - num(compareScenario?.delta_vs_baseline_mean);

      el("baselineCompareCards").innerHTML = `
        <div class="metric-card">
          <div class="label">${escapeHtml(modeMap[state.mode].short_label)} baseline</div>
          <div class="value">${fmt(num(baseline?.baseline_pred_mean), 2)}</div>
          <div class="sub">当前模式下的 2050 baseline national mean</div>
        </div>
        <div class="metric-card">
          <div class="label">${escapeHtml(modeMap[otherMode(state.mode)].short_label)} baseline</div>
          <div class="value">${fmt(num(compareBaseline?.baseline_pred_mean), 2)}</div>
          <div class="sub">相同 role 的另一种 baseline 口径</div>
        </div>
        <div class="metric-card">
          <div class="label">difference</div>
          <div class="value">${fmtSigned(baselineDiff, 2)}</div>
          <div class="sub">scenario level 差 = ${fmtSigned(scenarioDiff, 2)}；delta 差 = ${fmtSigned(deltaDiff, 3)}</div>
        </div>
      `;

      el("stateNarrative").innerHTML = `
        当前选中的是 <strong>${escapeHtml(modeMap[state.mode].short_label)}</strong> + <strong>${escapeHtml(roleMap[state.role].label)}</strong>。
        到 2050 年，全国 baseline 预测值约为 <strong>${fmt(num(baseline?.baseline_pred_mean), 2)}</strong>；
        在 <strong>${escapeHtml(scenarioMap[state.scenario].short_label)}</strong> 下，全国平均进一步变化 <strong>${fmtSigned(num(current?.delta_vs_baseline_mean), 2)}</strong>，
        得到 <strong>${fmt(num(current?.scenario_pred_mean), 2)}</strong>。当前情景下，地区层面反应最强的是
        <strong>${escapeHtml(regions[0]?.region || "—")}</strong>（${fmtSigned(num(regions[0]?.delta_vs_baseline_mean), 2)}），
        省级增量最高的是 <strong>${escapeHtml(topProvince?.Province || "—")}</strong>（${fmtSigned(num(topProvince?.delta_vs_baseline), 2)}），
        最低的是 <strong>${escapeHtml(lowProvince?.Province || "—")}</strong>（${fmtSigned(num(lowProvince?.delta_vs_baseline), 2)}）。
      `;
    }

    function renderRoleSensitivity() {
      const rows = roleSensitivityRows();
      const maxAbs = Math.max(...rows.map(row => Math.abs(num(row.delta_vs_baseline_mean) || 0)), 0.1);
      el("roleSensitivity").innerHTML = rows.map(row => {
        const delta = num(row.delta_vs_baseline_mean) || 0;
        const width = Math.max((Math.abs(delta) / maxAbs) * 100, 2);
        const positive = delta >= 0;
        return `
          <div class="coeff-row">
            <div>
              <strong>${escapeHtml(row.role_label)}</strong><br />
              <span class="code">${escapeHtml(row.scheme_id)}</span>
            </div>
            <div class="coeff-track">
              <div class="coeff-bar ${positive ? "coeff-pos" : "coeff-neg"}" style="${positive ? `left:50%;width:${width / 2}%` : `left:${50 - width / 2}%;width:${width / 2}%`}"></div>
            </div>
            <div class="${positive ? "delta-up" : "delta-down"}">${fmtSigned(delta, 2)}</div>
          </div>
        `;
      }).join("");
    }

    function renderNational() {
      const series = chartSeries();
      el("nationalLegend").innerHTML = DATA.scenario_meta.map(item => `
        <span class="legend-item">
          <span class="legend-swatch" style="background:${scenarioColors[item.id] || "#1e40af"}"></span>
          <span>${escapeHtml(item.short_label)}</span>
        </span>
      `).join("");
      el("nationalChart").innerHTML = makeLineChart(series);

      const rows = DATA.scenario_meta.map(meta => {
        const baseline = meta.id === "baseline_ets" ? summaryRow(state.mode, state.role, meta.id, "baseline") : null;
        const median = meta.id === "baseline_ets" ? baseline : summaryRow(state.mode, state.role, meta.id, "median");
        const p10 = meta.id === "baseline_ets" ? null : summaryRow(state.mode, state.role, meta.id, "p10");
        const p90 = meta.id === "baseline_ets" ? null : summaryRow(state.mode, state.role, meta.id, "p90");
        return { meta, median, p10, p90 };
      }).filter(item => item.median);

      el("scenarioTable").innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>2050 baseline</th>
              <th>2050 predicted</th>
              <th>Δ vs baseline</th>
              <th>Uncertainty</th>
              <th>Δ vs last observed</th>
              <th>rx1day 2050</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(item => {
              const delta = num(item.median.delta_vs_baseline_mean);
              const deltaClass = delta >= 0 ? "delta-up" : "delta-down";
              const range = item.p10 && item.p90 ? `${fmtSigned(num(item.p10.delta_vs_baseline_mean), 2)} to ${fmtSigned(num(item.p90.delta_vs_baseline_mean), 2)}` : "—";
              return `
                <tr class="${item.meta.id === state.scenario ? "row-highlight" : ""}">
                  <td><strong>${escapeHtml(item.meta.short_label)}</strong></td>
                  <td>${fmt(num(item.median.baseline_pred_mean), 2)}</td>
                  <td>${fmt(num(item.median.scenario_pred_mean), 2)}</td>
                  <td class="${deltaClass}">${fmtSigned(delta, 2)}</td>
                  <td>${range}</td>
                  <td>${fmtSigned(num(item.median.delta_vs_last_observed), 2)}</td>
                  <td>${fmt(num(item.median.rx1day_scenario_mean), 2)}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      `;

      el("nationalFigures").innerHTML = DATA.assets[state.mode].national.map(item => `
        <article class="gallery-card">
          <img src="${escapeHtml(item.path)}" alt="${escapeHtml(item.label)}" />
          <div class="gallery-body">
            <h3>${escapeHtml(item.label)}</h3>
            <p>${escapeHtml(item.note)}</p>
            <a class="link-btn ghost" href="${escapeHtml(item.path)}">打开文件</a>
          </div>
        </article>
      `).join("");
    }

    function renderRegional() {
      const rows = regionRowsForState();
      el("regionalChart").innerHTML = makeRegionChart(rows);
      el("regionalTable").innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Region</th>
              <th>Province n</th>
              <th>2050 baseline</th>
              <th>2050 predicted</th>
              <th>Δ vs baseline</th>
              <th>rx1day baseline</th>
              <th>rx1day scenario</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(row => {
              const delta = num(row.delta_vs_baseline_mean);
              return `
                <tr>
                  <td><strong>${escapeHtml(row.region)}</strong><br /><span style="color:#5b6f86">${escapeHtml(row.region_en)}</span></td>
                  <td>${escapeHtml(row.province_n)}</td>
                  <td>${fmt(num(row.baseline_pred_mean), 2)}</td>
                  <td>${fmt(num(row.scenario_pred_mean), 2)}</td>
                  <td class="${delta >= 0 ? "delta-up" : "delta-down"}">${fmtSigned(delta, 2)}</td>
                  <td>${fmt(num(row.rx1day_baseline_mean), 2)}</td>
                  <td>${fmt(num(row.rx1day_scenario_mean), 2)}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      `;

      el("regionalFigures").innerHTML = DATA.assets[state.mode].regional.map(item => `
        <article class="gallery-card">
          <img src="${escapeHtml(item.path)}" alt="${escapeHtml(item.label)}" />
          <div class="gallery-body">
            <h3>${escapeHtml(item.label)}</h3>
            <p>${escapeHtml(item.note)}</p>
            <a class="link-btn ghost" href="${escapeHtml(item.path)}">打开文件</a>
          </div>
        </article>
      `).join("");
    }

    function simpleProvinceTable(rows) {
      return `
        <table>
          <thead>
            <tr>
              <th>Province</th>
              <th>Region</th>
              <th>2050 predicted</th>
              <th>Δ vs baseline</th>
              <th>rx1day delta</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(row => {
              const delta = num(row.delta_vs_baseline);
              return `
                <tr>
                  <td><strong>${escapeHtml(row.Province)}</strong></td>
                  <td>${escapeHtml(row.region || "—")}</td>
                  <td>${fmt(num(row.scenario_pred), 2)}</td>
                  <td class="${delta >= 0 ? "delta-up" : "delta-down"}">${fmtSigned(delta, 2)}</td>
                  <td>${fmtSigned(num(row.rx1day_delta), 2)}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      `;
    }

    function renderProvincial() {
      const rows = provinceRowsForState();
      el("provincePositive").innerHTML = simpleProvinceTable(rows.slice(0, 10));
      el("provinceNegative").innerHTML = simpleProvinceTable(rows.slice(-10).reverse());

      const gapRows = dualGapRowsForState().slice(0, 12);
      el("dualScenarioTable").innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Province</th>
              <th>Region</th>
              <th>SSP1-1.9</th>
              <th>SSP5-8.5</th>
              <th>Gap</th>
            </tr>
          </thead>
          <tbody>
            ${gapRows.map(row => `
              <tr>
                <td><strong>${escapeHtml(row.Province)}</strong></td>
                <td>${escapeHtml(row.region || "—")}</td>
                <td>${fmtSigned(row.ssp119, 2)}</td>
                <td>${fmtSigned(row.ssp585, 2)}</td>
                <td class="delta-up">${fmtSigned(row.scenario_gap, 2)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;

      el("provincialFigures").innerHTML = DATA.assets[state.mode].provincial.map(item => `
        <article class="gallery-card">
          <img src="${escapeHtml(item.path)}" alt="${escapeHtml(item.label)}" />
          <div class="gallery-body">
            <h3>${escapeHtml(item.label)}</h3>
            <p>${escapeHtml(item.note)}</p>
            <a class="link-btn ghost" href="${escapeHtml(item.path)}">打开文件</a>
          </div>
        </article>
      `).join("");
    }

    function renderProvenance() {
      el("modelCards").innerHTML = DATA.roles.map(role => `
        <article class="model-card ${role.id === state.role ? "active" : ""}">
          <div class="eyebrow">${escapeHtml(role.label)}</div>
          <h3>${escapeHtml(role.scheme_id)}</h3>
          <p><span class="code">${escapeHtml(role.fe_label)}</span> · ${escapeHtml(role.scheme_source)}</p>
          <div class="chip-row">
            ${role.variables.map(variable => `<span class="chip">${escapeHtml(variable)}</span>`).join("")}
          </div>
        </article>
      `).join("");

      const coeffRows = DATA.coefficients.filter(row => row.role_id === state.role);
      const maxAbs = Math.max(...coeffRows.map(row => Math.abs(num(row.coef) || 0)), 0.1);
      el("coefficientBars").innerHTML = coeffRows.map(row => {
        const value = num(row.coef) || 0;
        const positive = value >= 0;
        const percent = Math.max((Math.abs(value) / maxAbs) * 50, 2);
        return `
          <div class="coeff-row">
            <div><strong>${escapeHtml(row.predictor)}</strong></div>
            <div class="coeff-track">
              <div class="coeff-bar ${positive ? "coeff-pos" : "coeff-neg"}" style="${positive ? `left:50%;width:${percent}%` : `left:${50 - percent}%;width:${percent}%`}"></div>
            </div>
            <div class="${positive ? "delta-up" : "delta-down"}">${fmtSigned(value, 3)}</div>
          </div>
        `;
      }).join("");

      el("lancetMethodTable").innerHTML = `
        <table>
          <thead><tr><th>Role</th><th>Method</th><th>Province n</th></tr></thead>
          <tbody>
            ${DATA.lancet_method_summary.map(row => `
              <tr>
                <td>${escapeHtml(row.role_label)}</td>
                <td><span class="code">${escapeHtml(row.method)}</span></td>
                <td>${escapeHtml(String(row.province_n))}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;

      el("xDrivenMethodTable").innerHTML = `
        <table>
          <thead><tr><th>Role</th><th>Component</th><th>Method</th><th>Value</th></tr></thead>
          <tbody>
            ${DATA.x_driven_method_rows.map(row => `
              <tr>
                <td>${escapeHtml(row.role_label)}</td>
                <td>${escapeHtml(row.component)}</td>
                <td><span class="code">${escapeHtml(row.method)}</span></td>
                <td>${row.value ? fmt(num(row.value), 3) : "—"}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;

      el("covariateMethodTable").innerHTML = `
        <table>
          <thead><tr><th>Variable</th><th>Dominant method</th><th>Province n</th><th>Method count</th></tr></thead>
          <tbody>
            ${DATA.covariate_method_summary.map(row => `
              <tr>
                <td>${escapeHtml(row.variable)}</td>
                <td><span class="code">${escapeHtml(row.dominant_method)}</span></td>
                <td>${escapeHtml(String(row.province_n))}</td>
                <td>${escapeHtml(String(row.method_n))}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;

      el("biasTable").innerHTML = `
        <table>
          <thead><tr><th>Scenario</th><th>Statistic</th><th>Mean bias</th><th>Min</th><th>Max</th><th>Province n</th></tr></thead>
          <tbody>
            ${DATA.bias_summary.map(row => `
              <tr>
                <td>${escapeHtml(scenarioMap[row.scenario]?.short_label || row.scenario)}</td>
                <td>${escapeHtml(row.statistic)}</td>
                <td>${fmt(num(row.mean_bias), 2)}</td>
                <td>${fmt(num(row.min_bias), 2)}</td>
                <td>${fmt(num(row.max_bias), 2)}</td>
                <td>${escapeHtml(String(row.province_n))}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function renderCatalog() {
      el("fileCatalog").innerHTML = DATA.file_catalog.map(group => `
        <details open>
          <summary>${escapeHtml(group.title)}<span>${group.items.length} files</span></summary>
          <div class="detail-body">
            ${group.items.map(item => `
              <div class="info-card">
                <h3>${escapeHtml(item.label)}</h3>
                <p>${escapeHtml(item.note)}</p>
                <div class="chip-row"><span class="code">${escapeHtml(item.path)}</span></div>
                <a class="link-btn primary" href="${escapeHtml(item.path)}">打开文件</a>
              </div>
            `).join("")}
          </div>
        </details>
      `).join("");
    }
"""


def build_script_bootstrap() -> str:
    return """    function renderControls() {
      renderChoices(
        "modeControls",
        DATA.mode_meta.map(item => ({ id: item.id, label: item.short_label })),
        state.mode,
        value => { state.mode = value; render(); }
      );
      renderChoices(
        "roleControls",
        DATA.roles.map(item => ({ id: item.id, label: item.label })),
        state.role,
        value => { state.role = value; render(); }
      );
      renderChoices(
        "scenarioControls",
        DATA.scenario_meta.filter(item => item.id !== "baseline_ets").map(item => ({ id: item.id, label: item.short_label })),
        state.scenario,
        value => { state.scenario = value; render(); },
        "subtle-active"
      );
      renderChoices(
        "metricControls",
        metricMeta,
        state.nationalMetric,
        value => { state.nationalMetric = value; render(); }
      );
    }

    function render() {
      renderControls();
      renderOverview();
      renderRoleSensitivity();
      renderNational();
      renderRegional();
      renderProvincial();
      renderProvenance();
      renderCatalog();
    }

    renderHeroStats();
    render();
  </script>"""


def build_html(data: dict[str, object]) -> str:
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n"
        "  <title>6 未来情景分析 Dashboard</title>\n"
        f"{build_styles()}\n"
        "</head>\n"
        "<body>\n"
        f"{build_body()}\n"
        f"{build_scripts(data_json)}\n"
        "</body>\n"
        "</html>\n"
    )
    return html.replace("__GENERATED_AT__", str(data["generated_at"]))


def main() -> None:
    data = build_data()
    html = build_html(data)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Wrote interactive dashboard to {OUT_FILE}")


if __name__ == "__main__":
    main()
