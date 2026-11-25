# Numerai scoring facts and attribution pitfalls

Living reference for the `numerai-evaluation` skill. **Every fact below carries the date it was
last verified. Re-verify against the sources in step 1 of the skill before relying on it, and update
this file (with the new date) when something changed.**

## Scoring and payout (verified 2026-11-12)

| From | Main target (behind CORR / MMC) | Payout formula | Source |
|---|---|---|---|
| 2024-01-02 | Cyrus-20 (`target_cyrus_20`) | 0.5·CORR20v2 + 2·MMC | forum / blog |
| 2026-01-01 | Ender-20 (`target_ender_20`), data v5.2 "Faith II" | 0.75·CORR20v2 + 2.25·MMC | forum "New Target for Payouts and Data V5.2 - Faith II", blog "Numerai Monthly … 2026 Payout Updates" |
| round 1343 (2026-08-28) | Ender-60 (`target_ender_60`) for CORR, MMC **and BMC** | 3·CORR60 + 15·MMC60 | docs scoring page ("Ender-60 scoring cutover at round 1343"); payout multipliers from the API |
| round 1393 (2026-11-06), data v6 "Unity" | Jupiter-60 (`target_jupiter_60`), all scores neutralized against Numerai's neutralizer matrix | 8·NCORR60 + 32·NMMC60 (`neutral_corr` ×8, `neutral_mmc` ×32, 60 days; `neutral_bmc` scored, not paid), universe GIANT_UNIVERSE_V2 | API `roundScoreConfigs` (round 1396, checked 2026-11-12); forum "The Unity Data Release" (2026-10-15); docs scoring page |
| announced for 2027-01-01 | Jupiter-60; Classic and Signals merge into one Numerai Meta Model | NBMC replaces NCORR; multipliers "announced soon" | forum "The Tournament Roadmap" (2026-11-06) |

- Sources to check: `https://docs.numer.ai/numerai-tournament/scoring` (most current),
  `https://docs.numer.ai/numerai-tournament/data` (what `target` aliases),
  `https://forum.numer.ai` announcements, `https://blog.numer.ai` (Numerai Monthly).
  `https://docs.numer.ai/numerai-tournament/scoring/definitions` was **stale** on 2026-10-04 (still
  named `target_cyrus_20` / `target_jerome_60`) — never trust it alone.
- `numerai-scores --help` also carries a payout history; it is code, so it can lag announcements
  (on 2026-11-12 it still ended at Ender-60).
- The docs pages on BMC (Ender-60, stake-weighted benchmarks), `/scoring/definitions` and the
  v5.3 diagnostics section were stale on 2026-11-11; `/numerai-tournament/diagnostics` returns 404.

## Metrics (verified 2026-11-12)

| Metric | Horizon (final at day) | Role |
|---|---|---|
| `neutral_corr` (NCORR), `neutral_mmc` (NMMC) | 60 | Paid from round 1393: correlation with / contribution to the Meta Model on Jupiter-60, after neutralization |
| `neutral_bmc` (NBMC) | 60 | From round 1393: contribution against the benchmark after neutralization; attribution metric, not paid until it replaces NCORR (2027) |
| `canon_neutral_*` | 60 | Companion series, not paid |
| `v2_corr20` (CORR20v2), `mmc` | 20 | Paid until round 1342; not scored for rounds from 1393 |
| `corr60`, `mmc60` | 60 | Paid for rounds 1343–1392 |
| `bmc` | **60** | Until round 1392: contribution after neutralizing to stake-weighted benchmark models; best single gauge of unique, regime-robust signal; not paid |
| `fnc_v3`, `cort20` (teager), `corj60` (jerome), `season_score` | 20 / 60 | Auxiliary |
| `corr_w_meta_model` | daily | Uniqueness (low = orthogonal to the crowd) |
| `apcwnm` / `mcwnm` | — | Average / max correlation with other submissions |

- The `neutral_*` names are the `displayName`s of the rounds' `roundScoreConfigs`. On 2026-11-12 no
  round from 1393 on had scores yet (latest scored round 1392), so `numerai-scores -m neutral_corr`
  returned nothing — confirm the names once the first scores appear.
