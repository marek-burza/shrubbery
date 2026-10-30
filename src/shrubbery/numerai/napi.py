import itertools
import os
import time
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import requests
from numerapi import NumerAPI

from shrubbery.numerai.constants import (
    COLUMN_ERA,
    COLUMN_ID,
    COLUMN_PREDICTION,
    COLUMN_SIGNAL,
)
from shrubbery.numerai.observability import logger


def numerai_api() -> NumerAPI:
    public_id = os.environ.get('NUMERAI_PUBLIC_ID')
    secret_key = os.environ.get('NUMERAI_SECRET_KEY')
    while True:
        try:
            napi = NumerAPI(public_id=public_id, secret_key=secret_key)
            return napi
        except Exception:
            logger.exception('Login failed')
            time.sleep(10)


def numerai_models() -> list[str]:
    return list(napi.get_models().keys())


def resolve_numerai_model_id(model_name: str) -> str:
    try:
        account_models = napi.get_models()
    except Exception:
        account_models = {}
    if model_name in account_models:
        return account_models[model_name]
    profile = napi.public_user_profile(model_name)
    if not profile:
        raise ValueError(f'Unknown Numerai model: {model_name}')
    return profile['id']


def upload_frame(df: pd.DataFrame, id_columns: list[str]) -> pd.DataFrame:
    frame = df.rename(columns={COLUMN_PREDICTION: COLUMN_SIGNAL})[
        [*id_columns, COLUMN_SIGNAL]
    ]
    if frame.duplicated(subset=id_columns).any():
        raise ValueError(f'Duplicate {id_columns} in predictions')
    if not frame[COLUMN_SIGNAL].between(0, 1).all():
        raise ValueError(f'{COLUMN_SIGNAL} is NaN or outside [0, 1]')
    return frame


def save_prediction(
    df: pd.DataFrame, name: str, id_columns: list[str]
) -> Path:
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    name = f'{stamp}_{name}'
    frame = upload_frame(df, id_columns)
    with NamedTemporaryFile(
        prefix=f'{name}_', suffix='.csv', delete=False
    ) as prediction_file:
        prediction_path = Path(prediction_file.name)
    frame.to_csv(prediction_path, index=False)
    return prediction_path


def upload_attempts(tries: int | None) -> range | itertools.count:
    return itertools.count() if tries is None else range(tries)


def submit_diagnostic_predictions(
    prediction_data: pd.DataFrame,
    numerai_model_id: str,
    tries: int | None = 10,
) -> dict[str, float]:
    prediction_name = 'validation'
    prediction_path = save_prediction(
        prediction_data, prediction_name, [COLUMN_ID, COLUMN_ERA]
    )
    model_id = resolve_numerai_model_id(numerai_model_id)
    for _ in range(3):
        diagnostics_ids = []
        # Upload validation prediction (Scores -> Models -> Run Diagnostics)
        for _ in upload_attempts(tries):
            try:
                logger.info('Uploading diagnostic predictions')
                diagnostics_id = napi.upload_diagnostics(
                    file_path=str(prediction_path),
                    model_id=model_id,
                )
                diagnostics_ids.append(diagnostics_id)
                logger.info('Uploaded diagnostic predictions')
                break
            except requests.exceptions.HTTPError as error:
                if (
                    error.response is not None
                    and error.response.status_code == 429
                ):
                    logger.info('Backing off upload of diagnostic predictions')
                    time.sleep(60)
                else:
                    logger.exception(
                        'Network failure for diagnostic predictions'
                    )
                    time.sleep(60)
            except Exception:
                logger.exception('Upload failure for diagnostic predictions')
                time.sleep(10)
        else:
            logger.error(
                f'Gave up uploading diagnostic predictions after {tries} tries'
            )
            return {}
        # Fetch diagnostics
        for _ in range(5):
            for diagnostics_id in diagnostics_ids:
                diagnostics = napi.diagnostics(
                    model_id=model_id, diagnostics_id=diagnostics_id
                )[0]
                if diagnostics['status'] == 'done':
                    break
            if diagnostics['status'] == 'done':
                break
            time.sleep(60)
        if diagnostics['status'] == 'done':
            break
    metrics = {}
    if diagnostics['status'] == 'done':
        logger.info('Got diagnostic predictions')
        for key, value in diagnostics.items():
            if isinstance(value, float) or isinstance(value, int):
                metrics[key] = float(value)
                logger.info(f'Numerai Diagnostics - {key}: {metrics[key]}')
    return metrics


def submit_tournament_predictions(
    df: pd.DataFrame, numerai_model_id: str, tries: int | None = 10
) -> None:
    prediction_path = save_prediction(
        df, f'tournament_{COLUMN_SIGNAL}', [COLUMN_ID]
    )
    # Upload validation prediction (Submissions -> Models -> Upload Submission)
    model_id = resolve_numerai_model_id(numerai_model_id)
    for _ in upload_attempts(tries):
        try:
            logger.info('Submitting tournament predictions')
            napi.upload_predictions(
                file_path=str(prediction_path),
                model_id=model_id,
            )
            logger.info('Submitted tournament predictions')
            break
        except requests.exceptions.HTTPError as error:
            if (
                error.response is not None
                and error.response.status_code == 429
            ):
                logger.info('Backing off upload of tournament predictions')
                time.sleep(30 * 60)
            else:
                logger.exception('Network failure for tournament predictions')
                time.sleep(60)
        except Exception as error:
            logger.exception('Submission failure for tournament predictions')
            if 'Are you using the latest live ids' in str(error):
                break
            time.sleep(10)
    else:
        logger.error(
            f'Gave up submitting tournament predictions after {tries} tries'
        )


napi = numerai_api()
