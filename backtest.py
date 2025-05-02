import pandas as pd
import numpy as np
import itertools
import json
import matplotlib.pyplot as plt

ORDER_SIZE = 5000
STEP_SIZE = 100

# Cost model from pseudocode
def compute_cost(split, venues, order_size, lambda_over, lambda_under, theta_queue):
    executed = 0
    cash_spent = 0.0
    for i in range(len(venues)):
        exe = min(split[i], venues[i]['ask_size'])
        executed += exe
        cash_spent += exe * (venues[i]['ask'] + venues[i]['fee'])
        rebate = max(split[i] - exe, 0) * venues[i]['rebate']
        cash_spent -= rebate

    underfill = max(order_size - executed, 0)
    overfill = max(executed - order_size, 0)
    risk_penalty = theta_queue * (underfill + overfill)
    cost_penalty = lambda_under * underfill + lambda_over * overfill
    return cash_spent + risk_penalty + cost_penalty


def allocate(order_size, venues, lambda_over, lambda_under, theta_queue):
    splits = [[]]
    for v in range(len(venues)):
        new_splits = []
        for alloc in splits:
            used = sum(alloc)
            max_v = min(order_size - used, venues[v]['ask_size'])
            for q in range(0, max_v + 1, STEP_SIZE):
                new_splits.append(alloc + [q])
        splits = new_splits

    best_cost = float('inf')
    best_split = []
    for alloc in splits:
        if sum(alloc) != order_size:
            continue
        cost = compute_cost(alloc, venues, order_size, lambda_over, lambda_under, theta_queue)
        if cost < best_cost:
            best_cost = cost
            best_split = alloc
    return best_split, best_cost


def get_snapshots(df):
    df = df.sort_values(by='ts_event')
    df = df.drop_duplicates(subset=['ts_event', 'publisher_id'], keep='first')
    snapshots = df.groupby('ts_event')
    return snapshots


def baseline_best_ask(snapshots):
    remaining = ORDER_SIZE
    total_cost = 0
    for _, snap in snapshots:
        best_row = snap.loc[snap['ask_px_00'].idxmin()]
        fill = min(remaining, best_row['ask_sz_00'])
        total_cost += fill * best_row['ask_px_00']
        remaining -= fill
        if remaining <= 0:
            break
    return total_cost, ORDER_SIZE - remaining


def baseline_twap(snapshots):
    slices = list(snapshots)
    slice_shares = ORDER_SIZE // len(slices)
    remaining = ORDER_SIZE
    total_cost = 0
    for _, snap in slices:
        fill = 0
        for _, row in snap.iterrows():
            qty = min(slice_shares - fill, row['ask_sz_00'])
            total_cost += qty * row['ask_px_00']
            fill += qty
            remaining -= qty
            if fill >= slice_shares or remaining <= 0:
                break
        if remaining <= 0:
            break
    return total_cost, ORDER_SIZE - remaining


def baseline_vwap(snapshots):
    remaining = ORDER_SIZE
    total_cost = 0
    for _, snap in snapshots:
        total_size = snap['ask_sz_00'].sum()
        if total_size == 0:
            continue
        for _, row in snap.iterrows():
            weight = row['ask_sz_00'] / total_size
            qty = min(int(weight * ORDER_SIZE), row['ask_sz_00'], remaining)
            total_cost += qty * row['ask_px_00']
            remaining -= qty
            if remaining <= 0:
                break
        if remaining <= 0:
            break
    return total_cost, ORDER_SIZE - remaining


def run_backtest(snapshots, param_grid):
    best_params = None
    best_total_cost = float('inf')
    best_cumulative = []

    for lambda_over, lambda_under, theta_queue in param_grid:
        remaining = ORDER_SIZE
        total_cost = 0
        cumulative_cost = []
        filled = 0
        for _, snap in snapshots:
            venues = [
                {'ask': row['ask_px_00'], 'ask_size': row['ask_sz_00'], 'fee': 0.0, 'rebate': 0.0}
                for _, row in snap.iterrows()
            ]
            alloc, _ = allocate(remaining, venues, lambda_over, lambda_under, theta_queue)
            for i, (row, alloc_qty) in enumerate(zip(snap.itertuples(), alloc)):
                qty = min(alloc_qty, getattr(row, 'ask_sz_00'))
                if qty > 0:
                    total_cost += qty * getattr(row, 'ask_px_00')
                    remaining -= qty
                    filled += qty
                    cumulative_cost.append((filled, total_cost))
                if remaining <= 0:
                    break
            if remaining <= 0:
                break

        if total_cost < best_total_cost:
            best_total_cost = total_cost
            best_params = (lambda_over, lambda_under, theta_queue)
            best_cumulative = cumulative_cost

    return best_params, best_total_cost, best_cumulative


def plot_cumulative_cost(cumulative):
    filled, cost = zip(*cumulative)
    plt.figure(figsize=(10, 6))
    plt.plot(filled, cost, marker='o')
    plt.title('Cumulative Cost Over Fills')
    plt.xlabel('Shares Filled')
    plt.ylabel('Cumulative Cost ($)')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('results.png')


if __name__ == '__main__':
    df = pd.read_csv('l1_day.csv')
    snapshots = get_snapshots(df)

    # Parameter grid search
    search_grid = list(itertools.product([0.1, 1.0], [0.1, 1.0], [0.1, 1.0]))
    best_params, best_cost, best_cumulative = run_backtest(snapshots, search_grid)

    # Plot cumulative cost
    plot_cumulative_cost(best_cumulative)

    # Baselines
    ba_cost, ba_filled = baseline_best_ask(snapshots)
    twap_cost, twap_filled = baseline_twap(snapshots)
    vwap_cost, vwap_filled = baseline_vwap(snapshots)

    result = {
        "best_params": {
            "lambda_over": best_params[0],
            "lambda_under": best_params[1],
            "theta_queue": best_params[2],
        },
        "allocator": {
            "total_cash_spent": best_cost,
            "avg_fill_price": best_cost / ORDER_SIZE
        },
        "baseline_best_ask": {
            "total_cash_spent": ba_cost,
            "avg_fill_price": ba_cost / ba_filled
        },
        "baseline_twap": {
            "total_cash_spent": twap_cost,
            "avg_fill_price": twap_cost / twap_filled if twap_filled else None
        },
        "baseline_vwap": {
            "total_cash_spent": vwap_cost,
            "avg_fill_price": vwap_cost / vwap_filled if vwap_filled else None
        },
        "savings_vs_baselines_bps": {
            "best_ask": 10000 * (1 - best_cost / ba_cost),
            "twap": 10000 * (1 - best_cost / twap_cost) if twap_cost else None,
            "vwap": 10000 * (1 - best_cost / vwap_cost) if vwap_cost else None
        }
    }

    print(json.dumps(result, indent=2))
