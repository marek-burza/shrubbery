"""Collect recent Numerai tournament/data and numerapi changes, plus model training dates.

Prints a markdown digest of machine-readable sources:
  1. Payout & main-target history of the Classic tournament (numerapi `list_rounds`,
     `roundScoreConfigs` with `isPayout`): change points and the current configuration
  2. Dataset versions (`list_datasets`) and the benchmark models of the latest version
  3. Forum announcements (https://forum.numer.ai/c/announcements/8) since --since
  4. Blog posts incl. "Numerai Monthly" (https://blog.numer.ai/rss/) since --since
  5. numerapi: version locked in --lock-file vs PyPI releases, CHANGELOG entries newer than it
  6. Model artifacts `<timestamp>.pkl` in --models-dir with their modification (= training) times

Run from the repository root:
  python .claude/skills/numerai-update/scripts/check_numerai.py [--since 2026-06-01]
"""

# Code structure, to keep when editing this file:
# - Write code as small functions whose names state exactly what each does
#   (e.g. `extract_zip_safely`, `report_unused_runtime_dependencies`).
# - Keep code and functions short, concise, understandable and readable to a single SWE
#   reviewing: roughly under 30 lines, one responsibility each. No long monolithic functions.
# - Why: the code is audited personally by its maintainer.

import argparse
import html
import io
import json
import re
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq
from numerapi import NumerAPI

FORUM = 'https://forum.numer.ai'
BLOG_RSS = 'https://blog.numer.ai/rss/'
PYPI = 'https://pypi.org/pypi/numerapi/json'
CHANGELOG = (
    'https://raw.githubusercontent.com/numerai/numerapi/master/CHANGELOG.md'
)
TIMESTAMP = '%Y-%m-%dT%H:%M:%SZ'
BENCHMARK_NON_MODEL_COLUMNS = (
    'id',
    'era',
    'data_type',
    'numerai_ticker',
    'date',
)
DEFAULT_LOOKBACK_DAYS = 180
BULK_REWRITE_SECONDS = 600
BULK_REWRITE_WARNING = (
    '\n**Warning:** artifacts marked "yes" were written within 10 minutes of '
    'another one, likely a bulk re-serialization/copy, not training. Do not '
    'use their times as training dates.'
)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={'User-Agent': 'numerai-update-skill'}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def html_to_plain_excerpt(fragment: str, limit: int = 400) -> str:
    plain = re.sub(
        r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(fragment))
    ).strip()
    return plain[:limit] + ('…' if len(plain) > limit else '')


def payout_scores(round_: dict) -> list[str]:
    return sorted(
        f'{c["displayName"]}×{c["defaultMultiplier"]:g} ({c["totalScoreDays"]}d)'
        for c in round_['roundScoreConfigs']
        if c.get('isPayout')
    )


def payout_change_rows(rounds: list[dict]) -> list[str]:
    rows, previous = [], None
    for round_ in rounds:
        payout = payout_scores(round_)
        signature = (round_['target'], tuple(payout))
        if signature != previous:
            rows.append(
                f'| {round_["number"]} | {round_["openTime"]:%Y-%m-%d} | {round_["target"]} | '
                f'{", ".join(payout) or "-"} |'
            )
            previous = signature
    return rows


def payout_history(napi: NumerAPI) -> list[str]:
    rounds = sorted(napi.list_rounds(), key=lambda r: r['number'])
    current = rounds[-1]
    header = [
        (
            f'Current round {current["number"]} (open {current["openTime"]:{TIMESTAMP}}): '
            f'target `{current["target"]}`.\n'
        ),
        '| from round | open date | main target | payout scores × multiplier |',
        '|---|---|---|---|',
    ]
    return header + payout_change_rows(rounds)


def version_sort_key(version: str) -> list[int]:
    return [int(x) for x in re.findall(r'\d+', version)]


def dataset_versions(napi: NumerAPI) -> list[str]:
    return sorted(
        {f.split('/')[0] for f in napi.list_datasets() if '/' in f},
        key=version_sort_key,
    )


def benchmark_model_names(napi: NumerAPI, version: str) -> list[str]:
    query = 'query($f:String!){dataset(filename:$f)}'
    url = napi.raw_query(
        query, {'f': f'{version}/live_benchmark_models.parquet'}
    )['data']['dataset']
    schema = pq.read_schema(io.BytesIO(fetch(url)))
    return [c for c in schema.names if c not in BENCHMARK_NON_MODEL_COLUMNS]


def datasets(napi: NumerAPI) -> list[str]:
    versions = dataset_versions(napi)
    latest = versions[-1]
    return [
        f'Versions: {", ".join(versions)}; latest **{latest}**.',
        f'Benchmark models in {latest}: {", ".join(benchmark_model_names(napi, latest))}',
    ]


def forum_announcement_topics() -> list[dict]:
    return json.loads(fetch(f'{FORUM}/c/announcements/8.json'))['topic_list'][
        'topics'
    ]


def parse_forum_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def forum_topic_line(topic: dict, created: datetime) -> str:
    first = json.loads(fetch(f'{FORUM}/t/{topic["id"]}.json'))['post_stream'][
        'posts'
    ][0]
    return (
        f'- {created:%Y-%m-%d} [{topic["title"]}]({FORUM}/t/{topic["id"]}) '
        f'(replies {topic["posts_count"] - 1}, last {topic["last_posted_at"][:10]}): '
        f'{html_to_plain_excerpt(first["cooked"])}'
    )


