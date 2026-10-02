from dataclasses import dataclass
from typing import Any, Self

import numpy as np
import pandas as pd

from shrubbery.constants import COLUMN_ERA, COLUMN_PREDICTION
from shrubbery.observability import logger


def unpack_numerai_features(
    data: pd.DataFrame, feature_names: list[str]
) -> np.ndarray:
    # For more information about int8 encoding, see:
    # https://forum.numer.ai/t/rain-data-release/6657
    features = data[feature_names].to_numpy(dtype=np.float32, na_value=np.nan)
    features /= 4.0
    nans_per_col = np.isnan(features).sum(axis=0)
    logger.info('Checking for nans in the features')
    if nans_per_col.any():
        nans_per_col_count = {
            name: int(count)
            for name, count in zip(feature_names, nans_per_col)
            if count > 0
        }
        logger.info(f'Number of nans per column: {nans_per_col_count}')
        logger.info(f'Out of {features.shape[0]} total rows')
        logger.info('Filling nans with 0.5')
        np.nan_to_num(features, copy=False, nan=0.5)
    else:
        logger.info('No nans in the features!')
    eras = np.where(
        data[COLUMN_ERA] == 'X', np.finfo(np.float32).max, data[COLUMN_ERA]
    ).astype(np.float32)
    return np.column_stack((eras, features))


@dataclass(frozen=True)
class NumeraiModel:
    estimator: Any
    feature_names: list[str]
    target_names: list[str]

    def __call__(
        self,
        live_features: pd.DataFrame,
        live_benchmark_models: pd.DataFrame,
    ) -> pd.DataFrame:
        return self.predict(live_features, live_benchmark_models)

    def fit(
        self,
        features_and_targets: pd.DataFrame,
        benchmark_models: pd.DataFrame,
    ) -> Self:
        self.estimator.fit(
            unpack_numerai_features(features_and_targets, self.feature_names),
            features_and_targets[self.target_names].to_numpy(),
        )
        return self

    def predict(
        self,
        features: pd.DataFrame,
        benchmark_models: pd.DataFrame,
    ) -> pd.DataFrame:
        prediction = self.estimator.predict(
            unpack_numerai_features(features, self.feature_names)
        )
        return pd.DataFrame(
            {COLUMN_PREDICTION: np.ravel(prediction)}, index=features.index
        )
