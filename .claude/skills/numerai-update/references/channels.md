# Where Numerai and numerapi announce changes

Researched 2026-10-04. Re-check when a source stops working or a change is found through a channel
not listed here — then update this file.

## Numerai tournament and data

| Channel | Access | What it carried (examples) |
|---|---|---|
| **Tournament API** (`numerapi.list_rounds()` → `target`, `roundScoreConfigs` with `isPayout`, `defaultMultiplier`, `totalScoreDays`) | public, programmatic | Ground truth of the main target and payout formula per round: `v2_corr20` paid from round 484 (2023-05-13); 0.5·CORR + 2·MMC from round 650 (2024-01-02); Ender-20 with 0.75/2.25 from round 1172 (2026-01-01); Ender-60 with 3·CORR60 + 15·MMC60 from round 1343 (2026-08-28); Jupiter-60 with 8·`neutral_corr` + 32·`neutral_mmc` from round 1393 (2026-11-06). Also exposed by the GraphQL field `Round.roundScoreConfigs` and Numerai's MCP server (`https://api-tournament.numer.ai/mcp`). |
| **Dataset listing** (`numerapi.list_datasets()`) | public, programmatic | New data versions appear here on release day (v5.3 on 2026-07-15, v6.0 on 2026-10-15, which also added `*_neutralizer.parquet`). Benchmark model names are the columns of `<version>/live_benchmark_models.parquet` (e.g. `v53_lgbm_ender20`, `v53_lgbm_ender60`; v6.0 has only `lgbm_jupiter_60`, public model `v6_lgbm_jupiter60`). |
| **Forum, Announcements category** (`https://forum.numer.ai/c/announcements/8`, JSON: append `.json`; RSS: `.rss`) | public | Official posts by Numerai staff (ark, master_key, slyfox, pschork): data releases ("The Unity Data Release" 2026-10-15: data v6, Jupiter-60, neutral payouts; "The Tournament Roadmap" 2026-11-06: NBMC replaces NCORR from 2027-01-01, one Meta Model with Signals; "Numerai v5.3 'Quantum' Data Release" 2026-07-15, "New Target for Payouts and Data V5.2 - Faith II" 2025-12-15, "Data V5.1 Release - Faith" 2025-10-31), new scores ("Numerai 60D Scores" 2025-05-05), new primary targets ("Target Cyrus - New Primary Target" 2023-04-17), staking changes. Important details often follow in staff **replies** (e.g. v5.2 support timeline). |
| **Forum search** (`https://forum.numer.ai/search.json?q=<terms>%20after:<YYYY-MM-DD>`) | public | Staff answers in other categories clarify cutovers (e.g. "Payout anomaly on recent rounds", Tournament category, 2026-09: the 20D → 60D transition and staking migration). |
| **Blog** (`https://blog.numer.ai/rss/`, "Numerai Monthly" posts, also mailed as a newsletter) | public | The **Ender-60 payout switch for rounds from 2026-08-28 was announced only here** (Numerai Monthly, 2026-08-04) and in the docs — not in the forum Announcements category. Also payout-multiplier updates (2026-01 issue). |
| **Docs** (`https://docs.numer.ai/numerai-tournament/scoring`, `/data`, `/api`) | public, no changelog | Current-state descriptions: "Ender-60 scoring cutover at round 1343", `target` alias of the latest data version. Pages are updated in place without dates; `/scoring/definitions` was stale on 2026-10-04. |
| X/Twitter `@numerai`, office hours (YouTube) | need an account / not machine-readable | Mirrors of the above; cannot be checked by the skill — ask the user whether they saw anything there. |

## numerapi Python package

| Channel | Access | Notes |
|---|---|---|
| **PyPI JSON** (`https://pypi.org/pypi/numerapi/json`) | public | Versions with upload dates (2.24.0 on 2026-08-05, 3.1.1 on 2026-08-12). |
| **CHANGELOG.md** (`https://raw.githubusercontent.com/numerai/numerapi/master/CHANGELOG.md`; repo `github.com/numerai/numerapi`) | public | Release notes incl. deprecations and removals (2.24.0: `roundScoreConfigs` added, old multiplier fields deprecated; 3.1.1: removed six deprecated Corr/MMC multiplier projections from `list_rounds`, `round_model_performances_v2` multiplier fields replaced by `payoutMultipliers`). The repo has **no GitHub releases** — use the changelog. |
| Runtime warnings | local | `DeprecationWarning`s emitted by numerapi in run logs (e.g. `round_model_performances_v2` is deprecated → use `submission_scores`). |
