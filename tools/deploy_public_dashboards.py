from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public_dashboards"
RELEASES_DIR = PUBLIC_DIR / "releases"
MODEL_ARCHIVE_BUILDER = ROOT / "tools" / "build_model_archive_12.py"


@dataclass(frozen=True)
class BundleLink:
    label: str
    target: str
    tone: str = ""


@dataclass(frozen=True)
class DashboardBundle:
    slug: str
    label: str
    description: str
    scope_note: str
    source_dir: Path
    builder_script: Path
    files: dict[str, str]
    links: tuple[BundleLink, ...]
    required_builder_inputs: tuple[Path, ...] = ()
    copy_paths: tuple[str, ...] = ()
    write_metadata_file: bool = True


LATEST_BUNDLE = DashboardBundle(
    slug="latest",
    label="Latest Exhaustive Dashboard",
    description="全空间 exhaustive 搜索结果，包含首页、Lancet 子页和横向矩阵。",
    scope_note="当前主线发布版本，直接读取 exhaustive_* 结果。",
    source_dir=ROOT / "2 固定效应模型",
    builder_script=ROOT / "tools" / "build_results_dashboard.py",
    files={
        "home": "results_dashboard.html",
        "lancet": "results_dashboard_lancet.html",
        "matrix": "results_dashboard_matrix.html",
    },
    links=(
        BundleLink(label="Open home", target="index.html", tone="primary"),
        BundleLink(label="Lancet subpage", target="results_dashboard_lancet.html"),
        BundleLink(label="Matrix view", target="results_dashboard_matrix.html"),
        BundleLink(
            label="12-model archive",
            target="results/model_archive_12/selected_models.csv",
        ),
        BundleLink(
            label="Strict top-8 archive",
            target="results/strict_top8_archive/strict_top8_models.csv",
        ),
        BundleLink(label="metadata.json", target="metadata.json", tone="ghost"),
    ),
    copy_paths=("results/model_archive_12", "results/strict_top8_archive"),
)

LEGACY_PUBLIC_EXHAUSTIVE_BUNDLE = DashboardBundle(
    slug="legacy-exhaustive-20260419",
    label="Legacy Public Exhaustive Dashboard",
    description="保留 2026-04-19 对外发布的 exhaustive dashboard，作为更新筛选逻辑前的公开快照。",
    scope_note="来源于 public_dashboards/legacy-exhaustive-20260419 这份已提交的公开快照，用于回看之前的 public latest 版本。",
    source_dir=PUBLIC_DIR / "legacy-exhaustive-20260419",
    builder_script=ROOT / "tools" / "build_results_dashboard.py",
    files={
        "home": "results_dashboard.html",
        "lancet": "results_dashboard_lancet.html",
        "matrix": "results_dashboard_matrix.html",
    },
    links=(
        BundleLink(label="Open home", target="index.html", tone="primary"),
        BundleLink(label="Lancet subpage", target="results_dashboard_lancet.html"),
        BundleLink(label="Matrix view", target="results_dashboard_matrix.html"),
        BundleLink(label="metadata.json", target="metadata.json", tone="ghost"),
    ),
)

LEGACY_BUNDLE = DashboardBundle(
    slug="legacy-12models",
    label="Legacy 12-Model Dashboard",
    description="旧版 4 套人工方案 × 3 种固定效应，共 12 个模型的三页式备份。",
    scope_note="用于和当前 exhaustive 版并排对照的历史快照。",
    source_dir=ROOT / "2 固定效应模型" / "backups" / "legacy_12models_dashboard_20260417",
    builder_script=ROOT
    / "2 固定效应模型"
    / "backups"
    / "legacy_12models_dashboard_20260417"
    / "process"
    / "build_results_dashboard_legacy_12models.py",
    files={
        "home": "results_dashboard_legacy_12models.html",
        "lancet": "results_dashboard_legacy_12models_lancet.html",
        "matrix": "results_dashboard_legacy_12models_matrix.html",
    },
    links=(
        BundleLink(label="Open home", target="index.html", tone="primary"),
        BundleLink(label="Lancet subpage", target="results_dashboard_legacy_12models_lancet.html"),
        BundleLink(label="Matrix view", target="results_dashboard_legacy_12models_matrix.html"),
        BundleLink(label="metadata.json", target="metadata.json", tone="ghost"),
    ),
)

