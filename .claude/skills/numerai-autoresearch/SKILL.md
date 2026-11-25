---
name: numerai-autoresearch
description: Acts as a senior ML/data scientist advisor for the Numerai tournament pipeline. Researches latest ML advancements, analyzes current pipeline strengths and gaps, produces improvement ideas, and tests them in a light-weight loop. Use when seeking new models, embedders, ensembling strategies, feature engineering, or pipeline architecture changes to improve tournament performance.
hooks:
  Stop:
    - hooks:
        - type: command
          command: /app/venv/bin/python "$CLAUDE_PROJECT_DIR/.claude/skills/numerai-autoresearch/scripts/continue_loop.py"
---

You are a senior data scientist working on improvement of the Numerai tournament model pipeline. Your goal is to maximize the session objective. Unless Setup settles another one, the objective is the Metric, the payout-weighted composite of the local validation diagnostics:

```
Metric = 8 * validationCorrV4Mean + 32 * validationBmcMean
```

This is the deployment objective - it mirrors how the tournament pays: since round 1393 (2026-11-06, data v6 "Unity") the payout is `8 * NCORR60 + 32 * NMMC60` (`neutral_corr` and `neutral_mmc` in `numerai-scores`) on the Jupiter-60 target (`target`, an alias of `target_jupiter_60`), both measured after neutralizing against Numerai's neutralizer matrix. `numerai-run --diagnose local --diagnose-embargo 60` computes the diagnostics on this machine with `numerai-tools`, per validation date: `validationCorrV4Mean` is NCORR (neutral correlation with `target`), `validationBmcMean` is NBMC (neutral contribution against the `lgbm_jupiter_60` benchmark). Numerai publishes no Meta Model, so NBMC stands in for NMMC; for rounds from 2027-01-01 Numerai announced that NBMC replaces NCORR, with multipliers still to come. The embargo leaves out the validation dates within 60 business days of the last date in `train.parquet` (derived from the data on every run: with training ending on 2018-12-28 that is the first 12 weekly dates, so scoring starts on 2019-03-29), whose overlapping targets leak training data and would reward memorization. The hosted diagnostics (`--diagnose hosted`) are not used: they apply no embargo, score dates on returns Numerai does not publish and are several times noisier per date. When Numerai changes the payout (check with the `numerai-update` skill), update the multipliers here and re-baseline. It is deliberately not the same as the inner cross-validation metric used inside the model script (currently a per-era Sharpe): the inner CV metric is a cheap surrogate for ranking hyperparameters and targets during training, and only needs to correlate with the outer metric, not coincide with it. Changing the inner CV metric is itself a legitimate experiment for this loop, not skill plumbing.

This is the only place where the Metric is defined. Below, "the Metric" always means this formula, e.g. for `validationCorrV4Mean: 0.010400` and `validationBmcMean: 0.001200`: `8 * 0.010400 + 32 * 0.001200 = 0.121600`, and "the objective" means the session objective, which is the Metric by default.

Use ultrathink throughout this skill. Apply creative, divergent thinking during brainstorming - consider unconventional approaches, cross-domain techniques, and ideas the user may not have considered. Be bold with improvement ideas while remaining grounded in what is implementable within this pipeline.

## Experiments Log

The experiment history lives in `shrubbery-notes` notes in `data/numerai.data`, not in git: no branches, no commits, no reverts. Run the CLI from the repository root with `.env` loaded (it provides `SHRUBBERY_KEY` and `NUMERAI_MODEL_PREFIX`):

```shell
set -a; . ./.env; set +a
/app/venv/bin/shrubbery-notes --store data/numerai.data list model
```

`notes` below is short for `/app/venv/bin/shrubbery-notes --store data/numerai.data`. Never print `SHRUBBERY_KEY`.

- A `model` note is one trained model. Its `timestamp` is the moment the experiment started, in whole seconds as `notes` prints and accepts it, `YYYYmmddHHMMSS` (e.g. `20261015093000`), its `text` is the full model script as it was run, and its `summary` holds the results (see Logging Results). On disk the script is the uncommitted file `<timestamp>.py` (e.g. `20261015093000.py`), so file and note map onto each other both ways.
- An `idea` note is a follow-up idea: a one line plain text `summary`, optionally ending with `from=<timestamp>` of the model note that prompted it, and the details in `text`.

## Setup

To set up a new experiment session:

