import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from shrubbery.constants import COLUMN_ERA
from shrubbery.napi import napi
from shrubbery.observability import logger


def locate_numerai_file(file_name: str) -> Path:
    data_directory_path = Path('./workspace') / 'data'
    data_directory_path.mkdir(parents=True, exist_ok=True)
    file_path = data_directory_path / file_name
    return file_path


def download_file(file_name: str) -> None:
    file_path = locate_numerai_file(file_name)
    logger.info(f'Downloading {file_name} to {file_path}')
    napi.download_dataset(f'v5.3/{file_name}', str(file_path))
    if file_name.endswith('.parquet'):
        length = len(pd.read_parquet(file_path, columns=[]))
        logger.info(f'File {file_name} has {length} rows')


def log_all_dataset_entries() -> None:
    file_names = napi.list_datasets()
    digits = math.ceil(math.log10(len(file_names) + 1))
    for i, file_name in enumerate(file_names):
        logger.info(f'Dataset list entry #{str(i).zfill(digits)}: {file_name}')


def download_numerai_files():
    log_all_dataset_entries()
    logger.info('Downloading dataset files...')
    for file_name in [
        'train.parquet',
        'validation.parquet',
        'live.parquet',
        'features.json',
    ]:
        download_file(file_name)


def get_feature_set(selected_feature_set: str) -> list[str]:
    with open(locate_numerai_file('features.json'), 'r') as handle:
        feature_metadata = json.load(handle)
    all_features = set()
    for feature_set in feature_metadata['feature_sets'].values():
        all_features.update(feature_set)
    feature_count = len(all_features)
    logger.info(f'Feature count - all: {feature_count}')
    for feature_set in feature_metadata['feature_sets'].keys():
        feature_set_length = len(feature_metadata['feature_sets'][feature_set])
        logger.info(f'Feature count - {feature_set}: {feature_set_length}')
    features = feature_metadata['feature_sets'][selected_feature_set]
    return sorted(features)


def read_parquet_and_unpack(
    file_name: str, read_columns: list[str], feature_cols: list[str]
) -> pd.DataFrame:
    logger.info(f'Reading {file_name}')
    data = pd.read_parquet(
        locate_numerai_file(file_name), columns=read_columns
    )
    # For more information about int8 encoding, see:
    # https://forum.numer.ai/t/rain-data-release/6657
    data[feature_cols] = (
        data[feature_cols].apply(lambda x: x / 4.0).astype(np.float32)
    )
    # Not quite the "current era", but guaranteed to be ahead
    current_era = np.float32(napi.get_current_round())
    data_column_era = data[COLUMN_ERA]
    data_column_era = np.where(
        data_column_era == 'X', current_era, data_column_era
    )
    data[COLUMN_ERA] = data_column_era.astype(np.float32)
    return data


def get_training_targets() -> list[str]:
    with open(locate_numerai_file('features.json'), 'r') as handle:
        feature_metadata = json.load(handle)
    available_targets = feature_metadata['targets']
    train_parquet_file_path = locate_numerai_file('train.parquet')
    training_data = pd.read_parquet(
        train_parquet_file_path, columns=available_targets
    )
    finite_targets = [
        target
        for target in available_targets
        if not (
            np.isinf(training_data[target]).any()
            or np.isnan(training_data[target]).any()
        )
    ]
    for target in available_targets:
        if target not in finite_targets:
            logger.warning(
                f'Dropped {target} after checking for infinity & NaN'
            )
    finite_targets = sorted(finite_targets)
    logger.info(f'Targets - {finite_targets}')
    return finite_targets
