# ECON 4555 Problem Set 4

This repository contains the code, data, and figures for ECON 4555 Problem Set 4.

## Repository layout

- `scripts/` holds Python scripts for the analysis and figure generation.
- `data/` holds input data used by the scripts.
- `figures/` holds figures produced by the analysis.

## Question 2 · Union Pacific and Norfolk Southern

### Regenerate the network map

1. Place the **North American Rail Network Lines** shapefile ZIP from the [BTS National Transportation Atlas Database](https://geodata.bts.gov/search?q=North%20American%20Rail%20Network%20Lines) at `data/narn_lines.zip`. The published figure uses the October 19, 2026 FRA update. The reassembled ZIP has SHA-256 `297b6e76438db8d7142a93bc4a78124043367103d40751df65d20278eb567089`. You can also pass the extracted `.shp` path with its sidecar files alongside it.
2. Run these commands from the repository root:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   python scripts/rail_networks.py data/narn_lines.zip
   ```

The script writes `figures/rail_networks.png`. It downloads a pinned [U.S. Atlas state boundary file](https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json) derived from Census boundaries. For offline plotting, save that file locally and pass `--boundaries path/to/states-10m.json`.

The plotting code matches the exact carrier codes `UP` and `NS` in NARN fields `RROWNER1`–`RROWNER3` and `TRKRGHTS1`–`TRKRGHTS9`. The owner fields can also indicate dispatch or maintenance responsibility. It reports each carrier's record counts and uses alternating colors where both codes occur on the same record. The script selects U.S. records using `COUNTRY` and excludes Alaska and Hawaii using `STATEAB`, preserving rail geometry across rivers and coastal waters. Interchange markers indicate metro areas.

### Network size and interchange costs

UP's western network and NS's eastern network meet at gateways including Chicago, Kansas City, St. Louis, Memphis, and New Orleans. Combining those networks could expand the number of origin–destination pairs served by a single carrier. Where traffic can be pooled on common corridors, longer trains or fuller departures could spread fixed train and terminal costs over more shipments.

For eligible shipments that currently move UP–NS, single-carrier routing could eliminate a handoff between companies. That could reduce coordination, billing, and scheduling costs, as well as delays from missed connections. Physical switching and classification may still be needed. The map shows where those mechanisms could apply. Estimating savings would require shipment volumes, routing, and terminal dwell data.
