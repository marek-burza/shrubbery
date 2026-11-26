"""Condense one Claude Code session transcript into a plain-text digest for review.

Keeps what shows how the session went and drops the bulk (tool outputs, skill bodies, compaction
summaries, thinking, subagent records). One line per event, in transcript order:

  <UTC date time> <first 8 characters of the record uuid> <KIND> <text>

KIND is USER (a prompt), QUEUED (a prompt typed while Claude worked), PEER (a message from
another session), COMMAND (a slash command), INTERRUPT, IDLE (more than --idle-minutes without
activity before a user message), SKILL (a skill load with its version, see transcripts.py),
SAY (Claude's text), TOOL (a tool call), ERROR (a failed tool call), REJECT (a tool call the
user declined), TASK (a background task's status), HOOK (a hook that blocked Claude from
stopping) or COMPACT (a compaction). Texts are cut at the given lengths; continuation lines are
indented. A header counts the events and lists the skill files the session read, edited or used
in a shell command. `--subagents` appends a section per subagent transcript of the session
(`<session>/subagents/agent-<id>.jsonl`, described by its `.meta.json`), digested alike.
`--redact-env-file` replaces the values of that file's variables with `<NAME>`.

Run from the repository root:
  python .claude/skills/numerai-sleeping/scripts/digest_session.py SESSION.jsonl \
    --redact-env-file .env > digest.txt
"""

# Code structure, to keep when editing this file:
# - Write code as small functions whose names state exactly what each does
#   (e.g. `extract_zip_safely`, `report_unused_runtime_dependencies`).
# - Keep code and functions short, concise, understandable and readable to a single SWE
#   reviewing: roughly under 30 lines, one responsibility each. No long monolithic functions.
# - Why: the code is audited personally by its maintainer.

import argparse
import html
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from transcripts import (
    body_version,
    content_blocks,
    loaded_skill,
    read_records,
    skill_name,
)

TASK_FIELD = re.compile(r'<(task-id|status|summary)>(.*?)</\1>', re.S)
COMMAND_NAME = re.compile(r'<command-name>(.*?)</command-name>', re.S)
COMMAND_ARGS = re.compile(r'<command-args>(.*?)</command-args>', re.S)
SKILL_PATH = re.compile(r'\.claude/skills/[\w.-]+(?:/[\w.-]+)*')
SKIPPED_TEXT = (
    '<local-command-caveat>',
    '<local-command-stdout>',
    '<local-command-stderr>',
    'This session is being continued',
)
REJECTED = "doesn't want to proceed"
USER_EVENTS = ('USER', 'COMMAND', 'INTERRUPT')
SUMMARY_KEYS = ('command', 'file_path', 'skill', 'query', 'url', 'pattern')
EDIT_TOOLS = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')
TOOL_CHARS = 200
ERROR_CHARS = 400
MIN_SECRET_CHARS = 8


@dataclass
class Limits:
    user: int
    say: int
    idle_minutes: int


@dataclass
class Digest:
    limits: Limits
    sidechain: bool = False
    ai_title: str = ''
    custom_title: str = ''
    events: list[str] = field(default_factory=list)
    kinds: Counter = field(default_factory=Counter)
    tools: Counter = field(default_factory=Counter)
    errors: Counter = field(default_factory=Counter)
    tasks: Counter = field(default_factory=Counter)
    skill_files: Counter = field(default_factory=Counter)
    tool_names: dict[str, str] = field(default_factory=dict)
    tasks_seen: set[tuple[str, str]] = field(default_factory=set)
    first: datetime | None = None
    last: datetime | None = None
    idle_seconds: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('transcript', type=Path)
    parser.add_argument('--redact-env-file', type=Path)
    parser.add_argument('--subagents', action='store_true')
    parser.add_argument('--user-chars', type=int, default=3000)
    parser.add_argument('--say-chars', type=int, default=600)
    parser.add_argument('--idle-minutes', type=int, default=30)
    return parser.parse_args()


