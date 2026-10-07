import enum
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from shrubbery.numerai.napi import (
    napi,
    numerai_models,
    resolve_numerai_model_id,
)
from shrubbery.numerai.observability import logger

HELP = """
Fetch live tournament scores of Numerai models for performance evaluation.

Scores come from the Numerai API `submission_scores` query. Each score is
stored as daily snapshots while a round resolves (day 1..20 for 20-day
scores, day 1..60 for 60-day scores). By default only the latest snapshot
per model, round and metric is returned. `day` tells how many days of
scoring a value covers; a 20-day score is final at day 20, a 60-day score
at day 60. `resolved` only turns true once the whole round has resolved
(about 3 months after the round, for all metrics), so for recent final
20-day scores filter with `--min-day 20` instead of `--resolved-only`.

**Models**: pass model names as arguments. Names of models owned by the
account in `NUMERAI_PUBLIC_ID`/`NUMERAI_SECRET_KEY` are resolved first,
any other name is looked up as a public model (e.g. `integration_test`,
Numerai's example model, useful as a regime reference). Without arguments
all models of the account are fetched.

**Output**: stdout carries only data - by default a JSON array of records
(ISO-8601 dates, `null` for missing values); `--format csv` for files,
`--format table` for humans. Logs and errors go to stderr; a failure exits
non-zero. One record per model x round x metric (x day with `--daily`):
`model`, `round`, `round_date` (staking close of the round, a proxy for
when the predictions were made), `resolve_date`, `metric`, `day`, `value`,
`percentile` (0..1 rank among all submissions), `resolved`, `version`.
With `--summary`, one record per model x metric over the filtered rounds:
`n`, `mean`, `std`, `sharpe` (mean/std), `hit_rate` (share of rounds > 0),
`mean_pct`, `first_round`, `last_round`.

**Metrics** (`--metric`, repeatable; default: all available):

- `v2_corr20` (CORR20v2) and `mmc` - 20-day correlation and meta model
contribution against the main target of the time; paid until round 1342
- `corr60`, `mmc60` - 60-day versions; paid from round 1343
- `bmc` - contribution after neutralizing to the benchmark models; best
single gauge of unique signal, not paid
- `fnc_v3` (feature neutral corr), `cort20` (teager target), `corj60`
(jerome target), `season_score`, `corr_w_meta_model` (uniqueness),
`apcwnm`/`mcwnm` (average/max correlation with other submissions)
- `canon_*` duplicate the plain metrics; `tc` exists only for old rounds

**Payout history** (main target and formula): Cyrus-20 with
0.5 CORR + 2 MMC from 2024-01-02; Ender-20 with 0.75 CORR + 2.25 MMC from
2026-01-01; Ender-60 with 3 CORR60 + 15 MMC60 from round 1343
(2026-08-28). Values before and after a target change are measured against
different targets.

**Interpretation caveats**: rounds are daily but their scoring windows
overlap (20 or 60 days), so consecutive rounds are strongly correlated;
a 4-week block is roughly one independent observation. Percentiles are
relative to all submissions and swing with the crowd (a heavily
neutralized model ranks low when feature-exposed models do well); prefer
values, BMC and a reference model for attribution.

**Examples**:

- `numerai-scores again bail integration_test -m v2_corr20 -m bmc -n 30`
- `numerai-scores --summary --min-day 20 --since 2026-06-01 -m v2_corr20`
- `numerai-scores again -m mmc --daily -n 5` (daily snapshot paths)
- `numerai-scores -m corr60 -m mmc60 --format csv --output scores.csv`
"""

COLUMNS = {
    'roundNumber': 'round',
    'roundCloseStakingTime': 'round_date',
    'roundResolveTime': 'resolve_date',
    'displayName': 'metric',
    'day': 'day',
    'value': 'value',
    'percentile': 'percentile',
    'resolved': 'resolved',
    'version': 'version',
}


class OutputFormat(str, enum.Enum):
    JSON = 'json'
    CSV = 'csv'
    TABLE = 'table'


def _query_with_retries(
    model_id: str,
    display_name: str | None,
    distinct_on_round: bool | None,
    attempts: int = 3,
) -> list[dict]:
    for attempt in range(1, attempts + 1):
        try:
            return napi.submission_scores(
                model_id,
                display_name=display_name,
                distinct_on_round=distinct_on_round,
            )
        except Exception:
            if attempt == attempts:
                raise
            logger.warning(f'Retrying submission_scores ({attempt})')
            time.sleep(5 * attempt)
    return []


def fetch_scores(
    model: str,
    metrics: list[str] | None = None,
    last_n_rounds: int | None = None,
    daily: bool = False,
) -> pd.DataFrame:
    model_id = resolve_numerai_model_id(model)
    # Daily snapshots of all metrics at once time out on the API side, so
    # without --daily only the latest snapshot per round is requested
    distinct_on_round = None if daily else True
    if metrics:
        rows = [
            row
            for metric in metrics
            for row in _query_with_retries(model_id, metric, distinct_on_round)
        ]
    elif daily:
        raise ValueError('Daily snapshots require explicit metrics')
    else:
        rows = _query_with_retries(model_id, None, distinct_on_round)
    scores = pd.DataFrame(rows, columns=list(COLUMNS)).rename(columns=COLUMNS)
    scores = scores.dropna(subset=['value'])
    scores.insert(0, 'model', model)
    for column in ['round_date', 'resolve_date']:
        scores[column] = pd.to_datetime(scores[column], utc=True)
    # Not passing last_n_rounds to the API: it counts the latest rounds even
    # when they have no score yet for the requested metric
    if last_n_rounds is not None:
        rank = scores.groupby('metric')['round'].rank(
            method='dense', ascending=False
        )
        scores = scores[rank <= last_n_rounds]
    return scores.sort_values(['round', 'metric', 'day'], ignore_index=True)


