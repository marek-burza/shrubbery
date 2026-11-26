"""Find the Claude Code sessions that used or edited the skills of a name prefix.

Scans the main transcripts `<projects-dir>/*/<session>.jsonl` (subagent transcripts are counted,
not scanned) and prints a JSON array, oldest session first, of the sessions active at or after
`--since` that loaded a skill named `<prefix>*` (role `used`) or only edited files under
`.claude/skills/<prefix>*` with the Edit or Write tools (role `authored`). Each skill load
carries the version of the body the session ran and whether it is the current SKILL.md (see
transcripts.py). `--versions-dir` saves every distinct body as `<skill>-<version>.md` and the
current ones as `<skill>-current.md`, so that `diff -u` of the two shows what changed in a skill
since a session ran it.

Run from the repository root:
  python .claude/skills/numerai-sleeping/scripts/find_sessions.py --since 2026-11-20 \
    --exclude "$CLAUDE_CODE_SESSION_ID" --versions-dir workspace/analysis/sleep-<date>/versions
"""

# Code structure, to keep when editing this file:
# - Write code as small functions whose names state exactly what each does
#   (e.g. `extract_zip_safely`, `report_unused_runtime_dependencies`).
# - Keep code and functions short, concise, understandable and readable to a single SWE
#   reviewing: roughly under 30 lines, one responsibility each. No long monolithic functions.
# - Why: the code is audited personally by its maintainer.

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from transcripts import (
    body_version,
    content_blocks,
    current_skill_bodies,
    loaded_skill,
    normalized_body,
    parse_record,
    skill_name,
)

TIMESTAMP = re.compile(r'"timestamp":"([^"]+)"')
SECONDS = '%Y-%m-%dT%H:%M:%S'
EDIT_TOOLS = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')
ARGS_CHARS = 300


@dataclass
class Scan:
    first: str = ''
    last: str = ''
    ai_title: str = ''
    custom_title: str = ''
    loads: list[dict] = field(default_factory=list)
    bodies: dict[tuple[str, str], str] = field(default_factory=dict)
    edits: set[str] = field(default_factory=set)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    projects = Path.home() / '.claude' / 'projects'
    parser.add_argument('--projects-dir', type=Path, default=projects)
    parser.add_argument('--skills-dir', type=Path, default='.claude/skills')
    parser.add_argument('--prefix', default='numerai-')
    parser.add_argument(
        '--since', default='', help='UTC ISO 8601, e.g. 2026-11-20T08:00:00Z'
    )
    parser.add_argument('--exclude', nargs='*', default=[], help='session ids')
    parser.add_argument('--versions-dir', type=Path)
    return parser.parse_args()


def canonical_since(since: str) -> str:
    if not since:
        return ''
    moment = datetime.fromisoformat(since)
    if moment.tzinfo:
        moment = moment.astimezone(UTC)
    return moment.strftime(SECONDS)


def modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).strftime(SECONDS)


def candidate_transcripts(
    projects_dir: Path, since: str, exclude: list[str]
) -> list[Path]:
    return [
        path
        for path in sorted(projects_dir.glob('*/*.jsonl'))
        if path.stem not in exclude and modified_at(path) >= since
    ]


def note_timestamp(scan: Scan, line: str) -> None:
    match = TIMESTAMP.search(line)
    if match:
        moment = match[1][:19]
        scan.first = min(scan.first or moment, moment)
        scan.last = max(scan.last, moment)


def note_title(scan: Scan, record: dict) -> None:
    match record.get('type'):
        case 'ai-title':
            scan.ai_title = record.get('aiTitle') or scan.ai_title
        case 'custom-title':
            scan.custom_title = record.get('customTitle') or scan.custom_title


def note_skill_load(scan: Scan, record: dict, prefix: str) -> None:
    load = loaded_skill(record)
    if not load or not skill_name(load).startswith(prefix):
        return
    version = body_version(load['body'])
    scan.bodies[(skill_name(load), version)] = normalized_body(load['body'])
    scan.loads.append(
        {
            'skill': skill_name(load),
            'timestamp': record.get('timestamp', ''),
            'uuid': record.get('uuid', ''),
            'version': version,
            'args': (load['args'] or '')[:ARGS_CHARS],
        }
    )


def note_skill_edits(scan: Scan, record: dict, prefix: str) -> None:
    if record.get('type') != 'assistant':
        return
    marker = f'/.claude/skills/{prefix}'
    for block in content_blocks(record):
        target = str((block.get('input') or {}).get('file_path', ''))
        if block.get('name') in EDIT_TOOLS and marker in target:
            scan.edits.add(target)


def scan_transcript(path: Path, prefix: str) -> Scan:
    scan = Scan()
    with path.open(errors='replace') as lines:
        for line in lines:
            note_timestamp(scan, line)
            if prefix in line or '-title"' in line:
                record = parse_record(line)
                note_title(scan, record)
                note_skill_load(scan, record, prefix)
                note_skill_edits(scan, record, prefix)
    return scan


def save_versions(versions_dir: Path, bodies: dict[str, str]) -> None:
    versions_dir.mkdir(parents=True, exist_ok=True)
    for name, body in bodies.items():
        (versions_dir / f'{name}.md').write_text(body)


def name_versions(scan: Scan) -> dict[str, str]:
    return {
        f'{skill}-{version}': body
        for (skill, version), body in scan.bodies.items()
    }


def name_current_bodies(current_bodies: dict[str, str]) -> dict[str, str]:
    return {f'{skill}-current': body for skill, body in current_bodies.items()}


def count_subagent_transcripts(path: Path) -> int:
    return len(list((path.parent / path.stem / 'subagents').glob('*.jsonl')))


def mark_current_loads(scan: Scan, current: dict[str, str]) -> list[dict]:
    return [
        load | {'current': current.get(load['skill']) == load['version']}
        for load in scan.loads
    ]


def describe_session(path: Path, scan: Scan, current: dict[str, str]) -> dict:
    return {
        'session': path.stem,
        'path': str(path),
        'title': scan.custom_title or scan.ai_title,
        'first': scan.first,
        'last': scan.last,
        'role': 'used' if scan.loads else 'authored',
        'loads': mark_current_loads(scan, current),
        'skill_edits': sorted(scan.edits),
        'subagent_transcripts': count_subagent_transcripts(path),
        'megabytes': round(path.stat().st_size / 1e6, 1),
    }


def find_sessions(
    args: argparse.Namespace, current: dict[str, str]
) -> list[dict]:
    since = canonical_since(args.since)
    sessions = []
    for path in candidate_transcripts(args.projects_dir, since, args.exclude):
        scan = scan_transcript(path, args.prefix)
        if (scan.loads or scan.edits) and scan.last >= since:
            sessions.append(describe_session(path, scan, current))
            if args.versions_dir:
                save_versions(args.versions_dir, name_versions(scan))
    return sorted(sessions, key=lambda session: session['first'])


def main() -> None:
    args = parse_args()
    bodies = current_skill_bodies(args.skills_dir, args.prefix)
    current = {skill: body_version(body) for skill, body in bodies.items()}
    sessions = find_sessions(args, current)
    if args.versions_dir:
        save_versions(args.versions_dir, name_current_bodies(bodies))
    print(json.dumps(sessions, indent=2))


if __name__ == '__main__':
    main()