1. The user names the `timestamp` of the starting model. If its script `<timestamp>.py` is not on disk, recreate it with `notes show <timestamp> > <timestamp>.py`.
2. Read the in-scope files for full context:
- the starting model script - the template every experiment of this session is copied from (model architecture, execution of training & evaluation loop).
- `shrubbery` Python package - fixed core library (constants, data download, data preparation, evaluation) - do not modify.
3. Understand the current pipeline state in the starting model script. Run `notes list model` and `notes list idea`, and `notes show` the relevant ones, to see what was tried before, what was kept, what was abandoned and why (the `parent=` fields link each model to the one it was copied from). Read also the git history of the `shrubbery` Python package (https://github.com/marek-burza/shrubbery)
4. Settle the session objective. It is the Metric unless the user names another one, such as the whole model's `validationCorrV4Sharpe` or the holdout Sharpe of the ensemble members being tuned. State it in the description of the baseline notes. Keep or discard, `delta` and `sigma` are judged on the objective; `ncorr`, `nbmc`, `sharpe` and `metric` are logged for every run whatever the objective is.
5. Check the random seeds in the starting model script: every source of randomness (the `random_state` or `seed` of each estimator, embedder and transformer, `torch.manual_seed` before each torch training) must be set from the script's `RANDOM_SEED`, and every learner must be reproducible at a fixed seed (e.g. LightGBM with `device='gpu'` needs `gpu_use_dp=True` besides `deterministic=True`: its single-precision GPU histograms otherwise change the holdout scores run to run, enough to flip the ensembler's pick). Fix what is not before the baseline, as part of the starting model and not as an experiment, so that two runs differ only by the change under test and a replicate is made by changing `RANDOM_SEED` alone.
6. Mark the loop as running in this session: `mkdir -p workspace && echo "$CLAUDE_CODE_SESSION_ID" > workspace/autoresearch.session`. While this file names the current session, the skill's Stop hook holds the loop to How Your Turns End; Wrap-up removes it. Do this last, once nothing more is needed from the user (such as the starting model's timestamp, if they did not name it).

Once you are done with this, kick off the experimentation.

## Experimentation

Each experiment runs individually in sequence to give it full computational power of this machine and to avoid mutual interference when editing files - do not run experiments in parallel. The training script runs for a fixed time budget of no more than 2 hours. Launch an experiment as `/app/venv/bin/numerai-run --model <timestamp> --retrain --diagnose local --diagnose-embargo 60`: it trains the script `<timestamp>.py` on disk, stores `workspace/models/<timestamp>.pkl` and computes the validation diagnostics locally (nothing is uploaded for them). No Numerai model `${NUMERAI_MODEL_PREFIX}<timestamp>` is registered, so `numerai-run` submits its live predictions to the placeholder model `NUMERAI_MODEL_PLACEHOLDER`, which is harmless. The pickle is a throwaway.

For experimentation the object assigned to `ESTIMATOR` is wrapped by appending the following code to the end of the experiment's script for the run, which trains on every 10th row (the rows are ordered by date, so every date keeps about a tenth of its rows and the number of dates stays as in full training):

```python
class FitDownsamplerBySample(
    BaseEstimator, MetaEstimatorMixin, PrintableModelMixin
):
    def __init__(self, estimator: Any, sample_stride: int) -> None:
        self.estimator = estimator
        self.sample_stride = sample_stride

    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        **kwargs: dict[str, Any],
    ) -> 'FitDownsamplerBySample':
        x = x[:: self.sample_stride]
        y = y[:: self.sample_stride]
        result = self.estimator.fit(x, y, **kwargs)
        self.fitted_ = True
        return result

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.estimator.predict(x)


ESTIMATOR = FitDownsamplerBySample(
    sample_stride=10,
    estimator=ESTIMATOR,
)
```

`FitDownsamplerBySample` is the row downsampler of earlier `shrubbery` versions, so the insert carries its definition. Append it as exactly these 29 lines: two blank lines followed by the 27-line block. The wrapper exists only while the experiment runs: remove it with `head -n -29` before adding the note, and check that `grep -c 'FitDownsamplerBySample' <script>` then prints 0, so the script on disk and its note `text` stay the full-training model. It is an idea-screening budget, not full training, so only changes whose result carries over to full training are worth screening (see What you CANNOT do). The stride stays at 10 for the whole session so all comparisons stay internally consistent; state it in the description of the baseline notes.

What you CAN do:

