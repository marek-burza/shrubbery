#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12", "huggingface_hub>=0.25"]
# ///
"""Local LLM toolkit for llama.cpp — sizes everything from the hardware it finds.

llm probe                  show detected GPU/VRAM/RAM/CPU and the derived settings
llm get                    download the best quant of the default model (bonsai) that fits this box
llm check                  preflight: will it run without paging?
llm serve                  OpenAI-compatible server on 127.0.0.1:8080
llm tune threads           llama bench sweep of threads or micro-batch size (--fit places layers)
llm code                   probe, get, check and serve, then an agent (opencode or claude) on the server
"""

from __future__ import annotations

import functools
import json
import os
import re
import resource
import shutil
import struct
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)

GiB = 1024**3
MiB = 1024**2
GB = 1000**3  # Unsloth publishes sizes in decimal GB
HOST = '127.0.0.1'
PORT = 8080
UBATCH = 1024
PROMPT, GENERATE = 2048, 128
FIT_TARGET_MIB = 1536
VRAM_OVERHEAD = 2 * GiB


# =========================================================================== hardware probe


@dataclass(frozen=True)
class Gpu:
    name: str
    vram_total: int
    vram_free: int


@dataclass(frozen=True)
class Hardware:
    gpus: tuple[Gpu, ...]
    ram_total: int
    ram_available: int
    swap_total: int
    memlock_unlimited: bool

    @property
    def vram_free(self) -> int:
        return sum(g.vram_free for g in self.gpus)


def _meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            k, v = line.split(':', 1)
            out[k] = int(v.split()[0]) * 1024
    except OSError:
        pass
    return out


DEVICE_LINE = re.compile(r'^\s*\S+: (.+) \((\d+) MiB, (\d+) MiB free\)$')


