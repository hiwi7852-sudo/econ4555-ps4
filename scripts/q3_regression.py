"""Fit the Question 3 pooled railroad cost regression and export its results."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[1]
OUTCOME = "l_totcosts"
PREDICTORS = ["l_tonmiles", "l_netsize", "l_pdiesel", "l_wage"]
LABELS = ["Intercept", "ln(tonmiles)", "ln(netsize)", "ln(pdiesel)", "ln(wage)"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "RR1.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "figures" / "q3_regression_table.csv")
    args = parser.parse_args()

    data = pd.read_csv(args.data)
    print(f"Input: {len(data)} rows, {len(data.columns)} columns, "
          f"{data['rr'].nunique()} railroads, {data['year'].min()}–{data['year'].max()}")
    print(f"Observations by year: {data.groupby('year').size().to_dict()}")
    print(f"Duplicate railroad-year rows: {data.duplicated(['rr', 'year']).sum()}")
    print(f"Missing values by column: {data.isna().sum().to_dict()}")

    terms = [OUTCOME, *PREDICTORS]
    sample = data[terms].dropna()
    print(f"Rows excluded for missing regression values: {len(data) - len(sample)}")
    # Confirm the supplied logs agree with their level columns up to CSV rounding.
    for term in terms:
        levels = data.loc[sample.index, term.removeprefix("l_")]
        if not np.allclose(sample[term], np.log(levels), rtol=0, atol=2e-6):
            raise ValueError(f"{term} does not match the natural log of its level column.")

    design = sm.add_constant(sample[PREDICTORS], has_constant="add")
    fit = sm.OLS(sample[OUTCOME], design, missing="raise").fit(cov_type="nonrobust")
    # The least-favorable null for a lower-tail test of beta >= 1 is beta = 1.
    density_t = (fit.params["l_tonmiles"] - 1) / fit.bse["l_tonmiles"]
    density_p = t.cdf(density_t, df=fit.df_resid)

    coefficients = pd.DataFrame({
        "Term": LABELS,
        "Estimate or value": fit.params.to_numpy(),
        "Standard error": fit.bse.to_numpy(),
        "t-statistic": fit.tvalues.to_numpy(),
        "p-value": fit.pvalues.to_numpy(),
    })
    summary = pd.DataFrame([
        {"Term": "R-squared", "Estimate or value": fit.rsquared},
        {"Term": "Observations", "Estimate or value": int(fit.nobs)},
        {"Term": "Residual degrees of freedom", "Estimate or value": int(fit.df_resid)},
        {"Term": "Density test (H1: ton-mile elasticity < 1)",
         "t-statistic": density_t, "p-value": density_p},
    ])
    table = pd.concat([coefficients, summary], ignore_index=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False, float_format="%.10g")
    print(table.to_string(index=False, na_rep="", float_format=lambda x: f"{x:.8g}"))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