- 60-day metrics (incl. BMC) are final only ~84 calendar days after the round. For changes younger
  than that, BMC is partial: use it with an explicit caveat and lean on final 20-day metrics (rounds
  up to 1392 only; from round 1393 every score is 60-day, so recent changes have only partial scores).
- Percentiles rank against all submissions and swing with the crowd. For a heavily neutralized
  family they were anti-correlated (−0.4…−0.6) with the example model's percentile while raw corr was
  uncorrelated — percentile moves were regime artefacts. Attribute on values.

## `target` alias per data version (verified on the files 2026-10-04)

| Data | `target` is identical to |
|---|---|
| v5.0 | `target_cyrusd_20` |
| v5.2 | `target_ender_20` |
| v5.3 | `target_ender_60` |
| v6.0 | `target_jupiter_60` (5 bins; verified 2026-11-11) |

A data-version bump silently changes what anything trained on `target` (or on target index 0, since
the target list is sorted) learns — effective at the next retrain. Verify the alias for any new
version: correlation 1.0 / identical values between `target` and one named target.

## Regime references (verified 2026-11-12)

- `integration_test` — Numerai's example model: feature-exposed, tracks the "feature-momentum" regime.
- `v6_lgbm_jupiter60` — the benchmark trained on the current payout target (column `lgbm_jupiter_60`
  in `*_benchmark_models.parquet`). The name changes with data version and target: `v53_lgbm_ender60`
  and `v52_lgbm_ender60` cover earlier eras — look up the current one.

## Validation diagnostics (verified 2026-11-11)

- Hosted v6 diagnostics (`numerai-run --diagnose hosted`) return `validationCorrV4*`,
  `validationRic*`, `validationIcV2*`, `validationBmcMean` and `erasAcceptedCount`;
  `validationCorrMean` is gone. They apply **no embargo**: train ends 2018-12-28, and the first
  ~12 weekly validation dates leak (per-date CorrV4 ≈ 0.5 on 2019-01-04). They also score recent
  dates on returns Numerai does not publish, and are 4–9× noisier per date than local scores, so
  they cannot be reproduced locally.
- `numerai-run --diagnose local --diagnose-embargo 60` (shrubbery `numerai/diagnostics.py`) computes
  `validationCorrV4*` as NCORR and `validationBmcMean` as NBMC against `lgbm_jupiter_60` with
  `numerai-tools`, on dates with published targets more than 60 business days after the last `train.parquet` date
  (from 2019-03-29 with the current data). This is the `numerai-autoresearch`
  metric `8·ncorr + 32·nbmc`. NMMC cannot be computed locally because no Meta Model is published.

## Noise (measured 2026-10-04 on the family)

- Rounds are daily but scoring windows overlap: ~28 calendar days ≈ one independent 20-day
  observation, ~84 days ≈ one 60-day observation.
- Std of 28-day block means of `v2_corr20` ≈ 0.008; of 84-day block means of `bmc` ≈ 0.005.
  With ±42-day windows almost no single event reached |z| ≥ 2 — expect most attributions to be
  "suggestive" at best, and say so.

## Mechanics that decide when a change can show up

- **Config changes take effect only at the next retrain** (cron runs inference only), i.e. from the
  first round whose staking closes after the retrain: the end of the training run in `workspace/logs/`, else
  the model's first scored round.
- **Shared-library (shrubbery) inference-path changes take effect immediately for all models**
  without any new model (cron pulls the latest image). They can also break unpickling of old models,
  which shows up as missed rounds. Family-wide swings without a new model may have this cause.
- numerapi re-downloads a data file when its size differs from the server's (not by content) — a new
  data version arrives on the next run, retrain or not.

## Method pitfalls seen before (2026-10)

- Co-timed changes cannot be separated — say "confounded" rather than picking one.
- A retrain with an effectively unchanged config is a natural control: a performance swing right
  after it points to regime (e.g. `neutralization_cap` 50 → None was a no-op with 42 features;
  `learning_schedule` defaults to `None`).
- Library defaults vs config: check whether a new option is actually enabled in each config at the
  time of the retrain (e.g. `refit` in `CombinatorialEnsembler` defaults to `False`).
- Ranks in Numerai's reports list follow MMC-20; they agree only weakly (≈0.4 rank corr) with BMC and
  with the 60-day payout metrics.
