"""Structural checks of the fat-tree against the paper (Sec. 2.2, Fig. 3)."""

import unittest
from collections import Counter

from bfs import bfs_distances, shortest_path_length
from topology import (AGG, CORE, EDGE, HOST, build_fat_tree, expected_counts,
                      link_kind, paper_address, validate_k)

KS = [2, 4, 6, 8, 10, 16]


def count_shortest_paths(adj, src, dst):
    """Number of distinct shortest src-dst paths (BFS layer counting)."""
    dist = bfs_distances(adj, src)
    ways = {src: 1}
    for node in sorted(dist, key=dist.get):
        for nb in adj[node]:
            if dist.get(nb) == dist[node] + 1:
                ways[nb] = ways.get(nb, 0) + ways[node]
    return ways.get(dst, 0)


class TestCounts(unittest.TestCase):
    def test_node_and_link_counts(self):
        for k in KS:
            with self.subTest(k=k):
                tree = build_fat_tree(k)
                exp = expected_counts(k)
                tiers = Counter(n[0] for n in tree.adj)
                self.assertEqual(tiers[HOST], exp["hosts"])
                self.assertEqual(tiers[HOST], k ** 3 // 4)
                self.assertEqual(tiers[EDGE], exp["edge"])
                self.assertEqual(tiers[AGG], exp["agg"])
                self.assertEqual(tiers[CORE], (k // 2) ** 2)
                self.assertEqual(tiers[EDGE] + tiers[AGG] + tiers[CORE], 5 * k * k // 4)
                kinds = Counter(link_kind(l) for l in tree.links)
                for kind in ("host-edge", "edge-agg", "agg-core"):
                    self.assertEqual(kinds[kind], k ** 3 // 4)
                self.assertEqual(len(tree.links), 3 * k ** 3 // 4)

    def test_pods(self):
        for k in KS:
            with self.subTest(k=k):
                tree = build_fat_tree(k)
                pods = {n[1] for n in tree.adj if n[0] != CORE}
                self.assertEqual(pods, set(range(k)))
                for pod in range(k):
                    self.assertEqual(sum(1 for n in tree.nodes(EDGE) if n[1] == pod), k // 2)
                    self.assertEqual(sum(1 for n in tree.nodes(AGG) if n[1] == pod), k // 2)
                    self.assertEqual(sum(1 for n in tree.nodes(HOST) if n[1] == pod), k * k // 4)

    def test_links_are_simple_and_consistent(self):
        for k in KS:
            with self.subTest(k=k):
                tree = build_fat_tree(k)
                canon = {frozenset(l) for l in tree.links}
                self.assertEqual(len(canon), len(tree.links), "duplicate link")
                self.assertTrue(all(u != v for u, v in tree.links), "self loop")
                # adjacency list and link list describe the same graph
                self.assertEqual(sum(len(nb) for nb in tree.adj.values()), 2 * len(tree.links))
                for u, v in tree.links:
                    self.assertIn(v, tree.adj[u])
                    self.assertIn(u, tree.adj[v])

    def test_degrees(self):
        for k in KS:
            with self.subTest(k=k):
                tree = build_fat_tree(k)
                for node, nbrs in tree.adj.items():
                    if node[0] == HOST:
                        self.assertEqual(len(nbrs), 1)
                    else:
                        self.assertEqual(len(nbrs), k, node)

    def test_invalid_k(self):
        for bad in (0, 1, 3, 7, -4):
            with self.assertRaises(ValueError):
                validate_k(bad)
        for bad in (4.0, "4", True):
            with self.assertRaises(TypeError):
                validate_k(bad)


class TestWiring(unittest.TestCase):
    def test_edge_and_host_wiring(self):
        for k in KS:
            with self.subTest(k=k):
                tree = build_fat_tree(k)
                half = k // 2
                for (_, pod, e, h) in tree.nodes(HOST):
                    self.assertEqual(tree.adj[(HOST, pod, e, h)], {(EDGE, pod, e)})
                for (_, pod, e) in tree.nodes(EDGE):
                    up = {n for n in tree.adj[(EDGE, pod, e)] if n[0] == AGG}
                    self.assertEqual(up, {(AGG, pod, a) for a in range(half)})

    def test_core_connectivity(self):
        for k in KS:
            with self.subTest(k=k):
                tree = build_fat_tree(k)
                half = k // 2
                for core in tree.nodes(CORE):
                    _, j, i = core
                    nbrs = tree.adj[core]
                    # one port per pod, always to aggregation switch j-1
                    self.assertEqual(nbrs, {(AGG, pod, j - 1) for pod in range(k)})
                for (_, pod, a) in tree.nodes(AGG):
                    cores = {n for n in tree.adj[(AGG, pod, a)] if n[0] == CORE}
                    # k/2 consecutive cores (stride a of size k/2)
                    self.assertEqual(cores, {(CORE, a + 1, i) for i in range(1, half + 1)})
                # every pair of pods is joined through every core switch
                for core in tree.nodes(CORE):
                    self.assertEqual(len({n[1] for n in tree.adj[core]}), k)

    def test_figure3_k4(self):
        """Links visible in Figure 3 of the paper (k = 4), by IP-style name."""
        tree = build_fat_tree(4)
        named = {frozenset((paper_address(u, 4), paper_address(v, 4))) for u, v in tree.links}
        for a, b in [("10.0.2.1", "10.4.1.1"), ("10.0.2.1", "10.4.1.2"),
                     ("10.0.3.1", "10.4.2.1"), ("10.0.3.1", "10.4.2.2"),
                     ("10.2.2.1", "10.4.1.1"), ("10.0.1.1", "10.0.2.1"),
                     ("10.0.1.1", "10.0.1.2"), ("10.2.0.1", "10.2.0.3")]:
            self.assertIn(frozenset((a, b)), named)
        self.assertNotIn(frozenset(("10.0.2.1", "10.4.2.1")), named)
        # The dashed path of Fig. 3: 10.0.1.2 -> 10.2.0.3 is 6 hops.
        src, dst = (HOST, 0, 1, 0), (HOST, 2, 0, 1)
        self.assertEqual(paper_address(src, 4), "10.0.1.2")
        self.assertEqual(paper_address(dst, 4), "10.2.0.3")
        self.assertEqual(shortest_path_length(tree.adj, src, dst), 6)


class TestDistances(unittest.TestCase):
    def expected_distance(self, a, b):
        if a == b:
            return 0
        if a[1:3] == b[1:3]:
            return 2  # same edge switch
        if a[1] == b[1]:
            return 4  # same pod, different edge
        return 6      # different pods

    def test_intact_graph_connected(self):
        for k in KS:
            with self.subTest(k=k):
                tree = build_fat_tree(k)
                host = tree.nodes(HOST)[0]
                self.assertEqual(len(bfs_distances(tree.adj, host)), len(tree.adj))

    def test_all_host_pairs_k4_and_k6(self):
        for k in (4, 6):
            tree = build_fat_tree(k)
            hosts = tree.nodes(HOST)
            for a in hosts:
                dist = bfs_distances(tree.adj, a)
                for b in hosts:
                    self.assertEqual(dist[b], self.expected_distance(a, b), (k, a, b))

    def test_selected_pairs_k8(self):
        tree = build_fat_tree(8)
        cases = [((HOST, 0, 0, 0), (HOST, 0, 0, 3), 2),
                 ((HOST, 0, 0, 0), (HOST, 0, 3, 0), 4),
                 ((HOST, 0, 0, 0), (HOST, 7, 3, 3), 6),
                 ((HOST, 3, 1, 2), (HOST, 4, 1, 2), 6)]
        for a, b, d in cases:
            self.assertEqual(shortest_path_length(tree.adj, a, b), d)

    def test_number_of_shortest_paths(self):
        """(k/2)^2 shortest paths between pods (paper: 576 for k = 48), k/2 inside a pod."""
        for k in (4, 6, 8):
            with self.subTest(k=k):
                tree = build_fat_tree(k)
                a = (HOST, 0, 0, 0)
                self.assertEqual(count_shortest_paths(tree.adj, a, (HOST, 1, 0, 0)), (k // 2) ** 2)
                self.assertEqual(count_shortest_paths(tree.adj, a, (HOST, 0, 1, 0)), k // 2)
                self.assertEqual(count_shortest_paths(tree.adj, a, (HOST, 0, 0, 1)), 1)


if __name__ == "__main__":
    unittest.main()
