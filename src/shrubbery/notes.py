import base64
import binascii
import fcntl
import lzma
import os
import re
import sqlite3
import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from nacl.exceptions import CryptoError
from nacl.secret import SecretBox

HELP = """
Agent memory: notes in a single table SQLite store, `lzma` compressed and
encrypted with `SecretBox` under `SHRUBBERY_KEY` in `data/notes.data`.

Each note has a unique UTC `timestamp` (its id), a single word `type`, a one
line `summary` and a Markdown `text`. `list` prints one note per line,
`show` prints the text of one note verbatim, `add` reads the text from stdin and
prints the new timestamp (now unless `--timestamp` is given), `delete` removes a
note.
"""

STORE = Path('data/notes.data')
SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    timestamp TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    summary TEXT NOT NULL,
    text TEXT NOT NULL
)
"""

app = typer.Typer(
    help=HELP,
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode='markdown',
    context_settings={'help_option_names': ['-h', '--help']},
)


def fail(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(1)


def secret_box() -> SecretBox:
    try:
        key = base64.b64decode(os.environ['SHRUBBERY_KEY'], validate=True)
        return SecretBox(key)
    except (KeyError, binascii.Error, ValueError, TypeError):
        raise fail(
            'SHRUBBERY_KEY must be the output of openssl rand -base64 32'
        )


def load(store: Path, box: SecretBox) -> sqlite3.Connection:
    con = sqlite3.connect(':memory:')
    if store.exists():
        try:
            data = lzma.decompress(box.decrypt(store.read_bytes()))
        except CryptoError:
            raise fail(f'wrong SHRUBBERY_KEY or corrupted {store}')
        con.deserialize(data)
    con.execute(SCHEMA)
    return con


def save(store: Path, con: sqlite3.Connection, box: SecretBox) -> None:
    con.commit()
    con.execute('VACUUM')
    temporary = store.with_suffix('.tmp')
    temporary.write_bytes(
        box.encrypt(lzma.compress(con.serialize(), preset=9))
    )
    temporary.replace(store)


@contextmanager
def locked(store: Path) -> Generator[None]:
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'


def now() -> str:
    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


def is_timestamp(timestamp: str) -> bool:
    try:
        parsed = datetime.strptime(timestamp, TIMESTAMP_FORMAT)
    except ValueError:
        return False
    return parsed.strftime(TIMESTAMP_FORMAT) == timestamp


@app.callback()
def main(
    ctx: typer.Context,
    store: Annotated[
        Path,
        typer.Option(help='Encrypted store; the lock file sits next to it'),
    ] = STORE,
) -> None:
    ctx.obj = store


@app.command('list', help='One line per note: timestamp, type, summary')
def list_notes(ctx: typer.Context) -> None:
    rows = load(ctx.obj, secret_box()).execute(
        'SELECT timestamp, type, summary FROM notes ORDER BY timestamp'
    )
    for timestamp, kind, summary in rows:
        typer.echo(f'{timestamp} {kind} {summary}')


@app.command(help='The text of the note, verbatim')
def show(ctx: typer.Context, timestamp: str) -> None:
    row = (
        load(ctx.obj, secret_box())
        .execute('SELECT text FROM notes WHERE timestamp = ?', (timestamp,))
        .fetchone()
    )
    if row is None:
        raise fail(f'no note at {timestamp}')
    sys.stdout.write(row[0])


@app.command(help='Add a note with the text from stdin, print its timestamp')
def add(
    ctx: typer.Context,
    kind: Annotated[
        str, typer.Argument(metavar='TYPE', help='Single word, e.g. numerai')
    ],
    summary: Annotated[str, typer.Argument(help='One line')],
    timestamp: Annotated[
        str,
        typer.Option(
            default_factory=now,
            show_default='now',
            help='UTC, e.g. 2026-10-09T11:47:03.123456Z',
        ),
    ],
) -> None:
    text = sys.stdin.read()
    if not is_timestamp(timestamp):
        raise fail('TIMESTAMP must look like 2026-10-09T11:47:03.123456Z')
    if not re.fullmatch(r'[a-z]+', kind):
        raise fail('TYPE must be a single lowercase word')
    if not summary.strip() or '\n' in summary:
        raise fail('SUMMARY must be a single non-empty line')
    if not text.strip():
        raise fail('the text on stdin must not be empty')
    box = secret_box()
    with locked(ctx.obj):
        con = load(ctx.obj, box)
        try:
            con.execute(
                'INSERT INTO notes VALUES (?, ?, ?, ?)',
                (timestamp, kind, summary.strip(), text),
            )
        except sqlite3.IntegrityError:
            raise fail(f'a note at {timestamp} already exists')
        save(ctx.obj, con, box)
    typer.echo(timestamp)


@app.command(help='Delete the note at the timestamp')
def delete(ctx: typer.Context, timestamp: str) -> None:
    box = secret_box()
    with locked(ctx.obj):
        con = load(ctx.obj, box)
        deleted = con.execute(
            'DELETE FROM notes WHERE timestamp = ?', (timestamp,)
        ).rowcount
        if not deleted:
            raise fail(f'no note at {timestamp}')
        save(ctx.obj, con, box)
