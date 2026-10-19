"""Main experiment: shortest-path length between two hosts in different pods
as a function of the fraction of failed switch-to-switch links.

For every trial t a 64-bit trial seed is drawn from random.Random(--seed).
The trial seed drives one random permutation of the eligible links; failure
rate f fails its first round(f * N) links (see failures.py). Running
    python generate.py --k K --failure-rate f --seed <trial seed>
reproduces exactly the same failed topology as that trial.

Outputs (in --outdir):
    summary.csv      one row per failure rate (metrics + uncertainty)
    trials.csv       one row per (trial, failure rate): the raw BFS result
    run_config.json  the parameters of the run
and the plots produced by plot_results.py.

Example:
    python experiment.py                     # k=8, 500 trials, default rates
    python experiment.py --k 4 --trials 200 --percents 0 10 20 50
"""

import argparse
import csv
import json
import os
import random
import time
from collections import Counter

from bfs import shortest_path_length
from failures import eligible_links, num_links_to_fail, random_failure_order, remove_links
from generate import default_host_pair, parse_host
from stats_utils import mean_with_ci, prob_all_of_m_links_failed, wilson_interval
from topology import build_fat_tree, paper_address, validate_k

DEFAULT_PERCENTS = [0, 1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90]


def run_trials(k, percents, trials, seed, src, dst):
    """Run the Monte-Carlo trials.

    Returns (tree, n_eligible, n_failed per percent, trial seeds, distances)
    where distances[p][t] is the BFS distance in trial t at percent p, or None
    if src and dst are disconnected.
    """
    tree = build_fat_tree(k)
    links = eligible_links(tree)
    n_elig = len(links)
    n_failed = [num_links_to_fail(p / 100.0, n_elig) for p in percents]

    master = random.Random(seed)
    trial_seeds = [master.getrandbits(64) for _ in range(trials)]

    distances = {p: [] for p in percents}
    for trial_seed in trial_seeds:
        order = random_failure_order(links, random.Random(trial_seed))
        for p, n in zip(percents, n_failed):
            adj = remove_links(tree.adj, order[:n])
            distances[p].append(shortest_path_length(adj, src, dst))
    return tree, n_elig, n_failed, trial_seeds, distances


def edge_isolation_probability(k, n_failed, n_elig):
    """P(the source or the destination edge switch loses all k/2 uplinks).

    The two edge switches are in different pods, so their uplink sets are
    disjoint; by inclusion-exclusion
        P(A or B) = 2 P(k/2 given links failed) - P(k given links failed).
    Either event disconnects the hosts, so this is a lower bound on the
    disconnection probability.
    """
    half = k // 2
    return (2 * prob_all_of_m_links_failed(half, n_failed, n_elig)
            - prob_all_of_m_links_failed(k, n_failed, n_elig))


def summarize(k, percents, n_failed, n_elig, distances):
    rows = []
    for p, n in zip(percents, n_failed):
        ds = distances[p]
        connected = [d for d in ds if d is not None]
        lo, hi = wilson_interval(len(connected), len(ds))
        m, s, ci = mean_with_ci(connected)
        rows.append({
            "percent_requested": p,
            "n_failed": n,
            "percent_failed": 100.0 * n / n_elig,
            "trials": len(ds),
            "connected": len(connected),
            "p_connected": len(connected) / len(ds),
            "p_connected_lo95": lo,
            "p_connected_hi95": hi,
            "p_connected_edge_bound": 1.0 - edge_isolation_probability(k, n, n_elig),
            "mean_len": m,
            "std_len": s,
            "mean_len_ci95": ci,
            "min_len": min(connected) if connected else None,
            "max_len": max(connected) if connected else None,
            "length_counts": dict(sorted(Counter(connected).items())),
        })
    return rows


