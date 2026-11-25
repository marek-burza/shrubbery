---
name: numerai-update
description: Checks Numerai's recent tournament, data and scoring announcements and numerapi package releases, compares them with the model code (this repo and shrubbery), the skills in this repo and their references (e.g. references/scoring.md), checks when the models were last trained, and recommends changes to bring code, skills and models in line. Use periodically, after Numerai news, before a retrain, or when asked whether anything changed at Numerai, whether the code is up to date, or whether a new data version, target or payout is in effect.
---

You keep the Numerai pipeline in line with what Numerai currently runs. Missed changes have cost
performance before: training on v5.2 two months after v5.3 was released, not noticing the switch of
the paid correlation to `v2_corr20`, of the main target (Cyrus → Ender-20 → Ender-60), and of the
payout from 20-day to 60-day scores. Your output is a dated list of what changed at Numerai, where
the code, skills and trained models diverge from it, and the recommended changes.

Read `references/channels.md` first: where each kind of change gets announced, and which channels
carried which past changes. Changes are not always in the forum Announcements category — the
Ender-60 payout switch was only in the blog's Numerai Monthly and in the docs.

## Ground rules

- **Read-only.** Do not edit code, configs, skills or references. Write only the report to
  `workspace/analysis/update-<YYYYmmdd>/report.md` (git-ignored). Offer to apply the changes after.
- **Never print secrets.** Load credentials from shrubbery's `.env` into the environment only; the
  checks below work without credentials.
- Prefer machine-readable ground truth (API) over prose; use prose to learn the why, the timing of
  future changes and deprecation schedules.

## Tooling

Locate shrubbery: `SHRUBBERY_DIR` if set, else `../shrubbery` next to this repo, else
`~/workspace/shrubbery`. Run Python with `/app/venv/bin/python` in the container, else
`uv run --project "$SHRUBBERY_DIR" python`.

## Procedure

### 1. Collect announcements and ground truth

1. Run `python scripts/check_numerai.py --since <date> --shrubbery "$SHRUBBERY_DIR" --models-dir
   workspace/models`. `<date>`: the oldest of (a) the oldest "verified" date in any skill reference
   in this repo, (b) the oldest model training date, (c) 180 days ago. It prints:
   - payout and main-target history per round from the API, and the current configuration
   - available data versions and the latest version's benchmark models
   - forum announcements and blog posts since `<date>`
   - the locked numerapi version vs PyPI, and changelog entries newer than the locked version
   - model files with their modification times
2. Read every announcement and blog post it lists that touches the Classic tournament (data,
   targets, scoring, payouts, staking mechanics affecting submissions, deadlines, deprecations) —
   including staff replies in the thread. Skip Signals and Crypto unless they affect shared tooling.
3. Search the forum for staff clarifications since `<date>`
   (`https://forum.numer.ai/search.json?q=<payout|target|dataset|deprecat|round>%20after:<date>`)
   and fetch the docs pages `https://docs.numer.ai/numerai-tournament/scoring`, `/data`, `/api`
   (current-state descriptions; the docs have no changelog, and `/scoring/definitions` has been stale).
4. Note **announced future changes** (cutover rounds or dates not yet reached, data versions to be
   decommissioned, scheduled numerapi removals) — they are the most actionable findings.
5. List the channels you could not check (X, office hours) and ask the user whether they saw
   anything there.

Write down the current facts with date and source: latest data version and what `target` aliases in
it (verify on the data if needed: `target` equals one named target in 100% of rows), main/payout
target, payout formula and horizons, benchmark models, numerapi version and deprecations.

### 2. Inventory where the code and skills encode these facts

Search both repos (this one and shrubbery; skip `.venv`, `workspace/`, `uv.lock` except for the
numerapi pin):

```bash
grep -rn -I -E "v5\.[0-9]|v[0-9]{2}_lgbm|target_[a-z0-9]+_(20|60)|COLUMN_INDEX_TARGET|COLUMN_TARGET|\
v2_corr20|corr60|mmc60|bmc|neutral_|jupiter|neutralizer|validation[A-Z][A-Za-z0-9]+|diagnose|\
payout|multiplier|0\.75|2\.25|feature_set_name|integration_test|\
round_model_performances|napi\.[a-z_]+" --include=*.py --include=*.md --include=*.toml .
```

Known places (verify, the list drifts):
- shrubbery: data version and downloaded files in `src/shrubbery/numerai/ingest.py`; benchmark column,
  neutralizer file and local diagnostic metrics in `src/shrubbery/numerai/diagnostics.py`; numerapi pin in `pyproject.toml` /
  `uv.lock`; all `napi.*` calls (`napi.py`, `tournament.py`, `main.py`, `numerai/scores.py`); metric
  definitions and the payout history in the `numerai-scores` help text (`numerai/scores.py`);
  target constants in `constants.py`.
- this repo: model configs (`*.py` in the root — feature set, targets by name or index, metrics used
  for CV and ensembling); `README.md` (= `CLAUDE.md`/`AGENTS.md`); every skill under `.claude/skills/` with its references and scripts (e.g. the
  deployment objective, `numerai-run --diagnose` flags and `grep` keys in `numerai-autoresearch`, `numerai-evaluation/references/scoring.md`, metric
  horizons and reference model names in its scripts).

### 3. Check the trained models

- Training time of each model = modification time of its file in `workspace/models/`. If the script
  warns that all files were written within minutes, the times reflect a bulk rewrite (e.g. a
  serialization change), not training; then use the end of its training run in `workspace/logs/`
  (`Stored model:` line), or ask the user.
- For each model, list the Numerai changes that happened **after** it was trained and matter for it:
  a new data version (the model still uses old features and the old `target` alias), a new main or
  payout target, a new payout horizon. A model trained before such a change needs a retrain to
  benefit, even after the code is updated.

### 4. Compare and recommend

For every fact from step 1, check each place from step 2 and each model from step 3. Classify:

- **Pays now** — divergence that changes what the models learn or are judged on today (old data
  version, training target ≠ payout target, objective or experiment metric ≠ payout formula,
  models trained before a cutover).
- **Will break** — deprecated numerapi calls with a scheduled removal, data versions announced for
  decommissioning, announced future cutovers.
- **Stale documentation** — skills, references, help texts or README describing an old state.

Write the report:
1. Digest of changes since `<date>`, each with date and source link; announced future changes first.
2. Current facts (data version, `target` alias, main/payout target, payout formula, benchmark models,
   numerapi version).
3. Model training dates and the changes each model has not been retrained for.
4. Divergences by class, each with `file:line`, what it says, what is true now, and the recommended
   change. Note when a change needs a retrain, a Docker image rebuild (shrubbery dependency or code
   changes), or a re-baseline of the `numerai-autoresearch` noise floor (a changed experiment metric makes
   old `model` notes incomparable).
5. Channels not checked, questions for the user.

If you found a change through a channel not described in `references/channels.md`, recommend
adding it there.
