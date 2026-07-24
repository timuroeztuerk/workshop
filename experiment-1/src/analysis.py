#!/usr/bin/env python3
"""Reproduce the descriptive and spatial analysis for Experiment 1.

Inputs are immutable Eurostat and GISCO snapshots under data/raw. Outputs are
written to data/interim, data/processed, figures, tables, and docs.
"""

from __future__ import annotations

import json
import math
import platform
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyogrio
import pyproj
import scipy
import shapely
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import norm, rankdata


ROOT = Path(__file__).resolve().parents[1]
RAW_GDP = ROOT / "data/raw/eurostat/nama_10r_2gdp_PPS_HAB_EU27_2020_2023.csv"
RAW_SHP = ROOT / "data/raw/gisco/NUTS_RG_20M_2024_4326_LEVL_2.shp"
INTERIM = ROOT / "data/interim"
PROCESSED = ROOT / "data/processed"
FIGURES = ROOT / "figures"
TABLES = ROOT / "tables"
DOCS = ROOT / "docs"
TMP = ROOT / "tmp"

YEAR = 2023
UNIT = "PPS_HAB_EU27_2020"
PERMUTATIONS = 99_999
GLOBAL_SEED = 20_260_723
LOCAL_SEED = 20_260_724
FDR_Q = 0.05

GDP_BOUNDS = [0, 50, 75, 100, 125, 150, np.inf]
GDP_LABELS = ["<50", "50-74", "75-99", "100-124", "125-149", "150+"]
GDP_COLORS = ["#b2182b", "#ef8a62", "#fddbc7", "#d1e5f0", "#67a9cf", "#2166ac"]
LISA_ORDER = [
    "High-High",
    "Low-Low",
    "High-Low",
    "Low-High",
    "Not significant",
    "No contiguity neighbor",
]
LISA_COLORS = {
    "High-High": "#d73027",
    "Low-Low": "#4575b4",
    "High-Low": "#fdae61",
    "Low-High": "#74add1",
    "Not significant": "#e0e0e0",
    "No contiguity neighbor": "#ffffff",
}
OUTERMOST_IDS = ["FRY1", "FRY2", "FRY3", "FRY4", "FRY5"]


def ensure_directories() -> None:
    for directory in (INTERIM, PROCESSED, FIGURES, TABLES, DOCS, TMP):
        directory.mkdir(parents=True, exist_ok=True)


def infer_geo_level(code: str) -> str:
    if code == "EU27_2020":
        return "EU aggregate"
    if len(code) == 2:
        return "national"
    if len(code) == 3:
        return "NUTS 1"
    if len(code) == 4:
        return "NUTS 2"
    return "other"