def _gpus() -> tuple[Gpu, ...]:
    llama = shutil.which('llama')
    if llama is None:
        return ()
    try:
        out = subprocess.run(
            [llama, 'serve', '--list-devices'],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return ()
    matches = (DEVICE_LINE.match(line) for line in out.splitlines())
    return tuple(
        Gpu(m[1], int(m[2]) * MiB, int(m[3]) * MiB) for m in matches if m
    )


@functools.lru_cache(maxsize=1)
def probe_hw() -> Hardware:
    mem = _meminfo()
    soft, _ = resource.getrlimit(resource.RLIMIT_MEMLOCK)
    return Hardware(
        gpus=_gpus(),
        ram_total=mem.get('MemTotal', 0),
        ram_available=mem.get('MemAvailable', 0),
        swap_total=mem.get('SwapTotal', 0),
        memlock_unlimited=soft == resource.RLIM_INFINITY,
    )


# =========================================================================== derived plan


@dataclass(frozen=True)
class Plan:
    ram_reserve: int
    kv_reserve: int
    vram_reserve: int
    budget: int

    @property
    def vram_for_weights(self) -> int:
        return max(0, probe_hw().vram_free - self.vram_reserve)


@functools.lru_cache(maxsize=1)
def plan() -> Plan:
    hw = probe_hw()
    ram_reserve = max(6 * GiB, int(0.08 * hw.ram_total))
    kv_reserve = 4 * GiB
    vram_reserve = (FIT_TARGET_MIB * MiB + VRAM_OVERHEAD) * len(hw.gpus)
    budget = (hw.ram_total - ram_reserve - kv_reserve) + max(
        0, hw.vram_free - vram_reserve
    )
    return Plan(ram_reserve, kv_reserve, vram_reserve, max(0, budget))


# =========================================================================== model presets


@dataclass(frozen=True)
class Quant:
    name: str
    size_gb: float  # published size, decimal GB (actual file size wins once downloaded)
    note: str = ''


@dataclass(frozen=True)
class Draft:
    path: str
    size_gb: float


@dataclass(frozen=True)
class Preset:
    repo: str
    family: str  # "qwen" | "bonsai" | "mimo": sampling defaults
    note: str
    quants: tuple[
        Quant, ...
    ]  # in order of preference: best quality-per-byte first
    ctx: int = 65536
    spec: tuple[str, ...] = ()
    draft: Optional[Draft] = None
    dense: bool = False
    kv_per_token: int = 0
    kv_cache: str = 'f16'

    @property
    def dir_name(self) -> str:
        return self.repo.split('/')[-1]


def mtp(n_max: int) -> tuple[str, ...]:
    return (
        '--spec-type',
        'draft-mtp',
        '--spec-draft-n-min',
        '0',
        '--spec-draft-n-max',
        str(n_max),
        '--spec-draft-p-min',
        '0',
    )


QWEN35_KV_PER_TOKEN = 64 * 1024
KV_CACHE_SCALE = {'f16': 1.0, 'q8_0': 34 / 64}

DEFAULT_MODEL = 'bonsai'

PRESETS: dict[str, Preset] = {
    'bonsai': Preset(
        repo='prism-ml/Ternary-Bonsai-2.5-27B-GGUF',
        family='bonsai',
        note='Ternary Bonsai 2.5 27B (Qwen3.8-27B at 1.76 bpw) + MTP draft head: agentic default',
        quants=(Quant('PTQ1_0-mtp', 6.23, 'ternary, PrismML fork'),),
        ctx=131072,
        spec=mtp(3),
        dense=True,
        kv_per_token=QWEN35_KV_PER_TOKEN,
    ),
    'flash': Preset(
        repo='unsloth/Qwen3.8-Flash-Next-GGUF',
        family='qwen',
        note='Qwen3.8-Flash-Next 125B-A6B + 51B n-gram table — the one-model pick',
        quants=(
            Quant('UD-Q5_K_XL', 158.3, '93.7% top-1'),
            Quant('UD-Q4_K_XL', 111.3, '92.3% top-1'),
            Quant('UD-IQ4_XS', 93.7, '89.6% top-1'),
            Quant('UD-Q3_K_XL', 90.0, '88.3% top-1'),
            Quant('UD-IQ3_XXS', 82.0, '85.4% top-1'),
            Quant('UD-Q2_K_XL', 78.9, '82.7% top-1'),
        ),
    ),
    '27b': Preset(
        repo='unsloth/Qwen3.8-27B-GGUF',
        family='qwen',
        note='Qwen3.8-27B dense + MTP draft: fast coder, sized to fit VRAM',
        quants=(
            Quant('Q8_0', 29.0, 'near-lossless'),
            Quant('UD-Q6_K_XL', 25.3, '6-bit'),
            Quant('UD-Q5_K_XL', 21.0, '5-bit'),
            Quant('UD-Q4_K_XL', 17.7, '4-bit'),
            Quant('UD-IQ4_XS', 14.4, '4-bit, smaller'),
            Quant('UD-Q3_K_XL', 13.1, '3-bit'),
        ),
        spec=mtp(2),
        draft=Draft('MTP/mtp-Qwen3.8-27B-Q4_0.gguf', 1.37),
        dense=True,
        kv_per_token=QWEN35_KV_PER_TOKEN,
        kv_cache='q8_0',
    ),
    'mimo': Preset(
        repo='TrevorJS/MiMo-V2.6-Flash-RL-GGUF',
        family='mimo',
        note='MiMo-V2.6-Flash 309B-A15B: strongest coding agent that fits, 2.55 bpw',
        quants=(Quant('IQ2_XS_M-v2.1', 98.7, 'GSM8K 95.6 vs 96.4 FP8'),),
    ),
}

EFFORTS = {
    'qwen': {'low', 'medium', 'xhigh'},
    'bonsai': {'medium', 'xhigh'},
    'mimo': set(),
}


class Mode(str, Enum):
    thinking = 'thinking'
    instruct = 'instruct'


class Agent(str, Enum):
    opencode = 'opencode'
    claude = 'claude'


class Sweep(str, Enum):
    threads = 'threads'
    ubatch = 'ubatch'


# =========================================================================== paths & files


def root() -> Path:
    path = Path(os.environ.get('LLM_ROOT', Path.home() / 'llm')).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def preset_or_die(name: str) -> Preset:
    if name not in PRESETS:
        raise typer.BadParameter(
            f"unknown model '{name}', choose from: {', '.join(PRESETS)}"
        )
    return PRESETS[name]


def snapshot_dir(p: Preset) -> Optional[Path]:
    from huggingface_hub.constants import HF_HUB_CACHE

    repo = Path(HF_HUB_CACHE) / f'models--{p.repo.replace("/", "--")}'
    ref = repo / 'refs' / 'main'
    if not ref.is_file():
        return None
    snapshot = repo / 'snapshots' / ref.read_text().strip()
    return snapshot if snapshot.is_dir() else None


def shards(p: Preset, quant: str) -> list[Path]:
    base = snapshot_dir(p)
    if base is None:
        return []
    # match the quant as a whole token so "Q4_K_XL" doesn't also match "UD-Q4_K_XL"
    rx = re.compile(rf'(^|[-_.]){re.escape(quant)}([-_.]|$)')
    return sorted(
        f
        for f in base.rglob('*.gguf')
        if rx.search(f.stem) and not f.name.startswith(('mmproj', 'mtp'))
    )


def quant_size(p: Preset, q: Quant) -> int:
    if not is_downloaded(p, q):
        return int(q.size_gb * GB)
    return sum(f.stat().st_size for f in shards(p, q.name))


SHARD_OF = re.compile(r'-\d{5}-of-(\d{5})$')


def is_downloaded(p: Preset, q: Quant) -> bool:
    files = shards(p, q.name)
    split = SHARD_OF.search(files[0].stem) if files else None
    return bool(files) and (split is None or len(files) == int(split[1]))


def draft_bytes(p: Preset) -> int:
    return int(p.draft.size_gb * GB) if p.draft else 0


def vram_budget(p: Preset) -> int:
    kv = int(p.ctx * p.kv_per_token * KV_CACHE_SCALE[p.kv_cache])
    return plan().vram_for_weights - kv - draft_bytes(p)


def candidates(p: Preset, pool: list[Quant]) -> list[tuple[int, list[Quant]]]:
    resident = (plan().budget, pool)
    if not (p.dense and probe_hw().gpus):
        return [resident]
    least_spill = sorted(pool, key=lambda q: quant_size(p, q))
    return [(vram_budget(p), pool), (plan().budget, least_spill)]


def fit_label(p: Preset, size: int) -> str:
    if p.dense and probe_hw().gpus and size <= vram_budget(p):
        return 'vram'
    return 'fits' if size <= plan().budget else 'pages'


def pick_quant(p: Preset, downloaded_only: bool) -> tuple[Quant, bool]:
    """Best quant that fits VRAM (dense) or stays resident (MoE); a dense model that fits nowhere spills least."""
    pool = (
        [q for q in p.quants if is_downloaded(p, q)]
        if downloaded_only
        else list(p.quants)
    )
    if not pool:
        raise LookupError
    for budget, quants in candidates(p, pool):
        for q in quants:
            if quant_size(p, q) <= budget:
                return q, True
    return min(pool, key=lambda q: quant_size(p, q)), False


def resolve_quant(
    p: Preset, name: Optional[str], downloaded_only: bool
) -> Quant:
    if name:
        return next(
            (q for q in p.quants if q.name == name), Quant(name, 0.0, 'custom')
        )
    try:
        q, fits = pick_quant(p, downloaded_only)
    except LookupError:
        typer.secho(
            f'No quant of {p.dir_name} downloaded — run: llm get <model>',
            fg='red',
            err=True,
        )
        raise typer.Exit(1)
    if not fits:
        typer.secho(
            f'!! no {"downloaded " if downloaded_only else ""}quant fits the '
            f'{plan().budget / GiB:.0f} GiB resident budget; using the smallest ({q.name})',
            fg='yellow',
            err=True,
        )
    typer.secho(
        f'quant: {q.name} ({quant_size(p, q) / GiB:.1f} GiB, {q.note}) — auto-selected',
        fg='cyan',
        err=True,
    )
    return q


def first_shard(p: Preset, q: Quant) -> Path:
    files = shards(p, q.name)
    if not files:
        typer.secho(
            f'No {q.name} GGUF of {p.repo} in the Hugging Face cache, run: '
            f'llm get <model> --quant {q.name}',
            fg='red',
            err=True,
        )
        raise typer.Exit(1)
    return files[0]


def draft_args(p: Preset) -> list[str]:
    if p.draft is None:
        return list(p.spec)
    base = snapshot_dir(p)
    path = base / p.draft.path if base else Path(p.draft.path)
    return ['-md', str(path), *p.spec]


def need_llama(command: str, dry_run: bool = False) -> list[str]:
    b = shutil.which('llama')
    if b is None and not dry_run:
        typer.secho(
            'Missing llama on PATH: the Dockerfile installs the PrismML llama.cpp fork',
            fg='red',
            err=True,
        )
        raise typer.Exit(1)
    return [b or 'llama', command]


# =========================================================================== GGUF metadata


_GGUF_SCALAR = {
    0: '<B',
    1: '<b',
    2: '<H',
    3: '<h',
    4: '<I',
    5: '<i',
    6: '<f',
    7: '<?',
    10: '<Q',
    11: '<q',
    12: '<d',
}


def gguf_meta(path: Path) -> dict[str, str | int | float | bool]:
    """Read scalar/string KV metadata from a GGUF header (arrays are skipped)."""
    out: dict[str, str | int | float | bool] = {}
    with path.open('rb') as f:

        def read(fmt: str):
            return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]

        def read_str() -> str:
            return f.read(read('<Q')).decode('utf-8', 'replace')

        if f.read(4) != b'GGUF':
            raise ValueError(f'{path} is not a GGUF file')
        if read('<I') < 2:
            raise ValueError('GGUF v1 not supported')
        read('<Q')  # tensor count
        for _ in range(read('<Q')):
            key, typ = read_str(), read('<I')
            if typ == 8:
                out[key] = read_str()
            elif typ == 9:
                atyp, n = read('<I'), read('<Q')
                if atyp == 8:
                    for _ in range(n):
                        f.seek(read('<Q'), 1)
                else:
                    f.seek(n * struct.calcsize(_GGUF_SCALAR[atyp]), 1)
            else:
                out[key] = read(_GGUF_SCALAR[typ])
    return out


