#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"${ROOT_DIR}/src/run_analysis.sh"
"${ROOT_DIR}/src/build_paper.sh"
