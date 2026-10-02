import argparse
import gc
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import torch

from shrubbery.constants import COLUMN_ERA, RANDOM_SEED
from shrubbery.data.ingest import (
    download_numerai_files,
    get_feature_set,
    get_training_targets,
    read_numerai_parquet,
)
from shrubbery.metrics import submit_diagnostic_predictions
from shrubbery.model import NumeraiModel
from shrubbery.napi import napi
from shrubbery.observability import logger, silence_false_positive_warnings
from shrubbery.tournament import submit_tournament_predictions
from shrubbery.utilities import load_model, store_model


class NumeraiRunner:
    def __init__(
        self,
        feature_set_name: str,
        retrain: bool,
        estimator: Any,
        numerai_model_id: str,
        version: str,
        notes: str,
        deterministic: bool,
    ) -> None:
        self.feature_set_name = feature_set_name
        self.retrain = retrain
        self.estimator = estimator
        self.numerai_model_id = numerai_model_id
        self.version = version
        self.notes = notes
        self.deterministic = deterministic

    def run(self) -> None:
        if self.deterministic:
            # Seeding pins every stochastic component (weight init, dropout,
            # DataLoader shuffling, GAN/denoise noise, unseeded RF bootstrap)
            # to a single draw. That makes runs reproducible but can lock
            # training onto a worse-than-average outcome compared to an
            # unseeded run, so only enable it when you specifically need
            # determinism.
            torch.manual_seed(RANDOM_SEED)
            np.random.seed(RANDOM_SEED)
        silence_false_positive_warnings()
        tournament_round = napi.get_current_round()
        logger.info(f'Tournament round: {tournament_round}')
        logger.info(f'Model Name: {self.numerai_model_id}')
        logger.info(f'Notes: {self.notes}')
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


def main_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Shrubbery')
    parser.add_argument(
        '--retrain', action='store_true', help='Use this flag to retrain'
    )
    parser.add_argument(
        '--training-era-stride',
        type=int,
        default=1,
        help='Use this argument to downsample eras by given stride',
    )
    parser.add_argument(
        '--live', action='store_true', help='Start bash shell in-situ'
    )
    arguments = parser.parse_args()
    if arguments.live:
        subprocess.run('/bin/bash')
        sys.exit()
    return arguments