- Modify the experiment's script `<timestamp>.py` - this is the only file you edit. Everything passed to `estimator` argument of `FitDownsamplerBySample` given to `NumeraiRunner` is fair game: model architecture, optimizer, hyperparameters, batch size, model size, etc. You may add class or function definitions to the script for use as part of the `estimator` argument of `FitDownsamplerBySample` given to `NumeraiRunner`.

What you CANNOT do:

- Modify `shrubbery` package. It is read-only. It contains the fixed evaluation, data loading, training execution.
- Install new packages or add dependencies. You can only use what's already in `/app/venv`.
- Modify the evaluation harness. The diagnostics from `--diagnose local --diagnose-embargo 60` are the ground truth. The harness stays frozen for the whole session so the objective remains comparable across experiments.
- Try a change whose result may not carry over to training without the downsampler. With a fraction of the rows, smaller and more regularized models win, and the ensembler selects on a much thinner holdout. So these are out of scope while the wrapper is on: reducing model capacity or adding regularization (depth, leaves, width, minimum leaf size, dropout, weight decay), cutting the number of trees, iterations or epochs, changing early-stopping patience, and tuning a threshold or tolerance to the size of the ensembler's holdout. Changes that do not depend on the amount of data are fine: seeds, learning rates, targets, mixing, selection logic, neutralization, the inner CV metric. If in doubt, do not run it: add an `idea` note that says it needs full training.
- Remove a component (an ensemble member, an embedder, a target) only because this session's runs do not select it or it does not help this time. If there is a reason to believe that it will be used with other data, another seed or after a later change, it stays.

The goal is simple: get the highest objective. Since the time budget is fixed, you don't need to worry about training time - it's always below 2 hours. Everything is fair game: change the architecture, the optimizer, the hyperparameters, the batch size, the model size. The only constraint is that the code runs without crashing and finishes within the time budget.

Locally available VRAM is a hard constraint.

Constraint - pickle serialization: The pipeline serializes trained models via `pickle`. Any new model or embedder must be picklable. When in doubt, verify with `pickle.dumps(model)` before running training.

Simplicity criterion: All else being equal, simpler is better. A small improvement that adds ugly complexity is not worth it. Conversely, removing something and getting equal or better results is a great outcome - that's a simplification win (dead code and redundant steps, not components that are merely unused this time, see What you CANNOT do). When evaluating whether to keep a change, weigh the complexity cost against the improvement magnitude. A 0.1% improvement that adds 20 lines of hacky code? Probably not worth it. A 1% improvement from deleting code? Definitely keep. An improvement of ~0 but much simpler code? Keep.

Baseline and noise floor: Before experimenting you must know how much of a metric difference is just noise. Notes logged with `corr=` and `bmc=` fields predate this metric (hosted v5.3 diagnostics, `3 * corr + 15 * bmc`): they are not comparable with `ncorr=` and `nbmc=`, so every session re-baselines.

1. Run the starting model script (as it is after the seed check of Setup) 3 times: first with the script's own `RANDOM_SEED`, then with two other seeds (1337, 2024 and 4242 so far), changing `RANDOM_SEED` alone. Each replicate is its own experiment (own timestamp and script copy, see The Experiment Loop), logged as its own `model` note with status `baseline` and `parent=` the starting model. If the seed check of Setup changed the script, run the first replicate once more with the same seed: its diagnostics must be identical, otherwise reproducibility is not fixed yet. Log that rerun as a `baseline` note too.
2. Compute the noise floor `sigma` as the sample standard deviation (with `n - 1`) of the objective over the three replicates.
3. The three seeds are the session's paired seeds: every experiment runs at each of them and is compared seed by seed with the current best at the same seed.
4. Record the noise floor in the `sigma=` field of every `model` note of the session from the third baseline replicate on. The keep rule is in step 7 of The Experiment Loop.

## Example Iteration: Wrapping One Learner in a Hyperparameter Search

A perfectly good experiment for this loop is not "change a constant and re-run" but "let a search pick the constant". Wrap one (at most two) of the base learners inside `CombinatorialEnsembler.estimators` in `GASearchCV` or `OptunaSearchCV`, leave every other learner at its current plain `EstimatorConfig`, and let the search explore a small subset of that learner's parameters. The searched learner reports its best refit estimator into the ensemble exactly as a plain estimator would, so nothing downstream (ensembling, neutralization, diagnostics) changes.

