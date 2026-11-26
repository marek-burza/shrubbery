"""Trace the parent= chains of model notes back to their roots.

Reads the output of `notes list model` from stdin (pipe the whole listing, never a truncated one)
and, for every TIMESTAMP given, prints the chain from its root down to it, one note per line:
`timestamp status parent=<parent> | <summary>`. A TIMESTAMP without a note, or a parent
missing from the listing, is reported as `MISSING <timestamp>`.

Usage: notes list model | python lineage.py [--width 400] TIMESTAMP ...
"""

import argparse
import re
import sys


def parse_notes(lines):
    notes = {}
    for line in lines:
        fields = line.rstrip('\n').split(' ', 3)
        if (
            len(fields) == 4
            and fields[1] == 'model'
            and re.fullmatch(r'\d{14}', fields[0])
        ):
            parent = re.search(r'parent=(\S+)', fields[3])
            notes[fields[0]] = {
                'parent': parent.group(1) if parent else '-',
                'rest': f'{fields[2]} {fields[3]}',
            }
    return notes


def chain_to_root(timestamp, notes):
    chain, current = [], timestamp
    while current in notes and current not in chain:
        chain.append(current)
        current = notes[current]['parent']
    missing = current if current != '-' and current not in chain else None
    return list(reversed(chain)), missing


def print_chain(timestamp, notes, width):
    chain, missing = chain_to_root(timestamp, notes)
    print(f'== {timestamp}')
    if missing:
        print(f'MISSING {missing}')
    for member in chain:
        print(f'{member} {notes[member]["rest"][:width]}')


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--width', type=int, default=400)
    parser.add_argument('timestamps', nargs='+')
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_arguments()
    notes = parse_notes(sys.stdin)
    for timestamp in arguments.timestamps:
        print_chain(timestamp, notes, arguments.width)
