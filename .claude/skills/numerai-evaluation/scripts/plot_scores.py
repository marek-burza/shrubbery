"""Performance plots annotated with model-change events.

Input: long-format CSV from `numerai-scores --format csv` and an events CSV (date: ISO 8601 UTC date-time) with
columns date,id,scope,label where scope is
  all      family-wide code/config change (dashed line, circled id)
  target   scoring/training target or data-version change (blue dotted line)
  retrain  retrain without further detail (triangle marker)
  <model>  change specific to that model (lettered marker in its panel)

Writes to --out-dir:
  performance_annotated.png  regime panel (family means vs reference) + one panel per
                             model (30-day rolling means of two metrics) + event key
  <control>_full_history.png whole live history of the control model vs reference

Usage: python plot_scores.py --scores scores.csv --events events.csv \
    --models again bail ... --reference integration_test [--control again] \
    [--metrics v2_corr20 bmc] [--since 2025-08-01] [--out-dir workspace/analysis]
"""

# Code structure, to keep when editing this file:
# - Write code as small functions whose names state exactly what each does
#   (e.g. `extract_zip_safely`, `report_unused_runtime_dependencies`).
# - Keep code and functions short, concise, understandable and readable to a single SWE
#   reviewing: roughly under 30 lines, one responsibility each. No long monolithic functions.
# - Why: the code is audited personally by its maintainer.

import argparse
import textwrap
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from score_data import horizon_days, read_events, read_latest_score_snapshots

BLUE, ORANGE, GREY, INK, INK2, SURFACE = '#2a78d6', '#eb6834', '#8a8984', '#0b0b0b', '#52514e', '#fcfcfb'
EVENT_LINE, TARGET_INK = '#6f6e69', '#1c5cab'
HOUSE_STYLE = {
    'font.size': 10, 'axes.edgecolor': '#c9c8c3', 'axes.labelcolor': INK2, 'xtick.color': INK2,
    'ytick.color': INK2, 'axes.facecolor': SURFACE, 'figure.facecolor': SURFACE,
    'axes.spines.top': False, 'axes.spines.right': False, 'grid.color': '#e6e5e0',
}
TIMESTAMP = '%Y-%m-%dT%H:%M:%SZ'
MAX_DAYS_BETWEEN_CONNECTED_POINTS = 10


@dataclass
class PlotInputs:
    scores: pd.DataFrame
    events: pd.DataFrame
    plotted: pd.DataFrame
    models: list[str]
    reference: str
    control: str | None
    first: str
    second: str
    start: pd.Timestamp
    end: pd.Timestamp
    out_dir: Path

    @property
    def metric_colours(self) -> list[tuple[str, str]]:
        return [(self.first, BLUE), (self.second, ORANGE)]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--scores', required=True)
    parser.add_argument('--events', required=True)
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--reference', required=True)
    parser.add_argument('--control')
    parser.add_argument('--metrics', nargs=2, default=['v2_corr20', 'bmc'])
    parser.add_argument('--since', default=None)
    parser.add_argument('--out-dir', type=Path, default=Path('workspace/analysis'))
    return parser.parse_args()


def build_plot_inputs(args: argparse.Namespace) -> PlotInputs:
    scores = read_latest_score_snapshots(args.scores)
    events = read_events(args.events)
    start = pd.Timestamp(args.since) if args.since else scores['date'].min()
    end = scores['date'].max() + pd.Timedelta(days=3)
    plotted = events[(events['date'] >= start) & (events['date'] <= end)]
    first, second = args.metrics
    return PlotInputs(scores=scores, events=events, plotted=plotted, models=args.models, reference=args.reference,
                      control=args.control, first=first, second=second, start=start, end=end, out_dir=args.out_dir)


def model_metric_series(scores: pd.DataFrame, model: str, metric: str) -> pd.Series:
    rows = scores[(scores['model'] == model) & (scores['metric'] == metric)]
    return rows.groupby('date')['value'].mean().sort_index()


def blank_points_after_gaps(smooth: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    smooth[index.to_series().diff().dt.days > MAX_DAYS_BETWEEN_CONNECTED_POINTS] = np.nan
    return smooth


def rolling_mean(values: pd.Series, days: int = 30) -> pd.Series:
    values = values.dropna().sort_index()
    if values.empty:
        return values
    smooth = values.rolling(f'{days}D', min_periods=5).mean()
    return blank_points_after_gaps(smooth, values.index)


def style_time_axis(axis, start: pd.Timestamp, end: pd.Timestamp) -> None:
    axis.axhline(0, color='#9b9a95', lw=0.8)
    axis.grid(axis='y', lw=0.6)
    axis.set_xlim(start, end)
    axis.xaxis.set_major_locator(mdates.MonthLocator(bymonth=None if (end - start).days < 800 else [1, 4, 7, 10]))
    axis.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
    axis.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:+.3f}' if v else '0'))


