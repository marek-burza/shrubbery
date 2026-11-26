"""Readers for Claude Code session transcripts, shared by find_sessions.py and digest_session.py.

A transcript is `~/.claude/projects/<project>/<session>.jsonl`, one JSON record per line. Loading
a skill, by the Skill tool or by a slash command, adds a meta user record whose text is
`Base directory for this skill: <dir>`, a blank line, the SKILL.md body without its frontmatter
and, if the skill got arguments, `ARGUMENTS: <args>` after two blank lines. The version of a skill
is the first 12 hex digits of the sha256 of that body stripped of surrounding whitespace, so the
body a session ran and the current SKILL.md hash alike when they are the same text.
"""

# Code structure, to keep when editing this file:
# - Write code as small functions whose names state exactly what each does
#   (e.g. `extract_zip_safely`, `report_unused_runtime_dependencies`).
# - Keep code and functions short, concise, understandable and readable to a single SWE
#   reviewing: roughly under 30 lines, one responsibility each. No long monolithic functions.
# - Why: the code is audited personally by its maintainer.

import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path

SKILL_LOAD = re.compile(
    r'Base directory for this skill: (?P<dir>\S+)\n\n(?P<body>.*?)'
    r'(?:\n\n\nARGUMENTS: (?P<args>.*))?\Z',
    re.S,
)
FRONTMATTER = re.compile(r'\A---\n.*?\n---\n', re.S)
VERSION_DIGITS = 12


def read_records(path: Path) -> Iterator[dict]:
    with path.open(errors='replace') as lines:
        for line in lines:
            record = parse_record(line)
            if record:
                yield record


def parse_record(line: str) -> dict:
    try:
        record = json.loads(line)
    except ValueError:
        return {}
    return record if isinstance(record, dict) else {}


def content_blocks(record: dict) -> list[dict]:
    content = (record.get('message') or {}).get('content')
    if isinstance(content, str):
        return [{'type': 'text', 'text': content}]
    return [block for block in content or [] if isinstance(block, dict)]


def message_text(record: dict) -> str:
    return ''.join(
        block.get('text', '')
        for block in content_blocks(record)
        if block.get('type') == 'text'
    )


def loaded_skill(record: dict) -> re.Match | None:
    if record.get('type') != 'user' or not record.get('isMeta'):
        return None
    return SKILL_LOAD.match(message_text(record))


def skill_name(load: re.Match) -> str:
    return Path(load['dir']).name


def body_version(body: str) -> str:
    return hashlib.sha256(body.strip().encode()).hexdigest()[:VERSION_DIGITS]


def normalized_body(body: str) -> str:
    return body.strip() + '\n'


def current_skill_bodies(skills_dir: Path, prefix: str) -> dict[str, str]:
    return {
        path.parent.name: normalized_body(
            FRONTMATTER.sub('', path.read_text())
        )
        for path in sorted(skills_dir.glob(f'{prefix}*/SKILL.md'))
    }