# =========================================================================== commands


@app.command()
def probe() -> None:
    """Show detected hardware, the settings derived from it, and the quant each model would use."""
    hw, pl = probe_hw(), plan()
    typer.secho('hardware', bold=True)
    for i, g in enumerate(hw.gpus):
        typer.echo(
            f'  GPU{i}  {g.name}  {g.vram_total / GiB:.1f} GiB  ({g.vram_free / GiB:.1f} free)'
        )
    if not hw.gpus:
        typer.secho(
            '  no GPU listed by `llama serve --list-devices`: CPU-only plan',
            fg='yellow',
        )
    typer.echo(
        f'  RAM   {hw.ram_total / GiB:.1f} GiB (available {hw.ram_available / GiB:.1f}), '
        f'swap {hw.swap_total / GiB:.1f} GiB, memlock {"unlimited" if hw.memlock_unlimited else "LIMITED"}'
    )

    typer.secho('derived', bold=True)
    typer.echo(
        f'  VRAM       --fit-target {FIT_TARGET_MIB} MiB; {pl.vram_reserve / GiB:.1f} GiB '
        f'reserved → {pl.vram_for_weights / GiB:.1f} GiB for weights, KV and draft'
    )
    typer.echo(
        f'  RAM        {pl.ram_reserve / GiB:.1f} GiB OS reserve + {pl.kv_reserve / GiB:.0f} GiB '
        f'KV/buffers → {(hw.ram_total - pl.ram_reserve - pl.kv_reserve) / GiB:.1f} GiB for weights'
    )
    typer.secho(
        f'  budget     {pl.budget / GiB:.1f} GiB of weights can stay resident (no paging)',
        bold=True,
    )

    typer.secho('models', bold=True)
    for name, p in PRESETS.items():
        q, fits = pick_quant(p, downloaded_only=False)
        mark = (
            typer.style('✓', fg='green')
            if fits
            else typer.style('✗ none fits', fg='red')
        )
        typer.echo(
            f'  {name:6} {mark} {q.name:11} {quant_size(p, q) / GiB:6.1f} GiB  {q.note}'
        )


