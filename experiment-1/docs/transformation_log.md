# Transformation and analysis log

This log documents every substantive transformation performed by
`src/analysis.py`. The script uses fixed seeds and fails when structural
assertions are not satisfied.

## 1. Raw inputs

1. Read the Eurostat CSV with `geo`, `OBS_FLAG`, and `CONF_STATUS` preserved as
   strings.
2. Read the five-file GISCO Shapefile layer. The ZIP archive and extracted
   sidecars remain unchanged.
3. Verify the exact URLs, retrieval date, sizes, hashes, and supporting
   metadata listed in `docs/source_manifest.md`.

## 2. Economic-data validation and cleaning

1. Assert the nine expected source columns in their downloaded order.
2. Strip surrounding whitespace from `geo`; preserve case and leading or
   trailing zeroes within identifiers.
3. Assert unique, nonmissing `geo` keys.
4. Assert the constants:
   - `STRUCTURE == dataflow`;
   - `STRUCTURE_ID == ESTAT:NAMA_10R_2GDP(1.0)`;
   - `freq == A`;
   - `unit == PPS_HAB_EU27_2020`;
   - `TIME_PERIOD == 2023`.
5. Parse `OBS_VALUE` numerically with errors set to fail; assert that all
   selected values are present and positive.
6. Copy the value to the descriptive name `gdp_pc_index`.
7. Infer a geographic audit label from the exact keys: country (length 2),
   NUTS 1 (length 3), NUTS 2 (length 4), or `EU27_2020`.
8. Preserve `OBS_FLAG` and `CONF_STATUS`; represent source blanks as empty
   strings in clean tabular outputs.
9. Save all 416 cleaned rows to
   `data/interim/gdp_2023_clean_all_levels.csv`.

No value is imputed, rounded, winsorized, or otherwise altered.

## 3. Geometry validation

1. Assert 299 features and unique `NUTS_ID`.
2. Assert `LEVL_CODE == 2` for every feature.
3. Assert `EPSG:4326`.
4. Assert no missing, empty, or invalid geometry.

The raw source is retained in EPSG:4326. Only the largest-component
nearest-neighbor sensitivity creates an in-memory projected copy in
`EPSG:3035`.

## 4. Inner join and coverage audit

1. Inner-join geometry `NUTS_ID` to economic `geo` with one-to-one validation.
2. Sort deterministically by `NUTS_ID`.
3. Assert 276 joined rows, four-character NUTS 2 keys, unique identifiers,
   nonmissing values, and valid geometry.
4. Save GDP-side and shape-side anti-joins separately.
5. Assert zero unmatched GDP NUTS 2 keys and 23 shape-only features.
6. Derive `is_eu` from `EU_STAT == "T"` and label the remaining joined rows
   `candidate country`.
7. Derive the natural log of the positive index for spatial analysis.
8. Create only a display class for mapping:
   `<50`, `50-74`, `75-99`, `100-124`, `125-149`, and `150+`.

The headline sample retains all 276 rows created by the requested inner join.
An EU27-only result is a prespecified sensitivity, not the primary sample.

## 5. Distributional statistics

Every region receives equal weight. The source selection contains no population
field, so results must not be read as person-weighted inequality.

Computed measures:

- mean, median, sample standard deviation, and coefficient of variation;
- minimum, maximum, quartiles, 10th and 90th percentiles;
- 90/10 percentile ratio;
- Gini coefficient for positive regional index values;
- Theil T, using each value relative to the region-equal mean;
- region shares below 75, at or above 100, and at or above 125;
- between-country share of total log-index sum of squares.

The last measure is descriptive variance accounting. It is not a causal
country effect.

## 6. Contiguity graphs

1. Query exact polygon touches from the saved generalized geometry.
2. Queen contiguity retains shared edge or point contacts.
3. Rook contiguity retains only contacts with positive shared-boundary length.
4. Set diagonal elements to zero and make the binary graph symmetric.
5. Save each undirected edge once.
6. Row-standardize weights only after defining the inferential sample.

Queen graph diagnostics:

- 276 nodes;
- 590 undirected edges;
- 21 zero-neighbor regions;
- 25 connected components;
- component sizes 238, 12, 3, 2, and 21 singletons;
- median degree 5, mean degree 4.28, maximum degree 11.

The 21 zero-neighbor regions remain in descriptive results and maps. They are
marked "No contiguity neighbor" and are not assigned an arbitrary neighbor for
the primary statistic.

## 7. Global Moran analysis

1. Remove only the 21 queen zero-neighbor regions, yielding 255 regions.
2. Re-center log GDP per capita in that exact sample.
3. Row-standardize the induced queen graph.
4. Compute
   `I = (n / S0) * (z' W z) / (z' z)`.
5. Generate 99,999 random-label permutations with seed `20260723`.
6. Compute the prespecified one-sided greater pseudo p-value with a +1
   numerator and denominator correction.
7. Also save a two-sided permutation value centered on the simulated mean.

The random-label null tests spatial arrangement over a fixed graph. It is not
a sampling-error test for Eurostat estimates and has no causal interpretation.

## 8. Local Moran analysis

1. Standardize log GDP with population standard deviation within the same 255
   regions that have at least one contiguity neighbor.
2. Compute each region's row-standardized spatial lag and local product.
3. With seed `20260724`, create 99,999 random orderings.
4. For every focal region, hold its standardized value fixed and draw exactly
   its observed number of neighbor values without replacement from the other
   254 regions.
5. Form a two-sided pseudo p-value around that region's conditional permutation
   mean, with the +1 correction.
6. Assign the HH, LL, HL, or LH quadrant from the signs of the focal value and
   spatial lag.
7. Apply Benjamini-Hochberg adjustment across all 255 local tests; the main map
   uses `q <= 0.05`. Because overlapping LISA tests are spatially dependent,
   this is described as BH-adjusted rather than as a guaranteed false-discovery
   rate under arbitrary dependence.
8. Apply Holm family-wise-error adjustment as a stricter robustness check.

Quadrant labels are attached only to multiplicity-adjusted survivors. "High"
and "low" mean relative to the inferential sample center, not necessarily above
or below the EU benchmark of 100.

## 9. Prespecified spatial sensitivities

Each global sensitivity uses 99,999 one-sided random-label permutations and its
own recorded seed:

- raw index with queen contiguity;
- rank-normalized index with queen contiguity;
- log index with rook contiguity;
- EU27-only log index with queen contiguity;
- log index on the largest queen-connected component;
- log index on a symmetric 5-nearest-neighbor graph for that component.

Nearest-neighbor centroids are calculated after projection to EPSG:3035. The
graph is restricted to the 238-region largest component to avoid
trans-continental links to outermost regions. The maximum retained centroid
link is 625.3 km.

## 10. Outputs and quality checks

- Save nonspatial processed values and all local-inference fields as CSV.
- Save the same fields with geometry as a GeoPackage.
- Save graph edge lists, QA checks, descriptive tables, sensitivity estimates,
  country summaries, extreme-region lists, and generated LaTeX fragments.
- Save all figures as 300-dpi PNG and vector PDF.
- Save a machine-readable result and software manifest in
  `docs/analysis_summary.json`.
- Compile the paper with XeLaTeX and BibTeX.
- Render every final PDF page to PNG and inspect for clipping, overlap, broken
  glyphs, unresolved citations, bad page breaks, or unreadable tables.

All seven automated data-quality checks in
`tables/data_quality_checks.csv` pass.
