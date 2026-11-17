"""Estimate the Question 5 interchange premium from the 2024 STB public file."""

import argparse
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
DATA_MEMBER = "PublicUseWaybillSample2024.txt"
# One-based, inclusive positions from Tables 4-6 and 4-7.
FIELDS = {
    "period": (7, 10),
    "stcc": (36, 40),
    "billed_tons": (41, 47),
    "actual_tons": (48, 54),
    "revenue": (55, 63),
    "rebill": (88, 88),
    "distance": (89, 92),
    "exact_factor": (95, 99),
    "interchanges": (103, 103),
    "routing": (215, 215),
}
TERMS = ["Interchange", "ln(Dist)", "ln(Tons)"]


def read_waybills(archive_path, extra_fields=None, extra_text_fields=()):
    with ZipFile(archive_path) as archive, TemporaryDirectory() as scratch:
        path = Path(scratch) / DATA_MEMBER
        with archive.open(DATA_MEMBER) as source, path.open("wb") as target:
            copyfileobj(source, target)
        if path.stat().st_size % 249:
            raise ValueError("Expected 247 data bytes plus CRLF per record.")
        records = np.memmap(path, dtype="S249", mode="r")
        bytes_by_position = records.view("S1").reshape(-1, 249)
        if not (np.all(bytes_by_position[:, 247] == b"\r")
                and np.all(bytes_by_position[:, 248] == b"\n")):
            raise ValueError("Record delimiters do not match the 2024 release.")
        columns = {}
        for name, (start, end) in (FIELDS | (extra_fields or {})).items():
            field = np.ascontiguousarray(bytes_by_position[:, start - 1:end])
            value = pd.Series(field.view(f"S{end - start + 1}").ravel())
            if name in {"period", "stcc", "routing"} or name in extra_text_fields:
                columns[name] = value.str.decode("ascii").str.strip()
            else:
                columns[name] = pd.to_numeric(value, errors="coerce")
        del bytes_by_position, records
    data = pd.DataFrame(columns)
    if not data["period"].str.fullmatch(r"(0[1-9]|1[0-2])24").all():
        raise ValueError("Expected all accounting periods to be in 2024.")
    data["exact_factor"] /= 100
    return data


def clean_samples(data):
    counts = []

    def retain(label, frame, keep):
        kept = frame.loc[keep]
        counts.append((label, len(frame), len(frame) - len(kept), len(kept)))
        return kept

    counts.append(("Raw records (verified 247 bytes)", len(data), 0, len(data)))
    data = retain("Published STCC is five digits and nonzero", data,
                  data.stcc.str.fullmatch(r"(?!00000)[0-9]{5}", na=False))
    data = retain("Valid number of interchanges (0–9)", data, data.interchanges.between(0, 9))
    data = retain("Routing flag T", data, data.routing.eq("T"))
    data = retain("Positive line-haul revenue", data, data.revenue.gt(0))
    data = retain("Positive estimated short-line miles", data, data.distance.gt(0))
    data = retain("Positive billed tons", data, data.billed_tons.gt(0))
    counts.append(("All otherwise valid records", len(data), 0, len(data)))
    baseline = retain("Baseline restriction: Rebill Code 0", data, data.rebill.eq(0))
    weighted = retain("Baseline sensitivity: positive exact weight", baseline,
                      np.isfinite(baseline.exact_factor) & baseline.exact_factor.gt(0))
    actual = retain("Baseline sensitivity: positive actual tons", baseline,
                    baseline.actual_tons.gt(0))
    return data, baseline, weighted, actual, pd.DataFrame(
        counts, columns=["Step", "Entering", "Excluded at step", "Retained"]
    )


