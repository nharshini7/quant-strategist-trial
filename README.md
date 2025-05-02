## Overview of the project

This project implements a Smart Order Router based on the static cost model from Cont & Kukanov (2014). This router splits a 5,000-share buy order across multiple venues, using a brute-force allocator to minimize execution cost under queue and fill-risk penalties.

## Files executed and the output

- `backtest.py`: Main script that:
  - Implements the allocator as per provided pseudocode
  - Replays a market snapshot stream from `l1_day.csv`
  - Tunes risk parameters (`lambda_over`, `lambda_under`, `theta_queue`)
  - Benchmarks against Best Ask, TWAP, and VWAP
  - Outputs results as a JSON summary
  - Plots cumulative fill cost to `results.png`

- `results.png`: Plot showing cumulative cost vs shares filled.

## Parameter Search

A simple grid search is used over the following values:

- `lambda_over` ∈ {0.1, 1.0}
- `lambda_under` ∈ {0.1, 1.0}
- `theta_queue` ∈ {0.1, 1.0}

The best parameter set is selected based on lowest total execution cost.

## Metrics Reported in the project

- Total and average fill price for:
  - Optimal allocation
  - Best Ask
  - TWAP (time-weighted average price)
  - VWAP (volume-weighted average price)
- Savings vs each baseline in basis points (bps)

## Suggested Improvement 

The current model assumes static queue risk and immediate fills up to posted depth. A future improvement could involve:
> Modeling queue position and order priority decay, which would account for the likelihood of getting filled based on relative depth and market activity, improving realism.

## How to Run

python backtest.py

- Requires only: `numpy`, `pandas`, `matplotlib`, and Python 3.8+
- Outputs JSON results and `results.png` to the local directory

## Submission Notes

This repository includes:

- ✅ `backtest.py` (standalone, efficient)
- ✅ `README.md` (this file)
- ✅ `results.png` (optional visualization)
