# Shrubbery

Shrubbery is a repo where I experiment with learning about financial markets and Numerai and how to apply machine learning and AI agents to these topics. GPU-accelerated models are used here also in the context of expanding knowledge/skills related to AI/ML engineering.

[Numerai](https://numer.ai/) is a hedge fund where stock market trades are determined based on predictions crowdsourced from data scientists given anonymized financial data.

## Living Document

This file provides guidance to the user and coding agent when working with code in this repository.

As project priorities shift, this file is meant to be updated to reflect current goals, constraints, and conventions. Outdated instructions are worse than none - keep them accurate.

## Build & Development Commands

- **Package manager**: `uv` (dependencies in `pyproject.toml`, lockfile in `uv.lock`)
- **Sandboxing**: `podman`

**Running Numerai Models**:

Numerai models are executed by the user in a Docker container via shrubbery's `run.sh`:

```bash
# Run model inference
run.sh -c "numerai-run --model <model>"

# Run model training
run.sh -c "numerai-run --model <model> --retrain"
```

Numerai models are executed by the coding agent already inside a container directly via:

```bash
# Run model inference
numerai-run --model <model>

# Run model training
numerai-run --model <model> --retrain
```

All models also run automatically via cron (see `tournament.cron`) Tuesday-Saturday at 15:30. The cron job runs every `workspace/models/*.pkl` file in the repo.

**Linting**:
```bash
/bin/sh .github/workflows/linter.sh
```

### Numerai Workspace

The `workspace/` directory (git-ignored) contains:
- `data/` - cached Numerai parquet files
- `models/` - serialized trained models
- `logs/` - training and inference logs, written by `numerai-run` itself

## Architecture

### Numerai Pipeline (`src/shrubbery/numerai/`)

**Entry point**: `main.py` - `numerai-run --model <timestamp>` takes the 14 digits (`YYYYmmddHHMMSS`) of a model's timestamp, the timestamp of its `model` note in the `shrubbery-notes` store `data/numerai.data` of the current directory. The model name is `NUMERAI_MODEL_PREFIX` followed by those digits, and `NumeraiRunner` names its files after the bare digits: the script `<timestamp>.py` in the current directory and the artifact `workspace/models/<timestamp>.pkl` (so that inference can pass the artifact's basename as `--model`). With `--retrain` it uses the script on disk, or first writes the note's text to it (left on disk) when it is absent, failing if there is no such note either. It then loads `ESTIMATOR` from the script, resolves the feature and target names, fits, and stores it as an artifact. Without `--retrain` it loads the artifact and never reads the script. Either way it then submits tournament predictions and validation diagnostics per `--diagnose`: `hosted` (default) uploads them to Numerai, `local` computes the documented subset of the hosted metrics and logs them under the hosted keys, leaving out the validation dates within `--diagnose-embargo` business days of the last date in `train.parquet` (default 0, like the hosted diagnostics; 60 for 60-day targets), `none` skips them. Submissions go to the Numerai model of that name if the account has one, otherwise to `NUMERAI_MODEL_PLACEHOLDER` (e.g. for experiments, or before the model is registered).

**Model wrapper**: `model.py` - `NumeraiModel` binds an estimator to its feature and target names and exposes the `__call__(live_features, live_benchmark_models)` signature of Numerai's model upload. `fit` and `predict` leave out `feature_country`, and `unpack_numerai_features` decodes the int8 features and prepends the era (the `date` column) as the first column, as the number of weeks since the Unix epoch. In v6.0 the data has no index (`numerai_ticker` and `date` are ordinary columns), so `predict` returns a single `prediction` column on the input's `RangeIndex`, and the runner joins `numerai_ticker` and `date` back on (`NumeraiRunner.predict_with_ids`). The IDs are attached outside the artifact because it carries `NumeraiModel` by value, so a change to `predict` reaches only newly trained artifacts.

**Data layer**: `ingest.py` downloads/caches the Numerai datasets and reads feature sets and training targets. `augmentation.py` finds the riskiest features (largest change in target correlation between the first and second half of the eras).

**Numerai API**: `napi.py` - shared `NumerAPI` client, model id resolution, saving of predictions to CSV in the shape of Numerai's v6.0 example notebook `hello_numerai.ipynb` (live: `numerai_ticker,prediction`, diagnostics: `numerai_ticker,date,prediction`), which raises on duplicate IDs or a `prediction` that is NaN or outside `[0, 1]`, and upload of tournament and diagnostic predictions with retries and back-off.

