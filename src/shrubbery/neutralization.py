from typing import Any

import numpy as np
import pandas as pd
from numerai_tools.scoring import neutralize as numerai_tools_neutralize
from sklearn.base import BaseEstimator, MetaEstimatorMixin, RegressorMixin

from shrubbery.constants import (
    COLUMN_ERA,
    COLUMN_FEATURE_PREFIX,
    COLUMN_INDEX_ERA,
    COLUMN_TARGET,
)
from shrubbery.utilities import PrintableModelMixin


def _combine_x_y_into_frame(x: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    feature_count = x.shape[1] - COLUMN_INDEX_ERA - 1
    feature_columns = [
        f'{COLUMN_FEATURE_PREFIX}_{index}' for index in range(feature_count)
    ]
    frame = pd.DataFrame(x, columns=pd.Index([COLUMN_ERA] + feature_columns))
    frame[COLUMN_TARGET] = np.asarray(y).reshape(-1)
    return frame


class NumeraiToolsNeutralization(
    BaseEstimator, MetaEstimatorMixin, RegressorMixin, PrintableModelMixin
):
    def __init__(
        self,
        estimator: Any,
        neutralization_proportion: float,
    ) -> None:
        self.estimator = estimator
        self.neutralization_proportion = neutralization_proportion

    def fit(
        self, x: np.ndarray, y: np.ndarray, **kwargs: dict[str, Any]
    ) -> 'NumeraiToolsNeutralization':
        self.estimator = self.estimator.fit(x, y)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        predictions = self.estimator.predict(x)
        frame = _combine_x_y_into_frame(x, predictions)
        feature_columns = [
            column
            for column in frame.columns
            if column.startswith(COLUMN_FEATURE_PREFIX)
        ]
        neutralized = frame.groupby(COLUMN_ERA, group_keys=False).apply(
            lambda group: numerai_tools_neutralize(
                group[[COLUMN_TARGET]].copy(),
                group[feature_columns].copy(),
                self.neutralization_proportion,
            ),
            include_groups=False,
        )
        frame[COLUMN_TARGET] = neutralized[COLUMN_TARGET]
        # Ranking per era so columns combine safely on the same scales.
        # https://forum.numer.ai/t/neutralization-output-in-5-5-range/6324
        ranked = frame.groupby(COLUMN_ERA, group_keys=False)[
            COLUMN_TARGET
        ].rank(pct=True)
        return ranked.to_numpy().reshape(-1, 1)
