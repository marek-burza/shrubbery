"""Readers for the score and event CSVs shared by analyze_scores.py and plot_scores.py."""

# Code structure, to keep when editing this file:
# - Write code as small functions whose names state exactly what each does
#   (e.g. `extract_zip_safely`, `report_unused_runtime_dependencies`).
# - Keep code and functions short, concise, understandable and readable to a single SWE
#   reviewing: roughly under 30 lines, one responsibility each. No long monolithic functions.
# - Why: the code is audited personally by its maintainer.

import pandas as pd

HORIZON_DAYS = {
    'v2_corr20': 20,
    'mmc': 20,
    'fnc_v3': 20,
    'cort20': 20,
    'corr_w_meta_model': 1,
    'corr60': 60,
    'mmc60': 60,
    'bmc': 60,
    'corj60': 60,
    'neutral_corr': 60,
    'neutral_mmc': 60,
    'neutral_bmc': 60,
}
DEFAULT_HORIZON_DAYS = 20


def horizon_days(metric: str) -> int:
    return HORIZON_DAYS.get(metric, DEFAULT_HORIZON_DAYS)


def read_latest_score_snapshots(path: str) -> pd.DataFrame:
    scores = pd.read_csv(path, parse_dates=['round_date'])
    scores['date'] = scores['round_date'].dt.tz_convert(None)
    return scores.sort_values('day').drop_duplicates(
        ['model', 'round', 'metric'], keep='last'
    )


def read_events(path: str) -> pd.DataFrame:
    events = pd.read_csv(path)
    events['date'] = pd.to_datetime(
        events['date'], utc=True, format='ISO8601'
    ).dt.tz_convert(None)
    return events.sort_values('date')
