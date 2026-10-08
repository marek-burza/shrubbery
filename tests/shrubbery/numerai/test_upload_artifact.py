import inspect
import os
import pickle
import pickletools
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.dummy import DummyRegressor

from shrubbery.numerai.constants import (
    COLUMN_ERA,
    COLUMN_INDEX_ERA,
    COLUMN_PREDICTION,
)
from shrubbery.numerai.main import NumeraiRunner
from shrubbery.numerai.model import NumeraiModel
from shrubbery.numerai.utilities import load_model, store_model

FEATURE_NAMES = ['feature_a', 'feature_b', 'feature_c']


class PerEraRanker(BaseEstimator, RegressorMixin):
    def fit(self, x: np.ndarray, y: np.ndarray) -> 'PerEraRanker':
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        frame = pd.DataFrame(
            {
                COLUMN_ERA: x[:, COLUMN_INDEX_ERA],
                'raw': x[:, COLUMN_INDEX_ERA + 1 :].sum(axis=1),
            }
        )
        ranked = frame.groupby(COLUMN_ERA, group_keys=False)['raw'].rank(
            pct=True
        )
        return ranked.to_numpy().reshape(-1, 1)


def make_frame(eras: list[str], rows_per_era: int = 20) -> pd.DataFrame:
    generator = np.random.default_rng(0)
    rows = len(eras) * rows_per_era
    frame = pd.DataFrame(
        {
            name: generator.integers(0, 5, rows).astype(np.int8)
            for name in FEATURE_NAMES
        },
        index=pd.Index([f'id{row}' for row in range(rows)], name='id'),
    )
    frame[COLUMN_ERA] = np.repeat(eras, rows_per_era)
    frame['target'] = generator.random(rows)
    return frame


def make_model(estimator: Any = None) -> NumeraiModel:
    frame = make_frame(['0001', '0002'])
    return NumeraiModel(
        estimator if estimator is not None else PerEraRanker(),
        FEATURE_NAMES,
        ['target'],
    ).fit(frame, pd.DataFrame())


def live_frame() -> pd.DataFrame:
    frame = make_frame(['X'])
    return frame.drop(columns=['target'])


def shrubbery_globals(blob: bytes) -> list[str]:
    strings: list[str] = []
    found: list[str] = []
    for opcode, argument, _ in pickletools.genops(blob):
        if opcode.name in ('SHORT_BINUNICODE', 'BINUNICODE', 'UNICODE'):
            strings.append(str(argument))
        elif opcode.name == 'STACK_GLOBAL' and len(strings) >= 2:
            attribute = strings.pop()
            module = strings.pop()
            if module.startswith('shrubbery'):
                found.append(f'{module}.{attribute}')
        elif opcode.name == 'GLOBAL' and str(argument).startswith('shrubbery'):
            found.append(str(argument))
    return found


def test_stored_artifact_reports_two_parameters(tmp_path: Path) -> None:
    model_file = tmp_path / 'model.pkl'
    store_model(make_model(), model_file)
    reloaded = cast(Any, pd.read_pickle(model_file))
    assert len(inspect.signature(reloaded).parameters) == 2


def test_prediction_satisfies_the_runner_contract() -> None:
    frame = live_frame()
    prediction = make_model()(frame, pd.DataFrame())
    assert type(prediction) is pd.DataFrame
    assert list(prediction.columns) == [COLUMN_PREDICTION]
    assert prediction.index.equals(frame.index)
    assert not prediction.empty
    assert not prediction.isna().any().any()
    assert prediction[COLUMN_PREDICTION].between(0, 1).all()


def test_estimator_receives_the_era_as_the_first_column() -> None:
    class Recorder(BaseEstimator, RegressorMixin):
        def fit(self, x: np.ndarray, y: np.ndarray) -> 'Recorder':
            return self

        def predict(self, x: np.ndarray) -> np.ndarray:
            self.seen_ = x
            return np.zeros(len(x))

    frame = make_frame(['0001', '0002']).drop(columns=['target'])
    model = NumeraiModel(Recorder(), FEATURE_NAMES, ['target'])
    model.predict(frame, pd.DataFrame())
    eras = model.estimator.seen_[:, COLUMN_INDEX_ERA]
    assert model.estimator.seen_.shape == (40, len(FEATURE_NAMES) + 1)
    assert sorted(np.unique(eras).tolist()) == [1.0, 2.0]
    assert (eras == 1.0).sum() == 20