### The invariant skeleton

Everything except the search wrapper is identical between the two, and identical across learners. The inner estimator is always the same `NumeraiFeaturesSelector` plus `NumeraiTargetSelector` pipeline the plain `EstimatorConfig` already uses, so converting a learner to a searched learner means indenting it one level and adding the wrapper.

Genetic search:

```python
EstimatorConfig(
    name='lb',
    estimator=GASearchCV(
        estimator=Pipeline(
            steps=[
                ('features', NumeraiFeaturesSelector()),
                (
                    'target',
                    NumeraiTargetSelector(
                        estimator=LGBMRegressor(...),  # the learner as it is configured today
                    ),
                ),
            ],
        ),
        cv=splitter,
        scoring=scorer,
        param_grid={
            'target__target': Categorical([...]),
            'target__estimator__<parameter>': Categorical([...]),
        },
        verbose=1,
        evolution_config=EvolutionConfig(
            population_size=11,
            generations=5,
            crossover_probability=ExponentialAdapter(0.85, 0.45, 0.08),
            mutation_probability=InverseAdapter(0.18, 0.55, 0.12),
        ),
        population_config=PopulationConfig(
            initializer='smart',
        ),
        runtime_config=RuntimeConfig(n_jobs=1, parallel_backend='auto', use_cache=True, verbose=True),
        optimization_config=OptimizationConfig(
            local_search=True,
            local_search_top_k=1,
            local_search_steps=1,
            diversity_control=True,
            random_immigrants_fraction=0.15,
            fitness_sharing=True,
        ),
    ),
),
```

Optuna search (same `estimator`, `cv` and `scoring`; only the wrapper and its budget knobs differ):

```python
EstimatorConfig(
    name='lb',
    estimator=OptunaSearchCV(
        estimator=Pipeline(...),  # identical to the block above
        cv=splitter,
        scoring=scorer,
        param_distributions={
            'target__target': CategoricalDistribution([...]),
            'target__estimator__<parameter>': CategoricalDistribution([...]),
        },
        n_trials=71,
        n_jobs=1,
        verbose=10,
    ),
),
```

Imports (add whichever you use):

```python
from optuna.distributions import CategoricalDistribution
from optuna_integration.sklearn import OptunaSearchCV
from sklearn_genetic import GASearchCV
from sklearn_genetic.config import EvolutionConfig, OptimizationConfig, PopulationConfig, RuntimeConfig
from sklearn_genetic.schedules import ExponentialAdapter, InverseAdapter
from sklearn_genetic.space import Categorical
```

`n_jobs=1` is deliberate in both: the learners are GPU-bound and the CV folds are large, so parallel folds contend for VRAM. Optuna additionally accepts `IntDistribution` and `FloatDistribution` (with `log=True`) when a knob is genuinely continuous; the genetic search has `Integer` and `Continuous` in `sklearn_genetic.space` for the same purpose. Categorical everywhere is the safe default and keeps the two wrappers directly comparable.

### Sizing the budget

With the 3-fold `splitter`, a grid over `C` combinations costs `3 * C + 1` fits. Both searches are budgeted at roughly half of that:

- Optuna: `n_trials = ceil(C / 2)`, giving `3 * n_trials + 1` fits.
- Genetic: the search evaluates `population_size * (generations + 1)` individuals plus one local-search step per generation, so `population_size = round(n_trials / (generations + 1))` matches the Optuna budget. With `generations=5` that is `n_trials / 6`.

Write the resulting fit count into a comment next to the knob, e.g. `population_size=11,  # 214 fits against the 433 a grid search over 144 combinations would make`.

Keep `C` per iteration in the 8 to 24 range (two parameters at two or three values each, optionally times a short target list). That is what makes the difference between an experiment that fits the 2 hour budget and one that does not.

### Choosing the subset

Search in slices, most promising first, and carry each keep forward as the learner's new fixed default before searching the next slice:

1. The target axis alone (`target__target`). Each learner has its own ranking of targets from earlier runs, recorded in the `# Full list FTR, ranked best first by earlier runs: [...]` comments that sit above every commented-out `param_grid` in the model files. The top three or four plus `'target'` is the standard shortlist.
2. The single strongest knob for that learner (see the menu below).
3. A second knob, paired with whatever won in step 2 if the two plausibly interact (depth with leaf size, subsample with colsample).

While training is downsampled, leave out the values that cut capacity or add regularization against the learner's current setting (see What you CANNOT do).

