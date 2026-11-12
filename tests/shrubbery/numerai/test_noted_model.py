import base64
import os
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from shrubbery import notes
from shrubbery.numerai import main
from shrubbery.numerai.model import NumeraiModel

SCRIPT = 'ESTIMATOR = None\n'


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        'SHRUBBERY_KEY', base64.b64encode(os.urandom(32)).decode()
    )
    monkeypatch.setenv('NUMERAI_MODEL_PREFIX', 'example')
    return tmp_path / main.MODEL_NOTES


def test_model_timestamp() -> None:
    assert main.model_timestamp('20261008111501') == '20261008111501'
    for model in ('example20261008111501', 'example', '2026100811150'):
        with pytest.raises(typer.BadParameter):
            main.model_timestamp(model)


@pytest.mark.parametrize(
    ('timestamp', 'numerai_model_id'),
    [
        ('20261008111501', 'example20261008111501'),
        ('20261015160106', 'example'),
    ],
)
def test_submit_falls_back_to_placeholder(
    store: Path,
    monkeypatch: pytest.MonkeyPatch,
    timestamp: str,
    numerai_model_id: str,
) -> None:
    monkeypatch.setenv('NUMERAI_MODEL_PLACEHOLDER', 'example')
    monkeypatch.setattr(
        main, 'numerai_models', lambda: ['example', 'example20261008111501']
    )
    submitted = []
    monkeypatch.setattr(
        main,
        'submit_tournament_predictions',
        lambda predictions, model_id: submitted.append(model_id),
    )
    runner = main.NumeraiRunner(
        timestamp,
        'small',
        retrain=False,
        full=False,
        diagnose=main.DiagnoseMode.NONE,
    )
    monkeypatch.setattr(runner, 'predict_with_ids', lambda *args: None)

    runner.submit(NumeraiModel(None, [], []), [])

    assert submitted == [numerai_model_id]


@pytest.mark.parametrize(
    ('mode', 'expected'),
    [
        (main.DiagnoseMode.NONE, []),
        (main.DiagnoseMode.HOSTED, ['hosted']),
        (main.DiagnoseMode.LOCAL, ['local/60']),
    ],
)
def test_submit_dispatches_on_diagnose_mode(
    store: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: main.DiagnoseMode,
    expected: list[str],
) -> None:
    monkeypatch.setattr(
        main, 'numerai_models', lambda: ['example20261008111501']
    )
    monkeypatch.setattr(main, 'submit_tournament_predictions', lambda *a: None)
    diagnosed = []
    monkeypatch.setattr(
        main,
        'submit_diagnostic_predictions',
        lambda *args: diagnosed.append('hosted'),
    )
    monkeypatch.setattr(
        main,
        'compute_local_diagnostics',
        lambda predictions, embargo: diagnosed.append(f'local/{embargo}'),
    )
    runner = main.NumeraiRunner(
        '20261008111501',
        'small',
        retrain=False,
        full=False,
        diagnose=mode,
        diagnose_embargo=60,
    )
    monkeypatch.setattr(runner, 'predict_with_ids', lambda *args: None)

    runner.submit(NumeraiModel(None, [], []), [])

    assert diagnosed == expected


def test_diagnose_option_takes_a_mode() -> None:
    result = CliRunner().invoke(
        main.app, ['--model', '20261008111501', '--diagnose', 'yes']
    )
    assert result.exit_code != 0
    assert 'none' in result.output and 'local' in result.output


def test_cache_noted_script(store: Path) -> None:
    result = CliRunner().invoke(
        notes.app,
        [
            '--store',
            str(store),
            'add',
            '--timestamp',
            '20261008111501',
            'model',
            'manual corr=- | test',
        ],
        input=SCRIPT,
    )
    assert result.exit_code == 0, result.output
    script = Path('20261008111501.py')

    main.cache_noted_script('20261008111501', script)

    assert script.read_text() == SCRIPT


def test_missing_note_fails(store: Path) -> None:
    with pytest.raises(FileNotFoundError):
        main.cache_noted_script('20261008111501', Path('20261008111501.py'))
    assert not Path('20261008111501.py').exists()
