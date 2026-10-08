#!/usr/bin/env python3

import argparse
import os
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--model',
        type=str,
    )
    parser.add_argument('command', nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    run_docker(arguments)


def run_docker(arguments: argparse.Namespace) -> None:
    base = Path(__file__).parent
    extra_arguments = [
        argument for argument in arguments.command if argument != '--'
    ]
    command = [
        'podman',
        'run',
        '--rm',
        '-it',
        '--device',
        'nvidia.com/gpu=all',
        f'--shm-size={os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")}',
        '--userns=keep-id',
        '-v',
        f'{os.getcwd()}:/w',
        '-w',
        '/w',
        '--env-file',
        f'{base / ".env"}',
        '-e',
        f'NUMERAI_MODEL={arguments.model}',
        '--pull=always',
        'ghcr.io/marek-burza/shrubbery:latest',
        '-c',
        f'"numerai-run --model {arguments.model} {" ".join(extra_arguments)}"',
    ]
    command = ' '.join(command)
    Path('workspace/logs').mkdir(parents=True, exist_ok=True)
    command += ' 2>&1 > workspace/logs/$(date +%Y%m%d%H%M%S).log'
    print(command)
    subprocess.run(command, shell=True, check=True)


if __name__ == '__main__':
    main()
