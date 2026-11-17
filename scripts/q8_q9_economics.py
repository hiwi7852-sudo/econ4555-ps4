"""Translate Q6 scenarios into payment comparisons and routing competition estimates."""

from functools import lru_cache

import numpy as np
import pandas as pd

from q5_waybill_regression import estimate

MERGING = {"UP", "NS"}


def q8_estimates(data):
    interline = data.loc[data.interchanges.eq(1)]
    matched = interline.Classification
    conservative = matched.eq("Matched: conservative UP–NS")
    broad = conservative | matched.eq("Matched: possible UP–NS")
    # Read the saved Q5 estimates from the working tree used for this analysis.
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "figures" / "q5_waybill_regression_table.csv"
    q5 = pd.read_csv(path)
    estimates = q5.loc[q5.Term.eq("Interchange")].set_index("Model").Estimate
    rows = []
    for label, selected in [("Conservative", conservative), ("Broader", broad)]:
        frame = interline.loc[selected]
        revenue = (frame.exact_factor * frame.revenue).sum()
        ton_miles = (frame.exact_factor * frame.billed_tons * frame.distance).sum()
        for coefficient in ("Baseline: Rebill Code 0", "All otherwise valid records"):
            beta = estimates[coefficient]
            fraction = -np.expm1(-beta)
            rows.append({
                "Affected scenario": label, "Q5 estimate": coefficient,
                "Sample records": len(frame), "Expanded waybills": frame.exact_factor.sum(),
                "Expanded ton-miles": ton_miles, "Expanded interline revenue": revenue,
                "Avoided payment fraction": fraction, "Potential payment savings": revenue * fraction,
            })
    return pd.DataFrame(rows)


@lru_cache(maxsize=100_000)
def independent_count(options):
    """Maximum number of options with disjoint controlling-carrier sets."""
    allocations = {frozenset(): 0}
    for option in options:
        for occupied, size in list(allocations.items()):
            if occupied.isdisjoint(option):
                union = occupied | option
                allocations[union] = max(size + 1, allocations.get(union, 0))
    return max(allocations.values())


def routing_counts(data, anchors, catalog, tolerance, direct_only):
    index = {bea: i for i, bea in enumerate(anchors.bea)}
    keys = ["origin", "destination", "distance"]
    cases = data[keys].drop_duplicates().copy()

    def classify(row):
        if row.origin == row.destination or row.origin not in index or row.destination not in index:
            return 0, 0
        routes = catalog.get((index[row.origin], index[row.destination]), {})
        limit = row.distance + max(100, tolerance * row.distance)
        # Counterfactual options need not match the realized count or interchange state.
        feasible = {frozenset(route[:2]) if len(route) == 3 else frozenset(route)
                    for route, miles in routes.items()
                    if miles <= limit and (len(route) == 1 or route[2] == "")}
        merged = {frozenset("UP–NS" if carrier in MERGING else carrier for carrier in option)
                  for option in feasible}
        if direct_only:
            feasible = {option for option in feasible if len(option) == 1}
            merged = {option for option in merged if len(option) == 1}
        return independent_count(frozenset(feasible)), independent_count(frozenset(merged))

    counts = [classify(row) for row in cases.itertuples()]
    cases[["Pre", "Post"]] = np.asarray(counts)
    return data.merge(cases, on=keys, validate="many_to_one")


def q9_estimates(data, anchors, catalog, tolerance):
    regressions, transitions = [], []
    for direct_only, label in [(False, "Carrier-disjoint direct or interline"),
                               (True, "Single controlling carrier only")]:
        routed = routing_counts(data, anchors, catalog, tolerance, direct_only)
        # Preserve the actual counts in the transitions. Pool 5 and 6 in the regression.
        covered = routed.loc[routed.Pre.gt(0)].copy()
        categories = covered.Pre.clip(upper=5)
        for weighted in (False, True):
            model = "Exact expansion-weighted" if weighted else "Unweighted OLS"
            result = pd.DataFrame(estimate(covered, model, weighted=weighted,
                                           routing_categories=categories))
            regressions.append(result.assign(**{"Option definition": label}))
            premiums = {1: 0.0}
            for row in result.loc[result.Term.str.startswith("Routings:")].itertuples():
                premiums[int(row.Term.split()[-1].rstrip("+"))] = row.Estimate
            frame = routed.assign(
                Expanded_waybills=routed.exact_factor,
                Expanded_revenue=routed.revenue * routed.exact_factor,
                Q8_overlap=routed.Classification.isin([
                    "Matched: conservative UP–NS", "Matched: possible UP–NS",
                ]),
            )
            for (pre, post), group in frame.groupby(["Pre", "Post"]):
                supported = min(pre, 5) in premiums and min(post, 5) in premiums
                # Within the pooled 5+ category the regression cannot distinguish actual counts.
                supported &= pre == post or not (pre >= 5 and post >= 5)
                delta = np.expm1(premiums[min(post, 5)] - premiums[min(pre, 5)]) if supported else np.nan
                revenue = group.Expanded_revenue.sum()
                transitions.append({
                    "Option definition": label, "Model": model,
                    "Pre options": pre, "Post options": post, "Sample records": len(group),
                    "Expanded waybills": group.Expanded_waybills.sum(), "Expanded revenue": revenue,
                    "Q8 broader overlap records": int(group.Q8_overlap.sum()),
                    "Q8 conservative overlap records": int(
                        group.Classification.eq("Matched: conservative UP–NS").sum()),
                    "Modeled payment change fraction": delta, "Modeled payment change": delta * revenue,
                })
    return pd.concat(regressions, ignore_index=True), pd.DataFrame(transitions)


def economic_results(data, anchors, catalog, tolerance, scenario, output_dir):
    q8 = q8_estimates(data)
    q9, transitions = q9_estimates(data, anchors, catalog, tolerance)
    suffix = "baseline" if scenario == "Baseline" else "owner_only"
    for frame, name in [(q8, "q8_payment_scenarios"), (q9, "q9_regressions"),
                        (transitions, "q9_transitions")]:
        frame.to_csv(output_dir / f"{name}_{suffix}.csv", index=False, float_format="%.10g")
