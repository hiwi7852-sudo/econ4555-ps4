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

## Questions 6–7 · Potential UP–NS interchange reductions

Use the Python environment above and the same local FRA/BTS and STB ZIPs as in Questions 2 and 5:

```bash
OPENBLAS_NUM_THREADS=1 python scripts/q6_routing.py /path/to/narn_lines.zip /path/to/PublicUseWaybillSample2024.zip
```

The analysis covers 40 selected contiguous-U.S. BEA areas. The BEA codes and principal cities come from Table 4-4 of the 2024 STB guide. The small coordinate file gives approximate city centers. Each carrier's nearest ownership-attributed FRA node within the scenario's snap radius proxies for local access. Exact Waybill stations, commercial terminal access, and participating railroads are unavailable. A city-center snap can miss a real terminal or suggest a connection that lacks commercial access.

The model builds separate undirected networks for BNSF, CN, CPKC, CSX, NS and UP from the FRA node identifiers. No new physical tracks are added. Parallel links with the same endpoints are represented by the shortest link. The main scenario allows exact reporting-mark matches in the owner and trackage-rights fields. It permits a handoff at a shared FRA node with at least five route miles on either side. A common node is a connectivity proxy. It does not verify commercial interchange permission. The owner-only sensitivity also tightens the snap radius from 25 to 15 miles and the route distance allowance from 50% to 25%. Both route checks allow at least 100 extra miles over the reported shortest-distance proxy. The 2026 network snapshot is applied to 2024 traffic. Short-lines, other reporting marks, additional transfers, and exact station locations are outside the model.

The Waybill supplies BEA endpoints, reported distance, interchange count, and first interchange state. The modeled carrier paths are inferred. For records reporting one interchange, a candidate must fit the distance allowance and, when available, the interchange state. A conservative UP–NS candidate must be the only compatible carrier pair in the model and have a qualifying shared node within 25 miles of Chicago, Memphis, New Orleans, St. Louis or Kansas City. The broader scenario also includes records compatible with UP–NS and another pair, or lacking the gateway check. The scenarios are conditional on the selected routes and data, so neither identifies actual UP–NS traffic or a statistical bound.

For a compatible UP–NS path, common control would eliminate the modeled change in carrier identity along the same physical path. Yard switching and handling may still be required. Same-BEA moves, unmodeled areas, shipments with multiple interchanges, and records without a compatible network path are reported as unmatched. The output reports record and exact-expansion-weighted shares using all Q5 baseline records, all baseline interline records, and matched baseline interline records as separate denominators. Weighted tons, ton-miles, and revenue are calculated by expanding each Waybill once.

## Questions 8–9 · Payment scenarios and routing competition

Add `--economic-results` to the Question 6 command to regenerate the Q8 and Q9 tables. Each has a main-network file ending in `_baseline.csv` and an owner-only, tighter-distance file ending in `_owner_only.csv`. The results depend on the version of the Question 5 coefficient table in this checkout. To verify the underlying Q5 numbers independently, rerun the Question 5 command.

**Q8.** For each compatible Waybill reporting exactly one interchange, the modeled UP–NS handoff becomes internal and the modeled interchange indicator changes from one to zero. The conservative set uses only cases meeting the gateway and unique-pair screen. The broader set also includes ambiguous candidates, as a scenario in which they all use UP–NS. Apply `1 - exp(-beta)` to the observed interline revenue. With the Q5 baseline coefficient the reduction is 22.02%. This is equivalent to multiplying the per-ton-mile reduction by billed tons and shortest rail miles, then expanding each Waybill once. The alternative Q5 estimate is applied to the same revenue base for sensitivity. The results are potential reductions in shipper payments on the modeled subset. The analysis does not measure carrier operating expenses or the physical handling avoided.

**Q9.** Count the maximum number of options that share no controlling carrier. Physical path variants and different transfer nodes for the same carrier set count once. Compare the main option definition, which permits up to one interline transfer, with a single-controlling-carrier definition. Reassign UP and NS to one controlling carrier on existing modeled paths. The resulting competition measure is a proxy for pricing independence. Public records do not establish contracts or prove that a route was commercially offered. For the direct-only sensitivity, UP–NS becomes an eligible internal option where a modeled two-carrier route already existed. The broader option definition includes that same route on both sides of the merger, with the carrier sets changing.

For each option definition, estimate the association between log revenue per ton-mile and the pre-merger option category using log short-line distance, log billed tons, and published STCC fixed effects. One option is the reference. Report supported categories through four and pool five or more if present. Records with zero inferred options stay visible in the transition tables and are excluded from the regression. The primary regression is unweighted OLS, with conventional and HC3 inference. Exact expansion-weighted estimates are a sensitivity check. Apply `exp(gamma_post - gamma_pre) - 1` to the expanded observed freight revenue in each supported transition. Transitions involving zero or an unestimated category have blank dollar values. The dollar changes are sample-coverage-dependent scenarios. They rely on cross-sectional associations and do not identify causal price effects.

The transition tables report which records overlap the Q8 conservative and broader sets. Count overlap for rows where option counts change to describe the interaction of the two modeled mechanisms. Report payment reductions and competition-related changes separately because the same shipments can be affected by both and the estimates are sensitive to route assumptions.

### Results and coverage

In the main network, 267,673 of 1,130,209 baseline records matched the observed single-line or one-interchange status. This includes 17,377 of 209,741 reported interline records. The conservative candidate set contains 39 records and the broader set contains 12,266, including those 39. The broader set is 1.09% of baseline records and 1.12% after expansion weighting. It represents 5.85% of reported interline records and 9.23% after weighting. In the owner-only/tighter scenario 272 meet the conservative screen and 1,234 meet the broader screen. Removing alternative paths can make some UP–NS candidates appear unique, so the conservative sets need not be nested across network definitions.

On the modeled records, Q8 gives potential payment reductions of about $0.79 million and $209.12 million in the main conservative and broader scenarios. In the owner-only/tighter network those values are $4.89 million and $17.11 million. The range reflects route classification and coverage, not sampling confidence.

The main Q9 option definition yields 272,664 records with at least one inferred option. In the unweighted model, two, three, and four options are associated with 8.63%, 12.92%, and 15.85% lower revenue per ton-mile relative to one. The merger changes the modeled option count for 7,092 records, including 217 in the broader Q8 set. Using the unweighted coefficients, supported transitions with a positive change imply about $7.07 million in payment increases. A separately reported transition implies about $0.51 million in decreases, and 125 changed records cannot be priced because their transition is within the pooled 5+ category. Using expansion weights in the regression changes the pattern materially. These results do not establish a stable nationwide price effect.