def estimate(data, name, *, tons_column="billed_tons", stcc_digits=5, weighted=False, routing_categories=None):
    group, labels = pd.factorize(data.stcc.str.slice(stop=stcc_digits))
    interline = data.interchanges.gt(0).to_numpy()
    log_distance = np.log(data.distance.to_numpy())
    log_tons = np.log(data[tons_column].to_numpy())
    y = np.log(data.revenue.to_numpy()) - log_distance - log_tons
    if routing_categories is None:
        terms = TERMS
        x = np.column_stack((interline, log_distance, log_tons))
        comparison_count = 1
    else:
        categories = sorted(routing_categories.unique())
        if not categories or categories[0] != 1:
            raise ValueError("The routing regression requires one routing as a reference.")
        comparison_count = len(categories) - 1
        terms = [f"Routings: {k if k < 5 else '5+'}" for k in categories[1:]] + TERMS[1:]
        x = np.column_stack([routing_categories.eq(k) for k in categories[1:]]
                            + [log_distance, log_tons])
    weights = data.exact_factor.to_numpy() if weighted else np.ones(len(data))
    group_weight = np.bincount(group, weights)
    # Project out the intercept and commodity dummies by within-STCC demeaning.
    def demean(values):
        means = np.bincount(group, weights * values) / group_weight
        return values - means[group]

    within_x = np.column_stack([demean(column) for column in x.T])
    within_y = demean(y)
    model = sm.WLS(within_y, within_x, weights=weights) if weighted else sm.OLS(within_y, within_x)
    fit = model.fit(method="qr")
    df = len(y) - len(labels) - len(terms)
    if fit.model.rank != len(terms) or df <= 0:
        raise ValueError(f"{name}: the full fixed-effects model must have full rank.")

    # Conventional covariance uses the residual df of the full dummy regression.
    residuals = fit.wresid
    bread = fit.normalized_cov_params
    conventional = bread * (residuals @ residuals / df)
    # In the full design, leverage is the sum of the STCC and within-X leverages.
    wx = fit.model.wexog
    leverage = weights / group_weight[group] + np.sum((wx @ bread) * wx, axis=1)
    singleton = np.bincount(group)[group] == 1
    # Singleton groups have zero within-group regressors and contribute no slope score.
    score_scale = np.zeros(len(y))
    if np.any(leverage[~singleton] >= 1):
        raise ValueError(f"{name}: unit leverage outside singleton groups.")
    score_scale[~singleton] = residuals[~singleton] / (1 - leverage[~singleton])
    scores = (wx @ bread) * score_scale[:, None]
    robust = scores.T @ scores
    centered = y - np.average(y, weights=weights)
    r_squared = 1 - (residuals @ residuals) / np.dot(weights, centered**2)
    mixed = np.count_nonzero((np.bincount(group, interline) > 0)
                             & (np.bincount(group, ~interline) > 0))

    output = []
    critical = t.ppf(0.975, df)
    for i, term in enumerate(terms):
        beta = fit.params[i]
        row = {
            "Model": name, "Term": term, "Estimate": beta, "Observations": len(y),
            "Interchange observations": int(interline.sum()), "STCC groups": len(labels),
            "STCC groups with both statuses": mixed, "Singleton groups": int(singleton.sum()),
            "Residual df": df, "R-squared": r_squared,
            "Percent difference": 100 * np.expm1(beta) if i < comparison_count else np.nan,
        }
        for label, cov in [("Conventional", conventional), ("HC3", robust)]:
            se = np.sqrt(cov[i, i])
            row[f"{label} SE"] = se
            row[f"{label} p-value"] = 2 * t.sf(abs(beta / se), df)
            row[f"{label} CI lower"] = beta - critical * se
            row[f"{label} CI upper"] = beta + critical * se
            if i < comparison_count:
                row[f"{label} percent CI lower"] = 100 * np.expm1(beta - critical * se)
                row[f"{label} percent CI upper"] = 100 * np.expm1(beta + critical * se)
        output.append(row)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "figures")
    args = parser.parse_args()
    all_valid, baseline, weighted, actual, counts = clean_samples(read_waybills(args.archive))
    runs = [
        estimate(baseline, "Baseline: Rebill Code 0"),
        estimate(all_valid, "All otherwise valid records"),
        estimate(weighted, "Baseline: exact expansion weights", weighted=True),
        estimate(baseline, "Baseline: two-digit STCC", stcc_digits=2),
        estimate(actual, "Actual-ton subset: billed tons"),
        estimate(actual, "Actual-ton subset: actual tons", tons_column="actual_tons"),
    ]
    if len(weighted) != len(baseline):
        runs.append(estimate(weighted, "Exact-weight subset: unweighted"))
    results = pd.DataFrame(row for run in runs for row in run)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    counts.to_csv(args.output_dir / "q5_waybill_sample_cleaning.csv", index=False)
    results.to_csv(args.output_dir / "q5_waybill_regression_table.csv", index=False, float_format="%.10g")
    print(counts.to_string(index=False))
    print(results.loc[results.Term.eq("Interchange"), [
        "Model", "Observations", "Estimate", "Conventional SE", "HC3 SE", "Percent difference",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