FUTURE_SCENARIO_BUNDLE = DashboardBundle(
    slug="future-scenario-analysis",
    label="Future Scenario Analysis Dashboard",
    description="双 baseline 的未来情景总览页，整合全国、地区、省级结果、模型来源和文件入口。",
    scope_note="对应 6 未来情景分析/index.html，并随 results/、docs/ 与关键映射表一起发布。",
    source_dir=ROOT / "6 未来情景分析",
    builder_script=ROOT / "tools" / "build_future_scenario_dashboard_report.py",
    files={
        "home": "index.html",
    },
    links=(
        BundleLink(label="Open dashboard", target="index.html", tone="primary"),
        BundleLink(label="Temperature dashboard", target="temperature_dashboard.html"),
        BundleLink(label="README", target="README.md"),
        BundleLink(label="2050 compare CSV", target="results/baseline_mode_compare/scenario_summary_2050_compare.csv"),
        BundleLink(
            label="Selected models snapshot",
            target="results/model_screening/selected_models_snapshot.csv",
        ),
        BundleLink(label="metadata.json", target="metadata.json", tone="ghost"),
    ),
    copy_paths=(
        "results",
        "docs",
        "README.md",
        "temperature_dashboard.html",
        "data_processed/province_to_region_7zones.csv",
        "data_processed/TA_future_panel.csv",
        "data_processed/ssp_province_mean_tas_panel.csv",
    ),
)

BAYES_BUNDLE = DashboardBundle(
    slug="bayes-analysis",
    label="Bayesian Analysis Dashboard",
    description="Bayesian model-grid dashboard with one-page interpretation plus downloadable summaries and diagnostics.",
    scope_note="Tracks the six Bayesian variants and publishes the CSV summaries alongside the page.",
    source_dir=PUBLIC_DIR / "bayes-analysis",
    builder_script=ROOT / "tools" / "build_bayes_analysis_dashboard_v2.py",
    files={
        "home": "index.html",
    },
    links=(
        BundleLink(label="Open home", target="index.html", tone="primary"),
        BundleLink(label="Primary summary CSV", target="data/focus_primary_summary.csv"),
        BundleLink(label="Variant bridge CSV", target="data/focus_variant_bridge_summary.csv"),
        BundleLink(label="12-model archive", target="data/selected_models.csv"),
        BundleLink(label="Diagnostics CSV", target="data/combined_diagnostics.csv", tone="ghost"),
    ),
    copy_paths=("data", "metadata.json"),
    write_metadata_file=False,
)

COUNTERFACTUAL_BUNDLE = DashboardBundle(
    slug="counterfactual-amr-agg",
    label="Counterfactual Simulation Dashboard",
    description="AMR_AGG 的反事实推演入口，包含模型筛选、推演方程、单模型聚焦分析和分省结果。",
    scope_note="基于已筛选固定效应模型开展 counterfactual simulation，并打包 figures、CSV 和写作说明。",
    source_dir=ROOT / "5 反事实推演" / "results" / "AMR_AGG",
    builder_script=ROOT / "5 反事实推演" / "build_counterfactual_dashboard.py",
    files={
        "home": "counterfactual_results_dashboard.html",
    },
    links=(
        BundleLink(label="Open dashboard", target="index.html", tone="primary"),
        BundleLink(label="Model screening", target="model_screening/selected_models.csv"),
        BundleLink(
            label="Selected models snapshot",
            target="model_screening/selected_models_source_snapshot.csv",
        ),
        BundleLink(label="National summary", target="counterfactual_outputs/national_overall.csv"),
        BundleLink(label="Write-up notes", target="selection_and_writeup_notes.md", tone="ghost"),
    ),
    copy_paths=("figures", "counterfactual_outputs", "model_screening", "selection_and_writeup_notes.md"),
)

VARIABLE_GROUP_BUNDLE = DashboardBundle(
    slug="variable-group-deep-dive",
    label="Final Model Decision",
    description="Final paper-facing decision page for the 12 candidate models: 8 strict high-correlation models plus 4 hand-picked Year FE models, integrated with FE, Bayesian, counterfactual, and future-scenario evidence.",
    scope_note="Published as an independent entry for final model selection without touching the existing FE, Bayesian, counterfactual, or future dashboards.",
    source_dir=PUBLIC_DIR / "variable-group-deep-dive",
    builder_script=ROOT / "tools" / "build_variable_group_deep_dive_dashboard.py",
    files={
        "home": "index.html",
    },
    links=(
        BundleLink(label="Open dashboard", target="index.html", tone="primary"),
        BundleLink(label="Summary CSV", target="data/variable_group_scheme_summary.csv"),
        BundleLink(label="Coefficients CSV", target="data/variable_group_scheme_coefficients.csv"),
        BundleLink(label="VIF CSV", target="data/variable_group_scheme_vif.csv"),
        BundleLink(label="metadata.json", target="metadata.json", tone="ghost"),
    ),
    copy_paths=("data",),
)

