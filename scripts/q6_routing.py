"""Scenario-based Class I routing for selected 2024 Waybill BEA areas."""

import argparse
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from shapely import get_point

from q5_waybill_regression import clean_samples, read_waybills

ROOT = Path(__file__).resolve().parents[1]
CARRIERS = ("BNSF", "CN", "CPKC", "CSXT", "NS", "UP")
GATEWAYS = (64, 73, 83, 96, 99)
METERS_PER_MILE = 1609.344
WAYBILL_FIELDS = {"origin": (104, 106), "destination": (126, 128),
                  "interchange_state": (108, 109)}


def load_waybills(path):
    # Reuse the checked 247-byte parser and Q5 eligibility criteria.
    raw = read_waybills(path, WAYBILL_FIELDS, ("interchange_state",))
    _, baseline, _, _, _ = clean_samples(raw)
    return baseline


def read_network(path):
    source = f"zip://{path.resolve()}" if path.suffix.lower() == ".zip" else path
    rails = gpd.read_file(source, where="COUNTRY = 'US' AND STATEAB NOT IN ('AK','HI')")
    rails = rails.loc[rails.MILES.gt(0) & rails.geom_type.eq("LineString")].to_crs(5070)
    # NARN endpoint IDs establish topology; the geometry supplies snap locations.
    nodes = pd.concat([
        pd.DataFrame({"node": rails[id_field], "x": points.x, "y": points.y,
                      "state": rails.STATEAB})
        for id_field, points in [
            ("FRFRANODE", gpd.GeoSeries(get_point(rails.geometry.array, 0), index=rails.index)),
            ("TOFRANODE", gpd.GeoSeries(get_point(rails.geometry.array, -1), index=rails.index)),
        ]
    ], ignore_index=True)
    positions = nodes.groupby("node", sort=True)[["x", "y"]].median()
    node_index = positions.index
    node_states = {state: node_index.isin(group.node)
                   for state, group in nodes.groupby("state")}
    return rails, positions, node_states


