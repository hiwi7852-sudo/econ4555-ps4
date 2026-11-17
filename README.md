# ECON 4555 Problem Set 4

This repository contains the code, data, and figures for ECON 4555 Problem Set 4.

## Repository layout

- `scripts/` holds Python scripts for the analysis and figure generation.
- `data/` holds input data used by the scripts.
- `figures/` holds figures produced by the analysis.

## Question 2 · Union Pacific and Norfolk Southern

### Regenerate the network map

1. Download the **North American Rail Network Lines** layer from the [BTS National Transportation Atlas Database](https://geodata.bts.gov/search?q=North%20American%20Rail%20Network%20Lines). Use a shapefile ZIP or GeoPackage that includes the railroad owner and trackage-rights fields. Save it under `data/`.
2. Run these commands from the repository root:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   python scripts/rail_networks.py data/narn_lines.zip
   ```

The script writes `figures/rail_networks.png`. It downloads a pinned [U.S. Atlas state boundary file](https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json) derived from Census boundaries. For offline plotting, save that file locally and pass `--boundaries path/to/states-10m.json`.

The plotting code matches the exact carrier codes `UP` and `NS` in the NARN ownership and trackage-rights fields. It reports each carrier's record counts and uses alternating colors where both codes occur on the same record. Census boundaries limit the view to the contiguous United States. Interchange markers indicate metro areas.

### Network size and interchange costs

UP's western network and NS's eastern network meet at gateways including Chicago, Kansas City, St. Louis, Memphis, and New Orleans. Combining those networks could expand the number of origin–destination pairs served by a single carrier. Where traffic can be pooled on common corridors, longer trains or fuller departures could spread fixed train and terminal costs over more shipments.

For eligible shipments that currently move UP–NS, single-carrier routing could eliminate a handoff between companies. That could reduce coordination, billing, and scheduling costs, as well as delays from missed connections. Physical switching and classification may still be needed. The map shows where those mechanisms could apply. Estimating savings would require shipment volumes, routing, and terminal dwell data.
