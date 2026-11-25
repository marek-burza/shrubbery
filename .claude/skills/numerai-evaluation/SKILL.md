---
name: numerai-evaluation
description: Evaluates how changes to the Numerai model code affected live tournament performance. Reconstructs the timeline of model changes from the `model` notes of the experiments log (`shrubbery-notes`) and run logs, pulls live scores with the `numerai-scores` tool, checks Numerai's current scoring announcements, attributes performance inflections to code changes while separating out market-regime effects and noise, produces performance plots annotated with the changes, and writes recommendations for upcoming experiments. Use when asked what worked or did not work, why performance changed, to plot model performance over time, or what to try next.
---

You are a quantitative researcher auditing the Numerai model family in this repo. The goal is an
honest attribution: which model-code decisions moved live tournament performance, which swings
were market regime or noise, and what to test next. Being clear about uncertainty is part of the
job — most single inflections will not be statistically separable from noise, and saying so is a
valid result.

Read `references/scoring.md` first. It holds dated scoring facts, the `target` alias per data
version, noise levels and pitfalls from earlier evaluations.

## Ground rules

- **Model changes come from the `model` notes in `data/numerai.data` (their format is defined in the
  Experiments Log and Logging Results sections of the `numerai-autoresearch` skill), plus the run logs in `workspace/logs/` if present.** Do not read git history (of this repo or shrubbery) or use `gh`. Other sources are
  limited to the `numerai-scores` tool and Numerai's public docs, forum and blog.
- **Read-only** with respect to model code, configs, README and shrubbery. Write outputs only to
  `workspace/analysis/<YYYYmmdd>/` (git-ignored). The only file in the repo you may edit is
  `references/scoring.md`, to refresh facts that step 1 found outdated.
- **Never print secrets.** Load credentials from shrubbery's `.env` into the environment only.

## Tooling

Locate shrubbery: `SHRUBBERY_DIR` if set, else `../shrubbery` next to this repo, else
`~/workspace/shrubbery`. Then:

- Scores: `numerai-scores` on `PATH` (Docker image), else
  `set -a; . "$SHRUBBERY_DIR/.env"; set +a; uv run --project "$SHRUBBERY_DIR" numerai-scores ...`.
  Read `numerai-scores --help` once — it documents fields, metrics and caveats.
- Experiments log: `/app/venv/bin/shrubbery-notes --store data/numerai.data list model` in the
  container, else `uv run --project "$SHRUBBERY_DIR" shrubbery-notes --store data/numerai.data list model`,
  from this repo's root with its `.env` loaded (`SHRUBBERY_KEY`). `show TIMESTAMP` prints a model's
  script. Never print the key.
- Python for the scripts in `scripts/`: `/app/venv/bin/python` in the container, else
  `uv run --project "$SHRUBBERY_DIR" python`.

## Procedure

### 1. Verify the current scoring

Before any analysis, confirm what Numerai currently pays for and scores against:

1. Fetch `https://docs.numer.ai/numerai-tournament/scoring` and `https://docs.numer.ai/numerai-tournament/data`,
   search the forum and blog for announcements newer than the "verified" date in
   `references/scoring.md` (payout formula, main target, horizons, new data version, BMC definition).
2. Compare with `references/scoring.md` and `numerai-scores --help`. If anything changed, update
   `references/scoring.md` (new date, cite the source) and note the change in the report.
3. Decide the metrics for this run and state them explicitly:
   - **Attribution metric**: `neutral_bmc` for rounds from 1393 (2026-11-06), `bmc` before
     (regime-robust, measured against the payout target of the time). The two are different series
     with a break at the cutover: never compare values across it. Switch only if step 1 shows
     Numerai changed what BMC measures or a better benchmark-neutral metric exists.
   - **Payout metrics**: whatever the current formula uses (`neutral_corr`, `neutral_mmc` from round
     1393; `corr60`, `mmc60` for rounds 1343–1392), reported alongside — this is what earns money.
   - **Early indicator**: partial (`--include-partial`) 60-day scores for changes younger than
     ~84 days. Rounds from 1393 have no 20-day scores any more; final 20-day `v2_corr20` / `mmc`
     exist only for older rounds.
   - **Regime references**: `integration_test` plus the current benchmark model for the payout
     target (`v6_lgbm_jupiter60` for data v6; `v53_lgbm_ender60` before; confirm the name exists).

### 2. Reconstruct the change timeline

1. Parse `list model`. Each line is `TIMESTAMP model <status> ncorr=… nbmc=… metric=… sigma=…
   delta=… parent=… | <description>`, one trained model per note: `TIMESTAMP` is when the experiment
   started, the description says what changed, `status` (baseline / keep / discard / crash / manual)
   whether it was kept, and
   `ncorr` / `nbmc` / `metric` are its offline validation diagnostics (`-` where not applicable):
   local v6 diagnostics with `metric = 8·ncorr + 32·nbmc`. Older notes carry `corr=` / `bmc=`
   instead: hosted v5.3 diagnostics with `metric = 3·corr + 15·bmc`. The two kinds are not
   comparable.
   `parent` links to the model it was copied from; `show TIMESTAMP` gives the full script when
   the description is not enough.
2. A Numerai model named `${NUMERAI_MODEL_PREFIX}<YYYYmmddHHMMSS>` is the full-training deployment
   of the note at that timestamp (normally a `keep`); follow its `parent=` chain back to see the
   changes that led to it. Such models are trained once and never retrained, so each one is its own
   change event, scoped to that model, going live from the first round whose staking closes after
   its training finished. Notes without a Numerai model of that name never went live: use them only
   as context (what was tried and rejected offline).
