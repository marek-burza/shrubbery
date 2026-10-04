import os
import time

from numerapi import NumerAPI

from shrubbery.observability import logger


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


napi = numerai_api()
