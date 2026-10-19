"""Canonical k-ary fat-tree topology (Al-Fares et al., SIGCOMM 2008, Section 2.2).

The network is an undirected graph stored as an adjacency list:
    adj[node] -> set of neighbouring nodes

Node identifiers are tuples whose first element is the tier:
    ("host", pod, e, h)   host h attached to edge switch e of pod `pod`
    ("edge", pod, e)      edge (lower-layer) switch e of pod `pod`
    ("agg",  pod, a)      aggregation (upper-layer) switch a of pod `pod`
    ("core", j, i)        core switch at position (j, i) of the (k/2) x (k/2) grid

with pod in [0, k-1], e, h, a in [0, k/2 - 1] and j, i in [1, k/2]
(the paper's 1-based core grid coordinates).
"""

from dataclasses import dataclass

HOST, EDGE, AGG, CORE = "host", "edge", "agg", "core"


def validate_k(k):
    """A fat-tree needs an even port count k >= 2."""
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an integer, got {k!r}")
    if k < 2 or k % 2 != 0:
        raise ValueError(f"k must be an even integer >= 2, got {k}")


@dataclass
class FatTree:
    k: int
    adj: dict    # node -> set of neighbours
    links: list  # every undirected link exactly once, as (u, v), in build order

    def nodes(self, tier):
        """All nodes of one tier, in deterministic (build) order."""
        return [n for n in self.adj if n[0] == tier]


def build_fat_tree(k):
    """Build the canonical k-ary fat-tree of the paper.

    Per pod: k/2 edge and k/2 aggregation switches. Each edge switch has
    k/2 hosts below it and is connected to every aggregation switch of its
    pod (complete bipartite graph inside the pod).

    Core wiring (paper, Sec. 2.2 / Fig. 3): there are (k/2)^2 core switches.
    Port p of every core switch goes to pod p, and the k/2 core-facing ports
    of an aggregation switch go to k/2 consecutive core switches. Numbering
    the cores row by row, aggregation switch a of every pod connects to the
    a-th block ("stride") of k/2 cores, i.e. to core (j = a + 1, i) for
    i = 1..k/2.  Example (k = 4): aggregation 10.0.2.1 -> cores 10.4.1.1 and
    10.4.1.2, exactly as drawn in Figure 3.
    """
    validate_k(k)
    half = k // 2
    adj = {}
    links = []

    def add_node(n):
        adj[n] = set()

    def add_link(u, v):
        adj[u].add(v)
        adj[v].add(u)
        links.append((u, v))

    for j in range(1, half + 1):
        for i in range(1, half + 1):
            add_node((CORE, j, i))

    for pod in range(k):
        for s in range(half):
            add_node((EDGE, pod, s))
            add_node((AGG, pod, s))

        # Hosts <-> edge switches.
        for e in range(half):
            for h in range(half):
                host = (HOST, pod, e, h)
                add_node(host)
                add_link((EDGE, pod, e), host)

        # Edge <-> aggregation: complete bipartite inside the pod.
        for e in range(half):
            for a in range(half):
                add_link((EDGE, pod, e), (AGG, pod, a))

        # Aggregation <-> core: aggregation a uses core row j = a + 1.
        for a in range(half):
            for i in range(1, half + 1):
                add_link((AGG, pod, a), (CORE, a + 1, i))

    return FatTree(k=k, adj=adj, links=links)


def link_kind(link):
    """'host-edge', 'edge-agg' or 'agg-core' for a link (u, v)."""
    tiers = {link[0][0], link[1][0]}
    if tiers == {HOST, EDGE}:
        return "host-edge"
    if tiers == {EDGE, AGG}:
        return "edge-agg"
    if tiers == {AGG, CORE}:
        return "agg-core"
    raise ValueError(f"not a fat-tree link: {link}")


def is_switch_link(link):
    """True for switch-to-switch links (edge-agg and agg-core)."""
    return HOST not in (link[0][0], link[1][0])


def expected_counts(k):
    """Closed-form sizes of the k-ary fat-tree (paper, Sec. 2.2)."""
    validate_k(k)
    half = k // 2
    return {
        "pods": k,
        "hosts": k ** 3 // 4,
        "edge": k * half,
        "agg": k * half,
        "core": half ** 2,
        "switches": 5 * k ** 2 // 4,
        "host-edge links": k ** 3 // 4,
        "edge-agg links": k ** 3 // 4,
        "agg-core links": k ** 3 // 4,
        "links": 3 * k ** 3 // 4,
    }


def paper_address(node, k):
    """The paper's IP-style name of a node (Sec. 3.2), valid for k < 256."""
    half = k // 2
    tier = node[0]
    if tier == HOST:
        _, pod, e, h = node
        return f"10.{pod}.{e}.{h + 2}"
    if tier == EDGE:
        _, pod, e = node
        return f"10.{pod}.{e}.1"
    if tier == AGG:
        _, pod, a = node
        return f"10.{pod}.{half + a}.1"
    if tier == CORE:
        _, j, i = node
        return f"10.{k}.{j}.{i}"
    raise ValueError(f"unknown node {node!r}")
