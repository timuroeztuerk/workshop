# AGENTS.md

<!--
Sample AGENTS.md for an empirical economics project.
Works with Codex, Claude Code (also reads CLAUDE.md), Cursor, Gemini CLI, Aider, etc.
Keep it short (< ~200 lines) — every line is read on each turn and costs context budget.
Standard reference: https://agents.md/
-->

## Project overview

Panel-data study of firm-level investment. Cleans raw administrative data,
builds a balanced panel, and estimates fixed-effects and IV specifications.
Primary language: R (tidyverse + fixest). Some legacy cleaning in Stata.

## Repository layout

- `data/raw/`         Source files. **Read-only — never edit or overwrite.**
- `data/confidential/` Licensed microdata. **Do not read, copy, or send anywhere.**
- `data/clean/`       Generated panels. Safe to rebuild.
- `code/clean/`       Data-cleaning scripts.
- `code/estimation/`  Regression and IV code.
- `output/`           Tables and figures (regenerated, not hand-edited).
- `paper/`            LaTeX manuscript.

## Setup commands

- Install R deps: `Rscript -e 'renv::restore()'`
- Rebuild clean data: `make data`
- Run all estimation: `make estimate`
- Build paper: `make paper`

## How to run tests / checks

- Reproducibility check: `make clean && make all` must run end-to-end with no manual steps.
- Lint R code: `Rscript -e 'lintr::lint_dir("code")'`
- Confirm no confidential paths appear in committed output before finishing.

## Conventions

- Always cluster standard errors at the firm level.
- Set seeds explicitly (`set.seed(42)`) for any simulation or bootstrap.
- Never hard-code file paths; use the `here::here()` helper.
- Tables in LaTeX via `modelsummary`; do not paste numbers by hand.
- One script = one output; keep steps reproducible and idempotent.

## Data security (important)

- Confidential microdata must stay in `data/confidential/` and never leave the machine.
- Do not include raw data values, IDs, or sample rows in code comments or commit messages.
- If a task would require reading confidential data, stop and ask first.

## Commit / PR guidance

- Commit message format: `[clean] ...`, `[estimate] ...`, `[paper] ...`
- Run `make all` and the linter before committing.
- Update or add checks for any code you change.