def test_prediction_ranks_within_era_not_across_eras() -> None:
    frame = make_frame(['0001', '0002']).drop(columns=['target'])
    prediction = make_model().predict(frame, pd.DataFrame())
    per_era = prediction[COLUMN_PREDICTION].groupby(
        frame[COLUMN_ERA].to_numpy()
    )
    assert per_era.count().eq(20).all()
    assert per_era.max().gt(0.9).all()
    assert per_era.min().lt(0.1).all()


def test_live_era_matches_its_numeric_substitute() -> None:
    model = make_model()
    symbolic = live_frame()
    numeric = symbolic.copy()
    numeric[COLUMN_ERA] = np.finfo(np.float32).max
    assert model(symbolic, pd.DataFrame()).equals(
        model(numeric, pd.DataFrame())
    )


def test_missing_artifact_is_an_error_not_a_training_run(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match='No stored model at'):
        load_model(tmp_path / 'absent.pkl')


def test_bare_estimator_artifact_is_rejected(tmp_path: Path) -> None:
    model_file = tmp_path / 'model.pkl'
    store_model(make_model(), model_file)
    model_file.write_bytes(pickle.dumps(DummyRegressor()))
    with pytest.raises(TypeError, match='holds DummyRegressor'):
        load_model(model_file)


def test_inference_uses_the_feature_names_from_the_artifact(
    tmp_path: Path,
) -> None:
    model_file = tmp_path / 'model.pkl'
    store_model(make_model(), model_file)
    assert load_model(model_file).feature_names == FEATURE_NAMES


def test_runner_derives_both_paths_from_the_model_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = NumeraiRunner('faint', 'small', retrain=False)
    assert runner.model_script_file == Path('faint.py')
    assert runner.model_pickle_file == Path('workspace/models/model_faint.pkl')


def test_artifact_carries_no_shrubbery_import(tmp_path: Path) -> None:
    model = make_model(DummyRegressor())
    model_file = tmp_path / 'model.pkl'
    store_model(model, model_file)
    assert shrubbery_globals(pickle.dumps(model)), (
        'detector must find the import that plain pickling leaves behind'
    )
    assert shrubbery_globals(model_file.read_bytes()) == []


def test_artifact_loads_without_shrubbery_installed(tmp_path: Path) -> None:
    model_file = tmp_path / 'model.pkl'
    store_model(make_model(DummyRegressor()), model_file)
    script = f"""
import sys


class Blocker:
    def find_module(self, name, path=None):
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        if name == 'shrubbery' or name.startswith('shrubbery.'):
            raise ModuleNotFoundError(name)
        return None


for name in list(sys.modules):
    if name == 'shrubbery' or name.startswith('shrubbery.'):
        del sys.modules[name]
sys.meta_path.insert(0, Blocker())

import pandas as pd

model = pd.read_pickle({str(model_file)!r})
frame = pd.read_parquet({str(tmp_path / 'live.parquet')!r})
prediction = model(frame, pd.DataFrame())
assert 'shrubbery' not in sys.modules
assert type(prediction) is pd.DataFrame
assert not prediction.isna().any().any()
print('ok')
"""
    live_frame().to_parquet(tmp_path / 'live.parquet')
    result = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert 'ok' in result.stdout


@pytest.mark.skipif(
    not Path('/proc/driver/nvidia').exists(), reason='needs an NVIDIA GPU'
)
def test_gpu_fitted_model_predicts_on_cpu(tmp_path: Path) -> None:
    from xgboost import XGBRegressor

    frame = make_frame(['0001', '0002'])
    model = NumeraiModel(
        XGBRegressor(device='cuda', n_estimators=10, max_depth=3),
        FEATURE_NAMES,
        ['target'],
    ).fit(frame, pd.DataFrame())
    model_file = tmp_path / 'model.pkl'
    store_model(model, model_file)
    live = live_frame()
    live.to_parquet(tmp_path / 'live.parquet')
    on_gpu = model(live, pd.DataFrame())
    prediction_file = tmp_path / 'prediction.parquet'
    script = (
        'import pandas as pd;'
        f'model = pd.read_pickle({str(model_file)!r});'
        f'frame = pd.read_parquet({str(tmp_path / "live.parquet")!r});'
        'model(frame, pd.DataFrame())'
        f'.to_parquet({str(prediction_file)!r})'
    )
    result = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True,
        text=True,
        env={**os.environ, 'CUDA_VISIBLE_DEVICES': ''},
    )
    assert result.returncode == 0, result.stderr
    on_cpu = pd.read_parquet(prediction_file)
    assert np.allclose(on_gpu.to_numpy(), on_cpu.to_numpy())
