import gc
import logging
import os
import re
import runpy
import traceback
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
import typer

from shrubbery import notes
from shrubbery.numerai.constants import (
    COLUMN_ERA,
    COLUMN_ID,
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
    numerai_models,
    submit_diagnostic_predictions,
    submit_tournament_predictions,
)
from shrubbery.numerai.observability import (
    dated_log_file,
    setup_logger,
    silence_false_positive_warnings,
)
from shrubbery.numerai.utilities import (
    load_model,
    store_model,
)

logger = logging.getLogger('shrubbery')

MODEL_NOTES = Path('data/numerai.data')


class NumeraiRunner:
    def __init__(
        self,
        timestamp: str,
        feature_set_name: str,
        retrain: bool,
        full: bool,
        diagnose: bool,
    ) -> None:
        self.timestamp = timestamp
        self.feature_set_name = feature_set_name
        self.retrain = retrain
        self.full = full
        self.diagnose = diagnose

    @property
    def model_script_file(self) -> Path:
        return Path(f'{self.timestamp}.py')

    @property
    def model_pickle_file(self) -> Path:
        model_directory_path = Path('./workspace') / SUBDIRECTORY_MODELS
        model_directory_path.mkdir(parents=True, exist_ok=True)
        return model_directory_path / f'{self.timestamp}.pkl'

    def load_estimator(self) -> Any:
        logger.info(f'Loading estimator from {self.model_script_file}')
        name_space = runpy.run_path(
            str(self.model_script_file), run_name=self.timestamp
        )
        return name_space['ESTIMATOR']

    def read_training_data(
        self, feature_names: list[str], target_names: list[str]
    ) -> pd.DataFrame:
        columns = [COLUMN_ERA, *feature_names, *target_names]
        train = read_numerai_parquet('train.parquet', columns)
        if not self.full:
            return train
        validation = read_numerai_parquet(
            'validation.parquet', columns
        ).dropna(subset=target_names)
        logger.info(
            f'Training on train ({len(train)} rows) and '
            f'validation ({len(validation)} rows with targets)'
        )
        return pd.concat([train, validation])

    def train_model(
        self, feature_names: list[str], target_names: list[str]
    ) -> NumeraiModel:
        logger.info(f'Training model: {self.timestamp}')
        model = NumeraiModel(
            self.load_estimator(), feature_names, target_names
        ).fit(
            self.read_training_data(feature_names, target_names),
            read_numerai_parquet('train_benchmark_models.parquet'),
        )
        store_model(model, self.model_pickle_file)
        return model

    def predict_with_ids(
        self, model: NumeraiModel, feature_names: list[str], data_name: str
    ) -> pd.DataFrame:
        features = read_numerai_parquet(
            f'{data_name}.parquet', [COLUMN_ID, COLUMN_ERA, *feature_names]
        )
        prediction = model(
            features,
            read_numerai_parquet(f'{data_name}_benchmark_models.parquet'),
        )
        return features[[COLUMN_ID, COLUMN_ERA]].join(prediction)

    def submit(self, model: NumeraiModel, feature_names: list[str]) -> None:
        numerai_model_id = (
            f'{os.environ["NUMERAI_MODEL_PREFIX"]}{self.timestamp}'
        )
        if numerai_model_id not in numerai_models():
            numerai_model_id = os.environ['NUMERAI_MODEL_PLACEHOLDER']
        logger.info(f'Numerai model: {numerai_model_id}')
        submit_tournament_predictions(
            self.predict_with_ids(model, feature_names, 'live'),
            numerai_model_id,
        )
        if not self.diagnose:
            return
        gc.collect()
        try:
            submit_diagnostic_predictions(
                self.predict_with_ids(model, feature_names, 'validation'),
                numerai_model_id,
            )
        except MemoryError:
            traceback.print_exc()

    def run(self) -> None:
        silence_false_positive_warnings()
        logger.info(f'Tournament round: {napi.get_current_round()}')
        logger.info(f'Model Name: {self.timestamp}')
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


def model_timestamp(timestamp: str) -> str:
    if re.fullmatch(r'[0-9]{14}', timestamp) is None:
        raise typer.BadParameter('must be 14 digits, YYYYmmddHHMMSS')
    return timestamp


def cache_noted_script(timestamp: str, script: Path) -> None:
    text = notes.note_text(MODEL_NOTES, notes.checked_timestamp(timestamp))
    if text is None:
        raise FileNotFoundError(f'No note at {timestamp} in {MODEL_NOTES}')
    script.write_text(text)
    logger.info(f'Wrote {script} from the note at {timestamp}')


app = typer.Typer(
    add_completion=False,
    context_settings={'help_option_names': ['-h', '--help']},
)


@app.command()
def main(
    model: Annotated[
        str,
        typer.Option(
            callback=model_timestamp,
            help=(
                'Timestamp of the model as YYYYmmddHHMMSS; the model is'
                ' NUMERAI_MODEL_PREFIX followed by it'
            ),
        ),
    ],
    retrain: Annotated[
        bool, typer.Option('--retrain', help='Use this flag to retrain')
    ] = False,
    diagnose: Annotated[
        bool,
        typer.Option(
            '--diagnose/--no-diagnose',
            help='Submit validation diagnostic predictions',
        ),
    ] = True,
    feature_set_name: Annotated[
        str, typer.Option(help='Name of the Numerai feature set')
    ] = 'small',
    full: Annotated[
        bool,
        typer.Option('--full', help='Train on training and validation data'),
    ] = False,
) -> None:
    setup_logger(dated_log_file())
    script = Path(f'{model}.py')
    if retrain and not script.exists():
        cache_noted_script(model, script)
    NumeraiRunner(
        timestamp=model,
        feature_set_name=feature_set_name,
        retrain=retrain,
        diagnose=diagnose,
        full=full,
    ).run()


if __name__ == '__main__':
    app()