@app.command('list')
def list_models() -> None:
    """Show presets, known quants, what is downloaded, and what fits."""
    budget = plan().budget
    typer.echo(f'resident budget on this machine: {budget / GiB:.1f} GiB\n')
    for name, p in PRESETS.items():
        typer.secho(f'{name:6} {p.note}', bold=True)
        for q in p.quants:
            size = quant_size(p, q)
            label = fit_label(p, size)
            fit = typer.style(
                label, fg='yellow' if label == 'pages' else 'green'
            )
            have = 'downloaded' if is_downloaded(p, q) else ''
            typer.echo(
                f'   {q.name:12} {size / GiB:6.1f} GiB  {fit:>5}  {q.note:14} {have}'
            )


@app.command()
def get(
    model: Annotated[
        str, typer.Argument(help=f'one of: {", ".join(PRESETS)}')
    ] = DEFAULT_MODEL,
    quant: Annotated[
        Optional[str],
        typer.Option(help='default: best quant that fits this machine'),
    ] = None,
) -> None:
    """Download a quant (and its draft model) into the Hugging Face cache (resumable)."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.constants import HF_HUB_CACHE

    p = preset_or_die(model)
    q = resolve_quant(p, quant, downloaded_only=False)
    probe_dir = Path(HF_HUB_CACHE)
    while not probe_dir.exists():
        probe_dir = probe_dir.parent
    free = shutil.disk_usage(probe_dir).free
    need = 0 if is_downloaded(p, q) else int(q.size_gb * GB)
    if need > free:
        typer.secho(
            f'!! needs ~{need / GiB:.0f} GiB, only {free / GiB:.0f} GiB free on disk',
            fg='red',
        )
        raise typer.Exit(1)
    typer.echo(f'Downloading {p.repo} [{q.name}] -> {HF_HUB_CACHE}')
    snapshot_download(
        repo_id=p.repo,
        allow_patterns=[f'*[-_./]{q.name}[-_.]*']
        + ([p.draft.path] if p.draft else []),
    )


@app.command()
def check(
    model: Annotated[str, typer.Argument()] = DEFAULT_MODEL,
    quant: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Preflight for no-paging runs: size vs derived budget, memlock limit, swap."""
    raise typer.Exit(0 if preflight(model, quant) else 1)


