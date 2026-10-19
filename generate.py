"""Generate a k-ary fat-tree, optionally fail random links, and report on it.

Examples:
    python generate.py --k 4
    python generate.py --k 8 --failure-percent 10 --seed 7
    python generate.py --k 8 --failure-rate 0.1 --seed 7 --src 10.0.0.2 --dst 10.5.1.3
    python generate.py --k 4 --failure-percent 25 --edges-out topo.txt --show-failed
"""

import argparse
import random
from collections import Counter

from bfs import bfs_distances, shortest_path_length
from failures import eligible_links, fail_random_links
from topology import (EDGE, HOST, build_fat_tree, expected_counts, link_kind,
                      paper_address, validate_k)


def default_host_pair(k):
    """First host of pod 0 and last host of pod k-1 (different pods)."""
    half = k // 2
    return (HOST, 0, 0, 0), (HOST, k - 1, half - 1, half - 1)


def parse_host(address, k):
    """Parse a paper-style host address 10.pod.edge.id (id in [2, k/2+1])."""
    half = k // 2
    try:
        ten, pod, e, hid = (int(x) for x in address.split("."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad host address {address!r}")
    if ten != 10 or not (0 <= pod < k and 0 <= e < half and 2 <= hid <= half + 1):
        raise argparse.ArgumentTypeError(
            f"{address!r} is not a host of the k={k} fat-tree "
            f"(expected 10.<pod 0..{k-1}>.<edge 0..{half-1}>.<id 2..{half+1}>)")
    return (HOST, pod, e, hid - 2)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--k", type=int, default=4,
                   help="switch port count; even integer >= 2 (default: 4)")
    rate = p.add_mutually_exclusive_group()
    rate.add_argument("--failure-rate", type=float,
                      help="fraction of switch-to-switch links to fail, in [0, 1]")
    rate.add_argument("--failure-percent", type=float,
                      help="same, as a percentage in [0, 100]")
    p.add_argument("--seed", type=int, default=0,
                   help="random seed for the link failures (default: 0)")
    p.add_argument("--src", help="source host, e.g. 10.0.0.2 (default: first host of pod 0)")
    p.add_argument("--dst", help="destination host (default: last host of pod k-1)")
    p.add_argument("--edges-out", metavar="PATH",
                   help="write the surviving links as an edge list to PATH")
    p.add_argument("--show-failed", action="store_true",
                   help="print every failed link")
    args = p.parse_args(argv)

    try:
        validate_k(args.k)
    except ValueError as exc:
        p.error(str(exc))
    if args.failure_percent is not None:
        args.failure_rate = args.failure_percent / 100.0
    if args.failure_rate is None:
        args.failure_rate = 0.0
    if not 0.0 <= args.failure_rate <= 1.0:
        p.error("failure rate must be in [0, 1] (or percent in [0, 100])")

    src, dst = default_host_pair(args.k)
    try:
        args.src = parse_host(args.src, args.k) if args.src else src
        args.dst = parse_host(args.dst, args.k) if args.dst else dst
    except argparse.ArgumentTypeError as exc:
        p.error(str(exc))
    return args


def main(argv=None):
    args = parse_args(argv)
    k = args.k
    tree = build_fat_tree(k)
    expected = expected_counts(k)
    addr = lambda n: paper_address(n, k)

    print(f"k = {k} fat-tree")
    tiers = Counter(n[0] for n in tree.adj)
    for tier, key in (("host", "hosts"), ("edge", "edge"), ("agg", "agg"), ("core", "core")):
        print(f"  {tier:5s} nodes : {tiers[tier]:6d}   (expected {expected[key]})")
    kinds = Counter(link_kind(l) for l in tree.links)
    for kind in ("host-edge", "edge-agg", "agg-core"):
        print(f"  {kind:9s} links: {kinds[kind]:6d}   (expected {expected[kind + ' links']})")
    switch_degrees = {len(nb) for n, nb in tree.adj.items() if n[0] != HOST}
    print(f"  switch degrees (intact): {sorted(switch_degrees)}")

    rng = random.Random(args.seed)
    adj, failed = fail_random_links(tree, args.failure_rate, rng)
    n_elig = len(eligible_links(tree))
    print(f"\nFailures: requested rate {args.failure_rate:.4g}, seed {args.seed}")
    print(f"  eligible (switch-switch) links: {n_elig}")
    print(f"  failed links: {len(failed)}  (= {100 * len(failed) / n_elig:.2f}% of eligible)")
    print(f"  failed by kind: {dict(Counter(link_kind(l) for l in failed))}")
    if args.show_failed:
        for u, v in failed:
            print(f"    {addr(u):>12s} -- {addr(v):<12s} ({link_kind((u, v))})")

    hosts = tree.nodes(HOST)
    reach = bfs_distances(adj, args.src)
    n_reach = sum(1 for h in hosts if h in reach)
    isolated_edges = [n for n in tree.nodes(EDGE) if len(adj[n]) == k // 2]
    print(f"  edge switches with no uplink left: {len(isolated_edges)}")
    print(f"  hosts reachable from {addr(args.src)}: {n_reach} / {len(hosts)}")

    d = shortest_path_length(adj, args.src, args.dst)
    result = "disconnected" if d is None else f"{d} hops"
    print(f"\nShortest path {addr(args.src)} -> {addr(args.dst)}: {result}")

    if args.edges_out:
        with open(args.edges_out, "w") as f:
            f.write(f"# k={k} failure_rate={args.failure_rate} seed={args.seed}\n")
            f.write("# u v kind\n")
            failed_set = set(failed)
            for link in tree.links:
                if link not in failed_set:
                    f.write(f"{addr(link[0])} {addr(link[1])} {link_kind(link)}\n")
        print(f"Surviving links written to {args.edges_out}")


if __name__ == "__main__":
    main()
