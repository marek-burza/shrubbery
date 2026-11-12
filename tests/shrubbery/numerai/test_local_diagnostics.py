from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shrubbery.numerai.constants import (
    COLUMN_ERA,
    COLUMN_ID,
    COLUMN_PREDICTION,
    COLUMN_TARGET,
)
from shrubbery.numerai.diagnostics import (
    COLUMN_BENCHMARK,
    compute_local_diagnostics,
    max_drawdown,
    summarize,
)

DATES = ['2019-01-04', '2019-01-11', '2019-01-18', '2019-01-25']
SCORED_DATES = DATES[:-1]  # the last date has no published target
TICKERS = [f'T{i:03d}' for i in range(60)]
HOSTED_KEYS = {
    'erasAcceptedCount',
    'validationCorrV4Mean',
    'validationCorrV4Std',
    'validationCorrV4Sharpe',
    'validationCorrV4MaxDrawdown',
    'validationBmcMean',
}


@pytest.fixture
def validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> pd.DataFrame:
    monkeypatch.chdir(tmp_path)
    data_directory = tmp_path / 'workspace' / 'data'
    data_directory.mkdir(parents=True)
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        [(ticker, date) for date in DATES for ticker in TICKERS],
        columns=[COLUMN_ID, COLUMN_ERA],
    )
    frame[COLUMN_TARGET] = rng.integers(0, 5, len(frame)) / 4
    frame.loc[frame[COLUMN_ERA] == DATES[-1], COLUMN_TARGET] = np.nan
    frame[COLUMN_BENCHMARK] = rng.random(len(frame)).astype('float32')
    frame[[COLUMN_ID, COLUMN_ERA, COLUMN_TARGET]].to_parquet(
        data_directory / 'validation.parquet'
    )
    frame[[COLUMN_ID, COLUMN_ERA, COLUMN_BENCHMARK]].to_parquet(
        data_directory / 'validation_benchmark_models.parquet'
    )
    neutralizers = frame[[COLUMN_ID, COLUMN_ERA]].copy()
    for i in range(4):
        neutralizers[f'neutralizer_column_{i}'] = rng.normal(
            size=len(frame)
        ).astype('float32')
    neutralizers.to_parquet(data_directory / 'validation_neutralizer.parquet')
    return frame


def predictions(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    result = frame[[COLUMN_ID, COLUMN_ERA]].copy()
    result[COLUMN_PREDICTION] = frame[column].fillna(0.5)
    return result


def test_returns_the_hosted_keys_for_dates_with_targets(
    validation: pd.DataFrame,
) -> None:
    metrics = compute_local_diagnostics(predictions(validation, COLUMN_TARGET))
    assert set(metrics) == HOSTED_KEYS
    assert metrics['erasAcceptedCount'] == len(SCORED_DATES)


def test_predicting_the_target_scores_positive(
    validation: pd.DataFrame,
) -> None:
    metrics = compute_local_diagnostics(predictions(validation, COLUMN_TARGET))
    assert metrics['validationCorrV4Mean'] > 0.5
    assert metrics['validationBmcMean'] > 0


def test_copying_the_benchmark_contributes_nothing(
    validation: pd.DataFrame,
) -> None:
    metrics = compute_local_diagnostics(
        predictions(validation, COLUMN_BENCHMARK)
    )
    assert metrics['validationBmcMean'] == pytest.approx(0, abs=1e-6)


def test_embargo_drops_leading_dates(validation: pd.DataFrame) -> None:
    metrics = compute_local_diagnostics(
        predictions(validation, COLUMN_TARGET), embargo_dates=1
    )
    assert metrics['erasAcceptedCount'] == len(SCORED_DATES) - 1


def test_skips_dates_without_neutralizers(validation: pd.DataFrame) -> None:
    path = Path('workspace/data/validation_neutralizer.parquet')
    neutralizers = pd.read_parquet(path)
    neutralizers[neutralizers[COLUMN_ERA] != DATES[0]].to_parquet(path)
    metrics = compute_local_diagnostics(predictions(validation, COLUMN_TARGET))
    assert metrics['erasAcceptedCount'] == len(SCORED_DATES) - 1


def test_aggregates_like_the_hosted_diagnostics() -> None:
    scores = pd.Series([0.1, -0.2, 0.05, -0.1])
    assert max_drawdown(scores) == pytest.approx(-0.25)
    summary = summarize('x', scores)
    assert summary['xMean'] == pytest.approx(-0.0375)
    assert summary['xStd'] == pytest.approx(scores.std(ddof=1))
    assert summary['xSharpe'] == pytest.approx(-0.0375 / scores.std(ddof=1))
    assert summary['xMaxDrawdown'] == pytest.approx(-0.25)
