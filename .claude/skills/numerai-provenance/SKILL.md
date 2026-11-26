---
name: numerai-provenance
description: Draws the provenance of the user's Numerai models as a rendered tree diagram (PNG) - the root models, which model each one derives from, what changed along the way, the metric each model is actually selected or fitted on, and which learners its ensemble uses with their weights - covering the models registered on the account plus any being trained. Use when asked where a model comes from, how the models relate, what differs between them, or for a model family tree or lineage diagram.
---

You draw a faithful family tree of the user's Numerai models from primary sources: the `model` notes of the experiments log, the model scripts, the trained artifacts and the run logs. Every label must be traceable to one of them; say "inferred" where it is not.

## Privacy (read first)

The diagram reveals how the models are built, so nothing model-specific may enter a tracked file.

- This skill (`SKILL.md`, `scripts/`) stays generic. Never add class names, attribute names, learner codes, metric formulas, weighting schemes or any other model internals to it. They exist only in the config, which every run derives afresh from the model code (see Config), and in the outputs.
- Never keep the config. Write it to the session scratchpad, never to the repository, `data/`, `workspace/`, memory or notes. Delete it when the run ends.
- Outputs go to `model_provenance.json` (the spec) and `model_provenance.png` in the repository root, unless the user names another place. Before writing them, check that git ignores them (`git check-ignore model_provenance.png model_provenance.json`); if not, add them to `.git/info/exclude` (local, never committed). Never `git add` them or the extracted scripts, and never paste their content into tracked files, commit messages, PRs or external services.
- Extract model scripts only to the session scratchpad, never into the repository.

## Tooling

Run from the repository root with `.env` loaded into the environment only (`set -a; . ./.env; set +a`); never print its values, including `NUMERAI_MODEL_PREFIX`.

- `notes` is short for `/app/venv/bin/shrubbery-notes --store data/numerai.data`; `notes list model` lists the model notes (format in the `numerai-autoresearch` skill), `notes show TIMESTAMP` prints a model's script.
- Python: `/app/venv/bin/python` (it has `matplotlib`, `numpy` and `shrubbery`; `uv run` needs the network). Set `MPLCONFIGDIR` to a scratchpad folder.
- `scripts/` is short for `.claude/skills/numerai-provenance/scripts/`:
  - `lineage.py`: root-to-model `parent=` chains from `notes list model` on stdin.
  - `inspect_models.py --config CONFIG`: per model, the configured learners, ensembler kind, mix function, metric constant and whether it is used, selection metric (from the script), and the picked learners with normalized weights or the stacking coefficients (from the artifact). It loads pickles, so only run it on this repository's own artifacts.
  - `ensemble_labels.py --config CONFIG`: turns those records into the `metric` and `ensemble` labels of the spec.
  - `render_provenance.py SPEC OUT.png`: draws the spec.

## Procedure

1. **Collect the models.**
   - Registered: the account's model names (`NumerAPI(public_id, secret_key).get_models()`) that start with `NUMERAI_MODEL_PREFIX`; the rest of each name is the note timestamp. Cross-check with `workspace/models/*.pkl`.
   - In training: ask the user which ones, or take the `<timestamp>.py` scripts in the repository root without a pickle, and the `Model Name:` line of the current `run.log`.
2. **Trace the lineage.** Pipe the full listing, never a truncated one: `notes list model | python scripts/lineage.py TIMESTAMP ...`. Then:
   - A model with no note (`MISSING`), usually a script still in training: diff its script against the candidate parent notes (`notes show P > scratch/P.py; diff scratch/P.py <timestamp>.py`) and take the parent with the smallest diff. Label the parent as inferred.
   - Scripts on disk can differ from their notes. Diff them and report every difference.
   - Roots are notes with `parent=-`. Descriptions like "as X but ..." mark a variant relation that has no `parent=` link.
3. **Inspect each model.** Extract every script into the scratchpad (`notes show T > scratch/scripts/T.py`; for models in training, copy the script on disk). Derive the config into `scratch/provenance.json` (see Config). Then run `python scripts/inspect_models.py --config scratch/provenance.json --scripts-dir scratch/scripts T ... | python scripts/ensemble_labels.py --config scratch/provenance.json`.
   - Check that the picks of one registered model match the last `Ensemble:` line of its newest inference log in `workspace/logs/` (the cron run loads the same pickle).
   - Picks from training-time logs of downsampled runs are not the deployed ensemble. Use the artifact.
