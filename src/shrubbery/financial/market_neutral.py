"""Remove the S&P 500 correlated component from a series and test its trend.

Usage:
    uv run python -m shrubbery.financial.market_neutral data.csv SOME
    uv run python -m shrubbery.financial.market_neutral data.csv SOME \
        --benchmark-csv spx.csv

Design notes
------------

*Regression on changes, not on levels.* Both the input series and an
index like the S&P 500 are non stationary. Regressing one level on the
other is the textbook spurious regression: the shared upward drift alone
produces a high R^2 and a small p value even for unrelated series. Month
on month changes of the target against benchmark returns are close
enough to stationary for the ordinary least squares standard errors to
mean something.

*The benchmark enters as a return, the target as a difference.* The
target is an arbitrary quantity that may legitimately cross zero, so a
percentage change of it is not always defined or comparable. The
benchmark is a price index, where the return is the natural unit and the
one under which the exposure (beta) is stable across the window. That
gives a beta in "target units per 100% market move", which is directly
subtractable from a change.

*The intercept stays in.* Neutralization here answers "what would this
series have done if the benchmark had been flat", not "what is left once
every systematic component is gone". Under a flat benchmark the fitted
change is the intercept, so only `beta * market_return` is removed. That
keeps the series' own drift, which is exactly the thing the trend test
is supposed to measure. Subtracting the intercept as well would force
the residual trend towards zero by construction and make the verdict
close to meaningless.

*Residual changes are cumulated back into a level series.* The question
asked is about the trend and the total growth of a quantity, both of
which live in levels. Anchoring the cumulative sum at the first observed
value keeps the counterfactual on the same scale as the input, so the
two can be compared directly.

*A gap free monthly grid.* Reindexing onto a complete monthly grid
before differencing means a missing month yields a NaN change that is
dropped, rather than a change silently spanning several months that
would be paired with a single month of benchmark return. Missing months
are reported instead of being absorbed, because they shrink the sample
the exposure is estimated from.

*Monthly alignment by calendar period.* Both series are collapsed to one
observation per calendar month, so a month end input row and a month
start benchmark quote still meet in the same bucket. This tolerates up
to a month of timing slack, which is acceptable for a trend verdict but
would not be for anything trade like.

*Two trend tests.* The ordinary least squares slope gives the magnitude
and units the question asks for. Kendall's tau is reported alongside it
as a rank based check that is not driven by a single outlying month; the
two disagreeing is a signal that the sample is too small or too skewed
to trust. The verdict is labelled "not significant" rather than
suppressed when p exceeds alpha, so a weak direction is still visible
but is not presented as a finding.

*A single factor, fitted on few points.* One benchmark keeps the
degrees of freedom usable on the short monthly histories this is aimed
at; with eight rows a multi factor model would fit noise. The stated
p values are the honest counterweight to that, and betas from such short
windows should be read as indicative.
"""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import requests
from scipy import stats

YAHOO_CHART = 'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
DEFAULT_BENCHMARK = '^GSPC'
CLOSE_COLUMN_NAMES = frozenset({'close', 'adjclose', 'close/last'})


class MarketNeutralError(Exception):
    """Raised when the inputs cannot support the analysis."""


@dataclass
class TrendReport:
    """Outcome of fitting a linear trend to a monthly series."""

    slope: float
    p_value: float
    r_squared: float
    kendall_tau: float
    kendall_p_value: float
    significant: bool

    @property
    def direction(self) -> str:
        return 'RISING' if self.slope > 0 else 'FALLING'

    @property
    def verdict(self) -> str:
        if self.significant:
            return self.direction
        return f'{self.direction.lower()} (not significant)'


def load_series(
    path: str, column: str, date_column: str | None = None
) -> pd.Series:
    """Read `column` from a CSV into a date indexed float series."""
    frame = pd.read_csv(path)
    if date_column is None:
        date_column = str(frame.columns[0])
    if column not in frame.columns:
        available = ', '.join(
            str(name) for name in frame.columns if name != date_column
        )
        raise MarketNeutralError(
            f'column {column!r} is not in {path}; available: {available}'
        )
    series = pd.Series(
        frame[column].astype(float).to_numpy(),
        index=pd.to_datetime(frame[date_column]),
        name=column,
    )
    series = series.dropna().sort_index()
    if series.index.has_duplicates:
        raise MarketNeutralError(f'{path} has more than one row per date')
    return series


