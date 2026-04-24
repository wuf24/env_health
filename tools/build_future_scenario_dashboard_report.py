from __future__ import annotations

from html import escape
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_future_scenario_dashboard import OUT_FILE, build_data


SCENARIO_ORDER = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
ROLE_ALIASES = {
    "robust_systematic_2": ["robust_strict_fe"],
    "robust_strict_fe": ["robust_systematic_2"],
}


def num(value: object) -> float:
    return float(value)


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def fmt_signed(value: float, digits: int = 2) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:,.{digits}f}"


def scenario_label(data: dict, scenario_id: str) -> str:
    for item in data["scenario_meta"]:
        if item["id"] == scenario_id:
            return str(item["short_label"])
    return scenario_id


def mode_short(data: dict, mode_id: str) -> str:
    for item in data["mode_meta"]:
        if item["id"] == mode_id:
            return str(item["short_label"])
    return mode_id


def role_label(data: dict, role_id: str) -> str:
    for item in data["roles"]:
        if item["id"] == role_id:
            return str(item["label"])
    return role_id


def role_ids(data: dict) -> list[str]:
    ordered = list(data.get("role_order", []))
    if ordered:
        return ordered
    return [str(item["id"]) for item in data.get("roles", [])]


def primary_role_id(data: dict) -> str:
    ids = role_ids(data)
    if "main_model" in ids:
        return "main_model"
    if not ids:
        raise KeyError("No role ids found in future-scenario dashboard data.")
    return ids[0]


def archive_mix_counts(data: dict) -> tuple[int, int]:
    ids = role_ids(data)
    legacy_count = sum(1 for role_id in ids if role_id == "main_model" or role_id.startswith("robust_"))
    strict_count = sum(1 for role_id in ids if role_id.startswith("strict_"))
    return legacy_count, strict_count


def first_row(rows: list[dict], **filters: str) -> dict:
    for row in rows:
        if all(str(row.get(key, "")) == str(value) for key, value in filters.items()):
            return row
    raise KeyError(filters)


def rows_where(rows: list[dict], **filters: str) -> list[dict]:
    return [
        row
        for row in rows
        if all(str(row.get(key, "")) == str(value) for key, value in filters.items())
    ]


def rel(path: str) -> str:
    return path.replace("\\", "/")


def resolve_role_id(rows: list[dict], desired_role_id: str, **filters: str) -> str:
    candidates = [desired_role_id] + ROLE_ALIASES.get(desired_role_id, [])
    for candidate in candidates:
        matched = rows_where(rows, role_id=candidate, **filters)
        if matched:
            return candidate
    return desired_role_id


def build_mode_story(data: dict, mode_id: str, role_id: str | None = None) -> dict:
    target_role = role_id or primary_role_id(data)
    national_role = resolve_role_id(
        data["national_yearly"],
        target_role,
        baseline_mode=mode_id,
        scenario_id="baseline_ets",
    )
    scenario_role = resolve_role_id(
        data["scenario_summary_2050"],
        target_role,
        baseline_mode=mode_id,
        scenario_id="ssp119",
        statistic="median",
    )
    regional_role = resolve_role_id(
        data["regional_summary_2050"],
        target_role,
        baseline_mode=mode_id,
        scenario_id="ssp119",
    )
    provincial_role = resolve_role_id(
        data["province_projection_2050"],
        target_role,
        baseline_mode=mode_id,
        scenario_id="ssp585",
    )
    national_rows = rows_where(
        data["national_yearly"],
        baseline_mode=mode_id,
        role_id=national_role,
        scenario_id="baseline_ets",
    )
    national_rows = sorted(national_rows, key=lambda row: int(row["Year"]))
    baseline_2024 = num(national_rows[0]["scenario_pred_mean"])
    baseline_2050 = num(national_rows[-1]["scenario_pred_mean"])

    scenario_rows = [
        first_row(
            data["scenario_summary_2050"],
            baseline_mode=mode_id,
            role_id=scenario_role,
            scenario_id=scenario_id,
            statistic="median",
        )
        for scenario_id in SCENARIO_ORDER
    ]
    scenario_rows = sorted(scenario_rows, key=lambda row: num(row["scenario_pred_mean"]))
    low_row = scenario_rows[0]
    high_row = scenario_rows[-1]

    regional_119 = sorted(
        rows_where(
            data["regional_summary_2050"],
            baseline_mode=mode_id,
            role_id=regional_role,
            scenario_id="ssp119",
        ),
        key=lambda row: num(row["delta_vs_baseline_mean"]),
    )
    regional_585 = sorted(
        rows_where(
            data["regional_summary_2050"],
            baseline_mode=mode_id,
            role_id=regional_role,
            scenario_id="ssp585",
        ),
        key=lambda row: num(row["delta_vs_baseline_mean"]),
    )

    provincial_585 = sorted(
        rows_where(
            data["province_projection_2050"],
            baseline_mode=mode_id,
            role_id=provincial_role,
            scenario_id="ssp585",
        ),
        key=lambda row: num(row["delta_vs_baseline"]),
    )
    provincial_119_map = {
        row["Province"]: row
        for row in rows_where(
            data["province_projection_2050"],
            baseline_mode=mode_id,
            role_id=provincial_role,
            scenario_id="ssp119",
        )
    }
    dual_gap_rows: list[dict] = []
    for row in provincial_585:
        paired = provincial_119_map.get(row["Province"])
        if not paired:
            continue
        dual_gap_rows.append(
            {
                "Province": row["Province"],
                "region": row["region"],
                "ssp119": num(paired["delta_vs_baseline"]),
                "ssp585": num(row["delta_vs_baseline"]),
                "gap": num(row["delta_vs_baseline"]) - num(paired["delta_vs_baseline"]),
            }
        )
    dual_gap_rows.sort(key=lambda row: row["gap"], reverse=True)

    role_rows = []
    for role_id in role_ids(data):
        ssp119 = first_row(
            data["scenario_summary_2050"],
            baseline_mode=mode_id,
            role_id=role_id,
            scenario_id="ssp119",
            statistic="median",
        )
        ssp585 = first_row(
            data["scenario_summary_2050"],
            baseline_mode=mode_id,
            role_id=role_id,
            scenario_id="ssp585",
            statistic="median",
        )
        baseline = first_row(
            data["scenario_summary_2050"],
            baseline_mode=mode_id,
            role_id=role_id,
            scenario_id="baseline_ets",
            statistic="baseline",
        )
        r1 = next(
            (
                num(row["coef"])
                for row in data["coefficients"]
                if row["role_id"] == role_id and row["predictor"] == "R1xday"
            ),
            0.0,
        )
        role_rows.append(
            {
                "role_id": role_id,
                "role_label": role_label(data, role_id),
                "baseline_2050": num(baseline["baseline_pred_mean"]),
                "ssp119_delta": num(ssp119["delta_vs_baseline_mean"]),
                "ssp585_delta": num(ssp585["delta_vs_baseline_mean"]),
                "spread": num(ssp585["delta_vs_baseline_mean"]) - num(ssp119["delta_vs_baseline_mean"]),
                "ssp585_pred": num(ssp585["scenario_pred_mean"]),
                "r1_coef": r1,
            }
        )

    return {
        "mode_id": mode_id,
        "mode_short": mode_short(data, mode_id),
        "role_id": target_role,
        "role_label": role_label(data, target_role),
        "baseline_2024": baseline_2024,
        "baseline_2050": baseline_2050,
        "baseline_change": baseline_2050 - baseline_2024,
        "scenario_rows": scenario_rows,
        "low_row": low_row,
        "high_row": high_row,
        "spread": num(high_row["scenario_pred_mean"]) - num(low_row["scenario_pred_mean"]),
        "delta_spread": num(high_row["delta_vs_baseline_mean"]) - num(low_row["delta_vs_baseline_mean"]),
        "all_below_last_observed": all(num(row["delta_vs_last_observed"]) < 0 for row in scenario_rows),
        "regional_119": regional_119,
        "regional_585": regional_585,
        "provincial_585": provincial_585,
        "dual_gap_rows": dual_gap_rows,
        "role_rows": role_rows,
        "assets": data["assets"][mode_id],
    }


