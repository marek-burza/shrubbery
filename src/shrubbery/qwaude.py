#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12", "huggingface_hub>=0.25"]
# ///
"""Local LLM toolkit for llama.cpp — sizes everything from the hardware it finds.

llm probe                  show detected GPU/VRAM/RAM/CPU and the derived settings
llm get flash              download the best quant of a model that fits this box
llm check flash            preflight: will it run without paging?
llm serve flash            OpenAI-compatible server on 127.0.0.1:8080
llm tune moe flash         llama bench sweep around an estimate from the model file
llm code flash             all of the above, then an agent (opencode or claude) on the server
"""

from __future__ import annotations

import functools
import json
import math
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


# =========================================================================== hardware probe


@dataclass(frozen=True)
class Gpu:
    name: str
    vram_total: int
    vram_used: int
    compute_cap: str  # e.g. "8.6"
    display_active: bool


@dataclass(frozen=True)
class Hardware:
    gpus: tuple[Gpu, ...]
    cpu_model: str
    physical_cores: int
    logical_cores: int
    ram_total: int
    ram_available: int
    swap_total: int
    memlock_unlimited: bool

    @property
    def vram_total(self) -> int:
        return sum(g.vram_total for g in self.gpus)

    @property
    def vram_free(self) -> int:
        return sum(g.vram_total - g.vram_used for g in self.gpus)


def _meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            k, v = line.split(':', 1)
            out[k] = int(v.split()[0]) * 1024
    except OSError:
        pass
    return out


