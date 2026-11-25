"""Attribution statistics for Numerai live scores around model-change events.

Input: a long-format CSV from `numerai-scores --format csv` (columns model, round,
round_date, metric, day, value, percentile, ...) covering the family of models plus
one or more reference models (e.g. integration_test, v6_lgbm_jupiter60), and an
events CSV with columns date,id,scope,label (date: ISO 8601 UTC date-time; scope: all | target | retrain | <model>).

Prints a markdown report: coverage, noise floor, regime exposure, before/after tests
for family-wide events (family vs reference), difference-in-differences tests for
model-specific events (model vs rest of family), the gap of each model to a control
model, and a biweekly table. Only final scores are used unless --include-partial.

Usage: python analyze_scores.py --scores scores.csv --events events.csv \
    [--models again bail ...] --reference integration_test v6_lgbm_jupiter60 [--metric neutral_bmc] [--corr-metric neutral_corr] \
    [--control again] [--since 2025-08-01] [--window 42] [--include-partial]
"""

# Code structure, to keep when editing this file:
# - Write code as small functions whose names state exactly what each does
#   (e.g. `extract_zip_safely`, `report_unused_runtime_dependencies`).
# - Keep code and functions short, concise, understandable and readable to a single SWE
#   reviewing: roughly under 30 lines, one responsibility each. No long monolithic functions.
# - Why: the code is audited personally by its maintainer.

import argparse
import sys
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
from score_data import (
    DEFAULT_HORIZON_DAYS,
    HORIZON_DAYS,
    horizon_days,
    read_events,
    read_latest_score_snapshots,
)

CALENDAR_DAYS_PER_INDEPENDENT_BLOCK = {20: 28, 60: 84, 1: 7}
MIN_SCORED_ROUNDS_AFTER_CONTROL_START = 10
MIN_ROUNDS_FOR_REGIME_FIT = 10
TIMESTAMP = '%Y-%m-%dT%H:%M:%SZ'