**Persistence**: `utilities.py` stores and loads the `NumeraiModel` with cloudpickle, registering every loaded `shrubbery.*` module for by-value pickling so the artifact carries its code rather than import paths, and refuses to load anything that is not a `NumeraiModel`.

**Support**: `constants.py` (column names, random seed), `observability.py` (logger, warning filters, and for `numerai-run` the logging to both the console and a dated `workspace/logs/<YYYYmmddHHMMSS>.log`, with stdout logged at `INFO` and stderr (incl. warnings) at `WARNING` via `LoggerWriter`), `scores.py` (the `numerai-scores` tool, see Tools).

**Models**: The models (`scikit-learn`-compatible regressors) evolve frequently - ensemble models (e.g. `LightGBM`, `XGBoost`, `Random Forest`, `ResNet`, `FNN`, `Wide & Deep`) get added/removed and are subject to hyperparameter tuning, embedder strategies change (e.g. concatenation of embeddings to features), feature exposure neutralization, shared configuration drifts. 

### Financial Experiments (`src/shrubbery/financial/`)

- `market_neutral.py`: removes the S&P 500 correlated component from a series and tests the remaining trend (`uv run python -m shrubbery.financial.market_neutral --help`)
- `trader.py`: standalone uv script for VaR, beta and CAPM analysis of an asset against a market index via yfinance
- `semantics.py`: the `financial-semantics` tool, see Tools

### Key Design Patterns

- Model scripts define a module-level `ESTIMATOR` following **scikit-learn's estimator interface** (`fit`/`predict`); the harness owns data, training and submission
- **The estimator owns the prediction range.** Numerai validates an upload as: exactly a `pd.DataFrame`, non-empty, no NaN anywhere, and every value of the first column within `[0, 1]` inclusive, with the column named `prediction` on the index of the input. `NumeraiModel` guarantees the type, the single `prediction` column and the index; the range and the absence of NaN come from the estimator alone. Nothing downstream re-ranks or clips, so an `ESTIMATOR` that does not end in a per-era `rank(pct=True)` produces an artifact Numerai rejects, and the rejection happens on upload rather than locally
- Processing is **era-aware**: the era reaches the estimator as the first feature column, so it can split, evaluate and neutralize per era
- **GPU-first**: NVIDIA CUDA acceleration via cuML, XGBoost GPU, PyTorch

## Tools

- `numerai-scores` (`src/shrubbery/numerai/scores.py`) - fetches live tournament scores (CORR20v2, MMC, BMC, CORR60, MMC60, ... with percentiles) of own or public models from the Numerai API for performance evaluation; JSON records on stdout by default (CSV and table optional), with filtering and per-model summary options. Run `uv run numerai-scores --help` for metric definitions, payout history, interpretation caveats and examples.
- `shrubbery-notes` (`src/shrubbery/notes.py`) - agent memory, used through the `note` skill: notes in a single table SQLite store, `lzma` compressed and encrypted with PyNaCl's `SecretBox` under `SHRUBBERY_KEY`, kept in `data/notes.data` (gitignored). `list [TYPE]` prints `timestamp type summary` per note, only those of `TYPE` if given, `show TIMESTAMP` prints the text of one note verbatim and nothing else, `add [--timestamp TIMESTAMP] TYPE SUMMARY` reads the text from stdin, stores it verbatim and prints its timestamp (now by default), `delete TIMESTAMP` removes a note. Timestamps are UTC in whole seconds as digits, `YYYYmmddHHMMSS` (e.g. `20261009114703`), stored, printed and accepted in that one form. `--store PATH` before the command (e.g. `shrubbery-notes --store /tmp/notes.data list`) selects another store; the lock file sits next to it with a `.lock` suffix. The database is decrypted in memory only, writes are atomic and serialized with a lock on `data/notes.lock`. Notes are listed on request only; eventually a `SessionStart` hook running `uv run shrubbery-notes list` may be added and auto memory disabled with `"autoMemoryEnabled": false` in `.claude/settings.json`, neither is applied yet. Table `notes`:

  | Column | Type | Content |
  |---|---|---|
  | `timestamp` | `TEXT PRIMARY KEY` | UTC datetime in whole seconds as digits, `YYYYmmddHHMMSS`, e.g. `20261009114703`; unique |
  | `type` | `TEXT` | single lowercase word, e.g. `numerai`, `financial` |
  | `summary` | `TEXT` | one line |
  | `text` | `TEXT` | Markdown body |