def shorten(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return f'{text[:limit]} [... {len(text) - limit} more chars]'


def parse_moment(record: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(record.get('timestamp', ''))
    except ValueError:
        return None


def format_duration(seconds: float) -> str:
    hours, rest = divmod(int(seconds), 3600)
    return f'{hours}h{rest // 60:02d}m'


def note_idle_gap(digest: Digest, moment: datetime) -> None:
    gap = (moment - digest.last).total_seconds() if digest.last else 0.0
    if gap > digest.limits.idle_minutes * 60:
        digest.idle_seconds += gap
        digest.kinds['IDLE'] += 1
        digest.events.append(
            f'{moment:%Y-%m-%d %H:%M:%S} {"":8} IDLE '
            f'{format_duration(gap)} without activity'
        )


def add_event(digest: Digest, record: dict, kind: str, text: str) -> None:
    moment = parse_moment(record)
    if moment and kind in USER_EVENTS:
        note_idle_gap(digest, moment)
    if moment:
        digest.first = digest.first or moment
        digest.last = moment
    when = f'{moment:%Y-%m-%d %H:%M:%S}' if moment else ' ' * 19
    body = text.replace('\n', '\n    ')
    digest.kinds[kind] += 1
    digest.events.append(
        f'{when} {record.get("uuid", "")[:8]:8} {kind} {body}'
    )


def describe_skill_load(load: re.Match) -> str:
    text = f'{skill_name(load)} version {body_version(load["body"])}'
    return f'{text} args: {load["args"]}' if load['args'] else text


def describe_command(text: str) -> str:
    name = COMMAND_NAME.search(text)
    args = COMMAND_ARGS.search(text)
    return ' '.join(
        part.strip() for part in (name and name[1], args and args[1]) if part
    )


def add_task_event(digest: Digest, record: dict, text: str) -> None:
    fields = dict(TASK_FIELD.findall(text))
    status = fields.get('status', 'check-in')
    key = (fields.get('task-id', ''), status)
    if key in digest.tasks_seen:
        return
    digest.tasks_seen.add(key)
    digest.tasks[status] += 1
    summary = html.unescape(fields.get('summary', ''))
    add_event(digest, record, 'TASK', f'{status}: {shorten(summary, 300)}')


def digest_user_text(digest: Digest, record: dict, text: str) -> None:
    load = loaded_skill(record)
    if load:
        add_event(digest, record, 'SKILL', describe_skill_load(load))
    elif record.get('isMeta') or text.startswith(SKIPPED_TEXT):
        return
    elif text.startswith('<task-notification>'):
        add_task_event(digest, record, text)
    elif text.startswith('Stop hook feedback:'):
        add_event(digest, record, 'HOOK', shorten(text, digest.limits.say))
    elif text.startswith('[Request interrupted'):
        add_event(digest, record, 'INTERRUPT', text.strip())
    elif '<command-name>' in text:
        add_event(digest, record, 'COMMAND', describe_command(text))
    else:
        add_event(digest, record, 'USER', shorten(text, digest.limits.user))


def tool_result_text(block: dict) -> str:
    content = block.get('content')
    if isinstance(content, list):
        return ' '.join(
            part.get('text', '') for part in content if isinstance(part, dict)
        )
    return str(content or '')


def digest_tool_result(digest: Digest, record: dict, block: dict) -> None:
    text = tool_result_text(block)
    tool = digest.tool_names.get(block.get('tool_use_id', ''), '?')
    if REJECTED in text:
        add_event(digest, record, 'REJECT', f'{tool}: {shorten(text, 400)}')
    elif block.get('is_error'):
        digest.errors[tool] += 1
        add_event(digest, record, 'ERROR', f'{tool}: {shorten(text, 400)}')


def digest_user(digest: Digest, record: dict) -> None:
    if record.get('isCompactSummary'):
        return
    for block in content_blocks(record):
        match block.get('type'):
            case 'text':
                digest_user_text(digest, record, block.get('text', ''))
            case 'tool_result':
                digest_tool_result(digest, record, block)
            case 'image':
                add_event(digest, record, 'USER', '[image]')


def summarize_tool_input(tool_input: dict) -> str:
    for key in SUMMARY_KEYS:
        if tool_input.get(key):
            return str(tool_input[key])
    return json.dumps(tool_input, ensure_ascii=False)


def skill_file_action(tool: str) -> str:
    match tool:
        case 'Read':
            return 'read'
        case 'Bash':
            return 'shell'
        case _ if tool in EDIT_TOOLS:
            return 'edit'
        case _:
            return tool


def note_skill_files(digest: Digest, tool: str, tool_input: dict) -> None:
    text = json.dumps(tool_input, ensure_ascii=False)
    for path in set(SKILL_PATH.findall(text)):
        digest.skill_files[(skill_file_action(tool), path)] += 1


def digest_tool_use(digest: Digest, record: dict, block: dict) -> None:
    tool = block.get('name', '?')
    tool_input = block.get('input') or {}
    digest.tool_names[block.get('id', '')] = tool
    digest.tools[tool] += 1
    note_skill_files(digest, tool, tool_input)
    summary = shorten(summarize_tool_input(tool_input), TOOL_CHARS)
    add_event(digest, record, 'TOOL', f'{tool}: {summary}')


def digest_assistant(digest: Digest, record: dict) -> None:
    for block in content_blocks(record):
        match block.get('type'):
            case 'text':
                text = shorten(block.get('text', ''), digest.limits.say)
                add_event(digest, record, 'SAY', text)
            case 'tool_use':
                digest_tool_use(digest, record, block)


def digest_system(digest: Digest, record: dict) -> None:
    match record.get('subtype'):
        case 'compact_boundary':
            meta = record.get('compactMetadata') or {}
            text = f'{meta.get("trigger")}, {meta.get("preTokens")} tokens'
            add_event(digest, record, 'COMPACT', text)
        case _ if record.get('level') == 'error':
            text = shorten(str(record.get('content')), ERROR_CHARS)
            add_event(digest, record, 'ERROR', f'system: {text}')


def digest_queued_command(digest: Digest, record: dict, queued: dict) -> None:
    prompt = queued.get('prompt', '')
    moment = queued.get('timestamp') or record.get('timestamp', '')
    record = record | {'timestamp': moment}
    match (queued.get('origin') or {}).get('kind'):
        case 'human':
            text = shorten(prompt, digest.limits.user)
            add_event(digest, record, 'QUEUED', text)
        case 'peer':
            add_event(
                digest, record, 'PEER', shorten(prompt, digest.limits.say)
            )
        case _ if prompt.startswith('<task-notification>'):
            add_task_event(digest, record, prompt)


def digest_attachment(digest: Digest, record: dict) -> None:
    attachment = record.get('attachment') or {}
    if attachment.get('type') == 'queued_command':
        digest_queued_command(digest, record, attachment)


def digest_record(digest: Digest, record: dict) -> None:
    if record.get('isSidechain') and not digest.sidechain:
        return
    match record.get('type'):
        case 'user':
            digest_user(digest, record)
        case 'assistant':
            digest_assistant(digest, record)
        case 'system':
            digest_system(digest, record)
        case 'attachment':
            digest_attachment(digest, record)
        case 'ai-title':
            digest.ai_title = record.get('aiTitle') or digest.ai_title
        case 'custom-title':
            digest.custom_title = (
                record.get('customTitle') or digest.custom_title
            )


def format_counter(counter: Counter) -> str:
    return ', '.join(f'{key} {count}' for key, count in counter.most_common())


def format_tool_count(digest: Digest, tool: str, count: int) -> str:
    failed = digest.errors[tool]
    return f'{tool} {count} ({failed} failed)' if failed else f'{tool} {count}'


def format_tools(digest: Digest) -> str:
    return ', '.join(
        format_tool_count(digest, tool, count)
        for tool, count in digest.tools.most_common()
    )


def format_skill_files(digest: Digest) -> str:
    return '; '.join(
        f'{action} {path} x{count}'
        for (action, path), count in digest.skill_files.most_common()
    )


def format_span(digest: Digest) -> str:
    if not digest.first or not digest.last:
        return '?'
    span = format_duration((digest.last - digest.first).total_seconds())
    return f'{digest.first:%Y-%m-%d %H:%M} to {digest.last:%Y-%m-%d %H:%M} UTC ({span})'


def summary_lines(digest: Digest) -> list[str]:
    return [
        f'- span: {format_span(digest)}',
        f'- events: {format_counter(digest.kinds)}',
        f'- idle before user messages: {format_duration(digest.idle_seconds)}',
        f'- tools: {format_tools(digest) or "none"}',
        f'- background tasks: {format_counter(digest.tasks) or "none"}',
        f'- skill files: {format_skill_files(digest) or "none"}',
    ]


def header_lines(transcript: Path, digest: Digest) -> list[str]:
    title = digest.custom_title or digest.ai_title
    return [
        f'# Session {transcript.stem}: {title}',
        *summary_lines(digest),
        '',
    ]


def digest_transcript(transcript: Path, digest: Digest) -> Digest:
    for record in read_records(transcript):
        digest_record(digest, record)
    return digest


def subagent_transcripts(transcript: Path) -> list[Path]:
    subagents = transcript.parent / transcript.stem / 'subagents'
    return sorted(subagents.glob('agent-*.jsonl'))


def read_subagent_meta(subagent: Path) -> dict:
    try:
        return json.loads(subagent.with_suffix('.meta.json').read_text())
    except (OSError, ValueError):
        return {}


def subagent_lines(subagent: Path, limits: Limits) -> list[str]:
    digest = digest_transcript(subagent, Digest(limits, sidechain=True))
    meta = read_subagent_meta(subagent)
    name = subagent.stem.removeprefix('agent-')
    kind = meta.get('agentType', '?')
    title = f'## Subagent {name} ({kind}): {meta.get("description", "")}'
    return ['', title, *summary_lines(digest), '', *digest.events]


def read_env_values(env_file: Path) -> dict[str, str]:
    values = {}
    for line in env_file.read_text().splitlines():
        name, sign, value = line.removeprefix('export ').partition('=')
        value = value.strip().strip('\'"')
        if sign and len(value) >= MIN_SECRET_CHARS:
            values[name.strip()] = value
    return values


def redact(text: str, values: dict[str, str]) -> str:
    for name, value in values.items():
        text = text.replace(value, f'<{name}>')
    return text


def main() -> None:
    args = parse_args()
    limits = Limits(args.user_chars, args.say_chars, args.idle_minutes)
    digest = digest_transcript(args.transcript, Digest(limits))
    lines = header_lines(args.transcript, digest) + digest.events
    if args.subagents:
        for subagent in subagent_transcripts(args.transcript):
            lines += subagent_lines(subagent, limits)
    text = '\n'.join(lines)
    if args.redact_env_file:
        text = redact(text, read_env_values(args.redact_env_file))
    print(text)


if __name__ == '__main__':
    main()
