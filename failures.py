"""Random link-failure model.

Only switch-to-switch links (edge-agg and agg-core) are eligible to fail;
host-edge links are never failed. For a failure rate f and N eligible links,
exactly n = round_half_up(f * N) distinct links are chosen uniformly at random
without replacement and removed. Nodes are never removed.

Mechanism: one random permutation of the eligible links (the "failure order")
is drawn per trial, and a failure rate f fails its first n links. The first n
elements of a uniform random permutation form a uniform random n-subset, so
this is exactly "n links uniformly without replacement". Re-using one
permutation for several rates makes the failure sets nested (a link that is
down at 10% is also down at 20% in the same trial).
"""

import math

from topology import is_switch_link


def validate_rate(rate):
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        raise TypeError(f"failure rate must be a number, got {rate!r}")
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"failure rate must be a fraction in [0, 1], got {rate}")


def num_links_to_fail(rate, n_eligible):
    """Number of links to fail: nearest integer to rate * n_eligible, ties up."""
    validate_rate(rate)
    return min(n_eligible, math.floor(rate * n_eligible + 0.5))


def eligible_links(tree):
    """Switch-to-switch links of the tree, in deterministic build order."""
    return [link for link in tree.links if is_switch_link(link)]


def random_failure_order(links, rng):
    """A uniformly random permutation of `links` drawn from `rng`."""
    return rng.sample(links, len(links))


def remove_links(adj, failed):
    """Copy of `adj` without the `failed` links. All nodes are kept."""
    new_adj = {node: set(nbrs) for node, nbrs in adj.items()}
    for u, v in failed:
        new_adj[u].remove(v)
        new_adj[v].remove(u)
    return new_adj


def fail_random_links(tree, rate, rng):
    """Fail round(rate * N) random eligible links.

    Returns (failed_adj, failed_links). The original tree is not modified.
    """
    links = eligible_links(tree)
    n = num_links_to_fail(rate, len(links))
    failed = random_failure_order(links, rng)[:n]
    return remove_links(tree.adj, failed), failed
