from pathlib import Path
from typing import Any

import cloudpickle
import pandas as pd

from shrubbery.numerai.observability import logger

MODEL_SUBDIRECTORY = 'models'


def store_model(model: Any, model_file: Path) -> None:
    with model_file.open('wb') as file:
        cloudpickle.dump(model, file)
    logger.info(f'Stored model: {model_to_string(model)}')


def load_model(model_file: Path) -> Any:
    if model_file.is_file():
        with model_file.open('rb') as file:
            model = cloudpickle.load(file)
        logger.info(f'Loaded model: {model_to_string(model)}')
    else:
        logger.error('Model failed to materialize')
        return None
    return model


def model_to_string(model: Any) -> str:
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    model_name = model.__class__.__name__
    model_parameters = model.get_params(deep=False)
    description = f'{model_name}; {model_parameters}'
    return description.replace(' ', '').replace('\n', '')
