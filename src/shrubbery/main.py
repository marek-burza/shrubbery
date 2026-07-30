import argparse
import gc
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import GridSearchCV

from shrubbery.constants import (
    COLUMN_ERA,
    COLUMN_ID,
    RANDOM_SEED,
)
from shrubbery.data.augmentation import override_numerai_era
from shrubbery.data.ingest import (
    download_numerai_files,
    get_feature_set,
    get_training_targets,
    read_parquet_and_unpack,
)
from shrubbery.metrics import submit_diagnostic_predictions
from shrubbery.napi import napi
from shrubbery.observability import logger, silence_false_positive_warnings
from shrubbery.tournament import (
    submit_tournament_predictions,
    update_tournament_submissions,
)
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

    def run(self, config_content: bytes, config_name: str) -> None:
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
        update_tournament_submissions(self.numerai_model_id)
        tournament_round = napi.get_current_round()
        logger.info(f'Tournament round: {tournament_round}')
        logger.info(f'Model Name: {self.numerai_model_id}')
        logger.info(f'Notes: {self.notes}')
        download_numerai_files()
        feature_cols = get_feature_set(self.feature_set_name)
        targets = get_training_targets()
        read_columns = [COLUMN_ERA] + feature_cols + targets

        training_data, training_eras = read_parquet_and_unpack(
            'train.parquet', read_columns, feature_cols
        )
        validation_data, validation_eras = read_parquet_and_unpack(
            'validation.parquet', read_columns, feature_cols
        )
        live_data, _ = read_parquet_and_unpack(
            'live.parquet', read_columns, feature_cols
        )
        override_numerai_era(training_eras + validation_eras, live_data)

        # Check for nans and fill nans
        nans_per_col = live_data[feature_cols].isna().sum()
        logger.info('Checking for nans in the tournament data')
        if nans_per_col.any():
            total_rows = live_data.shape[0]
            nans_per_col_count = nans_per_col[nans_per_col > 0]
            logger.info(
                f'Number of nans per column this week: {nans_per_col_count}'
            )
            logger.info(f'Out of {total_rows} total rows')
            logger.info('Filling nans with 0.5')
            live_data.loc[:, feature_cols] = live_data.loc[
                :, feature_cols
            ].fillna(0.5)
        else:
            logger.info('No nans in the features this week!')
        # Load model if present
        model_name = f'model_{self.numerai_model_id}'
        model_file = Path(os.environ['NUMERAI_MODEL_PATH'])
        model = None if self.retrain else load_model(model_file)
        if model is None:
            logger.info(f'Training model: {model_name}')
            self.estimator = self.estimator.fit(
                training_data[[COLUMN_ERA] + feature_cols].to_numpy(),
                training_data[targets].to_numpy(),
            )
            store_model(self.estimator, model_file)
        else:
            self.estimator = model
        gc.collect()

        tournament_data = pd.DataFrame(live_data.index).set_index(COLUMN_ID)
        tournament_data['predictions'] = self.estimator.predict(
            live_data[[COLUMN_ERA] + feature_cols].to_numpy()
        )
        gc.collect()
        submit_tournament_predictions(tournament_data, self.numerai_model_id)

        try:
            diagnostic_data = pd.DataFrame(validation_data.index).set_index(
                COLUMN_ID
            )
            diagnostic_data['predictions'] = self.estimator.predict(
                validation_data[[COLUMN_ERA] + feature_cols].to_numpy()
            )
            gc.collect()
            submit_diagnostic_predictions(
                diagnostic_data, self.numerai_model_id
            )
        except MemoryError:
            traceback.print_exc()


def config_content(config_path: str) -> bytes:
    return Path(config_path).read_bytes()


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
        '--debug', action='store_true', help='Start bash shell in-situ'
    )
    arguments = parser.parse_args()
    if arguments.debug:
        subprocess.run('/bin/bash')
        sys.exit()
    return arguments