4. **Choose the nodes.**
   - One node per root, registered model and model in training.
   - Collapse every run of unregistered intermediate notes between them into one `path` node titled `first .. last  (path)`. Its body summarizes the changes that persisted, taken from the `keep` notes of that run; skip discarded experiments.
   - Body of a registered or training node: what changed relative to its parent, in one or two lines, from its note.
   - Add `borrow` edges where a note says a design or members were ported from another branch.
5. **Write the spec** (format below) to `model_provenance.json`. Fill `metric` and `ensemble` from step 3. Fill `legend.notes` from `legend_notes` in the config.
   - Show only what the model actually uses. A metric constant that the code defines but never uses is not the model's metric: the selection-metric argument or the meta model's own criterion is.
6. **Render and check.** `python scripts/render_provenance.py model_provenance.json model_provenance.png`, then open the image.
   - Text must stay inside its box, boxes must not overlap and arrows must not cross boxes needlessly. Adjust `x` and `y` and re-render.
   - Typical grid: columns 3.4 to 4 units apart, rows 2.4 to 2.7 apart. Leave more room for tall boxes.
7. **Callouts.** When the user asks about a difference between two models (e.g. whether two models share an implementation), diff the relevant code of their scripts. Answer in the chat, and on request add a callout to the node.
8. **Report and clean up.** Give the image path, the roots, the branches and every inferred parent or note-versus-disk difference. Delete `scratch/provenance.json` and the extracted scripts.

## Spec

```json
{
  "title": "...", "subtitle": "...",
  "nodes": {"<id>": {"x": 0.0, "y": 0.0, "kind": "root|deployed|training|path", "title": "<timestamp>  ROOT",
                     "body": "what changed", "metric": "...", "ensemble": "..."}},
  "edges": [["<from id>", "<to id>", "parent|variant|borrow"]],
  "callouts": [{"node": "<id>", "x": 0.0, "y": 0.0, "title": "...", "body": "..."}],
  "legend": {"x": 0.0, "y": 0.0, "notes": [["metric|ensemble", "text"]]}
}
```

Coordinates are in inches (1 unit = 1 inch at 110 dpi; y grows upward). Boxes are 3.6 wide, and their height follows the wrapped text. `metric` and `ensemble` are optional. Two nodes in the same row are joined top to top by an arc, nodes in different rows bottom to top.

## Config

The config is a JSON object holding every name that identifies the model code. Derive it afresh on every run, because the model code changes, and never keep it (see Privacy). Keys:

| Key | Meaning | How to derive it from a model script |
|---|---|---|
| `ensemblers` | ensembler class name -> `select` (keeps a subset of learners and mixes them) or `stack` (fits a meta model over learner predictions) | the classes that `ESTIMATOR` wraps the learner list in |
| `selected_attribute` | fitted attribute of a `select` ensembler holding the kept learner names | trailing-underscore attribute set in its `fit` and read in `predict` |
| `weights_attribute` | fitted attribute holding the per-learner mix weights (may be absent in older models) | the dict set in `fit` and passed to the mix function |
| `stack_final_attribute`, `wrapped_estimator_attribute` | fitted meta model of a `stack` ensembler, and the attribute through which wrappers expose their inner estimator | sklearn's stacking attribute; the wrapper class's constructor argument |
| `learner_list_argument`, `learner_name_pattern` | keyword introducing the learner list and a regex capturing each learner's name | the `(name, estimator)` tuples in that list |
| `metric_constant`, `scorer_constant` | module-level metric and scorer constants | upper-case assignments near `ESTIMATOR` |
| `selection_metric_argument` | keyword through which a `select` ensembler receives its selection metric | its constructor argument |
| `mix_function_pattern`, `equal_weight_mixes` | regex capturing the mix function a `select` ensembler calls, and those that weight learners equally | the `return <mix function>(` lines |
| `learner_pools`, `metric_names`, `weight_names`, `stack_metric`, `stack_label` | display names: learner-count -> pool description; substring of a metric definition -> label; substring -> description of the mix weights; label of the meta model's fitting criterion and of the meta model | from the script and the notes' descriptions |
| `legend_notes` | legend lines explaining the `metric` and `ensemble` labels | written to match the labels |

Derivation: read the scripts of the newest registered model, one root and one stacking model, if there is one. Fill every key; when older scripts use other names for the same role, add them too. Then run step 3 on a few models with known answers (the logged `Ensemble:` lines) before trusting the result.