def preflight(model: str, quant: Optional[str]) -> bool:
    hw, pl, p = probe_hw(), plan(), preset_or_die(model)
    q = resolve_quant(p, quant, downloaded_only=quant is None)
    size, ok = quant_size(p, q), True
    typer.echo(f'model   {model} [{q.name}]: {size / GiB:.1f} GiB')
    typer.echo(
        f'budget  {pl.budget / GiB:.1f} GiB  (run `llm probe` for the breakdown)'
    )
    if size > pl.budget:
        typer.secho(
            '  ✗ too big to stay resident: smaller quant or `serve --paging`',
            fg='red',
        )
        ok = False
    else:
        typer.secho(
            f'  ✓ fits with {(pl.budget - size) / GiB:.1f} GiB to spare',
            fg='green',
        )
    if hw.memlock_unlimited:
        typer.secho('  ✓ memlock unlimited', fg='green')
    elif not hw.swap_total:
        typer.secho(
            '  ! memlock limited, harmless without swap: unmapped weights cannot be paged out',
            fg='yellow',
        )
    else:
        typer.secho(
            '  ✗ memlock limited: `ulimit -l unlimited` (or memlock in '
            '/etc/security/limits.conf)',
            fg='red',
        )
        ok = False
    if hw.swap_total:
        typer.secho(
            f'  ! swap active ({hw.swap_total / GiB:.1f} GiB): `sudo swapoff -a` or '
            '`sudo sysctl vm.swappiness=1`',
            fg='yellow',
        )
    else:
        typer.secho('  ✓ no swap', fg='green')
    typer.echo('verify while generating: `vmstat 1` → si/so/bi should stay ~0')
    return ok