- `financial-semantics` (`src/shrubbery/financial/semantics.py`) - looks up financial vocabulary, identifier schemes and definitions from third-party sources (FIBO incl. its ACTUS module, FIX Orchestra, ISO 10383 MIC and ISO 4217 code lists, EuroVoc, QuantLib-Python-Docs, skfolio, quantstats) and resolves identifiers against FIRDS, GLEIF and OpenFIGI, used through the `financial-semantics` skill. `sources` lists every source with version and licence, `schemes` lists the identifier schemes discovered in FIBO (plus a `builtin` vendor-symbol scheme) and whether each is resolvable, `identify VALUE` infers the scheme of a bare string offline from its syntax, check digit or code list, `resolve VALUE [--to SCHEME]` asks a registry what the identifier denotes, `term LABEL` returns definitions with their source, version and IRI. Sources are fetched lazily and cached in `data/semantics.db` (gitignored), registry answers for 30 days; `--refresh SOURCE` (or `all`) before the command redownloads and reindexes. `--json` on every command. Run `uv run financial-semantics --help` for the full surface. Caution: Notable gap is no Open Risk Manual, terms covered by it are best looked up by the agent directly online.

## Libraries

- Financial market experiments can use the `QuantLib`, `skfolio` & `quantstats` to not reinvent the code from scratch.

## MCP

- [Numerai MCP](https://docs.numer.ai/numerai-tournament/api#numerai-mcp)

## Environment Variables (`.env`)

To run the code create `.env` script which sets the necessary environment variables:

- `NUMERAI_PUBLIC_ID` & `NUMERAI_SECRET_KEY` - Numerai API credentials
- `NUMERAI_MODEL_PREFIX` - prefix of the model names `numerai-run` derives from note timestamps
- `NUMERAI_MODEL_PLACEHOLDER` - Numerai model that receives the submissions of a model not registered on the account
- `SHRUBBERY_KEY` - key of the `shrubbery-notes` store, created with `openssl rand -base64 32`; back it up separately from `data/` (e.g. in a password manager), it cannot be regenerated and without it the notes are lost
- `OPENFIGI_API_KEY` - optional, raises the OpenFIGI rate limit of `financial-semantics resolve`

## CI/CD

GitHub Actions (`.github/workflows/ci.yaml`): On every push, it runs linting, builds and pushes a Docker container image to GHCR (`ghcr.io/{owner}/shrubbery`), and prunes old images (keeps latest 10).

## Profiling

Instructions in this section are meant for manual use by the user.

Profiling Compute:

```shell
# From: https://developer.nvidia.com/nsight-systems/get-started
curl -fsSL https://developer.nvidia.com/downloads/assets/tools/secure/nsight-systems/2026_2/NsightSystems-linux-cli-public-2026.2.1.210-3763964.deb -o NsightSystems-linux-cli-public-2026.2.1.210-3763964.deb
sudo dpkg -i NsightSystems-linux-cli-public-2026.2.1.210-3763964.deb
nsys profile -o trace --trace=cuda,nvtx,osrt numerai-run --model <model> --retrain
nsys export --type=perfetto --output=trace.pftrace trace.nsys-rep
curl -fsSL https://raw.githubusercontent.com/chenyu-jiang/nsys2json/main/nsys2json.py -o nsys2json.py
python3 nsys2json.py -f trace.sqlite -o trace.json
# Upload to: https://ui.perfetto.dev/
```

Profiling Memory:

```shell
uv run --with memray python -m memray run -o output.bin -m shrubbery.numerai.main --model <model> --retrain
uv run --with memray python -m memray flamegraph output.bin
```

## Other

- [Gloomberb - Open-source finance terminal](https://github.com/gloom-sh/gloomberb)
- [Toast 1 - specialized search agent for financial analysis](https://www.mixedbread.com/blog/toast-1)

## Useful Commands (intended for human operator)

Browsing numerai logs:

```shell
less +G $(find workspace/logs/ -name '*log' | sort | fzf --tac --preview 'cat {} | grep Name\: ; cat {} | grep Ensemble\: ; tail -n 36 {}')
```

Browsing notes:

```shell
shrubbery-notes list | fzf --preview 'shrubbery-notes show {1}' --preview-window right:60%:wrap
```