def fetch_benchmark(
    symbol: str, start: pd.Timestamp, end: pd.Timestamp
) -> pd.Series:
    """Download monthly closes for `symbol` from Yahoo Finance."""
    padding = pd.DateOffset(months=2)
    response = requests.get(
        YAHOO_CHART.format(symbol=symbol),
        params={
            'interval': '1mo',
            'period1': int((start - padding).timestamp()),
            'period2': int((end + padding).timestamp()),
        },
        headers={'User-Agent': 'Mozilla/5.0'},
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()['chart']['result'][0]
    stamps = [
        datetime.fromtimestamp(stamp, UTC) for stamp in result['timestamp']
    ]
    closes = result['indicators']['quote'][0]['close']
    series = pd.Series(
        closes,
        index=pd.to_datetime(stamps).tz_localize(None),
        name=symbol,
    )
    return series.dropna().sort_index()


def load_benchmark_csv(path: str) -> pd.Series:
    """Read benchmark closes from a local CSV (dates in the first column)."""
    frame = pd.read_csv(path)
    close_column = next(
        (
            name
            for name in frame.columns
            if str(name).lower().replace(' ', '') in CLOSE_COLUMN_NAMES
        ),
        frame.columns[-1],
    )
    closes = (
        frame[close_column]
        .astype(str)
        .str.replace(r'[$,]', '', regex=True)
        .astype(float)
    )
    series = pd.Series(
        closes.to_numpy(),
        index=pd.to_datetime(frame[frame.columns[0]]),
        name='benchmark',
    )
    return series.dropna().sort_index()


def to_monthly(series: pd.Series) -> pd.Series:
    """Keep the last observation of each calendar month, indexed by month."""
    months = pd.DatetimeIndex(series.index).to_period('M')
    return series.groupby(months).last()


def align_monthly(target: pd.Series, benchmark: pd.Series) -> pd.DataFrame:
    """Pair month on month changes of the target with benchmark returns.

    Both series are reindexed onto a gap free monthly grid first, so a
    missing month breaks the chain instead of silently producing a change
    that spans several months.
    """
    monthly = to_monthly(target)
    grid = pd.period_range(monthly.index.min(), monthly.index.max(), freq='M')
    monthly = monthly.reindex(grid)
    market = to_monthly(benchmark).reindex(grid)
    return pd.concat(
        {'change': monthly.diff(), 'market': market.pct_change()}, axis=1
    ).dropna()


def neutralize(
    target: pd.Series, benchmark: pd.Series
) -> tuple[pd.Series, pd.DataFrame, stats._stats_py.LinregressResult]:
    """Rebuild the series as it would look with a constant benchmark."""
    paired = align_monthly(target, benchmark)
    if len(paired) < 3:
        raise MarketNeutralError(
            f'only {len(paired)} monthly changes overlap the benchmark, '
            'at least 3 are needed to estimate an exposure'
        )
    fit = stats.linregress(paired['market'], paired['change'])
    # Counterfactual: the same months with a flat S&P 500, so only the
    # market driven part of each change is subtracted and the series keeps
    # its own drift.
    residual_changes = paired['change'] - fit.slope * paired['market']
    monthly = to_monthly(target)
    anchor = paired.index[0] - 1
    residual = pd.concat(
        [
            pd.Series({anchor: monthly.loc[anchor]}),
            residual_changes.cumsum() + monthly.loc[anchor],
        ]
    )
    return residual, paired, fit


def describe_trend(series: pd.Series, alpha: float = 0.05) -> TrendReport:
    """Fit a linear trend and cross check it with Kendall's tau."""
    values = series.to_numpy(dtype=float)
    positions = np.arange(len(values), dtype=float)
    fit = stats.linregress(positions, values)
    tau, tau_p_value = stats.kendalltau(positions, values)
    return TrendReport(
        slope=float(fit.slope),
        p_value=float(fit.pvalue),
        r_squared=float(fit.rvalue**2),
        kendall_tau=float(tau),
        kendall_p_value=float(tau_p_value),
        significant=bool(fit.pvalue < alpha),
    )


def report(
    column: str,
    benchmark_name: str,
    target: pd.Series,
    residual: pd.Series,
    paired: pd.DataFrame,
    market_fit: stats._stats_py.LinregressResult,
    alpha: float,
) -> None:
    """Print the exposure, the trend verdict and the residual series."""
    raw_trend = describe_trend(to_monthly(target).dropna(), alpha)
    residual_trend = describe_trend(residual, alpha)
    span = f'{target.index.min():%Y-%m} to {target.index.max():%Y-%m}'
    print(f'Series     : {column} ({len(target)} rows, {span})')
    print(
        f'Benchmark  : {benchmark_name} ({len(paired)} paired monthly returns)'
    )
    grid = pd.period_range(
        to_monthly(target).index.min(),
        to_monthly(target).index.max(),
        freq='M',
    )
    gaps = grid.difference(to_monthly(target).index)
    if len(gaps):
        missing = ', '.join(str(period) for period in gaps)
        print(f'Warning    : months missing from the input: {missing}')
        print('             changes across a gap are dropped')
    print()
    print('Exposure (monthly change ~ benchmark return)')
    print(
        f'  beta     : {market_fit.slope:+.2f} units per 100% market move '
        f'(p={market_fit.pvalue:.3f})'
    )
    print(
        f'  variance : {market_fit.rvalue**2:.1%} of the monthly changes '
        'explained by the market'
    )
    print()
    print('Trend after removing the market component')
    print(
        f'  slope    : {residual_trend.slope:+.3f} per month '
        f'(p={residual_trend.p_value:.3f}, '
        f'R^2={residual_trend.r_squared:.3f})'
    )
    print(
        f'  tau      : {residual_trend.kendall_tau:+.3f} '
        f'(p={residual_trend.kendall_p_value:.3f})'
    )
    print(f'  verdict  : {residual_trend.verdict}')
    print(
        f'  raw trend: {raw_trend.verdict} at {raw_trend.slope:+.3f} per month'
    )
    print()
    print('Level series as if the benchmark had stayed flat')
    for period, value in residual.items():
        print(f'  {period}  {value:9.2f}')


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Remove the component of a series that is correlated to S&P 500 '
            'variability and report whether the remainder is rising '
            'or falling.'
        )
    )
    parser.add_argument('csv', help='input CSV file')
    parser.add_argument('column', help='column to analyse, for example SOME')
    parser.add_argument(
        '--date-column',
        default=None,
        help='date column name (default: the first column)',
    )
    parser.add_argument(
        '--benchmark',
        default=DEFAULT_BENCHMARK,
        help=f'Yahoo Finance symbol (default: {DEFAULT_BENCHMARK})',
    )
    parser.add_argument(
        '--benchmark-csv',
        default=None,
        help='local benchmark CSV to use instead of downloading',
    )
    parser.add_argument(
        '--alpha',
        type=float,
        default=0.05,
        help='significance level for the trend test (default: 0.05)',
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        target = load_series(
            arguments.csv, arguments.column, arguments.date_column
        )
        if len(target) < 4:
            raise MarketNeutralError(
                f'need at least 4 dated rows, got {len(target)}'
            )
        if arguments.benchmark_csv:
            benchmark = load_benchmark_csv(arguments.benchmark_csv)
            benchmark_name = arguments.benchmark_csv
        else:
            benchmark = fetch_benchmark(
                arguments.benchmark, target.index.min(), target.index.max()
            )
            benchmark_name = arguments.benchmark
        residual, paired, market_fit = neutralize(target, benchmark)
    except MarketNeutralError as error:
        print(f'error: {error}')
        return 1
    report(
        arguments.column,
        benchmark_name,
        target,
        residual,
        paired,
        market_fit,
        arguments.alpha,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
