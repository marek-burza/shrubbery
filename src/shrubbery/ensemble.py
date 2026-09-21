import gc
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, MetaEstimatorMixin, RegressorMixin

from shrubbery.constants import COLUMN_INDEX_TARGET
from shrubbery.evaluation import METRIC_PREDICTION_VALUE, validation_metrics
from shrubbery.metrics import Metric
from shrubbery.mixer import mix_combinatorial, mix_predictions
from shrubbery.observability import logger
from shrubbery.utilities import PrintableModelMixin, model_to_string

METRIC = 'Metric'


@dataclass
class EstimatorConfig:
    name: str
    estimator: Any


class CombinatorialEnsembler(
    BaseEstimator, MetaEstimatorMixin, RegressorMixin, PrintableModelMixin
):
    def __init__(
        self,
        estimators: list[EstimatorConfig],
        ensemble_metric_function: Metric,
        mix_combinatorial_cap: int | None,
        cv: Any,
    ) -> None:
        self.estimators = estimators
        self.ensemble_metric_function = ensemble_metric_function
        self.ensemble_metric_greater_is_better = (
            ensemble_metric_function.greater_is_better
        )
        self.mix_combinatorial_cap = mix_combinatorial_cap
        self.cv = cv
        self.estimator_names_best_ = [config.name for config in estimators]

    def fit(
        self, x: np.ndarray, y: np.ndarray, **kwargs: dict[str, Any]
    ) -> 'CombinatorialEnsembler':
        # Consume all splits and keep the last one. For
        # NumeraiTimeSeriesSplitter the final fold trains on the earliest
        # eras and validates on the latest (era-disjoint, embargoed), which
        # keeps the holdout genuinely out-of-sample so time-ordered metrics
        # like Max Drawdown are meaningful instead of collapsing to 0.
        *_, (training_index, holdout_index) = self.cv.split(x, y)
        x_training = x[training_index]
        y_training = y[training_index]
        x_holdout = x[holdout_index]
        y_holdout = y[holdout_index]
        for config in self.estimators:
            # Now do a full train
            logger.info(f'Training ensemble model: {config.name}')
            logger.info(
                f'Ensemble model config: {model_to_string(config.estimator)}'
            )
            config.estimator = config.estimator.fit(x_training, y_training)
            # Garbage collection gets rid of unused data and frees up memory
            gc.collect()
        # Keep track of prediction columns and stats
        predictions: dict[str, np.ndarray] = {}
        validation_stats: list[dict[str, float]] = []
        for config in self.estimators:
            logger.info(f'Predicting ensemble model: {config.name}')
            logger.info(
                f'Ensemble model config: {model_to_string(config.estimator)}'
            )
            y_predictions = config.estimator.predict(x_holdout).clip(0.0, 1.0)
            predictions[config.name] = y_predictions
            validation_metrics(
                x_holdout,
                y_holdout[:, COLUMN_INDEX_TARGET].ravel(),
                y_predictions,
                self.ensemble_metric_function,
                validation_stats,
                config.name,
            )
            gc.collect()
        logger.info('Creating ensemble')
        ensemble_metric_function = self.ensemble_metric_function
        ensemble_metric_ascending = not self.ensemble_metric_greater_is_better
        best = mix_combinatorial(
            x_holdout,
            y_holdout[:, COLUMN_INDEX_TARGET].ravel(),
            predictions,
            ensemble_metric_function,
            validation_stats,
            sort_by=METRIC_PREDICTION_VALUE,
            sort_ascending=ensemble_metric_ascending,
            cap=self.mix_combinatorial_cap,
        )
        gc.collect()
        if best:
            logger.info(f'Ensemble with highest score: {best}')
            self.estimator_names_best_ = best
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        predictions: dict[str, np.ndarray] = {}
        for config in self.estimators:
            if config.name in self.estimator_names_best_:
                logger.info(f'Predicting ensemble model: {config.name}')
                logger.info(
                    f'Ensemble model config: {model_to_string(config.estimator)}'
                )
                predictions[config.name] = config.estimator.predict(
                    x.astype(np.float32)
                ).clip(0.0, 1.0)
                gc.collect()
        logger.info('Creating ensemble')
        logger.info(f'Ensemble: {self.estimator_names_best_}')
        return mix_predictions(predictions, self.estimator_names_best_)
