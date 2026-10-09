import base64
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from shrubbery import notes

BODY = '  Uses `numerai` models, "quoted" and \'single\'.\n\n**Why:** test\n\n'


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('SHRUBBERY_KEY', new_key())
    return tmp_path / notes.STORE


def new_key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def run(*args: str, stdin: str | None = None):
    return CliRunner().invoke(notes.app, list(args), input=stdin)


def add(kind: str, summary: str, body: str = BODY) -> str:
    result = run('add', kind, summary, stdin=body)
    assert result.exit_code == 0, result.output
    return result.stdout.strip()


def test_round_trip(store: Path) -> None:
    first = add('numerai', 'Live models in the sibling project')
    second = add('feedback', 'No em dashes')

    listed = run('list').stdout.splitlines()
    assert listed == [
        f'{first} numerai Live models in the sibling project',
        f'{second} feedback No em dashes',
    ]
    assert run('show', first).stdout == BODY


def test_list_filters_by_type(store: Path) -> None:
    first = add('numerai', 'First')
    add('feedback', 'Other')
    third = add('numerai', 'Third')

    assert run('list', 'numerai').stdout.splitlines() == [
        f'{first} numerai First',
        f'{third} numerai Third',
    ]
    assert run('list', 'financial').stdout == ''


@pytest.mark.parametrize('kind', ['two words', 'Numerai', ''])
def test_list_rejects_invalid_type(store: Path, kind: str) -> None:
    result = run('list', kind)
    assert result.exit_code == 1
    assert 'single lowercase word' in result.stderr


def test_store_is_encrypted(store: Path) -> None:
    add('numerai', 'Plainly visible summary')

    data = store.read_bytes()
    assert b'Plainly visible summary' not in data
    assert b'numerai' not in data
    assert b'SQLite format 3' not in data


def test_wrong_key_fails(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    add('numerai', 'Secret')
    monkeypatch.setenv('SHRUBBERY_KEY', new_key())

    result = run('list')
    assert result.exit_code == 1
    assert 'wrong SHRUBBERY_KEY' in result.stderr


def test_malformed_key_fails(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv('SHRUBBERY_KEY', 'not a key')

    result = run('list')
    assert result.exit_code == 1
    assert 'openssl rand -base64 32' in result.stderr


@pytest.mark.parametrize(
    ('kind', 'summary', 'body'),
    [
        ('two words', 'Summary', BODY),
        ('Numerai', 'Summary', BODY),
        ('numerai', 'Multi\nline', BODY),
        ('numerai', ' ', BODY),
        ('numerai', 'Summary', '  \n'),
    ],
)
def test_invalid_note_is_rejected(
    store: Path, kind: str, summary: str, body: str
) -> None:
    result = run('add', kind, summary, stdin=body)
    assert result.exit_code == 1
    assert not store.exists()


def test_timestamp_option(store: Path) -> None:
    timestamp = '2026-01-02T03:04:05.000006Z'
    result = run('add', '--timestamp', timestamp, 'numerai', 'Old', stdin=BODY)
    assert result.exit_code == 0, result.output
    assert result.stdout == f'{timestamp}\n'
    later = add('numerai', 'New')

    assert run('list').stdout.splitlines() == [
        f'{timestamp} numerai Old',
        f'{later} numerai New',
    ]
    duplicate = run(
        'add', '--timestamp', timestamp, 'numerai', 'X', stdin=BODY
    )
    assert duplicate.exit_code == 1
    assert 'already exists' in duplicate.stderr


@pytest.mark.parametrize(
    'timestamp',
    ['2026-01-02', '2026-01-02T03:04:05Z', '2026-01-02T03:04:05.1Z', 'now'],
)
def test_invalid_timestamp_is_rejected(store: Path, timestamp: str) -> None:
    result = run('add', '--timestamp', timestamp, 'numerai', 'X', stdin=BODY)
    assert result.exit_code == 1
    assert not store.exists()


def test_delete(store: Path) -> None:
    kept = add('numerai', 'Kept')
    removed = add('numerai', 'Removed')

    assert run('delete', removed).exit_code == 0
    assert run('list').stdout.splitlines() == [f'{kept} numerai Kept']
    assert run('show', removed).exit_code == 1
    assert run('delete', removed).exit_code == 1


def test_store_option(tmp_path: Path, store: Path) -> None:
    custom = tmp_path / 'elsewhere' / 'memory.data'
    result = run('--store', str(custom), 'add', 'numerai', 'Moved', stdin=BODY)
    assert result.exit_code == 0, result.output

    assert set(custom.parent.iterdir()) == {
        custom,
        custom.with_suffix('.lock'),
    }
    assert not store.parent.exists()
    assert run('list').stdout == ''
    listed = run('--store', str(custom), 'list').stdout
    assert listed.endswith(' numerai Moved\n')
