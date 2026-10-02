from dataclasses import dataclass
from typing import Any, Self

import numpy as np
import pandas as pd

from shrubbery.constants import COLUMN_PREDICTION
from shrubbery.data.ingest import unpack_numerai_features


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
