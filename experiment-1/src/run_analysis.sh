#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export MPLCONFIGDIR="${ROOT_DIR}/tmp/matplotlib"
export XDG_CACHE_HOME="${ROOT_DIR}/tmp/cache"
export MPLBACKEND="Agg"
mkdir -p "${MPLCONFIGDIR}" "${XDG_CACHE_HOME}"

python3 "${ROOT_DIR}/src/analysis.py"
