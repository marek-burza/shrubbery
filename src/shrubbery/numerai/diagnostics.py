import logging

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from numerai_tools.scoring import neutral_contribution, neutral_correlation

from shrubbery.numerai.constants import (
    COLUMN_ERA,
    COLUMN_ID,
    COLUMN_PREDICTION,
    COLUMN_TARGET,
)
from shrubbery.numerai.ingest import locate_numerai_file, read_numerai_parquet

logger = logging.getLogger('shrubbery')

NEUTRALIZER_FILE = 'validation_neutralizer.parquet'
COLUMN_BENCHMARK = 'lgbm_jupiter_60'
COLUMN_NEUTRALIZER_PREFIX = 'neutralizer_column_'
COLUMN_CORRV4 = 'corrV4'
COLUMN_BMC = 'bmc'


def max_drawdown(scores: pd.Series) -> float:
    cumulative = scores.cumsum()
    return float(-(cumulative.cummax() - cumulative).max())


def summarize(name: str, scores: pd.Series) -> dict[str, float]:
    mean = float(scores.mean())
    std = float(scores.std())
    return {
        f'{name}Mean': mean,
        f'{name}Std': std,
        f'{name}Sharpe': mean / std,
        f'{name}MaxDrawdown': max_drawdown(scores),
    }


def read_neutralizers(date: str) -> pd.DataFrame:
    table = pq.read_table(
        locate_numerai_file(NEUTRALIZER_FILE),
        filters=[(COLUMN_ERA, '==', date)],
    )
    frame = table.to_pandas().set_index(COLUMN_ID)
    return frame.filter(like=COLUMN_NEUTRALIZER_PREFIX)


def score_date(date_data: pd.DataFrame, date: str) -> tuple[float, float]:
    date_data = date_data.set_index(COLUMN_ID)
    neutralizers = read_neutralizers(date)
    predictions = date_data[[COLUMN_PREDICTION]]
    target = date_data[COLUMN_TARGET]
    ncorr = neutral_correlation(predictions, neutralizers, target)
    nbmc = neutral_contribution(
        predictions, date_data[COLUMN_BENCHMARK], neutralizers, target
    )
    return float(ncorr.iloc[0]), float(nbmc.iloc[0])


def embargo_end(business_days: int) -> str:
    # Last date whose target overlaps the target of the last training date
    last_train_date = read_numerai_parquet('train.parquet', [COLUMN_ERA])[
        COLUMN_ERA
    ].max()
    end = str(np.busday_offset(last_train_date, business_days, roll='forward'))
    logger.info(
        f'Diagnostics embargo: {business_days} business days after {last_train_date},'
        f' scoring dates after {end}'
    )
    return end


def per_date_scores(
    prediction_data: pd.DataFrame, embargo_business_days: int = 0
) -> pd.DataFrame:
    keys = [COLUMN_ID, COLUMN_ERA]
    data = (
        prediction_data[[*keys, COLUMN_PREDICTION]]
        .merge(
            read_numerai_parquet('validation.parquet', [*keys, COLUMN_TARGET]),
            on=keys,
        )
        .merge(
            read_numerai_parquet(
                'validation_benchmark_models.parquet',
                [*keys, COLUMN_BENCHMARK],
            ),
            on=keys,
        )
        .dropna(subset=[COLUMN_TARGET])
    )
    end = embargo_end(embargo_business_days)
    dates = sorted(date for date in data[COLUMN_ERA].unique() if date > end)
    groups = data.groupby(COLUMN_ERA)
    rows = {}
    for date in dates:
        try:
            rows[date] = score_date(groups.get_group(date), date)
        except AssertionError:
            logger.warning(f'Skipped {date}: too few neutralizer rows')
    return pd.DataFrame.from_dict(
        rows, orient='index', columns=[COLUMN_CORRV4, COLUMN_BMC]
    )


def compute_local_diagnostics(
    prediction_data: pd.DataFrame, embargo_business_days: int = 0
) -> dict[str, float]:
    """Local replacement of `submit_diagnostic_predictions`.

    Returns the subset of the hosted diagnostics with documented
    definitions, under the hosted keys. Only dates with published
    targets are scored, so the values approximate, not reproduce,
    the hosted ones. Only dates more than `embargo_business_days` after
    the last date of `train.parquet` are scored, so that their targets do
    not overlap the training targets (the hosted diagnostics apply no
    embargo; 60 matches 60-day targets).
    """
    logger.info('Diagnostics mode: local')
    scores = per_date_scores(prediction_data, embargo_business_days)
    metrics = {
        'erasAcceptedCount': float(len(scores)),
        **summarize('validationCorrV4', scores[COLUMN_CORRV4]),
        'validationBmcMean': float(scores[COLUMN_BMC].mean()),
    }
    for key, value in metrics.items():
        logger.info(f'Numerai Diagnostics - {key}: {value}')
    return metrics