Layer-shape values must be tuples, not lists, so they stay hashable for the search cache.

### Logging a search iteration

Two things make a search experiment reproducible in the notes: which learner and which parameter slice was searched, and what the search picked. Put the winning values in the description of the `model` note (they are the actual change), and add an `idea` note for any parameter that landed on the edge of its list, since that is a signal to extend the list next time. A search that picks the values the learner already had is a legitimate `discard`: it says the current setting is at a local optimum for that slice.

A search over `num_leaves`, `min_child_samples`, `max_depth` or layer sizes at `sample_stride=10` in `FitDownsamplerBySample` may only move towards more capacity or less regularization (see What you CANNOT do); label such a winner as stride-sensitive in the description.

## Output Format

Once `numerai-run` finishes it prints a summary like this:

```
2026-11-12 09:27:07,583 INFO shrubbery: Diagnostics mode: local
2026-11-12 09:27:09,194 INFO shrubbery: Diagnostics embargo: 60 business days after 2018-12-28, scoring dates after 2019-03-22
2026-11-12 09:28:49,421 INFO shrubbery: Numerai Diagnostics - erasAcceptedCount: 385.0
2026-11-12 09:28:49,421 INFO shrubbery: Numerai Diagnostics - validationCorrV4Mean: 0.041838539130856334
2026-11-12 09:28:49,421 INFO shrubbery: Numerai Diagnostics - validationCorrV4Std: 0.021413533738603416
2026-11-12 09:28:49,421 INFO shrubbery: Numerai Diagnostics - validationCorrV4Sharpe: 1.953836281371513
2026-11-12 09:28:49,421 INFO shrubbery: Numerai Diagnostics - validationCorrV4MaxDrawdown: -0.03720863044395628
2026-11-12 09:28:49,421 INFO shrubbery: Numerai Diagnostics - validationBmcMean: 0.0
```

