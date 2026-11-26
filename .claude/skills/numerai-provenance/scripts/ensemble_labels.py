"""Turn inspect_models.py records into the metric and ensemble labels of a provenance spec.

Display names (learner pools, metric and weight names, stack labels) come from the local
CONFIG file that is derived afresh for each run in the session scratchpad and never kept (format in SKILL.md).
Reads JSON lines from stdin, prints {timestamp: {"metric": ..., "ensemble": ...}}.
Stack coefficients below --min-weight in absolute value are summarized as "others".

Usage: python inspect_models.py ... | python ensemble_labels.py --config CONFIG [--min-weight 0.04]
"""

import argparse
import json
import sys
from pathlib import Path


def display_name(definition, names):
    matches = [key for key in names if key in (definition or '')]
    return names[max(matches, key=len)] if matches else definition


def chosen_metric(record, config):
    selected = record['selection_metric']
    return (
        record['metric']['definition']
        if selected == config['metric_constant']
        else selected
    )


def learner_pool(record, config):
    return config['learner_pools'].get(
        str(len(record['learners'])), ' '.join(record['learners'])
    )


def metric_label(record, config):
    if record['ensembler']['role'] == 'stack':
        return config['stack_metric']
    return display_name(chosen_metric(record, config), config['metric_names'])


def mixing_label(record, config):
    if record['mixing'] in config['equal_weight_mixes']:
        return 'equal-weight sum + rank'
    weights = display_name(
        chosen_metric(record, config), config['weight_names']
    )
    return f'weighted rank, weights = {weights}'


def stack_label(record, config, min_weight):
    stack = record['stack']
    large = sorted(
        ((k, v) for k, v in stack['learners'].items() if abs(v) >= min_weight),
        key=lambda kv: -abs(kv[1]),
    )
    weights = ', '.join(f'{name} {value:+.3f}' for name, value in large)
    return (
        f'{config["stack_label"]} over {learner_pool(record, config)}, alpha {stack["alpha"]:g}: {weights}; '
        f'others |w| < {min_weight}; {stack["passthrough_columns"]} passthrough columns sum |w| '
        f'{stack["passthrough_sum_abs"]}'
    )


def select_label(record, config):
    pool, mixing = learner_pool(record, config), mixing_label(record, config)
    if 'picked' not in record:
        return f'pick pending (no artifact) from {pool}; {mixing}'
    picks = ', '.join(
        f'{name} {weight:.3f}'
        for name, weight in sorted(
            record['picked'].items(), key=lambda kv: -kv[1]
        )
    )
    return f'{picks} (picked from {pool}; {mixing})'


def labels_for(record, config, min_weight):
    is_stack = record['ensembler']['role'] == 'stack'
    ensemble = (
        stack_label(record, config, min_weight)
        if is_stack and 'stack' in record
        else select_label(record, config)
    )
    return {'metric': metric_label(record, config), 'ensemble': ensemble}


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--min-weight', type=float, default=0.04)
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_arguments()
    config = json.loads(arguments.config.read_text())
    records = [json.loads(line) for line in sys.stdin if line.strip()]
    print(
        json.dumps(
            {
                r['timestamp']: labels_for(r, config, arguments.min_weight)
                for r in records
            },
            indent=2,
        )
    )
