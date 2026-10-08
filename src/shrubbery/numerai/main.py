import argparse
import gc
import os
import runpy
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import torch

from shrubbery.numerai.constants import (
    COLUMN_ERA,
    RANDOM_SEED,
    SUBDIRECTORY_MODELS,
)
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
from shrubbery.numerai.utilities import (
    load_model,
    store_model,
)


class NumeraiRunner:
    def __init__(
        self,
        numerai_model_id: str,
        feature_set_name: str,
        retrain: bool,
    ) -> None:
        self.numerai_model_id = numerai_model_id
        self.feature_set_name = feature_set_name
        self.retrain = retrain

    @property
    def model_script_file(self) -> Path:
        return Path(f'{self.numerai_model_id}.py')

    @property
    def model_pickle_file(self) -> Path:
        model_directory_path = Path('./workspace') / SUBDIRECTORY_MODELS
        model_directory_path.mkdir(parents=True, exist_ok=True)
        return model_directory_path / f'model_{self.numerai_model_id}.pkl'

    def load_estimator(self) -> Any:
        logger.info(f'Loading estimator from {self.model_script_file}')
        name_space = runpy.run_path(
            str(self.model_script_file), run_name=self.numerai_model_id
        )
        return name_space['ESTIMATOR']

    def train_model(
        self, feature_names: list[str], target_names: list[str]
    ) -> NumeraiModel:
        logger.info(f'Training model: {self.numerai_model_id}')
        model = NumeraiModel(
            self.load_estimator(), feature_names, target_names
        ).fit(
            read_numerai_parquet(
                'train.parquet',
                [COLUMN_ERA, *feature_names, *target_names],
            ),
            read_numerai_parquet('train_benchmark_models.parquet'),
        )
        store_model(model, self.model_pickle_file)
        return model

    def submit(self, model: NumeraiModel, feature_names: list[str]) -> None:
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
                        'validation.parquet',
                        [COLUMN_ERA, *feature_names],
                    ),
                    read_numerai_parquet(
                        'validation_benchmark_models.parquet'
                    ),
                ),
                self.numerai_model_id,
            )
        except MemoryError:
            traceback.print_exc()

    def run(self) -> None:
        silence_false_positive_warnings()
        logger.info(f'Tournament round: {napi.get_current_round()}')
        logger.info(f'Model Name: {self.numerai_model_id}')
        download_numerai_files()
        feature_names = get_feature_set(self.feature_set_name)
        target_names = get_training_targets()
        model = (
            self.train_model(feature_names, target_names)
            if self.retrain
            else load_model(self.model_pickle_file)
        )
        gc.collect()
        self.submit(model, feature_names)


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
    NumeraiRunner(
        numerai_model_id=arguments.model,
        feature_set_name='small',
        retrain=arguments.retrain,
    ).run()


if __name__ == '__main__':
    main()
