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

## Question 3 · Economies of density

From the repository root, create a Python 3.12 environment and run the regression:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/q3_regression.py
```

The script reads the supplied `data/RR1.csv` and regenerates `figures/q3_regression_table.csv`. The CSV contains 34 railroad-year observations, 11 distinct railroad labels, and 15 columns. The identifiers are `year`, `rr`, and `rr_id`. The operating measures are tons, ton-miles, total costs, network size, diesel price, and wages, with corresponding `l_` natural-log columns. There are no missing entries or duplicate railroad-year pairs.

The regression uses the supplied log columns directly and pools the 1998–2001 observations. It includes an intercept and uses conventional OLS standard errors, with no railroad or year fixed effects. The coefficient rows report two-sided p-values for tests against zero. The separate density-test row reports the lower-tail t-test of the ton-mile elasticity against one, using 29 residual degrees of freedom.

The estimated ton-mile elasticity is 0.745. Holding network size, diesel price, and wages fixed, 1% more ton-miles is associated with about 0.745% higher total cost and about 0.255% lower cost per ton-mile. The one-sided p-value of 0.0112 supports economies of density at the 5% level under the conventional OLS assumptions.
