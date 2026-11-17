"""Plot the UP and NS networks from an FRA/BTS NARN Lines export."""

import argparse
import hashlib
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
BOUNDARIES = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json"
BOUNDARY_SHA256 = "d76b391ccfa8bff601d51e3e3da5d43a89fa46cd5caca72ce731b383be5596d0"
CRS = "EPSG:5070"
COLORS = {"UP": "#f5c400", "NS": "#1663b7"}
CITIES = {
    "Chicago": (-87.630, 41.878, (8, 10)),
    "Kansas City": (-94.579, 39.100, (-9, 10)),
    "St. Louis": (-90.199, 38.627, (8, 8)),
    "Memphis": (-90.049, 35.150, (8, -2)),
    "New Orleans": (-90.072, 29.951, (10, -12)),
}


def read_states(path):
    if path is None:
        with TemporaryDirectory() as directory, urlopen(BOUNDARIES, timeout=30) as response:
            payload = response.read()
            if hashlib.sha256(payload).hexdigest() != BOUNDARY_SHA256:
                raise ValueError("The downloaded state boundaries failed SHA-256 verification.")
            downloaded = Path(directory) / "states.json"
            downloaded.write_bytes(payload)
            return read_states(downloaded)
    states = gpd.read_file(path, layer="states")
    if states.crs is None:
        states = states.set_crs(4326)
    return states.loc[~states["id"].astype(str).str.zfill(2).isin(
        {"02", "15", "60", "66", "69", "72", "78"}
    )].to_crs(CRS)


def read_routes(path, mask):
    source = f"zip://{path.resolve()}" if path.suffix.lower() == ".zip" else path
    lines = gpd.read_file(source)
    owners = [c for c in lines if re.fullmatch(r"RROWNER\d+", c, re.I)]
    rights = [c for c in lines if re.fullmatch(r"TRKRGHTS?\d+", c, re.I)]
    if not owners or not rights or lines.crs is None:
        raise ValueError("Use a NARN Lines export containing owner and trackage-rights fields and a CRS.")
    fields = lines[owners + rights].apply(lambda col: col.astype("string").str.strip().str.upper())
    matches = {code: fields.eq(code).any(axis=1) for code in COLORS}
    for code in COLORS:
        print(
            f"{code}: {fields[owners].eq(code).any(axis=1).sum():,} owner records, "
            f"{fields[rights].eq(code).any(axis=1).sum():,} rights records in source."
        )
    lines = lines.loc[matches["UP"] | matches["NS"], ["geometry"]].copy()
    for code, found in matches.items():
        lines[code] = found
    lines = lines.loc[lines.geom_type.isin(["LineString", "MultiLineString"])].to_crs(CRS)
    lines = lines.loc[lines.geometry.notna() & ~lines.geometry.is_empty]
    lines = lines.set_geometry(lines.geometry.make_valid())
    lines = gpd.clip(lines, mask, keep_geom_type=True)
    for code in COLORS:
        count = int(lines[code].sum())
        if count == 0:
            raise ValueError(f"No {code} segments with valid geometry inside the map footprint.")
        print(f"{code}: {count:,} source records intersect the map footprint.")
    print(f"Shared: {(lines['UP'] & lines['NS']).sum():,} records in map footprint.")
    return lines


def draw_map(states, lines, output):
    cities = gpd.GeoSeries(
        gpd.points_from_xy([c[0] for c in CITIES.values()], [c[1] for c in CITIES.values()]),
        index=list(CITIES), crs=4326,
    ).to_crs(CRS)
    fig, ax = plt.subplots(figsize=(13, 8), facecolor="white")
    fig.subplots_adjust(left=0.025, right=0.975, bottom=0.10, top=0.88)
    fig.text(0.052, 0.95, "Union Pacific and Norfolk Southern railroad networks",
             fontsize=22, weight="bold", color="#172b3b")
    fig.text(0.052, 0.911, "Contiguous United States  |  Ownership and trackage rights",
             fontsize=12, color="#425766")

    states.plot(ax=ax, color="#edf1f3", edgecolor="#b9c6cd", linewidth=0.5, zorder=1)
    up_only = lines.loc[lines["UP"] & ~lines["NS"]]
    ns_only = lines.loc[lines["NS"] & ~lines["UP"]]
    shared = lines.loc[lines["UP"] & lines["NS"]]
    for routes, code in [(up_only, "UP"), (ns_only, "NS"), (shared, "UP")]:
        if not routes.empty:
            routes.plot(ax=ax, color=COLORS[code], linewidth=0.85, zorder=2)
    if not shared.empty:
        shared.plot(ax=ax, color=COLORS["NS"], linewidth=0.85, linestyle=(0, (2, 2)), zorder=3)

    for city, point in cities.items():
        _, _, offset = CITIES[city]
        ax.scatter(point.x, point.y, s=30, c="#172b3b", edgecolors="white", linewidths=0.8, zorder=4)
        ax.annotate(city, (point.x, point.y), xytext=offset, textcoords="offset points",
                    ha="left" if offset[0] > 0 else "right", va="center",
                    fontsize=9, weight="bold", zorder=5,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2, "alpha": 0.9})
    ax.legend(handles=[
        Line2D([], [], color=COLORS["UP"], lw=3, label="Union Pacific (UP)"),
        Line2D([], [], color=COLORS["NS"], lw=3, label="Norfolk Southern (NS)"),
        Line2D([], [], marker="o", color="none", markerfacecolor="#172b3b",
               markeredgecolor="white", markersize=8, label="Interchange city"),
    ], loc="lower left", frameon=False)
    ax.set_axis_off()
    fig.text(0.052, 0.055, "Source: FRA/BTS North American Rail Network Lines. "
             "State boundaries: U.S. Census Bureau via U.S. Atlas.", fontsize=9, color="#425766")
    fig.text(0.052, 0.031, "Alternating colors mark records attributed to both carriers. "
             "City markers identify metro areas.", fontsize=9, color="#425766")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=240)
    plt.close(fig)
    print(f"Saved {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rail_lines", type=Path, help="FRA/BTS NARN Lines shapefile ZIP, SHP, or GeoPackage")
    parser.add_argument("--boundaries", type=Path, help="Local U.S. Atlas states-10m.json")
    parser.add_argument("--output", type=Path, default=ROOT / "figures" / "rail_networks.png")
    args = parser.parse_args()
    states = read_states(args.boundaries)
    draw_map(states, read_routes(args.rail_lines, states.geometry.union_all()), args.output)


if __name__ == "__main__":
    main()
