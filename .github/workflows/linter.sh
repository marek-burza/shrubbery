#!/bin/sh

set -e

uv run --extra dev ruff check --select I src
uv run --extra dev ruff format --check --diff
uv run --extra dev ty check
uv run --extra dev deptry . --ignore DEP001,DEP002,DEP003
