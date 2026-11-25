"""Stop hook of the numerai-autoresearch skill: sends a stalled experiment loop back to work.

On long tasks Claude Opus 5.5 reports progress as it works, and some of those reports end the
turn with text and no tool call. In an unattended loop the work stops there until the user
returns. This hook sends such a turn back, as recommended in
https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5#unattended-agentic-runs

It lets the turn end when:
- the loop is not running in this session: `workspace/autoresearch.session` is missing or names
  another session (before setup is done, after wrap-up, in any other session);
- background work is in flight or a wake-up is scheduled, since its completion wakes the session;
- the last message states a blocker on a line starting with `BLOCKED:`;
- it has already sent the loop back MAX_NUDGES times in a row without a new `run.log`, so that a
  loop that is genuinely stuck ends and can be reviewed.

Hook input (JSON on stdin) and output (JSON on stdout) are those of Claude Code's Stop event.
"""

# Code structure, to keep when editing this file:
# - Write code as small functions whose names state exactly what each does
#   (e.g. `extract_zip_safely`, `report_unused_runtime_dependencies`).
# - Keep code and functions short, concise, understandable and readable to a single SWE
#   reviewing: roughly under 30 lines, one responsibility each. No long monolithic functions.
# - Why: the code is audited personally by its maintainer.

import json
import os
import sys
from pathlib import Path

MAX_NUDGES = 3

REASON = (
    'The experiment loop is still running and nothing is in flight. If an experiment has finished, '
    'add its model note and clean up, then start the next experiment. If something outside the '
    "experiment's script blocks you, say what it is on a line starting with BLOCKED:. If the user "
    'asked you to stop, run Wrap-up.'
)


def project_dir(event: dict) -> Path:
    return Path(
        os.environ.get('CLAUDE_PROJECT_DIR') or event.get('cwd') or '.'
    )


def loop_runs_in_session(project: Path, session: str) -> bool:
    marker = project / 'workspace' / 'autoresearch.session'
    try:
        return bool(session) and marker.read_text().strip() == session
    except OSError:
        return False


def work_is_in_flight(event: dict) -> bool:
    return bool(event.get('background_tasks') or event.get('session_crons'))


def message_states_blocker(message: str) -> bool:
    return any(
        line.lstrip().startswith('BLOCKED:') for line in message.splitlines()
    )


def turn_may_end(event: dict, project: Path, session: str) -> bool:
    return (
        not loop_runs_in_session(project, session)
        or work_is_in_flight(event)
        or message_states_blocker(event.get('last_assistant_message') or '')
    )


def run_log_mtime(project: Path) -> int:
    try:
        return (project / 'run.log').stat().st_mtime_ns
    except OSError:
        return 0


def read_nudge_state(nudges: Path) -> dict:
    try:
        return json.loads(nudges.read_text())
    except (OSError, ValueError):
        return {}


def consecutive_nudges(state: dict, session: str, progress: int) -> int:
    same = (
        state.get('session') == session and state.get('progress') == progress
    )
    return state.get('count', 0) if same else 0


def report_stalled_loop(count: int) -> None:
    message = f'numerai-autoresearch: stalled {count} times in a row without a new run.log, left stopped for review'
    print(json.dumps({'systemMessage': message}))


def send_loop_back(
    nudges: Path, session: str, progress: int, count: int
) -> None:
    nudges.write_text(
        json.dumps(
            {'session': session, 'progress': progress, 'count': count + 1}
        )
    )
    print(json.dumps({'decision': 'block', 'reason': REASON}))


def send_loop_back_unless_stalled(project: Path, session: str) -> None:
    nudges = project / 'workspace' / 'autoresearch.nudges'
    progress = run_log_mtime(project)
    count = consecutive_nudges(read_nudge_state(nudges), session, progress)
    if count >= MAX_NUDGES:
        report_stalled_loop(count)
    else:
        send_loop_back(nudges, session, progress, count)


def main() -> None:
    event = json.load(sys.stdin)
    session = event.get('session_id') or ''
    project = project_dir(event)
    if not turn_may_end(event, project, session):
        send_loop_back_unless_stalled(project, session)


if __name__ == '__main__':
    main()
