from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SECTION_DIR = ROOT / "6 未来情景分析"
DATA_RAW_DIR = SECTION_DIR / "data_raw"
DATA_PROCESSED_DIR = SECTION_DIR / "data_processed"
LOG_DIR = SECTION_DIR / "logs"
DOCS_DIR = SECTION_DIR / "docs"
RESULTS_DIR = SECTION_DIR / "results"

AMR_PATH = ROOT / "amr_rate.csv"
X_PATH = ROOT / "climate_social_eco.csv"

COUNTERFACTUAL_RESULT_ROOT = ROOT / "5 反事实推演" / "results"
SELECTED_MODELS_DIR = COUNTERFACTUAL_RESULT_ROOT

RX1DAY_TIMESERIES_PATH = DATA_PROCESSED_DIR / "cckp_rx1day_timeseries_panel.csv"
TA_FUTURE_PATH = DATA_PROCESSED_DIR / "TA_future_panel.csv"
PROVINCE_TAS_SSP_PATH = DATA_PROCESSED_DIR / "ssp_province_mean_tas_panel.csv"

HISTORICAL_START_YEAR = 2014
HISTORICAL_END_YEAR = 2023
LAST_OBSERVED_YEAR = HISTORICAL_END_YEAR
FUTURE_START_YEAR = 2024
FUTURE_END_YEAR = 2050

DEFAULT_OUTCOME = "AMR_AGG_RAW"
DEFAULT_MODEL_SOURCE_OUTCOME = "AMR_AGG"
DEFAULT_SINGLE_OUTCOME_SCALE = "zscore"
DEFAULT_MODEL_ROLES: list[str] = []
DEFAULT_BASELINE_MODES = ["lancet_ets", "x_driven"]

BASELINE_MODE_LABELS = {
    "lancet_ets": "Lancet-like ETS baseline",
    "x_driven": "X-driven / Nature-like simplified baseline",
}

BASELINE_MODE_DESCRIPTIONS = {
    "lancet_ets": "Use ETS on the outcome itself as the future baseline, then add scenario deltas from future climate paths such as R1xday and supported temperature proxies.",
    "x_driven": "Use future covariate paths as the baseline driver; baseline covariates follow ETS extensions, then future AMR is reconstructed from the historical association model and perturbed by supported climate scenario inputs.",
}

BASELINE_OUTCOME_METHOD = "ets"
BASELINE_COVARIATE_METHOD = "ets"
ETS_TREND = "add"
ETS_DAMPED_TREND = True
MIN_SERIES_POINTS_FOR_TREND = 4

EXTERNAL_ALIGNMENT_METHOD = "mean_bias"
EXTERNAL_ALIGNMENT_MIN_OVERLAP = 3

RX1DAY_VARIABLE_NAME = "R1xday"
TA_VARIABLE_NAME = "TA（°C）"
PROVINCE_TAS_VARIABLE_NAME = "省平均气温"
CONTROLLED_FUTURE_VARIABLES = [
    RX1DAY_VARIABLE_NAME,
    TA_VARIABLE_NAME,
    PROVINCE_TAS_VARIABLE_NAME,
]
RX1DAY_SCENARIOS = ["ssp119", "ssp126", "ssp245", "ssp370", "ssp585"]
RX1DAY_STATISTICS = ["median", "p10", "p90"]
RX1DAY_MAIN_STATISTIC = "median"

SCENARIO_LABELS = {
    "ssp119": "SSP1-1.9",
    "ssp126": "SSP1-2.6",
    "ssp245": "SSP2-4.5",
    "ssp370": "SSP3-7.0",
    "ssp585": "SSP5-8.5",
}

BASELINE_SCENARIO = {
    "scenario_id": "baseline_ets",
    "scenario_label": "基线趋势延续（ETS）",
    "scenario_family": "baseline",
    "description": "不额外施加未来情景调整，仅按历史 AMR 趋势的 ETS 基线外推。",
    "rx1day_source_scenario": None,
    "tas_source_scenario": None,
    "adjustments": {},
}

CLIMATE_SCENARIOS = [
    {
        "scenario_id": scenario_id,
        "scenario_label": f"{SCENARIO_LABELS[scenario_id]}（climate）",
        "scenario_family": "climate_ssp",
        "description": f"将未来 R1xday 与已支持的温度路径替换为 CCKP {SCENARIO_LABELS[scenario_id]} 的省级年度序列，其余协变量保留基线延续路径。",
        "rx1day_source_scenario": scenario_id,
        "tas_source_scenario": scenario_id,
        "adjustments": {},
    }
    for scenario_id in RX1DAY_SCENARIOS
]

ACTIVE_SCENARIOS = [BASELINE_SCENARIO, *CLIMATE_SCENARIOS]
ACTIVE_SCENARIO_IDS = [item["scenario_id"] for item in ACTIVE_SCENARIOS]

# 论文中的死亡负担模块需要额外的感染死亡数和 RR 输入；当前仓库中尚未提供，
# 因此这里只保留可扩展接口，默认不启用。
MORTALITY_MODULE = {
    "enabled": False,
    "infection_deaths_path": RESULTS_DIR / "inputs" / "province_infection_deaths.csv",
    "relative_risk": None,
}

CCKP_PROVINCE_TO_CN = {
    "Anhui Sheng": "安徽",
    "Beijing Shi": "北京",
    "Chongqing Shi": "重庆",
    "Fujian Sheng": "福建",
    "Gansu Sheng": "甘肃",
    "Guangdong Sheng": "广东",
    "Guangxi Zhuangzu Zizhiqu": "广西",
    "Guizhou Sheng": "贵州",
    "Hainan Sheng": "海南",
    "Hebei Sheng": "河北",
    "Heilongjiang Sheng": "黑龙江",
    "Henan Sheng": "河南",
    "Hong Kong, SAR": "香港",
    "Hubei Sheng": "湖北",
    "Hunan Sheng": "湖南",
    "Jiangsu Sheng": "江苏",
    "Jiangxi Sheng": "江西",
    "Jilin Sheng": "吉林",
    "Liaoning Sheng": "辽宁",
    "Macau, SAR": "澳门",
    "Nei Mongol Zizhiqu": "内蒙古",
    "Ningxia Huizu Zizhiqu": "宁夏",
    "Qinghai Sheng": "青海",
    "Shaanxi Sheng": "陕西",
    "Shandong Sheng": "山东",
    "Shanghai Shi": "上海",
    "Shanxi Sheng": "山西",
    "Sichuan Sheng": "四川",
    "Taiwan Sheng": "台湾",
    "Tianjin Shi": "天津",
    "Xinjiang Uygur Zizhiqu": "新疆",
    "Xizang Zizhiqu": "西藏",
    "Yunnan Sheng": "云南",
    "Zhejiang Sheng": "浙江",
}

HISTORICAL_PROVINCE_EXCLUDE = {"全国", "μ", "σ"}
FUTURE_PROVINCE_EXCLUDE = {"香港", "澳门", "台湾"}


def ensure_directories() -> None:
    for path in (SECTION_DIR, DATA_RAW_DIR, DATA_PROCESSED_DIR, LOG_DIR, DOCS_DIR, RESULTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def resolve_results_output_dir(outcome: str) -> Path:
    if outcome == DEFAULT_OUTCOME:
        return RESULTS_DIR
    return RESULTS_DIR / outcome