def draw_event_lines(axis, events: pd.DataFrame) -> None:
    for _, event in events.iterrows():
        match event['scope']:
            case 'all':
                axis.axvline(event['date'], color=EVENT_LINE, lw=0.9, ls=(0, (4, 3)), zorder=0)
            case 'target':
                axis.axvline(event['date'], color=BLUE, lw=1.0, ls=(0, (1, 2)), zorder=0, alpha=0.8)


def decorate(axis, events: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> None:
    style_time_axis(axis, start, end)
    draw_event_lines(axis, events)


def shade_not_final_scores(axis, end: pd.Timestamp, metric: str) -> None:
    calendar_days = horizon_days(metric) * 7 // 5
    axis.axvspan(end - pd.Timedelta(days=calendar_days), end, color='#e9e8e4', zorder=-1, lw=0)


def create_performance_figure(n_models: int, n_events: int) -> tuple:
    figure = plt.figure(figsize=(15, 3.3 * (n_models + 1) + 6))
    key_height = 0.25 * (n_events + 4) / 4 + 0.6
    grid = figure.add_gridspec(n_models + 3, 1, height_ratios=[1.3] + [1] * n_models + [0.05, key_height], hspace=0.38)
    axes = [figure.add_subplot(grid[i, 0]) for i in range(n_models + 1)]
    for axis in axes[2:]:
        axis.sharey(axes[1])
    return figure, grid, axes


def plot_family_and_reference_lines(axis, p: PlotInputs) -> None:
    family = p.scores[p.scores['model'].isin(p.models) & (p.scores['date'] >= p.start)]
    family_means = family.groupby(['date', 'metric'])['value'].mean().unstack()
    reference = rolling_mean(model_metric_series(p.scores, p.reference, p.first))
    axis.plot(reference.index, reference, color=GREY, lw=2, label=f'{p.reference} {p.first} (regime reference)')
    for metric, colour in p.metric_colours:
        if metric in family_means:
            smooth = rolling_mean(family_means[metric])
            axis.plot(smooth.index, smooth, color=colour, lw=2, label=f'Family mean {metric}')


def mark_retrains(axis, plotted: pd.DataFrame, low: float, high: float) -> None:
    retrains = plotted[plotted['scope'] == 'retrain']
    if len(retrains):
        y = [low + 0.1 * (high - low) * 0.3] * len(retrains)
        axis.scatter(retrains['date'], y, marker='^', s=46, color=INK2, zorder=5, label='Retrain')


def label_family_wide_event(axis, event: pd.Series, high: float) -> None:
    axis.text(event['date'], high, str(event['id']), ha='center', va='bottom', fontsize=10, fontweight='bold',
              color=INK, bbox={'boxstyle': 'circle,pad=0.25', 'fc': 'white', 'ec': EVENT_LINE, 'lw': 0.8})


def label_target_event(axis, event: pd.Series, low: float, high: float) -> None:
    axis.text(event['date'], low + 0.22 * (high - low), str(event['id']), ha='center', va='bottom', fontsize=8.5,
              fontweight='bold', color=TARGET_INK, bbox={'boxstyle': 'round,pad=0.2', 'fc': 'white', 'ec': BLUE, 'lw': 0.8})


def label_family_wide_and_target_events(axis, plotted: pd.DataFrame, low: float, high: float) -> None:
    for _, event in plotted.iterrows():
        match event['scope']:
            case 'all':
                label_family_wide_event(axis, event, high)
            case 'target':
                label_target_event(axis, event, low, high)


def plot_regime_panel(axis, p: PlotInputs) -> None:
    plot_family_and_reference_lines(axis, p)
    decorate(axis, p.plotted, p.start, p.end)
    shade_not_final_scores(axis, p.end, p.second)
    axis.set_title(f'Family vs regime reference — 30-day rolling means by round date (grey band: {p.second} '
                   'not final yet)', loc='left', color=INK, fontsize=12, fontweight='bold', pad=26)
    low, high = axis.get_ylim()
    mark_retrains(axis, p.plotted, low, high)
    axis.legend(loc='upper left', frameon=False, ncol=4, fontsize=9)
    label_family_wide_and_target_events(axis, p.plotted, low, high)


def period_mean_summary(p: PlotInputs, model: str) -> str:
    recent = p.scores[(p.scores['model'] == model) & (p.scores['date'] >= p.start)]
    means = recent.groupby('metric')['value'].mean()
    return ', '.join(f'{m} {means[m]:+.4f}' for m in (p.first, p.second) if m in means)


def mark_model_specific_events(axis, events: pd.DataFrame) -> None:
    for _, event in events.iterrows():
        axis.axvline(event['date'], color=INK2, lw=1.2, ymin=0, ymax=0.08)
        axis.annotate(str(event['id']), (event['date'], 0.02), xycoords=('data', 'axes fraction'), ha='center',
                      va='bottom', fontsize=10, fontweight='bold', color=INK, xytext=(0, 10),
                      textcoords='offset points', bbox={'boxstyle': 'round,pad=0.2', 'fc': '#f0efec', 'ec': INK2, 'lw': 0.8})


def plot_model_metric_lines(axis, p: PlotInputs, model: str) -> None:
    for metric, colour in p.metric_colours:
        values = model_metric_series(p.scores, model, metric)
        smooth = rolling_mean(values[values.index >= p.start])
        axis.plot(smooth.index, smooth, color=colour, lw=2, label=metric)


def plot_model_panel(axis, p: PlotInputs, model: str, is_top: bool, is_bottom: bool) -> None:
    plot_model_metric_lines(axis, p, model)
    decorate(axis, p.plotted, p.start, p.end)
    shade_not_final_scores(axis, p.end, p.second)
    axis.set_title(f'{model}   ·   mean over the period: {period_mean_summary(p, model)}', loc='left', color=INK,
                   fontsize=11, fontweight='bold')
    mark_model_specific_events(axis, p.plotted[p.plotted['scope'] == model])
    if is_top:
        axis.legend(loc='upper left', frameon=False, ncol=2, fontsize=9)
    if not is_bottom:
        plt.setp(axis.get_xticklabels(), visible=False)


def event_key_line(row: pd.Series) -> str:
    label = textwrap.shorten(str(row['label']), 130)
    return f"  {row['id']}. {row['date']:{TIMESTAMP}} [{row['scope']}] {label}"


def event_key_lines(plotted: pd.DataFrame) -> list[str]:
    sections = [('Family-wide changes (dashed lines)', plotted['scope'] == 'all'),
                ('Target / data-version changes (blue dotted lines)', plotted['scope'] == 'target'),
                ('Retrains (triangles)', plotted['scope'] == 'retrain'),
                ('Model-specific changes (lettered markers)', ~plotted['scope'].isin(['all', 'target', 'retrain']))]
    lines = []
    for title, mask in sections:
        if mask.any():
            lines += ['', title] + [event_key_line(row) for _, row in plotted[mask].iterrows()]
    return lines[1:]


def plot_event_key(figure, grid_cell, plotted: pd.DataFrame) -> None:
    key = figure.add_subplot(grid_cell)
    key.axis('off')
    key.text(0, 1, '\n'.join(event_key_lines(plotted)), va='top', ha='left', family='monospace', fontsize=8.6,
             color=INK)


def save_and_close(figure, path: Path) -> None:
    figure.savefig(path, dpi=110, bbox_inches='tight')
    plt.close(figure)


def plot_performance_annotated(p: PlotInputs) -> None:
    n = len(p.models)
    figure, grid, axes = create_performance_figure(n, len(p.plotted))
    plot_regime_panel(axes[0], p)
    for index, model in enumerate(p.models):
        plot_model_panel(axes[index + 1], p, model, is_top=index == 0, is_bottom=index == n - 1)
    plot_event_key(figure, grid[n + 2, 0], p.plotted)
    save_and_close(figure, p.out_dir / 'performance_annotated.png')


def plot_control_and_reference_lines(axis, p: PlotInputs, control_start: pd.Timestamp) -> None:
    for metric, colour in p.metric_colours:
        smooth = rolling_mean(model_metric_series(p.scores, p.control, metric))
        axis.plot(smooth.index, smooth, color=colour, lw=2, label=metric)
    smooth = rolling_mean(model_metric_series(p.scores, p.reference, p.first))
    smooth = smooth[smooth.index >= control_start]
    axis.plot(smooth.index, smooth, color=GREY, lw=1.5, label=f'{p.reference} {p.first}')


def label_target_changes_alternating_height(axis, targets: pd.DataFrame) -> None:
    high = axis.get_ylim()[1]
    for i, (_, event) in enumerate(targets.iterrows()):
        axis.text(event['date'], high * (1 if i % 2 == 0 else 0.86), ' ' + textwrap.shorten(str(event['label']), 40),
                  fontsize=8.5, va='top', color=TARGET_INK)


def plot_control_full_history(p: PlotInputs) -> None:
    figure, axis = plt.subplots(figsize=(15, 4.5))
    control_start = p.scores.loc[p.scores['model'] == p.control, 'date'].min()
    plot_control_and_reference_lines(axis, p, control_start)
    targets = p.events[p.events['scope'] == 'target']
    decorate(axis, targets, control_start, p.end)
    label_target_changes_alternating_height(axis, targets)
    axis.set_title(f'{p.control} — full live history (30-day rolling means; scores are against the payout target '
                   'of the time)', loc='left', fontweight='bold', color=INK)
    axis.legend(frameon=False, loc='lower left', ncol=3, fontsize=9)
    save_and_close(figure, p.out_dir / f'{p.control}_full_history.png')


def main() -> None:
    args = parse_arguments()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(HOUSE_STYLE)
    inputs = build_plot_inputs(args)
    plot_performance_annotated(inputs)
    if inputs.control:
        plot_control_full_history(inputs)


if __name__ == '__main__':
    main()