def gini(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    if np.any(x < 0) or np.allclose(x.sum(), 0):
        raise ValueError("Gini requires non-negative values with a positive sum.")
    x = np.sort(x)
    n = x.size
    return float((2 * np.dot(np.arange(1, n + 1), x) / (n * x.sum())) - (n + 1) / n)


def clean_and_join() -> tuple[pd.DataFrame, gpd.GeoDataFrame, dict[str, object]]:
    expected_columns = [
        "STRUCTURE",
        "STRUCTURE_ID",
        "freq",
        "unit",
        "geo",
        "TIME_PERIOD",
        "OBS_VALUE",
        "OBS_FLAG",
        "CONF_STATUS",
    ]
    raw = pd.read_csv(
        RAW_GDP,
        dtype={"geo": "string", "OBS_FLAG": "string", "CONF_STATUS": "string"},
    )
    assert raw.columns.tolist() == expected_columns
    assert raw["geo"].notna().all()
    raw["geo"] = raw["geo"].str.strip()
    assert raw["geo"].is_unique
    assert set(raw["freq"]) == {"A"}
    assert set(raw["unit"]) == {UNIT}
    assert set(raw["TIME_PERIOD"]) == {YEAR}
    assert set(raw["STRUCTURE"]) == {"dataflow"}
    assert set(raw["STRUCTURE_ID"]) == {"ESTAT:NAMA_10R_2GDP(1.0)"}
    assert raw["OBS_VALUE"].notna().all()
    raw["gdp_pc_index"] = pd.to_numeric(raw["OBS_VALUE"], errors="raise")
    assert (raw["gdp_pc_index"] > 0).all()
    raw["geo_level"] = raw["geo"].map(infer_geo_level)
    raw["obs_flag"] = raw["OBS_FLAG"].fillna("")
    raw["conf_status"] = raw["CONF_STATUS"].fillna("")

    clean_columns = [
        "geo",
        "geo_level",
        "TIME_PERIOD",
        "unit",
        "gdp_pc_index",
        "obs_flag",
        "conf_status",
    ]
    clean = raw[clean_columns].sort_values(["geo_level", "geo"]).reset_index(drop=True)
    clean.to_csv(INTERIM / "gdp_2023_clean_all_levels.csv", index=False)

    regions = gpd.read_file(RAW_SHP)
    assert len(regions) == 299
    assert regions["NUTS_ID"].is_unique
    assert set(regions["LEVL_CODE"]) == {2}
    assert regions.crs is not None and regions.crs.to_epsg() == 4326
    assert regions.geometry.notna().all()
    assert (~regions.geometry.is_empty).all()
    assert regions.geometry.is_valid.all()

    joined = regions.merge(
        clean,
        left_on="NUTS_ID",
        right_on="geo",
        how="inner",
        validate="one_to_one",
    )
    joined = joined.sort_values("NUTS_ID").reset_index(drop=True)
    assert len(joined) == 276
    assert joined["NUTS_ID"].str.len().eq(4).all()
    assert joined["geo_level"].eq("NUTS 2").all()
    assert joined["gdp_pc_index"].notna().all()
    assert joined["NUTS_ID"].is_unique
    assert joined.geometry.is_valid.all()

    gdp_antijoin = clean.loc[~clean["geo"].isin(regions["NUTS_ID"])].copy()
    shape_antijoin = regions.loc[
        ~regions["NUTS_ID"].isin(clean["geo"]),
        ["NUTS_ID", "CNTR_CODE", "NAME_LATN", "EU_STAT", "EFTA_STAT", "CC_STAT"],
    ].copy()
    gdp_antijoin.to_csv(INTERIM / "gdp_keys_not_in_shapefile.csv", index=False)
    shape_antijoin.sort_values("NUTS_ID").to_csv(
        INTERIM / "shapefile_regions_without_gdp.csv", index=False
    )
    assert not (gdp_antijoin["geo_level"] == "NUTS 2").any()
    assert len(shape_antijoin) == 23

    joined["is_eu"] = joined["EU_STAT"].eq("T")
    joined["sample_group"] = np.where(joined["is_eu"], "EU27", "candidate country")
    joined["log_gdp_pc_index"] = np.log(joined["gdp_pc_index"])
    joined["gdp_map_class"] = pd.cut(
        joined["gdp_pc_index"],
        bins=GDP_BOUNDS,
        labels=GDP_LABELS,
        right=False,
        include_lowest=True,
    ).astype("string")

    joined.drop(columns="geometry").to_csv(INTERIM / "gdp_2023_nuts2_joined.csv", index=False)

    audit = {
        "csv_rows": int(len(raw)),
        "csv_columns": int(len(expected_columns)),
        "csv_geo_levels": {
            str(key): int(value) for key, value in raw["geo_level"].value_counts().items()
        },
        "shapefile_rows": int(len(regions)),
        "joined_rows": int(len(joined)),
        "joined_countries": int(joined["CNTR_CODE"].nunique()),
        "joined_eu_regions": int(joined["is_eu"].sum()),
        "joined_candidate_regions": int((~joined["is_eu"]).sum()),
        "shape_only_rows": int(len(shape_antijoin)),
        "gdp_side_nonmatches": int(len(gdp_antijoin)),
        "unmatched_gdp_nuts2": int((gdp_antijoin["geo_level"] == "NUTS 2").sum()),
        "joined_flag_counts": {
            ("unflagged" if str(key) == "" else str(key)): int(value)
            for key, value in joined["obs_flag"].value_counts(dropna=False).items()
        },
        "invalid_joined_geometries": int((~joined.geometry.is_valid).sum()),
        "missing_joined_values": int(joined["gdp_pc_index"].isna().sum()),
    }
    return clean, joined, audit


def contiguity_matrix(gdf: gpd.GeoDataFrame, kind: str = "queen") -> np.ndarray:
    if kind not in {"queen", "rook"}:
        raise ValueError("kind must be 'queen' or 'rook'")
    n = len(gdf)
    adjacency = np.zeros((n, n), dtype=np.uint8)
    pairs = gdf.sindex.query(gdf.geometry, predicate="touches")
    for left, right in zip(pairs[0], pairs[1]):
        if left >= right:
            continue
        if kind == "rook":
            intersection = gdf.geometry.iloc[left].boundary.intersection(
                gdf.geometry.iloc[right].boundary
            )
            if intersection.length <= 1e-12:
                continue
        adjacency[left, right] = 1
        adjacency[right, left] = 1
    np.fill_diagonal(adjacency, 0)
    return adjacency


def row_standardize(adjacency: np.ndarray) -> np.ndarray:
    weights = adjacency.astype(float)
    row_sums = weights.sum(axis=1)
    nonzero = row_sums > 0
    weights[nonzero] /= row_sums[nonzero, None]
    return weights


def graph_diagnostics(adjacency: np.ndarray) -> dict[str, object]:
    degrees = adjacency.sum(axis=1)
    n_components, labels = connected_components(csr_matrix(adjacency), directed=False)
    sizes = np.bincount(labels, minlength=n_components)
    return {
        "nodes": int(adjacency.shape[0]),
        "edges": int(adjacency.sum() // 2),
        "isolates": int((degrees == 0).sum()),
        "components": int(n_components),
        "component_sizes": sorted([int(value) for value in sizes], reverse=True),
        "degree_min": int(degrees.min()),
        "degree_median": float(np.median(degrees)),
        "degree_mean": float(degrees.mean()),
        "degree_max": int(degrees.max()),
        "component_labels": labels,
    }


def save_edge_list(
    gdf: gpd.GeoDataFrame,
    adjacency: np.ndarray,
    filename: str,
    distances_km: np.ndarray | None = None,
) -> None:
    rows: list[dict[str, object]] = []
    for left, right in zip(*np.where(np.triu(adjacency, k=1) > 0)):
        record: dict[str, object] = {
            "origin": gdf.iloc[left]["NUTS_ID"],
            "neighbor": gdf.iloc[right]["NUTS_ID"],
        }
        if distances_km is not None:
            record["centroid_distance_km"] = float(distances_km[left, right] / 1000)
        rows.append(record)
    pd.DataFrame(rows).sort_values(["origin", "neighbor"]).to_csv(
        INTERIM / filename, index=False
    )


def symmetric_knn_projected(
    gdf: gpd.GeoDataFrame, k: int = 5
) -> tuple[np.ndarray, np.ndarray]:
    projected = gdf.to_crs(3035)
    centroids = projected.geometry.centroid
    coordinates = np.column_stack([centroids.x.to_numpy(), centroids.y.to_numpy()])
    differences = coordinates[:, None, :] - coordinates[None, :, :]
    distances = np.sqrt(np.sum(differences**2, axis=2))
    np.fill_diagonal(distances, np.inf)
    directed = np.zeros((len(gdf), len(gdf)), dtype=np.uint8)
    nearest = np.argpartition(distances, kth=k - 1, axis=1)[:, :k]
    directed[np.arange(len(gdf))[:, None], nearest] = 1
    adjacency = np.maximum(directed, directed.T)
    np.fill_diagonal(distances, 0)
    return adjacency, distances


def moran_global(
    values: np.ndarray,
    adjacency: np.ndarray,
    permutations: int,
    seed: int,
) -> dict[str, float | int]:
    x = np.asarray(values, dtype=float)
    if adjacency.shape != (x.size, x.size):
        raise ValueError("Values and adjacency dimensions do not align.")
    if (adjacency.sum(axis=1) == 0).any():
        raise ValueError("Remove zero-neighbor observations before Moran inference.")
    weights = row_standardize(adjacency)
    z = x - x.mean()
    denominator = float(z @ z)
    s0 = float(weights.sum())
    n = x.size
    row, column = np.nonzero(weights)
    edge_weights = weights[row, column]

    def statistic(vector: np.ndarray) -> float:
        numerator = float(np.sum(edge_weights * vector[row] * vector[column]))
        return float((n / s0) * numerator / denominator)

    observed = statistic(z)
    rng = np.random.default_rng(seed)
    simulations = np.empty(permutations, dtype=float)
    for draw in range(permutations):
        simulations[draw] = statistic(rng.permutation(z))
    expected = -1 / (n - 1)
    p_greater = float((1 + np.sum(simulations >= observed)) / (permutations + 1))
    centered_observed = abs(observed - simulations.mean())
    p_two_sided = float(
        (1 + np.sum(np.abs(simulations - simulations.mean()) >= centered_observed))
        / (permutations + 1)
    )
    return {
        "n": int(n),
        "edges": int(adjacency.sum() // 2),
        "s0": s0,
        "moran_i": observed,
        "expected_i": expected,
        "permutation_mean": float(simulations.mean()),
        "permutation_sd": float(simulations.std(ddof=1)),
        "p_greater": p_greater,
        "p_two_sided": p_two_sided,
        "permutations": int(permutations),
        "seed": int(seed),
    }


def adjust_bh(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    m = p.size
    order = np.argsort(p)
    ranked = p[order]
    adjusted_ranked = ranked * m / np.arange(1, m + 1)
    adjusted_ranked = np.minimum.accumulate(adjusted_ranked[::-1])[::-1]
    adjusted = np.empty(m, dtype=float)
    adjusted[order] = np.clip(adjusted_ranked, 0, 1)
    return adjusted


def adjust_holm(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    m = p.size
    order = np.argsort(p)
    ranked = p[order]
    adjusted_ranked = ranked * (m - np.arange(m))
    adjusted_ranked = np.maximum.accumulate(adjusted_ranked)
    adjusted = np.empty(m, dtype=float)
    adjusted[order] = np.clip(adjusted_ranked, 0, 1)
    return adjusted


def moran_local(
    values: np.ndarray,
    adjacency: np.ndarray,
    permutations: int,
    seed: int,
) -> pd.DataFrame:
    x = np.asarray(values, dtype=float)
    n = x.size
    if adjacency.shape != (n, n):
        raise ValueError("Values and adjacency dimensions do not align.")
    degrees = adjacency.sum(axis=1).astype(int)
    if (degrees == 0).any():
        raise ValueError("Local Moran input must exclude zero-neighbor regions.")
    z = (x - x.mean()) / x.std(ddof=0)
    weights = row_standardize(adjacency)
    lag = weights @ z
    local_i = z * lag

    rng = np.random.default_rng(seed)
    # Only the first d+1 positions are needed to recover the first d draws
    # after removing a focal region. Storing this short prefix keeps the
    # 99,999-draw conditional test memory-bounded while preserving the exact
    # randomization stream produced by a full permutation on every draw.
    prefix_width = int(degrees.max()) + 1
    permutation_prefixes = np.empty(
        (permutations, prefix_width), dtype=np.int16
    )
    base = np.arange(n, dtype=np.int16)
    for draw in range(permutations):
        permutation_prefixes[draw] = rng.permutation(base)[:prefix_width]

    p_values = np.empty(n, dtype=float)
    permutation_means = np.empty(n, dtype=float)
    for index in range(n):
        degree = degrees[index]
        sampled_neighbors = permutation_prefixes[:, :degree]
        sampled_sum = z[sampled_neighbors].sum(axis=1)
        focal_in_sample = np.any(sampled_neighbors == index, axis=1)
        sampled_sum[focal_in_sample] += (
            z[permutation_prefixes[focal_in_sample, degree]] - z[index]
        )
        simulated_lag = sampled_sum / degree
        simulations = z[index] * simulated_lag
        center = simulations.mean()
        permutation_means[index] = center
        p_values[index] = (
            1 + np.sum(np.abs(simulations - center) >= abs(local_i[index] - center))
        ) / (permutations + 1)

    bh = adjust_bh(p_values)
    holm = adjust_holm(p_values)
    quadrant = np.select(
        [
            (z >= 0) & (lag >= 0),
            (z < 0) & (lag < 0),
            (z >= 0) & (lag < 0),
            (z < 0) & (lag >= 0),
        ],
        ["High-High", "Low-Low", "High-Low", "Low-High"],
        default="Undefined",
    )
    return pd.DataFrame(
        {
            "z_log_gdp": z,
            "spatial_lag": lag,
            "local_moran_i": local_i,
            "local_perm_mean": permutation_means,
            "local_p_two_sided": p_values,
            "local_q_bh": bh,
            "local_p_holm": holm,
            "lisa_quadrant": quadrant,
            "lisa_fdr_cluster": np.where(bh <= FDR_Q, quadrant, "Not significant"),
            "lisa_holm_cluster": np.where(holm <= 0.05, quadrant, "Not significant"),
        }
    )


def inequality_statistics(gdf: gpd.GeoDataFrame) -> tuple[pd.DataFrame, float]:
    values = gdf["gdp_pc_index"].to_numpy(dtype=float)
    p10, p25, p50, p75, p90 = np.percentile(values, [10, 25, 50, 75, 90])
    relative = values / values.mean()
    theil = float(np.mean(relative * np.log(relative)))
    log_values = np.log(values)
    total_ss = float(np.sum((log_values - log_values.mean()) ** 2))
    grouped = pd.DataFrame(
        {"country": gdf["CNTR_CODE"], "log_value": log_values}
    ).groupby("country")["log_value"]
    between_ss = float(
        sum(
            len(group) * (group.mean() - log_values.mean()) ** 2
            for _, group in grouped
        )
    )
    between_share = between_ss / total_ss
    records = [
        ("Regions", len(values), "count"),
        ("Countries", gdf["CNTR_CODE"].nunique(), "count"),
        ("Mean", values.mean(), "index"),
        ("Median", p50, "index"),
        ("Standard deviation", values.std(ddof=1), "index"),
        ("Coefficient of variation", values.std(ddof=1) / values.mean(), "ratio"),
        ("Minimum", values.min(), "index"),
        ("10th percentile", p10, "index"),
        ("25th percentile", p25, "index"),
        ("75th percentile", p75, "index"),
        ("90th percentile", p90, "index"),
        ("Maximum", values.max(), "index"),
        ("90/10 ratio", p90 / p10, "ratio"),
        ("Gini coefficient", gini(values), "ratio"),
        ("Theil T", theil, "ratio"),
        ("Share below 75", np.mean(values < 75), "share"),
        ("Share at or above 100", np.mean(values >= 100), "share"),
        ("Share at or above 125", np.mean(values >= 125), "share"),
        ("Between-country share of log variance", between_share, "share"),
    ]
    table = pd.DataFrame(records, columns=["statistic", "value", "unit"])
    return table, between_share


def create_country_and_extreme_tables(gdf: gpd.GeoDataFrame) -> None:
    country_summary = (
        gdf.groupby(["CNTR_CODE", "NAME_ENGL", "sample_group"], as_index=False)
        .agg(
            regions=("NUTS_ID", "size"),
            mean_index=("gdp_pc_index", "mean"),
            median_index=("gdp_pc_index", "median"),
            minimum_index=("gdp_pc_index", "min"),
            maximum_index=("gdp_pc_index", "max"),
            provisional=("obs_flag", lambda values: int((values == "p").sum())),
            estimated=("obs_flag", lambda values: int((values == "e").sum())),
        )
        .sort_values("mean_index", ascending=False)
    )
    country_summary.to_csv(TABLES / "country_summary.csv", index=False)

    display_columns = [
        "rank_group",
        "rank",
        "NUTS_ID",
        "NAME_LATN",
        "NAME_ENGL",
        "gdp_pc_index",
        "obs_flag",
    ]
    bottom = gdf.nsmallest(10, "gdp_pc_index").copy()
    bottom["rank_group"] = "Bottom 10"
    bottom["rank"] = np.arange(1, 11)
    top = gdf.nlargest(10, "gdp_pc_index").copy()
    top["rank_group"] = "Top 10"
    top["rank"] = np.arange(1, 11)
    pd.concat([top[display_columns], bottom[display_columns]], ignore_index=True).to_csv(
        TABLES / "top_bottom_regions.csv", index=False
    )


def plot_choropleth(gdf: gpd.GeoDataFrame) -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )
    cmap = ListedColormap(GDP_COLORS)
    norm_values = BoundaryNorm(GDP_BOUNDS, cmap.N)
    colors = [cmap(norm_values(value)) for value in gdf["gdp_pc_index"]]

    fig = plt.figure(figsize=(12, 8.2))
    ax = fig.add_axes([0.04, 0.13, 0.76, 0.75])
    gdf.plot(ax=ax, color=colors, edgecolor="#666666", linewidth=0.28)
    ax.set_xlim(-32.5, 45.5)
    ax.set_ylim(27, 72.5)
    ax.set_axis_off()
    fig.text(
        0.04,
        0.955,
        "Regional GDP per capita across available European NUTS 2 regions, 2023",
        fontsize=16,
        fontweight="bold",
        ha="left",
    )
    fig.text(
        0.04,
        0.922,
        "Purchasing power standard per inhabitant, EU27 average = 100",
        fontsize=10.5,
        color="#444444",
        ha="left",
    )

    handles = [
        Patch(facecolor=color, edgecolor="#666666", label=label)
        for color, label in zip(GDP_COLORS, GDP_LABELS)
    ]
    legend = ax.legend(
        handles=handles,
        title="GDP per capita index",
        loc="lower left",
        frameon=True,
        framealpha=0.95,
        ncol=2,
        handlelength=1.3,
        columnspacing=1.1,
        borderpad=0.7,
    )
    legend.get_title().set_fontweight("bold")

    for position, nuts_id in enumerate(OUTERMOST_IDS):
        inset = fig.add_axes([0.825, 0.765 - position * 0.145, 0.145, 0.115])
        subset = gdf.loc[gdf["NUTS_ID"] == nuts_id]
        color = cmap(norm_values(float(subset["gdp_pc_index"].iloc[0])))
        subset.plot(ax=inset, color=[color], edgecolor="#666666", linewidth=0.5)
        xmin, ymin, xmax, ymax = subset.total_bounds
        width = max(xmax - xmin, 0.15)
        height = max(ymax - ymin, 0.15)
        inset.set_xlim(xmin - width * 0.18, xmax + width * 0.18)
        inset.set_ylim(ymin - height * 0.18, ymax + height * 0.18)
        inset.set_axis_off()
        name = str(subset["NAME_LATN"].iloc[0])
        value = int(subset["gdp_pc_index"].iloc[0])
        inset.set_title(f"{nuts_id} {name} ({value})", fontsize=7.5, pad=1.5)

    fig.text(
        0.825,
        0.905,
        "French outermost regions",
        fontsize=9,
        fontweight="bold",
        ha="left",
    )
    fig.text(
        0.04,
        0.045,
        "Notes: Full inner-join sample (n = 276). Policy-relevant classes around the EU benchmark; "
        "no population weighting. Candidate-country regions with data are included.",
        fontsize=7.8,
        color="#444444",
        ha="left",
    )
    fig.text(
        0.04,
        0.022,
        "Sources: Eurostat nama_10r_2gdp and Eurostat GISCO NUTS 2024. Retrieved 23 July 2026.",
        fontsize=7.8,
        color="#444444",
        ha="left",
    )
    for suffix in ("png", "pdf"):
        fig.savefig(
            FIGURES / f"gdp_per_capita_map.{suffix}",
            dpi=300 if suffix == "png" else None,
            bbox_inches="tight",
        )
    plt.close(fig)


def plot_lisa_map(gdf: gpd.GeoDataFrame) -> None:
    colors = [LISA_COLORS[value] for value in gdf["lisa_fdr_cluster"]]
    fig = plt.figure(figsize=(12, 8.2))
    ax = fig.add_axes([0.04, 0.13, 0.76, 0.75])
    gdf.plot(ax=ax, color=colors, edgecolor="#666666", linewidth=0.28)
    ax.set_xlim(-32.5, 45.5)
    ax.set_ylim(27, 72.5)
    ax.set_axis_off()
    fig.text(
        0.04,
        0.955,
        "Local spatial association in log GDP per capita, 2023",
        fontsize=16,
        fontweight="bold",
        ha="left",
    )
    fig.text(
        0.04,
        0.922,
        "Local Moran quadrants retained after Benjamini-Hochberg adjustment at q = 0.05",
        fontsize=10.5,
        color="#444444",
        ha="left",
    )
    handles = [
        Patch(facecolor=LISA_COLORS[label], edgecolor="#666666", label=label)
        for label in LISA_ORDER
    ]
    legend = ax.legend(
        handles=handles,
        title="BH-adjusted category",
        loc="lower left",
        frameon=True,
        framealpha=0.95,
        ncol=2,
        handlelength=1.3,
        columnspacing=1.1,
        borderpad=0.7,
    )
    legend.get_title().set_fontweight("bold")

    for position, nuts_id in enumerate(OUTERMOST_IDS):
        inset = fig.add_axes([0.825, 0.765 - position * 0.145, 0.145, 0.115])
        subset = gdf.loc[gdf["NUTS_ID"] == nuts_id]
        color = LISA_COLORS[str(subset["lisa_fdr_cluster"].iloc[0])]
        subset.plot(ax=inset, color=[color], edgecolor="#666666", linewidth=0.5)
        xmin, ymin, xmax, ymax = subset.total_bounds
        width = max(xmax - xmin, 0.15)
        height = max(ymax - ymin, 0.15)
        inset.set_xlim(xmin - width * 0.18, xmax + width * 0.18)
        inset.set_ylim(ymin - height * 0.18, ymax + height * 0.18)
        inset.set_axis_off()
        inset.set_title(
            f"{nuts_id} {subset['NAME_LATN'].iloc[0]}", fontsize=7.5, pad=1.5
        )

    fig.text(
        0.825,
        0.905,
        "French outermost regions",
        fontsize=9,
        fontweight="bold",
        ha="left",
    )
    fig.text(
        0.04,
        0.045,
        "Notes: First-order queen contiguity; row-standardized weights. Inference uses 255 regions with a neighbor and "
        f"{PERMUTATIONS:,} conditional randomizations. High/low is relative to the analysis-sample mean.",
        fontsize=7.8,
        color="#444444",
        ha="left",
    )
    fig.text(
        0.04,
        0.022,
        "White regions have no polygon-contiguity neighbor and are not tested. Categories describe association, not causation.",
        fontsize=7.8,
        color="#444444",
        ha="left",
    )
    for suffix in ("png", "pdf"):
        fig.savefig(
            FIGURES / f"local_moran_cluster_map.{suffix}",
            dpi=300 if suffix == "png" else None,
            bbox_inches="tight",
        )
    plt.close(fig)


def plot_moran_scatter(
    analysis_gdf: gpd.GeoDataFrame,
    adjacency: np.ndarray,
    global_result: dict[str, float | int],
) -> None:
    x = np.log(analysis_gdf["gdp_pc_index"].to_numpy(dtype=float))
    z = (x - x.mean()) / x.std(ddof=0)
    weights = row_standardize(adjacency)
    scale = len(z) / weights.sum()
    scaled_lag = scale * (weights @ z)
    point_colors = [
        LISA_COLORS.get(value, "#bdbdbd")
        for value in analysis_gdf["lisa_fdr_cluster"]
    ]

    fig, ax = plt.subplots(figsize=(8.4, 6.9))
    ax.scatter(
        z,
        scaled_lag,
        c=point_colors,
        s=30,
        alpha=0.85,
        edgecolor="white",
        linewidth=0.35,
    )
    x_line = np.array([z.min() - 0.15, z.max() + 0.15])
    moran_i = float(global_result["moran_i"])
    ax.plot(x_line, moran_i * x_line, color="#222222", linewidth=1.5)
    ax.axhline(0, color="#888888", linewidth=0.7)
    ax.axvline(0, color="#888888", linewidth=0.7)
    ax.set_xlim(x_line)
    ax.set_xlabel("Standardized log GDP per capita index")
    ax.set_ylabel("Scaled row-standardized spatial lag")
    ax.set_title("Moran scatterplot", loc="left", pad=14)
    ax.text(
        0.02,
        0.98,
        f"Moran's I = {moran_i:.3f}\nPermutation p = {float(global_result['p_greater']):.5f}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#bbbbbb", "boxstyle": "round,pad=0.4"},
    )
    handles = [
        Patch(facecolor=LISA_COLORS[label], edgecolor="white", label=label)
        for label in LISA_ORDER[:-1]
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8, frameon=True)
    ax.grid(color="#eeeeee", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.text(
        0.11,
        0.015,
        f"Notes: n = {len(z)} regions with a contiguity neighbor; queen weights; {PERMUTATIONS:,} random-label permutations. "
        "Point colors use BH-adjusted local results.",
        fontsize=7.8,
        color="#444444",
    )
    fig.tight_layout(rect=(0.02, 0.045, 0.98, 0.98))
    for suffix in ("png", "pdf"):
        fig.savefig(
            FIGURES / f"moran_scatterplot.{suffix}",
            dpi=300 if suffix == "png" else None,
            bbox_inches="tight",
        )
    plt.close(fig)


def write_macros(
    gdf: gpd.GeoDataFrame,
    descriptive: pd.DataFrame,
    graph: dict[str, object],
    spatial_results: pd.DataFrame,
) -> None:
    values = gdf["gdp_pc_index"].to_numpy(dtype=float)
    get_stat = descriptive.set_index("statistic")["value"].to_dict()
    main = spatial_results.loc[spatial_results["specification"] == "Primary: log, queen"].iloc[0]
    raw = spatial_results.loc[spatial_results["specification"] == "Raw index, queen"].iloc[0]
    eu = spatial_results.loc[spatial_results["specification"] == "EU27 only: log, queen"].iloc[0]
    rook = spatial_results.loc[spatial_results["specification"] == "Log, rook"].iloc[0]
    lisa_counts = gdf["lisa_fdr_cluster"].value_counts()
    holm_counts = gdf["lisa_holm_cluster"].value_counts()
    minimum = gdf.loc[gdf["gdp_pc_index"].idxmin()]
    maximum = gdf.loc[gdf["gdp_pc_index"].idxmax()]

    commands = {
        "NRegions": f"{len(gdf)}",
        "NEURegions": f"{int(gdf['is_eu'].sum())}",
        "NCandidateRegions": f"{int((~gdf['is_eu']).sum())}",
        "NCountries": f"{gdf['CNTR_CODE'].nunique()}",
        "MeanGDP": f"{get_stat['Mean']:.1f}",
        "MedianGDP": f"{get_stat['Median']:.0f}",
        "SDGDP": f"{get_stat['Standard deviation']:.1f}",
        "CVGDP": f"{get_stat['Coefficient of variation']:.3f}",
        "GiniGDP": f"{get_stat['Gini coefficient']:.3f}",
        "TheilGDP": f"{get_stat['Theil T']:.3f}",
        "PtenGDP": f"{get_stat['10th percentile']:.0f}",
        "PninetyGDP": f"{get_stat['90th percentile']:.0f}",
        "PninetyTen": f"{get_stat['90/10 ratio']:.2f}",
        "BelowSeventyFive": f"{100 * get_stat['Share below 75']:.1f}",
        "AtLeastHundred": f"{100 * get_stat['Share at or above 100']:.1f}",
        "BetweenCountryShare": f"{100 * get_stat['Between-country share of log variance']:.1f}",
        "MinRegionName": str(minimum["NAME_LATN"]),
        "MinRegionCode": str(minimum["NUTS_ID"]),
        "MinRegionValue": f"{minimum['gdp_pc_index']:.0f}",
        "MaxRegionName": str(maximum["NAME_LATN"]),
        "MaxRegionCode": str(maximum["NUTS_ID"]),
        "MaxRegionValue": f"{maximum['gdp_pc_index']:.0f}",
        "QueenEdges": f"{graph['edges']}",
        "QueenIsolates": f"{graph['isolates']}",
        "QueenComponents": f"{graph['components']}",
        "MoranN": f"{int(main['n'])}",
        "MoranI": f"{main['moran_i']:.3f}",
        "MoranP": f"{main['p_greater']:.5f}",
        "MoranRawI": f"{raw['moran_i']:.3f}",
        "MoranEUI": f"{eu['moran_i']:.3f}",
        "MoranRookI": f"{rook['moran_i']:.3f}",
        "LISAHH": f"{int(lisa_counts.get('High-High', 0))}",
        "LISALL": f"{int(lisa_counts.get('Low-Low', 0))}",
        "LISAHL": f"{int(lisa_counts.get('High-Low', 0))}",
        "LISALH": f"{int(lisa_counts.get('Low-High', 0))}",
        "LISAFDRTotal": f"{int(sum(lisa_counts.get(label, 0) for label in LISA_ORDER[:4]))}",
        "LISAHolmTotal": f"{int(sum(holm_counts.get(label, 0) for label in LISA_ORDER[:4]))}",
        "NProvisional": f"{int((gdf['obs_flag'] == 'p').sum())}",
        "NEstimated": f"{int((gdf['obs_flag'] == 'e').sum())}",
        "Permutations": f"{PERMUTATIONS:,}",
    }
    lines = [
        "% Generated by src/analysis.py. Do not edit by hand.",
        *[
            rf"\newcommand{{\{name}}}{{{value}}}"
            for name, value in commands.items()
        ],
        "",
    ]
    (TABLES / "results_macros.tex").write_text("\n".join(lines), encoding="utf-8")


def write_table_fragments(
    descriptive: pd.DataFrame,
    spatial_results: pd.DataFrame,
    cluster_counts: pd.DataFrame,
) -> None:
    selected_stats = [
        "Regions",
        "Countries",
        "Mean",
        "Median",
        "Standard deviation",
        "Coefficient of variation",
        "10th percentile",
        "90th percentile",
        "90/10 ratio",
        "Gini coefficient",
        "Theil T",
        "Share below 75",
        "Share at or above 100",
        "Between-country share of log variance",
    ]
    subset = descriptive.set_index("statistic").loc[selected_stats].reset_index()
    lines = [r"\begin{tabular}{lr}", r"\toprule", r"Statistic & Value \\", r"\midrule"]
    for _, row in subset.iterrows():
        label = str(row["statistic"]).replace("%", r"\%")
        unit = row["unit"]
        value = float(row["value"])
        if unit == "count":
            formatted = f"{value:,.0f}"
        elif unit == "index":
            formatted = f"{value:,.1f}"
        elif unit == "share":
            formatted = f"{100 * value:.1f}\\%"
        else:
            formatted = f"{value:.3f}"
        lines.append(f"{label} & {formatted} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "descriptive_statistics.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Specification & $n$ & Moran's $I$ & $E[I]$ & Permutation $p$ \\",
        r"\midrule",
    ]
    for _, row in spatial_results.iterrows():
        label = str(row["specification"]).replace("27", "27")
        lines.append(
            f"{label} & {int(row['n'])} & {row['moran_i']:.3f} & "
            f"{row['expected_i']:.3f} & {row['p_greater']:.5f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "spatial_results.tex").write_text("\n".join(lines), encoding="utf-8")

    lines = [
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Category & BH $q\leq0.05$ & Holm \\",
        r"\midrule",
    ]
    for _, row in cluster_counts.iterrows():
        lines.append(
            f"{row['category']} & {int(row['bh_fdr_count'])} & {int(row['holm_count'])} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "lisa_cluster_counts.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ensure_directories()
    _, joined, data_audit = clean_and_join()
    descriptive, between_share = inequality_statistics(joined)
    descriptive.to_csv(TABLES / "descriptive_statistics.csv", index=False)
    create_country_and_extreme_tables(joined)

    queen = contiguity_matrix(joined, "queen")
    rook = contiguity_matrix(joined, "rook")
    queen_graph = graph_diagnostics(queen)
    rook_graph = graph_diagnostics(rook)
    save_edge_list(joined, queen, "spatial_weights_queen_edges.csv")
    save_edge_list(joined, rook, "spatial_weights_rook_edges.csv")

    degrees = queen.sum(axis=1)
    primary_positions = np.flatnonzero(degrees > 0)
    primary_gdf = joined.iloc[primary_positions].copy().reset_index(drop=True)
    primary_adjacency = queen[np.ix_(primary_positions, primary_positions)]
    assert len(primary_gdf) == 255
    assert (primary_adjacency.sum(axis=1) > 0).all()

    graph_labels = np.asarray(queen_graph["component_labels"])
    component_sizes = np.bincount(graph_labels)
    largest_label = int(np.argmax(component_sizes))
    largest_positions = np.flatnonzero(graph_labels == largest_label)
    largest_gdf = joined.iloc[largest_positions].copy().reset_index(drop=True)
    largest_queen = queen[np.ix_(largest_positions, largest_positions)]
    assert len(largest_gdf) == 238
    knn5, knn_distances = symmetric_knn_projected(largest_gdf, k=5)
    save_edge_list(
        largest_gdf,
        knn5,
        "spatial_weights_knn5_largest_component_edges.csv",
        distances_km=knn_distances,
    )

    eu_positions = np.flatnonzero(joined["is_eu"].to_numpy())
    eu_queen = queen[np.ix_(eu_positions, eu_positions)]
    eu_nonisland = np.flatnonzero(eu_queen.sum(axis=1) > 0)
    eu_analysis_positions = eu_positions[eu_nonisland]
    eu_gdf = joined.iloc[eu_analysis_positions].copy().reset_index(drop=True)
    eu_adjacency = eu_queen[np.ix_(eu_nonisland, eu_nonisland)]
    assert len(eu_gdf) == 223

    rook_nonisland = np.flatnonzero(rook.sum(axis=1) > 0)
    rook_gdf = joined.iloc[rook_nonisland].copy().reset_index(drop=True)
    rook_adjacency = rook[np.ix_(rook_nonisland, rook_nonisland)]
    assert len(rook_gdf) == 255

    ranks = rankdata(primary_gdf["gdp_pc_index"].to_numpy(dtype=float), method="average")
    rank_normal = norm.ppf((ranks - 0.5) / len(ranks))
    specifications: list[tuple[str, np.ndarray, np.ndarray, int]] = [
        (
            "Primary: log, queen",
            np.log(primary_gdf["gdp_pc_index"].to_numpy(dtype=float)),
            primary_adjacency,
            GLOBAL_SEED,
        ),
        (
            "Raw index, queen",
            primary_gdf["gdp_pc_index"].to_numpy(dtype=float),
            primary_adjacency,
            GLOBAL_SEED + 1,
        ),
        ("Rank-normalized, queen", rank_normal, primary_adjacency, GLOBAL_SEED + 2),
        (
            "Log, rook",
            np.log(rook_gdf["gdp_pc_index"].to_numpy(dtype=float)),
            rook_adjacency,
            GLOBAL_SEED + 3,
        ),
        (
            "EU27 only: log, queen",
            np.log(eu_gdf["gdp_pc_index"].to_numpy(dtype=float)),
            eu_adjacency,
            GLOBAL_SEED + 4,
        ),
        (
            "Largest component: log, queen",
            np.log(largest_gdf["gdp_pc_index"].to_numpy(dtype=float)),
            largest_queen,
            GLOBAL_SEED + 5,
        ),
        (
            "Largest component: log, symmetric 5-NN",
            np.log(largest_gdf["gdp_pc_index"].to_numpy(dtype=float)),
            knn5,
            GLOBAL_SEED + 6,
        ),
    ]
    spatial_records: list[dict[str, object]] = []
    for label, values, adjacency, seed in specifications:
        result = moran_global(values, adjacency, PERMUTATIONS, seed)
        result["specification"] = label
        spatial_records.append(result)
    spatial_results = pd.DataFrame(spatial_records)
    ordered_spatial_columns = [
        "specification",
        "n",
        "edges",
        "s0",
        "moran_i",
        "expected_i",
        "permutation_mean",
        "permutation_sd",
        "p_greater",
        "p_two_sided",
        "permutations",
        "seed",
    ]
    spatial_results = spatial_results[ordered_spatial_columns]
    spatial_results.to_csv(TABLES / "spatial_results.csv", index=False)

    local = moran_local(
        np.log(primary_gdf["gdp_pc_index"].to_numpy(dtype=float)),
        primary_adjacency,
        PERMUTATIONS,
        LOCAL_SEED,
    )
    for column in local.columns:
        joined[column] = np.nan if pd.api.types.is_numeric_dtype(local[column]) else ""
        joined.loc[primary_positions, column] = local[column].to_numpy()
    isolate_mask = joined.index.isin(np.flatnonzero(degrees == 0))
    joined.loc[isolate_mask, "lisa_fdr_cluster"] = "No contiguity neighbor"
    joined.loc[isolate_mask, "lisa_holm_cluster"] = "No contiguity neighbor"
    joined.loc[isolate_mask, "lisa_quadrant"] = "No contiguity neighbor"
    joined["queen_degree"] = degrees.astype(int)
    joined["is_queen_island"] = degrees == 0

    cluster_counts = pd.DataFrame(
        {
            "category": LISA_ORDER,
            "bh_fdr_count": [
                int((joined["lisa_fdr_cluster"] == label).sum()) for label in LISA_ORDER
            ],
            "holm_count": [
                int((joined["lisa_holm_cluster"] == label).sum()) for label in LISA_ORDER
            ],
        }
    )
    cluster_counts.to_csv(TABLES / "lisa_cluster_counts.csv", index=False)

    processed_columns = [
        "NUTS_ID",
        "CNTR_CODE",
        "NAME_LATN",
        "NAME_ENGL",
        "EU_STAT",
        "CC_STAT",
        "is_eu",
        "sample_group",
        "TIME_PERIOD",
        "unit",
        "gdp_pc_index",
        "log_gdp_pc_index",
        "obs_flag",
        "conf_status",
        "gdp_map_class",
        "queen_degree",
        "is_queen_island",
        "z_log_gdp",
        "spatial_lag",
        "local_moran_i",
        "local_perm_mean",
        "local_p_two_sided",
        "local_q_bh",
        "local_p_holm",
        "lisa_quadrant",
        "lisa_fdr_cluster",
        "lisa_holm_cluster",
    ]
    joined[processed_columns].to_csv(PROCESSED / "nuts2_gdp_2023.csv", index=False)
    joined[processed_columns + ["geometry"]].to_file(
        PROCESSED / "nuts2_gdp_2023.gpkg",
        layer="nuts2_gdp_2023",
        driver="GPKG",
    )

    graph_table = pd.DataFrame(
        [
            {"weights": "queen", **{k: v for k, v in queen_graph.items() if k != "component_labels"}},
            {"weights": "rook", **{k: v for k, v in rook_graph.items() if k != "component_labels"}},
        ]
    )
    graph_table["component_sizes"] = graph_table["component_sizes"].map(
        lambda values: ";".join(map(str, values))
    )
    graph_table.to_csv(TABLES / "spatial_graph_diagnostics.csv", index=False)

    data_quality = pd.DataFrame(
        [
            ("Raw GDP rows", data_audit["csv_rows"], 416, data_audit["csv_rows"] == 416),
            (
                "Raw shapefile features",
                data_audit["shapefile_rows"],
                299,
                data_audit["shapefile_rows"] == 299,
            ),
            (
                "Inner-joined NUTS 2 regions",
                data_audit["joined_rows"],
                276,
                data_audit["joined_rows"] == 276,
            ),
            (
                "Unmatched GDP NUTS 2 keys",
                data_audit["unmatched_gdp_nuts2"],
                0,
                data_audit["unmatched_gdp_nuts2"] == 0,
            ),
            (
                "Shape-only regions",
                data_audit["shape_only_rows"],
                23,
                data_audit["shape_only_rows"] == 23,
            ),
            (
                "Invalid joined geometries",
                data_audit["invalid_joined_geometries"],
                0,
                data_audit["invalid_joined_geometries"] == 0,
            ),
            (
                "Missing joined GDP values",
                data_audit["missing_joined_values"],
                0,
                data_audit["missing_joined_values"] == 0,
            ),
        ],
        columns=["check", "observed", "expected", "passed"],
    )
    data_quality.to_csv(TABLES / "data_quality_checks.csv", index=False)
    assert data_quality["passed"].all()

    main_result = spatial_records[0]
    primary_gdf = joined.iloc[primary_positions].copy().reset_index(drop=True)
    plot_choropleth(joined)
    plot_lisa_map(joined)
    plot_moran_scatter(primary_gdf, primary_adjacency, main_result)
    write_macros(joined, descriptive, queen_graph, spatial_results)
    write_table_fragments(descriptive, spatial_results, cluster_counts)

    max_knn_distance = float(
        max(
            knn_distances[left, right]
            for left, right in zip(*np.where(np.triu(knn5, k=1) > 0))
        )
        / 1000
    )
    summary = {
        "research_question": (
            "How strongly, and where, was 2023 GDP per capita spatially clustered "
            "among neighboring NUTS 2 regions with available Eurostat data?"
        ),
        "data_audit": data_audit,
        "descriptive": {
            row["statistic"]: float(row["value"]) for _, row in descriptive.iterrows()
        },
        "between_country_log_variance_share": float(between_share),
        "queen_graph": {k: v for k, v in queen_graph.items() if k != "component_labels"},
        "rook_graph": {k: v for k, v in rook_graph.items() if k != "component_labels"},
        "knn5_largest_component_max_link_km": max_knn_distance,
        "spatial_results": spatial_records,
        "local_cluster_counts": cluster_counts.to_dict(orient="records"),
        "software": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "geopandas": gpd.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "matplotlib": mpl.__version__,
            "shapely": shapely.__version__,
            "pyproj": pyproj.__version__,
            "pyogrio": pyogrio.__version__,
            "geos": shapely.geos_version_string,
            "proj": pyproj.proj_version_str,
            "gdal": pyogrio.__gdal_version_string__,
        },
    }
    (DOCS / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
