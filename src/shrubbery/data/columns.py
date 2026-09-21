from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, MetaEstimatorMixin, RegressorMixin
from sklearn.compose import ColumnTransformer

from shrubbery.constants import COLUMN_INDEX_ERA, COLUMN_INDEX_TARGET


class NumeraiFeaturesSelector(ColumnTransformer):
    def __init__(self) -> None:
        super().__init__(
            transformers=[('drop_era', 'drop', COLUMN_INDEX_ERA)],
            remainder='passthrough',
        )


class NumeraiTargetSelector(RegressorMixin, MetaEstimatorMixin, BaseEstimator):
    def __init__(
        self, estimator: Any, target: int = COLUMN_INDEX_TARGET
    ) -> None:
        self.estimator = estimator
        self.target = target

    def fit(
        self, x: np.ndarray, y: np.ndarray, **kwargs: dict[str, Any]
    ) -> 'NumeraiTargetSelector':
        target = self.target
        self.estimator.fit(x, y[:, [target]].ravel())
        self.fitted_ = True
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.estimator.predict(x)
