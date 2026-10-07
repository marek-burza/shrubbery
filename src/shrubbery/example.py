from xgboost import XGBRegressor

ESTIMATOR = XGBRegressor(
    device='cuda',
    verbosity=1,
    n_jobs=-1,
)
