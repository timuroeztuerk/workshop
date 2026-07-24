#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAPER_DIR="${ROOT_DIR}/paper"
OUTPUT_DIR="${ROOT_DIR}/output/pdf"

export XDG_CACHE_HOME="${ROOT_DIR}/tmp/cache"
mkdir -p "${OUTPUT_DIR}" "${XDG_CACHE_HOME}"
cd "${PAPER_DIR}"

xelatex -interaction=nonstopmode -halt-on-error paper.tex
bibtex paper
xelatex -interaction=nonstopmode -halt-on-error paper.tex
xelatex -interaction=nonstopmode -halt-on-error paper.tex

cp paper.pdf "${OUTPUT_DIR}/economic_geography_europe_2023.pdf"
