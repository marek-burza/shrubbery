---
name: numerai-update
description: Checks Numerai's recent tournament, data and scoring announcements and numerapi package releases, compares them with the shrubbery code, the scripts of the deployed models (their `model` notes), the skills in this repo and their references (e.g. references/channels.md), checks when the models were last trained, and recommends changes to bring code, skills and models in line. Use periodically, after Numerai news, before a retrain, or when asked whether anything changed at Numerai, whether the code is up to date, or whether a new data version, target or payout is in effect.
---

You keep the Numerai pipeline in line with what Numerai currently runs. Missed changes have cost performance before: training on v5.2 two months after v5.3 was released, not noticing the switch of the paid correlation to `v2_corr20`, of the main target (Cyrus, then Ender-20, Ender-60 and Jupiter-60), and of the payout from 20-day to 60-day scores. Your output is a dated list of what changed at Numerai, where the code, skills and trained models diverge from it, and the recommended changes.

Read `references/channels.md` first: where each kind of change gets announced, and which channels carried which past changes. Changes are not always in the forum Announcements category: the Ender-60 payout switch was only in the blog's Numerai Monthly and in the docs.

## Ground rules

- **Read-only.** Do not edit code, configs, notes, skills or references. Write only the report to `workspace/analysis/update-<YYYYmmdd>/report.md` (git-ignored). Offer to apply the changes after.
- **Never print secrets.** Load the repository's `.env` into the environment only (`set -a; . ./.env; set +a`); it provides `SHRUBBERY_KEY` for reading the model notes. The checks of step 1 work without credentials.
- Prefer machine-readable ground truth (API) over prose; use prose to learn the why, the timing of future changes and deprecation schedules.

## Tooling

Run everything from the repository root. Run Python with `/app/venv/bin/python` in the container, else `uv run python`. `notes` below is short for `/app/venv/bin/shrubbery-notes --store data/numerai.data` (outside the container `uv run shrubbery-notes --store data/numerai.data`).

Each model is identified by a timestamp `YYYYmmddHHMMSS`: its script is the text of the `model` note of that timestamp in `data/numerai.data` (`notes show <timestamp>`), its trained artifact is `workspace/models/<timestamp>.pkl`, and its Numerai model name is `NUMERAI_MODEL_PREFIX` followed by the timestamp. The deployed models are the artifacts in `workspace/models/`: the cron job (`tournament.cron`) runs every one of them. A `<timestamp>.py` in the repository root is only a working copy of a note and may be absent.

## Procedure

### 1. Collect announcements and ground truth

1. Run `python .claude/skills/numerai-update/scripts/check_numerai.py --since <date>` (`--lock-file` defaults to `uv.lock`, `--models-dir` to `workspace/models`). `<date>`: the oldest of (a) the oldest "researched" or "verified" date in any skill reference in this repo, (b) the oldest model training date, (c) 180 days ago. It prints:
   - payout and main-target history per round from the API, and the current configuration
   - available data versions and the latest version's benchmark models
   - forum announcements and blog posts since `<date>`
   - the locked numerapi version vs PyPI, and changelog entries newer than the locked version
   - the model artifacts with their modification times
2. Read every announcement and blog post it lists that touches the Classic tournament (data, targets, scoring, payouts, staking mechanics affecting submissions, deadlines, deprecations), including staff replies in the thread. Skip Signals and Crypto unless they affect shared tooling.
3. Search the forum for staff clarifications since `<date>` (`https://forum.numer.ai/search.json?q=<payout|target|dataset|deprecat|round>%20after:<date>`) and fetch the docs pages `https://docs.numer.ai/numerai-tournament/scoring`, `/data`, `/api` (current-state descriptions; the docs have no changelog, and `/scoring/definitions` has been stale).
4. Note **announced future changes** (cutover rounds or dates not yet reached, data versions to be decommissioned, scheduled numerapi removals): they are the most actionable findings.
5. List the channels you could not check (X, office hours) and ask the user whether they saw anything there.

Write down the current facts with date and source: latest data version and what `target` aliases in it (verify on the data if needed: `target` equals one named target in 100% of rows), main/payout target, payout formula and horizons, benchmark models, numerapi version and deprecations.

### 2. Inventory where the code, model scripts and skills encode these facts

Search the repository and the scripts of the deployed models with the same pattern:

```bash
set -a; . ./.env; set +a
notes() { /app/venv/bin/shrubbery-notes --store data/numerai.data "$@"; }
PATTERN="v[5-9]\.[0-9]|v[0-9]{2}_lgbm|lgbm_[a-z]+_[0-9]+|target_[a-z0-9]+_(20|60)|\
COLUMN_INDEX_TARGET|COLUMN_TARGET|v2_corr20|corr60|mmc60|bmc|neutral_|jupiter|\
neutralizer|validation[A-Z][A-Za-z0-9]+|diagnose|payout|multiplier|feature_set_name|\
round_model_performances|napi\.[a-z_]+"
grep -rn -I -E "$PATTERN" --include=*.py --include=*.md --include=*.toml \
  --exclude-dir=.venv --exclude-dir=workspace --exclude-dir=data .
for FILE in workspace/models/*.pkl; do
  MODEL=$(basename "${FILE%.pkl}")
  notes show "$MODEL" | grep -n -I -E "$PATTERN" | sed "s/^/note $MODEL:/"
done
```

The `grep` of the repository also matches the working copies `<timestamp>.py` in its root. If one of a deployed model differs from its note (`notes show <timestamp> | diff - <timestamp>.py`), report it: `numerai-run --retrain` trains the file on disk, not the note. Older `model` notes that are not deployed are the experiment history; do not report them as divergences.

Known places (verify, the list drifts):
- shrubbery package: data version and downloaded files in `src/shrubbery/numerai/ingest.py`; benchmark column, neutralizer file and local diagnostic metrics in `src/shrubbery/numerai/diagnostics.py`; numerapi pin in `pyproject.toml` and `uv.lock`; all `napi.*` calls (`napi.py`, `ingest.py`, `main.py`, `scores.py` in `src/shrubbery/numerai/`); metric definitions and the payout history in the `numerai-scores` help text (`src/shrubbery/numerai/scores.py`); target constants in `src/shrubbery/numerai/constants.py`.
- model scripts (the deployed `model` notes): feature set, targets by name or index, metrics used for CV and ensembling.
- documentation: `README.md` (= `CLAUDE.md` and `AGENTS.md`), e.g. the `--diagnose` defaults and the embargo of 60-day targets.
- skills under `.claude/skills/` with their references and scripts: the deployment objective (payout multipliers and metric keys), `numerai-run --diagnose` flags, `grep` keys and the benchmark model name in `numerai-autoresearch`; the channels and past changes in this skill's `references/channels.md`.

### 3. Check the trained models

- Training time of each model = modification time of `workspace/models/<timestamp>.pkl`. The timestamp in the name is when the model's experiment started, not when it was trained. The script marks artifacts written within 10 minutes of another one as a bulk write: their times reflect a copy or re-serialization, not training (e.g. the move of the artifacts into this repo). For those, use the latest run log in `workspace/logs/` (named after the run's start time) that contains `Training model: <timestamp>` and then a `Stored model:` line (`grep -l "Training model: <timestamp>" workspace/logs/*.log`), or ask the user.
- For each model, list the Numerai changes that happened **after** it was trained and matter for it: a new data version (the model still uses old features and the old `target` alias), a new main or payout target, a new payout horizon. A model trained before such a change needs a retrain to benefit, even after the code is updated.
- Inference loads the artifact and never reads the script, and the artifact carries the `shrubbery.*` code it was trained with by value. A change to the model script or to the estimator-side code (`model.py`, `constants.py` as used by the estimator) reaches a model only through a retrain; a change to the runner (`main.py`, `ingest.py`, `napi.py`, `diagnostics.py`) reaches every model at the next run once it is on `main`, since CI rebuilds the image that `run.sh` pulls.

### 4. Compare and recommend

For every fact from step 1, check each place from step 2 and each model from step 3. Classify:

- **Pays now**: divergence that changes what the models learn or are judged on today (old data version, training target ≠ payout target, objective or experiment metric ≠ payout formula, models trained before a cutover).
- **Will break**: deprecated numerapi calls with a scheduled removal, data versions announced for decommissioning, announced future cutovers.
- **Stale documentation**: skills, references, help texts or README describing an old state.

Write the report:
1. Digest of changes since `<date>`, each with date and source link; announced future changes first.
2. Current facts (data version, `target` alias, main/payout target, payout formula, benchmark models, numerapi version).
3. Model training dates and the changes each model has not been retrained for.
4. Divergences by class, each with its location (`file:line`, or `note <timestamp>:line` for a model script), what it says, what is true now, and the recommended change. Note when a change needs:
   - a retrain (see step 3 for which changes reach a model only through one);
   - a new model: a change to a model script becomes a new `model` note copied from the deployed one, since a note records the script as it was run; the new timestamp gives a new Numerai model name, which receives submissions only once it is registered on the account (until then they go to `NUMERAI_MODEL_PLACEHOLDER`);
   - a push to `main` (shrubbery dependency or code changes, which CI builds into the image);
   - a re-baseline of the `numerai-autoresearch` noise floor (a changed experiment metric makes old `model` notes incomparable).
5. Channels not checked, questions for the user.

If you found a change through a channel not described in `references/channels.md`, recommend adding it there.