def _gpus() -> tuple[Gpu, ...]:
    if not shutil.which('nvidia-smi'):
        return ()
    fields = 'name,memory.total,memory.used,compute_cap,display_active'
    try:
        out = subprocess.run(
            [
                'nvidia-smi',
                f'--query-gpu={fields}',
                '--format=csv,noheader,nounits',
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return ()
    gpus = []
    for row in out.strip().splitlines():
        name, total, used, cap, disp = (c.strip() for c in row.split(','))
        gpus.append(
            Gpu(
                name,
                int(total) * MiB,
                int(used) * MiB,
                cap,
                disp.lower() == 'enabled',
            )
        )
    return tuple(gpus)


def _cpu() -> tuple[str, int, int]:
    model = 'unknown'
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                model = line.split(':', 1)[1].strip()
                break
    except OSError:
        pass
    online = (
        os.sched_getaffinity(0)
        if hasattr(os, 'sched_getaffinity')
        else set(range(os.cpu_count() or 1))
    )
    cores: set[str] = set()
    for cpu in online:  # one entry per physical core: its SMT sibling list
        p = Path(
            f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list'
        )
        try:
            cores.add(p.read_text().strip())
        except OSError:
            pass
    logical = len(online)
    return model, len(cores) or max(1, logical // 2), logical


@functools.lru_cache(maxsize=1)
def probe_hw() -> Hardware:
    mem = _meminfo()
    model, phys, logical = _cpu()
    soft, _ = resource.getrlimit(resource.RLIMIT_MEMLOCK)
    return Hardware(
        gpus=_gpus(),
        cpu_model=model,
        physical_cores=phys,
        logical_cores=logical,
        ram_total=mem.get('MemTotal', 0),
        ram_available=mem.get('MemAvailable', 0),
        swap_total=mem.get('SwapTotal', 0),
        memlock_unlimited=soft == resource.RLIM_INFINITY,
    )


# =========================================================================== derived plan


@dataclass(frozen=True)
class Plan:
    """Every constant the old scripts hard-coded, derived from Hardware."""

    threads: int  # decode: memory-bound, physical cores win
    threads_batch: int  # prefill: compute-bound, use every logical core
    fit_target_mib: int  # VRAM --fit leaves free
    ram_reserve: int  # OS + desktop + page cache we refuse to touch
    kv_reserve: int  # KV cache + llama.cpp host buffers
    vram_reserve: int  # CUDA context + compute buffers + fit margin
    budget: int  # bytes of weights that can stay resident

    @property
    def vram_for_weights(self) -> int:
        return max(0, probe_hw().vram_free - self.vram_reserve)


@functools.lru_cache(maxsize=1)
def plan() -> Plan:
    hw = probe_hw()
    # A GPU that drives a display has VRAM use that fluctuates (browser, compositor).
    fit_target = 1536 if any(g.display_active for g in hw.gpus) else 1024
    ram_reserve = max(6 * GiB, int(0.08 * hw.ram_total))
    kv_reserve = 4 * GiB
    vram_reserve = (
        (fit_target * MiB + 2 * GiB) * max(1, len(hw.gpus)) if hw.gpus else 0
    )
    budget = (hw.ram_total - ram_reserve - kv_reserve) + max(
        0, hw.vram_free - vram_reserve
    )
    return Plan(
        threads=hw.physical_cores,
        threads_batch=hw.logical_cores,
        fit_target_mib=fit_target,
        ram_reserve=ram_reserve,
        kv_reserve=kv_reserve,
        vram_reserve=vram_reserve,
        budget=max(0, budget),
    )


# =========================================================================== model presets


@dataclass(frozen=True)
class Quant:
    name: str
    size_gb: float  # published size, decimal GB (actual file size wins once downloaded)
    note: str = ''


@dataclass(frozen=True)
class Preset:
    repo: str
    family: str  # "qwen" | "glm" — sampling defaults
    note: str
    quants: tuple[
        Quant, ...
    ]  # in order of preference: best quality-per-byte first
    ctx: int = 65536

    @property
    def dir_name(self) -> str:
        return self.repo.split('/')[-1]


PRESETS: dict[str, Preset] = {
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
        note='Qwen3.8-27B dense — fast, near-lossless coder',
        # BF16 ranks after Q8_0: no measurable quality gain for ~2x the bytes per token
        quants=(
            Quant('Q8_0', 29.0, 'near-lossless'),
            Quant('BF16', 54.7, 'unquantized'),
            Quant('Q4_K_M', 17.1, 'fits a 24 GB card alone'),
        ),
    ),
    'glm': Preset(
        repo='unsloth/GLM-5.3-Flash-GGUF',
        family='glm',
        note='GLM-5.3-Flash 320B-A18B — second opinion, heavy quant',
        quants=(
            Quant('UD-Q3_K_XL', 147.5, '86.3% top-1'),
            Quant('UD-IQ3_XXS', 120.4, '81.6% top-1'),
            Quant('UD-Q2_K_XL', 108.7, '78.3% top-1'),
            Quant('UD-IQ2_XXS', 101.8, '76.3% top-1'),
            Quant('UD-IQ1_M', 97.6, '73.1% top-1'),
        ),
    ),
}

QWEN_EFFORTS = {'low', 'medium', 'xhigh'}
GLM_EFFORTS = {'low', 'high', 'max'}


class Mode(str, Enum):
    thinking = 'thinking'
    instruct = 'instruct'


class Agent(str, Enum):
    opencode = 'opencode'
    claude = 'claude'


class Sweep(str, Enum):
    moe = 'moe'
    ngl = 'ngl'
    threads = 'threads'
    ubatch = 'ubatch'


# =========================================================================== paths & files


def root() -> Path:
    return Path(os.environ.get('LLM_ROOT', Path.home() / 'llm')).expanduser()


def preset_or_die(name: str) -> Preset:
    if name not in PRESETS:
        raise typer.BadParameter(
            f"unknown model '{name}', choose from: {', '.join(PRESETS)}"
        )
    return PRESETS[name]


def shards(p: Preset, quant: str) -> list[Path]:
    base = root() / 'models' / p.dir_name
    if not base.exists():
        return []
    # match the quant as a whole token so "Q4_K_XL" doesn't also match "UD-Q4_K_XL"
    rx = re.compile(rf'(^|[-_.]){re.escape(quant)}([-_.]|$)')
    return sorted(
        f
        for f in base.rglob('*.gguf')
        if rx.search(f.stem) and not f.name.startswith(('mmproj', 'mtp'))
    )


def quant_size(p: Preset, q: Quant) -> int:
    files = shards(p, q.name)
    return (
        sum(f.stat().st_size for f in files) if files else int(q.size_gb * GB)
    )


def is_downloaded(p: Preset, q: Quant) -> bool:
    return bool(shards(p, q.name))


def pick_quant(p: Preset, downloaded_only: bool) -> tuple[Quant, bool]:
    """Best-preference quant that stays resident; returns (quant, fits)."""
    budget = plan().budget
    pool = (
        [q for q in p.quants if is_downloaded(p, q)]
        if downloaded_only
        else list(p.quants)
    )
    if not pool:
        raise LookupError
    for q in pool:
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
            f'No {q.name} GGUF under {root() / "models" / p.dir_name} — run: '
            f'llm get <model> --quant {q.name}',
            fg='red',
            err=True,
        )
        raise typer.Exit(1)
    return files[0]


def need_llama(command: str, dry_run: bool = False) -> list[str]:
    b = shutil.which('llama')
    if b is None and not dry_run:
        typer.secho(
            'Missing llama on PATH: the Dockerfile installs it from llama.app',
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


@dataclass(frozen=True)
class ModelShape:
    arch: str
    layers: int
    experts: int  # 0 for dense
    size: int


def model_shape(p: Preset, q: Quant) -> ModelShape:
    gguf = first_shard(p, q)
    meta = gguf_meta(gguf)
    arch = str(meta.get('general.architecture', '?'))
    return ModelShape(
        arch=arch,
        layers=int(meta.get(f'{arch}.block_count', 0)),
        experts=int(meta.get(f'{arch}.expert_count', 0)),
        size=quant_size(p, q),
    )


# =========================================================================== commands


@app.command()
def probe() -> None:
    """Show detected hardware, the settings derived from it, and the quant each model would use."""
    hw, pl = probe_hw(), plan()
    typer.secho('hardware', bold=True)
    for i, g in enumerate(hw.gpus):
        typer.echo(
            f'  GPU{i}  {g.name}  {g.vram_total / GiB:.1f} GiB  (used {g.vram_used / GiB:.1f}), '
            f'sm_{g.compute_cap.replace(".", "")}{", drives display" if g.display_active else ""}'
        )
    if not hw.gpus:
        typer.secho(
            '  no NVIDIA GPU found (nvidia-smi missing) — CPU-only plan',
            fg='yellow',
        )
    typer.echo(
        f'  CPU   {hw.cpu_model}: {hw.physical_cores} cores / {hw.logical_cores} threads'
    )
    typer.echo(
        f'  RAM   {hw.ram_total / GiB:.1f} GiB (available {hw.ram_available / GiB:.1f}), '
        f'swap {hw.swap_total / GiB:.1f} GiB, memlock {"unlimited" if hw.memlock_unlimited else "LIMITED"}'
    )

    typer.secho('derived', bold=True)
    typer.echo(
        f'  threads    -t {pl.threads} (decode)  -tb {pl.threads_batch} (prefill)'
    )
    typer.echo(
        f'  VRAM       --fit-target {pl.fit_target_mib} MiB; {pl.vram_reserve / GiB:.1f} GiB '
        f'reserved → {pl.vram_for_weights / GiB:.1f} GiB for weights'
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
            fit = (
                typer.style('fits', fg='green')
                if size <= budget
                else typer.style('pages', fg='yellow')
            )
            have = 'downloaded' if is_downloaded(p, q) else ''
            typer.echo(
                f'   {q.name:12} {size / GiB:6.1f} GiB  {fit:>5}  {q.note:14} {have}'
            )


@app.command()
def get(
    model: Annotated[
        str, typer.Argument(help=f'one of: {", ".join(PRESETS)}')
    ],
    quant: Annotated[
        Optional[str],
        typer.Option(help='default: best quant that fits this machine'),
    ] = None,
) -> None:
    """Download a quant from Hugging Face (resumable)."""
    from huggingface_hub import snapshot_download

    p = preset_or_die(model)
    q = resolve_quant(p, quant, downloaded_only=False)
    dest = root() / 'models' / p.dir_name
    probe_dir = dest
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
    typer.echo(f'Downloading {p.repo} [{q.name}] -> {dest}')
    snapshot_download(
        repo_id=p.repo, local_dir=dest, allow_patterns=[f'*{q.name}*']
    )


@app.command()
def check(
    model: Annotated[str, typer.Argument()],
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
    ],
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
            help='reasoning effort — Qwen: low|medium|xhigh, GLM: low|high|max'
        ),
    ] = None,
    mode: Annotated[
        Mode, typer.Option(help='Qwen sampling preset')
    ] = Mode.thinking,
    ncmoe: Annotated[
        Optional[int],
        typer.Option(help='pin -ngl 99 --n-cpu-moe N instead of --fit'),
    ] = None,
    ngl: Annotated[
        Optional[int],
        typer.Option(help='pin GPU layers (dense models) instead of --fit'),
    ] = None,
    fit_target: Annotated[
        Optional[int],
        typer.Option(help='MiB of VRAM --fit leaves free [derived]'),
    ] = None,
    threads: Annotated[
        Optional[int], typer.Option(help='decode threads [physical cores]')
    ] = None,
    threads_batch: Annotated[
        Optional[int], typer.Option(help='prefill threads [logical cores]')
    ] = None,
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
        ncmoe,
        ngl,
        fit_target,
        threads,
        threads_batch,
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
    ncmoe: Optional[int] = None,
    ngl: Optional[int] = None,
    fit_target: Optional[int] = None,
    threads: Optional[int] = None,
    threads_batch: Optional[int] = None,
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
        '-t',
        str(threads or pl.threads),
        '-tb',
        str(threads_batch or pl.threads_batch),
        '-b',
        str(ubatch),
        '-ub',
        str(ubatch),
        '--host',
        host,
        '--port',
        str(port),
    ]
    if not hw.gpus:
        args += ['-ngl', '0']
    elif ncmoe is not None:
        args += ['-ngl', '99', '--n-cpu-moe', str(ncmoe)]
    elif ngl is not None:
        args += ['-ngl', str(ngl)]
    else:
        args += [
            '--fit',
            'on',
            '--fit-target',
            str(fit_target or pl.fit_target_mib),
        ]

    # Sampling: vendor-recommended defaults (Unsloth model docs)
    if p.family == 'qwen':
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
        allowed = QWEN_EFFORTS
    else:
        args += [
            '--temp',
            '1.0',
            '--top-p',
            '0.95',
            '--kv-unified',
        ]  # --kv-unified: GLM multi-seq
        template_kwargs = {'reasoning_effort': effort or 'max'}
        allowed = GLM_EFFORTS
    eff = template_kwargs.get('reasoning_effort')
    if eff is not None and eff not in allowed:
        raise typer.BadParameter(
            f'effort for {model} must be one of {sorted(allowed)}'
        )
    args += ['--chat-template-kwargs', json.dumps(template_kwargs)]

    if not paging:
        args += ['-lm', 'mlock']
        if not hw.memlock_unlimited:
            typer.secho(
                '!! memlock limited — --mlock will be partial; run `ulimit -l unlimited`',
                fg='yellow',
                err=True,
            )

    return args + list(extra)