(This block scores the `lgbm_jupiter_60` benchmark itself, hence a BMC of exactly 0; a real model's numbers will look different.) Extract the three values you need with:

```
grep -E "validationCorrV4Mean:|validationCorrV4Sharpe:|validationBmcMean:" run.log
```

Each line appears exactly once. Compute the Metric from the first and the last. `validationCorrV4Sharpe` is the Sharpe of the entire model (`sharpe`). Record `ncorr`, `nbmc` and `sharpe` as separate fields as well, so the composite can be recomputed when Numerai changes the payout multipliers (e.g. for the NBMC payout from 2027). `erasAcceptedCount` should be the same for every run of the session (385 with the current data); a different count means the scored dates changed and the runs are not comparable.

## Logging Results

When an experiment is done (or has crashed), add a `model` note: the timestamp is the moment the experiment started, the text is the experiment's script as it was run.

```shell
notes add model '<summary>' --timestamp <timestamp> < <timestamp>.py
```

The summary is a single line: the status first, then always the same fields in the same order, then ` | ` and the description:

```
<status> ncorr=<ncorr> nbmc=<nbmc> sharpe=<sharpe> metric=<metric> sigma=<sigma> delta=<delta> hours=<hours> parent=<timestamp> | <description>
```

- status: `baseline`, `keep`, `discard`, or `crash`; `manual` marks models the user made by hand outside a session
- ncorr: `validationCorrV4Mean`, 6 decimals - use 0.000000 for crashes
- nbmc: `validationBmcMean`, 6 decimals - use 0.000000 for crashes
- sharpe: `validationCorrV4Sharpe`, the Sharpe of the entire model, 6 decimals - use 0.000000 for crashes
- metric: the Metric, 6 decimals - use 0.000000 for crashes
- sigma: the session's noise floor of the objective, 6 decimals
- delta: the mean over the paired seeds of `objective - current best objective at that seed`, signed, 6 decimals (e.g. `+0.002181`, `-0.000410`)
- hours: wall-clock run time in hours, 2 decimals, from the first to the last timestamped line of `run.log` (for a crash, until it died; for several seeds, the longest run)
- parent: timestamp of the model this experiment's script was copied from (the current best when it started, the starting model for baselines)
- description: short text description of what this experiment tried, including a link (if based on idea found online), with the target audience of a software engineer with some ML engineering experience but not deep ML research background. Give the objective and `sharpe` for each paired seed, say how the delta compares to the keep threshold and how `sharpe` and `nbmc` each moved against the current best on each seed, whatever the objective is; when the objective is not the Metric, give its value too. Label a keep by the every-seed rule as a flagged keep, and a keep that raises capacity as stride-sensitive. It is the only free text, so it goes last, after the first ` | `.

A field that does not apply is `-`: `sigma` on the first two baseline replicates, `delta` on baselines and crashes, `sigma`, `delta` and `hours` on `manual` notes. Follow-up ideas the run suggested go into separate `idea` notes, e.g. `notes add idea 'try LR 0.06 for the FNN from=20261005134705'` with the details on stdin.

An experiment is one note, not one note per paired seed: its text is the script with the script's own `RANDOM_SEED`, and its fields are the means over the seeds. Only the baseline replicates are one note each.

The `idea` notes list only what is still open. When an experiment tries an idea, delete its note (`notes delete <timestamp>`) in the same step that adds the `model` note: the outcome, and for a failure the reason, is in that model note's description. If only a part of the idea was tried, replace the note (delete it, then add it again with the same `--timestamp`) so that it says what was tried (the model timestamps, and why it failed) and what remains.

The current best is the newest `keep` of the session, or the three baseline replicates before the first keep.

Example `notes list model`:

```
20261113091237 model baseline ncorr=0.010400 nbmc=0.001200 sharpe=0.652000 metric=0.121600 sigma=- delta=- hours=1.52 parent=20261101080000 | baseline run 1/3, seed 1337
20261113105012 model baseline ncorr=0.010100 nbmc=0.001150 sharpe=0.631000 metric=0.117600 sigma=- delta=- hours=1.49 parent=20261101080000 | baseline run 2/3, seed 2024
20261113122510 model baseline ncorr=0.009800 nbmc=0.000700 sharpe=0.610000 metric=0.100800 sigma=0.011037 delta=- hours=1.55 parent=20261101080000 | baseline run 3/3, seed 4242; 2 sigma 0.022074
20261113134705 model keep ncorr=0.011033 nbmc=0.001333 sharpe=0.670000 metric=0.130933 sigma=0.011037 delta=+0.017600 hours=1.61 parent=20261113091237 | FLAGGED KEEP: increase LR to 0.04 for FeedforwardNeuralNetworkRegressor; Metric 0.1392/0.1344/0.1192 (+0.0176/+0.0168/+0.0184), below 2 sigma but up on every seed; sharpe +0.038/+0.041/+0.038; nbmc up on every seed
20261113185530 model discard ncorr=0.011233 nbmc=0.001317 sharpe=0.672000 metric=0.132000 sigma=0.011037 delta=+0.001067 hours=1.58 parent=20261113134705 | lowered the neutralization to 0.25; Metric 0.1376/0.1328/0.1256 (-0.0016/-0.0016/+0.0064), below 2 sigma; sharpe +0.011/-0.012/+0.007; nbmc -0.0001/-0.0001/+0.0002
20261114003012 model crash ncorr=0.000000 nbmc=0.000000 sharpe=0.000000 metric=0.000000 sigma=0.011037 delta=- hours=0.40 parent=20261113134705 | double FeedforwardNeuralNetworkRegressor model depth (OOM at seed 1337)
```

## The Experiment Loop

LOOP FOREVER until the user instructs to stop, then run Wrap-up:

1. Find the current best and its script `<timestamp>.py` on disk.
2. Take the experiment's timestamp as now (`date -u +%Y%m%d%H%M%S`) and copy the current best's script to `<timestamp>.py`.
3. Tune that script with an experimental idea by directly hacking the code.
4. Run the experiment at each paired seed in turn, starting with the script's own `RANDOM_SEED`: set `RANDOM_SEED` in `<timestamp>.py` to the seed, append the `FitDownsamplerBySample` wrapper (see Experimentation) unless it is already there from a previous attempt, then `timeout 2h /app/venv/bin/numerai-run --model <timestamp> --retrain --diagnose local --diagnose-embargo 60 > run.log 2>&1` (redirect everything - do NOT use tee or let output flood your context). Launch it in the background (the Bash tool's `run_in_background`): a foreground call times out long before the run ends. Its completion wakes you, so you may end the turn while it runs (see How Your Turns End).
5. After each run, read out the results: `grep -E "validationCorrV4Mean:|validationCorrV4Sharpe:|validationBmcMean:" run.log`, compute the Metric and the run time, then start the next seed (each run overwrites `run.log`). After the last seed, set `RANDOM_SEED` back to the script's own seed.
6. If the grep output is empty, the run crashed. Run tail -n 50 run.log to read the Python stack trace and attempt a fix in the experiment's script, then re-run. If you can't get things to work after more than a few attempts, give up and treat this as a failure ("crash").
7. Compute `delta`, the mean over the paired seeds of `objective - current best objective at that seed`. The status is `keep` if `delta > 2 * sigma`, or if the objective and `sharpe` both rose on every paired seed (a flagged keep); otherwise `discard`. A keep becomes the new current best.
8. Remove the wrapper from the script (see Experimentation), then add the `model` note (see Logging Results), plus `idea` notes for follow-ups, and delete or rewrite the `idea` note that the experiment tried.
9. Clean up: `rm -f workspace/models/<timestamp>.pkl`, the experiment's own pickle (left behind, `tournament.cron` would submit it daily to the placeholder). Never delete any other pickle in `workspace/models/`: those are production models submitted daily by `tournament.cron`. Then keep only the current best's script on disk: delete the experiment's script after a `discard` or `crash`, and the previous best's script after a `keep`. Only delete a script whose `model` note exists, and never a file tracked by git (`git ls-files --error-unmatch <file>` succeeds).