SYS08952_PAPER_BUNDLE = DashboardBundle(
    slug="sys-08952-paper-analysis",
    label="SYS_08952 Paper Analysis",
    description="只聚焦最终论文主模型 SYS_08952 的中文论文陈述式证据链，串联固定效应、Bayes、反事实和未来情景。",
    scope_note="面向最终论文分析撰写，不展示其他候选模型；用于解释 SYS_08952 为什么可作为正文主模型以及每一层结果应如何表述。",
    source_dir=PUBLIC_DIR / "sys-08952-paper-analysis",
    builder_script=ROOT / "tools" / "build_sys08952_paper_analysis.py",
    files={
        "home": "index.html",
    },
    links=(
        BundleLink(label="Open paper analysis", target="index.html", tone="primary"),
        BundleLink(label="Payload JSON", target="data/sys08952_paper_payload.json", tone="ghost"),
    ),
    required_builder_inputs=(ROOT / "amr_rate.csv", ROOT / "climate_social_eco.csv"),
    copy_paths=("assets", "data"),
)

ALL_BUNDLES: tuple[DashboardBundle, ...] = (
    LATEST_BUNDLE,
    LEGACY_PUBLIC_EXHAUSTIVE_BUNDLE,
    LEGACY_BUNDLE,
    FUTURE_SCENARIO_BUNDLE,
    BAYES_BUNDLE,
    COUNTERFACTUAL_BUNDLE,
    VARIABLE_GROUP_BUNDLE,
    SYS08952_PAPER_BUNDLE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild and publish dashboard HTML files into public_dashboards/."
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Publish the current HTML snapshots without rerunning the upstream builders.",
    )
    parser.add_argument(
        "--skip-latest",
        action="store_true",
        help="Do not publish the latest exhaustive dashboard bundle.",
    )
    parser.add_argument(
        "--skip-legacy",
        action="store_true",
        help="Do not publish the legacy 12-model dashboard bundle.",
    )
    parser.add_argument(
        "--skip-future-scenario",
        action="store_true",
        help="Do not publish the future scenario analysis dashboard bundle.",
    )
    parser.add_argument(
        "--skip-bayes",
        action="store_true",
        help="Do not publish the Bayesian analysis dashboard bundle.",
    )
    parser.add_argument(
        "--skip-counterfactual",
        action="store_true",
        help="Do not publish the counterfactual simulation dashboard bundle.",
    )
    parser.add_argument(
        "--skip-variable-group",
        action="store_true",
        help="Do not publish the variable-group deep-dive dashboard bundle.",
    )
    parser.add_argument(
        "--skip-sys08952-paper",
        action="store_true",
        help="Do not publish the SYS_08952 paper-analysis dashboard bundle.",
    )
    parser.add_argument(
        "--release-tag",
        help="Optional release tag for the archive folder. Defaults to YYYYMMDD-HHMMSS.",
    )
    parser.add_argument(
        "--retain-releases",
        type=int,
        help="Optionally keep only the newest N release snapshot folders under public_dashboards/releases/.",
    )
    return parser.parse_args()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_builder(script_path: Path) -> None:
    subprocess.run(
        [sys.executable, "-X", "utf8", str(script_path)],
        cwd=ROOT,
        check=True,
    )


def run_bundle_builder(bundle: DashboardBundle) -> None:
    missing_inputs = [path for path in bundle.required_builder_inputs if not path.exists()]
    if missing_inputs:
        try:
            ensure_sources(bundle)
        except FileNotFoundError as exc:
            formatted = ", ".join(rel(path) for path in missing_inputs)
            raise FileNotFoundError(
                f"Cannot rebuild {bundle.slug}; missing required input(s): {formatted}. "
                f"The committed snapshot is also incomplete: {exc}"
            ) from exc

        formatted = ", ".join(rel(path) for path in missing_inputs)
        print(
            f"Skipped rebuild for {bundle.slug}; missing local-only input(s): {formatted}. "
            "Publishing the committed static snapshot instead."
        )
        return

    run_builder(bundle.builder_script)


