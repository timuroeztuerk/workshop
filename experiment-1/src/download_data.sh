#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GDP_DIR="${ROOT_DIR}/data/raw/eurostat"
GISCO_DIR="${ROOT_DIR}/data/raw/gisco"
DOCS_DIR="${ROOT_DIR}/docs/source_metadata"

mkdir -p "${GDP_DIR}" "${GISCO_DIR}" "${DOCS_DIR}"

GDP_URL='https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/data/dataflow/ESTAT/nama_10r_2gdp/1.0?c%5Bunit%5D=PPS_HAB_EU27_2020&c%5BTIME_PERIOD%5D=2023&format=csvdata&formatVersion=2.0&compress=false'
SHP_URL='https://gisco-services.ec.europa.eu/distribution/v2/nuts/shp/NUTS_RG_20M_2024_4326_LEVL_2.shp.zip'
DATAFLOW_URL='https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/structure/dataflow/ESTAT/nama_10r_2gdp/1.0?references=descendants&detail=referencepartial&compress=false'
GISCO_MANIFEST_URL='https://gisco-services.ec.europa.eu/distribution/v2/nuts/nuts-2024-files.json'
GISCO_RELEASE_URL='https://gisco-services.ec.europa.eu/distribution/v2/nuts/nuts-2024-release-notes.txt'

curl -L --fail --retry 3 "${GDP_URL}" \
  -o "${GDP_DIR}/nama_10r_2gdp_PPS_HAB_EU27_2020_2023.csv"
curl -L --fail --retry 3 "${SHP_URL}" \
  -o "${GISCO_DIR}/NUTS_RG_20M_2024_4326_LEVL_2.shp.zip"
curl -L --fail --retry 3 "${DATAFLOW_URL}" \
  -o "${DOCS_DIR}/nama_10r_2gdp_dataflow.xml"
curl -L --fail --retry 3 "${GISCO_MANIFEST_URL}" \
  -o "${DOCS_DIR}/nuts-2024-files.json"
curl -L --fail --retry 3 "${GISCO_RELEASE_URL}" \
  -o "${DOCS_DIR}/nuts-2024-release-notes.txt"

unzip -o "${GISCO_DIR}/NUTS_RG_20M_2024_4326_LEVL_2.shp.zip" -d "${GISCO_DIR}"

shasum -a 256 \
  "${GDP_DIR}/nama_10r_2gdp_PPS_HAB_EU27_2020_2023.csv" \
  "${GISCO_DIR}/NUTS_RG_20M_2024_4326_LEVL_2.shp.zip"