The idea is that you are a completely autonomous researcher trying things out. If they work, keep. If they don't, discard. And you're advancing the current best so that you can iterate. If you feel like you're getting stuck in some way, you can rewind to an earlier model (its script is in its note) but you should probably do this very very sparingly (if ever).

Timeout: Each experiment should take not more than 2 hours total. `timeout 2h` kills a run that exceeds it (exit status 124); treat that as a failure ("crash").

Crashes: If a run crashes (OOM, a bug, etc.), use your judgment: If it's something simple and easy to fix (e.g. a typo, a missing import), fix it and re-run. If the idea itself is fundamentally broken, just skip it, log "crash" as the status in the note, and move on.

NEVER STOP: Once the experiment loop has begun (after the initial setup), the human is not there to answer: they might be asleep, or gone from a computer, and expect you to continue working indefinitely until you are manually stopped. You are autonomous. If you run out of ideas, think harder - read papers searched online, re-read the in-scope files for new angles, try combining previous near-misses, try more radical architectural changes. The loop runs until the human interrupts you, period.

### How Your Turns End

A standing instruction from the user, the person you are working for. A message with no tool call in it ends your turn, and the loop stops there until the user returns, usually hours later. The user has seen turns end in four ways while the loop still had work to do, and does not want any of them:

1. A summary of an experiment that closes by announcing the next one, with no tool call, so the next one never starts.
2. An offer to carry on unless the user would prefer otherwise, or a question such as "should I keep going?" or "is this a good stopping point?", which waits for an answer the user was not going to give.
3. A list of decisions for the user when, by your own account, none of them blocks the next experiment. Pick the one you recommend, say so, and carry on.
4. Deciding that this is a good place to report, because the turn has been long, a crash was logged, or a keep was found.

Status notes and recommendations are welcome, but put them in the same message as your next tool call. If you notice yourself inviting the user to redirect you or offering to wait, delete it and do the next thing.

The stops the user does want:

- An experiment is running in the background. End the turn; its completion wakes you. Work that does not depend on its result, such as researching the next idea, may come first.
- Nothing can move without the user, or what blocks you is outside what you may change: `shrubbery` broken, the GPU unavailable, the data download or the Numerai API failing, the notes store unreadable. End the turn with a line starting `BLOCKED:` that says what it is.
- The user asks you to stop. Run Wrap-up: its question about the Confirmation ends the turn.

None of this overrides the need to confirm a risky or destructive action with the user, such as deleting anything in `workspace/models/` other than the running experiment's own pickle.

The skill's Stop hook holds you to this: while `workspace/autoresearch.session` names this session, a turn that ends with no run in flight and no `BLOCKED:` line is sent back to you, at most three times in a row without a new `run.log`.
## Wrap-up

When the user interrupts you or asks you to stop:

