import time

import pandas as pd
import requests

from shrubbery.napi import napi, resolve_numerai_model_id
from shrubbery.observability import logger
from shrubbery.utilities import save_prediction


def submit_diagnostic_predictions(
    prediction_data: pd.DataFrame, numerai_model_id: str
) -> dict[str, float]:
    prediction_name = 'validation'
    prediction_path = save_prediction(prediction_data, prediction_name)
    model_id = resolve_numerai_model_id(numerai_model_id)
    for _ in range(3):
        diagnostics_ids = []
        # Upload validation prediction (Scores -> Models -> Run Diagnostics)
        while True:
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
    metrics = {}
    if diagnostics['status'] == 'done':
        logger.info('Got diagnostic predictions')
        for key, value in diagnostics.items():
            if isinstance(value, float) or isinstance(value, int):
                metrics[key] = float(value)
                logger.info(f'Numerai Diagnostics - {key}: {metrics[key]}')
    return metrics