@dataclass
class Analysis:
    scores: pd.DataFrame
    events: pd.DataFrame
    family: list[str]
    references: list[str]
    metric: str
    corr_metric: str
    window: int
    include_partial: bool
    control: str | None
    values: pd.DataFrame
    corr: pd.DataFrame

    @property
    def reference(self) -> str:
        return self.references[0]

    @property
    def block_days(self) -> int:
        return independent_block_days(self.metric)

    @property
    def family_mean(self) -> pd.Series:
        return self.values[self.family].mean(axis=1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--scores', required=True)
    parser.add_argument('--events', required=True)
    parser.add_argument(
        '--models',
        nargs='+',
        help='Family models (default: every model that is not a reference)',
    )
    parser.add_argument(
        '--reference',
        nargs='+',
        required=True,
        help='Regime reference model(s); first is primary',
    )
    parser.add_argument(
        '--metric', default='bmc', help='Attribution metric (default bmc)'
    )
    parser.add_argument(
        '--corr-metric',
        default='v2_corr20',
        help='Correlation metric for regime checks',
    )
    parser.add_argument(
        '--control', help='Control model to compare every other model against'
    )
    parser.add_argument('--since')
    parser.add_argument(
        '--window', type=int, default=42, help='Days before/after an event'
    )
    parser.add_argument('--include-partial', action='store_true')
    return parser.parse_args()


def load_scores(
    path: str, include_partial: bool, since: str | None
) -> pd.DataFrame:
    scores = read_latest_score_snapshots(path)
    scores['final'] = scores['day'] >= scores['metric'].map(
        HORIZON_DAYS
    ).fillna(DEFAULT_HORIZON_DAYS)
    if not include_partial:
        scores = scores[scores['final']]
    if since:
        scores = scores[scores['date'] >= pd.Timestamp(since)]
    return scores


def metric_by_date_and_model(
    scores: pd.DataFrame, metric: str, field: str = 'value'
) -> pd.DataFrame:
    subset = scores[scores['metric'] == metric]
    return subset.pivot_table(
        index='date', columns='model', values=field, aggfunc='mean'
    ).sort_index()


def build_analysis(args: argparse.Namespace) -> Analysis:
    scores = load_scores(args.scores, args.include_partial, args.since)
    return Analysis(
        scores=scores,
        events=read_events(args.events),
        family=sorted(
            args.models or set(scores['model']) - set(args.reference)
        ),
        references=args.reference,
        metric=args.metric,
        corr_metric=args.corr_metric,
        window=args.window,
        include_partial=args.include_partial,
        control=args.control,
        values=metric_by_date_and_model(scores, args.metric),
        corr=metric_by_date_and_model(scores, args.corr_metric),
    )


def independent_block_days(metric: str) -> int:
    return CALENDAR_DAYS_PER_INDEPENDENT_BLOCK[horizon_days(metric)]


def std_of_block_means(series: pd.Series, block_days: int) -> float:
    blocks = series.dropna().resample(f'{block_days}D').mean().dropna()
    return float(blocks.std()) if len(blocks) > 2 else float('nan')


def window_mean(
    series: pd.Series, start: pd.Timestamp, end: pd.Timestamp
) -> tuple[float, int]:
    values = series[(series.index >= start) & (series.index < end)].dropna()
    return (float(values.mean()) if len(values) else float('nan')), len(values)


def before_after_test(
    series: pd.Series,
    when: pd.Timestamp,
    window: int,
    sigma: float,
    block_days: int,
) -> dict:
    span = timedelta(days=window)
    before, n_before = window_mean(series, when - span, when)
    after, n_after = window_mean(series, when, when + span)
    blocks = max(window / block_days, 1.0)
    se = np.sqrt(2) * sigma / np.sqrt(blocks)
    delta = after - before
    return {
        'before': before,
        'after': after,
        'delta': delta,
        'z': delta / se if se > 0 else np.nan,
        'n_before': n_before,
        'n_after': n_after,
    }


def format_x1000(value: float, scale: float = 1000) -> str:
    return 'nan' if pd.isna(value) else f'{value * scale:+.1f}'


def significance_verdict(z: float) -> str:
    if pd.isna(z):
        return 'insufficient data'
    return (
        'likely real'
        if abs(z) >= 2
        else ('suggestive' if abs(z) >= 1 else 'within noise')
    )


def report_header(a: Analysis) -> list[str]:
    return [
        f'# Attribution report: metric `{a.metric}` (x1000), regime via `{a.corr_metric}` of `{a.reference}`\n',
        (
            f'Final scores only: {not a.include_partial}. Window ±{a.window} days. '
            f'Independent block ≈ {a.block_days} calendar days.\n'
        ),
    ]


def coverage_row(model: str, rows: pd.DataFrame) -> str:
    return (
        f'| {model} | {rows["round"].min()} | {rows["round"].max()} | {rows["round"].nunique()} | '
        f'{rows["date"].max():{TIMESTAMP}} |'
    )


def coverage_section(a: Analysis) -> list[str]:
    lines = [
        '## Coverage\n\n| model | first | last | rounds | last final round date |\n|---|---|---|---|---|'
    ]
    for model in a.family + a.references:
        rows = a.scores[
            (a.scores['model'] == model) & (a.scores['metric'] == a.metric)
        ]
        if len(rows):
            lines.append(coverage_row(model, rows))
    return lines


def noise_floor_per_model(a: Analysis) -> dict[str, float]:
    return {
        m: std_of_block_means(a.values[m], a.block_days)
        for m in a.family
        if m in a.values
    }


def median_noise_floor(a: Analysis) -> float:
    return float(np.nanmedian(list(noise_floor_per_model(a).values())))


def noise_floor_section(a: Analysis) -> list[str]:
    per_model = ', '.join(
        f'{m} {format_x1000(s)}' for m, s in noise_floor_per_model(a).items()
    )
    return [
        (
            f'\n## Noise floor\n\nMedian std of {a.block_days}-day block means of `{a.metric}`: '
            f'**{format_x1000(median_noise_floor(a))}** (per model: {per_model}). '
            'A window mean differs by noise alone with roughly this std / sqrt(blocks).\n'
        )
    ]


def regime_exposure_row(
    a: Analysis, corr_pct: pd.DataFrame, model: str
) -> str | None:
    pair = a.corr[[model, a.reference]].dropna()
    pct = corr_pct[[model, a.reference]].dropna()
    if len(pair) <= MIN_ROUNDS_FOR_REGIME_FIT:
        return None
    beta = np.polyfit(pair[a.reference], pair[model], 1)[0]
    return (
        f'| {model} | {pair[model].corr(pair[a.reference]):+.2f} | {beta:+.2f} | '
        f'{pct[model].corr(pct[a.reference]):+.2f} |'
    )


def regime_exposure_section(a: Analysis) -> list[str]:
    lines = [
        '## Regime exposure\n\n| model | rho(corr, ref corr) | beta | rho(pct, ref pct) |\n|---|---|---|---|'
    ]
    corr_pct = metric_by_date_and_model(a.scores, a.corr_metric, 'percentile')
    rows = (regime_exposure_row(a, corr_pct, model) for model in a.family)
    lines += [row for row in rows if row]
    lines.append(
        '\nPercentiles swing with the crowd: a strongly negative rho(pct) with near-zero rho(corr) '
        'means percentile moves are regime artefacts; attribute on values, not percentiles.\n'
    )
    return lines


def reference_corr(a: Analysis) -> pd.Series:
    return (
        a.corr[a.reference]
        if a.reference in a.corr
        else pd.Series(dtype=float)
    )


def family_wide_event_row(
    event: pd.Series, family: dict, reference: dict
) -> str:
    regime_note = ' (regime moved too)' if abs(reference['z']) >= 2 else ''
    return (
        f'| {event["id"]} | {event["date"]:{TIMESTAMP}} | {event["label"][:70]} | '
        f'{format_x1000(family["before"])}→{format_x1000(family["after"])} | '
        f'{format_x1000(family["delta"])} | {family["z"]:+.1f} | {format_x1000(reference["delta"])} | '
        f'{significance_verdict(family["z"])}{regime_note} |'
    )


def family_wide_events_section(a: Analysis) -> list[str]:
    family_mean, sigma = a.family_mean, median_noise_floor(a)
    ref_corr = reference_corr(a)
    sigma_ref = std_of_block_means(
        ref_corr, independent_block_days(a.corr_metric)
    )
    lines = [
        '## Family-wide events (family mean vs regime reference)\n',
        (
            '| event | date | label | family before→after | Δ | z | reference corr Δ | verdict |\n'
            '|---|---|---|---|---|---|---|---|'
        ),
    ]
    for _, event in a.events[
        a.events['scope'].isin(['all', 'target'])
    ].iterrows():
        family = before_after_test(
            family_mean, event['date'], a.window, sigma, a.block_days
        )
        reference = before_after_test(
            ref_corr, event['date'], a.window, sigma_ref, a.block_days
        )
        lines.append(family_wide_event_row(event, family, reference))
    return lines


def gap_to_rest_of_family(a: Analysis, model: str) -> pd.Series:
    others = a.values[[m for m in a.family if m != model]].mean(axis=1)
    return a.values[model] - others


def model_specific_event_row(a: Analysis, event: pd.Series) -> str:
    model = event['scope']
    gap = gap_to_rest_of_family(a, model)
    test = before_after_test(
        gap,
        event['date'],
        a.window,
        std_of_block_means(gap, a.block_days),
        a.block_days,
    )
    return (
        f'| {event["id"]} | {event["date"]:{TIMESTAMP}} | {model} | {event["label"][:60]} | '
        f'{format_x1000(test["before"])}→{format_x1000(test["after"])} | {format_x1000(test["delta"])} | '
        f'{test["z"]:+.1f} | {significance_verdict(test["z"])} |'
    )


def model_specific_events_section(a: Analysis) -> list[str]:
    lines = [
        '\n## Model-specific events (difference-in-differences vs rest of family)\n',
        (
            '| event | date | model | label | (model − others) before→after | Δ | z | verdict |\n'
            '|---|---|---|---|---|---|---|---|'
        ),
    ]
    model_events = a.events[a.events['scope'].isin(a.family)]
    lines += [
        model_specific_event_row(a, event)
        for _, event in model_events.iterrows()
    ]
    return lines


def latest_family_change_with_enough_control_rounds(
    a: Analysis,
) -> pd.Timestamp:
    scored = a.values[a.control].dropna().index
    changes = a.events.loc[a.events['scope'].isin(['all', 'retrain']), 'date']
    enough = [
        (scored >= d).sum() >= MIN_SCORED_ROUNDS_AFTER_CONTROL_START
        for d in changes
    ]
    return changes[enough].max() if any(enough) else a.values.index[0]


def mean_gap_z_score(
    recent: pd.Series, gap_sigma: float, block_days: int
) -> float:
    if not len(recent) or not gap_sigma > 0:
        return np.nan
    blocks = max((recent.index[-1] - recent.index[0]).days / block_days, 1.0)
    return recent.mean() / (gap_sigma / np.sqrt(blocks))


def control_gap_row(a: Analysis, model: str, start: pd.Timestamp) -> str:
    gap = a.values[model] - a.values[a.control]
    recent = gap[gap.index >= start].dropna()
    z = mean_gap_z_score(
        recent, std_of_block_means(gap, a.block_days), a.block_days
    )
    return f'| {model} | {format_x1000(recent.mean())} | {len(recent)} | {z:+.1f} | {significance_verdict(z)} |'


def control_gap_section(a: Analysis) -> list[str]:
    if not (a.control and a.control in a.values):
        return []
    start = latest_family_change_with_enough_control_rounds(a)
    lines = [
        (
            f'\n## Gap to control `{a.control}` since the latest family-wide change/retrain '
            f'with ≥{MIN_SCORED_ROUNDS_AFTER_CONTROL_START} scored rounds ({start:{TIMESTAMP}})\n'
        ),
        '| model | mean gap | n | z | verdict |\n|---|---|---|---|---|',
    ]
    lines += [
        control_gap_row(a, model, start)
        for model in a.family
        if model != a.control
    ]
    return lines


def biweekly_means_x1000(a: Analysis) -> pd.DataFrame:
    table = a.values[a.family].copy()
    table['FAMILY'] = a.family_mean
    for ref_model in a.references:
        if ref_model in a.values:
            table[ref_model] = a.values[ref_model]
    if a.reference in a.corr:
        table[f'{a.reference} {a.corr_metric}'] = a.corr[a.reference]
    biweekly = (table.resample('2W-MON').mean() * 1000).round(1)
    biweekly.index = biweekly.index.date
    return biweekly


def biweekly_section(a: Analysis) -> list[str]:
    return [
        f'\n## Biweekly mean `{a.metric}` (x1000)\n',
        biweekly_means_x1000(a).to_markdown(),
    ]


REPORT_SECTIONS = [
    report_header,
    coverage_section,
    noise_floor_section,
    regime_exposure_section,
    family_wide_events_section,
    model_specific_events_section,
    control_gap_section,
    biweekly_section,
]


def main() -> None:
    analysis = build_analysis(parse_arguments())
    lines = [line for section in REPORT_SECTIONS for line in section(analysis)]
    sys.stdout.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