def est_ncmoe(shape: ModelShape) -> int:
    """Nearly all bytes of a sparse MoE are experts: offload the share that won't fit in VRAM."""
    gpu_share = min(1.0, plan().vram_for_weights / max(1, shape.size))
    return min(shape.layers, math.ceil(shape.layers * (1 - gpu_share)))


def est_ngl(shape: ModelShape) -> int:
    gpu_share = min(1.0, plan().vram_for_weights / max(1, shape.size))
    return math.floor(shape.layers * gpu_share)


def sweep_values(sweep: Sweep, shape: ModelShape) -> tuple[str, list[int]]:
    hw, L = probe_hw(), max(1, shape.layers)
    clamp = lambda vals: sorted({min(L, max(0, v)) for v in vals})
    if sweep is Sweep.moe:
        e = est_ncmoe(shape)
        return 'n-cpu-moe', clamp([e - 2, e, e + 2, e + 4, e + 8])
    if sweep is Sweep.ngl:
        e = est_ngl(shape)
        return 'ngl', clamp([e - 6, e - 4, e - 2, e, e + 2])
    if sweep is Sweep.threads:
        p, n = hw.physical_cores, hw.logical_cores
        return 'threads', sorted({max(1, p // 2), max(1, 3 * p // 4), p, n})
    return 'ubatch', [512, 1024, 2048, 4096]


@app.command()
def tune(
    sweep: Annotated[Sweep, typer.Argument(help='what to sweep')],
    model: Annotated[str, typer.Argument()],
    values: Annotated[
        Optional[str],
        typer.Option(help='override the derived sweep, e.g. 8,16,24'),
    ] = None,
    ncmoe: Annotated[
        Optional[int],
        typer.Option(help='pinned n-cpu-moe for threads/ubatch sweeps'),
    ] = None,
    ngl: Annotated[
        Optional[int],
        typer.Option(help='pinned ngl for threads/ubatch sweeps (dense)'),
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
    """Sweep with llama bench around values estimated from the model file and VRAM.

    Each value runs separately, so an out-of-memory at one value doesn't stop the sweep.
    Then pin the winner: `llm serve flash --ncmoe N` or `llm serve 27b --ngl N`.
    """
    pl, p = plan(), preset_or_die(model)
    q = resolve_quant(p, quant, downloaded_only=True)
    shape = model_shape(p, q)
    moe = shape.experts > 0
    typer.secho(
        f'{shape.arch}: {shape.layers} layers, {shape.experts or "no"} experts, '
        f'{shape.size / GiB:.1f} GiB; {pl.vram_for_weights / GiB:.1f} GiB VRAM for weights',
        fg='cyan',
        err=True,
    )
    if sweep is Sweep.moe and not moe:
        raise typer.BadParameter(
            f'{model} is dense — use `llm tune ngl {model}`'
        )
    if sweep is Sweep.ngl and moe:
        typer.secho(
            '!! MoE model: `tune moe` usually beats splitting whole layers',
            fg='yellow',
            err=True,
        )

    label, vals = sweep_values(sweep, shape)
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

    def placement(v: Optional[int] = None) -> list[str]:
        if sweep is Sweep.moe:
            return ['-ngl', '99', '--n-cpu-moe', str(v)]
        if sweep is Sweep.ngl:
            return ['-ngl', str(v)]
        if moe:  # threads/ubatch sweeps hold placement fixed
            return [
                '-ngl',
                '99',
                '--n-cpu-moe',
                str(ncmoe if ncmoe is not None else est_ncmoe(shape) + 2),
            ]
        return ['-ngl', str(ngl if ngl is not None else est_ngl(shape) - 2)]

    rows: list[tuple[int, dict[str, float]]] = []
    for v in vals:
        extra = {
            Sweep.threads: [
                '-t',
                str(v),
                '-ub',
                str(UBATCH),
                '-b',
                str(UBATCH),
            ],
            Sweep.ubatch: ['-t', str(pl.threads), '-ub', str(v), '-b', '4096'],
        }
        cmd = (
            base
            + placement(v)
            + extra.get(
                sweep,
                ['-t', str(pl.threads), '-ub', str(UBATCH), '-b', str(UBATCH)],
            )
        )
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
    flag = {
        Sweep.moe: '--ncmoe',
        Sweep.ngl: '--ngl',
        Sweep.threads: '--threads',
        Sweep.ubatch: '--ubatch',
    }[sweep]
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
    ],
    agent: Annotated[
        Agent, typer.Option(help='coding agent to run against the server')
    ] = Agent.opencode,
    quant: Annotated[
        Optional[str],
        typer.Option(help='default: best quant that fits this machine'),
    ] = None,
    tune_placement: Annotated[
        bool,
        typer.Option(
            '--tune/--no-tune',
            help='llama bench the GPU placement before serving',
        ),
    ] = True,
) -> None:
    """Probe, get, check, tune and serve a model, then run an agent on it. Extra args go to the agent."""
    probe()
    q = resolve_quant(preset_or_die(model), quant, downloaded_only=False).name
    get(model, q)
    if not preflight(model, q):
        raise typer.Exit(1)
    ncmoe = ngl = None
    if tune_placement and probe_hw().gpus:
        moe = model_shape(preset_or_die(model), Quant(q, 0.0)).experts > 0
        best = tune(Sweep.moe if moe else Sweep.ngl, model, quant=q)
        ncmoe, ngl = (best, None) if moe else (None, best)

    base_url = f'http://{HOST}:{PORT}'
    log_path = root() / f'llama-server.{model}.log'
    template = mid_conversation_system_template(
        first_shard(preset_or_die(model), Quant(q, 0.0)),
        root() / f'{model}.jinja',
    )
    args = server_command(
        model, q, ncmoe=ncmoe, ngl=ngl, extra=tuple(template)
    )
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
