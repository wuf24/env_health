# AMR_AGG_raw_mean baseline comparison

## Generated versions

- `lancet_ets`: Lancet-like ETS baseline.
- `x_driven`: X-driven / Nature-like simplified baseline.

## Core difference

- `lancet_ets`: future baseline comes from ETS on AMR itself, then future R1xday deltas are added.
- `x_driven`: future baseline comes from future covariate paths plugged back into the historical panel model.

## When to look at which version

- Use `lancet_ets` when you want the closest implementation of the Lancet phrase 'baseline scenario continued at current rates, as estimated by ETS models'.
- Use `x_driven` when you want future R1xday paths to play a larger role in shaping future AMR trajectories.

## Current scope

- projection window: `2024-2050`
- only `R1xday` is varied by future scenario at this stage
- comparison should no longer be limited to `main_model`; use `model_role_2050_compare.csv` for the 12-role digest
- national results remain arithmetic means across province-level AMR projections
- the x-driven version is still a simplified Nature-like baseline rather than the full spatiotemporal Bayesian model