def same_path(source: Path, target: Path) -> bool:
    try:
        return source.resolve() == target.resolve()
    except FileNotFoundError:
        return False


def copy_path(source: Path, target: Path) -> None:
    if same_path(source, target):
        return
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def ensure_sources(bundle: DashboardBundle) -> None:
    required_paths = list(bundle.files.values()) + list(bundle.copy_paths)
    missing = [name for name in required_paths if not (bundle.source_dir / name).exists()]
    if missing:
        formatted = ", ".join(missing)
        raise FileNotFoundError(f"Missing dashboard files for {bundle.slug}: {formatted}")


def copy_bundle(bundle: DashboardBundle, destination: Path, release_tag: str, generated_at: str) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for page_key, filename in bundle.files.items():
        source = bundle.source_dir / filename
        target = destination / filename
        copy_path(source, target)
        copied[page_key] = filename
        if page_key == "home":
            copy_path(source, destination / "index.html")
            copied["directory_index"] = "index.html"

    for rel_path in bundle.copy_paths:
        copy_path(bundle.source_dir / rel_path, destination / rel_path)

    metadata = {
        "label": bundle.label,
        "slug": bundle.slug,
        "description": bundle.description,
        "scope_note": bundle.scope_note,
        "generated_at": generated_at,
        "release_tag": release_tag,
        "source_dir": rel(bundle.source_dir),
        "builder_script": rel(bundle.builder_script),
        "files": copied,
        "links": [
            {"label": link.label, "target": link.target, "tone": link.tone}
            for link in bundle.links
        ],
    }
    if bundle.write_metadata_file:
        (destination / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return metadata


def bundle_card(bundle: dict[str, Any], base_href: str) -> str:
    home_href = f"{base_href}/{bundle['slug']}/index.html"
    lancet_href = f"{base_href}/{bundle['slug']}/{bundle['files']['lancet']}"
    matrix_href = f"{base_href}/{bundle['slug']}/{bundle['files']['matrix']}"
    metadata_href = f"{base_href}/{bundle['slug']}/metadata.json"
    return f"""
      <section class="panel">
        <div class="eyebrow">{escape(bundle['slug'])}</div>
        <h2>{escape(bundle['label'])}</h2>
        <p>{escape(bundle['description'])}</p>
        <div class="meta">
          <span>Scope: {escape(bundle['scope_note'])}</span>
          <span>Builder: <code>{escape(bundle['builder_script'])}</code></span>
        </div>
        <div class="links">
          <a class="btn primary" href="{escape(home_href)}">打开首页</a>
          <a class="btn" href="{escape(lancet_href)}">Lancet 子页</a>
          <a class="btn" href="{escape(matrix_href)}">横向矩阵</a>
          <a class="btn ghost" href="{escape(metadata_href)}">metadata.json</a>
        </div>
      </section>
    """


def render_bundle_links(bundle: dict[str, Any], base_href: str) -> str:
    buttons: list[str] = []
    for link in bundle["links"]:
        href = f"{base_href}/{bundle['slug']}/{link['target']}"
        tone = str(link.get("tone", "")).strip()
        classes = "btn"
        if tone:
            classes += f" {tone}"
        buttons.append(
            f'<a class="{escape(classes)}" href="{escape(href)}">{escape(link["label"])}</a>'
        )
    return "".join(buttons)


def bundle_card(bundle: dict[str, Any], base_href: str) -> str:
    return f"""
      <section class="panel">
        <div class="eyebrow">{escape(bundle['slug'])}</div>
        <h2>{escape(bundle['label'])}</h2>
        <p>{escape(bundle['description'])}</p>
        <div class="meta">
          <span>Scope: {escape(bundle['scope_note'])}</span>
          <span>Builder: <code>{escape(bundle['builder_script'])}</code></span>
        </div>
        <div class="links">
          {render_bundle_links(bundle, base_href)}
        </div>
      </section>
    """


def build_entry_html(manifest: dict[str, Any]) -> str:
    stable_cards = "".join(bundle_card(bundle, ".") for bundle in manifest["bundles"])
    release_cards = "".join(bundle_card(bundle, f"./releases/{manifest['release_tag']}") for bundle in manifest["bundles"])
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AMR Dashboard Deployment</title>
  <style>
    :root {{
      --bg: #f6efe7;
      --panel: rgba(255, 250, 244, 0.94);
      --ink: #20363c;
      --muted: #52666c;
      --accent: #b45735;
      --accent-2: #2f6f74;
      --line: rgba(32, 54, 60, 0.12);
      --shadow: 0 16px 44px rgba(39, 35, 31, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(180, 87, 53, 0.14), transparent 28%),
        radial-gradient(circle at top right, rgba(47, 111, 116, 0.10), transparent 26%),
        linear-gradient(180deg, #faf4eb 0%, #eef3f1 100%);
    }}
    .page {{
      width: min(1240px, calc(100vw - 24px));
      margin: 20px auto 28px;
      display: grid;
      gap: 18px;
    }}
    .card, .panel {{
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.72);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .card {{
      border-radius: 30px;
      padding: 28px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(25, 47, 53, 0.98), rgba(42, 96, 97, 0.94));
      color: #fbf7f1;
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -44px;
      top: -44px;
      width: 230px;
      height: 230px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255, 255, 255, 0.18), transparent 66%);
    }}
    .eyebrow {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: inherit;
      opacity: 0.76;
      margin-bottom: 12px;
    }}
    h1, h2 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      letter-spacing: -0.02em;
    }}
    h1 {{
      font-size: clamp(34px, 4vw, 54px);
      line-height: 1.04;
    }}
    h2 {{
      font-size: 28px;
      line-height: 1.12;
    }}
    p {{
      margin: 12px 0 0;
      line-height: 1.75;
      color: var(--muted);
      font-size: 16px;
    }}
    .hero p {{
      color: rgba(251, 247, 241, 0.92);
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 22px;
    }}
    .stat {{
      padding: 16px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.10);
      border: 1px solid rgba(255, 255, 255, 0.12);
    }}
    .stat .k {{
      font-size: 12px;
      text-transform: uppercase;
      opacity: 0.76;
      margin-bottom: 8px;
    }}
    .stat .v {{
      font-size: clamp(26px, 3vw, 40px);
      font-weight: 800;
      line-height: 1;
      margin-bottom: 6px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .stat .h {{
      font-size: 12px;
      line-height: 1.55;
      color: rgba(251, 247, 241, 0.84);
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      margin-bottom: 12px;
    }}
    .grid {{
      display: grid;
      gap: 18px;
    }}
    .grid.two {{
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }}
    .panel {{
      border-radius: 24px;
      padding: 22px;
    }}
    .panel p {{
      color: #53686e;
    }}
    .meta {{
      display: grid;
      gap: 8px;
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(32, 54, 60, 0.04);
      border: 1px solid var(--line);
      font-size: 13px;
      color: var(--muted);
      overflow: hidden;
    }}
    .meta span, .ops div {{
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 15px;
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      border: 1px solid var(--line);
      color: var(--ink);
      background: rgba(255, 255, 255, 0.76);
    }}
    .btn.primary {{
      background: linear-gradient(135deg, var(--accent), #984327);
      color: #fff8f2;
      border-color: transparent;
    }}
    .btn.ghost {{
      color: var(--accent-2);
      border-color: rgba(47, 111, 116, 0.16);
      background: rgba(47, 111, 116, 0.08);
    }}
    .ops {{
      display: grid;
      gap: 10px;
      color: var(--muted);
      line-height: 1.7;
      font-size: 14px;
    }}
    code {{
      font-family: Consolas, "SFMono-Regular", monospace;
      background: rgba(32, 54, 60, 0.06);
      border: 1px solid rgba(32, 54, 60, 0.08);
      border-radius: 10px;
      padding: 1px 7px;
      color: var(--ink);
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
      display: inline-block;
      max-width: 100%;
      vertical-align: top;
    }}
    .hero code {{
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.16);
      color: #fff9f3;
    }}
    @media (max-width: 940px) {{
      .grid.two, .stats {{
        grid-template-columns: 1fr;
      }}
      .page {{
        width: calc(100vw - 12px);
        margin: 8px auto 16px;
      }}
      .card, .panel {{
        padding: 20px;
        border-radius: 22px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="card hero">
      <div class="eyebrow">Public Deployment</div>
      <h1>AMR Dashboard 发布入口</h1>
      <p>这里是长期维护用的静态发布目录。研究目录继续保存原始分析结果，<code>public_dashboards/</code> 负责对外访问、稳定链接和版本归档。</p>
      <div class="stats">
        <div class="stat"><div class="k">生成时间</div><div class="v">{escape(manifest['generated_at'])}</div><div class="h">这次部署完成的时间戳</div></div>
        <div class="stat"><div class="k">发布版本</div><div class="v">{escape(manifest['release_tag'])}</div><div class="h">归档快照目录名</div></div>
        <div class="stat"><div class="k">稳定入口</div><div class="v">{len(manifest['bundles'])}</div><div class="h">当前维护中的 dashboard 套数</div></div>
        <div class="stat"><div class="k">发布根目录</div><div class="v">public</div><div class="h"><code>{escape(manifest['public_dir'])}</code></div></div>
      </div>
    </section>

    <section class="card">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Stable Paths</div>
          <h2>稳定发布入口</h2>
          <p>这两个目录始终指向当前最新一次部署后的首页和子页面，适合长期收藏或挂到静态服务器。</p>
        </div>
      </div>
      <div class="grid two">
        {stable_cards}
      </div>
    </section>

    <section class="card">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Release Snapshot</div>
          <h2>本次归档快照</h2>
          <p>每次部署都会把当前版本复制到 <code>releases/{escape(manifest['release_tag'])}</code>，方便以后回看或回滚。</p>
        </div>
        <div class="links">
          <a class="btn primary" href="./releases/{escape(manifest['release_tag'])}/index.html">打开本次快照</a>
          <a class="btn ghost" href="./manifest.json">manifest.json</a>
        </div>
      </div>
      <div class="grid two">
        {release_cards}
      </div>
    </section>

    <section class="card">
      <div class="section-head">
        <div>
          <div class="eyebrow" style="color: var(--muted);">Maintenance</div>
          <h2>维护约定</h2>
        </div>
      </div>
      <div class="ops">
        <div>重新构建并发布：<code>python -X utf8 tools/deploy_public_dashboards.py</code></div>
        <div>只发布当前已有 HTML，不重跑上游 builder：<code>python -X utf8 tools/deploy_public_dashboards.py --skip-build</code></div>
        <div>最新版本布局维护入口：<code>tools/build_results_dashboard.py</code></div>
        <div>旧版 12 模型布局维护入口：<code>2 固定效应模型/backups/legacy_12models_dashboard_20260417/process/build_results_dashboard_legacy_12models.py</code></div>
        <div>本发布目录说明见：<code>public_dashboards/README.md</code></div>
      </div>
    </section>
  </div>
</body>
</html>
"""


def build_release_index_html(manifest: dict[str, Any]) -> str:
    cards = "".join(bundle_card(bundle, ".") for bundle in manifest["bundles"])
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dashboard Release {escape(manifest['release_tag'])}</title>
  <style>
    :root {{
      --bg: #f6efe7;
      --panel: rgba(255, 250, 244, 0.94);
      --ink: #20363c;
      --muted: #52666c;
      --accent: #b45735;
      --line: rgba(32, 54, 60, 0.12);
      --shadow: 0 16px 44px rgba(39, 35, 31, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background: linear-gradient(180deg, #faf4eb 0%, #eef3f1 100%);
    }}
    .page {{
      width: min(1240px, calc(100vw - 24px));
      margin: 20px auto 28px;
      display: grid;
      gap: 18px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid rgba(255, 255, 255, 0.72);
      border-radius: 28px;
      padding: 26px;
      box-shadow: var(--shadow);
    }}
    .eyebrow {{
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 12px;
    }}
    h1, h2 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      letter-spacing: -0.02em;
    }}
    h1 {{
      font-size: clamp(34px, 4vw, 52px);
    }}
    h2 {{
      font-size: 28px;
    }}
    p {{
      margin: 12px 0 0;
      line-height: 1.72;
      color: var(--muted);
      font-size: 16px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      background: rgba(255, 255, 255, 0.78);
    }}
    .meta {{
      display: grid;
      gap: 8px;
      margin-top: 16px;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.65;
      overflow: hidden;
    }}
    .meta span {{
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 15px;
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
      color: var(--ink);
    }}
    .btn.primary {{
      background: linear-gradient(135deg, var(--accent), #984327);
      color: #fff8f2;
      border-color: transparent;
    }}
    code {{
      font-family: Consolas, "SFMono-Regular", monospace;
      background: rgba(32, 54, 60, 0.06);
      border: 1px solid rgba(32, 54, 60, 0.08);
      border-radius: 10px;
      padding: 1px 7px;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
      display: inline-block;
      max-width: 100%;
      vertical-align: top;
    }}
    @media (max-width: 900px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
      .page {{
        width: calc(100vw - 12px);
        margin: 8px auto 16px;
      }}
      .card {{
        padding: 20px;
        border-radius: 22px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="card">
      <div class="eyebrow">Release Snapshot</div>
      <h1>{escape(manifest['release_tag'])}</h1>
      <p>这是这一次部署的归档版本。稳定入口仍然在 <code>../../index.html</code> 对应的各个 bundle 目录中，这里保留的是可回看的静态快照。</p>
      <div class="links">
        <a class="btn primary" href="../../index.html">返回发布入口</a>
        <a class="btn" href="./manifest.json">查看快照 manifest</a>
      </div>
    </section>

    <section class="card">
      <div class="eyebrow">Archived Bundles</div>
      <h2>本次快照内容</h2>
      <div class="grid">
        {cards}
      </div>
    </section>
  </div>
</body>
</html>
"""


def build_public_readme(manifest: dict[str, Any]) -> str:
    bundle_dirs = [f"  {bundle['slug']}/" for bundle in manifest["bundles"]]
    builder_lines = [f"- {bundle['slug']} builder：`{bundle['builder_script']}`" for bundle in manifest["bundles"]]
    lines = [
        "# public_dashboards",
        "",
        "这个目录是 dashboard 的长期发布层。",
        "",
        "它和研究目录的职责分开：",
        "",
        "- `2 固定效应模型/` 继续保存分析过程和原始构建产物。",
        "- `public_dashboards/` 提供稳定链接、发布入口和历史归档。",
        "",
        "## 当前结构",
        "",
        "```text",
        "public_dashboards/",
        "  index.html",
        "  manifest.json",
        *bundle_dirs,
        f"  releases/{manifest['release_tag']}/",
        "```",
        "",
        "## 维护命令",
        "",
        "重新构建并发布：",
        "",
        "```bash",
        "python -X utf8 tools/deploy_public_dashboards.py",
        "```",
        "",
        "只发布已有 HTML，不重跑上游 builder：",
        "",
        "```bash",
        "python -X utf8 tools/deploy_public_dashboards.py --skip-build",
        "```",
        "",
        "在 GitHub Actions 里建议加上快照保留，例如：",
        "",
        "```bash",
        "python -X utf8 tools/deploy_public_dashboards.py --retain-releases 12",
        "```",
        "",
        "## 上游维护入口",
        "",
        *builder_lines,
        "",
        "## GitHub Pages",
        "",
        "- 推荐使用 GitHub Actions 发布，而不是手工提交生成后的静态文件分支。",
        "- 工作流文件见：`.github/workflows/deploy-github-pages.yml`。",
        "- 仓库设置路径：`Settings -> Pages -> Build and deployment -> Source -> GitHub Actions`。",
        "- 项目页默认 URL 一般是：`https://<用户名>.github.io/<仓库名>/`。",
        "- 这个站点内部已经统一使用相对链接，所以可以直接部署到项目子路径，不需要额外改 base URL。",
        "- 如果仓库是私有仓库，GitHub Pages 是否可用取决于你的 GitHub 方案；公开仓库在 GitHub Free 下可用。",
        "- GitHub Pages 站点是公开可访问的，不要把不希望公开的数据一起发布。",
        "",
        "## 首次启用步骤",
        "",
        "1. 把仓库推到 GitHub。",
        "2. 进入仓库的 `Settings -> Pages`，把 Source 设为 `GitHub Actions`。",
        "3. 推送到默认分支后，等待 `Deploy GitHub Pages` 工作流完成。",
        "4. 首次成功后，在 Pages 设置页里复制公开 URL。",
        "",
        "## 自定义域名",
        "",
        "- GitHub 官方建议先验证域名，再把域名接到 Pages，避免域名接管风险。",
        "- 如果你使用自定义 GitHub Actions workflow，需要在仓库 `Settings -> Pages` 里配置 Custom domain；仅靠仓库里的 `CNAME` 文件并不会自动新增或移除域名设置。",
        "- 域名生效后，再勾选 `Enforce HTTPS`。",
        "",
        "## 说明",
        "",
        "- 各个稳定 bundle 目录始终覆盖为最近一次部署后的稳定版本。",
        "- `releases/<timestamp>/` 会保留部署当时的归档快照，方便对照和回滚。",
        "- 每个 bundle 目录下都有 `metadata.json`，可用于排查来源和生成脚本。",
        "",
    ]
    return "\n".join(lines)


def publish_bundle(bundle: DashboardBundle, release_tag: str, generated_at: str) -> dict[str, Any]:
    stable_dir = PUBLIC_DIR / bundle.slug
    release_dir = RELEASES_DIR / release_tag / bundle.slug
    stable_metadata = copy_bundle(bundle, stable_dir, release_tag, generated_at)
    release_metadata = copy_bundle(bundle, release_dir, release_tag, generated_at)
    return {
        **stable_metadata,
        "stable_dir": rel(stable_dir),
        "release_dir": rel(release_dir),
        "stable_home": f"{bundle.slug}/index.html",
        "release_home": f"releases/{release_tag}/{bundle.slug}/index.html",
    }


def write_manifest(manifest: dict[str, Any]) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")
    (PUBLIC_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (PUBLIC_DIR / "index.html").write_text(build_entry_html(manifest), encoding="utf-8")
    (PUBLIC_DIR / "README.md").write_text(build_public_readme(manifest), encoding="utf-8")

    release_dir = RELEASES_DIR / manifest["release_tag"]
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (release_dir / "index.html").write_text(build_release_index_html(manifest), encoding="utf-8")


def prune_releases(max_count: int | None) -> None:
    if max_count is None:
        return
    if max_count < 1:
        raise ValueError("--retain-releases must be at least 1")
    if not RELEASES_DIR.exists():
        return

    release_dirs = sorted(path for path in RELEASES_DIR.iterdir() if path.is_dir())
    to_remove = release_dirs[:-max_count]
    for path in to_remove:
        shutil.rmtree(path)


def main() -> None:
    args = parse_args()
    release_tag = args.release_tag or datetime.now().strftime("%Y%m%d-%H%M%S")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    bundles: list[DashboardBundle] = []
    if not args.skip_latest:
        bundles.append(LATEST_BUNDLE)
        bundles.append(LEGACY_PUBLIC_EXHAUSTIVE_BUNDLE)
    if not args.skip_legacy:
        bundles.append(LEGACY_BUNDLE)
    if not args.skip_future_scenario:
        bundles.append(FUTURE_SCENARIO_BUNDLE)
    if not args.skip_bayes:
        bundles.append(BAYES_BUNDLE)
    if not args.skip_counterfactual:
        bundles.append(COUNTERFACTUAL_BUNDLE)
    if not args.skip_variable_group:
        bundles.append(VARIABLE_GROUP_BUNDLE)
    if not args.skip_sys08952_paper:
        bundles.append(SYS08952_PAPER_BUNDLE)
    if not bundles:
        raise SystemExit(
            "Nothing to publish. Remove skip flags or select at least one bundle."
        )
    selected_slugs = {bundle.slug for bundle in bundles}
    all_slugs = {bundle.slug for bundle in ALL_BUNDLES}
    is_full_publish = selected_slugs == all_slugs

    if not args.skip_build:
        if not args.skip_latest or not args.skip_bayes or not args.skip_counterfactual:
            run_builder(MODEL_ARCHIVE_BUILDER)
        built_scripts: set[Path] = set()
        for bundle in bundles:
            if bundle.builder_script in built_scripts:
                continue
            run_bundle_builder(bundle)
            built_scripts.add(bundle.builder_script)

    for bundle in bundles:
        ensure_sources(bundle)

    published = [publish_bundle(bundle, release_tag, generated_at) for bundle in bundles]
    manifest = {
        "generated_at": generated_at,
        "release_tag": release_tag,
        "public_dir": rel(PUBLIC_DIR),
        "bundles": published,
    }
    if is_full_publish:
        write_manifest(manifest)
    else:
        print(
            "Partial publish detected; kept existing public root index/manifest unchanged."
        )
    prune_releases(args.retain_releases)

    print(f"Published dashboards to: {PUBLIC_DIR}")
    print(f"Release archive: {RELEASES_DIR / release_tag}")
    for bundle in published:
        print(f"- {bundle['label']}: {bundle['stable_home']}")


if __name__ == "__main__":
    main()