def filter_scores(
    scores: pd.DataFrame,
    from_round: int | None = None,
    to_round: int | None = None,
    since: str | None = None,
    until: str | None = None,
    resolved_only: bool = False,
    min_day: int | None = None,
) -> pd.DataFrame:
    keep = pd.Series(True, index=scores.index)
    if from_round is not None:
        keep &= scores['round'] >= from_round
    if to_round is not None:
        keep &= scores['round'] <= to_round
    if since is not None:
        keep &= scores['round_date'] >= pd.Timestamp(since, tz='UTC')
    if until is not None:
        keep &= scores['round_date'] <= pd.Timestamp(until, tz='UTC')
    if resolved_only:
        keep &= scores['resolved'].astype(bool)
    if min_day is not None:
        keep &= scores['day'] >= min_day
    return scores[keep].reset_index(drop=True)


def summarize_scores(scores: pd.DataFrame) -> pd.DataFrame:
    latest = scores.sort_values('day').drop_duplicates(
        ['model', 'round', 'metric'], keep='last'
    )
    grouped = latest.groupby(['model', 'metric'])
    summary = grouped['value'].agg(['count', 'mean', 'std'])
    summary = summary.rename(columns={'count': 'n'})
    summary['sharpe'] = summary['mean'] / summary['std']
    summary['hit_rate'] = grouped['value'].apply(lambda v: (v > 0).mean())
    summary['mean_pct'] = grouped['percentile'].mean()
    summary['first_round'] = grouped['round'].min()
    summary['last_round'] = grouped['round'].max()
    return summary.reset_index()


def write_output(
    frame: pd.DataFrame, output_format: OutputFormat, output: Path | None
) -> None:
    if output_format == OutputFormat.CSV:
        text = frame.to_csv(index=False) or ''
    elif output_format == OutputFormat.JSON:
        text = frame.to_json(orient='records', date_format='iso') or ''
    else:
        with pd.option_context('display.max_rows', None):
            text = frame.to_string(index=False)
    if output is None:
        sys.stdout.write(text + '\n')
    else:
        output.write_text(text)


app = typer.Typer(
    add_completion=False,
    rich_markup_mode='markdown',
    context_settings={'help_option_names': ['-h', '--help']},
)


@app.command(help=HELP)
def main(
    models: Annotated[
        list[str] | None,
        typer.Argument(help='Model names; default: all account models'),
    ] = None,
    metrics: Annotated[
        list[str] | None,
        typer.Option('--metric', '-m', help='Repeatable; default: all'),
    ] = None,
    last_n_rounds: Annotated[
        int | None,
        typer.Option('--last-n-rounds', '-n', help='Latest N scored rounds'),
    ] = None,
    from_round: Annotated[
        int | None, typer.Option(help='First round (inclusive)')
    ] = None,
    to_round: Annotated[
        int | None, typer.Option(help='Last round (inclusive)')
    ] = None,
    since: Annotated[
        str | None, typer.Option(help='Earliest round date, e.g. 2026-01-01')
    ] = None,
    until: Annotated[
        str | None, typer.Option(help='Latest round date (inclusive)')
    ] = None,
    min_day: Annotated[
        int | None,
        typer.Option(help='Min scoring days, e.g. 20 for final 20D scores'),
    ] = None,
    resolved_only: Annotated[
        bool, typer.Option('--resolved-only', help='Fully resolved rounds')
    ] = False,
    daily: Annotated[
        bool,
        typer.Option('--daily', help='All daily snapshots; needs --metric'),
    ] = False,
    summary: Annotated[
        bool, typer.Option('--summary', help='Aggregate per model x metric')
    ] = False,
    output_format: Annotated[
        OutputFormat, typer.Option('--format', '-f', help='Output format')
    ] = OutputFormat.JSON,
    output: Annotated[
        Path | None, typer.Option('--output', '-o', help='Write to file')
    ] = None,
) -> None:
    if daily and not metrics:
        raise typer.BadParameter('--daily requires at least one --metric')
    names = models or numerai_models()
    logger.info(f'Fetching scores of {len(names)} model(s)')
    with ThreadPoolExecutor(max_workers=4) as executor:
        frames = list(
            executor.map(
                lambda name: fetch_scores(name, metrics, last_n_rounds, daily),
                names,
            )
        )
    scores = filter_scores(
        pd.concat(frames, ignore_index=True),
        from_round,
        to_round,
        since,
        until,
        resolved_only,
        min_day,
    )
    if scores.empty:
        logger.warning('No scores matched the given models and filters')
    result = summarize_scores(scores) if summary else scores
    write_output(result, output_format, output)


if __name__ == '__main__':
    app()
