# Experiment 1: The Economic Geography of Europe

## Paper title

**The Economic Geography of Europe: Regional Disparities in GDP per Capita**

## Sources

### Economic data

- **Source:** Eurostat
- **Dataset:** Gross domestic product (GDP) at current market prices by NUTS 2 region
- **Dataset code:** `nama_10r_2gdp`
- **Measure:** GDP per capita in purchasing power standards, expressed relative to the EU27 average (`PPS_HAB_EU27_2020`)
- **Year:** 2023
- **Documentation:** https://ec.europa.eu/eurostat/databrowser/view/nama_10r_2gdp/default/table?lang=en
- **Direct CSV:** https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/data/dataflow/ESTAT/nama_10r_2gdp/1.0?c%5Bunit%5D=PPS_HAB_EU27_2020&c%5BTIME_PERIOD%5D=2023&format=csvdata&formatVersion=2.0&compress=false

### Geographic data

- **Source:** Eurostat GISCO
- **Dataset:** NUTS 2024 statistical regions, NUTS level 2
- **Format:** ESRI Shapefile
- **Projection:** WGS 84 (`EPSG:4326`)
- **Resolution:** 1:20 million
- **Catalogue:** https://gisco-services.ec.europa.eu/distribution/v2/nuts/nuts-2024-files.html
- **Direct shapefile:** https://gisco-services.ec.europa.eu/distribution/v2/nuts/shp/NUTS_RG_20M_2024_4326_LEVL_2.shp.zip

## Instructions

Act as an empirical economist and conduct an autonomous study of regional
economic inequality in Europe.

1. Download and document the two official sources above.
2. Clean the GDP data and join `geo` in the Eurostat CSV to `NUTS_ID` in
   the shapefile. Use an inner join so national and NUTS 1 aggregates in the
   CSV are excluded.
3. Research the relevant economics literature and formulate a focused
   research question about regional disparities and spatial clustering.
4. Produce descriptive statistics, publication-quality maps, and an
   appropriate spatial analysis.
5. Write a concise academic paper with an abstract, introduction, literature
   review, data section, methods, results, limitations, and conclusion.
6. Save all code, intermediate data, figures, tables, references, and the
   finished paper in a clear, reproducible folder structure.

Clearly distinguish descriptive associations from causal claims. Cite only
sources that have been verified, document every transformation, and do not
invent references, data, or results.