def forum(since: datetime) -> list[str]:
    lines = []
    for topic in sorted(
        forum_announcement_topics(),
        key=lambda t: t['created_at'],
        reverse=True,
    ):
        created = parse_forum_time(topic['created_at'])
        if created >= since:
            lines.append(forum_topic_line(topic, created))
    return lines or ['- none']


def rss_field(item: str, tag: str) -> str:
    pattern = rf'<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>'
    match = re.search(pattern, item, re.DOTALL)
    if match is None:
        raise ValueError(f'RSS item without <{tag}>')
    return match.group(1)


def parse_rss_item(item: str) -> tuple[str, str, datetime]:
    title = rss_field(item, 'title')
    link = rss_field(item, 'link')
    pub_date = rss_field(item, 'pubDate')
    published = datetime.strptime(
        pub_date, '%a, %d %b %Y %H:%M:%S %Z'
    ).replace(tzinfo=UTC)
    return title, link, published


def blog(since: datetime) -> list[str]:
    feed = fetch(BLOG_RSS).decode()
    lines = []
    for item in re.findall(r'<item>(.*?)</item>', feed, re.DOTALL):
        title, link, published = parse_rss_item(item)
        if published >= since:
            lines.append(
                f'- {published:%Y-%m-%d} [{html.unescape(title)}]({link})'
            )
    return lines or ['- none']


def locked_numerapi_version(lock_file: Path) -> str:
    lock = lock_file.read_text() if lock_file.exists() else ''
    match = re.search(r'name = "numerapi"\nversion = "([^"]+)"', lock)
    return match.group(1) if match else 'unknown'


def pypi_releases_by_date() -> list[tuple[str, str]]:
    releases = json.loads(fetch(PYPI))['releases']
    return sorted(
        (files[0]['upload_time'][:10], version)
        for version, files in releases.items()
        if files
    )


def changelog_sections_newer_than(locked: str) -> list[str]:
    sections = []
    for section in re.split(r'\n(?=## \[)', fetch(CHANGELOG).decode()):
        version = re.match(r'## \[([^\]]+)\]', section)
        if not version:
            continue
        if version.group(1) == locked:
            break
        sections.append(section.strip())
    return sections


def numerapi_status(lock_file: Path) -> list[str]:
    locked = locked_numerapi_version(lock_file)
    dated = pypi_releases_by_date()
    newer = changelog_sections_newer_than(locked)
    return [
        f'Locked in {lock_file}: **{locked}**; latest on PyPI: **{dated[-1][1]}** ({dated[-1][0]}).',
        'Recent releases: ' + ', '.join(f'{v} ({d})' for d, v in dated[-6:]),
        '',
        'CHANGELOG entries newer than the locked version:',
        *(newer or ['- none']),
    ]


def model_files_in(models_dir: Path) -> list[Path]:
    return (
        [f for f in sorted(models_dir.glob('*.pkl')) if f.is_file()]
        if models_dir.exists()
        else []
    )


def written_in_bulk(file: Path, files: list[Path]) -> bool:
    mtime = file.stat().st_mtime
    return any(
        abs(other.stat().st_mtime - mtime) < BULK_REWRITE_SECONDS
        for other in files
        if other != file
    )


def model_file_row(file: Path, bulk: bool) -> str:
    written = datetime.fromtimestamp(file.stat().st_mtime, UTC)
    size = file.stat().st_size / 1e9
    return (
        f'| {file.name} | {written:{TIMESTAMP}} | {size:.2f} GB '
        f'| {"yes" if bulk else "no"} |'
    )


def model_files(models_dir: Path) -> list[str]:
    files = model_files_in(models_dir)
    if not files:
        return [f'No model artifacts (*.pkl) in {models_dir}']
    bulk = [written_in_bulk(file, files) for file in files]
    lines = [
        '| file | last written (mtime, UTC) | size | bulk write |',
        '|---|---|---|---|',
        *map(model_file_row, files, bulk),
    ]
    return lines + [BULK_REWRITE_WARNING] if any(bulk) else lines


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--since', help='Earliest announcement date (default: 180 days ago)'
    )
    parser.add_argument('--lock-file', type=Path, default=Path('uv.lock'))
    parser.add_argument(
        '--models-dir', type=Path, default=Path('workspace/models')
    )
    return parser.parse_args()


def since_date(since: str | None) -> datetime:
    if since:
        return datetime.fromisoformat(since).replace(tzinfo=UTC)
    return datetime.now(UTC) - timedelta(days=DEFAULT_LOOKBACK_DAYS)


def digest_sections(
    args: argparse.Namespace, since: datetime
) -> list[tuple[str, Callable[[], list[str]]]]:
    napi = NumerAPI()
    return [
        ('Payout and main-target history (API)', lambda: payout_history(napi)),
        ('Datasets (API)', lambda: datasets(napi)),
        (f'Forum announcements since {since:%Y-%m-%d}', lambda: forum(since)),
        (f'Blog posts since {since:%Y-%m-%d}', lambda: blog(since)),
        ('numerapi', lambda: numerapi_status(args.lock_file)),
        ('Model artifacts', lambda: model_files(args.models_dir)),
    ]


def render_section_or_its_failure(
    title: str, build: Callable[[], list[str]]
) -> list[str]:
    try:
        body = build()
    except Exception as error:
        body = [f'**Failed:** {error!r}; check this source manually.']
    return ['', f'## {title}', '', *body]


def main() -> None:
    args = parse_arguments()
    since = since_date(args.since)
    output = [f'# Numerai update digest ({datetime.now(UTC):{TIMESTAMP}})']
    for title, build in digest_sections(args, since):
        output += render_section_or_its_failure(title, build)
    print('\n'.join(output))


if __name__ == '__main__':
    main()
