import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import cloudpickle
import pandas as pd

from shrubbery.numerai.model import NumeraiModel
from shrubbery.numerai.observability import logger


def loaded_shrubbery_modules() -> list[ModuleType]:
    modules = [
        module
        for name, module in list(sys.modules.items())
        if name == 'shrubbery' or name.startswith('shrubbery.')
    ]
    logger.info(
        f'Pickling by value: {sorted(module.__name__ for module in modules)}'
    )
    return modules


def store_model(model: NumeraiModel, model_file: Path) -> None:
    modules = loaded_shrubbery_modules()
    for module in modules:
        cloudpickle.register_pickle_by_value(module)
    try:
        with model_file.open('wb') as file:
            cloudpickle.dump(model, file)
    finally:
        for module in modules:
            cloudpickle.unregister_pickle_by_value(module)
    logger.info(f'Stored model: {model_to_string(model.estimator)}')
    logger.info(
        f'Stored {model_file} ({model_file.stat().st_size / 1e9:.3f} GB)'
    )


def load_model(model_file: Path) -> NumeraiModel:
    if not model_file.is_file():
        raise FileNotFoundError(f'No stored model at {model_file}. ')
    with model_file.open('rb') as file:
        model = cloudpickle.load(file)
    if type(model).__name__ != NumeraiModel.__name__:
        raise TypeError(f'{model_file} holds {type(model).__name__}.')
    logger.info(f'Loaded model: {model_to_string(model.estimator)}')
    logger.info(
        f'Stored {model_file} ({model_file.stat().st_size / 1e9:.3f} GB)'
    )
    return model


def model_to_string(model: Any) -> str:
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    model_name = model.__class__.__name__
    model_parameters = model.get_params(deep=False)
    description = f'{model_name}; {model_parameters}'
    return description.replace(' ', '').replace('\n', '')