3. Models with no note at their timestamp predate the experiments log: date and label their changes
   from the run logs only. If a scope or go-live date is ambiguous, flag it as an assumption instead
   of guessing silently.
4. If `workspace/logs/*.log` exist, use them to date and check retrains. Each run logs `Model Name:`,
   `Notes:` (the experiment label of the config) and timestamped lines; a run containing
   `Training model: model_<name>` is a retrain, finishing at its `Stored model:` line (or last line).
   Timestamps inside the logs are UTC; log file names use the host's local time (they were 2 hours
   ahead in 2026-10), so date runs by their log lines. Use logs to:
   - add retrains missing from the notes (scope = that model, label = its `Notes:`) and confirm or
     correct note dates;
   - find runs that failed or never submitted (no `Submitted tournament predictions` line, a
     traceback) — they explain gaps in the scores;
   - read `Ensemble with highest score:` lines, which show what a retrained ensemble actually chose.
   When notes and logs disagree, prefer the logs for timing and the notes for intent, and say so.
5. Add external events from step 1: scoring-target and payout changes, and data-version changes
   (the `target` alias changes at the next retrain on the new version).
6. Write `events.csv` with columns `date,id,scope,label`, `date` as an ISO 8601 UTC date-time from
   the notes (convert their `YYYYmmddHHMMSS` timestamps) or the logs (external events: the announced cutover time, or the round's staking close). `scope` is `all` (family-wide change),
   `target` (scoring/training target or data version), `retrain`, or a model name. Number
   family-wide events `1, 2, …`, target events `T1, T2, …`, model events with letters.
7. Note gaps: live swings with no new model or logged retrain nearby stay **unexplained** (possible causes: regime,
   shared-library changes, untracked retrains) — report them as such rather than inventing a cause.

### 3. Fetch live scores

```bash
numerai-scores <all current and retired family models> integration_test <benchmark> \
  -m neutral_corr -m neutral_mmc -m neutral_bmc -m v2_corr20 -m mmc -m bmc -m corr60 -m mmc60 \
  -m corr_w_meta_model \
  --format csv --output workspace/analysis/<date>/scores.csv
```

Include retired models — they carry history. Without arguments the tool fetches all account
models, which then misses the references, so list everything explicitly.

### 4. Attribute — separate code effects from regime and noise

Run `python scripts/analyze_scores.py --scores ... --events ... --models <family> --reference
integration_test <benchmark> --control <frozen control model> --since <date>` once with final scores
of the attribution metric and once with `--metric neutral_corr` (`v2_corr20` for history before round
1393), and with `--include-partial` for recent events. Keep `--since` on one side of the round-1393
cutover, or run the two eras separately; from round 1393 also pass `--corr-metric neutral_corr` (the
default `v2_corr20` is no longer scored). It reports the noise floor, regime exposure, before/after tests for family-wide
events, difference-in-differences tests for model-specific events, and the gap of each model to the
control.

Interpret with these rules:

- **Noise first.** Use the reported z: |z| ≥ 2 likely real, 1–2 suggestive, < 1 noise. Never claim an
  attribution the numbers do not support. A shift must also persist for more than one independent
  block.
- **Regime.** If the reference moved strongly at the same time, or the family's raw corr is
  uncorrelated with the reference while percentiles anti-correlate, treat the swing as regime unless
  BMC or a within-family contrast also moved.
- **Within-family contrasts beat time comparisons.** A model-specific change measured against the
  rest of the family cancels the regime. A change applied to all models at once can only be compared
  against the reference and its own past — weaker evidence.
- **Natural controls.** Retrains with effectively unchanged configs, a frozen control model, or a
  model reverted to old code are the strongest evidence available; look for them.
- **Mechanics.** A change acts from the first round whose staking closes after the model finished training.
  Scoring-target changes alter the measuring stick, not the model. A family-wide swing with no new
  model nearby may come from shared-library changes or regime: leave it unexplained.
- **Confounding.** Changes made at the same time cannot be separated — say so.
- **Data quality.** Missed rounds (gaps in the scores, failed runs in the logs) are findings; note them
  where they distort a comparison.
- Cross-check: did experiments kept on offline validation (`keep` notes) also help live?

### 5. Plot

```bash
python scripts/plot_scores.py --scores ... --events ... --models <family in display order> \
  --reference integration_test --control <control> --metrics neutral_corr neutral_bmc --since <date> \
  --out-dir workspace/analysis/<date>
```

This produces `performance_annotated.png` (regime panel, one panel per model, event key) and
`<control>_full_history.png`. **Open both images and check them**: labels must not collide, events
must sit on the right dates, and every event in the key must be meaningful. Shorten labels or drop
trivial events and re-render if needed.

### 6. Report and recommend

Write `workspace/analysis/<date>/report.md` and summarize it in the reply:

1. Scoring context: current payout formula, targets, any change found in step 1, metrics used.
2. Inflection table: date range, trajectory, likely cause, evidence (z, contrast used), confidence.
3. Good and bad decisions, each with its evidence and confidence.
4. **Recommendations for upcoming experiments, scoped to predictive / tournament performance only**
   (data, features, targets, learners, ensembling, neutralization, training procedure, evaluation of
   experiments). Leave out infrastructure, tooling and ops — mention ops issues only as findings that
   affected attribution. For each recommendation give the hypothesis, the evidence behind it, the
   exact change, the expected direction, and how to judge it: keep a frozen control model, change one
   thing per model slot, rank on the attribution and payout metrics, and state the minimum duration
   (enough independent blocks to clear the noise floor measured in step 4).
5. Open questions and assumptions (e.g. retrain dates that were inferred).
