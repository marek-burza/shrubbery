import os

from xgboost import XGBRegressor

from shrubbery.main import NumeraiRunner, main_arguments
from shrubbery.neutralization import NumeraiToolsNeutralization

if __name__ == '__main__':
    arguments = main_arguments()
    NumeraiRunner(
        numerai_model_id=os.environ['NUMERAI_MODEL'],
        notes='Example',
        version='latest',
        feature_set_name='small',  # fncv3_features
        retrain=True,
        deterministic=False,
        estimator=NumeraiToolsNeutralization(
            neutralization_proportion=1.0,
            estimator=XGBRegressor(
                device='cuda',
                verbosity=1,
                n_jobs=-1,
            ),
        ),
    ).run()
