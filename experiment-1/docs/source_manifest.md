# Source manifest

Retrieval date: 23 July 2026.

The raw files below are archived without modification. The direct API and
download endpoints can change over time, so the SHA-256 hashes identify the
exact vintage used in the paper.

## Eurostat regional GDP

- Publisher: Eurostat.
- Dataset: Gross domestic product (GDP) at current market prices by NUTS 2
  region.
- Dataset code and DOI: `nama_10r_2gdp`,
  [doi:10.2908/NAMA_10R_2GDP](https://doi.org/10.2908/NAMA_10R_2GDP).
- Selection: annual 2023 observations with unit
  `PPS_HAB_EU27_2020`.
- Unit label verified in the downloaded dataflow metadata: "Purchasing power
  standard (PPS, EU27 from 2020), per inhabitant in percentage of the EU27
  (from 2020) average."
- [Data Browser documentation](https://ec.europa.eu/eurostat/databrowser/view/nama_10r_2gdp/default/table?lang=en).
- [Exact SDMX-CSV query](https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/data/dataflow/ESTAT/nama_10r_2gdp/1.0?c%5Bunit%5D=PPS_HAB_EU27_2020&c%5BTIME_PERIOD%5D=2023&format=csvdata&formatVersion=2.0&compress=false).
- Local file: `data/raw/eurostat/nama_10r_2gdp_PPS_HAB_EU27_2020_2023.csv`.
- Size: 29,328 bytes.
- SHA-256:
  `6fd77f3ef372a4279f7f4c81c5fabe8dd4f25004dcce7228e77d05ce1a3d288f`.
- Snapshot structure: 416 rows and 9 source columns; all `geo` keys unique.
- Geographic keys: 31 national, 108 NUTS 1, 276 NUTS 2, and one
  `EU27_2020` aggregate.
- Flags in the joined NUTS 2 sample: 174 unflagged, 101 provisional (`p`),
  and one estimated (`e`).

Supporting metadata is saved as
`docs/source_metadata/nama_10r_2gdp_dataflow.xml`:

- [Dataflow metadata endpoint](https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/structure/dataflow/ESTAT/nama_10r_2gdp/1.0?references=descendants&detail=referencepartial&compress=false).
- Size: 343,650 bytes.
- SHA-256:
  `ed6b3de8c3d4f948ee139b235bf33b20f17de3ef22e24942fd295936aa59c454`.

Relevant official metadata:

- [Regional economic accounts reference metadata](https://ec.europa.eu/eurostat/cache/metadata/en/reg_eco10_esms.htm).
- [Eurostat API introduction](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction).

Eurostat applies national purchasing-power parities within each country because
regional PPPs do not exist. Regional GDP measures production in the region,
not household income. The API serves the latest observation vintage, so a new
download can differ from this archive.

## GISCO NUTS geometry

- Publisher: Eurostat GISCO.
- Dataset: NUTS 2024 statistical regions, NUTS level 2.
- Format: ESRI Shapefile.
- Geometry: region polygons generalized for approximately 1:20 million
  cartography (`20M`).
- Coordinate reference system: WGS 84 (`EPSG:4326`).
- [NUTS 2024 catalogue](https://gisco-services.ec.europa.eu/distribution/v2/nuts/nuts-2024-files.html).
- [Exact shapefile archive](https://gisco-services.ec.europa.eu/distribution/v2/nuts/shp/NUTS_RG_20M_2024_4326_LEVL_2.shp.zip).
- Local archive:
  `data/raw/gisco/NUTS_RG_20M_2024_4326_LEVL_2.shp.zip`.
- Size: 159,288 bytes.
- SHA-256:
  `6f18e28eb10e9d3c3079b6bc333171d796832376b44f85b8818628e272105f1c`.
- Archive contents: `.shp`, `.shx`, `.dbf`, `.prj`, and UTF-8 `.cpg`.
- Snapshot structure: 299 unique level-2 features, 38 country or territory
  codes, no missing, empty, or invalid geometry.
- HTTP metadata observed during the source audit: `Last-Modified: Sat, 16 May
  2026 06:14:55 GMT`; `ETag: "26e38-651e93f8255c0"`.

Supporting GISCO files:

- `docs/source_metadata/nuts-2024-files.json`: 102,589 bytes; SHA-256
  `70abca1153abeb610aabb34e41a599cb6ffb556b28fc766015ed25a1fa3351bf`.
- `docs/source_metadata/nuts-2024-release-notes.txt`: 592 bytes; SHA-256
  `607832e17637451586dbb817857ed09f4f20ab3ca2e756f45b5f7e40320018d4`.

The GISCO filename is versioned by classification but the hosted archive has
received corrections. The saved archive and hash, rather than the live URL
alone, define the geometry used here.

## Join coverage

The exact one-to-one inner join of Eurostat CSV `geo` to GISCO `NUTS_ID`
returns 276 regions:

- 244 EU27 regions;
- 1 region in Montenegro;
- 1 region in North Macedonia;
- 4 regions in Serbia;
- 26 regions in Türkiye.

All 276 GDP-side NUTS 2 keys match. The 140 GDP-side nonmatches are the 31
national values, 108 NUTS 1 values, and the EU aggregate. The 23 shape-side
nonmatches are Albania (3), Bosnia and Herzegovina (3), Switzerland (7),
Iceland (1), Liechtenstein (1), Norway (7), and Kosovo (1). Both anti-joins are
archived under `data/interim/`.