def build_overall_story(data: dict, stories: dict[str, dict]) -> dict:
    lancet = stories["lancet_ets"]
    xdriven = stories["x_driven"]
    return {
        "baseline_gap_2024": xdriven["baseline_2024"] - lancet["baseline_2024"],
        "baseline_gap_2050": xdriven["baseline_2050"] - lancet["baseline_2050"],
        "same_delta_spread": lancet["delta_spread"],
        "regional_high": lancet["regional_585"][-1],
        "regional_low": lancet["regional_585"][0],
        "province_high": lancet["provincial_585"][-1],
        "province_low": lancet["provincial_585"][0],
        "province_gap": lancet["dual_gap_rows"][0],
    }


def figure_block(path: str, title: str, caption: str, hero: bool = False) -> str:
    cls = "figure-card hero-figure" if hero else "figure-card"
    return f"""
      <figure class="{cls}">
        <img src="{escape(rel(path))}" alt="{escape(title)}" loading="lazy" />
        <figcaption>
          <strong>{escape(title)}</strong>
          <span>{escape(caption)}</span>
        </figcaption>
      </figure>
    """


def bullet_items(items: list[str]) -> str:
    return "".join(f"<li>{item}</li>" for item in items)


def build_summary_table(data: dict, stories: dict[str, dict], role_id: str) -> str:
    rows = []
    for scenario_id in SCENARIO_ORDER:
        l_row = next(row for row in stories["lancet_ets"]["scenario_rows"] if row["scenario_id"] == scenario_id)
        x_row = next(row for row in stories["x_driven"]["scenario_rows"] if row["scenario_id"] == scenario_id)
        p10 = first_row(
            data["scenario_summary_2050"],
            baseline_mode="lancet_ets",
            role_id=role_id,
            scenario_id=scenario_id,
            statistic="p10",
        )
        p90 = first_row(
            data["scenario_summary_2050"],
            baseline_mode="lancet_ets",
            role_id=role_id,
            scenario_id=scenario_id,
            statistic="p90",
        )
        rows.append(
            f"""
            <tr>
              <td><strong>{escape(scenario_label(data, scenario_id))}</strong></td>
              <td>{fmt(num(l_row["baseline_pred_mean"]))}</td>
              <td>{fmt(num(l_row["scenario_pred_mean"]))}</td>
              <td class="delta">{fmt_signed(num(l_row["delta_vs_baseline_mean"]))}</td>
              <td>{fmt(num(x_row["baseline_pred_mean"]))}</td>
              <td>{fmt(num(x_row["scenario_pred_mean"]))}</td>
              <td class="delta">{fmt_signed(num(x_row["delta_vs_baseline_mean"]))}</td>
              <td>{fmt_signed(num(p10["delta_vs_baseline_mean"]))} to {fmt_signed(num(p90["delta_vs_baseline_mean"]))}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th rowspan="2">Scenario</th>
              <th colspan="3">Lancet ETS</th>
              <th colspan="3">X-driven</th>
              <th rowspan="2">Lancet uncertainty</th>
            </tr>
            <tr>
              <th>2050 baseline</th>
              <th>2050 predicted</th>
              <th>Δ vs baseline</th>
              <th>2050 baseline</th>
              <th>2050 predicted</th>
              <th>Δ vs baseline</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
      </div>
    """


def build_region_table(data: dict, rows_119: list[dict], rows_585: list[dict]) -> str:
    rows = []
    for row_119, row_585 in zip(rows_119, rows_585):
        rows.append(
            f"""
            <tr>
              <td><strong>{escape(row_119['region'])}</strong><br /><span class="muted">{escape(row_119['region_en'])}</span></td>
              <td>{fmt_signed(num(row_119['delta_vs_baseline_mean']))}</td>
              <td>{fmt_signed(num(row_585['delta_vs_baseline_mean']))}</td>
              <td>{fmt(num(row_585['scenario_pred_mean']))}</td>
              <td>{escape(row_585['province_n'])}</td>
            </tr>
            """
        )
    return f"""
      <div class="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th>Region</th>
              <th>SSP1-1.9 Δ</th>
              <th>SSP5-8.5 Δ</th>
              <th>SSP5-8.5 predicted</th>
              <th>Province n</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    """


def build_province_table(rows: list[dict], mode: str, table_type: str) -> str:
    if table_type == "gap":
        body = "".join(
            f"""
            <tr>
              <td><strong>{escape(row['Province'])}</strong></td>
              <td>{escape(row['region'])}</td>
              <td>{fmt_signed(row['ssp119'])}</td>
              <td>{fmt_signed(row['ssp585'])}</td>
              <td class="delta">{fmt_signed(row['gap'])}</td>
            </tr>
            """
            for row in rows[:8]
        )
        return f"""
          <div class="table-wrap compact">
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
              <tbody>{body}</tbody>
            </table>
          </div>
        """
    body = "".join(
        f"""
        <tr>
          <td><strong>{escape(row['Province'])}</strong></td>
          <td>{escape(row['region'])}</td>
          <td>{fmt(num(row['scenario_pred']))}</td>
          <td class="delta">{fmt_signed(num(row['delta_vs_baseline']))}</td>
          <td>{fmt_signed(num(row['rx1day_delta']))}</td>
        </tr>
        """
        for row in rows[:8]
    )
    return f"""
      <div class="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th>Province</th>
              <th>Region</th>
              <th>2050 predicted</th>
              <th>Δ vs baseline</th>
              <th>rx1day Δ</th>
            </tr>
          </thead>
          <tbody>{body}</tbody>
        </table>
      </div>
    """


def build_robustness_table(role_rows: list[dict], active_role_id: str | None = None) -> str:
    rows = "".join(
        f"""
        <tr class="{'active-row' if row['role_id'] == active_role_id else ''}">
          <td><strong>{escape(row['role_label'])}</strong></td>
          <td>{fmt(row['baseline_2050'])}</td>
          <td>{fmt_signed(row['ssp119_delta'])}</td>
          <td>{fmt_signed(row['ssp585_delta'])}</td>
          <td>{fmt_signed(row['spread'], 3)}</td>
          <td>{fmt_signed(row['r1_coef'], 3)}</td>
        </tr>
        """
        for row in role_rows
    )
    return f"""
      <div class="table-wrap compact">
        <table>
          <thead>
            <tr>
              <th>Role</th>
              <th>2050 baseline</th>
              <th>SSP1-1.9 Δ</th>
              <th>SSP5-8.5 Δ</th>
              <th>Scenario spread</th>
              <th>R1xday coef</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    """


def build_model_cards(data: dict, active_role_id: str | None = None) -> str:
    cards = []
    for role in data["roles"]:
        coeffs = [row for row in data["coefficients"] if row["role_id"] == role["id"]]
        coeff_rows = "".join(
            f"<li><span>{escape(row['predictor'])}</span><strong>{fmt_signed(num(row['coef']), 3)}</strong></li>"
            for row in coeffs
        )
        variable_chips = "".join(f"<span>{escape(var)}</span>" for var in role["variables"])
        cards.append(
            f"""
            <article class="model-card {'active' if role['id'] == active_role_id else ''}">
              <div class="eyebrow">{escape(role['label'])}</div>
              <h3>{escape(role['scheme_id'])}</h3>
              <p><span class="inline-code">{escape(role['fe_label'])}</span></p>
              <div class="chip-row">{variable_chips}</div>
              <ul class="coef-list">{coeff_rows}</ul>
            </article>
            """
        )
    return "".join(cards)


def build_appendix(data: dict) -> str:
    groups = []
    for group in data["file_catalog"]:
        items = "".join(
            f"""
            <li>
              <a href="{escape(rel(item['path']))}">{escape(item['label'])}</a>
              <span>{escape(item['note'])}</span>
            </li>
            """
            for item in group["items"]
        )
        groups.append(
            f"""
            <details>
              <summary>{escape(group['title'])}</summary>
              <ul class="link-list">{items}</ul>
            </details>
            """
        )
    return "".join(groups)


def build_mode_section(data: dict, story: dict, section_title: str, first_image: str, second_image: str) -> str:
    regional_positive_585 = sum(num(row["delta_vs_baseline_mean"]) > 0 for row in story["regional_585"])
    regional_negative_585 = sum(num(row["delta_vs_baseline_mean"]) < 0 for row in story["regional_585"])
    provincial_positive_585 = sum(num(row["delta_vs_baseline"]) > 0 for row in story["provincial_585"])
    provincial_negative_585 = sum(num(row["delta_vs_baseline"]) < 0 for row in story["provincial_585"])
    return f"""
      <section class="chapter-block">
        <div class="chapter-head">
          <div class="eyebrow">{escape(story['mode_short'])}</div>
          <h3>{escape(section_title)}</h3>
          <p>
            当前下拉框选中的是 <span class="inline-code">{escape(story['role_label'])}</span>。
            2050 baseline 从 {fmt(story['baseline_2024'])} 下降到 {fmt(story['baseline_2050'])}，
            变化 {fmt_signed(story['baseline_change'])}。到 2050 年，情景最低是 {escape(scenario_label(data, story['low_row']['scenario_id']))}
            ({fmt(num(story['low_row']['scenario_pred_mean']))})，最高是 {escape(scenario_label(data, story['high_row']['scenario_id']))}
            ({fmt(num(story['high_row']['scenario_pred_mean']))})，两者相差 {fmt(story['spread'], 3)}。
          </p>
        </div>
        <div class="figure-grid figure-grid-large">
          {figure_block(story['assets']['national'][0]['path'], f"{story['mode_short']} 全国总图", "页面默认模型导出的 Figure 5 风格总图，供快速对照。", True)}
        </div>
        <div class="figure-grid figure-grid-two">
          {figure_block(story['assets']['national'][1]['path'], f"{story['mode_short']} 全国轨迹", "页面默认模型导出的全国轨迹参考图。")}
          {figure_block(story['assets']['national'][2]['path'], f"{story['mode_short']} 2050 情景增量", "页面默认模型导出的 2050 情景增量参考图。")}
        </div>
        <div class="analysis-grid">
          <article class="analysis-card">
            <h4>全国结果怎么读</h4>
            <ul>
              {bullet_items([
                  f"五个 SSP 中，{scenario_label(data, story['low_row']['scenario_id'])} 始终最低，{scenario_label(data, story['high_row']['scenario_id'])} 始终最高。",
                  f"主模型下 2050 的情景 spread 为 {fmt(story['delta_spread'], 3)}，说明当前由 R1xday 带来的情景分化存在，但量级仍明显小于 baseline 本身的长期变化。",
                  "所有 SSP 在 2050 年都仍低于最后观测值，说明当前这版结果里 baseline 下降趋势仍然压过了情景抬升。",
              ])}
            </ul>
          </article>
          <article class="analysis-card">
            <h4>地区与省级空间格局</h4>
            <ul>
              {bullet_items([
                  f"在 SSP5-8.5 下，地区层面最高的是 {story['regional_585'][-1]['region']} ({fmt_signed(num(story['regional_585'][-1]['delta_vs_baseline_mean']))})，最低的是 {story['regional_585'][0]['region']} ({fmt_signed(num(story['regional_585'][0]['delta_vs_baseline_mean']))})。",
                  f"到 SSP5-8.5 时，7 大区里有 {regional_positive_585} 个为正、{regional_negative_585} 个为负；省级则有 {provincial_positive_585} 个为正、{provincial_negative_585} 个为负。",
                  f"省级极值中，抬升最高的是 {story['provincial_585'][-1]['Province']} ({fmt_signed(num(story['provincial_585'][-1]['delta_vs_baseline']))})，下降最明显的是 {story['provincial_585'][0]['Province']} ({fmt_signed(num(story['provincial_585'][0]['delta_vs_baseline']))})。",
              ])}
            </ul>
          </article>
        </div>
        <div class="figure-grid figure-grid-two">
          {figure_block(first_image, f"{story['mode_short']} 地区图", "页面默认模型导出的七大区轨迹参考图。")}
          {figure_block(second_image, f"{story['mode_short']} 地区热图", "页面默认模型导出的七大区 2050 热图参考图。")}
        </div>
        {build_region_table(data, story['regional_119'], story['regional_585'])}
        <div class="figure-grid figure-grid-two">
          {figure_block(story['assets']['provincial'][0]['path'], f"{story['mode_short']} 省级总图", "页面默认模型导出的省级总图参考件。")}
          {figure_block(story['assets']['provincial'][1]['path'], f"{story['mode_short']} 双情景比较", "页面默认模型导出的双情景对照参考图。")}
        </div>
        <div class="two-table-grid">
          <article>
            <h4>SSP5-8.5 下抬升最高的省份</h4>
            {build_province_table(list(reversed(story['provincial_585'])), story['mode_id'], "top")}
          </article>
          <article>
            <h4>SSP5-8.5 与 SSP1-1.9 的最大 gap</h4>
            {build_province_table(story['dual_gap_rows'], story['mode_id'], "gap")}
          </article>
        </div>
      </section>
    """


def build_role_payload(data: dict, role_id: str) -> dict[str, str]:
    stories = {
        "lancet_ets": build_mode_story(data, "lancet_ets", role_id),
        "x_driven": build_mode_story(data, "x_driven", role_id),
    }
    overall = build_overall_story(data, stories)
    role_meta = next((role for role in data["roles"] if role["id"] == role_id), None)
    role_name = role_meta["label"] if role_meta else role_id
    legacy_count, strict_count = archive_mix_counts(data)

    lancet_role_rows = stories["lancet_ets"]["role_rows"]
    selected_lancet = next((row for row in lancet_role_rows if row["role_id"] == role_id), None)
    selected_x = next((row for row in stories["x_driven"]["role_rows"] if row["role_id"] == role_id), None)
    highest_r1 = max(lancet_role_rows, key=lambda row: row["r1_coef"]) if lancet_role_rows else None
    lowest_r1 = min(lancet_role_rows, key=lambda row: row["r1_coef"]) if lancet_role_rows else None

    hero_points = [
        (
            "Current Role",
            role_name,
            f"当前查看的是 {role_name}；下方全国、地区、省级解读和 2050 汇总表都会切到这一组模型结果。",
        ),
        (
            "Baseline gap",
            fmt(overall["baseline_gap_2050"], 3),
            f"在 {role_name} 下，X-driven 比 Lancet ETS 到 2050 高出 {fmt(overall['baseline_gap_2050'], 3)} 个点，主差异仍来自 baseline 生成方式。",
        ),
        (
            "Scenario spread",
            fmt(overall["same_delta_spread"], 3),
            f"{role_name} 下，SSP5-8.5 与 SSP1-1.9 的 2050 national delta spread 为 {fmt(overall['same_delta_spread'], 3)}。",
        ),
        (
            "Regional split",
            f"{overall['regional_high']['region']} {fmt_signed(num(overall['regional_high']['delta_vs_baseline_mean']))}",
            f"在 {role_name} 下，SSP5-8.5 最高的是 {overall['regional_high']['region']}，最低的是 {overall['regional_low']['region']}。",
        ),
    ]

    if selected_lancet and selected_x and highest_r1 and lowest_r1:
        role_intro = (
            f"当前选中 <strong>{escape(role_name)}</strong>。"
            f"Lancet ETS 下 2050 baseline 为 <strong>{fmt(selected_lancet['baseline_2050'])}</strong>，"
            f"SSP5-8.5 相对 baseline 抬升 <strong>{fmt_signed(selected_lancet['ssp585_delta'])}</strong>；"
            f"X-driven 下对应 baseline 为 <strong>{fmt(selected_x['baseline_2050'])}</strong>。"
            f"当前稳健性表覆盖 {data['role_count']} 个归档模型角色，其中原始主线 {legacy_count} 个、严筛扩展 {strict_count} 个；"
            f"R1xday 系数最高的是 {highest_r1['role_label']} ({fmt_signed(highest_r1['r1_coef'], 3)})，"
            f"最低的是 {lowest_r1['role_label']} ({fmt_signed(lowest_r1['r1_coef'], 3)})。"
        )
    else:
        role_intro = f"当前选中 <strong>{escape(role_name)}</strong>。下方整页内容会同步切换到这一组模型结果。"

    judgements_html = f"""
      <div class="summary-grid">
        <article class="summary-card">
          <div class="eyebrow">1. baseline drives level</div>
          <strong>{fmt(overall['baseline_gap_2050'], 3)}</strong>
          <p>{escape(role_name)} 下，X-driven 比 Lancet ETS 在 2050 高出 {fmt(overall['baseline_gap_2050'], 3)}。这一差距主要仍由 baseline 口径驱动，而不是情景增量本身。</p>
        </article>
        <article class="summary-card">
          <div class="eyebrow">2. scenario spread is modest</div>
          <strong>{fmt(overall['same_delta_spread'], 3)}</strong>
          <p>{escape(role_name)} 下，SSP5-8.5 与 SSP1-1.9 的 national delta spread 仍然有限，说明当前由 R1xday 驱动的 SSP 分歧存在，但没有压过 baseline 趋势。</p>
        </article>
        <article class="summary-card">
          <div class="eyebrow">3. spatial pattern is split</div>
          <strong>{escape(overall['regional_high']['region'])}</strong>
          <p>SSP5-8.5 下，地区层面最高是 {escape(overall['regional_high']['region'])} {fmt_signed(num(overall['regional_high']['delta_vs_baseline_mean']))}，最低是 {escape(overall['regional_low']['region'])} {fmt_signed(num(overall['regional_low']['delta_vs_baseline_mean']))}。</p>
        </article>
        <article class="summary-card">
          <div class="eyebrow">4. province heterogeneity is large</div>
          <strong>{escape(overall['province_gap']['Province'])}</strong>
          <p>SSP5-8.5 下抬升最高是 {escape(overall['province_high']['Province'])}，最低是 {escape(overall['province_low']['Province'])}；而 SSP5-8.5 与 SSP1-1.9 的最大 gap 出现在 {escape(overall['province_gap']['Province'])}。</p>
        </article>
      </div>
    """

    baseline_html = f"""
      <div class="mode-compare">
        <article class="mode-card">
          <div class="eyebrow">Lancet ETS</div>
          <h3>先让 AMR 自身沿 ETS 延续</h3>
          <p>当前读取的是 <span class="inline-code">{escape(role_name)}</span>。这版更贴近 Lancet 2023 的写法，更强调结果变量自身历史惯性。</p>
          <div class="formula">Y_it = α_i + λ_t + Σ β_k Z_itk + ε_it
Y^base_it = ETS(Y_i, historical series)
Δ^scenario_it = Σ β_k × (Z^scenario_itk - Z^base_itk)
Y^scenario_it = Y^base_it + Δ^scenario_it</div>
          <ul>{bullet_items([
              f"2024 到 2050 的 national baseline 从 {fmt(stories['lancet_ets']['baseline_2024'])} 下降到 {fmt(stories['lancet_ets']['baseline_2050'])}。",
              f"在 {role_name} 下，SSP5-8.5 相对 baseline 的抬升为 {fmt_signed(selected_lancet['ssp585_delta']) if selected_lancet else '—'}。",
              "适合作为主分析，因为它最容易和参考文献对齐。",
          ])}</ul>
        </article>
        <article class="mode-card">
          <div class="eyebrow">X-driven</div>
          <h3>先用协变量路径重建 baseline</h3>
          <p>当前读取的是 <span class="inline-code">{escape(role_name)}</span>。这版更强调未来协变量路径怎样推开 baseline 水平。</p>
          <div class="formula">Y_it = α_i + λ_t + Σ β_k Z_itk + ε_it
Y^base_it = α_i* + λ_t* + Σ β_k Z^base_itk
Y^scenario_it = α_i* + λ_t* + Σ β_k Z^scenario_itk
If only R1xday varies:
Y^scenario_it = Y^base_it + β_R × (R1xday^scenario_it - R1xday^base_it)</div>
          <ul>{bullet_items([
              f"2024 到 2050 的 national baseline 从 {fmt(stories['x_driven']['baseline_2024'])} 下降到 {fmt(stories['x_driven']['baseline_2050'])}。",
              f"在 {role_name} 下，SSP5-8.5 相对 baseline 的抬升为 {fmt_signed(selected_x['ssp585_delta']) if selected_x else '—'}。",
              "更适合回答未来气候路径怎样拉开情景差距。",
          ])}</ul>
        </article>
      </div>
    """

    national_html = f"""
      {build_mode_section(data, stories['lancet_ets'], '全国结果：Lancet ETS', stories['lancet_ets']['assets']['regional'][0]['path'], stories['lancet_ets']['assets']['regional'][1]['path'])}
      {build_mode_section(data, stories['x_driven'], '全国结果：X-driven', stories['x_driven']['assets']['regional'][0]['path'], stories['x_driven']['assets']['regional'][1]['path'])}
      <article class="note-card">
        <div class="eyebrow">2050 National Comparison</div>
        <h3>把两版放在同一张表里看，差异更容易解释。</h3>
        <p>当前表格已经切换到 <span class="inline-code">{escape(role_name)}</span>。这样可以直接看这个模型下两种 baseline 在同一情景上的水平、增量和不确定性。</p>
        {build_summary_table(data, stories, role_id)}
      </article>
    """

    spatial_html = f"""
      <div class="analysis-grid">
        <article class="analysis-card">
          <h4>地区层面的统一结论</h4>
          <ul>{bullet_items([
              f"在 {role_name} 下，SSP1-1.9 时 7 大区中有 {sum(num(row['delta_vs_baseline_mean']) > 0 for row in stories['lancet_ets']['regional_119'])} 个正值、{sum(num(row['delta_vs_baseline_mean']) < 0 for row in stories['lancet_ets']['regional_119'])} 个负值；到 SSP5-8.5 变成 {sum(num(row['delta_vs_baseline_mean']) > 0 for row in stories['lancet_ets']['regional_585'])} 个正值、{sum(num(row['delta_vs_baseline_mean']) < 0 for row in stories['lancet_ets']['regional_585'])} 个负值。",
              f"华南仍是最高增量区，到 SSP5-8.5 为 {fmt_signed(num(overall['regional_high']['delta_vs_baseline_mean']))}；华中仍最低，到 SSP5-8.5 为 {fmt_signed(num(overall['regional_low']['delta_vs_baseline_mean']))}。",
              "这意味着全国均值上看似温和的变化，实际上是由一部分地区显著抬升、另一部分地区继续走低共同拼出来的。",
          ])}</ul>
        </article>
        <article class="analysis-card">
          <h4>省级层面的统一结论</h4>
          <ul>{bullet_items([
              f"在 {role_name} 下，SSP5-8.5 时 31 省里有 {sum(num(row['delta_vs_baseline']) > 0 for row in stories['lancet_ets']['provincial_585'])} 个省为正、{sum(num(row['delta_vs_baseline']) < 0 for row in stories['lancet_ets']['provincial_585'])} 个省为负。",
              f"抬升最高的是 {escape(overall['province_high']['Province'])} {fmt_signed(num(overall['province_high']['delta_vs_baseline']))}，下降最低的是 {escape(overall['province_low']['Province'])} {fmt_signed(num(overall['province_low']['delta_vs_baseline']))}。",
              f"双情景 gap 最大的省份是 {escape(overall['province_gap']['Province'])}，说明它对未来气候路径分化最敏感。",
          ])}</ul>
        </article>
      </div>
    """

    robustness_intro = role_intro
    robustness_tables_html = f"""
      <div class="robust-grid">
        <article class="note-card">
          <div class="eyebrow">Lancet ETS Roles</div>
          <h3>{data['role_count']} 个 role 的 2050 对照</h3>
          {build_robustness_table(stories['lancet_ets']['role_rows'], role_id)}
        </article>
        <article class="note-card">
          <div class="eyebrow">X-driven Roles</div>
          <h3>{data['role_count']} 个 role 的 2050 对照</h3>
          {build_robustness_table(stories['x_driven']['role_rows'], role_id)}
        </article>
      </div>
    """

    return {
        "role_name": role_name,
        "role_intro": role_intro,
        "hero_points_html": "".join(
            f'<article class="hero-card"><div class="eyebrow">{escape(title)}</div><strong>{escape(value)}</strong><p>{escape(note)}</p></article>'
            for title, value, note in hero_points
        ),
        "judgements_html": judgements_html,
        "baseline_html": baseline_html,
        "national_html": national_html,
        "spatial_html": spatial_html,
        "robustness_intro": robustness_intro,
        "robustness_tables_html": robustness_tables_html,
        "model_cards_html": build_model_cards(data, role_id),
    }


def build_html(data: dict) -> str:
    default_role = primary_role_id(data)
    role_payloads = {role["id"]: build_role_payload(data, role["id"]) for role in data["roles"]}
    role_options = "".join(
        f'<option value="{escape(role["id"])}" {"selected" if role["id"] == default_role else ""}>{escape(role["label"])}</option>'
        for role in data["roles"]
    )
    role_payload_json = json.dumps(role_payloads, ensure_ascii=False).replace("</", "<\\/")
    legacy_count, strict_count = archive_mix_counts(data)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>6 未来情景分析</title>
  <style>
    :root {{
      --bg: #f6f7fb;
      --panel: #ffffff;
      --ink: #141926;
      --muted: #5a6477;
      --line: #dbe2ec;
      --line-strong: #c7d3e1;
      --primary: #113a8f;
      --accent: #b45309;
      --green: #0f766e;
      --shadow: 0 20px 48px rgba(14, 26, 52, 0.08);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 14px;
      --sans: "Fira Sans", "Segoe UI", "Trebuchet MS", sans-serif;
      --mono: "Fira Code", Consolas, "SFMono-Regular", monospace;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(17, 58, 143, 0.10), transparent 26%),
        radial-gradient(circle at top right, rgba(180, 83, 9, 0.10), transparent 24%),
        linear-gradient(180deg, #fbfcff 0%, #f4f7fb 100%);
      color: var(--ink);
      font-family: var(--sans);
    }}
    .page {{
      width: min(1500px, calc(100vw - 28px));
      margin: 18px auto 40px;
      display: grid;
      gap: 18px;
    }}
    .panel, .section {{
      background: rgba(255, 255, 255, 0.90);
      border: 1px solid rgba(255, 255, 255, 0.78);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .hero {{
      border-radius: var(--radius-xl);
      overflow: hidden;
      padding: 34px;
      background:
        radial-gradient(circle at right top, rgba(255,255,255,0.18), transparent 32%),
        linear-gradient(135deg, #111827 0%, #163d8f 56%, #1f5ca8 100%);
      color: #f8fbff;
      display: grid;
      gap: 24px;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 24px;
      align-items: start;
    }}
    .eyebrow {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      opacity: 0.72;
      margin-bottom: 12px;
    }}
    h1, h2, h3, h4, p {{
      margin: 0;
    }}
    h1 {{
      font-size: clamp(38px, 5vw, 68px);
      line-height: 0.98;
      letter-spacing: -0.04em;
      max-width: 10ch;
    }}
    h2 {{
      font-size: clamp(28px, 2.8vw, 40px);
      line-height: 1.05;
      letter-spacing: -0.03em;
    }}
    h3 {{
      font-size: 24px;
      line-height: 1.15;
      letter-spacing: -0.02em;
    }}
    h4 {{
      font-size: 17px;
      line-height: 1.2;
    }}
    p, li {{
      color: var(--muted);
      line-height: 1.75;
      font-size: 15px;
    }}
    .hero p {{
      color: rgba(248, 251, 255, 0.90);
      max-width: 68ch;
    }}
    .hero-points {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    .hero-card {{
      padding: 18px;
      border-radius: 18px;
      background: rgba(255,255,255,0.10);
      border: 1px solid rgba(255,255,255,0.12);
      display: grid;
      gap: 8px;
    }}
    .hero-card strong {{
      font-size: clamp(22px, 3vw, 34px);
      line-height: 1;
      color: #ffffff;
      display: block;
    }}
    .hero-side {{
      display: grid;
      gap: 12px;
    }}
    .hero-note {{
      padding: 18px;
      border-radius: 18px;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.12);
    }}
    .role-select {{
      width: 100%;
      margin-top: 10px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid rgba(255,255,255,0.18);
      background: rgba(10, 18, 34, 0.34);
      color: #f8fbff;
      font: inherit;
    }}
    .role-select option {{
      color: #141926;
    }}
    .role-summary {{
      margin-top: 10px;
      font-size: 14px;
    }}
    .nav {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
    }}
    .nav a {{
      display: inline-flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 13px 15px;
      border-radius: 16px;
      text-decoration: none;
      color: var(--ink);
      background: rgba(255,255,255,0.85);
      border: 1px solid var(--line);
      font-weight: 700;
    }}
    .section {{
      border-radius: var(--radius-xl);
      padding: 28px;
      display: grid;
      gap: 20px;
    }}
    .section-head {{
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 22px;
      align-items: end;
    }}
    .summary-grid, .analysis-grid, .figure-grid, .mode-grid, .robust-grid, .appendix-grid, .two-table-grid {{
      display: grid;
      gap: 16px;
    }}
    .summary-grid {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }}
    .summary-card, .analysis-card, .note-card {{
      padding: 18px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.78);
    }}
    .summary-card strong {{
      display: block;
      font-size: 28px;
      line-height: 1;
      color: var(--primary);
      margin: 6px 0 8px;
    }}
    .mode-compare {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .mode-card {{
      padding: 22px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(245,248,253,0.92));
      display: grid;
      gap: 12px;
    }}
    .mode-card .inline-code,
    .inline-code {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      background: rgba(17, 58, 143, 0.08);
      border: 1px solid rgba(17, 58, 143, 0.12);
      font-family: var(--mono);
      font-size: 12px;
      color: var(--primary);
    }}
    .formula {{
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(20, 25, 38, 0.04);
      border: 1px solid var(--line);
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.75;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: #263248;
    }}
    .chapter-block {{
      display: grid;
      gap: 16px;
      padding: 24px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.82);
    }}
    .chapter-head {{
      display: grid;
      gap: 10px;
    }}
    .figure-grid-large {{
      grid-template-columns: 1fr;
    }}
    .figure-grid-two, .mode-grid, .robust-grid, .two-table-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .figure-card {{
      margin: 0;
      border-radius: 20px;
      overflow: hidden;
      border: 1px solid var(--line-strong);
      background: #f7fafc;
      box-shadow: 0 12px 32px rgba(17, 24, 39, 0.05);
    }}
    .figure-card img {{
      width: 100%;
      height: auto;
      display: block;
      background: #eef3f8;
    }}
    .hero-figure img {{
      max-height: 740px;
      object-fit: contain;
    }}
    figcaption {{
      display: grid;
      gap: 4px;
      padding: 14px 16px 16px;
      border-top: 1px solid var(--line);
      background: rgba(255,255,255,0.92);
    }}
    figcaption strong {{
      color: var(--ink);
      font-size: 15px;
    }}
    figcaption span {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.88);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 760px;
    }}
    .compact table {{
      min-width: 620px;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
      line-height: 1.55;
    }}
    thead th {{
      background: #eef3f8;
      color: #2b3a4e;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .delta {{
      color: var(--accent);
      font-weight: 700;
    }}
    .muted {{
      color: var(--muted);
    }}
    .active-row {{
      background: rgba(17, 58, 143, 0.06);
    }}
    .coef-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 8px;
    }}
    .coef-list li {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 8px 0;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
    }}
    .coef-list li:last-child {{
      border-bottom: none;
    }}
    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip-row span {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(17,58,143,0.06);
      border: 1px solid rgba(17,58,143,0.10);
      font-size: 12px;
      color: #2f456f;
    }}
    .model-card.active {{
      border-color: rgba(17, 58, 143, 0.26);
      background: linear-gradient(180deg, rgba(232, 240, 255, 0.95), rgba(245,248,253,0.98));
      box-shadow: 0 12px 30px rgba(17, 58, 143, 0.10);
    }}
    details {{
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.82);
      overflow: hidden;
    }}
    summary {{
      cursor: pointer;
      padding: 16px 18px;
      font-weight: 700;
      list-style: none;
      background: rgba(17,58,143,0.04);
    }}
    summary::-webkit-details-marker {{ display: none; }}
    .link-list {{
      margin: 0;
      padding: 8px 18px 18px 34px;
      display: grid;
      gap: 10px;
    }}
    .link-list a {{
      color: var(--primary);
      text-decoration: none;
      font-weight: 700;
    }}
    .footer {{
      padding: 4px 0 10px;
      text-align: center;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 1100px) {{
      .hero-grid,
      .hero-points,
      .section-head,
      .mode-compare,
      .mode-grid,
      .robust-grid,
      .analysis-grid,
      .figure-grid-two,
      .summary-grid,
      .two-table-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 760px) {{
      .page {{
        width: calc(100vw - 12px);
        margin: 8px auto 18px;
      }}
      .hero, .section {{
        padding: 18px;
      }}
      h1 {{
        max-width: unset;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="hero panel">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">6 未来情景分析</div>
          <h1>把未来情景结果写成一页能读清的研究报告。</h1>
          <p>
            这页保留原来的完整报告式结构：先讲最关键的判断，再把两种 baseline 的全国结果摆在一起，然后往下看地区、再看省级，最后回到稳健性和方法来源。
            页面默认还是正文入口模型，但现在可以在开头直接切换到其它模型角色，查看这一整页在对应模型下的结论和表格。
          </p>
        </div>
        <div class="hero-side">
          <div class="hero-note">
            <strong>模型切换</strong>
            <p>默认展示正文入口模型。切换后，下方“关键判断 / baseline 解释 / 全国 / 空间 / 稳健性”会整页同步替换成所选模型版本。</p>
            <select id="roleSelect" class="role-select">{role_options}</select>
            <p class="role-summary" id="roleSummary"></p>
          </div>
          <div class="hero-note">
            <strong>当前边界</strong>
            <p>当前 SSP 情景真正进入未来路径的协变量只有 <span class="inline-code">R1xday</span>；因此两种 baseline 的情景增量通常非常接近，主要差异来自 baseline 水平本身。</p>
          </div>
          <div class="hero-note">
            <strong>怎么看静态图</strong>
            <p>页面里的 PNG 仍保留原来的默认模型导出图，用来维持原报告页的完整阅读感；而文字解读、2050 汇总表、地区和省级排序会随下拉模型同步刷新。</p>
          </div>
          <div class="hero-note">
            <strong>稳健性范围</strong>
            <p>当前纳入 {data['role_count']} 个归档模型角色，其中原始主线 {legacy_count} 个、严筛扩展 {strict_count} 个。因为未来只让 R1xday 变动，所以不同模型的情景敏感度主要看历史 R1xday 系数大小。</p>
          </div>
        </div>
      </div>
      <div class="hero-points" id="heroPoints"></div>
    </header>

    <nav class="nav">
      <a href="#judgements"><span>Key Judgements</span><span>01</span></a>
      <a href="#baseline"><span>Baseline Logic</span><span>02</span></a>
      <a href="#national"><span>National Results</span><span>03</span></a>
      <a href="#spatial"><span>Regional & Provincial</span><span>04</span></a>
      <a href="#robustness"><span>Robustness</span><span>05</span></a>
      <a href="#appendix"><span>Appendix</span><span>06</span></a>
    </nav>

    <section class="section" id="judgements">
      <div class="section-head">
        <div>
          <div class="eyebrow">Key Judgements</div>
          <h2>这页最重要的判断，不需要先读表就能抓到。</h2>
        </div>
        <p>
          这里会随着所选模型一起刷新。这样你不用离开原来的阅读顺序，就能直接比较“换一套模型角色之后，最值得先说清的事实有没有变”。
        </p>
      </div>
      <div id="judgementsContent"></div>
    </section>

    <section class="section" id="baseline">
      <div class="section-head">
        <div>
          <div class="eyebrow">Baseline Logic</div>
          <h2>先把两种 baseline 分清，再去看结果，结论才不会串。</h2>
        </div>
        <p>
          两种 baseline 共享同一套历史 FE 系数、同一套未来 R1xday 情景和同一套全国平均口径。真正变的是“未来 baseline 到底由什么生成”，而模型切换会改变历史系数和固定效应配置。
        </p>
      </div>
      <div id="baselineContent"></div>
    </section>

    <section class="section" id="national">
      <div class="section-head">
        <div>
          <div class="eyebrow">National Results</div>
          <h2>全国结果的核心不是“哪条线更高”，而是 baseline 与情景抬升分别贡献了多少。</h2>
        </div>
        <p>
          下拉切换后，这一整段的解释、2050 汇总表、地区与省级排序都会切到对应模型。原来的静态 PNG 继续保留在页内，方便和默认模型版本对照。
        </p>
      </div>
      <div id="nationalContent"></div>
    </section>

    <section class="section" id="spatial">
      <div class="section-head">
        <div>
          <div class="eyebrow">Spatial Results</div>
          <h2>真正决定“全国平均长什么样”的，是空间分异，而不是一条全国线本身。</h2>
        </div>
        <p>
          这部分会直接切换到所选模型的地区与省级结论，帮助你快速判断空间格局是不是只依赖某个模型设定。
        </p>
      </div>
      <div id="spatialContent"></div>
    </section>

    <section class="section" id="robustness">
      <div class="section-head">
        <div>
          <div class="eyebrow">Robustness</div>
          <h2>稳健性不是附录装饰，它直接告诉你情景敏感度到底是谁在驱动。</h2>
        </div>
        <p id="robustnessIntro"></p>
      </div>
      <div id="robustnessTables"></div>
      <div class="section-head">
        <div>
          <div class="eyebrow">Model Provenance</div>
          <h2>每个 role 用了什么变量、对应什么系数，这里都摆出来。</h2>
        </div>
        <p>
          当前高亮的是你在顶部下拉框里选中的模型。由于未来情景现在只更改 R1xday，所以最值得盯住的仍然是各 role 的 R1xday 系数大小。
        </p>
      </div>
      <div class="mode-grid" id="modelCards"></div>
    </section>

    <section class="section" id="appendix">
      <div class="section-head">
        <div>
          <div class="eyebrow">Appendix</div>
          <h2>方法边界、运行命令和关键文件入口。</h2>
        </div>
        <p>
          图和分析已经全部放在正文里了。下面只保留你在复核、补图或写方法时真正会用到的说明和文件入口，不再把“打开文件”当成正文阅读流程的一部分。
        </p>
      </div>
      <div class="analysis-grid">
        <article class="analysis-card">
          <h4>当前结果的解释边界</h4>
          <ul>{bullet_items([
              "当前 SSP 情景真正接入未来路径的协变量只有 R1xday，因此这版更像是在回答“未来极端降水路径会把 AMR 推开多少”。",
              "抗菌药物使用、供水/卫生、经济和卫生投入等变量仍沿 baseline 路径延续，所以这版不能被解释成完整的多协变量 SSP 预测系统。",
              "如果后续把这些外部输入补齐，这个页面的框架仍然适用，只需要把 narrative 里的“仅 R1xday 变化”改掉。",
          ])}</ul>
        </article>
        <article class="analysis-card">
          <h4>最常用命令</h4>
          <div class="formula">python -X utf8 ".\\6 未来情景分析\\scripts\\run_future_scenario_projection.py"
python -X utf8 ".\\6 未来情景分析\\scripts\\run_regional_future_figure5.py"
python -X utf8 ".\\6 未来情景分析\\scripts\\run_provincial_future_figure.py"
python -X utf8 ".\\6 未来情景分析\\scripts\\run_dual_scenario_compare_figure.py"</div>
        </article>
      </div>
      {build_appendix(data)}
    </section>

    <div class="footer">Generated at {escape(str(data['generated_at']))} · Source: 6 未来情景分析</div>
  </div>
  <script>
    const ROLE_CONTENT = {role_payload_json};
    const DEFAULT_ROLE = {json.dumps(default_role, ensure_ascii=False)};

    function renderRole(roleId) {{
      const payload = ROLE_CONTENT[roleId] || ROLE_CONTENT[DEFAULT_ROLE];
      if (!payload) return;
      document.getElementById("roleSelect").value = roleId;
      document.getElementById("roleSummary").innerHTML = payload.role_intro;
      document.getElementById("heroPoints").innerHTML = payload.hero_points_html;
      document.getElementById("judgementsContent").innerHTML = payload.judgements_html;
      document.getElementById("baselineContent").innerHTML = payload.baseline_html;
      document.getElementById("nationalContent").innerHTML = payload.national_html;
      document.getElementById("spatialContent").innerHTML = payload.spatial_html;
      document.getElementById("robustnessIntro").innerHTML = payload.robustness_intro;
      document.getElementById("robustnessTables").innerHTML = payload.robustness_tables_html;
      document.getElementById("modelCards").innerHTML = payload.model_cards_html;
    }}

    const roleSelect = document.getElementById("roleSelect");
    roleSelect.addEventListener("change", (event) => {{
      const nextRole = event.target.value || DEFAULT_ROLE;
      renderRole(nextRole);
      const url = new URL(window.location.href);
      url.searchParams.set("role", nextRole);
      window.history.replaceState(null, "", url.toString());
    }});

    const initialRole = new URL(window.location.href).searchParams.get("role");
    renderRole(initialRole && ROLE_CONTENT[initialRole] ? initialRole : DEFAULT_ROLE);
  </script>
</body>
</html>
"""
    return html


def main() -> None:
    data = build_data()
    html = build_html(data)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Wrote dashboard report to {OUT_FILE}")


if __name__ == "__main__":
    main()