def carrier_layers(rails, positions, anchors, snap_miles, include_rights):
    owners = rails.filter(regex=r"^RROWNER\d+$")
    rights = rails.filter(regex=r"^TRKRGHTS\d+$")
    index = positions.index
    xy = positions.to_numpy()
    distance_by_carrier = {}
    diagnostics = []
    for carrier in CARRIERS:
        owner = owners.eq(carrier).any(axis=1)
        allowed = owner | rights.eq(carrier).any(axis=1) if include_rights else owner
        edges = rails.loc[allowed, ["FRFRANODE", "TOFRANODE", "MILES"]].copy()
        start, end = edges.FRFRANODE.to_numpy(), edges.TOFRANODE.to_numpy()
        edges["start"] = np.minimum(start, end)
        edges["end"] = np.maximum(start, end)
        edges = edges.loc[edges.start.ne(edges.end)].groupby(["start", "end"], as_index=False).MILES.min()
        a, b = index.get_indexer(edges.start), index.get_indexer(edges.end)
        graph = coo_matrix((np.tile(edges.MILES.to_numpy(), 2), (np.r_[a, b], np.r_[b, a])),
                           shape=(len(index), len(index))).tocsr()
        present = np.unique(np.r_[a, b])
        _, parts = connected_components(graph[present][:, present], directed=False)
        largest = np.bincount(parts).max()
        # Only owner-attributed endpoints can anchor local service in this model.
        eligible = index.get_indexer(pd.unique(pd.concat([
            rails.loc[owner, "FRFRANODE"], rails.loc[owner, "TOFRANODE"]
        ])))
        source_ids = []
        for anchor in anchors.itertuples():
            separation = np.hypot(xy[eligible, 0] - anchor.geometry.x,
                                  xy[eligible, 1] - anchor.geometry.y)
            nearest = int(separation.argmin())
            miles = separation[nearest] / METERS_PER_MILE
            accepted = miles <= snap_miles
            source_ids.append(eligible[nearest] if accepted else -1)
            diagnostics.append((carrier, anchor.bea, miles, accepted,
                                len(present), largest, int(graph.nnz // 2)))
        source_ids = np.array(source_ids)
        valid = source_ids >= 0
        distances = np.full((len(anchors), len(index)), np.inf)
        distances[valid] = dijkstra(graph, directed=False, indices=source_ids[valid])
        distance_by_carrier[carrier] = (distances, source_ids, present)
    return distance_by_carrier, pd.DataFrame(diagnostics, columns=[
        "Carrier", "BEA", "Snap miles", "Accepted", "Network nodes",
        "Largest component nodes", "Undirected links",
    ])


def route_catalog(layers, anchors, positions, node_states, gateway_miles):
    """Shortest one- and two-carrier paths; a transfer needs a shared FRA node."""
    n = len(anchors)
    routes = defaultdict(dict)
    gateway_anchors = anchors.loc[anchors.bea.isin(GATEWAYS)]
    xy = positions.to_numpy()
    near_gateway = np.zeros(len(positions), dtype=bool)
    for point in gateway_anchors.geometry:
        near_gateway |= np.hypot(xy[:, 0] - point.x, xy[:, 1] - point.y) <= gateway_miles * METERS_PER_MILE
    for a, (da, sa, pa) in layers.items():
        for i, j in np.ndindex(n, n):
            if i != j and sa[j] >= 0:
                distance = da[i, sa[j]]
                if np.isfinite(distance):
                    routes[i, j][(a,)] = distance
        for b, (db, _, pb) in layers.items():
            if a == b:
                continue
            common = np.intersect1d(pa, pb)
            if not len(common):
                continue
            groups = {"": np.ones(len(common), dtype=bool)}
            groups.update({state: mask[common] for state, mask in node_states.items()
                           if mask[common].any()})
            if {a, b} == {"UP", "NS"}:
                groups.update({f"gateway:{state}": mask[common] & near_gateway[common]
                               for state, mask in node_states.items()
                               if (mask[common] & near_gateway[common]).any()})
            left, right = da[:, common], db[:, common]
            for i, j in np.ndindex(n, n):
                if i == j:
                    continue
                distance = left[i] + right[j]
                distance[(left[i] < 5) | (right[j] < 5)] = np.inf
                for state, mask in groups.items():
                    shortest = distance[mask].min()
                    if np.isfinite(shortest):
                        routes[i, j][a, b, state] = shortest
    return routes


def classify(traffic, anchors, routes, tolerance):
    lookup = {bea: i for i, bea in enumerate(anchors.bea)}
    cases = traffic[["origin", "destination", "distance", "interchanges",
                     "interchange_state"]].drop_duplicates().copy()
    def label(row):
        if row.origin == row.destination:
            return "Unmatched: same BEA"
        if row.origin not in lookup or row.destination not in lookup:
            return "Unmatched: unmodeled BEA"
        if row.interchanges > 1:
            return "Unmatched: multiple reported interchanges"
        candidates = routes.get((lookup[row.origin], lookup[row.destination]), {})
        limit = row.distance + max(100, tolerance * row.distance)
        if row.interchanges == 0:
            return ("Matched: reported single-line" if any(
                len(k) == 1 and d <= limit for k, d in candidates.items()
            ) else "Unmatched: no compatible path")
        state = row.interchange_state
        choices = {k[:2] for k, d in candidates.items()
                   if len(k) == 3 and k[2] == state and d <= limit}
        if not choices:
            return "Unmatched: no compatible path"
        affected = {pair for pair in choices if set(pair) == {"UP", "NS"}}
        if not affected:
            return "Matched: other carrier pairs only"
        if state and choices == affected and any(
            candidates.get((*pair, f"gateway:{state}"), np.inf) <= limit for pair in affected
        ):
            return "Matched: conservative UP–NS"
        return "Matched: possible UP–NS"

    cases["Classification"] = [label(row) for row in cases.itertuples()]
    return traffic.merge(cases, how="left", validate="many_to_one")


def summarize(classified, scenario):
    data = classified.assign(
        Weighted_waybills=classified.exact_factor,
        Weighted_tons=classified.exact_factor * classified.billed_tons,
        Weighted_ton_miles=classified.exact_factor * classified.billed_tons * classified.distance,
        Weighted_revenue=classified.exact_factor * classified.revenue,
    )
    metrics = ["Weighted_waybills", "Weighted_tons", "Weighted_ton_miles", "Weighted_revenue"]
    rows = []
    for denominator, frame in [
        ("All Q5 baseline", data),
        ("Reported interline", data.loc[data.interchanges.gt(0)]),
        ("Matched interline", data.loc[data.interchanges.gt(0) & data.Classification.str.startswith("Matched")]),
    ]:
        for name, group in frame.groupby("Classification"):
            rows.append([scenario, denominator, name, len(group), len(frame),
                         len(group) / len(frame), group.Weighted_waybills.sum() / frame.Weighted_waybills.sum(),
                         *group[metrics].sum()])
    return pd.DataFrame(rows, columns=[
        "Network scenario", "Denominator", "Classification", "Sample records", "Denominator records",
        "Record share", "Weighted waybill share", *metrics,
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", type=Path)
    parser.add_argument("waybill", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "figures")
    parser.add_argument("--economic-results", action="store_true", help="Also generate Questions 8 and 9.")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    places = pd.read_csv(ROOT / "data" / "q6_bea_anchors.csv")
    anchors = gpd.GeoDataFrame(places, geometry=gpd.points_from_xy(
        places.longitude, places.latitude, crs=4326)).to_crs(5070)
    traffic = load_waybills(args.waybill)
    rails, positions, node_states = read_network(args.network)
    summaries, diagnostics = [], []
    for name, snap, rights, tolerance in [
        ("Baseline", 25, True, 0.5),
        ("Owner only, tighter snap and distance", 15, False, 0.25),
    ]:
        layers, diagnostic = carrier_layers(rails, positions, anchors, snap, rights)
        catalog = route_catalog(layers, anchors, positions, node_states, gateway_miles=25)
        classified = classify(traffic, anchors, catalog, tolerance)
        summaries.append(summarize(classified, name))
        diagnostics.append(diagnostic.assign(Scenario=name))
        print(name, classified.Classification.value_counts().to_dict(), flush=True)
        if args.economic_results:
            from q8_q9_economics import economic_results

            economic_results(classified, anchors, catalog, tolerance, name, args.output_dir)
    pd.concat(summaries).to_csv(args.output_dir / "q6_routing_summary.csv", index=False, float_format="%.10g")
    pd.concat(diagnostics).to_csv(args.output_dir / "q6_network_diagnostics.csv", index=False, float_format="%.10g")


if __name__ == "__main__":
    main()