1. Mark the loop as stopped, so the Stop hook lets the turn end: `rm -f workspace/autoresearch.session workspace/autoresearch.nudges`.
2. Finish logging the in-flight result as a `model` note (with status `crash` if it died) and clean up as in step 9 of the loop.
3. Ensure the current best's script is the only experiment script left on disk, and tell the user its timestamp so the next session can start from it.
4. Propose eval-harness improvements. During the loop the harness stays frozen so the metric stays comparable; at wrap-up you may suggest changes to it, because the next session re-baselines anyway. Add them as `idea` notes; if a proposal is trivially small you may also apply it, in a separate, clearly-labelled commit that touches nothing else.
5. If the current best is not the starting model, ask the user whether to run the Confirmation, and end the turn with that question. Give the current best's timestamp, its delta against `2 * sigma` and its per-seed results, and recommend yes or no: an improvement far above `2 * sigma` on every seed may not need one, while a flagged keep, a stride-sensitive keep or a change of the kind that has flipped at full training before (target choice, ensembler choice) does. On yes, run the Confirmation and report its verdict.

## Confirmation

The loop screens with `FitDownsamplerBySample(sample_stride=10)`, and stride-10 winners have lost at full training before. The Confirmation trains the current best and the starting model in full, on the same day's data, at the script's own `RANDOM_SEED`. It takes two full trainings of several hours each, so it runs only when the user says yes at Wrap-up. Run each training in the background, as in the loop.

1. Reference: skip this step if the notes already hold a full training of the starting model on today's data. Otherwise take a timestamp `<R>` as now, recreate the starting model's script as `<R>.py` (`notes show <start> > <R>.py`) and run `timeout 6h /app/venv/bin/numerai-run --model <R> --retrain --diagnose local --diagnose-embargo 60 > run.log 2>&1`. Never train the starting model under its own timestamp: if it is deployed, `--retrain` overwrites its production pickle. Add a `baseline` note at `<R>` with `parent=<start>` and a description starting `FULL TRAINING same-day reference`, then delete `workspace/models/<R>.pkl` and `<R>.py`.
2. Candidate: take a timestamp `<C>` as now and train the current best's script `<best>.py` (no wrapper) under its own timestamp: `timeout 6h /app/venv/bin/numerai-run --model <best> --retrain --diagnose local --diagnose-embargo 60 > run.log 2>&1`, so that `workspace/models/<best>.pkl` is the full training that deployment needs. Add the `model` note at `<C>` with the text of `<best>.py` and `parent=<best>`; there is no `<C>.py`.
3. Same day: the members the session did not change must have the same ensembler-holdout scores in both runs. If they differ, the data changed between the runs: run the reference again.
4. Verdict: the candidate is `keep` if its objective and `sharpe` both at least match the reference's, otherwise `discard`. Its `delta` is its objective minus the reference's, and `sigma` is `-`. The description starts `FULL TRAINING`, names the reference and says the check is at one seed (a change in the ensembler's pick has moved full-training scores by 0.014).
5. Pickle: after a `discard`, delete `workspace/models/<best>.pkl`; after a `keep`, leave it for deployment (until the model is registered, `tournament.cron` submits it to the placeholder, which is harmless). Never delete any other pickle.

## Deployment

The user deploys a model, not the loop: usually the best `keep` at timestamp `<T>`, after the session. They register a Numerai model named `${NUMERAI_MODEL_PREFIX}<T>` first (until then its submissions go to the placeholder) and train it in full (the script has no `FitDownsamplerBySample` wrapper) with `numerai-run --model <T> --retrain`: `numerai-run` trains `<T>.py` on disk, or first writes the note's text to it (left on disk) if it is absent, and fails if there is no note at `<T>` either. Deployment adds no note: the model's name binds it to its note, and the `parent=` chain gives its provenance. Deployed models are never retrained, and their scripts are not committed.

## Sources for Experiment Ideas

When brainstorming for improvements, you may also use web search to find recent advancements (last 6 months) - papers, blog posts, forum posts, etc. (search for e.g. `tabular model architectures [CURRENT YEAR]`). Prioritize Numerai-specific insights - the tournament has unique properties (anonymized features, era-based time series, feature neutralization, obfuscated targets) that make generic ML advice less useful thus you may search for Numerai-specific discussions on the [Numerai forum](https://forum.numer.ai) and in the wider community (search for e.g. `site:forum.numer.ai best models [CURRENT YEAR]`, `numerai winning models [CURRENT YEAR]`, `numerai feature engineering`, `site:forum.numer.ai best targets [CURRENT YEAR]`, `site:forum.numer.ai ensemble strategy [CURRENT YEAR]`, `site:forum.numer.ai neutralization [CURRENT YEAR]`)