@app.command(
    context_settings={'allow_extra_args': True, 'ignore_unknown_options': True}
)
def serve(
    ctx: typer.Context,
    model: Annotated[
        str, typer.Argument(help=f'one of: {", ".join(PRESETS)}')
    ] = DEFAULT_MODEL,
    quant: Annotated[
        Optional[str],
        typer.Option(help='default: best downloaded quant that fits'),
    ] = None,
    ctx_size: Annotated[
        Optional[int], typer.Option('--ctx', help='context length')
    ] = None,
    effort: Annotated[
        Optional[str],
        typer.Option(
            help='reasoning effort, Qwen: low|medium|xhigh, Bonsai: medium|xhigh, MiMo: none'
        ),
    ] = None,
    mode: Annotated[
        Mode, typer.Option(help='sampling preset; instruct turns thinking off')
    ] = Mode.thinking,
    fit_target: Annotated[
        int, typer.Option(help='MiB of VRAM --fit leaves free')
    ] = FIT_TARGET_MIB,
    ubatch: Annotated[
        int, typer.Option(help='batch / micro-batch size')
    ] = UBATCH,
    host: str = HOST,
    port: int = PORT,
    paging: Annotated[
        bool,
        typer.Option(
            '--paging/--no-paging',
            help='--no-paging (default): -lm mlock, refuse models over budget',
        ),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option(help="print the command, don't run it")
    ] = False,
) -> None:
    """Launch llama-server sized for this machine. Extra args after `--` go to llama serve."""
    args = server_command(
        model,
        quant,
        ctx_size,
        effort,
        mode,
        fit_target,
        ubatch,
        host,
        port,
        paging,
        dry_run,
        tuple(ctx.args),
    )
    typer.secho('+ ' + ' '.join(args), fg='cyan', err=True)
    if not dry_run:
        os.execv(args[0], args)


def server_command(
    model: str,
    quant: Optional[str] = None,
    ctx_size: Optional[int] = None,
    effort: Optional[str] = None,
    mode: Mode = Mode.thinking,
    fit_target: int = FIT_TARGET_MIB,
    ubatch: int = UBATCH,
    host: str = HOST,
    port: int = PORT,
    paging: bool = False,
    dry_run: bool = False,
    extra: tuple[str, ...] = (),
) -> list[str]:
    hw, pl, p = probe_hw(), plan(), preset_or_die(model)
    q = resolve_quant(p, quant, downloaded_only=True)
    gguf = first_shard(p, q)
    server = need_llama('serve', dry_run)

    if not paging and quant_size(p, q) > pl.budget:
        typer.secho(
            f'✗ {q.name} ({quant_size(p, q) / GiB:.1f} GiB) exceeds the resident budget '
            f'({pl.budget / GiB:.1f} GiB). Use a smaller quant or --paging.',
            fg='red',
            err=True,
        )
        raise typer.Exit(1)

    args: list[str] = [
        *server,
        '-m',
        str(gguf),
        '--alias',
        model,
        '--jinja',
        '-c',
        str(ctx_size or p.ctx),
        '-fa',
        'on',
        '-b',
        str(ubatch),
        '-ub',
        str(ubatch),
        '--host',
        host,
        '--port',
        str(port),
        '--fit',
        'on',
        '--fit-target',
        str(fit_target),
        '-ctk',
        p.kv_cache,
        '-ctv',
        p.kv_cache,
    ]

    # Sampling: vendor-recommended defaults (Unsloth model docs)
    if p.family in ('qwen', 'bonsai'):
        if mode is Mode.instruct:
            args += [
                '--temp',
                '0.7',
                '--top-p',
                '0.8',
                '--top-k',
                '20',
                '--min-p',
                '0',
                '--presence-penalty',
                '1.5',
            ]
            template_kwargs = {'enable_thinking': False}
        else:
            args += [
                '--temp',
                '1.0',
                '--top-p',
                '0.95',
                '--top-k',
                '20',
                '--min-p',
                '0',
            ]
            template_kwargs = {'reasoning_effort': effort or 'xhigh'}
    else:
        args += [
            '--temp',
            '1.0',
            '--top-p',
            '0.95',
            '--top-k',
            '0',
            '--min-p',
            '0',
        ]
        template_kwargs = {'enable_thinking': mode is Mode.thinking}
    if effort is not None and effort not in EFFORTS[p.family]:
        raise typer.BadParameter(
            f'effort for {model} must be one of {sorted(EFFORTS[p.family]) or "none"}'
        )
    args += ['--chat-template-kwargs', json.dumps(template_kwargs)]
    args += draft_args(p)

    if not paging:
        args += ['-lm', 'mlock']
        if not hw.memlock_unlimited:
            typer.secho(
                '!! memlock limited — --mlock will be partial; run `ulimit -l unlimited`',
                fg='yellow',
                err=True,
            )

    return args + list(extra)


