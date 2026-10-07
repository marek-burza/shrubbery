import argparse
import gc
import os
import runpy
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import torch

from shrubbery.numerai.constants import COLUMN_ERA, RANDOM_SEED
from shrubbery.numerai.ingest import (
    download_numerai_files,
    get_feature_set,
    get_training_targets,
    read_numerai_parquet,
)
from shrubbery.numerai.model import NumeraiModel
from shrubbery.numerai.napi import (
    napi,
    submit_diagnostic_predictions,
    submit_tournament_predictions,
)
from shrubbery.numerai.observability import (
    logger,
    silence_false_positive_warnings,
)
from shrubbery.numerai.utilities import load_model, store_model


class NumeraiRunner:
    def __init__(
        self,
        feature_set_name: str,
        retrain: bool,
        estimator: Any,
        numerai_model_id: str,
        deterministic: bool,
    ) -> None:
        self.feature_set_name = feature_set_name
        self.retrain = retrain
        self.estimator = estimator
        self.numerai_model_id = numerai_model_id
        self.deterministic = deterministic

    def run(self) -> None:
        if self.deterministic:
            torch.manual_seed(RANDOM_SEED)
            np.random.seed(RANDOM_SEED)
        silence_false_positive_warnings()
        tournament_round = napi.get_current_round()
        logger.info(f'Tournament round: {tournament_round}')
        logger.info(f'Model Name: {self.numerai_model_id}')
        download_numerai_files()
        feature_names = get_feature_set(self.feature_set_name)
        target_names = get_training_targets()
        model_name = f'model_{self.numerai_model_id}'
        model_file = Path(os.environ['NUMERAI_MODEL_PATH'])
        estimator = None if self.retrain else load_model(model_file)
        if estimator is None:
            logger.info(f'Training model: {model_name}')
            model = NumeraiModel(
                self.estimator, feature_names, target_names
            ).fit(
                read_numerai_parquet(
                    'train.parquet',
                    [COLUMN_ERA, *feature_names, *target_names],
                ),
                read_numerai_parquet('train_benchmark_models.parquet'),
            )
            store_model(model.estimator, model_file)
        else:
            model = NumeraiModel(estimator, feature_names, target_names)
        gc.collect()

        submit_tournament_predictions(
            model(
                read_numerai_parquet(
                    'live.parquet', [COLUMN_ERA, *feature_names]
                ),
                read_numerai_parquet('live_benchmark_models.parquet'),
            ),
            self.numerai_model_id,
        )
        gc.collect()

        try:
            submit_diagnostic_predictions(
                model.predict(
                    read_numerai_parquet(
                        'validation.parquet', [COLUMN_ERA, *feature_names]
                    ),
                    read_numerai_parquet(
                        'validation_benchmark_models.parquet'
                    ),
                ),
                self.numerai_model_id,
            )
        except MemoryError:
            traceback.print_exc()


def main() -> None:
    parser = argparse.ArgumentParser(description='Shrubbery')
    parser.add_argument(
        '--model',
        type=str,
        default=os.environ['NUMERAI_MODEL'],
        help='Name of the model',
    )
    parser.add_argument(
        '--retrain', action='store_true', help='Use this flag to retrain'
    )
    arguments = parser.parse_args()
    model_path = f'{arguments.model}.py'
    name_space = runpy.run_path(model_path, run_name=arguments.model)
    NumeraiRunner(
        numerai_model_id=arguments.model,
        feature_set_name='small',
        retrain=arguments.retrain,
        deterministic=False,
        estimator=name_space['ESTIMATOR'],
    ).run()


if __name__ == '__main__':
    main()
