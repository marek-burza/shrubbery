import time

import pandas as pd
import requests

from shrubbery.napi import napi, resolve_numerai_model_id
from shrubbery.observability import logger
from shrubbery.utilities import save_prediction


def submit_tournament_predictions(
    df: pd.DataFrame, numerai_model_id: str
) -> None:
    pred_col = df.columns.to_list()[0]
    prediction_path = save_prediction(df, f'tournament_{pred_col}')
    # Upload validation prediction (Submissions -> Models -> Upload Submission)
    model_id = resolve_numerai_model_id(numerai_model_id)
    while True:
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