def write_outputs(outdir, config, rows, percents, n_failed, trial_seeds, distances):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "run_config.json"), "w") as f:
        json.dump(config, f, indent=2)

    fields = [key for key in rows[0] if key != "length_counts"] + ["length_counts"]
    with open(os.path.join(outdir, "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            out = dict(r)
            out["length_counts"] = json.dumps({str(d): c for d, c in r["length_counts"].items()})
            w.writerow(out)

    with open(os.path.join(outdir, "trials.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trial", "trial_seed", "percent_requested", "n_failed", "distance"])
        for t, ts in enumerate(trial_seeds):
            for p, n in zip(percents, n_failed):
                d = distances[p][t]
                w.writerow([t, ts, p, n, "" if d is None else d])


def print_table(rows):
    print(f"{'req%':>5} {'failed':>6} {'act%':>6} {'P(conn)':>8} {'95% CI':>15} "
          f"{'edge-bound':>10} {'n_conn':>6} {'mean len':>9} {'+-95%':>6}  length counts")
    for r in rows:
        ci = f"[{r['p_connected_lo95']:.3f},{r['p_connected_hi95']:.3f}]"
        mean = f"{r['mean_len']:.3f}" if r["connected"] else "-"
        half = f"{r['mean_len_ci95']:.3f}" if r["connected"] > 1 else "-"
        print(f"{r['percent_requested']:>5g} {r['n_failed']:>6} {r['percent_failed']:>6.2f} "
              f"{r['p_connected']:>8.3f} {ci:>15} {r['p_connected_edge_bound']:>10.3f} "
              f"{r['connected']:>6} {mean:>9} {half:>6}  {r['length_counts']}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--k", type=int, default=8, help="switch port count (default: 8)")
    p.add_argument("--trials", type=int, default=500,
                   help="independent random trials per failure rate (default: 500)")
    p.add_argument("--percents", type=float, nargs="+", default=DEFAULT_PERCENTS,
                   help="failure percentages of switch-to-switch links to test")
    p.add_argument("--seed", type=int, default=2026, help="master random seed (default: 2026)")
    p.add_argument("--src", help="source host address (default: first host of pod 0)")
    p.add_argument("--dst", help="destination host address (default: last host of pod k-1)")
    p.add_argument("--outdir", default="results", help="output directory (default: results)")
    p.add_argument("--no-plot", action="store_true", help="skip plotting")
    args = p.parse_args(argv)
    try:
        validate_k(args.k)
    except ValueError as exc:
        p.error(str(exc))
    if args.trials < 1:
        p.error("--trials must be >= 1")
    if any(not 0 <= x <= 100 for x in args.percents):
        p.error("--percents must lie in [0, 100]")
    args.percents = [int(x) if float(x).is_integer() else x for x in args.percents]

    src, dst = default_host_pair(args.k)
    try:
        args.src = parse_host(args.src, args.k) if args.src else src
        args.dst = parse_host(args.dst, args.k) if args.dst else dst
    except argparse.ArgumentTypeError as exc:
        p.error(str(exc))
    if args.src[1] == args.dst[1]:
        p.error("--src and --dst must be in different pods")
    return args


def main(argv=None):
    args = parse_args(argv)
    start = time.time()
    tree, n_elig, n_failed, trial_seeds, distances = run_trials(
        args.k, args.percents, args.trials, args.seed, args.src, args.dst)
    rows = summarize(args.k, args.percents, n_failed, n_elig, distances)
    config = {
        "k": args.k,
        "trials": args.trials,
        "seed": args.seed,
        "percents": args.percents,
        "src": paper_address(args.src, args.k),
        "dst": paper_address(args.dst, args.k),
        "eligible_links": n_elig,
        "failure_model": "uniform without replacement over edge-agg and agg-core links; "
                         "n = floor(rate*N + 0.5); nested failure sets within a trial",
    }
    write_outputs(args.outdir, config, rows, args.percents, n_failed, trial_seeds, distances)

    print(f"k={args.k}, {args.trials} trials/rate, seed={args.seed}, "
          f"{config['src']} -> {config['dst']}, {n_elig} eligible links "
          f"({time.time() - start:.1f}s)")
    print_table(rows)

    if not args.no_plot:
        from plot_results import make_plots
        for path in make_plots(args.outdir):
            print(f"wrote {path}")


if __name__ == "__main__":
    main()
