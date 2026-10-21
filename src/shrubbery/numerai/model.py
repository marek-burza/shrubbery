from dataclasses import dataclass
from typing import Any, Self

import numpy as np
import pandas as pd

from shrubbery.numerai.constants import COLUMN_ERA, COLUMN_PREDICTION


def unpack_numerai_features(
    data: pd.DataFrame, feature_names: list[str]
) -> np.ndarray:
    # For more information about int8 encoding, see:
    # https://forum.numer.ai/t/rain-data-release/6657
    features = data[feature_names].to_numpy(dtype=np.float32, na_value=np.nan)
    features /= 4.0
    eras = (
        (pd.to_datetime(data[COLUMN_ERA]) - pd.Timestamp(0))
        // pd.Timedelta(weeks=1)
    ).to_numpy(dtype=np.float32)
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
        feature_names = [
            name for name in self.feature_names if name != 'feature_country'
        ]
        self.estimator.fit(
            unpack_numerai_features(features_and_targets, feature_names),
            features_and_targets[self.target_names].to_numpy(),
        )
        return self

    def predict(
        self,
        features: pd.DataFrame,
        benchmark_models: pd.DataFrame,
    ) -> pd.DataFrame:
        feature_names = [
            name for name in self.feature_names if name != 'feature_country'
        ]
        prediction = self.estimator.predict(
            unpack_numerai_features(features, feature_names)
        )
        return pd.DataFrame(
            {COLUMN_PREDICTION: np.ravel(prediction)}, index=features.index
        )
