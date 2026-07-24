# The Economic Geography of Europe

This folder is a complete, reproducible study of 2023 regional GDP-per-capita
disparities and spatial clustering across NUTS 2 regions with available
Eurostat data.

## Main deliverable

- Finished paper:
  `output/pdf/economic_geography_europe_2023.pdf`
- Paper source: `paper/paper.tex`
- Machine-readable result summary: `docs/analysis_summary.json`

## Research question and headline results

**Question:** How strongly, and where, was 2023 GDP per capita spatially
clustered among neighboring NUTS 2 regions with available Eurostat data?

The one-to-one inner join yields 276 regions: 244 EU27 regions and 32 regions
in Montenegro, North Macedonia, Serbia, and Türkiye. Across equally weighted
regions, the GDP-per-capita index has a median of 84, Gini coefficient of
0.219, and 90/10 ratio of 2.62. The primary log-index Moran statistic is 0.600
among 255 regions with a contiguity neighbor (`p = 0.00001`, 99,999 random-label
permutations). The EU27-only estimate is 0.503. Benjamini-Hochberg adjustment
retains 4 high-high, 16 low-low, and 1 high-low local cluster cores; 9 local
results survive the stricter Holm adjustment.

These are descriptive associations. The design does not identify causal
spillovers, agglomeration effects, policy impacts, convergence, or welfare.

## Reproduce the archived results

From `experiment-1/`:

```bash
./src/run_all.sh
```

Or run the two stages separately:

```bash
./src/run_analysis.sh
./src/build_paper.sh
```

The archived raw files reproduce the reported vintage. To refresh the official
sources instead, first copy `data/raw/` and `docs/source_metadata/` to a
separate vintage directory, then run:

```bash
./src/download_data.sh
```

The download script overwrites the archived raw and metadata files in place.
Refreshing can change results because Eurostat and GISCO update their hosted
files. Re-run the analysis, record the new hashes, and retain the original
snapshot separately if exact reproduction of this paper is required.

## Requirements

- Python 3.12 (the archived run used 3.12.3).
- Python packages listed in `requirements.txt`.
- XeLaTeX, BibTeX, and the Georgia and Helvetica fonts for the paper build.
- Poppler (`pdfinfo` and `pdftoppm`) for final visual QA.
- `curl`, `unzip`, and `shasum` for refreshing sources.

The spatial statistics are implemented directly from their documented formulas;
the project does not require PySAL.

## Folder structure

```text
experiment-1/
├── data/
│   ├── raw/          # archived source snapshots (refresh script overwrites)
│   ├── interim/      # clean all-level data, join audits, edge lists
│   └── processed/    # analysis-ready CSV and GeoPackage
├── docs/             # source manifest, transformation log, result JSON
├── figures/          # publication PNG and vector PDF figures
├── output/pdf/       # finished academic paper
├── paper/            # LaTeX paper source and build files
├── references/       # verified BibTeX library
├── src/              # download, analysis, and paper-build code
├── tables/           # CSV results and generated LaTeX tables
├── tmp/              # rendering and font caches used for QA
├── instructions.md
└── requirements.txt
```

## Method summary

- Economic measure: `PPS_HAB_EU27_2020`, 2023, from Eurostat dataset
  `nama_10r_2gdp`.
- Geometry: GISCO NUTS 2024 level 2, 1:20 million, EPSG:4326.
- Join: exact inner one-to-one match of CSV `geo` to shape `NUTS_ID`.
- Distribution: region-equal statistics; no population weighting.
- Primary spatial outcome: natural log of the positive GDP index.
- Primary weights: row-standardized first-order queen contiguity.
- Islands: retained descriptively; excluded from contiguity inference and
  labeled explicitly.
- Global inference: 99,999 one-sided random-label permutations.
- Local inference: 99,999 conditional two-sided randomizations,
  Benjamini-Hochberg adjustment at `q = 0.05`, with Holm as a
  dependence-robust stricter check.
- Sensitivities: raw and rank-normal outcomes, rook weights, EU27-only sample,
  largest component, and projected symmetric 5-nearest-neighbor weights.

See `docs/transformation_log.md` for every transformation and
`docs/source_manifest.md` for verified source metadata and hashes.
