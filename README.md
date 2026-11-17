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

## Question 4 · Economies of scale

Use the Python environment from Question 3 and run this command from the repository root:

```bash
python scripts/q3_regression.py --scale-output figures/q4_economies_scale.csv
```

The script uses the same pooled OLS fit for both questions. When ton-miles and network miles increase by the same percentage, traffic per network mile stays constant. Holding input prices fixed, the predicted percentage change in total cost per 1% expansion is the sum of the two coefficients, 0.744982 + 0.196552 = 0.941534. Total cost grows less than proportionally, so average cost per ton-mile falls by about 0.0585% for a 1% expansion.

The lower-tail test evaluates the null that the sum is at least one, using one as the null boundary. The standard error is the square root of the two coefficient variances plus twice their covariance. The covariance is −0.01120146 and the sum's standard error is 0.02812141. The test gives t(29) = −2.07907 and a one-sided p-value of 0.02328. The model supports economies of scale at the 5% level.

## Question 5 · Revenue per ton-mile and interchange

Use the Python 3.12 environment and pinned requirements from Question 3. Place the official [2024 STB Public Use Waybill Sample](https://www.stb.gov/reports-data/waybill/) ZIP at a local path outside the checkout. Run from the repository root:

```bash
unzip -t /path/to/PublicUseWaybillSample2024.zip
OPENBLAS_NUM_THREADS=1 python scripts/q5_waybill_regression.py /path/to/PublicUseWaybillSample2024.zip
```

The ZIP used here has SHA-256 `244e9dcb1430d9a40ff57b94b3ab472a806ec0d4225473859f75fa7709cc2249`. The script reads `PublicUseWaybillSample2024.txt` from the ZIP, temporarily writing about 540 MB to the system temporary directory. It verifies 247-byte records followed by CRLF and 2024 accounting periods. The results are `figures/q5_waybill_regression_table.csv` and `figures/q5_waybill_sample_cleaning.csv`. Use `--output-dir` to write a comparison run elsewhere.

The 2024 Reference Guide's Tables 4-6 and 4-7 define the inputs. Revenue per ton-mile is unexpanded line-haul freight revenue (field 16) divided by billed tons (field 14) times estimated short-line miles (field 26), with both quantities in the denominator. The regression uses log revenue per ton-mile, a positive reported interchange count indicator (field 31), log short-line distance, log tons, and categorical published STCC (field 13). The shortest-distance measure is rounded and can differ from miles traveled. The public record layout omits a calculated-rate flag, so contract revenue masking cannot be identified or reversed from these files.

The cleaning table counts exclusions sequentially and reports additional sensitivity filters relative to the baseline. Of 2,166,913 records, 25,856 were excluded for zero distance, then 74,841 for zero billed tons. The 2,066,216 remaining records form the all-valid sensitivity sample. The Rebill Code 0 restriction (field 25) excludes another 936,007 records, leaving 1,130,209. The baseline excludes Rule 11 rebills because those records can describe only the part of a shipment covered by the reported bill. In the all-valid fit, the interchange indicator refers to the reported movement.

The script uses statsmodels OLS after removing commodity means, which yields the same slope estimates as an intercept and STCC indicator variables. Conventional standard errors use the full model's residual degrees of freedom. HC3 uses full-model leverage, including the commodity indicators. Singleton commodities contribute no slope information and have zero contribution to slope covariance. Both confidence intervals use the full model's residual degrees of freedom. The table reports full-model R-squared, and a displayed zero p-value indicates numerical underflow. Additional fits check two-digit STCC, exact expansion-factor weights (field 29, scaled by 100 to restore its implied decimal), and actual tons (field 15) with a same-row billed-tons comparison. Weighted inference is a sensitivity check.

Holding shipment size, short-line distance, and commodity fixed, the baseline interline coefficient of 0.248674 corresponds to 28.23% higher modeled revenue per ton-mile using the single-line movement as the reference. The all-valid coefficient of 0.142730 corresponds to 15.34% higher. From the interline baseline, the corresponding single-line comparisons are 22.02% and 13.30% lower. These are conditional revenue comparisons. Carrier operating costs, route selection, and market power can also affect how an observed premium should be interpreted.