def sweep_values(sweep: Sweep) -> tuple[str, list[int]]:
    if sweep is Sweep.threads:
        n = os.cpu_count() or 1
        return 'threads', sorted({max(1, n * k // 4) for k in (1, 2, 3, 4)})
    return 'ubatch', [512, 1024, 2048, 4096]


def sweep_args(sweep: Sweep, value: int) -> list[str]:
    if sweep is Sweep.threads:
        return ['-t', str(value), '-ub', str(UBATCH), '-b', str(UBATCH)]
    return ['-ub', str(value), '-b', '4096']


@app.command()
def tune(
    sweep: Annotated[Sweep, typer.Argument(help='what to sweep')],
    model: Annotated[str, typer.Argument()] = DEFAULT_MODEL,
    values: Annotated[
        Optional[str],
        typer.Option(help='override the derived sweep, e.g. 8,16,24'),
    ] = None,
    quant: Annotated[Optional[str], typer.Option()] = None,
    depth: Annotated[
        Optional[str],
        typer.Option(
            help='context depths to test at [0 and the serving context]'
        ),
    ] = None,
    dry_run: bool = False,
) -> Optional[int]:
    """Sweep threads or micro-batch size with llama bench; --fit places the layers.

    Each value runs separately, so an out-of-memory at one value doesn't stop the sweep.
    """
    p = preset_or_die(model)
    q = resolve_quant(p, quant, downloaded_only=True)
    label, vals = sweep_values(sweep)
    if values:
        vals = [int(v) for v in values.split(',')]
    bench = need_llama('bench', dry_run)
    base = [
        *bench,
        '-m',
        str(first_shard(p, q)),
        '-fa',
        'on',
        '-lm',
        'none',
        '-fitt',
        str(FIT_TARGET_MIB),
        '-p',
        str(PROMPT),
        '-n',
        str(GENERATE),
        '-d',
        depth or f'0,{p.ctx - PROMPT - GENERATE}',
        '-r',
        '2',
        '-o',
        'json',
    ]

    rows: list[tuple[int, dict[str, float]]] = []
    for v in vals:
        cmd = base + sweep_args(sweep, v)
        if dry_run:
            typer.echo(' '.join(cmd))
            continue
        typer.secho(f'{label}={v} …', fg='cyan', err=True)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            typer.secho(
                f'  {label}={v}: failed ({(res.stderr.strip().splitlines() or ["no output"])[-1]}), skipping',
                fg='yellow',
                err=True,
            )
            continue
        cells: dict[str, float] = {}
        for r in json.loads(res.stdout):
            kind = 'pp' if r.get('n_prompt', 0) else 'tg'
            cells[f'{kind}@{r.get("n_depth", 0)}'] = float(r.get('avg_ts', 0))
        rows.append((v, cells))

    if dry_run or not rows:
        if not dry_run:
            typer.secho('no successful runs', fg='red')
        return None
    cols = sorted(
        {c for _, cells in rows for c in cells},
        key=lambda c: (int(c.split('@')[1]), c),
    )
    typer.echo(f'\n{label:>10} | ' + ' | '.join(f'{c:>10}' for c in cols))
    for v, cells in rows:
        typer.echo(
            f'{v:>10} | '
            + ' | '.join(f'{cells.get(c, 0):10.1f}' for c in cols)
        )
    tg_cols = [c for c in cols if c.startswith('tg')]
    key = (
        tg_cols[-1] if tg_cols else cols[0]
    )  # generation speed at the deepest context
    best = max(rows, key=lambda r: r[1].get(key, 0))[0]
    flag = {Sweep.threads: '-- -t', Sweep.ubatch: '--ubatch'}[sweep]
    typer.secho(
        f'\nbest {key}: {label}={best} → llm serve {model} {flag} {best}',
        bold=True,
    )
    return best


def ensure_opencode_config(model: str, base_url: str) -> None:
    config_path = Path('~/.config/opencode/opencode.json').expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    models = {
        name: {
            'name': name,
            'tool_call': True,
            'attachment': True,
            'reasoning': True,
        }
        for name in PRESETS
    }
    config = {
        '$schema': 'https://opencode.ai/config.json',
        'provider': {
            'llama.cpp': {
                'npm': '@ai-sdk/openai-compatible',
                'name': 'llama.cpp',
                'options': {'baseURL': f'{base_url}/v1'},
                'models': models,
            },
        },
        'model': f'llama.cpp/{model}',
    }
    config_path.write_text(json.dumps(config, indent=2) + '\n')


def ensure_attribution_header_disabled() -> None:
    settings_path = Path('~/.claude/settings.json').expanduser()
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    settings.setdefault('env', {}).update(
        {'CLAUDE_CODE_ATTRIBUTION_HEADER': '0'}
    )
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + '\n')


SYSTEM_MESSAGE_RAISE = (
    "{{- raise_exception('System message must be at the beginning.') }}"
)
SYSTEM_MESSAGE_TURN = (
    "{{- '<|im_start|>system\\n' + content + '<|im_end|>\\n' }}"
)


def mid_conversation_system_template(
    gguf: Path, destination: Path
) -> list[str]:
    template = str(gguf_meta(gguf).get('tokenizer.chat_template', ''))
    if SYSTEM_MESSAGE_RAISE not in template:
        return []
    destination.write_text(
        template.replace(SYSTEM_MESSAGE_RAISE, SYSTEM_MESSAGE_TURN)
    )
    return ['--chat-template-file', str(destination)]


def wait_until_healthy(
    process: subprocess.Popen, base_url: str, log_path: Path
) -> None:
    while process.poll() is None:
        try:
            with urllib.request.urlopen(
                f'{base_url}/health', timeout=5
            ) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    typer.secho(
        f'llama-server exited with {process.returncode}, see {log_path}',
        fg='red',
        err=True,
    )
    raise typer.Exit(1)


def agent_command(
    agent: Agent, model: str, base_url: str, extra: list[str]
) -> list[str]:
    match agent:
        case Agent.opencode:
            ensure_opencode_config(model, base_url)
            return ['opencode', *extra]
        case Agent.claude:
            ensure_attribution_header_disabled()
            os.environ['ANTHROPIC_AUTH_TOKEN'] = 'llama.cpp'
            os.environ['ANTHROPIC_BASE_URL'] = base_url
            return ['claude', '--model', model, *extra]


@app.command(
    context_settings={'allow_extra_args': True, 'ignore_unknown_options': True}
)
def code(
    ctx: typer.Context,
    model: Annotated[
        str, typer.Argument(help=f'one of: {", ".join(PRESETS)}')
    ] = DEFAULT_MODEL,
    agent: Annotated[
        Agent, typer.Option(help='coding agent to run against the server')
    ] = Agent.opencode,
    quant: Annotated[
        Optional[str],
        typer.Option(help='default: best quant that fits this machine'),
    ] = None,
) -> None:
    """Probe, get, check and serve a model, then run an agent on it. Extra args go to the agent."""
    probe()
    q = resolve_quant(preset_or_die(model), quant, downloaded_only=False).name
    get(model, q)
    if not preflight(model, q):
        raise typer.Exit(1)

    base_url = f'http://{HOST}:{PORT}'
    log_path = root() / f'llama-server.{model}.log'
    template = mid_conversation_system_template(
        first_shard(preset_or_die(model), Quant(q, 0.0)),
        root() / f'{model}.jinja',
    )
    args = server_command(model, q, extra=tuple(template))
    typer.secho('+ ' + ' '.join(args) + f' > {log_path}', fg='cyan', err=True)
    with (
        log_path.open('w') as log,
        subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT) as server,
    ):
        try:
            wait_until_healthy(server, base_url, log_path)
            subprocess.run(
                agent_command(agent, model, base_url, ctx.args), check=False
            )
        finally:
            server.terminate()
            server.wait()


if __name__ == '__main__':
    app()
