"""Report how each model script and artifact combines its learners.

Every name that identifies the model code (ensembler classes, fitted attributes, constants,
argument names, learner-name pattern) comes from a CONFIG file
(derived afresh for each run in the session scratchpad and never kept, format in SKILL.md),
so this script holds no model internals.

For every TIMESTAMP it reads SCRIPTS_DIR/<TIMESTAMP>.py and, if present, the artifact
MODELS_DIR/<TIMESTAMP>.pkl, and prints one JSON record per model:

  learners         learner names in the ensembler's learner list (script)
  ensembler        name of the ensembler class found in the script, role = select | stack
  mixing           mix function used by a select ensembler (script)
  metric           definition of the metric constant and whether uncommented code uses it (script)
  selection_metric the uncommented selection-metric argument of the ensembler (script)
  picked           learners a fitted select ensembler kept, weights normalized to sum 1 (artifact)
  stack            alpha, per-learner coefficients and passthrough sum |w| of a fitted stack (artifact)

Loading an artifact runs its pickled code: only use it on this repository's own models.

Usage: python inspect_models.py --scripts-dir DIR [--models-dir workspace/models] --config CONFIG TIMESTAMP ...
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np


def load_config(path: Path) -> dict[str, Any]:
    config: dict[str, Any] = json.loads(path.read_text())
    names = '|'.join(re.escape(str(name)) for name in config['ensemblers'])
    config['ensembler_pattern'] = re.compile(rf'({names})\(')
    config['learner_regex'] = re.compile(config['learner_name_pattern'])
    return config


def uncommented_lines(script):
    return [
        line
        for line in script.splitlines()
        if not line.lstrip().startswith('#')
    ]


def ensembler_start(lines, config):
    starts = [
        i
        for i, line in enumerate(lines)
        if config['ensembler_pattern'].search(line) and 'class ' not in line
    ]
    return starts[-1] if starts else None


def ensembler_name(lines, config):
    start = ensembler_start(lines, config)
    match = (
        config['ensembler_pattern'].search(lines[start])
        if start is not None
        else None
    )
    return match.group(1) if match else None


def configured_learners(lines, config):
    start = ensembler_start(lines, config)
    if start is None:
        return []
    begin = next(
        i
        for i in range(start, len(lines))
        if config['learner_list_argument'] in lines[i]
    )
    matches = [config['learner_regex'].search(line) for line in lines[begin:]]
    return list(
        dict.fromkeys(next(g for g in m.groups() if g) for m in matches if m)
    )


def mixing_function(lines, config):
    matches = [
        re.search(config['mix_function_pattern'], line) for line in lines
    ]
    return next((match.group(1) for match in matches if match), None)


def constant_definition(lines, name):
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(f'{name} = ')),
        None,
    )
    if start is None:
        return None
    for end in range(start, len(lines)):
        text = ' '.join(line.strip() for line in lines[start : end + 1])
        if text.count('(') == text.count(')'):
            return text.removeprefix(f'{name} = ')
    return None


def constant_is_used(lines, name, ignored_fragments):
    uses = [
        line
        for line in lines
        if re.search(rf'\b{name}\b', line)
        and not line.startswith(f'{name} = ')
    ]
    return any(
        not any(fragment in line for fragment in ignored_fragments)
        for line in uses
    )


def metric_is_used(lines, config):
    metric, scorer = config['metric_constant'], config['scorer_constant']
    return constant_is_used(
        lines, metric, [f'metric={metric})']
    ) or constant_is_used(lines, scorer, [])


def selection_metric(lines, config):
    matches = [
        re.search(rf'{config["selection_metric_argument"]}=([^,]+),', line)
        for line in lines
    ]
    return next((match.group(1) for match in matches if match), None)


def inspect_script(path, config):
    lines = uncommented_lines(path.read_text())
    name = ensembler_name(lines, config)
    role = config['ensemblers'].get(name)
    return {
        'learners': configured_learners(lines, config),
        'ensembler': {'name': name, 'role': role},
        'mixing': mixing_function(lines, config) if role == 'select' else None,
        'metric': {
            'definition': constant_definition(
                lines, config['metric_constant']
            ),
            'used': metric_is_used(lines, config),
        },
        'selection_metric': selection_metric(lines, config),
    }


def children_of(obj):
    if isinstance(obj, dict):
        return list(obj.values())
    if isinstance(obj, (list, tuple)):
        return list(obj)
    return list(vars(obj).values()) if hasattr(obj, '__dict__') else []


def find_by_class_name(obj, name, seen=None):
    seen = set() if seen is None else seen
    if id(obj) in seen or isinstance(obj, (str, bytes, np.ndarray)):
        return None
    seen.add(id(obj))
    if any(base.__name__ == name for base in type(obj).__mro__):
        return obj
    for child in children_of(obj):
        found = find_by_class_name(child, name, seen)
        if found is not None:
            return found
    return None


def picked_learners(ensembler, config):
    names = list(getattr(ensembler, config['selected_attribute']))
    weights = getattr(ensembler, config['weights_attribute'], None)
    raw = np.array(
        [weights[name] for name in names] if weights else [1.0] * len(names)
    )
    return {
        name: round(float(value), 3)
        for name, value in zip(names, raw / raw.sum())
    }


def unwrap_linear_model(estimator, config):
    while not hasattr(estimator, 'coef_'):
        estimator = (
            estimator[-1]
            if hasattr(estimator, 'steps')
            else getattr(estimator, config['wrapped_estimator_attribute'])
        )
    return estimator


def stack_weights(stacker, config):
    linear = unwrap_linear_model(
        getattr(stacker, config['stack_final_attribute']), config
    )
    names = [name for name, _ in stacker.estimators]
    coef = np.ravel(linear.coef_)
    return {
        'alpha': round(float(getattr(linear, 'alpha_', float('nan'))), 4),
        'learners': {
            name: round(float(value), 3) for name, value in zip(names, coef)
        },
        'passthrough_columns': int(coef.size - len(names)),
        'passthrough_sum_abs': round(
            float(np.abs(coef[len(names) :]).sum()), 3
        ),
    }


def inspect_artifact(path, config):
    from shrubbery.numerai.utilities import load_model

    model = load_model(path)
    for name, role in config['ensemblers'].items():
        found = find_by_class_name(model, name)
        if found is not None and role == 'stack':
            return {'stack': stack_weights(found, config)}
        if found is not None:
            return {'picked': picked_learners(found, config)}
    return {}


def inspect_model(timestamp, arguments, config):
    record = {
        'timestamp': timestamp,
        **inspect_script(arguments.scripts_dir / f'{timestamp}.py', config),
    }
    artifact = arguments.models_dir / f'{timestamp}.pkl'
    record['artifact'] = artifact.exists()
    if artifact.exists():
        record.update(inspect_artifact(artifact, config))
    return record


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--scripts-dir', type=Path, required=True)
    parser.add_argument(
        '--models-dir', type=Path, default=Path('workspace/models')
    )
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('timestamps', nargs='+')
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_arguments()
    config = load_config(arguments.config)
    for timestamp in arguments.timestamps:
        print(json.dumps(inspect_model(timestamp, arguments, config)))
